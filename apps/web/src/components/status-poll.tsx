'use client'

import Link from 'next/link'
import type { JSX } from 'react'
import { useEffect, useState } from 'react'

import { ScreeningResult } from '@/components/screening-result'
import { StateBadge } from '@/components/badges'
import type { SubmissionStatus } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

import { readReceiptToken, storeReceiptToken } from './check-form'
import { BUTTON_PRIMARY, Card, CardHeader, INPUT_CLASS } from './ui'

const POLL_MS = 2500

const STAGES = [
  'Mengambil konten',
  'Mencari sumber resmi',
  'Membaca halaman sumber',
  'Membandingkan detail',
  'Menilai kredibilitas sumber',
]

function stagedIndex(elapsedSeconds: number): number {
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
    <Card>
      <CardHeader
        eyebrow="Pemeriksaan berjalan"
        hint="biasanya kurang dari satu menit"
      />
      <ul className="space-y-3 p-5">
        {STAGES.map((stage, index) => (
          <li key={stage} className="flex items-center gap-3 text-sm">
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                index < active
                  ? 'border-good bg-good text-paper'
                  : index === active
                    ? 'border-accent text-accent'
                    : 'border-line text-transparent'
              }`}
            >
              {index < active ? (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="3" strokeLinecap="round" className="h-3 w-3">
                  <path d="M4 12l5 5L20 6" />
                </svg>
              ) : index === active ? (
                <span className="spin-slow h-2.5 w-2.5 rounded-full border border-accent border-t-transparent" />
              ) : (
                '·'
              )}
            </span>
            <span className={index <= active ? 'text-ink' : 'text-faint'}>
              {stage}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function ReceiptBanner({
  refId,
  token,
}: {
  refId: string
  token: string
}): JSX.Element {
  const [copied, setCopied] = useState(false)
  return (
    <Card className="border-ink/20">
      <CardHeader
        eyebrow="Token resi, hanya tampil sekali"
        hint="simpan sekarang"
      />
      <div className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
            Nomor rujukan
          </p>
          <p className="mt-1 font-mono text-lg font-semibold">{refId}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
            Token resi
          </p>
          <p className="mt-1 break-all font-mono text-sm">{token}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard.writeText(token)
              setCopied(true)
            }}
            className={BUTTON_PRIMARY}
          >
            {copied ? 'Tersalin' : 'Salin token'}
          </button>
          <a
            href={`data:text/plain,${encodeURIComponent(
              `JejakPeluang\nref: ${refId}\ntoken: ${token}\n`,
            )}`}
            download={`jejakpeluang-${refId}.txt`}
            className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-body hover:border-ink hover:text-ink"
          >
            Unduh .txt
          </a>
        </div>
        <p className="text-xs leading-5 text-faint">
          Token tidak dapat dipulihkan, kami hanya menyimpan hash-nya. Tanpa
          token, nomor rujukan saja tidak cukup untuk membuka hasil.
        </p>
      </div>
    </Card>
  )
}

function TokenGate({
  refId,
  onToken,
}: {
  refId: string
  onToken: (token: string) => void
}): JSX.Element {
  const [value, setValue] = useState('')
  return (
    <Card>
      <CardHeader eyebrow="Masukkan token resi" />
      <form
        className="space-y-4 p-5"
        onSubmit={(event) => {
          event.preventDefault()
          if (value.trim()) {
            onToken(value.trim())
          }
        }}
      >
        <p className="text-sm text-body">
          Token diberikan sekali saat kiriman diterima. Nomor rujukan ini:{' '}
          <span className="font-mono text-xs">{refId}</span>
        </p>
        <div className="flex gap-2">
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Token resi"
            className={`${INPUT_CLASS} font-mono text-xs`}
          />
          <button type="submit" className={`${BUTTON_PRIMARY} shrink-0`}>
            Buka
          </button>
        </div>
      </form>
    </Card>
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
          setError('Token resi tidak cocok.')
          return
        }
        if (response.status === 404) {
          setError('Kiriman tidak ditemukan.')
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
    return (
      <div className="mx-auto w-full max-w-3xl px-5 py-14">
        <TokenGate
          refId={refId}
          onToken={(value) => {
            storeReceiptToken(refId, value)
            setToken(value)
          }}
        />
      </div>
    )
  }
  if (error) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 px-5 py-14">
        <p className="rounded-lg bg-bad-tint px-4 py-3 text-sm text-bad">
          {error}
        </p>
        <Link href="/cek" className="text-sm text-accent hover:underline">
          Cek tautan lain
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
    <div className="mx-auto w-full max-w-3xl space-y-8 px-5 py-14">
      {isNew && <ReceiptBanner refId={refId} token={token} />}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-faint">{refId}</p>
          <h1 className="mt-1 font-display text-3xl font-bold tracking-[-0.02em]">
            {status?.status_label ?? 'Memuat…'}
          </h1>
        </div>
        {status && (
          <div className="flex flex-col items-end gap-1.5">
            <StateBadge state={status.state} />
            <p className="text-xs text-faint">
              dikirim {formatDateTime(status.created_at)}
            </p>
          </div>
        )}
      </div>

      {running && <Loading startedAt={startedAt} />}

      {screening && !running && <ScreeningResult screening={screening} />}

      {status?.state === 'published' && (
        <Card className="border-good/30 bg-good-tint/40 p-5">
          <p className="text-sm font-medium text-good">
            Moderator menyetujui kiriman ini.
          </p>
          <p className="mt-1 text-sm text-body">
            Sudah masuk{' '}
            <Link href="/peluang" className="text-accent hover:underline">
              katalog
            </Link>{' '}
            sebagai peluang terverifikasi.
          </p>
        </Card>
      )}
      {status?.state === 'review_pending' && !running && (
        <p className="text-xs leading-5 text-faint">
          Kiriman ini juga tampil publik di{' '}
          <Link
            href={`/antrean/${refId}`}
            className="text-accent hover:underline"
          >
            antrean
          </Link>{' '}
          sambil menunggu verifikasi moderator.
        </p>
      )}
      {status?.needs_more_evidence && (
        <Card className="border-warn/30 bg-warn-tint/40 p-5">
          <p className="text-sm font-medium text-warn-ink">
            Moderator meminta bukti tambahan.
          </p>
          <p className="mt-1 text-sm text-body">
            Tidak ada kanal unggah ulang. Kirim informasi baru lewat{' '}
            <Link href="/cek" className="text-accent hover:underline">
              formulir cek
            </Link>{' '}
            dengan bukti yang diminta.
          </p>
        </Card>
      )}
      <p className="text-xs leading-5 text-faint">
        Halaman ini satu-satunya saluran pembaruan, tidak ada email atau
        notifikasi.
      </p>
    </div>
  )
}
