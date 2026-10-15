/** 商品中心 /products —— docs/04 §2.5 */
import { http } from './request'
import type {
  PageResult,
  Product,
  ProductAuditParams,
  ProductInventoryItem,
  ProductPayload,
  ProductQuery
} from './types'

const BASE = '/products'

/** GET /api/v1/products 权限 product:read */
export function listProducts(params: ProductQuery): Promise<PageResult<Product>> {
  return http.get<PageResult<Product>>(BASE, params as Record<string, unknown>)
}

/** POST /api/v1/products 权限 product:write */
export function createProduct(data: ProductPayload): Promise<Product> {
  return http.post<Product>(BASE, data)
}

/** GET /api/v1/products/{id} 权限 product:read */
export function getProduct(id: number): Promise<Product> {
  return http.get<Product>(`${BASE}/${id}`)
}

/** PUT /api/v1/products/{id} 权限 product:write */
export function updateProduct(id: number, data: Partial<ProductPayload>): Promise<Product> {
  return http.put<Product>(`${BASE}/${id}`, data)
}

/** DELETE /api/v1/products/{id} 权限 product:write */
export function deleteProduct(id: number): Promise<null> {
  return http.delete<null>(`${BASE}/${id}`)
}

/** POST /api/v1/products/{id}/publish 权限 product:write —— 上架（需审核通过） */
export function publishProduct(id: number): Promise<Product> {
  return http.post<Product>(`${BASE}/${id}/publish`)
}

/** POST /api/v1/products/{id}/offline 权限 product:write —— 下架 */
export function offlineProduct(id: number): Promise<Product> {
  return http.post<Product>(`${BASE}/${id}/offline`)
}

/** POST /api/v1/products/{id}/audit 权限 product:audit */
export function auditProduct(id: number, data: ProductAuditParams): Promise<Product> {
  return http.post<Product>(`${BASE}/${id}/audit`, data)
}

/** GET /api/v1/products/{id}/inventory 权限 product:read —— 该商品各仓库库存 */
export function getProductInventory(id: number): Promise<ProductInventoryItem[]> {
  return http.get<ProductInventoryItem[]>(`${BASE}/${id}/inventory`)
}

/** GET /api/v1/products/search 登录 —— 全文检索（ES 优先，降级 SQL） */
export function searchProducts(params: {
  q: string
  page?: number
  page_size?: number
}): Promise<PageResult<Product>> {
  return http.get<PageResult<Product>>(`${BASE}/search`, params as Record<string, unknown>)
}
