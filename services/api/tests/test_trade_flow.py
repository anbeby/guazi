# -*- coding: utf-8 -*-
"""B2B 交易全链路测试：询价 → 报价 → 订单 → 扣库存 → 发货 → 完成 → 结算 → 回款。"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tests.conftest import unwrap


@pytest.fixture(scope="module")
def supplier_product(client, admin_headers, supplier_headers):
    """供应商准备好一个有 200 吨库存的上架商品。"""
    tree = unwrap(client.get("/api/v1/categories/tree", headers=supplier_headers))
    category = next(node for root in tree for node in root.get("children", []) if node["code"] == "GZ-SUN")
    product = unwrap(
        client.post(
            "/api/v1/products",
            headers=supplier_headers,
            json={
                "name": "链路测试葵花籽（200吨）",
                "category_id": category["id"],
                "spec": "千粒重≥185g",
                "grade": "special",
                "origin": "新疆阿勒泰",
                "harvest_year": "2025",
                "package": "50kg 编织袋",
                "unit": "ton",
                "price": 6400,
                "stock_warn_qty": 10,
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
    product = unwrap(
        client.post(f"/api/v1/products/{product['id']}/publish", headers=supplier_headers)
    )
    warehouse = unwrap(
        client.post(
            "/api/v1/warehouses",
            headers=supplier_headers,
            json={"name": "链路测试仓库", "capacity": 5000},
        )
    )
    unwrap(
        client.post(
            "/api/v1/inventory/in",
            headers=supplier_headers,
            json={
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
                "batch_no": "TRADE-BATCH-01",
                "quantity": 200,
                "unit_cost": 6000,
                "quality_status": "qualified",
            },
        )
    )
    return {"product": product, "warehouse": warehouse}


def test_full_b2b_trade_closed_loop(
    client, admin_headers, supplier_headers, buyer_headers, supplier_product
):
    product = supplier_product["product"]
    enterprise_ids = {
        "supplier": unwrap(client.get("/api/v1/auth/me", headers=supplier_headers))["enterprise_id"],
        "buyer": unwrap(client.get("/api/v1/auth/me", headers=buyer_headers))["enterprise_id"],
    }

    # 1. 采购商发起询价
    inquiry = unwrap(
        client.post(
            "/api/v1/inquiries",
            headers=buyer_headers,
            json={
                "product_id": product["id"],
                "quantity": 30,
                "unit": "ton",
                "supplier_enterprise_id": enterprise_ids["supplier"],
                "expect_price": 6300,
                "delivery_address": "乌鲁木齐市测试收货地址",
                "remark": "全链路测试询价",
                "submit": True,
            },
        )
    )
    assert inquiry["inquiry_no"].startswith("GZ-INQ-")
    assert inquiry["status"] == "submitted"
    assert inquiry["buyer_enterprise_id"] == enterprise_ids["buyer"]
    inquiry_id = inquiry["id"]

    # 2. 供应商报价
    quotation = unwrap(
        client.post(
            f"/api/v1/inquiries/{inquiry_id}/quotations",
            headers=supplier_headers,
            json={
                "unit_price": 6000,
                "tax_rate": 0.09,
                "payment_terms": "货到验收后 15 日电汇",
                "remark": "全链路测试报价",
            },
        )
    )
    assert quotation["amount"] == 180000.0
    assert quotation["status"] == "submitted"

    # 重复报价应被拒绝
    assert client.post(
        f"/api/v1/inquiries/{inquiry_id}/quotations",
        headers=supplier_headers,
        json={"unit_price": 5900},
    ).status_code == 409

    detail = unwrap(client.get(f"/api/v1/inquiries/{inquiry_id}", headers=buyer_headers))
    assert detail["status"] == "quoted"
    assert len(detail["quotations"]) == 1

    # 3. 采购商接受报价 → 生成订单并预占库存
    before = unwrap(client.get(f"/api/v1/products/{product['id']}", headers=supplier_headers))
    order = unwrap(
        client.post(
            f"/api/v1/quotations/{quotation['id']}/accept", headers=buyer_headers
        )
    )
    assert order["order_no"].startswith("GZ-SO-")
    assert order["status"] == "pending_confirm"
    assert order["stock_deducted"] is False
    assert order["amount"] == 180000.0
    assert order["tax_amount"] == 16200.0
    assert order["total_amount"] == 196200.0
    assert len(order["items"]) == 1
    assert order["items"][0]["quantity"] == 30.0
    order_id = order["id"]

    reserved = unwrap(client.get(f"/api/v1/products/{product['id']}", headers=supplier_headers))
    assert reserved["locked_quantity"] == 30.0
    assert reserved["available_quantity"] == before["available_quantity"] - 30.0
    assert reserved["total_quantity"] == before["total_quantity"], "预占阶段不应扣减账面库存"

    # 询价单已确认，报价已接受
    assert unwrap(client.get(f"/api/v1/inquiries/{inquiry_id}", headers=buyer_headers))[
        "status"
    ] == "confirmed"

    # 4. 供应商确认订单 → 扣减库存 + 生成交易流水
    confirmed = unwrap(
        client.post(f"/api/v1/orders/{order_id}/confirm", headers=supplier_headers)
    )
    assert confirmed["status"] == "confirmed"
    assert confirmed["stock_deducted"] is True

    after = unwrap(client.get(f"/api/v1/products/{product['id']}", headers=supplier_headers))
    assert after["total_quantity"] == before["total_quantity"] - 30.0
    assert after["locked_quantity"] == 0.0

    moves = unwrap(
        client.get(
            "/api/v1/inventory/moves",
            headers=supplier_headers,
            params={"product_id": product["id"], "move_type": "out"},
        )
    )
    assert moves["total"] >= 1
    assert any(row["ref_no"] == order["order_no"] for row in moves["items"])

    flows = unwrap(
        client.get(
            "/api/v1/finance/flows",
            headers=supplier_headers,
            params={"order_id": order_id},
        )
    )
    assert flows["total"] == 1
    assert flows["items"][0]["amount"] == 196200.0
    assert flows["items"][0]["biz_type"] == "order_payment"
    assert flows["items"][0]["direction"] == "in"

    # 重复确认应被拒绝
    assert client.post(
        f"/api/v1/orders/{order_id}/confirm", headers=supplier_headers
    ).status_code == 409

    # 5. 生成合同并双方签署
    contract = unwrap(
        client.post(
            "/api/v1/contracts",
            headers=supplier_headers,
            json={"order_id": order_id, "start_date": "2025-09-01", "end_date": "2025-12-31"},
        )
    )
    assert contract["status"] == "pending_sign"
    assert contract["amount"] == 196200.0
    signed = unwrap(
        client.post(
            f"/api/v1/contracts/{contract['id']}/sign",
            headers=supplier_headers,
            json={"party": "supplier"},
        )
    )
    assert signed["signed_by_supplier"] is True
    assert signed["status"] == "pending_sign"
    signed = unwrap(
        client.post(
            f"/api/v1/contracts/{contract['id']}/sign",
            headers=buyer_headers,
            json={"party": "buyer"},
        )
    )
    assert signed["status"] == "effective"

    # 6. 发货
    deliver = unwrap(
        client.post(
            f"/api/v1/orders/{order_id}/deliver",
            headers=supplier_headers,
            json={
                "items": [
                    {"item_id": order["items"][0]["id"], "delivered_quantity": 30}
                ],
                "logistics_company": "北屯物流有限公司",
                "logistics_no": "BTWL00000001",
            },
        )
    )
    assert deliver["status"] == "delivering"
    assert deliver["logistics_no"] == "BTWL00000001"

    # 7. 订单完成 → 生成应收结算单
    completed = unwrap(
        client.post(f"/api/v1/orders/{order_id}/complete", headers=supplier_headers)
    )
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    settlements = unwrap(
        client.get(
            "/api/v1/settlements",
            headers=supplier_headers,
            params={"enterprise_id": enterprise_ids["supplier"]},
        )
    )
    mine = [
        row
        for row in settlements["items"]
        if any(line["biz_no"] == order["order_no"] for line in [])  # 明细单独查询
    ]
    settlement_detail = None
    for row in settlements["items"]:
        detail_row = unwrap(
            client.get(f"/api/v1/settlements/{row['id']}", headers=supplier_headers)
        )
        if any(line["biz_no"] == order["order_no"] for line in detail_row["lines"]):
            settlement_detail = detail_row
            break
    assert settlement_detail is not None, "订单完成后应生成结算单"
    assert settlement_detail["order_amount"] == 196200.0
    assert settlement_detail["fee_amount"] == 981.0  # 平台服务费 0.5%
    assert settlement_detail["settle_amount"] == 195219.0
    assert settlement_detail["pay_status"] == "unpaid"
    assert {line["biz_type"] for line in settlement_detail["lines"]} == {"order", "service_fee"}
    settlement_id = settlement_detail["id"]

    # 8. 结算单确认 + 回款登记（部分）
    confirmed_settlement = unwrap(
        client.post(f"/api/v1/settlements/{settlement_id}/confirm", headers=supplier_headers)
    )
    assert confirmed_settlement["status"] == "confirmed"

    partial = unwrap(
        client.post(
            f"/api/v1/settlements/{settlement_id}/payment",
            headers=supplier_headers,
            json={
                "amount": 100000,
                "pay_method": "bank_transfer",
                "trade_no": "BANK202509010001",
                "remark": "首笔回款",
            },
        )
    )
    assert partial["pay_status"] == "partial"
    assert partial["settled_amount"] == 100000.0
    assert partial["unpaid_amount"] == 95219.0

    # 超额回款必须拒绝
    assert client.post(
        f"/api/v1/settlements/{settlement_id}/payment",
        headers=supplier_headers,
        json={"amount": 999999, "pay_method": "offline"},
    ).status_code == 400

    final = unwrap(
        client.post(
            f"/api/v1/settlements/{settlement_id}/payment",
            headers=supplier_headers,
            json={
                "amount": 95219,
                "pay_method": "bank_transfer",
                "trade_no": "BANK202509010002",
            },
        )
    )
    assert final["pay_status"] == "paid"
    assert final["status"] == "settled"
    assert final["unpaid_amount"] == 0.0

    # 9. 订单轨迹
    timeline = unwrap(client.get(f"/api/v1/orders/{order_id}/timeline", headers=buyer_headers))
    statuses = [row["status"] for row in timeline]
    assert "confirmed" in statuses and "delivering" in statuses and "completed" in statuses
    assert "settled" in statuses

    # 10. 对账单
    statement = unwrap(
        client.get(
            "/api/v1/finance/statement",
            headers=supplier_headers,
            params={"enterprise_id": enterprise_ids["supplier"]},
        )
    )
    assert statement["order_count"] >= 1
    assert any(item["order_no"] == order["order_no"] for item in statement["items"])

    # 11. 数据驾驶舱应反映真实交易
    overview = unwrap(client.get("/api/v1/dashboard/overview", headers=admin_headers))
    assert overview["order_count"] >= 1
    assert overview["order_amount"] > 0
    assert overview["product_count"] >= 1
    assert overview["inventory_quantity"] > 0
    assert overview["stall_count"] >= 40

    trend = unwrap(
        client.get("/api/v1/dashboard/trend", headers=admin_headers, params={"days": 7})
    )
    assert len(trend["dates"]) == 7
    assert len(trend["order_amount"]) == 7

    industry = unwrap(client.get("/api/v1/dashboard/industry", headers=admin_headers))
    assert industry["by_category"]
    assert any(row["name"] == "葵花籽" for row in industry["by_category"])


def test_order_cancel_releases_reserved_stock(
    client, admin_headers, supplier_headers, buyer_headers, supplier_product
):
    product = supplier_product["product"]
    before = unwrap(client.get(f"/api/v1/products/{product['id']}", headers=supplier_headers))

    order = unwrap(
        client.post(
            "/api/v1/orders",
            headers=buyer_headers,
            json={
                "supplier_enterprise_id": unwrap(
                    client.get("/api/v1/auth/me", headers=supplier_headers)
                )["enterprise_id"],
                "items": [
                    {"product_id": product["id"], "quantity": 15, "unit_price": 6100, "tax_rate": 0.09}
                ],
                "delivery_address": "测试收货地址",
                "remark": "取消测试订单",
            },
        )
    )
    assert order["status"] == "pending_confirm"

    reserved = unwrap(client.get(f"/api/v1/products/{product['id']}", headers=supplier_headers))
    assert reserved["locked_quantity"] == before["locked_quantity"] + 15.0

    cancelled = unwrap(
        client.post(
            f"/api/v1/orders/{order['id']}/cancel",
            headers=buyer_headers,
            json={"reason": "需求变更"},
        )
    )
    assert cancelled["status"] == "cancelled"

    after = unwrap(client.get(f"/api/v1/products/{product['id']}", headers=supplier_headers))
    assert after["locked_quantity"] == before["locked_quantity"]
    assert after["total_quantity"] == before["total_quantity"]


def test_order_rejected_when_stock_insufficient(
    client, supplier_headers, buyer_headers, supplier_product
):
    product = supplier_product["product"]
    response = client.post(
        "/api/v1/orders",
        headers=buyer_headers,
        json={
            "supplier_enterprise_id": unwrap(
                client.get("/api/v1/auth/me", headers=supplier_headers)
            )["enterprise_id"],
            "items": [
                {"product_id": product["id"], "quantity": 100000, "unit_price": 6100}
            ],
        },
    )
    assert response.status_code == 409
    assert "库存不足" in response.json()["message"]


def test_buyer_cannot_confirm_own_order(
    client, supplier_headers, buyer_headers, supplier_product
):
    product = supplier_product["product"]
    order = unwrap(
        client.post(
            "/api/v1/orders",
            headers=buyer_headers,
            json={
                "supplier_enterprise_id": unwrap(
                    client.get("/api/v1/auth/me", headers=supplier_headers)
                )["enterprise_id"],
                "items": [{"product_id": product["id"], "quantity": 5, "unit_price": 6000}],
            },
        )
    )
    forbidden = client.post(f"/api/v1/orders/{order['id']}/confirm", headers=buyer_headers)
    assert forbidden.status_code == 403
    unwrap(client.post(f"/api/v1/orders/{order['id']}/cancel", headers=buyer_headers, json={}))


def test_order_list_scope_by_role(client, supplier_headers, buyer_headers):
    supplier_view = unwrap(
        client.get("/api/v1/orders", headers=supplier_headers, params={"role": "supplier"})
    )
    buyer_view = unwrap(
        client.get("/api/v1/orders", headers=buyer_headers, params={"role": "buyer"})
    )
    assert supplier_view["total"] >= 1
    assert buyer_view["total"] >= 1
    for row in buyer_view["items"]:
        assert row["buyer_enterprise_id"] != row["supplier_enterprise_id"]
