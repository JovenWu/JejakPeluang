import Link from 'next/link'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import { SourceMatchBadge, VerificationBadge } from '@/components/badges'
import type { Category, OpportunitySummary } from '@/lib/api'
import { api, CATEGORIES } from '@/lib/api'
import { CATEGORY_LABELS, formatDate, hostOf } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'peluang',
}

const PAGE_SIZE = 20

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

function OpportunityRow({ item }: { item: OpportunitySummary }): JSX.Element {
  return (
    <li>
      <Link
        href={`/peluang/${item.slug}`}
        className="group flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-4"
      >
        <div className="min-w-0">
          <p className="font-medium group-hover:underline group-hover:underline-offset-4">
            {item.title}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {item.issuer_name}
            {item.source_url ? ` · ${hostOf(item.source_url)}` : ''}
          </p>
        </div>
        <div className="flex items-baseline gap-4 text-xs">
          {item.deadline && (
            <span className="text-muted">s.d. {formatDate(item.deadline)}</span>
          )}
          <SourceMatchBadge match={item.ai_source_match} />
          <VerificationBadge verification={item.verification} />
        </div>
      </Link>
    </li>
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
  const offset = Math.max(0, Number.parseInt(firstParam(params.offset) || '0', 10) || 0)

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

  function filterHref(next: { category?: string | null; q?: string; offset?: number }): string {
    const search = new URLSearchParams()
    const nextCategory = next.category === undefined ? category : next.category
    const nextQ = next.q === undefined ? q : next.q
    if (nextCategory) search.set('category', nextCategory)
    if (nextQ) search.set('q', nextQ)
    if (next.offset) search.set('offset', String(next.offset))
    const query = search.toString()
    return `/peluang${query ? `?${query}` : ''}`
  }

  return (
    <div className="space-y-8 pb-8">
      <h1 className="text-3xl font-semibold tracking-tight">peluang.</h1>

      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Link
            href={filterHref({ category: null, offset: 0 })}
            className={`px-3 py-1 text-xs ${
              category === null
                ? 'bg-ink text-paper'
                : 'border border-line text-muted hover:border-ink hover:text-ink'
            }`}
          >
            semua
          </Link>
          {CATEGORIES.map((value) => (
            <Link
              key={value}
              href={filterHref({ category: value, offset: 0 })}
              className={`px-3 py-1 text-xs ${
                category === value
                  ? 'bg-ink text-paper'
                  : 'border border-line text-muted hover:border-ink hover:text-ink'
              }`}
            >
              {CATEGORY_LABELS[value]}
            </Link>
          ))}
        </div>

        <form action="/peluang" method="get" className="flex gap-2">
          {category && <input type="hidden" name="category" value={category} />}
          <input
            name="q"
            defaultValue={q}
            placeholder="cari judul…"
            className="w-full border-0 border-b border-line bg-transparent py-1.5 outline-none placeholder:text-muted/50 focus:border-ink"
          />
          <button className="shrink-0 border border-line px-3 text-xs hover:border-ink">
            cari
          </button>
        </form>
      </div>

      {items.length === 0 ? (
        <p className="text-muted">
          belum ada peluang{q ? ` untuk &ldquo;${q}&rdquo;` : ''}.
        </p>
      ) : (
        <ul className="divide-y divide-line border-y border-line">
          {items.map((item) => (
            <OpportunityRow key={item.slug} item={item} />
          ))}
        </ul>
      )}

      {total > PAGE_SIZE && (
        <div className="flex justify-between text-xs text-muted">
          {offset > 0 ? (
            <Link
              href={filterHref({ offset: Math.max(0, offset - PAGE_SIZE) })}
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
              href={filterHref({ offset: offset + PAGE_SIZE })}
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
