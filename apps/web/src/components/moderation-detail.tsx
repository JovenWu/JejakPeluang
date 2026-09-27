'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { JSX } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { VerdictBadge } from '@/components/badges'
import type {
  Category,
  DecisionRequest,
  SubmissionDetail,
} from '@/lib/api'
import {
  CATEGORY_LABELS,
  FIELD_LABELS,
  formatDateTime,
  OUTCOME_LABELS,
} from '@/lib/format'

const FIELD_ORDER = [
  'title',
  'issuer',
  'deadline',
  'category',
  'region',
  'eligibility',
  'fees',
  'requested_data',
]

type ResultJson = {
  outcome?: string | null
  submission_text?: string | null
  extraction?: Record<string, unknown> | null
  discovery?: {
    status?: string
    query?: string | null
    results?: Array<{ url?: string; title?: string | null }> | null
  } | null
  evidence?: Array<{
    url?: string
    final_url?: string | null
    status?: number | null
    content_type?: string | null
    text?: string | null
    text_purged?: boolean
  }> | null
  comparison?: {
    field_verdicts?: Record<
      string,
      { verdict?: string; quote?: string | null }
    > | null
    notes?: string | null
  } | null
  judgments?: Array<{
    url?: string
    answers?: Record<
      string,
      { noul?: number; choice?: string; score?: number }
    > | null
  }> | null
  ai_source_match?: boolean | null
  errors?: Array<{ stage?: string; kind?: string; detail?: string }> | null
}

function text(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  return Array.isArray(value) ? value.join(', ') || '-' : String(value)
}

function EvidenceSection({ result }: { result: ResultJson }): JSX.Element {
  const extraction = result.extraction ?? {}
  const verdicts = result.comparison?.field_verdicts ?? {}
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span className="border border-line px-2 py-0.5">
          {result.outcome ? (OUTCOME_LABELS[result.outcome] ?? result.outcome) : '-'}
        </span>
        {result.ai_source_match === true && (
          <span className="text-good">sumber resmi cocok</span>
        )}
        {result.ai_source_match === false && (
          <span className="text-muted">sumber resmi belum cocok</span>
        )}
      </div>

      {result.extraction && (
        <section>
          <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
            ekstraksi.
          </h3>
          <dl className="divide-y divide-line">
            {FIELD_ORDER.filter((field) => field in extraction).map(
              (field) => (
                <div key={field} className="flex justify-between gap-6 py-2">
                  <dt className="text-muted">
                    {FIELD_LABELS[field] ?? field}
                  </dt>
                  <dd className="text-right">
                    {field === 'category' &&
                    typeof extraction[field] === 'string' &&
                    extraction[field] in CATEGORY_LABELS
                      ? CATEGORY_LABELS[extraction[field] as Category]
                      : text(extraction[field])}
                  </dd>
                </div>
              ),
            )}
          </dl>
        </section>
      )}

      {result.evidence && result.evidence.length > 0 && (
        <section>
          <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
            halaman sumber.
          </h3>
          <ul className="divide-y divide-line">
            {result.evidence.map((page, index) => {
              const judgment = (result.judgments ?? []).find(
                (entry) => entry.url === page.url,
              )
              const noul = judgment?.answers?.official_announcement?.noul
              const kind = judgment?.answers?.doc_kind?.choice
              return (
                <li key={index} className="py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <a
                      href={page.final_url ?? page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all font-mono text-xs underline underline-offset-4 hover:text-muted"
                    >
                      {page.final_url ?? page.url}
                    </a>
                    <span className="text-xs text-muted">
                      status {page.status ?? '-'}
                      {kind ? ` · ${kind}` : ''}
                      {noul !== undefined
                        ? ` · resmi ${(noul * 100).toFixed(0)}%`
                        : ''}
                    </span>
                  </div>
                  {page.text && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs text-muted">
                        isi halaman
                      </summary>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap border border-line bg-faint p-3 text-xs">
                        {page.text}
                      </pre>
                    </details>
                  )}
                  {page.text_purged && (
                    <p className="mt-1 text-xs text-muted">isi sudah dihapus.</p>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {Object.keys(verdicts).length > 0 && (
        <section>
          <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
            perbandingan field.
          </h3>
          <ul className="divide-y divide-line">
            {Object.entries(verdicts).map(([field, verdict]) => (
              <li key={field} className="py-2">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="text-muted">
                    {FIELD_LABELS[field] ?? field}
                  </span>
                  <VerdictBadge verdict={verdict.verdict ?? ''} />
                </div>
                {verdict.quote && (
                  <p className="mt-1 text-xs text-muted">
                    &ldquo;{verdict.quote}&rdquo;
                  </p>
                )}
              </li>
            ))}
          </ul>
          {result.comparison?.notes && (
            <p className="mt-3 text-xs text-muted">{result.comparison.notes}</p>
          )}
        </section>
      )}

      {result.discovery?.results && result.discovery.results.length > 0 && (
        <section>
          <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
            kandidat sumber.
          </h3>
          <ul className="space-y-1 pt-2">
            {result.discovery.results.map((entry, index) => (
              <li key={index} className="break-all font-mono text-xs text-muted">
                {entry.url}
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.submission_text && (
        <details>
          <summary className="cursor-pointer text-xs text-muted">
            teks hasil ekstraksi
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap border border-line bg-faint p-3 text-xs">
            {result.submission_text}
          </pre>
        </details>
      )}

      {result.errors && result.errors.length > 0 && (
        <ul className="space-y-1">
          {result.errors.map((error, index) => (
            <li key={index} className="text-xs text-bad">
              {error.stage}: {error.kind}
              {error.detail ? ` · ${error.detail}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const DECISION_LABELS: Record<string, string> = {
  approved: 'terbitkan',
  needs_more_evidence: 'minta bukti',
  rejected: 'tolak',
  expire: 'kedaluwarsakan',
}

export function ModerationDetail({ id }: { id: string }): JSX.Element {
  const router = useRouter()
  const [detail, setDetail] = useState<SubmissionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decision, setDecision] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [fields, setFields] = useState({
    title: '',
    category: 'scholarship' as Category,
    description: '',
    eligibility: '',
    region: '',
    deadline: '',
    slug: '',
    issuer_name: '',
    trust_basis: 'public_source' as
      | 'public_source'
      | 'issuer_confirmed_private',
  })
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const response = await fetch(`/api/v1/moderation/submissions/${id}`)
    if (response.status === 401 || response.status === 403) {
      router.replace('/admin/login')
      return
    }
    if (response.status === 404) {
      setError('kiriman tidak ditemukan')
      return
    }
    const body: SubmissionDetail = await response.json()
    setDetail(body)
    const extraction =
      (body.screening_run?.result_json as ResultJson | null)?.extraction ?? {}
    setFields((previous) => ({
      ...previous,
      title:
        typeof extraction.title === 'string' ? extraction.title : previous.title,
      issuer_name:
        typeof extraction.issuer === 'string'
          ? extraction.issuer
          : previous.issuer_name,
      deadline:
        typeof extraction.deadline === 'string' &&
        /^\d{4}-\d{2}-\d{2}$/.test(extraction.deadline)
          ? extraction.deadline
          : previous.deadline,
      category:
        typeof extraction.category === 'string' &&
        ['scholarship', 'internship', 'competition'].includes(
          extraction.category,
        )
          ? (extraction.category as Category)
          : previous.category,
      region:
        typeof extraction.region === 'string'
          ? extraction.region
          : previous.region,
      eligibility:
        typeof extraction.eligibility === 'string'
          ? extraction.eligibility
          : previous.eligibility,
    }))
  }, [id, router])

  useEffect(() => {
    queueMicrotask(() => void load())
  }, [load])

  async function submitDecision(): Promise<void> {
    if (!decision) {
      return
    }
    setBusy(true)
    setError(null)
    const payload: DecisionRequest = {
      decision: decision as DecisionRequest['decision'],
      reason: reason.trim() || null,
    }
    if (decision === 'approved') {
      payload.fields = {
        title: fields.title.trim(),
        category: fields.category,
        description: fields.description.trim(),
        eligibility: fields.eligibility.trim(),
        region: fields.region.trim() || null,
        deadline: fields.deadline || null,
        slug: fields.slug.trim() || null,
        issuer_name: fields.issuer_name.trim() || null,
        trust_basis: fields.trust_basis,
      }
    }
    const response = await fetch(
      `/api/v1/moderation/submissions/${id}/decision`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    )
    setBusy(false)
    if (response.ok) {
      router.push('/admin')
      return
    }
    const body = await response.json().catch(() => null)
    setError(
      response.status === 409
        ? 'kiriman sudah diputuskan atau slug bentrok'
        : typeof body?.detail === 'string'
          ? body.detail
          : 'keputusan gagal disimpan',
    )
  }

  if (error && !detail) {
    return <p className="pt-16 text-bad">{error}.</p>
  }
  if (!detail) {
    return <p className="pt-16 text-muted">memuat…</p>
  }

  const run = detail.screening_run
  const result = (run?.result_json as ResultJson | null) ?? null
  const decided = ['published', 'rejected', 'expired', 'closed_unreviewed'].includes(
    detail.state,
  )

  return (
    <div className="space-y-10 pb-12">
      <div className="space-y-2">
        <Link href="/admin" className="text-xs text-muted hover:text-ink">
          ← antrean
        </Link>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="font-mono text-2xl font-semibold tracking-tight">
            {detail.ref}
          </h1>
          <span className="text-xs text-muted">{detail.state}</span>
        </div>
      </div>

      <dl className="divide-y divide-line border-y border-line">
        {(
          [
            ['tautan', detail.submitted_url],
            ['konteks', detail.context || null],
            ['email', detail.contact_email],
            ['dikirim', formatDateTime(detail.created_at)],
            ['hapus data', formatDateTime(detail.purge_after)],
          ] as Array<[string, string | null]>
        ).map(([label, value]) => (
          <div key={label} className="flex justify-between gap-6 py-2">
            <dt className="shrink-0 text-muted">{label}</dt>
            <dd className="min-w-0 break-all text-right">
              {label === 'tautan' && value ? (
                <a
                  href={value}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs underline underline-offset-4"
                >
                  {value}
                </a>
              ) : (
                (value ?? '-')
              )}
            </dd>
          </div>
        ))}
      </dl>

      {detail.uploads.length > 0 && (
        <section>
          <h2 className="border-b border-line pb-2 text-xs text-muted lowercase">
            berkas.
          </h2>
          <ul className="divide-y divide-line">
            {detail.uploads.map((upload) => (
              <li
                key={upload.id}
                className="flex items-baseline justify-between gap-4 py-2"
              >
                <a
                  href={`/api/v1/moderation/submissions/${id}/uploads/${upload.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs underline underline-offset-4 hover:text-muted"
                >
                  {upload.storage_key}
                </a>
                <span className="text-xs text-muted">
                  {upload.detected_mime} ·{' '}
                  {(upload.size_bytes / 1024).toFixed(0)} KB
                  {upload.page_count ? ` · ${upload.page_count} hlm` : ''}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="border-b border-line pb-2 text-xs text-muted lowercase">
          pemeriksaan ai.
        </h2>
        {run ? (
          <div className="space-y-4">
            <p className="text-xs text-muted">
              {run.state}
              {run.provider_version ? ` · ${run.provider_version}` : ''}
              {run.model_version ? ` · ${run.model_version}` : ''}
              {run.finished_at
                ? ` · selesai ${formatDateTime(run.finished_at)}`
                : ''}
            </p>
            {run.error && <p className="text-xs text-bad">{run.error}</p>}
            {result && <EvidenceSection result={result} />}
          </div>
        ) : (
          <p className="text-muted">belum ada pemeriksaan.</p>
        )}
      </section>

      {detail.reports.length > 0 && (
        <section>
          <h2 className="border-b border-line pb-2 text-xs text-muted lowercase">
            laporan.
          </h2>
          <ul className="divide-y divide-line">
            {detail.reports.map((report) => (
              <li key={report.id} className="py-2 text-sm">
                <span className="text-xs text-muted">
                  {report.category} · {formatDateTime(report.created_at)}
                </span>
                {report.description && <p>{report.description}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {detail.decisions.length > 0 && (
        <section>
          <h2 className="border-b border-line pb-2 text-xs text-muted lowercase">
            riwayat keputusan.
          </h2>
          <ul className="divide-y divide-line">
            {detail.decisions.map((entry) => (
              <li key={entry.id} className="py-2 text-sm">
                <span className="text-xs text-muted">
                  {entry.status} · {formatDateTime(entry.decided_at)}
                </span>
                {entry.reason && <p>{entry.reason}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {detail.linked_opportunity_slug && (
        <Link
          href={`/peluang/${detail.linked_opportunity_slug}`}
          className="inline-block text-sm underline underline-offset-4"
        >
          lihat listing →
        </Link>
      )}

      {!decided && (
        <section className="space-y-4 border-t border-line pt-8">
          <h2 className="text-xs text-muted lowercase">keputusan.</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(DECISION_LABELS).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setDecision(value)}
                className={`px-3 py-1.5 text-xs ${
                  decision === value
                    ? 'bg-ink text-paper'
                    : 'border border-line text-muted hover:border-ink hover:text-ink'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {decision === 'approved' && (
            <div className="space-y-4 border border-line p-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="text-xs text-muted">judul *</span>
                  <input
                    value={fields.title}
                    onChange={(e) =>
                      setFields({ ...fields, title: e.target.value })
                    }
                    className="mt-1 w-full border-0 border-b border-line bg-transparent py-1.5 outline-none focus:border-ink"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-muted">kategori *</span>
                  <select
                    value={fields.category}
                    onChange={(e) =>
                      setFields({
                        ...fields,
                        category: e.target.value as Category,
                      })
                    }
                    className="mt-1 w-full border-0 border-b border-line bg-transparent py-1.5 outline-none focus:border-ink"
                  >
                    {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs text-muted">penyelenggara</span>
                  <input
                    value={fields.issuer_name}
                    onChange={(e) =>
                      setFields({ ...fields, issuer_name: e.target.value })
                    }
                    className="mt-1 w-full border-0 border-b border-line bg-transparent py-1.5 outline-none focus:border-ink"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-muted">batas akhir</span>
                  <input
                    type="date"
                    value={fields.deadline}
                    onChange={(e) =>
                      setFields({ ...fields, deadline: e.target.value })
                    }
                    className="mt-1 w-full border-0 border-b border-line bg-transparent py-1.5 outline-none focus:border-ink"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-muted">wilayah</span>
                  <input
                    value={fields.region}
                    onChange={(e) =>
                      setFields({ ...fields, region: e.target.value })
                    }
                    className="mt-1 w-full border-0 border-b border-line bg-transparent py-1.5 outline-none focus:border-ink"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-muted">slug</span>
                  <input
                    value={fields.slug}
                    onChange={(e) =>
                      setFields({ ...fields, slug: e.target.value })
                    }
                    placeholder="otomatis dari judul"
                    className="mt-1 w-full border-0 border-b border-line bg-transparent py-1.5 font-mono text-xs outline-none placeholder:text-muted/50 focus:border-ink"
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-xs text-muted">deskripsi *</span>
                <textarea
                  value={fields.description}
                  onChange={(e) =>
                    setFields({ ...fields, description: e.target.value })
                  }
                  rows={4}
                  className="mt-1 w-full border border-line bg-transparent p-3 outline-none focus:border-ink"
                />
              </label>
              <label className="block">
                <span className="text-xs text-muted">syarat *</span>
                <textarea
                  value={fields.eligibility}
                  onChange={(e) =>
                    setFields({ ...fields, eligibility: e.target.value })
                  }
                  rows={2}
                  className="mt-1 w-full border border-line bg-transparent p-3 outline-none focus:border-ink"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    ['public_source', 'sumber publik'],
                    ['issuer_confirmed_private', 'konfirmasi privat'],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() =>
                      setFields({ ...fields, trust_basis: value })
                    }
                    className={`px-3 py-1 text-xs ${
                      fields.trust_basis === value
                        ? 'bg-ink text-paper'
                        : 'border border-line text-muted hover:border-ink'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {decision && (
            <div className="space-y-3">
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="alasan (opsional)"
                className="w-full border border-line bg-transparent p-3 text-sm outline-none placeholder:text-muted/50 focus:border-ink"
              />
              <div className="flex items-center gap-4">
                <button
                  onClick={submitDecision}
                  disabled={busy}
                  className="bg-ink px-4 py-2 text-xs text-paper hover:bg-ink/80 disabled:opacity-40"
                >
                  {busy ? 'menyimpan…' : `simpan: ${DECISION_LABELS[decision]}`}
                </button>
                {error && <p className="text-xs text-bad">{error}</p>}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
