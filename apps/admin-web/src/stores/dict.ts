/**
 * 全局枚举字典。
 *
 * 取值严格来自 docs/04-接口规范.md「硬性要求」与 docs/03-数据模型设计.md 字段定义：
 *   企业类型 merchant/supplier/buyer/platform
 *   审核状态 pending/approved/rejected
 *   企业状态 active/disabled
 *   商品状态 draft/published/offline/rejected
 *   商品等级 special/first/second/mixed
 *   订单状态 draft/pending_confirm/confirmed/delivering/completed/settled/cancelled
 *   出入库类型 in/out/transfer/adjust/check
 *   结算类型 receivable/payable/park_fee
 *   支付状态 unpaid/partial/paid
 */
import { defineStore } from 'pinia'

export interface DictItem<T extends string | number = string> {
  label: string
  value: T
  /** Element Plus tag 类型 */
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  /** 主题色（图表 / 卡片用） */
  color?: string
}

function toMap<T extends string>(items: DictItem<T>[]): Record<string, DictItem<T>> {
  return items.reduce<Record<string, DictItem<T>>>((acc, item) => {
    acc[String(item.value)] = item
    return acc
  }, {})
}

/* ------------------------------ 企业 / 商户 ------------------------------ */

export const ENTERPRISE_TYPES: DictItem[] = [
  { label: '商户', value: 'merchant', type: 'primary', color: '#1f6feb' },
  { label: '供应商', value: 'supplier', type: 'success', color: '#16653f' },
  { label: '采购商', value: 'buyer', type: 'warning', color: '#d48806' },
  { label: '平台', value: 'platform', type: 'info', color: '#6b7280' }
]

export const AUDIT_STATUSES: DictItem[] = [
  { label: '待审核', value: 'pending', type: 'warning' },
  { label: '已通过', value: 'approved', type: 'success' },
  { label: '已驳回', value: 'rejected', type: 'danger' }
]

export const COMMON_STATUSES: DictItem[] = [
  { label: '正常', value: 'active', type: 'success' },
  { label: '已禁用', value: 'disabled', type: 'info' }
]

export const USER_STATUSES: DictItem[] = [
  { label: '正常', value: 'active', type: 'success' },
  { label: '已禁用', value: 'disabled', type: 'info' },
  { label: '已锁定', value: 'locked', type: 'danger' }
]

/* ------------------------------ 商品 ------------------------------ */

export const PRODUCT_STATUSES: DictItem[] = [
  { label: '草稿', value: 'draft', type: 'info' },
  { label: '已上架', value: 'published', type: 'success' },
  { label: '已下架', value: 'offline', type: 'warning' },
  { label: '审核驳回', value: 'rejected', type: 'danger' }
]

export const PRODUCT_GRADES: DictItem[] = [
  { label: '特级', value: 'special', type: 'danger', color: '#c0392b' },
  { label: '一级', value: 'first', type: 'warning', color: '#d48806' },
  { label: '二级', value: 'second', type: 'primary', color: '#1f6feb' },
  { label: '统货', value: 'mixed', type: 'info', color: '#6b7280' }
]

export const QUALITY_STATUSES: DictItem[] = [
  { label: '待检', value: 'pending', type: 'warning' },
  { label: '合格', value: 'qualified', type: 'success' },
  { label: '不合格', value: 'unqualified', type: 'danger' }
]

export const PRODUCT_UNITS: DictItem[] = [
  { label: '吨', value: 'ton' },
  { label: '千克', value: 'kg' },
  { label: '袋', value: 'bag' }
]

/* ------------------------------ 仓储库存 ------------------------------ */

export const WAREHOUSE_TYPES: DictItem[] = [
  { label: '自有仓', value: 'own', type: 'primary' },
  { label: '保税仓', value: 'bonded', type: 'warning' },
  { label: '临时仓', value: 'temp', type: 'info' }
]

export const STOCK_MOVE_TYPES: DictItem[] = [
  { label: '入库', value: 'in', type: 'success', color: '#16653f' },
  { label: '出库', value: 'out', type: 'warning', color: '#d48806' },
  { label: '调拨', value: 'transfer', type: 'primary', color: '#1f6feb' },
  { label: '调整', value: 'adjust', type: 'info', color: '#6b7280' },
  { label: '盘点', value: 'check', type: 'danger', color: '#c0392b' }
]

export const STOCK_REF_TYPES: DictItem[] = [
  { label: '手工操作', value: 'manual' },
  { label: '订单', value: 'order' },
  { label: '盘点', value: 'check' },
  { label: '调拨', value: 'transfer' }
]

/* ------------------------------ 交易 ------------------------------ */

export const INQUIRY_STATUSES: DictItem[] = [
  { label: '草稿', value: 'draft', type: 'info' },
  { label: '待报价', value: 'submitted', type: 'warning' },
  { label: '已报价', value: 'quoted', type: 'primary' },
  { label: '已确认', value: 'confirmed', type: 'success' },
  { label: '已关闭', value: 'closed', type: 'info' },
  { label: '已取消', value: 'cancelled', type: 'danger' }
]

export const QUOTATION_STATUSES: DictItem[] = [
  { label: '已提交', value: 'submitted', type: 'primary' },
  { label: '已接受', value: 'accepted', type: 'success' },
  { label: '已拒绝', value: 'rejected', type: 'danger' },
  { label: '已过期', value: 'expired', type: 'info' }
]

export const ORDER_STATUSES: DictItem[] = [
  { label: '草稿', value: 'draft', type: 'info' },
  { label: '待确认', value: 'pending_confirm', type: 'warning' },
  { label: '已确认', value: 'confirmed', type: 'primary' },
  { label: '发货中', value: 'delivering', type: 'primary' },
  { label: '已完成', value: 'completed', type: 'success' },
  { label: '已结算', value: 'settled', type: 'success' },
  { label: '已取消', value: 'cancelled', type: 'danger' }
]

export const ORDER_TYPES: DictItem[] = [
  { label: '销售单', value: 'sales' },
  { label: '采购单', value: 'purchase' }
]

export const CONTRACT_STATUSES: DictItem[] = [
  { label: '草稿', value: 'draft', type: 'info' },
  { label: '待签署', value: 'pending_sign', type: 'warning' },
  { label: '已签署', value: 'signed', type: 'primary' },
  { label: '已生效', value: 'effective', type: 'success' },
  { label: '已终止', value: 'terminated', type: 'danger' },
  { label: '已过期', value: 'expired', type: 'info' }
]

/* ------------------------------ 结算财务 ------------------------------ */

export const SETTLE_TYPES: DictItem[] = [
  { label: '应收', value: 'receivable', type: 'success' },
  { label: '应付', value: 'payable', type: 'warning' },
  { label: '园区费用', value: 'park_fee', type: 'primary' }
]

export const PAY_STATUSES: DictItem[] = [
  { label: '未支付', value: 'unpaid', type: 'danger' },
  { label: '部分支付', value: 'partial', type: 'warning' },
  { label: '已支付', value: 'paid', type: 'success' }
]

export const RECEIVE_STATUSES: DictItem[] = [
  { label: '未确认', value: 'unconfirmed', type: 'warning' },
  { label: '已确认', value: 'confirmed', type: 'success' }
]

export const SETTLEMENT_STATUSES: DictItem[] = [
  { label: '待确认', value: 'pending', type: 'warning' },
  { label: '已确认', value: 'confirmed', type: 'primary' },
  { label: '已结清', value: 'settled', type: 'success' },
  { label: '已取消', value: 'cancelled', type: 'danger' }
]

export const PAY_METHODS: DictItem[] = [
  { label: '银行转账', value: 'bank_transfer' },
  { label: '线下结算', value: 'offline' },
  { label: '其他', value: 'other' }
]

export const FLOW_DIRECTIONS: DictItem[] = [
  { label: '收入', value: 'in', type: 'success' },
  { label: '支出', value: 'out', type: 'warning' }
]

export const FLOW_BIZ_TYPES: DictItem[] = [
  { label: '订单货款', value: 'order_payment' },
  { label: '平台服务费', value: 'service_fee' },
  { label: '退款', value: 'refund' },
  { label: '保证金', value: 'deposit' }
]

export const FLOW_PAY_STATUSES: DictItem[] = [
  { label: '待支付', value: 'pending', type: 'warning' },
  { label: '支付成功', value: 'success', type: 'success' },
  { label: '支付失败', value: 'failed', type: 'danger' }
]

export const BIZ_TYPES: DictItem[] = [
  { label: '订单', value: 'order' },
  { label: '园区费用', value: 'park_fee' },
  { label: '服务费', value: 'service_fee' }
]

/* ------------------------------ 园区 ------------------------------ */

export const ZONE_TYPES: DictItem[] = [
  { label: '交易区', value: 'trade', type: 'primary' },
  { label: '加工区', value: 'processing', type: 'success' },
  { label: '物流区', value: 'logistics', type: 'warning' },
  { label: '服务区', value: 'service', type: 'info' }
]

export const STALL_STATUSES: DictItem[] = [
  { label: '空闲', value: 'free', type: 'success' },
  { label: '已租', value: 'rented', type: 'primary' },
  { label: '预留', value: 'reserved', type: 'warning' },
  { label: '维护中', value: 'maintenance', type: 'info' }
]

export const FEE_CYCLES: DictItem[] = [
  { label: '按月', value: 'month' },
  { label: '按季', value: 'quarter' },
  { label: '按年', value: 'year' }
]

export const PARK_CONTRACT_STATUSES: DictItem[] = [
  { label: '草稿', value: 'draft', type: 'info' },
  { label: '已生效', value: 'effective', type: 'success' },
  { label: '已到期', value: 'expired', type: 'warning' },
  { label: '已终止', value: 'terminated', type: 'danger' }
]

/* ------------------------------ 组织 / 溯源 ------------------------------ */

export const ORG_UNIT_TYPES: DictItem[] = [
  { label: '平台', value: 'platform', type: 'info' },
  { label: '园区', value: 'park', type: 'primary' },
  { label: '企业', value: 'enterprise', type: 'success' }
]

export const TRACE_STAGES: DictItem[] = [
  { label: '种植', value: 'planting', type: 'success' },
  { label: '加工', value: 'processing', type: 'warning' },
  { label: '仓储', value: 'warehouse', type: 'primary' },
  { label: '交易', value: 'trade', type: 'info' },
  { label: '销售', value: 'sale', type: 'danger' }
]

export const TRACE_BATCH_STATUSES: DictItem[] = [
  { label: '进行中', value: 'active', type: 'success' },
  { label: '已关闭', value: 'closed', type: 'info' }
]

/* ------------------------------ 系统集成 ------------------------------ */

export const OUTBOX_STATUSES: DictItem[] = [
  { label: '待推送', value: 'pending', type: 'warning' },
  { label: '推送中', value: 'processing', type: 'primary' },
  { label: '成功', value: 'success', type: 'success' },
  { label: '失败', value: 'failed', type: 'danger' }
]

/* ------------------------------ Store ------------------------------ */

export const useDictStore = defineStore('dict', () => {
  const maps = {
    enterpriseType: toMap(ENTERPRISE_TYPES),
    auditStatus: toMap(AUDIT_STATUSES),
    commonStatus: toMap(COMMON_STATUSES),
    userStatus: toMap(USER_STATUSES),
    productStatus: toMap(PRODUCT_STATUSES),
    productGrade: toMap(PRODUCT_GRADES),
    qualityStatus: toMap(QUALITY_STATUSES),
    productUnit: toMap(PRODUCT_UNITS),
    warehouseType: toMap(WAREHOUSE_TYPES),
    stockMoveType: toMap(STOCK_MOVE_TYPES),
    stockRefType: toMap(STOCK_REF_TYPES),
    inquiryStatus: toMap(INQUIRY_STATUSES),
    quotationStatus: toMap(QUOTATION_STATUSES),
    orderStatus: toMap(ORDER_STATUSES),
    orderType: toMap(ORDER_TYPES),
    contractStatus: toMap(CONTRACT_STATUSES),
    settleType: toMap(SETTLE_TYPES),
    payStatus: toMap(PAY_STATUSES),
    receiveStatus: toMap(RECEIVE_STATUSES),
    settlementStatus: toMap(SETTLEMENT_STATUSES),
    payMethod: toMap(PAY_METHODS),
    flowDirection: toMap(FLOW_DIRECTIONS),
    flowBizType: toMap(FLOW_BIZ_TYPES),
    flowPayStatus: toMap(FLOW_PAY_STATUSES),
    bizType: toMap(BIZ_TYPES),
    zoneType: toMap(ZONE_TYPES),
    stallStatus: toMap(STALL_STATUSES),
    feeCycle: toMap(FEE_CYCLES),
    parkContractStatus: toMap(PARK_CONTRACT_STATUSES),
    orgUnitType: toMap(ORG_UNIT_TYPES),
    traceStage: toMap(TRACE_STAGES),
    traceBatchStatus: toMap(TRACE_BATCH_STATUSES),
    outboxStatus: toMap(OUTBOX_STATUSES)
  }

  /** 取中文标签 */
  function label(group: keyof typeof maps, value?: string | number | null, fallback = '-'): string {
    if (value === null || value === undefined || value === '') return fallback
    const item = maps[group][String(value)]
    return item ? item.label : String(value)
  }

  /** 取 Element Plus tag 类型 */
  function tagType(
    group: keyof typeof maps,
    value?: string | number | null
  ): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
    if (value === null || value === undefined) return 'info'
    const item = maps[group][String(value)]
    return item?.type || 'info'
  }

  /** 取主题色（图表 / 指标卡） */
  function color(group: keyof typeof maps, value?: string | number | null): string {
    if (value === null || value === undefined) return '#909399'
    const item = maps[group][String(value)]
    return item?.color || '#909399'
  }

  /** 该组全部选项（下拉框） */
  function options(group: keyof typeof maps): DictItem[] {
    return Object.values(maps[group]) as DictItem[]
  }

  return { maps, label, tagType, color, options }
})
