<script setup lang="ts">
/**
 * 面包屑：由路由守卫写入 appStore.breadcrumbs。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAppStore } from '@/stores/app'

const router = useRouter()
const appStore = useAppStore()

const items = computed(() => appStore.breadcrumbs)

function go(path?: string): void {
  if (!path) return
  router.push(path)
}
</script>

<template>
  <el-breadcrumb separator="/">
    <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
    <el-breadcrumb-item v-for="(item, index) in items" :key="`${item.path}-${index}`">
      <span
        :class="{ 'breadcrumb-link': index < items.length - 1 }"
        @click="index < items.length - 1 ? go(item.path) : undefined"
      >
        {{ item.title }}
      </span>
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<style scoped>
.breadcrumb-link {
  cursor: pointer;
  color: var(--gz-primary);
}
</style>
