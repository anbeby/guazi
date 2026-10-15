# -*- coding: utf-8 -*-
"""系统与集成域：文件、集成出站事件、主键映射。"""
from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.core.database import Base
from app.core.timeutil import now
from app.models.base import bigint


class SysFile(Base):
    """文件元数据（MinIO 对象或本地磁盘）。"""

    __tablename__ = "sys_file"

    id = Column(bigint(), primary_key=True)
    file_key = Column(String(64), nullable=False, unique=True, index=True)
    bucket = Column(String(64), nullable=False)
    original_name = Column(String(255), nullable=False)
    object_name = Column(String(512), nullable=False)
    content_type = Column(String(128))
    size = Column(bigint(), nullable=False, default=0)
    biz_type = Column(String(32), index=True)
    biz_id = Column(bigint(), index=True)
    uploader_id = Column(bigint())
    storage = Column(String(16), nullable=False, default="minio")
    url = Column(String(512))
    created_at = Column(DateTime, default=now, nullable=False)


class SyncOutbox(Base):
    """集成出站事件表（事务性 outbox，保证与业务同事务写入）。"""

    __tablename__ = "sync_outbox"

    id = Column(bigint(), primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    aggregate_type = Column(String(64), nullable=False, index=True)
    aggregate_id = Column(String(64), index=True)
    idempotent_key = Column(String(128), index=True)
    payload = Column(JSON)
    status = Column(String(16), nullable=False, default="pending", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(DateTime)
    last_error = Column(Text)
    created_at = Column(DateTime, default=now, nullable=False)
    processed_at = Column(DateTime)


class IntegrationIdMap(Base):
    """两侧主键映射（自研实体 ↔ Odoo 记录）。"""

    __tablename__ = "integration_id_map"
    __table_args__ = (
        UniqueConstraint("local_type", "local_id", "remote_model", name="uq_idmap_local_remote"),
    )

    id = Column(bigint(), primary_key=True)
    local_type = Column(String(64), nullable=False, index=True)
    local_id = Column(String(64), nullable=False, index=True)
    remote_model = Column(String(64), nullable=False)
    remote_id = Column(String(64))
    updated_at = Column(DateTime, default=now, onupdate=now, nullable=False)


class SyncLog(Base):
    """集成同步日志。"""

    __tablename__ = "integration_sync_log"

    id = Column(bigint(), primary_key=True)
    direction = Column(String(16), nullable=False, default="push")
    event_type = Column(String(64), index=True)
    aggregate_id = Column(String(64), index=True)
    request = Column(Text)
    response = Column(Text)
    success = Column(Integer, nullable=False, default=0)
    error = Column(Text)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=now, nullable=False)
