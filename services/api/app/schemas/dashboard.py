# -*- coding: utf-8 -*-
"""数据驾驶舱 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class OverviewOut(BaseModel):
    enterprise_count: int = 0
    merchant_count: int = 0
    supplier_count: int = 0
    buyer_count: int = 0
    product_count: int = 0
    published_product_count: int = 0
    inventory_quantity: float = 0
    inventory_value: float = 0
    inventory_batch_count: int = 0
    inquiry_count: int = 0
    open_inquiry_count: int = 0
    quotation_count: int = 0
    order_count: int = 0
    order_amount: float = 0
    completed_order_count: int = 0
    completed_order_amount: float = 0
    today_order_count: int = 0
    today_order_amount: float = 0
    month_order_amount: float = 0
    park_count: int = 0
    stall_count: int = 0
    stall_rented: int = 0
    stall_rented_rate: float = 0
    warehouse_count: int = 0
    pending_audit_enterprise: int = 0
    pending_audit_product: int = 0
    unsettled_amount: float = 0


class TrendOut(BaseModel):
    dates: List[str] = Field(default_factory=list)
    order_count: List[int] = Field(default_factory=list)
    order_amount: List[float] = Field(default_factory=list)
    order_quantity: List[float] = Field(default_factory=list)
    inquiry_count: List[int] = Field(default_factory=list)


class PriceTrendOut(BaseModel):
    dates: List[str] = Field(default_factory=list)
    avg_price: List[float] = Field(default_factory=list)
    min_price: List[float] = Field(default_factory=list)
    max_price: List[float] = Field(default_factory=list)
    quantity: List[float] = Field(default_factory=list)
    unit: Optional[str] = None
    category_name: Optional[str] = None


class IndustryItemOut(BaseModel):
    name: str
    product_count: int = 0
    inventory_quantity: float = 0
    order_quantity: float = 0
    trade_amount: float = 0
    order_count: int = 0


class IndustryOut(BaseModel):
    by_category: List[IndustryItemOut] = Field(default_factory=list)
    by_grade: List[IndustryItemOut] = Field(default_factory=list)
    by_origin: List[IndustryItemOut] = Field(default_factory=list)
    by_enterprise: List[IndustryItemOut] = Field(default_factory=list)


class RankingItemOut(BaseModel):
    rank: int = 0
    name: str
    value: float = 0
    extra: Optional[str] = None


class RankingOut(BaseModel):
    title: str
    unit: str = ""
    items: List[RankingItemOut] = Field(default_factory=list)
