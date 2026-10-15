# -*- coding: utf-8 -*-
"""数据库引擎与会话管理。

- 生产（PostgreSQL）：通过 `options=-csearch_path=gz,public` 把自研业务表固定到 `gz` schema，
  与 Odoo 的 `public` schema 物理同库逻辑隔离。
- 测试（SQLite）：内存库 + StaticPool，同一连接共享数据，无需外部依赖。
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None
_engine_url: Optional[str] = None


def _build_engine(url: str) -> Engine:
    kwargs: Dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
        kwargs["echo"] = settings.DB_ECHO
    else:
        connect_args: Dict[str, Any] = {}
        if url.startswith("postgresql"):
            # 业务表落在 gz schema，公共对象仍可访问 public
            connect_args["options"] = f"-csearch_path={settings.DB_SCHEMA},public"
            connect_args["application_name"] = "gz-platform-api"
        kwargs["connect_args"] = connect_args
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        kwargs["pool_recycle"] = 1800
        kwargs["echo"] = settings.DB_ECHO
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - 测试便利
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def get_engine() -> Engine:
    global _engine, _engine_url
    if _engine is None or _engine_url != settings.DATABASE_URL:
        _engine = _build_engine(settings.DATABASE_URL)
        _engine_url = settings.DATABASE_URL
        global _session_factory
        _session_factory = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _engine


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：请求级会话，成功自动提交，异常自动回滚。"""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(drop: bool = False) -> None:
    """建表（导入全部模型后调用）。"""
    import app.models  # noqa: F401  确保所有模型已注册到 metadata

    engine = get_engine()
    if drop:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def ping() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - 就绪探针容错
        return False


def dialect_name() -> str:
    return get_engine().dialect.name


def lock_query(query, db: Session):
    """PostgreSQL 下行级锁；SQLite（测试）自动跳过，保证同一套业务代码可测。"""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return query.with_for_update()
    return query
