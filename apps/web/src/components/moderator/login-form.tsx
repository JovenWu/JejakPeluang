'use client'

import { useRouter } from 'next/navigation'
import { type FormEvent, type ReactNode, useState } from 'react'

export function LoginForm({ initialError }: { initialError?: string }): ReactNode {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(initialError ?? null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email.trim(), password }),
      })
      if (response.status === 204) {
        router.replace('/moderator')
        router.refresh()
        return
      }
      if (response.status === 429) {
        setError('Terlalu banyak percobaan. Tunggu satu menit lalu coba lagi.')
      } else {
        setError('Email atau kata sandi salah.')
      }
    } catch {
      setError('Tidak dapat terhubung ke server.')
    }
    setBusy(false)
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {error ? (
        <p role="alert" className="rounded-[3px] bg-bad-tint px-3 py-2.5 text-sm font-medium text-bad">
          {error}
        </p>
      ) : null}
      <div>
        <label htmlFor="email" className="mb-1.5 block text-sm font-semibold">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          required
          className="field"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="password" className="mb-1.5 block text-sm font-semibold">
          Kata sandi
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          className="field"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      <button type="submit" className="btn btn-primary w-full" disabled={busy}>
        {busy ? 'Memeriksa…' : 'Masuk'}
      </button>
    </form>
  )
}
