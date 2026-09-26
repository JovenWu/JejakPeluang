import type { JSX } from 'react'

import { IconSpinner } from '@/components/icons'

export default function Loading(): JSX.Element {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-10" id="konten">
      <p className="inline-flex items-center gap-2 text-sm font-medium text-ink-soft" role="status">
        <IconSpinner className="size-4 text-primary-ink" />
        Memuat peluang...
      </p>
      <div
        aria-hidden="true"
        className="mt-8 grid grid-cols-[repeat(auto-fit,minmax(min(100%,17rem),1fr))] gap-4 sm:gap-5"
      >
        {[0, 1, 2, 3, 4, 5].map((slot) => (
          <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5" key={slot}>
            <div className="h-4 w-2/5 animate-pulse rounded bg-line motion-reduce:animate-none" />
            <div className="h-5 w-4/5 animate-pulse rounded bg-line motion-reduce:animate-none" />
            <div className="h-4 w-3/5 animate-pulse rounded bg-line motion-reduce:animate-none" />
            <div className="h-7 w-1/2 animate-pulse rounded-full bg-line motion-reduce:animate-none" />
          </div>
        ))}
      </div>
    </main>
  )
}
