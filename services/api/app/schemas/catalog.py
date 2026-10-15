# -*- coding: utf-8 -*-
"""商品分类与商品 Schema。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


class CategoryIn(BaseModel):
    code: Optional[str] = Field(None, max_length=64, description="不传则自动生成 GZ-XXX")
    name: str = Field(..., min_length=1, max_length=128)
    parent_id: Optional[int] = None
    sort: int = 0
    status: str = "active"
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None


class CategoryOut(ORMModel):
    id: int
    code: str
    name: str
    parent_id: Optional[int] = None
    level: int = 1
    sort: int = 0
    status: str = "active"
    description: Optional[str] = None
    product_count: int = 0


class CategoryTreeOut(BaseModel):
    id: int
    code: str
    name: str
    parent_id: Optional[int] = None
    level: int = 1
    sort: int = 0
    status: str = "active"
    product_count: int = 0
    children: List["CategoryTreeOut"] = Field(default_factory=list)


CategoryTreeOut.model_rebuild()


class ProductIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    code: Optional[str] = Field(None, max_length=64, description="不传则自动生成")
    category_id: int
    enterprise_id: Optional[int] = Field(None, description="平台管理员可指定；商户默认本企业")
    spec: Optional[str] = Field(None, max_length=64)
    grade: Optional[str] = Field(None, description="special / first / second / mixed")
    origin: Optional[str] = Field(None, max_length=64)
    harvest_year: Optional[str] = Field(None, max_length=8)
    package: Optional[str] = Field(None, max_length=64)
    unit: str = Field("ton", description="ton / kg / bag")
    price: Optional[Decimal] = None
    currency: str = "CNY"
    min_order_qty: Optional[Decimal] = None
    stock_warn_qty: Optional[Decimal] = None
    supply_quantity: Optional[Decimal] = Field(None, ge=0)
    supply_period: Optional[str] = Field(None, max_length=64)
    pricing_mode: str = Field("listed", description="listed / negotiable / inquiry")
    supply_status: str = Field("active", description="active / paused / completed")
    allow_inquiry: bool = True
    allow_bulk_purchase: bool = True
    main_image: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    test_report_url: Optional[str] = None
    quality_status: str = "pending"
    trace_enabled: bool = True
    description: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    spec: Optional[str] = None
    grade: Optional[str] = None
    origin: Optional[str] = None
    harvest_year: Optional[str] = None
    package: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    min_order_qty: Optional[Decimal] = None
    stock_warn_qty: Optional[Decimal] = None
    supply_quantity: Optional[Decimal] = Field(None, ge=0)
    supply_period: Optional[str] = Field(None, max_length=64)
    pricing_mode: Optional[str] = None
    supply_status: Optional[str] = None
    allow_inquiry: Optional[bool] = None
    allow_bulk_purchase: Optional[bool] = None
    main_image: Optional[str] = None
    images: Optional[List[str]] = None
    test_report_url: Optional[str] = None
    quality_status: Optional[str] = None
    trace_enabled: Optional[bool] = None
    description: Optional[str] = None


class ProductAuditIn(BaseModel):
    approved: bool = True
    remark: Optional[str] = Field(None, max_length=255)


class ProductOut(ORMModel):
    id: int
    code: str
    name: str
    category_id: int
    category_name: Optional[str] = None
    enterprise_id: int
    enterprise_name: Optional[str] = None
    spec: Optional[str] = None
    grade: Optional[str] = None
    origin: Optional[str] = None
    harvest_year: Optional[str] = None
    package: Optional[str] = None
    unit: str = "ton"
    price: float = 0
    currency: str = "CNY"
    min_order_qty: float = 0
    stock_warn_qty: float = 0
    supply_quantity: float = 0
    supply_period: Optional[str] = None
    pricing_mode: str = "listed"
    supply_status: str = "active"
    allow_inquiry: bool = True
    allow_bulk_purchase: bool = True
    main_image: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    test_report_url: Optional[str] = None
    quality_status: str = "pending"
    trace_enabled: bool = True
    status: str = "draft"
    audit_status: str = "pending"
    audit_remark: Optional[str] = None
    description: Optional[str] = None
    total_quantity: float = 0
    locked_quantity: float = 0
    available_quantity: float = 0
    inventory_value: float = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProductSearchOut(BaseModel):
    items: List[ProductOut] = Field(default_factory=list)
    total: int = 0
    engine: str = "sql"
