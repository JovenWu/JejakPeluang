import Link from 'next/link'
import type { JSX } from 'react'

import { IconInbox } from './icons'

export interface EmptyStateProps {
  filtered: boolean
}

export function EmptyState({ filtered }: EmptyStateProps): JSX.Element {
  const hint = filtered
    ? 'Tidak ada hasil untuk kata kunci atau kategori ini. Coba ubah pencarian atau hapus filter.'
    : 'Entri baru akan tampil di sini setelah moderator memverifikasi sumbernya.'
  return (
    <section className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-line bg-surface px-6 py-14 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-neutral-badge text-neutral-badge-ink">
        <IconInbox className="size-6" />
      </span>
      <h2 className="text-xl">Belum ada peluang terverifikasi</h2>
      <p className="measure text-sm leading-relaxed text-ink-soft">{hint}</p>
      {filtered && (
        <Link
          className="rounded-lg border border-line bg-paper px-4 py-2 text-sm font-medium text-ink hover:border-primary-line hover:text-primary-ink"
          href="/"
        >
          Hapus filter
        </Link>
      )}
    </section>
  )
}
