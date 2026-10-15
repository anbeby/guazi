# gz_inventory — 瓜子油料平台库存域

## 模块用途

按“**Odoo 承载账实、平台承载交易视图**”的边界（docs/02 第 1.1、2.2 节），
本模块只在 Odoo 侧增加平台视角的批次与仓储参数，不改变原生库存账实逻辑：

- `gz.stock.batch`：平台批次（批次号 / 商品 / 归属企业 / 仓库 / 生产与失效日期 /
  数量 / 质检状态 / 检测报告 / 溯源码 / 种植基地）+ **库存预警**标记；
- `gz.warehouse.config`：仓储参数（库位数 / 库容 / 温控 / 联系方式）；
- `_inherit stock.lot`：原生批次挂接平台批次、质检状态与溯源码；
- 视图与菜单：`仓储管理 → 批次管理 / 库存预警 / 仓储参数`。

## 依赖

`gz_product`、`stock`。安装顺序：第 4（在 `gz_product` 之后）。

## 模型清单

| 模型 | 类型 | 关键字段 |
| --- | --- | --- |
| `gz.stock.batch` | 新建 | `name`(GZ-BATCH-<年>-<流水>) `product_id` `product_tmpl_id` `enterprise_id` `warehouse_id` `location_id` `lot_ids` `production_date` `expiry_date` `quantity` `uom_id` `quality_status` `test_report` `test_report_filename` `trace_code` `origin_base` `remark` `below_warn_qty` |
| `gz.warehouse.config` | 新建 | `warehouse_id` `enterprise_id` `park_name` `warehouse_type` `location_count` `capacity` `temperature_control` `contact_name` `contact_phone` `address` `remark` |
| `stock.lot` | `_inherit` | `gz_batch_id` `gz_quality_status` `gz_trace_code` |

唯一约束：`gz.stock.batch.name`、`gz.warehouse.config.warehouse_id`。

### 方法

| 模型 | 方法 | 说明 |
| --- | --- | --- |
| `gz.stock.batch` | `action_mark_qualified()` / `action_mark_unqualified()` | 质检结论 |
| `gz.stock.batch` | `action_generate_trace_code()` | 幂等生成溯源码（`{gz_platform.public_base_url}/api/v1/trace/public/{批次号}`） |
| `stock.lot` | `action_gz_sync_from_batch()` | 从平台批次同步质检状态与溯源码 |

### 库存预警实现

`below_warn_qty = product_id.gz_stock_warn_qty > 0 and quantity < product_id.gz_stock_warn_qty`
（`compute + store`，依赖 `quantity` 与 `product_id.gz_stock_warn_qty`），
支撑「库存预警」菜单的 `[('below_warn_qty', '=', True)]` 过滤，
避免使用 Odoo 域表达式不支持的“字段与字段比较”。

## 安全

- `security/ir.model.access.csv`：批次——平台管理员全权限、园区运营读写建、商户/供应商读写建、
  采购商/财务只读；仓储参数——仅平台管理员与园区运营可写。
- `security/security.xml`：`rule_gz_stock_batch_own_company`，商户/供应商/采购商仅见本企业批次
  （`enterprise_id` 为空的平台公共批次对所有角色可见）。

## 视图

| 文件 | 内容 |
| --- | --- |
| `views/gz_stock_batch_views.xml` | 批次 列表（含预警/质检配色、数量合计）/ 表单（状态栏、质检与溯源码按钮、Odoo 批次页签）/ 搜索；动作 `action_gz_stock_batch`、`action_gz_stock_batch_warning` |
| `views/gz_warehouse_config_views.xml` | 仓储参数 列表 / 表单 / 搜索 / 动作 |
| `views/stock_lot_views.xml` | 继承 `stock.view_production_lot_form`、`stock.view_production_lot_tree` |
| `views/gz_menu.xml` | `瓜子油料平台 → 仓储管理 → 批次管理 / 库存预警 / 仓储参数` |

## 数据文件

`data/gz_sequence.xml`：批次号序列（`noupdate="1"`），
code = `gz.stock.batch`，前缀 `GZ-BATCH-<年>-`，5 位流水。

## 与自研平台的集成

| 方向 | 对象 | 触发 | 幂等键 |
| --- | --- | --- | --- |
| Odoo → 自研 | 库存快照（`stock.quant` + 平台批次） | 定时 5min + 事件 | `warehouse+product+batch` |
| 自研 → Odoo | 溯源批次登记 | 批次创建 | `batch_no` |

自研侧 `inventory.quantity` 是“交易可用量视图”，Odoo 侧 `stock.quant.quantity`
为账实唯一来源（docs/02 第 2.2 节“双写禁止”）。

## 已知风险 / 待验证

- `stock.lot.product_qty` 用于批次表单中的数量展示，已在 Odoo 17 字段约定下核对，
  **未在本机运行 Odoo 验证**；若目标版本无该字段，需改为 `product_qty` 相关计算字段。
- 批次数量与 `stock.quant` 之间**不做自动同步**（阶段一由集成层负责），
  因此 `below_warn_qty` 预警基于平台登记数量。
