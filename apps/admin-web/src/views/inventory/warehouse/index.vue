<script setup lang="ts">
/**
 * 仓库与库位：仓库 CRUD + 库位管理（GET/POST /warehouses、/warehouses/{id}/locations、PUT/DELETE /locations/{id}）。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import {
  createLocation,
  createWarehouse,
  deleteLocation,
  deleteWarehouse,
  listLocations,
  listWarehouses,
  updateLocation,
  updateWarehouse
} from '@/api/warehouse'
import { listEnterprises } from '@/api/enterprise'
import { listParks } from '@/api/park'
import type {
  Enterprise,
  Park,
  StorageLocation,
  StorageLocationPayload,
  Warehouse,
  WarehousePayload,
  WarehouseQuery
} from '@/api/types'

/* ---------------- 仓库列表 ---------------- */
const loading = ref(false)
const list = ref<Warehouse[]>([])
const total = ref(0)
const enterprises = ref<Enterprise[]>([])
const parks = ref<Park[]>([])
const query = reactive<WarehouseQuery>({
  page: 1,
  page_size: 20,
  keyword: '',
  enterprise_id: null,
  warehouse_type: ''
})

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listWarehouses(query)
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
  query.enterprise_id = null
  query.warehouse_type = ''
  query.page = 1
  loadList()
}

async function loadOptions(): Promise<void> {
  try {
    const data = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = data.items || []
  } catch {
    enterprises.value = []
  }
  try {
    const data = await listParks({ page: 1, page_size: 200 })
    parks.value = data.items || []
  } catch {
    parks.value = []
  }
}

/* ---------------- 仓库新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增仓库')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<WarehousePayload>({
  code: '',
  name: '',
  enterprise_id: null,
  park_id: null,
  address: '',
  warehouse_type: 'own',
  contact_name: '',
  contact_phone: '',
  status: 'active'
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }]
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增仓库'
  Object.assign(form, {
    code: '',
    name: '',
    enterprise_id: null,
    park_id: null,
    address: '',
    warehouse_type: 'own',
    contact_name: '',
    contact_phone: '',
    status: 'active'
  })
  dialogVisible.value = true
}

function openEdit(row: Warehouse): void {
  editingId.value = row.id
  dialogTitle.value = `编辑仓库：${row.name}`
  Object.assign(form, {
    code: row.code,
    name: row.name,
    enterprise_id: row.enterprise_id,
    park_id: row.park_id ?? null,
    address: row.address || '',
    warehouse_type: row.warehouse_type,
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    status: row.status
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
        await createWarehouse({ ...form })
        ElMessage.success('仓库创建成功')
      } else {
        await updateWarehouse(editingId.value, { ...form })
        ElMessage.success('仓库已更新')
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

async function handleDelete(row: Warehouse): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除仓库「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteWarehouse(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 库位管理 ---------------- */
const locationVisible = ref(false)
const locationLoading = ref(false)
const locations = ref<StorageLocation[]>([])
const currentWarehouse = ref<Warehouse | null>(null)

const locationDialogVisible = ref(false)
const locationDialogTitle = ref('新增库位')
const locationSubmitting = ref(false)
const locationFormRef = ref<FormInstance>()
const editingLocationId = ref<number | null>(null)
const locationForm = reactive<StorageLocationPayload>({
  code: '',
  name: '',
  zone: '',
  capacity: '',
  status: 'active'
})

const locationRules: FormRules = {
  code: [{ required: true, message: '请输入库位编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入库位名称', trigger: 'blur' }]
}

async function openLocations(row: Warehouse): Promise<void> {
  currentWarehouse.value = row
  locationVisible.value = true
  locationLoading.value = true
  try {
    locations.value = await listLocations(row.id)
  } catch {
    locations.value = []
  } finally {
    locationLoading.value = false
  }
}

async function reloadLocations(): Promise<void> {
  if (!currentWarehouse.value) return
  locationLoading.value = true
  try {
    locations.value = await listLocations(currentWarehouse.value.id)
  } catch {
    locations.value = []
  } finally {
    locationLoading.value = false
  }
}

function openLocationCreate(): void {
  editingLocationId.value = null
  locationDialogTitle.value = '新增库位'
  Object.assign(locationForm, { code: '', name: '', zone: '', capacity: '', status: 'active' })
  locationDialogVisible.value = true
}

function openLocationEdit(row: StorageLocation): void {
  editingLocationId.value = row.id
  locationDialogTitle.value = `编辑库位：${row.name}`
  Object.assign(locationForm, {
    code: row.code,
    name: row.name,
    zone: row.zone || '',
    capacity: row.capacity || '',
    status: row.status
  })
  locationDialogVisible.value = true
}

async function submitLocation(): Promise<void> {
  const el = locationFormRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    if (!currentWarehouse.value) return
    locationSubmitting.value = true
    try {
      if (editingLocationId.value === null) {
        await createLocation(currentWarehouse.value.id, { ...locationForm })
        ElMessage.success('库位创建成功')
      } else {
        await updateLocation(editingLocationId.value, { ...locationForm })
        ElMessage.success('库位已更新')
      }
      locationDialogVisible.value = false
      await reloadLocations()
      loadList()
    } catch {
      /* 已提示 */
    } finally {
      locationSubmitting.value = false
    }
  })
}

async function handleLocationDelete(row: StorageLocation): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除库位「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteLocation(row.id)
    ElMessage.success('删除成功')
    await reloadLocations()
    loadList()
  } catch {
    /* 已提示 */
  }
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
                placeholder="仓库名称 / 编码"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="所属企业">
              <el-select
                v-model="query.enterprise_id"
                placeholder="全部企业"
                clearable
                filterable
                style="width: 200px"
              >
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="仓库类型">
              <DictSelect v-model="query.warehouse_type" group="warehouseType" with-all placeholder="全部类型" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'inventory:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>新增仓库</span>
        </el-button>
      </template>

      <el-table-column prop="code" label="仓库编码" width="130" />
      <el-table-column prop="name" label="仓库名称" min-width="180" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <StatusTag group="warehouseType" :value="row.warehouse_type" />
        </template>
      </el-table-column>
      <el-table-column prop="enterprise_name" label="所属企业" min-width="180" show-overflow-tooltip />
      <el-table-column prop="park_name" label="所属园区" min-width="140" />
      <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column prop="contact_name" label="联系人" width="100" />
      <el-table-column prop="contact_phone" label="联系电话" width="130" />
      <el-table-column label="库位数" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.location_count ?? 0 }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <StatusTag group="commonStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openLocations(row as Warehouse)">库位管理</el-button>
          <el-button v-permission="'inventory:write'" link type="primary" @click="openEdit(row as Warehouse)">编辑</el-button>
          <el-button v-permission="'inventory:write'" link type="danger" @click="handleDelete(row as Warehouse)">删除</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 仓库弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="仓库编码" prop="code">
              <el-input v-model="form.code" placeholder="如 WH-BT-01" :disabled="editingId !== null" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓库名称" prop="name">
              <el-input v-model="form.name" placeholder="如 北屯中心仓" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓库类型">
              <DictSelect v-model="form.warehouse_type" group="warehouseType" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属企业">
              <el-select v-model="form.enterprise_id" placeholder="默认当前用户企业" clearable filterable style="width: 100%">
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属园区">
              <el-select v-model="form.park_id" placeholder="请选择园区" clearable style="width: 100%">
                <el-option v-for="item in parks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <DictSelect v-model="form.status" group="commonStatus" :clearable="false" style="width: 100%" />
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
          <el-col :span="24">
            <el-form-item label="仓库地址">
              <el-input v-model="form.address" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 库位抽屉 -->
    <el-drawer
      v-model="locationVisible"
      :title="`库位管理：${currentWarehouse?.name || ''}`"
      size="640px"
    >
      <div class="flex-between mb-12">
        <span class="text-sub">共 {{ locations.length }} 个库位</span>
        <el-button v-permission="'inventory:write'" type="primary" size="small" @click="openLocationCreate">
          <el-icon><Plus /></el-icon>
          <span>新增库位</span>
        </el-button>
      </div>

      <el-table v-loading="locationLoading" :data="locations" border stripe>
        <el-table-column prop="code" label="库位编码" width="130" />
        <el-table-column prop="name" label="库位名称" min-width="130" />
        <el-table-column prop="zone" label="区域" width="110" />
        <el-table-column prop="capacity" label="容量" width="110" align="right" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusTag group="commonStatus" :value="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="'inventory:write'" link type="primary" @click="openLocationEdit(row as StorageLocation)">
              编辑
            </el-button>
            <el-button v-permission="'inventory:write'" link type="danger" @click="handleLocationDelete(row as StorageLocation)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 库位弹窗 -->
    <el-dialog v-model="locationDialogVisible" :title="locationDialogTitle" width="480px" append-to-body>
      <el-form ref="locationFormRef" :model="locationForm" :rules="locationRules" label-width="100px">
        <el-form-item label="库位编码" prop="code">
          <el-input v-model="locationForm.code" placeholder="如 A-01-01" :disabled="editingLocationId !== null" />
        </el-form-item>
        <el-form-item label="库位名称" prop="name">
          <el-input v-model="locationForm.name" />
        </el-form-item>
        <el-form-item label="所属区域">
          <el-input v-model="locationForm.zone" placeholder="如 A 区" />
        </el-form-item>
        <el-form-item label="容量">
          <el-input v-model="locationForm.capacity" placeholder="如 500" />
        </el-form-item>
        <el-form-item label="状态">
          <DictSelect v-model="locationForm.status" group="commonStatus" :clearable="false" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="locationDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="locationSubmitting" @click="submitLocation">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
