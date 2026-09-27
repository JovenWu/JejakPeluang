import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { LoginForm } from '@/components/moderator/login-form'
import { Wordmark } from '@/components/site-header'

export const metadata: Metadata = { title: 'Masuk moderator', robots: { index: false } }

interface Props {
  searchParams: Promise<{ galat?: string }>
}

export default async function LoginPage({ searchParams }: Props): Promise<ReactNode> {
  const { galat } = await searchParams
  return (
    <main id="konten" className="grid min-h-dvh place-items-center px-4 py-12">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-10 inline-block">
          <Wordmark />
        </Link>
        <p className="kicker mb-2">Konsol moderator</p>
        <h1 className="text-2xl font-extrabold tracking-tight">Masuk untuk meninjau kiriman</h1>
        <p className="mt-2 mb-8 text-sm text-ink-2">Akun dibuat oleh operator. Tidak ada pendaftaran mandiri.</p>
        <LoginForm initialError={galat === 'peran' ? 'Akun ini bukan akun moderator.' : undefined} />
      </div>
    </main>
  )
}
