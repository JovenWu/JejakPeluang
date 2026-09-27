import type { ScreeningView } from './api'

export type Verdict = 'supported' | 'conflicting' | 'not_found' | 'unreadable'

export interface FieldVerdict {
  verdict: Verdict
  quote: string | null
}

export interface Extracted {
  title: string | null
  issuer: string | null
  deadline: string | null
  category: string | null
  region: string | null
  eligibility: string | null
  fees: string | null
  requested_data: string[]
}

export const COMPARED_FIELDS = ['title', 'issuer', 'deadline', 'category', 'region', 'eligibility'] as const
export type ComparedField = (typeof COMPARED_FIELDS)[number]

export const FIELD_LABEL: Record<ComparedField, string> = {
  title: 'Judul',
  issuer: 'Penerbit',
  deadline: 'Batas akhir',
  category: 'Jenis',
  region: 'Wilayah',
  eligibility: 'Syarat',
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  supported: 'Cocok',
  conflicting: 'Berbeda',
  not_found: 'Tak ditemukan',
  unreadable: 'Tak terbaca',
}

export const EXTRACTED_CATEGORY_LABEL: Record<string, string> = {
  scholarship: 'Beasiswa',
  internship: 'Magang',
  competition: 'Lomba',
}

export const OUTCOME_COPY: Record<string, { title: string; body: string }> = {
  complete: {
    title: 'Pemeriksaan selesai',
    body: 'AI membaca kiriman, mencari halaman sumber di web, lalu membandingkannya per data.',
  },
  no_public_source: {
    title: 'Tidak ada sumber publik yang bisa dibandingkan',
    body: 'AI sudah membaca kiriman, tetapi tidak menemukan halaman web penerbit untuk dicocokkan. Ini belum tentu berarti palsu, karena banyak pengumuman hanya beredar lewat poster atau grup.',
  },
  no_content: {
    title: 'Isi kiriman tidak bisa dibaca',
    body: 'Halaman atau berkas tidak memuat teks yang bisa dibaca AI (misalnya halaman yang butuh JavaScript, atau gambar tanpa teks). Coba kirim tangkapan layar atau PDF pengumumannya.',
  },
  provider_unavailable: {
    title: 'Layanan pemeriksa sedang tidak tersedia',
    body: 'Salah satu layanan AI tidak merespons, jadi pemeriksaan tidak lengkap. Kiriman tetap masuk antrean moderator.',
  },
  manual_review_required: {
    title: 'Perlu dibaca manusia',
    body: 'Hasil AI tidak konsisten sehingga tidak ditampilkan. Moderator akan meninjau kiriman ini langsung.',
  },
}

export const SOURCE_ERROR_LABEL: Record<string, string> = {
  js_required: 'butuh JavaScript',
  empty_content: 'halaman kosong',
  timeout: 'waktu habis',
  connect_failed: 'gagal terhubung',
  http_error: 'galat HTTP',
  too_large: 'terlalu besar',
  too_many_redirects: 'terlalu banyak pengalihan',
  dns_blocked: 'domain tak dikenal',
  forbidden_host: 'alamat diblokir',
  invalid_url: 'URL tidak valid',
}

export const ERROR_KIND_LABEL: Record<string, string> = {
  ...SOURCE_ERROR_LABEL,
  not_configured: 'layanan belum aktif',
  unavailable: 'layanan tidak merespons',
  deadline_exceeded: 'waktu pemeriksaan habis',
  upload_missing: 'berkas tidak ditemukan',
  unsupported_upload: 'jenis berkas belum didukung',
  unreadable_upload: 'berkas tidak terbaca',
  malformed: 'hasil AI tidak valid',
  http: 'layanan menolak permintaan',
  connect: 'gagal terhubung ke layanan',
}

export const ERROR_STAGE_LABEL: Record<string, string> = {
  fetch: 'mengambil halaman',
  extract: 'membaca kiriman',
  discover: 'mencari sumber',
  discovery: 'mencari sumber',
  compare: 'membandingkan',
  judge: 'menilai sumber',
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null
}

export function readExtracted(screening: ScreeningView | null | undefined): Extracted | null {
  const raw = screening?.extracted
  if (!raw) {
    return null
  }
  const requested = Array.isArray(raw.requested_data)
    ? raw.requested_data.filter((item): item is string => typeof item === 'string' && item.trim() !== '')
    : []
  return {
    title: asString(raw.title),
    issuer: asString(raw.issuer),
    deadline: asString(raw.deadline),
    category: asString(raw.category),
    region: asString(raw.region),
    eligibility: asString(raw.eligibility),
    fees: asString(raw.fees),
    requested_data: requested,
  }
}

export function readVerdicts(screening: ScreeningView | null | undefined): Partial<Record<ComparedField, FieldVerdict>> {
  const raw = screening?.field_verdicts
  const result: Partial<Record<ComparedField, FieldVerdict>> = {}
  if (!raw) {
    return result
  }
  for (const field of COMPARED_FIELDS) {
    const entry = raw[field] as { verdict?: unknown; quote?: unknown } | undefined
    if (entry && typeof entry.verdict === 'string' && entry.verdict in VERDICT_LABEL) {
      result[field] = { verdict: entry.verdict as Verdict, quote: asString(entry.quote) }
    }
  }
  return result
}

export function isScreeningDone(screening: ScreeningView | null | undefined): boolean {
  return screening?.state === 'complete' || screening?.state === 'failed'
}

export type Headline = 'running' | 'failed' | 'match' | 'conflict' | 'no_official' | 'degraded'

export interface Summary {
  headline: Headline
  supported: number
  conflicting: number
  compared: number
  officialSources: number
  title: string | null
}

// Summaries state what the AI found, never whether the post is safe.
export function summarize(screening: ScreeningView | null | undefined): Summary {
  const verdicts = Object.values(readVerdicts(screening))
  const supported = verdicts.filter((v) => v.verdict === 'supported').length
  const conflicting = verdicts.filter((v) => v.verdict === 'conflicting').length
  const officialSources = (screening?.sources ?? []).filter((s) => s.official === true).length
  const base = {
    supported,
    conflicting,
    compared: verdicts.length,
    officialSources,
    title: readExtracted(screening)?.title ?? null,
  }
  if (!isScreeningDone(screening)) {
    return { ...base, headline: 'running' }
  }
  if (screening?.state === 'failed') {
    return { ...base, headline: 'failed' }
  }
  if (screening?.outcome !== 'complete') {
    return { ...base, headline: 'degraded' }
  }
  if (conflicting > 0) {
    return { ...base, headline: 'conflict' }
  }
  if (screening?.ai_source_match) {
    return { ...base, headline: 'match' }
  }
  return { ...base, headline: 'no_official' }
}

const UNREADABLE_PAGE_ERRORS = new Set(['js_required', 'empty_content'])

// `no_content` covers both "fetched but no readable text" and "could not be
// fetched at all"; tell the guest which one happened.
export function degradedCopy(screening: ScreeningView | null | undefined): { title: string; body: string } {
  const outcome = screening?.outcome ?? ''
  const sources = screening?.sources ?? []
  const fetchFailed =
    outcome === 'no_content' && sources.length > 0 && sources.every((s) => s.error && !UNREADABLE_PAGE_ERRORS.has(s.error))
  if (fetchFailed) {
    return {
      title: 'Tautan tidak bisa dibuka',
      body: 'Server pemeriksa gagal membuka halaman tersebut, jadi tidak ada teks yang bisa dibaca. Coba lagi nanti, atau kirim tangkapan layar / PDF pengumumannya.',
    }
  }
  return (
    OUTCOME_COPY[outcome] ?? {
      title: 'Pemeriksaan tidak lengkap',
      body: 'Pemeriksaan otomatis tidak selesai. Kiriman tetap ditinjau moderator.',
    }
  )
}

export function headlineText(summary: Summary, screening: ScreeningView | null | undefined): string {
  switch (summary.headline) {
    case 'running':
      return 'Sedang diperiksa AI'
    case 'failed':
      return 'Pemeriksaan AI gagal'
    case 'degraded':
      return degradedCopy(screening).title
    case 'conflict':
      return `${summary.conflicting} data berbeda dari sumber`
    case 'match':
      return 'Ditemukan halaman resmi penerbit, data selaras'
    case 'no_official':
      return 'Belum ditemukan halaman resmi penerbit'
  }
}
