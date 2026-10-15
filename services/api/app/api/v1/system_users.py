# -*- coding: utf-8 -*-
"""用户与权限接口：用户、角色、权限、组织架构。"""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups, user_out
from app.core.database import get_db
from app.core.deps import get_current_user, require
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.permissions import MODULE_NAMES
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.security import hash_password, password_strength_error
from app.models.enterprise import Enterprise
from app.models.org import OrgUnit, Permission, Role, User
from app.schemas.system import (
    AssignPermissionsIn,
    AssignRolesIn,
    OrgUnitIn,
    OrgUnitOut,
    OrgUnitUpdate,
    PermissionGroupOut,
    ResetPasswordIn,
    RoleIn,
    RoleOut,
    RoleUpdate,
    UserIn,
    UserOut,
    UserUpdate,
)

router = APIRouter(tags=["用户与权限"])

DEFAULT_PASSWORD = os.getenv("INITIAL_OPERATOR_PASSWORD", "Gz@123456")


# --------------------------------------------------------------------------- 用户


@router.get("/users", response_model=ApiResponse[PageData[UserOut]], summary="用户列表")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    enterprise_id: Optional[int] = None,
    org_id: Optional[int] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("user:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(User)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(User.username.like(like), User.full_name.like(like), User.phone.like(like))
        )
    if status:
        query = query.filter(User.status == status)
    if enterprise_id:
        query = query.filter(User.enterprise_id == enterprise_id)
    if org_id:
        query = query.filter(User.org_id == org_id)
    total = query.count()
    rows = query.order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok(paginate([user_out(db, row, lk) for row in rows], total, page, page_size))


@router.post("/users", response_model=ApiResponse[UserOut], summary="创建用户")
def create_user(
    payload: UserIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("user:write")),
) -> dict:
    if db.query(User).filter(User.username == payload.username).first():
        raise Conflict(f"用户名已存在：{payload.username}")
    password = payload.password or DEFAULT_PASSWORD
    error = password_strength_error(password)
    if error and payload.password:
        raise BadRequest(error)
    if payload.enterprise_id and not db.get(Enterprise, payload.enterprise_id):
        raise BadRequest("关联企业不存在")
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(password),
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        org_id=payload.org_id,
        enterprise_id=payload.enterprise_id,
        status=payload.status or "active",
        remark=payload.remark,
    )
    db.add(user)
    db.flush()
    if payload.role_ids:
        roles = db.query(Role).filter(Role.id.in_(payload.role_ids)).all()
        user.roles = roles
    db.flush()
    return ok(user_out(db, user, lk))


@router.get("/users/{user_id}", response_model=ApiResponse[UserOut], summary="用户详情")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("user:read")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    return ok(user_out(db, user, lk))


@router.put("/users/{user_id}", response_model=ApiResponse[UserOut], summary="更新用户")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("user:write")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    db.flush()
    return ok(user_out(db, user, lk))


@router.delete("/users/{user_id}", response_model=ApiResponse[dict], summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require("user:write")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    if user.id == current.id:
        raise BadRequest("不能删除当前登录账号")
    if user.is_superuser:
        raise Forbidden("超级管理员账号不允许删除")
    user.roles = []
    db.delete(user)
    db.flush()
    return ok({"deleted": True})


@router.post("/users/{user_id}/roles", response_model=ApiResponse[UserOut], summary="分配角色")
def assign_roles(
    user_id: int,
    payload: AssignRolesIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("user:write")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    roles = db.query(Role).filter(Role.id.in_(payload.role_ids or [])).all()
    if len(roles) != len(set(payload.role_ids or [])):
        raise BadRequest("存在无效的角色 ID")
    user.roles = roles
    db.flush()
    return ok(user_out(db, user, lk))


@router.post("/users/{user_id}/reset-password", response_model=ApiResponse[dict], summary="重置密码")
def reset_password(
    user_id: int,
    payload: ResetPasswordIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("user:write")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("用户不存在")
    error = password_strength_error(payload.new_password)
    if error:
        raise BadRequest(error)
    user.password_hash = hash_password(payload.new_password)
    db.flush()
    return ok({"reset": True, "username": user.username})


# --------------------------------------------------------------------------- 角色


@router.get("/roles", response_model=ApiResponse[List[RoleOut]], summary="角色列表")
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require("role:read", "user:read")),
) -> dict:
    roles = db.query(Role).order_by(Role.id.asc()).all()
    items = []
    for role in roles:
        items.append(
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "user_count": len(role.users),
                "permission_codes": sorted(perm.code for perm in role.permissions),
                "created_at": role.created_at,
            }
        )
    return ok(items)


@router.post("/roles", response_model=ApiResponse[RoleOut], summary="创建角色")
def create_role(
    payload: RoleIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("role:write")),
) -> dict:
    if db.query(Role).filter(Role.code == payload.code).first():
        raise Conflict(f"角色编码已存在：{payload.code}")
    role = Role(
        code=payload.code.strip(),
        name=payload.name,
        description=payload.description,
        is_system=False,
    )
    db.add(role)
    db.flush()
    return ok(
        {
            "id": role.id,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "user_count": 0,
            "permission_codes": [],
            "created_at": role.created_at,
        }
    )


@router.put("/roles/{role_id}", response_model=ApiResponse[RoleOut], summary="更新角色")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require("role:write")),
) -> dict:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(role, field, value)
    db.flush()
    return ok(
        {
            "id": role.id,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "user_count": len(role.users),
            "permission_codes": sorted(perm.code for perm in role.permissions),
            "created_at": role.created_at,
        }
    )


@router.delete("/roles/{role_id}", response_model=ApiResponse[dict], summary="删除角色")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("role:write")),
) -> dict:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    if role.is_system:
        raise Forbidden("系统内置角色不允许删除")
    if role.users:
        raise Conflict("该角色下仍有用户，请先解除关联")
    db.delete(role)
    db.flush()
    return ok({"deleted": True})


@router.get("/roles/{role_id}/permissions", response_model=ApiResponse[List[str]], summary="角色权限")
def role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("role:read", "user:read")),
) -> dict:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    return ok(sorted(perm.code for perm in role.permissions))


@router.put("/roles/{role_id}/permissions", response_model=ApiResponse[List[str]], summary="设置角色权限")
def set_role_permissions(
    role_id: int,
    payload: AssignPermissionsIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("role:write")),
) -> dict:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFound("角色不存在")
    if role.is_system and role.code == "platform_admin":
        raise Forbidden("平台管理员角色权限不可修改")
    permissions = db.query(Permission).filter(Permission.id.in_(payload.permission_ids or [])).all()
    if len(permissions) != len(set(payload.permission_ids or [])):
        raise BadRequest("存在无效的权限 ID")
    role.permissions = permissions
    db.flush()
    return ok(sorted(perm.code for perm in role.permissions))


@router.get("/permissions", response_model=ApiResponse[List[PermissionGroupOut]], summary="权限字典")
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require("role:read", "user:read")),
) -> dict:
    rows = db.query(Permission).order_by(Permission.module.asc(), Permission.id.asc()).all()
    grouped: dict = {}
    for row in rows:
        grouped.setdefault(row.module, []).append(
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "module": row.module,
                "description": row.description,
            }
        )
    return ok(
        [
            {
                "module": module,
                "module_name": MODULE_NAMES.get(module, module),
                "permissions": items,
            }
            for module, items in grouped.items()
        ]
    )


# --------------------------------------------------------------------------- 组织架构


@router.get("/org-units/tree", response_model=ApiResponse[List[OrgUnitOut]], summary="组织架构树")
def org_tree(
    db: Session = Depends(get_db),
    _: User = Depends(require("org:read", "user:read")),
) -> dict:
    rows = db.query(OrgUnit).order_by(OrgUnit.sort.asc(), OrgUnit.id.asc()).all()
    nodes = {
        row.id: {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "unit_type": row.unit_type,
            "parent_id": row.parent_id,
            "park_id": row.park_id,
            "region": row.region,
            "address": row.address,
            "contact_name": row.contact_name,
            "contact_phone": row.contact_phone,
            "status": row.status,
            "sort": row.sort,
            "children": [],
        }
        for row in rows
    }
    roots: List[dict] = []
    for row in rows:
        node = nodes[row.id]
        parent = nodes.get(row.parent_id) if row.parent_id else None
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return ok(roots)


@router.post("/org-units", response_model=ApiResponse[OrgUnitOut], summary="创建组织单元")
def create_org(
    payload: OrgUnitIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("org:write")),
) -> dict:
    if db.query(OrgUnit).filter(OrgUnit.code == payload.code).first():
        raise Conflict(f"组织编码已存在：{payload.code}")
    if payload.unit_type not in ("platform", "park", "enterprise"):
        raise BadRequest("unit_type 取值必须为 platform / park / enterprise")
    if payload.parent_id and not db.get(OrgUnit, payload.parent_id):
        raise BadRequest("上级组织不存在")
    org = OrgUnit(**payload.model_dump())
    db.add(org)
    db.flush()
    return ok(
        {
            "id": org.id,
            "code": org.code,
            "name": org.name,
            "unit_type": org.unit_type,
            "parent_id": org.parent_id,
            "park_id": org.park_id,
            "region": org.region,
            "address": org.address,
            "contact_name": org.contact_name,
            "contact_phone": org.contact_phone,
            "status": org.status,
            "sort": org.sort,
            "children": [],
        }
    )


@router.put("/org-units/{org_id}", response_model=ApiResponse[dict], summary="更新组织单元")
def update_org(
    org_id: int,
    payload: OrgUnitUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require("org:write")),
) -> dict:
    org = db.get(OrgUnit, org_id)
    if org is None:
        raise NotFound("组织单元不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.flush()
    return ok({"id": org.id, "name": org.name, "updated": True})


@router.delete("/org-units/{org_id}", response_model=ApiResponse[dict], summary="删除组织单元")
def delete_org(
    org_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("org:write")),
) -> dict:
    org = db.get(OrgUnit, org_id)
    if org is None:
        raise NotFound("组织单元不存在")
    if db.query(OrgUnit).filter(OrgUnit.parent_id == org_id).count():
        raise Conflict("存在下级组织，无法删除")
    if db.query(User).filter(User.org_id == org_id).count():
        raise Conflict("该组织下仍有用户，无法删除")
    db.delete(org)
    db.flush()
    return ok({"deleted": True})
