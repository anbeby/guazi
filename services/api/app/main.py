# -*- coding: utf-8 -*-
"""应用入口：中间件、异常处理、路由挂载、内置控制台。"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.v1.system import health_router
from app.core.config import settings
from app.core.context import get_current_user_id, new_request_id, set_request_id
from app.core.database import init_db
from app.core.errors import BizError, ErrorCode
from app.core.response import fail
from app.core.timeutil import now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("gz-platform")

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("数据库表结构校验完成")
    except SQLAlchemyError as exc:  # pragma: no cover - 启动期数据库异常
        logger.error("数据库初始化失败：%s", exc)
    logger.info(
        "%s v%s 启动完成 env=%s db=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENV,
        "sqlite" if settings.is_sqlite else "postgresql",
    )
    yield
    logger.info("服务已停止")


app = FastAPI(
    title=settings.APP_NAME + " · 自研产业平台 API",
    version=settings.APP_VERSION,
    description=(
        "第十师北屯市瓜子油料数字化交易与产业运营平台后端接口。\n\n"
        "- 统一响应信封：`{code, message, data, request_id}`\n"
        "- 认证方式：`Authorization: Bearer <access_token>`\n"
        "- 接口规范详见 `docs/04-接口规范.md`"
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Process-Time"],
)


# --------------------------------------------------------------------------- 中间件


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = new_request_id()
    set_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # pragma: no cover - 交给异常处理器
        raise
    duration_ms = int((time.perf_counter() - started) * 1000)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Process-Time"] = str(duration_ms)
    if request.method in WRITE_METHODS and request.url.path.startswith(settings.API_PREFIX):
        _write_operation_log(request, response.status_code, duration_ms, request_id)
    return response


def _write_operation_log(request: Request, status_code: int, duration_ms: int, request_id: str) -> None:
    """审计日志：仅记录写操作，失败不影响主流程。"""
    try:
        from app.core.database import get_session_factory
        from app.models.org import OperationLog

        path = request.url.path
        parts = [part for part in path.split("/") if part]
        module = parts[2] if len(parts) > 2 else "system"
        session = get_session_factory()()
        try:
            session.add(
                OperationLog(
                    user_id=get_current_user_id() or None,
                    username=None,
                    enterprise_id=None,
                    module=module,
                    action=request.method,
                    method=request.method,
                    path=path[:255],
                    target_type=parts[3] if len(parts) > 3 else None,
                    target_id=parts[4] if len(parts) > 4 else None,
                    ip=request.client.host if request.client else None,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    detail=None,
                    created_at=now(),
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception as exc:  # pragma: no cover - 审计失败不得影响业务
        logger.warning("操作日志写入失败：%s", exc)


# --------------------------------------------------------------------------- 异常处理


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=fail(exc.message, exc.code, exc.data))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", []) if item != "body")
        details.append({"field": location, "message": error.get("msg")})
    return JSONResponse(
        status_code=422,
        content=fail("参数校验失败", ErrorCode.BAD_REQUEST, {"errors": details}),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    mapping = {
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        405: ErrorCode.BAD_REQUEST,
        409: ErrorCode.CONFLICT,
    }
    code = mapping.get(exc.status_code, ErrorCode.INTERNAL if exc.status_code >= 500 else ErrorCode.BAD_REQUEST)
    message = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
    response = JSONResponse(status_code=exc.status_code, content=fail(message, code))
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("数据库完整性约束冲突：%s", exc)
    return JSONResponse(
        status_code=409,
        content=fail("数据冲突：唯一约束或外键校验失败，请检查编码是否重复", ErrorCode.CONFLICT),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常：%s %s", request.method, request.url.path)
    message = str(exc) if settings.DEBUG else "服务器内部错误，请联系平台管理员"
    return JSONResponse(status_code=500, content=fail(message, ErrorCode.INTERNAL))


# --------------------------------------------------------------------------- 路由


app.include_router(health_router)
app.include_router(api_router, prefix=settings.API_PREFIX)

if STATIC_DIR.exists():
    # 免构建运营控制台（PC）与移动端 H5：由 API 服务直接托管，无需前端构建工具链，
    # 保证「打开即用」与局域网/手机直接访问（见 README 的局域网部署说明）。
    app.mount("/console", StaticFiles(directory=str(STATIC_DIR / "console"), html=True), name="console")
    app.mount("/m", StaticFiles(directory=str(STATIC_DIR / "m"), html=True), name="mobile")


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "console": "/console/",
        "mobile": "/m/",
        "health": "/health",
    }
