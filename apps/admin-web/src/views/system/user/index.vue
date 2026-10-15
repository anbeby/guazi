<script setup lang="ts">
/**
 * 用户管理：分页查询 / 新增 / 编辑 / 删除 / 分配角色 / 重置密码 / 禁用启用。
 * 接口：/users、/users/{id}/roles、/users/{id}/reset-password、/roles、/enterprises、/org-units/tree
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import PageTable from '@/components/PageTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DictSelect from '@/components/DictSelect.vue'
import {
  assignUserRoles,
  createUser,
  deleteUser,
  listUsers,
  resetUserPassword,
  updateUser
} from '@/api/user'
import { listRoles } from '@/api/role'
import { listEnterprises } from '@/api/enterprise'
import { getOrgTree } from '@/api/org'
import type { Enterprise, OrgUnit, Role, SysUser, UserPayload, UserQuery } from '@/api/types'
import { formatDateTime } from '@/utils/format'

/* ---------------- 列表 ---------------- */
const loading = ref(false)
const list = ref<SysUser[]>([])
const total = ref(0)
const query = reactive<UserQuery>({ page: 1, page_size: 20, keyword: '', status: '' })
const enterprises = ref<Enterprise[]>([])
const roles = ref<Role[]>([])
const orgTree = ref<OrgUnit[]>([])

async function loadList(): Promise<void> {
  loading.value = true
  try {
    const data = await listUsers(query)
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
  query.enterprise_id = undefined
  query.org_id = undefined
  query.page = 1
  loadList()
}

async function loadOptions(): Promise<void> {
  try {
    const rolePage = await listRoles({ page: 1, page_size: 200 })
    roles.value = rolePage.items || []
  } catch {
    roles.value = []
  }
  try {
    const entPage = await listEnterprises({ page: 1, page_size: 200 })
    enterprises.value = entPage.items || []
  } catch {
    enterprises.value = []
  }
  try {
    orgTree.value = await getOrgTree()
  } catch {
    orgTree.value = []
  }
}

/* ---------------- 新增 / 编辑 ---------------- */
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const form = reactive<UserPayload & { role_ids: number[] }>({
  username: '',
  password: '',
  full_name: '',
  phone: '',
  email: '',
  org_id: null,
  enterprise_id: null,
  status: 'active',
  role_ids: []
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 3, max: 64, message: '账号长度 3 - 64 位', trigger: 'blur' }
  ],
  password: [{ min: 8, message: '密码长度不少于 8 位', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }]
}

function openCreate(): void {
  editingId.value = null
  dialogTitle.value = '新增用户'
  Object.assign(form, {
    username: '',
    password: '',
    full_name: '',
    phone: '',
    email: '',
    org_id: null,
    enterprise_id: null,
    status: 'active',
    role_ids: []
  })
  dialogVisible.value = true
}

function openEdit(row: SysUser): void {
  editingId.value = row.id
  dialogTitle.value = `编辑用户：${row.username}`
  Object.assign(form, {
    username: row.username,
    password: '',
    full_name: row.full_name || '',
    phone: row.phone || '',
    email: row.email || '',
    org_id: row.org_id ?? null,
    enterprise_id: row.enterprise_id ?? null,
    status: row.status,
    role_ids: row.role_ids ? [...row.role_ids] : []
  })
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const el = formRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    if (editingId.value === null && !form.password) {
      ElMessage.warning('请为新用户设置初始密码')
      return
    }
    submitting.value = true
    try {
      if (editingId.value === null) {
        const created = await createUser({ ...form })
        if (form.role_ids.length > 0 && created?.id) {
          await assignUserRoles(created.id, { role_ids: form.role_ids })
        }
        ElMessage.success('用户创建成功')
      } else {
        await updateUser(editingId.value, {
          full_name: form.full_name,
          phone: form.phone,
          email: form.email,
          org_id: form.org_id,
          enterprise_id: form.enterprise_id,
          status: form.status
        })
        await assignUserRoles(editingId.value, { role_ids: form.role_ids })
        ElMessage.success('用户信息已更新')
      }
      dialogVisible.value = false
      loadList()
    } catch {
      // 错误提示由 axios 拦截器统一处理
    } finally {
      submitting.value = false
    }
  })
}

/* ---------------- 分配角色 ---------------- */
const roleDialogVisible = ref(false)
const roleForm = reactive<{ id: number | null; username: string; role_ids: number[] }>({
  id: null,
  username: '',
  role_ids: []
})

function openAssignRole(row: SysUser): void {
  roleForm.id = row.id
  roleForm.username = row.username
  roleForm.role_ids = row.role_ids ? [...row.role_ids] : []
  roleDialogVisible.value = true
}

async function submitAssignRole(): Promise<void> {
  if (roleForm.id === null) return
  try {
    await assignUserRoles(roleForm.id, { role_ids: roleForm.role_ids })
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    loadList()
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 重置密码 ---------------- */
const pwdDialogVisible = ref(false)
const pwdForm = reactive<{ id: number | null; username: string; new_password: string }>({
  id: null,
  username: '',
  new_password: ''
})

function openResetPassword(row: SysUser): void {
  pwdForm.id = row.id
  pwdForm.username = row.username
  pwdForm.new_password = ''
  pwdDialogVisible.value = true
}

async function submitResetPassword(): Promise<void> {
  if (pwdForm.id === null) return
  if (pwdForm.new_password.length < 8) {
    ElMessage.warning('新密码长度不少于 8 位')
    return
  }
  try {
    await resetUserPassword(pwdForm.id, { new_password: pwdForm.new_password })
    ElMessage.success('密码重置成功')
    pwdDialogVisible.value = false
  } catch {
    /* 已提示 */
  }
}

/* ---------------- 禁用 / 启用 / 删除 ---------------- */
async function toggleStatus(row: SysUser): Promise<void> {
  const nextStatus = row.status === 'active' ? 'disabled' : 'active'
  const actionText = nextStatus === 'disabled' ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${actionText}用户「${row.username}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await updateUser(row.id, { status: nextStatus })
    ElMessage.success(`已${actionText}`)
    loadList()
  } catch {
    /* 已提示 */
  }
}

async function handleDelete(row: SysUser): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.username}」？删除后不可恢复。`, '危险操作', {
      type: 'error',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await deleteUser(row.id)
    ElMessage.success('删除成功')
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
                placeholder="账号 / 姓名 / 手机号"
                clearable
                style="width: 200px"
                @keyup.enter="handleSearch"
              />
            </el-form-item>
            <el-form-item label="状态">
              <DictSelect v-model="query.status" group="userStatus" with-all placeholder="全部状态" />
            </el-form-item>
            <el-form-item label="所属企业">
              <el-select
                v-model="query.enterprise_id"
                placeholder="全部企业"
                clearable
                filterable
                style="width: 200px"
              >
                <el-option
                  v-for="item in enterprises"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </template>

      <template #toolbar>
        <el-button v-permission="'user:write'" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          <span>新增用户</span>
        </el-button>
      </template>

      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="登录账号" min-width="130" />
      <el-table-column prop="full_name" label="姓名" min-width="100" />
      <el-table-column prop="phone" label="手机号" min-width="120" />
      <el-table-column label="所属企业" min-width="180">
        <template #default="{ row }">
          {{ row.enterprise_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="角色" min-width="160">
        <template #default="{ row }">
          <el-tag v-for="code in row.roles || []" :key="code" size="small" type="info" class="mr-4">
            {{ code }}
          </el-tag>
          <span v-if="!row.roles || row.roles.length === 0" class="text-sub">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <StatusTag group="userStatus" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="最近登录" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'user:write'" link type="primary" @click="openEdit(row as SysUser)">编辑</el-button>
          <el-button v-permission="'user:write'" link type="primary" @click="openAssignRole(row as SysUser)">
            分配角色
          </el-button>
          <el-button v-permission="'user:write'" link type="warning" @click="openResetPassword(row as SysUser)">
            重置密码
          </el-button>
          <el-button v-permission="'user:write'" link type="info" @click="toggleStatus(row as SysUser)">
            {{ row.status === 'active' ? '禁用' : '启用' }}
          </el-button>
          <el-button v-permission="'user:write'" link type="danger" @click="handleDelete(row as SysUser)">删除</el-button>
        </template>
      </el-table-column>
    </PageTable>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="620px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="登录账号" prop="username">
              <el-input v-model="form.username" :disabled="editingId !== null" placeholder="请输入账号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item v-if="editingId === null" label="初始密码" prop="password">
              <el-input v-model="form.password" type="password" show-password placeholder="不少于 8 位" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="full_name">
              <el-input v-model="form.full_name" placeholder="请输入姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="form.phone" placeholder="请输入手机号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" placeholder="请输入邮箱" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <DictSelect v-model="form.status" group="userStatus" :clearable="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属企业">
              <el-select v-model="form.enterprise_id" placeholder="请选择企业" clearable filterable style="width: 100%">
                <el-option v-for="item in enterprises" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属组织">
              <el-tree-select
                v-model="form.org_id"
                :data="orgTree"
                node-key="id"
                :props="{ label: 'name', children: 'children' }"
                check-strictly
                clearable
                placeholder="请选择组织"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="角色">
              <el-select v-model="form.role_ids" multiple placeholder="请选择角色" style="width: 100%">
                <el-option v-for="item in roles" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分配角色 -->
    <el-dialog v-model="roleDialogVisible" :title="`分配角色：${roleForm.username}`" width="480px" append-to-body>
      <el-select v-model="roleForm.role_ids" multiple placeholder="请选择角色" style="width: 100%">
        <el-option v-for="item in roles" :key="item.id" :label="`${item.name}（${item.code}）`" :value="item.id" />
      </el-select>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAssignRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="pwdDialogVisible" :title="`重置密码：${pwdForm.username}`" width="440px" append-to-body>
      <el-form label-width="90px">
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="不少于 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResetPassword">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mr-4 {
  margin-right: 4px;
}
</style>
