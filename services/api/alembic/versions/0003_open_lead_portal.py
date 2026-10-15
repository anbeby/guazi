# -*- coding: utf-8 -*-
"""开放留资、线索跟进和个人收藏。"""
from __future__ import annotations

from alembic import op

from app.core.database import Base
import app.models  # noqa: F401

revision = "0003_open_lead_portal"
down_revision = "0002_marketplace_matching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for name in ("match_lead", "lead_followup", "product_favorite"):
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for name in ("product_favorite", "lead_followup", "match_lead"):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
