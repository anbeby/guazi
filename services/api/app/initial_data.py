# -*- coding: utf-8 -*-
"""数据库初始化与种子数据（幂等，可重复执行）。

用法：
    python -m app.initial_data              # 初始化基础数据 + 演示交易闭环
    python -m app.initial_data --no-demo    # 只初始化基础数据
    python -m app.initial_data --reset      # 危险：删除全部业务表后重建
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.database import get_engine, get_session_factory, init_db
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import hash_password
from app.core.timeutil import now
from app.models.enterprise import Enterprise, Park, ParkZone, Stall
from app.models.org import OrgUnit, Permission, Role, User
from app.models.product import Category, Product, StorageLocation, Warehouse
from app.schemas.stock import StockInIn
from app.schemas.trade import DeliverIn, DeliverItemIn, InquiryIn, QuotationIn
from app.services import inventory_service, trade_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gz-init")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "Admin@123")
DEFAULT_PASSWORD = os.getenv("INITIAL_OPERATOR_PASSWORD", "Gz@123456")

CATEGORY_TREE = [
    ("GZ", "瓜子油料", None),
    ("GZ-SUN", "葵花籽", "GZ"),
    ("GZ-PUM", "南瓜籽", "GZ"),
    ("GZ-SEED", "打瓜籽", "GZ"),
    ("GZ-PRO", "加工产品", "GZ"),
    ("GZ-PRO-ROAST", "炒货成品", "GZ-PRO"),
    ("GZ-PRO-OIL", "榨油原料", "GZ-PRO"),
    ("GZ-PRO-FEED", "饲料原料", "GZ-PRO"),
]


# --------------------------------------------------------------------------- 权限与角色


def seed_permissions(db: Session) -> int:
    created = 0
    existing = {row.code: row for row in db.query(Permission).all()}
    for code, name, module in PERMISSIONS:
        row = existing.get(code)
        if row is None:
            db.add(Permission(code=code, name=name, module=module, description=f"{module} 模块权限"))
            created += 1
        else:
            row.name = name
            row.module = module
    db.flush()
    logger.info("权限字典：新增 %s 条，共 %s 条", created, len(PERMISSIONS))
    return created


def seed_roles(db: Session) -> int:
    permissions = {row.code: row for row in db.query(Permission).all()}
    created = 0
    for code, (name, codes, is_super) in ROLES.items():
        role = db.query(Role).filter(Role.code == code).first()
        if role is None:
            role = Role(code=code, name=name, description=f"{name}（平台内置角色）", is_system=True)
            db.add(role)
            db.flush()
            created += 1
        role.name = name
        role.permissions = [permissions[c] for c in codes if c in permissions]
    db.flush()
    logger.info("内置角色：新增 %s 个，共 %s 个", created, len(ROLES))
    return created


# --------------------------------------------------------------------------- 组织与园区


def seed_org_and_park(db: Session) -> tuple:
    platform = db.query(OrgUnit).filter(OrgUnit.code == "PLATFORM").first()
    if platform is None:
        platform = OrgUnit(
            code="PLATFORM",
            name="第十师瓜子油料数字化交易平台",
            unit_type="platform",
            region="新疆生产建设兵团第十师北屯市",
            address="北屯市工业园区",
            contact_name="平台运营中心",
            contact_phone="0906-1234567",
            status="active",
            sort=0,
        )
        db.add(platform)
        db.flush()
    park = db.query(Park).filter(Park.code == "PARK-BT01").first()
    if park is None:
        park = Park(
            code="PARK-BT01",
            name="第十师北屯瓜子产业园",
            region="新疆生产建设兵团第十师北屯市",
            address="北屯市经济技术开发区油料产业园 1 号",
            area_total=Decimal("120000.00"),
            contact_name="园区运营部",
            contact_phone="0906-7654321",
            status="active",
            description="瓜子油料现货交易、仓储物流、加工配套一体化园区",
            operator_org_id=platform.id,
        )
        db.add(park)
        db.flush()
    else:
        park.name = "第十师北屯瓜子产业园"
    park_org = db.query(OrgUnit).filter(OrgUnit.code == "PARK-BT01-ORG").first()
    if park_org is None:
        park_org = OrgUnit(
            code="PARK-BT01-ORG",
            name="第十师北屯瓜子产业园运营中心",
            unit_type="park",
            parent_id=platform.id,
            park_id=park.id,
            region=park.region,
            address=park.address,
            contact_name=park.contact_name,
            contact_phone=park.contact_phone,
            status="active",
            sort=1,
        )
        db.add(park_org)
        db.flush()

    zones = [
        ("Z-TRADE", "现货交易区", "trade", 40000),
        ("Z-PROC", "加工配套区", "processing", 35000),
        ("Z-LOGI", "仓储物流区", "logistics", 40000),
        ("Z-SERV", "综合服务区", "service", 5000),
    ]
    for code, name, zone_type, area in zones:
        exists = (
            db.query(ParkZone).filter(ParkZone.park_id == park.id, ParkZone.code == code).first()
        )
        if exists is None:
            db.add(
                ParkZone(
                    park_id=park.id,
                    code=code,
                    name=name,
                    zone_type=zone_type,
                    area=Decimal(str(area)),
                    status="active",
                )
            )
    db.flush()
    trade_zone = db.query(ParkZone).filter(ParkZone.park_id == park.id, ParkZone.code == "Z-TRADE").first()
    created_stalls = 0
    for index in range(1, 41):
        code = f"STALL-{index:03d}"
        if db.query(Stall).filter(Stall.code == code).first():
            continue
        db.add(
            Stall(
                park_id=park.id,
                zone_id=trade_zone.id if trade_zone else None,
                code=code,
                name=f"交易区 {index:03d} 号档口",
                area=Decimal("120.00"),
                monthly_fee=Decimal("3000.00"),
                status="free",
            )
        )
        created_stalls += 1
    db.flush()
    logger.info("园区与组织初始化完成：园区=%s，新增档口 %s 个", park.name, created_stalls)
    return platform, park, park_org


# --------------------------------------------------------------------------- 用户


def seed_users(db: Session, platform: OrgUnit, park_org: OrgUnit) -> dict:
    users = {}
    admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if admin is None:
        admin = User(
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            full_name="平台超级管理员",
            phone="0906-1234567",
            email="admin@gz-platform.local",
            org_id=platform.id,
            is_superuser=True,
            status="active",
            remark="系统初始化账号，首次登录后请修改密码",
        )
        admin.roles = [db.query(Role).filter(Role.code == "platform_admin").first()]
        db.add(admin)
        db.flush()
        logger.info("创建超级管理员：%s", ADMIN_USERNAME)
    users["admin"] = admin

    park_user = db.query(User).filter(User.username == "park01").first()
    if park_user is None:
        park_user = User(
            username="park01",
            password_hash=hash_password(DEFAULT_PASSWORD),
            full_name="园区运营员",
            phone="0906-7654321",
            org_id=park_org.id,
            status="active",
        )
        park_user.roles = [db.query(Role).filter(Role.code == "park_operator").first()]
        db.add(park_user)
        db.flush()
        logger.info("创建园区运营账号：park01")
    users["park01"] = park_user
    return users


# --------------------------------------------------------------------------- 分类


def seed_categories(db: Session) -> dict:
    by_code = {row.code: row for row in db.query(Category).all()}
    created = 0
    for code, name, parent_code in CATEGORY_TREE:
        if code in by_code:
            continue
        parent = by_code.get(parent_code) if parent_code else None
        level = (parent.level + 1) if parent else 1
        row = Category(
            code=code,
            name=name,
            parent_id=parent.id if parent else None,
            level=level,
            sort=len(by_code),
            status="active",
            description=f"{name}（平台标准分类）",
        )
        db.add(row)
        db.flush()
        by_code[code] = row
        created += 1
    logger.info("商品分类：新增 %s 个，共 %s 个", created, len(by_code))
    return by_code


# --------------------------------------------------------------------------- 企业


ENTERPRISES = [
    {
        "code": "ENT-2025-0001",
        "name": "北屯金穗瓜子有限公司",
        "credit": "91659001MA7X0001XA",
        "type": "supplier",
        "legal_person": "王金穗",
        "business_scope": "葵花籽、南瓜籽收购、加工与销售；农副产品仓储",
        "contact_name": "王金穗",
        "contact_phone": "13899000001",
        "region": "新疆生产建设兵团第十师北屯市",
        "address": "北屯市工业园区油料产业园 A 区 1 号",
        "stall_code": "STALL-001",
        "settle_bank": "中国农业银行北屯支行",
        "settle_account_name": "北屯金穗瓜子有限公司",
        "settle_account_no": "30-0123456789012",
        "username": "jinsui",
    },
    {
        "code": "ENT-2025-0002",
        "name": "新疆北屯丰源农产品有限公司",
        "credit": "91659001MA7X0002XB",
        "type": "merchant",
        "legal_person": "李丰源",
        "business_scope": "打瓜籽、葵花籽收购与批发；食用农产品初加工",
        "contact_name": "李丰源",
        "contact_phone": "13899000002",
        "region": "新疆生产建设兵团第十师北屯市",
        "address": "北屯市工业园区油料产业园 B 区 8 号",
        "stall_code": "STALL-002",
        "settle_bank": "中国建设银行北屯支行",
        "settle_account_name": "新疆北屯丰源农产品有限公司",
        "settle_account_no": "65-0987654321098",
        "username": "fengyuan",
    },
    {
        "code": "ENT-2025-0003",
        "name": "北屯市供销粮油采购有限公司",
        "credit": "91659001MA7X0003XC",
        "type": "buyer",
        "legal_person": "张采购",
        "business_scope": "粮油食品采购、批发与配送",
        "contact_name": "张采购",
        "contact_phone": "13899000003",
        "region": "新疆维吾尔自治区乌鲁木齐市",
        "address": "乌鲁木齐市高新技术产业开发区粮油大厦 18 层",
        "settle_bank": "中国银行乌鲁木齐分行",
        "settle_account_name": "北屯市供销粮油采购有限公司",
        "settle_account_no": "12-1122334455667",
        "username": "gongxiao",
    },
    {
        "code": "ENT-2025-0004",
        "name": "新疆西域坚果食品有限公司",
        "credit": "91659001MA7X0004XD",
        "type": "buyer",
        "legal_person": "赵坚果",
        "business_scope": "坚果炒货食品生产与销售",
        "contact_name": "赵坚果",
        "contact_phone": "13899000004",
        "region": "新疆维吾尔自治区昌吉市",
        "address": "昌吉市高新技术产业开发区食品产业园 6 号",
        "settle_bank": "中国工商银行昌吉分行",
        "settle_account_name": "新疆西域坚果食品有限公司",
        "settle_account_no": "10-5566778899001",
        "username": "xiyujianuo",
    },
    {
        # 需求指定的演示主体之一：北屯XX瓜子加工有限公司（商户：测试商户A）
        "code": "ENT-2025-0005",
        "name": "北屯XX瓜子加工有限公司",
        "credit": "91659001MA7X0005XE",
        "type": "merchant",
        "legal_person": "马加工",
        "business_scope": "葵花籽、南瓜籽收购、加工与销售；食用农产品初加工",
        "contact_name": "测试商户A",
        "contact_phone": "13899000005",
        "full_name": "测试商户A",
        "region": "新疆生产建设兵团第十师北屯市",
        "address": "北屯市工业园区油料产业园 C 区 6 号",
        "stall_code": "STALL-003",
        "settle_bank": "中国农业银行北屯支行",
        "settle_account_name": "北屯XX瓜子加工有限公司",
        "settle_account_no": "30-9988776655443",
        "username": "testmerchant",
    },
    {
        # 需求指定的演示主体之一：测试采购企业
        "code": "ENT-2025-0006",
        "name": "测试采购企业",
        "credit": "91659001MA7X0006XF",
        "type": "buyer",
        "legal_person": "测试采购",
        "business_scope": "农产品采购、批发与配送",
        "contact_name": "测试采购员",
        "contact_phone": "13899000006",
        "full_name": "测试采购员",
        "region": "新疆维吾尔自治区乌鲁木齐市",
        "address": "乌鲁木齐市测试大道 100 号",
        "stall_code": None,
        "settle_bank": "中国银行乌鲁木齐分行",
        "settle_account_name": "测试采购企业",
        "settle_account_no": "12-3344556677889",
        "username": "testbuyer",
    },
]


def seed_enterprises(db: Session, park: Park, park_org: OrgUnit) -> dict:
    role_map = {
        "merchant": "merchant",
        "supplier": "supplier",
        "buyer": "buyer",
        "platform": "platform_admin",
    }
    result = {}
    for item in ENTERPRISES:
        enterprise = db.query(Enterprise).filter(Enterprise.code == item["code"]).first()
        stall = db.query(Stall).filter(Stall.code == item["stall_code"]).first() if item.get("stall_code") else None
        if enterprise is None:
            enterprise = Enterprise(
                code=item["code"],
                name=item["name"],
                unified_social_credit_code=item["credit"],
                enterprise_type=item["type"],
                legal_person=item["legal_person"],
                registered_capital=Decimal("1000.00"),
                business_scope=item["business_scope"],
                contact_name=item["contact_name"],
                contact_phone=item["contact_phone"],
                region=item["region"],
                address=item["address"],
                park_id=park.id if stall else None,
                stall_id=stall.id if stall else None,
                audit_status="approved",
                audited_at=now(),
                status="active",
                settle_bank=item["settle_bank"],
                settle_account_name=item["settle_account_name"],
                settle_account_no=item["settle_account_no"],
            )
            db.add(enterprise)
            db.flush()
        org = db.query(OrgUnit).filter(OrgUnit.code == f"ORG-{enterprise.code}").first()
        if org is None:
            org = OrgUnit(
                code=f"ORG-{enterprise.code}",
                name=enterprise.name,
                unit_type="enterprise",
                parent_id=park_org.id,
                park_id=park.id,
                region=enterprise.region,
                address=enterprise.address,
                contact_name=enterprise.contact_name,
                contact_phone=enterprise.contact_phone,
                status="active",
                sort=10,
            )
            db.add(org)
            db.flush()
        enterprise.org_id = org.id
        if stall is not None:
            stall.enterprise_id = enterprise.id
            stall.status = "rented"
        user = db.query(User).filter(User.username == item["username"]).first()
        if user is None:
            user = User(
                username=item["username"],
                password_hash=hash_password(DEFAULT_PASSWORD),
                full_name=item.get("full_name") or item["contact_name"],
                phone=item["contact_phone"],
                org_id=org.id,
                enterprise_id=enterprise.id,
                status="active",
            )
            role = db.query(Role).filter(Role.code == role_map.get(item["type"], "merchant")).first()
            if role is not None:
                user.roles = [role]
            db.add(user)
            db.flush()
            logger.info("创建企业账号：%s（%s）", item["username"], enterprise.name)
        result[item["code"]] = enterprise
    db.flush()
    return result


# --------------------------------------------------------------------------- 仓库与商品


WAREHOUSES = [
    ("WH-JS-01", "金穗 1 号仓库", "ENT-2025-0001", "北屯市工业园区油料产业园 A 区仓库"),
    ("WH-FY-01", "丰源 1 号仓库", "ENT-2025-0002", "北屯市工业园区油料产业园 B 区仓库"),
    ("WH-GX-01", "瓜子加工 1 号仓库", "ENT-2025-0005", "北屯市工业园区油料产业园 C 区仓库"),
]

LOCATIONS = [
    ("A-01-01", "A 区 1 排 1 位", "A", 500),
    ("A-01-02", "A 区 1 排 2 位", "A", 500),
    ("B-01-01", "B 区 1 排 1 位", "B", 500),
]

PRODUCTS = [
    {
        "code": "GZ-SUN-0001",
        "name": "新疆特级葵花籽（食葵）",
        "category": "GZ-SUN",
        "enterprise": "ENT-2025-0001",
        "spec": "千粒重≥180g，水分≤9%",
        "grade": "special",
        "origin": "新疆阿勒泰",
        "harvest_year": "2025",
        "package": "50kg 编织袋",
        "price": "6800.00",
        "warn": "50.000",
        "batch": "B20250901",
        "quantity": "500.000",
        "cost": "6200.00",
    },
    {
        "code": "GZ-SUN-0002",
        "name": "新疆一级葵花籽（油葵）",
        "category": "GZ-SUN",
        "enterprise": "ENT-2025-0001",
        "spec": "含油率≥42%，水分≤9%",
        "grade": "first",
        "origin": "新疆塔城",
        "harvest_year": "2025",
        "package": "散装",
        "price": "5900.00",
        "warn": "80.000",
        "batch": "B20250902",
        "quantity": "800.000",
        "cost": "5500.00",
    },
    {
        "code": "GZ-PUM-0001",
        "name": "新疆特级南瓜籽（光板）",
        "category": "GZ-PUM",
        "enterprise": "ENT-2025-0001",
        "spec": "千粒重≥220g，水分≤8%",
        "grade": "special",
        "origin": "新疆北屯",
        "harvest_year": "2025",
        "package": "25kg 纸箱",
        "price": "14200.00",
        "warn": "20.000",
        "batch": "B20250903",
        "quantity": "180.000",
        "cost": "13000.00",
    },
    {
        "code": "GZ-SEED-0001",
        "name": "北屯打瓜籽（统货）",
        "category": "GZ-SEED",
        "enterprise": "ENT-2025-0002",
        "spec": "籽粒饱满，杂质≤1%",
        "grade": "mixed",
        "origin": "新疆北屯",
        "harvest_year": "2025",
        "package": "50kg 编织袋",
        "price": "7600.00",
        "warn": "40.000",
        "batch": "B20250904",
        "quantity": "620.000",
        "cost": "7000.00",
    },
    {
        "code": "GZ-SEED-0002",
        "name": "北屯打瓜籽（一级）",
        "category": "GZ-SEED",
        "enterprise": "ENT-2025-0002",
        "spec": "片大均匀，水分≤9%",
        "grade": "first",
        "origin": "新疆北屯",
        "harvest_year": "2025",
        "package": "50kg 编织袋",
        "price": "8900.00",
        "warn": "30.000",
        "batch": "B20250905",
        "quantity": "430.000",
        "cost": "8200.00",
    },
    {
        "code": "GZ-PRO-ROAST-0001",
        "name": "原味炒葵花籽成品",
        "category": "GZ-PRO-ROAST",
        "enterprise": "ENT-2025-0002",
        "spec": "10kg/箱，原味",
        "grade": "first",
        "origin": "新疆北屯",
        "harvest_year": "2025",
        "package": "10kg 纸箱",
        "price": "12800.00",
        "warn": "10.000",
        "batch": "B20250906",
        "quantity": "120.000",
        "cost": "11500.00",
    },
    {
        # 需求指定的演示商品：北屯葵花籽，库存 100 吨
        "code": "GZ-SUN-0003",
        "name": "北屯葵花籽",
        "category": "GZ-SUN",
        "enterprise": "ENT-2025-0005",
        "spec": "千粒重≥180g，水分≤9%，杂质≤1%",
        "grade": "special",
        "origin": "新疆北屯",
        "harvest_year": "2025",
        "package": "50kg 编织袋",
        "price": "6600.00",
        "warn": "20.000",
        "batch": "B20250907",
        "quantity": "100.000",
        "cost": "6100.00",
    },
]


def seed_warehouses(db: Session, enterprises: dict) -> dict:
    result = {}
    for code, name, ent_code, address in WAREHOUSES:
        enterprise = enterprises.get(ent_code)
        if enterprise is None:
            continue
        warehouse = db.query(Warehouse).filter(Warehouse.code == code).first()
        if warehouse is None:
            warehouse = Warehouse(
                code=code,
                name=name,
                enterprise_id=enterprise.id,
                park_id=enterprise.park_id,
                address=address,
                warehouse_type="own",
                contact_name=enterprise.contact_name,
                contact_phone=enterprise.contact_phone,
                capacity=Decimal("5000.000"),
                status="active",
            )
            db.add(warehouse)
            db.flush()
        for loc_code, loc_name, zone, capacity in LOCATIONS[:2]:
            exists = (
                db.query(StorageLocation)
                .filter(
                    StorageLocation.warehouse_id == warehouse.id,
                    StorageLocation.code == loc_code,
                )
                .first()
            )
            if exists is None:
                db.add(
                    StorageLocation(
                        warehouse_id=warehouse.id,
                        code=loc_code,
                        name=loc_name,
                        zone=zone,
                        capacity=Decimal(str(capacity)),
                        status="active",
                    )
                )
        db.flush()
        result[ent_code] = warehouse
    logger.info("仓库初始化完成：%s 个", len(result))
    return result


def seed_products(db: Session, categories: dict, enterprises: dict) -> dict:
    result = {}
    for item in PRODUCTS:
        product = db.query(Product).filter(Product.code == item["code"]).first()
        enterprise = enterprises.get(item["enterprise"])
        category = categories.get(item["category"])
        if enterprise is None or category is None:
            continue
        if product is None:
            product = Product(
                code=item["code"],
                name=item["name"],
                category_id=category.id,
                enterprise_id=enterprise.id,
                spec=item["spec"],
                grade=item["grade"],
                origin=item["origin"],
                harvest_year=item["harvest_year"],
                package=item["package"],
                unit="ton",
                price=Decimal(item["price"]),
                currency="CNY",
                min_order_qty=Decimal("5.000"),
                stock_warn_qty=Decimal(item["warn"]),
                quality_status="qualified",
                trace_enabled=True,
                status="published",
                audit_status="approved",
                description=f"{item['name']}；产地 {item['origin']}；{item['spec']}",
            )
            db.add(product)
            db.flush()
        result[item["code"]] = product
    logger.info("商品初始化完成：%s 个", len(result))
    return result


def seed_inventory(db: Session, products: dict, warehouses: dict, admin: User) -> int:
    created = 0
    for item in PRODUCTS:
        product = products.get(item["code"])
        warehouse = warehouses.get(item["enterprise"])
        if product is None or warehouse is None:
            continue
        existing = (
            db.query(inventory_service.Inventory)
            .filter(
                inventory_service.Inventory.product_id == product.id,
                inventory_service.Inventory.warehouse_id == warehouse.id,
                inventory_service.Inventory.batch_no == item["batch"],
            )
            .first()
        )
        if existing is not None:
            continue
        inventory_service.stock_in(
            db,
            StockInIn(
                product_id=product.id,
                warehouse_id=warehouse.id,
                batch_no=item["batch"],
                quantity=Decimal(item["quantity"]),
                unit_cost=Decimal(item["cost"]),
                production_date=date.today() - timedelta(days=30),
                quality_status="qualified",
                ref_type="init",
                ref_no="INIT-INVENTORY",
                remark="初始化库存",
            ),
            admin,
        )
        created += 1
    db.flush()
    logger.info("库存初始化完成：新增入库单 %s 条", created)
    return created


# --------------------------------------------------------------------------- 演示交易闭环


def seed_demo_trade(db: Session, products: dict, users: dict) -> None:
    from app.models.trade import TradeOrder

    if db.query(TradeOrder).count() > 0:
        logger.info("已存在订单数据，跳过演示交易闭环")
        return

    def _user(username: str):
        return db.query(User).filter(User.username == username).first()

    # (采购商账号, 供应商账号, 商品编码, 数量, 成交单价)
    scenarios = [
        # 需求指定的演示闭环：测试采购企业 → 北屯XX瓜子加工有限公司 · 北屯葵花籽
        ("testbuyer", "testmerchant", "GZ-SUN-0003", Decimal("10.000"), Decimal("6600.00")),
        ("gongxiao", "jinsui", "GZ-SUN-0001", Decimal("50.000"), Decimal("6750.00")),
        ("gongxiao", "jinsui", "GZ-SUN-0002", Decimal("120.000"), Decimal("5850.00")),
        ("xiyujianuo", "jinsui", "GZ-PUM-0001", Decimal("20.000"), Decimal("14000.00")),
        ("gongxiao", "fengyuan", "GZ-SEED-0001", Decimal("40.000"), Decimal("7550.00")),
    ]
    created = 0
    for buyer_username, supplier_username, product_code, quantity, price in scenarios:
        buyer = _user(buyer_username)
        supplier = _user(supplier_username)
        product = products.get(product_code)
        if buyer is None or supplier is None or product is None:
            logger.warning("跳过演示场景 %s：缺少账号或商品", product_code)
            continue
        buyer_enterprise = db.get(Enterprise, buyer.enterprise_id)
        inquiry = trade_service.create_inquiry(
            db,
            InquiryIn(
                product_id=product.id,
                quantity=quantity,
                unit="ton",
                supplier_enterprise_id=supplier.enterprise_id,
                expect_price=price,
                expect_delivery_date=date.today() + timedelta(days=7),
                delivery_address=buyer_enterprise.address if buyer_enterprise else None,
                remark="平台初始化演示询价",
                submit=True,
            ),
            buyer,
        )
        quotation = trade_service.create_quotation(
            db,
            inquiry,
            QuotationIn(
                unit_price=price,
                tax_rate=Decimal("0.09"),
                delivery_date=date.today() + timedelta(days=5),
                payment_terms="货到验收合格后 15 个工作日内电汇",
                remark="平台初始化演示报价",
            ),
            supplier,
        )
        order = trade_service.accept_quotation(db, quotation, buyer)
        trade_service.confirm_order(db, order, supplier)
        trade_service.deliver_order(
            db,
            order,
            DeliverIn(
                items=[
                    DeliverItemIn(item_id=item.id, delivered_quantity=item.quantity)
                    for item in order.items
                ],
                logistics_company="北屯物流有限公司",
                logistics_no=f"BTWL{order.id:08d}",
            ),
            supplier,
        )
        trade_service.complete_order(db, order, supplier)
        created += 1
    db.flush()

    # 再生成一笔已登记回款的结算，便于演示财务与驾驶舱
    from app.models.settlement import Settlement
    from app.schemas.finance import PaymentIn
    from app.services import settlement_service

    settlement = db.query(Settlement).order_by(Settlement.id.asc()).first()
    if settlement is not None:
        settlement_service.confirm_settlement(db, settlement, users.get("admin"))
        settlement_service.register_payment(
            db,
            settlement,
            PaymentIn(
                amount=settlement.settle_amount,
                pay_method="bank_transfer",
                trade_no="BT2025090100001",
                remark="演示回款登记（资金实际走银行）",
            ),
            users.get("admin"),
        )
    db.flush()
    logger.info("演示交易闭环完成：%s 笔订单（询价→报价→订单→扣库存→发货→完成→结算→回款）", created)


# --------------------------------------------------------------------------- 主流程


def run(reset: bool = False, demo: bool = True) -> None:
    if reset:
        logger.warning("--reset 将删除全部业务表并重建")
        init_db(drop=True)
    else:
        init_db()
    session: Session = get_session_factory()()
    try:
        seed_permissions(session)
        seed_roles(session)
        platform, park, park_org = seed_org_and_park(session)
        users = seed_users(session, platform, park_org)
        categories = seed_categories(session)
        enterprises = seed_enterprises(session, park, park_org)
        warehouses = seed_warehouses(session, enterprises)
        products = seed_products(session, categories, enterprises)
        seed_inventory(session, products, warehouses, users["admin"])
        if demo:
            seed_demo_trade(session, products, users)
        session.commit()
        logger.info("初始化完成。管理员账号：%s；初始密码按部署配置注入", ADMIN_USERNAME)
    except Exception:
        session.rollback()
        logger.exception("初始化失败，已回滚")
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="瓜子油料平台数据初始化")
    parser.add_argument("--reset", action="store_true", help="危险：删除全部业务表后重建")
    parser.add_argument("--no-demo", action="store_true", help="不生成演示交易数据")
    args = parser.parse_args()
    run(reset=args.reset, demo=not args.no_demo)


if __name__ == "__main__":
    main()
