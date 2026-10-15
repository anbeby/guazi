<script setup lang="ts">
/**
 * 404 页面：路由表 `/404` 与 `/:pathMatch(.*)*` 通配重定向的落地页。
 *
 * 插画全部用 CSS 绘制（不引入任何外部图片资源），保证离线 / 内网环境可用。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

defineOptions({ name: 'ErrorPage' })

const router = useRouter()
const route = useRoute()
const forbidden = computed(() => route.path === '/403')

/** 返回当前身份可访问的入口 */
function goHome(): void {
  router.push(forbidden.value ? '/account' : '/home')
}

/** 返回上一页；无历史记录时回退到首页，避免出现空白页 */
function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    goHome()
  }
}
</script>

<template>
  <div class="not-found">
    <div class="not-found__inner">
      <!-- CSS 插画：破损文档 + 放大镜 + 瓜子 -->
      <div class="art" aria-hidden="true">
        <span class="art__glow"></span>

        <div class="art__sheet">
          <span class="art__code">{{ forbidden ? '403' : '404' }}</span>
          <i class="art__line art__line--1"></i>
          <i class="art__line art__line--2"></i>
          <i class="art__line art__line--3"></i>
          <i class="art__fold"></i>
        </div>

        <div class="art__lens">
          <span class="art__lens-glass"></span>
          <span class="art__lens-handle"></span>
        </div>

        <i class="art__seed art__seed--1"></i>
        <i class="art__seed art__seed--2"></i>
        <i class="art__seed art__seed--3"></i>
      </div>

      <h1 class="not-found__title">{{ forbidden ? '当前账号没有访问权限' : '页面不存在或已被移除' }}</h1>
      <p class="not-found__desc">
        {{ forbidden ? '您可以返回个人中心，查看咨询、收藏和企业申请。需要后台权限请联系平台管理员。' : '您访问的页面可能已被删除、更名，或者链接地址有误。请返回首页继续操作。' }}
      </p>

      <div class="not-found__actions">
        <el-button type="primary" @click="goHome">
          <el-icon><HomeFilled /></el-icon>
          <span>{{ forbidden ? '前往个人中心' : '返回首页' }}</span>
        </el-button>
        <el-button @click="goBack">
          <el-icon><Back /></el-icon>
          <span>返回上一页</span>
        </el-button>
      </div>

      <p class="not-found__hint">{{ forbidden ? '错误码：403 · 访问受限' : '错误码：404 · 页面未找到' }}</p>
      <p class="not-found__support">如仍无法访问，请联系屯云大数据技术支持。</p>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 20px;
  background: var(--gz-page-bg, #f4f6f8);
}

.not-found__inner {
  width: 100%;
  max-width: 560px;
  text-align: center;
}

/* ---------------- CSS 插画 ---------------- */

.art {
  position: relative;
  width: 260px;
  height: 200px;
  margin: 0 auto 28px;
}

.art__glow {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 210px;
  height: 210px;
  margin: -105px 0 0 -105px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(22, 101, 63, 0.1) 0%, rgba(22, 101, 63, 0) 70%);
}

/* 文档纸 */
.art__sheet {
  position: absolute;
  left: 26px;
  top: 22px;
  width: 158px;
  height: 150px;
  padding: 20px 18px;
  border: 2px solid #cfe0d6;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 59, 37, 0.1);
  animation: art-float 4.6s ease-in-out infinite;
}

/* 折角（右上角破损） */
.art__fold {
  position: absolute;
  right: -2px;
  top: -2px;
  width: 46px;
  height: 46px;
  background: linear-gradient(225deg, var(--gz-page-bg, #f4f6f8) 0 50%, #e8f3ee 50% 100%);
  border-bottom-left-radius: 10px;
  border-top-right-radius: 9px;
}

.art__code {
  display: block;
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 4px;
  color: var(--gz-primary, #16653f);
  opacity: 0.9;
}

.art__line {
  display: block;
  height: 8px;
  margin-top: 11px;
  border-radius: 4px;
  background: #e4e7ed;
}

.art__line--1 {
  width: 100%;
}
.art__line--2 {
  width: 78%;
}
.art__line--3 {
  width: 56%;
  background: #eef1f4;
}

/* 放大镜：聚焦到「缺失」的位置 */
.art__lens {
  position: absolute;
  right: 12px;
  bottom: 4px;
  width: 84px;
  height: 84px;
  animation: art-float 4.6s ease-in-out infinite 0.8s;
}

.art__lens-glass {
  position: absolute;
  left: 0;
  top: 0;
  width: 66px;
  height: 66px;
  border: 5px solid var(--gz-primary, #16653f);
  border-radius: 50%;
  background: rgba(232, 243, 238, 0.55);
  box-shadow: inset 0 0 14px rgba(22, 101, 63, 0.16);
}

/* 镜面高光 */
.art__lens-glass::after {
  content: '';
  position: absolute;
  left: 12px;
  top: 10px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
}

.art__lens-handle {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 34px;
  height: 10px;
  border-radius: 5px;
  background: var(--gz-accent, #d48806);
  transform: rotate(45deg);
  transform-origin: left center;
}

/* 瓜子：椭圆 + 旋转，模拟葵花籽外形 */
.art__seed {
  position: absolute;
  width: 12px;
  height: 18px;
  border-radius: 50% 50% 50% 50% / 62% 62% 38% 38%;
  background: linear-gradient(150deg, #4a4f57 0%, #2c323c 70%);
  border-top: 2px solid rgba(214, 219, 224, 0.85);
}

.art__seed--1 {
  left: 6px;
  bottom: 18px;
  transform: rotate(-24deg);
  animation: art-float 5.2s ease-in-out infinite 0.3s;
}

.art__seed--2 {
  left: 34px;
  bottom: 2px;
  transform: rotate(12deg);
  animation: art-float 5.2s ease-in-out infinite 0.9s;
}

.art__seed--3 {
  right: 74px;
  top: 2px;
  width: 10px;
  height: 15px;
  transform: rotate(38deg);
  animation: art-float 5.2s ease-in-out infinite 1.4s;
}

@keyframes art-float {
  0%,
  100% {
    transform: translateY(0) rotate(var(--art-rotate, 0deg));
  }
  50% {
    transform: translateY(-7px) rotate(var(--art-rotate, 0deg));
  }
}

/* 种子的旋转角度不能被动画覆盖，单独声明 */
.art__seed--1 {
  --art-rotate: -24deg;
}
.art__seed--2 {
  --art-rotate: 12deg;
}
.art__seed--3 {
  --art-rotate: 38deg;
}

/* ---------------- 文案与按钮 ---------------- */

.not-found__title {
  margin: 0 0 10px;
  font-size: 22px;
  font-weight: 600;
  color: var(--gz-text-main, #1f2328);
}

.not-found__desc {
  margin: 0 auto 24px;
  max-width: 420px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gz-text-sub, #6b7280);
}

.not-found__actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

.not-found__actions .el-button + .el-button {
  margin-left: 0;
}

.not-found__hint {
  margin: 20px 0 0;
  font-size: 12px;
  color: var(--gz-text-sub, #6b7280);
  opacity: 0.8;
}

.not-found__support {
  margin: 8px 0 0;
  color: #668171;
  font-size: 12px;
}

@media (max-width: 480px) {
  .art {
    transform: scale(0.86);
  }
  .not-found__title {
    font-size: 19px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .art__sheet,
  .art__lens,
  .art__seed {
    animation: none;
  }
}
</style>
