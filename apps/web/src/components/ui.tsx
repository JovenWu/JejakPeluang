import type { JSX, ReactNode } from 'react'

export function Eyebrow({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p className="text-xs font-bold uppercase tracking-[0.15em] text-body">
      {children}
    </p>
  )
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}): JSX.Element {
  return (
    <div className={`rounded-xl border border-line bg-paper ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({
  eyebrow,
  hint,
}: {
  eyebrow: ReactNode
  hint?: ReactNode
}): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-3">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-body">
        {eyebrow}
      </p>
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </div>
  )
}

export const INPUT_CLASS =
  'w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm outline-none placeholder:text-faint focus:border-accent'

export const BUTTON_PRIMARY =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-paper hover:bg-accent/90 disabled:opacity-40'

export const BUTTON_GHOST =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-line px-4 py-2 text-sm font-medium text-body hover:border-ink hover:text-ink'

export const PAGER_BUTTON =
  'inline-flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-sm text-body hover:bg-surface'
