<script setup lang="ts">
/**
 * 交易流水与对账单：「交易流水」页签（GET /finance/flows）与「对账单」页签（GET /finance/statement）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import { getFinanceStatement, listFinanceFlows } from '@/api/settlement'
import { listEnterprises } from '@/api/enterprise'
import type {
  Enterprise,
  FlowQuery,
  StatementResult,
  TransactionFlow
} from '@/api/types'
import { formatDate, formatDateTime, formatMoney } from '@/utils/format'
import { exportCsv, printHtml } from '@/utils/download'

const activeTab = ref<'flows' | 'statement'>('flows')
const enterprises = ref<Enterprise[]>([])

const flowQuery = reactive<FlowQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  enterprise_id: null,
  direction: '',
  pay_status: '',
  biz_type: '',
  start_date: '',
  end_date: ''
})

/* ---------------- 流水 ---------------- */
const flowLoading = ref(false)
const flows = ref<TransactionFlow[]>([])
const flowTotal = ref(0)

async function loadFlows(): Promise<void> {
  flowLoading.value = true
  try {
    const data = await listFinanceFlows(flowQuery)
    flows.value = data.items || []
    flowTotal.value = data.total || 0
  } catch {
    flows.value = []
    flowTotal.value = 0
  } finally {
    flowLoading.value = false
  }
}

function handleFlowSearch(): void {
  flowQuery.page = 1
  loadFlows()
}

function handleFlowReset(): void {
  flowQuery.keyword = ''
  flowQuery.enterprise_id = null
  flowQuery.direction = ''
  flowQuery.pay_status = ''
  flowQuery.biz_type = ''
  flowQuery.start_date = ''
  flowQuery.end_date = ''
  flowQuery.page = 1
  loadFlows()
}

/** 当前页流水合计 */
const flowTotals = computed(() => {
  let income = 0
  let expense = 0
  flows.value.forEach((item) => {
    const amount = Number(item.amount || 0)
    if (item.direction === 'in') income += amount
    else expense += amount
  })
  return { income, expense }
})

/* ---------------- 对账单 ---------------- */
const statementQuery = reactive<{
  enterprise_id: number | undefined
  start_date: string
  end_date: string
}>({
  enterprise_id: undefined,
  start_date: '',
  end_date: ''
})

const statementLoading = ref(false)
const statement = ref<StatementResult | null>(null)

async function loadStatement(): Promise<void> {
  if (!statementQuery.enterprise_id) {
    ElMessage.warning('请先选择对账企业')
    return
  }
  if (!statementQuery.start_date || !statementQuery.end_date) {
    ElMessage.warning('请选择对账期间')
    return
  }
  statementLoading.value = true
  try {
    statement.value = await getFinanceStatement({
      enterprise_id: statementQuery.enterprise_id,
      start_date: statementQuery.start_date,
      end_date: statementQuery.end_date
    })
  } catch {
    statement.value = null
  } finally {
    statementLoading.value = false
  }
}

function handleTabChange(): void {
  if (activeTab.value === 'flows' && flows.value.length === 0) loadFlows()
}

async function loadEnterprises(): Promise<void> {
  try {
    const data = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = data.items || []
  } catch {
    enterprises.value = []
  }
}

/* ---------------- 导出 / 打印 ---------------- */
function exportFlows(): void {
  if (flows.value.length === 0) {
    ElMessage.warning('当前无流水数据可导出')
    return
  }
  exportCsv(
    flows.value.map((item) => ({
      flow_no: item.flow_no,
      order_no: item.order_no || '',
      enterprise_name: item.enterprise_name || '',
      counterparty: item.counterparty_enterprise_name || '',
      direction: item.direction === 'in' ? '收入' : '支出',
      biz_type: item.biz_type,
      amount: item.amount,
      pay_method: item.pay_method || '',
      pay_status: item.pay_status,
      trade_no: item.trade_no || '',
      created_at: item.created_at
    })),
    [
      { key: 'flow_no', label: '流水号' },
      { key: 'order_no', label: '关联订单' },
      { key: 'enterprise_name', label: '企业' },
      { key: 'counterparty', label: '对方企业' },
      { key: 'direction', label: '方向' },
      { key: 'biz_type', label: '业务类型' },
      { key: 'amount', label: '金额(元)' },
      { key: 'pay_method', label: '支付方式' },
      { key: 'pay_status', label: '支付状态' },
      { key: 'trade_no', label: '交易流水号' },
      { key: 'created_at', label: '发生时间' }
    ],
    `交易流水_${Date.now()}.csv`
  )
}

function printStatement(): void {
  const data = statement.value
  if (!data) {
    ElMessage.warning('请先生成对账单')
    return
  }
  const rows = (data.flows || [])
    .map(
      (item) => `<tr>
        <td>${item.flow_no}</td>
        <td>${item.order_no || '-'}</td>
        <td>${item.direction === 'in' ? '收入' : '支出'}</td>
        <td>${formatMoney(item.amount)}</td>
        <td>${item.pay_status}</td>
        <td>${formatDate(item.created_at)}</td>
      </tr>`
    )
    .join('')
  printHtml(
    '对账单',
    `<h1>第十师瓜子油料数字化交易平台 · 对账单</h1>
     <p>企业：${data.summary?.enterprise_name || '-'}</p>
     <p>期间：${data.summary?.start_date || ''} ~ ${data.summary?.end_date || ''}</p>
     <table>
       <thead>
         <tr><th>流水号</th><th>关联订单</th><th>方向</th><th>金额(元)</th><th>支付状态</th><th>日期</th></tr>
       </thead>
       <tbody>${rows}</tbody>
     </table>
     <p style="margin-top:12px">应收：${formatMoney(data.summary?.receivable_amount)} 元 ｜ 应付：${formatMoney(data.summary?.payable_amount)} 元</p>`
  )
}

function openFlowsDownload(): void {
  if (flows.value.length === 0) {
    ElMessage.warning('当前无流水数据可下载')
    return
  }
  exportCsv(
    flows.value.map((item) => ({
      flow_no: item.flow_no,
      order_no: item.order_no || '',
      enterprise_name: item.enterprise_name || '',
      direction: item.direction === 'in' ? '收入' : '支出',
      biz_type: item.biz_type,
      amount: item.amount,
      pay_status: item.pay_status,
      created_at: item.created_at
    })),
    [
      { key: 'flow_no', label: '流水号' },
      { key: 'order_no', label: '关联订单' },
      { key: 'enterprise_name', label: '企业' },
      { key: 'direction', label: '方向' },
      { key: 'biz_type', label: '业务类型' },
      { key: 'amount', label: '金额(元)' },
      { key: 'pay_status', label: '支付状态' },
      { key: 'created_at', label: '发生时间' }
    ],
    `交易流水_${Date.now()}.csv`
  )
}

onMounted(async () => {
  await Promise.all([loadFlows(), loadEnterprises()])
})
</script>

<template>
  <div class="page-container">
    <div class="page-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="交易流水" name="flows" />
        <el-tab-pane label="对账单" name="statement" />
      </el-tabs>

      <!-- 交易流水 -->
      <template v-if="activeTab === 'flows'">
        <el-form class="search-form" :inline="true" @submit.prevent>
          <el-form-item label="关键词">
            <el-input
              v-model="flowQuery.keyword"
              placeholder="流水号 / 订单号 / 交易流水号"
              clearable
              style="width: 220px"
              @keyup.enter="handleFlowSearch"
            />
          </el-form-item>
          <el-form-item label="企业">
            <el-select
              v-model="flowQuery.enterprise_id"
              placeholder="全部企业"
              clearable
              filterable
              style="width: 200px"
            >
              <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="方向">
            <DictSelect v-model="flowQuery.direction" group="flowDirection" with-all placeholder="全部" />
          </el-form-item>
          <el-form-item label="业务类型">
            <DictSelect v-model="flowQuery.biz_type" group="flowBizType" with-all placeholder="全部" />
          </el-form-item>
          <el-form-item label="支付状态">
            <DictSelect v-model="flowQuery.pay_status" group="flowPayStatus" with-all placeholder="全部" />
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker
              v-model="flowQuery.start_date"
              type="date"
              placeholder="开始日期"
              value-format="YYYY-MM-DD"
              style="width: 150px"
            />
            <span class="date-sep">-</span>
            <el-date-picker
              v-model="flowQuery.end_date"
              type="date"
              placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 150px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleFlowSearch">查询</el-button>
            <el-button @click="handleFlowReset">重置</el-button>
            <el-button @click="exportFlows">
              <el-icon><Download /></el-icon>
              <span>导出 CSV</span>
            </el-button>
          </el-form-item>
        </el-form>

        <div class="flow-total">
          当前页合计：收入 <b class="text-success">{{ formatMoney(flowTotals.income) }}</b> 元 · 支出
          <b class="text-danger">{{ formatMoney(flowTotals.expense) }}</b> 元
        </div>

        <el-table v-loading="flowLoading" :data="flows" border stripe>
          <el-table-column prop="flow_no" label="流水号" width="170" />
          <el-table-column prop="order_no" label="关联订单" width="170">
            <template #default="{ row }">{{ row.order_no || (row.order_id ? `#${row.order_id}` : '-') }}</template>
          </el-table-column>
          <el-table-column prop="enterprise_name" label="所属企业" min-width="160" show-overflow-tooltip />
          <el-table-column
            prop="counterparty_enterprise_name"
            label="对方企业"
            min-width="160"
            show-overflow-tooltip
          />
          <el-table-column label="方向" width="90">
            <template #default="{ row }">
              <StatusTag group="flowDirection" :value="row.direction" />
            </template>
          </el-table-column>
          <el-table-column label="业务类型" width="110">
            <template #default="{ row }">
              <StatusTag group="flowBizType" :value="row.biz_type" />
            </template>
          </el-table-column>
          <el-table-column label="金额" width="140" align="right">
            <template #default="{ row }">
              <span :class="row.direction === 'in' ? 'text-success' : 'text-danger'">
                {{ row.direction === 'in' ? '+' : '-' }}{{ formatMoney(row.amount) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="支付方式" width="110">
            <template #default="{ row }">
              {{ row.pay_method ? row.pay_method : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="支付状态" width="110">
            <template #default="{ row }">
              <StatusTag group="flowPayStatus" :value="row.pay_status" />
            </template>
          </el-table-column>
          <el-table-column prop="trade_no" label="交易流水号" min-width="150" show-overflow-tooltip />
          <el-table-column label="发生时间" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>

        <div class="table-pagination">
          <el-pagination
            v-model:current-page="flowQuery.page"
            v-model:page-size="flowQuery.page_size"
            :total="flowTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @current-change="loadFlows"
            @size-change="loadFlows"
          />
        </div>
      </template>

      <!-- 对账单 -->
      <template v-else>
        <el-form class="search-form" :inline="true" @submit.prevent>
          <el-form-item label="对账企业">
            <el-select
              v-model="statementQuery.enterprise_id"
              placeholder="请选择企业"
              filterable
              style="width: 240px"
            >
              <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="期间">
            <el-date-picker
              v-model="statementQuery.start_date"
              type="date"
              placeholder="开始日期"
              value-format="YYYY-MM-DD"
              style="width: 150px"
            />
            <span class="date-sep">-</span>
            <el-date-picker
              v-model="statementQuery.end_date"
              type="date"
              placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 150px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="statementLoading" @click="loadStatement">生成对账单</el-button>
            <el-button :disabled="!statement" @click="printStatement">
              <el-icon><Printer /></el-icon>
              <span>打印</span>
            </el-button>
            <el-button @click="openFlowsDownload">
              <el-icon><Download /></el-icon>
              <span>下载流水</span>
            </el-button>
          </el-form-item>
        </el-form>

        <template v-if="statement">
          <el-descriptions :column="4" border class="mb-12">
            <el-descriptions-item label="企业名称" :span="2">
              {{ statement.summary?.enterprise_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="对账期间" :span="2">
              {{ statement.summary?.start_date || '-' }} ~ {{ statement.summary?.end_date || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="订单数">{{ statement.summary?.order_count ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="订单金额">
              {{ formatMoney(statement.summary?.order_amount) }}
            </el-descriptions-item>
            <el-descriptions-item label="应收金额">
              {{ formatMoney(statement.summary?.receivable_amount) }}
            </el-descriptions-item>
            <el-descriptions-item label="应付金额">
              {{ formatMoney(statement.summary?.payable_amount) }}
            </el-descriptions-item>
            <el-descriptions-item label="已收金额">
              {{ formatMoney(statement.summary?.received_amount) }}
            </el-descriptions-item>
            <el-descriptions-item label="已付金额">
              {{ formatMoney(statement.summary?.paid_amount) }}
            </el-descriptions-item>
            <el-descriptions-item label="未收金额">
              <span class="text-amount">{{ formatMoney(statement.summary?.unreceived_amount) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="服务费">
              {{ formatMoney(statement.summary?.service_fee_amount) }}
            </el-descriptions-item>
          </el-descriptions>

          <el-table :data="statement.flows || []" border stripe>
            <el-table-column prop="flow_no" label="流水号" width="170" />
            <el-table-column prop="order_no" label="关联订单" width="170" />
            <el-table-column label="方向" width="90">
              <template #default="{ row }">
                <StatusTag group="flowDirection" :value="row.direction" />
              </template>
            </el-table-column>
            <el-table-column label="业务类型" width="110">
              <template #default="{ row }">
                <StatusTag group="flowBizType" :value="row.biz_type" />
              </template>
            </el-table-column>
            <el-table-column label="金额" width="140" align="right">
              <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="支付状态" width="110">
              <template #default="{ row }">
                <StatusTag group="flowPayStatus" :value="row.pay_status" />
              </template>
            </el-table-column>
            <el-table-column label="日期" width="120">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </template>

        <el-empty v-else description="请选择企业与期间后生成对账单" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.date-sep {
  margin: 0 6px;
  color: var(--gz-text-sub);
}

.flow-total {
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--gz-text-sub);
}

.text-success {
  color: #16653f;
}

.text-danger {
  color: #c0392b;
}
</style>
