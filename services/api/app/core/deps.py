# -*- coding: utf-8 -*-
"""FastAPI 依赖：数据库会话、当前用户、权限校验。"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.context import set_current_user_id
from app.core.database import get_db
from app.core.errors import ErrorCode, Forbidden, Unauthorized
from app.core.permissions import ALL_PERMISSION_CODES
from app.core.scope import is_unrestricted, permission_codes, role_codes
from app.core.security import TokenError, decode_token
from app.models.org import User

bearer_scheme = HTTPBearer(auto_error=False, description="Bearer <access_token>")


def get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise Unauthorized("缺少访问令牌")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise Unauthorized(str(exc)) from exc
    jti = payload.get("jti", "")
    if jti and cache.is_token_blacklisted(jti):
        raise Unauthorized("令牌已失效，请重新登录")
    return payload


def get_current_user(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
) -> User:
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError) as exc:
        raise Unauthorized("令牌主体非法") from exc
    user = db.get(User, user_id)
    if user is None:
        raise Unauthorized("用户不存在或已被删除")
    if user.status != "active":
        raise Unauthorized(
            "账号已被禁用，请联系平台管理员", code=ErrorCode.ACCOUNT_DISABLED
        )
    set_current_user_id(user.id)
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """公开留资允许游客；携带令牌时仍严格校验账号状态。"""
    if credentials is None:
        return None
    payload = get_token_payload(credentials)
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError) as exc:
        raise Unauthorized("令牌主体非法") from exc
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise Unauthorized("账号不可用，请重新登录")
    return user


def current_permissions(user: User) -> set:
    if user.is_superuser:
        return set(ALL_PERMISSION_CODES)
    return set(permission_codes(user))


def require(*codes: str, mode: str = "any") -> Callable[..., User]:
    """权限校验依赖工厂。

    用法：`user: User = Depends(require("product:write"))`
    """

    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.is_superuser:
            return user
        perms = current_permissions(user)
        if not codes:
            return user
        passed = any(code in perms for code in codes) if mode == "any" else all(
            code in perms for code in codes
        )
        if not passed:
            raise Forbidden(f"缺少权限：{' / '.join(codes)}")
        return user

    return _dependency


def require_login(user: User = Depends(get_current_user)) -> User:
    return user


__all__ = [
    "get_db",
    "get_current_user",
    "get_token_payload",
    "require",
    "require_login",
    "current_permissions",
    "is_unrestricted",
    "role_codes",
    "permission_codes",
]
