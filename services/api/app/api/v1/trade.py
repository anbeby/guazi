# -*- coding: utf-8 -*-
"""B2B 交易接口：询价、报价、订单、合同。"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import (
    Lookups,
    contract_out,
    inquiry_out,
    order_out,
    quotation_out,
)
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import BadRequest, Forbidden, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import apply_trade_scope, enterprise_scope_ids, is_unrestricted
from app.models.org import User
from app.models.trade import Contract, Inquiry, Quotation, TradeOrder
from app.schemas.common import ReasonIn
from app.schemas.trade import (
    ContractIn,
    ContractOut,
    ContractSignIn,
    ContractUpdate,
    DeliverIn,
    InquiryDetailOut,
    InquiryIn,
    InquiryOut,
    OrderIn,
    OrderOut,
    OrderTimelineOut,
    QuotationIn,
    QuotationOut,
)
from app.services import trade_service

router = APIRouter(tags=["B2B 交易"])


def _inquiry_quotation_counts(db: Session, inquiry_ids: List[int]) -> Dict[int, int]:
    if not inquiry_ids:
        return {}
    rows = (
        db.query(Quotation.inquiry_id, func.count(Quotation.id))
        .filter(Quotation.inquiry_id.in_(inquiry_ids))
        .group_by(Quotation.inquiry_id)
        .all()
    )
    return {int(row[0]): int(row[1]) for row in rows}


def _quotation_context(db: Session, quotations: List[Quotation]) -> Dict[int, Dict]:
    """为报价单补齐询价单号与买方名称、已生成订单。"""
    inquiry_ids = list({q.inquiry_id for q in quotations})
    context: Dict[int, Dict] = {}
    if not inquiry_ids:
        return context
    inquiries = {i.id: i for i in db.query(Inquiry).filter(Inquiry.id.in_(inquiry_ids)).all()}
    orders = (
        db.query(TradeOrder)
        .filter(TradeOrder.quotation_id.in_([q.id for q in quotations] or [-1]))
        .all()
    )
    order_map = {o.quotation_id: o for o in orders}
    lk = Lookups(db)
    for quotation in quotations:
        inquiry = inquiries.get(quotation.inquiry_id)
        context[quotation.id] = {
            "inquiry_no": inquiry.inquiry_no if inquiry else None,
            "buyer_enterprise_name": lk.enterprise_name(inquiry.buyer_enterprise_id) if inquiry else None,
            "order": order_map.get(quotation.id),
        }
    return context


# --------------------------------------------------------------------------- 询价


@router.get("/inquiries", response_model=ApiResponse[PageData[InquiryOut]], summary="询价单列表")
def list_inquiries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: str = Query("buyer", description="buyer=我发出的询价，supplier=待我报价/我报过价的询价"),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Inquiry)
    if not is_unrestricted(user):
        scope = enterprise_scope_ids(db, user) or []
        enterprise_id = user.enterprise_id
        if role == "supplier":
            if not enterprise_id:
                return ok(paginate([], 0, page, page_size))
            quoted_ids = [
                row[0]
                for row in db.query(Quotation.inquiry_id)
                .filter(Quotation.supplier_enterprise_id == enterprise_id)
                .all()
            ]
            query = query.filter(
                or_(
                    Inquiry.supplier_enterprise_id == enterprise_id,
                    Inquiry.id.in_(quoted_ids or [-1]),
                    Inquiry.supplier_enterprise_id.is_(None),
                )
            )
        else:
            query = query.filter(Inquiry.buyer_enterprise_id.in_(scope or [-1]))
    elif role == "supplier" and not user.enterprise_id:
        pass
    if status:
        query = query.filter(Inquiry.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(Inquiry.inquiry_no.like(like))
    total = query.count()
    rows = query.order_by(Inquiry.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    counts = _inquiry_quotation_counts(db, [row.id for row in rows])
    return ok(
        paginate(
            [inquiry_out(lk, row, counts.get(row.id, 0)) for row in rows], total, page, page_size
        )
    )


@router.post("/inquiries", response_model=ApiResponse[InquiryOut], summary="创建询价单")
def create_inquiry(
    payload: InquiryIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    inquiry = trade_service.create_inquiry(db, payload, user)
    return ok(inquiry_out(lk, inquiry))


@router.get("/inquiries/{inquiry_id}", response_model=ApiResponse[InquiryDetailOut], summary="询价单详情")
def get_inquiry(
    inquiry_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        quotations_owned = any(
            q.supplier_enterprise_id == user.enterprise_id for q in inquiry.quotations
        )
        if (
            inquiry.buyer_enterprise_id not in allowed
            and inquiry.supplier_enterprise_id not in allowed
            and not quotations_owned
        ):
            raise Forbidden("无权查看该询价单")
    data = inquiry_out(lk, inquiry, len(inquiry.quotations))
    context = _quotation_context(db, list(inquiry.quotations))
    data["quotations"] = [
        quotation_out(lk, row, context.get(row.id, {}).get("order"))
        for row in inquiry.quotations
    ]
    for item in data["quotations"]:
        item["inquiry_no"] = inquiry.inquiry_no
    return ok(data)


@router.post("/inquiries/{inquiry_id}/submit", response_model=ApiResponse[InquiryOut], summary="提交询价单")
def submit_inquiry(
    inquiry_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    inquiry = trade_service.submit_inquiry(db, inquiry, user)
    return ok(inquiry_out(lk, inquiry))


@router.post("/inquiries/{inquiry_id}/cancel", response_model=ApiResponse[InquiryOut], summary="取消询价单")
def cancel_inquiry(
    inquiry_id: int,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    inquiry = trade_service.cancel_inquiry(db, inquiry, user, payload.reason)
    return ok(inquiry_out(lk, inquiry))


@router.get(
    "/inquiries/{inquiry_id}/quotations",
    response_model=ApiResponse[List[QuotationOut]],
    summary="询价单的报价列表",
)
def list_inquiry_quotations(
    inquiry_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    rows = list(inquiry.quotations)
    context = _quotation_context(db, rows)
    items = []
    for row in rows:
        ctx = context.get(row.id, {})
        item = quotation_out(lk, row, ctx.get("order"))
        item["inquiry_no"] = inquiry.inquiry_no
        item["buyer_enterprise_name"] = ctx.get("buyer_enterprise_name")
        items.append(item)
    return ok(items)


@router.post(
    "/inquiries/{inquiry_id}/quotations",
    response_model=ApiResponse[QuotationOut],
    summary="供应商报价",
)
def create_quotation(
    inquiry_id: int,
    payload: QuotationIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFound("询价单不存在")
    quotation = trade_service.create_quotation(db, inquiry, payload, user)
    item = quotation_out(lk, quotation)
    item["inquiry_no"] = inquiry.inquiry_no
    item["buyer_enterprise_name"] = lk.enterprise_name(inquiry.buyer_enterprise_id)
    return ok(item)


# --------------------------------------------------------------------------- 报价


@router.get("/quotations", response_model=ApiResponse[PageData[QuotationOut]], summary="报价单列表")
def list_quotations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: str = Query("supplier", description="supplier=我提交的报价，buyer=我收到的报价"),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Quotation)
    if not is_unrestricted(user):
        scope = enterprise_scope_ids(db, user) or []
        if role == "buyer":
            inquiry_ids = [
                row[0]
                for row in db.query(Inquiry.id).filter(Inquiry.buyer_enterprise_id.in_(scope or [-1])).all()
            ]
            query = query.filter(Quotation.inquiry_id.in_(inquiry_ids or [-1]))
        else:
            query = query.filter(Quotation.supplier_enterprise_id.in_(scope or [-1]))
    if status:
        query = query.filter(Quotation.status == status)
    total = query.count()
    rows = query.order_by(Quotation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    context = _quotation_context(db, rows)
    items = []
    for row in rows:
        ctx = context.get(row.id, {})
        item = quotation_out(lk, row, ctx.get("order"))
        item["inquiry_no"] = ctx.get("inquiry_no")
        item["buyer_enterprise_name"] = ctx.get("buyer_enterprise_name")
        items.append(item)
    return ok(paginate(items, total, page, page_size))


@router.post("/quotations/{quotation_id}/accept", response_model=ApiResponse[OrderOut], summary="接受报价并生成订单")
def accept_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise NotFound("报价单不存在")
    order = trade_service.accept_quotation(db, quotation, user)
    return ok(order_out(lk, order))


@router.post("/quotations/{quotation_id}/reject", response_model=ApiResponse[QuotationOut], summary="拒绝报价")
def reject_quotation(
    quotation_id: int,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    quotation = db.get(Quotation, quotation_id)
    if quotation is None:
        raise NotFound("报价单不存在")
    quotation = trade_service.reject_quotation(db, quotation, user, payload.reason)
    inquiry = db.get(Inquiry, quotation.inquiry_id)
    item = quotation_out(lk, quotation)
    item["inquiry_no"] = inquiry.inquiry_no if inquiry else None
    return ok(item)


# --------------------------------------------------------------------------- 订单


@router.get("/orders", response_model=ApiResponse[PageData[OrderOut]], summary="订单列表")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: str = Query("all", description="all / buyer / supplier"),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(TradeOrder)
    if keyword:
        query = query.filter(TradeOrder.order_no.like(f"%{keyword.strip()}%"))
    if status:
        query = query.filter(TradeOrder.status == status)
    if start_date:
        query = query.filter(func.date(TradeOrder.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(TradeOrder.created_at) <= end_date)
    if not is_unrestricted(user):
        scope = enterprise_scope_ids(db, user) or []
        if role == "buyer":
            query = query.filter(TradeOrder.buyer_enterprise_id.in_(scope or [-1]))
        elif role == "supplier":
            query = query.filter(TradeOrder.supplier_enterprise_id.in_(scope or [-1]))
        else:
            query = query.filter(
                or_(
                    TradeOrder.buyer_enterprise_id.in_(scope or [-1]),
                    TradeOrder.supplier_enterprise_id.in_(scope or [-1]),
                )
            )
    total = query.count()
    rows = query.order_by(TradeOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    contracts = {
        row.order_id: row
        for row in db.query(Contract)
        .filter(Contract.order_id.in_([o.id for o in rows] or [-1]))
        .all()
    }
    return ok(
        paginate(
            [order_out(lk, row, contracts.get(row.id), with_items=False) for row in rows],
            total,
            page,
            page_size,
        )
    )


@router.post("/orders", response_model=ApiResponse[OrderOut], summary="直接下单")
def create_order(
    payload: OrderIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    order = trade_service.create_order(db, payload, user)
    return ok(order_out(lk, order))


@router.get("/orders/{order_id}", response_model=ApiResponse[OrderOut], summary="订单详情")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise NotFound("订单不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if order.buyer_enterprise_id not in allowed and order.supplier_enterprise_id not in allowed:
            raise Forbidden("无权查看该订单")
    contract = db.query(Contract).filter(Contract.order_id == order.id).first()
    return ok(order_out(lk, order, contract))


@router.post("/orders/{order_id}/confirm", response_model=ApiResponse[OrderOut], summary="供应商确认订单（扣减库存）")
def confirm_order(
    order_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise NotFound("订单不存在")
    order = trade_service.confirm_order(db, order, user)
    return ok(order_out(lk, order))


@router.post("/orders/{order_id}/deliver", response_model=ApiResponse[OrderOut], summary="供应商发货")
def deliver_order(
    order_id: int,
    payload: DeliverIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise NotFound("订单不存在")
    order = trade_service.deliver_order(db, order, payload, user)
    return ok(order_out(lk, order))


@router.post("/orders/{order_id}/complete", response_model=ApiResponse[OrderOut], summary="订单完成（生成结算单）")
def complete_order(
    order_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise NotFound("订单不存在")
    order = trade_service.complete_order(db, order, user)
    return ok(order_out(lk, order))


@router.post("/orders/{order_id}/cancel", response_model=ApiResponse[OrderOut], summary="取消订单")
def cancel_order(
    order_id: int,
    payload: ReasonIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise NotFound("订单不存在")
    order = trade_service.cancel_order(db, order, user, payload.reason)
    return ok(order_out(lk, order))


@router.get(
    "/orders/{order_id}/timeline",
    response_model=ApiResponse[List[OrderTimelineOut]],
    summary="订单状态轨迹",
)
def order_timeline(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require("trade:read")),
) -> dict:
    order = db.get(TradeOrder, order_id)
    if order is None:
        raise NotFound("订单不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if order.buyer_enterprise_id not in allowed and order.supplier_enterprise_id not in allowed:
            raise Forbidden("无权查看该订单")
    return ok(trade_service.order_timeline(db, order))


# --------------------------------------------------------------------------- 合同


@router.get("/contracts", response_model=ApiResponse[PageData[ContractOut]], summary="合同列表")
def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Contract)
    if status:
        query = query.filter(Contract.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Contract.contract_no.like(like), Contract.title.like(like)))
    query = apply_trade_scope(query, Contract, user, db)
    total = query.count()
    rows = query.order_by(Contract.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    order_ids = [row.order_id for row in rows if row.order_id]
    orders = {
        o.id: o for o in db.query(TradeOrder).filter(TradeOrder.id.in_(order_ids or [-1])).all()
    }
    return ok(
        paginate(
            [contract_out(lk, row, orders.get(row.order_id)) for row in rows], total, page, page_size
        )
    )


@router.post("/contracts", response_model=ApiResponse[ContractOut], summary="生成合同")
def create_contract(
    payload: ContractIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    contract = trade_service.create_contract(db, payload, user)
    order = db.get(TradeOrder, contract.order_id) if contract.order_id else None
    return ok(contract_out(lk, contract, order))


@router.get("/contracts/{contract_id}", response_model=ApiResponse[ContractOut], summary="合同详情")
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:read")),
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise NotFound("合同不存在")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if (
            contract.buyer_enterprise_id not in allowed
            and contract.supplier_enterprise_id not in allowed
        ):
            raise Forbidden("无权查看该合同")
    order = db.get(TradeOrder, contract.order_id) if contract.order_id else None
    return ok(contract_out(lk, contract, order))


@router.put("/contracts/{contract_id}", response_model=ApiResponse[ContractOut], summary="更新合同")
def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise NotFound("合同不存在")
    if contract.status in ("effective", "terminated"):
        raise BadRequest("已生效或已终止的合同不可修改")
    if not is_unrestricted(user):
        allowed = set(enterprise_scope_ids(db, user) or [])
        if (
            contract.buyer_enterprise_id not in allowed
            and contract.supplier_enterprise_id not in allowed
        ):
            raise Forbidden("无权修改该合同")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)
    db.flush()
    order = db.get(TradeOrder, contract.order_id) if contract.order_id else None
    return ok(contract_out(lk, contract, order))


@router.post("/contracts/{contract_id}/sign", response_model=ApiResponse[ContractOut], summary="合同签署")
def sign_contract(
    contract_id: int,
    payload: ContractSignIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("trade:write")),
) -> dict:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise NotFound("合同不存在")
    contract = trade_service.sign_contract(db, contract, payload.party, user)
    order = db.get(TradeOrder, contract.order_id) if contract.order_id else None
    return ok(contract_out(lk, contract, order))
