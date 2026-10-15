# -*- coding: utf-8 -*-
"""结算服务：结算单生成、确认、回款登记、对账单。

平台不自建支付通道（ADR-07）：本模块只登记交易流水与回款信息，资金实际收付由银行完成。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.scope import is_unrestricted
from app.core.timeutil import now
from app.models.enterprise import Enterprise
from app.models.org import User
from app.models.settlement import Settlement, SettlementLine, TransactionFlow
from app.models.trade import TradeOrder
from app.schemas.finance import PaymentIn, SettlementCreateIn
from app.services import integration
from app.services.inventory_service import dec
from app.services.numbering import next_no

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _year_prefix(prefix: str) -> str:
    from datetime import date

    return f"{prefix}-{date.today().year}"


def create_settlement(db: Session, data: SettlementCreateIn, user: Optional[User] = None) -> Settlement:
    enterprise = db.get(Enterprise, data.enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    query = db.query(TradeOrder).filter(TradeOrder.status.in_(["completed", "settled"]))
    if data.settle_type == "receivable":
        query = query.filter(TradeOrder.supplier_enterprise_id == data.enterprise_id)
    elif data.settle_type == "payable":
        query = query.filter(TradeOrder.buyer_enterprise_id == data.enterprise_id)
    else:
        raise BadRequest("园区费用结算单请使用 park_fee 专用接口")
    if data.order_ids:
        query = query.filter(TradeOrder.id.in_(data.order_ids))
    if data.period_start:
        query = query.filter(func.date(TradeOrder.completed_at) >= data.period_start)
    if data.period_end:
        query = query.filter(func.date(TradeOrder.completed_at) <= data.period_end)
    orders = query.all()
    if not orders:
        raise BadRequest("所选期间内没有可结算的已完成订单")
    already = {
        row[0]
        for row in db.query(SettlementLine.biz_no)
        .filter(
            SettlementLine.biz_type == "order",
            SettlementLine.biz_no.in_([o.order_no for o in orders]),
        )
        .all()
    }
    orders = [o for o in orders if o.order_no not in already]
    if not orders:
        raise BadRequest("所选订单均已结算")
    fee_rate = dec(settings.PLATFORM_SERVICE_FEE_RATE)
    order_amount = sum((dec(o.total_amount) for o in orders), ZERO).quantize(CENT)
    fee_amount = (order_amount * fee_rate).quantize(CENT)
    settlement = Settlement(
        settlement_no=next_no(db, "settlement", _year_prefix("GZ-SET")),
        enterprise_id=data.enterprise_id,
        settle_type=data.settle_type,
        period_start=data.period_start,
        period_end=data.period_end,
        order_amount=order_amount,
        fee_amount=fee_amount,
        settle_amount=(order_amount - fee_amount).quantize(CENT),
        settled_amount=ZERO,
        pay_status="unpaid",
        receive_status="unconfirmed",
        status="pending",
        remark=data.remark,
        created_by=user.id if user else None,
    )
    db.add(settlement)
    db.flush()
    lines: List[Dict] = []
    for order in orders:
        db.add(
            SettlementLine(
                settlement_id=settlement.id,
                biz_type="order",
                biz_no=order.order_no,
                order_id=order.id,
                amount=order.total_amount,
                fee_rate=ZERO,
                remark="订单货款",
            )
        )
        lines.append({"biz_no": order.order_no, "amount": float(order.total_amount)})
    if fee_amount > 0:
        db.add(
            SettlementLine(
                settlement_id=settlement.id,
                biz_type="service_fee",
                biz_no=settlement.settlement_no,
                amount=fee_amount,
                fee_rate=fee_rate,
                remark="平台服务费",
            )
        )
    db.add(
        TransactionFlow(
            flow_no=next_no(db, "transaction_flow", _year_prefix("GZ-FLOW"), width=6),
            settlement_id=settlement.id,
            enterprise_id=data.enterprise_id,
            direction="in" if data.settle_type == "receivable" else "out",
            biz_type="order_payment",
            amount=settlement.settle_amount,
            pay_method="bank_transfer",
            pay_status="pending",
            receive_status="pending",
            remark=f"结算单 {settlement.settlement_no} 待收付",
            created_at=now(),
        )
    )
    db.flush()
    integration.enqueue(
        db,
        event_type="settlement.created",
        aggregate_type="settlement",
        aggregate_id=settlement.settlement_no,
        payload=integration.settlement_payload(settlement, lines),
    )
    return settlement


def confirm_settlement(db: Session, settlement: Settlement, user: Optional[User] = None) -> Settlement:
    if settlement.status != "pending":
        raise Conflict(f"结算单当前状态【{settlement.status}】不可确认")
    settlement.status = "confirmed"
    settlement.receive_status = "confirmed"
    settlement.confirmed_at = now()
    settlement.remark = f"{settlement.remark or ''} 已确认".strip()
    db.flush()
    integration.enqueue(
        db,
        event_type="settlement.confirmed",
        aggregate_type="settlement",
        aggregate_id=settlement.settlement_no,
        payload=integration.settlement_payload(settlement, []),
    )
    return settlement


def register_payment(
    db: Session, settlement: Settlement, data: PaymentIn, user: Optional[User] = None
) -> Settlement:
    if settlement.status == "cancelled":
        raise Conflict("已取消的结算单不可登记回款")
    amount = dec(data.amount).quantize(CENT)
    if amount <= 0:
        raise BadRequest("回款金额必须大于 0")
    unpaid = (dec(settlement.settle_amount) - dec(settlement.settled_amount)).quantize(CENT)
    if amount > unpaid:
        raise BadRequest(f"回款金额超过未结金额 {unpaid}")
    settlement.settled_amount = (dec(settlement.settled_amount) + amount).quantize(CENT)
    if dec(settlement.settled_amount) >= dec(settlement.settle_amount):
        settlement.pay_status = "paid"
        settlement.status = "settled"
        settlement.settled_at = now()
    else:
        settlement.pay_status = "partial"
        if settlement.status == "pending":
            settlement.status = "confirmed"
            settlement.confirmed_at = settlement.confirmed_at or now()
    db.add(
        TransactionFlow(
            flow_no=next_no(db, "transaction_flow", _year_prefix("GZ-FLOW"), width=6),
            settlement_id=settlement.id,
            enterprise_id=settlement.enterprise_id,
            direction="in" if settlement.settle_type == "receivable" else "out",
            biz_type="order_payment",
            amount=amount,
            pay_method=data.pay_method,
            pay_status="success",
            receive_status="received",
            trade_no=data.trade_no,
            paid_at=data.paid_at or now(),
            remark=data.remark or f"结算单 {settlement.settlement_no} 回款登记",
            created_at=now(),
        )
    )
    db.flush()
    integration.enqueue(
        db,
        event_type="settlement.payment",
        aggregate_type="settlement",
        aggregate_id=settlement.settlement_no,
        payload={
            "settlement_no": settlement.settlement_no,
            "amount": float(amount),
            "pay_method": data.pay_method,
            "trade_no": data.trade_no,
            "settled_amount": float(settlement.settled_amount),
            "pay_status": settlement.pay_status,
        },
    )
    return settlement


def statement(
    db: Session,
    enterprise_id: int,
    start_date=None,
    end_date=None,
) -> Dict:
    enterprise = db.get(Enterprise, enterprise_id)
    if enterprise is None:
        raise NotFound("企业不存在")
    query = db.query(TradeOrder).filter(
        TradeOrder.status.in_(["completed", "settled"]),
    )
    from sqlalchemy import or_

    query = query.filter(
        or_(
            TradeOrder.supplier_enterprise_id == enterprise_id,
            TradeOrder.buyer_enterprise_id == enterprise_id,
        )
    )
    if start_date:
        query = query.filter(func.date(TradeOrder.completed_at) >= start_date)
    if end_date:
        query = query.filter(func.date(TradeOrder.completed_at) <= end_date)
    orders = query.order_by(TradeOrder.completed_at.asc()).all()
    order_nos = [o.order_no for o in orders]
    counterparties: Dict[int, str] = {
        e.id: e.name for e in db.query(Enterprise).all()
    }
    fee_rate = dec(settings.PLATFORM_SERVICE_FEE_RATE)
    settled_map: Dict[str, Decimal] = {}
    if order_nos:
        rows = (
            db.query(SettlementLine.biz_no, func.coalesce(func.sum(SettlementLine.amount), 0))
            .filter(
                SettlementLine.biz_type == "order",
                SettlementLine.biz_no.in_(order_nos),
            )
            .group_by(SettlementLine.biz_no)
            .all()
        )
        settled_map = {str(r[0]): dec(r[1]) for r in rows}
    items = []
    order_amount = ZERO
    fee_amount = ZERO
    settled_amount = ZERO
    for order in orders:
        is_supplier = order.supplier_enterprise_id == enterprise_id
        counterparty_id = order.buyer_enterprise_id if is_supplier else order.supplier_enterprise_id
        total = dec(order.total_amount)
        fee = (total * fee_rate).quantize(CENT) if is_supplier else ZERO
        order_amount += total
        fee_amount += fee
        settled_amount += settled_map.get(order.order_no, ZERO)
        items.append(
            {
                "order_no": order.order_no,
                "order_date": order.completed_at,
                "counterparty_name": counterparties.get(counterparty_id),
                "amount": float(total),
                "fee_amount": float(fee),
                "settled_amount": float(settled_map.get(order.order_no, ZERO)),
                "status": order.status,
            }
        )
    return {
        "enterprise_id": enterprise_id,
        "enterprise_name": enterprise.name,
        "start_date": start_date,
        "end_date": end_date,
        "order_count": len(orders),
        "order_amount": float(order_amount.quantize(CENT)),
        "fee_amount": float(fee_amount.quantize(CENT)),
        "settled_amount": float(settled_amount.quantize(CENT)),
        "invoiced_amount": 0.0,
        "items": items,
    }


def settlement_detail(db: Session, settlement: Settlement) -> Dict:
    lines = (
        db.query(SettlementLine)
        .filter(SettlementLine.settlement_id == settlement.id)
        .order_by(SettlementLine.id.asc())
        .all()
    )
    flows = (
        db.query(TransactionFlow)
        .filter(TransactionFlow.settlement_id == settlement.id)
        .order_by(TransactionFlow.id.asc())
        .all()
    )
    return {"lines": lines, "flows": flows}


def assert_visible(user: User, enterprise_id: int) -> None:
    if is_unrestricted(user):
        return
    if user.enterprise_id != enterprise_id:
        raise Forbidden("无权访问该企业的结算数据")
