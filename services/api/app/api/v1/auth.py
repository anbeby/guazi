# -*- coding: utf-8 -*-
"""认证接口：登录、刷新、登出、当前用户、修改密码。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.serializers import Lookups
from app.core.cache import cache
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_token_payload
from app.core.errors import BadRequest, Conflict, ErrorCode, Unauthorized
from app.core.response import ApiResponse, ok
from app.core.scope import permission_codes, role_codes
from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
    password_strength_error,
    token_remaining_seconds,
    verify_password,
)
from app.core.timeutil import now
from app.models.org import Role, User
from app.schemas.auth import ChangePasswordIn, LoginIn, RefreshIn, RegisterIn, TokenOut, UserProfile

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse[TokenOut], summary="普通用户注册")
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict:
    username = payload.username.strip()
    if len(username) < 3 or any(char.isspace() for char in username):
        raise BadRequest("用户名需至少 3 位且不能包含空格")
    if db.query(User).filter(User.username == username).first():
        raise Conflict("用户名已被使用")
    error = password_strength_error(payload.password)
    if error:
        raise BadRequest(error)
    phone = payload.phone.strip() if payload.phone else (username if username.isdigit() and len(username) == 11 else None)
    if phone and (not phone.isdigit() or len(phone) != 11):
        raise BadRequest("请输入 11 位手机号码")
    if phone and db.query(User).filter(User.phone == phone).first():
        raise Conflict("手机号码已注册")
    role = db.query(Role).filter(Role.code == "user").first()
    if role is None:
        role = Role(code="user", name="普通用户", description="平台注册用户", is_system=True)
        db.add(role)
        db.flush()
    user = User(username=username, password_hash=hash_password(payload.password),
                phone=phone, full_name=(payload.full_name or "").strip() or None,
                status="active", roles=[role])
    db.add(user)
    db.flush()
    return ok(issue_tokens(db, user))


def build_profile(db: Session, user: User, lk: Lookups | None = None) -> dict:
    lk = lk or Lookups(db)
    enterprise_name = lk.enterprise_name(user.enterprise_id)
    park_id = None
    if user.enterprise_id:
        from app.models.enterprise import Enterprise

        enterprise = db.get(Enterprise, user.enterprise_id)
        if enterprise is not None:
            park_id = enterprise.park_id
            enterprise_name = enterprise.name
    if park_id is None and user.org_id:
        from app.models.org import OrgUnit

        org = db.get(OrgUnit, user.org_id)
        if org is not None:
            park_id = org.park_id
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "org_id": user.org_id,
        "org_name": lk.org_name(user.org_id),
        "enterprise_id": user.enterprise_id,
        "enterprise_name": enterprise_name,
        "park_id": park_id,
        "is_superuser": user.is_superuser,
        "status": user.status,
        "roles": sorted(role_codes(user)),
        "role_names": [role.name for role in user.roles or []],
        "permissions": permission_codes(user),
    }


def issue_tokens(db: Session, user: User) -> dict:
    access_token = create_token(str(user.id), "access", extra={"username": user.username})
    refresh_token = create_token(str(user.id), "refresh")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": build_profile(db, user),
    }


@router.post("/login", response_model=ApiResponse[TokenOut], summary="账号密码登录")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.username == payload.username.strip()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise Unauthorized("用户名或密码错误", code=ErrorCode.LOGIN_FAILED)
    if user.status != "active":
        raise Unauthorized("账号已被禁用，请联系平台管理员", code=ErrorCode.ACCOUNT_DISABLED)
    user.last_login_at = now()
    db.flush()
    return ok(issue_tokens(db, user))


@router.post("/refresh", response_model=ApiResponse[TokenOut], summary="刷新访问令牌")
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> dict:
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise Unauthorized(str(exc), code=ErrorCode.REFRESH_TOKEN_INVALID) from exc
    jti = token_payload.get("jti", "")
    if jti and cache.is_token_blacklisted(jti):
        raise Unauthorized("刷新令牌已失效，请重新登录", code=ErrorCode.REFRESH_TOKEN_INVALID)
    user = db.get(User, int(token_payload["sub"]))
    if user is None or user.status != "active":
        raise Unauthorized("账号不可用，请重新登录", code=ErrorCode.REFRESH_TOKEN_INVALID)
    # 旋转刷新令牌：旧令牌立即作废
    if jti:
        cache.blacklist_token(jti, token_remaining_seconds(token_payload))
    return ok(issue_tokens(db, user))


@router.post("/logout", response_model=ApiResponse[dict], summary="退出登录")
def logout(
    token_payload: dict = Depends(get_token_payload),
) -> dict:
    jti = token_payload.get("jti", "")
    if jti:
        cache.blacklist_token(jti, max(1, token_remaining_seconds(token_payload)))
    return ok({"revoked": bool(jti)})


@router.get("/me", response_model=ApiResponse[UserProfile], summary="当前登录用户信息")
def me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return ok(build_profile(db, user))


@router.post("/change-password", response_model=ApiResponse[dict], summary="修改本账号密码")
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not verify_password(payload.old_password, user.password_hash):
        raise BadRequest("原密码不正确")
    error = password_strength_error(payload.new_password)
    if error:
        raise BadRequest(error)
    if payload.old_password == payload.new_password:
        raise BadRequest("新密码不能与原密码相同")
    user.password_hash = hash_password(payload.new_password)
    db.flush()
    return ok({"updated": True})
