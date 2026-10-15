# -*- coding: utf-8 -*-
"""数据权限（企业隔离 / 园区隔离）。

统一在查询层注入过滤条件，业务路由内禁止手写隔离逻辑。
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSION_CODES
from app.models.enterprise import Enterprise
from app.models.org import OrgUnit, User

PLATFORM_ROLES = {"platform_admin", "finance"}


def role_codes(user: User) -> set:
    return {role.code for role in (user.roles or [])}


def permission_codes(user: User) -> List[str]:
    if user.is_superuser:
        return list(ALL_PERMISSION_CODES)
    codes = set()
    for role in user.roles or []:
        for perm in role.permissions or []:
            codes.add(perm.code)
    return sorted(codes)


def is_unrestricted(user: User) -> bool:
    """平台管理员 / 超级管理员 / 财务：可见全平台数据。"""
    if user.is_superuser:
        return True
    return bool(role_codes(user) & PLATFORM_ROLES)


def is_park_operator(user: User) -> bool:
    return "park_operator" in role_codes(user)


def own_enterprise_id(user: User) -> Optional[int]:
    return user.enterprise_id


def park_scope_ids(db: Session, user: User) -> List[int]:
    """园区运营人员所辖园区 ID 列表。"""
    if user.org_id:
        org = db.get(OrgUnit, user.org_id)
        if org is not None and org.park_id:
            return [int(org.park_id)]
    return []


def enterprise_scope_ids(db: Session, user: User) -> Optional[List[int]]:
    """返回用户可见的企业 ID 列表；None 表示不限制。"""
    if is_unrestricted(user):
        return None
    if is_park_operator(user):
        park_ids = park_scope_ids(db, user)
        if not park_ids:
            return []
        rows = db.query(Enterprise.id).filter(Enterprise.park_id.in_(park_ids)).all()
        ids = [int(r[0]) for r in rows]
        if user.enterprise_id:
            ids.append(int(user.enterprise_id))
        return sorted(set(ids))
    return [int(user.enterprise_id)] if user.enterprise_id else []


def apply_own_enterprise(query, model, user: User, field: str = "enterprise_id", db: Optional[Session] = None):
    """对以 enterprise_id 归属的实体（商品、库存、仓库、结算单）注入隔离。"""
    if is_unrestricted(user):
        return query
    column = getattr(model, field, None)
    if column is None:
        return query
    ids = enterprise_scope_ids(db, user) if db is not None else None
    if ids is None:
        return query
    if not ids:
        return query.filter(column == -1)
    return query.filter(column.in_(ids))


def apply_trade_scope(query, model, user: User, db: Optional[Session] = None):
    """对买卖双向实体（询价、报价、订单、合同）注入隔离。"""
    if is_unrestricted(user):
        return query
    ids = enterprise_scope_ids(db, user) if db is not None else None
    if ids is None:
        return query
    if not ids:
        return query.filter(model.id == -1)
    clauses = []
    for field in ("buyer_enterprise_id", "supplier_enterprise_id", "enterprise_id"):
        column = getattr(model, field, None)
        if column is not None:
            clauses.append(column.in_(ids))
    if not clauses:
        return query
    return query.filter(or_(*clauses))


def ensure_owns(user: User, enterprise_id: Optional[int], db: Optional[Session] = None) -> None:
    """校验用户是否有权操作指定企业的数据。"""
    from app.core.errors import Forbidden

    if is_unrestricted(user):
        return
    allowed = enterprise_scope_ids(db, user) if db is not None else None
    if allowed is None:
        return
    if enterprise_id is None or int(enterprise_id) not in set(allowed):
        raise Forbidden("无权操作该企业的数据")


def resolve_own_enterprise(user: User, requested: Optional[int] = None) -> int:
    """确定写入数据应归属的企业 ID（商户只能写自己企业）。"""
    from app.core.errors import Forbidden

    if user.is_superuser or is_unrestricted(user):
        if requested:
            return int(requested)
        if user.enterprise_id:
            return int(user.enterprise_id)
        raise Forbidden("平台账号需显式指定企业")
    if not user.enterprise_id:
        raise Forbidden("当前账号未关联企业，无法执行该操作")
    if requested and int(requested) != int(user.enterprise_id):
        raise Forbidden("只能操作本企业的数据")
    return int(user.enterprise_id)


def scope_filter_ids(ids: Optional[Sequence[int]], column, query):
    if ids is None:
        return query
    if not ids:
        return query.filter(column == -1)
    return query.filter(column.in_(list(ids)))
