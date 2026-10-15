# -*- coding: utf-8 -*-
"""模型包：导入顺序无关（外键以字符串延迟解析），但必须全部导入以确保 metadata 完整。"""
from app.models.base import Base, TimestampMixin, bigint, money, qty, rate  # noqa: F401
from app.models.org import (  # noqa: F401
    OperationLog,
    OrgUnit,
    Permission,
    Role,
    SysSequence,
    User,
    role_permission,
    user_role,
)
from app.models.enterprise import (  # noqa: F401
    Enterprise,
    Park,
    ParkContract,
    ParkZone,
    Stall,
)
from app.models.product import (  # noqa: F401
    Category,
    Inventory,
    Product,
    StockMove,
    StorageLocation,
    Warehouse,
)
from app.models.trade import (  # noqa: F401
    Contract,
    Inquiry,
    Quotation,
    TradeOrder,
    TradeOrderItem,
)
from app.models.settlement import (  # noqa: F401
    Settlement,
    SettlementLine,
    TransactionFlow,
)
from app.models.trace import TraceBatch, TraceEvent  # noqa: F401
from app.models.matching import (  # noqa: F401
    LeadFollowup, MatchCase, MatchFollowup, MatchLead, ProductFavorite, PurchaseRequirement,
)
from app.models.system import (  # noqa: F401
    IntegrationIdMap,
    SysFile,
    SyncLog,
    SyncOutbox,
)

__all__ = [
    "Base",
    "OrgUnit",
    "User",
    "Role",
    "Permission",
    "SysSequence",
    "OperationLog",
    "Enterprise",
    "Park",
    "ParkZone",
    "Stall",
    "ParkContract",
    "Category",
    "Product",
    "Warehouse",
    "StorageLocation",
    "Inventory",
    "StockMove",
    "Inquiry",
    "Quotation",
    "TradeOrder",
    "TradeOrderItem",
    "Contract",
    "Settlement",
    "SettlementLine",
    "TransactionFlow",
    "TraceBatch",
    "TraceEvent",
    "PurchaseRequirement",
    "MatchCase",
    "MatchFollowup",
    "MatchLead",
    "LeadFollowup",
    "ProductFavorite",
    "SysFile",
    "SyncOutbox",
    "IntegrationIdMap",
    "SyncLog",
]
