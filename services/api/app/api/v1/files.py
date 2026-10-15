# -*- coding: utf-8 -*-
"""文件接口：上传（MinIO / 本地磁盘可降级）、列表、下载。"""
from __future__ import annotations

import mimetypes
import os
import secrets
from urllib.parse import quote
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require
from app.core.errors import BadRequest, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.timeutil import now
from app.integrations.storage import BUCKETS, storage
from app.models.org import User
from app.models.system import SysFile

router = APIRouter(prefix="/files", tags=["文件"])


def _safe_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if not ext:
        return ""
    if ext not in settings.ALLOWED_UPLOAD_EXT:
        raise BadRequest(f"不支持的文件类型：{ext}")
    return ext


@router.post("/upload", response_model=ApiResponse[dict], summary="上传文件")
async def upload_file(
    file: UploadFile = File(...),
    biz_type: str = Form("product"),
    biz_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ext = _safe_ext(file.filename or "")
    content = await file.read()
    if not content:
        raise BadRequest("上传文件为空")
    if len(content) > settings.UPLOAD_MAX_SIZE:
        raise BadRequest(f"文件超过大小限制 {settings.UPLOAD_MAX_SIZE // 1024 // 1024} MB")
    file_key = secrets.token_hex(16)
    bucket = BUCKETS.get(biz_type, BUCKETS["default"])
    object_name = f"{date.today().isoformat()}/{file_key}{ext}"
    content_type = (
        file.content_type if file.content_type and file.content_type != "application/octet-stream"
        else mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    )
    backend, stored_name = storage.save(object_name, content, content_type, bucket)
    record = SysFile(
        file_key=file_key,
        bucket=bucket,
        original_name=file.filename or stored_name,
        object_name=stored_name,
        content_type=content_type,
        size=len(content),
        biz_type=biz_type,
        biz_id=biz_id,
        uploader_id=user.id,
        storage=backend,
        url=f"{settings.STORAGE_PUBLIC_BASE}/{file_key}/download",
    )
    db.add(record)
    db.flush()
    return ok(
        {
            "file_key": file_key,
            "original_name": record.original_name,
            "size": record.size,
            "content_type": content_type,
            "storage": backend,
            "url": record.url,
        }
    )


@router.get("", response_model=ApiResponse[PageData[dict]], summary="文件列表")
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    biz_type: Optional[str] = None,
    biz_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require("user:read", "product:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(SysFile)
    if biz_type:
        query = query.filter(SysFile.biz_type == biz_type)
    if biz_id:
        query = query.filter(SysFile.biz_id == biz_id)
    total = query.count()
    rows = query.order_by(SysFile.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "file_key": row.file_key,
            "original_name": row.original_name,
            "size": row.size,
            "content_type": row.content_type,
            "biz_type": row.biz_type,
            "biz_id": row.biz_id,
            "storage": row.storage,
            "url": row.url,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return ok(paginate(items, total, page, page_size))


@router.get("/{file_key}/download", summary="下载文件")
def download_file(
    file_key: str,
    db: Session = Depends(get_db),
) -> Response:
    record = db.query(SysFile).filter(SysFile.file_key == file_key).first()
    if record is None:
        raise NotFound("文件不存在")
    stream = storage.open_stream(record.object_name, record.bucket)
    if stream is None:
        raise NotFound("文件已丢失")
    filename = record.original_name or record.object_name
    headers = {
        "Content-Disposition": f"inline; filename=download; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "public, max-age=86400",
    }
    return StreamingResponse(
        stream,
        media_type=record.content_type or "application/octet-stream",
        headers=headers,
    )


@router.get("/storage-status", response_model=ApiResponse[dict], summary="存储后端状态")
def storage_status(_: User = Depends(get_current_user)) -> dict:
    return ok(storage.status())
