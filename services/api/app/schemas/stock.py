# -*- coding: utf-8 -*-
"""仓储与库存 Schema。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


# ------------------------------------------------------------------ 仓库与库位
class WarehouseIn(BaseModel):
    code: Optional[str] = Field(None, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    enterprise_id: Optional[int] = None
    park_id: Optional[int] = None
    address: Optional[str] = None
    warehouse_type: str = "own"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    capacity: Optional[Decimal] = None
    status: str = "active"
    remark: Optional[str] = None


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    park_id: Optional[int] = None
    address: Optional[str] = None
    warehouse_type: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    capacity: Optional[Decimal] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class WarehouseOut(ORMModel):
    id: int
    code: str
    name: str
    enterprise_id: int
    enterprise_name: Optional[str] = None
    park_id: Optional[int] = None
    address: Optional[str] = None
    warehouse_type: str = "own"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    capacity: float = 0
    status: str = "active"
    remark: Optional[str] = None
    location_count: int = 0
    inventory_quantity: float = 0


class LocationIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    zone: Optional[str] = None
    capacity: Optional[Decimal] = None
    status: str = "active"
    remark: Optional[str] = None


class LocationOut(ORMModel):
    id: int
    warehouse_id: int
    code: str
    name: str
    zone: Optional[str] = None
    capacity: float = 0
    status: str = "active"
    remark: Optional[str] = None


# ------------------------------------------------------------------ 库存
class InventoryOut(ORMModel):
    id: int
    product_id: int
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    spec: Optional[str] = None
    grade: Optional[str] = None
    origin: Optional[str] = None
    unit: str = "ton"
    enterprise_id: Optional[int] = None
    enterprise_name: Optional[str] = None
    warehouse_id: int
    warehouse_name: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    batch_no: str = "DEFAULT"
    quantity: float = 0
    locked_quantity: float = 0
    available_quantity: float = 0
    unit_cost: float = 0
    amount: float = 0
    production_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quality_status: str = "pending"
    updated_at: Optional[datetime] = None


class InventorySummaryOut(BaseModel):
    product_id: int
    product_code: Optional[str] = None
    product_name: str
    category_name: Optional[str] = None
    enterprise_id: Optional[int] = None
    enterprise_name: Optional[str] = None
    unit: str = "ton"
    price: float = 0
    total_quantity: float = 0
    locked_quantity: float = 0
    available_quantity: float = 0
    inventory_value: float = 0
    warehouse_count: int = 0
    batch_count: int = 0


class StockMoveOut(ORMModel):
    id: int
    move_no: str
    move_type: str
    product_id: int
    product_name: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None
    location_id: Optional[int] = None
    to_warehouse_id: Optional[int] = None
    to_warehouse_name: Optional[str] = None
    quantity: float = 0
    unit_cost: float = 0
    batch_no: Optional[str] = None
    ref_type: Optional[str] = None
    ref_no: Optional[str] = None
    operator_name: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


# ------------------------------------------------------------------ 出入库请求
class StockInIn(BaseModel):
    product_id: int
    warehouse_id: int
    location_id: Optional[int] = None
    batch_no: Optional[str] = "DEFAULT"
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Optional[Decimal] = None
    production_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quality_status: Optional[str] = None
    ref_type: Optional[str] = "manual"
    ref_no: Optional[str] = None
    remark: Optional[str] = None


class StockOutIn(BaseModel):
    product_id: int
    warehouse_id: int
    location_id: Optional[int] = None
    batch_no: Optional[str] = "DEFAULT"
    quantity: Decimal = Field(..., gt=0)
    ref_type: Optional[str] = "manual"
    ref_no: Optional[str] = None
    remark: Optional[str] = None


class StockTransferIn(BaseModel):
    product_id: int
    from_warehouse_id: int
    from_location_id: Optional[int] = None
    to_warehouse_id: int
    to_location_id: Optional[int] = None
    batch_no: Optional[str] = "DEFAULT"
    quantity: Decimal = Field(..., gt=0)
    remark: Optional[str] = None


class StockAdjustIn(BaseModel):
    product_id: int
    warehouse_id: int
    location_id: Optional[int] = None
    batch_no: Optional[str] = "DEFAULT"
    target_quantity: Decimal = Field(..., ge=0, description="调整后的目标数量")
    remark: Optional[str] = None


class InventoryCheckItem(BaseModel):
    product_id: int
    location_id: Optional[int] = None
    batch_no: Optional[str] = "DEFAULT"
    actual_quantity: Decimal = Field(..., ge=0)


class InventoryCheckIn(BaseModel):
    warehouse_id: int
    items: List[InventoryCheckItem] = Field(..., min_length=1)
    remark: Optional[str] = None


class InventoryCheckResult(BaseModel):
    warehouse_id: int
    checked_count: int = 0
    diff_count: int = 0
    profit_quantity: float = 0
    loss_quantity: float = 0
    details: List[dict] = Field(default_factory=list)
