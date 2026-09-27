'use client'

import type { JSX } from 'react'
import { useState } from 'react'

import { REPORT_CATEGORIES } from '@/lib/format'

type Phase = 'idle' | 'sending' | 'sent' | 'error'

export function ReportForm({ slug }: { slug: string }): JSX.Element {
  const [category, setCategory] = useState('scam_suspect')
  const [description, setDescription] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault()
    setPhase('sending')
    const response = await fetch(`/api/v1/opportunities/${slug}/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category,
        description: description.trim() || null,
      }),
    })
    setPhase(response.status === 201 ? 'sent' : 'error')
  }

  if (phase === 'sent') {
    return (
      <p className="border border-line p-4 text-sm text-muted">
        laporan diterima, moderator akan meninjaunya.
      </p>
    )
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="text-xs text-muted lowercase">laporkan masalah.</p>
      <div className="flex flex-wrap gap-2">
        {Object.entries(REPORT_CATEGORIES).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setCategory(value)}
            className={`px-3 py-1 text-xs ${
              category === value
                ? 'bg-ink text-paper'
                : 'border border-line text-muted hover:border-ink hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <textarea
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        rows={2}
        maxLength={2000}
        placeholder="catatan (opsional)"
        className="w-full border border-line bg-transparent p-3 text-sm outline-none placeholder:text-muted/50 focus:border-ink"
      />
      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={phase === 'sending'}
          className="border border-ink px-3 py-1.5 text-xs hover:bg-ink hover:text-paper disabled:opacity-40"
        >
          {phase === 'sending' ? 'mengirim…' : 'kirim laporan'}
        </button>
        {phase === 'error' && (
          <p className="text-xs text-bad">gagal terkirim, coba lagi nanti</p>
        )}
      </div>
    </form>
  )
}
