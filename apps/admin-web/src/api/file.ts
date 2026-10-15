/** 文件 /files —— docs/04 §2.11 */
import { http } from './request'
import { API_BASE_URL } from './request'
import type { FileQuery, FileUploadResult, PageResult, SysFile } from './types'

const BASE = '/files'

/**
 * POST /api/v1/files/upload —— multipart/form-data：file、biz_type
 * 返回 { file_key, url, size }
 */
export function uploadFile(
  file: File,
  bizType = 'common',
  onProgress?: (percent: number) => void
): Promise<FileUploadResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('biz_type', bizType)
  return http.upload<FileUploadResult>(BASE + '/upload', formData, {
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) return
      onProgress(Math.round((event.loaded * 100) / event.total))
    }
  })
}

/** GET /api/v1/files 登录 —— 文件列表（分页） */
export function listFiles(params: FileQuery): Promise<PageResult<SysFile>> {
  return http.get<PageResult<SysFile>>(BASE, params as Record<string, unknown>)
}

/** GET /api/v1/files/{file_key}/download 登录 —— 下载地址（MinIO 不可用时走本地磁盘） */
export function getDownloadUrl(fileKey: string): string {
  return `${API_BASE_URL}${BASE}/${encodeURIComponent(fileKey)}/download`
}
