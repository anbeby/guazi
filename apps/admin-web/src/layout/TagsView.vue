<script setup lang="ts">
/**
 * 标签页导航：随路由自动新增标签，支持关闭 / 关闭其它 / 关闭全部。
 */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAppStore } from '@/stores/app'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const tags = computed(() => appStore.tagsView)

function isActive(path: string): boolean {
  return route.path === path
}

watch(
  () => route.fullPath,
  () => {
    if (!route.meta?.title || route.path === '/login') return
    appStore.addTagView({
      title: route.meta.title as string,
      path: route.path,
      fullPath: route.fullPath,
      name: (route.name as string) || undefined,
      closable: !route.meta?.affix
    })
  },
  { immediate: true }
)

/** 关闭标签：若关闭的是当前页则跳转到相邻标签 */
function closeTag(path: string): void {
  const index = tags.value.findIndex((item) => item.path === path)
  const wasActive = isActive(path)
  appStore.removeTagView(path)
  if (!wasActive) return
  const next = tags.value[index] || tags.value[index - 1] || tags.value[tags.value.length - 1]
  router.push(next ? next.fullPath : '/dashboard')
}

function closeOthers(): void {
  appStore.removeOtherTags(route.path)
}

function closeAll(): void {
  appStore.removeAllTags()
  const remain = appStore.tagsView
  router.push(remain.length > 0 ? remain[0].fullPath : '/dashboard')
}

function handleCommand(command: string): void {
  if (command === 'others') closeOthers()
  else if (command === 'all') closeAll()
}
</script>

<template>
  <div class="tags-view">
    <el-scrollbar class="tags-view__scroll">
      <div class="tags-view__list">
        <router-link
          v-for="tag in tags"
          :key="tag.path"
          class="tags-view__item"
          :class="{ 'is-active': isActive(tag.path) }"
          :to="tag.fullPath"
        >
          <span class="tags-view__dot" />
          <span>{{ tag.title }}</span>
          <el-icon v-if="tag.closable" class="tags-view__close" @click.prevent.stop="closeTag(tag.path)">
            <Close />
          </el-icon>
        </router-link>
      </div>
    </el-scrollbar>

    <el-dropdown trigger="click" @command="handleCommand">
      <el-button size="small" text>
        标签操作
        <el-icon><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="others">关闭其它标签</el-dropdown-item>
          <el-dropdown-item command="all">关闭全部标签</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.tags-view {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid var(--gz-border);
  border-radius: 4px;
  padding: 4px 8px;
}

.tags-view__scroll {
  flex: 1;
  min-width: 0;
}

.tags-view__list {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.tags-view__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 10px;
  border: 1px solid var(--gz-border);
  border-radius: 3px;
  font-size: 12px;
  color: #4b5563;
  background: #fff;
}

.tags-view__item.is-active {
  color: #fff;
  background: var(--gz-primary);
  border-color: var(--gz-primary);
}

.tags-view__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.6;
}

.tags-view__close {
  font-size: 12px;
}

.tags-view__close:hover {
  color: #c0392b;
}
</style>
