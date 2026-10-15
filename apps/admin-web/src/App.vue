<script setup lang="ts">
/**
 * 应用根组件：仅承载路由出口，按需套用 Element Plus 全局配置。
 */
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const locale = zhCn
</script>

<template>
  <el-config-provider :locale="locale" :z-index="3000">
    <router-view />
  </el-config-provider>
</template>

<style>
#app {
  height: 100%;
}
</style>
