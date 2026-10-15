# -*- coding: utf-8 -*-
"""认证、权限与数据隔离测试。"""
from __future__ import annotations

from tests.conftest import ADMIN, BUYER, SUPPLIER, auth_headers, login, unwrap


def test_health_and_ready(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["database"] == "up"
    assert body["cache"] in ("memory", "redis")
    assert body["storage"] in ("local", "minio")


def test_root_endpoint(client):
    body = client.get("/").json()
    assert body["docs"] == "/api/docs"
    assert body["console"] == "/console/"


def test_login_success_returns_profile(client):
    data = login(client, *ADMIN)
    assert data["access_token"] and data["refresh_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    user = data["user"]
    assert user["username"] == "admin"
    assert user["is_superuser"] is True
    assert "platform_admin" in user["roles"]
    assert "merchant:write" in user["permissions"]


def test_login_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 40100
    assert "密码" in body["message"]


def test_login_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "not-exist", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == 40100


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_token(client, admin_headers):
    data = unwrap(client.get("/api/v1/auth/me", headers=admin_headers))
    assert data["username"] == "admin"
    assert len(data["permissions"]) > 10


def test_refresh_token_flow(client):
    data = login(client, *ADMIN)
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    body = unwrap(response)
    assert body["access_token"] != data["access_token"]
    # 旧刷新令牌已被拉黑（旋转）
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert again.status_code == 401
    assert again.json()["code"] == 40102


def test_logout_blacklists_token(client):
    data = login(client, *SUPPLIER)
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    assert unwrap(client.post("/api/v1/auth/logout", headers=headers))["revoked"] is True
    after = client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


def test_change_password_and_restore(client):
    # 使用独立账号验证，避免影响其他测试
    admin = auth_headers(client, ADMIN)
    created = unwrap(
        client.post(
            "/api/v1/users",
            headers=admin,
            json={"username": "pwd_test_user", "password": "Test@123456", "full_name": "改密测试"},
        )
    )
    user_id = created["id"]
    headers = auth_headers(client, ("pwd_test_user", "Test@123456"))

    weak = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "Test@123456", "new_password": "12345678"},
    )
    assert weak.status_code == 400

    wrong_old = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "bad-old", "new_password": "Newpass@123"},
    )
    assert wrong_old.status_code == 400

    ok_response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "Test@123456", "new_password": "Newpass@123"},
    )
    assert unwrap(ok_response)["updated"] is True

    login(client, "pwd_test_user", "Newpass@123")
    client.delete(f"/api/v1/users/{user_id}", headers=admin)


def test_permission_denied_for_buyer(client, buyer_headers):
    # 采购商没有用户管理权限
    response = client.get("/api/v1/users", headers=buyer_headers)
    assert response.status_code == 403
    assert response.json()["code"] == 40003


def test_buyer_cannot_write_product(client, buyer_headers):
    categories = unwrap(client.get("/api/v1/categories/tree", headers=buyer_headers))
    assert categories
    response = client.post(
        "/api/v1/products",
        headers=buyer_headers,
        json={"name": "越权商品", "category_id": categories[0]["id"]},
    )
    assert response.status_code == 403


def test_enterprise_data_isolation(client, supplier_headers, buyer_headers):
    supplier_view = unwrap(client.get("/api/v1/enterprises", headers=supplier_headers))
    buyer_view = unwrap(client.get("/api/v1/enterprises", headers=buyer_headers))
    admin_view = unwrap(
        client.get("/api/v1/enterprises", headers=auth_headers(client, ADMIN))
    )
    assert supplier_view["total"] == 1
    assert buyer_view["total"] == 1
    assert admin_view["total"] >= 4

    supplier_id = supplier_view["items"][0]["id"]
    buyer_id = buyer_view["items"][0]["id"]
    assert supplier_id != buyer_id
    # 越权访问其他企业详情
    response = client.get(f"/api/v1/enterprises/{buyer_id}", headers=supplier_headers)
    assert response.status_code == 403


def test_role_and_permission_endpoints(client, admin_headers):
    roles = unwrap(client.get("/api/v1/roles", headers=admin_headers))
    codes = {row["code"] for row in roles}
    assert {"platform_admin", "park_operator", "merchant", "supplier", "buyer", "finance"} <= codes

    groups = unwrap(client.get("/api/v1/permissions", headers=admin_headers))
    assert len(groups) >= 8
    modules = {group["module"] for group in groups}
    assert {"user", "merchant", "product", "inventory", "trade", "settlement"} <= modules

    platform_admin = next(row for row in roles if row["code"] == "platform_admin")
    assert platform_admin["is_system"] is True
    assert len(platform_admin["permission_codes"]) >= 20
    # 系统内置角色不可删除
    assert client.delete(
        f"/api/v1/roles/{platform_admin['id']}", headers=admin_headers
    ).status_code == 403


def test_org_unit_tree(client, admin_headers):
    tree = unwrap(client.get("/api/v1/org-units/tree", headers=admin_headers))
    assert tree
    root = tree[0]
    assert root["unit_type"] == "platform"
    assert root["children"], "平台下应挂载园区组织"
    park_node = root["children"][0]
    assert park_node["unit_type"] == "park"
    assert park_node["children"], "园区下应挂载企业组织"
