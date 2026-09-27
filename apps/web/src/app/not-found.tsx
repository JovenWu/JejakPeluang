import Link from 'next/link'
import type { JSX } from 'react'

import { Eyebrow } from '@/components/ui'

export default function NotFound(): JSX.Element {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-5 py-24">
      <Eyebrow>404</Eyebrow>
      <h1 className="font-display text-4xl font-bold tracking-[-0.02em]">
        Halaman tidak ditemukan.
      </h1>
      <Link href="/" className="inline-block text-sm font-semibold text-accent hover:underline">
        Kembali ke beranda
      </Link>
    </div>
  )
}
