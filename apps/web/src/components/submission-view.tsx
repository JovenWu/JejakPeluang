'use client'

import Link from 'next/link'
import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from 'react'

import type { SubmissionStatus } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { forgetToken, isFresh, loadToken, markSaved, saveReceipt, statusLink } from '@/lib/receipt'
import { isScreeningDone } from '@/lib/screening'

import { CopyButton } from './copy-button'
import { ScreeningPending, ScreeningReport } from './screening-report'
import { Stamp } from './stamp'

// Status polls are rate-limited to 30/hour per network, so back off
// quickly and stop after a bounded number of attempts.
const POLL_DELAYS = [2, 3, 3, 4, 5, 6, 8, 10, 12, 15, 15, 20, 20, 30]

type Phase =
  | { kind: 'init' }
  | { kind: 'need_token'; message?: string }
  | { kind: 'loaded'; status: SubmissionStatus }
  | { kind: 'error'; message: string }

const STAGES = [
  { key: 'received', label: 'Diterima' },
  { key: 'screening', label: 'Dicek AI' },
  { key: 'review', label: 'Ditinjau moderator' },
  { key: 'decision', label: 'Keputusan' },
] as const

function stageIndex(state: string, screeningDone: boolean): number {
  if (state === 'received' || state === 'queued') {
    return screeningDone ? 2 : 1
  }
  if (state === 'processing') {
    return 1
  }
  if (state === 'review_pending') {
    return 2
  }
  return 3
}

const DECISION_COPY: Record<string, { title: string; body: string }> = {
  published: {
    title: 'Disetujui dan dipublikasikan',
    body: 'Moderator memverifikasi kiriman ini dan memasukkannya ke katalog.',
  },
  rejected: {
    title: 'Tidak dipublikasikan',
    body: 'Moderator memutuskan kiriman ini tidak masuk katalog. Kami tidak menjelaskan alasan secara publik.',
  },
  expired: {
    title: 'Ditutup karena kedaluwarsa',
    body: 'Peluang ini sudah lewat atau tidak lagi berlaku.',
  },
  closed_unreviewed: {
    title: 'Ditutup tanpa peninjauan',
    body: 'Kiriman melewati batas waktu antrean sebelum sempat ditinjau.',
  },
}

function Timeline({ status }: { status: SubmissionStatus }): ReactNode {
  const current = stageIndex(status.state, isScreeningDone(status.screening))
  return (
    <ol className="grid grid-cols-4 gap-1" aria-label="Tahap kiriman">
      {STAGES.map((stage, index) => {
        const done = index < current || (index === 3 && current === 3)
        const active = index === current && index !== 3
        let bar = 'bg-rule'
        if (done) {
          bar = 'bg-ink'
        } else if (active) {
          bar = 'bg-stamp'
        }
        return (
          <li key={stage.key} aria-current={active ? 'step' : undefined}>
            <div className={`h-1 rounded-full ${bar}`} />
            <p className={`mt-2 text-xs leading-snug ${done || active ? 'font-semibold text-ink' : 'text-ink-3'}`}>
              {index === 3 && current === 3 ? status.status_label : stage.label}
            </p>
          </li>
        )
      })}
    </ol>
  )
}

interface ReceiptProps {
  refCode: string
  token: string
  onSaved: () => void
}

function ReceiptPanel({ refCode, token, onSaved }: ReceiptProps): ReactNode {
  const link = statusLink(window.location.origin, refCode, token)

  function download(): void {
    const text = [
      'JejakPeluang: resi kiriman',
      '',
      `Nomor rujukan : ${refCode}`,
      `Token resi    : ${token}`,
      '',
      'Buka tautan ini untuk melihat status (jangan dibagikan):',
      link,
      '',
      'Token hanya ditampilkan sekali dan tidak dapat dipulihkan.',
    ].join('\n')
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = href
    anchor.download = `resi-${refCode}.txt`
    anchor.click()
    URL.revokeObjectURL(href)
  }

  return (
    <section aria-labelledby="resi" className="rounded-[3px] border-2 border-ink bg-surface">
      <div className="border-b border-ink bg-ink px-4 py-2 text-paper">
        <h2 id="resi" className="text-sm font-semibold">
          Simpan resi ini. Token hanya tampil sekali.
        </h2>
      </div>
      <div className="grid gap-5 p-4 sm:grid-cols-[auto_1fr] sm:gap-8 sm:p-5">
        <div>
          <p className="kicker mb-1">Nomor rujukan</p>
          <p className="font-mono text-xl font-semibold tracking-wide">{refCode}</p>
        </div>
        <div className="min-w-0">
          <p className="kicker mb-1">Token resi</p>
          <p className="rounded-[2px] bg-sunk px-2.5 py-2 font-mono text-sm break-all select-all">{token}</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-rule px-4 py-3 sm:px-5">
        <CopyButton value={link || token} label="Salin tautan status" />
        <CopyButton value={token} label="Salin token" />
        <button type="button" className="btn btn-ghost min-h-10" onClick={download}>
          Unduh .txt
        </button>
        <button type="button" className="btn btn-primary ml-auto min-h-10" onClick={onSaved}>
          Sudah saya simpan
        </button>
      </div>
      <p className="border-t border-rule px-4 py-3 text-xs leading-relaxed text-ink-2 sm:px-5">
        Tanpa token, nomor rujukan saja tidak cukup untuk membuka hasil ini lagi. Tidak ada email atau notifikasi; halaman
        status adalah satu-satunya saluran kabar.
      </p>
    </section>
  )
}

interface TokenFormProps {
  message?: string
  onSubmit: (token: string) => void
}

function TokenForm({ message, onSubmit }: TokenFormProps): ReactNode {
  const [value, setValue] = useState('')
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (value.trim()) {
      onSubmit(value.trim())
    }
  }
  return (
    <form onSubmit={submit} className="max-w-lg space-y-3">
      <p className="text-ink-2">Masukkan token resi untuk membuka kiriman ini.</p>
      {message ? (
        <p role="alert" className="rounded-[3px] bg-bad-tint px-3 py-2 text-sm font-medium text-bad">
          {message}
        </p>
      ) : null}
      <label htmlFor="token" className="block text-sm font-semibold">
        Token resi
      </label>
      <input
        id="token"
        className="field font-mono"
        autoComplete="off"
        spellCheck={false}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <button type="submit" className="btn btn-primary">
        Buka status
      </button>
    </form>
  )
}

// A token can arrive via the URL fragment of a downloaded/bookmarked
// status link; move it into sessionStorage and strip it from the address.
function initialToken(refCode: string): string | null {
  const fromHash = new URLSearchParams(window.location.hash.slice(1)).get('token')
  if (fromHash) {
    saveReceipt(refCode, fromHash, false)
    window.history.replaceState(null, '', window.location.pathname)
  }
  return fromHash ?? loadToken(refCode)
}

// Rendered client-only (see cek/[ref]/page.tsx) so initial state can read
// sessionStorage without a hydration mismatch.
export function SubmissionView({ refCode }: { refCode: string }): ReactNode {
  const [token, setToken] = useState<string | null>(() => initialToken(refCode))
  const [phase, setPhase] = useState<Phase>(() => (token ? { kind: 'init' } : { kind: 'need_token' }))
  const [fresh, setFresh] = useState(() => isFresh(refCode))
  const [pollsLeft, setPollsLeft] = useState(true)
  const [cycle, setCycle] = useState(0)

  const fetchStatus = useCallback(
    async (currentToken: string): Promise<SubmissionStatus | null> => {
      try {
        const response = await fetch(`/api/v1/submissions/${encodeURIComponent(refCode)}`, {
          headers: { 'X-Receipt-Token': currentToken },
          cache: 'no-store',
        })
        if (response.ok) {
          const status = (await response.json()) as SubmissionStatus
          setPhase({ kind: 'loaded', status })
          return status
        }
        if (response.status === 401) {
          forgetToken(refCode)
          setToken(null)
          setPhase({ kind: 'need_token', message: 'Token tidak cocok dengan nomor rujukan ini.' })
        } else if (response.status === 404) {
          setPhase({ kind: 'error', message: `Kiriman ${refCode} tidak ditemukan. Data kiriman dihapus otomatis setelah masa simpan berakhir.` })
        } else if (response.status === 429) {
          setPhase((prev) =>
            prev.kind === 'loaded' ? prev : { kind: 'error', message: 'Terlalu sering dicek. Tunggu beberapa menit lalu muat ulang.' },
          )
          setPollsLeft(false)
        } else {
          setPhase((prev) => (prev.kind === 'loaded' ? prev : { kind: 'error', message: 'Server sedang bermasalah. Coba lagi sebentar.' }))
        }
      } catch {
        setPhase((prev) => (prev.kind === 'loaded' ? prev : { kind: 'error', message: 'Tidak dapat terhubung ke server.' }))
      }
      return null
    },
    [refCode],
  )

  useEffect(() => {
    if (!token) {
      return
    }
    let cancelled = false
    let attempt = 0
    let timer: number | undefined
    async function tick(current: string): Promise<void> {
      const status = await fetchStatus(current)
      if (cancelled || !status || isScreeningDone(status.screening)) {
        return
      }
      if (attempt >= POLL_DELAYS.length) {
        setPollsLeft(false)
        return
      }
      timer = window.setTimeout(() => void tick(current), POLL_DELAYS[attempt] * 1000)
      attempt += 1
    }
    void tick(token)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [token, cycle, fetchStatus])

  function applyToken(value: string): void {
    saveReceipt(refCode, value, false)
    setPollsLeft(true)
    setPhase({ kind: 'init' })
    setToken(value)
  }

  function refresh(): void {
    setPollsLeft(true)
    setCycle((value) => value + 1)
  }

  const status = phase.kind === 'loaded' ? phase.status : null
  const decision = status ? DECISION_COPY[status.state] : undefined
  const screeningDone = isScreeningDone(status?.screening)

  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-ink pb-5">
        <div className="min-w-0">
          <p className="kicker mb-1">Kiriman</p>
          <h1 className="font-mono text-2xl font-semibold tracking-wide break-all min-[380px]:text-3xl sm:text-4xl">{refCode}</h1>
          {status ? (
            <p className="mt-2 text-sm text-ink-2">
              {status.status_label} · dikirim {formatDateTime(status.created_at)}
            </p>
          ) : null}
        </div>
        {status && screeningDone && status.state === 'review_pending' ? <Stamp tier="ai" size="lg" /> : null}
        {status?.state === 'published' ? <Stamp tier="verified" size="lg" animate /> : null}
      </header>

      {fresh && token ? (
        <ReceiptPanel
          refCode={refCode}
          token={token}
          onSaved={() => {
            markSaved(refCode)
            setFresh(false)
          }}
        />
      ) : null}

      {phase.kind === 'init' ? <div className="scan-bar max-w-xs" aria-label="Memuat" /> : null}
      {phase.kind === 'need_token' ? <TokenForm message={phase.message} onSubmit={applyToken} /> : null}
      {phase.kind === 'error' ? (
        <div role="alert" className="max-w-xl space-y-3">
          <p className="text-ink-2">{phase.message}</p>
          <Link href="/status" className="link text-sm font-semibold">
            Cek kiriman lain
          </Link>
        </div>
      ) : null}

      {status ? (
        <>
          <Timeline status={status} />

          {decision ? (
            <section className="rounded-[3px] border border-rule bg-surface px-5 py-4">
              <h2 className="font-semibold">{decision.title}</h2>
              <p className="mt-1 text-sm text-ink-2">{decision.body}</p>
              {status.state === 'published' ? (
                <Link href="/katalog" className="link mt-2 inline-block text-sm font-semibold">
                  Buka katalog →
                </Link>
              ) : null}
            </section>
          ) : null}

          {status.needs_more_evidence ? (
            <section className="rounded-[3px] border border-warn bg-warn-tint px-5 py-4 text-sm">
              <h2 className="font-semibold text-warn">Moderator meminta bukti tambahan</h2>
              <p className="mt-1 text-ink-2">
                Kiriman ini tidak bisa diubah. Jika Anda punya poster asli, surat resmi, atau tautan dari penerbit, kirim
                sebagai{' '}
                <Link href="/" className="link font-semibold">
                  kiriman baru
                </Link>{' '}
                dan sebutkan {refCode} di kolom konteks.
              </p>
            </section>
          ) : null}

          {status.screening && screeningDone ? <ScreeningReport screening={status.screening} /> : null}
          {!screeningDone && !decision && pollsLeft ? <ScreeningPending state={status.screening?.state} /> : null}

          {!pollsLeft && !screeningDone && !decision ? (
            <p className="text-sm text-ink-2">Pemeriksaan memakan waktu lebih lama dari biasanya.</p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-5">
            <button type="button" className="btn btn-ghost" onClick={refresh}>
              Perbarui status
            </button>
            <p className="text-xs text-ink-3">Keputusan moderator bisa memakan waktu beberapa jam. Simpan resi dan kembali lagi nanti.</p>
          </div>
        </>
      ) : null}
    </div>
  )
}
