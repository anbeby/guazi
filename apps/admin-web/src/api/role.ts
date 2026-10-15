/** 角色与权限 /roles /permissions —— docs/04 §2.2 */
import { http } from './request'
import type {
  PageResult,
  Permission,
  PermissionGroup,
  Role,
  RolePayload,
  RoleQuery
} from './types'

const ROLE_BASE = '/roles'
const PERMISSION_BASE = '/permissions'

/** GET /api/v1/roles 权限 role:read */
export function listRoles(params?: RoleQuery): Promise<PageResult<Role>> {
  return http.get<PageResult<Role>>(ROLE_BASE, (params || {}) as Record<string, unknown>)
}

/** POST /api/v1/roles 权限 role:write */
export function createRole(data: RolePayload): Promise<Role> {
  return http.post<Role>(ROLE_BASE, data)
}

/** PUT /api/v1/roles/{id} 权限 role:write */
export function updateRole(id: number, data: Partial<RolePayload>): Promise<Role> {
  return http.put<Role>(`${ROLE_BASE}/${id}`, data)
}

/** DELETE /api/v1/roles/{id} 权限 role:write（系统角色不可删） */
export function deleteRole(id: number): Promise<null> {
  return http.delete<null>(`${ROLE_BASE}/${id}`)
}

/** GET /api/v1/roles/{id}/permissions 权限 role:read */
export function getRolePermissions(id: number): Promise<Permission[]> {
  return http.get<Permission[]>(`${ROLE_BASE}/${id}/permissions`)
}

/** PUT /api/v1/roles/{id}/permissions 权限 role:write */
export function updateRolePermissions(id: number, permissionIds: number[]): Promise<null> {
  return http.put<null>(`${ROLE_BASE}/${id}/permissions`, { permission_ids: permissionIds })
}

/** GET /api/v1/permissions 权限 role:read —— 权限字典（按模块分组） */
export function listPermissions(): Promise<PermissionGroup[]> {
  return http.get<PermissionGroup[]>(PERMISSION_BASE)
}
