# -*- coding: utf-8 -*-
"""食品安全溯源接口：批次管理、链路事件、扫码公开查询。"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import apply_own_enterprise, enterprise_scope_ids, is_unrestricted, resolve_own_enterprise
from app.core.timeutil import now
from app.models.org import User
from app.models.product import Product, Warehouse
from app.models.trace import TraceBatch, TraceEvent
from app.schemas.trace import (
    PublicTraceOut,
    TraceBatchDetailOut,
    TraceBatchIn,
    TraceBatchOut,
    TraceEventIn,
    TraceEventOut,
)
from app.services import integration
from app.services.numbering import next_no

router = APIRouter(prefix="/trace", tags=["安全溯源"])

STAGES = ("planting", "processing", "warehouse", "trade", "sale")


def _trace_url(batch_no: str) -> str:
    return f"{settings.STORAGE_PUBLIC_BASE.rstrip('/')}/../trace/public/{batch_no}"


def _batch_out(db: Session, lk: Lookups, row: TraceBatch) -> dict:
    product = lk.product(row.product_id)
    event_count = db.query(TraceEvent).filter(TraceEvent.batch_id == row.id).count()
    return {
        "id": row.id,
        "batch_no": row.batch_no,
        "qr_code": row.qr_code,
        "product_id": row.product_id,
        "product_name": product.name if product else None,
        "product_code": product.code if product else None,
        "enterprise_id": row.enterprise_id,
        "enterprise_name": lk.enterprise_name(row.enterprise_id),
        "quantity": float(row.quantity or 0),
        "origin_base": row.origin_base,
        "origin_region": row.origin_region,
        "plant_date": row.plant_date,
        "harvest_date": row.harvest_date,
        "process_enterprise": row.process_enterprise,
        "process_date": row.process_date,
        "warehouse_id": row.warehouse_id,
        "warehouse_name": lk.warehouse_name(row.warehouse_id),
        "test_report_url": row.test_report_url,
        "quality_status": row.quality_status,
        "status": row.status,
        "remark": row.remark,
        "event_count": event_count,
        "created_at": row.created_at,
    }


def _event_out(row: TraceEvent) -> dict:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "stage": row.stage,
        "title": row.title,
        "description": row.description,
        "occurred_at": row.occurred_at,
        "location": row.location,
        "operator": row.operator,
        "evidence_url": row.evidence_url,
        "created_at": row.created_at,
    }


@router.get("/batches", response_model=ApiResponse[PageData[TraceBatchOut]], summary="溯源批次列表")
def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    product_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    keyword: Optional[str] = None,
    quality_status: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trace:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(TraceBatch)
    if product_id:
        query = query.filter(TraceBatch.product_id == product_id)
    if enterprise_id:
        query = query.filter(TraceBatch.enterprise_id == enterprise_id)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(TraceBatch.batch_no.like(like), TraceBatch.origin_base.like(like))
        )
    if quality_status:
        query = query.filter(TraceBatch.quality_status == quality_status)
    if status:
        query = query.filter(TraceBatch.status == status)
    query = apply_own_enterprise(query, TraceBatch, user, "enterprise_id", db)
    total = query.count()
    rows = query.order_by(TraceBatch.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok(paginate([_batch_out(db, lk, row) for row in rows], total, page, page_size))


@router.post("/batches", response_model=ApiResponse[TraceBatchOut], summary="创建溯源批次")
def create_batch(
    payload: TraceBatchIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trace:write")),
) -> dict:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise NotFound("商品不存在")
    enterprise_id = resolve_own_enterprise(
        user, payload.enterprise_id or product.enterprise_id
    )
    batch_no = payload.batch_no or next_no(db, "trace_batch", f"GZ-BATCH-{date.today().year}")
    if db.query(TraceBatch).filter(TraceBatch.batch_no == batch_no).first():
        raise Conflict(f"批次号已存在：{batch_no}")
    data = payload.model_dump(exclude={"batch_no", "enterprise_id"})
    batch = TraceBatch(
        batch_no=batch_no,
        qr_code=batch_no,
        enterprise_id=enterprise_id,
        **data,
    )
    db.add(batch)
    db.flush()
    db.add(
        TraceEvent(
            batch_id=batch.id,
            stage="warehouse",
            title="批次建档",
            description=f"批次 {batch_no} 由 {lk.enterprise_name(enterprise_id)} 建立",
            occurred_at=now(),
            operator=user.full_name or user.username,
        )
    )
    db.flush()
    integration.enqueue(
        db,
        event_type="trace_batch.created",
        aggregate_type="trace_batch",
        aggregate_id=batch.batch_no,
        payload={
            "batch_no": batch.batch_no,
            "product_code": product.code,
            "enterprise_id": enterprise_id,
            "origin_base": batch.origin_base,
            "quality_status": batch.quality_status,
        },
    )
    return ok(_batch_out(db, lk, batch))


@router.get("/batches/{batch_id}", response_model=ApiResponse[TraceBatchDetailOut], summary="批次详情")
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trace:read")),
) -> dict:
    batch = db.get(TraceBatch, batch_id)
    if batch is None:
        raise NotFound("批次不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if batch.enterprise_id not in allowed:
            raise Forbidden("无权查看该批次")
    data = _batch_out(db, lk, batch)
    data["events"] = [_event_out(row) for row in batch.events]
    return ok(data)


@router.post("/batches/{batch_id}/events", response_model=ApiResponse[TraceEventOut], summary="追加链路事件")
def add_event(
    batch_id: int,
    payload: TraceEventIn,
    db: Session = Depends(get_db),
    user: User = Depends(require("trace:write")),
) -> dict:
    batch = db.get(TraceBatch, batch_id)
    if batch is None:
        raise NotFound("批次不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if batch.enterprise_id not in allowed:
            raise Forbidden("无权操作该批次")
    if payload.stage not in STAGES:
        raise Conflict(f"stage 取值必须为 {'/'.join(STAGES)}")
    event = TraceEvent(
        batch_id=batch.id,
        stage=payload.stage,
        title=payload.title,
        description=payload.description,
        occurred_at=payload.occurred_at or now(),
        location=payload.location,
        operator=payload.operator or user.full_name or user.username,
        evidence_url=payload.evidence_url,
    )
    db.add(event)
    db.flush()
    return ok(_event_out(event))


@router.get("/public/{batch_no}", response_model=PublicTraceOut, summary="扫码查询（免鉴权）")
def public_trace(batch_no: str, db: Session = Depends(get_db)) -> dict:
    batch = db.query(TraceBatch).filter(TraceBatch.batch_no == batch_no).first()
    if batch is None:
        return {
            "batch_no": batch_no,
            "verified": False,
            "message": "未查询到该批次，请核对二维码或联系供应商",
            "quality_status": "pending",
            "events": [],
        }
    product = db.get(Product, batch.product_id)
    warehouse = db.get(Warehouse, batch.warehouse_id) if batch.warehouse_id else None
    from app.models.enterprise import Enterprise

    enterprise = db.get(Enterprise, batch.enterprise_id)
    events = sorted(batch.events, key=lambda row: (row.occurred_at is None, row.occurred_at))
    return {
        "batch_no": batch.batch_no,
        "product_name": product.name if product else None,
        "product_code": product.code if product else None,
        "spec": product.spec if product else None,
        "grade": product.grade if product else None,
        "unit": product.unit if product else None,
        "origin": product.origin if product else batch.origin_region,
        "harvest_year": product.harvest_year if product else None,
        "package": product.package if product else None,
        "enterprise_name": enterprise.name if enterprise else None,
        "enterprise_code": enterprise.code if enterprise else None,
        "origin_base": batch.origin_base,
        "origin_region": batch.origin_region or (enterprise.region if enterprise else None),
        "plant_date": batch.plant_date,
        "harvest_date": batch.harvest_date,
        "process_enterprise": batch.process_enterprise,
        "process_date": batch.process_date,
        "warehouse_name": warehouse.name if warehouse else None,
        "quality_status": batch.quality_status,
        "test_report_url": batch.test_report_url or (product.test_report_url if product else None),
        "qr_code": batch.qr_code,
        "trace_url": f"/api/v1/trace/public/{batch.batch_no}",
        "events": [_event_out(row) for row in events],
        "verified": batch.status == "active",
        "message": "该批次溯源信息由平台登记，数据来源可追溯" if batch.status == "active" else "该批次已关闭",
    }
