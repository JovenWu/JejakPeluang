import Link from 'next/link'
import type { JSX } from 'react'

export default function NotFound(): JSX.Element {
  return (
    <div className="space-y-4 pt-16">
      <h1 className="text-4xl font-semibold tracking-tight">tidak ditemukan.</h1>
      <Link href="/" className="underline underline-offset-4">
        ← kembali
      </Link>
    </div>
  )
}
