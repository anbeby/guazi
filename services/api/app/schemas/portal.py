# -*- coding: utf-8 -*-
"""开放留资、普通用户与企业自助资料。"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LeadIn(BaseModel):
    contact_name: str = Field(..., min_length=2, max_length=64)
    contact_phone: str = Field(..., min_length=7, max_length=32)
    need_content: str = Field(..., min_length=5, max_length=2000)
    product_id: Optional[int] = None
    enterprise_id: Optional[int] = None
    intent_product: Optional[str] = Field(None, max_length=160)
    quantity: Optional[Decimal] = Field(None, gt=0)


class LeadUpdate(BaseModel):
    status: str
    supplier_enterprise_id: Optional[int] = None
    result: Optional[str] = Field(None, max_length=2000)


class LeadFollowupIn(BaseModel):
    note: str = Field(..., min_length=2, max_length=2000)


class EnterpriseApplyIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    enterprise_type: str = "supplier"
    profile: Optional[str] = Field(None, max_length=2000)
    business_scope: Optional[str] = Field(None, max_length=512)
    contact_name: str = Field(..., min_length=2, max_length=64)
    contact_phone: str = Field(..., min_length=7, max_length=32)
    region: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=255)
    qualifications: list[str] = Field(default_factory=list, max_length=12)


class EnterpriseSelfUpdate(BaseModel):
    profile: Optional[str] = Field(None, max_length=2000)
    business_scope: Optional[str] = Field(None, max_length=512)
    contact_name: Optional[str] = Field(None, max_length=64)
    contact_phone: Optional[str] = Field(None, max_length=32)
    region: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=255)
    qualifications: Optional[list[str]] = Field(None, max_length=12)


class EnterpriseSelfImageIn(BaseModel):
    file_key: str = Field(..., min_length=1, max_length=64)
