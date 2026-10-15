<script setup lang="ts">
/**
 * ECharts 图表卡片：标题 + 自适应 resize + 空数据占位。
 *
 * 按需引入（core + 常用图表/组件），避免打包整个 echarts。
 *
 * 用法：
 *   <ChartCard title="交易趋势" :option="trendOption" :empty="trendData.length === 0" height="320px" />
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent
} from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import type { ComposeOption } from 'echarts/core'
import type { BarSeriesOption, LineSeriesOption, PieSeriesOption } from 'echarts/charts'
import type {
  GridComponentOption,
  LegendComponentOption,
  TitleComponentOption,
  TooltipComponentOption
} from 'echarts/components'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  DatasetComponent,
  LabelLayout,
  UniversalTransition,
  CanvasRenderer
])

/** 支持的图表配置类型 */
type ChartOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | PieSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
  | TitleComponentOption
>

const props = withDefaults(
  defineProps<{
    title?: string
    /** ECharts 配置项；空数据时请同时传 empty */
    option: Record<string, unknown>
    /** 是否无数据（显示占位） */
    empty: boolean
    emptyText?: string
    height?: string
    loading?: boolean
  }>(),
  {
    title: '',
    emptyText: '暂无数据',
    height: '320px',
    loading: false
  }
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

const showEmpty = computed(() => props.empty)

function render(): void {
  const el = chartRef.value
  if (!el) return
  if (!chart) {
    chart = echarts.init(el)
  }
  if (showEmpty.value) {
    chart.clear()
    return
  }
  chart.setOption(props.option, true)
}

function resize(): void {
  chart?.resize()
}

onMounted(async () => {
  await nextTick()
  render()
  if (chartRef.value && typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => resize())
    observer.observe(chartRef.value)
  }
  window.addEventListener('resize', resize)
})

watch(
  () => props.option,
  async () => {
    await nextTick()
    render()
  },
  { deep: true }
)

watch(showEmpty, async () => {
  await nextTick()
  render()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  observer?.disconnect()
  observer = null
  chart?.dispose()
  chart = null
})

defineExpose({ resize, getInstance: () => chart })
</script>

<template>
  <div class="chart-card page-card">
    <div v-if="title" class="chart-card__header">
      <span class="chart-card__title">{{ title }}</span>
      <slot name="extra" />
    </div>

    <div v-loading="loading" class="chart-card__body" :style="{ height }">
      <div ref="chartRef" class="chart-card__canvas" />
      <div v-if="showEmpty" class="chart-card__empty">
        <el-empty :description="emptyText" :image-size="80" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chart-card__title {
  font-size: 15px;
  font-weight: 600;
}

.chart-card__body {
  position: relative;
  width: 100%;
}

.chart-card__canvas {
  width: 100%;
  height: 100%;
}

.chart-card__empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
}
</style>
