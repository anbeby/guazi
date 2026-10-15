<script setup lang="ts">
/**
 * 数据驾驶舱：指标卡片 + 交易趋势折线 + 价格趋势 + 产业分布饼图。
 * 数据来源：/dashboard/overview、/dashboard/trend、/dashboard/price-trend、/dashboard/industry（权限 data:read）
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import ChartCard from '@/components/ChartCard.vue'
import { getIndustry, getOverview, getPriceTrend, getTrend } from '@/api/dashboard'
import { getCategoryTree } from '@/api/category'
import type {
  Category,
  DashboardIndustry,
  DashboardOverview,
  DashboardPricePoint,
  DashboardTrendPoint
} from '@/api/types'
import { formatMoney, formatMoneyShort, formatPercent, formatQuantity, unitLabel } from '@/utils/format'
import { useDictStore } from '@/stores/dict'
import { useAppStore } from '@/stores/app'

/** 图表配置（与 ChartCard 内部按需注册的图表类型兼容） */
type ChartOption = Record<string, unknown>

const dictStore = useDictStore()
const appStore = useAppStore()

const loading = ref(false)
const overview = ref<DashboardOverview | null>(null)
const trend = ref<DashboardTrendPoint[]>([])
const priceTrend = ref<DashboardPricePoint[]>([])
const industry = ref<DashboardIndustry>({})
const categories = ref<Category[]>([])
interface ShowcaseProduct {
  id: number
  name: string
  spec: string
  price: number
  unit: string
  enterprise: string
  image: string
}
interface ShowcaseDeal {
  order_no: string
  product: string
  quantity: number
  amount: number
  supplier: string
  date: string
}
interface ShowcaseData {
  park: { name: string; description: string } | null
  products: ShowcaseProduct[]
  recent_deals: ShowcaseDeal[]
}
const showcase = ref<ShowcaseData | null>(null)
const showcaseError = ref(false)
const displayNumber = (value: number): string => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value || 0)
const displayMoneyShort = (value: string | number | null | undefined): string => {
  const short = formatMoneyShort(value)
  return short === '-' ? '-' : `${short.replace(/\s/g, '')}元`
}

const days = ref(30)
const categoryId = ref<number | null>(null)

/** 指标卡片定义（全部来自 overview 接口真实字段） */
interface MetricCard {
  label: string
  value: string
  sub: string
  color: string
  icon: string
}

const metrics = computed<MetricCard[]>(() => {
  const data = overview.value
  if (!data) return []
  return [
    {
      label: '入驻企业',
      value: String(data.enterprise_count ?? 0),
      sub: `商户 ${data.merchant_count ?? 0} · 供应商 ${data.supplier_count ?? 0} · 采购商 ${data.buyer_count ?? 0}`,
      color: '#1f6feb',
      icon: 'OfficeBuilding'
    },
    {
      label: '商品总数',
      value: String(data.product_count ?? 0),
      sub: `已上架 ${data.published_product_count ?? 0} 个`,
      color: '#16653f',
      icon: 'Goods'
    },
    {
      label: '订单总数',
      value: String(data.order_count ?? 0),
      sub: `今日新增 ${data.today_order_count ?? 0} 单`,
      color: '#0f8b8d',
      icon: 'List'
    },
    {
      label: '库存总量',
      value: `${formatQuantity(data.inventory_quantity)} 吨`,
      sub: `库存货值 ${displayMoneyShort(data.inventory_value)}`,
      color: '#d48806',
      icon: 'Box'
    },
    {
      label: '交易金额',
      value: displayMoneyShort(data.order_amount),
      sub: `今日 ${displayMoneyShort(data.today_order_amount)}`,
      color: '#c0392b',
      icon: 'Money'
    },
    {
      label: '询价单数',
      value: String(data.inquiry_count ?? 0),
      sub: '采购商在线询价累计',
      color: '#6f42c1',
      icon: 'ChatDotRound'
    },
    {
      label: '档口出租率',
      value: formatPercent(data.stall_rented_rate),
      sub: `已租 ${data.stall_rented ?? 0} / 共 ${data.stall_count ?? 0} 个档口`,
      color: '#b8860b',
      icon: 'Shop'
    },
    {
      label: '待办审核',
      value: String((data.pending_audit_enterprise ?? 0) + (data.pending_audit_product ?? 0)),
      sub: `企业 ${data.pending_audit_enterprise ?? 0} · 商品 ${data.pending_audit_product ?? 0}`,
      color: '#e67e22',
      icon: 'Bell'
    }
  ]
})

/* ------------------------- 交易趋势折线 ------------------------- */

const trendOption = computed<ChartOption>(() => {
  const dates = trend.value.map((item) => item.date)
  const amounts = trend.value.map((item) => Number(item.order_amount || 0))
  const counts = trend.value.map((item) => Number(item.order_count || 0))
  const quantities = trend.value.map((item) => Number(item.quantity || 0))

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['交易金额(元)', '订单量(单)', '交易量(吨)'], top: 0 },
    grid: { left: 12, right: 16, bottom: 8, top: 42, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: dates },
    yAxis: [
      { type: 'value', name: '金额/元', axisLabel: { formatter: (value: number) => formatMoneyShort(value) } },
      { type: 'value', name: '单量/吨', splitLine: { show: false } }
    ],
    series: [
      {
        name: '交易金额(元)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.12 },
        itemStyle: { color: '#16653f' },
        data: amounts
      },
      {
        name: '订单量(单)',
        type: 'bar',
        barWidth: 10,
        yAxisIndex: 1,
        itemStyle: { color: '#d48806' },
        data: counts
      },
      {
        name: '交易量(吨)',
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        itemStyle: { color: '#1f6feb' },
        data: quantities
      }
    ]
  }
})

/* ------------------------- 价格趋势 ------------------------- */

const priceOption = computed<ChartOption>(() => {
  const dates = priceTrend.value.map((item) => item.date)
  const prices = priceTrend.value.map((item) => Number(item.avg_price || 0))
  return {
    tooltip: { trigger: 'axis', valueFormatter: (value: unknown) => `${formatMoney(value as number)} 元/吨` },
    grid: { left: 12, right: 16, bottom: 8, top: 30, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: dates },
    yAxis: { type: 'value', name: '元/吨', scale: true },
    series: [
      {
        name: '成交均价',
        type: 'line',
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#c0392b' },
        data: prices
      }
    ]
  }
})

/* ------------------------- 产业分布 ------------------------- */

function toPieData(items?: { name: string; value: string | number }[]): { name: string; value: number }[] {
  if (!items || items.length === 0) return []
  return items.map((item) => ({ name: item.name, value: Number(item.value || 0) }))
}

const categoryPie = computed(() => toPieData(industry.value.by_category))
const gradePie = computed(() =>
  toPieData(
    (industry.value.by_grade || []).map((item) => ({
      name: dictStore.label('productGrade', item.name),
      value: item.value
    }))
  )
)
const originPie = computed(() => toPieData(industry.value.by_origin))

function buildPieOption(data: { name: string; value: number }[], name: string): ChartOption {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle', textStyle: { fontSize: 12 } },
    series: [
      {
        name,
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['38%', '52%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data
      }
    ]
  }
}

const categoryOption = computed(() => buildPieOption(categoryPie.value, '品类分布'))
const gradeOption = computed(() => buildPieOption(gradePie.value, '等级分布'))
const originOption = computed(() => buildPieOption(originPie.value, '产地分布'))

/** 扁平化分类树，用于价格趋势筛选 */
const categoryOptions = computed(() => {
  const list: { label: string; value: number }[] = []
  const walk = (nodes: Category[], depth: number): void => {
    nodes.forEach((node) => {
      list.push({ label: `${'　'.repeat(depth)}${node.name}`, value: node.id })
      if (node.children?.length) walk(node.children, depth + 1)
    })
  }
  walk(categories.value, 0)
  return list
})

/* ------------------------- 数据加载 ------------------------- */

async function loadOverview(): Promise<void> {
  try {
    overview.value = await getOverview()
  } catch {
    overview.value = null
  }
}

async function loadTrend(): Promise<void> {
  try {
    trend.value = await getTrend(days.value)
  } catch {
    trend.value = []
  }
}

async function loadPriceTrend(): Promise<void> {
  try {
    priceTrend.value = await getPriceTrend(days.value, categoryId.value)
  } catch {
    priceTrend.value = []
  }
}

async function loadIndustry(): Promise<void> {
  try {
    industry.value = await getIndustry()
  } catch {
    industry.value = {}
  }
}

async function loadCategories(): Promise<void> {
  try {
    categories.value = await getCategoryTree()
  } catch {
    categories.value = []
  }
}

async function loadShowcase(): Promise<void> {
  try {
    const response = await fetch('/api/v1/showcase')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const result = await response.json()
    if (result.code !== 0 || !result.data) throw new Error(result.message || '展示数据读取失败')
    showcase.value = result.data as ShowcaseData
    showcaseError.value = false
  } catch {
    showcaseError.value = true
  }
}

async function refreshAll(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([loadOverview(), loadTrend(), loadPriceTrend(), loadIndustry(), loadShowcase()])
    ElMessage.success('数据已刷新')
  } finally {
    loading.value = false
  }
}

async function handleDaysChange(): Promise<void> {
  await loadTrend()
  await loadPriceTrend()
}

async function handleCategoryChange(): Promise<void> {
  await loadPriceTrend()
}

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([
      loadOverview(),
      loadTrend(),
      loadPriceTrend(),
      loadIndustry(),
      loadCategories(),
      loadShowcase()
    ])
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="dashboard">
    <section class="industry-hero" aria-label="北屯瓜子产业展示">
      <div class="industry-hero__content">
        <div class="industry-hero__eyebrow">第十师 · 北屯瓜子油料产业</div>
        <h1>北屯瓜子 <span>香飘全国</span></h1>
        <p>产地直供 · 数字交易 · 产业协同</p>
        <div class="industry-hero__links">
          <router-link to="/hall">进入商品交易大厅 →</router-link>
          <router-link to="/merchants">查看入驻企业</router-link>
        </div>
      </div>
      <span class="industry-hero__note">产业场景示意图</span>
    </section>
    <div class="page-title">
      <span>
        产业运营总览
        <span class="page-title__sub">企业、商品、库存与交易数据实时汇总</span>
      </span>
      <div class="dashboard__actions">
        <el-radio-group v-model="days" size="small" @change="handleDaysChange">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
        <el-button size="small" :loading="loading" @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </div>

    <el-row :gutter="12">
      <el-col v-for="item in metrics" :key="item.label" :xs="12" :sm="12" :md="6" :lg="6">
        <div class="metric-card page-card">
          <div class="metric-card__icon" :style="{ background: `${item.color}1a`, color: item.color }">
            <el-icon :size="20"><component :is="item.icon" /></el-icon>
          </div>
          <div class="metric-card__label">{{ item.label }}</div>
          <div class="metric-card__value" :style="{ color: item.color }">{{ item.value }}</div>
          <div class="metric-card__sub">{{ item.sub }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="dashboard-section-title"><div><small>产地好货</small><h2>平台在售商品</h2></div><router-link to="/hall">查看全部商品 →</router-link></div>
    <div v-if="showcase?.products.length" class="dashboard-product-grid">
      <router-link v-for="product in showcase.products.slice(0, 4)" :key="product.id" :to="`/item/${product.id}`" class="dashboard-product">
        <img :src="product.image" :alt="product.name" loading="lazy" decoding="async" />
        <div class="dashboard-product__body">
          <h3>{{ product.name }}</h3>
          <p>{{ product.spec }}</p>
          <span class="dashboard-product__enterprise">{{ product.enterprise }}</span>
          <div class="dashboard-product__price"><strong>¥{{ displayNumber(product.price) }}</strong><span>/{{ product.unit === 'ton' ? '吨' : product.unit }}</span></div>
        </div>
      </router-link>
    </div>
    <div v-else-if="showcaseError" class="page-card dashboard-data-error">商品展示数据暂不可用，请刷新重试。</div>

    <div class="dashboard-feature-grid">
      <section class="page-card dashboard-deals">
        <div class="dashboard-section-title"><div><small>市场动态</small><h2>最近交易</h2></div><router-link to="/trade/order">查看订单 →</router-link></div>
        <div v-if="showcase?.recent_deals.length" class="dashboard-deals__list">
          <div v-for="deal in showcase.recent_deals.slice(0, 5)" :key="deal.order_no" class="dashboard-deals__row">
            <div><strong>{{ deal.product }}</strong><span>{{ deal.supplier }} · {{ deal.date }}</span></div>
            <div><strong>¥{{ displayNumber(deal.amount) }}</strong><span>{{ deal.quantity }} 吨</span></div>
          </div>
        </div>
        <div v-else class="dashboard-empty">暂无已成交订单。订单完成后，交易动态会显示在这里。</div>
      </section>
      <section class="page-card dashboard-chain">
        <div><small>从产地到市场</small><h2>{{ showcase?.park?.name || '第十师北屯瓜子产业园' }}</h2>
          <p>{{ showcase?.park?.description || '平台连接瓜子油料产业链的企业、商品、仓储与交易。' }}</p>
          <div class="dashboard-chain__steps"><span>产地种植</span><b>→</b><span>加工仓储</span><b>→</b><span>线上交易</span></div>
          <router-link to="/merchants">了解产业链企业 →</router-link>
        </div>
      </section>
    </div>

    <el-row :gutter="12" class="mt-12">
      <el-col :xs="24" :lg="16">
        <ChartCard
          title="交易趋势（金额 / 单量 / 吨数）"
          :option="trendOption"
          :empty="trend.length === 0"
          :loading="loading"
          height="330px"
        />
      </el-col>
      <el-col :xs="24" :lg="8">
        <ChartCard title="品类交易分布" :option="categoryOption" :empty="categoryPie.length === 0" height="330px" />
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="12">
        <ChartCard
          title="成交价格趋势（成交均价）"
          :option="priceOption"
          :empty="priceTrend.length === 0"
          height="300px"
        >
          <template #extra>
            <el-select
              v-model="categoryId"
              size="small"
              clearable
              placeholder="全部分类"
              style="width: 180px"
              @change="handleCategoryChange"
            >
              <el-option
                v-for="item in categoryOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </ChartCard>
      </el-col>
      <el-col :xs="24" :lg="6">
        <ChartCard title="等级分布" :option="gradeOption" :empty="gradePie.length === 0" height="300px" />
      </el-col>
      <el-col :xs="24" :lg="6">
        <ChartCard title="产地分布" :option="originOption" :empty="originPie.length === 0" height="300px" />
      </el-col>
    </el-row>

    <div class="page-card mt-12">
      <div class="page-title">
        <span>园区运营概览</span>
      </div>
      <el-descriptions :column="appStore.device === 'mobile' ? 1 : 4" border>
        <el-descriptions-item label="园区数量">{{ overview?.park_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="档口总数">{{ overview?.stall_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="已租档口">{{ overview?.stall_rented ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="档口出租率">
          {{ overview ? formatPercent(overview.stall_rented_rate) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="库存货值">
          {{ overview ? `${formatMoney(overview.inventory_value)} 元` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="库存总量">
          {{ overview ? `${formatQuantity(overview.inventory_quantity)} 吨` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="累计交易额">
          {{ overview ? `${formatMoney(overview.order_amount)} 元` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="今日交易额">
          {{ overview ? `${formatMoney(overview.today_order_amount)} 元` : '-' }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="dashboard__hint">
        提示：库存单位吨按商品 unit 汇总展示（{{ unitLabel('ton') }}），价格趋势数据周期与上方天数选择联动。
      </div>
    </div>
  </div>
</template>

<style scoped>
.industry-hero {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 205px;
  overflow: hidden;
  border-radius: 16px;
  margin-bottom: 22px;
  background: linear-gradient(90deg, rgba(4, 49, 28, .96) 0%, rgba(5, 75, 40, .86) 37%, rgba(5, 75, 40, .12) 76%), url('/demo/hero.png') center 55% / cover;
  box-shadow: 0 15px 34px rgba(6, 58, 35, .19);
  color: #fff;
}
.industry-hero__content { position: relative; z-index: 1; padding: 26px 34px; }
.industry-hero__eyebrow { color: #ffdb85; font-weight: 700; letter-spacing: 3px; font-size: 13px; }
.industry-hero h1 { margin: 8px 0 5px; font-size: clamp(30px, 3vw, 43px); line-height: 1.25; letter-spacing: 3px; }
.industry-hero h1 span { color: #ffca5e; }
.industry-hero p { margin: 0 0 16px; color: #e0eee3; letter-spacing: 2px; font-size: 14px; }
.industry-hero__links { display: flex; gap: 11px; flex-wrap: wrap; }
.industry-hero__links a { padding: 10px 17px; border-radius: 7px; background: #f07a24; color: #fff; text-decoration: none; font-weight: 700; }
.industry-hero__links a + a { background: #ffffff25; border: 1px solid #ffffff95; }
.industry-hero__note { position: absolute; right: 13px; bottom: 10px; color: #fff; opacity: .78; font-size: 11px; text-shadow: 0 1px 4px #163a24; }
.dashboard-section-title { display: flex; align-items: end; justify-content: space-between; margin: 16px 0 14px; }
.dashboard-section-title small, .dashboard-chain small { color: #188457; font-weight: 700; letter-spacing: 2px; }
.dashboard-section-title h2, .dashboard-chain h2 { margin: 4px 0 0; font-size: 20px; color: #173b2a; }
.dashboard-section-title a, .dashboard-chain a { color: #087d4c; text-decoration: none; font-weight: 700; font-size: 13px; }
.dashboard-product-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 13px; }
.dashboard-product { display: block; overflow: hidden; background: #fff; border: 1px solid #e4ece5; border-radius: 12px; text-decoration: none; color: #213b2a; box-shadow: 0 4px 15px #17412910; }
.dashboard-product img { display: block; width: 100%; height: 145px; object-fit: cover; }
.dashboard-product__body { padding: 12px 13px; }
.dashboard-product h3 { margin: 0 0 4px; font-size: 15px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.dashboard-product p { margin: 0 0 6px; color: #6b7a70; font-size: 12px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.dashboard-product__enterprise { display: block; color: #75887b; font-size: 12px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.dashboard-product__price { margin-top: 9px; color: #e96318; }
.dashboard-product__price strong { font-size: 20px; }
.dashboard-product__price span { color: #87968b; font-size: 12px; }
.dashboard-feature-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; margin-top: 15px; }
.dashboard-feature-grid > section { margin: 0; overflow: hidden; }
.dashboard-deals { padding: 5px 17px 10px; }
.dashboard-deals__row { display: flex; justify-content: space-between; gap: 8px; padding: 11px 0; border-top: 1px solid #edf1ed; }
.dashboard-deals__row > div { min-width: 0; }
.dashboard-deals__row > div:last-child { flex: 0 0 auto; text-align: right; }
.dashboard-deals__row strong, .dashboard-deals__row span { display: block; }
.dashboard-deals__row strong { color: #254431; font-size: 13px; }
.dashboard-deals__row > div:last-child strong { color: #e96318; }
.dashboard-deals__row span { margin-top: 3px; font-size: 11px; color: #829187; }
.dashboard-chain { display: flex; align-items: center; background: linear-gradient(130deg, #f7fbf8, #fff 62%); }
.dashboard-chain > div { padding: 24px; }
.dashboard-chain p { color: #65776b; line-height: 1.7; font-size: 12px; max-height: 64px; overflow: hidden; }
.dashboard-chain__steps { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; color: #166c47; font-size: 11px; margin: 15px 0; }
.dashboard-chain__steps span { padding: 6px 8px; border-radius: 5px; background: #e9f5ec; }
.dashboard-chain__steps b { color: #d59a4e; }
.dashboard-data-error, .dashboard-empty { padding: 20px; color: #829187; font-size: 13px; }
.dashboard__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.metric-card {
  margin-bottom: 12px;
  padding: 12px 14px;
}

.metric-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.metric-card__label {
  font-size: 12px;
  color: var(--gz-text-sub);
}

.metric-card__value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.metric-card__sub {
  font-size: 12px;
  color: var(--gz-text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dashboard__hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--gz-text-sub);
}
@media (max-width: 1100px) {
  .dashboard-product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dashboard-feature-grid { grid-template-columns: 1fr; }
}
@media (max-width: 650px) {
  .industry-hero { min-height: 205px; background-position: 60% center; }
  .industry-hero__content { padding: 22px; }
  .industry-hero h1 { font-size: 30px; }
  .industry-hero p { font-size: 12px; }
  .dashboard-product img { height: 120px; }
  .dashboard-chain { display: block; }
}
</style>
