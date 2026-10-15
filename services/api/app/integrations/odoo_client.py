# -*- coding: utf-8 -*-
"""Odoo 集成客户端（JSON-RPC 2.0）。

自研平台访问 Odoo 的唯一通道：禁止直接读写 Odoo 数据库表（见 docs/02 第 2.1 节）。
所有调用均为容错设计——Odoo 不可用时抛 `OdooUnavailable`，由调用方决定重试或留待 worker。
"""
from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


class OdooError(Exception):
    """Odoo 业务错误。"""


class OdooUnavailable(OdooError):
    """Odoo 服务不可用（网络/超时/未启动）。"""


class OdooClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        db: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.ODOO_BASE_URL).rstrip("/")
        self.db = db or settings.ODOO_DB
        self.username = username or settings.ODOO_USER
        self.password = password or settings.ODOO_PASSWORD
        self.timeout = timeout or settings.ODOO_TIMEOUT
        self._uid: Optional[int] = None

    # ------------------------------------------------------------------ 基础调用
    def _rpc(self, service: str, method: str, args: List[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": int(time.time() * 1000) % 1_000_000,
        }
        url = f"{self.base_url}/jsonrpc"
        try:
            response = httpx.post(url, json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise OdooUnavailable(f"无法连接 Odoo：{exc}") from exc
        if response.status_code >= 500:
            raise OdooUnavailable(f"Odoo 返回 {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise OdooUnavailable("Odoo 响应非 JSON") from exc
        if "error" in body:
            error = body["error"]
            message = error.get("data", {}).get("message") or error.get("message") or str(error)
            raise OdooError(message)
        return body.get("result")

    def authenticate(self, force: bool = False) -> int:
        if self._uid and not force:
            return self._uid
        uid = self._rpc("common", "authenticate", [self.db, self.username, self.password, {}])
        if not uid:
            raise OdooError("Odoo 认证失败，请检查 ODOO_USER / ODOO_PASSWORD")
        self._uid = int(uid)
        return self._uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        uid = self.authenticate()
        return self._rpc(
            "object",
            "execute_kw",
            [self.db, uid, self.password, model, method, args or [], kwargs or {}],
        )

    # ------------------------------------------------------------------ 健康检查
    def health(self) -> Dict[str, Any]:
        try:
            version = self._rpc("common", "version", [])
            uid = self.authenticate()
            return {"available": True, "version": version.get("server_version"), "uid": uid}
        except OdooError as exc:
            return {"available": False, "error": str(exc)}

    # ------------------------------------------------------------------ 业务封装
    def upsert_partner(self, payload: Dict[str, Any]) -> Optional[int]:
        """按 ref（企业编码）幂等创建/更新 res.partner。"""
        ref = payload.get("ref") or payload.get("code")
        if not ref:
            raise OdooError("企业编码不能为空")
        record = {
            "name": payload.get("name"),
            "ref": ref,
            "vat": payload.get("vat"),
            "company_type": "company",
            "phone": payload.get("contact_phone"),
            "email": payload.get("email"),
            "street": payload.get("address"),
            "is_company": True,
        }
        record = {k: v for k, v in record.items() if v not in (None, "")}
        existing = self.execute_kw("res.partner", "search", [[["ref", "=", ref]]], {"limit": 1})
        if existing:
            self.execute_kw("res.partner", "write", [[existing[0]], record])
            return int(existing[0])
        return int(self.execute_kw("res.partner", "create", [record]))

    def upsert_product(self, payload: Dict[str, Any]) -> Optional[int]:
        code = payload.get("default_code")
        if not code:
            raise OdooError("商品编码不能为空")
        record = {
            "name": payload.get("name"),
            "default_code": code,
            "list_price": payload.get("list_price", 0),
            "type": "consu",
            "sale_ok": True,
            "purchase_ok": True,
        }
        unit_name = {"ton": "t", "kg": "kg", "bag": "Units", "piece": "Units"}.get(
            payload.get("uom"), "Units"
        )
        unit_ids = self.execute_kw("uom.uom", "search", [[ ["name", "=", unit_name] ]], {"limit": 1})
        if not unit_ids:
            raise OdooError(f"Odoo 缺少计量单位：{unit_name}")
        record["uom_id"] = unit_ids[0]
        record["uom_po_id"] = unit_ids[0]
        record = {k: v for k, v in record.items() if v not in (None, "")}
        for field in ("gz_spec", "gz_grade", "gz_origin", "gz_harvest_year", "gz_package"):
            if payload.get(field) is not None:
                record[field] = payload[field]
        existing = self.execute_kw(
            "product.template", "search", [[["default_code", "=", code]]], {"limit": 1}
        )
        if existing:
            self.execute_kw("product.template", "write", [[existing[0]], record])
            return int(existing[0])
        return int(self.execute_kw("product.template", "create", [record]))

    def product_variant(self, template_id: int) -> Dict[str, int]:
        """订单行必须使用 product.product 与其计量单位，不能使用模板 ID。"""
        rows = self.execute_kw(
            "product.template", "read", [[template_id]], {"fields": ["product_variant_id"]}
        )
        variant = rows[0].get("product_variant_id") if rows else None
        if not variant:
            raise OdooError(f"商品模板 {template_id} 尚未生成可交易变体")
        variant_id = int(variant[0])
        products = self.execute_kw(
            "product.product", "read", [[variant_id]], {"fields": ["uom_id"]}
        )
        uom = products[0].get("uom_id") if products else None
        if not uom:
            raise OdooError(f"商品变体 {variant_id} 缺少计量单位")
        return {"product_id": variant_id, "uom_id": int(uom[0])}

    def _order_tax_id(self, payload: Dict[str, Any], use: str) -> Optional[int]:
        amount = Decimal(str(payload.get("amount") or 0))
        tax_amount = Decimal(str(payload.get("tax_amount") or 0))
        if tax_amount == 0:
            return None
        if amount <= 0:
            raise OdooError("有税额的订单必须有正数未税金额")
        rate = float((tax_amount / amount * 100).quantize(Decimal("0.0001")))
        ids = self.execute_kw(
            "account.tax", "search",
            [[["type_tax_use", "=", use], ["amount_type", "=", "percent"], ["amount", "=", rate]]],
            {"limit": 1},
        )
        if not ids:
            raise OdooError(f"Odoo 缺少 {use} {rate}% 税配置")
        return int(ids[0])

    def _pricelist_id(self, currency: str) -> int:
        currency_id = self._currency_id(currency)
        ids = self.execute_kw(
            "product.pricelist", "search", [[["currency_id", "=", currency_id]]], {"limit": 1}
        )
        if not ids:
            raise OdooError(f"Odoo 缺少 {currency} 价目表")
        return int(ids[0])

    def _currency_id(self, currency: str) -> int:
        ids = self.execute_kw("res.currency", "search", [[["name", "=", currency]]], {"limit": 1})
        if not ids:
            raise OdooError(f"Odoo 缺少币种：{currency}")
        return int(ids[0])

    def create_sale_order(self, payload: Dict[str, Any]) -> Optional[int]:
        partner_id = payload.get("partner_id")
        if not partner_id:
            raise OdooError("缺少客户 partner_id")
        existing = self.execute_kw(
            "sale.order", "search", [[["client_order_ref", "=", payload.get("order_no")]]],
            {"limit": 1},
        )
        if existing:
            return int(existing[0])
        tax_id = self._order_tax_id(payload, "sale")
        pricelist_id = self._pricelist_id(payload.get("currency") or "CNY")
        lines = []
        for item in payload.get("items", []):
            if not item.get("odoo_product_id") or not item.get("odoo_uom_id"):
                raise OdooError("销售订单行缺少 Odoo 商品变体或计量单位")
            lines.append(
                [
                    0,
                    0,
                    {
                        "product_id": item.get("odoo_product_id"),
                        "product_uom": item.get("odoo_uom_id"),
                        "product_uom_qty": item.get("quantity", 0),
                        "price_unit": item.get("unit_price", 0),
                        "name": item.get("product_name") or "瓜子油料",
                        "tax_id": [[6, 0, [tax_id]]] if tax_id else [[5, 0, 0]],
                    },
                ]
            )
        if not lines:
            raise OdooError("销售订单没有商品明细")
        record = {
            "partner_id": partner_id,
            "client_order_ref": payload.get("order_no"),
            "pricelist_id": pricelist_id,
            "order_line": lines,
        }
        return int(self.execute_kw("sale.order", "create", [record]))

    def create_purchase_order(self, payload: Dict[str, Any]) -> Optional[int]:
        partner_id = payload.get("partner_id")
        if not partner_id:
            raise OdooError("缺少供应商 partner_id")
        existing = self.execute_kw(
            "purchase.order", "search", [[["partner_ref", "=", payload.get("order_no")]]],
            {"limit": 1},
        )
        if existing:
            return int(existing[0])
        tax_id = self._order_tax_id(payload, "purchase")
        lines = []
        for item in payload.get("items", []):
            if not item.get("odoo_product_id") or not item.get("odoo_uom_id"):
                raise OdooError("采购订单行缺少 Odoo 商品变体或计量单位")
            lines.append(
                [
                    0,
                    0,
                    {
                        "product_id": item.get("odoo_product_id"),
                        "product_uom": item.get("odoo_uom_id"),
                        "product_qty": item.get("quantity", 0),
                        "price_unit": item.get("unit_price", 0),
                        "name": item.get("product_name") or "瓜子油料",
                        "taxes_id": [[6, 0, [tax_id]]] if tax_id else [[5, 0, 0]],
                    },
                ]
            )
        if not lines:
            raise OdooError("采购订单没有商品明细")
        record = {
            "partner_id": partner_id,
            "partner_ref": payload.get("order_no"),
            "currency_id": self._currency_id(payload.get("currency") or "CNY"),
            "order_line": lines,
        }
        return int(self.execute_kw("purchase.order", "create", [record]))

    def create_settlement_move(self, payload: Dict[str, Any]) -> Optional[int]:
        """按结算单号幂等生成平衡的 Odoo 会计凭证草稿，不自动过账。"""
        settlement_no = payload.get("settlement_no")
        if not settlement_no:
            raise OdooError("结算单号不能为空")
        existing = self.execute_kw(
            "account.move", "search", [[["ref", "=", settlement_no], ["move_type", "=", "entry"]]],
            {"limit": 1},
        )
        if existing:
            return int(existing[0])
        amount = Decimal(str(payload.get("settle_amount") or 0)).quantize(Decimal("0.01"))
        if amount <= 0:
            raise OdooError("结算金额必须大于零")
        journals = self.execute_kw("account.journal", "search", [[["type", "=", "general"]]], {"limit": 1})
        if not journals:
            raise OdooError("Odoo 缺少杂项会计日记账，请先初始化演示账务配置")
        direction = payload.get("settle_type")
        debit_type, credit_type = (
            ("expense", "liability_payable") if direction == "payable"
            else ("asset_receivable", "income")
        )
        debit = self.execute_kw("account.account", "search", [[["account_type", "=", debit_type]]], {"limit": 1})
        credit = self.execute_kw("account.account", "search", [[["account_type", "=", credit_type]]], {"limit": 1})
        if not debit or not credit:
            raise OdooError(f"Odoo 缺少结算科目：{debit_type} / {credit_type}")
        label = f"瓜子平台结算 {settlement_no}"
        partner_id = payload.get("partner_id") or False
        record = {
            "ref": settlement_no,
            "move_type": "entry",
            "journal_id": int(journals[0]),
            "date": date.today().isoformat(),
            "narration": (
                f"平台结算草稿；订单金额 {payload.get('order_amount', 0)}；"
                f"服务费 {payload.get('fee_amount', 0)}；应结算 {amount}。"
                "实际收付以银行记录及平台回款登记为准。"
            ),
            "line_ids": [
                [0, 0, {"name": label, "account_id": int(debit[0]), "partner_id": partner_id,
                        "debit": float(amount), "credit": 0.0}],
                [0, 0, {"name": label, "account_id": int(credit[0]), "partner_id": partner_id,
                        "debit": 0.0, "credit": float(amount)}],
            ],
        }
        return int(self.execute_kw("account.move", "create", [record]))

    def note_settlement_payment(self, move_id: int, payload: Dict[str, Any]) -> None:
        """只在草稿备注中同步银行回款登记，保留财务人工过账环节。"""
        status = {"paid": "已登记回款", "partial": "部分回款", "unpaid": "待回款"}.get(
            payload.get("pay_status"), payload.get("pay_status") or "待核对"
        )
        note = (
            f"平台结算草稿；订单金额 {payload.get('order_amount', 0)}；"
            f"服务费 {payload.get('fee_amount', 0)}；应结算 {payload.get('settle_amount', 0)}。"
            f"平台回款流水号 {payload.get('trade_no') or '未填写'}；"
            f"累计登记回款 {payload.get('settled_amount', 0)}；状态 {status}。"
            "此记录不代表 Odoo 已过账或银行已自动扣款。"
        )
        self.execute_kw("account.move", "write", [[move_id], {"narration": note}])

    def pull_inventory_snapshot(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """拉取 Odoo 库存快照（stock.quant），用于两侧对账。"""
        fields = ["product_id", "location_id", "quantity", "lot_id"]
        rows = self.execute_kw(
            "stock.quant",
            "search_read",
            [[["location_id.usage", "=", "internal"]]],
            {"fields": fields, "limit": limit},
        )
        snapshot: List[Dict[str, Any]] = []
        for row in rows or []:
            snapshot.append(
                {
                    "product": row.get("product_id") and row["product_id"][1],
                    "location": row.get("location_id") and row["location_id"][1],
                    "lot": row.get("lot_id") and row["lot_id"][1],
                    "quantity": row.get("quantity", 0),
                }
            )
        return snapshot


odoo_client = OdooClient()
