'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'

interface Props {
  links: { href: string; label: string; short: string }[]
}

function isActive(pathname: string, href: string): boolean {
  if (href === '/') {
    return pathname === '/' || pathname.startsWith('/cek')
  }
  return pathname === href || pathname.startsWith(`${href}/`)
}

export function NavLinks({ links }: Props): ReactNode {
  const pathname = usePathname()
  return (
    <nav aria-label="Navigasi utama" className="w-full sm:w-auto">
      <ul className="-mx-2 grid grid-cols-4 sm:mx-0 sm:flex sm:items-center">
        {links.map((link) => {
          const active = isActive(pathname, link.href)
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={active ? 'page' : undefined}
                className={`relative flex min-h-11 items-center justify-center px-2 text-sm font-medium whitespace-nowrap transition-colors sm:px-2.5 ${
                  active ? 'text-ink after:absolute after:inset-x-2 after:bottom-1.5 after:h-0.5 after:bg-stamp' : 'text-ink-2 hover:text-ink'
                }`}
              >
                <span className="sm:hidden">{link.short}</span>
                <span className="hidden sm:inline">{link.label}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
