# -*- coding: utf-8 -*-
"""开放浏览后的留资、用户收藏和企业自助入口。"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user, require_login, require
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.response import ApiResponse, ok
from app.core.scope import role_codes
from app.core.timeutil import now
from app.integrations.storage import storage
from app.models.enterprise import Enterprise
from app.models.matching import LeadFollowup, MatchLead, ProductFavorite, PurchaseRequirement
from app.models.org import User
from app.models.product import Category, Product
from app.models.system import SysFile
from app.schemas.portal import (
    EnterpriseApplyIn, EnterpriseSelfImageIn, EnterpriseSelfUpdate,
    LeadFollowupIn, LeadIn, LeadUpdate,
)
from app.services.enterprise_images import enterprise_image_urls
from app.services.numbering import next_no
from app.services.product_images import public_product_image

router = APIRouter(prefix="/portal", tags=["开放留资与用户中心"])
PHONE_RE = re.compile(r"^[0-9+()\-\s]{7,32}$")
LEAD_STATUSES = {"new", "following", "completed"}


def _operator(user: User) -> None:
    if not user.is_superuser and "platform_admin" not in role_codes(user):
        raise Forbidden("仅平台运营人员可处理线索")


def _published_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    enterprise = db.get(Enterprise, product.enterprise_id) if product else None
    if (not product or product.status != "published" or product.audit_status != "approved"
            or product.supply_status != "active" or not enterprise
            or enterprise.status != "active" or enterprise.audit_status != "approved"):
        raise NotFound("供应信息不存在或未公开")
    return product


def _lead(db: Session, row: MatchLead, private: bool = False) -> dict:
    product = db.get(Product, row.product_id) if row.product_id else None
    supplier = db.get(Enterprise, row.supplier_enterprise_id) if row.supplier_enterprise_id else None
    result = {
        "id": row.id, "product_id": row.product_id,
        "product_name": product.name if product else None,
        "intent_product": row.intent_product, "quantity": float(row.quantity) if row.quantity is not None else None,
        "need_content": row.need_content, "status": row.status,
        "supplier_enterprise_id": row.supplier_enterprise_id,
        "supplier_enterprise_name": supplier.name if supplier else None,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }
    if private:
        operator = db.get(User, row.operator_id) if row.operator_id else None
        result.update({
            "user_id": row.user_id, "contact_name": row.contact_name,
            "contact_phone": row.contact_phone, "operator_id": row.operator_id,
            "operator_name": operator.full_name or operator.username if operator else None,
            "result": row.result,
            "followups": [{"id": item.id, "note": item.note, "created_at": item.created_at,
                           "created_by": item.created_by} for item in row.followups],
        })
    return result


def _enterprise(db: Session, row: Enterprise) -> dict:
    return {
        "id": row.id, "name": row.name, "enterprise_type": row.enterprise_type,
        "profile": row.profile, "business_scope": row.business_scope,
        "contact_name": row.contact_name, "contact_phone": row.contact_phone,
        "region": row.region, "address": row.address,
        "qualifications": row.qualifications or [], "audit_status": row.audit_status,
        "audit_remark": row.audit_remark,
        "image_url": enterprise_image_urls(db, [row.id]).get(row.id),
    }


@router.post("/leads", response_model=ApiResponse[dict], summary="游客或用户留下合作需求")
def create_lead(payload: LeadIn, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)) -> dict:
    phone = payload.contact_phone.strip()
    if not PHONE_RE.fullmatch(phone):
        raise BadRequest("请填写有效联系电话")
    product = _published_product(db, payload.product_id) if payload.product_id else None
    enterprise = db.get(Enterprise, payload.enterprise_id) if payload.enterprise_id else None
    if payload.enterprise_id and (enterprise is None or enterprise.status != "active" or enterprise.audit_status != "approved"):
        raise NotFound("企业不存在或未公开")
    if product and enterprise and product.enterprise_id != enterprise.id:
        raise BadRequest("供应信息与企业不匹配")
    intent = product.name if product else (payload.intent_product or "").strip()
    if len(intent) < 2:
        raise BadRequest("请填写意向产品")
    recent_count = db.query(MatchLead).filter(
        MatchLead.contact_phone == phone,
        MatchLead.created_at >= now() - timedelta(hours=1),
    ).count()
    if recent_count >= 5:
        raise Conflict("提交过于频繁，请稍后再试")
    row = MatchLead(
        user_id=user.id if user else None, product_id=product.id if product else None,
        intent_product=intent, quantity=payload.quantity,
        contact_name=payload.contact_name.strip(), contact_phone=phone,
        need_content=payload.need_content.strip(),
        supplier_enterprise_id=product.enterprise_id if product else enterprise.id if enterprise else None,
        status="new",
    )
    db.add(row)
    db.flush()
    return ok({"id": row.id, "status": row.status, "message": "需求已提交，平台运营人员将联系您"})


@router.get("/me/leads", response_model=ApiResponse[dict], summary="我的咨询记录")
def my_leads(db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    rows = db.query(MatchLead).filter(MatchLead.user_id == user.id).order_by(MatchLead.id.desc()).limit(200).all()
    return ok({"items": [{**_lead(db, row), "contact_name": row.contact_name,
                          "contact_phone": row.contact_phone, "result": row.result} for row in rows], "total": len(rows)})


@router.get("/me/favorites", response_model=ApiResponse[dict], summary="我的供应收藏")
def my_favorites(db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    rows = db.query(ProductFavorite).filter(ProductFavorite.user_id == user.id).order_by(ProductFavorite.id.desc()).all()
    items = []
    for row in rows:
        product = db.get(Product, row.product_id)
        if not product or product.status != "published" or product.audit_status != "approved":
            continue
        enterprise = db.get(Enterprise, product.enterprise_id)
        if not enterprise or enterprise.audit_status != "approved" or enterprise.status != "active":
            continue
        category = db.get(Category, product.category_id)
        items.append({"id": row.id, "product_id": product.id, "product_name": product.name,
                      "enterprise_name": enterprise.name,
                      "image": public_product_image(product.main_image, category.code if category else ""),
                      "created_at": row.created_at})
    return ok({"items": items, "total": len(items)})


@router.post("/me/favorites/{product_id}", response_model=ApiResponse[dict], summary="收藏供应")
def add_favorite(product_id: int, db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    _published_product(db, product_id)
    row = db.query(ProductFavorite).filter(ProductFavorite.user_id == user.id,
                                           ProductFavorite.product_id == product_id).first()
    if row is None:
        db.add(ProductFavorite(user_id=user.id, product_id=product_id))
        db.flush()
    return ok({"product_id": product_id, "favorited": True})


@router.delete("/me/favorites/{product_id}", response_model=ApiResponse[dict], summary="取消供应收藏")
def remove_favorite(product_id: int, db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    db.query(ProductFavorite).filter(ProductFavorite.user_id == user.id,
                                     ProductFavorite.product_id == product_id).delete()
    db.flush()
    return ok({"product_id": product_id, "favorited": False})


@router.get("/me/requirements", response_model=ApiResponse[dict], summary="本企业发布的采购需求")
def my_requirements(db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    if not user.enterprise_id:
        return ok({"items": [], "total": 0})
    rows = db.query(PurchaseRequirement).filter(
        PurchaseRequirement.buyer_enterprise_id == user.enterprise_id
    ).order_by(PurchaseRequirement.id.desc()).limit(200).all()
    return ok({"items": [{"id": row.id, "title": row.title, "quantity": float(row.quantity),
                           "unit": row.unit, "status": row.status, "created_at": row.created_at}
                          for row in rows], "total": len(rows)})


@router.get("/me/enterprise", response_model=ApiResponse[dict], summary="我的企业资料及认证状态")
def my_enterprise(db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    enterprise = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    return ok(_enterprise(db, enterprise) if enterprise else None)


@router.post("/me/enterprise", response_model=ApiResponse[dict], summary="申请企业身份")
def apply_enterprise(payload: EnterpriseApplyIn, db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    if user.enterprise_id:
        raise Conflict("账号已关联企业，请在个人中心查看审核状态")
    if payload.enterprise_type not in {"supplier", "buyer", "merchant"}:
        raise BadRequest("企业类型无效")
    if not PHONE_RE.fullmatch(payload.contact_phone.strip()):
        raise BadRequest("请填写有效联系电话")
    if db.query(Enterprise).filter(Enterprise.name == payload.name.strip()).first():
        raise Conflict("企业名称已存在，请联系平台运营人员")
    row = Enterprise(
        code=next_no(db, "enterprise", f"ENT-{date.today().year}"),
        name=payload.name.strip(), enterprise_type=payload.enterprise_type,
        profile=payload.profile, business_scope=payload.business_scope,
        contact_name=payload.contact_name.strip(), contact_phone=payload.contact_phone.strip(),
        region=payload.region, address=payload.address,
        qualifications=[item.strip() for item in payload.qualifications if item.strip()],
        audit_status="pending", status="active",
    )
    db.add(row)
    db.flush()
    user.enterprise_id = row.id
    db.flush()
    return ok(_enterprise(db, row))


@router.put("/me/enterprise", response_model=ApiResponse[dict], summary="维护本企业资料")
def update_my_enterprise(payload: EnterpriseSelfUpdate, db: Session = Depends(get_db),
                         user: User = Depends(require_login)) -> dict:
    row = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    if row is None:
        raise NotFound("请先提交企业申请")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush()
    return ok(_enterprise(db, row))


@router.post("/me/enterprise/image", response_model=ApiResponse[dict], summary="上传本企业展示图")
def set_my_enterprise_image(payload: EnterpriseSelfImageIn, db: Session = Depends(get_db),
                            user: User = Depends(require_login)) -> dict:
    enterprise = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    if enterprise is None:
        raise NotFound("请先提交企业申请")
    image = db.query(SysFile).filter(SysFile.file_key == payload.file_key,
                                     SysFile.uploader_id == user.id,
                                     SysFile.biz_type == "enterprise_image",
                                     SysFile.biz_id.is_(None)).first()
    if image is None:
        raise BadRequest("请选择本账号刚上传的企业图片")
    ext = (image.original_name or "").lower().rsplit(".", 1)[-1]
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        raise BadRequest("企业展示图仅支持 JPG、PNG、WebP")
    stream = storage.open_stream(image.object_name, image.bucket)
    if stream is None:
        raise BadRequest("上传的图片无法读取")
    try:
        header = stream.read(12)
    finally:
        stream.close()
    valid = ((ext in {"jpg", "jpeg"} and header.startswith(b"\xff\xd8\xff")) or
             (ext == "png" and header.startswith(b"\x89PNG\r\n\x1a\n")) or
             (ext == "webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP"))
    if not valid:
        raise BadRequest("图片内容与格式不符")
    image.biz_id = enterprise.id
    db.flush()
    return ok(_enterprise(db, enterprise))


@router.get("/me/enterprise-leads", response_model=ApiResponse[dict], summary="本企业咨询线索")
def my_enterprise_leads(db: Session = Depends(get_db), user: User = Depends(require_login)) -> dict:
    enterprise = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    if enterprise is None or enterprise.audit_status != "approved":
        raise Forbidden("企业审核通过后可查看合作意向")
    rows = db.query(MatchLead).filter(MatchLead.supplier_enterprise_id == enterprise.id).order_by(MatchLead.id.desc()).limit(200).all()
    return ok({"items": [_lead(db, row, True) for row in rows], "total": len(rows)})


@router.post("/me/enterprise-leads/{lead_id}/response", response_model=ApiResponse[dict], summary="企业处理合作意向")
def enterprise_response(lead_id: int, payload: LeadFollowupIn, db: Session = Depends(get_db),
                        user: User = Depends(require_login)) -> dict:
    enterprise = db.get(Enterprise, user.enterprise_id) if user.enterprise_id else None
    if enterprise is None or enterprise.audit_status != "approved":
        raise Forbidden("企业审核通过后可处理合作意向")
    row = db.get(MatchLead, lead_id)
    if row is None or row.supplier_enterprise_id != enterprise.id:
        raise NotFound("合作意向不存在")
    if row.status == "completed":
        raise Conflict("该线索已完成")
    db.add(LeadFollowup(lead_id=row.id, note=payload.note.strip(), created_by=user.id))
    row.status = "following"
    db.flush()
    return ok(_lead(db, row, True))


@router.get("/operations/leads/summary", response_model=ApiResponse[dict], summary="线索中心统计")
def lead_summary(db: Session = Depends(get_db), user: User = Depends(require("trade:read"))) -> dict:
    _operator(user)
    counts = {key: db.query(MatchLead).filter(MatchLead.status == key).count()
              for key in ("new", "following", "completed")}
    counts["today"] = db.query(MatchLead).filter(
        MatchLead.created_at >= datetime.combine(now().date(), time.min)).count()
    counts["total"] = sum(counts[key] for key in ("new", "following", "completed"))
    return ok(counts)


@router.get("/operations/leads", response_model=ApiResponse[dict], summary="运营线索列表")
def operator_leads(status: str | None = Query(None), db: Session = Depends(get_db),
                   user: User = Depends(require("trade:read"))) -> dict:
    _operator(user)
    if status and status not in LEAD_STATUSES:
        raise BadRequest("线索状态无效")
    query = db.query(MatchLead)
    if status:
        query = query.filter(MatchLead.status == status)
    total = query.count()
    rows = query.order_by(MatchLead.id.desc()).limit(200).all()
    return ok({"items": [_lead(db, row, True) for row in rows], "total": total})


@router.put("/operations/leads/{lead_id}", response_model=ApiResponse[dict], summary="分配企业与更新线索状态")
def update_lead(lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db),
                user: User = Depends(require("trade:write"))) -> dict:
    _operator(user)
    row = db.get(MatchLead, lead_id)
    if row is None:
        raise NotFound("线索不存在")
    if payload.status not in LEAD_STATUSES:
        raise BadRequest("线索状态无效")
    if row.status == "completed" and payload.status != "completed":
        raise Conflict("已完成线索不能重新流转")
    if "supplier_enterprise_id" in payload.model_fields_set:
        if payload.supplier_enterprise_id is None:
            row.supplier_enterprise_id = None
        else:
            supplier = db.get(Enterprise, payload.supplier_enterprise_id)
            if (supplier is None or supplier.audit_status != "approved" or supplier.status != "active"
                    or supplier.enterprise_type not in ("supplier", "merchant")):
                raise BadRequest("供应企业不存在或尚未认证")
            row.supplier_enterprise_id = supplier.id
    if payload.status == "completed" and not (payload.result or row.result):
        raise BadRequest("完成线索时请填写处理结果")
    row.status = payload.status
    row.operator_id = user.id
    if payload.result is not None:
        row.result = payload.result.strip()
    db.flush()
    return ok(_lead(db, row, True))


@router.post("/operations/leads/{lead_id}/followups", response_model=ApiResponse[dict], summary="运营线索跟进")
def add_lead_followup(lead_id: int, payload: LeadFollowupIn, db: Session = Depends(get_db),
                      user: User = Depends(require("trade:write"))) -> dict:
    _operator(user)
    row = db.get(MatchLead, lead_id)
    if row is None:
        raise NotFound("线索不存在")
    if row.status == "completed":
        raise Conflict("已完成线索不能追加跟进")
    row.status = "following"
    row.operator_id = user.id
    item = LeadFollowup(lead_id=row.id, note=payload.note.strip(), created_by=user.id)
    db.add(item)
    db.flush()
    return ok(_lead(db, row, True))
