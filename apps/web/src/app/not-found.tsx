import Link from 'next/link'
import type { JSX } from 'react'

import { IconArrowLeft, IconSearch } from '@/components/icons'

export default function NotFound(): JSX.Element {
  return (
    <main
      className="mx-auto flex w-full max-w-5xl flex-1 items-center px-4 py-12 sm:px-6"
      id="konten"
    >
      <section className="flex w-full flex-col items-center gap-4 rounded-xl border border-dashed border-line bg-surface px-6 py-14 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-neutral-badge text-neutral-badge-ink">
          <IconSearch className="size-6" />
        </span>
        <h1 className="text-xl">Peluang tidak ditemukan</h1>
        <p className="measure text-sm leading-relaxed text-ink-soft">
          Entri ini mungkin sudah kedaluwarsa, dihapus, atau alamatnya salah. Periksa kembali
          tautan atau telusuri katalog.
        </p>
        <Link
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary-strong px-4 py-2 text-sm font-medium text-paper transition-colors duration-150 hover:bg-primary-ink motion-reduce:transition-none"
          href="/"
        >
          <IconArrowLeft className="size-4" />
          Kembali ke katalog
        </Link>
      </section>
    </main>
  )
}
