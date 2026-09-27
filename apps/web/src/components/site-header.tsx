import Link from 'next/link'
import type { ReactNode } from 'react'

import { BrandMark } from './brand-mark'
import { NavLinks } from './nav-links'

export function Wordmark(): ReactNode {
  return (
    <span className="inline-flex items-center gap-2.5">
      <BrandMark />
      <span className="text-[1.0625rem] font-extrabold tracking-[-0.035em] text-ink">
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
