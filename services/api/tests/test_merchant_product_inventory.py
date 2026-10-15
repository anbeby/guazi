# -*- coding: utf-8 -*-
"""商户、商品、库存模块测试。"""
from __future__ import annotations

from decimal import Decimal

from tests.conftest import unwrap


def test_category_tree_contains_oil_seed_nodes(client, admin_headers):
    tree = unwrap(client.get("/api/v1/categories/tree", headers=admin_headers))
    root = next(node for node in tree if node["code"] == "GZ")
    assert root["name"] == "瓜子油料"
    children = {node["code"] for node in root["children"]}
    assert {"GZ-SUN", "GZ-PUM", "GZ-SEED", "GZ-PRO"} <= children
    processed = next(node for node in root["children"] if node["code"] == "GZ-PRO")
    assert {node["code"] for node in processed["children"]} >= {"GZ-PRO-ROAST", "GZ-PRO-OIL"}


def test_enterprise_crud_and_audit(client, admin_headers):
    created = unwrap(
        client.post(
            "/api/v1/enterprises",
            headers=admin_headers,
            json={
                "name": "北屯测试瓜子合作社",
                "unified_social_credit_code": "91659001TEST0001XZ",
                "enterprise_type": "merchant",
                "legal_person": "测试法人",
                "business_scope": "葵花籽收购与销售",
                "contact_name": "测试联系人",
                "contact_phone": "13900000001",
                "region": "新疆北屯",
                "address": "北屯市测试路 1 号",
                "create_account": True,
                "account_username": "test_coop",
                "account_password": "Test@123456",
            },
        )
    )
    assert created["code"].startswith("ENT-")
    assert created["audit_status"] == "pending"
    enterprise_id = created["id"]

    # 未审核企业：账号可登录但无商户权限
    login_body = unwrap(
        client.post(
            "/api/v1/auth/login", json={"username": "test_coop", "password": "Test@123456"}
        )
    )
    assert login_body["user"]["enterprise_id"] == enterprise_id

    audited = unwrap(
        client.post(
            f"/api/v1/enterprises/{enterprise_id}/audit",
            headers=admin_headers,
            json={"approved": True, "remark": "资质齐全，审核通过"},
        )
    )
    assert audited["audit_status"] == "approved"
    assert audited["org_id"] is not None, "审核通过后应自动创建组织单元"

    duplicate = client.post(
        "/api/v1/enterprises",
        headers=admin_headers,
        json={"name": "重复信用代码企业", "unified_social_credit_code": "91659001TEST0001XZ"},
    )
    assert duplicate.status_code == 409

    stats = unwrap(
        client.get(f"/api/v1/enterprises/{enterprise_id}/stats", headers=admin_headers)
    )
    assert stats["product_count"] == 0
    assert stats["inventory_quantity"] == 0

    updated = unwrap(
        client.put(
            f"/api/v1/enterprises/{enterprise_id}",
            headers=admin_headers,
            json={"contact_name": "新联系人", "contact_phone": "13900000002"},
        )
    )
    assert updated["contact_name"] == "新联系人"

    assert unwrap(
        client.delete(f"/api/v1/enterprises/{enterprise_id}", headers=admin_headers)
    )["deleted"] is True


def test_product_lifecycle(client, admin_headers, supplier_headers):
    tree = unwrap(client.get("/api/v1/categories/tree", headers=supplier_headers))
    sunflower = next(node for root in tree for node in root.get("children", []) if node["code"] == "GZ-SUN")

    created = unwrap(
        client.post(
            "/api/v1/products",
            headers=supplier_headers,
            json={
                "name": "测试特级葵花籽",
                "category_id": sunflower["id"],
                "spec": "千粒重≥190g",
                "grade": "special",
                "origin": "新疆阿勒泰",
                "harvest_year": "2025",
                "package": "50kg 编织袋",
                "unit": "ton",
                "price": 6900,
                "min_order_qty": 10,
                "stock_warn_qty": 20,
                "quality_status": "qualified",
                "description": "测试用商品",
            },
        )
    )
    product_id = created["id"]
    assert created["status"] == "draft"
    assert created["audit_status"] == "pending"
    assert created["category_name"] == "葵花籽"
    assert created["available_quantity"] == 0

    # 未审核不能上架
    assert client.post(
        f"/api/v1/products/{product_id}/publish", headers=supplier_headers
    ).status_code == 409

    unwrap(
        client.post(
            f"/api/v1/products/{product_id}/audit",
            headers=admin_headers,
            json={"approved": True, "remark": "OK"},
        )
    )
    published = unwrap(
        client.post(f"/api/v1/products/{product_id}/publish", headers=supplier_headers)
    )
    assert published["status"] == "published"

    # 列表过滤
    listing = unwrap(
        client.get(
            "/api/v1/products",
            headers=supplier_headers,
            params={"status": "published", "grade": "special", "keyword": "测试特级"},
        )
    )
    assert listing["total"] >= 1
    assert any(row["id"] == product_id for row in listing["items"])

    # 关键信息变更后自动转回待审核并下架
    updated = unwrap(
        client.put(
            f"/api/v1/products/{product_id}",
            headers=supplier_headers,
            json={"grade": "first"},
        )
    )
    assert updated["audit_status"] == "pending"
    assert updated["status"] == "offline"

    unwrap(
        client.post(
            f"/api/v1/products/{product_id}/audit",
            headers=admin_headers,
            json={"approved": True},
        )
    )
    unwrap(client.post(f"/api/v1/products/{product_id}/publish", headers=supplier_headers))
    offline = unwrap(client.post(f"/api/v1/products/{product_id}/offline", headers=supplier_headers))
    assert offline["status"] == "offline"

    # 商品检索（ES 不可用时自动降级 SQL）
    result = unwrap(
        client.get("/api/v1/products/search", headers=supplier_headers, params={"q": "葵花籽"})
    )
    assert result["engine"] in ("sql", "elasticsearch")
    assert isinstance(result["items"], list)

    # 删除（无库存与流水）
    assert unwrap(
        client.delete(f"/api/v1/products/{product_id}", headers=supplier_headers)
    )["deleted"] is True


def test_warehouse_location_and_inventory_flow(client, supplier_headers, admin_headers):
    warehouse = unwrap(
        client.post(
            "/api/v1/warehouses",
            headers=supplier_headers,
            json={
                "name": "测试临时仓库",
                "address": "北屯市测试仓储 3 号",
                "warehouse_type": "own",
                "capacity": 1000,
            },
        )
    )
    warehouse_id = warehouse["id"]
    assert warehouse["code"].startswith("GZ-WH-")

    location = unwrap(
        client.post(
            f"/api/v1/warehouses/{warehouse_id}/locations",
            headers=supplier_headers,
            json={"code": "T-01-01", "name": "测试 1 排 1 位", "zone": "T", "capacity": 200},
        )
    )
    location_id = location["id"]

    duplicate_location = client.post(
        f"/api/v1/warehouses/{warehouse_id}/locations",
        headers=supplier_headers,
        json={"code": "T-01-01", "name": "重复库位"},
    )
    assert duplicate_location.status_code == 409

    listing = unwrap(
        client.get(f"/api/v1/warehouses/{warehouse_id}/locations", headers=supplier_headers)
    )
    assert len(listing) == 1

    product = _create_published_product(client, admin_headers, supplier_headers, "库存测试葵花籽")

    stock_in = unwrap(
        client.post(
            "/api/v1/inventory/in",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "warehouse_id": warehouse_id,
                "location_id": location_id,
                "batch_no": "TB20250101",
                "quantity": 100,
                "unit_cost": 6000,
                "quality_status": "qualified",
                "remark": "测试入库",
            },
        )
    )
    assert stock_in["quantity"] == 100.0
    assert stock_in["available_quantity"] == 100.0
    assert stock_in["amount"] == 600000.0

    # 库存不足必须拒绝
    insufficient = client.post(
        "/api/v1/inventory/out",
        headers=supplier_headers,
        json={
            "product_id": product["id"],
            "warehouse_id": warehouse_id,
            "batch_no": "TB20250101",
            "quantity": 500,
        },
    )
    assert insufficient.status_code == 409
    assert "库存不足" in insufficient.json()["message"]

    stock_out = unwrap(
        client.post(
            "/api/v1/inventory/out",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "warehouse_id": warehouse_id,
                "batch_no": "TB20250101",
                "quantity": 30,
            },
        )
    )
    assert stock_out["remaining_quantity"] == 70.0

    adjusted = unwrap(
        client.post(
            "/api/v1/inventory/adjust",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "warehouse_id": warehouse_id,
                "batch_no": "TB20250101",
                "target_quantity": 75,
                "remark": "账面修正",
            },
        )
    )
    assert adjusted["quantity"] == 75.0

    check = unwrap(
        client.post(
            "/api/v1/inventory/check",
            headers=supplier_headers,
            json={
                "warehouse_id": warehouse_id,
                "items": [
                    {
                        "product_id": product["id"],
                        "batch_no": "TB20250101",
                        "actual_quantity": 72,
                    }
                ],
            },
        )
    )
    assert check["diff_count"] == 1
    assert check["loss_quantity"] == 3.0

    # 调拨到指定供应商的另一个仓库
    target_warehouse = unwrap(
        client.post(
            "/api/v1/warehouses",
            headers=supplier_headers,
            json={"name": "测试调拨目标仓库"},
        )
    )
    transfer = unwrap(
        client.post(
            "/api/v1/inventory/transfer",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "from_warehouse_id": warehouse_id,
                "batch_no": "TB20250101",
                "to_warehouse_id": target_warehouse["id"],
                "quantity": 20,
            },
        )
    )
    assert transfer["to"] == target_warehouse["id"]

    inventory_rows = unwrap(
        client.get(
            "/api/v1/inventory",
            headers=supplier_headers,
            params={"product_id": product["id"]},
        )
    )
    assert inventory_rows["total"] == 2

    summary = unwrap(
        client.get(
            "/api/v1/inventory/summary", headers=supplier_headers, params={"keyword": "库存测试"}
        )
    )
    assert len(summary) == 1
    assert summary[0]["total_quantity"] == 72.0
    assert summary[0]["warehouse_count"] == 2

    moves = unwrap(
        client.get(
            "/api/v1/inventory/moves",
            headers=supplier_headers,
            params={"product_id": product["id"]},
        )
    )
    types = [row["move_type"] for row in moves["items"]]
    assert "in" in types and "out" in types and "adjust" in types and "check" in types

    # 清理
    assert client.delete(
        f"/api/v1/locations/{location_id}", headers=supplier_headers
    ).status_code in (200, 409)


def _create_published_product(client, admin_headers, supplier_headers, name: str) -> dict:
    tree = unwrap(client.get("/api/v1/categories/tree", headers=supplier_headers))
    category = next(node for root in tree for node in root.get("children", []) if node["code"] == "GZ-SUN")
    product = unwrap(
        client.post(
            "/api/v1/products",
            headers=supplier_headers,
            json={
                "name": name,
                "category_id": category["id"],
                "grade": "first",
                "origin": "新疆北屯",
                "harvest_year": "2025",
                "unit": "ton",
                "price": 6200,
            },
        )
    )
    unwrap(
        client.post(
            f"/api/v1/products/{product['id']}/audit",
            headers=admin_headers,
            json={"approved": True},
        )
    )
    return unwrap(
        client.post(f"/api/v1/products/{product['id']}/publish", headers=supplier_headers)
    )


def test_warehouse_delete_conflict_when_stock_exists(client, supplier_headers, admin_headers):
    warehouse = unwrap(
        client.post(
            "/api/v1/warehouses", headers=supplier_headers, json={"name": "测试占用仓库"}
        )
    )
    product = _create_published_product(client, admin_headers, supplier_headers, "占用测试商品")
    unwrap(
        client.post(
            "/api/v1/inventory/in",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
                "quantity": 5,
                "unit_cost": 100,
            },
        )
    )
    response = client.delete(f"/api/v1/warehouses/{warehouse['id']}", headers=supplier_headers)
    assert response.status_code == 409
    assert "库存" in response.json()["message"]
