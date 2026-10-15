# -*- coding: utf-8 -*-
"""结算域：结算单、结算明细、交易流水。

设计原则（ADR-07）：平台不自建支付通道，只维护交易流水与对账信息；
资金实际收付仍走银行/持牌机构，平台只登记回单与状态。
"""
from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timeutil import now
from app.models.base import TimestampMixin, bigint, money, rate


class Settlement(Base, TimestampMixin):
    """结算单（应收/应付/园区费用）。"""

    __tablename__ = "settlement"

    id = Column(bigint(), primary_key=True)
    settlement_no = Column(String(64), nullable=False, unique=True, index=True)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    settle_type = Column(String(16), nullable=False, default="receivable", index=True)
    period_start = Column(Date)
    period_end = Column(Date)
    order_amount = Column(money(), nullable=False, default=0)
    fee_amount = Column(money(), nullable=False, default=0)
    settle_amount = Column(money(), nullable=False, default=0)
    settled_amount = Column(money(), nullable=False, default=0)
    pay_status = Column(String(16), nullable=False, default="unpaid", index=True)
    receive_status = Column(String(16), nullable=False, default="unconfirmed")
    status = Column(String(16), nullable=False, default="pending", index=True)
    remark = Column(String(255))
    created_by = Column(bigint())
    confirmed_at = Column(DateTime)
    settled_at = Column(DateTime)
    odoo_move_id = Column(bigint())

    lines = relationship(
        "SettlementLine", back_populates="settlement", cascade="all, delete-orphan", lazy="selectin"
    )


class SettlementLine(Base):
    """结算明细：订单货款 / 园区费用 / 平台服务费。"""

    __tablename__ = "settlement_line"

    id = Column(bigint(), primary_key=True)
    settlement_id = Column(bigint(), ForeignKey("settlement.id"), nullable=False, index=True)
    biz_type = Column(String(16), nullable=False, default="order")
    biz_no = Column(String(64), index=True)
    order_id = Column(bigint(), index=True)
    amount = Column(money(), nullable=False, default=0)
    fee_rate = Column(rate(), default=0)
    remark = Column(String(255))

    settlement = relationship("Settlement", back_populates="lines")


class TransactionFlow(Base):
    """交易流水（信息流，不代表真实资金通道）。"""

    __tablename__ = "transaction_flow"

    id = Column(bigint(), primary_key=True)
    flow_no = Column(String(64), nullable=False, unique=True, index=True)
    order_id = Column(bigint(), ForeignKey("trade_order.id"), index=True)
    settlement_id = Column(bigint(), ForeignKey("settlement.id"), index=True)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    counterparty_enterprise_id = Column(bigint(), index=True)
    direction = Column(String(8), nullable=False, default="in", index=True)
    biz_type = Column(String(24), nullable=False, default="order_payment", index=True)
    amount = Column(money(), nullable=False, default=0)
    pay_method = Column(String(24), nullable=False, default="bank_transfer")
    pay_status = Column(String(16), nullable=False, default="pending", index=True)
    receive_status = Column(String(16), nullable=False, default="pending")
    trade_no = Column(String(64), index=True)
    paid_at = Column(DateTime)
    remark = Column(String(255))
    created_at = Column(DateTime, default=now, nullable=False)
