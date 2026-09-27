import type { ReactNode } from 'react'

import type { TrustBasis } from '@/lib/api'
import { formatShortDate } from '@/lib/format'

type Tier = 'verified' | 'private' | 'ai'

interface Props {
  tier: Tier
  date?: string | null
  size?: 'sm' | 'lg'
  animate?: boolean
}

const TIER_TEXT: Record<Tier, { top: string; bottom: string; title: string }> = {
  verified: { top: 'Diverifikasi', bottom: 'moderator', title: 'Diverifikasi moderator terhadap sumber publik' },
  private: { top: 'Dikonfirmasi', bottom: 'penerbit', title: 'Dikonfirmasi penerbit, pengumuman privat' },
  ai: { top: 'Dicek AI', bottom: 'belum ditinjau', title: 'Dicek AI, belum diverifikasi moderator' },
}

const TIER_CLASS: Record<Tier, string> = {
  verified: 'border-stamp text-stamp border-2',
  private: 'border-stamp bg-stamp text-white border-2',
  ai: 'border-ink-3 text-ink-2 border-[1.5px] border-dashed',
}

// The stamp is the one trust mark in the UI: solid = a human checked it,
// dashed = only the AI has looked. It always carries literal claim text.
export function Stamp({ tier, date, size = 'sm', animate = false }: Props): ReactNode {
  const text = TIER_TEXT[tier]
  const sizing = size === 'lg' ? 'px-3 py-2 text-xs gap-0.5' : 'px-1.5 py-0.5 text-2xs'
  return (
    <span
      title={text.title}
      style={{ ['--stamp-rot' as string]: tier === 'ai' ? '0deg' : '-3deg' }}
      className={`inline-flex shrink-0 flex-col items-start rounded-[3px] font-mono font-semibold uppercase leading-tight tracking-[0.06em] ${sizing} ${TIER_CLASS[tier]} ${tier === 'ai' ? '' : '-rotate-3'} ${animate ? 'animate-press' : ''}`}
    >
      <span>
        {text.top}
        {size === 'sm' && date ? ` · ${formatShortDate(date)}` : ''}
      </span>
      {size === 'lg' ? (
        <>
          <span className="font-medium opacity-80">{text.bottom}</span>
          {date ? <span className="mt-1 border-t border-current pt-1 font-medium">{formatShortDate(date)}</span> : null}
        </>
      ) : (
        <span className="sr-only"> {text.bottom}</span>
      )}
    </span>
  )
}

export function tierFor(trustBasis: TrustBasis): Tier {
  return trustBasis === 'issuer_confirmed_private' ? 'private' : 'verified'
}
