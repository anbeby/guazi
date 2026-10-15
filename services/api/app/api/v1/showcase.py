# -*- coding: utf-8 -*-
"""演示门户公开只读数据；仅输出已审核上架的商品与公开经营信息。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ApiResponse, ok
from app.models.enterprise import Enterprise, Park
from app.models.product import Category, Inventory, Product
from app.models.trade import TradeOrder
from app.models.matching import MatchCase, PurchaseRequirement
from app.services.enterprise_images import enterprise_image_urls
from app.services.product_images import public_product_image

router = APIRouter(prefix="/showcase", tags=["产业展示"])


@router.get("", response_model=ApiResponse[dict], summary="演示门户公开数据")
def showcase(db: Session = Depends(get_db)) -> dict:
    park = db.query(Park).filter(Park.status == "active").order_by(Park.id).first()
    enterprises = (
        db.query(Enterprise)
        .filter(Enterprise.status == "active", Enterprise.audit_status == "approved")
        .order_by(Enterprise.id)
        .all()
    )
    products = (
        db.query(Product, Category.code, Category.name, Enterprise.name)
        .join(Category, Category.id == Product.category_id)
        .join(Enterprise, Enterprise.id == Product.enterprise_id)
        .filter(Product.status == "published", Product.audit_status == "approved", Product.supply_status == "active",
                Enterprise.status == "active", Enterprise.audit_status == "approved")
        .order_by(Product.id.desc())
        .limit(40)
        .all()
    )
    stock_rows = db.query(Inventory.product_id, func.sum(Inventory.quantity)).group_by(Inventory.product_id).all()
    stock_by_product = {product_id: float(quantity or 0) for product_id, quantity in stock_rows}
    recent_orders = (
        db.query(TradeOrder)
        .filter(TradeOrder.status.in_(["confirmed", "delivering", "completed", "settled"]))
        .order_by(TradeOrder.created_at.desc(), TradeOrder.id.desc())
        .limit(8)
        .all()
    )
    purchase_needs = (
        db.query(PurchaseRequirement, Enterprise.name)
        .join(Enterprise, Enterprise.id == PurchaseRequirement.buyer_enterprise_id)
        .filter(PurchaseRequirement.status == "open", Enterprise.status == "active", Enterprise.audit_status == "approved")
        .order_by(PurchaseRequirement.created_at.desc(), PurchaseRequirement.id.desc())
        .limit(6).all()
    )
    enterprise_names = {item.id: item.name for item in enterprises}
    enterprise_images = enterprise_image_urls(db, [item.id for item in enterprises])
    trade_amount = db.query(func.coalesce(func.sum(TradeOrder.total_amount), 0)).filter(
        TradeOrder.status.in_(["confirmed", "delivering", "completed", "settled"])
    ).scalar()
    return ok({
        "park": {"name": park.name, "region": park.region, "description": park.description} if park else None,
        "metrics": {
            "enterprise_count": len(enterprises),
            "product_count": db.query(Product).filter(Product.status == "published", Product.audit_status == "approved", Product.supply_status == "active").count(),
            "trade_amount": float(trade_amount or 0),
            "inventory_quantity": sum(stock_by_product.values()),
            "order_count": db.query(TradeOrder).count(),
            "requirement_count": db.query(PurchaseRequirement).count(),
            "match_count": db.query(MatchCase).count(),
        },
        "products": [
            {"id": item.id, "name": item.name, "spec": item.spec, "grade": item.grade,
             "origin": item.origin, "price": float(item.price or 0), "unit": item.unit,
             "category": category_name, "category_code": category_code,
             "enterprise": enterprise_name, "stock": stock_by_product.get(item.id, 0),
             "image": public_product_image(item.main_image, category_code),
             "supply_quantity": float(item.supply_quantity or stock_by_product.get(item.id, 0)),
             "supply_period": item.supply_period, "pricing_mode": item.pricing_mode,
             "supply_status": item.supply_status, "allow_inquiry": item.allow_inquiry,
             "allow_bulk_purchase": item.allow_bulk_purchase,
             "created_at": item.created_at.isoformat() if item.created_at else None,
             "enterprise_id": item.enterprise_id}
            for item, category_code, category_name, enterprise_name in products
        ],
        "enterprises": [
            {"id": item.id, "name": item.name, "type": item.enterprise_type,
             "region": item.region, "scope": item.business_scope,
             "image": enterprise_images.get(item.id) or (
                 "/demo/trace.png" if "仓储" in (item.business_scope or "") else
                 "/demo/hero.png" if item.enterprise_type == "supplier" else "/demo/park.png"
             )}
            for item in enterprises
        ],
        "recent_deals": [
            {"order_no": order.order_no, "product": order.items[0].product_name if order.items else "瓜子油料",
             "quantity": float(sum((item.quantity for item in order.items), 0)),
             "amount": float(order.total_amount or 0),
             "supplier": enterprise_names.get(order.supplier_enterprise_id, "供应企业"),
             "date": order.created_at.date().isoformat() if order.created_at else None}
            for order in recent_orders
        ],
        "purchase_needs": [
            {"id": need.id, "title": need.title, "product_name": need.product_name,
             "quantity": float(need.quantity), "unit": need.unit,
             "purchase_region": need.purchase_region, "buyer_enterprise_name": buyer_name,
             "created_at": need.created_at.isoformat() if need.created_at else None,
             "status": need.status}
            for need, buyer_name in purchase_needs
        ],
    })
