"""企业展示图关联，复用 sys_file，避免改动企业主数据表。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.system import SysFile


def enterprise_image_urls(db: Session, enterprise_ids: list[int]) -> dict[int, str]:
    if not enterprise_ids:
        return {}
    files = (
        db.query(SysFile)
        .filter(SysFile.biz_type == "enterprise_image", SysFile.biz_id.in_(enterprise_ids))
        .order_by(SysFile.id.desc())
        .all()
    )
    result: dict[int, str] = {}
    for file in files:
        if file.biz_id is not None and file.url:
            result.setdefault(file.biz_id, file.url)
    return result
