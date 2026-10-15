# -*- coding: utf-8 -*-
"""仓储与库存接口：仓库、库位、库存查询、出入库、调拨、调整、盘点。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups, inventory_out
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import apply_own_enterprise, enterprise_scope_ids, is_unrestricted, resolve_own_enterprise
from app.models.enterprise import Enterprise, Park
from app.models.org import User
from app.models.product import Inventory, Product, StockMove, StorageLocation, Warehouse
from app.schemas.stock import (
    InventoryCheckIn,
    InventoryCheckResult,
    InventoryOut,
    InventorySummaryOut,
    LocationIn,
    LocationOut,
    StockAdjustIn,
    StockInIn,
    StockMoveOut,
    StockOutIn,
    StockTransferIn,
    WarehouseIn,
    WarehouseOut,
    WarehouseUpdate,
)
from app.services import integration
from app.services.inventory_service import (
    adjust,
    assert_location_belongs,
    dec,
    inventory_check,
    inventory_summary,
    low_stock_products,
    q3,
    stock_in,
    stock_out,
    transfer,
    warehouse_overview,
)
from app.services.numbering import next_no

router = APIRouter(tags=["库存仓储"])


# --------------------------------------------------------------------------- 仓库


def _assert_warehouse_visible(db: Session, user: User, warehouse: Warehouse) -> None:
    if is_unrestricted(user):
        return
    allowed = set(enterprise_scope_ids(db, user) or [])
    if warehouse.enterprise_id not in allowed:
        raise Forbidden("无权操作该仓库")


@router.get("/warehouses", response_model=ApiResponse[List[WarehouseOut]], summary="仓库列表")
def list_warehouses(
    enterprise_id: Optional[int] = None,
    park_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:read")),
) -> dict:
    query = db.query(Warehouse)
    if enterprise_id:
        query = query.filter(Warehouse.enterprise_id == enterprise_id)
    if park_id:
        query = query.filter(Warehouse.park_id == park_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Warehouse.name.like(like), Warehouse.code.like(like)))
    query = apply_own_enterprise(query, Warehouse, user, "enterprise_id", db)
    ids = [w.id for w in query.all()] or [-1]
    scope = None if is_unrestricted(user) else enterprise_scope_ids(db, user)
    rows = [row for row in warehouse_overview(db, scope) if row["id"] in set(ids)]
    return ok(rows)


@router.post("/warehouses", response_model=ApiResponse[WarehouseOut], summary="创建仓库")
def create_warehouse(
    payload: WarehouseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:write")),
) -> dict:
    enterprise_id = resolve_own_enterprise(user, payload.enterprise_id)
    if not db.get(Enterprise, enterprise_id):
        raise BadRequest("归属企业不存在")
    if payload.park_id and not db.get(Park, payload.park_id):
        raise BadRequest("园区不存在")
    code = payload.code or next_no(db, "warehouse", f"GZ-WH-{date.today().year}")
    if db.query(Warehouse).filter(Warehouse.code == code).first():
        raise Conflict(f"仓库编码已存在：{code}")
    data = payload.model_dump(exclude={"code", "enterprise_id"})
    warehouse = Warehouse(code=code, enterprise_id=enterprise_id, **data)
    db.add(warehouse)
    db.flush()
    return ok(
        {
            "id": warehouse.id,
            "code": warehouse.code,
            "name": warehouse.name,
            "enterprise_id": warehouse.enterprise_id,
            "park_id": warehouse.park_id,
            "address": warehouse.address,
            "warehouse_type": warehouse.warehouse_type,
            "contact_name": warehouse.contact_name,
            "contact_phone": warehouse.contact_phone,
            "capacity": float(dec(warehouse.capacity)),
            "status": warehouse.status,
            "remark": warehouse.remark,
            "location_count": 0,
            "inventory_quantity": 0.0,
        }
    )


@router.get("/warehouses/{warehouse_id}", response_model=ApiResponse[WarehouseOut], summary="仓库详情")
def get_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:read")),
) -> dict:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    rows = warehouse_overview(db, None)
    for row in rows:
        if row["id"] == warehouse_id:
            return ok(row)
    raise NotFound("仓库不存在")


@router.put("/warehouses/{warehouse_id}", response_model=ApiResponse[dict], summary="更新仓库")
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:write")),
) -> dict:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)
    db.flush()
    return ok({"id": warehouse.id, "name": warehouse.name, "updated": True})


@router.delete("/warehouses/{warehouse_id}", response_model=ApiResponse[dict], summary="删除仓库")
def delete_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:write")),
) -> dict:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    if db.query(Inventory).filter(
        Inventory.warehouse_id == warehouse_id, Inventory.quantity > 0
    ).count():
        raise Conflict("该仓库仍有库存，无法删除")
    if db.query(StockMove).filter(StockMove.warehouse_id == warehouse_id).count():
        raise Conflict("该仓库存在出入库流水，无法删除")
    db.query(StorageLocation).filter(StorageLocation.warehouse_id == warehouse_id).delete()
    db.delete(warehouse)
    db.flush()
    return ok({"deleted": True})


# --------------------------------------------------------------------------- 库位


@router.get("/warehouses/{warehouse_id}/locations", response_model=ApiResponse[List[LocationOut]], summary="库位列表")
def list_locations(
    warehouse_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:read")),
) -> dict:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    rows = (
        db.query(StorageLocation)
        .filter(StorageLocation.warehouse_id == warehouse_id)
        .order_by(StorageLocation.code.asc())
        .all()
    )
    return ok(
        [
            {
                "id": row.id,
                "warehouse_id": row.warehouse_id,
                "code": row.code,
                "name": row.name,
                "zone": row.zone,
                "capacity": float(dec(row.capacity)),
                "status": row.status,
                "remark": row.remark,
            }
            for row in rows
        ]
    )


@router.post("/warehouses/{warehouse_id}/locations", response_model=ApiResponse[LocationOut], summary="创建库位")
def create_location(
    warehouse_id: int,
    payload: LocationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:write")),
) -> dict:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    exists = (
        db.query(StorageLocation)
        .filter(StorageLocation.warehouse_id == warehouse_id, StorageLocation.code == payload.code)
        .first()
    )
    if exists:
        raise Conflict(f"库位编码已存在：{payload.code}")
    location = StorageLocation(warehouse_id=warehouse_id, **payload.model_dump())
    db.add(location)
    db.flush()
    return ok(
        {
            "id": location.id,
            "warehouse_id": location.warehouse_id,
            "code": location.code,
            "name": location.name,
            "zone": location.zone,
            "capacity": float(dec(location.capacity)),
            "status": location.status,
            "remark": location.remark,
        }
    )


@router.put("/locations/{location_id}", response_model=ApiResponse[dict], summary="更新库位")
def update_location(
    location_id: int,
    payload: LocationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:write")),
) -> dict:
    location = db.get(StorageLocation, location_id)
    if location is None:
        raise NotFound("库位不存在")
    warehouse = db.get(Warehouse, location.warehouse_id)
    if warehouse is not None:
        _assert_warehouse_visible(db, user, warehouse)
    data = payload.model_dump(exclude_unset=True)
    if data.get("code") and data["code"] != location.code:
        exists = (
            db.query(StorageLocation)
            .filter(
                StorageLocation.warehouse_id == location.warehouse_id,
                StorageLocation.code == data["code"],
                StorageLocation.id != location.id,
            )
            .first()
        )
        if exists:
            raise Conflict(f"库位编码已存在：{data['code']}")
    for field, value in data.items():
        setattr(location, field, value)
    db.flush()
    return ok({"id": location.id, "code": location.code, "updated": True})


@router.delete("/locations/{location_id}", response_model=ApiResponse[dict], summary="删除库位")
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:write")),
) -> dict:
    location = db.get(StorageLocation, location_id)
    if location is None:
        raise NotFound("库位不存在")
    warehouse = db.get(Warehouse, location.warehouse_id)
    if warehouse is not None:
        _assert_warehouse_visible(db, user, warehouse)
    if db.query(Inventory).filter(
        Inventory.location_id == location_id, Inventory.quantity > 0
    ).count():
        raise Conflict("该库位仍有库存，无法删除")
    db.delete(location)
    db.flush()
    return ok({"deleted": True})


# --------------------------------------------------------------------------- 库存查询


@router.get("/inventory", response_model=ApiResponse[PageData[InventoryOut]], summary="库存列表")
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    product_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    keyword: Optional[str] = None,
    quality_status: Optional[str] = None,
    only_available: bool = False,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("inventory:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Inventory)
    if product_id:
        query = query.filter(Inventory.product_id == product_id)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    if batch_no:
        query = query.filter(Inventory.batch_no == batch_no)
    if quality_status:
        query = query.filter(Inventory.quality_status == quality_status)
    if keyword:
        like = f"%{keyword.strip()}%"
        product_ids = [
            row[0]
            for row in db.query(Product.id)
            .filter(or_(Product.name.like(like), Product.code.like(like)))
            .all()
        ]
        query = query.filter(Inventory.product_id.in_(product_ids or [-1]))
    query = apply_own_enterprise(query, Inventory, user, "enterprise_id", db)
    if only_available:
        query = query.filter(Inventory.quantity > Inventory.locked_quantity)
    total = query.count()
    rows = (
        query.order_by(Inventory.product_id.asc(), Inventory.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(paginate([inventory_out(lk, row) for row in rows], total, page, page_size))


@router.get("/inventory/summary", response_model=ApiResponse[List[InventorySummaryOut]], summary="库存汇总")
def inventory_summary_api(
    enterprise_id: Optional[int] = None,
    category_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:read")),
) -> dict:
    scope = None if is_unrestricted(user) else enterprise_scope_ids(db, user)
    if enterprise_id:
        if scope is not None and enterprise_id not in set(scope):
            raise Forbidden("无权查看该企业库存")
        scope = [enterprise_id]
    product_query = db.query(Product.id)
    if scope is not None:
        if not scope:
            return ok([])
        product_query = product_query.filter(Product.enterprise_id.in_(scope))
    if category_id:
        product_query = product_query.filter(Product.category_id == category_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        product_query = product_query.filter(
            or_(Product.name.like(like), Product.code.like(like))
        )
    product_ids = [row[0] for row in product_query.all()]
    if not product_ids:
        return ok([])
    return ok(inventory_summary(db, product_ids))


@router.get("/inventory/warnings", response_model=ApiResponse[List[dict]], summary="库存预警")
def inventory_warnings(
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:read")),
) -> dict:
    scope = None if is_unrestricted(user) else enterprise_scope_ids(db, user)
    return ok(low_stock_products(db, scope))


@router.get("/inventory/moves", response_model=ApiResponse[PageData[StockMoveOut]], summary="库存流水")
def list_moves(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    product_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    move_type: Optional[str] = None,
    ref_no: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("inventory:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(StockMove)
    if product_id:
        query = query.filter(StockMove.product_id == product_id)
    if warehouse_id:
        query = query.filter(StockMove.warehouse_id == warehouse_id)
    if move_type:
        query = query.filter(StockMove.move_type == move_type)
    if ref_no:
        query = query.filter(StockMove.ref_no == ref_no)
    if start_date:
        query = query.filter(func.date(StockMove.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(StockMove.created_at) <= end_date)
    if not is_unrestricted(user):
        scope = enterprise_scope_ids(db, user) or []
        product_ids = [
            row[0] for row in db.query(Product.id).filter(Product.enterprise_id.in_(scope or [-1])).all()
        ]
        query = query.filter(StockMove.product_id.in_(product_ids or [-1]))
    total = query.count()
    rows = (
        query.order_by(StockMove.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    items = []
    for row in rows:
        product = lk.product(row.product_id)
        items.append(
            {
                "id": row.id,
                "move_no": row.move_no,
                "move_type": row.move_type,
                "product_id": row.product_id,
                "product_name": product.name if product else None,
                "warehouse_id": row.warehouse_id,
                "warehouse_name": lk.warehouse_name(row.warehouse_id),
                "location_id": row.location_id,
                "to_warehouse_id": row.to_warehouse_id,
                "to_warehouse_name": lk.warehouse_name(row.to_warehouse_id),
                "quantity": float(dec(row.quantity)),
                "unit_cost": float(dec(row.unit_cost)),
                "batch_no": row.batch_no,
                "ref_type": row.ref_type,
                "ref_no": row.ref_no,
                "operator_name": row.operator_name,
                "remark": row.remark,
                "created_at": row.created_at,
            }
        )
    return ok(paginate(items, total, page, page_size))


# --------------------------------------------------------------------------- 出入库操作


def _assert_product_visible(db: Session, user: User, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if product.enterprise_id not in allowed:
            raise Forbidden("无权操作该商品的库存")
    return product


@router.post("/inventory/in", response_model=ApiResponse[InventoryOut], summary="入库")
def inventory_in(
    payload: StockInIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("inventory:execute")),
) -> dict:
    _assert_product_visible(db, user, payload.product_id)
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    if payload.location_id:
        assert_location_belongs(db, payload.location_id, payload.warehouse_id)
    row = stock_in(db, payload, user)
    integration.enqueue(
        db,
        event_type="inventory.in",
        aggregate_type="inventory",
        aggregate_id=f"{row.product_id}:{row.warehouse_id}:{row.batch_no}",
        payload={
            "product_id": row.product_id,
            "warehouse_id": row.warehouse_id,
            "batch_no": row.batch_no,
            "quantity": float(dec(payload.quantity)),
            "unit_cost": float(dec(row.unit_cost)),
        },
    )
    return ok(inventory_out(lk, row))


@router.post("/inventory/out", response_model=ApiResponse[dict], summary="出库")
def inventory_out_api(
    payload: StockOutIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:execute")),
) -> dict:
    _assert_product_visible(db, user, payload.product_id)
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    row = stock_out(db, payload, user)
    remaining = Decimal("0")
    if row is not None:
        remaining = dec(row.quantity)
    return ok(
        {
            "product_id": payload.product_id,
            "warehouse_id": payload.warehouse_id,
            "batch_no": payload.batch_no or "DEFAULT",
            "quantity": float(q3(payload.quantity)),
            "remaining_quantity": float(remaining),
        }
    )


@router.post("/inventory/transfer", response_model=ApiResponse[dict], summary="调拨")
def inventory_transfer(
    payload: StockTransferIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:execute")),
) -> dict:
    _assert_product_visible(db, user, payload.product_id)
    from_warehouse = db.get(Warehouse, payload.from_warehouse_id)
    to_warehouse = db.get(Warehouse, payload.to_warehouse_id)
    if from_warehouse is None or to_warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, from_warehouse)
    _assert_warehouse_visible(db, user, to_warehouse)
    return ok(transfer(db, payload, user))


@router.post("/inventory/adjust", response_model=ApiResponse[InventoryOut], summary="库存调整")
def inventory_adjust(
    payload: StockAdjustIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("inventory:execute")),
) -> dict:
    _assert_product_visible(db, user, payload.product_id)
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    row = adjust(db, payload, user)
    return ok(inventory_out(lk, row))


@router.post("/inventory/check", response_model=ApiResponse[InventoryCheckResult], summary="库存盘点")
def inventory_check_api(
    payload: InventoryCheckIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("inventory:execute")),
) -> dict:
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise NotFound("仓库不存在")
    _assert_warehouse_visible(db, user, warehouse)
    for item in payload.items:
        _assert_product_visible(db, user, item.product_id)
    return ok(inventory_check(db, payload, user))
