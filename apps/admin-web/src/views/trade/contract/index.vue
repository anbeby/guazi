<script setup lang="ts">
/**
 * 合同管理：列表 / 由订单生成 / 双方签署（POST /contracts、GET/PUT /contracts/{id}、POST /contracts/{id}/sign）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import FileUpload from '@/components/FileUpload.vue'
import {
  createContract,
  getContract,
  listContracts,
  listOrders,
  signContract,
  updateContract
} from '@/api/trade'
import { listEnterprises } from '@/api/enterprise'
import type {
  Contract,
  ContractPayload,
  ContractQuery,
  Enterprise,
  Order
} from '@/api/types'
import { formatDate, formatDateTime, formatMoney } from '@/utils/format'

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<Contract[]>([])
const total = ref(0)
const orders = ref<Order[]>([])
const enterprises = ref<Enterprise[]>([])
const query = reactive<ContractQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  status: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listContracts(query)
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
  query.status = ''
  query.order_id = null
  query.page = 1
  loadList()
}

async function loadOptions(): Promise<void> {
  try {
    const data = await listOrders({ page: 1, page_size: 100 })
    orders.value = data.items || []
  } catch {
    orders.value = []
  }
  try {
    const data = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = data.items || []
  } catch {
    enterprises.value = []
  }
}

/* ---------------- 新建 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('生成合同')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<ContractPayload>({
  title: '',
  order_id: null,
  buyer_enterprise_id: null,
  supplier_enterprise_id: null,
  amount: '',
  sign_date: '',
  start_date: '',
  end_date: '',
  file_url: '',
  remark: ''
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入合同标题', trigger: 'blur' }]
}

function handleOrderChange(orderId: number): void {
  const hit = orders.value.find((item) => item.id === orderId)
  if (!hit) return
  form.buyer_enterprise_id = hit.buyer_enterprise_id
  form.supplier_enterprise_id = hit.supplier_enterprise_id
  form.amount = hit.total_amount || hit.amount
  if (!form.title) form.title = `瓜子油料购销合同（订单 ${hit.order_no}）`
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '生成合同'
  Object.assign(form, {
    title: '',
    order_id: null,
    buyer_enterprise_id: null,
    supplier_enterprise_id: null,
    amount: '',
    sign_date: '',
    start_date: '',
    end_date: '',
    file_url: '',
    remark: ''
  })
  dialogVisible.value = true
}

async function openEdit(row: Contract): Promise<void> {
  editingId.value = row.id
  dialogTitle.value = `编辑合同：${row.contract_no}`
  let detail = row
  try {
    detail = await getContract(row.id)
  } catch {
    /* 使用列表数据 */
  }
  Object.assign(form, {
    title: detail.title,
    order_id: detail.order_id ?? null,
    buyer_enterprise_id: detail.buyer_enterprise_id,
    supplier_enterprise_id: detail.supplier_enterprise_id,
    amount: detail.amount,
    sign_date: detail.sign_date || '',
    start_date: detail.start_date || '',
    end_date: detail.end_date || '',
    file_url: detail.file_url || '',
    remark: detail.remark || ''
  })
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const el = formRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (editingId.value === null) {
        const created = await createContract({ ...form })
        ElMessage.success(`合同已生成：${created?.contract_no || ''}`)
      } else {
        await updateContract(editingId.value, { ...form })
        ElMessage.success('合同已更新')
      }
      dialogVisible.value = false
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      submitting.value = false
    }
  })
}

/* ---------------- 签署 ---------------- */
const signVisible = ref(false)
const signSubmitting = ref(false)
const signTarget = ref<Contract | null>(null)
const signParty = ref<'buyer' | 'supplier'>('buyer')

function openSign(row: Contract, party: 'buyer' | 'supplier'): void {
  signTarget.value = row
  signParty.value = party
  signVisible.value = true
}

async function submitSign(): Promise<void> {
  if (!signTarget.value) return
  signSubmitting.value = true
  try {
    const result = await signContract(signTarget.value.id, { party: signParty.value })
    ElMessage.success(
      result?.status === 'effective' ? '双方已签署，合同自动生效' : '签署成功，等待对方签署'
    )
    signVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  } finally {
    signSubmitting.value = false
  }
}

/* ---------------- 详情 ---------------- */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<Contract | null>(null)

async function openDetail(row: Contract): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = row
  try {
    detail.value = await getContract(row.id)
  } catch {
    /* 使用列表数据 */
  } finally {
    detailLoading.value = false
  }
}

async function handleFileSave(): Promise<void> {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm('将当前合同文件地址保存到合同记录？', '提示', {
      type: 'info',
      confirmButtonText: '保存',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await updateContract(detail.value.id, { file_url: detail.value.file_url || '' })
    ElMessage.success('合同文件已更新')
    loadList()
  } catch {
    /* 已提示 */
  }
}

onMounted(async () => {
  await Promise.all([loadList(), loadOptions()])
})
</script>

<template>
  <div class="page-container">
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
                placeholder="合同号 / 标题 / 企业"
                clearable
                style="width: 220px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="contractStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="关联订单">
              <el-select v-model="query.order_id" placeholder="全部订单" clearable filterable style="width: 220px">
                <el-option v-for="item in orders" :key="item.id" :label="item.order_no" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'trade:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>生成合同</span>
        </el-button>
      </template>

      <el-table-column prop="contract_no" label="合同编号" width="170">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="openDetail(row as Contract)">{{ row.contract_no }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="合同标题" min-width="220" show-overflow-tooltip />
      <el-table-column prop="order_no" label="关联订单" width="170">
        <template #default="{ row }">{{ row.order_no || (row.order_id ? `#${row.order_id}` : '-') }}</template>
      </el-table-column>
      <el-table-column prop="buyer_enterprise_name" label="买方" min-width="150" show-overflow-tooltip />
      <el-table-column prop="supplier_enterprise_name" label="卖方" min-width="150" show-overflow-tooltip />
      <el-table-column label="合同金额" width="140" align="right">
        <template #default="{ row }">
          <span class="text-amount">{{ formatMoney(row.amount) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="签署情况" min-width="170">
        <template #default="{ row }">
          <el-tag size="small" :type="row.signed_by_buyer ? 'success' : 'info'" class="mr-4">
            买方{{ row.signed_by_buyer ? '已签' : '未签' }}
          </el-tag>
          <el-tag size="small" :type="row.signed_by_supplier ? 'success' : 'info'">
            卖方{{ row.signed_by_supplier ? '已签' : '未签' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <StatusTag group="contractStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row as Contract)">详情</el-button>
          <el-button
            v-if="!row.signed_by_buyer"
            v-permission="'trade:write'"
            link
            type="success"
            @click="openSign(row as Contract, 'buyer')"
          >
            买方签署
          </el-button>
          <el-button
            v-if="!row.signed_by_supplier"
            v-permission="'trade:write'"
            link
            type="success"
            @click="openSign(row as Contract, 'supplier')"
          >
            卖方签署
          </el-button>
          <el-button v-permission="'trade:write'" link type="primary" @click="openEdit(row as Contract)">编辑</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 新建 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="680px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="24">
            <el-form-item label="关联订单">
              <el-select
                v-model="form.order_id"
                placeholder="可由订单生成合同"
                clearable
                filterable
                style="width: 100%"
                @change="handleOrderChange"
              >
                <el-option v-for="item in orders" :key="item.id" :label="item.order_no" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="合同标题" prop="title">
              <el-input v-model="form.title" placeholder="如 瓜子油料购销合同" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="买方">
              <el-select v-model="form.buyer_enterprise_id" clearable filterable style="width: 100%">
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="卖方">
              <el-select v-model="form.supplier_enterprise_id" clearable filterable style="width: 100%">
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同金额">
              <el-input v-model="form.amount" placeholder="元">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="签署日期">
              <el-date-picker
                v-model="form.sign_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生效日期">
              <el-date-picker
                v-model="form.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到期日期">
              <el-date-picker
                v-model="form.end_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="合同文件">
              <FileUpload v-model="form.file_url" biz-type="contract" accept=".pdf,.jpg,.png,.doc,.docx" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 签署确认 -->
    <el-dialog v-model="signVisible" title="合同签署" width="440px" append-to-body>
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        :title="`将以「${signParty === 'buyer' ? '买方' : '卖方'}」身份签署合同 ${signTarget?.contract_no || ''}，双方签署完成后合同自动生效。`"
      />
      <el-form class="mt-12" label-width="90px">
        <el-form-item label="签署身份">
          <el-radio-group v-model="signParty">
            <el-radio value="buyer">买方</el-radio>
            <el-radio value="supplier">卖方</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signVisible = false">取消</el-button>
        <el-button type="primary" :loading="signSubmitting" @click="submitSign">确认签署</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="合同详情" size="600px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="合同编号" :span="2">{{ detail.contract_no }}</el-descriptions-item>
            <el-descriptions-item label="合同标题" :span="2">{{ detail.title }}</el-descriptions-item>
            <el-descriptions-item label="关联订单">
              {{ detail.order_no || (detail.order_id ? `#${detail.order_id}` : '-') }}
            </el-descriptions-item>
            <el-descriptions-item label="合同金额">{{ formatMoney(detail.amount) }} 元</el-descriptions-item>
            <el-descriptions-item label="买方">{{ detail.buyer_enterprise_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="卖方">{{ detail.supplier_enterprise_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="签署日期">{{ formatDate(detail.sign_date) }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <StatusTag group="contractStatus" :value="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="生效日期">{{ formatDate(detail.start_date) }}</el-descriptions-item>
            <el-descriptions-item label="到期日期">{{ formatDate(detail.end_date) }}</el-descriptions-item>
            <el-descriptions-item label="买方签署">
              {{ detail.signed_by_buyer ? formatDateTime(detail.buyer_signed_at) : '未签署' }}
            </el-descriptions-item>
            <el-descriptions-item label="卖方签署">
              {{ detail.signed_by_supplier ? formatDateTime(detail.supplier_signed_at) : '未签署' }}
            </el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
          </el-descriptions>

          <div class="detail-block">
            <div class="detail-block__title">合同文件</div>
            <FileUpload v-model="detail.file_url" biz-type="contract" accept=".pdf,.jpg,.png,.doc,.docx" />
            <el-button class="mt-8" size="small" type="primary" @click="handleFileSave">保存文件地址</el-button>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.mr-4 {
  margin-right: 4px;
}

.detail-block {
  margin-top: 16px;
}

.detail-block__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}
</style>
