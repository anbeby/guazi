# -*- coding: utf-8 -*-
"""请求上下文（request_id 等），供日志与统一响应使用。"""
from __future__ import annotations

import contextvars
import uuid

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
_current_user_id: contextvars.ContextVar[int] = contextvars.ContextVar("current_user_id", default=0)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str:
    return _request_id.get()


def set_current_user_id(value: int) -> None:
    _current_user_id.set(value)


def get_current_user_id() -> int:
    return _current_user_id.get()
