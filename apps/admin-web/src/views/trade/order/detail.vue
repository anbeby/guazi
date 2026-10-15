<script setup lang="ts">
/**
 * 订单详情：明细、状态轨迹时间线、合同与结算关联，以及确认/发货/完成/取消操作。
 * 接口：GET /orders/{id}、GET /orders/{id}/timeline、POST /orders/{id}/confirm|deliver|complete|cancel、POST /contracts
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import StatusTag from '@/components/StatusTag.vue'
import {
  cancelOrder,
  completeOrder,
  confirmOrder,
  createContract,
  deliverOrder,
  getOrder,
  getOrderTimeline
} from '@/api/trade'
import type { Order, OrderTimelineNode } from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity, unitLabel } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const orderId = computed(() => Number(route.params.id))

const loading = ref(false)
const order = ref<Order | null>(null)
const timeline = ref<OrderTimelineNode[]>([])
const timelineLoading = ref(false)

async function loadDetail(): Promise<void> {
  if (!orderId.value) return
  loading.value = true
  try {
    order.value = await getOrder(orderId.value)
  } catch {
    order.value = null
  } finally {
    loading.value = false
  }
}

async function loadTimeline(): Promise<void> {
  if (!orderId.value) return
  timelineLoading.value = true
  try {
    timeline.value = await getOrderTimeline(orderId.value)
  } catch {
    timeline.value = []
  } finally {
    timelineLoading.value = false
  }
}

const canConfirm = computed(() => order.value?.status === 'pending_confirm')
const canDeliver = computed(() => order.value?.status === 'confirmed')
const canComplete = computed(() => order.value?.status === 'delivering')
const canCancel = computed(() =>
  ['draft', 'pending_confirm', 'confirmed'].includes(order.value?.status || '')
)

async function handleConfirm(): Promise<void> {
  if (!order.value) return
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
    await confirmOrder(order.value.id)
    ElMessage.success('订单已确认')
    await Promise.all([loadDetail(), loadTimeline()])
  } catch {
    /* 已提示 */
  }
}

async function handleComplete(): Promise<void> {
  if (!order.value) return
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
    await completeOrder(order.value.id)
    ElMessage.success('订单已完成，应收结算单已生成')
    await Promise.all([loadDetail(), loadTimeline()])
  } catch {
    /* 已提示 */
  }
}

const cancelVisible = ref(false)
const cancelSubmitting = ref(false)
const cancelReason = ref('')

function openCancel(): void {
  cancelReason.value = ''
  cancelVisible.value = true
}

async function submitCancel(): Promise<void> {
  if (!order.value) return
  if (!cancelReason.value.trim()) {
    ElMessage.warning('请填写取消原因')
    return
  }
  cancelSubmitting.value = true
  try {
    await cancelOrder(order.value.id, { reason: cancelReason.value })
    ElMessage.success('订单已取消')
    cancelVisible.value = false
    await Promise.all([loadDetail(), loadTimeline()])
  } catch {
    /* 已提示 */
  } finally {
    cancelSubmitting.value = false
  }
}

/* ---------------- 发货 ---------------- */
const deliverVisible = ref(false)
const deliverSubmitting = ref(false)
const deliverItems = ref<{ item_id: number; product_name: string; quantity: string; delivered_quantity: number }[]>([])
const logistics = reactive({ company: '', tracking_no: '' })

function openDeliver(): void {
  if (!order.value) return
  logistics.company = ''
  logistics.tracking_no = ''
  deliverItems.value = (order.value.items || []).map((item) => ({
    item_id: item.id,
    product_name: item.product_name || `商品#${item.product_id}`,
    quantity: item.quantity,
    delivered_quantity: Number(item.quantity)
  }))
  deliverVisible.value = true
}

async function submitDeliver(): Promise<void> {
  if (!order.value) return
  if (deliverItems.value.length === 0) {
    ElMessage.warning('该订单无明细，无法发货')
    return
  }
  deliverSubmitting.value = true
  try {
    await deliverOrder(order.value.id, {
      items: deliverItems.value.map((item) => ({
        item_id: item.item_id,
        delivered_quantity: item.delivered_quantity
      })),
      logistics: { company: logistics.company, tracking_no: logistics.tracking_no }
    })
    ElMessage.success('发货信息已登记')
    deliverVisible.value = false
    await Promise.all([loadDetail(), loadTimeline()])
  } catch {
    /* 已提示 */
  } finally {
    deliverSubmitting.value = false
  }
}

/* ---------------- 生成合同 ---------------- */
const contractVisible = ref(false)
const contractSubmitting = ref(false)
const contractForm = reactive({
  title: '',
  sign_date: '',
  start_date: '',
  end_date: '',
  file_url: '',
  remark: ''
})

function openContract(): void {
  if (!order.value) return
  contractForm.title = `瓜子油料购销合同（订单 ${order.value.order_no}）`
  contractForm.sign_date = ''
  contractForm.start_date = order.value.delivery_date || ''
  contractForm.end_date = ''
  contractForm.file_url = ''
  contractForm.remark = ''
  contractVisible.value = true
}

async function submitContract(): Promise<void> {
  if (!order.value) return
  if (!contractForm.title.trim()) {
    ElMessage.warning('请输入合同标题')
    return
  }
  contractSubmitting.value = true
  try {
    const created = await createContract({
      title: contractForm.title,
      order_id: order.value.id,
      buyer_enterprise_id: order.value.buyer_enterprise_id,
      supplier_enterprise_id: order.value.supplier_enterprise_id,
      amount: order.value.total_amount || order.value.amount,
      sign_date: contractForm.sign_date || undefined,
      start_date: contractForm.start_date || undefined,
      end_date: contractForm.end_date || undefined,
      file_url: contractForm.file_url || undefined,
      remark: contractForm.remark
    })
    ElMessage.success(`合同已生成：${created?.contract_no || ''}`)
    contractVisible.value = false
    await loadDetail()
  } catch {
    /* 已提示 */
  } finally {
    contractSubmitting.value = false
  }
}

/** 时间线节点颜色 */
function timelineColor(node: OrderTimelineNode): string {
  const status = (node.status || '') as string
  if (status === 'cancelled') return '#c0392b'
  if (status === 'completed' || status === 'settled') return '#16653f'
  if (status === 'pending_confirm') return '#d48806'
  return '#1f6feb'
}

onMounted(async () => {
  await loadDetail()
  await loadTimeline()
})
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-card">
      <div class="page-title">
        <span>
          订单详情
          <span class="page-title__sub">{{ order?.order_no || '' }}</span>
        </span>
        <div class="flex-center" style="gap: 8px">
          <el-button size="small" @click="router.back()">返回</el-button>
          <el-button size="small" @click="loadDetail(); loadTimeline()">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </el-button>
          <el-button
            v-if="canConfirm"
            v-permission="'trade:write'"
            size="small"
            type="success"
            @click="handleConfirm"
          >
            确认订单
          </el-button>
          <el-button
            v-if="canDeliver"
            v-permission="'trade:write'"
            size="small"
            type="primary"
            @click="openDeliver"
          >
            登记发货
          </el-button>
          <el-button
            v-if="canComplete"
            v-permission="'trade:write'"
            size="small"
            type="success"
            @click="handleComplete"
          >
            确认完成
          </el-button>
          <el-button
            v-if="canCancel"
            v-permission="'trade:write'"
            size="small"
            type="danger"
            @click="openCancel"
          >
            取消订单
          </el-button>
          <el-button
            v-if="order && !order.contract_id"
            v-permission="'trade:write'"
            size="small"
            type="primary"
            plain
            @click="openContract"
          >
            生成合同
          </el-button>
        </div>
      </div>

      <template v-if="order">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="订单号">{{ order.order_no }}</el-descriptions-item>
          <el-descriptions-item label="订单类型">
            <StatusTag group="orderType" :value="order.order_type" />
          </el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <StatusTag group="orderStatus" :value="order.status" />
          </el-descriptions-item>
          <el-descriptions-item label="买方">{{ order.buyer_enterprise_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="卖方">{{ order.supplier_enterprise_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="币种">{{ order.currency || 'CNY' }}</el-descriptions-item>
          <el-descriptions-item label="订单金额">{{ formatMoney(order.amount) }} 元</el-descriptions-item>
          <el-descriptions-item label="税额">{{ formatMoney(order.tax_amount) }} 元</el-descriptions-item>
          <el-descriptions-item label="含税总额">
            <span class="text-amount">{{ formatMoney(order.total_amount) }} 元</span>
          </el-descriptions-item>
          <el-descriptions-item label="交货日期">{{ order.delivery_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="交货地址" :span="2">{{ order.delivery_address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="库存扣减">
            <el-tag size="small" :type="order.stock_deducted ? 'success' : 'info'">
              {{ order.stock_deducted ? '已扣减' : '未扣减' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="确认时间">{{ formatDateTime(order.confirmed_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(order.completed_at) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(order.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ order.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <el-empty v-else-if="!loading" description="订单不存在或无权访问" />
    </div>

    <div class="page-card">
      <div class="page-title">
        <span>订单明细</span>
      </div>
      <el-table :data="order?.items || []" border stripe>
        <el-table-column prop="product_name" label="商品" min-width="200" show-overflow-tooltip />
        <el-table-column prop="product_code" label="商品编码" width="150" />
        <el-table-column prop="warehouse_name" label="仓库" min-width="140" />
        <el-table-column prop="batch_no" label="批次号" width="130" />
        <el-table-column label="订单数量" width="120" align="right">
          <template #default="{ row }">{{ formatQuantity(row.quantity) }} {{ unitLabel(row.unit) }}</template>
        </el-table-column>
        <el-table-column label="已发货" width="120" align="right">
          <template #default="{ row }">{{ formatQuantity(row.delivered_quantity) }}</template>
        </el-table-column>
        <el-table-column label="单价" width="120" align="right">
          <template #default="{ row }">{{ formatMoney(row.unit_price) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="140" align="right">
          <template #default="{ row }">
            <span class="text-amount">{{ formatMoney(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="税率" width="80" align="right">
          <template #default="{ row }">{{ row.tax_rate ? `${row.tax_rate}%` : '-' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <el-row :gutter="12">
      <el-col :xs="24" :md="14">
        <div class="page-card">
          <div class="page-title">
            <span>
              状态轨迹
              <span class="page-title__sub">/orders/{id}/timeline</span>
            </span>
          </div>
          <div v-loading="timelineLoading">
            <el-timeline v-if="timeline.length > 0">
              <el-timeline-item
                v-for="(node, index) in timeline"
                :key="node.id ?? index"
                :timestamp="formatDateTime(node.created_at)"
                :color="timelineColor(node)"
                placement="top"
              >
                <div class="timeline-title">
                  {{ node.title || node.action || node.status }}
                  <StatusTag v-if="node.status" group="orderStatus" :value="node.status" />
                </div>
                <div class="timeline-desc text-sub">
                  {{ node.description || '' }}
                  <span v-if="node.operator_name || node.operator">
                    · 操作人：{{ node.operator_name || node.operator }}
                  </span>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无轨迹记录" :image-size="80" />
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="10">
        <div class="page-card">
          <div class="page-title">
            <span>关联单据</span>
          </div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="询价单">
              <el-link
                v-if="order?.inquiry_id"
                type="primary"
                :underline="false"
                @click="router.push(`/trade/inquiry/${order.inquiry_id}`)"
              >
                #{{ order.inquiry_id }}
              </el-link>
              <span v-else class="text-sub">-</span>
            </el-descriptions-item>
            <el-descriptions-item label="报价单">{{ order?.quotation_id ? `#${order.quotation_id}` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="合同">
              <el-link
                v-if="order?.contract_id"
                type="primary"
                :underline="false"
                @click="router.push('/trade/contract')"
              >
                #{{ order.contract_id }}
              </el-link>
              <span v-else class="text-sub">未生成</span>
            </el-descriptions-item>
            <el-descriptions-item label="结算单">
              <el-link type="primary" :underline="false" @click="router.push('/settlement/list')">
                前往结算单
              </el-link>
            </el-descriptions-item>
            <el-descriptions-item label="交易流水">
              <el-link type="primary" :underline="false" @click="router.push('/settlement/flow')">
                前往流水与对账
              </el-link>
            </el-descriptions-item>
          </el-descriptions>

          <el-alert
            class="mt-12"
            type="info"
            :closable="false"
            show-icon
            title="状态流转：待确认 → 确认（扣库存+生成流水）→ 发货 → 完成（生成应收结算单）→ 结算"
          />
        </div>
      </el-col>
    </el-row>

    <!-- 取消订单 -->
    <el-dialog v-model="cancelVisible" title="取消订单" width="460px" append-to-body>
      <el-form label-width="90px">
        <el-form-item label="订单号">
          <span>{{ order?.order_no }}</span>
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

    <!-- 生成合同 -->
    <el-dialog v-model="contractVisible" title="由订单生成合同" width="600px" append-to-body>
      <el-form label-width="110px">
        <el-form-item label="合同标题">
          <el-input v-model="contractForm.title" />
        </el-form-item>
        <el-form-item label="合同金额">
          <span class="text-amount">{{ formatMoney(order?.total_amount || order?.amount) }} 元</span>
        </el-form-item>
        <el-form-item label="签署日期">
          <el-date-picker
            v-model="contractForm.sign_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker
            v-model="contractForm.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker
            v-model="contractForm.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="contractForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="contractVisible = false">取消</el-button>
        <el-button type="primary" :loading="contractSubmitting" @click="submitContract">生成合同</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.timeline-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.timeline-desc {
  margin-top: 4px;
  font-size: 12px;
}
</style>
