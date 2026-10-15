# -*- coding: utf-8 -*-
"""序列化辅助：把 ORM 对象转换为响应字典，补齐关联名称与计算字段。

设计取舍：不做 N+1 查询，小字典表（企业/分类/仓库/库位/园区/档口）一次性载入内存做映射。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enterprise import Enterprise, Park, Stall
from app.models.org import OrgUnit
from app.models.product import Category, Inventory, Product, StorageLocation, Warehouse
from app.models.settlement import Settlement, SettlementLine, TransactionFlow
from app.models.trade import Contract, Inquiry, Quotation, TradeOrder, TradeOrderItem

ZERO = Decimal("0")


def _f(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


class Lookups:
    """关联名称查找表（按请求构建一次）。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._enterprises: Optional[Dict[int, Enterprise]] = None
        self._categories: Optional[Dict[int, Category]] = None
        self._warehouses: Optional[Dict[int, Warehouse]] = None
        self._locations: Optional[Dict[int, StorageLocation]] = None
        self._parks: Optional[Dict[int, Park]] = None
        self._stalls: Optional[Dict[int, Stall]] = None
        self._orgs: Optional[Dict[int, OrgUnit]] = None
        self._products: Dict[int, Product] = {}
        self._availability: Dict[int, Dict[str, Decimal]] = {}

    # ------------------------------------------------------------------ 懒加载映射
    @property
    def enterprises(self) -> Dict[int, Enterprise]:
        if self._enterprises is None:
            self._enterprises = {e.id: e for e in self.db.query(Enterprise).all()}
        return self._enterprises

    @property
    def categories(self) -> Dict[int, Category]:
        if self._categories is None:
            self._categories = {c.id: c for c in self.db.query(Category).all()}
        return self._categories

    @property
    def warehouses(self) -> Dict[int, Warehouse]:
        if self._warehouses is None:
            self._warehouses = {w.id: w for w in self.db.query(Warehouse).all()}
        return self._warehouses

    @property
    def locations(self) -> Dict[int, StorageLocation]:
        if self._locations is None:
            self._locations = {l.id: l for l in self.db.query(StorageLocation).all()}
        return self._locations

    @property
    def parks(self) -> Dict[int, Park]:
        if self._parks is None:
            self._parks = {p.id: p for p in self.db.query(Park).all()}
        return self._parks

    @property
    def stalls(self) -> Dict[int, Stall]:
        if self._stalls is None:
            self._stalls = {s.id: s for s in self.db.query(Stall).all()}
        return self._stalls

    @property
    def orgs(self) -> Dict[int, OrgUnit]:
        if self._orgs is None:
            self._orgs = {o.id: o for o in self.db.query(OrgUnit).all()}
        return self._orgs

    # ------------------------------------------------------------------ 名称
    def enterprise_name(self, enterprise_id: Optional[int]) -> Optional[str]:
        if not enterprise_id:
            return None
        row = self.enterprises.get(int(enterprise_id))
        return row.name if row else None

    def category_name(self, category_id: Optional[int]) -> Optional[str]:
        if not category_id:
            return None
        row = self.categories.get(int(category_id))
        return row.name if row else None

    def warehouse_name(self, warehouse_id: Optional[int]) -> Optional[str]:
        if not warehouse_id:
            return None
        row = self.warehouses.get(int(warehouse_id))
        return row.name if row else None

    def location_name(self, location_id: Optional[int]) -> Optional[str]:
        if not location_id:
            return None
        row = self.locations.get(int(location_id))
        return row.name if row else None

    def park_name(self, park_id: Optional[int]) -> Optional[str]:
        if not park_id:
            return None
        row = self.parks.get(int(park_id))
        return row.name if row else None

    def stall_code(self, stall_id: Optional[int]) -> Optional[str]:
        if not stall_id:
            return None
        row = self.stalls.get(int(stall_id))
        return row.code if row else None

    def org_name(self, org_id: Optional[int]) -> Optional[str]:
        if not org_id:
            return None
        row = self.orgs.get(int(org_id))
        return row.name if row else None

    def product(self, product_id: int) -> Optional[Product]:
        if product_id not in self._products:
            row = self.db.get(Product, product_id)
            if row is not None:
                self._products[product_id] = row
        return self._products.get(product_id)

    # ------------------------------------------------------------------ 库存可用量
    def availability(self, product_id: int) -> Dict[str, Decimal]:
        if product_id not in self._availability:
            row = (
                self.db.query(
                    func.coalesce(func.sum(Inventory.quantity), 0),
                    func.coalesce(func.sum(Inventory.locked_quantity), 0),
                    func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
                )
                .filter(Inventory.product_id == product_id)
                .one()
            )
            total, locked, value = row
            total_d, locked_d = Decimal(str(total)), Decimal(str(locked))
            self._availability[product_id] = {
                "total": total_d,
                "locked": locked_d,
                "available": total_d - locked_d,
                "value": Decimal(str(value)),
            }
        return self._availability[product_id]

    def preload_availability(self, product_ids: Sequence[int]) -> None:
        ids = [int(pid) for pid in product_ids if pid is not None]
        missing = [pid for pid in ids if pid not in self._availability]
        if not missing:
            return
        rows = (
            self.db.query(
                Inventory.product_id,
                func.coalesce(func.sum(Inventory.quantity), 0),
                func.coalesce(func.sum(Inventory.locked_quantity), 0),
                func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
            )
            .filter(Inventory.product_id.in_(missing))
            .group_by(Inventory.product_id)
            .all()
        )
        for product_id, total, locked, value in rows:
            total_d, locked_d = Decimal(str(total)), Decimal(str(locked))
            self._availability[int(product_id)] = {
                "total": total_d,
                "locked": locked_d,
                "available": total_d - locked_d,
                "value": Decimal(str(value)),
            }


# --------------------------------------------------------------------------- 序列化函数


def enterprise_out(lk: Lookups, row: Enterprise) -> Dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "unified_social_credit_code": row.unified_social_credit_code,
        "enterprise_type": row.enterprise_type,
        "legal_person": row.legal_person,
        "registered_capital": _f(row.registered_capital),
        "business_scope": row.business_scope,
        "profile": row.profile,
        "qualifications": row.qualifications or [],
        "contact_name": row.contact_name,
        "contact_phone": row.contact_phone,
        "email": row.email,
        "region": row.region,
        "address": row.address,
        "org_id": row.org_id,
        "park_id": row.park_id,
        "park_name": lk.park_name(row.park_id),
        "stall_id": row.stall_id,
        "stall_code": lk.stall_code(row.stall_id),
        "audit_status": row.audit_status,
        "audit_remark": row.audit_remark,
        "audited_at": row.audited_at,
        "status": row.status,
        "settle_bank": row.settle_bank,
        "settle_account_name": row.settle_account_name,
        "settle_account_no": row.settle_account_no,
        "remark": row.remark,
        "created_at": row.created_at,
    }


def product_out(lk: Lookups, row: Product) -> Dict[str, Any]:
    availability = lk.availability(row.id)
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "category_id": row.category_id,
        "category_name": lk.category_name(row.category_id),
        "enterprise_id": row.enterprise_id,
        "enterprise_name": lk.enterprise_name(row.enterprise_id),
        "spec": row.spec,
        "grade": row.grade,
        "origin": row.origin,
        "harvest_year": row.harvest_year,
        "package": row.package,
        "unit": row.unit,
        "price": _f(row.price),
        "currency": row.currency,
        "min_order_qty": _f(row.min_order_qty),
        "stock_warn_qty": _f(row.stock_warn_qty),
        "supply_quantity": _f(row.supply_quantity),
        "supply_period": row.supply_period,
        "pricing_mode": row.pricing_mode,
        "supply_status": row.supply_status,
        "allow_inquiry": row.allow_inquiry,
        "allow_bulk_purchase": row.allow_bulk_purchase,
        "main_image": row.main_image or (row.images[0] if row.images else None),
        "images": row.images or [],
        "test_report_url": row.test_report_url,
        "quality_status": row.quality_status,
        "trace_enabled": row.trace_enabled,
        "status": row.status,
        "audit_status": row.audit_status,
        "audit_remark": row.audit_remark,
        "description": row.description,
        "total_quantity": _f(availability["total"]),
        "locked_quantity": _f(availability["locked"]),
        "available_quantity": _f(availability["available"]),
        "inventory_value": _f(availability["value"]),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def inquiry_out(lk: Lookups, row: Inquiry, quotation_count: Optional[int] = None) -> Dict[str, Any]:
    product = lk.product(row.product_id)
    return {
        "id": row.id,
        "inquiry_no": row.inquiry_no,
        "buyer_enterprise_id": row.buyer_enterprise_id,
        "buyer_enterprise_name": lk.enterprise_name(row.buyer_enterprise_id),
        "supplier_enterprise_id": row.supplier_enterprise_id,
        "supplier_enterprise_name": lk.enterprise_name(row.supplier_enterprise_id),
        "product_id": row.product_id,
        "product_name": product.name if product else None,
        "product_code": product.code if product else None,
        "spec": product.spec if product else None,
        "grade": product.grade if product else None,
        "origin": product.origin if product else None,
        "unit": row.unit,
        "quantity": _f(row.quantity),
        "expect_price": _f(row.expect_price),
        "expect_delivery_date": row.expect_delivery_date,
        "delivery_address": row.delivery_address,
        "remark": row.remark,
        "status": row.status,
        "quoted_count": int(row.quoted_count or 0),
        "quotation_count": int(quotation_count if quotation_count is not None else row.quoted_count or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def quotation_out(lk: Lookups, row: Quotation, order: Optional[TradeOrder] = None) -> Dict[str, Any]:
    product = lk.product(row.product_id)
    return {
        "id": row.id,
        "quotation_no": row.quotation_no,
        "inquiry_id": row.inquiry_id,
        "inquiry_no": getattr(row, "inquiry_no", None),
        "supplier_enterprise_id": row.supplier_enterprise_id,
        "supplier_enterprise_name": lk.enterprise_name(row.supplier_enterprise_id),
        "buyer_enterprise_name": getattr(row, "buyer_enterprise_name", None),
        "product_id": row.product_id,
        "product_name": product.name if product else None,
        "quantity": _f(row.quantity),
        "unit": row.unit,
        "unit_price": _f(row.unit_price),
        "amount": _f(row.amount),
        "tax_rate": _f(row.tax_rate),
        "valid_until": row.valid_until,
        "delivery_date": row.delivery_date,
        "payment_terms": row.payment_terms,
        "remark": row.remark,
        "status": row.status,
        "order_id": order.id if order else None,
        "order_no": order.order_no if order else None,
        "created_at": row.created_at,
    }


def order_item_out(lk: Lookups, row: TradeOrderItem) -> Dict[str, Any]:
    return {
        "id": row.id,
        "product_id": row.product_id,
        "product_name": row.product_name or (lk.product(row.product_id).name if lk.product(row.product_id) else None),
        "spec": row.spec,
        "grade": row.grade,
        "unit": row.unit,
        "warehouse_id": row.warehouse_id,
        "batch_no": row.batch_no,
        "quantity": _f(row.quantity),
        "delivered_quantity": _f(row.delivered_quantity),
        "unit_price": _f(row.unit_price),
        "amount": _f(row.amount),
        "tax_rate": _f(row.tax_rate),
    }


def order_out(
    lk: Lookups,
    row: TradeOrder,
    contract: Optional[Contract] = None,
    with_items: bool = True,
) -> Dict[str, Any]:
    items = list(row.items or [])
    total_quantity = sum((Decimal(str(item.quantity or 0)) for item in items), ZERO)
    data: Dict[str, Any] = {
        "id": row.id,
        "order_no": row.order_no,
        "order_type": row.order_type,
        "inquiry_id": row.inquiry_id,
        "inquiry_no": getattr(row, "inquiry_no", None),
        "quotation_id": row.quotation_id,
        "buyer_enterprise_id": row.buyer_enterprise_id,
        "buyer_enterprise_name": lk.enterprise_name(row.buyer_enterprise_id),
        "supplier_enterprise_id": row.supplier_enterprise_id,
        "supplier_enterprise_name": lk.enterprise_name(row.supplier_enterprise_id),
        "amount": _f(row.amount),
        "tax_amount": _f(row.tax_amount),
        "total_amount": _f(row.total_amount),
        "currency": row.currency,
        "delivery_date": row.delivery_date,
        "delivery_address": row.delivery_address,
        "delivery_method": row.delivery_method,
        "logistics_company": row.logistics_company,
        "logistics_no": row.logistics_no,
        "contract_id": row.contract_id,
        "contract_no": contract.contract_no if contract else None,
        "stock_deducted": row.stock_deducted,
        "status": row.status,
        "remark": row.remark,
        "item_count": len(items),
        "total_quantity": _f(total_quantity),
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
        "delivered_at": row.delivered_at,
        "completed_at": row.completed_at,
        "items": [order_item_out(lk, item) for item in items] if with_items else [],
    }
    return data


def contract_out(lk: Lookups, row: Contract, order: Optional[TradeOrder] = None) -> Dict[str, Any]:
    return {
        "id": row.id,
        "contract_no": row.contract_no,
        "title": row.title,
        "order_id": row.order_id,
        "order_no": order.order_no if order else None,
        "buyer_enterprise_id": row.buyer_enterprise_id,
        "buyer_enterprise_name": lk.enterprise_name(row.buyer_enterprise_id),
        "supplier_enterprise_id": row.supplier_enterprise_id,
        "supplier_enterprise_name": lk.enterprise_name(row.supplier_enterprise_id),
        "amount": _f(row.amount),
        "sign_date": row.sign_date,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "file_url": row.file_url,
        "terms": row.terms,
        "status": row.status,
        "signed_by_buyer": row.signed_by_buyer,
        "signed_by_supplier": row.signed_by_supplier,
        "buyer_signed_at": row.buyer_signed_at,
        "supplier_signed_at": row.supplier_signed_at,
        "remark": row.remark,
        "created_at": row.created_at,
    }


def settlement_out(
    lk: Lookups,
    row: Settlement,
    lines: Optional[Iterable[SettlementLine]] = None,
    flows: Optional[Iterable[TransactionFlow]] = None,
) -> Dict[str, Any]:
    settle_amount = Decimal(str(row.settle_amount or 0))
    settled_amount = Decimal(str(row.settled_amount or 0))
    data: Dict[str, Any] = {
        "id": row.id,
        "settlement_no": row.settlement_no,
        "enterprise_id": row.enterprise_id,
        "enterprise_name": lk.enterprise_name(row.enterprise_id),
        "settle_type": row.settle_type,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "order_amount": _f(row.order_amount),
        "fee_amount": _f(row.fee_amount),
        "settle_amount": _f(row.settle_amount),
        "settled_amount": _f(row.settled_amount),
        "unpaid_amount": _f(settle_amount - settled_amount),
        "pay_status": row.pay_status,
        "receive_status": row.receive_status,
        "status": row.status,
        "remark": row.remark,
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
        "settled_at": row.settled_at,
    }
    if lines is not None:
        data["lines"] = [
            {
                "id": line.id,
                "biz_type": line.biz_type,
                "biz_no": line.biz_no,
                "order_id": line.order_id,
                "amount": _f(line.amount),
                "fee_rate": _f(line.fee_rate),
                "remark": line.remark,
            }
            for line in lines
        ]
    if flows is not None:
        data["flows"] = [flow_out(lk, flow) for flow in flows]
    return data


def flow_out(lk: Lookups, row: TransactionFlow) -> Dict[str, Any]:
    return {
        "id": row.id,
        "flow_no": row.flow_no,
        "order_id": row.order_id,
        "order_no": getattr(row, "order_no", None),
        "settlement_id": row.settlement_id,
        "settlement_no": getattr(row, "settlement_no", None),
        "enterprise_id": row.enterprise_id,
        "enterprise_name": lk.enterprise_name(row.enterprise_id),
        "counterparty_enterprise_id": row.counterparty_enterprise_id,
        "counterparty_enterprise_name": lk.enterprise_name(row.counterparty_enterprise_id),
        "direction": row.direction,
        "biz_type": row.biz_type,
        "amount": _f(row.amount),
        "pay_method": row.pay_method,
        "pay_status": row.pay_status,
        "receive_status": row.receive_status,
        "trade_no": row.trade_no,
        "paid_at": row.paid_at,
        "remark": row.remark,
        "created_at": row.created_at,
    }


def inventory_out(lk: Lookups, row: Inventory) -> Dict[str, Any]:
    product = lk.product(row.product_id)
    quantity = Decimal(str(row.quantity or 0))
    locked = Decimal(str(row.locked_quantity or 0))
    unit_cost = Decimal(str(row.unit_cost or 0))
    return {
        "id": row.id,
        "product_id": row.product_id,
        "product_code": product.code if product else None,
        "product_name": product.name if product else None,
        "spec": product.spec if product else None,
        "grade": product.grade if product else None,
        "origin": product.origin if product else None,
        "unit": product.unit if product else "ton",
        "enterprise_id": row.enterprise_id,
        "enterprise_name": lk.enterprise_name(row.enterprise_id),
        "warehouse_id": row.warehouse_id,
        "warehouse_name": lk.warehouse_name(row.warehouse_id),
        "location_id": row.location_id,
        "location_name": lk.location_name(row.location_id),
        "batch_no": row.batch_no,
        "quantity": _f(quantity),
        "locked_quantity": _f(locked),
        "available_quantity": _f(quantity - locked),
        "unit_cost": _f(unit_cost),
        "amount": _f((quantity * unit_cost).quantize(Decimal("0.01"))),
        "production_date": row.production_date,
        "expiry_date": row.expiry_date,
        "quality_status": row.quality_status,
        "updated_at": row.updated_at,
    }


def user_out(db: Session, user, lk: Optional[Lookups] = None) -> Dict[str, Any]:
    lk = lk or Lookups(db)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "org_id": user.org_id,
        "org_name": lk.org_name(user.org_id),
        "enterprise_id": user.enterprise_id,
        "enterprise_name": lk.enterprise_name(user.enterprise_id),
        "is_superuser": user.is_superuser,
        "status": user.status,
        "remark": user.remark,
        "roles": [role.code for role in user.roles or []],
        "role_ids": [role.id for role in user.roles or []],
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }
