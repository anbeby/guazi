import type { Directive, DirectiveBinding } from 'vue'

import { useUserStore } from '@/stores/user'

/**
 * 按钮级权限指令。
 *
 * 用法：
 *   <el-button v-permission="'product:write'">发布商品</el-button>
 *   <el-button v-permission="['product:write', 'product:audit']">审核</el-button>
 *
 * 语义：数组为「任一满足即可」；无权限时直接从 DOM 移除元素。
 */
const permission: Directive<HTMLElement, string | string[]> = {
  mounted(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
    const value = binding.value
    if (!value) return
    const userStore = useUserStore()
    if (!userStore.hasPermission(value)) {
      el.parentNode?.removeChild(el)
    }
  }
}

export default permission

/** 便于在 setup 中使用同一套判定逻辑 */
export function checkPermission(value?: string | string[]): boolean {
  return useUserStore().hasPermission(value)
}
