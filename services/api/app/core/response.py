# -*- coding: utf-8 -*-
"""统一响应信封与分页工具。"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.context import get_request_id

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None
    request_id: Optional[str] = None


class PageData(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


def ok(data: Any = None, message: str = "ok") -> dict:
    """构造成功信封。"""
    return {
        "code": 0,
        "message": message,
        "data": data,
        "request_id": get_request_id(),
    }


def fail(message: str, code: int, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data, "request_id": get_request_id()}


def paginate(
    items: Sequence[Any],
    total: int,
    page: int,
    page_size: int,
) -> PageData:
    return PageData(items=list(items), total=int(total), page=int(page), page_size=int(page_size))


def normalize_page(page: Optional[int], page_size: Optional[int]) -> tuple:
    page = 1 if not page or page < 1 else int(page)
    size = settings.DEFAULT_PAGE_SIZE if not page_size or page_size < 1 else int(page_size)
    size = min(size, settings.MAX_PAGE_SIZE)
    return page, size


def apply_sort(query, model, order_by: Optional[str], default: str = "-id"):
    """order_by 支持 `field` 与 `-field`；非法字段回退默认排序。"""
    raw = (order_by or default or "").strip()
    descending = raw.startswith("-")
    field_name = raw.lstrip("-")
    column = getattr(model, field_name, None)
    if column is None:
        field_name = default.lstrip("-")
        descending = default.startswith("-")
        column = getattr(model, field_name, None)
    if column is None:
        return query
    return query.order_by(column.desc() if descending else column.asc())
