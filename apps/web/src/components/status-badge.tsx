import type { JSX } from 'react'

import type { Status } from '@/lib/format'
import { IconAlert, IconClock } from './icons'

export interface StatusBadgeProps {
  status: Status
}

export function StatusBadge({ status }: StatusBadgeProps): JSX.Element | null {
  if (status === 'expired') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-badge-line bg-neutral-badge px-2.5 py-1 text-sm font-medium leading-4 text-neutral-badge-ink">
        <IconClock className="size-3.5 shrink-0" />
        <span>Kedaluwarsa</span>
      </span>
    )
  }
  if (status === 'needs_review') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-caution-line bg-caution-tint px-2.5 py-1 text-sm font-medium leading-4 text-caution-ink">
        <IconAlert className="size-3.5 shrink-0" />
        <span>Perlu ditinjau</span>
      </span>
    )
  }
  return null
}
