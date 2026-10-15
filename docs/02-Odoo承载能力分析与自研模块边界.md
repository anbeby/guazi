# Odoo 承载能力分析与自研模块边界设计

本文是第一阶段的核心设计输入，回答两个问题：

1. **Odoo 适合承载哪些功能？哪些不适合？**
2. **自研模块的边界画在哪里？两边如何打通？**

---

## 一、Odoo 能力评估矩阵

评估维度：功能成熟度（Odoo 原生能力覆盖度）、改造成本、互联网化适配度、升级风险。

### 1.1 结论总表

| 业务域 | 建议承载方 | Odoo 原生模块 | 成熟度 | 决策理由 |
| --- | --- | --- | --- | --- |
| 企业档案 / 往来单位 | **Odoo（主）** + 自研（同步展示） | `base` `contacts` | ★★★★★ | `res.partner` 是全 Odoo 的往来单位主键，自研另起炉灶会造成对账困难；自研侧只保存交易所需的扩展字段 |
| 用户与登录 | **Odoo（内部）** + 自研（对外） | `base` `auth_*` | ★★★★★ | 平台内员工（运营/财务/审核）走 Odoo；互联网侧商户/采购商走自研 JWT，二者通过 `enterprise_code` 关联 |
| 采购管理 | **Odoo（主）** | `purchase` `purchase_stock` | ★★★★★ | 请购→询价→比价→订单→到货→入库→发票→付款，全链路成熟 |
| 销售管理 | **Odoo（主，内部）** | `sale_management` `sale_stock` | ★★★★★ | 同上，O2C 链路成熟 |
| B2B 撮合交易（询价/报价/撮合） | **自研（主）** | 无 | ☆ | Odoo 无"采购商发询价 → 多供应商报价 → 平台撮合"的公开市场模型，`purchase.order` 是买方单一视角，硬改会造成核心模型污染 |
| 商品中心 | **自研（主）** + Odoo（同步） | `product` | ★★★☆ | 农产品特有属性（规格/等级/产地/年份/包装/检测报告）需大量扩展；`product.template` 承载内部 SKU，自研承载对外发布信息 |
| 库存管理 | **Odoo（主，账实）** | `stock` `stock_account` | ★★★★★ | 多仓库、库位、批次/序列号、调拨、盘点、成本核算（FIFO/AVCO）成熟；自研侧只做交易可用量与预占 |
| 仓储物流（WMS 深度） | **Odoo（主）** | `stock` `delivery` | ★★★★ | 波次/拣货策略需企业版或三方 WMS，阶段一用原生 + 自研物流信息登记 |
| 财务管理 / 总账 | **Odoo（主）** | `account` `account_accountant`(EE) | ★★★★★ | 会计科目、凭证、多币种、税、报表；自研绝不自建总账 |
| 应收应付 | **Odoo（主）** | `account` | ★★★★★ | 与销售/采购单自动挂账 |
| 电子结算（平台交易流水/对账） | **自研（主）** + Odoo（凭证） | 无 | ☆ | 平台撮合产生的"交易流水、结算单、平台服务费"是平台级对象，不属于单一法人账套；自研生成后推 Odoo 生成凭证 |
| CRM | **Odoo（主，内部销售）** | `crm` | ★★★★ | 园区招商、客户跟进 |
| 合同管理 | **自研（主）** + Odoo（附件） | `sign`(EE) | ★★☆ | 平台合同含三方（买方/卖方/平台）要素与在线签署，Odoo CE 无签署能力 |
| 智慧园区（园区/区域/档口/入驻/费用/巡检） | **自研（主）** | 无 | ☆ | Odoo 无档口空间资源模型；用 `product` 模拟档口是典型的错误建模 |
| 食品安全溯源（批次二维码） | **自研（主）** | `stock.lot` 可辅助 | ★★☆ | 溯源链跨"基地→加工→仓储→交易→销售"多主体，超出单一 Odoo 库的数据边界，需平台级聚合 |
| 数据分析 / 驾驶舱 | **Superset + 自研聚合 API** | `analytic` 报表 | ★★★ | 产业级指标需跨库跨主体，Odoo 报表引擎不适用；Superset 直连两库 |
| 小程序 / 对外 API | **自研** | 无 | ☆ | Odoo 无面向互联网的多租户 REST API 与限流/鉴权体系 |
| 消息通知 / 待办 | 自研 | `mail` 可内部用 | ★★★ | 短信/微信模板消息需自研 |

### 1.2 一句话结论

> **Odoo 承载"法人内部的经营与账务"（采购、销售、库存账实、财务、CRM）；自研承载"跨法人的产业交易与公共运营"（撮合、合同、园区、结算、溯源、数据）。**

判断某个功能归属的**三条判据**：

1. **主体判据**：数据属于"某一个法人企业" → Odoo；数据属于"平台/多个法人之间的公共空间" → 自研。
2. **账实判据**：影响会计凭证与库存账实的 → Odoo；只是信息流/意向流的 → 自研。
3. **模型判据**：Odoo 原生模型能 80% 覆盖 → 定制扩展放在 Odoo；原生模型覆盖不足 50% → 自研。

## 二、自研模块边界（Bounded Context）

```
                    ┌──────────────── 平台侧（自研，gz_platform 库） ────────────────┐
                    │                                                              │
   ┌────────────────┴─────────────┐   ┌──────────────────┐   ┌────────────────────┐ │
   │ 交易域 Trade                  │   │ 园区域 Park       │   │ 结算域 Settlement   │ │
   │  询价单 inquiry               │   │  园区 park        │   │ 结算单 settlement   │ │
   │  报价单 quotation             │   │  区域 zone        │   │ 交易流水 flow       │ │
   │  订单 order / order_item      │   │  档口 stall       │   │ 对账 reconciliation │ │
   │  合同 contract                │   │  入驻申请 / 合同   │   │ 平台服务费          │ │
   │  交付 delivery                │   │  费用 / 巡检      │   │                    │ │
   └────────────┬─────────────────┘   └────────┬─────────┘   └─────────┬──────────┘ │
                │                              │                       │            │
   ┌────────────┴──────────────────────────────┴───────────────────────┴──────────┐ │
   │ 主数据域 Master Data                                                          │ │
   │  组织 org_unit(平台/园区/企业) 用户 user 角色 role 权限 permission             │ │
   │  企业 enterprise 商品分类 category 商品 product 仓库 warehouse 库位 location  │ │
   │  库存 inventory 库存流水 stock_move                                           │ │
   └───────────────────────────────┬───────────────────────────────────────────────┘ │
                    └──────────────┼───────────────────────────────────────────────┘
                                   │  集成层 Integration（唯一跨边界通道）
                    ┌──────────────▼───────────────┐
                    │ odoo_client (JSON-RPC)       │
                    │ sync_outbox (出站事件表)      │
                    │ id_map (两侧主键映射)         │
                    │ sync_log (同步日志/重试)      │
                    └──────────────┬───────────────┘
                    ┌──────────────▼───────────────────────────────┐
                    │ 企业侧 Odoo（gz_odoo 库）                     │
                    │  res.partner / product.template / stock.*     │
                    │  purchase.order / sale.order / account.move   │
                    └───────────────────────────────────────────────┘
```

### 2.1 集成契约（唯一通道）

**禁止**：自研平台直接 `INSERT/UPDATE` 访问 Odoo 库的表。
**允许**：自研 → Odoo 通过 `sync_outbox` 表 + 后台 worker 调用 Odoo JSON-RPC；Odoo → 自研通过 Odoo `ir.cron` 调用自研开放接口（`/api/v1/integration/odoo/*`，HMAC 签名）。

| 同步对象 | 方向 | 触发 | 幂等键 | 冲突策略 |
| --- | --- | --- | --- | --- |
| 企业档案 enterprise → res.partner | 自研 → Odoo | 企业审核通过 | `enterprise.code` | Odoo 侧只读，以自研为准 |
| 商品 product → product.template | 自研 → Odoo | 商品发布/变更 | `product.code` | 自研为准（名称/规格/等级） |
| 库存 inventory ← stock.quant | Odoo → 自研 | 定时 5min + 事件 | `warehouse+product+batch` | Odoo 为准（账实） |
| 订单 order → sale.order | 自研 → Odoo | 订单确认 | `order.order_no` | 自研为源，Odoo 生成销售单 |
| 采购订单 → purchase.order | 自研 → Odoo | 买方确认 | `order.order_no` | 同上，买方视角生成采购单 |
| 结算单 settlement → account.move | 自研 → Odoo | 结算单确认 | `settlement.settlement_no` | 自研为源，Odoo 生成凭证草稿 |

关键表：

```sql
sync_outbox(id, event_type, aggregate_type, aggregate_id, payload jsonb,
            status[pending/processing/success/failed], retry_count,
            next_retry_at, last_error, created_at, processed_at)
integration_id_map(local_type, local_id, remote_model, remote_id, updated_at)
integration_sync_log(id, direction, event_type, aggregate_id, request, response,
                     success, error, duration_ms, created_at)
```

### 2.2 边界防腐措施

1. **Odoo 定制全部落在 `gz_*` 独立模块**，不改 `odoo/addons` 与 `odoo/core`；模块间只用 `_inherit` 与依赖声明，禁止 monkey patch。
2. **自研侧不出现 Odoo 概念**（如 `account.move`、`stock.quant`），只出现领域概念（结算单、库存），由集成层翻译。
3. **双写禁止**：库存账实只有 Odoo 一个写入方，自研库存表的 `quantity` 是"交易可用量视图"，通过同步更新；交易预占量 `locked_quantity` 由自研维护。
4. **接口版本化**：自研对外 `/api/v1`，Odoo 侧调用集成接口同样带版本。

## 三、Odoo 定制模块清单（gz_*）

| 模块 | 依赖 | 承载内容 | 阶段 |
| --- | --- | --- | --- |
| `gz_platform_base` | `base`, `contacts`, `mail` | 企业主体模型 `gz.enterprise`、角色安全组、二次开发基础配置 | 一 |
| `gz_merchant` | `gz_platform_base` | 商户档案扩展、入驻审核流程、经营范围、资质附件 | 一 |
| `gz_product` | `gz_platform_base`, `product`, `stock` | 瓜子油料分类树、商品扩展字段（规格/等级/产地/年份/包装/检测报告） | 一 |
| `gz_inventory` | `gz_product`, `stock` | 批次 `gz.stock.batch`、质检状态、仓储参数、库存看板视图 | 一 |
| `gz_trade` | `gz_product`, `gz_inventory`, `sale_management`, `purchase` | 平台订单/询价/报价在 Odoo 侧的镜像单据、订单转销售单/采购单、结算凭证草稿 | 一 |
| `gz_park` | `gz_platform_base`, `account` | 园区/区域/档口/入驻合同/租金费用/巡检（阶段二） | 二 |
| `gz_data` | 全部 | Odoo 侧指标 SQL 视图、供 Superset 直连 | 二 |

## 四、风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| 双核心带来数据不一致 | 账实不符 | outbox 最终一致 + 每日对账任务 + 差异告警；库存以 Odoo 为准 |
| Odoo 定制模块升级困难 | 版本升级受阻 | 只用官方扩展点（`_inherit`/视图继承/xpath），禁止改核心；模块语义化版本 |
| 自研域模型膨胀 | 沦为"第二个 ERP" | 用第一节三条判据严格评审，凡属法人内部账务一律推给 Odoo |
| 农产品非标导致商品模型失控 | 撮合效率低 | 建立分类 + 等级 + 规格三级标准字典，平台统一编码（`GZ-CAT-xxx`） |
| 中间件故障 | 交易中断 | 全部适配器可降级（ADR-06） |
| 资金合规 | 监管风险 | 不自建支付通道，只做流水与对账（ADR-07） |
