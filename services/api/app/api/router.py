# -*- coding: utf-8 -*-
"""API v1 路由聚合。新增模块只需在此登记一次。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    catalog,
    dashboard,
    files,
    finance,
    merchant,
    matching,
    park,
    portal,
    showcase,
    stock,
    system,
    system_users,
    trace,
    trade,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(system_users.router)
api_router.include_router(merchant.router)
api_router.include_router(catalog.router)
api_router.include_router(stock.router)
api_router.include_router(trade.router)
api_router.include_router(finance.router)
api_router.include_router(park.router)
api_router.include_router(showcase.router)
api_router.include_router(matching.router)
api_router.include_router(portal.router)
api_router.include_router(trace.router)
api_router.include_router(dashboard.router)
api_router.include_router(files.router)
api_router.include_router(system.router)
api_router.include_router(system.integration_router)

__all__ = ["api_router"]
