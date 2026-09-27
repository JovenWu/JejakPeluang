import type { Category } from './api'

const TZ = 'Asia/Jakarta'

export const CATEGORY_LABEL: Record<Category, string> = {
  scholarship: 'Beasiswa',
  internship: 'Magang',
  competition: 'Lomba',
}

// A bare "YYYY-MM-DD" parses as UTC midnight, which is 07:00 WIB; pin
// date-only values to WIB midnight so "hari ini" flips at local midnight.
function toDate(value: string): Date {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00+07:00`) : new Date(value)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: TZ,
  }).format(toDate(value))
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  return new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', timeZone: TZ }).format(toDate(value))
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  const text = new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TZ,
  }).format(toDate(value))
  return `${text} WIB`
}

function wibDayNumber(date: Date): number {
  const [y, m, d] = new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(date).split('-').map(Number)
  return Math.round(Date.UTC(y, m - 1, d) / 86_400_000)
}

export function daysUntil(deadline: string, now: Date = new Date()): number {
  return wibDayNumber(toDate(deadline)) - wibDayNumber(now)
}

export type DeadlineTone = 'closed' | 'urgent' | 'soon' | 'open' | 'none'

export interface DeadlineInfo {
  tone: DeadlineTone
  label: string
}

export function deadlineInfo(deadline: string | null | undefined, now: Date = new Date()): DeadlineInfo {
  if (!deadline) {
    return { tone: 'none', label: 'Tanpa tenggat' }
  }
  const days = daysUntil(deadline, now)
  if (days < 0) {
    return { tone: 'closed', label: 'Sudah ditutup' }
  }
  if (days === 0) {
    return { tone: 'urgent', label: 'Berakhir hari ini' }
  }
  if (days === 1) {
    return { tone: 'urgent', label: 'Berakhir besok' }
  }
  if (days <= 7) {
    return { tone: 'urgent', label: `${days} hari lagi` }
  }
  if (days <= 30) {
    return { tone: 'soon', label: `${days} hari lagi` }
  }
  return { tone: 'open', label: `${days} hari lagi` }
}

export function relativeTime(value: string, now: Date = new Date()): string {
  const seconds = Math.round((now.getTime() - new Date(value).getTime()) / 1000)
  if (seconds < 60) {
    return 'baru saja'
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    return `${minutes} menit lalu`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours} jam lalu`
  }
  const days = Math.floor(hours / 24)
  if (days < 30) {
    return `${days} hari lalu`
  }
  return formatDate(value)
}

export function hostOf(url: string | null | undefined): string {
  if (!url) {
    return ''
  }
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export function displayUrl(url: string): string {
  try {
    const parsed = new URL(url)
    const path = parsed.pathname === '/' ? '' : parsed.pathname
    return `${parsed.hostname.replace(/^www\./, '')}${path}${parsed.search}`
  } catch {
    return url
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toLocaleString('id-ID', { maximumFractionDigits: 0 })} KB`
  }
  return `${(bytes / 1024 / 1024).toLocaleString('id-ID', { maximumFractionDigits: 1 })} MB`
}

export function formatCount(value: number): string {
  return value.toLocaleString('id-ID')
}
