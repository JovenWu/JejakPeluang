'use client'

import { useRouter } from 'next/navigation'
import type { FormEvent, JSX } from 'react'
import { useState } from 'react'

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
        ? 'terlalu banyak percobaan, tunggu sebentar'
        : 'email atau kata sandi salah',
    )
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div>
        <label htmlFor="email" className="block text-xs text-muted lowercase">
          email.
        </label>
        <input
          id="email"
          type="email"
          required
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1.5 w-full border-0 border-b border-line bg-transparent py-2 outline-none focus:border-ink"
        />
      </div>
      <div>
        <label htmlFor="password" className="block text-xs text-muted lowercase">
          kata sandi.
        </label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1.5 w-full border-0 border-b border-line bg-transparent py-2 outline-none focus:border-ink"
        />
      </div>
      {error && <p className="text-sm text-bad">{error}.</p>}
      <button
        type="submit"
        disabled={busy}
        className="bg-ink px-4 py-2 text-paper hover:bg-ink/80 disabled:opacity-40"
      >
        {busy ? 'memeriksa…' : 'masuk'}
      </button>
    </form>
  )
}
