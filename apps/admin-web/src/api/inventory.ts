/** 库存 /inventory —— docs/04 §2.6 */
import { http } from './request'
import type {
  InventoryAdjustParams,
  InventoryCheckParams,
  InventoryInParams,
  InventoryItem,
  InventoryOutParams,
  InventoryQuery,
  InventorySummaryItem,
  InventoryTransferParams,
  PageResult,
  StockMove,
  StockMoveQuery
} from './types'

const BASE = '/inventory'

/** GET /api/v1/inventory 权限 inventory:read */
export function listInventory(params: InventoryQuery): Promise<PageResult<InventoryItem>> {
  return http.get<PageResult<InventoryItem>>(BASE, params as Record<string, unknown>)
}

/** GET /api/v1/inventory/summary 权限 inventory:read —— 按商品汇总（总量/预占/可用） */
export function getInventorySummary(params: InventoryQuery): Promise<PageResult<InventorySummaryItem>> {
  return http.get<PageResult<InventorySummaryItem>>(`${BASE}/summary`, params as Record<string, unknown>)
}

/** POST /api/v1/inventory/in 权限 inventory:execute */
export function inventoryIn(data: InventoryInParams): Promise<StockMove | null> {
  return http.post<StockMove | null>(`${BASE}/in`, data)
}

/** POST /api/v1/inventory/out 权限 inventory:execute */
export function inventoryOut(data: InventoryOutParams): Promise<StockMove | null> {
  return http.post<StockMove | null>(`${BASE}/out`, data)
}

/** POST /api/v1/inventory/transfer 权限 inventory:execute */
export function inventoryTransfer(data: InventoryTransferParams): Promise<StockMove | null> {
  return http.post<StockMove | null>(`${BASE}/transfer`, data)
}

/** POST /api/v1/inventory/adjust 权限 inventory:execute —— 调整到目标值 */
export function inventoryAdjust(data: InventoryAdjustParams): Promise<StockMove | null> {
  return http.post<StockMove | null>(`${BASE}/adjust`, data)
}

/** POST /api/v1/inventory/check 权限 inventory:execute —— 盘点 */
export function inventoryCheck(data: InventoryCheckParams): Promise<StockMove[] | null> {
  return http.post<StockMove[] | null>(`${BASE}/check`, data)
}

/** GET /api/v1/inventory/moves 权限 inventory:read —— 库存流水 */
export function listStockMoves(params: StockMoveQuery): Promise<PageResult<StockMove>> {
  return http.get<PageResult<StockMove>>(`${BASE}/moves`, params as Record<string, unknown>)
}
