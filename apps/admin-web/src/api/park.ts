/** 园区与档口 /parks /zones /stalls /park-contracts —— docs/04 §2.3 */
import { http } from './request'
import type {
  PageResult,
  Park,
  ParkContract,
  ParkContractPayload,
  ParkContractQuery,
  ParkPayload,
  ParkQuery,
  ParkZone,
  ParkZonePayload,
  Stall,
  StallAssignParams,
  StallPayload,
  StallQuery
} from './types'

const PARK_BASE = '/parks'
const ZONE_BASE = '/zones'
const STALL_BASE = '/stalls'
const PARK_CONTRACT_BASE = '/park-contracts'

/* ---------------- 园区 ---------------- */

/** GET /api/v1/parks 权限 park:read */
export function listParks(params: ParkQuery): Promise<PageResult<Park>> {
  return http.get<PageResult<Park>>(PARK_BASE, params as Record<string, unknown>)
}

/** POST /api/v1/parks 权限 park:write */
export function createPark(data: ParkPayload): Promise<Park> {
  return http.post<Park>(PARK_BASE, data)
}

/** GET /api/v1/parks/{id} 权限 park:read */
export function getPark(id: number): Promise<Park> {
  return http.get<Park>(`${PARK_BASE}/${id}`)
}

/** PUT /api/v1/parks/{id} 权限 park:write */
export function updatePark(id: number, data: Partial<ParkPayload>): Promise<Park> {
  return http.put<Park>(`${PARK_BASE}/${id}`, data)
}

/** DELETE /api/v1/parks/{id} 权限 park:write */
export function deletePark(id: number): Promise<null> {
  return http.delete<null>(`${PARK_BASE}/${id}`)
}

/* ---------------- 区域 ---------------- */

/** GET /api/v1/parks/{id}/zones 权限 park:read */
export function listParkZones(parkId: number): Promise<ParkZone[]> {
  return http.get<ParkZone[]>(`${PARK_BASE}/${parkId}/zones`)
}

/** POST /api/v1/parks/{id}/zones 权限 park:write */
export function createParkZone(parkId: number, data: ParkZonePayload): Promise<ParkZone> {
  return http.post<ParkZone>(`${PARK_BASE}/${parkId}/zones`, data)
}

/** PUT /api/v1/zones/{id} 权限 park:write */
export function updateParkZone(id: number, data: Partial<ParkZonePayload>): Promise<ParkZone> {
  return http.put<ParkZone>(`${ZONE_BASE}/${id}`, data)
}

/** DELETE /api/v1/zones/{id} 权限 park:write */
export function deleteParkZone(id: number): Promise<null> {
  return http.delete<null>(`${ZONE_BASE}/${id}`)
}

/* ---------------- 档口 ---------------- */

/** GET /api/v1/stalls 权限 park:read */
export function listStalls(params: StallQuery): Promise<PageResult<Stall>> {
  return http.get<PageResult<Stall>>(STALL_BASE, params as Record<string, unknown>)
}

/** POST /api/v1/stalls 权限 park:write */
export function createStall(data: StallPayload): Promise<Stall> {
  return http.post<Stall>(STALL_BASE, data)
}

/** GET /api/v1/stalls/{id} 权限 park:read */
export function getStall(id: number): Promise<Stall> {
  return http.get<Stall>(`${STALL_BASE}/${id}`)
}

/** PUT /api/v1/stalls/{id} 权限 park:write */
export function updateStall(id: number, data: Partial<StallPayload>): Promise<Stall> {
  return http.put<Stall>(`${STALL_BASE}/${id}`, data)
}

/** DELETE /api/v1/stalls/{id} 权限 park:write */
export function deleteStall(id: number): Promise<null> {
  return http.delete<null>(`${STALL_BASE}/${id}`)
}

/** POST /api/v1/stalls/{id}/assign 权限 park:write —— 入驻 / 退租（enterprise_id 传 null 表示退租） */
export function assignStall(id: number, data: StallAssignParams): Promise<Stall> {
  return http.post<Stall>(`${STALL_BASE}/${id}/assign`, data)
}

/* ---------------- 园区合同 ---------------- */

/** GET /api/v1/park-contracts 权限 park:read */
export function listParkContracts(params: ParkContractQuery): Promise<PageResult<ParkContract>> {
  return http.get<PageResult<ParkContract>>(PARK_CONTRACT_BASE, params as Record<string, unknown>)
}

/** POST /api/v1/park-contracts 权限 park:write */
export function createParkContract(data: ParkContractPayload): Promise<ParkContract> {
  return http.post<ParkContract>(PARK_CONTRACT_BASE, data)
}

/** GET /api/v1/park-contracts/{id} 权限 park:read */
export function getParkContract(id: number): Promise<ParkContract> {
  return http.get<ParkContract>(`${PARK_CONTRACT_BASE}/${id}`)
}

/** PUT /api/v1/park-contracts/{id} 权限 park:write */
export function updateParkContract(
  id: number,
  data: Partial<ParkContractPayload>
): Promise<ParkContract> {
  return http.put<ParkContract>(`${PARK_CONTRACT_BASE}/${id}`, data)
}

/** POST /api/v1/park-contracts/{id}/effect 权限 park:write —— 合同生效并占用档口 */
export function effectParkContract(id: number): Promise<ParkContract> {
  return http.post<ParkContract>(`${PARK_CONTRACT_BASE}/${id}/effect`)
}
