"""Run inside the API container; print checks without exposing credentials."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from app.core.database import get_session_factory
from app.models.enterprise import Enterprise
from app.models.product import Inventory, Product, Warehouse
from app.models.trade import TradeOrder


def post(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


with get_session_factory()() as db:
    counts = {
        "enterprises": db.query(Enterprise).count(),
        "products": db.query(Product).count(),
        "warehouses": db.query(Warehouse).count(),
        "inventories": db.query(Inventory).count(),
        "orders": db.query(TradeOrder).count(),
    }
print("database_counts", counts)

status, body = post(
    "http://127.0.0.1:8000/api/v1/auth/login",
    {"username": "admin", "password": os.environ["INITIAL_ADMIN_PASSWORD"]},
)
print("platform_admin_login", status, bool(body.get("access_token") or body.get("data", {}).get("access_token")))

status, body = post(
    os.environ["ODOO_BASE_URL"] + "/web/session/authenticate",
    {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "db": os.environ["ODOO_DB"],
            "login": os.environ["ODOO_USER"],
            "password": os.environ["ODOO_PASSWORD"],
        },
    },
)
print("odoo_admin_auth", status, bool(body.get("result", {}).get("uid")))
