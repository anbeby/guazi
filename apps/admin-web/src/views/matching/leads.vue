<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api/request'
import { useUserStore } from '@/stores/user'

interface Lead { id: number; contact_name: string; contact_phone: string; need_content: string; intent_product: string; quantity?: number; product_id?: number; product_name?: string; supplier_enterprise_id?: number; supplier_enterprise_name?: string; operator_name?: string; status: string; result?: string; created_at: string; followups: Array<{ note: string; created_at: string }> }
interface Enterprise { id: number; name: string; enterprise_type: string }
interface Summary { today: number; new: number; following: number; completed: number }

const userStore = useUserStore()
const canWrite = userStore.hasPermission('trade:write')
const loading = ref(false)
const rows = ref<Lead[]>([])
const summary = ref<Summary>({ today: 0, new: 0, following: 0, completed: 0 })
const suppliers = ref<Enterprise[]>([])
const filter = ref('all')
const selected = ref<Lead | null>(null)
const visible = ref(false)
const saving = ref(false)
const form = ref({ status: 'new', supplier_enterprise_id: null as number | null, result: '', note: '' })
const filtered = computed(() => filter.value === 'all' ? rows.value : rows.value.filter(row => row.status === filter.value))
const label = (status: string) => ({ new: '待处理', following: '跟进中', completed: '已完成' }[status] || status)

async function load(): Promise<void> {
  loading.value = true
  try {
    const [stats, leadRows, enterpriseRows] = await Promise.all([
      http.get<Summary>('/portal/operations/leads/summary'),
      http.get<{ items: Lead[] }>('/portal/operations/leads'),
      http.get<{ items: Enterprise[] }>('/enterprises', { page_size: 200, audit_status: 'approved', status: 'active' })
    ])
    summary.value = stats
    rows.value = leadRows.items
    suppliers.value = enterpriseRows.items.filter(row => row.enterprise_type !== 'buyer' && row.enterprise_type !== 'platform')
  } finally { loading.value = false }
}

function open(value: unknown): void {
  const row = value as Lead
  selected.value = row
  form.value = { status: row.status, supplier_enterprise_id: row.supplier_enterprise_id || null, result: row.result || '', note: '' }
  visible.value = true
}

async function save(): Promise<void> {
  if (!selected.value) return
  if (form.value.status === 'completed' && !form.value.result.trim()) {
    ElMessage.warning('完成线索时请填写处理结果'); return
  }
  saving.value = true
  try {
    if (form.value.note.trim()) {
      await http.post(`/portal/operations/leads/${selected.value.id}/followups`, { note: form.value.note.trim() })
    }
    await http.put(`/portal/operations/leads/${selected.value.id}`, {
      status: form.value.note.trim() && form.value.status === 'new' ? 'following' : form.value.status,
      supplier_enterprise_id: form.value.supplier_enterprise_id,
      result: form.value.result.trim() || null
    })
    visible.value = false
    ElMessage.success('线索处理记录已保存')
    await load()
  } finally { saving.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page-container lead-center" v-loading="loading">
    <div class="lead-heading"><div><span>产业供需 · 运营线索</span><h1>线索中心</h1><p>查看游客与注册用户的咨询，分配供应企业并记录跟进结果。</p></div><el-button @click="load">刷新数据</el-button></div>
    <div class="lead-stats"><article><span>今日新增咨询</span><strong>{{ summary.today }}</strong></article><article><span>待处理线索</span><strong>{{ summary.new }}</strong></article><article><span>跟进中</span><strong>{{ summary.following }}</strong></article><article><span>已完成</span><strong>{{ summary.completed }}</strong></article></div>
    <section class="page-card"><div class="lead-toolbar"><h2>合作需求线索</h2><el-radio-group v-model="filter" size="small"><el-radio-button value="all">全部</el-radio-button><el-radio-button value="new">待处理</el-radio-button><el-radio-button value="following">跟进中</el-radio-button><el-radio-button value="completed">已完成</el-radio-button></el-radio-group></div>
      <el-table :data="filtered" stripe empty-text="暂无咨询线索"><el-table-column prop="id" label="编号" width="68" /><el-table-column prop="contact_name" label="联系人" width="95" /><el-table-column prop="contact_phone" label="电话" min-width="125" /><el-table-column prop="intent_product" label="意向产品" min-width="125" /><el-table-column prop="need_content" label="需求内容" min-width="175" show-overflow-tooltip /><el-table-column prop="product_name" label="关联供应" min-width="125" show-overflow-tooltip><template #default="{ row }">{{ row.product_name || '未指定' }}</template></el-table-column><el-table-column prop="supplier_enterprise_name" label="供应企业" min-width="125" show-overflow-tooltip><template #default="{ row }">{{ row.supplier_enterprise_name || '待匹配' }}</template></el-table-column><el-table-column prop="operator_name" label="处理人员" width="95"><template #default="{ row }">{{ row.operator_name || '待分配' }}</template></el-table-column><el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'completed' ? 'success' : row.status === 'following' ? 'warning' : 'info'">{{ label(row.status) }}</el-tag></template></el-table-column><el-table-column label="操作" width="76" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="open(row)">{{ canWrite ? '处理' : '查看' }}</el-button></template></el-table-column></el-table>
      <p class="lead-note">显示最近 200 条；联系方式仅向平台运营人员与对应认证企业开放。</p>
    </section>
    <el-dialog v-model="visible" :title="`线索 #${selected?.id || ''}`" width="620px" destroy-on-close><template v-if="selected"><p><strong>{{ selected.intent_product }}</strong> · {{ selected.contact_name }} {{ selected.contact_phone }}</p><p class="lead-content">{{ selected.need_content }}</p><p class="lead-note">关联供应：{{ selected.product_name || '未指定' }}　提交时间：{{ selected.created_at?.slice(0, 16).replace('T', ' ') }}</p><div v-if="selected.followups?.length" class="lead-history"><strong>跟进记录</strong><p v-for="(item, index) in selected.followups" :key="index">{{ item.created_at?.slice(0, 16).replace('T', ' ') }}　{{ item.note }}</p></div>
      <el-form v-if="canWrite" label-position="top"><el-form-item label="匹配供应企业"><el-select v-model="form.supplier_enterprise_id" filterable clearable placeholder="请选择认证企业" style="width:100%"><el-option v-for="row in suppliers" :key="row.id" :label="row.name" :value="row.id" /></el-select></el-form-item><el-form-item label="处理状态"><el-select v-model="form.status" style="width:100%"><el-option label="待处理" value="new" /><el-option label="跟进中" value="following" /><el-option label="已完成" value="completed" /></el-select></el-form-item><el-form-item label="本次跟进"><el-input v-model="form.note" type="textarea" :rows="3" maxlength="2000" placeholder="记录联系过程或双方反馈" /></el-form-item><el-form-item label="处理结果（完成时必填）"><el-input v-model="form.result" type="textarea" :rows="3" maxlength="2000" /></el-form-item></el-form>
    </template><template #footer><el-button @click="visible = false">关闭</el-button><el-button v-if="canWrite && selected?.status !== 'completed'" type="primary" :loading="saving" @click="save">保存处理记录</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.lead-heading,.lead-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px}.lead-heading{margin-bottom:18px}.lead-heading span{color:#168050;font-size:12px;font-weight:700}.lead-heading h1{margin:5px 0;color:#163e2b;font-size:25px}.lead-heading p,.lead-note{color:#718579;font-size:13px}.lead-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.lead-stats article{background:#fff;border:1px solid #e2ece4;border-radius:12px;padding:16px}.lead-stats span{display:block;color:#728778;font-size:12px}.lead-stats strong{display:block;margin:8px 0;color:#126d43;font-size:27px}.lead-toolbar{margin-bottom:15px}.lead-toolbar h2{margin:0;font-size:18px;color:#17412b}.lead-content{background:#f4f8f6;padding:12px;border-radius:8px;line-height:1.7}.lead-history{padding:12px 0;border-top:1px solid #e2ece4}.lead-history p{font-size:13px;color:#61766a}.lead-note{margin:12px 0 0}@media(max-width:700px){.lead-stats{grid-template-columns:repeat(2,1fr)}.lead-heading,.lead-toolbar{align-items:flex-start;flex-wrap:wrap}}
</style>
