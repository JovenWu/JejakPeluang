import Link from 'next/link'
import type { ReactNode } from 'react'

import { NavLinks } from './nav-links'

export function Wordmark(): ReactNode {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid size-7 -rotate-3 place-items-center rounded-[3px] border-2 border-stamp font-mono text-[0.625rem] font-bold tracking-tight text-stamp"
      >
        JP
      </span>
      <span className="text-[1.0625rem] font-extrabold tracking-[-0.02em] text-ink">
        Jejak<span className="font-medium text-ink-2">Peluang</span>
      </span>
    </span>
  )
}

const LINKS = [
  { href: '/', label: 'Cek peluang', short: 'Cek' },
  { href: '/antrean', label: 'Antrean', short: 'Antrean' },
  { href: '/katalog', label: 'Katalog', short: 'Katalog' },
  { href: '/status', label: 'Status kiriman', short: 'Status' },
]

export function SiteHeader(): ReactNode {
  return (
    <header className="border-b border-rule bg-paper">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="-m-1 rounded-sm p-1" aria-label="JejakPeluang, beranda">
          <Wordmark />
        </Link>
        <NavLinks links={LINKS} />
      </div>
    </header>
  )
}
