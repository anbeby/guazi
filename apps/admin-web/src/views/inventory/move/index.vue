<script setup lang="ts">
/**
 * 出入库操作与库存流水。
 * 接口：POST /inventory/in | /out | /transfer | /adjust | /check，GET /inventory/moves
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import {
  inventoryAdjust,
  inventoryCheck,
  inventoryIn,
  inventoryOut,
  inventoryTransfer,
  listStockMoves
} from '@/api/inventory'
import { listProducts } from '@/api/product'
import { listLocations, listWarehouses } from '@/api/warehouse'
import type {
  Product,
  StorageLocation,
  StockMove,
  StockMoveQuery,
  Warehouse
} from '@/api/types'
import { formatDateTime, formatMoney, formatQuantity } from '@/utils/format'

const products = ref<Product[]>([])
const warehouses = ref<Warehouse[]>([])
const locations = ref<StorageLocation[]>([])
const toLocations = ref<StorageLocation[]>([])

/* ---------------- 库存流水 ---------------- */
const loading = ref(false)
const list = ref<StockMove[]>([])
const total = ref(0)
const query = reactive<StockMoveQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  product_id: null,
  warehouse_id: null,
  move_type: '',
  batch_no: '',
  start_date: '',
  end_date: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listStockMoves(query)
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
  query.product_id = null
  query.warehouse_id = null
  query.move_type = ''
  query.batch_no = ''
  query.start_date = ''
  query.end_date = ''
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
    const data = await listWarehouses({ page: 1, page_size: 200 })
    warehouses.value = data.items || []
  } catch {
    warehouses.value = []
  }
}

async function loadLocations(warehouseId?: number | null, target: 'from' | 'to' = 'from'): Promise<void> {
  if (!warehouseId) {
    if (target === 'from') locations.value = []
    else toLocations.value = []
    return
  }
  try {
    const data = await listLocations(warehouseId)
    if (target === 'from') locations.value = data
    else toLocations.value = data
  } catch {
    if (target === 'from') locations.value = []
    else toLocations.value = []
  }
}

/* ---------------- 通用操作弹窗 ---------------- */
type MoveAction = 'in' | 'out' | 'transfer' | 'adjust' | 'check'

const ACTION_TITLES: Record<MoveAction, string> = {
  in: '入库登记',
  out: '出库登记',
  transfer: '库存调拨',
  adjust: '库存调整（调整到目标值）',
  check: '库存盘点'
}

const actionVisible = ref(false)
const action = ref<MoveAction>('in')
const actionLoading = ref(false)
const actionFormRef = ref<FormInstance>()
const actionForm = reactive({
  product_id: undefined as number | undefined,
  warehouse_id: undefined as number | undefined,
  location_id: undefined as number | undefined,
  to_warehouse_id: undefined as number | undefined,
  to_location_id: undefined as number | undefined,
  batch_no: 'DEFAULT',
  quantity: '',
  unit_cost: '',
  production_date: '',
  quality_status: 'qualified',
  ref_no: '',
  remark: ''
})

const actionTitle = computed(() => ACTION_TITLES[action.value])

const actionRules = computed<FormRules>(() => {
  const base: FormRules = {
    product_id: [{ required: true, message: '请选择商品', trigger: 'change' }],
    warehouse_id: [{ required: true, message: '请选择仓库', trigger: 'change' }],
    quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }]
  }
  if (action.value === 'transfer') {
    base.to_warehouse_id = [{ required: true, message: '请选择目标仓库', trigger: 'change' }]
  }
  return base
})

function resetActionForm(): void {
  Object.assign(actionForm, {
    product_id: undefined,
    warehouse_id: undefined,
    location_id: undefined,
    to_warehouse_id: undefined,
    to_location_id: undefined,
    batch_no: 'DEFAULT',
    quantity: '',
    unit_cost: '',
    production_date: '',
    quality_status: 'qualified',
    ref_no: '',
    remark: ''
  })
  locations.value = []
  toLocations.value = []
}

function openAction(type: MoveAction): void {
  action.value = type
  resetActionForm()
  actionVisible.value = true
}

async function submitAction(): Promise<void> {
  const el = actionFormRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    if (!actionForm.product_id || !actionForm.warehouse_id) return
    actionLoading.value = true
    try {
      const common = {
        product_id: actionForm.product_id,
        warehouse_id: actionForm.warehouse_id,
        location_id: actionForm.location_id ?? null,
        batch_no: actionForm.batch_no || 'DEFAULT',
        quantity: actionForm.quantity
      }
      if (action.value === 'in') {
        await inventoryIn({
          ...common,
          unit_cost: actionForm.unit_cost || undefined,
          production_date: actionForm.production_date || undefined,
          quality_status: actionForm.quality_status as 'qualified',
          remark: actionForm.remark
        })
        ElMessage.success('入库成功')
      } else if (action.value === 'out') {
        await inventoryOut({
          ...common,
          unit_cost: actionForm.unit_cost || undefined,
          ref_no: actionForm.ref_no || undefined,
          remark: actionForm.remark
        })
        ElMessage.success('出库成功')
      } else if (action.value === 'transfer') {
        if (!actionForm.to_warehouse_id) {
          ElMessage.warning('请选择目标仓库')
          return
        }
        await inventoryTransfer({
          ...common,
          to_warehouse_id: actionForm.to_warehouse_id,
          to_location_id: actionForm.to_location_id ?? null,
          remark: actionForm.remark
        })
        ElMessage.success('调拨成功')
      } else if (action.value === 'adjust') {
        await inventoryAdjust({
          ...common,
          unit_cost: actionForm.unit_cost || undefined,
          remark: actionForm.remark
        })
        ElMessage.success('库存调整成功')
      } else {
        await inventoryCheck({
          items: [
            {
              product_id: actionForm.product_id,
              warehouse_id: actionForm.warehouse_id,
              location_id: actionForm.location_id ?? null,
              batch_no: actionForm.batch_no || 'DEFAULT',
              quantity: actionForm.quantity,
              remark: actionForm.remark
            }
          ],
          remark: actionForm.remark
        })
        ElMessage.success('盘点已提交，已生成盈亏调整与流水')
      }
      actionVisible.value = false
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      actionLoading.value = false
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
          <el-form class="search-form" :inline="true" @submit.prevent>
            <el-form-item label="关键词">
              <el-input
                v-model="query.keyword"
                placeholder="流水号 / 关联单据"
                clearable
                style="width: 180px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="商品">
              <el-select v-model="query.product_id" placeholder="全部商品" clearable filterable style="width: 200px">
                <el-option v-for="item in products" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="仓库">
              <el-select v-model="query.warehouse_id" placeholder="全部仓库" clearable style="width: 170px">
                <el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="业务类型">
              <DictSelect v-model="query.move_type" group="stockMoveType" with-all placeholder="全部类型" />
            </el-form-item>
            <el-form-item label="批次号">
              <el-input v-model="query.batch_no" clearable style="width: 140px" placeholder="如 DEFAULT" />
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
        <el-button v-permission="'inventory:execute'" type="success" @click="openAction('in')">
          <el-icon><Download /></el-icon>
          <span>入库</span>
        </el-button>
        <el-button v-permission="'inventory:execute'" type="warning" @click="openAction('out')">
          <el-icon><Upload /></el-icon>
          <span>出库</span>
        </el-button>
        <el-button v-permission="'inventory:execute'" type="primary" @click="openAction('transfer')">
          <el-icon><Switch /></el-icon>
          <span>调拨</span>
        </el-button>
        <el-button v-permission="'inventory:execute'" @click="openAction('adjust')">
          <el-icon><Edit /></el-icon>
          <span>调整</span>
        </el-button>
        <el-button v-permission="'inventory:execute'" type="danger" @click="openAction('check')">
          <el-icon><Checked /></el-icon>
          <span>盘点</span>
        </el-button>
      </template>

      <el-table-column prop="move_no" label="流水号" width="170" />
      <el-table-column label="业务类型" width="100">
        <template #default="{ row }">
          <StatusTag group="stockMoveType" :value="row.move_type" />
        </template>
      </el-table-column>
      <el-table-column prop="product_name" label="商品" min-width="180" show-overflow-tooltip />
      <el-table-column prop="warehouse_name" label="仓库" min-width="140" />
      <el-table-column label="目标仓库" min-width="140">
        <template #default="{ row }">{{ row.to_warehouse_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="batch_no" label="批次号" width="130" />
      <el-table-column label="数量" width="120" align="right">
        <template #default="{ row }">
          <span :class="row.move_type === 'out' ? 'text-danger' : 'text-success'">
            {{ row.move_type === 'out' ? '-' : '+' }}{{ formatQuantity(row.quantity) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="成本单价" width="120" align="right">
        <template #default="{ row }">{{ formatMoney(row.unit_cost) }}</template>
      </el-table-column>
      <el-table-column label="来源" width="110">
        <template #default="{ row }">
          <StatusTag group="stockRefType" :value="row.ref_type" />
        </template>
      </el-table-column>
      <el-table-column prop="ref_no" label="关联单据" width="150" />
      <el-table-column label="操作时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
    </PageTable>

    <el-dialog v-model="actionVisible" :title="actionTitle" width="620px" append-to-body>
      <el-form ref="actionFormRef" :model="actionForm" :rules="actionRules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="商品" prop="product_id">
              <el-select v-model="actionForm.product_id" placeholder="请选择商品" filterable style="width: 100%">
                <el-option v-for="item in products" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="批次号">
              <el-input v-model="actionForm.batch_no" placeholder="默认 DEFAULT" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="action === 'transfer' ? '源仓库' : '仓库'" prop="warehouse_id">
              <el-select
                v-model="actionForm.warehouse_id"
                placeholder="请选择仓库"
                style="width: 100%"
                @change="(value: number) => loadLocations(value, 'from')"
              >
                <el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="action === 'transfer' ? '源库位' : '库位'">
              <el-select v-model="actionForm.location_id" placeholder="可不选" clearable style="width: 100%">
                <el-option v-for="item in locations" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>

          <template v-if="action === 'transfer'">
            <el-col :span="12">
              <el-form-item label="目标仓库" prop="to_warehouse_id">
                <el-select
                  v-model="actionForm.to_warehouse_id"
                  placeholder="请选择目标仓库"
                  style="width: 100%"
                  @change="(value: number) => loadLocations(value, 'to')"
                >
                  <el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="目标库位">
                <el-select v-model="actionForm.to_location_id" placeholder="可不选" clearable style="width: 100%">
                  <el-option v-for="item in toLocations" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
              </el-form-item>
            </el-col>
          </template>

          <el-col :span="12">
            <el-form-item :label="action === 'adjust' || action === 'check' ? '目标数量/实盘' : '数量'" prop="quantity">
              <el-input v-model="actionForm.quantity" placeholder="如 100.000">
                <template #append>吨</template>
              </el-input>
            </el-form-item>
          </el-col>

          <template v-if="action === 'in' || action === 'out' || action === 'adjust'">
            <el-col :span="12">
              <el-form-item label="成本单价">
                <el-input v-model="actionForm.unit_cost" placeholder="如 6500.00">
                  <template #append>元</template>
                </el-input>
              </el-form-item>
            </el-col>
          </template>

          <template v-if="action === 'in'">
            <el-col :span="12">
              <el-form-item label="生产日期">
                <el-date-picker
                  v-model="actionForm.production_date"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择日期"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="质量状态">
                <DictSelect
                  v-model="actionForm.quality_status"
                  group="qualityStatus"
                  :clearable="false"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </template>

          <el-col v-if="action === 'out'" :span="12">
            <el-form-item label="关联单据">
              <el-input v-model="actionForm.ref_no" placeholder="可选，如订单号" />
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="actionForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-alert
          v-if="action === 'adjust'"
          type="info"
          :closable="false"
          show-icon
          title="调整语义为目标值：系统按目标数量与账面数量的差额生成调整流水"
        />
        <el-alert
          v-else-if="action === 'check'"
          type="warning"
          :closable="false"
          show-icon
          title="盘点将按实盘数量生成盈亏调整与库存流水（ref_type=check）"
        />
        <el-alert
          v-else-if="action === 'transfer'"
          type="info"
          :closable="false"
          show-icon
          title="调拨为同商品跨仓库/库位转移，不改变企业总库存"
        />
      </el-form>

      <template #footer>
        <el-button @click="actionVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="submitAction">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.date-sep {
  margin: 0 6px;
  color: var(--gz-text-sub);
}

.text-danger {
  color: #c0392b;
}

.text-success {
  color: #16653f;
}
</style>
