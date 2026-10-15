<script setup lang="ts">
/**
 * 字典下拉选择：选项来自 stores/dict，与后端枚举保持一致。
 *
 * 用法：<DictSelect v-model="query.status" group="productStatus" clearable placeholder="全部" />
 */
import { computed, type CSSProperties } from 'vue'

import { useDictStore } from '@/stores/dict'
import type { DictItem } from '@/stores/dict'

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | null
    group: string
    placeholder?: string
    clearable?: boolean
    disabled?: boolean
    multiple?: boolean
    /** 是否在选项前追加「全部」空选项 */
    withAll?: boolean
    allLabel?: string
    allValue?: string | number | null
    style?: string | CSSProperties
  }>(),
  {
    modelValue: '',
    placeholder: '请选择',
    clearable: true,
    disabled: false,
    multiple: false,
    withAll: false,
    allLabel: '全部',
    allValue: '',
    style: 'width: 160px'
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number | null | (string | number)[]): void
  (e: 'change', value: string | number | null | (string | number)[]): void
}>()

const dictStore = useDictStore()

const items = computed<DictItem[]>(() => {
  const base = dictStore.options(props.group as never)
  if (!props.withAll) return base
  return [{ label: props.allLabel, value: props.allValue as string }, ...base]
})

function handleUpdate(value: string | number | null | (string | number)[]): void {
  emit('update:modelValue', value)
  emit('change', value)
}
</script>

<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    :clearable="clearable"
    :disabled="disabled"
    :multiple="multiple"
    :style="style"
    @update:model-value="handleUpdate"
  >
    <el-option
      v-for="item in items"
      :key="String(item.value)"
      :label="item.label"
      :value="item.value"
    />
  </el-select>
</template>
