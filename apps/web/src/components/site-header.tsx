import Link from 'next/link'
import type { JSX } from 'react'

export function SiteHeader(): JSX.Element {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-paper">
      <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4 sm:px-6">
        <Link
          className="inline-flex items-center gap-2.5 rounded-md font-display text-base font-semibold tracking-tight text-ink"
          href="/"
        >
          <svg aria-hidden="true" className="size-6" viewBox="0 0 24 24">
            <rect fill="var(--color-primary)" height="24" rx="6" width="24" />
            <path
              d="M12 5.5l4.7 1.9v3.6c0 2.9-1.95 5.3-4.7 6.6-2.75-1.3-4.7-3.7-4.7-6.6V7.4L12 5.5z"
              fill="none"
              stroke="white"
              strokeLinejoin="round"
              strokeWidth="1.4"
            />
            <path
              d="M10.1 11.6l1.4 1.4 2.6-2.6"
              fill="none"
              stroke="white"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.4"
            />
          </svg>
          <span>
            Jejak<span className="text-primary-ink">Peluang</span>
          </span>
        </Link>
        <nav aria-label="Navigasi utama" className="flex items-center gap-1 text-sm font-medium">
          <Link className="rounded-md px-3 py-2 text-ink-soft hover:bg-primary-tint hover:text-primary-ink" href="/">
            Katalog
          </Link>
          <Link className="rounded-md px-3 py-2 text-ink-soft hover:bg-primary-tint hover:text-primary-ink" href="/#verifikasi">
            Verifikasi
          </Link>
        </nav>
      </div>
    </header>
  )
}
