# Odoo 自研模块（`odoo/addons`）

第十师瓜子油料数字化交易平台的 **Odoo 17 企业侧模块**。自研平台（`services/api` + `apps/admin-web`）
是 B2B 撮合交易的主承载方，Odoo 承载**企业主体、商品、批次/仓储参数、ERP 单据（销售单/采购单/结算凭证）**
等企业侧能力，两侧通过 **outbox + JSON-RPC / HMAC 签名开放接口**最终一致（见 `docs/02` 第 2 节）。

模块以源码形式放在本目录，容器内挂载到 `/mnt/extra-addons`（`ADDONS_PATH` 的第一项，见
`deploy/docker-compose.yml` 的 `odoo` 服务），业务库为 `gz_odoo`，Odoo 端口 `8069`（长轮询 `8072`）。

---

## 1. 模块清单

| 模块 | 版本 | 依赖（`__manifest__.py` 声明） | 核心模型（`_name` / `_inherit`） | 提供的视图 / 菜单 |
| --- | --- | --- | --- | --- |
| **`gz_platform_base`**<br>瓜子油料平台基础 | 17.0.1.0.0 | `base`、`contacts`、`mail` | `gz.enterprise`（新建，继承 `mail.thread`、`mail.activity.mixin`） | 视图：`views/gz_enterprise_views.xml`<br>菜单：`瓜子油料平台`（根）→ `平台基础` → `企业主体` |
| **`gz_merchant`**<br>瓜子油料平台商户 | 17.0.1.0.0 | `gz_platform_base`、`mail` | `gz.enterprise`（`_inherit` 扩展：执照、许可证、商户等级、年产能、主营产品、资质附件）<br>`gz.merchant.qualification`（资质附件）<br>`gz.merchant.entry`（入驻申请，继承 `mail.thread`、`mail.activity.mixin`） | 视图：`views/gz_enterprise_views.xml`、`views/gz_merchant_qualification_views.xml`、`views/gz_merchant_entry_views.xml`<br>菜单：`商户中心` → `商户档案` / `入驻申请` / `资质台账` |
| **`gz_product`**<br>瓜子油料平台商品 | 17.0.1.0.0 | `gz_platform_base`、`product`、`stock` | `product.category`（`_inherit`：分类类型、平台编码、叶子标记）<br>`product.template`（`_inherit`：规格/等级/产地/年份/包装/质检/发布与审核状态等）<br>`gz.product.audit.log`（商品审核日志） | 视图：`views/product_template_views.xml`、`views/product_category_views.xml`<br>菜单：`商品中心` → `商品档案` / `商品分类` |
| **`gz_inventory`**<br>瓜子油料平台库存 | 17.0.1.0.0 | `gz_product`、`stock` | `gz.stock.batch`（平台批次 + 库存预警，继承 `mail.thread`）<br>`gz.warehouse.config`（仓储参数）<br>`stock.lot`（`_inherit`：挂接平台批次、质检状态、溯源码） | 视图：`views/gz_stock_batch_views.xml`、`views/gz_warehouse_config_views.xml`、`views/stock_lot_views.xml`<br>菜单：`仓储管理` → `批次管理` / `库存预警` / `仓储参数` |
| **`gz_trade`**<br>瓜子油料平台交易 | 17.0.1.0.0 | `gz_product`、`gz_inventory`、`sale_management`、`purchase`、`account` | `gz.inquiry`、`gz.quotation`（询价 / 报价镜像单据）<br>`gz.order`、`gz.order.line`、`gz.order.timeline`<br>`gz.contract`<br>`gz.settlement`、`gz.settlement.line`<br>`gz.trade.flow`<br>`gz.account.move.mixin`（抽象 mixin：生成 `account.move` 草稿） | 视图：`views/gz_inquiry_views.xml`、`views/gz_quotation_views.xml`、`views/gz_order_views.xml`、`views/gz_contract_views.xml`、`views/gz_settlement_views.xml`、`views/gz_trade_flow_views.xml`<br>菜单：`交易中心` → `撮合交易`（询价单 / 报价单）、`订单与合同`（平台订单 / 待确认订单 / 合同管理）、`结算与资金`（结算单 / 待回款结算单 / 交易流水） |

> 所有模块 `installable: True`；仅 `gz_platform_base` 为 `application: True`（其余为功能模块，随根菜单挂载）。
> 每个模块都自带 `security/security.xml` + `security/ir.model.access.csv`，权限由 `gz_platform_base`
> 定义的六类安全组（平台管理员 / 园区运营人员 / 商户 / 供应商 / 采购商 / 财务）承接。
> 数据文件：`gz_platform_base`、`gz_merchant`、`gz_inventory`、`gz_trade` 各带 `data/gz_sequence.xml`
> （单据序列）；`gz_product` 带 `data/gz_product_category.xml`（瓜子油料预置分类树，`noupdate="1"`）；
> `gz_trade` 带 `data/gz_trade_cron.xml`（定时任务，见 §4）。

---

## 2. 安装顺序

依赖链：`gz_platform_base` → (`gz_merchant` / `gz_product`) → `gz_inventory` → `gz_trade`。

| 顺序 | 模块 | 说明 |
| --- | --- | --- |
| 1 | `gz_platform_base` | 无自研依赖；提供 `gz.enterprise`、六类安全组、记录规则、根菜单 `瓜子油料平台`。必须先装 |
| 2 | `gz_merchant` | 依赖 `gz_platform_base`；扩展 `gz.enterprise`，提供资质与入驻流程 |
| 3 | `gz_product` | 依赖 `gz_platform_base` + Odoo 原生 `product`、`stock` |
| 4 | `gz_inventory` | 依赖 `gz_product`（取商品预警值）与原生 `stock` |
| 5 | `gz_trade` | 依赖 `gz_product`、`gz_inventory` 与 `sale_management`、`purchase`、`account`，最后安装 |

> Odoo 自身会按 `depends` 做拓扑排序，`-i` 时按上表顺序书写即可（下方命令即按此顺序）。

---

## 3. 安装命令

在 `deploy/` 目录（`docker-compose.yml` 所在处）执行：

```bash
docker compose exec odoo odoo -d gz_odoo -i gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade --stop-after-init
```

说明与注意事项：

- `-d gz_odoo`：目标业务库（与 `deploy/.env` 的 `ODOO_DB` 一致；不存在时 Odoo 会自动创建）。
- `--stop-after-init`：初始化完成后退出进程，避免与常驻服务争抢；`odoo` 服务为
  `restart: unless-stopped`，容器会自动拉起，必要时执行 `docker compose up -d odoo`。
- 生产环境建议直接使用仓库内的初始化脚本（会附带 `--without-demo=all --db_host=postgres --db_port=5432`，
  且不把密码写在命令行上）：

  ```bash
  ./scripts/init-data.sh          # 或 Windows: .\scripts\init-data.ps1
  ```

- **升级已安装模块**（改了模型或视图后）：

  ```bash
  docker compose exec odoo odoo -d gz_odoo -u gz_trade --stop-after-init
  docker compose exec odoo odoo -d gz_odoo -u gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade --stop-after-init
  ```

- 也可在 Odoo 界面「应用 → 更新应用列表」后搜索 `瓜子油料` 逐一点装（顺序同上）。
- 首次安装后访问 `http://<host>:8069`（生产经网关 `/odoo` 访问），业务库 `gz_odoo`。

---

## 4. 与自研平台的集成

集成总原则（`docs/02` 第 1.1 / 2 节）：**自研平台是 B2B 交易与业务的唯一主承载方，Odoo 承载企业侧
ERP 单据与账实**；两侧不共享数据库事务，通过 outbox 最终一致 + 幂等键 + 每日对账兜底。

### 4.1 自研 → Odoo：`sync_outbox` + JSON-RPC

- 自研侧业务动作写 `gz.sync_outbox`（`docs/03` 第 10 节），后台 worker 消费后通过
  **Odoo JSON-RPC** 调用 `gz_*` 模型（`odoo_client`）。
- 触发点：企业审核通过（`gz.enterprise`）、商品发布/审核（`product.template` + `gz.product.audit.log`）、
  批次与质检（`gz.stock.batch`）、订单/合同/结算（`gz.order`、`gz.contract`、`gz.settlement`）。
- 由 Odoo 侧单据生成规则（`gz_trade`）：
  - 确认订单 → `sale.order`（`client_order_ref` = 平台订单号）；
  - 采购方向 → `purchase.order`（`partner_ref` = 平台订单号）；
  - 结算单确认 → `account.move` 草稿（`ref` = 平台订单号 / 结算单号）。
- **幂等键**（`docs/02` 第 2.1 节，写在 `gz_trade/__manifest__.py` 说明中）：

  | 自研 | Odoo | 用途 |
  | --- | --- | --- |
  | `order.name` | `sale.order.client_order_ref` / `purchase.order.partner_ref` | 订单不重复生成 |
  | `settlement.name` | `account.move.ref` | 结算凭证不重复生成 |
  | `enterprise.code` | `gz.enterprise.code` → `res.partner.ref` | 企业主体不重复创建 |

- 冲突策略：以自研为准（Odoo 侧对应单据为承载/镜像）；库存账实以 Odoo 原生 `stock` 为准。

### 4.2 Odoo → 自研：`/api/v1/integration/odoo/*` + HMAC 签名

- 触发方式：Odoo `ir.cron`（`gz_trade/data/gz_trade_cron.xml`），**每 30 分钟**执行
  `gz.order._cron_sync_platform()`；该方法中已预留对自研平台开放接口的 REST 调用点，
  以 `try/except` 容错，Odoo 侧异常不会阻塞自身业务。
- 开放接口（`docs/04` §2.12）：

  | 方法 | 路径 | 说明 |
  | --- | --- | --- |
  | POST | `/api/v1/integration/odoo/pull-inventory` | Odoo 推送库存快照 |
  | POST | `/api/v1/integration/odoo/ack-order` | Odoo 回执订单已生成 |

- **签名规则**：请求头 `X-GZ-Signature = HMAC-SHA256(timestamp + "." + raw_body, INTEGRATION_SECRET)`，
  `X-GZ-Timestamp` 为秒级时间戳，服务端允许 **±300 秒**偏差；密钥由部署环境注入，不落库、不进代码。
- 出站事件（自研 → Odoo 的补推入口）由自研平台管理：`GET /api/v1/integration/outbox`
  （权限 `integration:read`）与 `POST /api/v1/integration/outbox/{id}/retry`（权限 `integration:write`）。

### 4.3 两侧数据边界速查

| 数据 | 主责方 | 对侧行为 |
| --- | --- | --- |
| 企业主体 / 商户资质 / 入驻审核 | 自研 | Odoo `gz.enterprise`、`gz.merchant.*` 承载并同步 `res.partner` |
| 商品与分类 | 自研 | Odoo `product.template` / `product.category` 扩展承载，发布前校验审核状态 |
| 库存账实（数量移动） | Odoo（原生 `stock`） | 自研 `inventory` 为平台视角；Odoo 通过 `/integration/odoo/pull-inventory` 回推快照 |
| 批次与质检、仓储参数 | 自研 | Odoo `gz.stock.batch`、`gz.warehouse.config` |
| 询价 / 报价 / 订单 / 合同 / 结算 / 流水 | 自研 | Odoo `gz.*` 镜像单据，并按需生成 `sale.order` / `purchase.order` / `account.move` |

---

## 5. 各模块详细说明

每个模块目录下均有独立 `README.md`（模型字段、方法、安全规则、字段映射与已知风险）：

| 模块 | 详细文档 |
| --- | --- |
| `gz_platform_base` | [`gz_platform_base/README.md`](./gz_platform_base/README.md) |
| `gz_merchant` | [`gz_merchant/README.md`](./gz_merchant/README.md) |
| `gz_product` | [`gz_product/README.md`](./gz_product/README.md) |
| `gz_inventory` | [`gz_inventory/README.md`](./gz_inventory/README.md) |
| `gz_trade` | [`gz_trade/README.md`](./gz_trade/README.md) |

相关文档：

- [`docs/02-Odoo承载能力分析与自研模块边界.md`](../../docs/02-Odoo承载能力分析与自研模块边界.md) —— 模块边界与集成原则
- [`docs/03-数据模型设计.md`](../../docs/03-数据模型设计.md) —— `sync_outbox` 与字段映射
- [`docs/04-接口规范.md`](../../docs/04-接口规范.md) §2.12 —— 集成接口与 HMAC 签名规则
- [`deploy/conf/odoo/README.md`](../../deploy/conf/odoo/README.md) —— Odoo 容器运维（安装 / 升级 / 排障）

---

## 6. 验证状态声明

> **本文档内容依据 5 个 `__manifest__.py`、`models/*.py` 的 `_name` / `_inherit`、各模块 `views/gz_menu.xml`
> 与 `docs/02`、`docs/03`、`docs/04` 静态核对写成。**
> 交付环境（Windows 主机）的 PowerShell 进程无法启动（错误码 `0xC0000142`），**未执行 `docker compose`、
> 未运行 Odoo，模块安装与界面效果均未经实际验证**；`ir.sequence` 占位符、`ir.cron` 调用自研接口等行为
> 需在真实 Odoo 17 实例上确认（各模块 README 的「已知风险 / 待验证」小节已列出待确认项）。
