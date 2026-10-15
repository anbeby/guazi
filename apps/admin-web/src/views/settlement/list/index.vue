<script setup lang="ts">
/**
 * 结算单：查询 / 手工生成（按企业+期间归集已完成订单）/ 确认 / 登记回款。
 * 接口：GET/POST /settlements、GET /settlements/{id}、POST /settlements/{id}/confirm、POST /settlements/{id}/payment
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import {
  confirmSettlement,
  createSettlement,
  getSettlement,
  listSettlements,
  registerSettlementPayment
} from '@/api/settlement'
import { listEnterprises } from '@/api/enterprise'
import type {
  Enterprise,
  PayMethod,
  Settlement,
  SettlementPayload,
  SettlementQuery
} from '@/api/types'
import { formatDate, formatDateTime, formatMoney } from '@/utils/format'

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<Settlement[]>([])
const total = ref(0)
const enterprises = ref<Enterprise[]>([])
const query = reactive<SettlementQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  enterprise_id: null,
  settle_type: '',
  status: '',
  pay_status: '',
  start_date: '',
  end_date: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listSettlements(query)
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
  query.enterprise_id = null
  query.settle_type = ''
  query.status = ''
  query.pay_status = ''
  query.start_date = ''
  query.end_date = ''
  query.page = 1
  loadList()
}

async function loadEnterprises(): Promise<void> {
  try {
    const data = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = data.items || []
  } catch {
    enterprises.value = []
  }
}

/* ---------------- 手工生成 ---------------- */
const createVisible = ref(false)
const createSubmitting = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<SettlementPayload>({
  enterprise_id: undefined as unknown as number,
  settle_type: 'receivable',
  period_start: '',
  period_end: '',
  remark: ''
})

const createRules: FormRules = {
  enterprise_id: [{ required: true, message: '请选择结算企业', trigger: 'change' }],
  settle_type: [{ required: true, message: '请选择结算类型', trigger: 'change' }],
  period_start: [{ required: true, message: '请选择结算期间开始日期', trigger: 'change' }],
  period_end: [{ required: true, message: '请选择结算期间结束日期', trigger: 'change' }]
}

function openCreate(): void {
  Object.assign(createForm, {
    enterprise_id: undefined,
    settle_type: 'receivable',
    period_start: '',
    period_end: '',
    remark: ''
  })
  createVisible.value = true
}

async function submitCreate(): Promise<void> {
  const el = createFormRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    createSubmitting.value = true
    try {
      await createSettlement({ ...createForm })
      ElMessage.success('结算单已生成')
      createVisible.value = false
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      createSubmitting.value = false
    }
  })
}

/* ---------------- 确认 ---------------- */
async function handleConfirm(row: Settlement): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认结算单「${row.settlement_no}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '确认结算',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await confirmSettlement(row.id)
    ElMessage.success('结算单已确认')
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 登记回款 ---------------- */
const paymentVisible = ref(false)
const paymentSubmitting = ref(false)
const paymentTarget = ref<Settlement | null>(null)
const paymentForm = reactive<{ amount: string; pay_method: PayMethod; trade_no: string; remark: string }>({
  amount: '',
  pay_method: 'bank_transfer',
  trade_no: '',
  remark: ''
})

function openPayment(row: Settlement): void {
  paymentTarget.value = row
  const remain = Number(row.settle_amount || 0) - Number(row.settled_amount || 0)
  paymentForm.amount = remain > 0 ? remain.toFixed(2) : ''
  paymentForm.pay_method = 'bank_transfer'
  paymentForm.trade_no = ''
  paymentForm.remark = ''
  paymentVisible.value = true
}

async function submitPayment(): Promise<void> {
  if (!paymentTarget.value) return
  if (!paymentForm.amount || Number(paymentForm.amount) <= 0) {
    ElMessage.warning('请输入正确的回款金额')
    return
  }
  paymentSubmitting.value = true
  try {
    await registerSettlementPayment(paymentTarget.value.id, {
      amount: paymentForm.amount,
      pay_method: paymentForm.pay_method,
      trade_no: paymentForm.trade_no,
      remark: paymentForm.remark
    })
    ElMessage.success('回款登记成功')
    paymentVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  } finally {
    paymentSubmitting.value = false
  }
}

/* ---------------- 详情 ---------------- */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<Settlement | null>(null)

async function openDetail(row: Settlement): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = row
  try {
    detail.value = await getSettlement(row.id)
  } catch {
    /* 使用列表数据 */
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadList(), loadEnterprises()])
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
                placeholder="结算单号 / 企业"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="企业">
              <el-select v-model="query.enterprise_id" placeholder="全部企业" clearable filterable style="width: 200px">
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="结算类型">
              <DictSelect v-model="query.settle_type" group="settleType" with-all placeholder="全部类型" />
            </el-form-item>
            <el-form-item label="支付状态">
              <DictSelect v-model="query.pay_status" group="payStatus" with-all placeholder="全部" />
            </el-form-item>
            <el-form-item label="单据状态">
              <DictSelect v-model="query.status" group="settlementStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="期间">
              <el-date-picker
                v-model="query.start_date"
                type="date"
                placeholder="开始日期"
                value-format="YYYY-MM-DD"
                style="width: 150px"
              />
              <span class="date-sep">-</span>
              <el-date-picker
                v-model="query.end_date"
                type="date"
                placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 150px"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'settlement:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>手工生成结算单</span>
        </el-button>
      </template>

      <el-table-column prop="settlement_no" label="结算单号" width="180">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="openDetail(row as Settlement)">{{ row.settlement_no }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="enterprise_name" label="结算企业" min-width="180" show-overflow-tooltip />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <StatusTag group="settleType" :value="row.settle_type" />
        </template>
      </el-table-column>
      <el-table-column label="结算期间" width="200">
        <template #default="{ row }">{{ formatDate(row.period_start) }} ~ {{ formatDate(row.period_end) }}</template>
      </el-table-column>
      <el-table-column label="订单金额" width="140" align="right">
        <template #default="{ row }">{{ formatMoney(row.order_amount) }}</template>
      </el-table-column>
      <el-table-column label="服务费" width="120" align="right">
        <template #default="{ row }">{{ formatMoney(row.fee_amount) }}</template>
      </el-table-column>
      <el-table-column label="应结金额" width="140" align="right">
        <template #default="{ row }">
          <span class="text-amount">{{ formatMoney(row.settle_amount) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="已结金额" width="140" align="right">
        <template #default="{ row }">{{ formatMoney(row.settled_amount) }}</template>
      </el-table-column>
      <el-table-column label="支付状态" width="100">
        <template #default="{ row }">
          <StatusTag group="payStatus" :value="row.pay_status" />
        </template>
      </el-table-column>
      <el-table-column label="单据状态" width="100">
        <template #default="{ row }">
          <StatusTag group="settlementStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row as Settlement)">详情</el-button>
          <el-button
            v-if="row.status === 'pending'"
            v-permission="'settlement:write'"
            link
            type="success"
            @click="handleConfirm(row as Settlement)"
          >
            确认
          </el-button>
          <el-button
            v-if="row.pay_status !== 'paid'"
            v-permission="'settlement:write'"
            link
            type="primary"
            @click="openPayment(row as Settlement)"
          >
            登记回款
          </el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 手工生成 -->
    <el-dialog v-model="createVisible" title="手工生成结算单" width="600px" append-to-body>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-form-item label="结算企业" prop="enterprise_id">
          <el-select v-model="createForm.enterprise_id" placeholder="请选择企业" filterable style="width: 100%">
            <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="结算类型" prop="settle_type">
          <DictSelect v-model="createForm.settle_type" group="settleType" :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="期间开始" prop="period_start">
          <el-date-picker
            v-model="createForm.period_start"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="期间结束" prop="period_end">
          <el-date-picker
            v-model="createForm.period_end"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="系统将按「企业 + 期间」归集已完成订单，并按平台服务费率计提服务费写入结算明细"
      />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">生成</el-button>
      </template>
    </el-dialog>

    <!-- 登记回款 -->
    <el-dialog v-model="paymentVisible" title="登记回款" width="520px" append-to-body>
      <el-form label-width="100px">
        <el-form-item label="结算单号">
          <span>{{ paymentTarget?.settlement_no }}</span>
        </el-form-item>
        <el-form-item label="应结金额">
          <span class="text-amount">{{ formatMoney(paymentTarget?.settle_amount) }} 元</span>
        </el-form-item>
        <el-form-item label="已结金额">
          <span>{{ formatMoney(paymentTarget?.settled_amount) }} 元</span>
        </el-form-item>
        <el-form-item label="本次回款">
          <el-input v-model="paymentForm.amount" placeholder="如 100000.00">
            <template #append>元</template>
          </el-input>
        </el-form-item>
        <el-form-item label="支付方式">
          <DictSelect v-model="paymentForm.pay_method" group="payMethod" :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="交易流水号">
          <el-input v-model="paymentForm.trade_no" placeholder="银行回单号 / 转账流水号" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="paymentForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="平台不自建支付通道，仅登记交易流水与凭证（payment_record）"
      />
      <template #footer>
        <el-button @click="paymentVisible = false">取消</el-button>
        <el-button type="primary" :loading="paymentSubmitting" @click="submitPayment">登记</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="结算单详情" size="640px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="结算单号" :span="2">{{ detail.settlement_no }}</el-descriptions-item>
            <el-descriptions-item label="结算企业" :span="2">{{ detail.enterprise_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="结算类型">
              <StatusTag group="settleType" :value="detail.settle_type" />
            </el-descriptions-item>
            <el-descriptions-item label="单据状态">
              <StatusTag group="settlementStatus" :value="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="期间开始">{{ formatDate(detail.period_start) }}</el-descriptions-item>
            <el-descriptions-item label="期间结束">{{ formatDate(detail.period_end) }}</el-descriptions-item>
            <el-descriptions-item label="订单金额">{{ formatMoney(detail.order_amount) }} 元</el-descriptions-item>
            <el-descriptions-item label="服务费">{{ formatMoney(detail.fee_amount) }} 元</el-descriptions-item>
            <el-descriptions-item label="应结金额">
              <span class="text-amount">{{ formatMoney(detail.settle_amount) }} 元</span>
            </el-descriptions-item>
            <el-descriptions-item label="已结金额">{{ formatMoney(detail.settled_amount) }} 元</el-descriptions-item>
            <el-descriptions-item label="支付状态">
              <StatusTag group="payStatus" :value="detail.pay_status" />
            </el-descriptions-item>
            <el-descriptions-item label="收款状态">
              <StatusTag group="receiveStatus" :value="detail.receive_status" />
            </el-descriptions-item>
            <el-descriptions-item label="确认时间">{{ formatDateTime(detail.confirmed_at) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
          </el-descriptions>

          <div class="detail-block">
            <div class="detail-block__title">结算明细（settlement_line）</div>
            <el-table :data="detail.lines || []" border stripe>
              <el-table-column label="业务类型" width="110">
                <template #default="{ row }">
                  <StatusTag group="bizType" :value="row.biz_type" />
                </template>
              </el-table-column>
              <el-table-column prop="biz_no" label="业务单号" min-width="170" />
              <el-table-column label="金额" width="140" align="right">
                <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
              </el-table-column>
              <el-table-column label="费率" width="90" align="right">
                <template #default="{ row }">{{ row.fee_rate ? `${row.fee_rate}` : '-' }}</template>
              </el-table-column>
              <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
            </el-table>
          </div>

          <div class="drawer-footer">
            <el-button
              v-if="detail.status === 'pending'"
              v-permission="'settlement:write'"
              type="success"
              @click="handleConfirm(detail)"
            >
              确认结算单
            </el-button>
            <el-button
              v-if="detail.pay_status !== 'paid'"
              v-permission="'settlement:write'"
              type="primary"
              @click="openPayment(detail)"
            >
              登记回款
            </el-button>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.date-sep {
  margin: 0 6px;
  color: var(--gz-text-sub);
}

.detail-block {
  margin-top: 16px;
}

.detail-block__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>
