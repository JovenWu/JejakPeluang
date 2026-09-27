import Link from 'next/link'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import { SourceMatchBadge, VerificationBadge } from '@/components/badges'
import type { IncomingItem } from '@/lib/api'
import { api } from '@/lib/api'
import { formatDate, hostOf } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'antrean',
}

const PAGE_SIZE = 20

function IncomingRow({ item }: { item: IncomingItem }): JSX.Element {
  const title = item.screening?.extracted?.title
  const issuer = item.screening?.extracted?.issuer
  const deadline = item.screening?.extracted?.deadline
  return (
    <li>
      <Link
        href={`/antrean/${item.ref}`}
        className="group flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-4"
      >
        <div className="min-w-0">
          <p className="font-medium group-hover:underline group-hover:underline-offset-4">
            {typeof title === 'string' && title
              ? title
              : hostOf(item.submitted_url) || item.ref}
          </p>
          <p className="mt-0.5 font-mono text-xs text-muted">
            {item.ref}
            {issuer ? ` · ${issuer}` : ''}
            {item.submitted_url ? ` · ${hostOf(item.submitted_url)}` : ''}
          </p>
        </div>
        <div className="flex items-baseline gap-4 text-xs">
          {typeof deadline === 'string' && deadline && (
            <span className="text-muted">s.d. {formatDate(deadline)}</span>
          )}
          <SourceMatchBadge match={item.screening?.ai_source_match} />
          <VerificationBadge verification={item.verification} />
        </div>
      </Link>
    </li>
  )
}

export default async function IncomingPage({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string | string[] }>
}): Promise<JSX.Element> {
  const params = await searchParams
  const rawOffset = Array.isArray(params.offset) ? params.offset[0] : params.offset
  const offset = Math.max(0, Number.parseInt(rawOffset || '0', 10) || 0)

  const { data, error } = await api.GET('/api/v1/opportunities/incoming', {
    params: { query: { limit: PAGE_SIZE, offset } },
  })
  const items = error ? [] : (data?.items ?? [])
  const total = error ? 0 : (data?.total ?? 0)

  return (
    <div className="space-y-8 pb-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">antrean.</h1>
        <p className="text-muted">
          kiriman yang sudah dicek AI dan menunggu verifikasi moderator.
        </p>
      </div>

      {items.length === 0 ? (
        <p className="text-muted">antrean kosong.</p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {items.map((item) => (
            <IncomingRow key={item.ref} item={item} />
          ))}
        </ul>
      )}

      {total > PAGE_SIZE && (
        <div className="flex justify-between text-xs text-muted">
          {offset > 0 ? (
            <Link
              href={`/antrean?offset=${Math.max(0, offset - PAGE_SIZE)}`}
              className="hover:text-ink"
            >
              ← baru
            </Link>
          ) : (
            <span />
          )}
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} dari {total}
          </span>
          {offset + PAGE_SIZE < total ? (
            <Link
              href={`/antrean?offset=${offset + PAGE_SIZE}`}
              className="hover:text-ink"
            >
              lama →
            </Link>
          ) : (
            <span />
          )}
        </div>
      )}
    </div>
  )
}
