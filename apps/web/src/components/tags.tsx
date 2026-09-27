import type { ReactNode } from 'react'

import type { Category } from '@/lib/api'
import { CATEGORY_LABEL, type DeadlineTone, deadlineInfo, formatDate } from '@/lib/format'
import { type Headline, VERDICT_LABEL, type Verdict } from '@/lib/screening'

export type Tone = 'ok' | 'bad' | 'warn' | 'mute' | 'stamp' | 'ink'

const TONE_CLASS: Record<Tone, string> = {
  ok: 'bg-ok-tint text-ok',
  bad: 'bg-bad-tint text-bad',
  warn: 'bg-warn-tint text-warn',
  mute: 'bg-mute-tint text-ink-2',
  stamp: 'bg-stamp-tint text-stamp-deep',
  ink: 'bg-ink text-paper',
}

const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-ok',
  bad: 'bg-bad',
  warn: 'bg-warn',
  mute: 'bg-ink-3',
  stamp: 'bg-stamp',
  ink: 'bg-paper',
}

interface TagProps {
  tone: Tone
  children: ReactNode
  dot?: boolean
}

export function Tag({ tone, children, dot = false }: TagProps): ReactNode {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[2px] px-1.5 py-0.5 text-xs font-semibold whitespace-nowrap ${TONE_CLASS[tone]}`}
    >
      {dot ? <span aria-hidden className={`size-1.5 rounded-full ${TONE_DOT[tone]}`} /> : null}
      {children}
    </span>
  )
}

export const VERDICT_TONE: Record<Verdict, Tone> = {
  supported: 'ok',
  conflicting: 'bad',
  not_found: 'mute',
  unreadable: 'warn',
}

export function VerdictTag({ verdict }: { verdict: Verdict }): ReactNode {
  return (
    <Tag tone={VERDICT_TONE[verdict]} dot>
      {VERDICT_LABEL[verdict]}
    </Tag>
  )
}

export const HEADLINE_TONE: Record<Headline, Tone> = {
  running: 'stamp',
  failed: 'warn',
  degraded: 'warn',
  conflict: 'bad',
  match: 'ok',
  no_official: 'mute',
}

export function CategoryLabel({ category }: { category: Category }): ReactNode {
  return <span className="kicker block text-ink-2!">{CATEGORY_LABEL[category]}</span>
}

const DEADLINE_CLASS: Record<DeadlineTone, string> = {
  closed: 'text-ink-3 line-through decoration-1',
  urgent: 'text-bad',
  soon: 'text-warn',
  open: 'text-ink-2',
  none: 'text-ink-3',
}

interface DeadlineProps {
  deadline: string | null | undefined
  showDate?: boolean
}

export function Deadline({ deadline, showDate = true }: DeadlineProps): ReactNode {
  const info = deadlineInfo(deadline)
  if (!deadline) {
    return <span className="text-ink-3">{info.label}</span>
  }
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      {showDate ? <span className="font-mono text-ink tabular-nums">{formatDate(deadline)}</span> : null}
      <span className={`text-xs font-semibold ${DEADLINE_CLASS[info.tone]}`}>{info.label}</span>
    </span>
  )
}
