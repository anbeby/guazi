# -*- coding: utf-8 -*-
"""B2B 交易 Schema：询价、报价、订单、合同。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


# ------------------------------------------------------------------ 询价
class InquiryIn(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    unit: str = "ton"
    supplier_enterprise_id: Optional[int] = Field(None, description="指定供应商则定向询价")
    expect_price: Optional[Decimal] = None
    expect_delivery_date: Optional[date] = None
    delivery_address: Optional[str] = None
    remark: Optional[str] = None
    submit: bool = Field(True, description="创建后是否直接提交（进入待报价）")


class InquiryOut(ORMModel):
    id: int
    inquiry_no: str
    buyer_enterprise_id: int
    buyer_enterprise_name: Optional[str] = None
    supplier_enterprise_id: Optional[int] = None
    supplier_enterprise_name: Optional[str] = None
    product_id: int
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    spec: Optional[str] = None
    grade: Optional[str] = None
    origin: Optional[str] = None
    unit: str = "ton"
    quantity: float = 0
    expect_price: float = 0
    expect_delivery_date: Optional[date] = None
    delivery_address: Optional[str] = None
    remark: Optional[str] = None
    status: str = "draft"
    quoted_count: int = 0
    quotation_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InquiryDetailOut(InquiryOut):
    quotations: List["QuotationOut"] = Field(default_factory=list)


# ------------------------------------------------------------------ 报价
class QuotationIn(BaseModel):
    unit_price: Decimal = Field(..., gt=0)
    quantity: Optional[Decimal] = Field(None, gt=0, description="不传则按询价数量")
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    valid_until: Optional[date] = None
    delivery_date: Optional[date] = None
    payment_terms: Optional[str] = Field(None, max_length=128)
    remark: Optional[str] = None


class QuotationOut(ORMModel):
    id: int
    quotation_no: str
    inquiry_id: int
    inquiry_no: Optional[str] = None
    supplier_enterprise_id: int
    supplier_enterprise_name: Optional[str] = None
    buyer_enterprise_name: Optional[str] = None
    product_id: int
    product_name: Optional[str] = None
    quantity: float = 0
    unit: str = "ton"
    unit_price: float = 0
    amount: float = 0
    tax_rate: float = 0
    valid_until: Optional[date] = None
    delivery_date: Optional[date] = None
    payment_terms: Optional[str] = None
    remark: Optional[str] = None
    status: str = "submitted"
    order_id: Optional[int] = None
    order_no: Optional[str] = None
    created_at: Optional[datetime] = None


# ------------------------------------------------------------------ 订单
class OrderItemIn(BaseModel):
    product_id: int
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None
    batch_no: Optional[str] = "DEFAULT"
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)


class OrderIn(BaseModel):
    supplier_enterprise_id: int
    buyer_enterprise_id: Optional[int] = Field(None, description="平台管理员可指定买方")
    items: List[OrderItemIn] = Field(..., min_length=1)
    delivery_date: Optional[date] = None
    delivery_address: Optional[str] = None
    delivery_method: str = "self_pickup"
    remark: Optional[str] = None
    auto_confirm: bool = False


class OrderItemOut(ORMModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    spec: Optional[str] = None
    grade: Optional[str] = None
    unit: str = "ton"
    warehouse_id: Optional[int] = None
    batch_no: Optional[str] = None
    quantity: float = 0
    delivered_quantity: float = 0
    unit_price: float = 0
    amount: float = 0
    tax_rate: float = 0


class OrderOut(ORMModel):
    id: int
    order_no: str
    order_type: str
    inquiry_id: Optional[int] = None
    inquiry_no: Optional[str] = None
    quotation_id: Optional[int] = None
    buyer_enterprise_id: int
    buyer_enterprise_name: Optional[str] = None
    supplier_enterprise_id: int
    supplier_enterprise_name: Optional[str] = None
    amount: float = 0
    tax_amount: float = 0
    total_amount: float = 0
    currency: str = "CNY"
    delivery_date: Optional[date] = None
    delivery_address: Optional[str] = None
    delivery_method: str = "self_pickup"
    logistics_company: Optional[str] = None
    logistics_no: Optional[str] = None
    contract_id: Optional[int] = None
    contract_no: Optional[str] = None
    stock_deducted: bool = False
    status: str = "draft"
    remark: Optional[str] = None
    item_count: int = 0
    total_quantity: float = 0
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    items: List[OrderItemOut] = Field(default_factory=list)


class DeliverItemIn(BaseModel):
    item_id: int
    delivered_quantity: Decimal = Field(..., ge=0)


class DeliverIn(BaseModel):
    items: List[DeliverItemIn] = Field(default_factory=list)
    logistics_company: Optional[str] = None
    logistics_no: Optional[str] = None
    remark: Optional[str] = None


class OrderTimelineOut(BaseModel):
    status: str
    title: str
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    operator: Optional[str] = None


# ------------------------------------------------------------------ 合同
class ContractIn(BaseModel):
    title: Optional[str] = None
    order_id: Optional[int] = None
    buyer_enterprise_id: Optional[int] = None
    supplier_enterprise_id: Optional[int] = None
    amount: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    file_url: Optional[str] = None
    terms: Optional[str] = None
    remark: Optional[str] = None


class ContractUpdate(BaseModel):
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    file_url: Optional[str] = None
    terms: Optional[str] = None
    remark: Optional[str] = None


class ContractSignIn(BaseModel):
    party: str = Field(..., description="buyer / supplier")


class ContractOut(ORMModel):
    id: int
    contract_no: str
    title: str
    order_id: Optional[int] = None
    order_no: Optional[str] = None
    buyer_enterprise_id: int
    buyer_enterprise_name: Optional[str] = None
    supplier_enterprise_id: int
    supplier_enterprise_name: Optional[str] = None
    amount: float = 0
    sign_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    file_url: Optional[str] = None
    terms: Optional[str] = None
    status: str = "draft"
    signed_by_buyer: bool = False
    signed_by_supplier: bool = False
    buyer_signed_at: Optional[datetime] = None
    supplier_signed_at: Optional[datetime] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


InquiryDetailOut.model_rebuild()
