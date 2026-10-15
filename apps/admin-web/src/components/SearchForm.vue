<script setup lang="ts">
/**
 * 通用查询表单容器。
 *
 * 用法：
 *   <SearchForm @search="handleSearch" @reset="handleReset">
 *     <el-form-item label="关键词">
 *       <el-input v-model="query.keyword" placeholder="请输入" clearable />
 *     </el-form-item>
 *   </SearchForm>
 */
withDefaults(
  defineProps<{
    /** 是否显示操作按钮（默认显示 查询 / 重置） */
    showActions?: boolean
    searchText?: string
    resetText?: string
    loading?: boolean
    labelWidth?: string
  }>(),
  {
    showActions: true,
    searchText: '查询',
    resetText: '重置',
    loading: false,
    labelWidth: '80px'
  }
)

const emit = defineEmits<{
  (e: 'search'): void
  (e: 'reset'): void
}>()
</script>

<template>
  <div class="page-card search-form-wrapper">
    <el-form class="search-form" :label-width="labelWidth" @submit.prevent>
      <slot />
      <el-form-item v-if="showActions">
        <el-button type="primary" :loading="loading" @click="emit('search')">
          <el-icon><Search /></el-icon>
          <span>{{ searchText }}</span>
        </el-button>
        <el-button @click="emit('reset')">
          <el-icon><Refresh /></el-icon>
          <span>{{ resetText }}</span>
        </el-button>
        <slot name="actions" />
      </el-form-item>
      <slot name="extra" />
    </el-form>
  </div>
</template>

<style scoped>
.search-form-wrapper {
  padding-bottom: 4px;
}
</style>
