/** 组织单元 /org-units —— docs/04 §2.2；层级：平台 → 园区 → 企业 */
import { http } from './request'
import type { OrgUnit, OrgUnitPayload } from './types'

const BASE = '/org-units'

/** GET /api/v1/org-units/tree 权限 org:read */
export function getOrgTree(params?: { keyword?: string; unit_type?: string }): Promise<OrgUnit[]> {
  return http.get<OrgUnit[]>(`${BASE}/tree`, params as Record<string, unknown>)
}

/** POST /api/v1/org-units 权限 org:write */
export function createOrgUnit(data: OrgUnitPayload): Promise<OrgUnit> {
  return http.post<OrgUnit>(BASE, data)
}

/** PUT /api/v1/org-units/{id} 权限 org:write */
export function updateOrgUnit(id: number, data: Partial<OrgUnitPayload>): Promise<OrgUnit> {
  return http.put<OrgUnit>(`${BASE}/${id}`, data)
}

/** DELETE /api/v1/org-units/{id} 权限 org:write */
export function deleteOrgUnit(id: number): Promise<null> {
  return http.delete<null>(`${BASE}/${id}`)
}
