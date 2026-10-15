/**
 * 文件下载 / 导出工具。
 *
 * 平台仅提供服务端直出（MinIO 或本地磁盘）的下载接口，
 * 因此这里统一处理：直接跳转 / 带 token 拉取 blob 后再保存。
 */
import { getAccessToken } from './auth'

/** 通过隐藏 <a> 触发浏览器下载 */
export function downloadByUrl(url: string, filename?: string): void {
  const a = document.createElement('a')
  a.href = url
  if (filename) a.download = filename
  a.target = '_blank'
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/** 带 Authorization 头拉取二进制并保存（用于需要鉴权的下载接口） */
export async function downloadWithAuth(url: string, filename: string): Promise<void> {
  const token = getAccessToken()
  const resp = await fetch(url, {
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  if (!resp.ok) {
    throw new Error(`下载失败：HTTP ${resp.status}`)
  }
  const blob = await resp.blob()
  saveBlob(blob, filename)
}

/** 保存 Blob 到本地 */
export function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = window.URL.createObjectURL(blob)
  downloadByUrl(objectUrl, filename)
  window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 3000)
}

/** 将对象数组导出为 CSV（带 BOM，Excel 可直接打开中文） */
export function exportCsv<T extends Record<string, unknown>>(
  rows: T[],
  columns: { key: keyof T | string; label: string }[],
  filename = 'export.csv'
): void {
  const header = columns.map((c) => `"${c.label}"`).join(',')
  const body = rows
    .map((row) =>
      columns
        .map((c) => {
          const value = row[c.key as keyof T]
          const text = value === null || value === undefined ? '' : String(value)
          return `"${text.replace(/"/g, '""')}"`
        })
        .join(',')
    )
    .join('\r\n')
  const csv = `\uFEFF${header}\r\n${body}`
  saveBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), filename)
}

/** 生成打印用 HTML 并打开新窗口（对账单 / 结算单打印） */
export function printHtml(title: string, innerHtml: string): void {
  const win = window.open('', '_blank', 'width=900,height=700')
  if (!win) return
  win.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${title}</title>
  <style>
    body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; padding: 24px; color: #1f2328; }
    h1 { font-size: 20px; text-align: center; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border: 1px solid #dcdfe6; padding: 6px 8px; text-align: left; }
    th { background: #f5f7fa; }
  </style>
</head>
<body>${innerHtml}</body>
</html>`)
  win.document.close()
  win.focus()
  win.print()
}
