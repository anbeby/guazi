# -*- coding: utf-8 -*-
"""B2B 交易域：询价单、报价单、订单与明细、合同。"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, bigint, money, qty, rate


class Inquiry(Base, TimestampMixin):
    """询价单（采购商发起）。"""

    __tablename__ = "inquiry"

    id = Column(bigint(), primary_key=True)
    inquiry_no = Column(String(64), nullable=False, unique=True, index=True)
    buyer_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    supplier_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    category_id = Column(bigint(), index=True)
    quantity = Column(qty(), nullable=False, default=0)
    unit = Column(String(16), nullable=False, default="ton")
    expect_price = Column(money(), default=0)
    expect_delivery_date = Column(Date)
    delivery_address = Column(String(255))
    remark = Column(String(255))
    status = Column(String(16), nullable=False, default="draft", index=True)
    quoted_count = Column(bigint(), nullable=False, default=0)
    created_by = Column(bigint())
    closed_at = Column(DateTime)

    quotations = relationship(
        "Quotation", back_populates="inquiry", cascade="all, delete-orphan", lazy="selectin"
    )


class Quotation(Base, TimestampMixin):
    """报价单（供应商针对询价提交）。"""

    __tablename__ = "quotation"

    id = Column(bigint(), primary_key=True)
    quotation_no = Column(String(64), nullable=False, unique=True, index=True)
    inquiry_id = Column(bigint(), ForeignKey("inquiry.id"), nullable=False, index=True)
    supplier_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    quantity = Column(qty(), nullable=False, default=0)
    unit = Column(String(16), nullable=False, default="ton")
    unit_price = Column(money(), nullable=False, default=0)
    amount = Column(money(), nullable=False, default=0)
    tax_rate = Column(rate(), nullable=False, default=0)
    valid_until = Column(Date)
    delivery_date = Column(Date)
    payment_terms = Column(String(128))
    remark = Column(String(255))
    status = Column(String(16), nullable=False, default="submitted", index=True)
    created_by = Column(bigint())

    inquiry = relationship("Inquiry", back_populates="quotations")


class TradeOrder(Base, TimestampMixin):
    """平台订单。order_type=sales 表示卖方视角销售单，purchase 表示买方视角采购单。"""

    __tablename__ = "trade_order"

    id = Column(bigint(), primary_key=True)
    order_no = Column(String(64), nullable=False, unique=True, index=True)
    order_type = Column(String(16), nullable=False, default="sales", index=True)
    inquiry_id = Column(bigint(), ForeignKey("inquiry.id"), index=True)
    quotation_id = Column(bigint(), ForeignKey("quotation.id"), index=True)
    buyer_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    supplier_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    amount = Column(money(), nullable=False, default=0)
    tax_amount = Column(money(), nullable=False, default=0)
    total_amount = Column(money(), nullable=False, default=0)
    currency = Column(String(8), nullable=False, default="CNY")
    delivery_date = Column(Date)
    delivery_address = Column(String(255))
    delivery_method = Column(String(32), default="self_pickup")
    logistics_company = Column(String(64))
    logistics_no = Column(String(64))
    # 循环外键规避：合同侧持有 order_id，此处仅存引用
    contract_id = Column(bigint(), index=True)
    stock_deducted = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="draft", index=True)
    remark = Column(String(255))
    created_by = Column(bigint())
    confirmed_at = Column(DateTime)
    delivered_at = Column(DateTime)
    completed_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    cancel_reason = Column(String(255))
    odoo_order_id = Column(bigint())

    items = relationship(
        "TradeOrderItem", back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class TradeOrderItem(Base):
    """订单明细。"""

    __tablename__ = "trade_order_item"

    id = Column(bigint(), primary_key=True)
    order_id = Column(bigint(), ForeignKey("trade_order.id"), nullable=False, index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    product_name = Column(String(160))
    spec = Column(String(64))
    grade = Column(String(32))
    unit = Column(String(16), nullable=False, default="ton")
    warehouse_id = Column(bigint(), index=True)
    location_id = Column(bigint())
    batch_no = Column(String(64), default="DEFAULT")
    quantity = Column(qty(), nullable=False, default=0)
    delivered_quantity = Column(qty(), nullable=False, default=0)
    unit_price = Column(money(), nullable=False, default=0)
    amount = Column(money(), nullable=False, default=0)
    tax_rate = Column(rate(), nullable=False, default=0)

    order = relationship("TradeOrder", back_populates="items")


class Contract(Base, TimestampMixin):
    """平台合同（买卖双方在线签署；可由订单生成）。"""

    __tablename__ = "contract"

    id = Column(bigint(), primary_key=True)
    contract_no = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(160), nullable=False)
    order_id = Column(bigint(), ForeignKey("trade_order.id"), index=True)
    buyer_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    supplier_enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    park_id = Column(bigint(), ForeignKey("park.id"), index=True)
    amount = Column(money(), nullable=False, default=0)
    sign_date = Column(Date)
    start_date = Column(Date)
    end_date = Column(Date)
    file_url = Column(String(255))
    terms = Column(Text)
    status = Column(String(16), nullable=False, default="draft", index=True)
    signed_by_buyer = Column(Boolean, nullable=False, default=False)
    signed_by_supplier = Column(Boolean, nullable=False, default=False)
    buyer_signed_at = Column(DateTime)
    supplier_signed_at = Column(DateTime)
    remark = Column(String(255))
