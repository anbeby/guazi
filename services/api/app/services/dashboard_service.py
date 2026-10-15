# -*- coding: utf-8 -*-
"""数据驾驶舱聚合服务。

所有指标直接来自业务表实时聚合（可选 Redis 短缓存），不使用预置静态数据。
为兼容 SQLite（测试）与 PostgreSQL（生产），仅使用 `func.date()` 等两库通用函数。
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.models.enterprise import Enterprise, Park, Stall
from app.models.org import User
from app.models.product import Category, Inventory, Product, Warehouse
from app.models.settlement import Settlement
from app.models.trade import Inquiry, Quotation, TradeOrder, TradeOrderItem
from app.core.scope import enterprise_scope_ids, is_unrestricted
from app.services.inventory_service import dec

ZERO = Decimal("0")


def _scoped_ids(db: Session, user: Optional[User]) -> Optional[List[int]]:
    if user is None:
        return None
    return enterprise_scope_ids(db, user)


def _date_series(days: int) -> List[str]:
    today = date.today()
    return [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]


def overview(db: Session, user: Optional[User] = None, use_cache: bool = True) -> Dict:
    ids = _scoped_ids(db, user)
    cache_key = f"dashboard:overview:{'all' if ids is None else ','.join(map(str, ids))}"
    if use_cache:
        cached = cache.get_json(cache_key)
        if cached:
            return cached

    enterprise_query = db.query(Enterprise)
    product_query = db.query(Product)
    inventory_query = db.query(Inventory)
    order_query = db.query(TradeOrder)
    inquiry_query = db.query(Inquiry)
    quotation_query = db.query(Quotation)
    warehouse_query = db.query(Warehouse)
    if ids is not None:
        if not ids:
            return _empty_overview()
        enterprise_query = enterprise_query.filter(Enterprise.id.in_(ids))
        product_query = product_query.filter(Product.enterprise_id.in_(ids))
        inventory_query = inventory_query.filter(Inventory.enterprise_id.in_(ids))
        warehouse_query = warehouse_query.filter(Warehouse.enterprise_id.in_(ids))
        order_query = order_query.filter(
            or_(
                TradeOrder.buyer_enterprise_id.in_(ids),
                TradeOrder.supplier_enterprise_id.in_(ids),
            )
        )
        inquiry_query = inquiry_query.filter(Inquiry.buyer_enterprise_id.in_(ids))
        quotation_query = quotation_query.filter(Quotation.supplier_enterprise_id.in_(ids))

    today_date = date.today()
    month_start = date.today().replace(day=1)

    enterprise_rows = enterprise_query.with_entities(
        Enterprise.id, Enterprise.enterprise_type, Enterprise.audit_status
    ).all()
    enterprise_count = len(enterprise_rows)
    merchant_count = sum(1 for row in enterprise_rows if row[1] == "merchant")
    supplier_count = sum(1 for row in enterprise_rows if row[1] == "supplier")
    buyer_count = sum(1 for row in enterprise_rows if row[1] == "buyer")
    pending_enterprise = sum(1 for row in enterprise_rows if row[2] == "pending")

    product_count = product_query.count()
    published_product_count = product_query.filter(Product.status == "published").count()
    pending_product = product_query.filter(Product.audit_status == "pending").count()

    inventory_totals = inventory_query.with_entities(
        func.coalesce(func.sum(Inventory.quantity), 0),
        func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
        func.count(Inventory.id),
    ).one()

    order_totals = order_query.with_entities(
        func.count(TradeOrder.id),
        func.coalesce(func.sum(TradeOrder.total_amount), 0),
    ).one()
    completed_totals = order_query.filter(TradeOrder.status.in_(["completed", "settled"])).with_entities(
        func.count(TradeOrder.id),
        func.coalesce(func.sum(TradeOrder.total_amount), 0),
    ).one()
    today_totals = order_query.filter(func.date(TradeOrder.created_at) == today_date).with_entities(
        func.count(TradeOrder.id),
        func.coalesce(func.sum(TradeOrder.total_amount), 0),
    ).one()
    month_totals = order_query.filter(func.date(TradeOrder.created_at) >= month_start).with_entities(
        func.coalesce(func.sum(TradeOrder.total_amount), 0)
    ).one()

    inquiry_count = inquiry_query.count()
    open_inquiry_count = inquiry_query.filter(Inquiry.status.in_(["submitted", "quoted"])).count()
    quotation_count = quotation_query.count()

    settlement_query = db.query(Settlement).filter(
        Settlement.status.in_(["pending", "confirmed"])
    )
    if ids is not None:
        settlement_query = settlement_query.filter(Settlement.enterprise_id.in_(ids))
    unsettled = settlement_query.with_entities(
        func.coalesce(func.sum(Settlement.settle_amount - Settlement.settled_amount), 0)
    ).one()

    park_count = db.query(Park).count()
    stall_query = db.query(Stall)
    if ids is not None and ids:
        park_ids = [
            row[0]
            for row in db.query(Enterprise.park_id)
            .filter(Enterprise.id.in_(ids), Enterprise.park_id.isnot(None))
            .all()
        ]
        stall_query = stall_query.filter(Stall.park_id.in_(park_ids or [-1]))
    stall_count = stall_query.count()
    stall_rented = stall_query.filter(Stall.status == "rented").count()

    result = {
        "enterprise_count": enterprise_count,
        "merchant_count": merchant_count,
        "supplier_count": supplier_count,
        "buyer_count": buyer_count,
        "product_count": product_count,
        "published_product_count": published_product_count,
        "inventory_quantity": float(dec(inventory_totals[0])),
        "inventory_value": float(dec(inventory_totals[1])),
        "inventory_batch_count": int(inventory_totals[2] or 0),
        "inquiry_count": inquiry_count,
        "open_inquiry_count": open_inquiry_count,
        "quotation_count": quotation_count,
        "order_count": int(order_totals[0] or 0),
        "order_amount": float(dec(order_totals[1])),
        "completed_order_count": int(completed_totals[0] or 0),
        "completed_order_amount": float(dec(completed_totals[1])),
        "today_order_count": int(today_totals[0] or 0),
        "today_order_amount": float(dec(today_totals[1])),
        "month_order_amount": float(dec(month_totals[0])),
        "park_count": park_count,
        "stall_count": stall_count,
        "stall_rented": stall_rented,
        "stall_rented_rate": round(stall_rented / stall_count, 4) if stall_count else 0.0,
        "warehouse_count": warehouse_query.count(),
        "pending_audit_enterprise": pending_enterprise,
        "pending_audit_product": pending_product,
        "unsettled_amount": float(dec(unsettled[0])),
    }
    if use_cache:
        cache.set_json(cache_key, result, ttl=60)
    return result


def _empty_overview() -> Dict:
    return {
        "enterprise_count": 0, "merchant_count": 0, "supplier_count": 0, "buyer_count": 0,
        "product_count": 0, "published_product_count": 0, "inventory_quantity": 0.0,
        "inventory_value": 0.0, "inventory_batch_count": 0, "inquiry_count": 0,
        "open_inquiry_count": 0, "quotation_count": 0, "order_count": 0, "order_amount": 0.0,
        "completed_order_count": 0, "completed_order_amount": 0.0, "today_order_count": 0,
        "today_order_amount": 0.0, "month_order_amount": 0.0, "park_count": 0, "stall_count": 0,
        "stall_rented": 0, "stall_rented_rate": 0.0, "warehouse_count": 0,
        "pending_audit_enterprise": 0, "pending_audit_product": 0, "unsettled_amount": 0.0,
    }


def trend(db: Session, days: int = 30, user: Optional[User] = None) -> Dict:
    days = max(1, min(days, 365))
    ids = _scoped_ids(db, user)
    start = date.today() - timedelta(days=days - 1)

    order_query = db.query(
        func.date(TradeOrder.created_at).label("d"),
        func.count(TradeOrder.id),
        func.coalesce(func.sum(TradeOrder.total_amount), 0),
    ).filter(func.date(TradeOrder.created_at) >= start)
    if ids is not None:
        if not ids:
            return {"dates": _date_series(days), "order_count": [0] * days,
                    "order_amount": [0.0] * days, "order_quantity": [0.0] * days,
                    "inquiry_count": [0] * days}
        order_query = order_query.filter(
            or_(
                TradeOrder.buyer_enterprise_id.in_(ids),
                TradeOrder.supplier_enterprise_id.in_(ids),
            )
        )
    order_rows = {str(r[0]): r for r in order_query.group_by(func.date(TradeOrder.created_at)).all()}

    quantity_query = (
        db.query(
            func.date(TradeOrder.created_at).label("d"),
            func.coalesce(func.sum(TradeOrderItem.quantity), 0),
        )
        .join(TradeOrderItem, TradeOrderItem.order_id == TradeOrder.id)
        .filter(func.date(TradeOrder.created_at) >= start)
    )
    if ids is not None and ids:
        quantity_query = quantity_query.filter(
            or_(
                TradeOrder.buyer_enterprise_id.in_(ids),
                TradeOrder.supplier_enterprise_id.in_(ids),
            )
        )
    quantity_rows = {
        str(r[0]): r[1]
        for r in quantity_query.group_by(func.date(TradeOrder.created_at)).all()
    }

    inquiry_query = db.query(
        func.date(Inquiry.created_at).label("d"), func.count(Inquiry.id)
    ).filter(func.date(Inquiry.created_at) >= start)
    if ids is not None and ids:
        inquiry_query = inquiry_query.filter(Inquiry.buyer_enterprise_id.in_(ids))
    inquiry_rows = {str(r[0]): r[1] for r in inquiry_query.group_by(func.date(Inquiry.created_at)).all()}

    dates = _date_series(days)
    return {
        "dates": dates,
        "order_count": [int(order_rows.get(d, (None, 0, 0))[1] or 0) for d in dates],
        "order_amount": [float(dec(order_rows.get(d, (None, 0, 0))[2])) for d in dates],
        "order_quantity": [float(dec(quantity_rows.get(d, 0))) for d in dates],
        "inquiry_count": [int(inquiry_rows.get(d, 0) or 0) for d in dates],
    }


def price_trend(
    db: Session, days: int = 30, category_id: Optional[int] = None, user: Optional[User] = None
) -> Dict:
    days = max(1, min(days, 365))
    ids = _scoped_ids(db, user)
    start = date.today() - timedelta(days=days - 1)
    query = (
        db.query(
            func.date(TradeOrder.confirmed_at).label("d"),
            func.avg(TradeOrderItem.unit_price),
            func.min(TradeOrderItem.unit_price),
            func.max(TradeOrderItem.unit_price),
            func.coalesce(func.sum(TradeOrderItem.quantity), 0),
        )
        .join(TradeOrderItem, TradeOrderItem.order_id == TradeOrder.id)
        .join(Product, Product.id == TradeOrderItem.product_id)
        .filter(
            TradeOrder.status.in_(["confirmed", "delivering", "completed", "settled"]),
            func.date(TradeOrder.confirmed_at) >= start,
        )
    )
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if ids is not None:
        if not ids:
            return {"dates": _date_series(days), "avg_price": [0.0] * days,
                    "min_price": [0.0] * days, "max_price": [0.0] * days,
                    "quantity": [0.0] * days}
        query = query.filter(
            or_(
                TradeOrder.buyer_enterprise_id.in_(ids),
                TradeOrder.supplier_enterprise_id.in_(ids),
            )
        )
    rows = {
        str(r[0]): r
        for r in query.group_by(func.date(TradeOrder.confirmed_at)).all()
    }
    dates = _date_series(days)
    category_name = None
    if category_id:
        category = db.get(Category, category_id)
        category_name = category.name if category else None
    return {
        "dates": dates,
        "avg_price": [round(float(dec(rows[d][1])), 2) if d in rows and rows[d][1] else 0.0 for d in dates],
        "min_price": [round(float(dec(rows[d][2])), 2) if d in rows and rows[d][2] else 0.0 for d in dates],
        "max_price": [round(float(dec(rows[d][3])), 2) if d in rows and rows[d][3] else 0.0 for d in dates],
        "quantity": [float(dec(rows[d][4])) if d in rows else 0.0 for d in dates],
        "unit": "ton",
        "category_name": category_name,
    }


def industry(db: Session, user: Optional[User] = None, limit: int = 10) -> Dict:
    ids = _scoped_ids(db, user)
    limit = max(1, min(limit, 50))

    def _trade_join():
        query = (
            db.query(
                func.count(TradeOrderItem.id),
                func.coalesce(func.sum(TradeOrderItem.quantity), 0),
                func.coalesce(func.sum(TradeOrderItem.amount), 0),
            )
            .join(TradeOrder, TradeOrder.id == TradeOrderItem.order_id)
            .join(Product, Product.id == TradeOrderItem.product_id)
        )
        if ids is not None and ids:
            query = query.filter(
                or_(
                    TradeOrder.buyer_enterprise_id.in_(ids),
                    TradeOrder.supplier_enterprise_id.in_(ids),
                )
            )
        return query

    by_category: List[Dict] = []
    product_counts = dict(
        db.query(Product.category_id, func.count(Product.id)).group_by(Product.category_id).all()
    )
    inventory_by_product = dict(
        db.query(Inventory.product_id, func.coalesce(func.sum(Inventory.quantity), 0))
        .group_by(Inventory.product_id)
        .all()
    )
    categories = db.query(Category).all()
    for category in categories:
        category_params = _trade_join().filter(Product.category_id == category.id).one()
        product_ids = [
            row[0] for row in db.query(Product.id).filter(Product.category_id == category.id).all()
        ]
        inventory_qty = sum((dec(inventory_by_product.get(pid, 0)) for pid in product_ids), ZERO)
        by_category.append(
            {
                "name": category.name,
                "product_count": int(product_counts.get(category.id, 0)),
                "inventory_quantity": float(inventory_qty),
                "order_quantity": float(dec(category_params[1])),
                "trade_amount": float(dec(category_params[2])),
                "order_count": int(category_params[0] or 0),
            }
        )
    by_category.sort(key=lambda row: row["trade_amount"], reverse=True)

    by_grade = _dimension(db, Product.grade, ids, _trade_join)
    by_origin = _dimension(db, Product.origin, ids, _trade_join)

    top_enterprises = (
        db.query(
            Enterprise.name,
            func.coalesce(func.sum(TradeOrderItem.amount), 0),
            func.count(TradeOrderItem.id),
            func.coalesce(func.sum(TradeOrderItem.quantity), 0),
        )
        .join(TradeOrder, TradeOrder.supplier_enterprise_id == Enterprise.id)
        .join(TradeOrderItem, TradeOrderItem.order_id == TradeOrder.id)
        .group_by(Enterprise.name)
        .order_by(func.coalesce(func.sum(TradeOrderItem.amount), 0).desc())
        .limit(limit)
        .all()
    )
    by_enterprise = [
        {
            "name": row[0],
            "product_count": 0,
            "inventory_quantity": 0.0,
            "order_quantity": float(dec(row[3])),
            "trade_amount": float(dec(row[1])),
            "order_count": int(row[2] or 0),
        }
        for row in top_enterprises
    ]
    return {
        "by_category": by_category,
        "by_grade": by_grade,
        "by_origin": by_origin,
        "by_enterprise": by_enterprise,
    }


def _dimension(db: Session, column, ids: Optional[Sequence[int]], trade_join_factory) -> List[Dict]:
    rows = (
        db.query(column, func.count(Product.id))
        .filter(column.isnot(None), column != "")
        .group_by(column)
        .all()
    )
    result: List[Dict] = []
    for name, product_count in rows:
        stats = trade_join_factory().filter(column == name).one()
        result.append(
            {
                "name": name or "未填写",
                "product_count": int(product_count or 0),
                "inventory_quantity": 0.0,
                "order_quantity": float(dec(stats[1])),
                "trade_amount": float(dec(stats[2])),
                "order_count": int(stats[0] or 0),
            }
        )
    result.sort(key=lambda row: row["trade_amount"], reverse=True)
    return result
