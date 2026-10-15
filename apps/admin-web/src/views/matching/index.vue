<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/request'
import { useUserStore } from '@/stores/user'

interface Need { id: number; title: string; product_name: string; quantity: number; unit: string; buyer_enterprise_id: number; buyer_enterprise_name: string; contact_name: string; contact_phone: string; purchase_region: string; status: string; created_at: string }
interface Case { id: number; requirement_id: number; requirement: Need; supplier_enterprise_name: string; supplier_enterprise_id: number; status: string; source: string; result: string; contact_name: string; contact_phone: string; followups: Array<{ id: number; note: string; created_at: string }> }
interface Summary { supplier_enterprises: number; supply_count: number; requirement_count: number; match_count: number; success_count: number; today_supplies: number; today_requirements: number; pending_matches: number }
interface Company { id: number; name: string; enterprise_type: string }

const userStore = useUserStore()
const canWrite = userStore.hasPermission('trade:write')
const summary = ref<Summary | null>(null)
const needs = ref<Need[]>([])
const cases = ref<Case[]>([])
const suppliers = ref<Company[]>([])
const loading = ref(false)
const matchVisible = ref(false)
const followupVisible = ref(false)
const statusVisible = ref(false)
const selectedCase = ref<Case | null>(null)
const selectedNeed = ref<Need | null>(null)
const supplierId = ref<number | null>(null)
const followupNote = ref('')
const statusForm = ref({ status: 'matching', result: '', contact_name: '', contact_phone: '' })
const labels: Record<string, string> = { pending: '待处理', matching: '匹配中', contacted: '已联系', success: '撮合成功', closed: '关闭' }

async function load(): Promise<void> {
  loading.value = true
  try {
    const [stats, requirementRows, matchRows, enterpriseRows] = await Promise.all([
      http.get<Summary>('/marketplace/operations/summary'),
      http.get<{ items: Need[] }>('/marketplace/operations/requirements'),
      http.get<{ items: Case[] }>('/marketplace/operations/matches'),
      http.get<{ items: Company[] }>('/enterprises', { page_size: 200, audit_status: 'approved', status: 'active' })
    ])
    summary.value = stats
    needs.value = requirementRows.items
    cases.value = matchRows.items
    suppliers.value = enterpriseRows.items.filter(item => item.enterprise_type !== 'buyer' && item.enterprise_type !== 'platform')
  } finally { loading.value = false }
}

function openMatch(row: unknown): void { selectedNeed.value = row as Need; supplierId.value = null; matchVisible.value = true }
async function setRequirementStatus(value: unknown, status: string): Promise<void> {
  const row = value as Need
  await http.put(`/marketplace/operations/requirements/${row.id}`, { status })
  ElMessage.success(status === 'open' ? '采购需求已审核公开' : status === 'rejected' ? '采购需求已驳回' : '采购需求已关闭')
  await load()
}
async function createMatch(): Promise<void> {
  if (!selectedNeed.value || !supplierId.value) return
  await http.post(`/marketplace/operations/matches?requirement_id=${selectedNeed.value.id}`, { supplier_enterprise_id: supplierId.value })
  matchVisible.value = false
  ElMessage.success('已建立人工撮合记录')
  await load()
}
function openFollowup(row: unknown): void { selectedCase.value = row as Case; followupNote.value = ''; followupVisible.value = true }
async function addFollowup(): Promise<void> {
  if (!selectedCase.value || !followupNote.value.trim()) return
  await http.post(`/marketplace/operations/matches/${selectedCase.value.id}/followups`, { note: followupNote.value.trim() })
  followupVisible.value = false
  ElMessage.success('跟进记录已保存')
  await load()
}
function openStatus(value: unknown): void {
  const row = value as Case
  selectedCase.value = row
  statusForm.value = { status: row.status, result: row.result || '', contact_name: row.contact_name || '', contact_phone: row.contact_phone || '' }
  statusVisible.value = true
}
async function updateStatus(): Promise<void> {
  if (!selectedCase.value) return
  await http.put(`/marketplace/operations/matches/${selectedCase.value.id}`, statusForm.value)
  statusVisible.value = false
  ElMessage.success('撮合状态已更新')
  await load()
}
onMounted(load)
</script>

<template>
  <div class="page-container matching-page" v-loading="loading">
    <div class="matching-heading"><div><span>产业供需 · 人工服务</span><h1>撮合管理</h1><p>查看采购需求、匹配供应企业、记录联系进展与结果。</p></div><el-button @click="load">刷新数据</el-button></div>
    <div class="matching-stats"><article><span>供应企业</span><strong>{{ summary?.supplier_enterprises ?? '—' }}</strong></article><article><span>供应信息</span><strong>{{ summary?.supply_count ?? '—' }}</strong><small>今日新增 {{ summary?.today_supplies ?? 0 }}</small></article><article><span>采购需求</span><strong>{{ summary?.requirement_count ?? '—' }}</strong><small>今日新增 {{ summary?.today_requirements ?? 0 }}</small></article><article><span>撮合次数</span><strong>{{ summary?.match_count ?? '—' }}</strong></article><article><span>成功案例</span><strong>{{ summary?.success_count ?? '—' }}</strong></article><article><span>待处理</span><strong>{{ summary?.pending_matches ?? '—' }}</strong></article></div>
    <section class="page-card"><div class="matching-section-head"><h2>采购需求池</h2><span>需求方联系方式仅在运营后台显示</span></div><el-table :data="needs" empty-text="暂无采购需求" stripe><el-table-column prop="title" label="需求名称" min-width="190" /><el-table-column prop="buyer_enterprise_name" label="需求企业" min-width="160" /><el-table-column prop="product_name" label="采购产品" min-width="150" /><el-table-column label="数量" width="110"><template #default="{ row }">{{ row.quantity }} {{ row.unit === 'ton' ? '吨' : row.unit }}</template></el-table-column><el-table-column prop="purchase_region" label="地区" width="110" /><el-table-column label="联系人" min-width="150"><template #default="{ row }">{{ row.contact_name }} {{ row.contact_phone }}</template></el-table-column><el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'open' ? 'success' : row.status === 'pending' ? 'warning' : 'info'">{{ row.status === 'open' ? '采购中' : row.status === 'pending' ? '待审核' : row.status === 'rejected' ? '已驳回' : '已关闭' }}</el-tag></template></el-table-column><el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><el-button v-if="canWrite && row.status === 'pending'" type="primary" link @click="setRequirementStatus(row, 'open')">审核通过</el-button><el-button v-if="canWrite && row.status === 'pending'" type="danger" link @click="setRequirementStatus(row, 'rejected')">驳回</el-button><el-button v-if="canWrite && row.status === 'open'" type="primary" link @click="openMatch(row)">匹配企业</el-button><el-button v-if="canWrite && row.status === 'open'" type="info" link @click="setRequirementStatus(row, 'closed')">关闭</el-button><el-button v-if="canWrite && row.status === 'closed'" type="primary" link @click="setRequirementStatus(row, 'open')">重新公开</el-button></template></el-table-column></el-table></section>
    <section class="page-card"><div class="matching-section-head"><h2>人工撮合记录</h2><span>从供货意向到结果全程留痕</span></div><el-table :data="cases" empty-text="暂无撮合记录" stripe><el-table-column label="采购需求" min-width="190"><template #default="{ row }">{{ row.requirement?.title }}</template></el-table-column><el-table-column prop="supplier_enterprise_name" label="供应企业" min-width="170" /><el-table-column label="来源" width="100"><template #default="{ row }">{{ row.source === 'interest' ? '企业意向' : '人工匹配' }}</template></el-table-column><el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="row.status === 'success' ? 'success' : row.status === 'closed' ? 'info' : 'warning'">{{ labels[row.status] || row.status }}</el-tag></template></el-table-column><el-table-column label="跟进" min-width="180"><template #default="{ row }">{{ row.followups?.length || 0 }} 条 · {{ row.result || '待跟进' }}</template></el-table-column><el-table-column label="操作" width="170" fixed="right"><template #default="{ row }"><el-button v-if="canWrite && !['success','closed'].includes(row.status)" link type="primary" @click="openFollowup(row)">写跟进</el-button><el-button v-if="canWrite" link @click="openStatus(row)">状态/结果</el-button></template></el-table-column></el-table></section>

    <el-dialog v-model="matchVisible" title="匹配供应企业" width="480px"><p>采购需求：{{ selectedNeed?.title }}</p><el-select v-model="supplierId" filterable placeholder="请选择供应企业" style="width:100%"><el-option v-for="company in suppliers.filter(item => item.id !== selectedNeed?.buyer_enterprise_id)" :key="company.id" :label="company.name" :value="company.id" /></el-select><template #footer><el-button @click="matchVisible = false">取消</el-button><el-button type="primary" :disabled="!supplierId" @click="createMatch">建立撮合</el-button></template></el-dialog>
    <el-dialog v-model="followupVisible" title="记录人工跟进" width="500px"><el-input v-model="followupNote" type="textarea" :rows="5" maxlength="2000" show-word-limit placeholder="记录联系过程、双方反馈或下一步安排" /><template #footer><el-button @click="followupVisible = false">取消</el-button><el-button type="primary" :disabled="followupNote.trim().length < 2" @click="addFollowup">保存记录</el-button></template></el-dialog>
    <el-dialog v-model="statusVisible" title="更新撮合状态" width="500px"><el-form label-width="84px"><el-form-item label="状态"><el-select v-model="statusForm.status" style="width:100%"><el-option v-for="(label, value) in labels" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="联系人"><el-input v-model="statusForm.contact_name" /></el-form-item><el-form-item label="联系电话"><el-input v-model="statusForm.contact_phone" /></el-form-item><el-form-item label="结果说明"><el-input v-model="statusForm.result" type="textarea" :rows="4" maxlength="2000" placeholder="撮合成功时需填写结果" /></el-form-item></el-form><template #footer><el-button @click="statusVisible = false">取消</el-button><el-button type="primary" @click="updateStatus">保存</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.matching-heading,.matching-section-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.matching-heading{margin-bottom:18px}.matching-heading span{color:#168050;font-size:12px;font-weight:700}.matching-heading h1{margin:5px 0;color:#163e2b;font-size:25px}.matching-heading p,.matching-section-head span{color:#718579;font-size:13px}.matching-stats{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:18px}.matching-stats article{background:#fff;border:1px solid #e2ece4;border-radius:12px;padding:16px}.matching-stats span,.matching-stats small{display:block;color:#728778;font-size:12px}.matching-stats strong{display:block;margin:8px 0 3px;color:#126d43;font-size:27px}.matching-page .page-card{margin-bottom:18px}.matching-section-head{margin-bottom:15px}.matching-section-head h2{margin:0;font-size:18px;color:#17412b}@media(max-width:1050px){.matching-stats{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.matching-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.matching-heading,.matching-section-head{align-items:flex-start}.matching-section-head span{display:none}}
</style>
