/** 企业 / 商户档案 /enterprises —— docs/04 §2.4 */
import { http } from './request'
import type {
  Enterprise,
  EnterpriseAuditParams,
  EnterprisePayload,
  EnterpriseQuery,
  EnterpriseStats,
  PageResult
} from './types'

const BASE = '/enterprises'

/** GET /api/v1/enterprises 权限 merchant:read */
export function listEnterprises(params: EnterpriseQuery): Promise<PageResult<Enterprise>> {
  return http.get<PageResult<Enterprise>>(BASE, params as Record<string, unknown>)
}

/** POST /api/v1/enterprises 权限 merchant:write（含入驻申请） */
export function createEnterprise(data: EnterprisePayload): Promise<Enterprise> {
  return http.post<Enterprise>(BASE, data)
}

/** GET /api/v1/enterprises/{id} 权限 merchant:read */
export function getEnterprise(id: number): Promise<Enterprise> {
  return http.get<Enterprise>(`${BASE}/${id}`)
}

/** PUT /api/v1/enterprises/{id} 权限 merchant:write */
export function updateEnterprise(id: number, data: Partial<EnterprisePayload>): Promise<Enterprise> {
  return http.put<Enterprise>(`${BASE}/${id}`, data)
}

/** 关联管理员刚上传的企业展示图，不改动企业档案字段。 */
export function setEnterpriseImage(id: number, fileKey: string): Promise<Enterprise> {
  return http.put<Enterprise>(`${BASE}/${id}/image`, { file_key: fileKey })
}

/** DELETE /api/v1/enterprises/{id} 权限 merchant:write */
export function deleteEnterprise(id: number): Promise<null> {
  return http.delete<null>(`${BASE}/${id}`)
}

/** POST /api/v1/enterprises/{id}/audit 权限 merchant:audit */
export function auditEnterprise(id: number, data: EnterpriseAuditParams): Promise<Enterprise> {
  return http.post<Enterprise>(`${BASE}/${id}/audit`, data)
}

/** GET /api/v1/enterprises/{id}/stats 权限 merchant:read */
export function getEnterpriseStats(id: number): Promise<EnterpriseStats> {
  return http.get<EnterpriseStats>(`${BASE}/${id}/stats`)
}
