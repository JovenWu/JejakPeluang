'use client'

import { useRouter } from 'next/navigation'
import { type FormEvent, type ReactNode, useState } from 'react'

import { normalizeRef, saveReceipt } from '@/lib/receipt'

export function StatusLookup(): ReactNode {
  const router = useRouter()
  const [ref, setRef] = useState('')
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (!ref.trim() || !token.trim()) {
      setError('Isi nomor rujukan dan token resi.')
      return
    }
    const normalized = normalizeRef(ref)
    saveReceipt(normalized, token.trim(), false)
    router.push(`/cek/${normalized}`)
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <div>
        <label htmlFor="ref" className="mb-1.5 block text-sm font-semibold">
          Nomor rujukan
        </label>
        <input
          id="ref"
          className="field font-mono uppercase"
          placeholder="JP-XXXXXXXX"
          autoComplete="off"
          spellCheck={false}
          value={ref}
          onChange={(event) => setRef(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="token" className="mb-1.5 block text-sm font-semibold">
          Token resi
        </label>
        <input
          id="token"
          className="field font-mono"
          autoComplete="off"
          spellCheck={false}
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
      </div>
      {error ? (
        <p role="alert" className="text-sm font-medium text-bad">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn btn-primary">
        Lihat status
      </button>
    </form>
  )
}
