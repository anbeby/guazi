<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { http } from '@/api/request'
import { getAccessToken } from '@/utils/auth'
import { useUserStore } from '@/stores/user'

interface ProductCard {
  id: number
  name: string
  spec: string
  grade: string
  origin: string
  price: number
  unit: string
  category: string
  category_code: string
  enterprise: string
  stock: number
  image: string
  enterprise_id?: number
  supply_quantity?: number
  supply_period?: string
  description?: string
  pricing_mode?: string
  supply_status?: string
  allow_inquiry?: boolean
  allow_bulk_purchase?: boolean
  created_at?: string
}
interface EnterpriseCard { id: number; name: string; type: string; region: string; scope: string; image: string }
interface Deal { order_no: string; product: string; quantity: number; amount: number; supplier: string; date: string }
interface PurchaseNeed { id: number; title: string; product_name: string; quantity: number; unit: string; purchase_region: string; buyer_enterprise_name: string; created_at: string; status: string }
interface EnterpriseProfile { id: number; name: string; profile: string; business_scope: string; qualifications: string[]; region: string; address: string; contact_name: string; contact_phone: string; image: string; products: Array<{ id: number; name: string; image: string; origin: string; pricing_mode: string; price: number }> }
interface ShowcaseData {
  park: { name: string; region: string; description: string } | null
  metrics: { enterprise_count: number; product_count: number; trade_amount: number; inventory_quantity: number; order_count: number; requirement_count?: number; match_count?: number }
  products: ProductCard[]
  enterprises: EnterpriseCard[]
  recent_deals: Deal[]
  purchase_needs?: PurchaseNeed[]
}

const route = useRoute()
const userStore = useUserStore()
const authenticated = Boolean(getAccessToken())
const accountTarget = userStore.hasPermission('data:read') ? '/dashboard' : '/account'
const favoriteSaved = ref(false)
const data = ref<ShowcaseData | null>(null)
const loading = ref(true)
const error = ref('')
const keyword = ref('')
const category = ref('全部商品')
const page = computed(() => route.path === '/supply' ? 'hall' : route.path === '/procurement' ? 'procurement' : route.path === '/enterprises' ? 'merchants' : route.path.startsWith('/enterprise/') ? 'enterprise' : route.path.startsWith('/supply/') ? 'item' : route.path === '/industry-news' ? 'news' : route.path === '/matching-service' ? 'service' : route.path === '/purchase/new' ? 'purchase_new' : route.path.startsWith('/inquiry/new/') ? 'inquiry_new' : 'home')
const supplies = ref<ProductCard[]>([])
const purchaseNeeds = ref<PurchaseNeed[]>([])
const enterpriseProfile = ref<EnterpriseProfile | null>(null)
const supplyDetail = ref<ProductCard | null>(null)
const actionMessage = ref('')
const submitting = ref(false)
const purchaseForm = ref({ title: '', product_name: '', quantity: '', unit: 'ton', purchase_region: '', requirements: '', contact_name: '', contact_phone: '' })
const inquiryForm = ref({ quantity: '', delivery_address: '', remark: '' })
const categories = computed(() => ['全部商品', ...new Set((page.value === 'hall' ? supplies.value : data.value?.products || []).map((p) => p.category))])
const filteredProducts = computed(() => (page.value === 'hall' ? supplies.value : data.value?.products || []).filter((p) =>
  (category.value === '全部商品' || p.category === category.value) &&
  (!keyword.value || `${p.name}${p.enterprise}${p.spec}`.includes(keyword.value.trim()))
))
const selectedProduct = computed(() => supplyDetail.value || data.value?.products.find((p) => p.id === Number(route.params.id)))
const money = (value: number) => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value || 0)
const enterpriseType = (enterprise: EnterpriseCard) => {
  if (enterprise.type === 'supplier') return '供应企业'
  if (enterprise.type === 'buyer') return '采购企业'
  const scope = enterprise.scope || ''
  if (scope.includes('加工') || scope.includes('烘炒')) return '加工企业'
  if (scope.includes('贸易')) return '贸易企业'
  if (scope.includes('仓储')) return '仓储企业'
  return '产业企业'
}
const gradeLabel = (grade: string) => ({ special: '特级', first: '一级', second: '二级', mixed: '统货' }[grade] || grade)
const hasEnterprisePhoto = (enterprise: EnterpriseCard) => Boolean(enterprise.image && !enterprise.image.startsWith('/demo/'))
const unitName = (unit: string) => ({ ton: '吨', kg: '千克', bag: '袋', piece: '件' }[unit] || unit)
const priceText = (product: ProductCard) => product.pricing_mode === 'inquiry' ? '面议' : product.pricing_mode === 'negotiable' ? '协商价' : `¥${money(product.price)}`
const dateText = (value?: string) => value ? value.slice(0, 10) : '—'

async function publicData<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const result = await response.json()
  if (result.code !== 0) throw new Error(result.message || '数据加载失败')
  return result.data as T
}

async function expressInterest(need: PurchaseNeed): Promise<void> {
  if (!getAccessToken()) { window.location.href = `/login?redirect=${encodeURIComponent('/procurement')}`; return }
  try {
    await http.post(`/marketplace/requirements/${need.id}/interest`)
    ElMessage.success('供货意向已提交，平台运营人员将联系双方')
  } catch { /* 统一请求层显示业务错误 */ }
}

async function saveFavorite(productId: number): Promise<void> {
  if (!getAccessToken()) { window.location.href = `/login?redirect=${encodeURIComponent(`/supply/${productId}`)}`; return }
  try {
    await http.post(`/portal/me/favorites/${productId}`)
    favoriteSaved.value = true
    ElMessage.success('已收藏到我的供应信息')
  } catch { /* 请求层展示错误 */ }
}

async function submitPurchase(): Promise<void> {
  if (!getAccessToken()) { window.location.href = `/login?redirect=${encodeURIComponent('/purchase/new')}`; return }
  submitting.value = true
  try {
    const result = await http.post<{ id: number }>('/marketplace/requirements', { ...purchaseForm.value, quantity: Number(purchaseForm.value.quantity) })
    actionMessage.value = `采购需求已提交审核，编号 #${result.id}。审核通过后将在采购大厅公开。`
  } catch { /* 统一请求层显示业务错误 */ }
  finally { submitting.value = false }
}

async function submitInquiry(): Promise<void> {
  if (!getAccessToken()) { window.location.href = `/login?redirect=${encodeURIComponent(route.fullPath)}`; return }
  if (!selectedProduct.value) return
  if (selectedProduct.value.supply_status !== 'active' || selectedProduct.value.allow_inquiry === false) {
    ElMessage.warning('该供应信息当前不接受询价')
    return
  }
  submitting.value = true
  try {
    const result = await http.post<{ inquiry_no: string }>('/inquiries', {
      product_id: selectedProduct.value.id, supplier_enterprise_id: selectedProduct.value.enterprise_id,
      quantity: Number(inquiryForm.value.quantity), unit: selectedProduct.value.unit,
      delivery_address: inquiryForm.value.delivery_address, remark: inquiryForm.value.remark, submit: true
    })
    actionMessage.value = `询价已提交，单号 ${result.inquiry_no}。供应企业可在平台内报价。`
  } catch { /* 统一请求层显示业务错误 */ }
  finally { submitting.value = false }
}

onMounted(async () => {
  try {
    data.value = await publicData<ShowcaseData>('/showcase')
    if (page.value === 'hall') {
      const result = await publicData<{ items: ProductCard[] }>('/marketplace/supplies?page_size=60')
      supplies.value = result.items
    }
    if (page.value === 'procurement') {
      const result = await publicData<{ items: PurchaseNeed[] }>('/marketplace/requirements?page_size=60')
      purchaseNeeds.value = result.items
    }
    if (page.value === 'enterprise') enterpriseProfile.value = await publicData<EnterpriseProfile>(`/marketplace/enterprises/${route.params.id}`)
    if (page.value === 'item' || page.value === 'inquiry_new') supplyDetail.value = await publicData<ProductCard>(`/marketplace/supplies/${route.params.id}`)
    if (page.value === 'item' && getAccessToken()) {
      try {
        const rows = await http.get<{ items: Array<{ product_id: number }> }>('/portal/me/favorites')
        favoriteSaved.value = rows.items.some(item => item.product_id === Number(route.params.id))
      } catch { /* 公开供应详情仍可浏览 */ }
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '数据加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="showcase">
    <header class="site-header">
      <a class="brand" href="/">
        <img class="brand-mark" src="/static/images/logo/platform-mark.svg" alt="" />
        <span><strong>第十师瓜子油料数字化交易平台</strong><small>产地直供 · 数字交易 · 服务全国</small></span>
      </a>
      <nav class="site-nav" aria-label="平台导航">
        <a href="/" :class="{ active: page === 'home' }">首页</a>
        <a href="/supply" :class="{ active: page === 'hall' || page === 'item' || page === 'inquiry_new' }">供应大厅</a>
        <a href="/procurement" :class="{ active: page === 'procurement' || page === 'purchase_new' }">采购大厅</a>
        <a href="/enterprises" :class="{ active: page === 'merchants' || page === 'enterprise' }">企业展示</a>
        <a href="/industry-news" :class="{ active: page === 'news' }">产业资讯</a>
        <a href="/matching-service" :class="{ active: page === 'service' }">撮合服务</a>
      </nav>
      <a class="header-login" :href="authenticated ? accountTarget : '/login?redirect=/account'">{{ authenticated ? (accountTarget === '/dashboard' ? '进入工作台' : '我的需求') : '登录 / 注册' }} <span>→</span></a>
    </header>

    <div v-if="loading" class="state-box">正在读取产业数据…</div>
    <div v-else-if="error" class="state-box">暂时无法读取平台数据：{{ error }}<small>请稍后重试，或联系屯云大数据技术支持。</small></div>
    <template v-else-if="data">
      <section v-if="page === 'home' || page === 'hall' || page === 'procurement' || page === 'merchants'" class="hero" :class="{ 'hero--compact': page !== 'home' }">
        <div class="hero-content">
          <span class="eyebrow">第十师 · 北屯瓜子产业</span>
          <h1>北屯瓜子 <em>香飘全国</em></h1>
          <p>产业资源展示 · 供需信息撮合 · 交易服务入口</p>
          <div class="hero-actions">
            <a href="/supply" class="button button--orange">查看供应信息 <span>→</span></a>
            <a href="/procurement" class="button button--glass">查看采购需求</a>
            <a href="/consult" class="button button--glass">留下需求</a>
          </div>
        </div>
      </section>

      <main class="site-main">
        <template v-if="page === 'home'">
          <section class="metrics" aria-label="产业数据">
            <div><span>入驻企业</span><strong>{{ money(data.metrics.enterprise_count) }}</strong><small>家产业链主体</small></div>
            <div><span>供应信息</span><strong>{{ money(data.metrics.product_count) }}</strong><small>条已审核供应信息</small></div>
            <div><span>采购需求</span><strong>{{ money(data.metrics.requirement_count || 0) }}</strong><small>条平台采购需求</small></div>
            <div><span>撮合记录</span><strong>{{ money(data.metrics.match_count || 0) }}</strong><small>次人工供需对接</small></div>
          </section>

          <section class="intro-card">
            <img src="/demo/park.png" alt="瓜子油料加工园区场景示意" loading="lazy" decoding="async" />
            <div><span class="section-kicker">产业集聚 · 源头供给</span><h2>{{ data.park?.name || '北屯瓜子油料产业园' }}</h2>
              <p>{{ data.park?.description || '汇集种植、加工、仓储与贸易企业，连接产地货源和全国采购需求。' }}</p>
              <a href="/enterprises">了解入驻企业 →</a>
            </div>
          </section>

          <section class="section-head"><div><span class="section-kicker">源头货源 · 企业直供</span><h2>供应大厅</h2></div><a href="/supply">查看全部供应 →</a></section>
          <div class="supply-grid"><article v-for="product in data.products.filter(p => p.supply_status !== 'paused' && p.supply_status !== 'completed').slice(0, 6)" :key="product.id" class="supply-card">
            <img :src="product.image || '/demo/sunflower.png'" :alt="product.name" loading="lazy" decoding="async" />
            <div><span class="supply-card__status">供应中</span><h3>{{ product.name }}</h3><p>{{ product.enterprise }}</p><dl><div><dt>产地</dt><dd>{{ product.origin || '待补充' }}</dd></div><div><dt>供应量</dt><dd>{{ money(product.supply_quantity || product.stock) }} {{ unitName(product.unit) }}</dd></div><div><dt>发布时间</dt><dd>{{ dateText(product.created_at) }}</dd></div></dl><a :href="`/supply/${product.id}`">查看详情 →</a><a :href="`/consult?product_id=${product.id}`">立即咨询</a></div>
          </article></div>

          <section class="section-head"><div><span class="section-kicker">采购寻源 · 平台撮合</span><h2>采购大厅</h2></div><a href="/procurement">查看采购大厅 →</a></section>
          <div v-if="data.purchase_needs?.length" class="need-grid"><article v-for="need in data.purchase_needs.slice(0, 3)" :key="need.id" class="need-card"><span>采购中</span><h3>{{ need.title }}</h3><p>采购产品：{{ need.product_name }}</p><p>需求数量：{{ money(need.quantity) }} {{ unitName(need.unit) }}</p><p>采购地区：{{ need.purchase_region || '待协商' }}</p><small>发布时间：{{ dateText(need.created_at) }}</small><a href="/procurement">我要供应 →</a></article></div>
          <div v-else class="portal-quiet">当前暂无公开采购需求。可留下采购计划，平台运营人员将协助匹配供应方。<a href="/consult?action=purchase">留下需求 →</a></div>

          <section class="section-head"><div><span class="section-kicker">产业链伙伴</span><h2>入驻企业</h2></div><a href="/enterprises">查看全部企业 →</a></section>
          <div class="enterprise-grid">
            <a v-for="enterprise in data.enterprises.slice(0, 4)" :key="enterprise.id" class="enterprise-card" :href="`/enterprise/${enterprise.id}`">
              <img v-if="hasEnterprisePhoto(enterprise)" :src="enterprise.image" :alt="enterprise.name" loading="lazy" decoding="async" />
              <div v-else class="enterprise-card__identity"><img src="/static/images/logo/platform-mark.svg" alt="" /><span>{{ enterpriseType(enterprise) }}</span></div>
              <div><span>{{ enterpriseType(enterprise) }}</span><h3>{{ enterprise.name }}</h3><p>{{ enterprise.region }}</p></div>
            </a>
          </div>
        </template>

        <template v-else-if="page === 'hall'">
          <section class="section-head section-head--first"><div><span class="section-kicker">产地货源 · 供应能力</span><h2>供应大厅</h2></div><span>共 {{ supplies.length }} 条供应信息</span></section>
          <div class="hall-layout"><div>
            <div class="filters"><input v-model="keyword" placeholder="搜索产品、产地或供应企业" aria-label="搜索供应" /><div class="category-list"><button v-for="item in categories" :key="item" :class="{ selected: category === item }" @click="category = item">{{ item }}</button></div></div>
            <div class="supply-grid supply-grid--hall"><article v-for="product in filteredProducts" :key="product.id" class="supply-card"><img :src="product.image || '/demo/sunflower.png'" :alt="product.name" loading="lazy" decoding="async" /><div><span class="supply-card__status">供应中</span><h3>{{ product.name }}</h3><p>{{ product.enterprise }}</p><dl><div><dt>产地</dt><dd>{{ product.origin || '待补充' }}</dd></div><div><dt>供应量</dt><dd>{{ money(product.supply_quantity || product.stock) }} {{ unitName(product.unit) }}</dd></div><div><dt>发布时间</dt><dd>{{ dateText(product.created_at) }}</dd></div></dl><a :href="`/supply/${product.id}`">查看详情 →</a><a :href="`/consult?product_id=${product.id}`">立即咨询</a></div></article></div>
            <div v-if="filteredProducts.length === 0" class="empty empty--search">
              <span class="empty__symbol" aria-hidden="true">⌕</span>
              <h3>没有找到符合条件的供应信息</h3>
              <p>试试其他产品名称、企业或分类。</p>
              <button type="button" @click="keyword = ''; category = '全部商品'">查看全部供应</button>
            </div>
          </div><aside class="hall-side"><div class="side-card"><h3>撮合服务</h3><p>按供应能力、产地和采购要求寻找合适企业。平台运营人员协助双方联系。</p><a href="/consult">留下需求 →</a></div><div class="side-card"><h3>供应企业</h3><p v-for="enterprise in data.enterprises.filter((e) => e.type !== 'buyer').slice(0, 6)" :key="enterprise.id"><a :href="`/enterprise/${enterprise.id}`">{{ enterprise.name }}</a></p></div></aside></div>
        </template>

        <template v-else-if="page === 'procurement'">
          <section class="section-head section-head--first"><div><span class="section-kicker">产业采购 · 平台撮合</span><h2>采购大厅</h2></div><a href="/consult?action=purchase">留下采购需求 →</a></section>
          <p class="portal-lead">认证企业可<a href="/purchase/new">发布公开采购需求</a>；游客可直接<a href="/consult?action=purchase">留下需求</a>，由平台协助寻找货源。供应企业可以对公开采购需求表达供货意向。</p>
          <div v-if="purchaseNeeds.length" class="need-grid need-grid--hall"><article v-for="need in purchaseNeeds" :key="need.id" class="need-card"><span>采购中</span><h3>{{ need.title }}</h3><p>采购产品：{{ need.product_name }}</p><p>需求数量：{{ money(need.quantity) }} {{ unitName(need.unit) }}</p><p>采购地区：{{ need.purchase_region || '待协商' }}</p><small>发布时间：{{ dateText(need.created_at) }}</small><button type="button" @click="expressInterest(need)">我要供应 →</button></article></div>
          <div v-else class="portal-quiet">暂无公开采购需求。<a href="/consult?action=purchase">留下需求 →</a></div>
        </template>

        <template v-else-if="page === 'merchants'">
          <section class="section-head section-head--first"><div><span class="section-kicker">从田间到市场</span><h2>企业展示</h2></div><span>已入驻 {{ data.metrics.enterprise_count }} 家</span></section>
          <div class="enterprise-grid enterprise-grid--all"><a v-for="enterprise in data.enterprises" :key="enterprise.id" class="enterprise-card" :href="`/enterprise/${enterprise.id}`"><img v-if="hasEnterprisePhoto(enterprise)" :src="enterprise.image" :alt="enterprise.name" loading="lazy" decoding="async" /><div v-else class="enterprise-card__identity"><img src="/static/images/logo/platform-mark.svg" alt="" /><span>{{ enterpriseType(enterprise) }}</span></div><div><span>{{ enterpriseType(enterprise) }}</span><h3>{{ enterprise.name }}</h3><p>{{ enterprise.scope }}</p><small>{{ enterprise.region }} · 查看企业主页 →</small></div></a></div>
        </template>

        <template v-else-if="page === 'enterprise'">
          <section v-if="enterpriseProfile" class="enterprise-profile"><a class="back-link" href="/enterprises">← 返回企业展示</a><div class="enterprise-profile__hero"><img v-if="enterpriseProfile.image" :src="enterpriseProfile.image" :alt="enterpriseProfile.name" /><div v-else class="enterprise-card__identity"><img src="/static/images/logo/platform-mark.svg" alt="" /><span>产业企业</span></div><div><span class="section-kicker">第十师 · 产业链企业</span><h1>{{ enterpriseProfile.name }}</h1><p>{{ enterpriseProfile.profile || '企业简介待完善' }}</p><small>{{ enterpriseProfile.region }} {{ enterpriseProfile.address }}</small></div></div><div class="enterprise-profile__sections"><article><h2>主营业务</h2><p>{{ enterpriseProfile.business_scope || '待完善' }}</p></article><article><h2>企业资质</h2><p v-if="!enterpriseProfile.qualifications.length">资质信息待完善</p><p v-for="qualification in enterpriseProfile.qualifications" :key="qualification">{{ qualification }}</p></article><article><h2>联系方式</h2><p>{{ enterpriseProfile.contact_name || '联系人待完善' }} · {{ enterpriseProfile.contact_phone || '电话待完善' }}</p><a :href="`/consult?enterprise_id=${enterpriseProfile.id}&action=contact`">联系这家企业 →</a></article></div><div class="section-head"><div><span class="section-kicker">企业供应</span><h2>供应产品</h2></div></div><div class="enterprise-profile__products"><a v-for="product in enterpriseProfile.products" :key="product.id" :href="`/supply/${product.id}`">{{ product.name }} <span>查看供应 →</span></a><p v-if="!enterpriseProfile.products.length">暂无公开供应信息</p></div></section>
        </template>

        <template v-else-if="page === 'item'">
          <div v-if="selectedProduct" class="detail"><a class="back-link" href="/supply">← 返回供应大厅</a><div class="detail-top"><img :src="selectedProduct.image || '/demo/sunflower.png'" :alt="selectedProduct.name" /><div><span class="section-kicker">{{ selectedProduct.category }} · {{ selectedProduct.origin }}</span><h1>{{ selectedProduct.name }}</h1><p class="detail-spec">{{ selectedProduct.spec }}</p><div class="detail-price">{{ priceText(selectedProduct) }} <span v-if="selectedProduct.pricing_mode === 'listed'">/{{ unitName(selectedProduct.unit) }}</span></div><div class="detail-facts"><p>供应企业 <strong><a :href="`/enterprise/${selectedProduct.enterprise_id}`">{{ selectedProduct.enterprise }}</a></strong></p><p>供应数量 <strong>{{ money(selectedProduct.supply_quantity || selectedProduct.stock) }} {{ unitName(selectedProduct.unit) }}</strong></p><p>供应周期 <strong>{{ selectedProduct.supply_period || '以双方商议为准' }}</strong></p><p>产地 <strong>{{ selectedProduct.origin || '待补充' }}</strong></p><p>价格方式 <strong>{{ selectedProduct.pricing_mode === 'inquiry' ? '询价' : selectedProduct.pricing_mode === 'negotiable' ? '协商' : '挂牌价' }}</strong></p><p>供应状态 <strong>{{ selectedProduct.supply_status === 'paused' ? '已暂停' : selectedProduct.supply_status === 'completed' ? '已完成' : '供应中' }}</strong></p></div><div class="detail-actions" v-if="selectedProduct.supply_status === 'active'"><a class="button button--orange" :href="`/consult?product_id=${selectedProduct.id}`">立即咨询</a><a class="button button--glass" :href="`/consult?product_id=${selectedProduct.id}&action=contact`">联系供应商</a><a class="button button--glass" :href="`/consult?product_id=${selectedProduct.id}&action=purchase`">提交采购需求</a><button class="button button--glass" type="button" :disabled="favoriteSaved" @click="saveFavorite(selectedProduct.id)">{{ favoriteSaved ? '已收藏' : '收藏供应' }}</button></div></div></div><div class="detail-note"><h2>产品介绍</h2><p>{{ selectedProduct.description || '该供应信息暂无详细产品介绍，可通过咨询向供应企业了解规格和交期。' }}</p><p>具体商务条件由供需双方沟通确认。</p></div></div>
          <div v-else class="empty empty--search"><span class="empty__symbol" aria-hidden="true">⌕</span><h3>该供应信息不存在或未公开</h3><p>可以返回供应大厅查看当前货源。</p><a href="/supply">返回供应大厅</a></div>
        </template>

        <template v-else-if="page === 'news'"><section class="portal-info"><span class="section-kicker">产业动态</span><h1>产业资讯</h1><p>资讯栏目正在整理第十师瓜子油料产业的公开信息。当前暂无经过审核的资讯内容。</p><a href="/supply">查看供应大厅 →</a></section></template>
        <template v-else-if="page === 'service'"><section class="portal-info"><span class="section-kicker">供需对接 · 人工服务</span><h1>撮合服务</h1><p>任何访客都可以留下合作需求。平台运营人员核对需求、联系认证企业并记录跟进结果；企业认证后可发布公开供需信息。</p><div class="service-steps"><span>留下需求</span><span>平台匹配</span><span>人工联系</span><span>记录结果</span></div><div class="detail-actions"><a class="button button--orange" href="/consult">无需注册，留下需求</a><a class="button button--glass" href="/procurement">查看采购大厅</a><a class="button button--glass" href="/account">申请企业身份</a></div></section></template>
        <template v-else-if="page === 'purchase_new'"><section class="portal-form"><a class="back-link" href="/procurement">← 返回采购大厅</a><span class="section-kicker">认证企业 · 公开采购</span><h1>发布采购需求</h1><p>认证企业提交后由平台审核，审核通过才会在采购大厅公开。游客和普通用户可<a href="/consult?action=purchase">直接留下需求</a>。</p><div v-if="actionMessage" class="portal-success">{{ actionMessage }} <a href="/account">查看审核进度</a></div><form v-else @submit.prevent="submitPurchase"><label>需求名称<input v-model="purchaseForm.title" required minlength="2" maxlength="160" placeholder="例如：采购北屯葵花籽原料" /></label><label>采购产品<input v-model="purchaseForm.product_name" required minlength="2" maxlength="160" placeholder="产品名称" /></label><label>采购数量<input v-model="purchaseForm.quantity" required type="number" min="0.001" step="0.001" placeholder="数量" /></label><label>单位<select v-model="purchaseForm.unit"><option value="ton">吨</option><option value="kg">千克</option><option value="bag">袋</option></select></label><label>采购地区<input v-model="purchaseForm.purchase_region" maxlength="128" placeholder="例如：新疆" /></label><label>联系人<input v-model="purchaseForm.contact_name" required minlength="2" maxlength="64" /></label><label>联系方式<input v-model="purchaseForm.contact_phone" required minlength="5" maxlength="32" /></label><label class="portal-form__wide">采购要求<textarea v-model="purchaseForm.requirements" maxlength="2000" rows="4" placeholder="规格、质量、交付周期等要求" /></label><button class="button button--orange" :disabled="submitting">{{ submitting ? '提交中…' : '提交审核' }}</button></form></section></template>
        <template v-else-if="page === 'inquiry_new'"><section class="portal-form"><a class="back-link" :href="`/supply/${route.params.id}`">← 返回供应详情</a><span class="section-kicker">供应信息 · 在线询价</span><h1>向供应企业询价</h1><p v-if="selectedProduct">{{ selectedProduct.name }} · {{ selectedProduct.enterprise }}</p><div v-if="actionMessage" class="portal-success">{{ actionMessage }} <a href="/supply">返回供应大厅</a></div><p v-else-if="selectedProduct && (selectedProduct.supply_status !== 'active' || selectedProduct.allow_inquiry === false)" class="portal-quiet">该供应信息当前不接受询价。<a href="/supply">查看其他供应信息 →</a></p><form v-else @submit.prevent="submitInquiry"><label>询价数量<input v-model="inquiryForm.quantity" required type="number" min="0.001" step="0.001" placeholder="请输入数量" /></label><label>交付地区<input v-model="inquiryForm.delivery_address" maxlength="255" placeholder="可选" /></label><label class="portal-form__wide">补充要求<textarea v-model="inquiryForm.remark" maxlength="255" rows="4" placeholder="规格、包装、交期等" /></label><button class="button button--orange" :disabled="submitting || !selectedProduct">{{ submitting ? '提交中…' : '提交询价' }}</button></form></section></template>

        <section v-if="page === 'home'" class="portal-info portal-info--home"><span class="section-kicker">产业服务入口</span><h2>让供需信息更快找到合适的企业</h2><p>平台汇聚第十师瓜子油料产业资源，由运营人员协助供需双方开展商务对接。既有询价和订单能力作为后续交易服务基础。</p><a href="/matching-service">了解撮合服务 →</a></section>
      </main>
    </template>

    <footer class="site-footer"><strong>© 2026 第十师瓜子油料数字化交易平台</strong><span>北屯产地直供 · 数字交易 · 产业协同</span><small>技术支持：屯云大数据</small></footer>
  </div>
</template>

<style scoped>
.showcase{min-height:100vh;background:#f4f8f6;color:#17332a;font-family:'Microsoft YaHei','PingFang SC',sans-serif}.site-header{height:76px;background:#fff;display:flex;align-items:center;gap:38px;padding:0 max(4%,calc((100vw - 1460px)/2));box-shadow:0 2px 14px #133b2410;position:relative;z-index:2}.brand{display:flex;align-items:center;gap:12px;color:#133e2b;text-decoration:none;min-width:300px}.brand-mark{display:grid;place-items:center;width:43px;height:43px;border-radius:50%;color:#fff;background:linear-gradient(135deg,#079044,#ffb51d);font-size:33px}.brand strong{display:block;font-size:17px;white-space:nowrap}.brand small{display:block;letter-spacing:2px;font-size:10px;color:#72837b;margin-top:3px}.site-nav{display:flex;gap:30px;align-items:center;flex:1}.site-nav a{white-space:nowrap;text-decoration:none;color:#42554a;font-size:15px;font-weight:600;padding:27px 0 24px}.site-nav a.active{color:#008b51;border-bottom:3px solid #008b51}.header-login{white-space:nowrap;text-decoration:none;color:#04764b;font-weight:700;border:1px solid #b8dec8;padding:10px 16px;border-radius:8px}.header-login span{margin-left:8px}.hero{height:430px;background:linear-gradient(90deg,#f1f8eeed 0%,#e8f4e1ad 37%,#ffffff00 67%),url('/demo/hero.png') center 52%/cover;display:flex;align-items:center}.hero--compact{height:300px}.hero-content{width:min(1400px,92%);margin:auto}.eyebrow,.section-kicker{color:#008f54;font-weight:800;letter-spacing:3px;font-size:13px}.hero h1{font-family:'STKaiti','KaiTi',serif;color:#084a2c;font-size:clamp(36px,4.5vw,70px);letter-spacing:6px;margin:15px 0 8px;text-shadow:0 2px 12px #fffc}.hero h1 em{font-style:normal}.hero p{font-size:19px;letter-spacing:4px;color:#194d32;margin:0 0 30px}.hero-actions{display:flex;gap:12px}.button{display:inline-flex;align-items:center;justify-content:center;gap:18px;text-decoration:none;border-radius:9px;padding:13px 23px;font-weight:800}.button--orange{color:#fff;background:#fa650c;box-shadow:0 8px 18px #e7622f55}.button--glass{background:#ffffffd9;color:#087247;border:1px solid #a7d3b8}.site-main{width:min(1400px,92%);margin:auto}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:-35px 0 48px;position:relative}.metrics div{background:#fff;box-shadow:0 10px 28px #16472c17;border-radius:15px;padding:21px 24px;border-top:3px solid #0ba45e}.metrics span,.metrics small{display:block;color:#62796c}.metrics strong{font-size:32px;color:#075739;display:block;margin:6px 0}.intro-card{display:grid;grid-template-columns:43% 1fr;background:#fff;overflow:hidden;border-radius:18px;box-shadow:0 8px 28px #16472c12;margin:0 0 48px}.intro-card img{width:100%;height:260px;object-fit:cover}.intro-card>div{padding:40px}.intro-card h2{font-size:29px;margin:10px 0}.intro-card p{color:#66746e;font-size:15px;line-height:1.9;max-width:620px}.intro-card a,.section-head a{color:#00894e;text-decoration:none;font-weight:800}.section-head{display:flex;justify-content:space-between;align-items:end;margin:44px 0 19px}.section-head--first{margin-top:48px}.section-head h2{font-size:29px;margin:4px 0 0;color:#173c2a}.section-head>span{color:#67766e}.product-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:17px}.product-card{text-decoration:none;color:inherit;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 5px 20px #1c493014;transition:transform .2s,box-shadow .2s}.product-card:hover{transform:translateY(-4px);box-shadow:0 12px 28px #1c49302b}.product-card img{width:100%;height:205px;object-fit:cover}.product-body{padding:16px}.product-category{color:#058a50;background:#e9f8ef;border-radius:4px;padding:3px 7px;font-size:12px}.product-body h3{font-size:18px;margin:10px 0 5px}.product-body p{color:#586b60;font-size:13px;height:19px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;margin:0 0 7px}.product-meta{font-size:12px;color:#84938a;height:19px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.product-price{display:flex;align-items:baseline;gap:3px;margin-top:13px}.product-price strong{color:#f05a12;font-size:24px}.product-price span{color:#839087;font-size:12px}.stock-line{border-top:1px solid #edf1ec;margin-top:12px;padding-top:10px;color:#19714a;font-size:12px;display:flex;justify-content:space-between}.enterprise-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:17px}.enterprise-grid--all{grid-template-columns:repeat(3,1fr);margin-bottom:60px}.enterprise-card{background:#fff;overflow:hidden;border-radius:14px;box-shadow:0 5px 20px #1c493014}.enterprise-card img{width:100%;height:150px;object-fit:cover}.enterprise-card>div{padding:16px}.enterprise-card span{font-size:12px;color:#057b4a}.enterprise-card h3{font-size:17px;margin:7px 0}.enterprise-card p,.enterprise-card small{font-size:12px;color:#718178;line-height:1.6}.deal-section{margin-bottom:55px}.deal-table{background:#fff;border-radius:14px;padding:4px 20px}.deal-table>div{display:grid;grid-template-columns:1.5fr 2fr .7fr .9fr .8fr;gap:14px;align-items:center;padding:15px 0;border-bottom:1px solid #edf2ee;font-size:13px}.deal-table>div:last-child{border:0}.deal-table b{color:#f26419}.deal-table small{color:#83938a}.hall-layout{display:grid;grid-template-columns:minmax(0,1fr) 275px;gap:20px;margin-bottom:60px}.hall-layout .product-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.filters,.side-card{background:#fff;border-radius:13px;padding:17px;margin-bottom:18px}.filters input{width:100%;border:1px solid #d5e4d8;border-radius:8px;font-size:15px;padding:12px 15px;box-sizing:border-box}.category-list{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.category-list button{border:1px solid #dcebe0;background:white;color:#4a6353;padding:7px 12px;border-radius:20px;cursor:pointer}.category-list button.selected{background:#098b52;color:white;border-color:#098b52}.side-card h3{margin:0 0 15px;border-left:4px solid #0aa05c;padding-left:10px}.side-card p{padding:9px 0;border-bottom:1px solid #eef2ef;font-size:13px}.deal{display:grid;gap:4px;border-bottom:1px solid #edf1ec;padding:11px 0}.deal strong{font-size:13px}.deal small{color:#87958b}.deal span{color:#e9631c;font-size:12px}.detail{margin:40px 0 60px}.back-link{color:#0d8d56;text-decoration:none}.detail-top{display:grid;grid-template-columns:47% 1fr;gap:40px;background:#fff;padding:25px;border-radius:16px;margin-top:18px}.detail-top>img{width:100%;height:480px;object-fit:cover;border-radius:12px}.detail-top h1{font-size:34px}.detail-spec{color:#6a7d71}.detail-price{color:#ed5e14;font-size:37px;font-weight:800;margin:25px 0}.detail-price span{font-size:15px;color:#818d83}.detail-facts{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:30px}.detail-facts p{background:#f4f8f5;border-radius:9px;padding:13px;color:#637769}.detail-facts strong{display:block;color:#163d2a;margin-top:7px}.detail-note{background:#fff;border-radius:14px;padding:20px 26px;margin-top:20px}.detail-note p{color:#6d7d70}.site-footer{background:#123d2c;color:#fff;padding:30px 5%;display:flex;align-items:center;gap:30px;flex-wrap:wrap}.site-footer span{opacity:.8}.site-footer small{margin-left:auto;opacity:.6}.state-box,.empty{padding:60px;text-align:center;color:#678174}
@media(max-width:1000px){.site-header{gap:18px;padding:0 3%}.brand{min-width:0}.brand small{display:none}.site-nav{gap:12px}.product-grid,.hall-layout .product-grid{grid-template-columns:repeat(2,1fr)}.enterprise-grid,.enterprise-grid--all{grid-template-columns:repeat(2,1fr)}.hall-layout{grid-template-columns:1fr}.hall-side{display:grid;grid-template-columns:1fr 1fr;gap:15px}}
@media(max-width:650px){.site-header{height:auto;min-height:65px;display:grid;grid-template-columns:1fr auto;gap:0;padding:9px 15px}.brand strong{font-size:13px}.brand-mark{width:34px;height:34px;font-size:25px}.site-nav{grid-column:1/3;order:3;overflow-x:auto;gap:20px}.site-nav a{padding:13px 0;font-size:12px}.header-login{font-size:12px;padding:7px}.hero,.hero--compact{height:310px;background-position:58% center}.hero h1{font-size:34px;letter-spacing:1px}.hero p{font-size:12px;letter-spacing:1px}.hero-actions{gap:7px}.button{font-size:12px;padding:11px}.site-main{width:94%}.metrics{grid-template-columns:repeat(2,1fr);gap:8px;margin:-20px 0 25px}.metrics div{padding:13px}.metrics strong{font-size:23px}.metrics span,.metrics small{font-size:11px}.intro-card{display:block}.intro-card img{height:145px}.intro-card>div{padding:19px}.intro-card h2{font-size:19px}.section-head h2{font-size:22px}.product-grid,.hall-layout .product-grid,.enterprise-grid,.enterprise-grid--all{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.product-card img{height:135px}.product-body{padding:9px}.product-body h3{font-size:14px}.product-body p,.product-meta{font-size:11px}.product-price strong{font-size:18px}.enterprise-card img{height:100px}.enterprise-card>div{padding:9px}.enterprise-card h3{font-size:13px}.hall-side{display:block}.deal-table>div{grid-template-columns:1fr 1fr}.deal-table>div span,.deal-table>div small{display:none}.detail-top{display:block;padding:10px}.detail-top>img{height:290px}.detail-top>div{padding:15px}.detail-top h1{font-size:25px}.detail-facts{gap:5px}.site-footer{display:block}.site-footer>*{display:block;margin:7px 0}}
.brand-mark { object-fit: contain; background: none; border-radius: 50%; font-size: 0; }
.enterprise-card__identity { height: 150px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 9px; background: linear-gradient(145deg, #e8f4ec, #f5faf5); color: #236444; }
.enterprise-card__identity img { width: 38px; height: 38px; object-fit: contain; }
.enterprise-card__identity span { font-size: 12px; font-weight: 700; letter-spacing: 1px; }
.state-box small { display: block; margin-top: 10px; color: #6b8372; }
.empty--search { margin-top: 18px; padding: 38px 18px; background: #fff; border: 1px solid #e0ece3; border-radius: 14px; }
.empty--search .empty__symbol { display: block; width: 52px; height: 52px; margin: 0 auto 12px; border-radius: 50%; background: #eaf5ed; color: #167848; font-size: 42px; line-height: 47px; }
.empty--search h3 { margin: 0 0 7px; color: #234735; font-size: 17px; }
.empty--search p { margin: 0 auto 17px; max-width: 360px; font-size: 13px; line-height: 1.6; }
.empty--search button, .empty--search a { display: inline-block; padding: 9px 18px; border: 0; border-radius: 8px; background: #116c43; color: #fff; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; }
.empty--search button:hover, .empty--search a:hover { background: #0c5836; }
.enterprise-card { display: block; color: inherit; text-decoration: none; }
.supply-grid,.need-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 16px; }
.supply-grid--hall { grid-template-columns: repeat(2,minmax(0,1fr)); }
.supply-card,.need-card { min-width: 0; background: #fff; border: 1px solid #e2ece4; border-radius: 14px; overflow: hidden; box-shadow: 0 5px 20px #1c493014; }
.supply-card { display: grid; grid-template-columns: 118px minmax(0,1fr); }
.supply-card>img { width: 118px; height: 100%; min-height: 224px; object-fit: cover; }
.supply-card>div { padding: 16px; }
.supply-card__status,.need-card>span { display: inline-block; color: #0b7848; background: #e8f7ec; border-radius: 5px; padding: 3px 8px; font-size: 11px; font-weight: 700; }
.supply-card h3,.need-card h3 { margin: 9px 0 6px; color: #173c2a; font-size: 17px; }
.supply-card p,.need-card p { margin: 5px 0; color: #61786a; font-size: 12px; }
.supply-card dl { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin: 12px 0; }
.supply-card dl>div:last-child { grid-column: 1/-1; }
.supply-card dt { color: #85968a; font-size: 11px; }
.supply-card dd { margin: 2px 0 0; color: #254a34; font-size: 12px; font-weight: 700; }
.supply-card a,.need-card a,.need-card button,.portal-quiet a,.portal-info a { display: inline-block; margin: 7px 12px 0 0; color: #087d4b; background: none; border: 0; padding: 0; text-decoration: none; font-size: 13px; font-weight: 800; cursor: pointer; }
.need-card { padding: 20px; }
.need-card small { display: block; margin-top: 10px; color: #84958a; }
.need-grid--hall { margin-bottom: 60px; }
.portal-lead { margin: 0 0 20px; color: #60776a; }
.portal-quiet { padding: 36px; margin: 12px 0 45px; background: #fff; border: 1px dashed #c8dfce; border-radius: 14px; color: #597463; }
.enterprise-profile,.portal-info,.portal-form { margin: 36px 0 60px; }
.portal-form > .back-link { display: block; width: fit-content; margin-bottom: 18px; }
.portal-form > .section-kicker { display: block; }
.detail-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 22px; }
.detail-actions button { border: 1px solid #b8d9c4; cursor: pointer; }
.detail-actions button:disabled { opacity: .6; cursor: default; }
@media(max-width:650px) { .detail-actions { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); } .detail-actions .button { text-align: center; padding: 11px 6px; } }
.enterprise-profile__hero { display: grid; grid-template-columns: 36% 1fr; gap: 24px; margin-top: 18px; background: #fff; border-radius: 16px; overflow: hidden; }
.enterprise-profile__hero>img,.enterprise-profile__hero>.enterprise-card__identity { width: 100%; height: 260px; object-fit: cover; }
.enterprise-profile__hero>div:last-child { padding: 26px 26px 26px 0; }
.enterprise-profile__hero h1 { margin: 11px 0; color: #153f2b; }
.enterprise-profile__hero p { color: #62796c; line-height: 1.7; }
.enterprise-profile__sections { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-top: 18px; }
.enterprise-profile__sections article { background: #fff; padding: 18px; border-radius: 12px; }
.enterprise-profile__sections h2 { font-size: 17px; color: #17432d; }
.enterprise-profile__sections p { color: #65766c; line-height: 1.65; }
.enterprise-profile__products { display: flex; flex-wrap: wrap; gap: 10px; }
.enterprise-profile__products a { padding: 12px 16px; background: #fff; border-radius: 10px; color: #224b33; text-decoration: none; }
.enterprise-profile__products span { color: #0c814c; margin-left: 14px; }
.portal-info,.portal-form { background: #fff; padding: 34px; border-radius: 16px; border: 1px solid #e2ece4; }
.portal-info h1,.portal-form h1 { margin: 9px 0; color: #163d2b; }
.portal-info p,.portal-form>p { max-width: 720px; color: #65786b; line-height: 1.8; }
.portal-info--home { margin-top: 45px; }
.service-steps { display: flex; flex-wrap: wrap; gap: 8px; margin: 24px 0; }
.service-steps span { padding: 13px; background: #eaf5ee; color: #135d3b; border-radius: 8px; font-weight: 700; }
.portal-form form { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; max-width: 820px; margin-top: 24px; }
.portal-form label { display: grid; gap: 7px; color: #345b41; font-size: 13px; font-weight: 700; }
.portal-form__wide { grid-column: 1/-1; }
.portal-form input,.portal-form select,.portal-form textarea { width: 100%; box-sizing: border-box; border: 1px solid #d8e7db; border-radius: 8px; padding: 11px 12px; background: #fff; color: #214634; font: inherit; font-weight: 400; }
.portal-form form>button { justify-self: start; border: 0; cursor: pointer; }
.portal-success { padding: 20px; margin-top: 20px; color: #145c38; background: #e9f7ed; border-radius: 10px; }
.portal-success a { color: #0b7546; margin-left: 10px; }
@media(max-width:650px) {
  .enterprise-card__identity { height: 100px; }
  .site-footer small { margin-left: 0; }
  .site-nav { min-width: 0; width: calc(100vw - 30px); }
  .supply-grid,.supply-grid--hall,.need-grid,.enterprise-profile__sections { grid-template-columns: 1fr; }
  .supply-card { grid-template-columns: 100px minmax(0,1fr); }
  .supply-card>img { width: 100px; min-height: 190px; }
  .supply-card>div,.need-card { padding: 13px; }
  .supply-card h3,.need-card h3 { font-size: 15px; }
  .enterprise-profile__hero { display: block; }
  .enterprise-profile__hero>img,.enterprise-profile__hero>.enterprise-card__identity { height: 180px; }
  .enterprise-profile__hero>div:last-child { padding: 18px; }
  .portal-info,.portal-form { padding: 20px; }
  .portal-form form { grid-template-columns: 1fr; }
  .portal-form__wide { grid-column: auto; }
}
</style>
