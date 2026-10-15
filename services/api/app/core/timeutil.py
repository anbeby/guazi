# -*- coding: utf-8 -*-
"""时间工具。

系统统一使用 **Asia/Shanghai 本地时间** 的 naive datetime 存储（容器 `TZ=Asia/Shanghai`），
理由：单一区域部署、业务口径按自然日统计、避免前后端时区换算错误。
所有业务代码必须通过 `now()` / `today()` 获取当前时间，禁止直接 `datetime.now()`。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def now() -> datetime:
    """当前本地时间（naive）。"""
    return datetime.now().replace(microsecond=0)


def today() -> date:
    return date.today()


def days_ago(days: int) -> datetime:
    return now() - timedelta(days=days)


def to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value[:10], DATE_FMT).date()
    raise ValueError(f"无法转换为日期: {value!r}")


def parse_date(value) -> date:
    return to_date(value)


def fmt(value, pattern: str = DATETIME_FMT) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime(pattern)
