import type { components } from '@jejakpeluang/contracts/generated'
import type { JSX } from 'react'

import { IconLock, IconShieldCheck } from './icons'

type TrustBasis = components['schemas']['OpportunitySummary']['trust_basis']

export interface TrustBadgeProps {
  basis: TrustBasis
}

export function TrustBadge({ basis }: TrustBadgeProps): JSX.Element {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-primary-line bg-primary-tint px-2.5 py-1 text-sm font-medium leading-4 text-primary-ink">
        <IconShieldCheck className="size-3.5 shrink-0" />
        <span>Diverifikasi moderator</span>
      </span>
      {basis === 'issuer_confirmed_private' && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-neutral-badge-line bg-neutral-badge px-2.5 py-1 text-sm font-medium leading-4 text-neutral-badge-ink">
          <IconLock className="size-3.5 shrink-0" />
          <span>Dikonfirmasi penerbit - pengumuman privat</span>
        </span>
      )}
    </span>
  )
}
