# -*- coding: utf-8 -*-
"""组织与权限域：组织单元、用户、角色、权限、操作日志、编码序列。"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timeutil import now
from app.models.base import TimestampMixin, bigint

user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", bigint(), ForeignKey("sys_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", bigint(), ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
)

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", bigint(), ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", bigint(), ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
)


class OrgUnit(Base, TimestampMixin):
    """组织单元树：平台 → 园区 → 企业 → 商户。"""

    __tablename__ = "org_unit"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=False)
    unit_type = Column(String(16), nullable=False, default="enterprise", index=True)
    parent_id = Column(bigint(), ForeignKey("org_unit.id"))
    park_id = Column(bigint(), index=True)
    region = Column(String(64))
    address = Column(String(255))
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    status = Column(String(16), nullable=False, default="active", index=True)
    sort = Column(Integer, nullable=False, default=0)
    remark = Column(String(255))

    parent = relationship("OrgUnit", remote_side=[id], backref="children")


class User(Base, TimestampMixin):
    """平台用户（互联网侧商户/采购商账号与平台内部账号统一管理）。"""

    __tablename__ = "sys_user"

    id = Column(bigint(), primary_key=True)
    username = Column(String(64), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(64))
    phone = Column(String(32), index=True)
    email = Column(String(128))
    org_id = Column(bigint(), ForeignKey("org_unit.id"), index=True)
    enterprise_id = Column(bigint(), index=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    status = Column(String(16), nullable=False, default="active", index=True)
    last_login_at = Column(DateTime)
    remark = Column(String(255))

    roles = relationship("Role", secondary=user_role, lazy="selectin", backref="users")


class Role(Base, TimestampMixin):
    __tablename__ = "role"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(255))
    is_system = Column(Boolean, nullable=False, default=False)

    permissions = relationship("Permission", secondary=role_permission, lazy="selectin")


class Permission(Base, TimestampMixin):
    __tablename__ = "permission"

    id = Column(bigint(), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(64), nullable=False)
    module = Column(String(32), nullable=False, index=True)
    description = Column(String(255))


class SysSequence(Base):
    """业务单号序列（询价单号、订单号、结算单号等）。"""

    __tablename__ = "sys_sequence"

    name = Column(String(64), primary_key=True)
    prefix = Column(String(32), nullable=False)
    current_value = Column(bigint(), nullable=False, default=0)
    updated_at = Column(DateTime, default=now, onupdate=now, nullable=False)


class OperationLog(Base):
    """操作审计日志。"""

    __tablename__ = "operation_log"

    id = Column(bigint(), primary_key=True)
    user_id = Column(bigint(), index=True)
    username = Column(String(64))
    enterprise_id = Column(bigint(), index=True)
    module = Column(String(32), index=True)
    action = Column(String(64))
    method = Column(String(8))
    path = Column(String(255))
    target_type = Column(String(64))
    target_id = Column(String(64))
    ip = Column(String(64))
    status_code = Column(Integer)
    duration_ms = Column(Integer)
    detail = Column(Text)
    created_at = Column(DateTime, default=now, nullable=False)
