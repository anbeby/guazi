/** 数据驾驶舱 /dashboard —— docs/04 §2.10，权限 data:read */
import { http } from './request'
import type {
  DashboardIndustry,
  DashboardOverview,
  DashboardPricePoint,
  DashboardTrendPoint
} from './types'

const BASE = '/dashboard'

interface TrendResponse {
  dates: string[]
  order_count: number[]
  order_amount: number[]
  order_quantity: number[]
}

interface PriceTrendResponse {
  dates: string[]
  avg_price: number[]
}

interface IndustryResponseItem {
  name: string
  trade_amount: number
}

interface IndustryResponse {
  by_category: IndustryResponseItem[]
  by_grade: IndustryResponseItem[]
  by_origin: IndustryResponseItem[]
}

/** GET /api/v1/dashboard/overview —— 核心指标卡片 */
export function getOverview(): Promise<DashboardOverview> {
  return http.get<DashboardOverview>(`${BASE}/overview`)
}

/** GET /api/v1/dashboard/trend?days=30 —— 交易趋势（金额/单量/吨数） */
export async function getTrend(days = 30): Promise<DashboardTrendPoint[]> {
  const data = await http.get<TrendResponse>(`${BASE}/trend`, { days })
  return data.dates.map((day, index) => ({
    date: day,
    order_count: data.order_count[index] ?? 0,
    order_amount: String(data.order_amount[index] ?? 0),
    quantity: String(data.order_quantity[index] ?? 0)
  }))
}

/** GET /api/v1/dashboard/price-trend?days=30&category_id= —— 价格趋势（成交均价） */
export async function getPriceTrend(days = 30, categoryId?: number | null): Promise<DashboardPricePoint[]> {
  const data = await http.get<PriceTrendResponse>(`${BASE}/price-trend`, {
    days,
    category_id: categoryId ?? undefined
  })
  return data.dates.map((day, index) => ({ date: day, avg_price: String(data.avg_price[index] ?? 0) }))
}

/** GET /api/v1/dashboard/industry —— 产业分析（按品类/等级/产地） */
export async function getIndustry(): Promise<DashboardIndustry> {
  const data = await http.get<IndustryResponse>(`${BASE}/industry`)
  const toChartItems = (items: IndustryResponseItem[]) =>
    items.map((item) => ({ name: item.name, value: item.trade_amount }))
  return {
    by_category: toChartItems(data.by_category),
    by_grade: toChartItems(data.by_grade),
    by_origin: toChartItems(data.by_origin)
  }
}
