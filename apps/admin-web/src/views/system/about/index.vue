<template>
  <div class="about page-container">
    <section class="page-card about__card">
      <div class="about__brand">
        <img src="/static/images/logo/platform-mark.svg" alt="瓜子平台标识" />
        <div>
          <span class="about__eyebrow">第十师 · 北屯瓜子产业</span>
          <h1>关于瓜子平台</h1>
          <p>产业交易 · 供应链协同 · 智慧运营</p>
        </div>
      </div>
      <dl class="about__facts">
        <div><dt>平台名称</dt><dd>第十师瓜子油料数字化交易平台</dd></div>
        <div><dt>平台定位</dt><dd>瓜子油料产业交易与运营展示</dd></div>
        <div><dt>技术支持</dt><dd>新疆屯云大数据科技有限公司</dd></div>
      </dl>
      <p class="about__note">当前为测试迭代阶段。页面展示数据以平台数据库中的记录为准。</p>
    </section>
  </div>
</template>

<style scoped>
.about { max-width: 900px; margin: 0 auto; }
.about__card { padding: 32px; }
.about__brand { display: flex; align-items: center; gap: 18px; padding-bottom: 26px; border-bottom: 1px solid var(--gz-border); }
.about__brand img { width: 64px; height: 64px; flex: none; }
.about__eyebrow { color: var(--gz-primary); font-size: 12px; font-weight: 700; letter-spacing: 1px; }
.about h1 { margin: 4px 0; font-size: 26px; color: var(--gz-text-main); }
.about__brand p { margin: 0; color: var(--gz-text-sub); font-size: 13px; }
.about__facts { margin: 12px 0 0; }
.about__facts div { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 16px; padding: 18px 0; border-bottom: 1px solid var(--gz-border); }
.about__facts dt { color: var(--gz-text-sub); }
.about__facts dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }
.about__note { margin: 22px 0 0; color: var(--gz-text-sub); font-size: 12px; line-height: 1.7; }
@media (max-width: 650px) {
  .about__card { padding: 20px; }
  .about__brand { align-items: flex-start; }
  .about__brand img { width: 48px; height: 48px; }
  .about h1 { font-size: 21px; }
  .about__facts div { grid-template-columns: 1fr; gap: 4px; }
}
</style>
