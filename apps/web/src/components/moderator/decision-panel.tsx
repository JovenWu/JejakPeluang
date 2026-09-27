'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { type FormEvent, type ReactNode, useState } from 'react'

import { CATEGORIES, type DecisionFields, type DecisionRequest, errorMessage, isCategory, readDetail } from '@/lib/api'
import { CATEGORY_LABEL } from '@/lib/format'
import type { Extracted } from '@/lib/screening'

type Action = DecisionRequest['decision']

const ACTIONS: { value: Action; label: string; hint: string }[] = [
  { value: 'approved', label: 'Setujui & publikasikan', hint: 'Masuk katalog dengan cap verifikasi.' },
  { value: 'needs_more_evidence', label: 'Minta bukti tambahan', hint: 'Tetap di antrean; tamu melihat permintaan ini.' },
  { value: 'rejected', label: 'Tolak', hint: 'Keluar dari antrean publik. Data tamu dihapus 7 hari lagi.' },
  { value: 'expire', label: 'Kedaluwarsa', hint: 'Peluang sudah lewat atau tidak berlaku lagi.' },
]

const BUTTON_CLASS: Record<Action, string> = {
  approved: 'btn-stamp',
  needs_more_evidence: 'btn-primary',
  rejected: 'btn-danger',
  expire: 'btn-primary',
}

interface SourceCandidate {
  url: string
  label: string
}

interface Props {
  submissionId: string
  sourceCandidates: SourceCandidate[]
  extracted: Extracted | null
}

function slugify(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 160)
}

export function DecisionPanel({ submissionId, sourceCandidates, extracted }: Props): ReactNode {
  const router = useRouter()
  const [action, setAction] = useState<Action | null>(null)
  const [reason, setReason] = useState('')
  const [fields, setFields] = useState({
    title: extracted?.title ?? '',
    category: isCategory(extracted?.category) ? extracted.category : '',
    issuer_name: extracted?.issuer ?? '',
    deadline: extracted?.deadline && /^\d{4}-\d{2}-\d{2}$/.test(extracted.deadline) ? extracted.deadline : '',
    region: extracted?.region ?? '',
    description: extracted?.description ?? '',
    eligibility: extracted?.eligibility ?? '',
    source_url: sourceCandidates[0]?.url ?? '',
    slug: '',
    trust_basis: (sourceCandidates.length > 0 ? 'public_source' : 'issuer_confirmed_private') as DecisionFields['trust_basis'],
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ slug: string | null; state: string } | null>(null)

  function set<K extends keyof typeof fields>(key: K, value: (typeof fields)[K]): void {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!action) {
      return
    }
    let payloadFields: DecisionFields | null = null
    if (action === 'approved') {
      if (!fields.title.trim() || !fields.category || !fields.description.trim() || !fields.eligibility.trim()) {
        setError('Judul, jenis, deskripsi, dan syarat wajib diisi untuk publikasi.')
        return
      }
      if (fields.trust_basis === 'issuer_confirmed_private' && !fields.issuer_name.trim()) {
        setError('Nama penerbit wajib diisi untuk konfirmasi privat.')
        return
      }
      payloadFields = {
        title: fields.title.trim(),
        category: fields.category as DecisionFields['category'],
        description: fields.description.trim(),
        eligibility: fields.eligibility.trim(),
        region: fields.region.trim() || null,
        deadline: fields.deadline || null,
        slug: fields.slug.trim() || null,
        issuer_name: fields.issuer_name.trim() || null,
        source_url: fields.trust_basis === 'public_source' ? fields.source_url.trim() || null : null,
        trust_basis: fields.trust_basis,
      }
    }
    setBusy(true)
    setError(null)
    const body: DecisionRequest = { decision: action, reason: reason.trim() || null, fields: payloadFields }
    try {
      const response = await fetch(`/api/v1/moderation/submissions/${submissionId}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (response.ok) {
        const result = (await response.json()) as { opportunity_slug?: string | null; submission_state: string }
        setDone({ slug: result.opportunity_slug ?? null, state: result.submission_state })
        router.refresh()
      } else if (response.status === 401 || response.status === 403) {
        setError('Sesi berakhir. Masuk lagi untuk melanjutkan.')
      } else {
        setError(errorMessage(await readDetail(response), `Keputusan gagal disimpan (HTTP ${response.status}).`))
      }
    } catch {
      setError('Tidak dapat terhubung ke server.')
    }
    setBusy(false)
  }

  if (done) {
    return (
      <div role="status" className="rounded-[3px] border border-ok bg-ok-tint p-5 text-sm">
        <p className="font-semibold text-ok">Keputusan tersimpan.</p>
        {done.slug ? (
          <Link href={`/katalog/${done.slug}`} className="link mt-2 inline-block font-semibold">
            Lihat entri katalog →
          </Link>
        ) : null}
        <p className="mt-2">
          <Link href="/moderator" className="link">
            Kembali ke antrean
          </Link>
        </p>
      </div>
    )
  }

  const approving = action === 'approved'
  const approveBlocked = approving && fields.trust_basis === 'public_source' && !fields.source_url.trim()

  return (
    <form onSubmit={submit} className="space-y-5">
      <fieldset>
        <legend className="kicker mb-3">Keputusan</legend>
        <div className="grid gap-2">
          {ACTIONS.map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer gap-3 rounded-[3px] border border-rule-2 bg-surface p-3 has-checked:border-ink has-checked:shadow-[inset_0_0_0_1px_var(--color-ink)] has-focus-visible:outline-3 has-focus-visible:outline-focus"
            >
              <input
                type="radio"
                name="decision"
                value={option.value}
                checked={action === option.value}
                onChange={() => {
                  setAction(option.value)
                  setError(null)
                }}
                className="mt-1 accent-stamp"
              />
              <span>
                <span className="block text-sm font-semibold">{option.label}</span>
                <span className="block text-xs text-ink-2">{option.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {approving ? (
        <fieldset className="space-y-4 rounded-[3px] border border-rule bg-surface p-4">
          <legend className="kicker px-1">Data entri katalog</legend>
          <p className="text-xs text-ink-2">Diisi awal dari ekstraksi AI. Periksa setiap kolom terhadap sumber.</p>

          <div>
            <span className="mb-1.5 block text-sm font-semibold">Dasar kepercayaan</span>
            <div className="grid gap-2 sm:grid-cols-2">
              {(['public_source', 'issuer_confirmed_private'] as const).map((basis) => (
                <label
                  key={basis}
                  className="flex cursor-pointer items-start gap-2 rounded-[3px] border border-rule-2 p-2.5 text-sm has-checked:border-ink"
                >
                  <input
                    type="radio"
                    name="trust_basis"
                    checked={fields.trust_basis === basis}
                    onChange={() => set('trust_basis', basis)}
                    className="mt-0.5 accent-stamp"
                  />
                  <span>
                    <span className="block font-semibold">{basis === 'public_source' ? 'Sumber publik' : 'Konfirmasi privat'}</span>
                    <span className="block text-xs text-ink-2">
                      {basis === 'public_source' ? 'Pilih halaman sumber yang sudah diperiksa.' : 'Penerbit mengonfirmasi; tanpa URL.'}
                    </span>
                  </span>
                </label>
              ))}
            </div>
            {fields.trust_basis === 'public_source' ? (
              <div className="mt-3">
                <label htmlFor="f-source" className="mb-1.5 block text-sm font-semibold">
                  URL sumber katalog
                </label>
                <input
                  id="f-source"
                  type="url"
                  list={`source-candidates-${submissionId}`}
                  className="field font-mono text-xs"
                  value={fields.source_url}
                  onChange={(event) => set('source_url', event.target.value)}
                  placeholder="https://situs-penerbit.id/peluang"
                />
                <datalist id={`source-candidates-${submissionId}`}>
                  {sourceCandidates.map((candidate) => (
                    <option key={candidate.url} value={candidate.url} label={candidate.label} />
                  ))}
                </datalist>
                <p className="mt-1 text-xs text-ink-3">
                  Pilih kandidat situs atau masukkan URL publik yang sudah diperiksa. Tautan QR tercatat terpisah sebagai petunjuk.
                </p>
              </div>
            ) : null}
            {approveBlocked ? (
              <p className="mt-2 text-xs font-medium text-bad">Pilih atau masukkan URL sumber yang sudah diperiksa, atau gunakan konfirmasi privat.</p>
            ) : null}
          </div>

          <div>
            <label htmlFor="f-title" className="mb-1.5 block text-sm font-semibold">
              Judul
            </label>
            <input
              id="f-title"
              className="field"
              maxLength={240}
              value={fields.title}
              onChange={(e) => set('title', e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="f-category" className="mb-1.5 block text-sm font-semibold">
                Jenis
              </label>
              <select
                id="f-category"
                className="field"
                value={fields.category}
                onChange={(e) => set('category', e.target.value as typeof fields.category)}
              >
                <option value="">Pilih…</option>
                {CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {CATEGORY_LABEL[category]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="f-deadline" className="mb-1.5 block text-sm font-semibold">
                Tenggat <span className="font-normal text-ink-3">(opsional)</span>
              </label>
              <input
                id="f-deadline"
                type="date"
                className="field"
                value={fields.deadline}
                onChange={(e) => set('deadline', e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="f-issuer" className="mb-1.5 block text-sm font-semibold">
                Penerbit{' '}
                <span className="font-normal text-ink-3">
                  {fields.trust_basis === 'issuer_confirmed_private' ? '(wajib)' : '(opsional)'}
                </span>
              </label>
              <input
                id="f-issuer"
                className="field"
                maxLength={160}
                value={fields.issuer_name}
                onChange={(e) => set('issuer_name', e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="f-region" className="mb-1.5 block text-sm font-semibold">
                Wilayah <span className="font-normal text-ink-3">(opsional)</span>
              </label>
              <input
                id="f-region"
                className="field"
                maxLength={160}
                value={fields.region}
                onChange={(e) => set('region', e.target.value)}
              />
            </div>
          </div>
          <div>
            <label htmlFor="f-description" className="mb-1.5 block text-sm font-semibold">
              Deskripsi
            </label>
            <textarea
              id="f-description"
              rows={4}
              className="field resize-y text-sm"
              value={fields.description}
              onChange={(e) => set('description', e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="f-eligibility" className="mb-1.5 block text-sm font-semibold">
              Syarat pendaftar
            </label>
            <textarea
              id="f-eligibility"
              rows={3}
              className="field resize-y text-sm"
              value={fields.eligibility}
              onChange={(e) => set('eligibility', e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="f-slug" className="mb-1.5 block text-sm font-semibold">
              Slug <span className="font-normal text-ink-3">(opsional, dibuat dari judul)</span>
            </label>
            <input
              id="f-slug"
              className="field font-mono text-sm"
              placeholder={slugify(fields.title) || 'beasiswa-contoh-2026'}
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              value={fields.slug}
              onChange={(e) => set('slug', e.target.value.toLowerCase())}
            />
          </div>
        </fieldset>
      ) : null}

      {action ? (
        <div>
          <label htmlFor="reason" className="mb-1.5 block text-sm font-semibold">
            Catatan internal <span className="font-normal text-ink-3">(opsional)</span>
          </label>
          <textarea
            id="reason"
            rows={2}
            maxLength={2000}
            className="field resize-y text-sm"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="rounded-[3px] bg-bad-tint px-3 py-2.5 text-sm font-medium text-bad">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={!action || busy || approveBlocked}
        className={`btn w-full ${BUTTON_CLASS[action ?? 'expire']}`}
      >
        {busy ? 'Menyimpan…' : (ACTIONS.find((a) => a.value === action)?.label ?? 'Pilih keputusan')}
      </button>
    </form>
  )
}
