<script setup lang="ts">
/**
 * 询价单：「我发出的」与「待我报价」两个页签。
 * 接口：GET /inquiries?role=buyer|supplier、POST /inquiries、/submit、/cancel
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import { cancelInquiry, createInquiry, listInquiries, submitInquiry } from '@/api/trade'
import { listProducts } from '@/api/product'
import { listEnterprises } from '@/api/enterprise'
import type { Enterprise, Inquiry, InquiryPayload, InquiryQuery, Product } from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity, unitLabel } from '@/utils/format'

const router = useRouter()

const activeTab = ref<'buyer' | 'supplier'>('buyer')
const loading = ref(false)
const list = ref<Inquiry[]>([])
const total = ref(0)
const products = ref<Product[]>([])
const suppliers = ref<Enterprise[]>([])

const query = reactive<InquiryQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  role: 'buyer',
  status: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listInquiries({ ...query, role: activeTab.value })
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
  query.start_date = ''
  query.end_date = ''
  query.page = 1
  loadList()
}
function handleTabChange(): void {
  query.page = 1
  loadList()
}

async function loadOptions(): Promise<void> {
  try {
    const data = await listProducts({ page: 1, page_size: 200, status: 'published' })
    products.value = data.items || []
  } catch {
    products.value = []
  }
  try {
    const data = await listEnterprises({ page: 1, page_size: 200, enterprise_type: 'supplier' })
    suppliers.value = data.items || []
  } catch {
    suppliers.value = []
  }
}

/* ---------------- 新建询价 ---------------- */
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<InquiryPayload & { submit_now: boolean }>({
  product_id: undefined as unknown as number,
  quantity: '',
  unit: 'ton',
  expect_price: '',
  expect_delivery_date: '',
  delivery_address: '',
  supplier_enterprise_id: null,
  remark: '',
  submit_now: true
})

const rules: FormRules = {
  product_id: [{ required: true, message: '请选择采购商品', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入采购数量', trigger: 'blur' }]
}

const selectedProduct = ref<Product | null>(null)

function handleProductChange(value: number): void {
  const hit = products.value.find((item) => item.id === value)
  selectedProduct.value = hit || null
  if (hit) {
    form.unit = hit.unit
    if (!form.expect_price) form.expect_price = hit.price
  }
}

function openCreate(): void {
  Object.assign(form, {
    product_id: undefined,
    quantity: '',
    unit: 'ton',
    expect_price: '',
    expect_delivery_date: '',
    delivery_address: '',
    supplier_enterprise_id: null,
    remark: '',
    submit_now: true
  })
  selectedProduct.value = null
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const el = formRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    const { submit_now, ...payload } = form
    try {
      const created = await createInquiry(payload)
      if (submit_now && created?.id) {
        await submitInquiry(created.id)
        ElMessage.success('询价单已提交，等待供应商报价')
      } else {
        ElMessage.success('询价单已保存为草稿')
      }
      dialogVisible.value = false
      activeTab.value = 'buyer'
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      submitting.value = false
    }
  })
}

/* ---------------- 提交 / 取消 ---------------- */
async function handleSubmit(row: Inquiry): Promise<void> {
  try {
    await submitInquiry(row.id)
    ElMessage.success('询价单已提交')
    loadList()
  } catch {
    /* 已提示 */
  }
}

async function handleCancel(row: Inquiry): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认取消询价单「${row.inquiry_no}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '取消询价',
      cancelButtonText: '返回'
    })
  } catch {
    return
  }
  try {
    await cancelInquiry(row.id)
    ElMessage.success('询价单已取消')
    loadList()
  } catch {
    /* 已提示 */
  }
}

function openDetail(row: Inquiry): void {
  router.push(`/trade/inquiry/${row.id}`)
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
          <el-tabs v-model="activeTab" @tab-change="handleTabChange">
            <el-tab-pane label="我发出的询价" name="buyer" />
            <el-tab-pane label="待我报价" name="supplier" />
          </el-tabs>

          <el-form class="search-form" :inline="true" @submit.prevent>
            <el-form-item label="关键词">
              <el-input
                v-model="query.keyword"
                placeholder="询价单号 / 商品"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="inquiryStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="日期">
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
        <el-button v-permission="'trade:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>发起询价</span>
        </el-button>
        <el-button @click="loadList">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </template>

      <el-table-column prop="inquiry_no" label="询价单号" width="170">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="openDetail(row as Inquiry)">{{ row.inquiry_no }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="product_name" label="采购商品" min-width="180" show-overflow-tooltip />
      <el-table-column label="数量" width="120" align="right">
        <template #default="{ row }">{{ formatQuantity(row.quantity) }} {{ unitLabel(row.unit) }}</template>
      </el-table-column>
      <el-table-column label="期望单价" width="120" align="right">
        <template #default="{ row }">{{ formatMoney(row.expect_price) }}</template>
      </el-table-column>
      <el-table-column label="采购商" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.buyer_enterprise_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="指定供应商" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.supplier_enterprise_name || '公开询价' }}</template>
      </el-table-column>
      <el-table-column label="期望交期" width="120">
        <template #default="{ row }">{{ row.expect_delivery_date || '-' }}</template>
      </el-table-column>
      <el-table-column label="报价数" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.quoted_count > 0 ? 'success' : 'info'">{{ row.quoted_count }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <StatusTag group="inquiryStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row as Inquiry)">详情</el-button>
          <el-button
            v-if="activeTab === 'buyer' && row.status === 'draft'"
            v-permission="'trade:write'"
            link
            type="success"
            @click="handleSubmit(row as Inquiry)"
          >
            提交
          </el-button>
          <el-button
            v-if="activeTab === 'buyer' && ['draft', 'submitted', 'quoted'].includes(row.status)"
            v-permission="'trade:write'"
            link
            type="danger"
            @click="handleCancel(row as Inquiry)"
          >
            取消
          </el-button>
          <el-button v-if="activeTab === 'supplier'" link type="primary" @click="openDetail(row as Inquiry)">
            去报价
          </el-button>
        </template>
      </el-table-column>
    </PageTable>

    <el-dialog v-model="dialogVisible" title="发起询价" width="680px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="24">
            <el-form-item label="采购商品" prop="product_id">
              <el-select
                v-model="form.product_id"
                placeholder="请选择已上架商品"
                filterable
                style="width: 100%"
                @change="handleProductChange"
              >
                <el-option
                  v-for="item in products"
                  :key="item.id"
                  :label="`${item.name}（${item.grade || '-'} / ${item.origin || '-'}）`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购数量" prop="quantity">
              <el-input v-model="form.quantity" placeholder="如 100.000">
                <template #append>{{ unitLabel(form.unit) || '吨' }}</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望单价">
              <el-input v-model="form.expect_price" placeholder="元/单位">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望交期">
              <el-date-picker
                v-model="form.expect_delivery_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="指定供应商">
              <el-select
                v-model="form.supplier_enterprise_id"
                placeholder="留空为公开询价"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option v-for="item in suppliers" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="交货地址">
              <el-input v-model="form.delivery_address" placeholder="如 新疆北屯市xx园区xx仓库" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="质量要求 / 付款方式等" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="立即提交">
              <el-switch v-model="form.submit_now" active-text="提交进入待报价" inactive-text="保存草稿" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-alert
          v-if="selectedProduct"
          type="success"
          :closable="false"
          show-icon
          :title="`参考信息：${selectedProduct.name} · 参考价 ${formatMoney(selectedProduct.price)} 元/${unitLabel(selectedProduct.unit)} · 可用库存 ${formatQuantity(selectedProduct.available_quantity)}`"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.date-sep {
  margin: 0 6px;
  color: var(--gz-text-sub);
}
</style>
