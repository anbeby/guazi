<script setup lang="ts">
/**
 * 角色管理：角色 CRUD + 权限树勾选（GET /permissions 按模块分组渲染，PUT /roles/{id}/permissions 保存）。
 */
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import { createRole, deleteRole, getRolePermissions, listPermissions, listRoles, updateRole, updateRolePermissions } from '@/api/role'
import type { Permission, PermissionGroup, Role, RolePayload, RoleQuery } from '@/api/types'
import { formatDateTime } from '@/utils/format'

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<Role[]>([])
const total = ref(0)
const query = reactive<RoleQuery>({ page: 1, page_size: 20, keyword: '' })

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listRoles(query)
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
  query.page = 1
  loadList()
}

/* ---------------- 新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<RolePayload>({ code: '', name: '', description: '' })

const rules: FormRules = {
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    { pattern: /^[a-z][a-z0-9_]{1,31}$/, message: '编码为小写字母/数字/下划线，如 park_operator', trigger: 'blur' }
  ],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增角色'
  Object.assign(form, { code: '', name: '', description: '' })
  dialogVisible.value = true
}

function openEdit(row: Role): void {
  editingId.value = row.id
  dialogTitle.value = `编辑角色：${row.name}`
  Object.assign(form, {
    code: row.code,
    name: row.name,
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
        await createRole({ ...form })
        ElMessage.success('角色创建成功')
      } else {
        await updateRole(editingId.value, { name: form.name, description: form.description })
        ElMessage.success('角色已更新')
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

async function handleDelete(row: Role): Promise<void> {
  if (row.is_system) {
    ElMessage.warning('系统内置角色不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 权限树 ---------------- */
const permissionVisible = ref(false)
const permissionLoading = ref(false)
const permissionSaving = ref(false)
const permissionGroups = ref<PermissionGroup[]>([])
const currentRole = ref<Role | null>(null)
/** el-tree 实例（仅使用 setCheckedKeys / getCheckedKeys） */
interface TreeInstance {
  setCheckedKeys: (keys: (string | number)[], leafOnly?: boolean) => void
  getCheckedKeys: (leafOnly?: boolean) => (string | number)[]
}

const treeRef = ref<TreeInstance>()

/** 权限树节点：模块为父节点，权限码为子节点 */
interface PermissionNode {
  id: number | string
  label: string
  isModule: boolean
  children?: PermissionNode[]
}

const MODULE_LABELS: Record<string, string> = {
  user: '用户管理',
  role: '角色权限',
  org: '组织架构',
  merchant: '商户管理',
  product: '商品中心',
  inventory: '仓储库存',
  trade: '交易服务',
  settlement: '结算财务',
  trace: '质量溯源',
  park: '智慧园区',
  data: '数据驾驶舱',
  integration: '系统集成'
}

const permissionTree = computed<PermissionNode[]>(() =>
  permissionGroups.value.map((group, index) => ({
    id: `module-${group.module || index}`,
    label: `${MODULE_LABELS[group.module] || group.module_name || group.module}（${group.permissions.length}）`,
    isModule: true,
    children: group.permissions.map((item) => ({
      id: item.id,
      label: `${item.name}（${item.code}）`,
      isModule: false
    }))
  }))
)

const permissionCount = computed(() =>
  permissionGroups.value.reduce((sum, group) => sum + group.permissions.length, 0)
)

async function ensurePermissionGroups(): Promise<void> {
  if (permissionGroups.value.length > 0) return
  try {
    const groups = await listPermissions()
    permissionGroups.value = (groups || []).filter((group) => (group.permissions || []).length > 0)
  } catch {
    permissionGroups.value = []
  }
}

async function openPermissions(row: Role): Promise<void> {
  currentRole.value = row
  permissionVisible.value = true
  permissionLoading.value = true
  await nextTick()
  try {
    await ensurePermissionGroups()
    await nextTick()
    const owned: Permission[] = await getRolePermissions(row.id)
    const ownedIds = new Set((owned || []).map((item) => item.id))
    const checkedKeys = permissionTree.value
      .flatMap((node) => node.children || [])
      .filter((child) => typeof child.id === 'number' && ownedIds.has(child.id as number))
      .map((child) => child.id)
    treeRef.value?.setCheckedKeys(checkedKeys, false)
    checkedLeafCount.value = checkedKeys.length
  } catch {
    treeRef.value?.setCheckedKeys([], false)
    checkedLeafCount.value = 0
  } finally {
    permissionLoading.value = false
  }
}

/** 保存权限：只提交叶子权限 id */
const checkedLeafCount = ref(0)

function syncCheckedCount(): void {
  const checked = (treeRef.value?.getCheckedKeys(false) || []) as (string | number)[]
  checkedLeafCount.value = checked.filter((key) => typeof key === 'number').length
}

async function submitPermissions(): Promise<void> {
  const role = currentRole.value
  if (!role) return
  const checked = (treeRef.value?.getCheckedKeys(false) || []) as (string | number)[]
  const permissionIds = checked.filter((key): key is number => typeof key === 'number')
  permissionSaving.value = true
  try {
    await updateRolePermissions(role.id, permissionIds)
    ElMessage.success(`权限已保存（${permissionIds.length} 项）`)
    permissionVisible.value = false
  } catch {
    /* 已提示 */
  } finally {
    permissionSaving.value = false
  }
}

onMounted(() => {
  loadList()
  ensurePermissionGroups()
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
                placeholder="角色名称 / 编码"
                clearable
                style="width: 220px"
                @keyup.enter="handleSearch"
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
        <el-button v-permission="'role:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>新增角色</span>
        </el-button>
      </template>

      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="code" label="角色编码" min-width="140" />
      <el-table-column prop="name" label="角色名称" min-width="140" />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_system ? 'warning' : 'info'" size="small">
            {{ row.is_system ? '系统内置' : '自定义' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'role:write'" link type="primary" @click="openPermissions(row as Role)">
            分配权限
          </el-button>
          <el-button v-permission="'role:write'" link type="primary" @click="openEdit(row as Role)">编辑</el-button>
          <el-button
            v-permission="'role:write'"
            link
            type="danger"
            :disabled="row.is_system"
            @click="handleDelete(row as Role)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="如 park_operator" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="如 园区运营人员" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="角色职责说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 权限树 -->
    <el-dialog
      v-model="permissionVisible"
      :title="`分配权限：${currentRole?.name || ''}`"
      width="640px"
      append-to-body
    >
      <div v-loading="permissionLoading" class="permission-box">
        <div class="permission-box__tip">
          共 {{ permissionCount }} 个权限码，已勾选 {{ checkedLeafCount }} 项；父级为模块分组，保存时仅提交叶子节点。
        </div>
        <el-tree
          ref="treeRef"
          :data="permissionTree"
          node-key="id"
          show-checkbox
          default-expand-all
          :props="{ label: 'label', children: 'children' }"
          @check="syncCheckedCount"
        />
      </div>
      <template #footer>
        <el-button @click="permissionVisible = false">取消</el-button>
        <el-button type="primary" :loading="permissionSaving" @click="submitPermissions">保存权限</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.permission-box {
  max-height: 460px;
  overflow: auto;
}

.permission-box__tip {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--gz-text-sub);
}
</style>
