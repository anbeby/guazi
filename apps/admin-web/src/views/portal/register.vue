<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '@/api/request'
import { useUserStore } from '@/stores/user'
import type { UserProfile } from '@/api/types'
import './portal.css'

const router = useRouter()
const userStore = useUserStore()
const submitting = ref(false)
const error = ref('')
const form = ref({ username: '', phone: '', full_name: '', password: '', confirm: '' })

async function submit(): Promise<void> {
  error.value = ''
  if (form.value.password !== form.value.confirm) { error.value = '两次输入的密码不一致'; return }
  submitting.value = true
  try {
    const result = await http.post<{ access_token: string; refresh_token: string; expires_in: number; user: UserProfile }>('/auth/register', {
      username: form.value.username.trim(), phone: form.value.phone.trim() || null,
      full_name: form.value.full_name.trim() || null, password: form.value.password
    })
    userStore.setSession(result)
    await userStore.fetchUserInfo()
    router.replace('/account')
  } catch (cause) { error.value = cause instanceof Error ? cause.message : '注册失败' }
  finally { submitting.value = false }
}
</script>

<template>
  <div class="open-portal">
    <header class="open-portal__header"><a class="open-portal__brand" href="/home"><img src="/static/images/logo/platform-mark.svg" alt="" />第十师瓜子油料数字化交易平台</a><nav class="open-portal__nav"><a href="/supply">供应大厅</a><a href="/procurement">采购大厅</a><a href="/consult">游客留下需求</a><a href="/login?redirect=/account">登录</a></nav></header>
    <main class="open-portal__main" style="max-width:680px"><span class="open-portal__eyebrow">注册运营 · 保留开放浏览</span><h1>注册普通用户</h1><p class="open-portal__intro">注册后管理自己的咨询、收藏供应信息；申请并通过企业认证后可发布供应与采购需求。浏览和游客咨询无需注册。</p>
      <form class="open-portal__card" @submit.prevent="submit"><div class="open-portal__grid">
        <label class="open-portal__field">用户名或手机号<input v-model.trim="form.username" required minlength="3" maxlength="64" autocomplete="username" placeholder="用于登录" /></label>
        <label class="open-portal__field">手机号（可选）<input v-model.trim="form.phone" inputmode="tel" maxlength="11" autocomplete="tel" placeholder="若用户名已是手机号可不填" /></label>
        <label class="open-portal__field">姓名（可选）<input v-model.trim="form.full_name" maxlength="64" autocomplete="name" /></label>
        <span></span>
        <label class="open-portal__field">密码<input v-model="form.password" required minlength="8" maxlength="128" type="password" autocomplete="new-password" /></label>
        <label class="open-portal__field">确认密码<input v-model="form.confirm" required type="password" autocomplete="new-password" /></label>
      </div><p v-if="error" role="alert" style="color:#b73720">{{ error }}</p><div class="open-portal__actions"><button class="open-portal__button" :disabled="submitting">{{ submitting ? '注册中…' : '创建账号' }}</button><a href="/consult">先不注册，直接留下需求 →</a></div></form>
    </main><footer class="open-portal__footer">© 2026 第十师瓜子油料数字化交易平台　技术支持：屯云大数据</footer>
  </div>
</template>
