# -*- coding: utf-8 -*-
"""园区、区域、档口、园区合同 Schema。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


class ParkIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    region: Optional[str] = None
    address: Optional[str] = None
    area_total: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"
    description: Optional[str] = None


class ParkUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    area_total: Optional[float] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


class ParkOut(ORMModel):
    id: int
    code: str
    name: str
    region: Optional[str] = None
    address: Optional[str] = None
    area_total: float = 0
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"
    description: Optional[str] = None
    zone_count: int = 0
    stall_count: int = 0
    stall_rented: int = 0
    enterprise_count: int = 0
    created_at: Optional[datetime] = None


class ZoneIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    zone_type: str = Field("trade", description="trade / processing / logistics / service")
    area: Optional[float] = None
    sort: int = 0
    status: str = "active"


class ZoneOut(ORMModel):
    id: int
    park_id: int
    code: str
    name: str
    zone_type: str
    area: float = 0
    sort: int = 0
    status: str = "active"
    stall_count: int = 0


class StallIn(BaseModel):
    park_id: int
    zone_id: Optional[int] = None
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    area: Optional[float] = None
    monthly_fee: Optional[float] = None
    status: str = "free"
    remark: Optional[str] = None


class StallUpdate(BaseModel):
    name: Optional[str] = None
    zone_id: Optional[int] = None
    area: Optional[float] = None
    monthly_fee: Optional[float] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class StallAssignIn(BaseModel):
    enterprise_id: Optional[int] = Field(None, description="传 None 表示退租")
    remark: Optional[str] = None


class StallOut(ORMModel):
    id: int
    park_id: int
    park_name: Optional[str] = None
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    code: str
    name: str
    area: float = 0
    monthly_fee: float = 0
    status: str = "free"
    enterprise_id: Optional[int] = None
    enterprise_name: Optional[str] = None
    remark: Optional[str] = None


class ParkContractIn(BaseModel):
    park_id: int
    stall_id: Optional[int] = None
    enterprise_id: int
    start_date: date
    end_date: date
    rent_amount: Optional[float] = 0
    deposit_amount: Optional[float] = 0
    fee_cycle: str = Field("year", description="month / quarter / year")
    file_url: Optional[str] = None
    remark: Optional[str] = None


class ParkContractUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rent_amount: Optional[float] = None
    deposit_amount: Optional[float] = None
    fee_cycle: Optional[str] = None
    file_url: Optional[str] = None
    remark: Optional[str] = None


class ParkContractOut(ORMModel):
    id: int
    contract_no: str
    park_id: int
    park_name: Optional[str] = None
    stall_id: Optional[int] = None
    stall_code: Optional[str] = None
    enterprise_id: int
    enterprise_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rent_amount: float = 0
    deposit_amount: float = 0
    fee_cycle: str = "year"
    status: str = "draft"
    signed_at: Optional[datetime] = None
    file_url: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
