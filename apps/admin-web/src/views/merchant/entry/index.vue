<script setup lang="ts">
/**
 * 入驻申请与审核：按 audit_status=pending 过滤商户入驻申请，逐条审核（通过 / 驳回）。
 * 接口：/enterprises（含 audit_status 过滤）、/enterprises/{id}/audit
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import FileUpload from '@/components/FileUpload.vue'
import { auditEnterprise, getEnterprise, getEnterpriseStats, listEnterprises } from '@/api/enterprise'
import type { Enterprise, EnterpriseQuery, EnterpriseStats } from '@/api/types'
import { formatAmount, formatDateTime, formatQuantity } from '@/utils/format'

const loading = ref(false)
const list = ref<Enterprise[]>([])
const total = ref(0)
const query = reactive<EnterpriseQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  audit_status: 'pending',
  enterprise_type: ''
})

const pendingCount = computed(() => (query.audit_status === 'pending' ? total.value : 0))

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listEnterprises(query)
    list.value = data.items || []
    total.value = data.total || 0
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  query.page = 1
  loadList()
}

function handleReset(): void {
  query.keyword = ''
  query.audit_status = 'pending'
  query.enterprise_type = ''
  query.page = 1
  loadList()
}

/* ---------------- 审核面板 ---------------- */
const auditVisible = ref(false)
const auditLoading = ref(false)
const auditSubmitting = ref(false)
const current = ref<Enterprise | null>(null)
const stats = ref<EnterpriseStats | null>(null)
const auditForm = reactive<{ approved: boolean; remark: string }>({ approved: true, remark: '' })

const checklist = reactive([
  { label: '营业执照与统一社会信用代码一致', checked: false },
  { label: '法定代表人身份信息无误', checked: false },
  { label: '经营范围包含瓜子油料相关业务', checked: false },
  { label: '结算账户信息完整', checked: false }
])

const allChecked = computed(() => checklist.every((item) => item.checked))

async function openAudit(row: Enterprise): Promise<void> {
  auditVisible.value = true
  auditForm.approved = true
  auditForm.remark = ''
  checklist.forEach((item) => (item.checked = false))
  auditLoading.value = true
  current.value = row
  try {
    const [info, stat] = await Promise.all([
      getEnterprise(row.id),
      getEnterpriseStats(row.id).catch(() => null)
    ])
    current.value = info
    stats.value = stat
  } catch {
    /* 已提示 */
  } finally {
    auditLoading.value = false
  }
}

async function submitAudit(): Promise<void> {
  const row = current.value
  if (!row) return
  if (auditForm.approved && !allChecked.value) {
    ElMessage.warning('请先完成全部资料核验项')
    return
  }
  if (!auditForm.approved && !auditForm.remark.trim()) {
    ElMessage.warning('驳回时必须填写审核意见')
    return
  }
  auditSubmitting.value = true
  try {
    await auditEnterprise(row.id, { approved: auditForm.approved, remark: auditForm.remark })
    ElMessage.success(auditForm.approved ? '入驻申请已通过' : '入驻申请已驳回')
    auditVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  } finally {
    auditSubmitting.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <div class="page-container">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mb-12"
      :title="`入驻申请审核：当前待审核 ${pendingCount} 家。审核通过后系统自动创建组织单元并推送 Odoo。`"
    />

    <PageTable
      :data="list"
      :total="total"
      :loading="loading"
      v-model:page="query.page"
      v-model:page-size="query.page_size"
      @change="loadList"
    >
      <template #search>
        <div class="page-card">
          <el-form class="search-form" :inline="true" @submit.prevent>
            <el-form-item label="关键词">
              <el-input
                v-model="query.keyword"
                placeholder="企业名称 / 信用代码"
                clearable
                style="width: 220px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="审核状态">
              <DictSelect v-model="query.audit_status" group="auditStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="企业类型">
              <DictSelect v-model="query.enterprise_type" group="enterpriseType" with-all placeholder="全部类型" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-tag type="warning" effect="plain">待审核 {{ pendingCount }} 家</el-tag>
      </template>

      <el-table-column prop="code" label="企业编码" width="130" />
      <el-table-column prop="name" label="企业名称" min-width="200" show-overflow-tooltip />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <StatusTag group="enterpriseType" :value="row.enterprise_type" />
        </template>
      </el-table-column>
      <el-table-column prop="unified_social_credit_code" label="统一社会信用代码" min-width="180" />
      <el-table-column prop="legal_person" label="法定代表人" width="110" />
      <el-table-column prop="contact_name" label="联系人" width="100" />
      <el-table-column prop="contact_phone" label="联系电话" width="130" />
      <el-table-column label="提交时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="审核状态" width="100">
        <template #default="{ row }">
          <StatusTag group="auditStatus" :value="row.audit_status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'merchant:audit'" link type="primary" @click="openAudit(row as Enterprise)">
            审核
          </el-button>
        </template>
      </el-table-column>
    </PageTable>

    <el-drawer v-model="auditVisible" title="入驻申请审核" size="640px">
      <div v-loading="auditLoading">
        <template v-if="current">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="企业名称" :span="2">{{ current.name }}</el-descriptions-item>
            <el-descriptions-item label="企业编码">{{ current.code }}</el-descriptions-item>
            <el-descriptions-item label="企业类型">
              <StatusTag group="enterpriseType" :value="current.enterprise_type" />
            </el-descriptions-item>
            <el-descriptions-item label="统一社会信用代码" :span="2">
              {{ current.unified_social_credit_code || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="法定代表人">{{ current.legal_person || '-' }}</el-descriptions-item>
            <el-descriptions-item label="注册资本">
              {{ current.registered_capital ? `${current.registered_capital} 万元` : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="联系人">{{ current.contact_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ current.contact_phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="行政区划">{{ current.region || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属园区">{{ current.park_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="详细地址" :span="2">{{ current.address || '-' }}</el-descriptions-item>
            <el-descriptions-item label="结算账户" :span="2">
              {{ current.settle_bank || '-' }} / {{ current.settle_account_name || '-' }} /
              {{ current.settle_account_no || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="经营范围" :span="2">{{ current.business_scope || '-' }}</el-descriptions-item>
          </el-descriptions>

          <div class="entry-block">
            <div class="entry-block__title">经营能力（/enterprises/{id}/stats）</div>
            <el-row :gutter="10">
              <el-col :span="6">
                <div class="entry-stat">
                  <div class="entry-stat__label">商品数</div>
                  <div class="entry-stat__value">{{ stats?.product_count ?? 0 }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="entry-stat">
                  <div class="entry-stat__label">库存量</div>
                  <div class="entry-stat__value">{{ formatQuantity(stats?.inventory_quantity) }} 吨</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="entry-stat">
                  <div class="entry-stat__label">订单数</div>
                  <div class="entry-stat__value">{{ stats?.order_count ?? 0 }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="entry-stat">
                  <div class="entry-stat__label">交易额</div>
                  <div class="entry-stat__value">{{ formatAmount(stats?.order_amount) }}</div>
                </div>
              </el-col>
            </el-row>
          </div>

          <div class="entry-block">
            <div class="entry-block__title">资质附件核验</div>
            <FileUpload
              model-value=""
              biz-type="entry_license"
              tip="可上传补充的核验材料（后端按 biz_type=entry_license 归档）"
            />
          </div>

          <div class="entry-block">
            <div class="entry-block__title">资料核验项</div>
            <el-checkbox v-for="item in checklist" :key="item.label" v-model="item.checked" class="entry-check">
              {{ item.label }}
            </el-checkbox>
          </div>

          <div class="entry-block">
            <div class="entry-block__title">审核结论</div>
            <el-radio-group v-model="auditForm.approved">
              <el-radio :value="true">通过（自动创建组织单元并推送 Odoo）</el-radio>
              <el-radio :value="false">驳回</el-radio>
            </el-radio-group>
            <el-input
              v-model="auditForm.remark"
              type="textarea"
              :rows="3"
              class="mt-8"
              :placeholder="auditForm.approved ? '审核意见（可选）' : '请填写驳回原因'"
            />
          </div>

          <div class="entry-footer">
            <el-button @click="auditVisible = false">取消</el-button>
            <el-button
              v-permission="'merchant:audit'"
              :type="auditForm.approved ? 'success' : 'warning'"
              :loading="auditSubmitting"
              @click="submitAudit"
            >
              提交审核结论
            </el-button>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.entry-block {
  margin-top: 16px;
}

.entry-block__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.entry-stat {
  padding: 10px;
  border-radius: 4px;
  background: #f7f9fa;
  text-align: center;
}

.entry-stat__label {
  font-size: 12px;
  color: var(--gz-text-sub);
}

.entry-stat__value {
  font-size: 15px;
  font-weight: 600;
  margin-top: 4px;
}

.entry-check {
  display: block;
  margin-bottom: 4px;
}

.entry-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin: 20px 0 8px;
}
</style>
