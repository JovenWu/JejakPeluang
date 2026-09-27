'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { JSX } from 'react'
import { useCallback, useEffect, useState } from 'react'

import type { QueueItem } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

const STATES = [
  ['review_pending', 'menunggu'],
  ['received', 'diterima'],
  ['queued', 'antre'],
  ['processing', 'diproses'],
  ['published', 'terbit'],
  ['rejected', 'ditolak'],
  ['expired', 'lewat'],
  ['closed_unreviewed', 'ditutup'],
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
    return <p className="pt-16 text-muted">memuat…</p>
  }

  return (
    <div className="space-y-8 pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            antrean moderator.
          </h1>
          <p className="mt-1 text-xs text-muted">{me}</p>
        </div>
        <button
          onClick={logout}
          className="text-xs text-muted underline underline-offset-4 hover:text-ink"
        >
          keluar
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATES.map(([value, label]) => (
          <button
            key={value}
            onClick={() => {
              setState(value)
              setOffset(0)
            }}
            className={`px-3 py-1 text-xs ${
              state === value
                ? 'bg-ink text-paper'
                : 'border border-line text-muted hover:border-ink hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {items === null ? (
        <p className="text-muted">memuat…</p>
      ) : items.length === 0 ? (
        <p className="text-muted">tidak ada kiriman.</p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/admin/${item.id}`}
                className="group flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-3"
              >
                <div className="min-w-0">
                  <span className="font-mono text-xs">{item.ref}</span>
                  {item.submitted_url_host && (
                    <span className="ml-3 text-xs text-muted">
                      {item.submitted_url_host}
                    </span>
                  )}
                  <p className="mt-0.5 text-xs text-muted">
                    {item.uploads_count > 0 && `${item.uploads_count} berkas · `}
                    {item.has_contact_email && 'ada email · '}
                    {formatDateTime(item.created_at)}
                  </p>
                </div>
                <div className="flex items-baseline gap-3 text-xs">
                  {item.open_reports_count > 0 && (
                    <span className="text-bad">
                      {item.open_reports_count} laporan
                    </span>
                  )}
                  <span className="text-muted group-hover:text-ink">→</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {total > PAGE_SIZE && (
        <div className="flex justify-between text-xs text-muted">
          {offset > 0 ? (
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="hover:text-ink"
            >
              ← sebelumnya
            </button>
          ) : (
            <span />
          )}
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} dari {total}
          </span>
          {offset + PAGE_SIZE < total ? (
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="hover:text-ink"
            >
              berikutnya →
            </button>
          ) : (
            <span />
          )}
        </div>
      )}
    </div>
  )
}
