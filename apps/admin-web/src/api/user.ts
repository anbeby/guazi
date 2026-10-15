/** 用户管理 /users —— docs/04 §2.2 */
import { http } from './request'
import type {
  AssignRolesParams,
  PageResult,
  ResetPasswordParams,
  SysUser,
  UserPayload,
  UserQuery
} from './types'

const BASE = '/users'

/** GET /api/v1/users 权限 user:read */
export function listUsers(params: UserQuery): Promise<PageResult<SysUser>> {
  return http.get<PageResult<SysUser>>(BASE, params as Record<string, unknown>)
}

/** GET /api/v1/users/{id} 权限 user:read */
export function getUser(id: number): Promise<SysUser> {
  return http.get<SysUser>(`${BASE}/${id}`)
}

/** POST /api/v1/users 权限 user:write */
export function createUser(data: UserPayload): Promise<SysUser> {
  return http.post<SysUser>(BASE, data)
}

/** PUT /api/v1/users/{id} 权限 user:write */
export function updateUser(id: number, data: Partial<UserPayload>): Promise<SysUser> {
  return http.put<SysUser>(`${BASE}/${id}`, data)
}

/** DELETE /api/v1/users/{id} 权限 user:write */
export function deleteUser(id: number): Promise<null> {
  return http.delete<null>(`${BASE}/${id}`)
}

/** POST /api/v1/users/{id}/roles 权限 user:write —— 分配角色 */
export function assignUserRoles(id: number, data: AssignRolesParams): Promise<null> {
  return http.post<null>(`${BASE}/${id}/roles`, data)
}

/** POST /api/v1/users/{id}/reset-password 权限 user:write —— 重置密码 */
export function resetUserPassword(id: number, data: ResetPasswordParams): Promise<null> {
  return http.post<null>(`${BASE}/${id}/reset-password`, data)
}
