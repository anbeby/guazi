# 第十师瓜子油料数字化交易平台

面向新疆生产建设兵团**第十师北屯市**瓜子油料产业的数字化交易与产业运营平台。

平台定位不是"网上商城"，而是四合一：

```
产业互联网交易平台  +  智慧园区管理  +  商户经营管理  +  数据分析中心
```

---

## 一、仓库结构

```
瓜子/
├── docs/                       项目文档（架构 / 边界 / 数据模型 / 接口 / 部署 / 变更记录）
├── deploy/                     Docker 部署编排与环境配置
│   ├── docker-compose.yml      全栈一键编排
│   ├── .env.example            环境变量模板
│   ├── conf/                   各中间件与 Odoo 配置
│   └── scripts/                启停 / 初始化 / 备份脚本
├── odoo/                       Odoo ERP 底座
│   ├── Dockerfile
│   └── addons/                 自研 Odoo 业务模块（gz_*）
├── services/
│   ├── api/                    自研 B2B 交易与产业运营平台（FastAPI + PostgreSQL）
│   └── worker/                 后台任务（索引同步 / Odoo 同步 / 结算跑批）
├── apps/
│   ├── admin-web/              PC 管理后台（Vue3 + Vite + Element Plus）
│   ├── merchant-web/           商户后台（复用 admin-web 构建产物 + 独立入口）
│   └── miniapp/                微信小程序端（阶段二）
└── tests/                      集成测试与验收脚本
```

## 二、技术栈

| 层次 | 选型 | 说明 |
| --- | --- | --- |
| ERP 底座 | Odoo 17 (CE) | 采购 / 销售 / 库存 / 财务 / CRM，承载企业经营管理 |
| 交易平台后端 | FastAPI + SQLAlchemy 2.0 + Alembic | 自研产业交易与运营域，独立库 `gz_platform` |
| 数据库 | PostgreSQL 16 | Odoo 库 `gz_odoo` 与自研库 `gz_platform` 同实例分库 |
| 缓存 | Redis 7 | 会话 / Token 黑名单 / 幂等键 / 热点缓存 |
| 对象存储 | MinIO | 商品图片、检测报告、合同附件、溯源证据 |
| 搜索 | ElasticSearch 8 | 商品与商户全文检索（不可用时自动降级 SQL LIKE） |
| 数据分析 | Apache Superset | 产业驾驶舱、跨库报表 |
| 网关 | Nginx | 统一入口、反向代理、静态资源 |
| 前端 | Vue3 + Vite + Element Plus + ECharts + Pinia | PC 管理后台 / 商户后台 |

## 三、快速启动

```bash
cd deploy
cp .env.example .env          # Windows: copy .env.example .env
docker compose up -d --build
docker compose ps
```

启动后访问：

| 入口 | 地址 | 说明 |
| --- | --- | --- |
| 统一网关 | http://localhost:8080 | 管理后台 / API / Odoo 统一入口 |
| 平台 API 文档 | http://localhost:8080/api/docs | OpenAPI 交互式文档（真实数据库） |
| 内置控制台 | http://localhost:8080/console/ | 免构建可用的运营控制台（直连真实 API） |
| Odoo ERP | http://localhost:8080/odoo | 账号见 `.env` 的 `ODOO_ADMIN_PASSWD` |
| Superset | http://localhost:8088 | 数据分析（首次启动需初始化） |
| MinIO 控制台 | http://localhost:9001 | 对象存储 |
| ElasticSearch | http://localhost:9200 | 搜索引擎 |

初始化业务数据（角色、权限、管理员、园区、商品、库存、示例交易）：

```bash
docker compose exec api python -m app.initial_data
```

本地免 Docker 运行（开发态，需本机 PostgreSQL 或使用 SQLite 内存库做验证）：

```bash
cd services/api
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements-dev.txt
python -m pytest -q
uvicorn app.main:app --reload --port 8000
```

## 四、第一阶段范围（已交付）

1. 基础平台部署（Docker 全栈）
2. 用户权限体系（RBAC + 企业数据隔离）
3. 商户管理（企业档案、入驻审核）
4. 商品中心（瓜子油料分类、商品档案、检测报告）
5. 库存管理（仓库 / 库位 / 出入库 / 盘点 / 批次）
6. B2B 交易基础流程（发布商品 → 询价 → 报价 → 确认 → 订单 → 库存扣减 → 交易流水 → 结算单）

阶段二范围（园区管理深化、溯源二维码、数据驾驶舱、小程序端）已在架构与目录中预留。

## 五、文档索引

- [总体技术架构](docs/01-总体技术架构.md)
- [Odoo 承载能力分析与自研模块边界](docs/02-Odoo承载能力分析与自研模块边界.md)
- [数据模型设计](docs/03-数据模型设计.md)
- [REST 接口规范](docs/04-接口规范.md)
- [部署与运维手册](docs/05-部署与运维手册.md)
- [开发规范](docs/06-开发规范.md)
- [变更记录](docs/CHANGELOG.md)
