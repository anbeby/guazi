/** 结算与财务 /settlements /finance —— docs/04 §2.8 */
import { http } from './request'
import type {
  FlowQuery,
  PageResult,
  Settlement,
  SettlementPayload,
  SettlementPaymentParams,
  SettlementQuery,
  StatementResult,
  TransactionFlow
} from './types'

const SETTLEMENT_BASE = '/settlements'
const FINANCE_BASE = '/finance'

/** GET /api/v1/settlements 权限 settlement:read */
export function listSettlements(params: SettlementQuery): Promise<PageResult<Settlement>> {
  return http.get<PageResult<Settlement>>(SETTLEMENT_BASE, params as Record<string, unknown>)
}

/** GET /api/v1/settlements/{id} 权限 settlement:read（含明细） */
export function getSettlement(id: number): Promise<Settlement> {
  return http.get<Settlement>(`${SETTLEMENT_BASE}/${id}`)
}

/** POST /api/v1/settlements 权限 settlement:write —— 手工生成（按企业 + 期间归集已完成订单） */
export function createSettlement(data: SettlementPayload): Promise<Settlement> {
  return http.post<Settlement>(SETTLEMENT_BASE, data)
}

/** POST /api/v1/settlements/{id}/confirm 权限 settlement:write */
export function confirmSettlement(id: number): Promise<Settlement> {
  return http.post<Settlement>(`${SETTLEMENT_BASE}/${id}/confirm`)
}

/** POST /api/v1/settlements/{id}/payment 权限 settlement:write —— 登记回款 */
export function registerSettlementPayment(
  id: number,
  data: SettlementPaymentParams
): Promise<Settlement> {
  return http.post<Settlement>(`${SETTLEMENT_BASE}/${id}/payment`, data)
}

/** GET /api/v1/finance/flows 权限 settlement:read —— 交易流水 */
export function listFinanceFlows(params: FlowQuery): Promise<PageResult<TransactionFlow>> {
  return http.get<PageResult<TransactionFlow>>(`${FINANCE_BASE}/flows`, params as Record<string, unknown>)
}

/** GET /api/v1/finance/statement 权限 settlement:read —— 对账单 */
export function getFinanceStatement(params: {
  enterprise_id: number
  start_date: string
  end_date: string
}): Promise<StatementResult> {
  return http.get<StatementResult>(`${FINANCE_BASE}/statement`, params as unknown as Record<string, unknown>)
}
