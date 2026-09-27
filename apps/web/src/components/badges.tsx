import type { JSX } from 'react'

import type { Verification } from '@/lib/api'

export function VerificationBadge({
  verification,
}: {
  verification: Verification
}): JSX.Element {
  if (verification === 'moderator_verified') {
    return (
      <span className="inline-flex items-center gap-1.5 border border-ink px-2 py-0.5 text-xs">
        <span className="inline-block h-1.5 w-1.5 bg-ink" />
        terverifikasi
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 border border-dashed border-muted px-2 py-0.5 text-xs text-muted">
      <span className="inline-block h-1.5 w-1.5 border border-muted" />
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
    return <span className="text-xs text-good">sumber resmi cocok</span>
  }
  if (match === false) {
    return (
      <span className="text-xs text-muted">sumber resmi belum cocok</span>
    )
  }
  return null
}

export function VerdictBadge({ verdict }: { verdict: string }): JSX.Element {
  const style =
    verdict === 'supported'
      ? 'text-good'
      : verdict === 'conflicting'
        ? 'text-bad'
        : 'text-muted'
  const label =
    verdict === 'supported'
      ? 'cocok'
      : verdict === 'conflicting'
        ? 'berbeda'
        : verdict === 'not_found'
          ? 'tidak ditemukan'
          : 'tak terbaca'
  return <span className={`text-xs ${style}`}>{label}</span>
}
