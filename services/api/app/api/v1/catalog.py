# -*- coding: utf-8 -*-
"""商品中心接口：分类树、商品档案、上下架、审核、检索。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups, inventory_out, product_out
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import (
    apply_own_enterprise,
    enterprise_scope_ids,
    is_unrestricted,
    resolve_own_enterprise,
)
from app.integrations.search import search as search_engine
from app.models.enterprise import Enterprise
from app.models.product import Category, Inventory, Product, StockMove
from app.models.org import User
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    CategoryTreeOut,
    CategoryUpdate,
    ProductAuditIn,
    ProductIn,
    ProductOut,
    ProductSearchOut,
    ProductUpdate,
)
from app.services import integration
from app.services.inventory_service import product_availability
from app.services.numbering import next_no

router = APIRouter(tags=["商品中心"])

VALID_GRADES = ("special", "first", "second", "mixed")
VALID_UNITS = ("ton", "kg", "bag", "piece")
VALID_PRICING_MODES = ("listed", "negotiable", "inquiry")
VALID_SUPPLY_STATUSES = ("active", "paused", "completed")


# --------------------------------------------------------------------------- 分类


def _category_tree(db: Session) -> List[dict]:
    rows = db.query(Category).order_by(Category.sort.asc(), Category.id.asc()).all()
    counts = dict(
        db.query(Product.category_id, func.count(Product.id)).group_by(Product.category_id).all()
    )
    nodes = {
        row.id: {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "parent_id": row.parent_id,
            "level": row.level,
            "sort": row.sort,
            "status": row.status,
            "product_count": int(counts.get(row.id, 0)),
            "children": [],
        }
        for row in rows
    }
    roots: List[dict] = []
    for row in rows:
        node = nodes[row.id]
        parent = nodes.get(row.parent_id) if row.parent_id else None
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


@router.get("/categories/tree", response_model=ApiResponse[List[CategoryTreeOut]], summary="商品分类树")
def category_tree(
    db: Session = Depends(get_db),
    _: User = Depends(require("product:read")),
) -> dict:
    return ok(_category_tree(db))


@router.post("/categories", response_model=ApiResponse[CategoryOut], summary="创建分类")
def create_category(
    payload: CategoryIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("product:write")),
) -> dict:
    level = 1
    if payload.parent_id:
        parent = db.get(Category, payload.parent_id)
        if parent is None:
            raise BadRequest("上级分类不存在")
        level = int(parent.level or 1) + 1
        if level > 3:
            raise BadRequest("分类层级最多 3 级")
    code = payload.code or next_no(db, "category", "GZ-CAT")
    if db.query(Category).filter(Category.code == code).first():
        raise Conflict(f"分类编码已存在：{code}")
    category = Category(
        code=code,
        name=payload.name,
        parent_id=payload.parent_id,
        level=level,
        sort=payload.sort,
        status=payload.status,
        description=payload.description,
    )
    db.add(category)
    db.flush()
    return ok(
        {
            "id": category.id,
            "code": category.code,
            "name": category.name,
            "parent_id": category.parent_id,
            "level": category.level,
            "sort": category.sort,
            "status": category.status,
            "description": category.description,
            "product_count": 0,
        }
    )


@router.put("/categories/{category_id}", response_model=ApiResponse[dict], summary="更新分类")
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require("product:write")),
) -> dict:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFound("分类不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("parent_id"):
        if data["parent_id"] == category_id:
            raise BadRequest("上级分类不能是自己")
        parent = db.get(Category, data["parent_id"])
        if parent is None:
            raise BadRequest("上级分类不存在")
        category.level = int(parent.level or 1) + 1
    for field, value in data.items():
        setattr(category, field, value)
    db.flush()
    return ok({"id": category.id, "name": category.name, "updated": True})


@router.delete("/categories/{category_id}", response_model=ApiResponse[dict], summary="删除分类")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("product:write")),
) -> dict:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFound("分类不存在")
    if db.query(Category).filter(Category.parent_id == category_id).count():
        raise Conflict("存在下级分类，无法删除")
    if db.query(Product).filter(Product.category_id == category_id).count():
        raise Conflict("该分类下存在商品，无法删除")
    db.delete(category)
    db.flush()
    return ok({"deleted": True})


# --------------------------------------------------------------------------- 商品


def _index_product(lk: Lookups, product: Product) -> None:
    availability = lk.availability(product.id)
    search_engine.index_document(
        {
            "id": product.id,
            "code": product.code,
            "name": product.name,
            "category_id": product.category_id,
            "category_name": lk.category_name(product.category_id),
            "enterprise_id": product.enterprise_id,
            "enterprise_name": lk.enterprise_name(product.enterprise_id),
            "spec": product.spec,
            "grade": product.grade,
            "origin": product.origin,
            "harvest_year": product.harvest_year,
            "status": product.status,
            "price": float(product.price or 0),
            "available_quantity": float(availability["available"]),
        }
    )


@router.get("/products", response_model=ApiResponse[PageData[ProductOut]], summary="商品列表")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    status: Optional[str] = None,
    audit_status: Optional[str] = None,
    grade: Optional[str] = None,
    origin: Optional[str] = None,
    harvest_year: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    only_available: bool = False,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Product)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Product.name.like(like),
                Product.code.like(like),
                Product.spec.like(like),
                Product.origin.like(like),
            )
        )
    if category_id:
        child_ids = [
            row[0]
            for row in db.query(Category.id).filter(Category.parent_id == category_id).all()
        ]
        query = query.filter(Product.category_id.in_([category_id] + child_ids))
    if enterprise_id:
        query = query.filter(Product.enterprise_id == enterprise_id)
    if status:
        query = query.filter(Product.status == status)
    if audit_status:
        query = query.filter(Product.audit_status == audit_status)
    if grade:
        query = query.filter(Product.grade == grade)
    if origin:
        query = query.filter(Product.origin == origin)
    if harvest_year:
        query = query.filter(Product.harvest_year == harvest_year)
    if min_price is not None:
        query = query.filter(Product.price >= Decimal(str(min_price)))
    if max_price is not None:
        query = query.filter(Product.price <= Decimal(str(max_price)))
    query = apply_own_enterprise(query, Product, user, "enterprise_id", db)
    total = query.count()
    rows = query.order_by(Product.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    if only_available:
        rows = [row for row in rows if lk.availability(row.id)["available"] > 0]
    return ok(paginate([product_out(lk, row) for row in rows], total, page, page_size))


@router.get("/products/search", response_model=ApiResponse[ProductSearchOut], summary="商品全文检索")
def search_products(
    q: str = Query("", description="检索关键字"),
    category_id: Optional[int] = None,
    grade: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:read")),
) -> dict:
    scope_ids = enterprise_scope_ids(db, user)
    filters = {"status": "published"}
    if category_id:
        filters["category_id"] = category_id
    if grade:
        filters["grade"] = grade
    if scope_ids is not None:
        if not scope_ids:
            return ok({"items": [], "total": 0, "engine": search_engine.engine})
        filters["enterprise_id"] = scope_ids
    hits = search_engine.search(q, filters=filters, offset=0, limit=limit)
    engine = "elasticsearch"
    if hits is None:
        engine = "sql"
        query = db.query(Product).filter(Product.status == "published")
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(
                or_(Product.name.like(like), Product.code.like(like), Product.spec.like(like))
            )
        if category_id:
            query = query.filter(Product.category_id == category_id)
        if grade:
            query = query.filter(Product.grade == grade)
        query = apply_own_enterprise(query, Product, user, "enterprise_id", db)
        rows = query.limit(limit).all()
    else:
        if not hits:
            return ok({"items": [], "total": 0, "engine": engine})
        rows = db.query(Product).filter(Product.id.in_(hits)).all()
    return ok(
        {
            "items": [product_out(lk, row) for row in rows],
            "total": len(rows),
            "engine": engine,
        }
    )


@router.post("/products", response_model=ApiResponse[ProductOut], summary="创建商品")
def create_product(
    payload: ProductIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:write")),
) -> dict:
    category = db.get(Category, payload.category_id)
    if category is None:
        raise BadRequest("商品分类不存在")
    if payload.grade and payload.grade not in VALID_GRADES:
        raise BadRequest(f"等级取值必须为 {'/'.join(VALID_GRADES)}")
    if payload.unit not in VALID_UNITS:
        raise BadRequest(f"计量单位取值必须为 {'/'.join(VALID_UNITS)}")
    if payload.pricing_mode not in VALID_PRICING_MODES or payload.supply_status not in VALID_SUPPLY_STATUSES:
        raise BadRequest("供应价格方式或供应状态无效")
    enterprise_id = resolve_own_enterprise(user, payload.enterprise_id)
    if not db.get(Enterprise, enterprise_id):
        raise BadRequest("归属企业不存在")
    code = payload.code or next_no(db, "product", f"GZ-PRD-{date.today().year}")
    if db.query(Product).filter(Product.code == code).first():
        raise Conflict(f"商品编码已存在：{code}")
    product = Product(
        code=code,
        name=payload.name,
        category_id=payload.category_id,
        enterprise_id=enterprise_id,
        spec=payload.spec,
        grade=payload.grade,
        origin=payload.origin,
        harvest_year=payload.harvest_year,
        package=payload.package,
        unit=payload.unit,
        price=payload.price or Decimal("0"),
        currency=payload.currency,
        min_order_qty=payload.min_order_qty or Decimal("0"),
        stock_warn_qty=payload.stock_warn_qty or Decimal("0"),
        supply_quantity=payload.supply_quantity or Decimal("0"),
        supply_period=payload.supply_period,
        pricing_mode=payload.pricing_mode,
        supply_status=payload.supply_status,
        allow_inquiry=payload.allow_inquiry,
        allow_bulk_purchase=payload.allow_bulk_purchase,
        main_image=payload.main_image,
        images=payload.images or [],
        test_report_url=payload.test_report_url,
        quality_status=payload.quality_status,
        trace_enabled=payload.trace_enabled,
        status="draft",
        audit_status="pending",
        description=payload.description,
        created_by=user.id,
    )
    db.add(product)
    db.flush()
    _index_product(lk, product)
    integration.enqueue(
        db,
        event_type="product.created",
        aggregate_type="product",
        aggregate_id=product.code,
        payload=integration.product_payload(product, lk.category_name(product.category_id)),
    )
    return ok(product_out(lk, product))


@router.get("/products/{product_id}", response_model=ApiResponse[ProductOut], summary="商品详情")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:read")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if product.enterprise_id not in allowed:
            raise Forbidden("无权查看该商品")
    return ok(product_out(lk, product))


@router.put("/products/{product_id}", response_model=ApiResponse[ProductOut], summary="更新商品")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:write")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    if not is_unrestricted(user) and product.enterprise_id != user.enterprise_id:
        raise Forbidden("只能修改本企业的商品")
    data = payload.model_dump(exclude_unset=True)
    if data.get("grade") and data["grade"] not in VALID_GRADES:
        raise BadRequest(f"等级取值必须为 {'/'.join(VALID_GRADES)}")
    if data.get("unit") and data["unit"] not in VALID_UNITS:
        raise BadRequest(f"计量单位取值必须为 {'/'.join(VALID_UNITS)}")
    if data.get("category_id") and not db.get(Category, data["category_id"]):
        raise BadRequest("商品分类不存在")
    if data.get("pricing_mode") and data["pricing_mode"] not in VALID_PRICING_MODES:
        raise BadRequest("供应价格方式无效")
    if data.get("supply_status") and data["supply_status"] not in VALID_SUPPLY_STATUSES:
        raise BadRequest("供应状态无效")
    for field, value in data.items():
        setattr(product, field, value)
    # 已上架商品的关键信息变更后需重新审核，避免"先审后改"绕过审核
    sensitive = {"name", "category_id", "spec", "grade", "origin", "harvest_year", "package", "supply_quantity", "supply_period", "pricing_mode", "allow_inquiry", "allow_bulk_purchase"}
    if product.status == "published" and sensitive & set(data.keys()):
        product.audit_status = "pending"
        product.status = "offline"
        product.audit_remark = "关键信息变更，待重新审核"
    db.flush()
    _index_product(lk, product)
    integration.enqueue(
        db,
        event_type="product.updated",
        aggregate_type="product",
        aggregate_id=product.code,
        payload=integration.product_payload(product, lk.category_name(product.category_id)),
    )
    return ok(product_out(lk, product))


@router.delete("/products/{product_id}", response_model=ApiResponse[dict], summary="删除商品")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("product:write")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    if not is_unrestricted(user) and product.enterprise_id != user.enterprise_id:
        raise Forbidden("只能删除本企业的商品")
    if db.query(Inventory).filter(Inventory.product_id == product_id, Inventory.quantity > 0).count():
        raise Conflict("该商品仍有库存，无法删除")
    if db.query(StockMove).filter(StockMove.product_id == product_id).count():
        raise Conflict("该商品存在出入库记录，无法删除，请改为下架")
    search_engine.delete_document(product_id)
    db.delete(product)
    db.flush()
    return ok({"deleted": True})


@router.post("/products/{product_id}/publish", response_model=ApiResponse[ProductOut], summary="商品上架")
def publish_product(
    product_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:write")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    if not is_unrestricted(user) and product.enterprise_id != user.enterprise_id:
        raise Forbidden("只能操作本企业的商品")
    if product.audit_status != "approved" and not user.is_superuser:
        raise Conflict("商品尚未通过审核，不能上架")
    if product.status == "published":
        raise Conflict("商品已处于上架状态")
    product.status = "published"
    db.flush()
    _index_product(lk, product)
    integration.enqueue(
        db,
        event_type="product.published",
        aggregate_type="product",
        aggregate_id=product.code,
        payload=integration.product_payload(product, lk.category_name(product.category_id)),
    )
    return ok(product_out(lk, product))


@router.post("/products/{product_id}/offline", response_model=ApiResponse[ProductOut], summary="商品下架")
def offline_product(
    product_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:write")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    if not is_unrestricted(user) and product.enterprise_id != user.enterprise_id:
        raise Forbidden("只能操作本企业的商品")
    product.status = "offline"
    db.flush()
    _index_product(lk, product)
    return ok(product_out(lk, product))


@router.post("/products/{product_id}/audit", response_model=ApiResponse[ProductOut], summary="商品审核")
def audit_product(
    product_id: int,
    payload: ProductAuditIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:audit")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    product.audit_status = "approved" if payload.approved else "rejected"
    product.audit_remark = payload.remark
    if not payload.approved:
        product.status = "rejected"
    db.flush()
    return ok(product_out(lk, product))


@router.get(
    "/products/{product_id}/inventory",
    response_model=ApiResponse[dict],
    summary="商品各仓库库存",
)
def product_inventory(
    product_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("product:read")),
) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("商品不存在")
    rows = (
        db.query(Inventory)
        .filter(Inventory.product_id == product_id)
        .order_by(Inventory.warehouse_id.asc(), Inventory.id.asc())
        .all()
    )
    total, locked, available = product_availability(db, product_id)
    return ok(
        {
            "product_id": product.id,
            "product_name": product.name,
            "unit": product.unit,
            "total_quantity": float(total),
            "locked_quantity": float(locked),
            "available_quantity": float(available),
            "items": [inventory_out(lk, row) for row in rows],
        }
    )
