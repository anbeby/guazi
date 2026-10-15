# -*- coding: utf-8 -*-
"""领导演示数据扩充。固定场景、幂等执行，不改业务模型与交易流程。

用法：python -m app.demo_enrichment
所有新增主体、图片和交易均为本地演示内容，不代表真实企业资料或成交。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from app import initial_data as seed
from app.core.database import get_session_factory
from app.models.enterprise import Enterprise, Park
from app.models.org import OrgUnit, User
from app.models.product import Category, Inventory, Product
from app.models.trade import Inquiry
from app.schemas.stock import StockInIn
from app.schemas.trade import DeliverIn, DeliverItemIn, InquiryIn, QuotationIn
from app.services import inventory_service, trade_service

log = logging.getLogger("gz-demo")

# 名称、经营类型和经营范围为人工编写的北屯产业链演示样本。
ENTITIES = [
    (7, "北屯向阳油料加工有限公司", "merchant", "葵花籽精选、脱壳与初加工", "xiangyang"),
    (8, "第十师绿洲瓜子加工有限公司", "merchant", "食葵分级、烘炒与包装", "lvzhou"),
    (9, "北屯雪域籽仁食品有限公司", "supplier", "葵花籽仁、南瓜籽仁加工供应", "xueyu"),
    (10, "北屯丰禾农产品贸易有限公司", "merchant", "葵花籽、南瓜籽收购与现货贸易", "fenghe"),
    (11, "新疆丝路油脂贸易有限公司", "supplier", "油葵原料与油料产品贸易", "silu"),
    (12, "北屯北丰供应链有限公司", "merchant", "农产品集采、分拣与仓配服务", "beifeng"),
    (13, "北屯粮仓仓储服务有限公司", "merchant", "瓜子油料恒温仓储与物流配送", "liangcang"),
    (14, "第十师恒丰粮油仓储有限公司", "merchant", "粮油仓储、库位管理与运输", "hengfeng"),
    (15, "阿勒泰优品农产品采购有限公司", "buyer", "瓜子油料和食品原料采购", "altaybuyer"),
    (16, "乌鲁木齐天山食品采购有限公司", "buyer", "炒货原料采购与供应链服务", "tianshanbuyer"),
    (17, "石河子绿谷休闲食品有限公司", "buyer", "休闲食品原料采购与加工", "lvgu"),
    (18, "克拉玛依西域商贸有限公司", "buyer", "农副产品批发与渠道分销", "kelamayi"),
]

# 编码、名称、品类、供应商序号、规格、等级、产地、元/吨、初始吨数、配图。
GOODS = [
    ("GZ-SUN-0101", "北屯大粒食葵籽", "GZ-SUN", 7, "千粒重≥190g，水分≤9%", "special", "新疆北屯", 7200, 210, "sunflower"),
    ("GZ-SUN-0102", "第十师精选葵花籽", "GZ-SUN", 8, "大粒精选，杂质≤1%", "first", "新疆北屯", 6900, 185, "sunflower"),
    ("GZ-SUN-0103", "北屯油葵籽原料", "GZ-SUN", 11, "含油率≥43%，水分≤9%", "first", "新疆北屯", 5850, 420, "sunflower"),
    ("GZ-SUN-0104", "向阳烘焙级葵花籽", "GZ-SUN", 7, "颗粒均匀，烘焙加工级", "first", "新疆北屯", 7450, 145, "sunflower"),
    ("GZ-SUN-0105", "丰禾秋收食葵籽", "GZ-SUN", 10, "2025季，50kg/袋", "first", "新疆阿勒泰", 6650, 165, "sunflower"),
    ("GZ-KER-0101", "北屯一级葵花籽仁", "GZ-KERNEL", 9, "脱壳精选，水分≤7%", "first", "新疆北屯", 12800, 90, "kernel"),
    ("GZ-KER-0102", "雪域烘焙用葵花籽仁", "GZ-KERNEL", 9, "整仁率≥92%，25kg/箱", "special", "新疆北屯", 13800, 75, "kernel"),
    ("GZ-KER-0103", "绿洲食品级葵花籽仁", "GZ-KERNEL", 8, "食品加工用，杂质≤0.5%", "first", "新疆北屯", 12400, 88, "kernel"),
    ("GZ-KER-0104", "北屯精选南瓜籽仁", "GZ-KERNEL", 9, "脱壳光板仁，25kg/箱", "special", "新疆北屯", 19800, 52, "pumpkin"),
    ("GZ-PUM-0101", "北屯光板南瓜籽", "GZ-PUM", 10, "千粒重≥210g，水分≤8%", "first", "新疆北屯", 13600, 120, "pumpkin"),
    ("GZ-PUM-0102", "第十师大板南瓜籽", "GZ-PUM", 7, "25kg/袋，颗粒饱满", "special", "新疆北屯", 14800, 105, "pumpkin"),
    ("GZ-PUM-0103", "丰禾精选白南瓜籽", "GZ-PUM", 10, "色泽洁白，分级筛选", "first", "新疆阿勒泰", 13900, 110, "pumpkin"),
    ("GZ-SEED-0101", "北屯一级打瓜籽", "GZ-SEED", 12, "片大均匀，水分≤9%", "first", "新疆北屯", 9100, 150, "melon"),
    ("GZ-SEED-0102", "丰禾打瓜籽统货", "GZ-SEED", 10, "原料统货，50kg/袋", "mixed", "新疆北屯", 7800, 205, "melon"),
    ("GZ-SEED-0103", "北丰精选打瓜籽", "GZ-SEED", 12, "杂质≤1%，色泽均匀", "first", "新疆北屯", 8800, 130, "melon"),
    ("GZ-SEED-0104", "绿洲大粒打瓜籽", "GZ-SEED", 8, "大粒筛选，50kg/袋", "special", "新疆北屯", 9400, 95, "melon"),
    ("GZ-ROAST-0101", "北屯原味炒葵花籽", "GZ-PRO-ROAST", 8, "原味，10kg/箱", "first", "新疆北屯", 13200, 65, "roasted"),
    ("GZ-ROAST-0102", "绿洲五香葵花籽", "GZ-PRO-ROAST", 8, "五香炒制，10kg/箱", "first", "新疆北屯", 13900, 55, "roasted"),
    ("GZ-ROAST-0103", "向阳盐焗南瓜籽", "GZ-PRO-ROAST", 7, "盐焗风味，10kg/箱", "special", "新疆北屯", 17200, 42, "roasted"),
    ("GZ-ROAST-0104", "北屯混合炒货籽仁", "GZ-PRO-ROAST", 9, "葵花籽仁与南瓜籽仁混合", "first", "新疆北屯", 18500, 38, "roasted"),
    ("GZ-ROAST-0105", "金穗原味炒瓜子", "GZ-PRO-ROAST", 1, "原味炒制，10kg/箱", "first", "新疆北屯", 12900, 60, "roasted"),
    ("GZ-SUN-0106", "北屯金穗油葵原料", "GZ-SUN", 1, "含油率≥41%，散装", "first", "新疆北屯", 5700, 360, "sunflower"),
    ("GZ-KER-0105", "北屯加工用葵花籽仁", "GZ-KERNEL", 5, "25kg/箱，整仁率≥90%", "first", "新疆北屯", 11900, 48, "kernel"),
]

WAREHOUSE_ROWS = [
    ("WH-XY-01", "向阳精选仓", 7), ("WH-LZ-01", "绿洲加工成品仓", 8),
    ("WH-XYR-01", "雪域籽仁恒温仓", 9), ("WH-FH-01", "丰禾现货仓", 10),
    ("WH-SL-01", "丝路油料仓", 11), ("WH-BF-01", "北丰集配仓", 12),
    ("WH-LC-01", "北屯粮仓一号库", 13), ("WH-HF-01", "恒丰粮油仓", 14),
]

# 固定采购方、商品编码、吨数、距离今天的天数。数量和价格均基于商品档案。
DEALS = [
    (15, "GZ-SUN-0101", 12, 1), (16, "GZ-KER-0101", 8, 2), (17, "GZ-PUM-0101", 9, 3),
    (18, "GZ-SEED-0101", 11, 4), (15, "GZ-ROAST-0101", 7, 5), (16, "GZ-SUN-0103", 18, 6),
    (17, "GZ-KER-0102", 6, 7), (18, "GZ-PUM-0102", 8, 8), (15, "GZ-SEED-0102", 14, 9),
    (16, "GZ-ROAST-0102", 6, 10), (17, "GZ-SUN-0104", 12, 11), (18, "GZ-KER-0103", 7, 12),
    (15, "GZ-PUM-0103", 10, 13), (16, "GZ-SEED-0103", 13, 14), (17, "GZ-ROAST-0103", 5, 15),
    (18, "GZ-SUN-0105", 12, 17), (15, "GZ-KER-0104", 5, 18), (16, "GZ-SEED-0104", 8, 20),
    (17, "GZ-ROAST-0104", 5, 21), (18, "GZ-SUN-0106", 19, 23), (15, "GZ-KER-0105", 6, 25),
    (16, "GZ-ROAST-0105", 7, 27), (17, "GZ-SUN-0102", 14, 28),
]


def run() -> None:
    db = get_session_factory()()
    try:
        park = db.query(Park).filter(Park.code == "PARK-BT01").one()
        park_org = db.query(OrgUnit).filter(OrgUnit.code == "PARK-BT01-ORG").one()
        if not any(code == "GZ-KERNEL" for code, _, _ in seed.CATEGORY_TREE):
            seed.CATEGORY_TREE.append(("GZ-KERNEL", "瓜子仁", "GZ"))
        for index, name, kind, scope, username in ENTITIES:
            code = f"ENT-2025-{index:04d}"
            if any(item["code"] == code for item in seed.ENTERPRISES):
                continue
            seed.ENTERPRISES.append({
                "code": code, "name": name, "credit": f"91659001DEMO{index:08d}",
                "type": kind, "legal_person": "演示负责人", "business_scope": scope,
                "contact_name": "演示联系人", "contact_phone": f"1389900{index:04d}",
                "region": "新疆生产建设兵团第十师北屯市" if kind != "buyer" else "新疆维吾尔自治区",
                "address": f"北屯市瓜子油料产业园演示区 {index} 号",
                "stall_code": f"STALL-{index:03d}" if kind != "buyer" else None,
                "settle_bank": "演示银行", "settle_account_name": name,
                "settle_account_no": f"DEMO-{index:04d}", "username": username,
            })
        for code, name, index in WAREHOUSE_ROWS:
            row = (code, name, f"ENT-2025-{index:04d}", f"北屯瓜子产业园仓储区 {index} 号")
            if row not in seed.WAREHOUSES:
                seed.WAREHOUSES.append(row)
        for code, name, category, owner, spec, grade, origin, price, quantity, photo in GOODS:
            if any(item["code"] == code for item in seed.PRODUCTS):
                continue
            seed.PRODUCTS.append({
                "code": code, "name": name, "category": category,
                "enterprise": f"ENT-2025-{owner:04d}", "spec": spec, "grade": grade,
                "origin": origin, "harvest_year": "2025", "package": "25kg/袋",
                "price": str(price), "warn": "5.000", "batch": f"B-DEMO-{code}",
                "quantity": f"{quantity}.000", "cost": str(Decimal(price) * Decimal("0.9")),
                "photo": photo,
            })
        categories = seed.seed_categories(db)
        enterprises = seed.seed_enterprises(db, park, park_org)
        warehouses = seed.seed_warehouses(db, enterprises)
        products = seed.seed_products(db, categories, enterprises)
        admin = db.query(User).filter(User.username == "admin").one()
        seed.seed_inventory(db, products, warehouses, admin)

        photo_by_category = {"GZ-SUN": "sunflower", "GZ-PUM": "pumpkin", "GZ-SEED": "melon",
                             "GZ-KERNEL": "kernel", "GZ-PRO-ROAST": "roasted"}
        for item in seed.PRODUCTS:
            product = products.get(item["code"])
            if product and not product.main_image:
                photo = item.get("photo") or photo_by_category.get(item["category"], "sunflower")
                product.main_image = f"/demo/{photo}.png"
                product.images = [product.main_image]

        for code, *_ in GOODS[:14]:
            product = products[code]
            item = next(row for row in seed.PRODUCTS if row["code"] == code)
            warehouse = warehouses[item["enterprise"]]
            batch = f"B-DEMO-2-{code}"
            exists = db.query(Inventory).filter(Inventory.product_id == product.id, Inventory.batch_no == batch).first()
            if not exists:
                inventory_service.stock_in(db, StockInIn(
                    product_id=product.id, warehouse_id=warehouse.id, batch_no=batch,
                    quantity=Decimal("24.000"), unit_cost=Decimal(item["cost"]),
                    production_date=date.today() - timedelta(days=18), quality_status="qualified",
                    ref_type="demo", ref_no="DEMO-BATCH-2", remark="领导演示第二库存批次",
                ), admin)
        db.commit()

        completed = 0
        for buyer_index, product_code, quantity, days_ago in DEALS:
            marker = f"领导演示场景:{product_code}:{buyer_index}:{days_ago}"
            if db.query(Inquiry.id).filter(Inquiry.remark == marker).first():
                continue
            product = products[product_code]
            supplier = db.query(User).filter(User.enterprise_id == product.enterprise_id).first()
            buyer_enterprise = enterprises[f"ENT-2025-{buyer_index:04d}"]
            buyer = db.query(User).filter(User.enterprise_id == buyer_enterprise.id).first()
            price = Decimal(product.price) * Decimal("0.98")
            inquiry = trade_service.create_inquiry(db, InquiryIn(
                product_id=product.id, quantity=Decimal(quantity), unit="ton",
                supplier_enterprise_id=product.enterprise_id, expect_price=price,
                expect_delivery_date=date.today() + timedelta(days=7),
                delivery_address=buyer_enterprise.address, remark=marker, submit=True,
            ), buyer)
            quotation = trade_service.create_quotation(db, inquiry, QuotationIn(
                unit_price=price, tax_rate=Decimal("0.09"),
                delivery_date=date.today() + timedelta(days=5),
                payment_terms="货到验收合格后电汇", remark="领导演示报价",
            ), supplier)
            order = trade_service.accept_quotation(db, quotation, buyer)
            trade_service.confirm_order(db, order, supplier)
            trade_service.deliver_order(db, order, DeliverIn(
                items=[DeliverItemIn(item_id=line.id, delivered_quantity=line.quantity) for line in order.items],
                logistics_company="北屯园区物流（演示）", logistics_no=f"DEMO-{days_ago:03d}-{order.id}",
            ), supplier)
            trade_service.complete_order(db, order, supplier)
            trade_date = datetime.now() - timedelta(days=days_ago)
            inquiry.created_at = trade_date - timedelta(days=3)
            quotation.created_at = trade_date - timedelta(days=2)
            order.created_at = trade_date
            order.confirmed_at = trade_date
            order.delivered_at = trade_date + timedelta(days=1)
            order.completed_at = trade_date + timedelta(days=2)
            db.commit()
            completed += 1
        log.info("演示扩充完成：企业=%s 商品=%s 新增交易=%s", len(enterprises), len(products), completed)
    except Exception:
        db.rollback()
        log.exception("演示扩充失败，当前事务已回滚")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
