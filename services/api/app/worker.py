# -*- coding: utf-8 -*-
"""后台任务进程：集成出站推送、检索索引同步、定时对账。

启动方式：`python -m app.worker`
容器中作为独立服务运行（与 api 共用镜像，command 不同）。
"""
from __future__ import annotations

import logging
import signal
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session_factory
from app.core.timeutil import now
from app.integrations.odoo_client import OdooError, OdooUnavailable, odoo_client
from app.integrations.search import search
from app.integrations.storage import storage
from app.models.enterprise import Enterprise
from app.models.product import Product
from app.models.settlement import Settlement
from app.models.system import SyncOutbox
from app.models.trade import TradeOrder
from app.services import integration

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("gz-worker")

_running = True


def _stop(signum, frame):  # pragma: no cover - 仅在容器信号下触发
    global _running
    _running = False
    logger.info("收到停止信号 %s，准备退出", signum)


# --------------------------------------------------------------------------- 出站事件处理


def _partner_id_for(db: Session, enterprise_id: Optional[int]) -> Optional[int]:
    if not enterprise_id:
        return None
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        return None
    if enterprise.odoo_partner_id:
        return int(enterprise.odoo_partner_id)
    remote_id = integration.get_remote_id(db, "enterprise", enterprise.code, "res.partner")
    if remote_id:
        enterprise.odoo_partner_id = int(remote_id)
        return int(remote_id)
    remote_id = odoo_client.upsert_partner(integration.enterprise_payload(enterprise))
    if remote_id:
        enterprise.odoo_partner_id = int(remote_id)
        integration.map_remote_id(db, "enterprise", enterprise.code, "res.partner", remote_id)
    return remote_id


def _product_variant_for(db: Session, product: Product) -> Dict[str, int]:
    template_id = product.odoo_template_id or integration.get_remote_id(
        db, "product", product.code, "product.template"
    )
    if not template_id:
        template_id = odoo_client.upsert_product(integration.product_payload(product))
        if not template_id:
            raise OdooError(f"Odoo 商品创建失败：{product.code}")
        integration.map_remote_id(db, "product", product.code, "product.template", template_id)
        product.odoo_template_id = int(template_id)
    return odoo_client.product_variant(int(template_id))


def handle_event(db: Session, event: SyncOutbox) -> Dict[str, Any]:
    """按事件类型分发到 Odoo。返回处理结果摘要。"""
    payload = event.payload or {}
    event_type = event.event_type

    if event_type.startswith("enterprise."):
        remote_id = odoo_client.upsert_partner(payload)
        if remote_id:
            integration.map_remote_id(db, "enterprise", payload.get("code"), "res.partner", remote_id)
            code = payload.get("code")
            enterprise = db.query(Enterprise).filter(Enterprise.code == code).first()
            if enterprise is not None:
                enterprise.odoo_partner_id = int(remote_id)
        return {"model": "res.partner", "remote_id": remote_id}

    if event_type.startswith("product."):
        remote_id = odoo_client.upsert_product(payload)
        if remote_id:
            integration.map_remote_id(db, "product", payload.get("default_code"), "product.template", remote_id)
            code = payload.get("default_code")
            product = db.query(Product).filter(Product.code == code).first()
            if product is not None:
                product.odoo_template_id = int(remote_id)
        return {"model": "product.template", "remote_id": remote_id}

    if event_type == "order.confirmed":
        order = (
            db.query(TradeOrder)
            .filter(TradeOrder.order_no == payload.get("order_no"))
            .first()
        )
        if order is None:
            return {"skipped": "订单不存在"}
        buyer_partner = _partner_id_for(db, order.buyer_enterprise_id)
        supplier_partner = _partner_id_for(db, order.supplier_enterprise_id)
        items = []
        for item in order.items:
            product = db.get(Product, item.product_id)
            if product is None:
                raise OdooError(f"订单商品不存在：{item.product_id}")
            variant = _product_variant_for(db, product)
            items.append(
                {
                    "odoo_product_id": variant["product_id"],
                    "odoo_uom_id": variant["uom_id"],
                    "quantity": float(item.quantity or 0),
                    "unit_price": float(item.unit_price or 0),
                    "product_name": item.product_name,
                }
            )
        sale_id = odoo_client.create_sale_order(
            {"partner_id": buyer_partner, "order_no": order.order_no, "items": items,
             "amount": float(order.amount or 0), "tax_amount": float(order.tax_amount or 0),
             "currency": order.currency}
        )
        purchase_id = odoo_client.create_purchase_order(
            {"partner_id": supplier_partner, "order_no": order.order_no, "items": items,
             "amount": float(order.amount or 0), "tax_amount": float(order.tax_amount or 0),
             "currency": order.currency}
        )
        if sale_id:
            order.odoo_order_id = int(sale_id)
            integration.map_remote_id(db, "trade_order", order.order_no, "sale.order", sale_id)
        if purchase_id:
            integration.map_remote_id(db, "trade_order", order.order_no, "purchase.order", purchase_id)
        return {"model": "sale.order", "sale_order_id": sale_id, "purchase_order_id": purchase_id}

    if event_type.startswith("settlement."):
        settlement = db.query(Settlement).filter(
            Settlement.settlement_no == event.aggregate_id
        ).first()
        if settlement is None:
            raise OdooError(f"结算单不存在：{event.aggregate_id}")
        draft = integration.settlement_payload(settlement, [])
        draft["partner_id"] = _partner_id_for(db, settlement.enterprise_id)
        remote_id = odoo_client.create_settlement_move(draft)
        if remote_id:
            settlement.odoo_move_id = int(remote_id)
            integration.map_remote_id(db, "settlement", settlement.settlement_no, "account.move", remote_id)
            if event_type == "settlement.payment":
                odoo_client.note_settlement_payment(int(remote_id), {
                    **draft, **payload,
                    "settled_amount": float(settlement.settled_amount or 0),
                    "pay_status": settlement.pay_status,
                })
        return {"model": "account.move", "remote_id": remote_id}

    # 无需推送 Odoo 的事件（询价、报价、园区合同、溯源等）直接视为已处理
    return {"skipped": "无 Odoo 侧对应动作"}


def process_outbox_batch(db: Session, limit: Optional[int] = None) -> Dict[str, Any]:
    events = integration.fetch_pending(db, limit)
    if not events:
        return {"processed": 0, "success": 0, "failed": 0, "pending": 0}
    success = 0
    failed = 0
    for event in events:
        started = time.perf_counter()
        try:
            result = handle_event(db, event)
            integration.mark_success(db, event, result)
            success += 1
            logger.info("事件推送成功 %s #%s -> %s", event.event_type, event.id, result)
        except Exception as exc:  # noqa: BLE001 - outbox 需要吞掉所有异常并留痕重试
            message = f"{type(exc).__name__}: {exc}"
            integration.mark_failure(db, event, message)
            failed += 1
            logger.warning("事件推送失败 %s #%s：%s", event.event_type, event.id, message)
        finally:
            db.commit()
    return {"processed": len(events), "success": success, "failed": failed, "pending": 0}


# --------------------------------------------------------------------------- 检索索引


def reindex_products(db: Session, limit: int = 1000) -> Dict[str, Any]:
    if not search.check():
        logger.info("ElasticSearch 不可用，跳过索引同步（业务自动降级为 SQL 检索）")
        return {"indexed": 0, "engine": "sql"}
    search.ensure_index()
    products = db.query(Product).limit(limit).all()
    indexed = 0
    for product in products:
        enterprise = db.get(Enterprise, product.enterprise_id)
        if search.index_document(
            {
                "id": product.id,
                "code": product.code,
                "name": product.name,
                "category_id": product.category_id,
                "enterprise_id": product.enterprise_id,
                "enterprise_name": enterprise.name if enterprise else None,
                "spec": product.spec,
                "grade": product.grade,
                "origin": product.origin,
                "harvest_year": product.harvest_year,
                "status": product.status,
                "price": float(product.price or 0),
            }
        ):
            indexed += 1
    return {"indexed": indexed, "engine": "elasticsearch"}


# --------------------------------------------------------------------------- 主循环


def main() -> None:  # pragma: no cover - 常驻进程
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    storage.ensure_local_dirs()
    logger.info("worker 启动，集成目标 %s", settings.ODOO_BASE_URL)
    session_factory = get_session_factory()
    last_index = 0.0
    while _running:
        db = session_factory()
        try:
            process_outbox_batch(db)
            if time.time() - last_index > 600:
                reindex_products(db)
                last_index = time.time()
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker 轮询异常：%s", exc)
            db.rollback()
        finally:
            db.close()
        for _ in range(5):
            if not _running:
                break
            time.sleep(1)
    logger.info("worker 已退出")


if __name__ == "__main__":  # pragma: no cover
    main()
