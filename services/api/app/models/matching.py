# -*- coding: utf-8 -*-
"""V1.1 采购需求与人工撮合；与既有询价、订单链路相互独立。"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timeutil import now
from app.models.base import TimestampMixin, bigint, qty


class PurchaseRequirement(Base, TimestampMixin):
    __tablename__ = "purchase_requirement"

    id = Column(bigint(), primary_key=True)
    title = Column(String(160), nullable=False, index=True)
    product_name = Column(String(160), nullable=False)
    category_id = Column(bigint(), ForeignKey("category.id"), index=True)
    quantity = Column(qty(), nullable=False)
    unit = Column(String(16), nullable=False, default="ton")
    requirements = Column(Text)
    purchase_region = Column(String(128))
    contact_name = Column(String(64), nullable=False)
    contact_phone = Column(String(32), nullable=False)
    buyer_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="open", index=True)
    created_by = Column(bigint(), ForeignKey("sys_user.id"), nullable=False)


class MatchCase(Base, TimestampMixin):
    __tablename__ = "match_case"

    id = Column(bigint(), primary_key=True)
    requirement_id = Column(bigint(), ForeignKey("purchase_requirement.id"), nullable=False, index=True)
    supplier_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    operator_id = Column(bigint(), ForeignKey("sys_user.id"))
    source = Column(String(16), nullable=False, default="manual")
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    status = Column(String(16), nullable=False, default="pending", index=True)
    result = Column(Text)
    closed_at = Column(DateTime)

    followups = relationship("MatchFollowup", back_populates="case", order_by="MatchFollowup.created_at")


class MatchFollowup(Base):
    __tablename__ = "match_followup"

    id = Column(bigint(), primary_key=True)
    case_id = Column(bigint(), ForeignKey("match_case.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_by = Column(bigint(), ForeignKey("sys_user.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)

    case = relationship("MatchCase", back_populates="followups")


class MatchLead(Base, TimestampMixin):
    """游客及注册用户提交的轻量合作线索，不改变企业询价单流程。"""

    __tablename__ = "match_lead"

    id = Column(bigint(), primary_key=True)
    user_id = Column(bigint(), ForeignKey("sys_user.id"), index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), index=True)
    intent_product = Column(String(160), nullable=False)
    quantity = Column(qty())
    contact_name = Column(String(64), nullable=False)
    contact_phone = Column(String(32), nullable=False)
    need_content = Column(Text, nullable=False)
    supplier_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), index=True)
    operator_id = Column(bigint(), ForeignKey("sys_user.id"))
    status = Column(String(16), nullable=False, default="new", index=True)
    result = Column(Text)

    followups = relationship("LeadFollowup", back_populates="lead", order_by="LeadFollowup.created_at")


class LeadFollowup(Base):
    __tablename__ = "lead_followup"

    id = Column(bigint(), primary_key=True)
    lead_id = Column(bigint(), ForeignKey("match_lead.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_by = Column(bigint(), ForeignKey("sys_user.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=now)

    lead = relationship("MatchLead", back_populates="followups")


class ProductFavorite(Base):
    __tablename__ = "product_favorite"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_product_favorite_user_product"),)

    id = Column(bigint(), primary_key=True)
    user_id = Column(bigint(), ForeignKey("sys_user.id"), nullable=False, index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=now)
