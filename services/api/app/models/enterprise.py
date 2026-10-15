# -*- coding: utf-8 -*-
"""主体与园区域：企业/商户档案、园区、区域、档口、园区合同。"""
from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base
from app.models.base import TimestampMixin, bigint, money


class Park(Base, TimestampMixin):
    """交易园区。"""

    __tablename__ = "park"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    region = Column(String(64))
    address = Column(String(255))
    area_total = Column(money())
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    status = Column(String(16), nullable=False, default="active", index=True)
    description = Column(Text)
    operator_org_id = Column(bigint(), index=True)


class ParkZone(Base, TimestampMixin):
    """园区区域：交易区 / 加工区 / 物流区 / 服务区。"""

    __tablename__ = "park_zone"

    id = Column(bigint(), primary_key=True)
    park_id = Column(bigint(), ForeignKey("park.id"), nullable=False, index=True)
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    zone_type = Column(String(16), nullable=False, default="trade")
    area = Column(money())
    sort = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="active")


class Stall(Base, TimestampMixin):
    """园区档口（空间资源）。"""

    __tablename__ = "stall"

    id = Column(bigint(), primary_key=True)
    park_id = Column(bigint(), ForeignKey("park.id"), nullable=False, index=True)
    zone_id = Column(bigint(), ForeignKey("park_zone.id"), index=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    area = Column(money())
    monthly_fee = Column(money(), default=0)
    status = Column(String(16), nullable=False, default="free", index=True)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), index=True)
    remark = Column(String(255))


class ParkContract(Base, TimestampMixin):
    """园区入驻合同（档口租赁）。"""

    __tablename__ = "park_contract"

    id = Column(bigint(), primary_key=True)
    contract_no = Column(String(64), nullable=False, unique=True, index=True)
    park_id = Column(bigint(), ForeignKey("park.id"), nullable=False, index=True)
    stall_id = Column(bigint(), ForeignKey("stall.id"), index=True)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    rent_amount = Column(money(), default=0)
    deposit_amount = Column(money(), default=0)
    fee_cycle = Column(String(16), nullable=False, default="year")
    status = Column(String(16), nullable=False, default="draft", index=True)
    signed_at = Column(DateTime)
    file_url = Column(String(255))
    remark = Column(String(255))


class Enterprise(Base, TimestampMixin):
    """企业/商户档案（平台侧主数据，与 Odoo res.partner 映射）。"""

    __tablename__ = "enterprise"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    unified_social_credit_code = Column(String(32), unique=True, index=True)
    enterprise_type = Column(String(16), nullable=False, default="merchant", index=True)
    legal_person = Column(String(64))
    registered_capital = Column(money(), default=0)
    business_scope = Column(String(512))
    profile = Column(Text)
    qualifications = Column(JSON, default=list)
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    email = Column(String(128))
    region = Column(String(64))
    address = Column(String(255))
    org_id = Column(bigint(), ForeignKey("org_unit.id"), index=True)
    park_id = Column(bigint(), ForeignKey("park.id"), index=True)
    # 循环外键规避：档口侧持有 enterprise_id 外键，此处仅存引用
    stall_id = Column(bigint(), index=True)
    audit_status = Column(String(16), nullable=False, default="pending", index=True)
    audit_remark = Column(String(255))
    audited_at = Column(DateTime)
    audited_by = Column(bigint())
    status = Column(String(16), nullable=False, default="active", index=True)
    settle_bank = Column(String(128))
    settle_account_name = Column(String(128))
    settle_account_no = Column(String(64))
    odoo_partner_id = Column(bigint())
    remark = Column(String(255))
