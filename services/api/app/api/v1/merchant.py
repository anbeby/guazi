# -*- coding: utf-8 -*-
"""商户/企业接口：档案、审核、统计。"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups, enterprise_out
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import apply_own_enterprise, enterprise_scope_ids, is_unrestricted
from app.core.security import hash_password
from app.core.timeutil import now
from app.models.enterprise import Enterprise, Park, Stall
from app.models.org import OrgUnit, Role, User
from app.models.product import Inventory, Product, Warehouse
from app.models.settlement import Settlement
from app.models.trade import Inquiry, TradeOrder
from app.models.system import SysFile
from app.schemas.merchant import (
    EnterpriseAuditIn,
    EnterpriseImageIn,
    EnterpriseIn,
    EnterpriseOut,
    EnterpriseStatsOut,
    EnterpriseUpdate,
)
from app.services import integration
from app.services.inventory_service import dec
from app.services.numbering import next_no
from app.services.enterprise_images import enterprise_image_urls
from app.integrations.storage import storage

router = APIRouter(prefix="/enterprises", tags=["商户管理"])

VALID_TYPES = ("merchant", "supplier", "buyer", "platform")


@router.get("", response_model=ApiResponse[PageData[EnterpriseOut]], summary="企业/商户列表")
def list_enterprises(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    enterprise_type: Optional[str] = None,
    audit_status: Optional[str] = None,
    status: Optional[str] = None,
    park_id: Optional[int] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("merchant:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Enterprise)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Enterprise.name.like(like),
                Enterprise.code.like(like),
                Enterprise.unified_social_credit_code.like(like),
                Enterprise.contact_name.like(like),
                Enterprise.contact_phone.like(like),
            )
        )
    if enterprise_type:
        query = query.filter(Enterprise.enterprise_type == enterprise_type)
    if audit_status:
        query = query.filter(Enterprise.audit_status == audit_status)
    if status:
        query = query.filter(Enterprise.status == status)
    if park_id:
        query = query.filter(Enterprise.park_id == park_id)
    query = apply_own_enterprise(query, Enterprise, user, "id", db)
    total = query.count()
    rows = query.order_by(Enterprise.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    images = enterprise_image_urls(db, [row.id for row in rows])
    items = [{**enterprise_out(lk, row), "image_url": images.get(row.id)} for row in rows]
    return ok(paginate(items, total, page, page_size))


@router.post("", response_model=ApiResponse[EnterpriseOut], summary="创建企业（入驻申请）")
def create_enterprise(
    payload: EnterpriseIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("merchant:write")),
) -> dict:
    if payload.enterprise_type not in VALID_TYPES:
        raise BadRequest(f"企业类型取值必须为 {'/'.join(VALID_TYPES)}")
    if payload.unified_social_credit_code:
        exists = (
            db.query(Enterprise)
            .filter(Enterprise.unified_social_credit_code == payload.unified_social_credit_code)
            .first()
        )
        if exists:
            raise Conflict(f"统一社会信用代码已存在：{payload.unified_social_credit_code}")
    if payload.park_id and not db.get(Park, payload.park_id):
        raise BadRequest("园区不存在")
    code = payload.code or next_no(db, "enterprise", f"ENT-{date.today().year}")
    if db.query(Enterprise).filter(Enterprise.code == code).first():
        raise Conflict(f"企业编码已存在：{code}")
    data = payload.model_dump(exclude={"create_account", "account_username", "account_password", "code"})
    enterprise = Enterprise(code=code, **data)
    enterprise.audit_status = "pending"
    db.add(enterprise)
    db.flush()
    account_username = None
    if payload.create_account:
        account_username = payload.account_username or f"ent{enterprise.id:04d}"
        if db.query(User).filter(User.username == account_username).first():
            raise Conflict(f"账号已存在：{account_username}")
        role_code = "buyer" if enterprise.enterprise_type == "buyer" else "merchant"
        role = db.query(Role).filter(Role.code == role_code).first()
        account = User(
            username=account_username,
            password_hash=hash_password(payload.account_password or os.getenv("INITIAL_OPERATOR_PASSWORD", "Gz@123456")),
            full_name=payload.contact_name or enterprise.name,
            phone=payload.contact_phone,
            enterprise_id=enterprise.id,
            status="active",
        )
        if role is not None:
            account.roles = [role]
        db.add(account)
        db.flush()
    integration.enqueue(
        db,
        event_type="enterprise.created",
        aggregate_type="enterprise",
        aggregate_id=enterprise.code,
        payload=integration.enterprise_payload(enterprise),
    )
    result = enterprise_out(lk, enterprise)
    if account_username:
        result["account_username"] = account_username
    return ok(result)


@router.get("/{enterprise_id}", response_model=ApiResponse[EnterpriseOut], summary="企业详情")
def get_enterprise(
    enterprise_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("merchant:read")),
) -> dict:
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if enterprise.id not in allowed:
            raise Forbidden("无权查看该企业")
    image = enterprise_image_urls(db, [enterprise.id]).get(enterprise.id)
    return ok({**enterprise_out(lk, enterprise), "image_url": image})


@router.put("/{enterprise_id}/image", response_model=ApiResponse[EnterpriseOut], summary="管理员更换企业展示图")
def set_enterprise_image(
    enterprise_id: int,
    payload: EnterpriseImageIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("merchant:write")),
) -> dict:
    if not user.is_superuser:
        raise Forbidden("仅平台管理员可更换企业展示图")
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    image = db.query(SysFile).filter(SysFile.file_key == payload.file_key).first()
    if image is None or image.biz_type != "enterprise_image" or image.uploader_id != user.id:
        raise BadRequest("请选择刚上传的企业图片")
    if image.biz_id is not None:
        raise Conflict("图片已关联企业，请重新上传")
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
    valid = (
        (ext in {"jpg", "jpeg"} and header.startswith(b"\xff\xd8\xff")) or
        (ext == "png" and header.startswith(b"\x89PNG\r\n\x1a\n")) or
        (ext == "webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP")
    )
    if not valid:
        raise BadRequest("图片内容与格式不符")
    image.content_type = "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"
    image.biz_id = enterprise.id
    db.flush()
    return ok({**enterprise_out(lk, enterprise), "image_url": image.url})


@router.put("/{enterprise_id}", response_model=ApiResponse[EnterpriseOut], summary="更新企业")
def update_enterprise(
    enterprise_id: int,
    payload: EnterpriseUpdate,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("merchant:write")),
) -> dict:
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    if not is_unrestricted(user) and enterprise.id != user.enterprise_id:
        raise Forbidden("只能修改本企业档案")
    data = payload.model_dump(exclude_unset=True)
    if data.get("enterprise_type") and data["enterprise_type"] not in VALID_TYPES:
        raise BadRequest(f"企业类型取值必须为 {'/'.join(VALID_TYPES)}")
    for field, value in data.items():
        setattr(enterprise, field, value)
    db.flush()
    integration.enqueue(
        db,
        event_type="enterprise.updated",
        aggregate_type="enterprise",
        aggregate_id=enterprise.code,
        payload=integration.enterprise_payload(enterprise),
    )
    image = enterprise_image_urls(db, [enterprise.id]).get(enterprise.id)
    return ok({**enterprise_out(lk, enterprise), "image_url": image})


@router.delete("/{enterprise_id}", response_model=ApiResponse[dict], summary="删除企业")
def delete_enterprise(
    enterprise_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("merchant:write")),
) -> dict:
    if not user.is_superuser:
        raise Forbidden("仅平台超级管理员可删除企业档案")
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    if db.query(Product).filter(Product.enterprise_id == enterprise_id).count():
        raise Conflict("该企业下存在商品，无法删除")
    if db.query(TradeOrder).filter(
        or_(
            TradeOrder.buyer_enterprise_id == enterprise_id,
            TradeOrder.supplier_enterprise_id == enterprise_id,
        )
    ).count():
        raise Conflict("该企业存在订单记录，无法删除")
    db.query(User).filter(User.enterprise_id == enterprise_id).update({User.enterprise_id: None})
    db.delete(enterprise)
    db.flush()
    return ok({"deleted": True})


@router.post("/{enterprise_id}/audit", response_model=ApiResponse[EnterpriseOut], summary="企业审核")
def audit_enterprise(
    enterprise_id: int,
    payload: EnterpriseAuditIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("merchant:audit")),
) -> dict:
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    if enterprise.audit_status == "approved" and payload.approved:
        raise Conflict("该企业已审核通过")
    enterprise.audit_status = "approved" if payload.approved else "rejected"
    enterprise.audit_remark = payload.remark
    enterprise.audited_at = now()
    enterprise.audited_by = user.id
    if payload.approved:
        role_code = "buyer" if enterprise.enterprise_type == "buyer" else "supplier" if enterprise.enterprise_type == "supplier" else "merchant"
        enterprise_role = db.query(Role).filter(Role.code == role_code).first()
        if enterprise_role is not None:
            for account in db.query(User).filter(User.enterprise_id == enterprise.id).all():
                if enterprise_role not in account.roles:
                    account.roles.append(enterprise_role)
        org = None
        if enterprise.org_id:
            org = db.get(OrgUnit, enterprise.org_id)
        if org is None:
            parent = None
            if enterprise.park_id:
                parent = (
                    db.query(OrgUnit)
                    .filter(OrgUnit.park_id == enterprise.park_id, OrgUnit.unit_type == "park")
                    .first()
                )
            if parent is None:
                parent = db.query(OrgUnit).filter(OrgUnit.unit_type == "platform").first()
            code = f"ORG-{enterprise.code}"
            org = db.query(OrgUnit).filter(OrgUnit.code == code).first()
            if org is None:
                org = OrgUnit(
                    code=code,
                    name=enterprise.name,
                    unit_type="enterprise",
                    parent_id=parent.id if parent else None,
                    park_id=enterprise.park_id,
                    region=enterprise.region,
                    address=enterprise.address,
                    contact_name=enterprise.contact_name,
                    contact_phone=enterprise.contact_phone,
                    status="active",
                )
                db.add(org)
                db.flush()
            enterprise.org_id = org.id
            db.query(User).filter(User.enterprise_id == enterprise.id).update(
                {User.org_id: org.id}
            )
    else:
        for account in db.query(User).filter(User.enterprise_id == enterprise.id).all():
            account.roles = [role for role in account.roles if role.code not in {"merchant", "supplier", "buyer"}]
    db.flush()
    integration.enqueue(
        db,
        event_type="enterprise.approved" if payload.approved else "enterprise.rejected",
        aggregate_type="enterprise",
        aggregate_id=enterprise.code,
        payload=integration.enterprise_payload(enterprise),
    )
    image = enterprise_image_urls(db, [enterprise.id]).get(enterprise.id)
    return ok({**enterprise_out(lk, enterprise), "image_url": image})


@router.get(
    "/{enterprise_id}/stats",
    response_model=ApiResponse[EnterpriseStatsOut],
    summary="企业经经营统计",
)
def enterprise_stats(
    enterprise_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("merchant:read")),
) -> dict:
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if enterprise.id not in allowed:
            raise Forbidden("无权查看该企业统计")
    product_count = db.query(Product).filter(Product.enterprise_id == enterprise_id).count()
    published = (
        db.query(Product)
        .filter(Product.enterprise_id == enterprise_id, Product.status == "published")
        .count()
    )
    inventory_row = (
        db.query(
            func.coalesce(func.sum(Inventory.quantity), 0),
            func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
        )
        .filter(Inventory.enterprise_id == enterprise_id)
        .one()
    )
    sale_row = (
        db.query(
            func.count(TradeOrder.id),
            func.coalesce(func.sum(TradeOrder.total_amount), 0),
        )
        .filter(
            TradeOrder.supplier_enterprise_id == enterprise_id,
            TradeOrder.status.in_(["confirmed", "delivering", "completed", "settled"]),
        )
        .one()
    )
    purchase_row = (
        db.query(
            func.count(TradeOrder.id),
            func.coalesce(func.sum(TradeOrder.total_amount), 0),
        )
        .filter(
            TradeOrder.buyer_enterprise_id == enterprise_id,
            TradeOrder.status.in_(["confirmed", "delivering", "completed", "settled"]),
        )
        .one()
    )
    pending_settlement = (
        db.query(func.coalesce(func.sum(Settlement.settle_amount - Settlement.settled_amount), 0))
        .filter(
            Settlement.enterprise_id == enterprise_id,
            Settlement.status.in_(["pending", "confirmed"]),
        )
        .one()
    )
    inquiry_count = (
        db.query(func.count(Inquiry.id))
        .filter(
            Inquiry.supplier_enterprise_id == enterprise_id,
            Inquiry.status.in_(["submitted", "quoted", "confirmed"]),
        )
        .count()
    )
    return ok(
        {
            "enterprise_id": enterprise.id,
            "enterprise_name": enterprise.name,
            "product_count": product_count,
            "published_product_count": published,
            "inventory_quantity": float(dec(inventory_row[0])),
            "inventory_value": float(dec(inventory_row[1])),
            "sale_order_count": int(sale_row[0] or 0),
            "sale_order_amount": float(dec(sale_row[1])),
            "purchase_order_count": int(purchase_row[0] or 0),
            "purchase_order_amount": float(dec(purchase_row[1])),
            "pending_settlement_amount": float(dec(pending_settlement[0])),
            "as_supplier_inquiry_count": int(inquiry_count or 0),
        }
    )
