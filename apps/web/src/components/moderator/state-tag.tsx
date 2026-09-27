import type { ReactNode } from 'react'

import { Tag, type Tone } from '../tags'

export const STATE_LABEL: Record<string, string> = {
  received: 'Diterima',
  queued: 'Antre AI',
  processing: 'Diproses AI',
  review_pending: 'Menunggu tinjauan',
  published: 'Dipublikasikan',
  rejected: 'Ditolak',
  expired: 'Kedaluwarsa',
  closed_unreviewed: 'Ditutup',
}

const STATE_TONE: Record<string, Tone> = {
  received: 'mute',
  queued: 'mute',
  processing: 'stamp',
  review_pending: 'warn',
  published: 'ok',
  rejected: 'bad',
  expired: 'mute',
  closed_unreviewed: 'mute',
}

export const TERMINAL_STATES = new Set(['published', 'rejected', 'expired', 'closed_unreviewed'])

export function StateTag({ state }: { state: string }): ReactNode {
  return (
    <Tag tone={STATE_TONE[state] ?? 'mute'} dot>
      {STATE_LABEL[state] ?? state}
    </Tag>
  )
}
