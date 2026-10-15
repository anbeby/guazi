# -*- coding: utf-8 -*-
"""采购需求和人工撮合输入。"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class RequirementIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    product_name: str = Field(..., min_length=2, max_length=160)
    category_id: Optional[int] = None
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field("ton", max_length=16)
    requirements: Optional[str] = Field(None, max_length=2000)
    purchase_region: Optional[str] = Field(None, max_length=128)
    contact_name: str = Field(..., min_length=2, max_length=64)
    contact_phone: str = Field(..., min_length=5, max_length=32)


class RequirementStatusUpdate(BaseModel):
    status: str


class MatchIn(BaseModel):
    supplier_enterprise_id: int
    contact_name: Optional[str] = Field(None, max_length=64)
    contact_phone: Optional[str] = Field(None, max_length=32)


class MatchUpdate(BaseModel):
    status: str
    result: Optional[str] = Field(None, max_length=2000)
    contact_name: Optional[str] = Field(None, max_length=64)
    contact_phone: Optional[str] = Field(None, max_length=32)


class FollowupIn(BaseModel):
    note: str = Field(..., min_length=2, max_length=2000)
