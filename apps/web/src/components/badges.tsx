import type { JSX } from 'react'

import type { Category, Verification } from '@/lib/api'
import { CATEGORY_LABELS } from '@/lib/format'

const PILL = 'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none'

const CATEGORY_STYLES: Record<Category, string> = {
  scholarship: 'bg-good-tint text-good',
  internship: 'bg-accent-tint text-accent',
  competition: 'bg-ai-tint text-ai',
}

export function CategoryBadge({
  category,
}: {
  category: Category
}): JSX.Element {
  return (
    <span className={`${PILL} ${CATEGORY_STYLES[category]}`}>
      {CATEGORY_LABELS[category]}
    </span>
  )
}

function CheckIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
      className="h-2.5 w-2.5" aria-hidden="true">
      <path d="M4 12l5 5L20 6" />
    </svg>
  )
}

function SparkIcon(): JSX.Element {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-2.5 w-2.5"
      aria-hidden="true">
      <path d="M12 2l2.1 6.4L21 10l-6.9 1.6L12 18l-2.1-6.4L3 10l6.9-1.6z" />
    </svg>
  )
}

export function VerificationBadge({
  verification,
}: {
  verification: Verification
}): JSX.Element {
  if (verification === 'moderator_verified') {
    return (
      <span className={`${PILL} bg-good-tint text-good`}>
        <CheckIcon />
        terverifikasi
      </span>
    )
  }
  return (
    <span className={`${PILL} bg-ai-tint text-ai`}>
      <SparkIcon />
      dicek ai
    </span>
  )
}

export function SourceMatchBadge({
  match,
}: {
  match: boolean | null | undefined
}): JSX.Element | null {
  if (match === true) {
    return (
      <span className={`${PILL} bg-good-tint text-good`}>
        <CheckIcon />
        sumber resmi
      </span>
    )
  }
  if (match === false) {
    return (
      <span className={`${PILL} bg-surface text-body`}>
        sumber belum cocok
      </span>
    )
  }
  return null
}

const VERDICT_STYLES: Record<string, string> = {
  supported: 'bg-good-tint text-good',
  conflicting: 'bg-bad-tint text-bad',
  not_found: 'bg-surface text-faint',
  unreadable: 'bg-warn-tint text-warn-ink',
}

const VERDICT_LABELS: Record<string, string> = {
  supported: 'cocok',
  conflicting: 'berbeda',
  not_found: 'tidak ditemukan',
  unreadable: 'tak terbaca',
}

export function VerdictBadge({ verdict }: { verdict: string }): JSX.Element {
  return (
    <span
      className={`${PILL} ${VERDICT_STYLES[verdict] ?? 'bg-surface text-faint'}`}
    >
      {VERDICT_LABELS[verdict] ?? verdict}
    </span>
  )
}

const STATE_STYLES: Record<string, string> = {
  review_pending: 'bg-warn-tint text-warn-ink',
  processing: 'bg-accent-tint text-accent',
  queued: 'bg-surface text-body',
  received: 'bg-surface text-body',
  published: 'bg-good-tint text-good',
  rejected: 'bg-bad-tint text-bad',
  expired: 'bg-surface text-faint',
  closed_unreviewed: 'bg-surface text-faint',
}

const STATE_LABELS: Record<string, string> = {
  review_pending: 'menunggu peninjauan',
  processing: 'diproses',
  queued: 'dalam antrean',
  received: 'diterima',
  published: 'terbit',
  rejected: 'ditolak',
  expired: 'kedaluwarsa',
  closed_unreviewed: 'ditutup',
}

export function StateBadge({ state }: { state: string }): JSX.Element {
  return (
    <span
      className={`${PILL} ${STATE_STYLES[state] ?? 'bg-surface text-body'}`}
    >
      {STATE_LABELS[state] ?? state}
    </span>
  )
}
