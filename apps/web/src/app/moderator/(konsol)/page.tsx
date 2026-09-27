import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { LoadError } from '@/components/load-error'
import { StateTag } from '@/components/moderator/state-tag'
import { Pagination, readOffset } from '@/components/pagination'
import { formatCount, formatDateTime, relativeTime } from '@/lib/format'
import { moderatorApi } from '@/lib/moderator'

export const metadata: Metadata = { title: 'Antrean moderasi' }

const LIMIT = 25

const FILTERS = [
  { value: 'review_pending', label: 'Perlu ditinjau' },
  { value: 'processing', label: 'Diproses AI' },
  { value: 'queued', label: 'Antre AI' },
  { value: 'published', label: 'Dipublikasikan' },
  { value: 'rejected', label: 'Ditolak' },
  { value: 'all', label: 'Semua' },
]

interface Props {
  searchParams: Promise<{ state?: string; offset?: string }>
}

function hrefFor(state: string, offset = 0): string {
  const params = new URLSearchParams()
  if (state !== 'review_pending') {
    params.set('state', state)
  }
  if (offset) {
    params.set('offset', String(offset))
  }
  const query = params.toString()
  return query ? `/moderator?${query}` : '/moderator'
}

export default async function QueuePage({ searchParams }: Props): Promise<ReactNode> {
  const raw = await searchParams
  const state = FILTERS.some((filter) => filter.value === raw.state) ? (raw.state as string) : 'review_pending'
  const offset = readOffset(raw.offset)
  const client = await moderatorApi()
  const { data } = await client
    .GET('/api/v1/moderation/submissions', {
      params: { query: { state: state === 'all' ? undefined : state, limit: LIMIT, offset } },
    })
    .catch(() => ({ data: undefined }))

  return (
    <>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Antrean moderasi</h1>
          <p className="mt-1 text-sm text-ink-2">
            {data ? `${formatCount(data.total)} kiriman · ` : ''}terlama di atas. AI hanya menyiapkan bukti; keputusan ada
            di tangan Anda.
          </p>
        </div>
      </header>

      <nav aria-label="Filter status" className="mb-4 border-b border-rule">
        <ul className="-mb-px flex overflow-x-auto">
          {FILTERS.map((filter) => {
            const active = filter.value === state
            return (
              <li key={filter.value}>
                <Link
                  href={hrefFor(filter.value)}
                  aria-current={active ? 'page' : undefined}
                  className={`flex min-h-11 items-center border-b-2 px-3.5 text-sm font-medium whitespace-nowrap ${
                    active ? 'border-stamp text-ink' : 'border-transparent text-ink-2 hover:text-ink'
                  }`}
                >
                  {filter.label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {data ? (
        <>
          {data.items.length > 0 ? (
            <div className="overflow-x-auto rounded-[3px] border border-rule bg-surface">
              <table className="w-full min-w-[46rem] text-sm">
                <thead>
                  <tr className="border-b border-rule text-left">
                    <th scope="col" className="kicker px-4 py-2.5 font-normal">Ref</th>
                    <th scope="col" className="kicker px-4 py-2.5 font-normal">Sumber</th>
                    <th scope="col" className="kicker px-4 py-2.5 font-normal">Status</th>
                    <th scope="col" className="kicker px-4 py-2.5 text-right font-normal">Berkas</th>
                    <th scope="col" className="kicker px-4 py-2.5 font-normal">Kontak</th>
                    <th scope="col" className="kicker px-4 py-2.5 font-normal">Laporan</th>
                    <th scope="col" className="kicker px-4 py-2.5 text-right font-normal">Masuk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {data.items.map((item) => (
                    <tr key={item.id} className="group relative hover:bg-paper">
                      <td className="px-4 py-3">
                        <Link
                          href={`/moderator/${item.id}`}
                          className="font-mono font-semibold text-ink after:absolute after:inset-0 group-hover:underline"
                        >
                          {item.ref}
                        </Link>
                      </td>
                      <td className="max-w-56 truncate px-4 py-3 font-mono text-xs">
                        {item.submitted_url_host ?? <span className="font-sans text-ink-3">hanya berkas</span>}
                      </td>
                      <td className="px-4 py-3">
                        <StateTag state={item.state} />
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {item.uploads_count || <span className="text-ink-3">-</span>}
                      </td>
                      <td className="px-4 py-3">{item.has_contact_email ? 'Ada email' : <span className="text-ink-3">-</span>}</td>
                      <td className="px-4 py-3">
                        {item.open_reports_count > 0 ? (
                          <span className="font-semibold text-bad">{item.open_reports_count} terbuka</span>
                        ) : (
                          <span className="text-ink-3">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap" title={formatDateTime(item.created_at)}>
                        {relativeTime(item.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-[3px] border border-dashed border-rule-2 py-16 text-center">
              <p className="font-semibold">Tidak ada kiriman di sini.</p>
              <p className="mt-1 text-sm text-ink-2">
                {state === 'review_pending' ? 'Antrean bersih. Semua kiriman sudah ditinjau.' : 'Coba filter lain.'}
              </p>
            </div>
          )}
          <Pagination
            total={data.total}
            offset={offset}
            limit={LIMIT}
            shown={data.items.length}
            noun="kiriman"
            hrefFor={(next) => hrefFor(state, next)}
          />
        </>
      ) : (
        <LoadError what="Antrean" />
      )}
    </>
  )
}
