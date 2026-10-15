# -*- coding: utf-8 -*-
"""模型公共构件：主键类型、金额/数量类型、时间戳混入。

主键统一使用 `BigInteger().with_variant(Integer, "sqlite")`，
使生产 PostgreSQL 使用 BIGINT，而测试用 SQLite 仍可自增。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Integer, Numeric

from app.core.database import Base  # noqa: F401  统一从 core.database 暴露 Base
from app.core.timeutil import now


def bigint():
    """主键/外键列类型。"""
    return BigInteger().with_variant(Integer, "sqlite")


def money():
    """金额：numeric(18,2)。"""
    return Numeric(18, 2)


def qty():
    """数量：numeric(18,3)，单位可为吨/千克/袋。"""
    return Numeric(18, 3)


def rate():
    """比率：numeric(8,4)，如税率 0.0900、费率 0.0050。"""
    return Numeric(8, 4)


class TimestampMixin:
    created_at = Column(DateTime, default=now, nullable=False)
    updated_at = Column(DateTime, default=now, onupdate=now, nullable=False)
