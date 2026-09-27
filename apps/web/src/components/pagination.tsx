import Link from 'next/link'
import type { ReactNode } from 'react'

import { formatCount } from '@/lib/format'

interface Props {
  total: number
  offset: number
  limit: number
  shown: number
  hrefFor: (offset: number) => string
  noun: string
}

export function Pagination({ total, offset, limit, shown, hrefFor, noun }: Props): ReactNode {
  const hasPrev = offset > 0
  const hasNext = offset + shown < total
  const page = Math.floor(offset / limit) + 1
  const pages = Math.max(1, Math.ceil(total / limit))
  return (
    <nav aria-label="Halaman" className="mt-6 flex flex-wrap items-center justify-between gap-4 text-sm">
      <p className="font-mono text-xs text-ink-3" aria-live="polite">
        {shown > 0 ? `${formatCount(offset + 1)}–${formatCount(offset + shown)}` : '0'} dari {formatCount(total)} {noun}
      </p>
      {pages > 1 ? (
        <div className="flex items-center gap-2">
          {hasPrev ? (
            <Link className="btn btn-ghost min-h-10" href={hrefFor(Math.max(0, offset - limit))} rel="prev">
              ← Sebelumnya
            </Link>
          ) : null}
          <span className="px-2 font-mono text-xs text-ink-3">
            {page}/{pages}
          </span>
          {hasNext ? (
            <Link className="btn btn-ghost min-h-10" href={hrefFor(offset + limit)} rel="next">
              Berikutnya →
            </Link>
          ) : null}
        </div>
      ) : null}
    </nav>
  )
}

export function readOffset(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0
}
