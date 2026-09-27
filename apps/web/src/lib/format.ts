import type { Category } from './api'

export const CATEGORY_LABELS: Record<Category, string> = {
  scholarship: 'beasiswa',
  internship: 'magang',
  competition: 'lomba',
}

export const VERDICT_LABELS: Record<string, string> = {
  supported: 'cocok',
  conflicting: 'berbeda',
  not_found: 'tidak ditemukan',
  unreadable: 'tak terbaca',
}

export const OUTCOME_LABELS: Record<string, string> = {
  complete: 'pemeriksaan selesai',
  provider_unavailable: 'layanan pemeriksa sedang sibuk',
  manual_review_required: 'perlu tinjauan manual',
  no_public_source: 'sumber resmi tidak ditemukan',
  no_content: 'konten tidak dapat dibaca',
}

export const FIELD_LABELS: Record<string, string> = {
  title: 'judul',
  issuer: 'penyelenggara',
  deadline: 'batas akhir',
  category: 'kategori',
  region: 'wilayah',
  eligibility: 'syarat',
  fees: 'biaya',
  requested_data: 'data diminta',
  source_hint: 'petunjuk sumber',
}

export const REPORT_CATEGORIES: Record<string, string> = {
  scam_suspect: 'dicurigai penipuan',
  deadline_wrong: 'batas waktu salah',
  link_broken: 'tautan rusak',
  info_incorrect: 'info tidak akurat',
  other: 'lainnya',
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  return new Intl.DateTimeFormat('id-ID', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function hostOf(url: string | null | undefined): string {
  if (!url) {
    return ''
  }
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}
