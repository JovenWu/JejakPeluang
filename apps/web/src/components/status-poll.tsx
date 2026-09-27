'use client'

import Link from 'next/link'
import type { JSX } from 'react'
import { useEffect, useState } from 'react'

import { ScreeningResult } from '@/components/screening-result'
import type { SubmissionStatus } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

import { readReceiptToken } from './check-form'

const POLL_MS = 2500

const STAGES = [
  'mengambil konten',
  'mencari sumber resmi',
  'membaca halaman sumber',
  'membandingkan detail',
  'menilai kredibilitas sumber',
]

function stagedIndex(elapsedSeconds: number): number {
  // Screening runs take seconds-to-a-minute; walk stages so the UI shows
  // forward motion rather than one static spinner.
  return Math.min(Math.floor(elapsedSeconds / 4), STAGES.length - 1)
}

function Loading({ startedAt }: { startedAt: number }): JSX.Element {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const timer = setInterval(
      () => setElapsed((Date.now() - startedAt) / 1000),
      500,
    )
    return () => clearInterval(timer)
  }, [startedAt])
  const active = stagedIndex(elapsed)
  return (
    <div className="space-y-3 border border-line p-4">
      <p className="flex items-center gap-2 text-xs text-muted">
        <span className="spin-slow inline-block h-3 w-3 rounded-full border border-ink border-t-transparent" />
        memeriksa…
      </p>
      <ul className="space-y-1.5">
        {STAGES.map((stage, index) => (
          <li
            key={stage}
            className={
              index < active
                ? 'text-muted line-through'
                : index === active
                  ? 'text-ink'
                  : 'text-muted/40'
            }
          >
            {index === active ? '› ' : '  '}
            {stage}
          </li>
        ))}
      </ul>
    </div>
  )
}

function ReceiptBanner({ token }: { token: string }): JSX.Element {
  const [copied, setCopied] = useState(false)
  return (
    <div className="border border-ink p-4">
      <p className="text-xs text-muted">
        token resi, simpan untuk membuka hasil ini lagi nanti.
      </p>
      <div className="mt-2 flex items-center gap-3">
        <code className="truncate font-mono text-xs">{token}</code>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard.writeText(token)
            setCopied(true)
          }}
          className="shrink-0 border border-line px-2 py-1 text-xs hover:border-ink"
        >
          {copied ? 'tersalin' : 'salin'}
        </button>
      </div>
    </div>
  )
}

function TokenGate({ onToken }: { onToken: (token: string) => void }): JSX.Element {
  const [value, setValue] = useState('')
  return (
    <div className="space-y-3 border border-line p-4">
      <p className="text-xs text-muted">
        masukkan token resi untuk melihat hasil kiriman ini.
      </p>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (value.trim()) {
            onToken(value.trim())
          }
        }}
      >
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="token resi"
          className="w-full border-0 border-b border-line bg-transparent py-1.5 font-mono text-xs outline-none placeholder:text-muted/50 focus:border-ink"
        />
        <button className="shrink-0 border border-line px-3 text-xs hover:border-ink">
          buka
        </button>
      </form>
    </div>
  )
}

export function StatusPoll({
  refId,
  isNew,
}: {
  refId: string
  isNew: boolean
}): JSX.Element {
  const [token, setToken] = useState<string | null>(null)
  const [status, setStatus] = useState<SubmissionStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [startedAt] = useState(() => Date.now())

  useEffect(() => {
    queueMicrotask(() => setToken(readReceiptToken(refId)))
  }, [refId])

  useEffect(() => {
    if (!token) {
      return
    }
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    async function poll(): Promise<void> {
      try {
        const response = await fetch(`/api/v1/submissions/${refId}`, {
          headers: { 'X-Receipt-Token': token ?? '' },
        })
        if (response.status === 401) {
          setError('token resi tidak cocok')
          return
        }
        if (response.status === 404) {
          setError('kiriman tidak ditemukan')
          return
        }
        if (!response.ok) {
          timer = setTimeout(poll, POLL_MS)
          return
        }
        const next: SubmissionStatus = await response.json()
        if (cancelled) {
          return
        }
        setStatus(next)
        const terminal = [
          'published',
          'rejected',
          'expired',
          'closed_unreviewed',
        ].includes(next.state)
        if (!terminal) {
          timer = setTimeout(poll, POLL_MS)
        }
      } catch {
        timer = setTimeout(poll, POLL_MS)
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer) {
        clearTimeout(timer)
      }
    }
  }, [refId, token])

  if (!token) {
    return <TokenGate onToken={setToken} />
  }
  if (error) {
    return (
      <div className="space-y-4 pt-4">
        <p className="text-bad">{error}.</p>
        <Link href="/cek" className="underline underline-offset-4">
          ← cek tautan lain
        </Link>
      </div>
    )
  }

  const screening = status?.screening ?? null
  const running =
    screening == null ||
    screening.state === 'queued' ||
    screening.state === 'processing'

  return (
    <div className="space-y-8 pb-8">
      {isNew && status && <ReceiptBanner token={token} />}

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-muted">{refId}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            {status?.status_label.toLowerCase() ?? 'memuat…'}
          </h1>
        </div>
        {status && (
          <p className="text-xs text-muted">
            dikirim {formatDateTime(status.created_at)}
          </p>
        )}
      </div>

      {running && <Loading startedAt={startedAt} />}

      {screening && !running && <ScreeningResult screening={screening} />}

      {status?.state === 'published' && (
        <p className="border border-ink p-4 text-sm">
          moderator menyetujui kiriman ini dan sudah masuk{' '}
          <Link href="/peluang" className="underline underline-offset-4">
            katalog
          </Link>
          .
        </p>
      )}
      {status?.state === 'review_pending' && !running && (
        <p className="text-xs text-muted">
          kiriman ini juga tampil publik di{' '}
          <Link href={`/antrean/${refId}`} className="underline underline-offset-4">
            antrean
          </Link>{' '}
          sambil menunggu verifikasi moderator.
        </p>
      )}
      {status?.needs_more_evidence && (
        <p className="border border-line p-4 text-sm text-muted">
          moderator meminta bukti tambahan. kirim ulang lewat{' '}
          <Link href="/cek" className="underline underline-offset-4">
            cek info
          </Link>{' '}
          dengan bukti yang diminta.
        </p>
      )}
    </div>
  )
}
