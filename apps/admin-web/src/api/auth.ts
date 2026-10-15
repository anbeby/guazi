/** 认证 /auth —— docs/04 §2.1 */
import { http } from './request'
import type { ChangePasswordParams, LoginParams, LoginResult, RefreshResult, UserProfile } from './types'

/** POST /api/v1/auth/login 公开 */
export function login(data: LoginParams): Promise<LoginResult> {
  return http.post<LoginResult>('/auth/login', data, { silent: true })
}

/** POST /api/v1/auth/refresh 公开 */
export function refreshToken(refresh_token: string): Promise<RefreshResult> {
  return http.post<RefreshResult>('/auth/refresh', { refresh_token }, { silent: true })
}

/** POST /api/v1/auth/logout 登录 */
export function logout(): Promise<null> {
  return http.post<null>('/auth/logout', {}, { silent: true })
}

/** GET /api/v1/auth/me 用户 + 角色 + 权限码列表 */
export function getMe(): Promise<UserProfile> {
  return http.get<UserProfile>('/auth/me')
}

/** POST /api/v1/auth/change-password */
export function changePassword(data: ChangePasswordParams): Promise<null> {
  return http.post<null>('/auth/change-password', data)
}
