# -*- coding: utf-8 -*-
"""企业与商户 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


class EnterpriseIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    code: Optional[str] = Field(None, max_length=64, description="不传则自动生成 ENT-YYYY-XXXX")
    unified_social_credit_code: Optional[str] = Field(None, max_length=32)
    enterprise_type: str = Field("merchant", description="merchant / supplier / buyer / platform")
    legal_person: Optional[str] = Field(None, max_length=64)
    registered_capital: Optional[float] = None
    business_scope: Optional[str] = Field(None, max_length=512)
    profile: Optional[str] = None
    qualifications: List[str] = Field(default_factory=list)
    contact_name: Optional[str] = Field(None, max_length=64)
    contact_phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=128)
    region: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=255)
    park_id: Optional[int] = None
    stall_id: Optional[int] = None
    settle_bank: Optional[str] = None
    settle_account_name: Optional[str] = None
    settle_account_no: Optional[str] = None
    remark: Optional[str] = None
    # 可选：同时创建管理员账号
    create_account: bool = Field(False, description="是否为该企业创建商户管理员账号")
    account_username: Optional[str] = None
    account_password: Optional[str] = None


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = None
    enterprise_type: Optional[str] = None
    legal_person: Optional[str] = None
    registered_capital: Optional[float] = None
    business_scope: Optional[str] = None
    profile: Optional[str] = None
    qualifications: Optional[List[str]] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    park_id: Optional[int] = None
    stall_id: Optional[int] = None
    status: Optional[str] = None
    settle_bank: Optional[str] = None
    settle_account_name: Optional[str] = None
    settle_account_no: Optional[str] = None
    remark: Optional[str] = None


class EnterpriseAuditIn(BaseModel):
    approved: bool = True
    remark: Optional[str] = Field(None, max_length=255)


class EnterpriseImageIn(BaseModel):
    file_key: str = Field(..., min_length=1, max_length=64)


class EnterpriseOut(ORMModel):
    id: int
    code: str
    name: str
    image_url: Optional[str] = None
    unified_social_credit_code: Optional[str] = None
    enterprise_type: str
    legal_person: Optional[str] = None
    registered_capital: float = 0
    business_scope: Optional[str] = None
    profile: Optional[str] = None
    qualifications: List[str] = Field(default_factory=list)
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    org_id: Optional[int] = None
    park_id: Optional[int] = None
    park_name: Optional[str] = None
    stall_id: Optional[int] = None
    stall_code: Optional[str] = None
    audit_status: str = "pending"
    audit_remark: Optional[str] = None
    audited_at: Optional[datetime] = None
    status: str = "active"
    settle_bank: Optional[str] = None
    settle_account_name: Optional[str] = None
    settle_account_no: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


class EnterpriseStatsOut(BaseModel):
    enterprise_id: int
    enterprise_name: str
    product_count: int = 0
    published_product_count: int = 0
    inventory_quantity: float = 0
    inventory_value: float = 0
    sale_order_count: int = 0
    sale_order_amount: float = 0
    purchase_order_count: int = 0
    purchase_order_amount: float = 0
    pending_settlement_amount: float = 0
    as_supplier_inquiry_count: int = 0


class EnterpriseSimpleOut(ORMModel):
    id: int
    code: str
    name: str
    enterprise_type: str
    audit_status: str


class EnterpriseOptionOut(BaseModel):
    items: List[EnterpriseSimpleOut] = Field(default_factory=list)
