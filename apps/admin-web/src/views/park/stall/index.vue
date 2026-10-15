<script setup lang="ts">
/**
 * 档口管理与入驻：档口 CRUD（/stalls）+ 入驻/退租（POST /stalls/{id}/assign）+ 园区合同与生效（/park-contracts）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import FileUpload from '@/components/FileUpload.vue'
import {
  assignStall,
  createParkContract,
  createStall,
  deleteStall,
  effectParkContract,
  listParkContracts,
  listParkZones,
  listParks,
  listStalls,
  updateParkContract,
  updateStall
} from '@/api/park'
import { listEnterprises } from '@/api/enterprise'
import type {
  Enterprise,
  FeeCycle,
  Park,
  ParkContract,
  ParkContractPayload,
  ParkContractQuery,
  ParkZone,
  Stall,
  StallPayload,
  StallQuery
} from '@/api/types'
import { formatDate, formatMoney } from '@/utils/format'

/* ---------------- 选项数据 ---------------- */
const parks = ref<Park[]>([])
const zones = ref<ParkZone[]>([])
const enterprises = ref<Enterprise[]>([])

async function loadParks(): Promise<void> {
  try {
    const data = await listParks({ page: 1, page_size: 200 })
    parks.value = data.items || []
  } catch {
    parks.value = []
  }
}

async function loadEnterprises(): Promise<void> {
  try {
    const data = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = data.items || []
  } catch {
    enterprises.value = []
  }
}

async function loadZones(parkId?: number | null): Promise<void> {
  if (!parkId) {
    zones.value = []
    return
  }
  try {
    zones.value = await listParkZones(parkId)
  } catch {
    zones.value = []
  }
}

/* ---------------- 档口列表 ---------------- */
const loading = ref(false)
const list = ref<Stall[]>([])
const total = ref(0)
const query = reactive<StallQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  park_id: null,
  zone_id: null,
  status: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listStalls(query)
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
  query.park_id = null
  query.zone_id = null
  query.status = ''
  query.page = 1
  loadList()
}

/** 出租率统计（当前页） */
function rentedRate(): string {
  if (list.value.length === 0) return '-'
  const rented = list.value.filter((item) => item.status === 'rented').length
  return `${((rented / list.value.length) * 100).toFixed(1)}%`
}

/* ---------------- 档口新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增档口')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<StallPayload>({
  park_id: undefined as unknown as number,
  zone_id: null,
  code: '',
  name: '',
  area: '',
  monthly_fee: '',
  status: 'free',
  remark: ''
})

const rules: FormRules = {
  park_id: [{ required: true, message: '请选择所属园区', trigger: 'change' }],
  code: [{ required: true, message: '请输入档口编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入档口名称', trigger: 'blur' }]
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增档口'
  Object.assign(form, {
    park_id: query.park_id || undefined,
    zone_id: query.zone_id ?? null,
    code: '',
    name: '',
    area: '',
    monthly_fee: '',
    status: 'free',
    remark: ''
  })
  if (form.park_id) loadZones(form.park_id)
  dialogVisible.value = true
}

function openEdit(row: Stall): void {
  editingId.value = row.id
  dialogTitle.value = `编辑档口：${row.name}`
  Object.assign(form, {
    park_id: row.park_id,
    zone_id: row.zone_id ?? null,
    code: row.code,
    name: row.name,
    area: row.area || '',
    monthly_fee: row.monthly_fee || '',
    status: row.status,
    remark: row.remark || ''
  })
  loadZones(row.park_id)
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
        await createStall({ ...form })
        ElMessage.success('档口创建成功')
      } else {
        await updateStall(editingId.value, { ...form })
        ElMessage.success('档口已更新')
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

async function handleDelete(row: Stall): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除档口「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteStall(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 入驻 / 退租 ---------------- */
const assignVisible = ref(false)
const assignSubmitting = ref(false)
const assignTarget = ref<Stall | null>(null)
const assignForm = reactive<{ enterprise_id: number | null; mode: 'in' | 'out' }>({
  enterprise_id: null,
  mode: 'in'
})

function openAssign(row: Stall): void {
  assignTarget.value = row
  if (row.enterprise_id) {
    assignForm.mode = 'out'
    assignForm.enterprise_id = row.enterprise_id
  } else {
    assignForm.mode = 'in'
    assignForm.enterprise_id = null
  }
  assignVisible.value = true
}

async function submitAssign(): Promise<void> {
  if (!assignTarget.value) return
  if (assignForm.mode === 'in' && !assignForm.enterprise_id) {
    ElMessage.warning('请选择入驻企业')
    return
  }
  assignSubmitting.value = true
  try {
    await assignStall(assignTarget.value.id, {
      enterprise_id: assignForm.mode === 'in' ? assignForm.enterprise_id : null
    })
    ElMessage.success(assignForm.mode === 'in' ? '入驻登记成功' : '退租成功，档口已释放')
    assignVisible.value = false
    loadList()
    loadContracts()
  } catch {
    /* 已提示 */
  } finally {
    assignSubmitting.value = false
  }
}

/* ---------------- 园区合同 ---------------- */
const contractLoading = ref(false)
const contracts = ref<ParkContract[]>([])
const contractTotal = ref(0)
const contractQuery = reactive<ParkContractQuery>({
  page: 1,
  page_size: 10,
  keyword: '',
  park_id: null,
  status: ''
})

async function loadContracts(): Promise<void> {
  contractLoading.value = true
  try {
    const data = await listParkContracts(contractQuery)
    contracts.value = data.items || []
    contractTotal.value = data.total || 0
  } catch {
    contracts.value = []
    contractTotal.value = 0
  } finally {
    contractLoading.value = false
  }
}

const contractVisible = ref(false)
const contractTitle = ref('新增园区合同')
const contractSubmitting = ref(false)
const contractFormRef = ref<FormInstance>()
const editingContractId = ref<number | null>(null)
const contractForm = reactive<ParkContractPayload>({
  contract_no: '',
  park_id: undefined as unknown as number,
  stall_id: undefined as unknown as number,
  enterprise_id: undefined as unknown as number,
  start_date: '',
  end_date: '',
  rent_amount: '',
  deposit_amount: '',
  fee_cycle: 'month',
  file_url: '',
  remark: ''
})

const contractRules: FormRules = {
  park_id: [{ required: true, message: '请选择园区', trigger: 'change' }],
  stall_id: [{ required: true, message: '请选择档口', trigger: 'change' }],
  enterprise_id: [{ required: true, message: '请选择入驻企业', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
  rent_amount: [{ required: true, message: '请输入租金金额', trigger: 'blur' }]
}

const contractStalls = ref<Stall[]>([])

async function loadContractStalls(parkId?: number | null): Promise<void> {
  if (!parkId) {
    contractStalls.value = []
    return
  }
  try {
    const data = await listStalls({ page: 1, page_size: 200, park_id: parkId })
    contractStalls.value = data.items || []
  } catch {
    contractStalls.value = []
  }
}

function openContractCreate(): void {
  editingContractId.value = null
  contractTitle.value = '新增园区合同'
  Object.assign(contractForm, {
    contract_no: '',
    park_id: query.park_id || undefined,
    stall_id: undefined,
    enterprise_id: undefined,
    start_date: '',
    end_date: '',
    rent_amount: '',
    deposit_amount: '',
    fee_cycle: 'month' as FeeCycle,
    file_url: '',
    remark: ''
  })
  if (contractForm.park_id) loadContractStalls(contractForm.park_id)
  contractVisible.value = true
}

function openContractEdit(row: ParkContract): void {
  editingContractId.value = row.id
  contractTitle.value = `编辑合同：${row.contract_no}`
  Object.assign(contractForm, {
    contract_no: row.contract_no,
    park_id: row.park_id,
    stall_id: row.stall_id,
    enterprise_id: row.enterprise_id,
    start_date: row.start_date,
    end_date: row.end_date,
    rent_amount: row.rent_amount,
    deposit_amount: row.deposit_amount || '',
    fee_cycle: row.fee_cycle,
    file_url: row.file_url || '',
    remark: row.remark || ''
  })
  loadContractStalls(row.park_id)
  contractVisible.value = true
}

async function submitContract(): Promise<void> {
  const el = contractFormRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    contractSubmitting.value = true
    try {
      if (editingContractId.value === null) {
        await createParkContract({ ...contractForm })
        ElMessage.success('园区合同已创建')
      } else {
        await updateParkContract(editingContractId.value, { ...contractForm })
        ElMessage.success('园区合同已更新')
      }
      contractVisible.value = false
      loadContracts()
    } catch {
      /* 已提示 */
    } finally {
      contractSubmitting.value = false
    }
  })
}

async function handleEffect(row: ParkContract): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认合同「${row.contract_no}」生效？生效后将占用档口并更新档口状态。`,
      '合同生效',
      { type: 'warning', confirmButtonText: '确认生效', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await effectParkContract(row.id)
    ElMessage.success('合同已生效，档口已占用')
    await Promise.all([loadContracts(), loadList()])
  } catch {
    /* 已提示 */
  }
}

onMounted(async () => {
  await Promise.all([loadParks(), loadEnterprises(), loadList(), loadContracts()])
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
                placeholder="档口编码 / 名称"
                clearable
                style="width: 190px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="园区">
              <el-select
                v-model="query.park_id"
                placeholder="全部园区"
                clearable
                style="width: 200px"
                @change="(value: number) => loadZones(value)"
              >
                <el-option v-for="item in parks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="区域">
              <el-select v-model="query.zone_id" placeholder="全部区域" clearable style="width: 170px">
                <el-option v-for="item in zones" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="stallStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'park:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>新增档口</span>
        </el-button>
        <el-button v-permission="'park:write'" @click="openContractCreate">
          <el-icon><Document /></el-icon>
          <span>新增园区合同</span>
        </el-button>
        <el-tag type="info" effect="plain">当前页出租率：{{ rentedRate() }}</el-tag>
      </template>

      <el-table-column prop="code" label="档口编码" width="130" />
      <el-table-column prop="name" label="档口名称" min-width="160" />
      <el-table-column prop="park_name" label="所属园区" min-width="180" show-overflow-tooltip />
      <el-table-column prop="zone_name" label="所属区域" min-width="130" />
      <el-table-column prop="area" label="面积(㎡)" width="110" align="right" />
      <el-table-column label="月租金" width="130" align="right">
        <template #default="{ row }">{{ formatMoney(row.monthly_fee) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <StatusTag group="stallStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="入驻企业" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.enterprise_name || '未入驻' }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'park:write'" link type="primary" @click="openAssign(row as Stall)">
            {{ row.enterprise_id ? '退租' : '入驻登记' }}
          </el-button>
          <el-button v-permission="'park:write'" link type="primary" @click="openEdit(row as Stall)">编辑</el-button>
          <el-button v-permission="'park:write'" link type="danger" @click="handleDelete(row as Stall)">删除</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 园区合同 -->
    <div class="page-card">
      <div class="page-title">
        <span>
          园区租赁合同
          <span class="page-title__sub">共 {{ contractTotal }} 份合同</span>
        </span>
        <el-button size="small" @click="loadContracts">
          <el-icon><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>

      <el-table v-loading="contractLoading" :data="contracts" border stripe>
        <el-table-column prop="contract_no" label="合同编号" width="170" />
        <el-table-column prop="park_name" label="园区" min-width="170" show-overflow-tooltip />
        <el-table-column prop="stall_name" label="档口" min-width="140" />
        <el-table-column prop="enterprise_name" label="入驻企业" min-width="180" show-overflow-tooltip />
        <el-table-column label="租期" width="200">
          <template #default="{ row }">{{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}</template>
        </el-table-column>
        <el-table-column label="租金" width="130" align="right">
          <template #default="{ row }">{{ formatMoney(row.rent_amount) }}</template>
        </el-table-column>
        <el-table-column label="押金" width="130" align="right">
          <template #default="{ row }">{{ formatMoney(row.deposit_amount) }}</template>
        </el-table-column>
        <el-table-column label="缴费周期" width="100">
          <template #default="{ row }">
            <StatusTag group="feeCycle" :value="row.fee_cycle" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag group="parkContractStatus" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'draft'"
              v-permission="'park:write'"
              link
              type="success"
              @click="handleEffect(row as ParkContract)"
            >
              生效
            </el-button>
            <el-button v-permission="'park:write'" link type="primary" @click="openContractEdit(row as ParkContract)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-pagination">
        <el-pagination
          v-model:current-page="contractQuery.page"
          v-model:page-size="contractQuery.page_size"
          :total="contractTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="loadContracts"
          @size-change="loadContracts"
        />
      </div>
    </div>

    <!-- 档口弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="所属园区" prop="park_id">
              <el-select
                v-model="form.park_id"
                placeholder="请选择园区"
                style="width: 100%"
                @change="(value: number) => loadZones(value)"
              >
                <el-option v-for="item in parks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属区域">
              <el-select v-model="form.zone_id" placeholder="请选择区域" clearable style="width: 100%">
                <el-option v-for="item in zones" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="档口编码" prop="code">
              <el-input v-model="form.code" placeholder="如 ST-A-001" :disabled="editingId !== null" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="档口名称" prop="name">
              <el-input v-model="form.name" placeholder="如 A 区 001 号档口" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="面积(㎡)">
              <el-input v-model="form.area" placeholder="如 60.00" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="月租金(元)">
              <el-input v-model="form.monthly_fee" placeholder="如 3000.00" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="档口状态">
              <DictSelect v-model="form.status" group="stallStatus" :clearable="false" style="width: 100%" />
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

    <!-- 入驻 / 退租 -->
    <el-dialog v-model="assignVisible" title="档口入驻 / 退租" width="480px" append-to-body>
      <el-form label-width="100px">
        <el-form-item label="档口">
          <span>{{ assignTarget?.name }}（{{ assignTarget?.code }}）</span>
        </el-form-item>
        <el-form-item label="操作类型">
          <el-radio-group v-model="assignForm.mode">
            <el-radio value="in">入驻</el-radio>
            <el-radio value="out">退租</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="assignForm.mode === 'in'" label="入驻企业">
          <el-select v-model="assignForm.enterprise_id" placeholder="请选择企业" filterable style="width: 100%">
            <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="当前企业">
          <span>{{ assignTarget?.enterprise_name || '未入驻' }}</span>
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="POST /stalls/{id}/assign：enterprise_id 传企业 id 表示入驻，传 null 表示退租"
      />
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignSubmitting" @click="submitAssign">确认</el-button>
      </template>
    </el-dialog>

    <!-- 园区合同弹窗 -->
    <el-dialog v-model="contractVisible" :title="contractTitle" width="680px" append-to-body>
      <el-form ref="contractFormRef" :model="contractForm" :rules="contractRules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="合同编号">
              <el-input v-model="contractForm.contract_no" placeholder="留空由后端生成" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="园区" prop="park_id">
              <el-select
                v-model="contractForm.park_id"
                placeholder="请选择园区"
                style="width: 100%"
                @change="(value: number) => loadContractStalls(value)"
              >
                <el-option v-for="item in parks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="档口" prop="stall_id">
              <el-select v-model="contractForm.stall_id" placeholder="请选择档口" filterable style="width: 100%">
                <el-option v-for="item in contractStalls" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入驻企业" prop="enterprise_id">
              <el-select v-model="contractForm.enterprise_id" placeholder="请选择企业" filterable style="width: 100%">
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker
                v-model="contractForm.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker
                v-model="contractForm.end_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="租金金额" prop="rent_amount">
              <el-input v-model="contractForm.rent_amount" placeholder="元">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="押金">
              <el-input v-model="contractForm.deposit_amount" placeholder="元">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="缴费周期">
              <DictSelect v-model="contractForm.fee_cycle" group="feeCycle" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="合同文件">
              <FileUpload v-model="contractForm.file_url" biz-type="park_contract" accept=".pdf,.jpg,.png,.doc,.docx" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="contractForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="contractVisible = false">取消</el-button>
        <el-button type="primary" :loading="contractSubmitting" @click="submitContract">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
