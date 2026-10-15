/** 商品分类 /categories —— docs/04 §2.5 */
import { http } from './request'
import type { Category, CategoryPayload } from './types'

const BASE = '/categories'

/** GET /api/v1/categories/tree 登录即可（含商品数） */
export function getCategoryTree(): Promise<Category[]> {
  return http.get<Category[]>(`${BASE}/tree`)
}

/** POST /api/v1/categories 权限 product:write */
export function createCategory(data: CategoryPayload): Promise<Category> {
  return http.post<Category>(BASE, data)
}

/** PUT /api/v1/categories/{id} 权限 product:write */
export function updateCategory(id: number, data: Partial<CategoryPayload>): Promise<Category> {
  return http.put<Category>(`${BASE}/${id}`, data)
}

/** DELETE /api/v1/categories/{id} 权限 product:write */
export function deleteCategory(id: number): Promise<null> {
  return http.delete<null>(`${BASE}/${id}`)
}
