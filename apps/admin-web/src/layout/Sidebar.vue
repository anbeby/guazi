<script setup lang="ts">
/**
 * 侧边菜单：按路由表渲染，按 meta.permission 过滤无权限菜单。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { routes } from '@/router/routes'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

interface MenuNode {
  path: string
  title: string
  icon?: string
  children: MenuNode[]
}

/** 拼接父子路径 */
function joinPath(parent: string, child: string): string {
  if (child.startsWith('/')) return child
  return `${parent.replace(/\/$/, '')}/${child}`
}

function buildMenus(list: RouteRecordRaw[], parentPath = ''): MenuNode[] {
  const result: MenuNode[] = []
  list.forEach((item) => {
    if (item.meta?.hidden) return
    if (item.meta?.public) return

    const fullPath = joinPath(parentPath, item.path)
    const permission = item.meta?.permission as string | undefined
    if (permission && !userStore.hasPermission(permission)) return
    const roles = item.meta?.roles as string[] | undefined
    if (roles && !userStore.isSuperuser && !userStore.hasRole(roles)) return

    const children = item.children ? buildMenus(item.children, fullPath) : []
    const hasSelf = Boolean(item.name && item.meta?.title)

    if (children.length === 0 && !hasSelf) return

    // 只有一个子菜单且父级无自身页面时，扁平化为单项
    if (children.length === 1 && !hasSelf && !item.meta?.title) {
      result.push(children[0])
      return
    }

    result.push({
      path: children.length > 0 ? (children[0]?.path ?? fullPath) : fullPath,
      title: (item.meta?.title as string) || '',
      icon: item.meta?.icon as string | undefined,
      children
    })
  })
  return result
}

const menus = computed<MenuNode[]>(() => buildMenus(routes))

const activeMenu = computed<string>(() => (route.meta?.activeMenu as string) || route.path)
</script>

<template>
  <div class="sidebar">
    <div class="sidebar__logo" :class="{ 'is-collapsed': appStore.sidebarCollapsed }">
      <img class="sidebar__logo-mark" src="/static/images/logo/platform-mark.svg" alt="" />
      <span v-show="!appStore.sidebarCollapsed" class="sidebar__logo-text">
        瓜子油料交易平台
      </span>
    </div>

    <el-scrollbar class="sidebar__scroll">
      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        :collapse-transition="false"
        unique-opened
        router
        background-color="#12331f"
        text-color="#c9d8cf"
        active-text-color="#ffd666"
      >
        <template v-for="menu in menus" :key="menu.path">
          <el-sub-menu v-if="menu.children.length > 0" :index="menu.path">
            <template #title>
              <el-icon v-if="menu.icon"><component :is="menu.icon" /></el-icon>
              <span>{{ menu.title }}</span>
            </template>
            <el-menu-item v-for="child in menu.children" :key="child.path" :index="child.path">
              <el-icon v-if="child.icon"><component :is="child.icon" /></el-icon>
              <template #title>{{ child.title }}</template>
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item v-else :index="menu.path">
            <el-icon v-if="menu.icon"><component :is="menu.icon" /></el-icon>
            <template #title>{{ menu.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #12331f;
}

.sidebar__logo {
  display: flex;
  align-items: center;
  gap: 8px;
  height: var(--gz-header-height);
  padding: 0 14px;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.sidebar__logo.is-collapsed {
  justify-content: center;
  padding: 0;
}

.sidebar__logo-mark {
  width: 30px;
  height: 30px;
  object-fit: contain;
  flex-shrink: 0;
}

.sidebar__logo-text {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 1px;
}

.sidebar__scroll {
  flex: 1;
}

:deep(.el-menu) {
  border-right: none;
}

:deep(.el-menu-item.is-active) {
  background: rgba(255, 214, 102, 0.12);
}

:deep(.el-menu--collapse) {
  width: var(--gz-sidebar-collapsed-width);
}
</style>
