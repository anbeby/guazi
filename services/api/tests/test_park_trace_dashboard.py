# -*- coding: utf-8 -*-
"""园区、溯源、数据驾驶舱与文件上传测试。"""
from __future__ import annotations

from tests.conftest import unwrap


# --------------------------------------------------------------------------- 园区


def test_park_and_zone_crud(client, admin_headers, park_headers):
    parks = unwrap(client.get("/api/v1/parks", headers=admin_headers))
    assert parks["total"] >= 1
    park = parks["items"][0]
    assert park["zone_count"] >= 4
    assert park["stall_count"] >= 40
    park_id = park["id"]

    # 园区运营人员按园区隔离，可见同一园区
    park_view = unwrap(client.get("/api/v1/parks", headers=park_headers))
    assert park_view["total"] == 1
    assert park_view["items"][0]["id"] == park_id

    zones = unwrap(client.get(f"/api/v1/parks/{park_id}/zones", headers=admin_headers))
    assert {zone["zone_type"] for zone in zones} >= {"trade", "processing", "logistics", "service"}

    new_zone = unwrap(
        client.post(
            f"/api/v1/parks/{park_id}/zones",
            headers=admin_headers,
            json={"code": "Z-TEST", "name": "测试区", "zone_type": "trade", "area": 100},
        )
    )
    assert new_zone["stall_count"] == 0
    assert client.post(
        f"/api/v1/parks/{park_id}/zones",
        headers=admin_headers,
        json={"code": "Z-TEST", "name": "重复编码区"},
    ).status_code == 409

    updated = unwrap(
        client.put(
            f"/api/v1/zones/{new_zone['id']}",
            headers=admin_headers,
            json={"code": "Z-TEST", "name": "测试区（改名）"},
        )
    )
    assert updated["updated"] is True
    assert unwrap(
        client.delete(f"/api/v1/zones/{new_zone['id']}", headers=admin_headers)
    )["deleted"] is True


def test_park_contract_effect_and_stall_assign(client, admin_headers, supplier_headers):
    park = unwrap(client.get("/api/v1/parks", headers=admin_headers))["items"][0]
    supplier_id = unwrap(client.get("/api/v1/auth/me", headers=supplier_headers))["enterprise_id"]

    stalls = unwrap(
        client.get("/api/v1/stalls", headers=admin_headers, params={"status": "free", "page_size": 5})
    )
    assert stalls["total"] >= 1
    stall = stalls["items"][0]

    contract = unwrap(
        client.post(
            "/api/v1/park-contracts",
            headers=admin_headers,
            json={
                "park_id": park["id"],
                "stall_id": stall["id"],
                "enterprise_id": supplier_id,
                "start_date": "2025-01-01",
                "end_date": "2027-12-31",
                "rent_amount": 36000,
                "deposit_amount": 3000,
                "fee_cycle": "year",
                "remark": "测试入驻合同",
            },
        )
    )
    assert contract["contract_no"].startswith("GZ-PC-")
    assert contract["status"] == "draft"

    effective = unwrap(
        client.post(f"/api/v1/park-contracts/{contract['id']}/effect", headers=admin_headers)
    )
    assert effective["status"] == "effective"
    assert client.post(
        f"/api/v1/park-contracts/{contract['id']}/effect", headers=admin_headers
    ).status_code == 409

    stall_after = unwrap(client.get(f"/api/v1/stalls/{stall['id']}", headers=admin_headers))
    assert stall_after["status"] == "rented"
    assert stall_after["enterprise_id"] == supplier_id

    released = unwrap(
        client.post(
            f"/api/v1/stalls/{stall['id']}/assign", headers=admin_headers, json={"enterprise_id": None}
        )
    )
    assert released["status"] == "free"
    assert released["enterprise_id"] is None


# --------------------------------------------------------------------------- 溯源


def test_trace_batch_and_public_lookup(client, admin_headers, supplier_headers):
    tree = unwrap(client.get("/api/v1/categories/tree", headers=supplier_headers))
    category = next(node for root in tree for node in root.get("children", []) if node["code"] == "GZ-SUN")
    product = unwrap(
        client.post(
            "/api/v1/products",
            headers=supplier_headers,
            json={
                "name": "溯源测试葵花籽",
                "category_id": category["id"],
                "grade": "special",
                "origin": "新疆北屯",
                "harvest_year": "2025",
                "unit": "ton",
                "price": 6600,
            },
        )
    )

    batch = unwrap(
        client.post(
            "/api/v1/trace/batches",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "quantity": 100,
                "origin_base": "第十师一八三团葵花籽种植基地",
                "origin_region": "新疆北屯",
                "plant_date": "2025-04-20",
                "harvest_date": "2025-08-25",
                "process_enterprise": "北屯金穗瓜子有限公司",
                "process_date": "2025-09-01",
                "quality_status": "qualified",
                "test_report_url": "/api/v1/files/demo-report/download",
            },
        )
    )
    assert batch["batch_no"].startswith("GZ-BATCH-")
    assert batch["event_count"] == 1
    batch_id = batch["id"]

    unwrap(
        client.post(
            f"/api/v1/trace/batches/{batch_id}/events",
            headers=supplier_headers,
            json={
                "stage": "planting",
                "title": "基地播种",
                "description": "4 月 20 日完成播种，选用食葵品种",
                "location": "第十师一八三团",
                "operator": "种植户张师傅",
            },
        )
    )
    invalid_stage = client.post(
        f"/api/v1/trace/batches/{batch_id}/events",
        headers=supplier_headers,
        json={"stage": "unknown", "title": "非法阶段"},
    )
    assert invalid_stage.status_code == 409

    detail = unwrap(client.get(f"/api/v1/trace/batches/{batch_id}", headers=supplier_headers))
    assert len(detail["events"]) == 2
    stages = {event["stage"] for event in detail["events"]}
    assert {"warehouse", "planting"} <= stages

    # 扫码公开查询（免鉴权）
    public = client.get(f"/api/v1/trace/public/{batch['batch_no']}")
    assert public.status_code == 200
    body = public.json()
    assert body["verified"] is True
    assert body["product_name"] == "溯源测试葵花籽"
    assert body["enterprise_name"]
    assert body["test_report_url"]
    assert len(body["events"]) == 2

    missing = client.get("/api/v1/trace/public/NOT-EXIST-BATCH").json()
    assert missing["verified"] is False
    assert "未查询到" in missing["message"]


# --------------------------------------------------------------------------- 驾驶舱


def test_dashboard_endpoints(client, admin_headers):
    overview = unwrap(
        client.get("/api/v1/dashboard/overview", headers=admin_headers, params={"refresh": True})
    )
    for field in (
        "enterprise_count",
        "merchant_count",
        "supplier_count",
        "buyer_count",
        "product_count",
        "published_product_count",
        "inventory_quantity",
        "inventory_value",
        "order_count",
        "order_amount",
        "park_count",
        "stall_count",
        "stall_rented",
        "stall_rented_rate",
        "pending_audit_enterprise",
        "pending_audit_product",
        "unsettled_amount",
    ):
        assert field in overview, f"缺少指标字段 {field}"
    assert overview["enterprise_count"] >= 4
    assert overview["product_count"] >= 5
    assert overview["stall_count"] >= 40
    assert 0 <= overview["stall_rented_rate"] <= 1

    trend = unwrap(
        client.get("/api/v1/dashboard/trend", headers=admin_headers, params={"days": 14})
    )
    assert len(trend["dates"]) == 14
    assert len(trend["order_count"]) == 14
    assert sum(trend["order_count"]) >= 1
    assert sum(trend["order_amount"]) > 0

    price = unwrap(
        client.get("/api/v1/dashboard/price-trend", headers=admin_headers, params={"days": 14})
    )
    assert len(price["dates"]) == 14
    assert len(price["avg_price"]) == 14

    industry = unwrap(client.get("/api/v1/dashboard/industry", headers=admin_headers))
    assert industry["by_category"]
    assert industry["by_grade"]
    assert industry["by_origin"]

    ranking = unwrap(
        client.get(
            "/api/v1/dashboard/ranking",
            headers=admin_headers,
            params={"dimension": "enterprise", "metric": "amount"},
        )
    )
    assert ranking["items"]
    assert ranking["items"][0]["rank"] == 1

    settlement = unwrap(client.get("/api/v1/dashboard/settlement-summary", headers=admin_headers))
    assert settlement["settlement_count"] >= 1
    assert 0 <= settlement["settle_rate"] <= 1


def test_dashboard_scope_for_enterprise_user(client, supplier_headers, admin_headers):
    supplier_overview = unwrap(client.get("/api/v1/dashboard/overview", headers=supplier_headers))
    admin_overview = unwrap(
        client.get("/api/v1/dashboard/overview", headers=admin_headers, params={"refresh": True})
    )
    assert supplier_overview["enterprise_count"] <= admin_overview["enterprise_count"]
    assert supplier_overview["product_count"] <= admin_overview["product_count"]


# --------------------------------------------------------------------------- 文件与系统


def test_file_upload_local_fallback(client, admin_headers):
    content = "检测报告测试内容：水分 8.6%，杂质 0.4%，符合一级标准。".encode("utf-8")
    response = client.post(
        "/api/v1/files/upload",
        headers=admin_headers,
        files={"file": ("测试检测报告.txt", content, "text/plain")},
        data={"biz_type": "report"},
    )
    data = unwrap(response)
    assert data["file_key"]
    assert data["size"] == len(content)
    assert data["storage"] in ("local", "minio")

    download = client.get(f"/api/v1/files/{data['file_key']}/download")
    assert download.status_code == 200
    assert download.content == content

    rejected = client.post(
        "/api/v1/files/upload",
        headers=admin_headers,
        files={"file": ("恶意脚本.exe", b"MZ", "application/octet-stream")},
        data={"biz_type": "report"},
    )
    assert rejected.status_code == 400

    listing = unwrap(
        client.get("/api/v1/files", headers=admin_headers, params={"biz_type": "report"})
    )
    assert listing["total"] >= 1

    status = unwrap(client.get("/api/v1/files/storage-status", headers=admin_headers))
    assert status["backend"] in ("local", "minio")


def test_system_info_and_integration_outbox(client, admin_headers):
    info = unwrap(client.get("/api/v1/system/info", headers=admin_headers))
    assert info["app"]
    assert info["database"]["ok"] is True
    assert "cache" in info and "search" in info and "storage" in info
    assert info["outbox"]["pending"] >= 0
    assert info["business"]["service_fee_rate"] == 0.005

    outbox = unwrap(
        client.get("/api/v1/integration/outbox", headers=admin_headers, params={"page_size": 5})
    )
    assert outbox["total"] >= 1
    event_types = {row["event_type"] for row in outbox["items"]}
    assert event_types, "业务操作应写入集成出站事件"

    event_id = outbox["items"][0]["id"]
    retried = unwrap(
        client.post(f"/api/v1/integration/outbox/{event_id}/retry", headers=admin_headers)
    )
    assert retried["status"] == "pending"


def test_integration_signature_rejected(client):
    response = client.post(
        "/api/v1/integration/odoo/pull-inventory",
        json={"items": []},
        headers={"X-GZ-Timestamp": "1", "X-GZ-Signature": "bad-signature"},
    )
    assert response.status_code == 403


def test_operation_log_written_for_write_requests(client, admin_headers):
    unwrap(
        client.post(
            "/api/v1/parks",
            headers=admin_headers,
            json={"code": "PARK-AUDIT-01", "name": "审计日志测试园区"},
        )
    )
    from app.core.database import get_session_factory
    from app.models.org import OperationLog

    session = get_session_factory()()
    try:
        count = (
            session.query(OperationLog)
            .filter(OperationLog.path.like("/api/v1/parks%"), OperationLog.method == "POST")
            .count()
        )
    finally:
        session.close()
    assert count >= 1, "写操作应写入审计日志"
