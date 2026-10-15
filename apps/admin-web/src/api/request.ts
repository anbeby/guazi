/**
 * Axios 统一请求实例。
 *
 * 职责：
 *  1. baseURL = /api/v1（开发环境由 Vite 代理到 http://localhost:8000，生产由 nginx 反代到 api:8000）
 *  2. 请求拦截：自动注入 Authorization: Bearer <access_token>
 *  3. 响应拦截：统一解包 {code, message, data} 信封；code === 0 才算成功，直接返回 data
 *  4. code !== 0 / HTTP 非 2xx：抛出 Error 并 ElMessage 提示
 *  5. 401（业务码 40001 / HTTP 401）：使用 refresh_token 静默续期，**单飞锁** 保证并发只刷新一次
 *  6. 续期失败：清理本地令牌并跳转登录页（携带 redirect 参数）
 */
import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig
} from 'axios'
import { ElMessage } from 'element-plus'

import type { ApiEnvelope, RefreshResult } from './types'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '@/utils/auth'

/** 后端统一前缀 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || '/api/v1'
/** 认证接口前缀（刷新令牌不走业务信封重试逻辑） */
export const AUTH_BASE_URL = `${API_BASE_URL}/auth`

/** 业务错误码（docs/04 1.2） */
export const BizCode = {
  SUCCESS: 0,
  PARAM_ERROR: 40000,
  UNAUTHENTICATED: 40001,
  FORBIDDEN: 40003,
  NOT_FOUND: 40004,
  CONFLICT: 40009,
  LOGIN_FAILED: 40100,
  ACCOUNT_DISABLED: 40101,
  REFRESH_INVALID: 40102,
  SERVER_ERROR: 50000
} as const

/** 业务错误对象 */
export class BizError extends Error {
  code: number
  requestId?: string
  httpStatus?: number

  constructor(code: number, message: string, requestId?: string, httpStatus?: number) {
    super(message)
    this.name = 'BizError'
    this.code = code
    this.requestId = requestId
    this.httpStatus = httpStatus
  }
}

/** 需要重试的请求配置（标记已重试，避免死循环） */
interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
  /** 静默模式：不弹出错误提示（用于 /auth/me 等后台探测） */
  silent?: boolean
}

/* ------------------------------------------------------------------ *
 * axios 实例
 * ------------------------------------------------------------------ */

const service: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json;charset=UTF-8' }
})

/* ------------------------------------------------------------------ *
 * 单飞刷新锁
 * ------------------------------------------------------------------ */

let isRefreshing = false
let pendingQueue: Array<(token: string | null) => void> = []

function flushQueue(token: string | null): void {
  const queue = pendingQueue
  pendingQueue = []
  queue.forEach((cb) => cb(token))
}

function toLoginPage(): void {
  clearTokens()
  const { pathname, search, hash } = window.location
  if (pathname.startsWith('/login')) return
  const redirect = encodeURIComponent(`${pathname}${search}${hash}`)
  window.location.href = `/login?redirect=${redirect}`
}

/** 调用 /auth/refresh 换取新令牌（使用裸 axios，避免拦截器递归） */
async function requestRefreshToken(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null
  try {
    const resp = await axios.post<ApiEnvelope<RefreshResult>>(
      `${AUTH_BASE_URL}/refresh`,
      { refresh_token: refreshToken },
      { timeout: 15000, headers: { 'Content-Type': 'application/json;charset=UTF-8' } }
    )
    const body = resp.data
    if (!body || body.code !== BizCode.SUCCESS || !body.data?.access_token) {
      return null
    }
    setTokens(body.data.access_token, body.data.refresh_token, body.data.expires_in)
    return body.data.access_token
  } catch {
    return null
  }
}

/* ------------------------------------------------------------------ *
 * 请求拦截器
 * ------------------------------------------------------------------ */

service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken()
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`)
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error)
)

/* ------------------------------------------------------------------ *
 * 响应拦截器
 * ------------------------------------------------------------------ */

function extractMessage(error: AxiosError<ApiEnvelope<unknown>>): {
  code: number
  message: string
  requestId?: string
  status?: number
} {
  const status = error.response?.status
  const body = error.response?.data
  if (body && typeof body === 'object' && typeof body.code === 'number') {
    return { code: body.code, message: body.message || '请求失败', requestId: body.request_id, status }
  }
  if (status === 401) return { code: BizCode.UNAUTHENTICATED, message: '登录状态已失效，请重新登录', status }
  if (status === 403) return { code: BizCode.FORBIDDEN, message: '无权限执行该操作', status }
  if (status === 404) return { code: BizCode.NOT_FOUND, message: '请求的资源不存在', status }
  if (status === 409) return { code: BizCode.CONFLICT, message: '业务冲突，请刷新后重试', status }
  if (status === 422) return { code: BizCode.PARAM_ERROR, message: '参数校验失败', status }
  if (status && status >= 500) return { code: BizCode.SERVER_ERROR, message: '服务器内部错误', status }
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return { code: -1, message: '请求超时，请稍后重试' }
  }
  return { code: -1, message: error.message || '网络异常，请检查网络连接' }
}

service.interceptors.response.use(
  (response: AxiosResponse<ApiEnvelope<unknown>>) => {
    const body = response.data

    // 非信封响应（文件直出 / 探针）：直接透传
    if (response.config.responseType === 'blob' || response.config.responseType === 'arraybuffer') {
      return response.data as unknown as never
    }
    if (!body || typeof body !== 'object' || typeof (body as ApiEnvelope<unknown>).code !== 'number') {
      return body as unknown as never
    }

    if (body.code === BizCode.SUCCESS) {
      // 统一解包：调用方直接拿到 data
      return body.data as unknown as never
    }

    if (body.code === BizCode.UNAUTHENTICATED) {
      return handleUnauthorized(response.config as RetriableConfig, body.message || '登录状态已失效')
    }

    const err = new BizError(body.code, body.message || '请求失败', body.request_id, response.status)
    if (!(response.config as RetriableConfig).silent) {
      ElMessage.error(err.message)
    }
    return Promise.reject(err)
  },
  async (error: AxiosError<ApiEnvelope<unknown>>) => {
    const config = (error.config || {}) as RetriableConfig

    // 401：尝试静默续期
    if (error.response?.status === 401) {
      return handleUnauthorized(config, '登录状态已失效')
    }
    if (error.response?.status === 403) {
      const info = extractMessage(error)
      const err = new BizError(info.code, '无权限执行该操作', info.requestId, 403)
      if (!config.silent) ElMessage.error(err.message)
      return Promise.reject(err)
    }

    const info = extractMessage(error)
    const bizError = new BizError(info.code, info.message, info.requestId, info.status)
    if (!config.silent) {
      ElMessage.error(bizError.message)
    }
    return Promise.reject(bizError)
  }
)

/** 401 处理：单飞刷新 + 队列重放；刷新失败则跳登录 */
function handleUnauthorized(config: RetriableConfig, fallbackMessage: string): Promise<never> {
  // 刷新接口自身 401 -> 直接登出
  const isAuthApi = typeof config.url === 'string' && config.url.includes('/auth/')
  if (isAuthApi || config._retried) {
    toLoginPage()
    return Promise.reject(new BizError(BizCode.UNAUTHENTICATED, fallbackMessage, undefined, 401))
  }

  if (isRefreshing) {
    // 已有刷新在进行：排队等待
    return new Promise<never>((resolve, reject) => {
      pendingQueue.push((token: string | null) => {
        if (!token) {
          reject(new BizError(BizCode.UNAUTHENTICATED, fallbackMessage, undefined, 401))
          return
        }
        config._retried = true
        config.headers.set('Authorization', `Bearer ${token}`)
        resolve(service.request(config) as unknown as never)
      })
    })
  }

  isRefreshing = true
  return new Promise<never>((resolve, reject) => {
    requestRefreshToken()
      .then((token) => {
        if (!token) {
          flushQueue(null)
          toLoginPage()
          reject(new BizError(BizCode.UNAUTHENTICATED, fallbackMessage, undefined, 401))
          return
        }
        flushQueue(token)
        config._retried = true
        config.headers.set('Authorization', `Bearer ${token}`)
        resolve(service.request(config) as unknown as never)
      })
      .catch(() => {
        flushQueue(null)
        toLoginPage()
        reject(new BizError(BizCode.UNAUTHENTICATED, fallbackMessage, undefined, 401))
      })
      .finally(() => {
        isRefreshing = false
      })
  })
}

/* ------------------------------------------------------------------ *
 * 对外导出的类型化请求方法
 * ------------------------------------------------------------------ */

export interface RequestOptions extends AxiosRequestConfig {
  /** 静默：不弹错误提示 */
  silent?: boolean
}

export const http = {
  get<T>(url: string, params?: Record<string, unknown>, options?: RequestOptions): Promise<T> {
    return service.get(url, { params, ...options }) as unknown as Promise<T>
  },
  post<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return service.post(url, data, options) as unknown as Promise<T>
  },
  put<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return service.put(url, data, options) as unknown as Promise<T>
  },
  delete<T>(url: string, params?: Record<string, unknown>, options?: RequestOptions): Promise<T> {
    return service.delete(url, { params, ...options }) as unknown as Promise<T>
  },
  /** multipart/form-data 上传 */
  upload<T>(url: string, formData: FormData, options?: RequestOptions): Promise<T> {
    return service.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
      ...options
    }) as unknown as Promise<T>
  },
  /** 二进制下载 */
  blob(url: string, params?: Record<string, unknown>, options?: RequestOptions): Promise<Blob> {
    return service.get(url, { params, responseType: 'blob', ...options }) as unknown as Promise<Blob>
  }
}

export default service
