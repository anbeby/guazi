<script setup lang="ts">
/**
 * 询价详情 + 报价列表 + 供应商报价 + 采购商接受/拒绝报价（接受后自动生成订单）。
 * 接口：GET /inquiries/{id}、GET/POST /inquiries/{id}/quotations、POST /quotations/{id}/accept|reject、/inquiries/{id}/submit|cancel
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import StatusTag from '@/components/StatusTag.vue'
import {
  acceptQuotation,
  cancelInquiry,
  createQuotation,
  getInquiry,
  listInquiryQuotations,
  rejectQuotation,
  submitInquiry
} from '@/api/trade'
import type { Inquiry, Quotation, QuotationPayload } from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity, unitLabel } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const inquiryId = computed(() => Number(route.params.id))

const loading = ref(false)
const inquiry = ref<Inquiry | null>(null)
const quotations = ref<Quotation[]>([])
const quotationLoading = ref(false)

async function loadDetail(): Promise<void> {
  if (!inquiryId.value) return
  loading.value = true
  try {
    inquiry.value = await getInquiry(inquiryId.value)
    if (inquiry.value?.quotations && inquiry.value.quotations.length > 0) {
      quotations.value = inquiry.value.quotations
    } else {
      await loadQuotations()
    }
  } catch {
    inquiry.value = null
  } finally {
    loading.value = false
  }
}

async function loadQuotations(): Promise<void> {
  if (!inquiryId.value) return
  quotationLoading.value = true
  try {
    quotations.value = await listInquiryQuotations(inquiryId.value)
  } catch {
    quotations.value = []
  } finally {
    quotationLoading.value = false
  }
}

/* ---------------- 供应商报价 ---------------- */
const quoteVisible = ref(false)
const quoteSubmitting = ref(false)
const quoteFormRef = ref<FormInstance>()
const quoteForm = reactive<QuotationPayload>({
  quantity: '',
  unit_price: '',
  tax_rate: '9',
  valid_until: '',
  delivery_date: '',
  payment_terms: '款到发货',
  remark: ''
})

const quoteRules: FormRules = {
  unit_price: [{ required: true, message: '请输入报价单价', trigger: 'blur' }]
}

function openQuote(): void {
  Object.assign(quoteForm, {
    quantity: inquiry.value?.quantity || '',
    unit_price: '',
    tax_rate: '9',
    valid_until: '',
    delivery_date: inquiry.value?.expect_delivery_date || '',
    payment_terms: '款到发货',
    remark: ''
  })
  quoteVisible.value = true
}

const quoteAmount = computed(() => {
  const qty = Number(quoteForm.quantity || 0)
  const price = Number(quoteForm.unit_price || 0)
  if (!qty || !price) return '-'
  return formatMoney(qty * price)
})

async function submitQuote(): Promise<void> {
  const el = quoteFormRef.value
  if (!el || !inquiryId.value) return
  await el.validate(async (valid) => {
    if (!valid) return
    quoteSubmitting.value = true
    try {
      await createQuotation(inquiryId.value, { ...quoteForm })
      ElMessage.success('报价已提交')
      quoteVisible.value = false
      await loadDetail()
    } catch {
      /* 已提示 */
    } finally {
      quoteSubmitting.value = false
    }
  })
}

/* ---------------- 接受 / 拒绝报价 ---------------- */
async function handleAccept(row: Quotation): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认接受报价「${row.quotation_no}」？系统将按该报价生成订单（状态：待确认）。`,
      '确认接受报价',
      { type: 'warning', confirmButtonText: '接受并生成订单', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const order = await acceptQuotation(row.id)
    ElMessage.success('已接受报价并生成订单')
    if (order?.id) {
      router.push(`/trade/order/${order.id}`)
    } else {
      loadDetail()
    }
  } catch {
    /* 已提示 */
  }
}

async function handleReject(row: Quotation): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认拒绝报价「${row.quotation_no}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '拒绝',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await rejectQuotation(row.id)
    ElMessage.success('已拒绝该报价')
    loadDetail()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 提交 / 取消询价 ---------------- */
async function handleSubmitInquiry(): Promise<void> {
  if (!inquiry.value) return
  try {
    await submitInquiry(inquiry.value.id)
    ElMessage.success('询价单已提交')
    loadDetail()
  } catch {
    /* 已提示 */
  }
}

async function handleCancelInquiry(): Promise<void> {
  if (!inquiry.value) return
  try {
    await ElMessageBox.confirm('确认取消该询价单？', '提示', {
      type: 'warning',
      confirmButtonText: '取消询价',
      cancelButtonText: '返回'
    })
  } catch {
    return
  }
  try {
    await cancelInquiry(inquiry.value.id)
    ElMessage.success('询价单已取消')
    loadDetail()
  } catch {
    /* 已提示 */
  }
}

onMounted(loadDetail)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-card">
      <div class="page-title">
        <span>
          询价单详情
          <span class="page-title__sub">{{ inquiry?.inquiry_no || '' }}</span>
        </span>
        <div class="flex-center" style="gap: 8px">
          <el-button size="small" @click="router.back()">返回</el-button>
          <el-button size="small" @click="loadDetail">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </el-button>
          <el-button
            v-if="inquiry?.status === 'draft'"
            v-permission="'trade:write'"
            size="small"
            type="success"
            @click="handleSubmitInquiry"
          >
            提交询价
          </el-button>
          <el-button
            v-if="inquiry && ['draft', 'submitted', 'quoted'].includes(inquiry.status)"
            v-permission="'trade:write'"
            size="small"
            type="danger"
            @click="handleCancelInquiry"
          >
            取消询价
          </el-button>
          <el-button
            v-if="inquiry && ['submitted', 'quoted'].includes(inquiry.status)"
            v-permission="'trade:write'"
            size="small"
            type="primary"
            @click="openQuote"
          >
            我要报价
          </el-button>
        </div>
      </div>

      <template v-if="inquiry">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="询价单号">{{ inquiry.inquiry_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag group="inquiryStatus" :value="inquiry.status" />
          </el-descriptions-item>
          <el-descriptions-item label="报价数">{{ inquiry.quoted_count }}</el-descriptions-item>
          <el-descriptions-item label="采购商品">{{ inquiry.product_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="商品编码">{{ inquiry.product_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购数量">
            {{ formatQuantity(inquiry.quantity) }} {{ unitLabel(inquiry.unit) }}
          </el-descriptions-item>
          <el-descriptions-item label="期望单价">
            {{ inquiry.expect_price ? `${formatMoney(inquiry.expect_price)} 元` : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="期望交期">{{ inquiry.expect_delivery_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="交货地址">{{ inquiry.delivery_address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="采购商">{{ inquiry.buyer_enterprise_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="指定供应商">
            {{ inquiry.supplier_enterprise_name || '公开询价' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(inquiry.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ inquiry.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <el-empty v-else-if="!loading" description="询价单不存在或无权访问" />
    </div>

    <div class="page-card">
      <div class="page-title">
        <span>
          报价列表
          <span class="page-title__sub">共 {{ quotations.length }} 条报价</span>
        </span>
        <el-button size="small" @click="loadQuotations">
          <el-icon><Refresh /></el-icon>
          <span>刷新报价</span>
        </el-button>
      </div>

      <el-table v-loading="quotationLoading" :data="quotations" border stripe>
        <el-table-column prop="quotation_no" label="报价单号" width="170" />
        <el-table-column prop="supplier_enterprise_name" label="供应商" min-width="180" show-overflow-tooltip />
        <el-table-column label="报价数量" width="120" align="right">
          <template #default="{ row }">{{ formatQuantity(row.quantity) }} {{ unitLabel(row.unit) }}</template>
        </el-table-column>
        <el-table-column label="报价单价" width="120" align="right">
          <template #default="{ row }">{{ formatMoney(row.unit_price) }}</template>
        </el-table-column>
        <el-table-column label="报价金额" width="140" align="right">
          <template #default="{ row }">
            <span class="text-amount">{{ formatMoney(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="税率" width="80" align="right">
          <template #default="{ row }">{{ row.tax_rate ? `${row.tax_rate}%` : '-' }}</template>
        </el-table-column>
        <el-table-column label="交货日期" width="120">
          <template #default="{ row }">{{ row.delivery_date || '-' }}</template>
        </el-table-column>
        <el-table-column label="有效期至" width="120">
          <template #default="{ row }">{{ row.valid_until || '-' }}</template>
        </el-table-column>
        <el-table-column prop="payment_terms" label="付款条件" min-width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag group="quotationStatus" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="报价时间" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'submitted'"
              v-permission="'trade:write'"
              link
              type="success"
              @click="handleAccept(row as Quotation)"
            >
              接受
            </el-button>
            <el-button
              v-if="row.status === 'submitted'"
              v-permission="'trade:write'"
              link
              type="danger"
              @click="handleReject(row as Quotation)"
            >
              拒绝
            </el-button>
            <span v-if="row.status !== 'submitted'" class="text-sub">已处理</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 报价弹窗 -->
    <el-dialog v-model="quoteVisible" title="提交报价" width="620px" append-to-body>
      <el-form ref="quoteFormRef" :model="quoteForm" :rules="quoteRules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="报价数量">
              <el-input v-model="quoteForm.quantity" placeholder="默认询价数量">
                <template #append>{{ unitLabel(inquiry?.unit) || '吨' }}</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="报价单价" prop="unit_price">
              <el-input v-model="quoteForm.unit_price" placeholder="元/单位">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="税率(%)">
              <el-input v-model="quoteForm.tax_rate" placeholder="如 9" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="交货日期">
              <el-date-picker
                v-model="quoteForm.delivery_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="报价有效期">
              <el-date-picker
                v-model="quoteForm.valid_until"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="付款条件">
              <el-input v-model="quoteForm.payment_terms" placeholder="如 款到发货 / 30 天账期" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="quoteForm.remark" type="textarea" :rows="2" placeholder="质量、包装、运输说明" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-alert
          type="info"
          :closable="false"
          show-icon
          :title="`预估报价金额：${quoteAmount === '-' ? '请填写数量与单价' : `${quoteAmount} 元`}`"
        />
      </el-form>
      <template #footer>
        <el-button @click="quoteVisible = false">取消</el-button>
        <el-button type="primary" :loading="quoteSubmitting" @click="submitQuote">提交报价</el-button>
      </template>
    </el-dialog>
  </div>
</template>
