# -*- coding: utf-8 -*-
"""初始版本：建立自研平台全部业务表（schema gz）。

实现方式说明：
第一阶段共 30+ 张表，手写 DDL 迁移既冗长又易与 ORM 模型漂移。
因此在首个 revision 中直接以 `Base.metadata.create_all()` 建立基线结构，
后续每个迭代再用 `alembic revision --autogenerate` 生成增量脚本。
这样既保证"迁移历史可追溯"，又保证"基线永远与模型一致"。

Revision ID: 0001_initial
Revises:
Create Date: 2025-09-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.core.database import Base
import app.models  # noqa: F401  注册全部模型

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
