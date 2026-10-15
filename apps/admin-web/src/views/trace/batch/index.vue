<script setup lang="ts">
/**
 * 溯源批次：批次 CRUD、链路事件追加、二维码展示与公开扫码预览。
 * 接口：GET/POST /trace/batches、GET /trace/batches/{id}、POST /trace/batches/{id}/events、GET /trace/public/{batch_no}
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import FileUpload from '@/components/FileUpload.vue'
import { appendTraceEvent, createTraceBatch, getTraceBatch, getTracePublic, listTraceBatches } from '@/api/trace'
import { listProducts } from '@/api/product'
import { listWarehouses } from '@/api/warehouse'
import type {
  Product,
  TraceBatch,
  TraceBatchPayload,
  TraceBatchQuery,
  TraceEvent,
  TraceEventPayload,
  TracePublicView,
  Warehouse
} from '@/api/types'
import { formatDate, formatDateTime } from '@/utils/format'

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<TraceBatch[]>([])
const total = ref(0)
const products = ref<Product[]>([])
const warehouses = ref<Warehouse[]>([])
const query = reactive<TraceBatchQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  product_id: null,
  status: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listTraceBatches(query)
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
  query.status = ''
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

/* ---------------- 新建批次 ---------------- */
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<TraceBatchPayload>({
  batch_no: '',
  product_id: undefined as unknown as number,
  origin_base: '新疆阿勒泰',
  origin_region: '新疆·北屯市',
  plant_date: '',
  harvest_date: '',
  process_enterprise: '',
  process_date: '',
  warehouse_id: null,
  test_report_url: '',
  quality_status: 'qualified'
})

const rules: FormRules = {
  product_id: [{ required: true, message: '请选择关联商品', trigger: 'change' }]
}

function openCreate(): void {
  Object.assign(form, {
    batch_no: '',
    product_id: undefined,
    origin_base: '新疆阿勒泰',
    origin_region: '新疆·北屯市',
    plant_date: '',
    harvest_date: '',
    process_enterprise: '',
    process_date: '',
    warehouse_id: null,
    test_report_url: '',
    quality_status: 'qualified'
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
      await createTraceBatch({ ...form })
      ElMessage.success('溯源批次已创建')
      dialogVisible.value = false
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      submitting.value = false
    }
  })
}

/* ---------------- 批次详情 / 链路 ---------------- */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<TraceBatch | null>(null)

async function openDetail(row: TraceBatch): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = row
  try {
    detail.value = await getTraceBatch(row.id)
  } catch {
    /* 使用列表数据 */
  } finally {
    detailLoading.value = false
  }
}

/* ---------------- 追加事件 ---------------- */
const eventVisible = ref(false)
const eventSubmitting = ref(false)
const eventFormRef = ref<FormInstance>()
const eventBatchId = ref<number | null>(null)
const eventForm = reactive<TraceEventPayload>({
  stage: 'planting',
  title: '',
  description: '',
  occurred_at: '',
  location: '',
  operator: '',
  evidence_url: ''
})

const eventRules: FormRules = {
  stage: [{ required: true, message: '请选择环节', trigger: 'change' }],
  title: [{ required: true, message: '请输入事件标题', trigger: 'blur' }],
  occurred_at: [{ required: true, message: '请选择发生时间', trigger: 'change' }]
}

function openEvent(batch: TraceBatch): void {
  eventBatchId.value = batch.id
  Object.assign(eventForm, {
    stage: 'planting',
    title: '',
    description: '',
    occurred_at: '',
    location: batch.origin_base || '',
    operator: '',
    evidence_url: ''
  })
  eventVisible.value = true
}

async function submitEvent(): Promise<void> {
  const el = eventFormRef.value
  if (!el || eventBatchId.value === null) return
  await el.validate(async (valid) => {
    if (!valid) return
    eventSubmitting.value = true
    try {
      await appendTraceEvent(eventBatchId.value as number, {
        ...eventForm,
        occurred_at: eventForm.occurred_at.length === 10 ? `${eventForm.occurred_at} 00:00:00` : eventForm.occurred_at
      })
      ElMessage.success('链路事件已追加')
      eventVisible.value = false
      if (detail.value?.id === eventBatchId.value) {
        detail.value = await getTraceBatch(eventBatchId.value as number).catch(() => detail.value)
      }
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      eventSubmitting.value = false
    }
  })
}

/* ---------------- 二维码 / 公开预览 ---------------- */
const qrVisible = ref(false)
const qrBatch = ref<TraceBatch | null>(null)
const publicView = ref<TracePublicView | null>(null)
const publicLoading = ref(false)

/** 公开扫码地址（GET /trace/public/{batch_no}） */
const publicUrl = computed(() => {
  const batchNo = qrBatch.value?.batch_no || ''
  if (!batchNo) return ''
  return `${window.location.origin}/api/v1/trace/public/${encodeURIComponent(batchNo)}`
})

/** 由批次号派生的确定性点阵（离线二维码占位，真实二维码由小程序/后端生成） */
const qrMatrix = computed<boolean[][]>(() => {
  const text = qrBatch.value?.qr_code || qrBatch.value?.batch_no || ''
  const size = 21
  const matrix: boolean[][] = []
  let seed = 0
  for (let i = 0; i < text.length; i++) {
    seed = (seed * 31 + text.charCodeAt(i)) % 100000
  }
  for (let row = 0; row < size; row++) {
    const line: boolean[] = []
    for (let col = 0; col < size; col++) {
      seed = (seed * 1103515245 + 12345) % 2147483648
      line.push(seed % 100 < 46)
    }
    matrix.push(line)
  }
  // 三个定位角
  const drawFinder = (top: number, left: number): void => {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const isBorder = r === 0 || r === 6 || c === 0 || c === 6
        const isCenter = r >= 2 && r <= 4 && c >= 2 && c <= 4
        matrix[top + r][left + c] = isBorder || isCenter
      }
    }
  }
  drawFinder(0, 0)
  drawFinder(0, size - 7)
  drawFinder(size - 7, 0)
  return matrix
})

async function openQr(row: TraceBatch): Promise<void> {
  qrBatch.value = row
  qrVisible.value = true
  publicView.value = null
  publicLoading.value = true
  try {
    publicView.value = await getTracePublic(row.batch_no)
  } catch {
    publicView.value = null
  } finally {
    publicLoading.value = false
  }
}

async function copyPublicUrl(): Promise<void> {
  if (!publicUrl.value) return
  try {
    await navigator.clipboard.writeText(publicUrl.value)
    ElMessage.success('扫码地址已复制')
  } catch {
    ElMessage.warning('当前浏览器不支持自动复制，请手动选择复制')
  }
}

/** 按环节分组展示链路 */
const eventsByStage = computed(() => {
  const events: TraceEvent[] = publicView.value?.events || detail.value?.events || []
  const groups = new Map<string, TraceEvent[]>()
  events.forEach((event) => {
    const key = event.stage || 'other'
    const arr = groups.get(key) || []
    arr.push(event)
    groups.set(key, arr)
  })
  return Array.from(groups.entries()).map(([stage, items]) => ({ stage, items }))
})

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
                placeholder="批次号 / 二维码"
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
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="traceBatchStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'trace:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>新建溯源批次</span>
        </el-button>
      </template>

      <el-table-column prop="batch_no" label="批次号" width="160">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="openDetail(row as TraceBatch)">{{ row.batch_no }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="product_name" label="关联商品" min-width="180" show-overflow-tooltip />
      <el-table-column label="所属企业" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.enterprise_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="origin_base" label="种植基地" min-width="140" />
      <el-table-column prop="origin_region" label="产地" min-width="130" />
      <el-table-column label="种植日期" width="120">
        <template #default="{ row }">{{ formatDate(row.plant_date) }}</template>
      </el-table-column>
      <el-table-column label="采收日期" width="120">
        <template #default="{ row }">{{ formatDate(row.harvest_date) }}</template>
      </el-table-column>
      <el-table-column label="质量状态" width="100">
        <template #default="{ row }">
          <StatusTag group="qualityStatus" :value="row.quality_status" />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <StatusTag group="traceBatchStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row as TraceBatch)">链路</el-button>
          <el-button link type="success" @click="openQr(row as TraceBatch)">二维码</el-button>
          <el-button v-permission="'trace:write'" link type="primary" @click="openEvent(row as TraceBatch)">追加事件</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 新建批次 -->
    <el-dialog v-model="dialogVisible" title="新建溯源批次" width="700px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="批次号">
              <el-input v-model="form.batch_no" placeholder="留空由后端生成，如 B20250901" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联商品" prop="product_id">
              <el-select v-model="form.product_id" placeholder="请选择商品" filterable style="width: 100%">
                <el-option v-for="item in products" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="种植基地">
              <el-input v-model="form.origin_base" placeholder="如 阿勒泰某某合作社基地" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产地">
              <el-input v-model="form.origin_region" placeholder="如 新疆·阿勒泰" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="种植日期">
              <el-date-picker
                v-model="form.plant_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采收日期">
              <el-date-picker
                v-model="form.harvest_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="加工企业">
              <el-input v-model="form.process_enterprise" placeholder="如 新疆XX瓜子有限公司" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="加工日期">
              <el-date-picker
                v-model="form.process_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓储仓库">
              <el-select v-model="form.warehouse_id" placeholder="请选择仓库" clearable style="width: 100%">
                <el-option v-for="item in warehouses" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="质量状态">
              <DictSelect v-model="form.quality_status" group="qualityStatus" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="检测报告">
              <FileUpload v-model="form.test_report_url" biz-type="trace_report" accept=".pdf,.jpg,.png" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">创建</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="溯源批次详情" size="640px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="批次号" :span="2">{{ detail.batch_no }}</el-descriptions-item>
            <el-descriptions-item label="二维码" :span="2">{{ detail.qr_code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联商品">{{ detail.product_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="商品编码">{{ detail.product_code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属企业" :span="2">{{ detail.enterprise_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="种植基地">{{ detail.origin_base || '-' }}</el-descriptions-item>
            <el-descriptions-item label="产地">{{ detail.origin_region || '-' }}</el-descriptions-item>
            <el-descriptions-item label="种植日期">{{ formatDate(detail.plant_date) }}</el-descriptions-item>
            <el-descriptions-item label="采收日期">{{ formatDate(detail.harvest_date) }}</el-descriptions-item>
            <el-descriptions-item label="加工企业">{{ detail.process_enterprise || '-' }}</el-descriptions-item>
            <el-descriptions-item label="加工日期">{{ formatDate(detail.process_date) }}</el-descriptions-item>
            <el-descriptions-item label="仓储仓库">{{ detail.warehouse_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="质量状态">
              <StatusTag group="qualityStatus" :value="detail.quality_status" />
            </el-descriptions-item>
            <el-descriptions-item label="批次状态">
              <StatusTag group="traceBatchStatus" :value="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
          </el-descriptions>

          <div class="detail-block">
            <div class="detail-block__title">检测报告</div>
            <el-link v-if="detail.test_report_url" type="primary" :href="detail.test_report_url" target="_blank">
              <el-icon><Document /></el-icon>
              <span>打开检测报告</span>
            </el-link>
            <span v-else class="text-sub">未上传</span>
          </div>

          <div class="detail-block">
            <div class="detail-block__title">溯源链路（trace_event）</div>
            <el-timeline v-if="(detail.events || []).length > 0">
              <el-timeline-item
                v-for="event in detail.events"
                :key="event.id"
                :timestamp="formatDateTime(event.occurred_at)"
                placement="top"
              >
                <div class="event-title">
                  <StatusTag group="traceStage" :value="event.stage" />
                  <span>{{ event.title }}</span>
                </div>
                <div class="text-sub">{{ event.description || '' }}</div>
                <div class="text-sub">
                  {{ event.location || '' }} {{ event.operator ? `· ${event.operator}` : '' }}
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无链路事件" :image-size="70" />
          </div>
        </template>
      </div>
    </el-drawer>

    <!-- 追加事件 -->
    <el-dialog v-model="eventVisible" title="追加溯源链路事件" width="600px" append-to-body>
      <el-form ref="eventFormRef" :model="eventForm" :rules="eventRules" label-width="110px">
        <el-form-item label="环节" prop="stage">
          <DictSelect v-model="eventForm.stage" group="traceStage" :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="事件标题" prop="title">
          <el-input v-model="eventForm.title" placeholder="如 采收完成 / 入库 / 发运" />
        </el-form-item>
        <el-form-item label="发生时间" prop="occurred_at">
          <el-date-picker
            v-model="eventForm.occurred_at"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="eventForm.location" />
        </el-form-item>
        <el-form-item label="操作人">
          <el-input v-model="eventForm.operator" />
        </el-form-item>
        <el-form-item label="事件说明">
          <el-input v-model="eventForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="凭证附件">
          <FileUpload v-model="eventForm.evidence_url" biz-type="trace_evidence" accept=".pdf,.jpg,.png" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="eventVisible = false">取消</el-button>
        <el-button type="primary" :loading="eventSubmitting" @click="submitEvent">提交</el-button>
      </template>
    </el-dialog>

    <!-- 二维码 -->
    <el-dialog v-model="qrVisible" title="溯源二维码与公开视图" width="780px" append-to-body>
      <el-row :gutter="16">
        <el-col :span="9">
          <div class="qr-box">
            <div class="qr-matrix">
              <template v-for="(line, rowIndex) in qrMatrix" :key="`row-${rowIndex}`">
                <span
                  v-for="(cell, colIndex) in line"
                  :key="`cell-${rowIndex}-${colIndex}`"
                  class="qr-cell"
                  :class="{ 'is-dark': cell }"
                />
              </template>
            </div>
            <div class="qr-batch">{{ qrBatch?.batch_no }}</div>
            <div class="text-sub qr-tip">
              离线点阵示意（由批次号派生）。正式二维码请使用小程序或后端生成的 qr_code。
            </div>
            <el-input :model-value="publicUrl" readonly class="mt-8">
              <template #append>
                <el-button @click="copyPublicUrl">复制</el-button>
              </template>
            </el-input>
          </div>
        </el-col>

        <el-col :span="15">
          <div v-loading="publicLoading" class="public-view">
            <template v-if="publicView">
              <el-descriptions :column="1" border>
                <el-descriptions-item label="公开接口">
                  GET /api/v1/trace/public/{{ publicView.batch_no }}
                </el-descriptions-item>
                <el-descriptions-item label="商品">{{ publicView.product_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="规格/等级">
                  {{ publicView.spec || '-' }} / {{ publicView.grade || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="产地">
                  {{ publicView.origin_region || '-' }} {{ publicView.origin_base || '' }}
                </el-descriptions-item>
                <el-descriptions-item label="生产企业">{{ publicView.enterprise_name || '-' }}</el-descriptions-item>
                <el-descriptions-item label="采收日期">{{ formatDate(publicView.harvest_date) }}</el-descriptions-item>
                <el-descriptions-item label="质量状态">
                  <StatusTag group="qualityStatus" :value="publicView.quality_status" />
                </el-descriptions-item>
                <el-descriptions-item label="检测报告">
                  <el-link
                    v-if="publicView.test_report_url"
                    type="primary"
                    :href="publicView.test_report_url"
                    target="_blank"
                  >
                    查看报告
                  </el-link>
                  <span v-else class="text-sub">无</span>
                </el-descriptions-item>
              </el-descriptions>

              <div class="detail-block">
                <div class="detail-block__title">公开链路</div>
                <div v-for="group in eventsByStage" :key="group.stage" class="public-stage">
                  <StatusTag group="traceStage" :value="group.stage" />
                  <ul class="public-stage__list">
                    <li v-for="event in group.items" :key="event.id">
                      <b>{{ event.title }}</b>
                      <span class="text-sub">
                        （{{ formatDate(event.occurred_at) }} {{ event.location || '' }}）
                      </span>
                    </li>
                  </ul>
                </div>
              </div>
            </template>
            <el-empty v-else description="公开视图加载失败或批次不存在" :image-size="80" />
          </div>
        </el-col>
      </el-row>
      <template #footer>
        <el-button @click="qrVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-block {
  margin-top: 16px;
}

.detail-block__title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.event-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.qr-box {
  text-align: center;
}

.qr-matrix {
  display: grid;
  grid-template-columns: repeat(21, 12px);
  grid-template-rows: repeat(21, 12px);
  justify-content: center;
  margin: 0 auto;
  padding: 8px;
  background: #fff;
  border: 1px solid var(--gz-border);
  border-radius: 6px;
  width: fit-content;
}

.qr-cell {
  width: 12px;
  height: 12px;
  background: #fff;
}

.qr-cell.is-dark {
  background: #14181f;
}

.qr-batch {
  margin-top: 8px;
  font-weight: 600;
  letter-spacing: 1px;
}

.qr-tip {
  margin-top: 4px;
  font-size: 12px;
}

.public-stage {
  margin-bottom: 10px;
}

.public-stage__list {
  margin: 6px 0 0;
  padding-left: 18px;
  line-height: 1.9;
}
</style>
