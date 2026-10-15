# -*- coding: utf-8 -*-
"""pytest 公共夹具。

默认使用 SQLite 内存库（StaticPool）运行，无需外部依赖；
如设置 `TEST_DATABASE_URL` 则改用该库（可用于 PostgreSQL 回归验证）。
"""
from __future__ import annotations

import os
import shutil
import tempfile

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", "sqlite://"))
os.environ.setdefault("REDIS_ENABLED", "0")
os.environ.setdefault("ELASTICSEARCH_ENABLED", "0")
os.environ.setdefault("MINIO_ENABLED", "0")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("INTEGRATION_SECRET", "test-integration-secret")
os.environ.setdefault("PASSWORD_PBKDF2_ROUNDS", "1000")  # 测试加速
os.environ.setdefault("LOCAL_STORAGE_DIR", os.path.join(tempfile.gettempdir(), "gz-test-uploads"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import initial_data  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = ("admin", "Admin@123")
SUPPLIER = ("jinsui", "Gz@123456")
MERCHANT = ("fengyuan", "Gz@123456")
BUYER = ("gongxiao", "Gz@123456")
BUYER2 = ("xiyujianuo", "Gz@123456")
PARK = ("park01", "Gz@123456")


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    init_db(drop=True)
    initial_data.run(reset=False, demo=True)
    yield
    shutil.rmtree(os.environ["LOCAL_STORAGE_DIR"], ignore_errors=True)


@pytest.fixture(scope="session")
def client(_prepare_database) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def auth_headers(client: TestClient, account: tuple) -> dict:
    data = login(client, account[0], account[1])
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client: TestClient) -> dict:
    return auth_headers(client, ADMIN)


@pytest.fixture(scope="session")
def supplier_headers(client: TestClient) -> dict:
    return auth_headers(client, SUPPLIER)


@pytest.fixture(scope="session")
def merchant_headers(client: TestClient) -> dict:
    return auth_headers(client, MERCHANT)


@pytest.fixture(scope="session")
def buyer_headers(client: TestClient) -> dict:
    return auth_headers(client, BUYER)


@pytest.fixture(scope="session")
def buyer2_headers(client: TestClient) -> dict:
    return auth_headers(client, BUYER2)


@pytest.fixture(scope="session")
def park_headers(client: TestClient) -> dict:
    return auth_headers(client, PARK)


def unwrap(response, expected_status: int = 200):
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]
