<script setup lang="ts">
/**
 * 登录页：POST /auth/login，成功后拉取 /auth/me 并跳转 redirect 或首页。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '', remember: true })
const rememberKey = 'gz_admin_last_username'

const rules: FormRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 3, max: 64, message: '账号长度 3 - 64 位', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入登录密码', trigger: 'blur' },
    { min: 6, message: '密码长度不少于 6 位', trigger: 'blur' }
  ]
}

onMounted(() => {
  const cached = localStorage.getItem(rememberKey)
  if (cached) {
    form.username = cached
  }
})

async function handleLogin(): Promise<void> {
  const el = formRef.value
  if (!el) return
  await el.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.login({ username: form.username.trim(), password: form.password })
      if (form.remember) localStorage.setItem(rememberKey, form.username.trim())
      else localStorage.removeItem(rememberKey)

      // 确保用户信息（角色 / 权限）就绪，避免首屏菜单缺项
      if (!userStore.loaded) {
        await userStore.fetchUserInfo()
      }
      ElMessage.success('登录成功')
      const requested = route.query.redirect
      let redirect = userStore.hasPermission('data:read') ? '/dashboard' : '/account'
      if (typeof requested === 'string' && requested.startsWith('/') && !requested.startsWith('//')) {
        const resolved = router.resolve(requested)
        const permission = resolved.meta.permission as string | undefined
        const roles = resolved.meta.roles as string[] | undefined
        const permitted = (!permission || userStore.hasPermission(permission))
          && (!roles || userStore.isSuperuser || userStore.hasRole(roles))
        if (resolved.name && !['Login', 'NotFound', 'Forbidden'].includes(String(resolved.name)) && permitted) {
          redirect = requested
        }
      }
      router.replace(redirect)
    } catch {
      // 错误提示由 axios 拦截器统一处理（40100 用户名或密码错误 / 40101 账号被禁用）
    } finally {
      loading.value = false
    }
  })
}
</script>

<template>
  <div class="login">
    <div class="login__banner">
      <div class="login__banner-inner">
        <span class="login__eyebrow">第十师 · 北屯瓜子产业</span>
        <h1 class="login__title">第十师瓜子油料</h1>
        <h2 class="login__subtitle">数字化交易平台</h2>
        <p class="login__slogan">北屯瓜子 · 香飘全国</p>
        <ul class="login__features">
          <li>产业互联网交易平台 · 撮合 / 履约 / 结算</li>
          <li>智慧园区管理 · 园区 / 区域 / 档口 / 入驻</li>
          <li>商户经营管理 · 商品 / 库存 / 应收应付</li>
          <li>数据分析中心 · 产业驾驶舱 / 价格指数</li>
        </ul>
        <p class="login__foot">新疆·北屯市 ｜ 葵花籽 · 南瓜籽 · 打瓜籽</p>
        <router-link class="login__home-link" to="/home">← 返回平台首页</router-link>
      </div>
      <span class="login__image-note">产业场景示意图</span>
    </div>

    <div class="login__panel">
      <div class="login__card">
        <div class="login__brand">
          <img class="login__brand-mark" src="/static/images/logo/platform-mark.svg" alt="" />
          <div class="login__brand-copy">
            <strong>第十师瓜子油料数字化交易平台</strong>
            <span>产业交易 · 供应链协同 · 智慧运营</span>
          </div>
        </div>
        <div class="login__card-head">
          <h3>登录交易平台</h3>
          <p>注册用户可管理咨询记录；企业与运营人员进入各自工作台</p>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="handleLogin">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="登录账号" clearable>
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="登录密码" show-password>
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <div class="login__options">
            <el-checkbox v-model="form.remember">记住账号</el-checkbox>
          </div>

          <el-button type="primary" class="login__submit" :loading="loading" @click="handleLogin">
            登 录
          </el-button>
        </el-form>

        <p class="login__tip">还没有账号？<router-link to="/register">注册普通用户</router-link> · <router-link to="/consult">不注册，直接留下需求</router-link></p>

        <p class="login__tip">
          忘记密码请联系平台管理员重置（支持平台管理员在「用户管理」中重置密码）
        </p>
      </div>
      <p class="login__support">技术支持：屯云大数据</p>
    </div>
  </div>
</template>

<style scoped>
.login {
  display: flex;
  height: 100vh;
  min-height: 560px;
  background: #f4f6f8;
}

.login__banner {
  flex: 1.15;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #fff;
  background: linear-gradient(90deg, rgba(6, 53, 32, .96), rgba(7, 76, 42, .74) 57%, rgba(7, 76, 42, .18)), url('/demo/hero.png') 54% center / cover;
  position: relative;
  overflow: hidden;
}

.login__banner-inner {
  max-width: 520px;
  z-index: 1;
}
.login__eyebrow { color: #ffdc8b; font-size: 14px; font-weight: 700; letter-spacing: 3px; }

.login__title {
  margin: 0;
  font-size: 34px;
  letter-spacing: 4px;
}

.login__subtitle {
  margin: 6px 0 26px;
  font-size: 22px;
  font-weight: 400;
  letter-spacing: 6px;
  color: #ffd666;
}
.login__slogan { margin: 0 0 21px; font-size: 17px; letter-spacing: 4px; font-weight: 700; }

.login__features {
  margin: 0;
  padding-left: 18px;
  line-height: 2.1;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.86);
}

.login__foot {
  margin-top: 30px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.65);
}
.login__home-link { display: inline-block; margin-top: 16px; padding: 10px 15px; border: 1px solid #ffffffa8; border-radius: 7px; color: #fff; text-decoration: none; font-weight: 700; }
.login__image-note { position: absolute; right: 16px; bottom: 14px; color: #fff; opacity: .75; font-size: 11px; text-shadow: 0 1px 4px #143d29; }

.login__panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 32px;
  background:
    radial-gradient(circle at 78% 16%, rgba(166, 210, 178, .43), transparent 32%),
    radial-gradient(circle at 7% 86%, rgba(109, 176, 132, .18), transparent 42%),
    linear-gradient(138deg, #e7f1e9 0%, #eff5ef 48%, #dcebe2 100%);
}

.login__panel::before,
.login__panel::after {
  content: '';
  position: absolute;
  border: 1px solid rgba(28, 106, 66, .08);
  border-radius: 50%;
  pointer-events: none;
}
.login__panel::before { width: 510px; height: 510px; right: -250px; top: -220px; }
.login__panel::after { width: 390px; height: 390px; left: -210px; bottom: -230px; }

.login__card {
  position: relative;
  z-index: 1;
  width: min(430px, 100%);
  box-sizing: border-box;
  padding: 40px 38px 32px;
  border: 1px solid rgba(255, 255, 255, .82);
  border-radius: 24px;
  background: rgba(255, 255, 255, .67);
  backdrop-filter: blur(22px) saturate(1.2);
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
  box-shadow: 0 22px 54px rgba(14, 75, 43, .13), inset 0 1px 0 rgba(255, 255, 255, .74);
}

.login__brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 25px;
  margin-bottom: 25px;
  border-bottom: 1px solid rgba(29, 93, 58, .12);
}
.login__brand-mark {
  flex: 0 0 46px;
  height: 46px;
  width: 46px;
  border-radius: 50%;
  box-shadow: 0 8px 17px rgba(19, 102, 64, .14);
}
.login__brand-copy { min-width: 0; }
.login__brand-copy strong {
  display: block;
  color: #153d2b;
  font-size: 15px;
  line-height: 1.45;
  letter-spacing: .3px;
}
.login__brand-copy span {
  display: block;
  margin-top: 5px;
  color: #5c806c;
  font-size: 11px;
  letter-spacing: .5px;
}

.login__card-head h3 {
  margin: 0 0 6px;
  color: #173d2b;
  font-size: 22px;
}

.login__card-head p {
  margin: 0 0 22px;
  font-size: 13px;
  color: var(--gz-text-sub);
}

.login__options {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}

.login__submit {
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: 10px;
  background: linear-gradient(110deg, #0c6540, #208454 55%, #0d6b47);
  box-shadow: 0 10px 20px rgba(13, 107, 71, .19);
  letter-spacing: 6px;
  transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
}
.login__submit:not(.is-disabled):hover,
.login__submit:not(.is-disabled):focus-visible {
  background: linear-gradient(110deg, #0e7549, #279664 55%, #117a50);
  box-shadow: 0 13px 24px rgba(13, 107, 71, .25);
  transform: translateY(-2px);
}
.login__submit:not(.is-disabled):active { transform: translateY(0); }

.login__card :deep(.el-input__wrapper) {
  border-radius: 9px;
  background: rgba(255, 255, 255, .62);
  box-shadow: inset 0 0 0 1px rgba(31, 94, 60, .16);
  transition: box-shadow .2s ease, background .2s ease;
}
.login__card :deep(.el-input__wrapper:hover),
.login__card :deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, .82);
  box-shadow: inset 0 0 0 1px #3b9a66;
}

.login__tip {
  margin: 16px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--gz-text-sub);
}

.login__support {
  position: absolute;
  bottom: 18px;
  margin: 0;
  color: #6d8877;
  font-size: 11px;
  letter-spacing: .4px;
}

@media (max-width: 860px) {
  .login { display: block; min-height: 100vh; height: auto; }
  .login__banner {
    min-height: 205px;
    padding: 20px;
    box-sizing: border-box;
  }
  .login__title { font-size: 24px; }
  .login__subtitle { font-size: 18px; margin-bottom: 8px; }
  .login__slogan, .login__features, .login__foot { display: none; }
  .login__panel { min-height: max(470px, calc(100vh - 205px)); padding: 20px 14px 45px; }
  .login__card { padding: 30px 24px 26px; }
  .login__brand-copy strong { font-size: 13px; }
}
</style>
