# -*- coding: utf-8 -*-
"""认证相关 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.response import ORMModel


class LoginIn(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)
    full_name: Optional[str] = Field(None, max_length=64)


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserProfile(ORMModel):
    id: int
    username: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[int] = None
    org_name: Optional[str] = None
    enterprise_id: Optional[int] = None
    enterprise_name: Optional[str] = None
    park_id: Optional[int] = None
    is_superuser: bool = False
    status: str = "active"
    roles: List[str] = Field(default_factory=list)
    role_names: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile
