# gz_trade — 瓜子油料平台交易域

## 模块用途

自研平台是 B2B 撮合交易的主承载方，本模块把**询价 → 报价 → 订单 → 合同 →
结算 → 流水**整条链路在 Odoo 侧落地为镜像单据，并完成与
`sale_management` / `purchase` / `account` 的对接（docs/02 第 2.1 节集成契约）：

| 平台动作 | Odoo 结果 | 幂等键 |
| --- | --- | --- |
| 接受报价 `gz.quotation.action_accept()` | 生成 `gz.order`（`pending_confirm`） | `quotation.name` |
| 确认订单 `gz.order.action_confirm()` | 置 `confirmed` + `stock_deducted=True` + 写订单轨迹 | `order.name` |
| 生成销售单 `action_create_sale_order()` | `sale.order`（`client_order_ref` = 订单号） | `order.name` |
| 生成采购单 `action_create_purchase_order()` | `purchase.order`（`partner_ref` = 订单号） | `order.name` |
| 生成凭证 `action_create_settlement_move()` / `gz.settlement.action_confirm()` | `account.move` 草稿（`ref` = 订单号 / 结算单号） | `order.name` / `settlement.name` |

## 依赖

`gz_product`、`gz_inventory`、`sale_management`、`purchase`、`account`。
安装顺序：第 5（最后）。

## 模型清单

| 模型 | 说明 |
| --- | --- |
| `gz.inquiry` | 询价单：`name`(GZ-INQ-<年>-<流水>) `buyer_enterprise_id` `supplier_enterprise_id` `product_id` `quantity` `unit` `expect_price` `currency_id` `expect_delivery_date` `delivery_address` `state` `quotation_ids` `quoted_count` `remark` |
| `gz.quotation` | 报价单：`name`(GZ-QUO-) `inquiry_id` `buyer_enterprise_id` `supplier_enterprise_id` `product_id` `quantity` `unit_price` `amount`(computed) `tax_rate` `valid_until` `delivery_date` `payment_terms` `state` `order_id` |
| `gz.order` | 平台订单：`name`(GZ-SO-) `order_type` `inquiry_id` `quotation_id` `buyer_enterprise_id` `supplier_enterprise_id` `line_ids` `amount_untaxed` `tax_amount` `amount_total`（均 computed store）`currency_id` `delivery_date` `delivery_address` `stock_deducted` `state` `sale_order_id` `purchase_order_id` `timeline_ids` `contract_ids` `trade_flow_ids` `remark` |
| `gz.order.line` | 订单明细：`order_id` `product_id` `quantity` `delivered_quantity` `unit_price` `tax_rate` `price_subtotal`(computed store) `uom_id` |
| `gz.order.timeline` | 订单轨迹：`order_id` `state` `note` `operator_id` `event_time` |
| `gz.contract` | 平台合同：`name`(GZ-CT-) `title` `order_id` `buyer_enterprise_id` `supplier_enterprise_id` `amount` `sign_date` `start_date` `end_date` `file` `state` `signed_by_buyer` `signed_by_supplier` `buyer_signed_at` `supplier_signed_at` |
| `gz.settlement` | 结算单：`name`(GZ-SET-) `enterprise_id` `settle_type` `period_start` `period_end` `order_amount` `fee_amount` `settle_amount` `settled_amount` `pay_status` `state` `line_ids` `move_id` |
| `gz.settlement.line` | 结算明细：`settlement_id` `biz_type` `biz_no` `amount` `fee_rate` `remark` |
| `gz.trade.flow` | 交易流水：`name`(GZ-FLOW-) `order_id` `enterprise_id` `direction` `biz_type` `amount` `pay_method` `pay_status` `trade_no` `paid_at` |
| `gz.account.move.mixin` | 抽象模型（无表）：`_gz_create_draft_move()` 生成应收/应付凭证草稿，被 `gz.order` 与 `gz.settlement` 复用 |

唯一约束：`gz.inquiry.name`（序列保证）、`gz.quotation.name`、`gz.order.name`、
`gz.contract.name`、`gz.settlement.name`、`gz.trade.flow.name` 均由 `ir.sequence`
唯一生成；`gz.order.name`、`gz.settlement.name` 显式声明了 `_sql_constraints`。

## 状态机

- 询价单 `state`：`draft → submitted → quoted → confirmed →（closed / cancelled）`
- 报价单 `state`：`submitted →（accepted / rejected / expired）`
- 平台订单 `state`：`draft → pending_confirm → confirmed → delivering → completed → settled`，
  任意阶段（未完成/未结算前）可 `cancelled`
- 合同 `state`：`draft → pending_sign → signed → effective →（terminated / expired）`
- 结算单 `state`：`pending → confirmed → settled`（可 `cancelled`）
- `pay_status`：`unpaid / partial / paid`
- 交易流水 `pay_status`：`pending / success / failed`

## 定时任务（data/gz_trade_cron.xml）

`ir.cron`（Odoo 17 的 `ir.cron` 基于 `ir.actions.server`，`model_id` / `state` /
`code` 通过 delegate 直接写在 cron 记录上）：

- 名称：瓜子油料：平台订单进度同步（每 30 分钟）
- 调用：`model._cron_sync_platform()`（`gz.order`）
- 行为：读取 `gz_platform.api_base_url` / `gz_platform.api_token` 系统参数，
  `POST {base_url}/api/v1/integration/odoo/ack-order` 回执订单进度；
  **未配置地址、`requests` 缺失、网络异常、HTTP 错误一律只记日志并返回 False，不抛异常**。
- `noupdate="1"`：部署环境调整周期不会被升级覆盖。

## 安全

- `security/ir.model.access.csv`（45 条）：平台管理员全权限；园区运营读 + 部分写；
  商户 / 供应商读写本企业单据；采购商可创建询价、写订单 / 报价 / 合同，结算与流水只读；
  财务可读写结算单、结算明细、交易流水，业务单据只读。
- `security/security.xml`：9 条按企业隔离的记录规则，统一以
  `user.partner_id` 与单据上的 `buyer_enterprise_id` / `supplier_enterprise_id` /
  `enterprise_id` 比对；询价单额外允许供应商看到“公开询价（未指定供应商）”。

## 视图

| 文件 | 内容 |
| --- | --- |
| `views/gz_inquiry_views.xml` | 询价单 列表 / 表单（状态栏、报价数统计按钮、报价页签、chatter）/ 搜索 / 动作 |
| `views/gz_quotation_views.xml` | 报价单 列表 / 表单（接受生成订单、拒绝）/ 搜索 / 动作 |
| `views/gz_order_views.xml` | 平台订单 列表 / 表单（明细可编辑 + 金额小计、订单轨迹页签、关联单据页签、7 个业务按钮、chatter）/ 搜索 / 动作（含待确认订单） |
| `views/gz_contract_views.xml` | 合同 列表 / 表单（双边签署、生效、终止）/ 搜索 / 动作 |
| `views/gz_settlement_views.xml` | 结算单 列表 / 表单（确认生成凭证、结算、查看凭证）/ 搜索 / 动作（含待回款） |
| `views/gz_trade_flow_views.xml` | 交易流水 列表 / 表单（登记支付成功/失败）/ 搜索 / 动作 |
| `views/gz_menu.xml` | `瓜子油料平台 → 交易中心 → 撮合交易（询价单/报价单）、订单与合同（平台订单/待确认订单/合同管理）、结算与资金（结算单/待回款结算单/交易流水）` |

## 与自研平台的接口对应（docs/04 第 2.7、2.8、2.12 节）

| 自研接口 | Odoo 侧动作 |
| --- | --- |
| `POST /inquiries/{id}/submit` | `gz.inquiry.action_submit()` |
| `POST /inquiries/{id}/cancel` | `gz.inquiry.action_cancel()` |
| `POST /quotations/{id}/accept` | `gz.quotation.action_accept()` → 生成 `gz.order` |
| `POST /quotations/{id}/reject` | `gz.quotation.action_reject()` |
| `POST /orders/{id}/confirm` | `gz.order.action_confirm()` |
| `POST /orders/{id}/complete` | `gz.order.action_complete()` |
| `POST /orders/{id}/cancel` | `gz.order.action_cancel()` |
| `GET /orders/{id}/timeline` | `gz.order.timeline_ids` |
| `POST /contracts/{id}/sign` | `action_sign_buyer()` / `action_sign_supplier()` |
| `POST /settlements/{id}/confirm` | `gz.settlement.action_confirm()` → `account.move` 草稿 |
| `POST /integration/odoo/ack-order` | `gz.order._cron_sync_platform()` |

## 已知风险 / 待验证

1. **未运行 Odoo 验证**：本模块代码按 Odoo 17 API 编写（`fields.Command`、
   `invisible="expr"`、`ir.cron` 基于 `ir.actions.server`），需在真实实例上安装回归。
2. `sale.order.line.tax_id` / `purchase.order.line.taxes_id` 被显式清空，
   以避免与平台侧计税重复；若企业要求 Odoo 侧也计税，需要改为按 `tax_rate`
   匹配 Odoo 税种。
3. `_gz_create_draft_move()` 在通过平台角色校验后使用 `sudo()` 创建凭证草稿
   （Odoo 会计权限由平台角色而非 `account` 组控制），科目取往来单位默认科目，
   缺失时按 `account_type` 兜底检索；生产环境应显式配置科目表与默认科目。
4. `stock_deducted` 仅做平台标记，**不直接改写库存账实**（双写禁止，
   账实由 Odoo 库存单据 / 集成层负责）。
5. 记录规则的 `user.partner_id` 依赖“企业 ↔ res.partner ↔ 用户”的关联链路，
   上线前需确认每个企业账号的 `res.partner` 已正确同步。
