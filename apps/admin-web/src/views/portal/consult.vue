<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { http } from '@/api/request'
import { getAccessToken } from '@/utils/auth'
import './portal.css'

interface Supply { id: number; name: string; enterprise: string; image: string }
interface Company { id: number; name: string }
const route = useRoute()
const supply = ref<Supply | null>(null)
const company = ref<Company | null>(null)
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const leadId = ref<number | null>(null)
const action = String(route.query.action || '')
const productId = Number(route.query.product_id || 0)
const enterpriseId = Number(route.query.enterprise_id || 0)
const form = ref({ contact_name: '', contact_phone: '', need_content: '', intent_product: '', quantity: '' })
const title = action === 'contact' ? '联系供应企业' : action === 'purchase' ? '提交采购需求' : productId ? '立即咨询' : '留下采购与合作需求'

onMounted(async () => {
  if (!productId && !enterpriseId) return
  loading.value = true
  try {
    const response = await fetch(productId ? `/api/v1/marketplace/supplies/${productId}` : `/api/v1/marketplace/enterprises/${enterpriseId}`)
    const result = await response.json()
    if (!response.ok || result.code !== 0) throw new Error('供应信息不存在或尚未公开')
    if (productId) {
      supply.value = result.data as Supply
      form.value.intent_product = supply.value.name
    } else {
      company.value = result.data as Company
      form.value.intent_product = company.value.name
    }
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '供应信息加载失败' }
  finally { loading.value = false }
})

async function submit(): Promise<void> {
  if ((productId && !supply.value) || (enterpriseId && !company.value)) return
  submitting.value = true
  try {
    const result = await http.post<{ id: number }>('/portal/leads', {
      ...form.value, product_id: supply.value?.id || null, enterprise_id: company.value?.id || null,
      quantity: form.value.quantity ? Number(form.value.quantity) : null
    })
    leadId.value = result.id
  } catch { /* 请求层展示错误 */ }
  finally { submitting.value = false }
}
</script>

<template>
  <div class="open-portal">
    <header class="open-portal__header"><a class="open-portal__brand" href="/home"><img src="/static/images/logo/platform-mark.svg" alt="" />第十师瓜子油料数字化交易平台</a><nav class="open-portal__nav"><a href="/supply">找供应</a><a href="/procurement">找采购</a><a href="/register">注册</a><a :href="getAccessToken() ? '/account' : '/login?redirect=/account'">我的需求</a></nav></header>
    <main class="open-portal__main">
      <span class="open-portal__eyebrow">开放浏览 · 留资撮合</span><h1>{{ title }}</h1>
      <p class="open-portal__intro">无需注册。留下联系方式和真实需求后，平台运营人员会联系您并协助对接供应企业；不会自动生成订单。</p>
      <p v-if="loading" class="open-portal__card">正在读取供应信息…</p>
      <p v-else-if="error" class="open-portal__card">{{ error }} <a href="/supply">返回供应大厅</a></p>
      <div v-else-if="leadId" class="open-portal__success"><strong>需求已提交，线索编号 #{{ leadId }}</strong><br />平台运营人员将根据您填写的信息跟进。<div class="open-portal__actions"><a class="open-portal__button" href="/supply">继续找供应</a><a v-if="getAccessToken()" href="/account">查看我的记录</a><a v-else href="/register">注册后管理新提交的需求 →</a></div></div>
      <template v-else>
        <div v-if="supply" class="open-portal__card"><strong>意向供应：{{ supply.name }}</strong><p class="open-portal__muted">供应企业：{{ supply.enterprise }}</p></div>
        <div v-if="company" class="open-portal__card"><strong>联系企业：{{ company.name }}</strong></div>
        <form class="open-portal__card" @submit.prevent="submit"><h2>填写合作信息</h2><div class="open-portal__grid">
          <label class="open-portal__field">姓名<input v-model.trim="form.contact_name" required minlength="2" maxlength="64" autocomplete="name" placeholder="怎么称呼您" /></label>
          <label class="open-portal__field">联系电话<input v-model.trim="form.contact_phone" required minlength="7" maxlength="32" autocomplete="tel" inputmode="tel" placeholder="手机或固定电话" /></label>
          <label class="open-portal__field">意向产品或合作方向<input v-model.trim="form.intent_product" required minlength="2" maxlength="160" :readonly="Boolean(supply)" placeholder="例如：北屯葵花籽" /></label>
          <label class="open-portal__field">需求数量（可选）<input v-model="form.quantity" type="number" min="0.001" step="0.001" placeholder="单位按吨填写" /></label>
          <label class="open-portal__field open-portal__field--wide">需求内容<textarea v-model.trim="form.need_content" required minlength="5" maxlength="2000" rows="5" placeholder="说明规格、用途、预计采购时间或希望联系的事项" /></label>
        </div><div class="open-portal__actions"><button class="open-portal__button" :disabled="submitting">{{ submitting ? '提交中…' : '提交合作需求' }}</button><span class="open-portal__muted">仅平台运营与相关认证企业按业务需要查看联系方式</span></div></form>
      </template>
    </main><footer class="open-portal__footer">© 2026 第十师瓜子油料数字化交易平台　技术支持：屯云大数据</footer>
  </div>
</template>
