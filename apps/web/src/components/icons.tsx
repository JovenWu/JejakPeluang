import type { JSX, ReactNode } from 'react'

export interface IconProps {
  className?: string
}

function BaseIcon({ className, children }: IconProps & { children: ReactNode }): JSX.Element {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.8}
      viewBox="0 0 24 24"
    >
      {children}
    </svg>
  )
}

export function IconShieldCheck({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <path d="M12 3l7 2.8v5.4c0 4.3-2.9 7.9-7 9.8-4.1-1.9-7-5.5-7-9.8V5.8L12 3z" />
      <path d="M9.2 11.8l2 2 3.8-3.8" />
    </BaseIcon>
  )
}

export function IconLock({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <rect height="9.5" rx="2" width="14" x="5" y="10.5" />
      <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
      <path d="M12 14.5v2" />
    </BaseIcon>
  )
}

export function IconCalendar({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <rect height="15" rx="2" width="16" x="4" y="5.5" />
      <path d="M4 10.5h16" />
      <path d="M8.5 3.5v4M15.5 3.5v4" />
    </BaseIcon>
  )
}

export function IconExternal({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <path d="M13.5 4.5H19.5V10.5" />
      <path d="M19.5 4.5L10.5 13.5" />
      <path d="M19.5 14v4.5a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5V6.5A1.5 1.5 0 0 1 6 5h4.5" />
    </BaseIcon>
  )
}

export function IconSearch({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M15.8 15.8L20 20" />
    </BaseIcon>
  )
}

export function IconAlert({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <path d="M12 4.5L20.5 19.5H3.5L12 4.5z" />
      <path d="M12 10v4.2" />
      <path d="M12 17.2v.3" />
    </BaseIcon>
  )
}

export function IconInbox({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <path d="M4.5 13.5l1.8-8h11.4l1.8 8v5A1.5 1.5 0 0 1 18 20H6a1.5 1.5 0 0 1-1.5-1.5v-5z" />
      <path d="M4.5 13.5h5l1 2h3l1-2h5" />
    </BaseIcon>
  )
}

export function IconArrowLeft({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <path d="M19.5 12H4.5" />
      <path d="M10.5 6l-6 6 6 6" />
    </BaseIcon>
  )
}

export function IconClock({ className }: IconProps): JSX.Element {
  return (
    <BaseIcon className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </BaseIcon>
  )
}

export function IconSpinner({ className }: IconProps): JSX.Element {
  return (
    <svg aria-hidden="true" className={`animate-spin motion-reduce:animate-none ${className ?? ''}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-20" cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" />
      <path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeLinecap="round" strokeWidth="2.5" />
    </svg>
  )
}
