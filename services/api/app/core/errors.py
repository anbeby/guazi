# -*- coding: utf-8 -*-
"""业务异常与错误码。"""
from __future__ import annotations

from typing import Any, Optional


class ErrorCode:
    OK = 0
    BAD_REQUEST = 40000
    UNAUTHORIZED = 40001
    FORBIDDEN = 40003
    NOT_FOUND = 40004
    CONFLICT = 40009
    LOGIN_FAILED = 40100
    ACCOUNT_DISABLED = 40101
    REFRESH_TOKEN_INVALID = 40102
    INTERNAL = 50000


class BizError(Exception):
    """业务异常：由全局异常处理器转换为统一信封。"""

    def __init__(
        self,
        message: str,
        code: int = ErrorCode.BAD_REQUEST,
        status_code: int = 400,
        data: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data


class BadRequest(BizError):
    def __init__(self, message: str = "参数或业务校验失败", data: Optional[Any] = None) -> None:
        super().__init__(message, ErrorCode.BAD_REQUEST, 400, data)


class Unauthorized(BizError):
    def __init__(self, message: str = "未认证或登录已失效", code: int = ErrorCode.UNAUTHORIZED) -> None:
        super().__init__(message, code, 401)


class Forbidden(BizError):
    def __init__(self, message: str = "无权限执行该操作") -> None:
        super().__init__(message, ErrorCode.FORBIDDEN, 403)


class NotFound(BizError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message, ErrorCode.NOT_FOUND, 404)


class Conflict(BizError):
    def __init__(self, message: str = "业务冲突", data: Optional[Any] = None) -> None:
        super().__init__(message, ErrorCode.CONFLICT, 409, data)


class InsufficientStock(Conflict):
    def __init__(self, product_name: str, available, required) -> None:
        super().__init__(
            f"商品【{product_name}】可用库存不足：可用 {available}，需要 {required}",
            data={"product_name": product_name, "available": str(available), "required": str(required)},
        )
