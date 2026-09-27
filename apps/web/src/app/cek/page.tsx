import type { Metadata } from 'next'
import type { JSX } from 'react'

import { CheckForm } from '@/components/check-form'

export const metadata: Metadata = {
  title: 'cek info',
}

export default function CheckPage(): JSX.Element {
  return (
    <div className="space-y-8 pb-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">cek info.</h1>
        <p className="mt-2 text-muted">
          AI membaca isinya, mencari sumber resmi, lalu membandingkan detailnya.
        </p>
      </div>
      <CheckForm />
    </div>
  )
}
