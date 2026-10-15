# -*- coding: utf-8 -*-
"""食品安全溯源域：批次与链路事件。

链路：种植基地 → 加工企业 → 仓储 → 交易 → 销售。
"""
from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timeutil import now
from app.models.base import TimestampMixin, bigint, qty


class TraceBatch(Base, TimestampMixin):
    """产品批次（一物一码）。"""

    __tablename__ = "trace_batch"

    id = Column(bigint(), primary_key=True)
    batch_no = Column(String(64), nullable=False, unique=True, index=True)
    qr_code = Column(String(128), unique=True, index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    quantity = Column(qty(), default=0)
    origin_base = Column(String(160))
    origin_region = Column(String(64))
    plant_date = Column(Date)
    harvest_date = Column(Date)
    process_enterprise = Column(String(160))
    process_date = Column(Date)
    warehouse_id = Column(bigint(), ForeignKey("warehouse.id"), index=True)
    test_report_url = Column(String(255))
    quality_status = Column(String(16), nullable=False, default="pending")
    status = Column(String(16), nullable=False, default="active", index=True)
    remark = Column(String(255))

    events = relationship(
        "TraceEvent", back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )


class TraceEvent(Base):
    """溯源链路事件。"""

    __tablename__ = "trace_event"

    id = Column(bigint(), primary_key=True)
    batch_id = Column(bigint(), ForeignKey("trace_batch.id"), nullable=False, index=True)
    stage = Column(String(16), nullable=False, index=True)
    title = Column(String(128), nullable=False)
    description = Column(Text)
    occurred_at = Column(DateTime)
    location = Column(String(160))
    operator = Column(String(64))
    evidence_url = Column(String(255))
    created_at = Column(DateTime, default=now, nullable=False)

    batch = relationship("TraceBatch", back_populates="events")
