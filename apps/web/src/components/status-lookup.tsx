'use client'

import { useRouter } from 'next/navigation'
import type { FormEvent, JSX } from 'react'
import { useState } from 'react'

import { storeReceiptToken } from './check-form'
import { BUTTON_PRIMARY, Card, CardHeader, INPUT_CLASS } from './ui'

export function StatusLookup(): JSX.Element {
  const router = useRouter()
  const [ref, setRef] = useState('')
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    const cleanRef = ref.trim().toUpperCase()
    const cleanToken = token.trim()
    if (!cleanRef || !cleanToken) {
      setError('Isi nomor rujukan dan token resi.')
      return
    }
    storeReceiptToken(cleanRef, cleanToken)
    router.push(`/cek/${cleanRef}`)
  }

  return (
    <Card>
      <CardHeader eyebrow="Buka kiriman" />
      <form onSubmit={onSubmit} className="space-y-5 p-5 sm:p-6">
        <label className="block">
          <span className="text-xs font-semibold">Nomor rujukan</span>
          <input
            value={ref}
            onChange={(event) => setRef(event.target.value)}
            placeholder="JP-…"
            className={`${INPUT_CLASS} mt-2 font-mono`}
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold">Token resi</span>
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Token dari layar penerimaan"
            className={`${INPUT_CLASS} mt-2 font-mono text-xs`}
          />
        </label>
        {error && (
          <p className="rounded-lg bg-bad-tint px-4 py-3 text-sm text-bad">
            {error}
          </p>
        )}
        <button type="submit" className={BUTTON_PRIMARY}>
          Lihat status
        </button>
      </form>
    </Card>
  )
}
