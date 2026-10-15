/**
 * 展示层格式化工具：金额（元）、数量（吨/千克）、日期时间、百分比。
 * 后端 numeric 字段以字符串返回，前端仅做展示格式化，绝不参与精度计算。
 */
import dayjs from 'dayjs'

/** 千分位金额，默认保留 2 位小数：'42680000.00' -> '42,680,000.00' */
export function formatMoney(value?: string | number | null, decimals = 2): string {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return String(value)
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

/** 带货币符号的金额（默认 CNY -> 元） */
export function formatAmount(value?: string | number | null, currency = '元', decimals = 2): string {
  if (value === null || value === undefined || value === '') return '-'
  return `${formatMoney(value, decimals)} ${currency}`
}

/** 数量：保留 3 位小数并去除无意义的尾随零 */
export function formatQuantity(value?: string | number | null, decimals = 3): string {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return String(value)
  const fixed = num.toFixed(decimals)
  return fixed.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')
}

/** 单位中文名 */
export function unitLabel(unit?: string | null): string {
  const map: Record<string, string> = { ton: '吨', kg: '千克', bag: '袋' }
  if (!unit) return ''
  return map[unit] || unit
}

/** 数量 + 单位：'500.000' + 'ton' -> '500 吨' */
export function formatQuantityWithUnit(value?: string | number | null, unit?: string | null): string {
  const q = formatQuantity(value)
  if (q === '-') return '-'
  const u = unitLabel(unit)
  return u ? `${q} ${u}` : q
}

/** 大额金额压缩展示，用于指标卡片：42680000 -> '4268.00 万' */
export function formatMoneyShort(value?: string | number | null): string {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return String(value)
  if (Math.abs(num) >= 100000000) return `${(num / 100000000).toFixed(2)} 亿`
  if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(2)} 万`
  return formatMoney(num)
}

export function formatPercent(value?: number | string | null, decimals = 2): string {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return String(value)
  const ratio = num > 1 ? num : num * 100
  return `${ratio.toFixed(decimals)}%`
}

/** 日期：YYYY-MM-DD */
export function formatDate(value?: string | number | Date | null, fallback = '-'): string {
  if (!value) return fallback
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD') : fallback
}

/** 日期时间：YYYY-MM-DD HH:mm:ss */
export function formatDateTime(value?: string | number | Date | null, fallback = '-'): string {
  if (!value) return fallback
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : fallback
}

/** 时间：HH:mm */
export function formatTime(value?: string | number | Date | null, fallback = '-'): string {
  if (!value) return fallback
  const d = dayjs(value)
  return d.isValid() ? d.format('HH:mm') : fallback
}

/** 相对时间：3 分钟前 */
export function formatFromNow(value?: string | number | Date | null, fallback = '-'): string {
  if (!value) return fallback
  const target = dayjs(value)
  if (!target.isValid()) return fallback
  const diff = dayjs().diff(target, 'second')
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
  return target.format('YYYY-MM-DD')
}

/** 生成最近 N 天的日期数组（含今天），用于图表 X 轴兜底 */
export function lastDays(days: number): string[] {
  const list: string[] = []
  for (let i = days - 1; i >= 0; i--) {
    list.push(dayjs().subtract(i, 'day').format('YYYY-MM-DD'))
  }
  return list
}

/** 文件大小：1024 -> '1.00 KB' */
export function formatFileSize(size?: number | null): string {
  if (size === null || size === undefined) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}
