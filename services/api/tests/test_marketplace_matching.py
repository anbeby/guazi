# -*- coding: utf-8 -*-
"""V1.1 供应展示、采购需求、企业意向与平台人工撮合。"""
from __future__ import annotations

from tests.conftest import unwrap


def test_marketplace_flow_and_public_contact_boundary(client, admin_headers, supplier_headers, buyer_headers, buyer2_headers, park_headers):
    supply = unwrap(client.get("/api/v1/marketplace/supplies"))
    assert supply["total"] >= 1
    assert all(item["supply_status"] == "active" for item in supply["items"])
    assert len({item["image"] for item in supply["items"]}) >= 2
    product = supply["items"][0]
    assert product["enterprise_id"] and product["origin"]
    detail = unwrap(client.get(f"/api/v1/marketplace/supplies/{product['id']}"))
    assert detail["name"] == product["name"]
    company = unwrap(client.get(f"/api/v1/marketplace/enterprises/{product['enterprise_id']}"))
    assert company["name"] == product["enterprise"]
    assert isinstance(company["qualifications"], list)

    payload = {
        "title": "采购北屯葵花籽原料",
        "product_name": "葵花籽原料",
        "quantity": 200,
        "unit": "ton",
        "requirements": "清选，水分不高于 10%",
        "purchase_region": "新疆北屯",
        "contact_name": "采购联系人",
        "contact_phone": "13900000001",
    }
    assert client.post("/api/v1/marketplace/requirements", json=payload).status_code == 401
    created = unwrap(client.post("/api/v1/marketplace/requirements", headers=buyer_headers, json=payload))
    requirement_id = created["id"]
    assert created["contact_phone"] == payload["contact_phone"]
    assert created["status"] == "pending"
    assert not any(item["id"] == requirement_id for item in unwrap(client.get("/api/v1/marketplace/requirements"))["items"])
    unwrap(client.put(f"/api/v1/marketplace/operations/requirements/{requirement_id}",
                      headers=admin_headers, json={"status": "open"}))

    public = unwrap(client.get("/api/v1/marketplace/requirements"))
    posted = next(item for item in public["items"] if item["id"] == requirement_id)
    assert posted["quantity"] == 200
    assert "contact_phone" not in posted and "contact_name" not in posted
    assert client.post(f"/api/v1/marketplace/requirements/{requirement_id}/interest", headers=buyer_headers).status_code == 403
    assert client.post(f"/api/v1/marketplace/requirements/{requirement_id}/interest", headers=buyer2_headers).status_code == 403

    interest = unwrap(client.post(f"/api/v1/marketplace/requirements/{requirement_id}/interest", headers=supplier_headers))
    case_id = interest["id"]
    assert interest["status"] == "pending"
    assert client.post(f"/api/v1/marketplace/requirements/{requirement_id}/interest", headers=supplier_headers).status_code == 409
    assert client.get("/api/v1/marketplace/operations/matches", headers=park_headers).status_code == 403

    board = unwrap(client.get("/api/v1/marketplace/operations/summary", headers=admin_headers))
    assert board["requirement_count"] >= 1 and board["pending_matches"] >= 1
    pool = unwrap(client.get("/api/v1/marketplace/operations/requirements", headers=admin_headers))
    private = next(item for item in pool["items"] if item["id"] == requirement_id)
    assert private["contact_phone"] == payload["contact_phone"]
    cases = unwrap(client.get("/api/v1/marketplace/operations/matches", headers=admin_headers))
    assert any(item["id"] == case_id for item in cases["items"])

    followup = unwrap(client.post(f"/api/v1/marketplace/operations/matches/{case_id}/followups", headers=admin_headers, json={"note": "已联系供应企业，待核对规格"}))
    assert followup["id"]
    assert client.put(f"/api/v1/marketplace/operations/matches/{case_id}", headers=admin_headers, json={"status": "success"}).status_code == 400
    completed = unwrap(client.put(f"/api/v1/marketplace/operations/matches/{case_id}", headers=admin_headers, json={"status": "success", "result": "双方完成商务对接，后续线下洽谈"}))
    assert completed["status"] == "success"
    assert completed["followups"][0]["note"] == followup["note"]
    assert client.post(f"/api/v1/marketplace/operations/matches/{case_id}/followups", headers=admin_headers, json={"note": "再次联系"}).status_code == 409
    assert client.put(f"/api/v1/marketplace/operations/matches/{case_id}", headers=admin_headers, json={"status": "matching"}).status_code == 409
    closed = unwrap(client.put(f"/api/v1/marketplace/operations/requirements/{requirement_id}", headers=admin_headers, json={"status": "closed"}))
    assert closed["status"] == "closed"
    assert not any(item["id"] == requirement_id for item in unwrap(client.get("/api/v1/marketplace/requirements"))["items"])
    reopened = unwrap(client.put(f"/api/v1/marketplace/operations/requirements/{requirement_id}", headers=admin_headers, json={"status": "open"}))
    assert reopened["status"] == "open"


def test_manual_match_rejects_buyer_as_supplier(client, admin_headers, buyer_headers):
    requirement = unwrap(client.post("/api/v1/marketplace/requirements", headers=buyer_headers, json={
        "title": "采购优质瓜子仁", "product_name": "瓜子仁", "quantity": 20,
        "contact_name": "采购联系人", "contact_phone": "13900000002",
    }))
    unwrap(client.put(f"/api/v1/marketplace/operations/requirements/{requirement['id']}",
                      headers=admin_headers, json={"status": "open"}))
    buyer_id = unwrap(client.get("/api/v1/auth/me", headers=buyer_headers))["enterprise_id"]
    response = client.post(f"/api/v1/marketplace/operations/matches?requirement_id={requirement['id']}", headers=admin_headers, json={"supplier_enterprise_id": buyer_id})
    assert response.status_code == 400


def test_company_profile_and_paused_supply(client, admin_headers, buyer_headers):
    supply = unwrap(client.get("/api/v1/marketplace/supplies"))["items"][0]
    enterprise_id = supply["enterprise_id"]
    updated = unwrap(client.put(f"/api/v1/enterprises/{enterprise_id}", headers=admin_headers, json={
        "profile": "第十师北屯瓜子油料供应企业",
        "qualifications": ["食品生产许可", "农产品质量检测"],
    }))
    assert updated["profile"] == "第十师北屯瓜子油料供应企业"
    public = unwrap(client.get(f"/api/v1/marketplace/enterprises/{enterprise_id}"))
    assert public["qualifications"] == ["食品生产许可", "农产品质量检测"]

    from app.core.database import get_session_factory
    from app.models.product import Product
    db = get_session_factory()()
    try:
        product = db.get(Product, supply["id"])
        product.supply_status = "paused"
        db.commit()
        assert not any(item["id"] == product.id for item in unwrap(client.get("/api/v1/marketplace/supplies"))["items"])
        response = client.post("/api/v1/inquiries", headers=buyer_headers, json={
            "product_id": product.id, "supplier_enterprise_id": enterprise_id,
            "quantity": 5, "unit": product.unit, "submit": True,
        })
        assert response.status_code == 400
    finally:
        product.supply_status = "active"
        db.commit()
        db.close()
