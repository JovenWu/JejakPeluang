'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { JSX } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { StateBadge } from '@/components/badges'
import { Eyebrow, PAGER_BUTTON } from '@/components/ui'
import type { QueueItem } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

const STATES = [
  ['review_pending', 'Menunggu peninjauan'],
  ['processing', 'Diproses'],
  ['queued', 'Dalam antrean'],
  ['published', 'Terbit'],
  ['rejected', 'Ditolak'],
  ['expired', 'Kedaluwarsa'],
  ['closed_unreviewed', 'Ditutup'],
  ['', 'Semua'],
] as const

const PAGE_SIZE = 50

export function QueueView(): JSX.Element {
  const router = useRouter()
  const [state, setState] = useState<string>('review_pending')
  const [offset, setOffset] = useState(0)
  const [items, setItems] = useState<QueueItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [me, setMe] = useState<string | null>(null)

  const load = useCallback(async () => {
    const query = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
    })
    if (state) {
      query.set('state', state)
    }
    const response = await fetch(`/api/v1/moderation/submissions?${query}`)
    if (response.status === 401 || response.status === 403) {
      router.replace('/admin/login')
      return
    }
    if (response.ok) {
      const body = await response.json()
      setItems(body.items)
      setTotal(body.total)
    }
  }, [router, state, offset])

  useEffect(() => {
    void fetch('/api/v1/users/me').then(async (response) => {
      if (!response.ok) {
        router.replace('/admin/login')
        return
      }
      setMe((await response.json()).email)
    })
  }, [router])

  useEffect(() => {
    queueMicrotask(() => void load())
  }, [load])

  async function logout(): Promise<void> {
    await fetch('/api/v1/auth/logout', { method: 'POST' })
    router.replace('/admin/login')
  }

  if (me === null && items === null) {
    return (
      <div className="mx-auto w-full max-w-5xl px-5 py-16 text-sm text-body">
        Memuat…
      </div>
    )
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Eyebrow>Antrean peninjauan</Eyebrow>
            <span className="rounded-full bg-ink px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-paper">
              moderator
            </span>
          </div>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-[-0.02em]">
            {total} kiriman menunggu
          </h1>
          <p className="mt-1 text-xs text-faint">
            diurutkan terlama dulu{me ? ` · ${me}` : ''}
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-body hover:border-ink hover:text-ink"
        >
          Keluar
        </button>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {STATES.map(([value, label]) => (
          <button
            key={value || 'all'}
            onClick={() => {
              setState(value)
              setOffset(0)
            }}
            className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ${
              state === value
                ? 'bg-ink text-paper'
                : 'border border-line text-body hover:border-ink hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-6 overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-line bg-surface text-[11px] uppercase tracking-[0.12em] text-faint">
              <th className="px-4 py-3 font-bold">Ref</th>
              <th className="px-4 py-3 font-bold">Sumber</th>
              <th className="px-4 py-3 font-bold">State</th>
              <th className="px-4 py-3 font-bold">Berkas</th>
              <th className="px-4 py-3 font-bold">Laporan</th>
              <th className="px-4 py-3 font-bold">Dikirim</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {items === null ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-body">
                  Memuat…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-body">
                  Tidak ada kiriman.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-surface/60">
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/${item.id}`}
                      className="font-mono text-xs font-semibold text-accent hover:underline"
                    >
                      {item.ref}
                    </Link>
                  </td>
                  <td className="max-w-[220px] truncate px-4 py-3 font-mono text-xs text-body">
                    {item.submitted_url_host || '(unggahan saja)'}
                  </td>
                  <td className="px-4 py-3">
                    <StateBadge state={item.state} />
                  </td>
                  <td className="px-4 py-3 text-xs text-body">
                    {item.uploads_count > 0
                      ? `${item.uploads_count} berkas`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {item.open_reports_count > 0 ? (
                      <span className="font-semibold text-bad">
                        {item.open_reports_count} laporan
                      </span>
                    ) : (
                      <span className="text-faint">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-faint">
                    {formatDateTime(item.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="mt-6 flex items-center justify-between text-xs text-faint">
          <span>
            Menampilkan {items?.length ?? 0} dari {total} kiriman
          </span>
          <div className="flex items-center gap-1">
            {offset > 0 && (
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                className={PAGER_BUTTON}
                aria-label="sebelumnya"
              >
                ‹
              </button>
            )}
            {Array.from({ length: pages }, (_, index) => index + 1).map(
              (number) => (
                <button
                  key={number}
                  onClick={() => setOffset((number - 1) * PAGE_SIZE)}
                  className={`${PAGER_BUTTON} ${
                    number === page ? 'bg-ink font-semibold text-paper' : ''
                  }`}
                >
                  {number}
                </button>
              ),
            )}
            {offset + PAGE_SIZE < total && (
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                className={PAGER_BUTTON}
                aria-label="berikutnya"
              >
                ›
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
