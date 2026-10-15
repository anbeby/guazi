# -*- coding: utf-8 -*-
"""商品与库存域：分类、商品、仓库、库位、库存、库存流水。"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timeutil import now
from app.models.base import TimestampMixin, bigint, money, qty


class Category(Base, TimestampMixin):
    """商品分类（瓜子油料标准分类树）。"""

    __tablename__ = "category"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    parent_id = Column(bigint(), ForeignKey("category.id"), index=True)
    level = Column(Integer, nullable=False, default=1)
    sort = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="active")
    description = Column(String(255))

    parent = relationship("Category", remote_side=[id], backref="children")


class Product(Base, TimestampMixin):
    """商品（商户/供应商对外发布的瓜子油料货品）。"""

    __tablename__ = "product"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    category_id = Column(bigint(), ForeignKey("category.id"), nullable=False, index=True)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    spec = Column(String(64))
    grade = Column(String(32), index=True)
    origin = Column(String(64), index=True)
    harvest_year = Column(String(8), index=True)
    package = Column(String(64))
    unit = Column(String(16), nullable=False, default="ton")
    price = Column(money(), default=0)
    currency = Column(String(8), nullable=False, default="CNY")
    min_order_qty = Column(qty(), default=0)
    stock_warn_qty = Column(qty(), default=0)
    supply_quantity = Column(qty(), default=0)
    supply_period = Column(String(64))
    pricing_mode = Column(String(16), nullable=False, default="listed")
    supply_status = Column(String(16), nullable=False, default="active", index=True)
    allow_inquiry = Column(Boolean, nullable=False, default=True)
    allow_bulk_purchase = Column(Boolean, nullable=False, default=True)
    main_image = Column(String(255))
    images = Column(JSON, default=list)
    test_report_url = Column(String(255))
    quality_status = Column(String(16), nullable=False, default="pending", index=True)
    trace_enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String(16), nullable=False, default="draft", index=True)
    audit_status = Column(String(16), nullable=False, default="pending", index=True)
    audit_remark = Column(String(255))
    description = Column(Text)
    created_by = Column(bigint())
    odoo_template_id = Column(bigint())


class Warehouse(Base, TimestampMixin):
    """仓库。"""

    __tablename__ = "warehouse"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    enterprise_id = Column(bigint(), ForeignKey("enterprise.id"), nullable=False, index=True)
    park_id = Column(bigint(), ForeignKey("park.id"), index=True)
    address = Column(String(255))
    warehouse_type = Column(String(16), nullable=False, default="own")
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    capacity = Column(qty(), default=0)
    status = Column(String(16), nullable=False, default="active")
    remark = Column(String(255))


class StorageLocation(Base, TimestampMixin):
    """库位。"""

    __tablename__ = "storage_location"
    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uq_location_wh_code"),)

    id = Column(bigint(), primary_key=True)
    warehouse_id = Column(bigint(), ForeignKey("warehouse.id"), nullable=False, index=True)
    code = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    zone = Column(String(32))
    capacity = Column(qty(), default=0)
    status = Column(String(16), nullable=False, default="active")
    remark = Column(String(255))


class Inventory(Base, TimestampMixin):
    """库存（按 商品 + 仓库 + 库位 + 批次 维度）。

    quantity 为账面数量，locked_quantity 为交易预占数量，可用量 = quantity - locked_quantity。
    生产环境下账面数量的唯一写入方是自研库存服务（并与 Odoo stock.quant 对账）。
    """

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "warehouse_id", "location_id", "batch_no", name="uq_inventory_dim"
        ),
    )

    id = Column(bigint(), primary_key=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    warehouse_id = Column(bigint(), ForeignKey("warehouse.id"), nullable=False, index=True)
    location_id = Column(bigint(), ForeignKey("storage_location.id"), index=True)
    batch_no = Column(String(64), nullable=False, default="DEFAULT", index=True)
    quantity = Column(qty(), nullable=False, default=0)
    locked_quantity = Column(qty(), nullable=False, default=0)
    unit_cost = Column(money(), default=0)
    production_date = Column(Date)
    expiry_date = Column(Date)
    quality_status = Column(String(16), nullable=False, default="pending")
    enterprise_id = Column(bigint(), index=True)


class StockMove(Base):
    """库存流水（入库/出库/调拨/调整/盘点）。"""

    __tablename__ = "stock_move"

    id = Column(bigint(), primary_key=True)
    move_no = Column(String(64), nullable=False, unique=True, index=True)
    move_type = Column(String(16), nullable=False, index=True)
    product_id = Column(bigint(), ForeignKey("product.id"), nullable=False, index=True)
    warehouse_id = Column(bigint(), ForeignKey("warehouse.id"), index=True)
    location_id = Column(bigint(), ForeignKey("storage_location.id"), index=True)
    to_warehouse_id = Column(bigint())
    to_location_id = Column(bigint())
    quantity = Column(qty(), nullable=False, default=0)
    unit_cost = Column(money(), default=0)
    batch_no = Column(String(64), index=True)
    ref_type = Column(String(32), index=True)
    ref_id = Column(bigint())
    ref_no = Column(String(64), index=True)
    operator_id = Column(bigint())
    operator_name = Column(String(64))
    remark = Column(String(255))
    created_at = Column(DateTime, default=now, nullable=False)
