'use client'

import { type FormEvent, type ReactNode, useState } from 'react'

import type { ReportRequest } from '@/lib/api'

const OPTIONS: { value: ReportRequest['category']; label: string }[] = [
  { value: 'scam_suspect', label: 'Dicurigai penipuan' },
  { value: 'deadline_wrong', label: 'Tenggat salah' },
  { value: 'link_broken', label: 'Tautan rusak' },
  { value: 'info_incorrect', label: 'Info tidak akurat' },
  { value: 'other', label: 'Lainnya' },
]

type State = 'idle' | 'sending' | 'sent'

export function ReportForm({ slug }: { slug: string }): ReactNode {
  const [category, setCategory] = useState<ReportRequest['category'] | ''>('')
  const [description, setDescription] = useState('')
  const [state, setState] = useState<State>('idle')
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!category) {
      setError('Pilih jenis masalah.')
      return
    }
    setState('sending')
    setError(null)
    const body: ReportRequest = { category, description: description.trim() || null }
    try {
      const response = await fetch(`/api/v1/opportunities/${encodeURIComponent(slug)}/reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (response.status === 201) {
        setState('sent')
        return
      }
      setError(response.status === 429 ? 'Terlalu banyak laporan dari jaringan Anda. Coba lagi nanti.' : 'Laporan gagal dikirim.')
    } catch {
      setError('Tidak dapat terhubung ke server.')
    }
    setState('idle')
  }

  if (state === 'sent') {
    return (
      <p role="status" className="text-sm leading-relaxed text-ink-2">
        <strong className="text-ink">Terima kasih, laporan diterima.</strong> Moderator akan melihatnya saat meninjau entri
        ini. Kami tidak bisa membalas laporan anonim.
      </p>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Apa masalahnya?</legend>
        <div className="flex flex-wrap gap-1.5">
          {OPTIONS.map((option) => (
            <label
              key={option.value}
              className="inline-flex min-h-10 cursor-pointer items-center rounded-[3px] border border-rule-2 px-3 text-sm has-checked:border-ink has-checked:bg-ink has-checked:text-paper has-focus-visible:outline-3 has-focus-visible:outline-focus"
            >
              <input
                type="radio"
                name="category"
                value={option.value}
                className="sr-only"
                checked={category === option.value}
                onChange={() => setCategory(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor="report-description" className="mb-1.5 block text-sm font-semibold">
          Keterangan <span className="font-normal text-ink-3">(opsional)</span>
        </label>
        <textarea
          id="report-description"
          rows={3}
          maxLength={2000}
          className="field resize-y text-sm"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      {error ? (
        <p role="alert" className="text-sm font-medium text-bad">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn btn-primary min-h-10" disabled={state === 'sending'}>
          {state === 'sending' ? 'Mengirim…' : 'Kirim laporan'}
        </button>
        <span className="text-xs text-ink-3">Anonim. Laporan tidak langsung mengubah entri.</span>
      </div>
    </form>
  )
}
