/**
 * Token 读写工具。
 *
 * 说明：本模块**不依赖** Pinia / api 层，以便 axios 实例（api/request.ts）
 * 在拦截器中安全使用，避免循环依赖。
 */

const ACCESS_TOKEN_KEY = 'gz_admin_access_token'
const REFRESH_TOKEN_KEY = 'gz_admin_refresh_token'
const EXPIRES_AT_KEY = 'gz_admin_expires_at'
const USER_INFO_KEY = 'gz_admin_user_info'

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || ''
}

export function getRefreshToken(): string {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || ''
}

/** 记录 access_token 过期时间（毫秒时间戳） */
export function getExpiresAt(): number {
  const raw = localStorage.getItem(EXPIRES_AT_KEY)
  return raw ? Number(raw) : 0
}

export function setTokens(accessToken: string, refreshToken?: string, expiresIn?: number): void {
  if (accessToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  }
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
  if (expiresIn && expiresIn > 0) {
    localStorage.setItem(EXPIRES_AT_KEY, String(Date.now() + expiresIn * 1000))
  }
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(EXPIRES_AT_KEY)
  localStorage.removeItem(USER_INFO_KEY)
}

export function setUserInfoCache(json: string): void {
  localStorage.setItem(USER_INFO_KEY, json)
}

export function getUserInfoCache<T>(): T | null {
  const raw = localStorage.getItem(USER_INFO_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}
