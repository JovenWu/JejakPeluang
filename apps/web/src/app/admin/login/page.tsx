import type { Metadata } from 'next'
import type { JSX } from 'react'

import { LoginForm } from '@/components/login-form'
import { Eyebrow } from '@/components/ui'

export const metadata: Metadata = {
  title: 'Konsol moderator',
  robots: { index: false, follow: false },
}

export default function AdminLoginPage(): JSX.Element {
  return (
    <div className="mx-auto flex w-full max-w-sm flex-col justify-center px-5 py-24">
      <Eyebrow>Konsol moderator</Eyebrow>
      <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.02em]">
        Akses khusus tim peninjau.
      </h1>
      <div className="mt-8">
        <LoginForm />
      </div>
      <p className="mt-6 text-xs leading-5 text-faint">
        Tidak ada pendaftaran, akun dibuat oleh operator.
      </p>
    </div>
  )
}
