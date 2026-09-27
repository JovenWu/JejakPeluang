'use client'

import { useRouter } from 'next/navigation'
import type { FormEvent, JSX } from 'react'
import { useState } from 'react'

import { BUTTON_PRIMARY, Card, CardHeader, INPUT_CLASS } from './ui'

export function LoginForm(): JSX.Element {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setBusy(true)
    setError(null)
    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    })
    setBusy(false)
    if (response.status === 204) {
      router.replace('/admin')
      return
    }
    setError(
      response.status === 429
        ? 'Terlalu banyak percobaan, tunggu sebentar.'
        : 'Nama pengguna atau kata sandi salah.',
    )
  }

  return (
    <Card>
      <CardHeader eyebrow="Masuk" />
      <form onSubmit={onSubmit} className="space-y-5 p-5">
        <label className="block">
          <span className="text-xs font-semibold">Nama pengguna</span>
          <input
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={`${INPUT_CLASS} mt-2`}
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold">Kata sandi</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className={`${INPUT_CLASS} mt-2`}
          />
        </label>
        {error && (
          <p className="rounded-lg bg-bad-tint px-4 py-3 text-sm text-bad">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className={BUTTON_PRIMARY}>
          {busy ? 'Memeriksa…' : 'Masuk'}
        </button>
      </form>
    </Card>
  )
}
