/** 系统与集成 —— docs/04 §2.12 */
import { http } from './request'
import type { OutboxEvent, OutboxQuery, PageResult, SystemInfo } from './types'

const SYSTEM_BASE = '/system'
const INTEGRATION_BASE = '/integration'

/** GET /api/v1/system/info 登录 —— 版本、环境、中间件状态 */
export function getSystemInfo(): Promise<SystemInfo> {
  return http.get<SystemInfo>(`${SYSTEM_BASE}/info`, undefined, { silent: true })
}

/** GET /api/v1/integration/outbox 权限 integration:read —— 出站事件列表 */
export function listOutbox(params: OutboxQuery): Promise<PageResult<OutboxEvent>> {
  return http.get<PageResult<OutboxEvent>>(`${INTEGRATION_BASE}/outbox`, params as Record<string, unknown>)
}

/** POST /api/v1/integration/outbox/{id}/retry 权限 integration:write —— 重试推送 */
export function retryOutbox(id: number): Promise<OutboxEvent> {
  return http.post<OutboxEvent>(`${INTEGRATION_BASE}/outbox/${id}/retry`)
}
