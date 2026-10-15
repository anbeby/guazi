# gz_merchant — 瓜子油料平台商户域

## 模块用途

在 `gz_platform_base` 的企业主体基础上扩展**商户 / 供应商档案与入驻流程**：

- 证照与经营能力：营业执照号、食品生产许可证号、商户等级、年产能（吨）、主营产品；
- 资质附件台账：营业执照 / 食品生产许可证 / 检测报告 / 其他，含有效期与自动到期状态；
- 入驻申请流程：`草稿 → 已提交 → 审核通过 / 审核驳回`，通过后回填企业主体园区信息；
- 商户档案、入驻申请（列表 / 看板 / 表单）、资质台账视图与菜单。

## 依赖

`gz_platform_base`、`mail`。安装顺序：第 2（在 `gz_platform_base` 之后）。

## 模型清单

| 模型 | 类型 | 说明 |
| --- | --- | --- |
| `gz.enterprise` | `_inherit`（gz_platform_base） | 追加 `license_no` `food_production_license` `merchant_level` `annual_capacity` `main_products` `qualification_ids` `qualification_count` `expired_qualification_count` `entry_ids` |
| `gz.merchant.qualification` | 新建 | 资质附件：`enterprise_id` `name` `qual_type` `file` `file_name` `issue_date` `expire_date` `state` `days_to_expire` `remark` |
| `gz.merchant.entry` | 新建 | 入驻申请：`name`(GZ-ENTRY-<年>-<流水>) `enterprise_id` `enterprise_type` `park_name` `stall_code` `apply_date` `applicant` `contact_phone` `main_products` `state` `audit_user_id` `audit_date` `audit_remark` `remark` |

### 方法

| 模型 | 方法 | 说明 |
| --- | --- | --- |
| `gz.merchant.qualification` | `action_set_invalid()` | 作废资质（状态不再被日期覆盖） |
| `gz.merchant.entry` | `action_submit()` / `action_approve()` / `action_reject()` / `action_reset_draft()` | 入驻申请状态流转；驳回必须先填审核意见 |

### 状态定义

- 资质 `state`：`valid` 有效 / `expiring` 即将到期（≤30 天）/ `expired` 已过期 / `invalid` 作废
- 入驻申请 `state`：`draft` / `submitted` / `approved` / `rejected`

## 安全

- `security/ir.model.access.csv`：平台管理员全权限；园区运营读 + 写；商户 / 供应商读写；采购商 / 财务只读。
- `security/security.xml`：记录规则 `rule_gz_merchant_qualification_own_company`、
  `rule_gz_merchant_entry_own_company`，商户 / 供应商 / 采购商仅可见
  `enterprise_id.partner_id = user.partner_id` 的资质与申请。

## 视图

| 文件 | 内容 |
| --- | --- |
| `views/gz_enterprise_views.xml` | 继承企业主体 列表 / 表单，新增「商户档案」「入驻申请」页签；`action_gz_merchant_profile` |
| `views/gz_merchant_qualification_views.xml` | 资质附件 列表 / 表单 / 搜索 / 动作 |
| `views/gz_merchant_entry_views.xml` | 入驻申请 列表 / 看板 / 表单（chatter + 状态栏）/ 搜索 / 动作 |
| `views/gz_menu.xml` | `瓜子油料平台 → 商户中心 → 商户档案 / 入驻申请 / 资质台账` |

## 数据文件

`data/gz_sequence.xml`：入驻申请序列（`noupdate="1"`），
code = `gz.merchant.entry`，前缀 `GZ-ENTRY-<年>-`，4 位流水。

## 与自研平台的对应

自研 `enterprise` 的证照类字段（`license_no` 等）与 `stall_id`、`park_id`
在本模块以扩展字段 / 文本占位承载；阶段二 `gz_park` 接管园区与档口资源模型后，
`park_name` / `stall_code` 将改为 Many2one。

## 已知风险 / 待验证

- `state` 为 `compute + store + readonly=False`，人工置 `invalid` 后不会被日期重算覆盖；
  其余取值在 `expire_date` 变更时自动重算，需在真实环境回归验证。
- 入驻审核通过时使用 `sudo()` 回填企业主体园区，绕过记录规则，属有意为之（审核人可能是园区运营）。
