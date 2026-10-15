# -*- coding: utf-8 -*-
"""库存服务：入库、出库、调拨、调整、盘点、预占与扣减。

并发控制：
- PostgreSQL 下所有库存行读取一律走 `SELECT ... FOR UPDATE`（`lock_query`）；
- SQLite（测试）自动跳过行锁，保证同一套业务代码可测。

数量精度：统一 Decimal，保留 3 位小数（吨/千克/袋）。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import lock_query
from app.core.errors import BadRequest, InsufficientStock, NotFound
from app.core.timeutil import now
from app.models.enterprise import Enterprise, Park
from app.models.org import User
from app.models.product import (
    Category,
    Inventory,
    Product,
    StockMove,
    StorageLocation,
    Warehouse,
)
from app.schemas.stock import (
    InventoryCheckIn,
    StockAdjustIn,
    StockInIn,
    StockOutIn,
    StockTransferIn,
)
from app.services.numbering import next_no

Q3 = Decimal("0.001")
ZERO = Decimal("0")


def dec(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def q3(value) -> Decimal:
    return dec(value).quantize(Q3)


# --------------------------------------------------------------------------- 查询


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound(f"商品不存在：{product_id}")
    return product


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise NotFound(f"仓库不存在：{warehouse_id}")
    return warehouse


def find_inventory_rows(
    db: Session,
    product_id: int,
    warehouse_id: Optional[int] = None,
    location_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    for_update: bool = False,
) -> List[Inventory]:
    query = db.query(Inventory).filter(Inventory.product_id == product_id)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    if location_id:
        query = query.filter(Inventory.location_id == location_id)
    if batch_no:
        query = query.filter(Inventory.batch_no == batch_no)
    query = query.order_by(Inventory.id.asc())
    if for_update:
        query = lock_query(query, db)
    return query.all()


def product_availability(db: Session, product_id: int) -> Tuple[Decimal, Decimal, Decimal]:
    row = (
        db.query(
            func.coalesce(func.sum(Inventory.quantity), 0),
            func.coalesce(func.sum(Inventory.locked_quantity), 0),
        )
        .filter(Inventory.product_id == product_id)
        .one()
    )
    total = dec(row[0])
    locked = dec(row[1])
    return total, locked, total - locked


def availability_map(db: Session, product_ids: Sequence[int]) -> Dict[int, Dict[str, Decimal]]:
    if not product_ids:
        return {}
    rows = (
        db.query(
            Inventory.product_id,
            func.coalesce(func.sum(Inventory.quantity), 0),
            func.coalesce(func.sum(Inventory.locked_quantity), 0),
            func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
        )
        .filter(Inventory.product_id.in_(list(product_ids)))
        .group_by(Inventory.product_id)
        .all()
    )
    result: Dict[int, Dict[str, Decimal]] = {}
    for product_id, total, locked, value in rows:
        total_d, locked_d = dec(total), dec(locked)
        result[int(product_id)] = {
            "total": total_d,
            "locked": locked_d,
            "available": total_d - locked_d,
            "value": dec(value),
        }
    return result


def inventory_summary(db: Session, product_ids: Optional[Sequence[int]] = None) -> List[dict]:
    query = (
        db.query(
            Inventory.product_id,
            func.coalesce(func.sum(Inventory.quantity), 0),
            func.coalesce(func.sum(Inventory.locked_quantity), 0),
            func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
            func.count(func.distinct(Inventory.warehouse_id)),
            func.count(Inventory.id),
        )
        .group_by(Inventory.product_id)
    )
    if product_ids:
        query = query.filter(Inventory.product_id.in_(list(product_ids)))
    aggregates = {int(r[0]): r for r in query.all()}
    if not aggregates:
        return []
    products = db.query(Product).filter(Product.id.in_(list(aggregates.keys()))).all()
    categories = {c.id: c.name for c in db.query(Category).all()}
    enterprises = {e.id: e.name for e in db.query(Enterprise).all()}
    result = []
    for product in products:
        agg = aggregates.get(product.id)
        if agg is None:
            continue
        total, locked, value = dec(agg[1]), dec(agg[2]), dec(agg[3])
        result.append(
            {
                "product_id": product.id,
                "product_code": product.code,
                "product_name": product.name,
                "category_name": categories.get(product.category_id),
                "enterprise_id": product.enterprise_id,
                "enterprise_name": enterprises.get(product.enterprise_id),
                "unit": product.unit,
                "price": float(product.price or 0),
                "total_quantity": float(total),
                "locked_quantity": float(locked),
                "available_quantity": float(total - locked),
                "inventory_value": float(value),
                "warehouse_count": int(agg[4] or 0),
                "batch_count": int(agg[5] or 0),
            }
        )
    result.sort(key=lambda item: item["total_quantity"], reverse=True)
    return result


# --------------------------------------------------------------------------- 内部工具


def _get_or_create_row(
    db: Session,
    product: Product,
    warehouse_id: int,
    location_id: Optional[int],
    batch_no: str,
    unit_cost: Optional[Decimal] = None,
    production_date=None,
    expiry_date=None,
    quality_status: Optional[str] = None,
) -> Inventory:
    rows = find_inventory_rows(
        db, product.id, warehouse_id=warehouse_id, location_id=location_id, batch_no=batch_no,
        for_update=True,
    )
    if rows:
        row = rows[0]
        if unit_cost is not None and unit_cost > 0:
            row.unit_cost = unit_cost
        if production_date:
            row.production_date = production_date
        if expiry_date:
            row.expiry_date = expiry_date
        if quality_status:
            row.quality_status = quality_status
        row.updated_at = now()
        return row
    row = Inventory(
        product_id=product.id,
        warehouse_id=warehouse_id,
        location_id=location_id,
        batch_no=batch_no or "DEFAULT",
        quantity=ZERO,
        locked_quantity=ZERO,
        unit_cost=unit_cost or product.price or ZERO,
        production_date=production_date,
        expiry_date=expiry_date,
        quality_status=quality_status or product.quality_status or "pending",
        enterprise_id=product.enterprise_id,
    )
    db.add(row)
    db.flush()
    return row


def _write_move(
    db: Session,
    *,
    move_type: str,
    product_id: int,
    warehouse_id: Optional[int],
    location_id: Optional[int],
    quantity: Decimal,
    unit_cost: Optional[Decimal],
    batch_no: Optional[str],
    operator: Optional[User],
    ref_type: str = "manual",
    ref_id: Optional[int] = None,
    ref_no: Optional[str] = None,
    to_warehouse_id: Optional[int] = None,
    to_location_id: Optional[int] = None,
    remark: Optional[str] = None,
) -> StockMove:
    move = StockMove(
        move_no=next_no(db, "stock_move", "GZ-SM", width=6),
        move_type=move_type,
        product_id=product_id,
        warehouse_id=warehouse_id,
        location_id=location_id,
        to_warehouse_id=to_warehouse_id,
        to_location_id=to_location_id,
        quantity=q3(quantity),
        unit_cost=unit_cost,
        batch_no=batch_no,
        ref_type=ref_type,
        ref_id=ref_id,
        ref_no=ref_no,
        operator_id=operator.id if operator else None,
        operator_name=(operator.full_name or operator.username) if operator else None,
        remark=remark,
        created_at=now(),
    )
    db.add(move)
    db.flush()
    return move


def _low_stock_warn(product: Product, available: Decimal) -> Optional[str]:
    warn = dec(product.stock_warn_qty)
    if warn > 0 and available < warn:
        return f"商品【{product.name}】可用库存 {available} 低于预警值 {warn}"
    return None


# --------------------------------------------------------------------------- 入库 / 出库


def stock_in(db: Session, data: StockInIn, operator: Optional[User] = None) -> Inventory:
    product = get_product(db, data.product_id)
    get_warehouse(db, data.warehouse_id)
    quantity = q3(data.quantity)
    if quantity <= 0:
        raise BadRequest("入库数量必须大于 0")
    row = _get_or_create_row(
        db,
        product,
        data.warehouse_id,
        data.location_id,
        data.batch_no or "DEFAULT",
        unit_cost=dec(data.unit_cost) if data.unit_cost is not None else None,
        production_date=data.production_date,
        expiry_date=data.expiry_date,
        quality_status=data.quality_status,
    )
    row.quantity = q3(dec(row.quantity) + quantity)
    row.updated_at = now()
    _write_move(
        db,
        move_type="in",
        product_id=product.id,
        warehouse_id=data.warehouse_id,
        location_id=data.location_id,
        quantity=quantity,
        unit_cost=row.unit_cost,
        batch_no=row.batch_no,
        operator=operator,
        ref_type=data.ref_type or "manual",
        ref_no=data.ref_no,
        remark=data.remark,
    )
    db.flush()
    return row


def stock_out(db: Session, data: StockOutIn, operator: Optional[User] = None) -> Inventory:
    product = get_product(db, data.product_id)
    quantity = q3(data.quantity)
    if quantity <= 0:
        raise BadRequest("出库数量必须大于 0")
    rows = find_inventory_rows(
        db,
        product.id,
        warehouse_id=data.warehouse_id,
        location_id=data.location_id,
        batch_no=data.batch_no or "DEFAULT",
        for_update=True,
    )
    available = sum((dec(r.quantity) - dec(r.locked_quantity) for r in rows), ZERO)
    if available < quantity:
        raise InsufficientStock(product.name, available, quantity)
    remaining = quantity
    first_row = rows[0] if rows else None
    for row in rows:
        if remaining <= 0:
            break
        row_available = dec(row.quantity) - dec(row.locked_quantity)
        take = min(row_available, remaining)
        if take <= 0:
            continue
        row.quantity = q3(dec(row.quantity) - take)
        row.updated_at = now()
        remaining -= take
    _write_move(
        db,
        move_type="out",
        product_id=product.id,
        warehouse_id=data.warehouse_id,
        location_id=data.location_id,
        quantity=quantity,
        unit_cost=(first_row.unit_cost if first_row else product.price),
        batch_no=data.batch_no or "DEFAULT",
        operator=operator,
        ref_type=data.ref_type or "manual",
        ref_no=data.ref_no,
        remark=data.remark,
    )
    db.flush()
    return first_row  # type: ignore[return-value]


def transfer(db: Session, data: StockTransferIn, operator: Optional[User] = None) -> dict:
    if data.from_warehouse_id == data.to_warehouse_id and data.from_location_id == data.to_location_id:
        raise BadRequest("调出与调入位置不能相同")
    product = get_product(db, data.product_id)
    quantity = q3(data.quantity)
    rows = find_inventory_rows(
        db,
        product.id,
        warehouse_id=data.from_warehouse_id,
        location_id=data.from_location_id,
        batch_no=data.batch_no or "DEFAULT",
        for_update=True,
    )
    available = sum((dec(r.quantity) - dec(r.locked_quantity) for r in rows), ZERO)
    if available < quantity:
        raise InsufficientStock(product.name, available, quantity)
    remaining = quantity
    for row in rows:
        if remaining <= 0:
            break
        row_available = dec(row.quantity) - dec(row.locked_quantity)
        take = min(row_available, remaining)
        if take <= 0:
            continue
        row.quantity = q3(dec(row.quantity) - take)
        row.updated_at = now()
        remaining -= take
    target = _get_or_create_row(
        db,
        product,
        data.to_warehouse_id,
        data.to_location_id,
        data.batch_no or "DEFAULT",
        unit_cost=None,
    )
    target.quantity = q3(dec(target.quantity) + quantity)
    target.updated_at = now()
    _write_move(
        db,
        move_type="transfer",
        product_id=product.id,
        warehouse_id=data.from_warehouse_id,
        location_id=data.from_location_id,
        to_warehouse_id=data.to_warehouse_id,
        to_location_id=data.to_location_id,
        quantity=quantity,
        unit_cost=target.unit_cost,
        batch_no=data.batch_no or "DEFAULT",
        operator=operator,
        ref_type="transfer",
        remark=data.remark,
    )
    db.flush()
    return {"product_id": product.id, "quantity": float(quantity), "from": data.from_warehouse_id,
            "to": data.to_warehouse_id}


def adjust(db: Session, data: StockAdjustIn, operator: Optional[User] = None) -> Inventory:
    product = get_product(db, data.product_id)
    row = _get_or_create_row(
        db, product, data.warehouse_id, data.location_id, data.batch_no or "DEFAULT"
    )
    target = q3(data.target_quantity)
    current = dec(row.quantity)
    diff = target - current
    if diff == 0:
        raise BadRequest("目标数量与当前数量一致，无需调整")
    if target < dec(row.locked_quantity):
        raise BadRequest("调整后数量不得小于预占数量")
    row.quantity = target
    row.updated_at = now()
    _write_move(
        db,
        move_type="adjust",
        product_id=product.id,
        warehouse_id=data.warehouse_id,
        location_id=data.location_id,
        quantity=abs(diff),
        unit_cost=row.unit_cost,
        batch_no=row.batch_no,
        operator=operator,
        ref_type="adjust",
        remark=f"{'盘盈' if diff > 0 else '盘亏'} {abs(diff)}；{data.remark or ''}".strip("；"),
    )
    db.flush()
    return row


def inventory_check(db: Session, data: InventoryCheckIn, operator: Optional[User] = None) -> dict:
    get_warehouse(db, data.warehouse_id)
    details: List[dict] = []
    profit = ZERO
    loss = ZERO
    diff_count = 0
    for item in data.items:
        product = get_product(db, item.product_id)
        row = _get_or_create_row(
            db, product, data.warehouse_id, item.location_id, item.batch_no or "DEFAULT"
        )
        book = dec(row.quantity)
        actual = q3(item.actual_quantity)
        diff = actual - book
        if diff != 0:
            diff_count += 1
            if diff > 0:
                profit += diff
            else:
                loss += -diff
            row.quantity = actual
            row.updated_at = now()
            _write_move(
                db,
                move_type="check",
                product_id=product.id,
                warehouse_id=data.warehouse_id,
                location_id=item.location_id,
                quantity=abs(diff),
                unit_cost=row.unit_cost,
                batch_no=row.batch_no,
                operator=operator,
                ref_type="check",
                remark=f"盘点{'盘盈' if diff > 0 else '盘亏'}：账面 {book} → 实盘 {actual}；{data.remark or ''}".strip("；"),
            )
        details.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "batch_no": row.batch_no,
                "book_quantity": float(book),
                "actual_quantity": float(actual),
                "diff": float(diff),
            }
        )
    db.flush()
    return {
        "warehouse_id": data.warehouse_id,
        "checked_count": len(data.items),
        "diff_count": diff_count,
        "profit_quantity": float(profit),
        "loss_quantity": float(loss),
        "details": details,
    }


# --------------------------------------------------------------------------- 交易预占与扣减


def reserve(db: Session, product_id: int, quantity: Decimal, warehouse_id: Optional[int] = None) -> None:
    """交易预占：锁定可用量，防止超卖。"""
    quantity = q3(quantity)
    if quantity <= 0:
        return
    product = get_product(db, product_id)
    rows = find_inventory_rows(db, product_id, warehouse_id=warehouse_id, for_update=True)
    total_available = sum((dec(r.quantity) - dec(r.locked_quantity) for r in rows), ZERO)
    if total_available < quantity:
        raise InsufficientStock(product.name, total_available, quantity)
    remaining = quantity
    for row in rows:
        if remaining <= 0:
            break
        row_available = dec(row.quantity) - dec(row.locked_quantity)
        take = min(row_available, remaining)
        if take <= 0:
            continue
        row.locked_quantity = q3(dec(row.locked_quantity) + take)
        row.updated_at = now()
        remaining -= take
    db.flush()


def release(db: Session, product_id: int, quantity: Decimal, warehouse_id: Optional[int] = None) -> None:
    """释放预占（订单取消）。"""
    quantity = q3(quantity)
    rows = find_inventory_rows(db, product_id, warehouse_id=warehouse_id, for_update=True)
    remaining = quantity
    for row in rows:
        if remaining <= 0:
            break
        locked = dec(row.locked_quantity)
        take = min(locked, remaining)
        if take <= 0:
            continue
        row.locked_quantity = q3(locked - take)
        row.updated_at = now()
        remaining -= take
    db.flush()


def consume_reserved(
    db: Session,
    product_id: int,
    quantity: Decimal,
    *,
    warehouse_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    ref_type: str = "order",
    ref_id: Optional[int] = None,
    ref_no: Optional[str] = None,
    operator: Optional[User] = None,
) -> None:
    """订单确认：把预占量转为实际出库（数量减少 + 写库存流水）。"""
    quantity = q3(quantity)
    if batch_no == "DEFAULT":
        batch_no = None
    product = get_product(db, product_id)
    rows = find_inventory_rows(
        db, product_id, warehouse_id=warehouse_id, batch_no=batch_no, for_update=True
    )
    locked_total = sum((dec(r.locked_quantity) for r in rows), ZERO)
    if locked_total < quantity:
        # 无预占（如直接下单未预占）则按可用量直接扣减
        available = sum((dec(r.quantity) - dec(r.locked_quantity) for r in rows), ZERO)
        if available < quantity:
            raise InsufficientStock(product.name, available, quantity)
    remaining = quantity
    for row in rows:
        if remaining <= 0:
            break
        locked = dec(row.locked_quantity)
        take = min(locked, remaining)
        if take > 0:
            row.locked_quantity = q3(locked - take)
        else:
            row_available = dec(row.quantity) - dec(row.locked_quantity)
            take = min(row_available, remaining)
            if take <= 0:
                continue
        row.quantity = q3(dec(row.quantity) - take)
        row.updated_at = now()
        remaining -= take
        _write_move(
            db,
            move_type="out",
            product_id=product.id,
            warehouse_id=row.warehouse_id,
            location_id=row.location_id,
            quantity=take,
            unit_cost=row.unit_cost,
            batch_no=row.batch_no,
            operator=operator,
            ref_type=ref_type,
            ref_id=ref_id,
            ref_no=ref_no,
            remark="订单确认出库",
        )
    if remaining > 0:
        raise InsufficientStock(product.name, quantity - remaining, quantity)
    db.flush()


def revert_out(
    db: Session,
    product_id: int,
    quantity: Decimal,
    *,
    warehouse_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    ref_no: Optional[str] = None,
    operator: Optional[User] = None,
) -> None:
    """红冲出库（订单取消且已扣减库存时使用），回补到原出库仓库/批次。"""
    quantity = q3(quantity)
    if quantity <= 0:
        return
    product = get_product(db, product_id)
    rows = find_inventory_rows(
        db, product_id, warehouse_id=warehouse_id, batch_no=batch_no, for_update=True
    )
    if not rows:
        # 原行已被清零删除的场景不允许发生（库存行不做物理删除），此处显式报错便于排查
        raise BadRequest(f"未找到可回补的库存行：商品 {product_id} / 仓库 {warehouse_id}")
    row = rows[0]
    row.quantity = q3(dec(row.quantity) + quantity)
    row.updated_at = now()
    _write_move(
        db,
        move_type="in",
        product_id=product.id,
        warehouse_id=row.warehouse_id,
        location_id=row.location_id,
        quantity=quantity,
        unit_cost=row.unit_cost,
        batch_no=row.batch_no,
        operator=operator,
        ref_type="order_cancel",
        ref_no=ref_no,
        remark="订单取消回补库存",
    )
    db.flush()


def assert_warehouse_exists(db: Session, warehouse_id: int) -> Warehouse:
    return get_warehouse(db, warehouse_id)


def assert_location_belongs(db: Session, location_id: int, warehouse_id: int) -> StorageLocation:
    location = db.get(StorageLocation, location_id)
    if location is None:
        raise NotFound(f"库位不存在：{location_id}")
    if location.warehouse_id != warehouse_id:
        raise BadRequest("库位不属于所选仓库")
    return location


def low_stock_products(db: Session, enterprise_ids: Optional[Iterable[int]] = None) -> List[dict]:
    query = db.query(Product).filter(Product.stock_warn_qty > 0)
    if enterprise_ids is not None:
        ids = list(enterprise_ids)
        if not ids:
            return []
        query = query.filter(Product.enterprise_id.in_(ids))
    products = query.all()
    if not products:
        return []
    availability = availability_map(db, [p.id for p in products])
    result = []
    for product in products:
        agg = availability.get(product.id, {"total": ZERO, "locked": ZERO, "available": ZERO})
        if agg["available"] < dec(product.stock_warn_qty):
            result.append(
                {
                    "product_id": product.id,
                    "product_code": product.code,
                    "product_name": product.name,
                    "warn_qty": float(product.stock_warn_qty or 0),
                    "available_quantity": float(agg["available"]),
                    "unit": product.unit,
                }
            )
    return result


def warehouse_overview(db: Session, enterprise_ids: Optional[Iterable[int]] = None) -> List[dict]:
    query = db.query(Warehouse)
    if enterprise_ids is not None:
        ids = list(enterprise_ids)
        if not ids:
            return []
        query = query.filter(Warehouse.enterprise_id.in_(ids))
    warehouses = query.all()
    if not warehouses:
        return []
    parks = {p.id: p.name for p in db.query(Park).all()}
    enterprises = {e.id: e.name for e in db.query(Enterprise).all()}
    location_counts = dict(
        db.query(StorageLocation.warehouse_id, func.count(StorageLocation.id))
        .group_by(StorageLocation.warehouse_id)
        .all()
    )
    quantity_sums = dict(
        db.query(Inventory.warehouse_id, func.coalesce(func.sum(Inventory.quantity), 0))
        .group_by(Inventory.warehouse_id)
        .all()
    )
    result = []
    for warehouse in warehouses:
        result.append(
            {
                "id": warehouse.id,
                "code": warehouse.code,
                "name": warehouse.name,
                "enterprise_id": warehouse.enterprise_id,
                "enterprise_name": enterprises.get(warehouse.enterprise_id),
                "park_id": warehouse.park_id,
                "park_name": parks.get(warehouse.park_id),
                "address": warehouse.address,
                "warehouse_type": warehouse.warehouse_type,
                "contact_name": warehouse.contact_name,
                "contact_phone": warehouse.contact_phone,
                "capacity": float(warehouse.capacity or 0),
                "status": warehouse.status,
                "remark": warehouse.remark,
                "location_count": int(location_counts.get(warehouse.id, 0)),
                "inventory_quantity": float(dec(quantity_sums.get(warehouse.id, 0))),
            }
        )
    return result
