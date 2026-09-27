import type { Metadata } from 'next'
import type { JSX } from 'react'

import { StatusLookup } from '@/components/status-lookup'
import { Eyebrow } from '@/components/ui'

export const metadata: Metadata = {
  title: 'Cek status',
}

export default function StatusPage(): JSX.Element {
  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-14">
      <Eyebrow>Cek status</Eyebrow>
      <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.02em] sm:text-4xl">
        Status kiriman.
      </h1>
      <p className="mt-3 max-w-lg leading-7 text-body">
        Masukkan nomor rujukan dan token resi dari layar penerimaan.
      </p>
      <div className="mt-8">
        <StatusLookup />
      </div>
    </div>
  )
}
