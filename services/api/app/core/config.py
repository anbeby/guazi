# -*- coding: utf-8 -*-
"""应用配置：全部来源于环境变量，带安全默认值，便于本地开发与容器部署。"""
from __future__ import annotations

import os
from typing import List


def _env(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    return default if value is None or value == "" else value


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key, "1" if default else "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _env_list(key: str, default: str) -> List[str]:
    raw = _env(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """运行期配置快照。"""

    def __init__(self) -> None:
        # ---- 基础 ----
        self.APP_NAME = _env("APP_NAME", "第十师瓜子油料数字化交易平台")
        self.APP_VERSION = _env("APP_VERSION", "1.0.0")
        self.ENV = _env("APP_ENV", "dev")
        self.DEBUG = _env_bool("APP_DEBUG", True)
        self.API_PREFIX = "/api/v1"
        self.TIMEZONE = _env("TZ", "Asia/Shanghai")

        # ---- 数据库 ----
        # 生产：postgresql+psycopg://user:pass@postgres:5432/gz_platform
        # 测试：sqlite://（内存库，StaticPool 共享连接）
        self.DATABASE_URL = _env("DATABASE_URL", "sqlite://")
        self.DB_SCHEMA = _env("DB_SCHEMA", "gz")
        self.DB_ECHO = _env_bool("DB_ECHO", False)
        self.DB_POOL_SIZE = _env_int("DB_POOL_SIZE", 10)
        self.DB_MAX_OVERFLOW = _env_int("DB_MAX_OVERFLOW", 20)

        # ---- 鉴权 ----
        self.JWT_SECRET = _env("JWT_SECRET", "gz-platform-dev-secret-change-me")
        self.JWT_ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 120)
        self.REFRESH_TOKEN_EXPIRE_DAYS = _env_int("REFRESH_TOKEN_EXPIRE_DAYS", 7)
        self.PASSWORD_PBKDF2_ROUNDS = _env_int("PASSWORD_PBKDF2_ROUNDS", 260000)

        # ---- 集成 ----
        self.INTEGRATION_SECRET = _env("INTEGRATION_SECRET", "gz-integration-secret-change-me")
        self.INTEGRATION_SIGN_TOLERANCE = _env_int("INTEGRATION_SIGN_TOLERANCE", 300)
        self.ODOO_BASE_URL = _env("ODOO_BASE_URL", "http://odoo:8069")
        self.ODOO_DB = _env("ODOO_DB", "gz_odoo")
        self.ODOO_USER = _env("ODOO_USER", "admin")
        self.ODOO_PASSWORD = _env("ODOO_PASSWORD", "admin")
        self.ODOO_TIMEOUT = _env_int("ODOO_TIMEOUT", 15)
        self.OUTBOX_BATCH_SIZE = _env_int("OUTBOX_BATCH_SIZE", 50)
        self.OUTBOX_MAX_RETRY = _env_int("OUTBOX_MAX_RETRY", 8)

        # ---- 中间件 ----
        self.REDIS_URL = _env("REDIS_URL", "redis://redis:6379/0")
        self.REDIS_ENABLED = _env_bool("REDIS_ENABLED", True)
        self.CACHE_PREFIX = _env("CACHE_PREFIX", "gz:")
        self.ELASTICSEARCH_URL = _env("ELASTICSEARCH_URL", "http://elasticsearch:9200")
        self.ELASTICSEARCH_ENABLED = _env_bool("ELASTICSEARCH_ENABLED", True)
        self.ELASTICSEARCH_INDEX = _env("ELASTICSEARCH_INDEX", "gz_products")
        self.MINIO_ENDPOINT = _env("MINIO_ENDPOINT", "minio:9000")
        self.MINIO_ACCESS_KEY = _env("MINIO_ACCESS_KEY", "gzminio")
        self.MINIO_SECRET_KEY = _env("MINIO_SECRET_KEY", "gzminio123456")
        self.MINIO_SECURE = _env_bool("MINIO_SECURE", False)
        self.MINIO_BUCKET = _env("MINIO_BUCKET", "gz-product")
        self.MINIO_ENABLED = _env_bool("MINIO_ENABLED", True)
        self.LOCAL_STORAGE_DIR = _env("LOCAL_STORAGE_DIR", "./uploads")
        self.STORAGE_PUBLIC_BASE = _env("STORAGE_PUBLIC_BASE", "/api/v1/files")

        # ---- 业务参数 ----
        self.PLATFORM_SERVICE_FEE_RATE = _env_float("PLATFORM_SERVICE_FEE_RATE", 0.005)
        self.DEFAULT_TAX_RATE = _env_float("DEFAULT_TAX_RATE", 0.09)
        self.MAX_PAGE_SIZE = _env_int("MAX_PAGE_SIZE", 200)
        self.DEFAULT_PAGE_SIZE = _env_int("DEFAULT_PAGE_SIZE", 20)
        self.UPLOAD_MAX_SIZE = _env_int("UPLOAD_MAX_SIZE", 100 * 1024 * 1024)
        self.ALLOWED_UPLOAD_EXT = _env_list(
            "ALLOWED_UPLOAD_EXT",
            ".jpg,.jpeg,.png,.webp,.gif,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.zip",
        )

        # ---- 跨域 ----
        self.CORS_ORIGINS = _env_list("CORS_ORIGINS", "*")

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
