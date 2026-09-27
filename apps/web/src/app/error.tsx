'use client'

import type { JSX } from 'react'

import { Eyebrow } from '@/components/ui'

export default function Error({ reset }: { reset: () => void }): JSX.Element {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-5 py-24">
      <Eyebrow>Galat</Eyebrow>
      <h1 className="font-display text-4xl font-bold tracking-[-0.02em]">
        Ada yang salah.
      </h1>
      <button
        onClick={reset}
        className="text-sm font-semibold text-accent hover:underline"
      >
        Coba lagi
      </button>
    </div>
  )
}
