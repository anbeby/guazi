/** 仓库与库位 /warehouses /locations —— docs/04 §2.6 */
import { http } from './request'
import type {
  PageResult,
  StorageLocation,
  StorageLocationPayload,
  Warehouse,
  WarehousePayload,
  WarehouseQuery
} from './types'

const WAREHOUSE_BASE = '/warehouses'
const LOCATION_BASE = '/locations'

/** GET /api/v1/warehouses 权限 inventory:read */
export function listWarehouses(params: WarehouseQuery): Promise<PageResult<Warehouse>> {
  return http.get<PageResult<Warehouse>>(WAREHOUSE_BASE, params as Record<string, unknown>)
}

/** POST /api/v1/warehouses 权限 inventory:write */
export function createWarehouse(data: WarehousePayload): Promise<Warehouse> {
  return http.post<Warehouse>(WAREHOUSE_BASE, data)
}

/** GET /api/v1/warehouses/{id} 权限 inventory:read */
export function getWarehouse(id: number): Promise<Warehouse> {
  return http.get<Warehouse>(`${WAREHOUSE_BASE}/${id}`)
}

/** PUT /api/v1/warehouses/{id} 权限 inventory:write */
export function updateWarehouse(id: number, data: Partial<WarehousePayload>): Promise<Warehouse> {
  return http.put<Warehouse>(`${WAREHOUSE_BASE}/${id}`, data)
}

/** DELETE /api/v1/warehouses/{id} 权限 inventory:write */
export function deleteWarehouse(id: number): Promise<null> {
  return http.delete<null>(`${WAREHOUSE_BASE}/${id}`)
}

/** GET /api/v1/warehouses/{id}/locations 权限 inventory:read */
export function listLocations(warehouseId: number): Promise<StorageLocation[]> {
  return http.get<StorageLocation[]>(`${WAREHOUSE_BASE}/${warehouseId}/locations`)
}

/** POST /api/v1/warehouses/{id}/locations 权限 inventory:write */
export function createLocation(
  warehouseId: number,
  data: StorageLocationPayload
): Promise<StorageLocation> {
  return http.post<StorageLocation>(`${WAREHOUSE_BASE}/${warehouseId}/locations`, data)
}

/** PUT /api/v1/locations/{id} 权限 inventory:write */
export function updateLocation(
  id: number,
  data: Partial<StorageLocationPayload>
): Promise<StorageLocation> {
  return http.put<StorageLocation>(`${LOCATION_BASE}/${id}`, data)
}

/** DELETE /api/v1/locations/{id} 权限 inventory:write */
export function deleteLocation(id: number): Promise<null> {
  return http.delete<null>(`${LOCATION_BASE}/${id}`)
}
