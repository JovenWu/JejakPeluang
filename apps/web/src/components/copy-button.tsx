'use client'

import { type ReactNode, useState } from 'react'

interface Props {
  value: string
  label: string
  className?: string
}

export function CopyButton({ value, label, className = 'btn btn-ghost min-h-10' }: Props): ReactNode {
  const [copied, setCopied] = useState(false)

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button type="button" onClick={copy} className={className} aria-live="polite">
      {copied ? 'Tersalin ✓' : label}
    </button>
  )
}
