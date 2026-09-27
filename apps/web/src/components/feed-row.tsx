import Link from 'next/link'
import type { ReactNode } from 'react'

import type { IncomingItem, OpportunitySummary } from '@/lib/api'
import { hostOf, relativeTime } from '@/lib/format'
import { headlineText, readExtracted, summarize } from '@/lib/screening'

import { Stamp, tierFor } from './stamp'
import { CategoryLabel, Deadline, HEADLINE_TONE, Tag } from './tags'

// Rows are one stretched link each: the title anchor's ::after covers the
// row so the whole line is clickable without nesting interactive content.
// Layout keys off the row's own width (container queries) so the same row
// works in a full-width list and in a half-width homepage column.

export function IncomingRow({ item }: { item: IncomingItem }): ReactNode {
  const summary = summarize(item.screening)
  const extracted = readExtracted(item.screening)
  const host = hostOf(item.submitted_url)
  const title = summary.title ?? (host ? `Kiriman dari ${host}` : 'Kiriman berkas')
  return (
    <li className="group @container relative border-b border-rule transition-colors hover:bg-surface">
      <div className="grid gap-x-6 gap-y-1.5 py-4 @2xl:grid-cols-[7rem_1fr_auto] @2xl:px-2">
        <p className="font-mono text-2xs text-ink-3 @2xl:pt-1 @2xl:text-xs">
          {item.ref}
          <span className="@2xl:hidden"> · {relativeTime(item.created_at)}</span>
        </p>
        <div className="min-w-0">
          <Link
            href={`/antrean/${item.ref}`}
            className="font-semibold leading-snug text-ink after:absolute after:inset-0 group-hover:underline"
          >
            {title}
          </Link>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-sm text-ink-2">
            {extracted?.issuer ? <span>{extracted.issuer}</span> : null}
            {host ? <span className="font-mono text-xs text-ink-3">{host}</span> : null}
            {extracted?.fees ? <span className="text-xs">Biaya: {extracted.fees}</span> : null}
          </p>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 @2xl:mt-0 @2xl:flex-col @2xl:items-end @2xl:gap-1.5">
          <Tag tone={HEADLINE_TONE[summary.headline]} dot>
            {headlineText(summary, item.screening)}
          </Tag>
          <span className="font-mono text-2xs text-ink-3">
            {summary.compared > 0 ? `${summary.supported}/${summary.compared} data cocok` : null}
            <span className="hidden @2xl:inline">
              {summary.compared > 0 ? ' · ' : ''}
              {relativeTime(item.created_at)}
            </span>
          </span>
        </div>
      </div>
    </li>
  )
}

export function CatalogueRow({ item }: { item: OpportunitySummary }): ReactNode {
  const host = hostOf(item.source_url)
  return (
    <li className="group @container relative border-b border-rule transition-colors hover:bg-surface">
      <div className="grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-3 py-5 @2xl:grid-cols-[1fr_12rem_auto] @2xl:px-2">
        <div className="col-span-2 min-w-0 @2xl:col-span-1">
          <CategoryLabel category={item.category} />
          <Link
            href={`/katalog/${item.slug}`}
            className="mt-0.5 block text-[1.0625rem] leading-snug font-semibold text-ink after:absolute after:inset-0 group-hover:underline"
          >
            {item.title}
          </Link>
          <p className="mt-1 flex flex-wrap gap-x-3 text-sm text-ink-2">
            <span>{item.issuer_name}</span>
            {host ? <span className="font-mono text-xs leading-5 text-ink-3">{host}</span> : null}
            {item.source_url ? null : <span className="text-xs leading-5 text-ink-3">sumber privat</span>}
          </p>
        </div>
        <div className="text-sm">
          <Deadline deadline={item.deadline} />
        </div>
        <div className="justify-self-end">
          <Stamp tier={tierFor(item.trust_basis)} date={item.verified_at} />
        </div>
      </div>
    </li>
  )
}
