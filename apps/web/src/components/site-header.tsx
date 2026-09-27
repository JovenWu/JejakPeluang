'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { JSX } from 'react'

const LINKS = [
  { href: '/peluang', label: 'Katalog' },
  { href: '/cek', label: 'Cek Peluang' },
  { href: '/status', label: 'Cek Status' },
  { href: '/antrean', label: 'Antrean' },
]

function LogoMark(): JSX.Element {
  return (
    <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-accent">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-[17px] w-[17px]"
        aria-hidden="true"
      >
        <path d="M4 12l4.5 4.5L20 6" />
        <path d="M8.5 20l2-2" opacity="0.55" />
      </svg>
    </span>
  )
}

export function SiteHeader(): JSX.Element {
  const pathname = usePathname()
  return (
    <header className="border-b border-line bg-paper">
      <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2.5">
          <LogoMark />
          <span className="font-display text-lg font-extrabold tracking-tight text-ink">
            JejakPeluang
          </span>
        </Link>
        <nav className="flex items-center gap-6">
          {LINKS.map((link) => {
            const active =
              link.href === '/peluang'
                ? pathname?.startsWith('/peluang')
                : pathname === link.href ||
                  pathname?.startsWith(`${link.href}/`)
            return (
              <Link
                key={link.href}
                href={link.href}
                className={
                  active
                    ? 'text-sm font-semibold text-accent'
                    : 'text-sm text-body hover:text-ink'
                }
              >
                {link.label}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
