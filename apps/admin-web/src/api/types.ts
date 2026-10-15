/**
 * 全量 TS 类型定义 —— 与 docs/04-接口规范.md、docs/03-数据模型设计.md 严格对齐。
 *
 * 约定：
 *  - 所有金额字段后端返回 numeric(18,2) 序列化后的字符串，前端统一按 string 接收，展示时用 utils/format 转换；
 *  - 所有数量字段为 numeric(18,3) 序列化后的字符串；
 *  - 时间为 ISO8601 字符串（timestamptz），日期为 YYYY-MM-DD。
 */

/* ------------------------------------------------------------------ *
 * 1. 通用信封 / 分页
 * ------------------------------------------------------------------ */

export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  request_id?: string
}

/** 分页响应 data */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** 分页请求参数 */
export interface PageQuery {
  page?: number
  page_size?: number
  keyword?: string
  order_by?: string
}

/** 日期区间查询 */
export interface DateRangeQuery {
  start_date?: string
  end_date?: string
}

/** 通用下拉选项 */
export interface OptionItem<T = string> {
  label: string
  value: T
}

/* ------------------------------------------------------------------ *
 * 2. 认证与权限
 * ------------------------------------------------------------------ */

export interface LoginParams {
  username: string
  password: string
}

export interface UserProfile {
  id: number
  username: string
  full_name?: string
  phone?: string
  email?: string
  enterprise_id?: number | null
  enterprise_name?: string | null
  org_id?: number | null
  org_name?: string | null
  is_superuser?: boolean
  status?: UserStatus
  roles: string[]
  permissions: string[]
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserProfile
}

export interface RefreshResult {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface ChangePasswordParams {
  old_password: string
  new_password: string
}

/* ------------------------------------------------------------------ *
 * 3. 用户 / 角色 / 权限 / 组织
 * ------------------------------------------------------------------ */

export type UserStatus = 'active' | 'disabled' | 'locked'

export interface SysUser {
  id: number
  username: string
  full_name?: string
  phone?: string
  email?: string
  org_id?: number | null
  org_name?: string | null
  enterprise_id?: number | null
  enterprise_name?: string | null
  is_superuser?: boolean
  status: UserStatus
  role_ids?: number[]
  roles?: string[]
  last_login_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface UserQuery extends PageQuery {
  status?: UserStatus | ''
  enterprise_id?: number | null
  org_id?: number | null
}

export interface UserPayload {
  username: string
  password?: string
  full_name?: string
  phone?: string
  email?: string
  org_id?: number | null
  enterprise_id?: number | null
  status?: UserStatus
  role_ids?: number[]
}

export interface ResetPasswordParams {
  new_password: string
}

export interface AssignRolesParams {
  role_ids: number[]
}

export interface Role {
  id: number
  code: string
  name: string
  description?: string | null
  is_system?: boolean
  permission_ids?: number[]
  created_at?: string
}

export interface RoleQuery extends PageQuery {
  code?: string
}

export interface RolePayload {
  code: string
  name: string
  description?: string
}

export interface Permission {
  id: number
  code: string
  name: string
  module: string
  description?: string | null
}

/** GET /permissions 按模块分组 */
export interface PermissionGroup {
  module: string
  module_name?: string
  permissions: Permission[]
}

export type OrgUnitType = 'platform' | 'park' | 'enterprise'
export type OrgUnitStatus = 'active' | 'disabled'

export interface OrgUnit {
  id: number
  code: string
  name: string
  unit_type: OrgUnitType
  parent_id?: number | null
  park_id?: number | null
  region?: string | null
  address?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  status: OrgUnitStatus
  sort?: number
  children?: OrgUnit[]
  created_at?: string
  updated_at?: string
}

export interface OrgUnitPayload {
  code: string
  name: string
  unit_type: OrgUnitType
  parent_id?: number | null
  park_id?: number | null
  region?: string
  address?: string
  contact_name?: string
  contact_phone?: string
  status?: OrgUnitStatus
  sort?: number
}

/* ------------------------------------------------------------------ *
 * 4. 企业 / 商户
 * ------------------------------------------------------------------ */

export type EnterpriseType = 'merchant' | 'supplier' | 'buyer' | 'platform'
export type AuditStatus = 'pending' | 'approved' | 'rejected'
export type CommonStatus = 'active' | 'disabled'

export interface Enterprise {
  id: number
  code: string
  name: string
  image_url?: string | null
  unified_social_credit_code?: string
  enterprise_type: EnterpriseType
  legal_person?: string
  registered_capital?: string
  business_scope?: string
  profile?: string
  qualifications?: string[]
  contact_name?: string
  contact_phone?: string
  email?: string
  region?: string
  address?: string
  org_id?: number | null
  park_id?: number | null
  park_name?: string | null
  stall_id?: number | null
  stall_name?: string | null
  audit_status: AuditStatus
  audit_remark?: string | null
  status: CommonStatus
  settle_bank?: string
  settle_account_name?: string
  settle_account_no?: string
  odoo_partner_id?: number | null
  remark?: string
  created_at?: string
  updated_at?: string
}

export interface EnterpriseQuery extends PageQuery {
  enterprise_type?: EnterpriseType | ''
  audit_status?: AuditStatus | ''
  status?: CommonStatus | ''
  park_id?: number | null
}

export interface EnterprisePayload {
  code?: string
  name: string
  unified_social_credit_code?: string
  enterprise_type: EnterpriseType
  legal_person?: string
  registered_capital?: string | number
  business_scope?: string
  profile?: string
  qualifications?: string[]
  contact_name?: string
  contact_phone?: string
  email?: string
  region?: string
  address?: string
  park_id?: number | null
  stall_id?: number | null
  settle_bank?: string
  settle_account_name?: string
  settle_account_no?: string
  remark?: string
}

export interface EnterpriseAuditParams {
  approved: boolean
  remark?: string
}

export interface EnterpriseStats {
  enterprise_id: number
  product_count: number
  published_product_count?: number
  inventory_quantity: string
  inventory_value?: string
  order_count: number
  order_amount: string
}

/* ------------------------------------------------------------------ *
 * 5. 商品中心
 * ------------------------------------------------------------------ */

export interface Category {
  id: number
  code: string
  name: string
  parent_id?: number | null
  level?: number
  sort?: number
  status?: CommonStatus
  description?: string | null
  product_count?: number
  children?: Category[]
}

export interface CategoryPayload {
  code: string
  name: string
  parent_id?: number | null
  sort?: number
  status?: CommonStatus
  description?: string
}

export type ProductStatus = 'draft' | 'published' | 'offline' | 'rejected'
/** 等级：特级 / 一级 / 二级 / 统货 */
export type ProductGrade = 'special' | 'first' | 'second' | 'mixed'
export type QualityStatus = 'pending' | 'qualified' | 'unqualified'
export type ProductUnit = 'ton' | 'kg' | 'bag'

export interface Product {
  id: number
  code: string
  name: string
  category_id: number
  category_name?: string
  enterprise_id: number
  enterprise_name?: string
  spec?: string
  grade?: ProductGrade | string
  origin?: string
  harvest_year?: string
  package?: string
  unit: ProductUnit
  price: string
  currency?: string
  min_order_qty?: string
  stock_warn_qty?: string
  supply_quantity?: string | number
  supply_period?: string
  pricing_mode?: 'listed' | 'negotiable' | 'inquiry'
  supply_status?: 'active' | 'paused' | 'completed'
  allow_inquiry?: boolean
  allow_bulk_purchase?: boolean
  main_image?: string | null
  images?: string[] | null
  test_report_url?: string | null
  quality_status?: QualityStatus
  trace_enabled?: boolean
  status: ProductStatus
  audit_status: AuditStatus
  audit_remark?: string | null
  description?: string | null
  total_quantity?: string
  available_quantity?: string
  created_at?: string
  updated_at?: string
}

export interface ProductQuery extends PageQuery {
  category_id?: number | null
  enterprise_id?: number | null
  status?: ProductStatus | ''
  grade?: ProductGrade | ''
  origin?: string
  harvest_year?: string
}

export interface ProductPayload {
  name: string
  category_id: number
  enterprise_id?: number | null
  code?: string
  spec?: string
  grade?: ProductGrade | ''
  origin?: string
  harvest_year?: string
  package?: string
  unit?: ProductUnit
  price?: string | number
  currency?: string
  min_order_qty?: string | number
  stock_warn_qty?: string | number
  supply_quantity?: string | number
  supply_period?: string
  pricing_mode?: 'listed' | 'negotiable' | 'inquiry'
  supply_status?: 'active' | 'paused' | 'completed'
  allow_inquiry?: boolean
  allow_bulk_purchase?: boolean
  main_image?: string
  images?: string[]
  test_report_url?: string
  trace_enabled?: boolean
  description?: string
}

export interface ProductAuditParams {
  approved: boolean
  remark?: string
}

/** GET /products/{id}/inventory 单商品各仓库库存 */
export interface ProductInventoryItem {
  warehouse_id: number
  warehouse_name?: string
  location_id?: number | null
  location_name?: string | null
  batch_no?: string
  quantity: string
  locked_quantity: string
  available_quantity?: string
  unit_cost?: string
  production_date?: string | null
  quality_status?: QualityStatus
}

/* ------------------------------------------------------------------ *
 * 6. 仓储与库存
 * ------------------------------------------------------------------ */

export type WarehouseType = 'own' | 'bonded' | 'temp'

export interface Warehouse {
  id: number
  code: string
  name: string
  enterprise_id: number
  enterprise_name?: string
  park_id?: number | null
  park_name?: string | null
  address?: string
  warehouse_type: WarehouseType
  contact_name?: string
  contact_phone?: string
  status: CommonStatus
  location_count?: number
  created_at?: string
}

export interface WarehousePayload {
  code: string
  name: string
  enterprise_id?: number | null
  park_id?: number | null
  address?: string
  warehouse_type?: WarehouseType
  contact_name?: string
  contact_phone?: string
  status?: CommonStatus
}

export interface WarehouseQuery extends PageQuery {
  enterprise_id?: number | null
  warehouse_type?: WarehouseType | ''
  status?: CommonStatus | ''
}

export interface StorageLocation {
  id: number
  warehouse_id: number
  warehouse_name?: string
  code: string
  name: string
  zone?: string
  capacity?: string
  status: CommonStatus
}

export interface StorageLocationPayload {
  code: string
  name: string
  zone?: string
  capacity?: string | number
  status?: CommonStatus
}

export type StockMoveType = 'in' | 'out' | 'transfer' | 'adjust' | 'check'

export interface InventoryItem {
  id: number
  product_id: number
  product_name?: string
  product_code?: string
  warehouse_id: number
  warehouse_name?: string
  location_id?: number | null
  location_name?: string | null
  batch_no: string
  quantity: string
  locked_quantity: string
  available_quantity?: string
  unit_cost?: string
  production_date?: string | null
  expiry_date?: string | null
  quality_status?: QualityStatus
  unit?: ProductUnit
  updated_at?: string
}

export interface InventoryQuery extends PageQuery {
  product_id?: number | null
  warehouse_id?: number | null
  batch_no?: string
}

/** GET /inventory/summary 按商品汇总 */
export interface InventorySummaryItem {
  product_id: number
  product_name?: string
  product_code?: string
  unit?: ProductUnit
  quantity: string
  locked_quantity: string
  available_quantity: string
  unit_cost?: string
  amount?: string
}

export interface InventoryInParams {
  product_id: number
  warehouse_id: number
  location_id?: number | null
  batch_no?: string
  quantity: string | number
  unit_cost?: string | number
  production_date?: string
  expiry_date?: string
  quality_status?: QualityStatus
  remark?: string
}

export interface InventoryOutParams {
  product_id: number
  warehouse_id: number
  location_id?: number | null
  batch_no?: string
  quantity: string | number
  unit_cost?: string | number
  ref_type?: string
  ref_no?: string
  remark?: string
}

export interface InventoryTransferParams {
  product_id: number
  warehouse_id: number
  location_id?: number | null
  to_warehouse_id: number
  to_location_id?: number | null
  batch_no?: string
  quantity: string | number
  remark?: string
}

/** 调整：目标值语义 */
export interface InventoryAdjustParams {
  product_id: number
  warehouse_id: number
  location_id?: number | null
  batch_no?: string
  quantity: string | number
  unit_cost?: string | number
  remark?: string
}

export interface InventoryCheckItem {
  product_id: number
  warehouse_id: number
  location_id?: number | null
  batch_no?: string
  quantity: string | number
  remark?: string
}

export interface InventoryCheckParams {
  items: InventoryCheckItem[]
  remark?: string
}

export interface StockMove {
  id: number
  move_no: string
  move_type: StockMoveType
  product_id: number
  product_name?: string
  warehouse_id: number
  warehouse_name?: string
  location_id?: number | null
  to_warehouse_id?: number | null
  to_warehouse_name?: string | null
  to_location_id?: number | null
  quantity: string
  unit_cost?: string
  batch_no?: string
  ref_type?: string
  ref_id?: number | null
  ref_no?: string | null
  operator_id?: number | null
  operator_name?: string | null
  remark?: string | null
  created_at: string
}

export interface StockMoveQuery extends PageQuery {
  product_id?: number | null
  warehouse_id?: number | null
  move_type?: StockMoveType | ''
  batch_no?: string
  start_date?: string
  end_date?: string
}

/* ------------------------------------------------------------------ *
 * 7. B2B 交易：询价 / 报价 / 订单 / 合同
 * ------------------------------------------------------------------ */

export type InquiryStatus =
  | 'draft'
  | 'submitted'
  | 'quoted'
  | 'confirmed'
  | 'closed'
  | 'cancelled'

export interface Inquiry {
  id: number
  inquiry_no: string
  buyer_enterprise_id: number
  buyer_enterprise_name?: string
  supplier_enterprise_id?: number | null
  supplier_enterprise_name?: string | null
  product_id: number
  product_name?: string
  product_code?: string
  quantity: string
  unit: string
  expect_price?: string | null
  expect_delivery_date?: string | null
  delivery_address?: string | null
  remark?: string | null
  status: InquiryStatus
  quoted_count: number
  created_by?: number | null
  created_at: string
  updated_at?: string
  quotations?: Quotation[]
}

export interface InquiryQuery extends PageQuery {
  /** buyer = 我发出的询价；supplier = 待我报价 */
  role?: 'buyer' | 'supplier'
  status?: InquiryStatus | ''
  start_date?: string
  end_date?: string
}

export interface InquiryPayload {
  product_id: number
  quantity: string | number
  unit?: string
  expect_price?: string | number
  expect_delivery_date?: string
  delivery_address?: string
  supplier_enterprise_id?: number | null
  remark?: string
}

export type QuotationStatus = 'submitted' | 'accepted' | 'rejected' | 'expired'

export interface Quotation {
  id: number
  quotation_no: string
  inquiry_id: number
  inquiry_no?: string
  supplier_enterprise_id: number
  supplier_enterprise_name?: string
  product_id: number
  product_name?: string
  quantity: string
  unit: string
  unit_price: string
  amount: string
  tax_rate?: string | null
  valid_until?: string | null
  delivery_date?: string | null
  payment_terms?: string | null
  remark?: string | null
  status: QuotationStatus
  created_by?: number | null
  created_at: string
}

export interface QuotationQuery extends PageQuery {
  inquiry_id?: number | null
  status?: QuotationStatus | ''
}

export interface QuotationPayload {
  quantity?: string | number
  unit_price: string | number
  tax_rate?: string | number
  valid_until?: string
  delivery_date?: string
  payment_terms?: string
  remark?: string
}

export type OrderStatus =
  | 'draft'
  | 'pending_confirm'
  | 'confirmed'
  | 'delivering'
  | 'completed'
  | 'settled'
  | 'cancelled'

export type OrderType = 'sales' | 'purchase'

export interface OrderItem {
  id: number
  order_id: number
  product_id: number
  product_name?: string
  product_code?: string
  warehouse_id?: number | null
  warehouse_name?: string | null
  location_id?: number | null
  batch_no?: string | null
  quantity: string
  delivered_quantity: string
  unit: string
  unit_price: string
  amount: string
  tax_rate?: string | null
}

export interface Order {
  id: number
  order_no: string
  order_type?: OrderType
  inquiry_id?: number | null
  quotation_id?: number | null
  buyer_enterprise_id: number
  buyer_enterprise_name?: string
  supplier_enterprise_id: number
  supplier_enterprise_name?: string
  amount: string
  tax_amount?: string
  total_amount: string
  currency?: string
  delivery_date?: string | null
  delivery_address?: string | null
  contract_id?: number | null
  stock_deducted?: boolean
  status: OrderStatus
  remark?: string | null
  created_by?: number | null
  confirmed_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at?: string
  items?: OrderItem[]
}

export interface OrderQuery extends PageQuery {
  /** buyer = 我作为买方；supplier = 我作为卖方 */
  role?: 'buyer' | 'supplier'
  status?: OrderStatus | ''
  start_date?: string
  end_date?: string
}

export interface OrderItemPayload {
  product_id: number
  warehouse_id?: number | null
  location_id?: number | null
  batch_no?: string
  quantity: string | number
  unit?: string
  unit_price: string | number
  tax_rate?: string | number
}

export interface OrderPayload {
  buyer_enterprise_id?: number | null
  supplier_enterprise_id: number
  delivery_date?: string
  delivery_address?: string
  remark?: string
  items: OrderItemPayload[]
}

export interface OrderDeliverItem {
  item_id: number
  delivered_quantity: string | number
}

export interface OrderDeliverParams {
  items: OrderDeliverItem[]
  logistics?: {
    company?: string
    tracking_no?: string
  }
}

export interface OrderCancelParams {
  reason: string
}

export interface OrderTimelineNode {
  id?: number
  status?: OrderStatus | string
  action?: string
  title?: string
  description?: string
  operator?: string
  operator_name?: string
  created_at: string
}

export type ContractStatus =
  | 'draft'
  | 'pending_sign'
  | 'signed'
  | 'effective'
  | 'terminated'
  | 'expired'

export interface Contract {
  id: number
  contract_no: string
  title: string
  order_id?: number | null
  order_no?: string | null
  buyer_enterprise_id: number
  buyer_enterprise_name?: string
  supplier_enterprise_id: number
  supplier_enterprise_name?: string
  park_id?: number | null
  amount: string
  sign_date?: string | null
  start_date?: string | null
  end_date?: string | null
  file_url?: string | null
  status: ContractStatus
  signed_by_buyer: boolean
  signed_by_supplier: boolean
  buyer_signed_at?: string | null
  supplier_signed_at?: string | null
  remark?: string | null
  created_at?: string
}

export interface ContractQuery extends PageQuery {
  status?: ContractStatus | ''
  order_id?: number | null
}

export interface ContractPayload {
  title: string
  order_id?: number | null
  buyer_enterprise_id?: number | null
  supplier_enterprise_id?: number | null
  amount?: string | number
  sign_date?: string
  start_date?: string
  end_date?: string
  file_url?: string
  remark?: string
}

export interface ContractSignParams {
  party: 'buyer' | 'supplier'
}

/* ------------------------------------------------------------------ *
 * 8. 结算与财务
 * ------------------------------------------------------------------ */

export type SettleType = 'receivable' | 'payable' | 'park_fee'
export type PayStatus = 'unpaid' | 'partial' | 'paid'
export type ReceiveStatus = 'unconfirmed' | 'confirmed'
export type SettlementStatus = 'pending' | 'confirmed' | 'settled' | 'cancelled'

export interface SettlementLine {
  id: number
  settlement_id: number
  order_id?: number | null
  order_no?: string | null
  biz_type: 'order' | 'park_fee' | 'service_fee'
  biz_no?: string | null
  amount: string
  fee_rate?: string | null
  remark?: string | null
}

export interface Settlement {
  id: number
  settlement_no: string
  enterprise_id: number
  enterprise_name?: string
  settle_type: SettleType
  period_start: string
  period_end: string
  order_amount: string
  fee_amount: string
  settle_amount: string
  settled_amount: string
  pay_status: PayStatus
  receive_status: ReceiveStatus
  status: SettlementStatus
  remark?: string | null
  created_at: string
  confirmed_at?: string | null
  lines?: SettlementLine[]
}

export interface SettlementQuery extends PageQuery {
  enterprise_id?: number | null
  settle_type?: SettleType | ''
  status?: SettlementStatus | ''
  pay_status?: PayStatus | ''
  start_date?: string
  end_date?: string
}

export interface SettlementPayload {
  enterprise_id: number
  settle_type: SettleType
  period_start: string
  period_end: string
  remark?: string
}

export interface SettlementPaymentParams {
  amount: string | number
  pay_method: PayMethod
  trade_no?: string
  remark?: string
}

export type FlowDirection = 'in' | 'out'
export type FlowBizType = 'order_payment' | 'service_fee' | 'refund' | 'deposit'
export type PayMethod = 'bank_transfer' | 'offline' | 'other'
export type FlowPayStatus = 'pending' | 'success' | 'failed'

export interface TransactionFlow {
  id: number
  flow_no: string
  order_id?: number | null
  order_no?: string | null
  settlement_id?: number | null
  settlement_no?: string | null
  enterprise_id: number
  enterprise_name?: string
  counterparty_enterprise_id?: number | null
  counterparty_enterprise_name?: string | null
  direction: FlowDirection
  biz_type: FlowBizType
  amount: string
  pay_method?: PayMethod | null
  pay_status: FlowPayStatus
  receive_status?: ReceiveStatus
  trade_no?: string | null
  paid_at?: string | null
  remark?: string | null
  created_at: string
}

export interface FlowQuery extends PageQuery {
  enterprise_id?: number | null
  direction?: FlowDirection | ''
  pay_status?: FlowPayStatus | ''
  biz_type?: FlowBizType | ''
  start_date?: string
  end_date?: string
}

/** GET /finance/statement 对账单 */
export interface StatementSummary {
  enterprise_id: number
  enterprise_name?: string
  start_date: string
  end_date: string
  order_count?: number
  order_amount?: string
  receivable_amount?: string
  payable_amount?: string
  received_amount?: string
  paid_amount?: string
  unreceived_amount?: string
  service_fee_amount?: string
}

export interface StatementResult {
  summary: StatementSummary
  flows: TransactionFlow[]
  settlements?: Settlement[]
}

/* ------------------------------------------------------------------ *
 * 9. 园区
 * ------------------------------------------------------------------ */

export interface Park {
  id: number
  code: string
  name: string
  region?: string
  address?: string
  area_total?: string
  contact_name?: string
  contact_phone?: string
  status: CommonStatus
  description?: string | null
  zone_count?: number
  stall_count?: number
  created_at?: string
  updated_at?: string
}

export interface ParkPayload {
  code: string
  name: string
  region?: string
  address?: string
  area_total?: string | number
  contact_name?: string
  contact_phone?: string
  status?: CommonStatus
  description?: string
}

export interface ParkQuery extends PageQuery {
  status?: CommonStatus | ''
  region?: string
}

export type ZoneType = 'trade' | 'processing' | 'logistics' | 'service'

export interface ParkZone {
  id: number
  park_id: number
  park_name?: string
  code: string
  name: string
  zone_type: ZoneType
  area?: string
  sort?: number
  status: CommonStatus
}

export interface ParkZonePayload {
  code: string
  name: string
  zone_type: ZoneType
  area?: string | number
  sort?: number
  status?: CommonStatus
}

/** free 空闲 / rented 已租 / reserved 预留 / maintenance 维护 */
export type StallStatus = 'free' | 'rented' | 'reserved' | 'maintenance'

export interface Stall {
  id: number
  park_id: number
  park_name?: string
  zone_id?: number | null
  zone_name?: string | null
  code: string
  name: string
  area?: string
  monthly_fee?: string
  status: StallStatus
  enterprise_id?: number | null
  enterprise_name?: string | null
  remark?: string | null
}

export interface StallQuery extends PageQuery {
  park_id?: number | null
  zone_id?: number | null
  status?: StallStatus | ''
}

export interface StallPayload {
  park_id: number
  zone_id?: number | null
  code: string
  name: string
  area?: string | number
  monthly_fee?: string | number
  status?: StallStatus
  remark?: string
}

export interface StallAssignParams {
  enterprise_id: number | null
}

export type FeeCycle = 'month' | 'quarter' | 'year'
export type ParkContractStatus = 'draft' | 'effective' | 'expired' | 'terminated'

export interface ParkContract {
  id: number
  contract_no: string
  park_id: number
  park_name?: string
  stall_id: number
  stall_name?: string
  enterprise_id: number
  enterprise_name?: string
  start_date: string
  end_date: string
  rent_amount: string
  deposit_amount?: string
  fee_cycle: FeeCycle
  status: ParkContractStatus
  signed_at?: string | null
  file_url?: string | null
  remark?: string | null
}

export interface ParkContractQuery extends PageQuery {
  park_id?: number | null
  enterprise_id?: number | null
  status?: ParkContractStatus | ''
}

export interface ParkContractPayload {
  contract_no?: string
  park_id: number
  stall_id: number
  enterprise_id: number
  start_date: string
  end_date: string
  rent_amount: string | number
  deposit_amount?: string | number
  fee_cycle?: FeeCycle
  file_url?: string
  remark?: string
}

/* ------------------------------------------------------------------ *
 * 10. 溯源
 * ------------------------------------------------------------------ */

export type TraceStage = 'planting' | 'processing' | 'warehouse' | 'trade' | 'sale'
export type TraceBatchStatus = 'active' | 'closed'

export interface TraceEvent {
  id: number
  batch_id: number
  stage: TraceStage
  title: string
  description?: string | null
  occurred_at: string
  location?: string | null
  operator?: string | null
  evidence_url?: string | null
  created_at?: string
}

export interface TraceBatch {
  id: number
  batch_no: string
  qr_code?: string
  product_id: number
  product_name?: string
  product_code?: string
  enterprise_id: number
  enterprise_name?: string
  origin_base?: string | null
  origin_region?: string | null
  plant_date?: string | null
  harvest_date?: string | null
  process_enterprise?: string | null
  process_date?: string | null
  warehouse_id?: number | null
  warehouse_name?: string | null
  test_report_url?: string | null
  quality_status?: QualityStatus
  status: TraceBatchStatus
  created_at?: string
  events?: TraceEvent[]
}

export interface TraceBatchQuery extends PageQuery {
  product_id?: number | null
  enterprise_id?: number | null
  status?: TraceBatchStatus | ''
}

export interface TraceBatchPayload {
  batch_no?: string
  product_id: number
  origin_base?: string
  origin_region?: string
  plant_date?: string
  harvest_date?: string
  process_enterprise?: string
  process_date?: string
  warehouse_id?: number | null
  test_report_url?: string
  quality_status?: QualityStatus
}

export interface TraceEventPayload {
  stage: TraceStage
  title: string
  description?: string
  occurred_at: string
  location?: string
  operator?: string
  evidence_url?: string
}

/** GET /trace/public/{batch_no} 公开扫码视图 */
export interface TracePublicView {
  batch_no: string
  product_name?: string
  spec?: string
  grade?: string
  origin_region?: string
  origin_base?: string
  enterprise_name?: string
  harvest_date?: string
  quality_status?: QualityStatus
  test_report_url?: string | null
  events: TraceEvent[]
}

/* ------------------------------------------------------------------ *
 * 11. 数据驾驶舱
 * ------------------------------------------------------------------ */

export interface DashboardOverview {
  enterprise_count: number
  merchant_count: number
  supplier_count: number
  buyer_count: number
  product_count: number
  published_product_count: number
  inventory_quantity: string
  inventory_value: string
  inquiry_count: number
  order_count: number
  order_amount: string
  today_order_count: number
  today_order_amount: string
  park_count: number
  stall_count: number
  stall_rented: number
  stall_rented_rate: number
  pending_audit_enterprise: number
  pending_audit_product: number
}

export interface DashboardTrendPoint {
  date: string
  order_count?: number
  order_amount?: string
  quantity?: string
}

export interface DashboardPricePoint {
  date: string
  avg_price?: string
  category_id?: number
  category_name?: string
}

export interface DashboardIndustryItem {
  name: string
  value: string | number
  count?: number
  amount?: string
}

export interface DashboardIndustry {
  by_category?: DashboardIndustryItem[]
  by_grade?: DashboardIndustryItem[]
  by_origin?: DashboardIndustryItem[]
}

/* ------------------------------------------------------------------ *
 * 12. 文件与系统
 * ------------------------------------------------------------------ */

export interface FileUploadResult {
  file_key: string
  url: string
  size: number
  original_name?: string
}

export interface SysFile {
  id: number
  file_key: string
  bucket?: string
  original_name: string
  object_name?: string
  content_type?: string
  size: number
  biz_type?: string | null
  biz_id?: number | null
  uploader_id?: number | null
  storage?: 'local' | 'minio'
  url?: string
  created_at?: string
}

export interface FileQuery extends PageQuery {
  biz_type?: string
}

export interface SystemInfo {
  version: string
  environment: string
  middlewares?: Record<string, string>
  database?: string
  redis?: string
  minio?: string
  elasticsearch?: string
  odoo?: string
}

export type OutboxStatus = 'pending' | 'processing' | 'success' | 'failed'

export interface OutboxEvent {
  id: number
  event_type: string
  aggregate_type: string
  aggregate_id: number
  payload?: Record<string, unknown>
  status: OutboxStatus
  retry_count: number
  next_retry_at?: string | null
  last_error?: string | null
  created_at: string
  processed_at?: string | null
}

export interface OutboxQuery extends PageQuery {
  status?: OutboxStatus | ''
  event_type?: string
}
