<script setup lang="ts">
/**
 * 状态标签：按字典分组自动取中文文案与 tag 颜色。
 *
 * 用法：<StatusTag group="orderStatus" :value="row.status" />
 */
import { computed } from 'vue'

import { useDictStore } from '@/stores/dict'

const props = withDefaults(
  defineProps<{
    group: string
    value?: string | number | null
    size?: 'large' | 'default' | 'small'
    effect?: 'dark' | 'light' | 'plain'
  }>(),
  {
    value: '',
    size: 'small',
    effect: 'light'
  }
)

const dictStore = useDictStore()

const text = computed(() =>
  dictStore.label(props.group as never, props.value ?? '', String(props.value ?? '-'))
)
const type = computed(() => dictStore.tagType(props.group as never, props.value ?? ''))
</script>

<template>
  <el-tag :type="type" :size="size" :effect="effect" disable-transitions>{{ text }}</el-tag>
</template>
