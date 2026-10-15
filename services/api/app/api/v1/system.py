# -*- coding: utf-8 -*-
"""系统接口：健康检查、运行信息、Odoo 集成回调。"""
from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import settings
from app.core.database import get_db, ping
from app.core.deps import get_current_user, require
from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.security import verify_integration_signature
from app.core.timeutil import now
from app.integrations.odoo_client import OdooError, odoo_client
from app.integrations.search import search
from app.integrations.storage import storage
from app.models.org import User
from app.models.product import Inventory, Product, Warehouse
from app.models.system import SyncOutbox
from app.services import integration

# 根级探针（不带 /api/v1 前缀）
health_router = APIRouter(tags=["系统"])

router = APIRouter(prefix="/system", tags=["系统"])


@health_router.get("/health", summary="存活探针")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.ENV,
        "time": now().isoformat(),
    }


@health_router.get("/ready", summary="就绪探针")
def ready() -> dict:
    db_ok = ping()
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "cache": cache.status()["backend"],
        "search": search.engine,
        "storage": storage.backend,
        "odoo": odoo_client.base_url,
    }


@router.get("/info", response_model=ApiResponse[dict], summary="系统运行信息")
def system_info(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    outbox_pending = db.query(SyncOutbox).filter(SyncOutbox.status == "pending").count()
    outbox_failed = db.query(SyncOutbox).filter(SyncOutbox.status == "failed").count()
    odoo_status = odoo_client.health()
    return ok(
        {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.ENV,
            "timezone": settings.TIMEZONE,
            "time": now().isoformat(),
            "database": {"dialect": db.bind.dialect.name if db.bind else "unknown", "ok": ping()},
            "cache": cache.status(),
            "search": search.status(),
            "storage": storage.status(),
            "odoo": odoo_status,
            "outbox": {"pending": outbox_pending, "failed": outbox_failed},
            "counts": {
                "product": db.query(Product).count(),
                "inventory": db.query(Inventory).count(),
                "warehouse": db.query(Warehouse).count(),
            },
            "business": {
                "service_fee_rate": settings.PLATFORM_SERVICE_FEE_RATE,
                "default_tax_rate": settings.DEFAULT_TAX_RATE,
            },
        }
    )


# --------------------------------------------------------------------------- 集成


def _verify_signature(request: Request, raw_body: bytes) -> None:
    timestamp = request.headers.get("X-GZ-Timestamp", "")
    signature = request.headers.get("X-GZ-Signature", "")
    if not timestamp or not signature:
        raise Forbidden("缺少集成签名头")
    if not verify_integration_signature(timestamp, raw_body, signature):
        raise Forbidden("集成签名校验失败")


integration_router = APIRouter(prefix="/integration", tags=["系统集成"])


@integration_router.post("/odoo/pull-inventory", response_model=ApiResponse[dict], summary="接收 Odoo 库存快照")
async def pull_inventory(request: Request, db: Session = Depends(get_db)) -> dict:
    raw = await request.body()
    _verify_signature(request, raw)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except ValueError as exc:
        raise BadRequest("请求体不是合法 JSON") from exc
    items = payload.get("items") or []
    updated = 0
    skipped = 0
    for item in items:
        product_code = item.get("product_code")
        warehouse_code = item.get("warehouse_code")
        quantity = item.get("quantity")
        if not product_code or not warehouse_code or quantity is None:
            skipped += 1
            continue
        product = db.query(Product).filter(Product.code == product_code).first()
        warehouse = db.query(Warehouse).filter(Warehouse.code == warehouse_code).first()
        if product is None or warehouse is None:
            skipped += 1
            continue
        row = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == product.id,
                Inventory.warehouse_id == warehouse.id,
                Inventory.batch_no == (item.get("batch_no") or "DEFAULT"),
            )
            .first()
        )
        if row is None:
            row = Inventory(
                product_id=product.id,
                warehouse_id=warehouse.id,
                batch_no=item.get("batch_no") or "DEFAULT",
                quantity=quantity,
                locked_quantity=0,
                unit_cost=item.get("unit_cost") or 0,
                enterprise_id=product.enterprise_id,
            )
            db.add(row)
        else:
            row.quantity = quantity
            row.updated_at = now()
        updated += 1
    db.flush()
    integration.log_sync(
        db,
        direction="pull",
        event_type="inventory.pull",
        aggregate_id=None,
        request=payload,
        response={"updated": updated, "skipped": skipped},
        success=True,
    )
    return ok({"updated": updated, "skipped": skipped})


@integration_router.post("/odoo/ack-order", response_model=ApiResponse[dict], summary="接收 Odoo 订单回执")
async def ack_order(request: Request, db: Session = Depends(get_db)) -> dict:
    raw = await request.body()
    _verify_signature(request, raw)
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except ValueError as exc:
        raise BadRequest("请求体不是合法 JSON") from exc
    order_no = payload.get("order_no")
    remote_id = payload.get("remote_id")
    remote_model = payload.get("remote_model", "sale.order")
    if not order_no or remote_id is None:
        raise BadRequest("order_no 与 remote_id 必填")
    integration.map_remote_id(db, "trade_order", order_no, remote_model, remote_id)
    from app.models.trade import TradeOrder

    order = db.query(TradeOrder).filter(TradeOrder.order_no == order_no).first()
    if order is not None:
        order.odoo_order_id = int(remote_id)
    integration.log_sync(
        db,
        direction="pull",
        event_type="order.ack",
        aggregate_id=order_no,
        request=payload,
        response={"mapped": True},
        success=True,
    )
    db.flush()
    return ok({"order_no": order_no, "remote_id": remote_id, "mapped": True})


@integration_router.get("/outbox", response_model=ApiResponse[PageData[dict]], summary="集成出站事件列表")
def list_outbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require("integration:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(SyncOutbox)
    if status:
        query = query.filter(SyncOutbox.status == status)
    if event_type:
        query = query.filter(SyncOutbox.event_type == event_type)
    total = query.count()
    rows = query.order_by(SyncOutbox.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": row.id,
            "event_type": row.event_type,
            "aggregate_type": row.aggregate_type,
            "aggregate_id": row.aggregate_id,
            "status": row.status,
            "retry_count": row.retry_count,
            "next_retry_at": row.next_retry_at,
            "last_error": row.last_error,
            "created_at": row.created_at,
            "processed_at": row.processed_at,
        }
        for row in rows
    ]
    return ok(paginate(items, total, page, page_size))


@integration_router.post("/outbox/{event_id}/retry", response_model=ApiResponse[dict], summary="重试出站事件")
def retry_outbox(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("integration:write")),
) -> dict:
    event = integration.retry_event(db, event_id)
    return ok({"id": event.id, "status": event.status})


@integration_router.post("/odoo/push-now", response_model=ApiResponse[dict], summary="立即推送待处理事件")
def push_now(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require("integration:write")),
) -> dict:
    from app.worker import process_outbox_batch

    result = process_outbox_batch(db, limit=limit)
    return ok(result)
