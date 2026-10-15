<script setup lang="ts">
/**
 * 顶栏：折叠按钮、面包屑入口、待办提醒、主题切换、用户下拉（个人信息 / 修改密码 / 退出）。
 */
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { getOverview } from '@/api/dashboard'
import type { DashboardOverview } from '@/api/types'

const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

const overview = ref<DashboardOverview | null>(null)

const todoCount = computed(() => {
  if (!overview.value) return 0
  return (overview.value.pending_audit_enterprise || 0) + (overview.value.pending_audit_product || 0)
})

async function loadTodo(): Promise<void> {
  if (!userStore.hasPermission('data:read')) return
  try {
    overview.value = await getOverview()
  } catch {
    overview.value = null
  }
}
loadTodo()

/* ---------------- 修改密码 ---------------- */
const pwdVisible = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码长度不少于 8 位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback: (error?: Error) => void) => {
        if (value !== pwdForm.new_password) callback(new Error('两次输入的新密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

function openChangePassword(): void {
  pwdForm.old_password = ''
  pwdForm.new_password = ''
  pwdForm.confirm_password = ''
  pwdVisible.value = true
}

async function submitChangePassword(): Promise<void> {
  const form = pwdFormRef.value
  if (!form) return
  await form.validate(async (valid) => {
    if (!valid) return
    try {
      await userStore.changePassword(pwdForm.old_password, pwdForm.new_password)
      ElMessage.success('密码修改成功，请重新登录')
      pwdVisible.value = false
      await userStore.logout()
      router.push('/login')
    } catch {
      // 错误提示已由 axios 拦截器统一处理
    }
  })
}

/* ---------------- 退出登录 ---------------- */
async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm('确认退出当前登录账号？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  await userStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

async function handleCommand(command: string): Promise<void> {
  if (command === 'profile') {
    router.push('/dashboard')
    return
  }
  if (command === 'password') {
    openChangePassword()
    return
  }
  if (command === 'about') {
    router.push('/system/about')
    return
  }
  if (command === 'logout') {
    await handleLogout()
  }
}
</script>

<template>
  <div class="navbar">
    <div class="navbar__left">
      <el-icon class="navbar__toggle" @click="appStore.toggleSidebar()">
        <component :is="appStore.sidebarCollapsed ? 'Expand' : 'Fold'" />
      </el-icon>
      <span class="navbar__system">
        {{ userStore.enterpriseName || '第十师北屯市 · 瓜子油料产业互联网平台' }}
      </span>
    </div>

    <div class="navbar__right">
      <el-tooltip content="待处理：企业审核 + 商品审核" placement="bottom">
        <el-badge :value="todoCount" :hidden="todoCount === 0" class="navbar__badge">
          <el-icon class="navbar__icon" @click="router.push('/merchant/entry')">
            <Bell />
          </el-icon>
        </el-badge>
      </el-tooltip>

      <el-tooltip :content="appStore.theme === 'light' ? '切换深色' : '切换浅色'" placement="bottom">
        <el-icon class="navbar__icon" @click="appStore.toggleTheme()">
          <component :is="appStore.theme === 'light' ? 'Moon' : 'Sunny'" />
        </el-icon>
      </el-tooltip>

      <el-dropdown trigger="click" @command="handleCommand">
        <div class="navbar__user">
          <el-avatar :size="28" class="navbar__avatar">
            {{ userStore.displayName.slice(0, 1) }}
          </el-avatar>
          <span class="navbar__user-name">{{ userStore.displayName }}</span>
          <el-tag v-if="userStore.roles.length" size="small" type="success" effect="plain">
            {{ userStore.roles[0] }}
          </el-tag>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">工作台</el-dropdown-item>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item command="about">关于系统</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-dialog v-model="pwdVisible" title="修改密码" width="440px" append-to-body>
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="不少于 8 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="pwdForm.confirm_password"
            type="password"
            show-password
            placeholder="请再次输入新密码"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" @click="submitChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 16px;
}

.navbar__left,
.navbar__right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.navbar__toggle {
  font-size: 18px;
  cursor: pointer;
  color: #4b5563;
}

.navbar__system {
  font-size: 14px;
  color: var(--gz-text-sub);
}

.navbar__icon {
  font-size: 18px;
  cursor: pointer;
  color: #4b5563;
}

.navbar__badge {
  margin-top: 4px;
}

.navbar__user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}

.navbar__user:hover {
  background: #f4f6f8;
}

.navbar__avatar {
  background: var(--gz-primary);
  color: #fff;
  font-size: 13px;
}

.navbar__user-name {
  font-size: 14px;
}

@media (max-width: 650px) {
  .navbar { padding: 0 10px; }
  .navbar__left, .navbar__right { gap: 10px; }
  .navbar__system, .navbar__user-name, .navbar__user .el-tag { display: none; }
  .navbar__user { gap: 4px; padding: 3px; }
}
</style>
