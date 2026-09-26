import type { components } from '@jejakpeluang/contracts/generated'
import Link from 'next/link'
import type { JSX } from 'react'

import { categoryLabel, deadlineCountdown, formatDate, formatDeadline, isDeadlineSoon } from '@/lib/format'
import { IconCalendar, IconExternal, IconShieldCheck } from './icons'
import { StatusBadge } from './status-badge'
import { TrustBadge } from './trust-badge'

type Opportunity = components['schemas']['OpportunitySummary']

export interface OpportunityCardProps {
  opportunity: Opportunity
  index?: number
}

export function OpportunityCard({ opportunity, index = 0 }: OpportunityCardProps): JSX.Element {
  const deadlineSoon = isDeadlineSoon(opportunity.deadline, opportunity.status)
  const deadlineText = opportunity.deadline === null
    ? 'Belum diumumkan'
    : formatDeadline(opportunity.deadline)
  const deadlineClass = deadlineSoon ? 'text-caution-ink' : 'text-ink'
  const deadlineSuffix = deadlineSoon && opportunity.deadline !== null
    ? ` (${deadlineCountdown(opportunity.deadline)})`
    : ''

  return (
    <article
      className="animate-card-in flex h-full flex-col gap-4 rounded-xl border border-line bg-surface p-5 transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-card motion-reduce:transform-none motion-reduce:transition-none"
      style={{ animationDelay: `${Math.min(index, 12) * 45}ms` }}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-ink-soft">{opportunity.issuer_name}</p>
        <span className="shrink-0 rounded-md border border-line bg-paper px-2 py-0.5 text-sm font-medium text-ink-soft">
          {categoryLabel(opportunity.category)}
        </span>
      </div>
      <h2 className="text-lg leading-snug">
        <Link
          className="text-ink decoration-primary/40 underline-offset-4 hover:text-primary-ink hover:underline"
          href={`/opportunities/${opportunity.slug}`}
        >
          {opportunity.title}
        </Link>
      </h2>
      <dl className="grid gap-1.5 text-sm">
        <div className="flex items-center gap-2">
          <dt className="inline-flex items-center gap-1.5 text-ink-soft">
            <IconCalendar className="size-4 shrink-0" />
            Tenggat
          </dt>
          <dd className={`font-medium ${deadlineClass}`}>{deadlineText}{deadlineSuffix}</dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="inline-flex items-center gap-1.5 text-ink-soft">
            <IconShieldCheck className="size-4 shrink-0" />
            Diperiksa
          </dt>
          <dd className="text-ink">{formatDate(opportunity.checked_at)}</dd>
        </div>
      </dl>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-line pt-3">
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <TrustBadge basis={opportunity.trust_basis} />
          <StatusBadge status={opportunity.status} />
        </span>
        {opportunity.source_url && (
          <a
            className="inline-flex items-center gap-1 text-sm font-medium text-primary-ink underline decoration-primary/30 underline-offset-4 hover:decoration-primary-ink"
            href={opportunity.source_url}
            rel="noopener noreferrer"
            target="_blank"
          >
            Sumber asli
            <IconExternal className="size-3.5 shrink-0" />
          </a>
        )}
      </div>
    </article>
  )
}
