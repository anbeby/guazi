import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

import App from './App.vue'
import router from './router'
import permission from './directives/permission'

import 'element-plus/dist/index.css'
import 'nprogress/nprogress.css'
import './styles/index.css'

dayjs.locale('zh-cn')

const app = createApp(App)

// Element Plus 中文语言包
app.use(ElementPlus, { locale: zhCn, size: 'default', zIndex: 3000 })

// 全量注册图标组件（<el-icon><Search /></el-icon> 亦可由 unplugin 自动导入）
Object.entries(ElementPlusIconsVue).forEach(([key, component]) => {
  app.component(key, component)
})

app.use(createPinia())
app.use(router)
app.directive('permission', permission)

app.mount('#app')
