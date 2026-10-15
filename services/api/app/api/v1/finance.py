# -*- coding: utf-8 -*-
"""电子结算接口：结算单、确认、回款登记、交易流水、对账单。"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups, flow_out, settlement_out
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import apply_own_enterprise, enterprise_scope_ids, is_unrestricted
from app.models.org import User
from app.models.settlement import Settlement, SettlementLine, TransactionFlow
from app.models.trade import TradeOrder
from app.schemas.finance import (
    PaymentIn,
    SettlementCreateIn,
    SettlementDetailOut,
    SettlementOut,
    StatementOut,
    TransactionFlowOut,
)
from app.services import settlement_service

router = APIRouter(tags=["电子结算"])


def _visible(db: Session, user: User, enterprise_id: int) -> None:
    if is_unrestricted(user):
        return
    if enterprise_id not in set(enterprise_scope_ids(db, user) or []):
        raise Forbidden("无权访问该企业的结算数据")


@router.get("/settlements", response_model=ApiResponse[PageData[SettlementOut]], summary="结算单列表")
def list_settlements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    enterprise_id: Optional[int] = None,
    settle_type: Optional[str] = None,
    status: Optional[str] = None,
    pay_status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("settlement:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Settlement)
    if enterprise_id:
        _visible(db, user, enterprise_id)
        query = query.filter(Settlement.enterprise_id == enterprise_id)
    if settle_type:
        query = query.filter(Settlement.settle_type == settle_type)
    if status:
        query = query.filter(Settlement.status == status)
    if pay_status:
        query = query.filter(Settlement.pay_status == pay_status)
    if start_date:
        query = query.filter(func.date(Settlement.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Settlement.created_at) <= end_date)
    query = apply_own_enterprise(query, Settlement, user, "enterprise_id", db)
    total = query.count()
    rows = query.order_by(Settlement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok(paginate([settlement_out(lk, row) for row in rows], total, page, page_size))


@router.post("/settlements", response_model=ApiResponse[SettlementOut], summary="生成结算单")
def create_settlement(
    payload: SettlementCreateIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("settlement:write")),
) -> dict:
    _visible(db, user, payload.enterprise_id)
    settlement = settlement_service.create_settlement(db, payload, user)
    return ok(settlement_out(lk, settlement))


@router.get("/settlements/{settlement_id}", response_model=ApiResponse[SettlementDetailOut], summary="结算单详情")
def get_settlement(
    settlement_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("settlement:read")),
) -> dict:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise NotFound("结算单不存在")
    _visible(db, user, settlement.enterprise_id)
    detail = settlement_service.settlement_detail(db, settlement)
    return ok(settlement_out(lk, settlement, detail["lines"], detail["flows"]))


@router.post("/settlements/{settlement_id}/confirm", response_model=ApiResponse[SettlementOut], summary="确认结算单")
def confirm_settlement(
    settlement_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("settlement:write")),
) -> dict:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise NotFound("结算单不存在")
    _visible(db, user, settlement.enterprise_id)
    settlement = settlement_service.confirm_settlement(db, settlement, user)
    return ok(settlement_out(lk, settlement))


@router.post("/settlements/{settlement_id}/payment", response_model=ApiResponse[SettlementOut], summary="登记回款")
def register_payment(
    settlement_id: int,
    payload: PaymentIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("settlement:write")),
) -> dict:
    settlement = db.get(Settlement, settlement_id)
    if settlement is None:
        raise NotFound("结算单不存在")
    _visible(db, user, settlement.enterprise_id)
    settlement = settlement_service.register_payment(db, settlement, payload, user)
    return ok(settlement_out(lk, settlement))


@router.get("/finance/flows", response_model=ApiResponse[PageData[TransactionFlowOut]], summary="交易流水")
def list_flows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    enterprise_id: Optional[int] = None,
    order_id: Optional[int] = None,
    settlement_id: Optional[int] = None,
    direction: Optional[str] = None,
    biz_type: Optional[str] = None,
    pay_status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("settlement:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(TransactionFlow)
    if enterprise_id:
        _visible(db, user, enterprise_id)
        query = query.filter(TransactionFlow.enterprise_id == enterprise_id)
    if order_id:
        query = query.filter(TransactionFlow.order_id == order_id)
    if settlement_id:
        query = query.filter(TransactionFlow.settlement_id == settlement_id)
    if direction:
        query = query.filter(TransactionFlow.direction == direction)
    if biz_type:
        query = query.filter(TransactionFlow.biz_type == biz_type)
    if pay_status:
        query = query.filter(TransactionFlow.pay_status == pay_status)
    if start_date:
        query = query.filter(func.date(TransactionFlow.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(TransactionFlow.created_at) <= end_date)
    query = apply_own_enterprise(query, TransactionFlow, user, "enterprise_id", db)
    total = query.count()
    rows = query.order_by(TransactionFlow.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    order_ids = [row.order_id for row in rows if row.order_id]
    settlement_ids = [row.settlement_id for row in rows if row.settlement_id]
    orders = {
        o.id: o.order_no
        for o in db.query(TradeOrder).filter(TradeOrder.id.in_(order_ids or [-1])).all()
    }
    settlements = {
        s.id: s.settlement_no
        for s in db.query(Settlement).filter(Settlement.id.in_(settlement_ids or [-1])).all()
    }
    items = []
    for row in rows:
        item = flow_out(lk, row)
        item["order_no"] = orders.get(row.order_id)
        item["settlement_no"] = settlements.get(row.settlement_id)
        items.append(item)
    return ok(paginate(items, total, page, page_size))


@router.get("/finance/statement", response_model=ApiResponse[StatementOut], summary="企业对账单")
def finance_statement(
    enterprise_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("settlement:read")),
) -> dict:
    _visible(db, user, enterprise_id)
    return ok(settlement_service.statement(db, enterprise_id, start_date, end_date))


@router.get(
    "/finance/overview",
    response_model=ApiResponse[dict],
    summary="财务概览（应收/应付/已收/未收）",
)
def finance_overview(
    enterprise_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require("settlement:read")),
) -> dict:
    query = db.query(Settlement)
    if enterprise_id:
        _visible(db, user, enterprise_id)
        query = query.filter(Settlement.enterprise_id == enterprise_id)
    query = apply_own_enterprise(query, Settlement, user, "enterprise_id", db)
    rows = query.all()
    receivable = sum(
        (row.settle_amount - row.settled_amount)
        for row in rows
        if row.settle_type == "receivable" and row.status in ("pending", "confirmed")
    )
    payable = sum(
        (row.settle_amount - row.settled_amount)
        for row in rows
        if row.settle_type == "payable" and row.status in ("pending", "confirmed")
    )
    received = sum((row.settled_amount for row in rows if row.settle_type == "receivable"))
    paid = sum((row.settled_amount for row in rows if row.settle_type == "payable"))
    fee = sum((row.fee_amount for row in rows))
    return ok(
        {
            "settlement_count": len(rows),
            "receivable_unsettled": float(receivable),
            "payable_unsettled": float(payable),
            "received_amount": float(received),
            "paid_amount": float(paid),
            "service_fee_amount": float(fee),
        }
    )
