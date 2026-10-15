# -*- coding: utf-8 -*-
"""集成出站服务：事务性 outbox + Odoo 推送。

设计要点（ADR-02/ADR-06）：
- 业务事务内只写 outbox 行，不直接调用外部系统，避免长事务与外部故障拖垮交易；
- worker 异步消费 outbox，幂等键去重、指数退避重试、失败留痕；
- Odoo 不可用时事件保持 pending，不影响主链路。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFound
from app.core.timeutil import now
from app.models.system import IntegrationIdMap, SyncLog, SyncOutbox


def enqueue(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Any,
    payload: Dict[str, Any],
    idempotent_key: Optional[str] = None,
) -> SyncOutbox:
    """写入出站事件（与业务同事务）。"""
    event = SyncOutbox(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        idempotent_key=idempotent_key or f"{event_type}:{aggregate_type}:{aggregate_id}",
        payload=payload,
        status="pending",
        retry_count=0,
        next_retry_at=now(),
    )
    db.add(event)
    db.flush()
    return event


def map_remote_id(
    db: Session, local_type: str, local_id: Any, remote_model: str, remote_id: Any
) -> IntegrationIdMap:
    row = (
        db.query(IntegrationIdMap)
        .filter(
            IntegrationIdMap.local_type == local_type,
            IntegrationIdMap.local_id == str(local_id),
            IntegrationIdMap.remote_model == remote_model,
        )
        .first()
    )
    if row is None:
        row = IntegrationIdMap(
            local_type=local_type,
            local_id=str(local_id),
            remote_model=remote_model,
            remote_id=str(remote_id),
        )
        db.add(row)
    else:
        row.remote_id = str(remote_id)
        row.updated_at = now()
    db.flush()
    return row


def get_remote_id(db: Session, local_type: str, local_id: Any, remote_model: str) -> Optional[str]:
    row = (
        db.query(IntegrationIdMap)
        .filter(
            IntegrationIdMap.local_type == local_type,
            IntegrationIdMap.local_id == str(local_id),
            IntegrationIdMap.remote_model == remote_model,
        )
        .first()
    )
    return row.remote_id if row else None


def log_sync(
    db: Session,
    *,
    direction: str,
    event_type: str,
    aggregate_id: Optional[str],
    request: Any,
    response: Any,
    success: bool,
    error: Optional[str] = None,
    duration_ms: int = 0,
) -> SyncLog:
    row = SyncLog(
        direction=direction,
        event_type=event_type,
        aggregate_id=aggregate_id,
        request=_dump(request),
        response=_dump(response),
        success=1 if success else 0,
        error=error,
        duration_ms=duration_ms,
    )
    db.add(row)
    db.flush()
    return row


def _dump(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:8000]
    try:
        return json.dumps(value, ensure_ascii=False, default=str)[:8000]
    except (TypeError, ValueError):
        return str(value)[:8000]


def fetch_pending(db: Session, limit: Optional[int] = None) -> List[SyncOutbox]:
    limit = limit or settings.OUTBOX_BATCH_SIZE
    return (
        db.query(SyncOutbox)
        .filter(
            # failed 为达到重试上限的终态；由管理接口显式 retry 后才重新入队。
            SyncOutbox.status == "pending",
            or_(SyncOutbox.next_retry_at.is_(None), SyncOutbox.next_retry_at <= now()),
        )
        .order_by(SyncOutbox.id.asc())
        .limit(limit)
        .all()
    )


def mark_success(db: Session, event: SyncOutbox, response: Any = None) -> None:
    event.status = "success"
    event.processed_at = now()
    event.last_error = None
    db.flush()
    log_sync(
        db,
        direction="push",
        event_type=event.event_type,
        aggregate_id=event.aggregate_id,
        request=event.payload,
        response=response,
        success=True,
    )


def mark_failure(db: Session, event: SyncOutbox, error: str) -> None:
    event.retry_count = int(event.retry_count or 0) + 1
    event.last_error = error[:2000]
    if event.retry_count >= settings.OUTBOX_MAX_RETRY:
        event.status = "failed"
    else:
        event.status = "pending"
        backoff = min(3600, 30 * (2 ** (event.retry_count - 1)))
        from datetime import timedelta

        event.next_retry_at = now() + timedelta(seconds=backoff)
    db.flush()
    log_sync(
        db,
        direction="push",
        event_type=event.event_type,
        aggregate_id=event.aggregate_id,
        request=event.payload,
        response=None,
        success=False,
        error=error,
    )


def retry_event(db: Session, event_id: int) -> SyncOutbox:
    event = db.get(SyncOutbox, event_id)
    if event is None:
        raise NotFound("出站事件不存在")
    event.status = "pending"
    event.next_retry_at = now()
    event.retry_count = 0
    event.last_error = None
    db.flush()
    return event


# --------------------------------------------------------------------------- 事件载荷构造


def enterprise_payload(enterprise) -> Dict[str, Any]:
    return {
        "code": enterprise.code,
        "name": enterprise.name,
        "vat": enterprise.unified_social_credit_code,
        "enterprise_type": enterprise.enterprise_type,
        "legal_person": enterprise.legal_person,
        "contact_name": enterprise.contact_name,
        "contact_phone": enterprise.contact_phone,
        "email": enterprise.email,
        "region": enterprise.region,
        "address": enterprise.address,
        "ref": enterprise.code,
    }


def product_payload(product, category_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "default_code": product.code,
        "name": product.name,
        "category_name": category_name,
        "gz_spec": product.spec,
        "gz_grade": product.grade,
        "gz_origin": product.origin,
        "gz_harvest_year": product.harvest_year,
        "gz_package": product.package,
        "list_price": float(product.price or 0),
        "uom": product.unit,
    }


def order_payload(order, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "order_no": order.order_no,
        "buyer_enterprise_code": getattr(order, "buyer_enterprise_code", None),
        "supplier_enterprise_code": getattr(order, "supplier_enterprise_code", None),
        "amount": float(order.amount or 0),
        "tax_amount": float(order.tax_amount or 0),
        "total_amount": float(order.total_amount or 0),
        "currency": order.currency,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "delivery_address": order.delivery_address,
        "items": items,
    }


def settlement_payload(settlement, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "settlement_no": settlement.settlement_no,
        "settle_type": settlement.settle_type,
        "order_amount": float(settlement.order_amount or 0),
        "fee_amount": float(settlement.fee_amount or 0),
        "settle_amount": float(settlement.settle_amount or 0),
        "period_start": settlement.period_start.isoformat() if settlement.period_start else None,
        "period_end": settlement.period_end.isoformat() if settlement.period_end else None,
        "lines": lines,
    }
