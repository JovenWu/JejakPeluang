import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { LogoutButton } from '@/components/moderator/logout-button'
import { requireModerator } from '@/lib/moderator'

export const metadata: Metadata = { robots: { index: false } }
export const dynamic = 'force-dynamic'

interface Props {
  children: ReactNode
}

export default async function ConsoleLayout({ children }: Props): Promise<ReactNode> {
  const user = await requireModerator()
  return (
    <>
      <header className="bg-ink text-paper">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-2.5 sm:px-6">
          <div className="flex items-center gap-5">
            <Link href="/moderator" className="flex items-center gap-2.5 font-extrabold tracking-tight">
              <BrandMark size="sm" inverse />
              Konsol moderator
            </Link>
            <Link href="/" className="hidden text-sm text-paper/70 hover:text-paper sm:inline">
              Situs publik ↗
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-paper/70">{user.email}</span>
            <LogoutButton />
          </div>
        </div>
      </header>
      <main id="konten" className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        {children}
      </main>
    </>
  )
}
