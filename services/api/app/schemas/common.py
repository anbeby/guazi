# -*- coding: utf-8 -*-
"""公共 Schema。"""
from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.response import ORMModel

T = TypeVar("T")

__all__ = ["ORMModel", "ListQuery", "IdListIn", "ReasonIn", "CountItem", "NamedCount", "TreeOut"]


class ListQuery(BaseModel):
    page: int = Field(1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(20, ge=1, le=200, description="每页条数，上限 200")
    keyword: Optional[str] = Field(None, description="模糊搜索关键字")
    order_by: Optional[str] = Field(None, description="排序字段，前缀 - 表示倒序")


class IdListIn(BaseModel):
    ids: List[int] = Field(default_factory=list)


class ReasonIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class CountItem(BaseModel):
    name: str
    value: float = 0


class NamedCount(ORMModel):
    name: Optional[str] = None
    count: int = 0
    quantity: float = 0
    amount: float = 0


class TreeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: Optional[str] = None
    name: str
    parent_id: Optional[int] = None
    level: Optional[int] = None
    extra: Optional[dict] = None
    children: List["TreeOut"] = Field(default_factory=list)


TreeOut.model_rebuild()
