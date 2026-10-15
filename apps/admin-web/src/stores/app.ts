/**
 * 应用级 UI 状态：侧边栏折叠、面包屑、主题、标签页、设备类型。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface BreadcrumbItem {
  title: string
  path?: string
}

export interface TagViewItem {
  title: string
  path: string
  /** 完整路由地址（含 query） */
  fullPath: string
  name?: string
  closable?: boolean
}

export type ThemeMode = 'light' | 'dark'

const SIDEBAR_KEY = 'gz_admin_sidebar_collapsed'
const THEME_KEY = 'gz_admin_theme'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref<boolean>(localStorage.getItem(SIDEBAR_KEY) === '1')
  const device = ref<'desktop' | 'mobile'>('desktop')
  const breadcrumbs = ref<BreadcrumbItem[]>([])
  const tagsView = ref<TagViewItem[]>([])
  const theme = ref<ThemeMode>((localStorage.getItem(THEME_KEY) as ThemeMode) || 'light')
  const pageLoading = ref(false)

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed.value ? '1' : '0')
  }

  function setSidebarCollapsed(value: boolean): void {
    sidebarCollapsed.value = value
    localStorage.setItem(SIDEBAR_KEY, value ? '1' : '0')
  }

  function setDevice(value: 'desktop' | 'mobile'): void {
    device.value = value
    if (value === 'mobile') setSidebarCollapsed(true)
  }

  function setBreadcrumbs(items: BreadcrumbItem[]): void {
    breadcrumbs.value = items
  }

  function setTheme(value: ThemeMode): void {
    theme.value = value
    localStorage.setItem(THEME_KEY, value)
    document.documentElement.classList.toggle('dark', value === 'dark')
  }

  function toggleTheme(): void {
    setTheme(theme.value === 'light' ? 'dark' : 'light')
  }

  /** 打开（或激活）一个标签页 */
  function addTagView(tag: TagViewItem): void {
    if (!tag.path || tag.path === '/login') return
    const exists = tagsView.value.find((item) => item.path === tag.path)
    if (exists) {
      exists.fullPath = tag.fullPath
      exists.title = tag.title
      return
    }
    tagsView.value.push(tag)
  }

  function removeTagView(path: string): void {
    const index = tagsView.value.findIndex((item) => item.path === path)
    if (index > -1) tagsView.value.splice(index, 1)
  }

  /** 关闭其它标签（保留固定标签） */
  function removeOtherTags(path: string): void {
    tagsView.value = tagsView.value.filter((item) => item.path === path || item.closable === false)
  }

  function removeAllTags(): void {
    tagsView.value = tagsView.value.filter((item) => item.closable === false)
  }

  return {
    sidebarCollapsed,
    device,
    breadcrumbs,
    tagsView,
    theme,
    pageLoading,
    toggleSidebar,
    setSidebarCollapsed,
    setDevice,
    setBreadcrumbs,
    setTheme,
    toggleTheme,
    addTagView,
    removeTagView,
    removeOtherTags,
    removeAllTags
  }
})
