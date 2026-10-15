# -*- coding: utf-8 -*-
"""路由公共依赖。"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.serializers import Lookups
from app.core.database import get_db


def get_lookups(db: Session = Depends(get_db)) -> Lookups:
    """请求级关联名称查找表。"""
    return Lookups(db)
