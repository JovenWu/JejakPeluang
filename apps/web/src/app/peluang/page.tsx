import Link from 'next/link'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import {
  CategoryBadge,
  SourceMatchBadge,
  VerificationBadge,
} from '@/components/badges'
import { Eyebrow, PAGER_BUTTON } from '@/components/ui'
import type { Category, OpportunitySummary } from '@/lib/api'
import { api, CATEGORIES } from '@/lib/api'
import { CATEGORY_LABELS, formatDate, hostOf } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Katalog peluang',
}

const PAGE_SIZE = 12

function firstParam(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value
  return raw?.trim() ?? ''
}

function parseCategory(value: string | undefined): Category | null {
  if (!value) {
    return null
  }
  return CATEGORIES.includes(value as Category) ? (value as Category) : null
}

function OpportunityCard({ item }: { item: OpportunitySummary }): JSX.Element {
  return (
    <Link
      href={`/peluang/${item.slug}`}
      className="group flex flex-col rounded-xl border border-line bg-paper p-5 hover:border-accent"
    >
      <div className="flex flex-wrap items-center gap-2">
        <CategoryBadge category={item.category} />
        <SourceMatchBadge match={item.ai_source_match} />
        {item.source_url === null && (
          <span className="rounded-full bg-surface px-2.5 py-1 text-[11px] font-semibold leading-none text-body">
            tanpa tautan publik
          </span>
        )}
      </div>
      <p className="mt-4 font-display text-lg font-bold leading-snug group-hover:text-accent">
        {item.title}
      </p>
      <p className="mt-1 text-sm text-body">{item.issuer_name}</p>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-line pt-3 text-xs text-faint">
        <span>
          {hostOf(item.source_url) || 'Indonesia'}
          {item.deadline ? ` · tenggat ${formatDate(item.deadline)}` : ''}
        </span>
        <VerificationBadge verification={item.verification} />
      </div>
    </Link>
  )
}

export default async function CataloguePage({
  searchParams,
}: {
  searchParams: Promise<{
    category?: string | string[]
    q?: string | string[]
    offset?: string | string[]
  }>
}): Promise<JSX.Element> {
  const params = await searchParams
  const category = parseCategory(firstParam(params.category) || undefined)
  const q = firstParam(params.q)
  const offset = Math.max(
    0,
    Number.parseInt(firstParam(params.offset) || '0', 10) || 0,
  )

  const { data, error } = await api.GET('/api/v1/opportunities', {
    params: {
      query: {
        category: category ?? undefined,
        q: q || undefined,
        limit: PAGE_SIZE,
        offset,
      },
    },
  })

  const items = error ? [] : (data?.items ?? [])
  const total = error ? 0 : (data?.total ?? 0)
  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function filterHref(next: {
    category?: string | null
    q?: string
    offset?: number
  }): string {
    const search = new URLSearchParams()
    const nextCategory =
      next.category === undefined ? category : next.category
    const nextQ = next.q === undefined ? q : next.q
    if (nextCategory) search.set('category', nextCategory)
    if (nextQ) search.set('q', nextQ)
    if (next.offset) search.set('offset', String(next.offset))
    const query = search.toString()
    return `/peluang${query ? `?${query}` : ''}`
  }

  return (
    <div>
      <section className="border-b border-line bg-surface">
        <div className="mx-auto w-full max-w-5xl px-5 py-14">
          <Eyebrow>Katalog peluang</Eyebrow>
          <h1 className="mt-3 max-w-xl font-display text-3xl font-bold tracking-[-0.02em] sm:text-4xl">
            Peluang yang sudah ditinjau moderator.
          </h1>
          <form
            action="/peluang"
            method="get"
            className="mt-6 flex max-w-xl items-center gap-2 rounded-xl border border-line bg-paper p-1.5 pl-4 focus-within:border-accent"
          >
            {category && (
              <input type="hidden" name="category" value={category} />
            )}
            <input
              name="q"
              defaultValue={q}
              placeholder="Cari judul peluang"
              className="w-full bg-transparent text-sm outline-none placeholder:text-faint"
            />
            <button
              type="submit"
              className="shrink-0 rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-paper hover:bg-accent/90"
            >
              Cari
            </button>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href={filterHref({ category: null, offset: 0 })}
              className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ${
                category === null
                  ? 'bg-ink text-paper'
                  : 'border border-line bg-paper text-body hover:border-ink hover:text-ink'
              }`}
            >
              Semua
            </Link>
            {CATEGORIES.map((value) => (
              <Link
                key={value}
                href={filterHref({ category: value, offset: 0 })}
                className={`rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize ${
                  category === value
                    ? 'bg-ink text-paper'
                    : 'border border-line bg-paper text-body hover:border-ink hover:text-ink'
                }`}
              >
                {CATEGORY_LABELS[value]}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-5 py-10">
        <div className="flex items-baseline justify-between gap-4 text-xs text-faint">
          <span>
            {total > 0
              ? `${total} peluang ditemukan`
              : q
                ? `tidak ada hasil untuk "${q}"`
                : 'belum ada peluang'}
          </span>
          <span>diurutkan terbaru</span>
        </div>

        {items.length > 0 && (
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <OpportunityCard key={item.slug} item={item} />
            ))}
          </div>
        )}

        {pages > 1 && (
          <div className="mt-8 flex items-center justify-center gap-1">
            {offset > 0 && (
              <Link
                href={filterHref({ offset: Math.max(0, offset - PAGE_SIZE) })}
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
                  href={filterHref({ offset: (number - 1) * PAGE_SIZE })}
                  className={`${PAGER_BUTTON} ${
                    number === page
                      ? 'bg-ink font-semibold text-paper'
                      : ''
                  }`}
                >
                  {number}
                </Link>
              ),
            )}
            {offset + PAGE_SIZE < total && (
              <Link
                href={filterHref({ offset: offset + PAGE_SIZE })}
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
