<script setup lang="ts">
/**
 * 园区与区域：园区 CRUD（/parks）+ 区域管理（/parks/{id}/zones、PUT/DELETE /zones/{id}）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import {
  createPark,
  createParkZone,
  deletePark,
  deleteParkZone,
  listParkZones,
  listParks,
  updatePark,
  updateParkZone
} from '@/api/park'
import type {
  Park,
  ParkPayload,
  ParkQuery,
  ParkZone,
  ParkZonePayload
} from '@/api/types'
import { formatMoney } from '@/utils/format'

/* ---------------- 园区列表 ---------------- */
const loading = ref(false)
const list = ref<Park[]>([])
const total = ref(0)
const query = reactive<ParkQuery>({ page: 1, page_size: 20, keyword: '', status: '' })

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listParks(query)
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
  query.region = ''
  query.page = 1
  loadList()
}

/* ---------------- 园区新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增园区')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<ParkPayload>({
  code: '',
  name: '',
  region: '新疆·北屯市',
  address: '',
  area_total: '',
  contact_name: '',
  contact_phone: '',
  status: 'active',
  description: ''
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入园区编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入园区名称', trigger: 'blur' }]
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增园区'
  Object.assign(form, {
    code: '',
    name: '',
    region: '新疆·北屯市',
    address: '',
    area_total: '',
    contact_name: '',
    contact_phone: '',
    status: 'active',
    description: ''
  })
  dialogVisible.value = true
}

function openEdit(row: Park): void {
  editingId.value = row.id
  dialogTitle.value = `编辑园区：${row.name}`
  Object.assign(form, {
    code: row.code,
    name: row.name,
    region: row.region || '',
    address: row.address || '',
    area_total: row.area_total || '',
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    status: row.status,
    description: row.description || ''
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
      if (editingId.value === null) {
        await createPark({ ...form })
        ElMessage.success('园区创建成功')
      } else {
        await updatePark(editingId.value, { ...form })
        ElMessage.success('园区已更新')
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

async function handleDelete(row: Park): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除园区「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deletePark(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 区域管理 ---------------- */
const zoneVisible = ref(false)
const zoneLoading = ref(false)
const zones = ref<ParkZone[]>([])
const currentPark = ref<Park | null>(null)

const zoneDialogVisible = ref(false)
const zoneDialogTitle = ref('新增区域')
const zoneSubmitting = ref(false)
const zoneFormRef = ref<FormInstance>()
const editingZoneId = ref<number | null>(null)
const zoneForm = reactive<ParkZonePayload>({
  code: '',
  name: '',
  zone_type: 'trade',
  area: '',
  sort: 0,
  status: 'active'
})

const zoneRules: FormRules = {
  code: [{ required: true, message: '请输入区域编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入区域名称', trigger: 'blur' }],
  zone_type: [{ required: true, message: '请选择区域类型', trigger: 'change' }]
}

async function openZones(row: Park): Promise<void> {
  currentPark.value = row
  zoneVisible.value = true
  await reloadZones()
}

async function reloadZones(): Promise<void> {
  if (!currentPark.value) return
  zoneLoading.value = true
  try {
    zones.value = await listParkZones(currentPark.value.id)
  } catch {
    zones.value = []
  } finally {
    zoneLoading.value = false
  }
}

function openZoneCreate(): void {
  editingZoneId.value = null
  zoneDialogTitle.value = '新增区域'
  Object.assign(zoneForm, { code: '', name: '', zone_type: 'trade', area: '', sort: 0, status: 'active' })
  zoneDialogVisible.value = true
}

function openZoneEdit(row: ParkZone): void {
  editingZoneId.value = row.id
  zoneDialogTitle.value = `编辑区域：${row.name}`
  Object.assign(zoneForm, {
    code: row.code,
    name: row.name,
    zone_type: row.zone_type,
    area: row.area || '',
    sort: row.sort ?? 0,
    status: row.status
  })
  zoneDialogVisible.value = true
}

async function submitZone(): Promise<void> {
  const el = zoneFormRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    if (!currentPark.value) return
    zoneSubmitting.value = true
    try {
      if (editingZoneId.value === null) {
        await createParkZone(currentPark.value.id, { ...zoneForm })
        ElMessage.success('区域创建成功')
      } else {
        await updateParkZone(editingZoneId.value, { ...zoneForm })
        ElMessage.success('区域已更新')
      }
      zoneDialogVisible.value = false
      await reloadZones()
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      zoneSubmitting.value = false
    }
  })
}

async function handleZoneDelete(row: ParkZone): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除区域「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteParkZone(row.id)
    ElMessage.success('删除成功')
    await reloadZones()
    loadList()
  } catch {
    /* 已提示 */
  }
}

onMounted(loadList)
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
                placeholder="园区名称 / 编码"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="行政区划">
              <el-input v-model="query.region" placeholder="如 新疆·北屯市" clearable style="width: 180px" />
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="commonStatus" with-all placeholder="全部状态" />
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
          <span>新增园区</span>
        </el-button>
      </template>

      <el-table-column prop="code" label="园区编码" width="140" />
      <el-table-column prop="name" label="园区名称" min-width="200" />
      <el-table-column prop="region" label="行政区划" min-width="150" />
      <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column label="占地面积(亩)" width="130" align="right">
        <template #default="{ row }">{{ formatMoney(row.area_total, 2) }}</template>
      </el-table-column>
      <el-table-column prop="contact_name" label="联系人" width="100" />
      <el-table-column prop="contact_phone" label="联系电话" width="130" />
      <el-table-column label="区域数" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.zone_count ?? 0 }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="档口数" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.stall_count ?? 0 }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <StatusTag group="commonStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openZones(row as Park)">区域管理</el-button>
          <el-button v-permission="'park:write'" link type="primary" @click="openEdit(row as Park)">编辑</el-button>
          <el-button v-permission="'park:write'" link type="danger" @click="handleDelete(row as Park)">删除</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 园区弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="园区编码" prop="code">
              <el-input v-model="form.code" placeholder="如 PARK-BT01" :disabled="editingId !== null" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="园区名称" prop="name">
              <el-input v-model="form.name" placeholder="如 北屯瓜子油料交易园区" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="行政区划">
              <el-input v-model="form.region" placeholder="如 新疆·北屯市" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="占地面积(亩)">
              <el-input v-model="form.area_total" placeholder="如 320.00" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="form.contact_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="form.contact_phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <DictSelect v-model="form.status" group="commonStatus" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="园区地址">
              <el-input v-model="form.address" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="园区简介">
              <el-input v-model="form.description" type="textarea" :rows="3" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 区域抽屉 -->
    <el-drawer v-model="zoneVisible" :title="`区域管理：${currentPark?.name || ''}`" size="640px">
      <div class="flex-between mb-12">
        <span class="text-sub">共 {{ zones.length }} 个区域</span>
        <el-button v-permission="'park:write'" type="primary" size="small" @click="openZoneCreate">
          <el-icon><Plus /></el-icon>
          <span>新增区域</span>
        </el-button>
      </div>

      <el-table v-loading="zoneLoading" :data="zones" border stripe>
        <el-table-column prop="code" label="区域编码" width="130" />
        <el-table-column prop="name" label="区域名称" min-width="140" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <StatusTag group="zoneType" :value="row.zone_type" />
          </template>
        </el-table-column>
        <el-table-column prop="area" label="面积" width="110" align="right" />
        <el-table-column prop="sort" label="排序" width="80" align="center" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusTag group="commonStatus" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="'park:write'" link type="primary" @click="openZoneEdit(row as ParkZone)">编辑</el-button>
            <el-button v-permission="'park:write'" link type="danger" @click="handleZoneDelete(row as ParkZone)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 区域弹窗 -->
    <el-dialog v-model="zoneDialogVisible" :title="zoneDialogTitle" width="480px" append-to-body>
      <el-form ref="zoneFormRef" :model="zoneForm" :rules="zoneRules" label-width="100px">
        <el-form-item label="区域编码" prop="code">
          <el-input v-model="zoneForm.code" placeholder="如 Z-TRADE-01" :disabled="editingZoneId !== null" />
        </el-form-item>
        <el-form-item label="区域名称" prop="name">
          <el-input v-model="zoneForm.name" placeholder="如 交易一区" />
        </el-form-item>
        <el-form-item label="区域类型" prop="zone_type">
          <DictSelect v-model="zoneForm.zone_type" group="zoneType" :clearable="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="面积">
          <el-input v-model="zoneForm.area" placeholder="如 12000.00" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="zoneForm.sort" :min="0" :max="9999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <DictSelect v-model="zoneForm.status" group="commonStatus" :clearable="false" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="zoneDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="zoneSubmitting" @click="submitZone">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
