'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { JSX } from 'react'
import { useCallback, useEffect, useState } from 'react'

import { StateBadge, VerdictBadge } from '@/components/badges'
import { Card, CardHeader, INPUT_CLASS } from '@/components/ui'
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
    extract_error?: string | null
    fetch_error?: string | null
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

const DECISION_LABELS: Record<string, string> = {
  approved: 'Setujui & publikasikan',
  needs_more_evidence: 'Minta bukti tambahan',
  rejected: 'Tolak kiriman',
  expire: 'Kedaluwarsakan',
}

function text(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  return Array.isArray(value) ? value.join(', ') || '—' : String(value)
}

function EvidenceSection({ result }: { result: ResultJson }): JSX.Element {
  const extraction = result.extraction ?? {}
  const verdicts = result.comparison?.field_verdicts ?? {}
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-surface px-2.5 py-1 text-[11px] font-semibold leading-none text-body">
          {result.outcome
            ? (OUTCOME_LABELS[result.outcome] ?? result.outcome)
            : '—'}
        </span>
        {result.ai_source_match === true && (
          <span className="rounded-full bg-good-tint px-2.5 py-1 text-[11px] font-semibold leading-none text-good">
            ai_source_match: true
          </span>
        )}
        {result.ai_source_match === false && (
          <span className="rounded-full bg-surface px-2.5 py-1 text-[11px] font-semibold leading-none text-body">
            ai_source_match: false
          </span>
        )}
        <span className="text-[11px] text-faint">
          lencana ringan, bukan sertifikasi
        </span>
      </div>

      {result.extraction && (
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
            Perbandingan per-field
          </p>
          <div className="mt-2 overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[560px] text-left text-xs">
              <thead>
                <tr className="border-b border-line bg-surface text-[10px] uppercase tracking-[0.1em] text-faint">
                  <th className="px-3 py-2 font-bold">Field</th>
                  <th className="px-3 py-2 font-bold">Ekstraksi</th>
                  <th className="px-3 py-2 font-bold">Verdict</th>
                  <th className="px-3 py-2 font-bold">Kutipan sumber</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {FIELD_ORDER.filter(
                  (field) =>
                    field in extraction || field in verdicts,
                ).map((field) => (
                  <tr key={field}>
                    <td className="px-3 py-2 font-medium text-body">
                      {FIELD_LABELS[field] ?? field}
                    </td>
                    <td className="max-w-[200px] px-3 py-2">
                      {field === 'category' &&
                      typeof extraction[field] === 'string' &&
                      extraction[field] in CATEGORY_LABELS
                        ? CATEGORY_LABELS[extraction[field] as Category]
                        : text(extraction[field])}
                    </td>
                    <td className="px-3 py-2">
                      <VerdictBadge
                        verdict={verdicts[field]?.verdict ?? ''}
                      />
                    </td>
                    <td className="max-w-[260px] px-3 py-2 text-faint">
                      {verdicts[field]?.quote
                        ? `"${verdicts[field].quote}"`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.comparison?.notes && (
            <p className="mt-2 text-xs leading-5 text-faint">
              {result.comparison.notes}
            </p>
          )}
        </div>
      )}

      {result.evidence && result.evidence.length > 0 && (
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
            Halaman sumber
          </p>
          <ul className="mt-2 divide-y divide-line rounded-lg border border-line">
            {result.evidence.map((page, index) => {
              const judgment = (result.judgments ?? []).find(
                (entry) => entry.url === page.url,
              )
              const noul = judgment?.answers?.official_announcement?.noul
              const kind = judgment?.answers?.doc_kind?.choice
              const unreadable = page.extract_error ?? page.fetch_error
              return (
                <li key={index} className="px-4 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <a
                      href={page.final_url ?? page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-w-0 break-all font-mono text-xs text-accent hover:underline"
                    >
                      {page.final_url ?? page.url}
                    </a>
                    <span className="shrink-0 text-xs text-faint">
                      status {page.status ?? '—'}
                      {kind ? ` · ${kind}` : ''}
                      {noul !== undefined
                        ? ` · resmi ${(noul * 100).toFixed(0)}%`
                        : ''}
                      {unreadable ? ` · ${unreadable}` : ''}
                    </span>
                  </div>
                  {page.text && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs text-body">
                        Isi halaman
                      </summary>
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 text-xs">
                        {page.text}
                      </pre>
                    </details>
                  )}
                  {page.text_purged && (
                    <p className="mt-1 text-xs text-faint">
                      teks dihapus (retensi)
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {result.discovery?.results &&
        result.discovery.results.length > 0 && (
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
              Penemuan sumber
              {result.discovery.query
                ? ` · query: "${result.discovery.query}"`
                : ''}
            </p>
            <ul className="mt-2 space-y-1">
              {result.discovery.results.map((entry, index) => (
                <li
                  key={index}
                  className="break-all font-mono text-xs text-body"
                >
                  {entry.title ? `${entry.title} · ` : ''}
                  {entry.url}
                </li>
              ))}
            </ul>
          </div>
        )}

      {result.submission_text && (
        <details>
          <summary className="cursor-pointer text-xs text-body">
            Teks hasil ekstraksi
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 text-xs">
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
    return (
      <div className="mx-auto w-full max-w-5xl px-5 py-16 text-sm text-bad">
        {error}.
      </div>
    )
  }
  if (!detail) {
    return (
      <div className="mx-auto w-full max-w-5xl px-5 py-16 text-sm text-body">
        Memuat…
      </div>
    )
  }

  const run = detail.screening_run
  const result = (run?.result_json as ResultJson | null) ?? null
  const decided = [
    'published',
    'rejected',
    'expired',
    'closed_unreviewed',
  ].includes(detail.state)

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-10">
      <nav className="flex items-center gap-2 text-xs text-faint">
        <Link href="/admin" className="hover:text-ink">
          Antrean
        </Link>
        <span>/</span>
        <span className="font-mono text-ink">{detail.ref}</span>
      </nav>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-xl font-bold">{detail.ref}</h1>
        <StateBadge state={detail.state} />
        <span className="text-xs text-faint">
          dikirim {formatDateTime(detail.created_at)}
        </span>
        {detail.purge_after && (
          <span className="text-xs text-faint">
            PII dihapus {formatDateTime(detail.purge_after)}
          </span>
        )}
        {detail.reports.length > 0 && (
          <span className="rounded-full bg-bad-tint px-2.5 py-1 text-[11px] font-semibold leading-none text-bad">
            {detail.reports.length} laporan terbuka
          </span>
        )}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader eyebrow="Kiriman tamu" />
            <dl className="divide-y divide-line text-sm">
              <div className="flex justify-between gap-6 px-5 py-3">
                <dt className="shrink-0 text-body">URL yang dikirim</dt>
                <dd className="min-w-0 break-all text-right">
                  {detail.submitted_url ? (
                    <a
                      href={detail.submitted_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs text-accent hover:underline"
                    >
                      {detail.submitted_url}
                    </a>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
              <div className="flex justify-between gap-6 px-5 py-3">
                <dt className="shrink-0 text-body">Konteks tamu</dt>
                <dd className="min-w-0 text-right text-body">
                  {detail.context || '—'}
                </dd>
              </div>
              <div className="flex justify-between gap-6 px-5 py-3">
                <dt className="shrink-0 text-body">Kontak tamu</dt>
                <dd className="text-right">
                  {detail.contact_email ?? '—'}
                </dd>
              </div>
            </dl>
          </Card>

          {detail.uploads.length > 0 && (
            <Card>
              <CardHeader
                eyebrow="Berkas unggahan"
                hint={`${detail.uploads.length} berkas`}
              />
              <ul className="divide-y divide-line">
                {detail.uploads.map((upload) => (
                  <li
                    key={upload.id}
                    className="flex items-baseline justify-between gap-4 px-5 py-3"
                  >
                    <a
                      href={`/api/v1/moderation/submissions/${id}/uploads/${upload.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="min-w-0 break-all font-mono text-xs text-accent hover:underline"
                    >
                      {upload.storage_key}
                    </a>
                    <span className="shrink-0 text-xs text-faint">
                      {upload.detected_mime} ·{' '}
                      {(upload.size_bytes / 1024).toFixed(0)} KB
                      {upload.page_count ? ` · ${upload.page_count} hlm` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card>
            <CardHeader
              eyebrow="Bukti AI"
              hint="advisory, bukan vonis"
            />
            <div className="p-5">
              {run ? (
                <div className="space-y-4">
                  <p className="text-xs text-faint">
                    {run.state}
                    {run.provider_version
                      ? ` · ${run.provider_version}`
                      : ''}
                    {run.model_version ? ` · ${run.model_version}` : ''}
                    {run.finished_at
                      ? ` · selesai ${formatDateTime(run.finished_at)}`
                      : ''}
                  </p>
                  {run.error && (
                    <p className="text-xs text-bad">{run.error}</p>
                  )}
                  {result && <EvidenceSection result={result} />}
                </div>
              ) : (
                <p className="text-sm text-body">Belum ada pemeriksaan.</p>
              )}
            </div>
          </Card>

          {detail.reports.length > 0 && (
            <Card>
              <CardHeader eyebrow="Laporan komunitas" />
              <ul className="divide-y divide-line">
                {detail.reports.map((report) => (
                  <li key={report.id} className="px-5 py-3 text-sm">
                    <span className="text-xs text-faint">
                      {report.category} · {formatDateTime(report.created_at)}
                    </span>
                    {report.description && (
                      <p className="mt-1 text-body">{report.description}</p>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {detail.decisions.length > 0 && (
            <Card>
              <CardHeader eyebrow="Riwayat keputusan" />
              <ul className="divide-y divide-line">
                {detail.decisions.map((entry) => (
                  <li key={entry.id} className="px-5 py-3 text-sm">
                    <span className="text-xs text-faint">
                      {entry.status} · {formatDateTime(entry.decided_at)}
                    </span>
                    {entry.reason && (
                      <p className="mt-1 text-body">{entry.reason}</p>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {detail.linked_opportunity_slug && (
            <Link
              href={`/peluang/${detail.linked_opportunity_slug}`}
              className="inline-block text-sm font-medium text-accent hover:underline"
            >
              Lihat listing →
            </Link>
          )}
        </div>

        {!decided && (
          <Card className="h-fit lg:sticky lg:top-6">
            <CardHeader eyebrow="Keputusan" />
            <div className="space-y-4 p-5">
              <div className="grid gap-2">
                {Object.entries(DECISION_LABELS).map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => setDecision(value)}
                    className={`rounded-lg px-4 py-2.5 text-left text-sm font-medium ${
                      decision === value
                        ? 'bg-ink text-paper'
                        : 'border border-line text-body hover:border-ink hover:text-ink'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {decision === 'approved' && (
                <div className="space-y-4 border-t border-line pt-4">
                  <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
                    Formulir publikasi, wajib saat menyetujui
                  </p>
                  <label className="block">
                    <span className="text-xs font-semibold">Judul *</span>
                    <input
                      value={fields.title}
                      onChange={(e) =>
                        setFields({ ...fields, title: e.target.value })
                      }
                      className={`${INPUT_CLASS} mt-1.5`}
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold">Kategori *</span>
                    <select
                      value={fields.category}
                      onChange={(e) =>
                        setFields({
                          ...fields,
                          category: e.target.value as Category,
                        })
                      }
                      className={`${INPUT_CLASS} mt-1.5 capitalize`}
                    >
                      {Object.entries(CATEGORY_LABELS).map(
                        ([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold">
                      Nama penerbit *
                    </span>
                    <input
                      value={fields.issuer_name}
                      onChange={(e) =>
                        setFields({ ...fields, issuer_name: e.target.value })
                      }
                      className={`${INPUT_CLASS} mt-1.5`}
                    />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <label className="block">
                      <span className="text-xs font-semibold">
                        Batas akhir
                      </span>
                      <input
                        type="date"
                        value={fields.deadline}
                        onChange={(e) =>
                          setFields({ ...fields, deadline: e.target.value })
                        }
                        className={`${INPUT_CLASS} mt-1.5`}
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs font-semibold">Wilayah</span>
                      <input
                        value={fields.region}
                        onChange={(e) =>
                          setFields({ ...fields, region: e.target.value })
                        }
                        className={`${INPUT_CLASS} mt-1.5`}
                      />
                    </label>
                  </div>
                  <label className="block">
                    <span className="text-xs font-semibold">Slug</span>
                    <input
                      value={fields.slug}
                      onChange={(e) =>
                        setFields({ ...fields, slug: e.target.value })
                      }
                      placeholder="otomatis dari judul"
                      className={`${INPUT_CLASS} mt-1.5 font-mono text-xs`}
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold">
                      Deskripsi *
                    </span>
                    <textarea
                      value={fields.description}
                      onChange={(e) =>
                        setFields({ ...fields, description: e.target.value })
                      }
                      rows={4}
                      className={`${INPUT_CLASS} mt-1.5`}
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold">
                      Syarat & kelayakan *
                    </span>
                    <textarea
                      value={fields.eligibility}
                      onChange={(e) =>
                        setFields({ ...fields, eligibility: e.target.value })
                      }
                      rows={2}
                      className={`${INPUT_CLASS} mt-1.5`}
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        ['public_source', 'Sumber publik'],
                        ['issuer_confirmed_private', 'Konfirmasi privat'],
                      ] as const
                    ).map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() =>
                          setFields({ ...fields, trust_basis: value })
                        }
                        className={`rounded-full px-3.5 py-1.5 text-xs font-semibold ${
                          fields.trust_basis === value
                            ? 'bg-ink text-paper'
                            : 'border border-line text-body hover:border-ink'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {decision && (
                <div className="space-y-3 border-t border-line pt-4">
                  <textarea
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    rows={2}
                    maxLength={2000}
                    placeholder="Alasan (opsional)"
                    className={INPUT_CLASS}
                  />
                  <button
                    onClick={submitDecision}
                    disabled={busy}
                    className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-paper hover:bg-accent/90 disabled:opacity-40"
                  >
                    {busy
                      ? 'Menyimpan…'
                      : `Simpan: ${DECISION_LABELS[decision]}`}
                  </button>
                  {error && <p className="text-xs text-bad">{error}</p>}
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
