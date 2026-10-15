# -*- coding: utf-8 -*-
"""B2B 交易服务：询价 → 报价 → 订单 → 库存扣减 → 交易流水 → 结算。

状态机（订单）：
    draft ─提交─▶ pending_confirm ─供方确认─▶ confirmed ─发货─▶ delivering
                       │                        │                  │
                       └─取消─▶ cancelled       │                  ▼
                                     (扣减库存+生成流水)        completed
                                                                  │
                                                          生成应收结算单
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.scope import is_unrestricted
from app.core.timeutil import now
from app.models.enterprise import Enterprise
from app.models.org import User
from app.models.product import Inventory, Product, Warehouse
from app.models.settlement import Settlement, SettlementLine, TransactionFlow
from app.models.trade import Contract, Inquiry, Quotation, TradeOrder, TradeOrderItem
from app.schemas.trade import (
    ContractIn,
    DeliverIn,
    InquiryIn,
    OrderIn,
    QuotationIn,
)
from app.services import integration
from app.services.inventory_service import (
    consume_reserved,
    dec,
    get_product,
    q3,
    release,
    reserve,
    revert_out,
)
from app.services.numbering import next_no

ZERO = Decimal("0")


def _year_prefix(prefix: str) -> str:
    from datetime import date

    return f"{prefix}-{date.today().year}"


def _enterprise_name(db: Session, enterprise_id: Optional[int]) -> Optional[str]:
    if not enterprise_id:
        return None
    row = db.query(Enterprise.name).filter(Enterprise.id == enterprise_id).first()
    return row[0] if row else None


def _product_of(db: Session, product_id: int) -> Product:
    return get_product(db, product_id)


def default_warehouse_id(db: Session, enterprise_id: int) -> Optional[int]:
    row = (
        db.query(Warehouse)
        .filter(Warehouse.enterprise_id == enterprise_id, Warehouse.status == "active")
        .order_by(Warehouse.id.asc())
        .first()
    )
    return row.id if row else None


def pick_warehouse_for_stock(db: Session, product_id: int, quantity: Decimal) -> Optional[int]:
    """选择可用量最大的仓库用于预占/扣减。"""
    rows = (
        db.query(
            Inventory.warehouse_id,
            func.coalesce(func.sum(Inventory.quantity - Inventory.locked_quantity), 0),
        )
        .filter(Inventory.product_id == product_id)
        .group_by(Inventory.warehouse_id)
        .order_by(func.coalesce(func.sum(Inventory.quantity - Inventory.locked_quantity), 0).desc())
        .all()
    )
    for warehouse_id, available in rows:
        if dec(available) >= q3(quantity):
            return int(warehouse_id)
    return int(rows[0][0]) if rows else None


# --------------------------------------------------------------------------- 询价


def create_inquiry(db: Session, data: InquiryIn, user: User) -> Inquiry:
    product = _product_of(db, data.product_id)
    if product.status != "published":
        raise BadRequest("该商品未上架，无法发起询价")
    if product.supply_status != "active" or not product.allow_inquiry:
        raise BadRequest("该供应信息当前不接受询价")
    buyer_id = user.enterprise_id
    if is_unrestricted(user) and not buyer_id:
        raise BadRequest("平台账号需在企业账号下发起询价，请先指定买方企业")
    if not buyer_id:
        raise Forbidden("当前账号未关联企业，无法发起询价")
    if data.supplier_enterprise_id and data.supplier_enterprise_id == buyer_id:
        raise BadRequest("不能向本企业发起询价")
    inquiry = Inquiry(
        inquiry_no=next_no(db, "inquiry", _year_prefix("GZ-INQ")),
        buyer_enterprise_id=buyer_id,
        supplier_enterprise_id=data.supplier_enterprise_id,
        product_id=product.id,
        category_id=product.category_id,
        quantity=q3(data.quantity),
        unit=data.unit or product.unit,
        expect_price=dec(data.expect_price) if data.expect_price is not None else None,
        expect_delivery_date=data.expect_delivery_date,
        delivery_address=data.delivery_address,
        remark=data.remark,
        status="draft",
        quoted_count=0,
        created_by=user.id,
    )
    db.add(inquiry)
    db.flush()
    if data.submit:
        inquiry.status = "submitted"
        db.flush()
        integration.enqueue(
            db,
            event_type="inquiry.submitted",
            aggregate_type="inquiry",
            aggregate_id=inquiry.inquiry_no,
            payload={
                "inquiry_no": inquiry.inquiry_no,
                "buyer_enterprise_id": buyer_id,
                "product_code": product.code,
                "quantity": float(inquiry.quantity),
                "unit": inquiry.unit,
                "expect_price": float(inquiry.expect_price or 0),
            },
        )
    return inquiry


def submit_inquiry(db: Session, inquiry: Inquiry, user: User) -> Inquiry:
    if inquiry.status not in ("draft",):
        raise Conflict(f"当前状态【{inquiry.status}】不允许提交")
    if not is_unrestricted(user) and inquiry.buyer_enterprise_id != user.enterprise_id:
        raise Forbidden("只能提交本企业的询价单")
    inquiry.status = "submitted"
    db.flush()
    return inquiry


def cancel_inquiry(db: Session, inquiry: Inquiry, user: User, reason: Optional[str] = None) -> Inquiry:
    if inquiry.status in ("confirmed", "closed", "cancelled"):
        raise Conflict(f"当前状态【{inquiry.status}】不允许取消")
    allowed = is_unrestricted(user) or inquiry.buyer_enterprise_id == user.enterprise_id
    if not allowed:
        raise Forbidden("只能取消本企业的询价单")
    inquiry.status = "cancelled"
    inquiry.remark = f"{inquiry.remark or ''} 取消原因：{reason or '未填写'}".strip()
    db.flush()
    return inquiry


def create_quotation(db: Session, inquiry: Inquiry, data: QuotationIn, user: User) -> Quotation:
    if inquiry.status not in ("submitted", "quoted"):
        raise Conflict("询价单当前状态不接受报价")
    if (
        inquiry.supplier_enterprise_id
        and user.enterprise_id
        and inquiry.supplier_enterprise_id != user.enterprise_id
        and not is_unrestricted(user)
    ):
        raise Forbidden("该询价为定向询价，仅指定供应商可报价")
    product = _product_of(db, inquiry.product_id)
    supplier_id = user.enterprise_id
    if not supplier_id:
        raise Forbidden("当前账号未关联企业，无法报价")
    if product.enterprise_id != supplier_id and not is_unrestricted(user):
        raise Forbidden("只能对归属于本企业的商品报价")
    existing = (
        db.query(Quotation)
        .filter(
            Quotation.inquiry_id == inquiry.id,
            Quotation.supplier_enterprise_id == supplier_id,
        )
        .first()
    )
    if existing is not None:
        raise Conflict("本企业已对该询价单报价，请勿重复报价")
    quantity = q3(data.quantity if data.quantity is not None else inquiry.quantity)
    unit_price = dec(data.unit_price)
    tax_rate = dec(data.tax_rate) if data.tax_rate is not None else dec(settings.DEFAULT_TAX_RATE)
    quotation = Quotation(
        quotation_no=next_no(db, "quotation", _year_prefix("GZ-QUO")),
        inquiry_id=inquiry.id,
        supplier_enterprise_id=supplier_id,
        product_id=product.id,
        quantity=quantity,
        unit=inquiry.unit or product.unit,
        unit_price=unit_price,
        amount=q3(unit_price * quantity).quantize(Decimal("0.01")),
        tax_rate=tax_rate,
        valid_until=data.valid_until,
        delivery_date=data.delivery_date or inquiry.expect_delivery_date,
        payment_terms=data.payment_terms,
        remark=data.remark,
        status="submitted",
        created_by=user.id,
    )
    db.add(quotation)
    inquiry.quoted_count = int(inquiry.quoted_count or 0) + 1
    if inquiry.status == "submitted":
        inquiry.status = "quoted"
    db.flush()
    integration.enqueue(
        db,
        event_type="quotation.submitted",
        aggregate_type="quotation",
        aggregate_id=quotation.quotation_no,
        payload={
            "quotation_no": quotation.quotation_no,
            "inquiry_no": inquiry.inquiry_no,
            "supplier_enterprise_id": supplier_id,
            "unit_price": float(unit_price),
            "quantity": float(quantity),
            "amount": float(quotation.amount),
        },
    )
    return quotation


def reject_quotation(db: Session, quotation: Quotation, user: User, reason: Optional[str] = None) -> Quotation:
    inquiry = db.get(Inquiry, quotation.inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    if not is_unrestricted(user) and inquiry.buyer_enterprise_id != user.enterprise_id:
        raise Forbidden("只能处理本企业询价单的报价")
    if quotation.status != "submitted":
        raise Conflict("该报价已被处理")
    quotation.status = "rejected"
    quotation.remark = f"{quotation.remark or ''} 拒绝原因：{reason or '未填写'}".strip()
    inquiry.quoted_count = max(0, int(inquiry.quoted_count or 0) - 1)
    db.flush()
    return quotation


# --------------------------------------------------------------------------- 订单


def _build_order(
    db: Session,
    *,
    buyer_id: int,
    supplier_id: int,
    items: List[TradeOrderItem],
    user: User,
    inquiry: Optional[Inquiry] = None,
    quotation: Optional[Quotation] = None,
    delivery_date=None,
    delivery_address: Optional[str] = None,
    delivery_method: str = "self_pickup",
    remark: Optional[str] = None,
) -> TradeOrder:
    amount = sum((dec(item.amount) for item in items), ZERO)
    tax_amount = sum((dec(item.amount) * dec(item.tax_rate) for item in items), ZERO)
    order = TradeOrder(
        order_no=next_no(db, "trade_order", _year_prefix("GZ-SO")),
        order_type="sales",
        inquiry_id=inquiry.id if inquiry else None,
        quotation_id=quotation.id if quotation else None,
        buyer_enterprise_id=buyer_id,
        supplier_enterprise_id=supplier_id,
        amount=amount.quantize(Decimal("0.01")),
        tax_amount=tax_amount.quantize(Decimal("0.01")),
        total_amount=(amount + tax_amount).quantize(Decimal("0.01")),
        currency="CNY",
        delivery_date=delivery_date,
        delivery_address=delivery_address,
        delivery_method=delivery_method,
        stock_deducted=False,
        status="pending_confirm",
        remark=remark,
        created_by=user.id,
    )
    db.add(order)
    db.flush()
    for item in items:
        item.order_id = order.id
        db.add(item)
    db.flush()
    # 预占库存，防止超卖
    for item in items:
        reserve(db, item.product_id, dec(item.quantity), warehouse_id=item.warehouse_id)
    db.flush()
    integration.enqueue(
        db,
        event_type="order.created",
        aggregate_type="trade_order",
        aggregate_id=order.order_no,
        payload={
            "order_no": order.order_no,
            "buyer_enterprise_id": buyer_id,
            "supplier_enterprise_id": supplier_id,
            "total_amount": float(order.total_amount),
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                }
                for item in items
            ],
        },
    )
    return order


def accept_quotation(db: Session, quotation: Quotation, user: User) -> TradeOrder:
    inquiry = db.get(Inquiry, quotation.inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    if not is_unrestricted(user) and inquiry.buyer_enterprise_id != user.enterprise_id:
        raise Forbidden("只能接受本企业询价单的报价")
    if quotation.status != "submitted":
        raise Conflict(f"报价当前状态【{quotation.status}】不可接受")
    product = _product_of(db, quotation.product_id)
    warehouse_id = pick_warehouse_for_stock(db, product.id, dec(quotation.quantity))
    if warehouse_id is None:
        raise BadRequest("商品尚未建立库存记录，无法下单，请先入库")
    item = TradeOrderItem(
        product_id=product.id,
        product_name=product.name,
        spec=product.spec,
        grade=product.grade,
        unit=quotation.unit or product.unit,
        warehouse_id=warehouse_id,
        batch_no="DEFAULT",
        quantity=q3(quotation.quantity),
        delivered_quantity=ZERO,
        unit_price=quotation.unit_price,
        amount=quotation.amount,
        tax_rate=quotation.tax_rate,
    )
    order = _build_order(
        db,
        buyer_id=inquiry.buyer_enterprise_id,
        supplier_id=quotation.supplier_enterprise_id,
        items=[item],
        user=user,
        inquiry=inquiry,
        quotation=quotation,
        delivery_date=quotation.delivery_date or inquiry.expect_delivery_date,
        delivery_address=inquiry.delivery_address,
        remark=f"由询价单 {inquiry.inquiry_no} 报价 {quotation.quotation_no} 生成",
    )
    quotation.status = "accepted"
    inquiry.status = "confirmed"
    other = (
        db.query(Quotation)
        .filter(
            Quotation.inquiry_id == inquiry.id,
            Quotation.id != quotation.id,
            Quotation.status == "submitted",
        )
        .all()
    )
    for row in other:
        row.status = "rejected"
    inquiry.quoted_count = 0
    db.flush()
    return order


def create_order(db: Session, data: OrderIn, user: User) -> TradeOrder:
    supplier_id = data.supplier_enterprise_id
    supplier = db.get(Enterprise, supplier_id)
    if supplier is None:
        raise NotFound("供应商不存在")
    buyer_id = data.buyer_enterprise_id or user.enterprise_id
    if not is_unrestricted(user):
        buyer_id = user.enterprise_id
    if not buyer_id:
        raise BadRequest("缺少买方企业信息")
    if buyer_id == supplier_id:
        raise BadRequest("买卖双方不能为同一企业")
    items: List[TradeOrderItem] = []
    for raw in data.items:
        product = _product_of(db, raw.product_id)
        if product.enterprise_id != supplier_id:
            raise BadRequest(f"商品【{product.name}】不属于所选供应商")
        warehouse_id = raw.warehouse_id or pick_warehouse_for_stock(
            db, product.id, dec(raw.quantity)
        )
        if warehouse_id is None:
            raise BadRequest(f"商品【{product.name}】尚未建立库存记录，请先入库")
        quantity = q3(raw.quantity)
        unit_price = dec(raw.unit_price)
        tax_rate = dec(raw.tax_rate) if raw.tax_rate is not None else dec(settings.DEFAULT_TAX_RATE)
        amount = (unit_price * quantity).quantize(Decimal("0.01"))
        items.append(
            TradeOrderItem(
                product_id=product.id,
                product_name=product.name,
                spec=product.spec,
                grade=product.grade,
                unit=product.unit,
                warehouse_id=warehouse_id,
                location_id=raw.location_id,
                batch_no=raw.batch_no or "DEFAULT",
                quantity=quantity,
                delivered_quantity=ZERO,
                unit_price=unit_price,
                amount=amount,
                tax_rate=tax_rate,
            )
        )
    order = _build_order(
        db,
        buyer_id=buyer_id,
        supplier_id=supplier_id,
        items=items,
        user=user,
        delivery_date=data.delivery_date,
        delivery_address=data.delivery_address,
        delivery_method=data.delivery_method,
        remark=data.remark,
    )
    if data.auto_confirm:
        confirm_order(db, order, user)
    return order


def confirm_order(db: Session, order: TradeOrder, user: User) -> TradeOrder:
    if order.status != "pending_confirm":
        raise Conflict(f"订单当前状态【{order.status}】不可确认")
    if not is_unrestricted(user) and order.supplier_enterprise_id != user.enterprise_id:
        raise Forbidden("只有供应商可以确认订单")
    for item in order.items:
        consume_reserved(
            db,
            item.product_id,
            dec(item.quantity),
            warehouse_id=item.warehouse_id,
            batch_no=item.batch_no,
            ref_type="order",
            ref_id=order.id,
            ref_no=order.order_no,
            operator=user,
        )
    order.stock_deducted = True
    order.status = "confirmed"
    order.confirmed_at = now()
    db.add(
        TransactionFlow(
            flow_no=next_no(db, "transaction_flow", _year_prefix("GZ-FLOW"), width=6),
            order_id=order.id,
            enterprise_id=order.supplier_enterprise_id,
            counterparty_enterprise_id=order.buyer_enterprise_id,
            direction="in",
            biz_type="order_payment",
            amount=order.total_amount,
            pay_method="bank_transfer",
            pay_status="pending",
            receive_status="pending",
            remark=f"订单 {order.order_no} 待收款",
            created_at=now(),
        )
    )
    db.flush()
    integration.enqueue(
        db,
        event_type="order.confirmed",
        aggregate_type="trade_order",
        aggregate_id=order.order_no,
        payload={
            "order_no": order.order_no,
            "total_amount": float(order.total_amount),
            "confirmed_at": order.confirmed_at.isoformat(),
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                }
                for item in order.items
            ],
        },
    )
    return order


def deliver_order(db: Session, order: TradeOrder, data: DeliverIn, user: User) -> TradeOrder:
    if order.status not in ("confirmed", "delivering"):
        raise Conflict(f"订单当前状态【{order.status}】不可发货")
    if not is_unrestricted(user) and order.supplier_enterprise_id != user.enterprise_id:
        raise Forbidden("只有供应商可以发货")
    delivered_map: Dict[int, Decimal] = {}
    for row in data.items:
        delivered_map[int(row.item_id)] = q3(row.delivered_quantity)
    for item in order.items:
        if item.id in delivered_map:
            quantity = delivered_map[item.id]
            if quantity > dec(item.quantity):
                raise BadRequest(f"发货数量超过订单数量：{item.product_name}")
            item.delivered_quantity = quantity
    if data.logistics_company:
        order.logistics_company = data.logistics_company
    if data.logistics_no:
        order.logistics_no = data.logistics_no
    if data.remark:
        order.remark = f"{order.remark or ''} {data.remark}".strip()
    order.status = "delivering"
    order.delivered_at = now()
    db.flush()
    integration.enqueue(
        db,
        event_type="order.delivered",
        aggregate_type="trade_order",
        aggregate_id=order.order_no,
        payload={
            "order_no": order.order_no,
            "logistics_company": order.logistics_company,
            "logistics_no": order.logistics_no,
            "items": [
                {"item_id": item.id, "delivered_quantity": float(item.delivered_quantity)}
                for item in order.items
            ],
        },
    )
    return order


def complete_order(db: Session, order: TradeOrder, user: User) -> TradeOrder:
    if order.status not in ("delivering", "confirmed"):
        raise Conflict(f"订单当前状态【{order.status}】不可完成")
    if not is_unrestricted(user) and user.enterprise_id not in (
        order.supplier_enterprise_id,
        order.buyer_enterprise_id,
    ):
        raise Forbidden("无权操作该订单")
    for item in order.items:
        if dec(item.delivered_quantity) <= 0:
            item.delivered_quantity = item.quantity
    order.status = "completed"
    order.completed_at = now()
    db.flush()
    build_settlement_for_order(db, order, user)
    return order


def cancel_order(db: Session, order: TradeOrder, user: User, reason: Optional[str] = None) -> TradeOrder:
    if order.status in ("completed", "settled", "cancelled"):
        raise Conflict(f"订单当前状态【{order.status}】不可取消")
    if not is_unrestricted(user) and user.enterprise_id not in (
        order.supplier_enterprise_id,
        order.buyer_enterprise_id,
    ):
        raise Forbidden("无权操作该订单")
    if order.stock_deducted:
        for item in order.items:
            revert_out(
                db,
                item.product_id,
                dec(item.quantity),
                warehouse_id=item.warehouse_id,
                batch_no=item.batch_no,
                ref_no=order.order_no,
                operator=user,
            )
        order.stock_deducted = False
    else:
        for item in order.items:
            release(db, item.product_id, dec(item.quantity), warehouse_id=item.warehouse_id)
    order.status = "cancelled"
    order.cancelled_at = now()
    order.cancel_reason = reason
    db.flush()
    flows = db.query(TransactionFlow).filter(TransactionFlow.order_id == order.id).all()
    for flow in flows:
        if flow.pay_status == "pending":
            flow.pay_status = "failed"
            flow.remark = f"{flow.remark or ''} 订单已取消".strip()
    integration.enqueue(
        db,
        event_type="order.cancelled",
        aggregate_type="trade_order",
        aggregate_id=order.order_no,
        payload={"order_no": order.order_no, "reason": reason or ""},
    )
    return order


def build_settlement_for_order(db: Session, order: TradeOrder, user: Optional[User] = None) -> Settlement:
    """订单完成后生成供应商应收结算单（含平台服务费）。"""
    existing = (
        db.query(SettlementLine)
        .filter(SettlementLine.biz_type == "order", SettlementLine.biz_no == order.order_no)
        .first()
    )
    if existing is not None:
        settlement = db.get(Settlement, existing.settlement_id)
        if settlement is not None:
            return settlement
    fee_rate = dec(settings.PLATFORM_SERVICE_FEE_RATE)
    order_amount = dec(order.total_amount)
    fee_amount = (order_amount * fee_rate).quantize(Decimal("0.01"))
    settlement = Settlement(
        settlement_no=next_no(db, "settlement", _year_prefix("GZ-SET")),
        enterprise_id=order.supplier_enterprise_id,
        settle_type="receivable",
        period_start=(order.completed_at or now()).date(),
        period_end=(order.completed_at or now()).date(),
        order_amount=order_amount,
        fee_amount=fee_amount,
        settle_amount=(order_amount - fee_amount).quantize(Decimal("0.01")),
        settled_amount=ZERO,
        pay_status="unpaid",
        receive_status="unconfirmed",
        status="pending",
        remark=f"订单 {order.order_no} 完成自动生成",
        created_by=user.id if user else None,
    )
    db.add(settlement)
    db.flush()
    db.add(
        SettlementLine(
            settlement_id=settlement.id,
            biz_type="order",
            biz_no=order.order_no,
            order_id=order.id,
            amount=order_amount,
            fee_rate=ZERO,
            remark="订单货款",
        )
    )
    if fee_amount > 0:
        db.add(
            SettlementLine(
                settlement_id=settlement.id,
                biz_type="service_fee",
                biz_no=order.order_no,
                order_id=order.id,
                amount=fee_amount,
                fee_rate=fee_rate,
                remark="平台服务费",
            )
        )
    db.flush()
    integration.enqueue(
        db,
        event_type="settlement.created",
        aggregate_type="settlement",
        aggregate_id=settlement.settlement_no,
        payload=integration.settlement_payload(settlement, []),
    )
    return settlement


def order_timeline(db: Session, order: TradeOrder) -> List[dict]:
    timeline: List[dict] = [
        {
            "status": "draft",
            "title": "订单创建",
            "description": f"订单号 {order.order_no}",
            "occurred_at": order.created_at,
            "operator": None,
        }
    ]
    if order.confirmed_at:
        timeline.append(
            {
                "status": "confirmed",
                "title": "供应商确认订单",
                "description": "已扣减库存并生成交易流水",
                "occurred_at": order.confirmed_at,
                "operator": None,
            }
        )
    if order.delivered_at:
        timeline.append(
            {
                "status": "delivering",
                "title": "供应商发货",
                "description": " ".join(
                    item for item in [order.logistics_company, order.logistics_no] if item
                )
                or "已发货",
                "occurred_at": order.delivered_at,
                "operator": None,
            }
        )
    if order.completed_at:
        timeline.append(
            {
                "status": "completed",
                "title": "订单完成",
                "description": "已生成应收结算单",
                "occurred_at": order.completed_at,
                "operator": None,
            }
        )
    if order.cancelled_at:
        timeline.append(
            {
                "status": "cancelled",
                "title": "订单取消",
                "description": order.cancel_reason or "",
                "occurred_at": order.cancelled_at,
                "operator": None,
            }
        )
    flows = (
        db.query(TransactionFlow)
        .filter(TransactionFlow.order_id == order.id)
        .order_by(TransactionFlow.id.asc())
        .all()
    )
    for flow in flows:
        if flow.paid_at:
            timeline.append(
                {
                    "status": "settled",
                    "title": "登记回款",
                    "description": f"流水号 {flow.flow_no}，金额 {flow.amount}",
                    "occurred_at": flow.paid_at,
                    "operator": None,
                }
            )
    # 一张结算单可覆盖多笔订单，回款流水不一定带单笔 order_id。
    # 通过结算明细关联订单，结清后在订单轨迹展示真实结算结果。
    settled_rows = (
        db.query(Settlement)
        .join(SettlementLine, SettlementLine.settlement_id == Settlement.id)
        .filter(SettlementLine.order_id == order.id, SettlementLine.biz_type == "order",
                Settlement.status == "settled")
        .all()
    )
    for settlement in settled_rows:
        timeline.append({
            "status": "settled", "title": "结算完成",
            "description": f"结算单 {settlement.settlement_no} 已结清",
            "occurred_at": settlement.settled_at,
            "operator": None,
        })
    timeline.sort(key=lambda row: (row["occurred_at"] is None, row["occurred_at"]))
    return timeline


# --------------------------------------------------------------------------- 合同


def create_contract(db: Session, data: ContractIn, user: User) -> Contract:
    order: Optional[TradeOrder] = None
    if data.order_id:
        order = db.get(TradeOrder, data.order_id)
        if order is None:
            raise NotFound("订单不存在")
    buyer_id = data.buyer_enterprise_id or (order.buyer_enterprise_id if order else user.enterprise_id)
    supplier_id = data.supplier_enterprise_id or (order.supplier_enterprise_id if order else None)
    if not buyer_id or not supplier_id:
        raise BadRequest("缺少买方或卖方企业信息")
    amount = dec(data.amount) if data.amount is not None else (dec(order.total_amount) if order else ZERO)
    title = data.title or (f"瓜子油料购销合同（{order.order_no}）" if order else "瓜子油料购销合同")
    contract = Contract(
        contract_no=next_no(db, "contract", _year_prefix("GZ-CT")),
        title=title,
        order_id=order.id if order else None,
        buyer_enterprise_id=buyer_id,
        supplier_enterprise_id=supplier_id,
        amount=amount,
        start_date=data.start_date,
        end_date=data.end_date,
        file_url=data.file_url,
        terms=data.terms,
        status="pending_sign",
        remark=data.remark,
    )
    db.add(contract)
    db.flush()
    if order is not None:
        order.contract_id = contract.id
        db.flush()
    integration.enqueue(
        db,
        event_type="contract.created",
        aggregate_type="contract",
        aggregate_id=contract.contract_no,
        payload={
            "contract_no": contract.contract_no,
            "title": contract.title,
            "order_no": order.order_no if order else None,
            "amount": float(contract.amount),
        },
    )
    return contract


def sign_contract(db: Session, contract: Contract, party: str, user: User) -> Contract:
    if contract.status in ("terminated", "expired"):
        raise Conflict(f"合同当前状态【{contract.status}】不可签署")
    if party == "buyer":
        if not is_unrestricted(user) and user.enterprise_id != contract.buyer_enterprise_id:
            raise Forbidden("只有买方企业可以签署买方栏")
        contract.signed_by_buyer = True
        contract.buyer_signed_at = now()
    elif party == "supplier":
        if not is_unrestricted(user) and user.enterprise_id != contract.supplier_enterprise_id:
            raise Forbidden("只有卖方企业可以签署卖方栏")
        contract.signed_by_supplier = True
        contract.supplier_signed_at = now()
    else:
        raise BadRequest("party 取值必须为 buyer 或 supplier")
    if contract.signed_by_buyer and contract.signed_by_supplier:
        contract.status = "effective"
        contract.sign_date = now().date()
    else:
        contract.status = "pending_sign"
    db.flush()
    return contract
