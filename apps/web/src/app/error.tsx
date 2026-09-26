'use client'

import type { JSX } from 'react'
import { useEffect } from 'react'

import { IconAlert } from '@/components/icons'

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}): JSX.Element {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <main
      className="mx-auto flex w-full max-w-5xl flex-1 items-center px-4 py-12 sm:px-6"
      id="konten"
      role="alert"
    >
      <section className="flex w-full flex-col items-center gap-4 rounded-xl border border-alert-line bg-alert-tint px-6 py-12 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-paper text-alert-ink">
          <IconAlert className="size-6" />
        </span>
        <h1 className="text-xl">Katalog belum tersedia</h1>
        <p className="measure text-sm leading-relaxed text-ink-soft">
          Terjadi gangguan saat mengambil data peluang. Silakan coba lagi dalam beberapa saat.
        </p>
        <button
          className="rounded-lg bg-primary-strong px-4 py-2 text-sm font-medium text-paper transition-colors duration-150 hover:bg-primary-ink motion-reduce:transition-none"
          onClick={reset}
          type="button"
        >
          Coba lagi
        </button>
      </section>
    </main>
  )
}
