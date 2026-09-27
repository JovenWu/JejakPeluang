'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { type ChangeEvent, type DragEvent, type FormEvent, type ReactNode, useEffect, useId, useRef, useState } from 'react'

import { type DedupeCheck, readDetail, type SubmissionCreated } from '@/lib/api'
import { formatBytes } from '@/lib/format'
import { saveReceipt } from '@/lib/receipt'

const MAX_FILES = 3
const MAX_FILE_BYTES = 10 * 1024 * 1024
const MAX_TOTAL_BYTES = 20 * 1024 * 1024
const MAX_CONTEXT = 4096
const ACCEPT = '.pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg'
const ALLOWED_TYPE = /\.(pdf|png|jpe?g)$/i

// Backend validation messages are English; translate the ones guests hit.
const SERVER_MESSAGES: [RegExp, string][] = [
  [/url or at least one file/i, 'Isi tautan atau unggah minimal satu berkas.'],
  [/scheme|http/i, 'Tautan harus diawali http:// atau https://.'],
  [/url/i, 'Tautan tidak valid.'],
  [/at most 3 files/i, 'Maksimal 3 berkas.'],
  [/too large|exceeds|size/i, 'Berkas terlalu besar (maks 10 MB per berkas, 20 MB total).'],
  [/type|mime|unsupported/i, 'Jenis berkas tidak didukung. Gunakan PDF, PNG, atau JPG.'],
  [/email/i, 'Alamat email tidak valid.'],
  [/context/i, 'Konteks terlalu panjang (maks 4.096 karakter).'],
]

function translate(detail: unknown): string {
  if (typeof detail === 'string') {
    return SERVER_MESSAGES.find(([pattern]) => pattern.test(detail))?.[1] ?? detail
  }
  return 'Kiriman ditolak. Periksa kembali isian Anda.'
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

interface Errors {
  url?: string
  files?: string
  email?: string
  context?: string
  form?: string
}

function validate(url: string, files: File[], email: string, context: string): Errors {
  const errors: Errors = {}
  if (!url && files.length === 0) {
    errors.form = 'Isi tautan atau unggah minimal satu berkas.'
  }
  if (url && !isHttpUrl(url)) {
    errors.url = 'Tautan harus lengkap dan diawali http:// atau https://.'
  } else if (url.length > 2048) {
    errors.url = 'Tautan terlalu panjang (maks 2.048 karakter).'
  }
  if (files.length > MAX_FILES) {
    errors.files = 'Maksimal 3 berkas.'
  } else if (files.some((file) => !ALLOWED_TYPE.test(file.name))) {
    errors.files = 'Hanya PDF, PNG, atau JPG.'
  } else if (files.some((file) => file.size > MAX_FILE_BYTES)) {
    errors.files = 'Setiap berkas maksimal 10 MB.'
  } else if (files.reduce((sum, file) => sum + file.size, 0) > MAX_TOTAL_BYTES) {
    errors.files = 'Total berkas maksimal 20 MB.'
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = 'Alamat email tidak valid.'
  }
  if (context.length > MAX_CONTEXT) {
    errors.context = 'Maksimal 4.096 karakter.'
  }
  return errors
}

function DuplicateNotice({ match }: { match: DedupeCheck }): ReactNode {
  if (match.kind === 'listing' && match.slug) {
    return (
      <div role="status" className="rounded-[3px] border border-stamp bg-stamp-tint px-4 py-3 text-sm text-stamp-deep">
        <p className="font-semibold">Tautan ini sudah ada di katalog terverifikasi.</p>
        <p className="mt-1">
          {match.title ? <>“{match.title}” · </> : null}
          <Link className="font-semibold underline" href={`/katalog/${match.slug}`}>
            Lihat entri katalog →
          </Link>
        </p>
      </div>
    )
  }
  if (match.kind === 'incoming' && match.ref) {
    return (
      <div role="status" className="rounded-[3px] border border-rule-2 bg-surface px-4 py-3 text-sm">
        <p className="font-semibold">Tautan ini sudah dicek AI dan sedang menunggu moderator.</p>
        <p className="mt-1 text-ink-2">
          Tidak perlu mengirim ulang ·{' '}
          <Link className="link font-semibold" href={`/antrean/${match.ref}`}>
            Lihat hasil pemeriksaannya →
          </Link>
        </p>
      </div>
    )
  }
  return null
}

export function CheckForm(): ReactNode {
  const router = useRouter()
  const id = useId()
  const fileInput = useRef<HTMLInputElement>(null)
  const [url, setUrl] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [context, setContext] = useState('')
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [duplicate, setDuplicate] = useState<DedupeCheck | null>(null)
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const trimmedUrl = url.trim()

  useEffect(() => {
    if (!isHttpUrl(trimmedUrl)) {
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/v1/submissions/check?url=${encodeURIComponent(trimmedUrl)}`, {
          signal: controller.signal,
        })
        if (response.ok) {
          const body = (await response.json()) as DedupeCheck
          setDuplicate(body.duplicate ? body : null)
        }
      } catch {
        // The lookup is a convenience; intake re-checks duplicates anyway.
      }
    }, 650)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [trimmedUrl])

  function addFiles(list: FileList | null): void {
    if (!list) {
      return
    }
    const next = [...files, ...Array.from(list)].slice(0, MAX_FILES + 1)
    setFiles(next)
    setErrors((prev) => ({ ...prev, files: validate('', next, '', '').files, form: undefined }))
  }

  function removeFile(index: number): void {
    const next = files.filter((_, i) => i !== index)
    setFiles(next)
    setErrors((prev) => ({ ...prev, files: validate('', next, '', '').files }))
  }

  function onDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault()
    setDragging(false)
    addFiles(event.dataTransfer.files)
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const found = validate(trimmedUrl, files, email.trim(), context)
    setErrors(found)
    if (Object.keys(found).length > 0 || (duplicate && trimmedUrl)) {
      return
    }
    setSubmitting(true)
    const body = new FormData()
    if (trimmedUrl) {
      body.set('url', trimmedUrl)
    }
    if (context.trim()) {
      body.set('context', context.trim())
    }
    if (email.trim()) {
      body.set('contact_email', email.trim())
    }
    files.forEach((file) => body.append('files', file))
    try {
      const response = await fetch('/api/v1/submissions', { method: 'POST', body })
      if (response.status === 202) {
        const created = (await response.json()) as SubmissionCreated
        saveReceipt(created.ref, created.receipt_token, true)
        router.push(`/cek/${created.ref}`)
        return
      }
      const detail = await readDetail(response)
      if (response.status === 409 && detail && typeof detail === 'object') {
        setDuplicate({ duplicate: true, ...(detail as Omit<DedupeCheck, 'duplicate'>) })
      } else if (response.status === 429) {
        setErrors({ form: 'Batas 10 kiriman per jam dari jaringan Anda sudah tercapai. Coba lagi nanti.' })
      } else if (response.status === 413) {
        setErrors({ files: 'Total berkas terlalu besar.' })
      } else {
        setErrors({ form: translate(detail) })
      }
    } catch {
      setErrors({ form: 'Tidak dapat terhubung ke server. Periksa koneksi Anda lalu coba lagi.' })
    }
    setSubmitting(false)
  }

  const blocked = Boolean(duplicate && trimmedUrl)

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5" aria-describedby={errors.form ? `${id}-form` : undefined}>
      <div>
        <label htmlFor={`${id}-url`} className="mb-1.5 block text-sm font-semibold">
          Tautan pengumuman
        </label>
        <input
          id={`${id}-url`}
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://instagram.com/p/… atau situs penyelenggara"
          className="field h-13 font-mono text-[0.9375rem]"
          value={url}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            setUrl(event.target.value)
            setDuplicate(null)
            setErrors((prev) => ({ ...prev, url: undefined, form: undefined }))
          }}
          aria-invalid={errors.url ? true : undefined}
          aria-describedby={errors.url ? `${id}-url-error` : undefined}
        />
        {errors.url ? (
          <p id={`${id}-url-error`} className="mt-1.5 text-sm font-medium text-bad">
            {errors.url}
          </p>
        ) : null}
      </div>

      {duplicate && trimmedUrl ? <DuplicateNotice match={duplicate} /> : null}

      <div>
        <div className="mb-1.5 flex items-baseline justify-between gap-3">
          <span id={`${id}-files-label`} className="text-sm font-semibold">
            Atau unggah poster / PDF
          </span>
          <span className="font-mono text-2xs text-ink-3">maks 3 · 10 MB/berkas</span>
        </div>
        <div
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex flex-wrap items-center gap-3 rounded-[3px] border border-dashed px-4 py-3.5 transition-colors ${
            dragging ? 'border-stamp bg-stamp-tint' : 'border-rule-2 bg-surface'
          }`}
        >
          <button
            type="button"
            className="btn btn-ghost min-h-10 bg-paper"
            onClick={() => fileInput.current?.click()}
            aria-describedby={`${id}-files-label`}
          >
            Pilih berkas
          </button>
          <span className="text-sm text-ink-3">atau seret ke sini (PDF, PNG, JPG)</span>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-labelledby={`${id}-files-label`}
            onChange={(event) => {
              addFiles(event.target.files)
              event.target.value = ''
            }}
          />
        </div>
        {files.length > 0 ? (
          <ul className="mt-2 divide-y divide-rule border-y border-rule">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`} className="flex items-center gap-3 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate font-medium">{file.name}</span>
                <span className="font-mono text-2xs text-ink-3">{formatBytes(file.size)}</span>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="min-h-9 rounded-sm px-2 text-xs font-semibold text-ink-2 hover:text-bad"
                  aria-label={`Hapus ${file.name}`}
                >
                  Hapus
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {errors.files ? <p className="mt-1.5 text-sm font-medium text-bad">{errors.files}</p> : null}
      </div>

      <details className="group rounded-[3px] border border-rule open:bg-surface">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between px-4 text-sm font-semibold marker:hidden">
          Tambah konteks atau email (opsional)
          <span aria-hidden className="font-mono text-ink-3 transition-transform group-open:rotate-45">
            +
          </span>
        </summary>
        <div className="space-y-4 border-t border-rule px-4 pt-4 pb-5">
          <div>
            <label htmlFor={`${id}-context`} className="mb-1.5 block text-sm font-semibold">
              Dari mana Anda mendapatkannya?
            </label>
            <textarea
              id={`${id}-context`}
              rows={3}
              maxLength={MAX_CONTEXT}
              className="field resize-y"
              placeholder="Misal: diteruskan di grup WhatsApp angkatan, poster di mading kampus…"
              value={context}
              onChange={(event) => setContext(event.target.value)}
              aria-invalid={errors.context ? true : undefined}
            />
            <p className="mt-1 text-xs text-ink-3">Hanya dibaca moderator, tidak ditampilkan publik.</p>
          </div>
          <div>
            <label htmlFor={`${id}-email`} className="mb-1.5 block text-sm font-semibold">
              Email untuk klarifikasi
            </label>
            <input
              id={`${id}-email`}
              type="email"
              autoComplete="email"
              className="field"
              placeholder="nama@email.com"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value)
                setErrors((prev) => ({ ...prev, email: undefined }))
              }}
              aria-invalid={errors.email ? true : undefined}
            />
            {errors.email ? <p className="mt-1.5 text-sm font-medium text-bad">{errors.email}</p> : null}
            <p className="mt-1 text-xs text-ink-3">
              Kami tidak mengirim notifikasi. Email dihapus otomatis paling lambat 30 hari.
            </p>
          </div>
        </div>
      </details>

      {errors.form ? (
        <p id={`${id}-form`} role="alert" className="rounded-[3px] bg-bad-tint px-4 py-3 text-sm font-medium text-bad">
          {errors.form}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <button type="submit" className="btn btn-stamp h-12 px-6 text-base" disabled={submitting || blocked}>
          {submitting ? 'Mengirim…' : 'Periksa sekarang'}
        </button>
        <p className="text-xs leading-relaxed text-ink-3">
          Gratis, tanpa akun. Anda akan menerima token resi untuk melihat hasilnya lagi.
        </p>
      </div>
    </form>
  )
}
