/** B2B 交易 /inquiries /quotations /orders /contracts —— docs/04 §2.7 */
import { http } from './request'
import type {
  Contract,
  ContractPayload,
  ContractQuery,
  ContractSignParams,
  Inquiry,
  InquiryPayload,
  InquiryQuery,
  Order,
  OrderCancelParams,
  OrderDeliverParams,
  OrderPayload,
  OrderQuery,
  OrderTimelineNode,
  PageResult,
  Quotation,
  QuotationPayload,
  QuotationQuery
} from './types'

/* ---------------- 询价单 ---------------- */

/** GET /api/v1/inquiries 权限 trade:read（role=buyer|supplier） */
export function listInquiries(params: InquiryQuery): Promise<PageResult<Inquiry>> {
  return http.get<PageResult<Inquiry>>('/inquiries', params as Record<string, unknown>)
}

/** POST /api/v1/inquiries 权限 trade:write */
export function createInquiry(data: InquiryPayload): Promise<Inquiry> {
  return http.post<Inquiry>('/inquiries', data)
}

/** GET /api/v1/inquiries/{id} 权限 trade:read（含报价列表） */
export function getInquiry(id: number): Promise<Inquiry> {
  return http.get<Inquiry>(`/inquiries/${id}`)
}

/** POST /api/v1/inquiries/{id}/submit 权限 trade:write */
export function submitInquiry(id: number): Promise<Inquiry> {
  return http.post<Inquiry>(`/inquiries/${id}/submit`)
}

/** POST /api/v1/inquiries/{id}/cancel 权限 trade:write */
export function cancelInquiry(id: number): Promise<Inquiry> {
  return http.post<Inquiry>(`/inquiries/${id}/cancel`)
}

/* ---------------- 报价单 ---------------- */

/** GET /api/v1/inquiries/{id}/quotations 权限 trade:read */
export function listInquiryQuotations(id: number): Promise<Quotation[]> {
  return http.get<Quotation[]>(`/inquiries/${id}/quotations`)
}

/** POST /api/v1/inquiries/{id}/quotations 权限 trade:write —— 供应商报价 */
export function createQuotation(inquiryId: number, data: QuotationPayload): Promise<Quotation> {
  return http.post<Quotation>(`/inquiries/${inquiryId}/quotations`, data)
}

/** POST /api/v1/quotations/{id}/accept 权限 trade:write —— 采购商接受 → 生成订单 */
export function acceptQuotation(id: number): Promise<Order> {
  return http.post<Order>(`/quotations/${id}/accept`)
}

/** POST /api/v1/quotations/{id}/reject 权限 trade:write */
export function rejectQuotation(id: number): Promise<Quotation> {
  return http.post<Quotation>(`/quotations/${id}/reject`)
}

/** GET /api/v1/quotations 权限 trade:read */
export function listQuotations(params: QuotationQuery): Promise<PageResult<Quotation>> {
  return http.get<PageResult<Quotation>>('/quotations', params as Record<string, unknown>)
}

/* ---------------- 订单 ---------------- */

/** GET /api/v1/orders 权限 trade:read（role/status/keyword/日期区间） */
export function listOrders(params: OrderQuery): Promise<PageResult<Order>> {
  return http.get<PageResult<Order>>('/orders', params as Record<string, unknown>)
}

/** POST /api/v1/orders 权限 trade:write —— 直接下单 */
export function createOrder(data: OrderPayload): Promise<Order> {
  return http.post<Order>('/orders', data)
}

/** GET /api/v1/orders/{id} 权限 trade:read（含明细、合同、流水、结算） */
export function getOrder(id: number): Promise<Order> {
  return http.get<Order>(`/orders/${id}`)
}

/** POST /api/v1/orders/{id}/confirm 权限 trade:write —— 供方确认（扣减库存 + 生成流水） */
export function confirmOrder(id: number): Promise<Order> {
  return http.post<Order>(`/orders/${id}/confirm`)
}

/** POST /api/v1/orders/{id}/deliver 权限 trade:write */
export function deliverOrder(id: number, data: OrderDeliverParams): Promise<Order> {
  return http.post<Order>(`/orders/${id}/deliver`, data)
}

/** POST /api/v1/orders/{id}/complete 权限 trade:write —— 完成（生成应收结算单） */
export function completeOrder(id: number): Promise<Order> {
  return http.post<Order>(`/orders/${id}/complete`)
}

/** POST /api/v1/orders/{id}/cancel 权限 trade:write */
export function cancelOrder(id: number, data: OrderCancelParams): Promise<Order> {
  return http.post<Order>(`/orders/${id}/cancel`, data)
}

/** GET /api/v1/orders/{id}/timeline 权限 trade:read —— 状态轨迹 */
export function getOrderTimeline(id: number): Promise<OrderTimelineNode[]> {
  return http.get<OrderTimelineNode[]>(`/orders/${id}/timeline`)
}

/* ---------------- 合同 ---------------- */

/** GET /api/v1/contracts 权限 trade:read */
export function listContracts(params: ContractQuery): Promise<PageResult<Contract>> {
  return http.get<PageResult<Contract>>('/contracts', params as Record<string, unknown>)
}

/** POST /api/v1/contracts 权限 trade:write —— 生成合同（可由订单生成） */
export function createContract(data: ContractPayload): Promise<Contract> {
  return http.post<Contract>('/contracts', data)
}

/** GET /api/v1/contracts/{id} 权限 trade:read */
export function getContract(id: number): Promise<Contract> {
  return http.get<Contract>(`/contracts/${id}`)
}

/** PUT /api/v1/contracts/{id} 权限 trade:write */
export function updateContract(id: number, data: Partial<ContractPayload>): Promise<Contract> {
  return http.put<Contract>(`/contracts/${id}`, data)
}

/** POST /api/v1/contracts/{id}/sign 权限 trade:write —— 双方签署后自动生效 */
export function signContract(id: number, data: ContractSignParams): Promise<Contract> {
  return http.post<Contract>(`/contracts/${id}/sign`, data)
}
