'use client'

import type { JSX } from 'react'

export default function Error({ reset }: { reset: () => void }): JSX.Element {
  return (
    <div className="space-y-4 pt-16">
      <h1 className="text-4xl font-semibold tracking-tight">ada yang salah.</h1>
      <button
        onClick={reset}
        className="underline underline-offset-4 hover:text-muted"
      >
        coba lagi
      </button>
    </div>
  )
}
