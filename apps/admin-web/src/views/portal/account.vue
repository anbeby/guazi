<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '@/api/request'
import { getAccessToken } from '@/utils/auth'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import './portal.css'

interface Lead { id: number; intent_product: string; need_content: string; status: string; result?: string; contact_name: string; contact_phone: string; created_at: string; product_id?: number; followups?: Array<{ note: string; created_at: string }> }
interface Favorite { product_id: number; product_name: string; enterprise_name: string; image: string }
interface Requirement { id: number; title: string; quantity: number; unit: string; status: string }
interface Enterprise { id: number; name: string; enterprise_type: string; profile: string; business_scope: string; contact_name: string; contact_phone: string; region: string; address: string; qualifications: string[]; audit_status: string; audit_remark: string; image_url?: string }

const userStore = useUserStore()
const loading = ref(true)
const saving = ref(false)
const leads = ref<Lead[]>([])
const favorites = ref<Favorite[]>([])
const requirements = ref<Requirement[]>([])
const enterprise = ref<Enterprise | null>(null)
const enterpriseLeads = ref<Lead[]>([])
const replies = ref<Record<number, string>>({})
const application = ref({ name: '', enterprise_type: 'supplier', profile: '', business_scope: '', contact_name: '', contact_phone: '', region: '', address: '', qualifications: '' })
const edit = ref({ profile: '', business_scope: '', contact_name: '', contact_phone: '', region: '', address: '', qualifications: '' })
const statusLabel = (status: string) => ({ new: '待处理', following: '跟进中', completed: '已完成', pending: '审核中', approved: '已认证', rejected: '未通过', open: '采购中', closed: '已关闭' }[status] || status)

function setEnterprise(row: Enterprise | null): void {
  enterprise.value = row
  if (row) edit.value = { profile: row.profile || '', business_scope: row.business_scope || '', contact_name: row.contact_name || '', contact_phone: row.contact_phone || '', region: row.region || '', address: row.address || '', qualifications: (row.qualifications || []).join('、') }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    await userStore.fetchUserInfo()
    const [leadRows, favoriteRows, requirementRows, company] = await Promise.all([
      http.get<{ items: Lead[] }>('/portal/me/leads'),
      http.get<{ items: Favorite[] }>('/portal/me/favorites'),
      http.get<{ items: Requirement[] }>('/portal/me/requirements'),
      http.get<Enterprise | null>('/portal/me/enterprise')
    ])
    leads.value = leadRows.items
    favorites.value = favoriteRows.items
    requirements.value = requirementRows.items
    setEnterprise(company)
    enterpriseLeads.value = company?.audit_status === 'approved'
      ? (await http.get<{ items: Lead[] }>('/portal/me/enterprise-leads')).items : []
  } finally { loading.value = false }
}

async function apply(): Promise<void> {
  saving.value = true
  try {
    const row = await http.post<Enterprise>('/portal/me/enterprise', { ...application.value,
      qualifications: application.value.qualifications.split(/[、,，\n]/).map(s => s.trim()).filter(Boolean) })
    setEnterprise(row)
    await userStore.fetchUserInfo()
    ElMessage.success('企业申请已提交，等待平台审核')
  } finally { saving.value = false }
}

async function saveProfile(): Promise<void> {
  saving.value = true
  try {
    const row = await http.put<Enterprise>('/portal/me/enterprise', { ...edit.value,
      qualifications: edit.value.qualifications.split(/[、,，\n]/).map(s => s.trim()).filter(Boolean) })
    setEnterprise(row)
    ElMessage.success('企业资料已保存')
  } finally { saving.value = false }
}

async function uploadImage(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
    ElMessage.warning('请选择 5MB 以内的 JPG、PNG 或 WebP 图片'); return
  }
  saving.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    body.append('biz_type', 'enterprise_image')
    const response = await fetch('/api/v1/files/upload', { method: 'POST', headers: { Authorization: `Bearer ${getAccessToken()}` }, body })
    const uploaded = await response.json()
    if (!response.ok || uploaded.code !== 0) throw new Error(uploaded.message || '图片上传失败')
    setEnterprise(await http.post<Enterprise>('/portal/me/enterprise/image', { file_key: uploaded.data.file_key }))
    ElMessage.success('企业图片已更新')
  } catch (cause) { ElMessage.error(cause instanceof Error ? cause.message : '图片上传失败') }
  finally { saving.value = false; input.value = '' }
}

async function removeFavorite(productId: number): Promise<void> {
  await http.delete(`/portal/me/favorites/${productId}`)
  favorites.value = favorites.value.filter(item => item.product_id !== productId)
  ElMessage.success('已取消收藏')
}

async function respond(leadId: number): Promise<void> {
  const note = (replies.value[leadId] || '').trim()
  if (note.length < 2) return
  await http.post(`/portal/me/enterprise-leads/${leadId}/response`, { note })
  replies.value[leadId] = ''
  enterpriseLeads.value = (await http.get<{ items: Lead[] }>('/portal/me/enterprise-leads')).items
  ElMessage.success('合作意向已记录')
}

async function logout(): Promise<void> {
  await userStore.logout()
  window.location.assign('/home')
}

onMounted(load)
</script>

<template>
  <div class="open-portal">
    <header class="open-portal__header"><a class="open-portal__brand" href="/home"><img src="/static/images/logo/platform-mark.svg" alt="" />第十师瓜子油料数字化交易平台</a><nav class="open-portal__nav"><a href="/supply">找供应</a><a href="/procurement">找采购</a><a href="/consult">留下需求</a><a v-if="userStore.hasPermission('data:read')" href="/dashboard">进入工作台</a><button type="button" class="open-portal__nav-action" @click="logout">退出登录</button></nav></header>
    <main class="open-portal__main"><span class="open-portal__eyebrow">我的需求 · 企业资料</span><h1>{{ userStore.displayName }}，欢迎回来</h1><p class="open-portal__intro">查看咨询进展与收藏的供应信息；企业申请通过审核后，可以维护资料、发布供需信息并处理合作意向。</p>
      <p v-if="loading">正在读取我的记录…</p><template v-else>
        <div class="open-portal__stats"><article><span>我的咨询</span><strong>{{ leads.length }}</strong></article><article><span>收藏供应</span><strong>{{ favorites.length }}</strong></article><article><span>企业状态</span><strong style="font-size:18px">{{ enterprise ? statusLabel(enterprise.audit_status) : '未申请' }}</strong></article></div>
        <section class="open-portal__card"><h2>我的咨询记录</h2><div v-if="leads.length" class="open-portal__list"><article v-for="item in leads" :key="item.id" class="open-portal__row"><div><strong>#{{ item.id }} · {{ item.intent_product }}</strong><p>{{ item.need_content }}</p><small>{{ item.created_at?.slice(0,10) }} · {{ item.contact_name }} {{ item.contact_phone }}</small><p v-if="item.result">处理结果：{{ item.result }}</p></div><span class="open-portal__badge">{{ statusLabel(item.status) }}</span></article></div><p v-else class="open-portal__muted">尚未提交咨询。<a href="/consult">留下需求 →</a></p><p class="open-portal__muted">游客时期提交的线索不会仅凭同号手机号自动关联账号；如需查询，请保留线索编号并联系平台运营人员。</p></section>
        <section class="open-portal__card"><h2>收藏的供应信息</h2><div v-if="favorites.length" class="open-portal__list"><article v-for="item in favorites" :key="item.product_id" class="open-portal__row"><div><a :href="`/supply/${item.product_id}`"><strong>{{ item.product_name }}</strong></a><p>{{ item.enterprise_name }}</p></div><button class="open-portal__button open-portal__button--line" @click="removeFavorite(item.product_id)">取消收藏</button></article></div><p v-else class="open-portal__muted">还没有收藏供应。<a href="/supply">去供应大厅查找 →</a></p></section>
        <section class="open-portal__card"><h2>企业身份</h2>
          <form v-if="!enterprise" @submit.prevent="apply"><p class="open-portal__muted">先提交企业资料，经平台审核后开通企业发布与线索处理权限。</p><div class="open-portal__grid">
            <label class="open-portal__field">企业名称<input v-model.trim="application.name" required minlength="2" maxlength="160" /></label>
            <label class="open-portal__field">企业类型<select v-model="application.enterprise_type"><option value="supplier">供应企业</option><option value="buyer">采购企业</option><option value="merchant">加工/贸易企业</option></select></label>
            <label class="open-portal__field">联系人<input v-model.trim="application.contact_name" required minlength="2" /></label>
            <label class="open-portal__field">联系电话<input v-model.trim="application.contact_phone" required minlength="7" inputmode="tel" /></label>
            <label class="open-portal__field">主营业务<input v-model.trim="application.business_scope" maxlength="512" /></label>
            <label class="open-portal__field">地区<input v-model.trim="application.region" maxlength="64" /></label>
            <label class="open-portal__field open-portal__field--wide">企业地址<input v-model.trim="application.address" maxlength="255" /></label>
            <label class="open-portal__field open-portal__field--wide">企业简介<textarea v-model.trim="application.profile" rows="3" maxlength="2000" /></label>
            <label class="open-portal__field open-portal__field--wide">资质信息（用顿号分隔）<input v-model.trim="application.qualifications" placeholder="例如：食品生产许可证、质量管理认证" /></label>
          </div><div class="open-portal__actions"><button class="open-portal__button" :disabled="saving">提交企业申请</button></div></form>
          <div v-else><p><strong>{{ enterprise.name }}</strong>　<span class="open-portal__badge">{{ statusLabel(enterprise.audit_status) }}</span></p><p v-if="enterprise.audit_remark" class="open-portal__muted">审核说明：{{ enterprise.audit_remark }}</p><p v-if="enterprise.audit_status === 'pending'" class="open-portal__muted">企业资料已提交，平台审核前不可发布供应或采购信息。</p><form @submit.prevent="saveProfile"><div class="open-portal__grid">
            <label class="open-portal__field">企业简介<textarea v-model.trim="edit.profile" rows="3" maxlength="2000" /></label>
            <label class="open-portal__field">主营业务<textarea v-model.trim="edit.business_scope" rows="3" maxlength="512" /></label>
            <label class="open-portal__field">联系人<input v-model.trim="edit.contact_name" /></label>
            <label class="open-portal__field">联系电话<input v-model.trim="edit.contact_phone" inputmode="tel" /></label>
            <label class="open-portal__field">地区<input v-model.trim="edit.region" /></label>
            <label class="open-portal__field">地址<input v-model.trim="edit.address" /></label>
            <label class="open-portal__field open-portal__field--wide">资质信息（用顿号分隔）<input v-model.trim="edit.qualifications" /></label>
          </div><div class="open-portal__actions"><button class="open-portal__button" :disabled="saving">保存企业资料</button><label class="open-portal__button open-portal__button--line" style="cursor:pointer">更换企业图片<input type="file" accept="image/jpeg,image/png,image/webp" hidden @change="uploadImage" /></label></div></form><img v-if="enterprise.image_url" :src="enterprise.image_url" :alt="enterprise.name" style="max-width:240px;border-radius:10px;margin-top:16px" /></div>
        </section>
        <section v-if="enterprise?.audit_status === 'approved'" class="open-portal__card"><h2>企业运营入口</h2><div class="open-portal__actions"><a v-if="enterprise.enterprise_type !== 'buyer'" class="open-portal__button" href="/product/list">管理供应信息</a><a class="open-portal__button open-portal__button--line" href="/purchase/new">发布采购需求</a></div><h2 style="margin-top:25px">收到的咨询线索</h2><div v-if="enterpriseLeads.length" class="open-portal__list"><article v-for="item in enterpriseLeads" :key="item.id" class="open-portal__row"><div style="width:100%"><strong>{{ item.intent_product }} · {{ item.contact_name }}</strong><p>{{ item.need_content }} · {{ item.contact_phone }}</p><p v-for="(followup, index) in item.followups || []" :key="index" class="open-portal__muted">跟进：{{ followup.note }}</p><div v-if="item.status !== 'completed'" class="open-portal__actions"><input v-model="replies[item.id]" style="flex:1;min-width:180px;padding:10px;border:1px solid #dce9df;border-radius:8px" placeholder="记录联系或合作反馈" /><button class="open-portal__button open-portal__button--line" :disabled="!replies[item.id]?.trim()" @click="respond(item.id)">记录处理</button></div></div><span class="open-portal__badge">{{ statusLabel(item.status) }}</span></article></div><p v-else class="open-portal__muted">目前没有关联的咨询线索。</p></section>
        <section v-if="requirements.length" class="open-portal__card"><h2>本企业采购需求</h2><div class="open-portal__list"><article v-for="item in requirements" :key="item.id" class="open-portal__row"><div><strong>{{ item.title }}</strong><p>{{ item.quantity }} {{ item.unit === 'ton' ? '吨' : item.unit }}</p></div><span class="open-portal__badge">{{ statusLabel(item.status) }}</span></article></div></section>
      </template>
    </main><footer class="open-portal__footer">© 2026 第十师瓜子油料数字化交易平台　技术支持：屯云大数据</footer>
  </div>
</template>
