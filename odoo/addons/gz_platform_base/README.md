# gz_platform_base — 瓜子油料平台基础

## 模块用途

第十师瓜子油料数字化交易平台在 Odoo 企业侧的**主体域基础模块**。承载：

- 企业主体档案 `gz.enterprise`（商户 / 供应商 / 采购商 / 平台），与自研平台
  `gz_platform.gz.enterprise` 通过 `code`、`unified_social_credit_code` 对齐；
- 企业主体 ↔ `res.partner` 往来单位同步（`ref` = 企业编码、`vat` = 统一社会信用代码、
  `company_type` = company、`supplier_rank/customer_rank`）；
- 平台六类角色安全组与**企业级数据隔离**记录规则；
- 企业编码序列 `ENT-<年>-<5 位流水>`（`ir.sequence` code = `gz.enterprise`）；
- 平台根菜单 `瓜子油料平台`，作为 gz_merchant / gz_product / gz_inventory / gz_trade
  各模块菜单挂载点。

## 依赖

`base`、`contacts`、`mail`（无自研模块依赖，安装顺序第一）。

## 模型清单

| 模型 | 说明 | 关键字段 |
| --- | --- | --- |
| `gz.enterprise` | 企业主体档案 | `name` `code` `unified_social_credit_code` `enterprise_type` `legal_person` `registered_capital` `business_scope` `contact_name` `contact_phone` `email` `region` `address` `park_name` `platform_code` `audit_status` `audit_remark` `status` `partner_id` `remark` |

唯一约束：`code`、`unified_social_credit_code`。

方法：

| 方法 | 说明 |
| --- | --- |
| `action_approve()` | 审核通过，回写审核人/审核时间，并同步往来单位 |
| `action_reject()` | 审核驳回（要求先填写审核意见），企业置停用 |
| `action_reset_pending()` | 撤回审核结果回到待审核 |
| `action_sync_partner()` | 按钮：同步往来单位并打开 `res.partner` 表单 |
| `_gz_sync_partner()` | 内部方法：按 `ref` 幂等创建 / 更新 `res.partner`，供 `gz_trade` 复用 |
| `_gz_get_user_enterprise()` | 按 `user.partner_id` 反查企业主体，供其他 gz_* 模块取默认值 |

## 安全组

| 外部 ID | 名称 | 对应自研角色 |
| --- | --- | --- |
| `group_gz_platform_admin` | 平台管理员 | `platform_admin` |
| `group_gz_park_operator` | 园区运营人员 | `park_operator` |
| `group_gz_merchant` | 商户 | `merchant` |
| `group_gz_supplier` | 供应商 | `supplier` |
| `group_gz_buyer` | 采购商 | `buyer` |
| `group_gz_finance` | 财务 | `finance` |

记录规则 `rule_gz_enterprise_own_company`：商户 / 供应商 / 采购商仅可见
`partner_id = user.partner_id`（或本人创建）的企业主体；平台管理员、财务不限制。
园区运营按园区过滤的规则待阶段二 `gz_park` 模块追加 `park_id` 后补充。

## 视图与菜单

- `views/gz_enterprise_views.xml`：企业主体 列表 / 表单（含审核状态栏、往来单位页签、chatter）/ 搜索
- `views/gz_menu.xml`：`瓜子油料平台`（根）→ `平台基础` → `企业主体`

## 与自研平台的集成

| 方向 | 触发 | 幂等键 | 冲突策略 |
| --- | --- | --- | --- |
| 自研 → Odoo | 企业审核通过 | `enterprise.code` | 以自研为准，Odoo 侧 `gz.enterprise` 只做承载 |

自研侧通过 JSON-RPC（`sync_outbox` + worker）创建 / 更新 `gz.enterprise`，
本模块在审核通过时把数据同步到 `res.partner`，保证全 Odoo 往来单位主键唯一。

字段映射（docs/03 第 9 节）：

| 自研 | Odoo |
| --- | --- |
| `enterprise.code` | `gz.enterprise.code` → `res.partner.ref` |
| `enterprise.name` | `gz.enterprise.name` → `res.partner.name` |
| `enterprise.unified_social_credit_code` | `res.partner.vat` |
| `enterprise.enterprise_type` | `gz.enterprise.enterprise_type` |
| `enterprise.audit_status` | `gz.enterprise.audit_status` |
| `enterprise.park_id` | `gz.enterprise.park_name`（阶段一占位，阶段二换 `park_id`） |

## 安装顺序

1（最先安装）。

## 已知风险 / 待验证

- `%(year)s` 序列占位符与 `padding` 组合生成为 `ENT-2025-00001`，需在真实
  Odoo 17 实例上确认 `ir.sequence` 的占位符行为（本仓库未运行 Odoo 验证）。
- 阶段一 `park_name` 为 Char 占位；阶段二 `gz_park` 模块需提供迁移脚本把
  `park_name` 匹配为 `park_id`。
