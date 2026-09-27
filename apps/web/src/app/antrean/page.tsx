import Link from 'next/link'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import { SourceMatchBadge, VerificationBadge } from '@/components/badges'
import { Eyebrow, PAGER_BUTTON } from '@/components/ui'
import type { IncomingItem } from '@/lib/api'
import { api } from '@/lib/api'
import { formatDate, hostOf } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Antrean',
}

const PAGE_SIZE = 20

function IncomingCard({ item }: { item: IncomingItem }): JSX.Element {
  const extracted = item.screening?.extracted
  const title =
    typeof extracted?.title === 'string' && extracted.title
      ? extracted.title
      : hostOf(item.submitted_url) || item.ref
  const issuer =
    typeof extracted?.issuer === 'string' ? extracted.issuer : null
  const deadline =
    typeof extracted?.deadline === 'string' ? extracted.deadline : null
  return (
    <Link
      href={`/antrean/${item.ref}`}
      className="group flex flex-col rounded-xl border border-line bg-paper p-5 hover:border-accent"
    >
      <div className="flex flex-wrap items-center gap-2">
        <VerificationBadge verification={item.verification} />
        <SourceMatchBadge match={item.screening?.ai_source_match} />
      </div>
      <p className="mt-4 font-display text-lg font-bold leading-snug group-hover:text-accent">
        {title}
      </p>
      <p className="mt-1 text-sm text-body">{issuer ?? 'menunggu tinjauan'}</p>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-line pt-3 text-xs text-faint">
        <span className="font-mono">{item.ref}</span>
        <span>
          {deadline
            ? `tenggat ${formatDate(deadline)}`
            : `dikirim ${formatDate(item.created_at)}`}
        </span>
      </div>
    </Link>
  )
}

export default async function IncomingPage({
  searchParams,
}: {
  searchParams: Promise<{ offset?: string | string[] }>
}): Promise<JSX.Element> {
  const params = await searchParams
  const rawOffset = Array.isArray(params.offset)
    ? params.offset[0]
    : params.offset
  const offset = Math.max(0, Number.parseInt(rawOffset || '0', 10) || 0)

  const { data, error } = await api.GET('/api/v1/opportunities/incoming', {
    params: { query: { limit: PAGE_SIZE, offset } },
  })
  const items = error ? [] : (data?.items ?? [])
  const total = error ? 0 : (data?.total ?? 0)
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const page = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div>
      <section className="border-b border-line bg-surface">
        <div className="mx-auto w-full max-w-5xl px-5 py-14">
          <Eyebrow>Antrean peninjauan</Eyebrow>
          <h1 className="mt-3 max-w-xl font-display text-3xl font-bold tracking-[-0.02em] sm:text-4xl">
            Baru dicek AI, menunggu moderator.
          </h1>
          <p className="mt-3 max-w-lg leading-7 text-body">
            Kiriman terbaru yang sudah diperiksa AI terhadap sumber publik.
            Belum ditinjau manusia, jadi anggap sebagai bahan awal, bukan
            kepastian.
          </p>
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-5 py-10">
        <div className="flex items-baseline justify-between gap-4 text-xs text-faint">
          <span>
            {total > 0 ? `${total} kiriman menunggu` : 'antrean kosong'}
          </span>
          <span>diurutkan terbaru</span>
        </div>

        {items.length > 0 && (
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <IncomingCard key={item.ref} item={item} />
            ))}
          </div>
        )}

        {pages > 1 && (
          <div className="mt-8 flex items-center justify-center gap-1">
            {offset > 0 && (
              <Link
                href={`/antrean?offset=${Math.max(0, offset - PAGE_SIZE)}`}
                className={PAGER_BUTTON}
                aria-label="sebelumnya"
              >
                ‹
              </Link>
            )}
            {Array.from({ length: pages }, (_, index) => index + 1).map(
              (number) => (
                <Link
                  key={number}
                  href={`/antrean?offset=${(number - 1) * PAGE_SIZE}`}
                  className={`${PAGER_BUTTON} ${
                    number === page ? 'bg-ink font-semibold text-paper' : ''
                  }`}
                >
                  {number}
                </Link>
              ),
            )}
            {offset + PAGE_SIZE < total && (
              <Link
                href={`/antrean?offset=${offset + PAGE_SIZE}`}
                className={PAGER_BUTTON}
                aria-label="berikutnya"
              >
                ›
              </Link>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
