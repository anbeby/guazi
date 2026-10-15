<script setup lang="ts">
/**
 * 库存查询：按商品汇总（总量 / 预占 / 可用）+ 明细库存（批次 / 库位 / 成本）。
 * 接口：GET /inventory/summary、GET /inventory
 */
import { onMounted, reactive, ref } from 'vue'

import StatusTag from '@/components/StatusTag.vue'
import { getInventorySummary, listInventory } from '@/api/inventory'
import { listProducts } from '@/api/product'
import { listWarehouses } from '@/api/warehouse'
import type {
  InventoryItem,
  InventoryQuery,
  InventorySummaryItem,
  Product,
  Warehouse
} from '@/api/types'
import { formatMoney, formatQuantity, formatQuantityWithUnit, unitLabel } from '@/utils/format'

const activeTab = ref<'summary' | 'detail'>('summary')

const products = ref<Product[]>([])
const warehouses = ref<Warehouse[]>([])

const query = reactive<InventoryQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  product_id: null,
  warehouse_id: null,
  batch_no: ''
})

/* ---------------- 汇总 ---------------- */
const summaryLoading = ref(false)
const summaryRows = ref<InventorySummaryItem[]>([])
const summaryTotal = ref(0)

async function loadSummary(): Promise<void> {
  summaryLoading.value = true
  try {
    const data = await getInventorySummary(query)
    summaryRows.value = data.items || []
    summaryTotal.value = data.total || 0
  } catch {
    summaryRows.value = []
    summaryTotal.value = 0
  } finally {
    summaryLoading.value = false
  }
}

/* ---------------- 明细 ---------------- */
const detailLoading = ref(false)
const detailRows = ref<InventoryItem[]>([])
const detailTotal = ref(0)

async function loadDetail(): Promise<void> {
  detailLoading.value = true
  try {
    const data = await listInventory(query)
    detailRows.value = data.items || []
    detailTotal.value = data.total || 0
  } catch {
    detailRows.value = []
    detailTotal.value = 0
  } finally {
    detailLoading.value = false
  }
}

function loadCurrent(): void {
  if (activeTab.value === 'summary') loadSummary()
  else loadDetail()
}

function handleSearch(): void {
  query.page = 1
  loadCurrent()
}

function handleReset(): void {
  query.keyword = ''
  query.product_id = null
  query.warehouse_id = null
  query.batch_no = ''
  query.page = 1
  loadCurrent()
}

function handleTabChange(): void {
  query.page = 1
  loadCurrent()
}

/** 汇总合计 */
const summaryTotals = ref({ quantity: 0, locked: 0, available: 0, amount: 0 })

async function loadAllForTotals(): Promise<void> {
  // 仅当后端返回分页数据时，用当前页做展示合计，避免额外请求
  const rows = summaryRows.value
  summaryTotals.value = {
    quantity: rows.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
    locked: rows.reduce((sum, item) => sum + Number(item.locked_quantity || 0), 0),
    available: rows.reduce((sum, item) => sum + Number(item.available_quantity || 0), 0),
    amount: rows.reduce((sum, item) => sum + Number(item.amount || 0), 0)
  }
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

async function handleSummaryChange(): Promise<void> {
  await loadSummary()
  await loadAllForTotals()
}

onMounted(async () => {
  await Promise.all([loadOptions(), handleSummaryChange()])
})
</script>

<template>
  <div class="page-container">
    <div class="page-card">
      <el-form class="search-form" :inline="true" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="商品名称 / 编码 / 批次号"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="商品">
          <el-select v-model="query.product_id" placeholder="全部商品" clearable filterable style="width: 220px">
            <el-option v-for="item in products" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="query.warehouse_id" placeholder="全部仓库" clearable style="width: 180px">
            <el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="query.batch_no" placeholder="如 B20250901" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="page-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="按商品汇总" name="summary" />
        <el-tab-pane label="库存明细" name="detail" />
      </el-tabs>

      <template v-if="activeTab === 'summary'">
        <div class="stock-total">
          <span>
            当前页合计：账面
            <b>{{ formatQuantity(summaryTotals.quantity) }}</b> · 预占
            <b>{{ formatQuantity(summaryTotals.locked) }}</b> · 可用
            <b class="text-amount">{{ formatQuantity(summaryTotals.available) }}</b> · 货值
            <b class="text-amount">{{ formatMoney(summaryTotals.amount) }}</b> 元
          </span>
        </div>

        <el-table v-loading="summaryLoading" :data="summaryRows" border stripe>
          <el-table-column prop="product_code" label="商品编码" width="150" />
          <el-table-column prop="product_name" label="商品名称" min-width="200" show-overflow-tooltip />
          <el-table-column label="单位" width="80">
            <template #default="{ row }">{{ unitLabel(row.unit) || '-' }}</template>
          </el-table-column>
          <el-table-column label="账面总量" width="130" align="right">
            <template #default="{ row }">{{ formatQuantity(row.quantity) }}</template>
          </el-table-column>
          <el-table-column label="预占数量" width="130" align="right">
            <template #default="{ row }">{{ formatQuantity(row.locked_quantity) }}</template>
          </el-table-column>
          <el-table-column label="可用数量" width="130" align="right">
            <template #default="{ row }">
              <span class="text-amount">{{ formatQuantity(row.available_quantity) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="成本单价" width="130" align="right">
            <template #default="{ row }">{{ formatMoney(row.unit_cost) }}</template>
          </el-table-column>
          <el-table-column label="库存货值" width="150" align="right">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
        </el-table>

        <div class="table-pagination">
          <el-pagination
            v-model:current-page="query.page"
            v-model:page-size="query.page_size"
            :total="summaryTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            background
            @current-change="handleSummaryChange"
            @size-change="handleSummaryChange"
          />
        </div>
      </template>

      <template v-else>
        <el-table v-loading="detailLoading" :data="detailRows" border stripe>
          <el-table-column prop="product_code" label="商品编码" width="150" />
          <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="warehouse_name" label="仓库" min-width="150" />
          <el-table-column prop="location_name" label="库位" width="120" />
          <el-table-column prop="batch_no" label="批次号" width="140" />
          <el-table-column label="账面数量" width="130" align="right">
            <template #default="{ row }">
              {{ formatQuantityWithUnit(row.quantity, row.unit) }}
            </template>
          </el-table-column>
          <el-table-column label="预占数量" width="130" align="right">
            <template #default="{ row }">{{ formatQuantity(row.locked_quantity) }}</template>
          </el-table-column>
          <el-table-column label="可用数量" width="130" align="right">
            <template #default="{ row }">
              <span class="text-amount">{{ formatQuantity(row.available_quantity) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="成本单价" width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.unit_cost) }}</template>
          </el-table-column>
          <el-table-column label="生产日期" width="120">
            <template #default="{ row }">{{ row.production_date || '-' }}</template>
          </el-table-column>
          <el-table-column label="质量状态" width="100">
            <template #default="{ row }">
              <StatusTag group="qualityStatus" :value="row.quality_status" />
            </template>
          </el-table-column>
        </el-table>

        <div class="table-pagination">
          <el-pagination
            v-model:current-page="query.page"
            v-model:page-size="query.page_size"
            :total="detailTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            background
            @current-change="loadDetail"
            @size-change="loadDetail"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.stock-total {
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--gz-text-sub);
}
</style>
