/** 食品安全溯源 /trace —— docs/04 §2.9 */
import { http } from './request'
import type {
  PageResult,
  TraceBatch,
  TraceBatchPayload,
  TraceBatchQuery,
  TraceEvent,
  TraceEventPayload,
  TracePublicView
} from './types'

const BASE = '/trace'

/** GET /api/v1/trace/batches 权限 trace:read */
export function listTraceBatches(params: TraceBatchQuery): Promise<PageResult<TraceBatch>> {
  return http.get<PageResult<TraceBatch>>(`${BASE}/batches`, params as Record<string, unknown>)
}

/** POST /api/v1/trace/batches 权限 trace:write */
export function createTraceBatch(data: TraceBatchPayload): Promise<TraceBatch> {
  return http.post<TraceBatch>(`${BASE}/batches`, data)
}

/** GET /api/v1/trace/batches/{id} 权限 trace:read —— 批次详情（含链路） */
export function getTraceBatch(id: number): Promise<TraceBatch> {
  return http.get<TraceBatch>(`${BASE}/batches/${id}`)
}

/** POST /api/v1/trace/batches/{id}/events 权限 trace:write —— 追加链路事件 */
export function appendTraceEvent(batchId: number, data: TraceEventPayload): Promise<TraceEvent> {
  return http.post<TraceEvent>(`${BASE}/batches/${batchId}/events`, data)
}

/** GET /api/v1/trace/public/{batch_no} —— 公开扫码视图（无需鉴权） */
export function getTracePublic(batchNo: string): Promise<TracePublicView> {
  return http.get<TracePublicView>(`${BASE}/public/${encodeURIComponent(batchNo)}`)
}
