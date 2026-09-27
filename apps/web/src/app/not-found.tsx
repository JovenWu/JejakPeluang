import Link from 'next/link'
import type { ReactNode } from 'react'

import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'

export default function NotFound(): ReactNode {
  return (
    <>
      <SiteHeader />
      <main id="konten" className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <p className="kicker mb-3">404</p>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Halaman ini tidak ada di arsip kami</h1>
        <p className="mt-4 max-w-xl leading-relaxed text-ink-2">
          Mungkin tautannya salah ketik, atau entri katalog sudah dipindahkan. Anda bisa mencari di katalog atau memeriksa
          sebuah info peluang dari awal.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/katalog" className="btn btn-primary">
            Buka katalog
          </Link>
          <Link href="/" className="btn btn-ghost">
            Cek sebuah peluang
          </Link>
        </div>
      </main>
      <SiteFooter />
    </>
  )
}
