# -*- coding: utf-8 -*-
"""业务单号生成（数据库序列表 + 行锁）。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import lock_query
from app.core.errors import Conflict
from app.core.timeutil import now
from app.models.org import SysSequence


def next_no(db: Session, name: str, prefix: str, width: int = 4) -> str:
    """生成单号：`{prefix}{序号补零}`，例如 GZ-INQ-2025-0001。

    并发安全：PostgreSQL 下使用 `SELECT ... FOR UPDATE`，缺失序列行时用保存点重试。
    """
    if not prefix.endswith("-"):
        prefix = prefix + "-"
    seq: Optional[SysSequence] = lock_query(
        db.query(SysSequence).filter(SysSequence.name == name), db
    ).first()
    if seq is None:
        try:
            with db.begin_nested():
                seq = SysSequence(name=name, prefix=prefix, current_value=0)
                db.add(seq)
                db.flush()
        except IntegrityError:
            seq = lock_query(
                db.query(SysSequence).filter(SysSequence.name == name), db
            ).first()
            if seq is None:
                raise Conflict(f"单号序列初始化失败：{name}")
    seq.prefix = prefix
    seq.current_value = int(seq.current_value or 0) + 1
    seq.updated_at = now()
    db.flush()
    return f"{prefix}{seq.current_value:0{width}d}"


def peek_no(db: Session, name: str, prefix: str, width: int = 4) -> str:
    """只读预览下一个单号（不消耗序号）。"""
    if not prefix.endswith("-"):
        prefix = prefix + "-"
    seq = db.query(SysSequence).filter(SysSequence.name == name).first()
    current = int(seq.current_value) if seq else 0
    return f"{prefix}{current + 1:0{width}d}"


def year_prefix(prefix: str, year: Optional[int] = None) -> str:
    from datetime import date

    return f"{prefix}-{year or date.today().year}"
