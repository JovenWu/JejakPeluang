import type { Metadata } from 'next'
import type { JSX } from 'react'

import { LoginForm } from '@/components/login-form'

export const metadata: Metadata = {
  title: 'masuk',
  robots: { index: false, follow: false },
}

export default function AdminLoginPage(): JSX.Element {
  return (
    <div className="mx-auto max-w-sm space-y-8 pt-24">
      <h1 className="text-3xl font-semibold tracking-tight">masuk.</h1>
      <LoginForm />
    </div>
  )
}
