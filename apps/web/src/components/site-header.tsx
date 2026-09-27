import Link from 'next/link'
import type { JSX } from 'react'

const LINKS = [
  { href: '/cek', label: 'cek info' },
  { href: '/peluang', label: 'peluang' },
  { href: '/antrean', label: 'antrean' },
]

export function SiteHeader(): JSX.Element {
  return (
    <header className="mx-auto flex w-full max-w-3xl items-baseline justify-between px-5 pt-6 pb-10">
      <Link href="/" className="font-semibold tracking-tight">
        [JejakPeluang]
      </Link>
      <nav className="flex gap-4 text-muted">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className="hover:text-ink">
            [{link.label}]
          </Link>
        ))}
      </nav>
    </header>
  )
}
