'use client'

import { useRouter } from 'next/navigation'
import { type ReactNode, useState } from 'react'

export function LogoutButton(): ReactNode {
  const router = useRouter()
  const [busy, setBusy] = useState(false)

  async function logout(): Promise<void> {
    setBusy(true)
    await fetch('/api/v1/auth/logout', { method: 'POST' }).catch(() => null)
    router.replace('/moderator/masuk')
    router.refresh()
  }

  return (
    <button
      type="button"
      onClick={logout}
      disabled={busy}
      className="min-h-9 rounded-[3px] border border-white/25 px-3 text-sm font-medium text-paper hover:border-white/60"
    >
      Keluar
    </button>
  )
}
