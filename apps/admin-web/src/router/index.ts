import { createRouter, createWebHistory, type RouteLocationNormalized, type RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'

import { routes } from './routes'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { getAccessToken } from '@/utils/auth'

NProgress.configure({ showSpinner: false, minimum: 0.15, speed: 400, trickleSpeed: 150 })

/** 无需登录即可访问的路由白名单 */
const WHITE_LIST = ['/login', '/403', '/404']

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

function routeTitle(to: RouteLocationNormalized): string {
  const title = to.meta?.title as string | undefined
  const appTitle = (import.meta.env.VITE_APP_TITLE as string | undefined) || '瓜子油料交易平台'
  return title ? `${title} · ${appTitle}` : appTitle
}

router.beforeEach(async (to, _from, next) => {
  NProgress.start()
  document.title = routeTitle(to)

  const userStore = useUserStore()
  const appStore = useAppStore()
  const token = getAccessToken()

  // 1. 未登录
  if (!token) {
    if (WHITE_LIST.includes(to.path) || to.meta?.public) {
      next()
    } else {
      next({ path: '/login', query: { redirect: to.fullPath } })
    }
    NProgress.done()
    return
  }

  // 2. 已登录但用户信息未加载（刷新页面 / 新标签页）-> 拉取 /auth/me
  if (!userStore.loaded) {
    try {
      await userStore.fetchUserInfo()
    } catch {
      userStore.resetState()
      if (to.meta?.public) next()
      else next({ path: '/login', query: { redirect: to.fullPath } })
      NProgress.done()
      return
    }
  }

  // 3. 已登录访问登录页 -> 仅接受当前账号有权访问的跳转目标
  if (to.path === '/login') {
    const requested = to.query.redirect
    let target = userStore.hasPermission('data:read') ? '/dashboard' : '/account'
    if (typeof requested === 'string' && requested.startsWith('/') && !requested.startsWith('//')) {
      const resolved = router.resolve(requested)
      const permission = resolved.meta.permission as string | undefined
      const roles = resolved.meta.roles as string[] | undefined
      const permitted = (!permission || userStore.hasPermission(permission))
        && (!roles || userStore.isSuperuser || userStore.hasRole(roles))
      if (resolved.name && !['Login', 'NotFound', 'Forbidden'].includes(String(resolved.name)) && permitted) {
        target = requested
      }
    }
    next(target)
    NProgress.done()
    return
  }

  // 4. 路由级权限校验（meta.permission 来自 /auth/me 的 permissions）
  const permission = to.meta?.permission as string | undefined
  if (permission && !userStore.hasPermission(permission)) {
    next({ path: '/403' })
    NProgress.done()
    return
  }
  const roles = to.meta?.roles as string[] | undefined
  if (roles && !userStore.isSuperuser && !userStore.hasRole(roles)) {
    next({ path: '/403' })
    NProgress.done()
    return
  }

  // 5. 写入面包屑
  const crumbs = to.matched
    .filter((item) => item.meta && item.meta.title)
    .map((item) => ({ title: item.meta.title as string, path: (item.path as string) || '' }))
  appStore.setBreadcrumbs(crumbs)

  next()
})

router.afterEach(() => {
  NProgress.done()
})

router.onError(() => {
  NProgress.done()
})

export default router

/** 供菜单渲染使用的原始路由表 */
export const menuRoutes: RouteRecordRaw[] = routes
