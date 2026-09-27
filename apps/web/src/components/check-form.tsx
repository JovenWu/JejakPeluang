'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { FormEvent, JSX } from 'react'
import { useRef, useState } from 'react'

import type { DedupeCheck } from '@/lib/api'
import { hostOf } from '@/lib/format'

import {
  BUTTON_PRIMARY,
  Card,
  CardHeader,
  INPUT_CLASS,
} from './ui'

const RECEIPT_PREFIX = 'jp_receipt:'

export function storeReceiptToken(ref: string, token: string): void {
  try {
    localStorage.setItem(`${RECEIPT_PREFIX}${ref}`, token)
  } catch {
    // private browsing; the banner still shows the token once
  }
}

export function readReceiptToken(ref: string): string | null {
  try {
    return localStorage.getItem(`${RECEIPT_PREFIX}${ref}`)
  } catch {
    return null
  }
}

type Phase =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'submitting' }
  | { kind: 'duplicate'; match: DedupeCheck }
  | { kind: 'error'; message: string }

function FieldLabel({
  children,
  optional,
}: {
  children: React.ReactNode
  optional?: boolean
}): JSX.Element {
  return (
    <span className="text-xs font-semibold text-ink">
      {children}
      {optional && (
        <span className="ml-1.5 font-normal text-faint">opsional</span>
      )}
    </span>
  )
}

function DuplicateNotice({ match }: { match: DedupeCheck }): JSX.Element {
  if (match.kind === 'listing') {
    return (
      <div className="rounded-xl border border-line bg-surface p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-body">
          Sudah ada di katalog
        </p>
        <Link
          href={`/peluang/${match.slug}`}
          className="mt-2 inline-block font-display text-lg font-bold text-accent hover:underline"
        >
          {match.title ?? match.slug}
        </Link>
        <p className="mt-1 text-sm text-body">
          Peluang ini sudah ditinjau moderator.
        </p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-body">
        Sudah dicek AI
      </p>
      <p className="mt-2 text-sm text-body">
        Tautan ini sudah diperiksa dan sedang menunggu verifikasi moderator.
      </p>
      <Link
        href={`/antrean/${match.ref}`}
        className="mt-3 inline-flex items-center rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-paper hover:bg-accent/90"
      >
        Lihat hasil pemeriksaan
      </Link>
    </div>
  )
}

export function CheckForm(): JSX.Element {
  const router = useRouter()
  const [url, setUrl] = useState('')
  const [context, setContext] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const fileInput = useRef<HTMLInputElement | null>(null)

  const busy = phase.kind === 'checking' || phase.kind === 'submitting'

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const trimmedUrl = url.trim()
    if (!trimmedUrl && files.length === 0) {
      setPhase({
        kind: 'error',
        message: 'Isi tautan atau unggah minimal satu berkas.',
      })
      return
    }

    if (trimmedUrl) {
      setPhase({ kind: 'checking' })
      const check = await fetch(
        `/api/v1/submissions/check?url=${encodeURIComponent(trimmedUrl)}`,
      )
      if (check.ok) {
        const match: DedupeCheck = await check.json()
        if (match.duplicate) {
          setPhase({ kind: 'duplicate', match })
          return
        }
      }
    }

    setPhase({ kind: 'submitting' })
    const form = new FormData()
    if (trimmedUrl) {
      form.set('url', trimmedUrl)
    }
    if (context.trim()) {
      form.set('context', context.trim())
    }
    for (const file of files.slice(0, 3)) {
      form.append('files', file)
    }

    const response = await fetch('/api/v1/submissions', {
      method: 'POST',
      body: form,
    })

    if (response.status === 202) {
      const created = await response.json()
      storeReceiptToken(created.ref, created.receipt_token)
      router.push(`/cek/${created.ref}?new=1`)
      return
    }

    if (response.status === 409) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail
      if (detail && detail.error === 'duplicate') {
        setPhase({ kind: 'duplicate', match: { duplicate: true, ...detail } })
        return
      }
    }

    let message = 'Kiriman gagal diproses.'
    if (response.status === 429) {
      message = 'Terlalu sering, coba lagi sebentar lagi.'
    } else {
      const body = await response.json().catch(() => null)
      if (typeof body?.detail === 'string') {
        message = body.detail
      }
    }
    setPhase({ kind: 'error', message })
  }

  return (
    <Card>
      <CardHeader
        eyebrow="Formulir pemeriksaan"
        hint="maks. 10 kiriman per jam"
      />
      <form onSubmit={onSubmit} className="space-y-6 p-5 sm:p-6">
        <label className="block">
          <FieldLabel>Tautan sumber</FieldLabel>
          <input
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://…"
            className={`${INPUT_CLASS} mt-2 font-mono`}
          />
          <span className="mt-1.5 block text-xs text-faint">
            Wajib, atau unggah minimal satu berkas di bawah.
          </span>
          {url.trim() && (
            <span className="mt-1 block font-mono text-xs text-body">
              {hostOf(url.trim())}
            </span>
          )}
        </label>

        <div>
          <FieldLabel optional>Berkas pendukung</FieldLabel>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="mt-2 flex w-full flex-col items-center justify-center rounded-xl border border-dashed border-line-strong bg-surface px-4 py-8 text-center hover:border-accent"
          >
            <span className="text-sm font-medium text-body">
              Seret berkas ke sini, atau pilih berkas
            </span>
            <span className="mt-1 text-xs text-faint">
              PDF, PNG, JPG · maks 3 berkas · ≤10 MB per berkas
            </span>
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,image/png,image/jpeg,application/pdf"
            multiple
            className="hidden"
            onChange={(event) =>
              setFiles(Array.from(event.target.files ?? []).slice(0, 3))
            }
          />
          {files.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {files.map((file) => (
                <li
                  key={file.name}
                  className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-xs"
                >
                  <span className="min-w-0 truncate font-mono">
                    {file.name}
                  </span>
                  <span className="ml-3 shrink-0 text-faint">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <label className="block">
          <FieldLabel optional>Konteks tambahan</FieldLabel>
          <textarea
            value={context}
            onChange={(event) => setContext(event.target.value)}
            rows={3}
            maxLength={4096}
            placeholder="Di mana kamu menemukan ini? Misal: grup WhatsApp, poster kampus."
            className={`${INPUT_CLASS} mt-2`}
          />
          <span className="mt-1.5 block text-xs text-faint">
            Membantu AI dan moderator memahami asal kiriman.
          </span>
        </label>

        {phase.kind === 'duplicate' && <DuplicateNotice match={phase.match} />}
        {phase.kind === 'error' && (
          <p className="rounded-lg bg-bad-tint px-4 py-3 text-sm text-bad">
            {phase.message}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-4 border-t border-line pt-5">
          <button type="submit" disabled={busy} className={BUTTON_PRIMARY}>
            {phase.kind === 'checking'
              ? 'Memeriksa duplikat…'
              : phase.kind === 'submitting'
                ? 'Mengirim…'
                : 'Kirim untuk diperiksa'}
          </button>
          <p className="text-xs leading-5 text-faint">
            Setelah terkirim kamu menerima token resi satu kali. Simpan, itu
            satu-satunya cara membuka ulang hasilnya.
          </p>
        </div>
      </form>
    </Card>
  )
}
