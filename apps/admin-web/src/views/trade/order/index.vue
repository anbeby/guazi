<script setup lang="ts">
/**
 * 订单列表：买方 / 卖方页签，状态流转按钮（确认 / 发货 / 完成 / 取消），直接下单。
 * 接口：GET /orders、POST /orders、POST /orders/{id}/confirm|deliver|complete|cancel
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import {
  cancelOrder,
  completeOrder,
  confirmOrder,
  createOrder,
  deliverOrder,
  getOrder,
  listOrders
} from '@/api/trade'
import { listProducts } from '@/api/product'
import { listEnterprises } from '@/api/enterprise'
import { listWarehouses } from '@/api/warehouse'
import type {
  Enterprise,
  Order,
  OrderPayload,
  OrderQuery,
  Product,
  Warehouse
} from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity, unitLabel } from '@/utils/format'

const router = useRouter()

const activeTab = ref<'buyer' | 'supplier'>('buyer')
const loading = ref(false)
const list = ref<Order[]>([])
const total = ref(0)
const products = ref<Product[]>([])
const suppliers = ref<Enterprise[]>([])
const warehouses = ref<Warehouse[]>([])

const query = reactive<OrderQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  role: 'buyer',
  status: '',
  start_date: '',
  end_date: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listOrders({ ...query, role: activeTab.value })
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
    const data = await listProducts({ page: 1, page_size: 200 })
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
  try {
    const data = await listWarehouses({ page: 1, page_size: 200 })
    warehouses.value = data.items || []
  } catch {
    warehouses.value = []
  }
}

/* ---------------- 状态流转 ---------------- */
async function handleConfirm(row: Order): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '确认订单后将按明细扣减库存并生成交易流水，操作不可撤销。是否继续？',
      '确认订单',
      { type: 'warning', confirmButtonText: '确认订单', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await confirmOrder(row.id)
    ElMessage.success('订单已确认，库存已扣减并生成交易流水')
    loadList()
  } catch {
    /* 已提示 */
  }
}

async function handleComplete(row: Order): Promise<void> {
  try {
    await ElMessageBox.confirm('确认订单已完成？系统将生成应收结算单。', '完成订单', {
      type: 'warning',
      confirmButtonText: '确认完成',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await completeOrder(row.id)
    ElMessage.success('订单已完成，应收结算单已生成')
    loadList()
  } catch {
    /* 已提示 */
  }
}

const cancelVisible = ref(false)
const cancelSubmitting = ref(false)
const cancelTarget = ref<Order | null>(null)
const cancelReason = ref('')

function openCancel(row: Order): void {
  cancelTarget.value = row
  cancelReason.value = ''
  cancelVisible.value = true
}

async function submitCancel(): Promise<void> {
  if (!cancelTarget.value) return
  if (!cancelReason.value.trim()) {
    ElMessage.warning('请填写取消原因')
    return
  }
  cancelSubmitting.value = true
  try {
    await cancelOrder(cancelTarget.value.id, { reason: cancelReason.value })
    ElMessage.success('订单已取消')
    cancelVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  } finally {
    cancelSubmitting.value = false
  }
}

/* ---------------- 发货 ---------------- */
const deliverVisible = ref(false)
const deliverSubmitting = ref(false)
const deliverTarget = ref<Order | null>(null)
const deliverItems = ref<{ item_id: number; product_name: string; quantity: string; delivered_quantity: number }[]>([])
const logistics = reactive({ company: '', tracking_no: '' })

async function openDeliver(row: Order): Promise<void> {
  deliverTarget.value = row
  logistics.company = ''
  logistics.tracking_no = ''
  let order = row
  if (!order.items || order.items.length === 0) {
    try {
      order = await getOrder(row.id)
      deliverTarget.value = order
    } catch {
      /* 保持列表数据 */
    }
  }
  deliverItems.value = (order.items || []).map((item) => ({
    item_id: item.id,
    product_name: item.product_name || `商品#${item.product_id}`,
    quantity: item.quantity,
    delivered_quantity: Number(item.quantity)
  }))
  deliverVisible.value = true
}

async function submitDeliver(): Promise<void> {
  if (!deliverTarget.value) return
  if (deliverItems.value.length === 0) {
    ElMessage.warning('该订单无明细，无法发货')
    return
  }
  deliverSubmitting.value = true
  try {
    await deliverOrder(deliverTarget.value.id, {
      items: deliverItems.value.map((item) => ({
        item_id: item.item_id,
        delivered_quantity: item.delivered_quantity
      })),
      logistics: { company: logistics.company, tracking_no: logistics.tracking_no }
    })
    ElMessage.success('发货信息已登记')
    deliverVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  } finally {
    deliverSubmitting.value = false
  }
}

/* ---------------- 直接下单 ---------------- */
const createVisible = ref(false)
const createSubmitting = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<OrderPayload>({
  supplier_enterprise_id: undefined as unknown as number,
  buyer_enterprise_id: null,
  delivery_date: '',
  delivery_address: '',
  remark: '',
  items: []
})

const createRules: FormRules = {
  supplier_enterprise_id: [{ required: true, message: '请选择供应商', trigger: 'change' }]
}

interface CreateItem {
  product_id: number | undefined
  warehouse_id: number | null
  location_id: number | null
  batch_no: string
  quantity: string
  unit: string
  unit_price: string
  tax_rate: string
}

const createItems = ref<CreateItem[]>([])

const createAmount = computed(() =>
  createItems.value.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.unit_price || 0), 0)
)

function addItem(): void {
  createItems.value.push({
    product_id: undefined,
    warehouse_id: null,
    location_id: null,
    batch_no: 'DEFAULT',
    quantity: '',
    unit: 'ton',
    unit_price: '',
    tax_rate: '9'
  })
}

function removeItem(index: number): void {
  createItems.value.splice(index, 1)
}

function handleItemProductChange(index: number, productId: number): void {
  const hit = products.value.find((item) => item.id === productId)
  const row = createItems.value[index]
  if (!hit || !row) return
  row.unit = hit.unit
  row.unit_price = hit.price
}

function openCreate(): void {
  createForm.supplier_enterprise_id = undefined as unknown as number
  createForm.buyer_enterprise_id = null
  createForm.delivery_date = ''
  createForm.delivery_address = ''
  createForm.remark = ''
  createItems.value = []
  addItem()
  createVisible.value = true
}

async function submitCreate(): Promise<void> {
  const el = createFormRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    const validItems = createItems.value.filter((item) => item.product_id && item.quantity)
    if (validItems.length === 0) {
      ElMessage.warning('请至少添加一条商品明细（含商品与数量）')
      return
    }
    createSubmitting.value = true
    try {
      await createOrder({
        ...createForm,
        items: validItems.map((item) => ({
          product_id: item.product_id as number,
          warehouse_id: item.warehouse_id,
          location_id: item.location_id,
          batch_no: item.batch_no,
          quantity: item.quantity,
          unit: item.unit,
          unit_price: item.unit_price,
          tax_rate: item.tax_rate
        }))
      })
      ElMessage.success('订单创建成功，等待供应商确认')
      createVisible.value = false
      activeTab.value = 'buyer'
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      createSubmitting.value = false
    }
  })
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
            <el-tab-pane label="我采购的订单" name="buyer" />
            <el-tab-pane label="我销售的订单" name="supplier" />
          </el-tabs>

          <el-form class="search-form" :inline="true" @submit.prevent>
            <el-form-item label="关键词">
              <el-input
                v-model="query.keyword"
                placeholder="订单号 / 企业名称"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="orderStatus" with-all placeholder="全部状态" />
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
          <span>直接下单</span>
        </el-button>
        <el-button @click="loadList">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </template>

      <el-table-column prop="order_no" label="订单号" width="170">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="router.push(`/trade/order/${row.id}`)">
            {{ row.order_no }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <StatusTag group="orderType" :value="row.order_type" />
        </template>
      </el-table-column>
      <el-table-column prop="buyer_enterprise_name" label="买方" min-width="160" show-overflow-tooltip />
      <el-table-column prop="supplier_enterprise_name" label="卖方" min-width="160" show-overflow-tooltip />
      <el-table-column label="订单金额" width="140" align="right">
        <template #default="{ row }">
          <span class="text-amount">{{ formatMoney(row.total_amount || row.amount) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="币种" width="80">
        <template #default="{ row }">{{ row.currency || 'CNY' }}</template>
      </el-table-column>
      <el-table-column label="交货日期" width="120">
        <template #default="{ row }">{{ row.delivery_date || '-' }}</template>
      </el-table-column>
      <el-table-column label="库存扣减" width="100" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.stock_deducted ? 'success' : 'info'">
            {{ row.stock_deducted ? '已扣减' : '未扣减' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <StatusTag group="orderStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/trade/order/${row.id}`)">详情</el-button>
          <el-button
            v-if="row.status === 'pending_confirm' && activeTab === 'supplier'"
            v-permission="'trade:write'"
            link
            type="success"
            @click="handleConfirm(row as Order)"
          >
            确认
          </el-button>
          <el-button
            v-if="row.status === 'confirmed' && activeTab === 'supplier'"
            v-permission="'trade:write'"
            link
            type="primary"
            @click="openDeliver(row as Order)"
          >
            发货
          </el-button>
          <el-button
            v-if="row.status === 'delivering'"
            v-permission="'trade:write'"
            link
            type="success"
            @click="handleComplete(row as Order)"
          >
            完成
          </el-button>
          <el-button
            v-if="['draft', 'pending_confirm', 'confirmed'].includes(row.status)"
            v-permission="'trade:write'"
            link
            type="danger"
            @click="openCancel(row as Order)"
          >
            取消
          </el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 取消订单 -->
    <el-dialog v-model="cancelVisible" title="取消订单" width="460px" append-to-body>
      <el-form label-width="90px">
        <el-form-item label="订单号">
          <span>{{ cancelTarget?.order_no }}</span>
        </el-form-item>
        <el-form-item label="取消原因">
          <el-input v-model="cancelReason" type="textarea" :rows="3" placeholder="请填写取消原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelVisible = false">返回</el-button>
        <el-button type="danger" :loading="cancelSubmitting" @click="submitCancel">确认取消</el-button>
      </template>
    </el-dialog>

    <!-- 发货 -->
    <el-dialog v-model="deliverVisible" title="订单发货登记" width="700px" append-to-body>
      <el-table :data="deliverItems" border stripe>
        <el-table-column prop="product_name" label="商品" min-width="180" show-overflow-tooltip />
        <el-table-column label="订单数量" width="120" align="right">
          <template #default="{ row }">{{ formatQuantity(row.quantity) }}</template>
        </el-table-column>
        <el-table-column label="本次发货数量" width="180">
          <template #default="{ row }">
            <el-input-number v-model="row.delivered_quantity" :min="0" :precision="3" :step="1" style="width: 100%" />
          </template>
        </el-table-column>
      </el-table>

      <el-form class="mt-12" label-width="100px">
        <el-form-item label="物流公司">
          <el-input v-model="logistics.company" placeholder="如 顺丰速运 / 自有车队" />
        </el-form-item>
        <el-form-item label="运单号">
          <el-input v-model="logistics.tracking_no" placeholder="物流单号（可选）" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="deliverVisible = false">取消</el-button>
        <el-button type="primary" :loading="deliverSubmitting" @click="submitDeliver">确认发货</el-button>
      </template>
    </el-dialog>

    <!-- 直接下单 -->
    <el-dialog v-model="createVisible" title="直接下单" width="920px" append-to-body>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier_enterprise_id">
              <el-select
                v-model="createForm.supplier_enterprise_id"
                placeholder="请选择供应商"
                filterable
                style="width: 100%"
              >
                <el-option v-for="item in suppliers" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="交货日期">
              <el-date-picker
                v-model="createForm.delivery_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="交货地址">
              <el-input v-model="createForm.delivery_address" placeholder="如 新疆北屯市xx园区xx仓库" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="createForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="flex-between mb-12">
        <span>商品明细</span>
        <el-button size="small" type="primary" @click="addItem">
          <el-icon><Plus /></el-icon>
          <span>添加明细</span>
        </el-button>
      </div>

      <el-table :data="createItems" border stripe>
        <el-table-column label="商品" min-width="220">
          <template #default="{ row, $index }">
            <el-select
              v-model="row.product_id"
              placeholder="请选择商品"
              filterable
              style="width: 100%"
              @change="(value: number) => handleItemProductChange($index, value)"
            >
              <el-option
                v-for="item in products"
                :key="item.id"
                :label="`${item.name}（可用 ${formatQuantity(item.available_quantity)} ${unitLabel(item.unit)}）`"
                :value="item.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="仓库" width="160">
          <template #default="{ row }">
            <el-select v-model="row.warehouse_id" placeholder="可选" clearable style="width: 100%">
              <el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="批次号" width="140">
          <template #default="{ row }">
            <el-input v-model="row.batch_no" placeholder="DEFAULT" />
          </template>
        </el-table-column>
        <el-table-column label="数量" width="140">
          <template #default="{ row }">
            <el-input v-model="row.quantity" placeholder="如 100.000" />
          </template>
        </el-table-column>
        <el-table-column label="单价" width="140">
          <template #default="{ row }">
            <el-input v-model="row.unit_price" placeholder="元/单位" />
          </template>
        </el-table-column>
        <el-table-column label="税率(%)" width="110">
          <template #default="{ row }">
            <el-input v-model="row.tax_rate" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ $index }">
            <el-button link type="danger" @click="removeItem($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-alert
        class="mt-12"
        type="info"
        :closable="false"
        show-icon
        :title="`订单金额（不含税）：${formatMoney(createAmount)} 元`"
      />

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">提交订单</el-button>
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
