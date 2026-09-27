'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { FormEvent, JSX } from 'react'
import { useState } from 'react'

import type { DedupeCheck } from '@/lib/api'
import { hostOf } from '@/lib/format'

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

function DuplicateNotice({ match }: { match: DedupeCheck }): JSX.Element {
  if (match.kind === 'listing') {
    return (
      <div className="border border-line p-4">
        <p className="text-xs text-muted">tautan ini sudah ada di katalog.</p>
        <Link
          href={`/peluang/${match.slug}`}
          className="mt-2 inline-block font-medium underline underline-offset-4"
        >
          {match.title ?? match.slug} →
        </Link>
      </div>
    )
  }
  return (
    <div className="border border-line p-4">
      <p className="text-xs text-muted">
        tautan ini sudah dicek AI dan sedang menunggu verifikasi moderator.
      </p>
      <Link
        href={`/antrean/${match.ref}`}
        className="mt-2 inline-block font-medium underline underline-offset-4"
      >
        lihat hasil pemeriksaan →
      </Link>
    </div>
  )
}

export function CheckForm(): JSX.Element {
  const router = useRouter()
  const [url, setUrl] = useState('')
  const [context, setContext] = useState('')
  const [files, setFiles] = useState<FileList | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })

  const busy = phase.kind === 'checking' || phase.kind === 'submitting'

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const trimmedUrl = url.trim()
    if (!trimmedUrl && (!files || files.length === 0)) {
      setPhase({
        kind: 'error',
        message: 'isi tautan atau unggah minimal satu berkas',
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
    for (const file of Array.from(files ?? []).slice(0, 3)) {
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

    let message = 'kiriman gagal diproses'
    if (response.status === 429) {
      message = 'terlalu sering, coba lagi sebentar lagi'
    } else {
      const body = await response.json().catch(() => null)
      if (typeof body?.detail === 'string') {
        message = body.detail
      }
    }
    setPhase({ kind: 'error', message })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <label htmlFor="url" className="block text-xs text-muted lowercase">
          tautan pengumuman.
        </label>
        <input
          id="url"
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://…"
          className="mt-2 w-full border-0 border-b border-ink bg-transparent py-2 font-mono text-base outline-none placeholder:text-muted/50 focus:border-ink"
        />
        {url && (
          <p className="mt-1 text-xs text-muted">{hostOf(url.trim())}</p>
        )}
      </div>

      <div>
        <label htmlFor="context" className="block text-xs text-muted lowercase">
          konteks tambahan <span className="text-muted/60">(opsional)</span>
        </label>
        <textarea
          id="context"
          value={context}
          onChange={(event) => setContext(event.target.value)}
          rows={3}
          maxLength={4096}
          placeholder="tempel isi poster atau catatan singkat"
          className="mt-2 w-full border border-line bg-transparent p-3 outline-none placeholder:text-muted/50 focus:border-ink"
        />
      </div>

      <div>
        <label htmlFor="files" className="block text-xs text-muted lowercase">
          poster / pdf <span className="text-muted/60">(opsional, maks 3)</span>
        </label>
        <input
          id="files"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,image/png,image/jpeg,application/pdf"
          multiple
          onChange={(event) => setFiles(event.target.files)}
          className="mt-2 w-full text-muted file:mr-4 file:border file:border-line file:bg-transparent file:px-3 file:py-1.5 file:text-xs file:text-ink hover:file:border-ink"
        />
      </div>

      {phase.kind === 'duplicate' && <DuplicateNotice match={phase.match} />}
      {phase.kind === 'error' && (
        <p className="text-sm text-bad">{phase.message}</p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="bg-ink px-4 py-2 text-paper hover:bg-ink/80 disabled:opacity-40"
      >
        {phase.kind === 'checking'
          ? 'memeriksa duplikat…'
          : phase.kind === 'submitting'
            ? 'mengirim…'
            : 'cek sekarang'}
      </button>
    </form>
  )
}
