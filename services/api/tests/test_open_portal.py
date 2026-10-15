# -*- coding: utf-8 -*-
"""开放留资、普通用户、企业认证与运营线索的权限边界。"""
from __future__ import annotations

from uuid import uuid4

from tests.conftest import unwrap


def test_guest_lead_supplier_response_and_operator_close(client, admin_headers, supplier_headers, merchant_headers, buyer_headers):
    supplier_id = unwrap(client.get("/api/v1/auth/me", headers=supplier_headers))["enterprise_id"]
    supply = next(item for item in unwrap(client.get("/api/v1/marketplace/supplies?page_size=60"))["items"]
                  if item["enterprise_id"] == supplier_id)
    lead = unwrap(client.post("/api/v1/portal/leads", json={
        "product_id": supply["id"], "contact_name": "采购访客", "contact_phone": "13911223344",
        "need_content": "咨询北屯瓜子原料规格及近期供货周期", "quantity": 15,
    }))
    assert lead["status"] == "new"
    assert client.get("/api/v1/portal/operations/leads").status_code == 401
    assert client.get("/api/v1/portal/operations/leads", headers=buyer_headers).status_code == 403
    assert client.get("/api/v1/portal/me/leads").status_code == 401

    enterprise_leads = unwrap(client.get("/api/v1/portal/me/enterprise-leads", headers=supplier_headers))["items"]
    assert any(item["id"] == lead["id"] for item in enterprise_leads)
    response = unwrap(client.post(f"/api/v1/portal/me/enterprise-leads/{lead['id']}/response",
                                  headers=supplier_headers, json={"note": "已确认库存，待进一步沟通规格"}))
    assert response["status"] == "following"
    assert client.post(f"/api/v1/portal/me/enterprise-leads/{lead['id']}/response",
                       headers=buyer_headers, json={"note": "无权操作"}).status_code == 404

    board = unwrap(client.get("/api/v1/portal/operations/leads", headers=admin_headers))["items"]
    assert any(item["id"] == lead["id"] and item["contact_phone"] == "13911223344" for item in board)
    buyer_id = unwrap(client.get("/api/v1/auth/me", headers=buyer_headers))["enterprise_id"]
    assert client.put(f"/api/v1/portal/operations/leads/{lead['id']}", headers=admin_headers,
                      json={"status": "following", "supplier_enterprise_id": buyer_id}).status_code == 400
    merchant_id = unwrap(client.get("/api/v1/auth/me", headers=merchant_headers))["enterprise_id"]
    assigned = unwrap(client.put(f"/api/v1/portal/operations/leads/{lead['id']}", headers=admin_headers,
                                 json={"status": "following", "supplier_enterprise_id": merchant_id}))
    assert assigned["supplier_enterprise_id"] == merchant_id
    assert not any(item["id"] == lead["id"] for item in
                   unwrap(client.get("/api/v1/portal/me/enterprise-leads", headers=supplier_headers))["items"])
    assert any(item["id"] == lead["id"] for item in
               unwrap(client.get("/api/v1/portal/me/enterprise-leads", headers=merchant_headers))["items"])
    assert client.put(f"/api/v1/portal/operations/leads/{lead['id']}", headers=admin_headers,
                      json={"status": "completed"}).status_code == 400
    completed = unwrap(client.put(f"/api/v1/portal/operations/leads/{lead['id']}", headers=admin_headers,
                                  json={"status": "completed", "result": "已促成双方线下商务对接"}))
    assert completed["status"] == "completed"


def test_registration_favorite_enterprise_review_and_requirement_review(client, admin_headers):
    username = f"portal_{uuid4().hex[:9]}"
    registered = unwrap(client.post("/api/v1/auth/register", json={
        "username": username, "password": "Portal@1234", "full_name": "平台注册访客",
    }))
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    assert registered["user"]["roles"] == ["user"]
    assert registered["user"]["permissions"] == []
    assert client.post("/api/v1/auth/register", json={"username": username, "password": "Portal@1234"}).status_code == 409
    supply = unwrap(client.get("/api/v1/marketplace/supplies"))["items"][0]
    unwrap(client.post(f"/api/v1/portal/me/favorites/{supply['id']}", headers=headers))
    assert unwrap(client.get("/api/v1/portal/me/favorites", headers=headers))["total"] == 1
    unwrap(client.delete(f"/api/v1/portal/me/favorites/{supply['id']}", headers=headers))
    assert unwrap(client.get("/api/v1/portal/me/favorites", headers=headers))["total"] == 0

    own_lead = unwrap(client.post("/api/v1/portal/leads", headers=headers, json={
        "intent_product": "北屯南瓜籽", "contact_name": "平台注册访客",
        "contact_phone": "13911223345", "need_content": "计划采购三十吨北屯南瓜籽原料",
    }))
    assert any(row["id"] == own_lead["id"] for row in unwrap(client.get("/api/v1/portal/me/leads", headers=headers))["items"])
    assert client.post("/api/v1/marketplace/requirements", headers=headers, json={
        "title": "采购南瓜籽原料", "product_name": "南瓜籽", "quantity": 30,
        "contact_name": "平台注册访客", "contact_phone": "13911223345",
    }).status_code == 403

    company = unwrap(client.post("/api/v1/portal/me/enterprise", headers=headers, json={
        "name": f"北屯合作企业{username}", "enterprise_type": "supplier",
        "profile": "第十师北屯瓜子油料原料供应", "business_scope": "瓜子油料收购与供应",
        "contact_name": "企业联系人", "contact_phone": "13911223345",
    }))
    assert company["audit_status"] == "pending"
    assert client.get("/api/v1/portal/me/enterprise-leads", headers=headers).status_code == 403
    assert client.post("/api/v1/marketplace/requirements", headers=headers, json={
        "title": "采购南瓜籽原料", "product_name": "南瓜籽", "quantity": 30,
        "contact_name": "企业联系人", "contact_phone": "13911223345",
    }).status_code == 403
    approved = unwrap(client.post(f"/api/v1/enterprises/{company['id']}/audit", headers=admin_headers,
                                  json={"approved": True}))
    assert approved["audit_status"] == "approved"
    assert "supplier" in unwrap(client.get("/api/v1/auth/me", headers=headers))["roles"]
    updated = unwrap(client.put("/api/v1/portal/me/enterprise", headers=headers,
                                json={"profile": "北屯瓜子油料产地供应与加工协同"}))
    assert "产地供应" in updated["profile"]

    need = unwrap(client.post("/api/v1/marketplace/requirements", headers=headers, json={
        "title": "采购南瓜籽原料", "product_name": "南瓜籽", "quantity": 30,
        "contact_name": "企业联系人", "contact_phone": "13911223345",
    }))
    assert need["status"] == "pending"
    assert not any(row["id"] == need["id"] for row in unwrap(client.get("/api/v1/marketplace/requirements"))["items"])
    assert any(row["id"] == need["id"] for row in unwrap(client.get("/api/v1/portal/me/requirements", headers=headers))["items"])
    unwrap(client.put(f"/api/v1/marketplace/operations/requirements/{need['id']}",
                      headers=admin_headers, json={"status": "open"}))
    assert any(row["id"] == need["id"] for row in unwrap(client.get("/api/v1/marketplace/requirements"))["items"])
