/// <reference types="vite/client" />

/**
 * 环境变量类型（.env.development / .env.production）
 */
interface ImportMetaEnv {
  readonly VITE_APP_TITLE: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_UPLOAD_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/**
 * .vue 单文件组件类型声明
 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

/**
 * nprogress 无官方类型包，此处按使用到的 API 声明
 */
declare module 'nprogress' {
  interface NProgress {
    start(): NProgress
    done(force?: boolean): NProgress
    inc(amount?: number): NProgress
    set(n: number): NProgress
    remove(): void
    configure(options: {
      minimum?: number
      template?: string
      easing?: string
      speed?: number
      trickle?: boolean
      trickleSpeed?: number
      showSpinner?: boolean
      parent?: string
    }): NProgress
    status: number | null
  }
  const nprogress: NProgress
  export default nprogress
}

/** 全局挂载的站点标题 */
declare const __APP_TITLE__: string
