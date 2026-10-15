# -*- coding: utf-8 -*-
"""用户、角色、权限、组织 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


# ------------------------------------------------------------------ 用户
class UserIn(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="不传则使用默认初始密码")
    full_name: Optional[str] = Field(None, max_length=64)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=128)
    org_id: Optional[int] = None
    enterprise_id: Optional[int] = None
    status: str = "active"
    role_ids: List[int] = Field(default_factory=list)
    remark: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[int] = None
    enterprise_id: Optional[int] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class UserOut(ORMModel):
    id: int
    username: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[int] = None
    org_name: Optional[str] = None
    enterprise_id: Optional[int] = None
    enterprise_name: Optional[str] = None
    is_superuser: bool = False
    status: str = "active"
    remark: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    role_ids: List[int] = Field(default_factory=list)
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AssignRolesIn(BaseModel):
    role_ids: List[int] = Field(default_factory=list)


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


# ------------------------------------------------------------------ 角色与权限
class RoleIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RoleOut(ORMModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    user_count: int = 0
    permission_codes: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class PermissionOut(ORMModel):
    id: int
    code: str
    name: str
    module: str
    description: Optional[str] = None


class PermissionGroupOut(BaseModel):
    module: str
    module_name: str
    permissions: List[PermissionOut] = Field(default_factory=list)


class AssignPermissionsIn(BaseModel):
    permission_ids: List[int] = Field(default_factory=list)


# ------------------------------------------------------------------ 组织
class OrgUnitIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    unit_type: str = Field("enterprise", description="platform / park / enterprise")
    parent_id: Optional[int] = None
    park_id: Optional[int] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"
    sort: int = 0
    remark: Optional[str] = None


class OrgUnitUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: Optional[str] = None
    sort: Optional[int] = None
    remark: Optional[str] = None


class OrgUnitOut(ORMModel):
    id: int
    code: str
    name: str
    unit_type: str
    parent_id: Optional[int] = None
    park_id: Optional[int] = None
    region: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"
    sort: int = 0
    children: List["OrgUnitOut"] = Field(default_factory=list)


OrgUnitOut.model_rebuild()
