# -*- coding: utf-8 -*-
"""V1.1 供应属性、企业介绍、采购需求与撮合记录。

0001 基线使用当前 ORM metadata.create_all，因此这里检查列/表是否已存在，
同时支持旧库升级和从空库运行完整迁移链。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.core.database import Base
import app.models  # noqa: F401

revision = "0002_marketplace_matching"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    product_columns = {c["name"] for c in inspector.get_columns("product")}
    additions = [
        sa.Column("supply_quantity", sa.Numeric(18, 3), server_default="0"),
        sa.Column("supply_period", sa.String(64)),
        sa.Column("pricing_mode", sa.String(16), nullable=False, server_default="listed"),
        sa.Column("supply_status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("allow_inquiry", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_bulk_purchase", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]
    for column in additions:
        if column.name not in product_columns:
            op.add_column("product", column)
    enterprise_columns = {c["name"] for c in inspector.get_columns("enterprise")}
    if "profile" not in enterprise_columns:
        op.add_column("enterprise", sa.Column("profile", sa.Text()))
    if "qualifications" not in enterprise_columns:
        op.add_column("enterprise", sa.Column("qualifications", sa.JSON()))
    if not any(i["name"] == "ix_product_supply_status" for i in sa.inspect(bind).get_indexes("product")):
        op.create_index("ix_product_supply_status", "product", ["supply_status"])
    for name in ("purchase_requirement", "match_case", "match_followup"):
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for name in ("match_followup", "match_case", "purchase_requirement"):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
    inspector = sa.inspect(bind)
    if any(i["name"] == "ix_product_supply_status" for i in inspector.get_indexes("product")):
        op.drop_index("ix_product_supply_status", table_name="product")
    for name in ("allow_bulk_purchase", "allow_inquiry", "supply_status", "pricing_mode", "supply_period", "supply_quantity"):
        if name in {c["name"] for c in sa.inspect(bind).get_columns("product")}:
            op.drop_column("product", name)
    for name in ("qualifications", "profile"):
        if name in {c["name"] for c in sa.inspect(bind).get_columns("enterprise")}:
            op.drop_column("enterprise", name)
