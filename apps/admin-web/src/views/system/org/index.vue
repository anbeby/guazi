<script setup lang="ts">
/**
 * 组织架构：平台 → 园区 → 企业（GET /org-units/tree，POST/PUT/DELETE /org-units）。
 * 左侧树 + 右侧明细表格。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import DictSelect from '@/components/DictSelect.vue'
import StatusTag from '@/components/StatusTag.vue'
import { createOrgUnit, deleteOrgUnit, getOrgTree, updateOrgUnit } from '@/api/org'
import { listParks } from '@/api/park'
import type { OrgUnit, OrgUnitPayload, Park } from '@/api/types'
import { useDictStore } from '@/stores/dict'

const dictStore = useDictStore()

const loading = ref(false)
const tree = ref<OrgUnit[]>([])
const parks = ref<Park[]>([])
const keyword = ref('')
const selectedId = ref<number | null>(null)

const treeProps = { label: 'name', children: 'children' }

async function loadTree(): Promise<void> {
  loading.value = true
  try {
    tree.value = await getOrgTree(keyword.value ? { keyword: keyword.value } : undefined)
  } catch {
    tree.value = []
  } finally {
    loading.value = false
  }
}

async function loadParks(): Promise<void> {
  try {
    const data = await listParks({ page: 1, page_size: 200 })
    parks.value = data.items || []
  } catch {
    parks.value = []
  }
}

/** 扁平化便于右侧表格展示 */
function flatten(nodes: OrgUnit[], depth = 0, parentName = ''): (OrgUnit & { depth: number; parent_name: string })[] {
  const rows: (OrgUnit & { depth: number; parent_name: string })[] = []
  nodes.forEach((node) => {
    rows.push({ ...node, depth, parent_name: parentName })
    if (node.children?.length) {
      rows.push(...flatten(node.children, depth + 1, node.name))
    }
  })
  return rows
}

const flatRows = computed(() => flatten(tree.value))

const selectedNode = computed<OrgUnit | null>(() => {
  if (selectedId.value === null) return null
  const found = flatRows.value.find((item) => item.id === selectedId.value)
  return found || null
})

function handleNodeClick(node: OrgUnit): void {
  selectedId.value = node.id
}

/* ---------------- 新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增组织单元')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<OrgUnitPayload>({
  code: '',
  name: '',
  unit_type: 'enterprise',
  parent_id: null,
  park_id: null,
  region: '',
  address: '',
  contact_name: '',
  contact_phone: '',
  status: 'active',
  sort: 0
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入组织编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入组织名称', trigger: 'blur' }],
  unit_type: [{ required: true, message: '请选择组织类型', trigger: 'change' }]
}

function resetForm(): void {
  Object.assign(form, {
    code: '',
    name: '',
    unit_type: 'enterprise',
    parent_id: null,
    park_id: null,
    region: '',
    address: '',
    contact_name: '',
    contact_phone: '',
    status: 'active',
    sort: 0
  })
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增组织单元'
  resetForm()
  form.parent_id = selectedNode.value?.id ?? null
  if (selectedNode.value?.park_id) form.park_id = selectedNode.value.park_id
  dialogVisible.value = true
}

function openCreateChild(node: OrgUnit): void {
  openCreate()
  form.parent_id = node.id
  if (node.park_id) form.park_id = node.park_id
}

function openEdit(node: OrgUnit): void {
  editingId.value = node.id
  dialogTitle.value = `编辑：${node.name}`
  Object.assign(form, {
    code: node.code,
    name: node.name,
    unit_type: node.unit_type,
    parent_id: node.parent_id ?? null,
    park_id: node.park_id ?? null,
    region: node.region || '',
    address: node.address || '',
    contact_name: node.contact_name || '',
    contact_phone: node.contact_phone || '',
    status: node.status,
    sort: node.sort ?? 0
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
        await createOrgUnit({ ...form })
        ElMessage.success('组织单元创建成功')
      } else {
        await updateOrgUnit(editingId.value, { ...form })
        ElMessage.success('组织单元已更新')
      }
      dialogVisible.value = false
      await loadTree()
    } catch {
      /* 已提示 */
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(node: OrgUnit): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除组织单元「${node.name}」？若存在下级组织或关联企业将无法删除。`,
      '危险操作',
      { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteOrgUnit(node.id)
    ElMessage.success('删除成功')
    if (selectedId.value === node.id) selectedId.value = null
    await loadTree()
  } catch {
    /* 已提示 */
  }
}

onMounted(async () => {
  await Promise.all([loadTree(), loadParks()])
})
</script>

<template>
  <div class="page-container">
    <el-row :gutter="12">
      <el-col :xs="24" :md="7">
        <div class="page-card org-tree">
          <div class="flex-between mb-12">
            <span class="org-tree__title">组织架构</span>
            <el-button v-permission="'org:write'" size="small" type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon>
              <span>新增</span>
            </el-button>
          </div>

          <el-input
            v-model="keyword"
            placeholder="按名称搜索"
            clearable
            class="mb-12"
            @keyup.enter="loadTree"
            @clear="loadTree"
          >
            <template #append>
              <el-button @click="loadTree">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>

          <el-tree
            v-loading="loading"
            :data="tree"
            :props="treeProps"
            node-key="id"
            default-expand-all
            highlight-current
            :expand-on-click-node="false"
            @node-click="handleNodeClick"
          >
            <template #default="{ data }">
              <div class="org-node">
                <el-tag size="small" :type="dictStore.tagType('orgUnitType', data.unit_type)" effect="plain">
                  {{ dictStore.label('orgUnitType', data.unit_type) }}
                </el-tag>
                <span class="org-node__name">{{ data.name }}</span>
                <span class="org-node__code text-sub">{{ data.code }}</span>
                <span class="org-node__actions">
                  <el-icon v-permission="'org:write'" title="新增下级" @click.stop="openCreateChild(data)">
                    <Plus />
                  </el-icon>
                  <el-icon v-permission="'org:write'" title="编辑" @click.stop="openEdit(data)">
                    <Edit />
                  </el-icon>
                  <el-icon v-permission="'org:write'" title="删除" @click.stop="handleDelete(data)">
                    <Delete />
                  </el-icon>
                </span>
              </div>
            </template>
          </el-tree>
        </div>
      </el-col>

      <el-col :xs="24" :md="17">
        <div class="page-card">
          <div class="page-title">
            <span>
              组织单元明细
              <span class="page-title__sub">共 {{ flatRows.length }} 个节点</span>
            </span>
            <el-button size="small" @click="loadTree">
              <el-icon><Refresh /></el-icon>
              <span>刷新</span>
            </el-button>
          </div>

          <el-table :data="flatRows" border stripe row-key="id" default-expand-all>
            <el-table-column prop="name" label="组织名称" min-width="200">
              <template #default="{ row }">
                <span :style="{ paddingLeft: `${row.depth * 16}px` }">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="code" label="编码" min-width="130" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <StatusTag group="orgUnitType" :value="row.unit_type" />
              </template>
            </el-table-column>
            <el-table-column prop="parent_name" label="上级组织" min-width="150" />
            <el-table-column prop="region" label="行政区划" min-width="130" />
            <el-table-column prop="contact_name" label="联系人" width="100" />
            <el-table-column prop="contact_phone" label="联系电话" width="130" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <StatusTag group="commonStatus" :value="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button v-permission="'org:write'" link type="primary" @click="openEdit(row as OrgUnit)">编辑</el-button>
                <el-button v-permission="'org:write'" link type="danger" @click="handleDelete(row as OrgUnit)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="组织编码" prop="code">
              <el-input v-model="form.code" placeholder="如 PARK-BT01 / ENT-0001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入组织名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织类型" prop="unit_type">
              <DictSelect v-model="form.unit_type" group="orgUnitType" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="上级组织">
              <el-tree-select
                v-model="form.parent_id"
                :data="tree"
                :props="treeProps"
                node-key="id"
                check-strictly
                clearable
                placeholder="顶级组织留空"
                style="width: 100%"
              />
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
            <el-form-item label="行政区划">
              <el-input v-model="form.region" placeholder="如 新疆·北屯市" />
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
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :max="9999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="地址">
              <el-input v-model="form.address" placeholder="详细地址" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.org-tree {
  min-height: 520px;
}

.org-tree__title {
  font-size: 15px;
  font-weight: 600;
}

.org-node {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding-right: 8px;
}

.org-node__name {
  flex-shrink: 0;
}

.org-node__code {
  font-size: 12px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.org-node__actions {
  display: none;
  gap: 6px;
  color: var(--gz-primary);
  cursor: pointer;
}

.org-node:hover .org-node__actions {
  display: inline-flex;
}
</style>
