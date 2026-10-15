# -*- coding: utf-8 -*-
"""V1.1 产业供需门户与平台人工撮合。"""
from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.response import ApiResponse, ok
from app.core.scope import role_codes
from app.core.timeutil import now
from app.models.enterprise import Enterprise
from app.models.matching import MatchCase, MatchFollowup, PurchaseRequirement
from app.models.org import User
from app.models.product import Category, Inventory, Product
from app.schemas.matching import FollowupIn, MatchIn, MatchUpdate, RequirementIn, RequirementStatusUpdate
from app.services.enterprise_images import enterprise_image_urls
from app.services.product_images import public_product_image

router = APIRouter(prefix="/marketplace", tags=["产业供需撮合"])
MATCH_STATUSES = ("pending", "matching", "contacted", "success", "closed")
VALID_UNITS = ("ton", "kg", "bag", "piece")


def _operator(user: User) -> None:
    if not user.is_superuser and "platform_admin" not in role_codes(user):
        raise Forbidden("仅平台运营人员可管理撮合")


def _requirement(row: PurchaseRequirement, buyer_name: str | None = None, private: bool = False) -> dict:
    return {
        "id": row.id, "title": row.title, "product_name": row.product_name,
        "category_id": row.category_id, "quantity": float(row.quantity), "unit": row.unit,
        "requirements": row.requirements, "purchase_region": row.purchase_region,
        "buyer_enterprise_id": row.buyer_enterprise_id, "buyer_enterprise_name": buyer_name,
        "status": row.status, "created_at": row.created_at,
        **({"contact_name": row.contact_name, "contact_phone": row.contact_phone} if private else {}),
    }


def _case(db: Session, row: MatchCase) -> dict:
    requirement = db.get(PurchaseRequirement, row.requirement_id)
    supplier = db.get(Enterprise, row.supplier_enterprise_id)
    buyer = db.get(Enterprise, requirement.buyer_enterprise_id) if requirement else None
    return {
        "id": row.id, "requirement_id": row.requirement_id,
        "requirement": _requirement(requirement, buyer.name if buyer else None, True) if requirement else None,
        "supplier_enterprise_id": row.supplier_enterprise_id,
        "supplier_enterprise_name": supplier.name if supplier else None,
        "operator_id": row.operator_id, "source": row.source, "status": row.status,
        "contact_name": row.contact_name, "contact_phone": row.contact_phone,
        "result": row.result, "created_at": row.created_at, "updated_at": row.updated_at,
        "followups": [{"id": f.id, "note": f.note, "created_by": f.created_by, "created_at": f.created_at} for f in row.followups],
    }


@router.get("/supplies", response_model=ApiResponse[dict], summary="公开供应大厅")
def supplies(
    page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=60),
    keyword: str | None = None, category_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    query = (db.query(Product, Category.name, Category.code, Enterprise.name)
             .join(Category, Category.id == Product.category_id)
             .join(Enterprise, Enterprise.id == Product.enterprise_id)
             .filter(Product.status == "published", Product.audit_status == "approved",
                     Product.supply_status == "active", Enterprise.status == "active",
                     Enterprise.audit_status == "approved"))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Product.name.like(like), Enterprise.name.like(like), Product.origin.like(like)))
    total = query.count()
    rows = query.order_by(Product.created_at.desc(), Product.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    ids = [r[0].id for r in rows]
    stocks = dict(db.query(Inventory.product_id, func.sum(Inventory.quantity - Inventory.locked_quantity)).filter(Inventory.product_id.in_(ids)).group_by(Inventory.product_id).all()) if ids else {}
    return ok({"items": [{
        "id": p.id, "name": p.name, "category": category, "category_id": p.category_id,
        "enterprise": company, "enterprise_id": p.enterprise_id, "origin": p.origin,
        "spec": p.spec, "image": public_product_image(p.main_image, category_code), "supply_quantity": float(p.supply_quantity or stocks.get(p.id) or 0),
        "unit": p.unit, "supply_period": p.supply_period, "pricing_mode": p.pricing_mode,
        "price": float(p.price or 0), "supply_status": p.supply_status,
        "allow_inquiry": p.allow_inquiry, "allow_bulk_purchase": p.allow_bulk_purchase,
        "created_at": p.created_at,
    } for p, category, category_code, company in rows], "total": total, "page": page, "page_size": page_size})


@router.get("/enterprises/{enterprise_id}", response_model=ApiResponse[dict], summary="公开企业主页")
def enterprise_profile(enterprise_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Enterprise, enterprise_id)
    if row is None or row.status != "active" or row.audit_status != "approved":
        raise NotFound("企业未公开")
    products = (db.query(Product, Category.code).join(Category, Category.id == Product.category_id)
                .filter(Product.enterprise_id == row.id, Product.status == "published",
                        Product.audit_status == "approved", Product.supply_status == "active")
                .order_by(Product.id.desc()).limit(12).all())
    image = enterprise_image_urls(db, [row.id]).get(row.id)
    return ok({"id": row.id, "name": row.name, "profile": row.profile or row.business_scope,
               "business_scope": row.business_scope, "qualifications": row.qualifications or [],
               "region": row.region, "address": row.address, "enterprise_type": row.enterprise_type,
               "contact_name": row.contact_name, "contact_phone": row.contact_phone,
               "image": image, "products": [{"id": p.id, "name": p.name, "image": public_product_image(p.main_image, category_code),
               "origin": p.origin, "pricing_mode": p.pricing_mode, "price": float(p.price or 0)} for p, category_code in products]})


@router.get("/supplies/{product_id}", response_model=ApiResponse[dict], summary="公开供应详情")
def supply_detail(product_id: int, db: Session = Depends(get_db)) -> dict:
    row = (db.query(Product, Category.name, Category.code, Enterprise.name)
           .join(Category, Category.id == Product.category_id)
           .join(Enterprise, Enterprise.id == Product.enterprise_id)
           .filter(Product.id == product_id, Product.status == "published", Product.audit_status == "approved",
                   Enterprise.status == "active", Enterprise.audit_status == "approved").first())
    if row is None:
        raise NotFound("供应信息不存在或未公开")
    product, category, category_code, company = row
    available = db.query(func.sum(Inventory.quantity - Inventory.locked_quantity)).filter(Inventory.product_id == product.id).scalar()
    return ok({"id": product.id, "name": product.name, "category": category, "enterprise": company,
               "enterprise_id": product.enterprise_id, "origin": product.origin, "spec": product.spec,
               "grade": product.grade, "image": public_product_image(product.main_image, category_code), "images": product.images or [],
               "supply_quantity": float(product.supply_quantity or available or 0), "unit": product.unit,
               "supply_period": product.supply_period, "pricing_mode": product.pricing_mode,
               "price": float(product.price or 0), "supply_status": product.supply_status,
               "allow_inquiry": product.allow_inquiry, "allow_bulk_purchase": product.allow_bulk_purchase,
               "description": product.description, "created_at": product.created_at})


@router.get("/requirements", response_model=ApiResponse[dict], summary="公开采购大厅")
def requirements(
    page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=60),
    keyword: str | None = None, db: Session = Depends(get_db),
) -> dict:
    query = (db.query(PurchaseRequirement, Enterprise.name)
             .join(Enterprise, Enterprise.id == PurchaseRequirement.buyer_enterprise_id)
             .filter(PurchaseRequirement.status == "open", Enterprise.status == "active", Enterprise.audit_status == "approved"))
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(PurchaseRequirement.title.like(like), PurchaseRequirement.product_name.like(like)))
    total = query.count()
    rows = query.order_by(PurchaseRequirement.created_at.desc(), PurchaseRequirement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok({"items": [_requirement(row, name) for row, name in rows], "total": total, "page": page, "page_size": page_size})


@router.post("/requirements", response_model=ApiResponse[dict], summary="发布采购需求")
def create_requirement(payload: RequirementIn, db: Session = Depends(get_db), user: User = Depends(require("trade:write"))) -> dict:
    if payload.unit not in VALID_UNITS:
        raise BadRequest("采购单位无效")
    if payload.category_id and db.get(Category, payload.category_id) is None:
        raise BadRequest("产品分类不存在")
    buyer = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    if buyer is None or buyer.status != "active" or buyer.audit_status != "approved":
        raise Forbidden("请先使用已审核的企业账号发布采购需求")
    row = PurchaseRequirement(**payload.model_dump(), buyer_enterprise_id=buyer.id,
                              created_by=user.id, status="pending")
    db.add(row)
    db.flush()
    return ok(_requirement(row, buyer.name, True))


@router.post("/requirements/{requirement_id}/interest", response_model=ApiResponse[dict], summary="供应企业表达供货意向")
def express_interest(requirement_id: int, db: Session = Depends(get_db), user: User = Depends(require("trade:write"))) -> dict:
    requirement = db.get(PurchaseRequirement, requirement_id)
    if requirement is None or requirement.status != "open":
        raise NotFound("采购需求不存在或已关闭")
    supplier = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    if supplier is None or supplier.status != "active" or supplier.audit_status != "approved" or supplier.enterprise_type not in ("supplier", "merchant"):
        raise Forbidden("请使用已审核的供应企业账号")
    if supplier.id == requirement.buyer_enterprise_id:
        raise BadRequest("不能响应本企业的采购需求")
    existing = db.query(MatchCase).filter(MatchCase.requirement_id == requirement_id, MatchCase.supplier_enterprise_id == supplier.id, MatchCase.status != "closed").first()
    if existing:
        raise Conflict("已提交供货意向，请等待平台联系")
    row = MatchCase(requirement_id=requirement_id, supplier_enterprise_id=supplier.id, source="interest", status="pending")
    db.add(row)
    db.flush()
    return ok({"id": row.id, "status": row.status})


@router.get("/operations/summary", response_model=ApiResponse[dict], summary="撮合运营看板")
def operations_summary(db: Session = Depends(get_db), user: User = Depends(require("trade:read"))) -> dict:
    _operator(user)
    today = datetime.combine(now().date(), time.min)
    return ok({
        "supplier_enterprises": db.query(Enterprise).filter(Enterprise.status == "active", Enterprise.audit_status == "approved", Enterprise.enterprise_type.in_(["supplier", "merchant"])).count(),
        "supply_count": db.query(Product).filter(Product.status == "published", Product.audit_status == "approved", Product.supply_status == "active").count(),
        "requirement_count": db.query(PurchaseRequirement).count(),
        "match_count": db.query(MatchCase).count(),
        "success_count": db.query(MatchCase).filter(MatchCase.status == "success").count(),
        "today_supplies": db.query(Product).filter(Product.created_at >= today).count(),
        "today_requirements": db.query(PurchaseRequirement).filter(PurchaseRequirement.created_at >= today).count(),
        "pending_matches": db.query(MatchCase).filter(MatchCase.status == "pending").count(),
    })


@router.get("/operations/requirements", response_model=ApiResponse[dict], summary="运营采购需求池")
def operator_requirements(db: Session = Depends(get_db), user: User = Depends(require("trade:read"))) -> dict:
    _operator(user)
    rows = db.query(PurchaseRequirement, Enterprise.name).join(Enterprise, Enterprise.id == PurchaseRequirement.buyer_enterprise_id).order_by(PurchaseRequirement.created_at.desc()).limit(200).all()
    return ok({"items": [_requirement(row, name, True) for row, name in rows], "total": len(rows)})


@router.put("/operations/requirements/{requirement_id}", response_model=ApiResponse[dict], summary="关闭或重开采购需求")
def update_requirement(requirement_id: int, payload: RequirementStatusUpdate,
                       db: Session = Depends(get_db), user: User = Depends(require("trade:write"))) -> dict:
    _operator(user)
    if payload.status not in ("pending", "open", "rejected", "closed"):
        raise BadRequest("采购需求状态无效")
    row = db.get(PurchaseRequirement, requirement_id)
    if row is None:
        raise NotFound("采购需求不存在")
    if row.status == "rejected" and payload.status == "open":
        raise Conflict("已驳回需求请由企业重新提交")
    row.status = payload.status
    db.flush()
    buyer = db.get(Enterprise, row.buyer_enterprise_id)
    return ok(_requirement(row, buyer.name if buyer else None, True))


@router.get("/operations/matches", response_model=ApiResponse[dict], summary="撮合管理列表")
def matches(db: Session = Depends(get_db), user: User = Depends(require("trade:read"))) -> dict:
    _operator(user)
    rows = db.query(MatchCase).order_by(MatchCase.created_at.desc(), MatchCase.id.desc()).limit(200).all()
    return ok({"items": [_case(db, row) for row in rows], "total": len(rows)})


@router.post("/operations/matches", response_model=ApiResponse[dict], summary="人工匹配供应企业")
def create_match(payload: MatchIn, requirement_id: int, db: Session = Depends(get_db), user: User = Depends(require("trade:write"))) -> dict:
    _operator(user)
    requirement = db.get(PurchaseRequirement, requirement_id)
    supplier = db.get(Enterprise, payload.supplier_enterprise_id)
    if requirement is None or requirement.status != "open":
        raise NotFound("采购需求不存在或已关闭")
    if supplier is None or supplier.status != "active" or supplier.audit_status != "approved" or supplier.enterprise_type not in ("supplier", "merchant"):
        raise BadRequest("供应企业不存在或尚未通过审核")
    if supplier.id == requirement.buyer_enterprise_id:
        raise BadRequest("供需双方不能是同一企业")
    existing = db.query(MatchCase).filter(MatchCase.requirement_id == requirement_id, MatchCase.supplier_enterprise_id == supplier.id, MatchCase.status != "closed").first()
    if existing:
        raise Conflict("该供应企业已参与本次撮合")
    row = MatchCase(requirement_id=requirement_id, supplier_enterprise_id=supplier.id,
                    operator_id=user.id, source="manual", status="matching",
                    contact_name=payload.contact_name, contact_phone=payload.contact_phone)
    db.add(row)
    db.flush()
    return ok(_case(db, row))


@router.put("/operations/matches/{case_id}", response_model=ApiResponse[dict], summary="更新撮合状态和结果")
def update_match(case_id: int, payload: MatchUpdate, db: Session = Depends(get_db), user: User = Depends(require("trade:write"))) -> dict:
    _operator(user)
    row = db.get(MatchCase, case_id)
    if row is None:
        raise NotFound("撮合记录不存在")
    if payload.status not in MATCH_STATUSES:
        raise BadRequest("撮合状态无效")
    if row.status in ("success", "closed") and payload.status != row.status:
        raise Conflict("已结束的撮合不能重新流转")
    if payload.status == "success" and not (payload.result or row.result):
        raise BadRequest("撮合成功时请记录结果")
    row.status = payload.status
    row.operator_id = user.id
    if payload.result is not None:
        row.result = payload.result
    if payload.contact_name is not None:
        row.contact_name = payload.contact_name
    if payload.contact_phone is not None:
        row.contact_phone = payload.contact_phone
    if payload.status in ("success", "closed"):
        row.closed_at = now()
    db.flush()
    return ok(_case(db, row))


@router.post("/operations/matches/{case_id}/followups", response_model=ApiResponse[dict], summary="添加人工跟进记录")
def add_followup(case_id: int, payload: FollowupIn, db: Session = Depends(get_db), user: User = Depends(require("trade:write"))) -> dict:
    _operator(user)
    row = db.get(MatchCase, case_id)
    if row is None:
        raise NotFound("撮合记录不存在")
    if row.status in ("success", "closed"):
        raise Conflict("撮合已结束，不能追加跟进")
    followup = MatchFollowup(case_id=row.id, note=payload.note, created_by=user.id)
    db.add(followup)
    db.flush()
    return ok({"id": followup.id, "note": followup.note, "created_at": followup.created_at})
