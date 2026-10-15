# -*- coding: utf-8 -*-
"""数据驾驶舱接口。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups
from app.core.database import get_db
from app.core.deps import require
from app.core.response import ApiResponse, ok
from app.models.org import User
from app.models.settlement import Settlement
from app.schemas.dashboard import (
    IndustryOut,
    OverviewOut,
    PriceTrendOut,
    RankingItemOut,
    RankingOut,
    TrendOut,
)
from app.services import dashboard_service
from app.core.scope import apply_own_enterprise, is_unrestricted

router = APIRouter(prefix="/dashboard", tags=["数据驾驶舱"])


@router.get("/overview", response_model=ApiResponse[OverviewOut], summary="核心指标概览")
def overview(
    refresh: bool = Query(False, description="是否跳过 60 秒缓存"),
    db: Session = Depends(get_db),
    user: User = Depends(require("data:read")),
) -> dict:
    return ok(dashboard_service.overview(db, user, use_cache=not refresh))


@router.get("/trend", response_model=ApiResponse[TrendOut], summary="交易趋势")
def trend(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require("data:read")),
) -> dict:
    return ok(dashboard_service.trend(db, days, user))


@router.get("/price-trend", response_model=ApiResponse[PriceTrendOut], summary="价格趋势")
def price_trend(
    days: int = Query(30, ge=1, le=365),
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("data:read")),
) -> dict:
    return ok(dashboard_service.price_trend(db, days, category_id, user))


@router.get("/industry", response_model=ApiResponse[IndustryOut], summary="产业分析")
def industry(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require("data:read")),
) -> dict:
    return ok(dashboard_service.industry(db, user, limit))


@router.get("/ranking", response_model=ApiResponse[RankingOut], summary="排行榜")
def ranking(
    dimension: str = Query("enterprise", description="enterprise / product"),
    metric: str = Query("amount", description="amount / quantity"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("data:read")),
) -> dict:
    from sqlalchemy import func, or_

    from app.models.trade import TradeOrder, TradeOrderItem

    if dimension == "product":
        column = TradeOrderItem.product_id
        metric_column = (
            func.coalesce(func.sum(TradeOrderItem.amount), 0)
            if metric == "amount"
            else func.coalesce(func.sum(TradeOrderItem.quantity), 0)
        )
    else:
        column = TradeOrder.supplier_enterprise_id
        metric_column = (
            func.coalesce(func.sum(TradeOrder.total_amount), 0)
            if metric == "amount"
            else func.coalesce(func.sum(TradeOrder.total_amount), 0)
        )
    query = db.query(column, metric_column)
    if dimension == "product":
        query = query.join(TradeOrder, TradeOrder.id == TradeOrderItem.order_id)
    query = query.filter(TradeOrder.status.in_(["confirmed", "delivering", "completed", "settled"]))
    if not is_unrestricted(user):
        from app.core.scope import enterprise_scope_ids

        scope = enterprise_scope_ids(db, user) or []
        query = query.filter(
            or_(
                TradeOrder.buyer_enterprise_id.in_(scope or [-1]),
                TradeOrder.supplier_enterprise_id.in_(scope or [-1]),
            )
        )
    rows = query.group_by(column).order_by(metric_column.desc()).limit(limit).all()
    items: List[dict] = []
    for index, row in enumerate(rows, start=1):
        if dimension == "product":
            product = lk.product(int(row[0])) if row[0] else None
            name = product.name if product else f"商品#{row[0]}"
        else:
            name = lk.enterprise_name(int(row[0])) or f"企业#{row[0]}"
        items.append(
            {
                "rank": index,
                "name": name,
                "value": float(row[1] or 0),
                "extra": None,
            }
        )
    return ok(
        {
            "title": "商品交易排行" if dimension == "product" else "商户交易排行",
            "unit": "元" if metric == "amount" else "吨",
            "items": items,
        }
    )


@router.get("/settlement-summary", response_model=ApiResponse[dict], summary="结算概览")
def settlement_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require("data:read")),
) -> dict:
    from sqlalchemy import func

    query = db.query(
        func.count(Settlement.id),
        func.coalesce(func.sum(Settlement.settle_amount), 0),
        func.coalesce(func.sum(Settlement.settled_amount), 0),
        func.coalesce(func.sum(Settlement.fee_amount), 0),
    )
    query = apply_own_enterprise(query, Settlement, user, "enterprise_id", db)
    row = query.one()
    settle_amount = float(row[1] or 0)
    settled_amount = float(row[2] or 0)
    return ok(
        {
            "settlement_count": int(row[0] or 0),
            "settle_amount": settle_amount,
            "settled_amount": settled_amount,
            "unsettled_amount": round(settle_amount - settled_amount, 2),
            "service_fee_amount": float(row[3] or 0),
            "settle_rate": round(settled_amount / settle_amount, 4) if settle_amount else 0.0,
        }
    )
