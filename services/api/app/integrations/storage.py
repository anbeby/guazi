# -*- coding: utf-8 -*-
"""对象存储适配器：优先 MinIO，不可用时降级为本地磁盘（ADR-06）。

两种后端对外暴露同一组方法，业务层无需感知差异。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Dict, Optional, Tuple

from app.core.config import settings

try:  # pragma: no cover
    from minio import Minio
    from minio.error import S3Error
except Exception:  # pragma: no cover
    Minio = None  # type: ignore
    S3Error = Exception  # type: ignore

BUCKETS = {
    "product": "gz-product",
    "report": "gz-report",
    "contract": "gz-contract",
    "trace": "gz-trace",
    "default": "gz-product",
}


class Storage:
    def __init__(self) -> None:
        self._client = None
        self._healthy = False
        self._local_root = Path(settings.LOCAL_STORAGE_DIR).resolve()
        self.connect()

    # ------------------------------------------------------------------ 连接
    def connect(self) -> None:
        if not settings.MINIO_ENABLED or Minio is None:
            self._client = None
            self._healthy = False
            return
        try:
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            # 触发一次真实调用以确认可用
            client.bucket_exists(settings.MINIO_BUCKET)
            self._client = client
            self._healthy = True
        except Exception:
            self._client = None
            self._healthy = False

    @property
    def backend(self) -> str:
        return "minio" if self._healthy else "local"

    def status(self) -> Dict[str, object]:
        return {
            "backend": self.backend,
            "endpoint": settings.MINIO_ENDPOINT,
            "bucket": settings.MINIO_BUCKET,
            "local_root": str(self._local_root),
        }

    # ------------------------------------------------------------------ 读写
    def _ensure_bucket(self, bucket: str) -> None:
        if self._client is None:
            return
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
        except Exception:
            self._healthy = False
            self._client = None

    def save(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: Optional[str] = None,
    ) -> Tuple[str, str]:
        """保存对象，返回 (backend, object_name)。"""
        bucket = bucket or settings.MINIO_BUCKET
        if self._healthy and self._client is not None:
            try:
                self._ensure_bucket(bucket)
                from io import BytesIO

                self._client.put_object(
                    bucket, object_name, BytesIO(data), length=len(data), content_type=content_type
                )
                return "minio", object_name
            except Exception:
                self._healthy = False
                self._client = None
        target = self._local_root / bucket / object_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return "local", object_name

    def open_stream(self, object_name: str, bucket: Optional[str] = None) -> Optional[BinaryIO]:
        bucket = bucket or settings.MINIO_BUCKET
        if self._healthy and self._client is not None:
            try:
                response = self._client.get_object(bucket, object_name)
                return response  # type: ignore[return-value]
            except Exception:
                self._healthy = False
                self._client = None
        target = self._local_root / bucket / object_name
        if not target.exists():
            return None
        return target.open("rb")

    def local_path(self, object_name: str, bucket: Optional[str] = None) -> Optional[Path]:
        bucket = bucket or settings.MINIO_BUCKET
        target = self._local_root / bucket / object_name
        return target if target.exists() else None

    def delete(self, object_name: str, bucket: Optional[str] = None) -> None:
        bucket = bucket or settings.MINIO_BUCKET
        if self._healthy and self._client is not None:
            try:
                self._client.remove_object(bucket, object_name)
                return
            except Exception:
                self._healthy = False
                self._client = None
        target = self._local_root / bucket / object_name
        if target.exists():
            target.unlink()

    def ensure_local_dirs(self) -> None:
        for bucket in set(BUCKETS.values()):
            (self._local_root / bucket).mkdir(parents=True, exist_ok=True)


storage = Storage()
