# -*- coding: utf-8 -*-
"""缓存适配器：优先 Redis，不可用时自动降级为进程内缓存。

降级是硬性要求（ADR-06）：中间件故障不得导致交易主链路不可用。
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings

try:  # pragma: no cover - 依赖缺失时直接降级
    import redis as redis_lib
except Exception:  # pragma: no cover
    redis_lib = None  # type: ignore


class MemoryCache:
    """进程内缓存（带 TTL 与容量上限）。"""

    def __init__(self, max_size: int = 20000) -> None:
        self._data: Dict[str, Tuple[str, Optional[float]]] = {}
        self._lock = threading.RLock()
        self._max_size = max_size

    def _purge(self) -> None:
        now_ts = time.time()
        expired = [k for k, (_, exp) in self._data.items() if exp is not None and exp < now_ts]
        for key in expired:
            self._data.pop(key, None)
        if len(self._data) > self._max_size:
            for key in list(self._data.keys())[: len(self._data) - self._max_size]:
                self._data.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            value, expires_at = item
            if expires_at is not None and expires_at < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._data[key] = (value, time.time() + ttl if ttl else None)
            self._purge()

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def incr(self, key: str, amount: int = 1) -> int:
        with self._lock:
            current = int(self.get(key) or 0) + amount
            item = self._data.get(key)
            ttl = None
            if item and item[1] is not None:
                ttl = max(1, int(item[1] - time.time()))
            self.set(key, str(current), ttl)
            return current


class Cache:
    """统一缓存门面。"""

    def __init__(self) -> None:
        self._memory = MemoryCache()
        self._redis = None
        self._redis_healthy = False
        self.connect()

    # ------------------------------------------------------------------ 连接
    def connect(self) -> None:
        if not settings.REDIS_ENABLED or redis_lib is None:
            self._redis = None
            self._redis_healthy = False
            return
        try:
            client = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                health_check_interval=30,
            )
            client.ping()
            self._redis = client
            self._redis_healthy = True
        except Exception:
            self._redis = None
            self._redis_healthy = False

    def _key(self, key: str) -> str:
        return key if key.startswith(settings.CACHE_PREFIX) else f"{settings.CACHE_PREFIX}{key}"

    @property
    def backend(self) -> str:
        return "redis" if self._redis_healthy else "memory"

    def status(self) -> Dict[str, Any]:
        return {"backend": self.backend, "enabled": settings.REDIS_ENABLED}

    # ------------------------------------------------------------------ 基础
    def get(self, key: str) -> Optional[str]:
        full = self._key(key)
        if self._redis_healthy and self._redis is not None:
            try:
                return self._redis.get(full)
            except Exception:
                self._redis_healthy = False
        return self._memory.get(full)

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        full = self._key(key)
        if self._redis_healthy and self._redis is not None:
            try:
                if ttl:
                    self._redis.setex(full, ttl, value)
                else:
                    self._redis.set(full, value)
                return
            except Exception:
                self._redis_healthy = False
        self._memory.set(full, value, ttl)

    def delete(self, key: str) -> None:
        full = self._key(key)
        if self._redis_healthy and self._redis is not None:
            try:
                self._redis.delete(full)
            except Exception:
                self._redis_healthy = False
        self._memory.delete(full)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def incr(self, key: str, amount: int = 1) -> int:
        full = self._key(key)
        if self._redis_healthy and self._redis is not None:
            try:
                return int(self._redis.incrby(full, amount))
            except Exception:
                self._redis_healthy = False
        return self._memory.incr(full, amount)

    # ------------------------------------------------------------------ JSON
    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl)

    # ------------------------------------------------------------------ 令牌黑名单
    def blacklist_token(self, jti: str, ttl: int) -> None:
        if ttl > 0:
            self.set(f"token:blacklist:{jti}", "1", ttl)

    def is_token_blacklisted(self, jti: str) -> bool:
        return self.exists(f"token:blacklist:{jti}")

    # ------------------------------------------------------------------ 幂等键
    def acquire_idempotent(self, key: str, ttl: int = 300) -> bool:
        """抢占幂等键，返回 True 表示首次执行。"""
        full = self._key(f"idem:{key}")
        if self._redis_healthy and self._redis is not None:
            try:
                return bool(self._redis.set(full, "1", nx=True, ex=ttl))
            except Exception:
                self._redis_healthy = False
        if self._memory.exists(full):
            return False
        self._memory.set(full, "1", ttl)
        return True


cache = Cache()
