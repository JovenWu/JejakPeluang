import type { ReactNode } from 'react'

interface Props {
  size?: 'sm' | 'md'
  inverse?: boolean
}

export function BrandMark({ size = 'md', inverse = false }: Props): ReactNode {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 32 32"
      className={`${size === 'sm' ? 'size-6' : 'size-8'} shrink-0 ${inverse ? 'text-paper' : 'text-stamp'}`}
      fill="none"
    >
      <rect x="1.75" y="1.75" width="28.5" height="28.5" rx="3.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M9 22.25V18.5a4.5 4.5 0 0 1 4.5-4.5h5a4.5 4.5 0 0 0 4.5-4.5V8"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="9" cy="24" r="2.25" fill="currentColor" />
      <circle cx="23" cy="7.75" r="2.25" fill="currentColor" />
    </svg>
  )
}
