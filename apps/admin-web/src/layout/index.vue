<script setup lang="ts">
/**
 * 全局布局：左侧菜单 + 顶栏 + 面包屑 + 标签页 + 内容区。
 */
import { computed, onMounted, onUnmounted } from 'vue'

import Sidebar from './Sidebar.vue'
import Navbar from './Navbar.vue'
import Breadcrumb from './Breadcrumb.vue'
import TagsView from './TagsView.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const sidebarWidth = computed(() =>
  appStore.sidebarCollapsed ? 'var(--gz-sidebar-collapsed-width)' : 'var(--gz-sidebar-width)'
)

function handleResize(): void {
  appStore.setDevice(window.innerWidth < 992 ? 'mobile' : 'desktop')
}

onMounted(() => {
  handleResize()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="layout">
    <aside class="layout__aside" :style="{ width: sidebarWidth }">
      <Sidebar />
    </aside>

    <section class="layout__main" :style="{ marginLeft: sidebarWidth }">
      <header class="layout__navbar">
        <Navbar />
      </header>

      <div class="layout__breadcrumb">
        <Breadcrumb />
      </div>

      <div class="layout__tags">
        <TagsView />
      </div>

      <main class="layout__content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <keep-alive :max="12">
              <component :is="Component" :key="$route.fullPath" />
            </keep-alive>
          </transition>
        </router-view>
      </main>
      <footer class="layout__footer">
        <span>© 2026 第十师瓜子油料数字化交易平台</span>
        <span>技术支持：屯云大数据</span>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: var(--gz-page-bg);
}

.layout__aside {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 1001;
  overflow: hidden;
  transition: width 0.25s ease;
  background: #12331f;
}

.layout__main {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  transition: margin-left 0.25s ease;
}

.layout__navbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  height: var(--gz-header-height);
  background: #fff;
  border-bottom: 1px solid var(--gz-border);
}

.layout__breadcrumb {
  padding: 10px 16px 0;
}

.layout__tags {
  padding: 8px 12px 0;
}

.layout__content {
  flex: 1;
  padding: 16px;
  min-width: 0;
}

.layout__footer {
  display: flex;
  justify-content: space-between;
  gap: 8px 18px;
  flex-wrap: wrap;
  padding: 10px 20px 15px;
  color: #789082;
  font-size: 11px;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 992px) {
  .layout__aside {
    width: var(--gz-sidebar-collapsed-width) !important;
  }
  .layout__main {
    margin-left: var(--gz-sidebar-collapsed-width) !important;
  }
}

@media (max-width: 650px) {
  .layout__content { padding: 8px; }
  .layout__footer { padding: 10px 12px 16px; }
}
</style>
