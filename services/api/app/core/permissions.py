# -*- coding: utf-8 -*-
"""权限码注册表与内置角色定义。

权限码规范：`<module>:<action>`，action ∈ read / write / audit / delete / execute。
新增模块只需在此登记，角色分配与前端按钮级鉴权自动生效。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# (code, 名称, 所属模块)
PERMISSIONS: List[Tuple[str, str, str]] = [
    ("user:read", "查看用户", "user"),
    ("user:write", "管理用户", "user"),
    ("role:read", "查看角色", "role"),
    ("role:write", "管理角色", "role"),
    ("org:read", "查看组织", "org"),
    ("org:write", "管理组织", "org"),
    ("merchant:read", "查看商户", "merchant"),
    ("merchant:write", "管理商户", "merchant"),
    ("merchant:audit", "审核商户", "merchant"),
    ("product:read", "查看商品", "product"),
    ("product:write", "管理商品", "product"),
    ("product:audit", "审核商品", "product"),
    ("inventory:read", "查看库存", "inventory"),
    ("inventory:write", "管理仓库", "inventory"),
    ("inventory:execute", "出入库操作", "inventory"),
    ("trade:read", "查看交易", "trade"),
    ("trade:write", "交易操作", "trade"),
    ("trade:audit", "交易审核", "trade"),
    ("settlement:read", "查看结算", "settlement"),
    ("settlement:write", "结算操作", "settlement"),
    ("trace:read", "查看溯源", "trace"),
    ("trace:write", "管理溯源", "trace"),
    ("park:read", "查看园区", "park"),
    ("park:write", "管理园区", "park"),
    ("data:read", "查看数据", "data"),
    ("integration:read", "查看集成", "integration"),
    ("integration:write", "集成操作", "integration"),
]

MODULE_NAMES: Dict[str, str] = {
    "user": "用户管理",
    "role": "角色权限",
    "org": "组织架构",
    "merchant": "商户管理",
    "product": "商品中心",
    "inventory": "库存仓储",
    "trade": "B2B 交易",
    "settlement": "电子结算",
    "trace": "安全溯源",
    "park": "智慧园区",
    "data": "数据中心",
    "integration": "系统集成",
}

ALL_PERMISSION_CODES: List[str] = [code for code, _, _ in PERMISSIONS]

# 角色编码 → (中文名, 权限码列表, 是否超级管理员)
ROLES: Dict[str, Tuple[str, List[str], bool]] = {
    "platform_admin": ("平台管理员", ALL_PERMISSION_CODES, True),
    "user": ("普通用户", [], False),
    "park_operator": (
        "园区运营人员",
        [
            "park:read", "park:write",
            "merchant:read", "merchant:audit",
            "product:read", "inventory:read", "trade:read",
            "settlement:read", "trace:read", "data:read", "org:read",
        ],
        False,
    ),
    "merchant": (
        "商户",
        [
            "merchant:read", "product:read", "product:write",
            "inventory:read", "inventory:write", "inventory:execute",
            "trade:read", "trade:write",
            "settlement:read", "settlement:write",
            "trace:read", "trace:write", "data:read",
        ],
        False,
    ),
    "supplier": (
        "供应商",
        [
            "merchant:read", "product:read", "product:write",
            "inventory:read", "inventory:write", "inventory:execute",
            "trade:read", "trade:write",
            "settlement:read", "settlement:write",
            "trace:read", "trace:write", "data:read",
        ],
        False,
    ),
    "buyer": (
        "采购商",
        [
            "merchant:read", "product:read",
            "trade:read", "trade:write",
            "settlement:read", "data:read", "trace:read",
        ],
        False,
    ),
    "finance": (
        "财务",
        [
            "settlement:read", "settlement:write",
            "trade:read", "merchant:read", "product:read",
            "data:read", "integration:read",
        ],
        False,
    ),
}

ENTERPRISE_SCOPED_ROLES = {"merchant", "supplier", "buyer"}
