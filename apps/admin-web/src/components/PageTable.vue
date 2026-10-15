<script setup lang="ts">
/**
 * 通用表格页容器：查询表单插槽 + 工具条插槽 + 表格 + 分页。
 *
 * 用法：
 *   <PageTable :data="list" :total="total" :loading="loading" v-model:page="query.page" v-model:page-size="query.page_size">
 *     <el-table-column prop="name" label="名称" />
 *   </PageTable>
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    data: unknown[]
    total: number
    loading?: boolean
    page?: number
    pageSize?: number
    pageSizes?: number[]
    /** 是否显示分页（不分页接口可关闭） */
    showPagination?: boolean
    emptyText?: string
    rowKey?: string
  }>(),
  {
    loading: false,
    page: 1,
    pageSize: 20,
    pageSizes: () => [10, 20, 50, 100],
    showPagination: true,
    emptyText: '暂无数据',
    rowKey: 'id'
  }
)

const emit = defineEmits<{
  (e: 'update:page', value: number): void
  (e: 'update:pageSize', value: number): void
  (e: 'change', payload: { page: number; page_size: number }): void
}>()

const pageValue = computed({
  get: () => props.page,
  set: (value: number) => emit('update:page', value)
})

const pageSizeValue = computed({
  get: () => props.pageSize,
  set: (value: number) => emit('update:pageSize', value)
})

function handleCurrentChange(page: number): void {
  emit('change', { page, page_size: props.pageSize })
}

function handleSizeChange(size: number): void {
  emit('update:pageSize', size)
  emit('update:page', 1)
  emit('change', { page: 1, page_size: size })
}
</script>

<template>
  <div>
    <slot name="search" />

    <div class="page-card">
      <div v-if="$slots.toolbar" class="table-toolbar">
        <div class="table-toolbar__left">
          <slot name="toolbar" />
        </div>
        <div class="table-toolbar__right">
          <slot name="toolbar-right" />
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="data as Record<string, unknown>[]"
        :row-key="rowKey"
        border
        stripe
        size="default"
        :empty-text="emptyText"
        style="width: 100%"
      >
        <slot />
      </el-table>

      <div v-if="showPagination" class="table-pagination">
        <el-pagination
          v-model:current-page="pageValue"
          v-model:page-size="pageSizeValue"
          :total="total"
          :page-sizes="pageSizes"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="handleCurrentChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.table-toolbar__left,
.table-toolbar__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
