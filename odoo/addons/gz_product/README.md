# gz_product — 瓜子油料平台商品域

## 模块用途

把 Odoo 原生 `product` / `product.category` 扩展为**瓜子油料商品中心**，
承载农产品的非标属性（规格 / 等级 / 产地 / 年份 / 包装 / 检测报告）与平台
上下架、审核流程。

- 分类树：瓜子油料(GZ) → 葵花籽 / 南瓜籽 / 打瓜籽 / 加工产品 →（炒货成品 / 榨油原料 / 饲料原料）；
- 商品扩展：归属商户、规格、等级（特级/一级/二级/统货）、产地、年份、包装、质检状态、
  检测报告、批次溯源开关、平台发布状态与审核状态、起订量、库存预警值；
- 上架前置校验：未通过平台审核（`gz_audit_status != 'approved'`）或质检不合格时
  `action_gz_publish()` 抛 `UserError`；
- 平台商品审核日志 `gz.product.audit.log`。

## 依赖

`gz_platform_base`、`product`、`stock`。安装顺序：第 3。

## 模型清单

| 模型 | 类型 | 关键字段 |
| --- | --- | --- |
| `product.category` | `_inherit` | `gz_category_type` `gz_code` `gz_is_leaf` |
| `product.template` | `_inherit` | `gz_enterprise_id` `gz_spec` `gz_grade` `gz_origin` `gz_harvest_year` `gz_package` `gz_quality_status` `gz_test_report` `gz_test_report_filename` `gz_trace_enabled` `gz_publish_state` `gz_audit_status` `gz_audit_remark` `gz_audit_user_id` `gz_audit_date` `gz_min_order_qty` `gz_stock_warn_qty` `gz_audit_log_ids` |
| `gz.product.audit.log` | 新建 | `product_tmpl_id` `product_id` `action` `note` `operator_id` `event_time` |

### 状态定义

- `gz_grade`：`special` 特级 / `first` 一级 / `second` 二级 / `mixed` 统货
- `gz_quality_status`：`pending` 待检 / `qualified` 合格 / `unqualified` 不合格
- `gz_publish_state`：`draft` / `published` / `offline` / `rejected`
- `gz_audit_status`：`pending` / `approved` / `rejected`

### 方法

| 方法 | 说明 |
| --- | --- |
| `action_gz_submit_audit()` | 提交平台审核（重置审核状态为待审核） |
| `action_gz_audit_approve()` | 平台审核通过 |
| `action_gz_audit_reject()` | 平台审核驳回（要求先填审核意见），同时置发布状态为已驳回 |
| `action_gz_publish()` | 上架（**必须已审核通过且质检非不合格**，否则 `UserError`） |
| `action_gz_offline()` | 下架 |
| `_gz_log_audit(action, note)` | 写审核日志（`sudo`） |

## 视图

| 文件 | 内容 |
| --- | --- |
| `views/product_template_views.xml` | 继承 `product.product_template_form_view` 插入「瓜子油料信息」「平台审核日志」页签与操作按钮；继承 `product.product_template_tree_view` 增加规格/等级/产地/年份/状态列；继承 `product.product_template_search_view` 增加等级/产地/发布状态过滤器与分组；自定义动作 `action_gz_product_template` |
| `views/product_category_views.xml` | 自定义分类 列表 / 表单 / 搜索 / 动作（不继承原生分类视图，避免依赖不确定的外部 ID） |
| `views/gz_menu.xml` | `瓜子油料平台 → 商品中心 → 商品档案 / 商品分类` |

## 安全

`security/ir.model.access.csv` 仅授权 `gz.product.audit.log`；
`product.template` / `product.category` 沿用原生权限（**刻意不加限制**，
否则采购商无法浏览供应商商品，B2B 撮合链路不可用）。
`security/security.xml` 只对审核日志做按企业可见性限制。

## 数据文件

`data/gz_product_category.xml`（`noupdate="1"`）：预置 8 条分类记录，
外部 ID 为 `gz_categ_root` / `gz_categ_sunflower` / `gz_categ_pumpkin` /
`gz_categ_seed` / `gz_categ_processed` / `gz_categ_roast` / `gz_categ_oil` /
`gz_categ_feed`。

## 与自研平台集成（docs/03 第 9 节）

| 自研 | Odoo |
| --- | --- |
| `product.code` | `product.template.default_code` |
| `product.name` | `product.template.name` |
| `product.spec/grade/origin/harvest_year/package` | `gz_spec` / `gz_grade` / `gz_origin` / `gz_harvest_year` / `gz_package` |
| `product.enterprise_id` | `gz_enterprise_id` |
| `product.status` / `product.audit_status` | `gz_publish_state` / `gz_audit_status` |
| `product.test_report_url` | `gz_test_report`（Binary，附件库） |

## 已知风险 / 待验证

- 视图继承依赖 `product.product_template_form_view`、`product.product_template_tree_view`、
  `product.product_template_search_view` 三个原生外部 ID；已在 Odoo 17 源码约定下核对，
  **未在本机运行 Odoo 验证**，升级到 18 时需重新核对（18 已把 `<tree>` 改为 `<list>`）。
- 商品级数据隔离刻意放在自研平台侧实现（Odoo 侧不做限制）。
