'use client'

import type { JSX } from 'react'
import { useState } from 'react'

import { BUTTON_PRIMARY, INPUT_CLASS } from '@/components/ui'
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
      <p className="rounded-lg bg-good-tint px-4 py-3 text-sm text-good">
        Laporan diterima. Moderator akan meninjaunya tanpa mengubah status
        listing.
      </p>
    )
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {Object.entries(REPORT_CATEGORIES).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setCategory(value)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-semibold capitalize ${
              category === value
                ? 'bg-ink text-paper'
                : 'border border-line text-body hover:border-ink hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <textarea
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        rows={3}
        maxLength={2000}
        placeholder="Ceritakan masalahnya, opsional."
        className={INPUT_CLASS}
      />
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          disabled={phase === 'sending'}
          className={BUTTON_PRIMARY}
        >
          {phase === 'sending' ? 'Mengirim…' : 'Kirim laporan'}
        </button>
        <p className="text-xs text-faint">Anonim, maks 20 laporan per jam.</p>
        {phase === 'error' && (
          <p className="text-xs text-bad">Gagal terkirim, coba lagi nanti.</p>
        )}
      </div>
    </form>
  )
}
