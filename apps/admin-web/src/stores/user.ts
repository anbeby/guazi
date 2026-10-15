/**
 * 用户会话 Store。
 *
 * - token 持久化在 localStorage（见 utils/auth.ts），刷新页面不丢失登录态；
 * - 页面刷新后由 router 守卫调用 fetchUserInfo() 拉取 /auth/me 恢复 userInfo/roles/permissions；
 * - hasPermission() 基于 /auth/me 返回的 permissions 数组，支持 `module:*` 通配与超级管理员。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as authApi from '@/api/auth'
import type { LoginParams, UserProfile } from '@/api/types'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  getUserInfoCache,
  setTokens,
  setUserInfoCache
} from '@/utils/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(getAccessToken())
  const refreshTokenValue = ref<string>(getRefreshToken())
  const userInfo = ref<UserProfile | null>(getUserInfoCache<UserProfile>())
  /** 是否已成功从 /auth/me 拉取过用户信息 */
  const loaded = ref(false)

  const roles = computed<string[]>(() => userInfo.value?.roles || [])
  const permissions = computed<string[]>(() => userInfo.value?.permissions || [])
  const isSuperuser = computed<boolean>(
    () => Boolean(userInfo.value?.is_superuser) || roles.value.includes('platform_admin')
  )
  const username = computed<string>(() => userInfo.value?.username || '')
  const displayName = computed<string>(
    () => userInfo.value?.full_name || userInfo.value?.username || '未登录'
  )
  const enterpriseName = computed<string>(() => userInfo.value?.enterprise_name || '')
  const enterpriseId = computed<number | null>(() => userInfo.value?.enterprise_id ?? null)

  /**
   * 权限判定。
   * @param required 单个权限码或权限码数组（数组为「任一满足」）
   */
  function hasPermission(required?: string | string[]): boolean {
    if (!required || (Array.isArray(required) && required.length === 0)) return true
    if (isSuperuser.value) return true
    const codes = permissions.value
    const needed = Array.isArray(required) ? required : [required]
    return needed.some((code) => {
      if (!code) return true
      if (codes.includes(code)) return true
      // 支持 module:* 通配（如 product:* 覆盖 product:read）
      const moduleName = code.split(':')[0]
      if (moduleName && codes.includes(`${moduleName}:*`)) return true
      // 支持 * 全量通配
      if (codes.includes('*')) return true
      // 该权限的模块读权限视为可访问（如仅写权限时允许查看列表）
      return false
    })
  }

  /** 是否具备指定角色 */
  function hasRole(required?: string | string[]): boolean {
    if (!required || (Array.isArray(required) && required.length === 0)) return true
    const needed = Array.isArray(required) ? required : [required]
    return needed.some((code) => roles.value.includes(code))
  }

  function setSession(payload: {
    access_token: string
    refresh_token?: string
    expires_in?: number
    user?: UserProfile
  }): void {
    token.value = payload.access_token
    if (payload.refresh_token) refreshTokenValue.value = payload.refresh_token
    setTokens(payload.access_token, payload.refresh_token, payload.expires_in)
    if (payload.user) {
      userInfo.value = payload.user
      setUserInfoCache(JSON.stringify(payload.user))
    }
  }

  /** 登录：POST /auth/login */
  async function login(params: LoginParams): Promise<UserProfile> {
    const result = await authApi.login(params)
    setSession(result)
    loaded.value = true
    return result.user
  }

  /** 拉取当前用户 + 角色 + 权限：GET /auth/me */
  async function fetchUserInfo(): Promise<UserProfile> {
    const me = await authApi.getMe()
    userInfo.value = me
    setUserInfoCache(JSON.stringify(me))
    loaded.value = true
    return me
  }

  /** 修改密码：POST /auth/change-password */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await authApi.changePassword({ old_password: oldPassword, new_password: newPassword })
  }

  function resetState(): void {
    token.value = ''
    refreshTokenValue.value = ''
    userInfo.value = null
    loaded.value = false
    clearTokens()
  }

  /** 退出登录：先调 /auth/logout 加入黑名单，再清理本地状态 */
  async function logout(): Promise<void> {
    try {
      if (token.value) await authApi.logout()
    } catch {
      // 令牌已失效等场景忽略异常，保证本地一定能退出
    } finally {
      resetState()
    }
  }

  return {
    token,
    refreshTokenValue,
    userInfo,
    loaded,
    roles,
    permissions,
    isSuperuser,
    username,
    displayName,
    enterpriseName,
    enterpriseId,
    hasPermission,
    hasRole,
    setSession,
    login,
    fetchUserInfo,
    changePassword,
    logout,
    resetState
  }
})
