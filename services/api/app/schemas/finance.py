# -*- coding: utf-8 -*-
"""结算与财务 Schema。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


class SettlementCreateIn(BaseModel):
    enterprise_id: int
    settle_type: str = Field("receivable", description="receivable / payable / park_fee")
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    order_ids: List[int] = Field(default_factory=list, description="指定订单；为空则按期间归集已完成订单")
    remark: Optional[str] = None


class SettlementLineOut(ORMModel):
    id: int
    biz_type: str
    biz_no: Optional[str] = None
    order_id: Optional[int] = None
    amount: float = 0
    fee_rate: float = 0
    remark: Optional[str] = None


class SettlementOut(ORMModel):
    id: int
    settlement_no: str
    enterprise_id: int
    enterprise_name: Optional[str] = None
    settle_type: str = "receivable"
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    order_amount: float = 0
    fee_amount: float = 0
    settle_amount: float = 0
    settled_amount: float = 0
    unpaid_amount: float = 0
    pay_status: str = "unpaid"
    receive_status: str = "unconfirmed"
    status: str = "pending"
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None


class SettlementDetailOut(SettlementOut):
    lines: List[SettlementLineOut] = Field(default_factory=list)
    flows: List["TransactionFlowOut"] = Field(default_factory=list)


class PaymentIn(BaseModel):
    amount: Decimal = Field(..., gt=0)
    pay_method: str = Field("bank_transfer", description="bank_transfer / offline / other")
    trade_no: Optional[str] = Field(None, max_length=64, description="银行回单号")
    paid_at: Optional[datetime] = None
    remark: Optional[str] = None


class TransactionFlowOut(ORMModel):
    id: int
    flow_no: str
    order_id: Optional[int] = None
    order_no: Optional[str] = None
    settlement_id: Optional[int] = None
    settlement_no: Optional[str] = None
    enterprise_id: int
    enterprise_name: Optional[str] = None
    counterparty_enterprise_id: Optional[int] = None
    counterparty_enterprise_name: Optional[str] = None
    direction: str = "in"
    biz_type: str = "order_payment"
    amount: float = 0
    pay_method: str = "bank_transfer"
    pay_status: str = "pending"
    receive_status: str = "pending"
    trade_no: Optional[str] = None
    paid_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


class StatementItemOut(BaseModel):
    order_no: str
    order_date: Optional[datetime] = None
    counterparty_name: Optional[str] = None
    amount: float = 0
    fee_amount: float = 0
    settled_amount: float = 0
    status: str = ""


class StatementOut(BaseModel):
    enterprise_id: int
    enterprise_name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    order_count: int = 0
    order_amount: float = 0
    fee_amount: float = 0
    settled_amount: float = 0
    invoiced_amount: float = 0
    items: List[StatementItemOut] = Field(default_factory=list)


SettlementDetailOut.model_rebuild()
