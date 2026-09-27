'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'

interface Props {
  error: Error & { digest?: string }
  reset: () => void
}

export default function ErrorPage({ error, reset }: Props): ReactNode {
  return (
    <main id="konten" className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
      <div role="alert">
        <p className="kicker mb-3">Galat</p>
        <h1 className="text-3xl font-extrabold tracking-tight">Terjadi kesalahan saat memuat halaman</h1>
        <p className="mt-4 max-w-xl leading-relaxed text-ink-2">
          Server mungkin sedang sibuk. Coba lagi. Jika masalah berlanjut, kembali beberapa menit lagi.
        </p>
        {error.digest ? <p className="mt-3 font-mono text-2xs text-ink-3">kode: {error.digest}</p> : null}
      </div>
      <div className="mt-8 flex flex-wrap gap-3">
        <button type="button" onClick={reset} className="btn btn-primary">
          Coba lagi
        </button>
        <Link href="/" className="btn btn-ghost">
          Ke beranda
        </Link>
      </div>
    </main>
  )
}
