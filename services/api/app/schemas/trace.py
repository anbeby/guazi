# -*- coding: utf-8 -*-
"""溯源 Schema。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


class TraceBatchIn(BaseModel):
    batch_no: Optional[str] = Field(None, max_length=64, description="不传则自动生成 GZ-BATCH-YYYY-XXXX")
    product_id: int
    enterprise_id: Optional[int] = None
    quantity: Optional[Decimal] = None
    origin_base: Optional[str] = Field(None, max_length=160)
    origin_region: Optional[str] = Field(None, max_length=64)
    plant_date: Optional[date] = None
    harvest_date: Optional[date] = None
    process_enterprise: Optional[str] = Field(None, max_length=160)
    process_date: Optional[date] = None
    warehouse_id: Optional[int] = None
    test_report_url: Optional[str] = None
    quality_status: str = "pending"
    remark: Optional[str] = None


class TraceEventIn(BaseModel):
    stage: str = Field(..., description="planting / processing / warehouse / trade / sale")
    title: str = Field(..., max_length=128)
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=160)
    operator: Optional[str] = Field(None, max_length=64)
    evidence_url: Optional[str] = None


class TraceEventOut(ORMModel):
    id: int
    batch_id: int
    stage: str
    title: str
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    location: Optional[str] = None
    operator: Optional[str] = None
    evidence_url: Optional[str] = None
    created_at: Optional[datetime] = None


class TraceBatchOut(ORMModel):
    id: int
    batch_no: str
    qr_code: Optional[str] = None
    product_id: int
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    enterprise_id: int
    enterprise_name: Optional[str] = None
    quantity: float = 0
    origin_base: Optional[str] = None
    origin_region: Optional[str] = None
    plant_date: Optional[date] = None
    harvest_date: Optional[date] = None
    process_enterprise: Optional[str] = None
    process_date: Optional[date] = None
    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None
    test_report_url: Optional[str] = None
    quality_status: str = "pending"
    status: str = "active"
    remark: Optional[str] = None
    event_count: int = 0
    created_at: Optional[datetime] = None


class TraceBatchDetailOut(TraceBatchOut):
    events: List[TraceEventOut] = Field(default_factory=list)


class PublicTraceOut(BaseModel):
    """扫码公开结果（免鉴权）。"""

    batch_no: str
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    spec: Optional[str] = None
    grade: Optional[str] = None
    unit: Optional[str] = None
    origin: Optional[str] = None
    harvest_year: Optional[str] = None
    package: Optional[str] = None
    enterprise_name: Optional[str] = None
    enterprise_code: Optional[str] = None
    origin_base: Optional[str] = None
    origin_region: Optional[str] = None
    plant_date: Optional[date] = None
    harvest_date: Optional[date] = None
    process_enterprise: Optional[str] = None
    process_date: Optional[date] = None
    warehouse_name: Optional[str] = None
    quality_status: str = "pending"
    test_report_url: Optional[str] = None
    qr_code: Optional[str] = None
    trace_url: Optional[str] = None
    events: List[TraceEventOut] = Field(default_factory=list)
    verified: bool = False
    message: str = ""


TraceBatchDetailOut.model_rebuild()
