import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { AiEvidenceSummary } from '@/components/ai-evidence-summary'
import { LoadError } from '@/components/load-error'
import { DecisionPanel } from '@/components/moderator/decision-panel'
import { STATE_LABEL, StateTag, TERMINAL_STATES } from '@/components/moderator/state-tag'
import { Tag, VerdictTag } from '@/components/tags'
import type { ScreeningView, SubmissionDetail } from '@/lib/api'
import {
  DISCOVERY_PURPOSE_LABEL,
  DISCOVERY_STATUS_LABEL,
  DOC_KIND_LABEL,
  type Evidence,
  JUDGMENT_LABEL,
  type Judgment,
  readEvidence,
} from '@/lib/evidence'
import { displayUrl, formatBytes, formatDate, formatDateTime } from '@/lib/format'
import { moderatorApi } from '@/lib/moderator'
import {
  COMPARED_FIELDS,
  ERROR_KIND_LABEL,
  EXTRACTED_CATEGORY_LABEL,
  FIELD_LABEL,
  OUTCOME_COPY,
  readExtracted,
  readVerdicts,
  siteAssessmentCopy,
} from '@/lib/screening'

export const metadata: Metadata = { title: 'Bukti kiriman' }

interface Props {
  params: Promise<{ id: string }>
}

const REPORT_LABEL: Record<string, string> = {
  scam_suspect: 'Dicurigai penipuan',
  deadline_wrong: 'Tenggat salah',
  link_broken: 'Tautan rusak',
  info_incorrect: 'Info tidak akurat',
  other: 'Lainnya',
}

const SOURCE_MATCH_LABEL: Record<string, string> = {
  true: 'AI menilai ada pengumuman penerbit dengan data selaras',
  false: 'AI belum menemukan pengumuman penerbit yang memenuhi sinyal',
  null: 'belum tersedia',
}

const EVIDENCE_ORIGIN_LABEL: Record<string, string> = {
  submitted_url: 'tautan kiriman',
  qr_code: 'tujuan QR',
  opportunity: 'hasil pencarian peluang',
  issuer_website: 'pencarian situs penerbit',
  application_url: 'URL pendaftaran',
  source_hint: 'sumber disebut di teks',
}

const DECISION_LABEL: Record<string, string> = {
  approved: 'Disetujui',
  needs_more_evidence: 'Minta bukti tambahan',
  rejected: 'Ditolak',
  expire: 'Kedaluwarsa',
  expired: 'Kedaluwarsa',
}

function Panel({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }): ReactNode {
  return (
    <section className="rounded-[3px] border border-rule bg-surface">
      <header className="flex items-center justify-between gap-3 border-b border-rule px-4 py-2.5">
        <h2 className="kicker text-ink-2!">{title}</h2>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </section>
  )
}

function Meter({ value, max }: { value: number | null; max: number }): ReactNode {
  if (value === null) {
    return <span className="text-ink-3">-</span>
  }
  const pct = Math.round(Math.min(1, Math.max(0, value / max)) * 100)
  let color = 'bg-bad'
  if (pct >= 80) {
    color = 'bg-ok'
  } else if (pct >= 50) {
    color = 'bg-warn'
  }
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-rule" aria-hidden>
        <span className={`block h-full ${color}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="font-mono text-xs tabular-nums">
        {value.toFixed(2)}
        {max !== 1 ? <span className="text-ink-3">/{max}</span> : null}
      </span>
    </span>
  )
}

function JudgmentCard({ judgment }: { judgment: Judgment }): ReactNode {
  return (
    <div className="rounded-[3px] border border-rule p-3">
      <p className="mb-2 truncate font-mono text-xs">{displayUrl(judgment.url)}</p>
      <dl className="space-y-1.5 text-sm">
        {judgment.answers.map((answer) => (
          <div key={answer.name} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <dt className="text-ink-2">
              {JUDGMENT_LABEL[answer.name] ?? answer.name}
              {answer.kind === 'choice' && answer.choice ? (
                <span className="ml-1.5 font-semibold text-ink">→ {DOC_KIND_LABEL[answer.choice] ?? answer.choice}</span>
              ) : null}
              {answer.kind === 'score' && answer.choice ? (
                <span className="block text-xs text-ink-3">{answer.choice}</span>
              ) : null}
            </dt>
            <dd className="shrink-0">
              <Meter value={answer.value} max={answer.max} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function EvidenceSection({ evidence, screening }: { evidence: Evidence; screening: ScreeningView }): ReactNode {
  const extracted = readExtracted(screening)
  const verdicts = readVerdicts(screening)
  return (
    <div className="space-y-5">
      <AiEvidenceSummary screening={screening} />
      <Panel title="Perbandingan per kolom" aside={<span className="font-mono text-2xs text-ink-3">ekstraksi vs sumber</span>}>
        <div className="-mx-4 -my-4 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left">
                <th scope="col" className="kicker px-4 py-2 font-normal">Kolom</th>
                <th scope="col" className="kicker px-4 py-2 font-normal">Ekstraksi</th>
                <th scope="col" className="kicker px-4 py-2 font-normal">Hasil</th>
                <th scope="col" className="kicker px-4 py-2 font-normal">Kutipan sumber</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule align-top">
              {COMPARED_FIELDS.map((field) => {
                const raw = extracted?.[field] ?? null
                const text = Array.isArray(raw) ? raw.join(', ') : raw
                const value = field === 'category' && text ? (EXTRACTED_CATEGORY_LABEL[text] ?? text) : text
                const verdict = verdicts[field]
                return (
                  <tr key={field}>
                    <th scope="row" className="px-4 py-2.5 text-left font-semibold whitespace-nowrap">
                      {FIELD_LABEL[field]}
                    </th>
                    <td className="max-w-64 px-4 py-2.5">{value ?? <span className="text-ink-3">-</span>}</td>
                    <td className="px-4 py-2.5">{verdict ? <VerdictTag verdict={verdict.verdict} /> : <span className="text-ink-3">-</span>}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-ink-2">
                      {verdict?.quote ? <q>{verdict.quote}</q> : <span className="text-ink-3">-</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {evidence.notes ? <p className="mt-6 border-t border-rule pt-3 text-sm text-ink-2">{evidence.notes}</p> : null}
      </Panel>

      {evidence.siteAssessment ? (
        <Panel title="Situs penerbit dan QR">
          <p className="mb-4 text-sm leading-relaxed text-ink-2">
            {siteAssessmentCopy(evidence.siteAssessment.status)} Penilaian ini membantu pencarian, bukan pengesahan otomatis.
          </p>
          {extracted?.application_url || extracted?.source_hint ? (
            <dl className="mb-4 grid gap-3 text-sm sm:grid-cols-2">
              {extracted.application_url ? (
                <div className="min-w-0">
                  <dt className="text-xs font-semibold text-ink-3">URL pendaftaran terbaca</dt>
                  <dd className="mt-1 break-all">
                    <a href={extracted.application_url} target="_blank" rel="noopener noreferrer nofollow" className="link">
                      {displayUrl(extracted.application_url)}
                    </a>
                  </dd>
                </div>
              ) : null}
              {extracted.source_hint ? (
                <div className="min-w-0">
                  <dt className="text-xs font-semibold text-ink-3">Sumber yang disebut dalam teks</dt>
                  <dd className="mt-1 break-all">
                    <a href={extracted.source_hint} target="_blank" rel="noopener noreferrer nofollow" className="link">
                      {displayUrl(extracted.source_hint)}
                    </a>
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}
          {evidence.siteAssessment.issuerWebsites.length > 0 ? (
            <div className="border-t border-rule pt-3">
              <h3 className="kicker mb-2">Kandidat situs</h3>
              <ul className="space-y-2 text-sm">
                {evidence.siteAssessment.issuerWebsites.map((site) => (
                  <li key={site.url} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <a href={site.url} target="_blank" rel="noopener noreferrer nofollow" className="link min-w-0 flex-1 break-all">
                      {displayUrl(site.url)}
                    </a>
                    <span className="text-xs text-ink-3">
                      {site.basis === 'moderator_confirmed_domain' ? 'domain pernah disetujui moderator' : 'kandidat dinilai AI'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {evidence.siteAssessment.socialSources.length > 0 ? (
            <div className="mt-4 border-t border-rule pt-3">
              <h3 className="kicker mb-2">Kanal sosial</h3>
              <ul className="space-y-2 text-sm">
                {evidence.siteAssessment.socialSources.map((source) => (
                  <li key={source.url} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <a href={source.url} target="_blank" rel="noopener noreferrer nofollow" className="link min-w-0 flex-1 break-all">
                      {source.platform ?? displayUrl(source.url)}
                    </a>
                    <span className="text-xs text-ink-3">
                      {source.issuerChannel ? 'AI menilai kanal terkait penerbit' : 'hubungan ke penerbit belum terbukti'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {evidence.siteAssessment.unclassifiedSources.length > 0 ? (
            <div className="mt-4 border-t border-rule pt-3">
              <h3 className="kicker mb-2">Belum cukup bukti untuk mengelompokkan sumber</h3>
              <ul className="space-y-2 text-sm">
                {evidence.siteAssessment.unclassifiedSources.map((url) => (
                  <li key={url} className="min-w-0">
                    <a href={url} target="_blank" rel="noopener noreferrer nofollow" className="link break-all">
                      {displayUrl(url)}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {evidence.qrCodes.length > 0 ? (
            <div className="mt-4 border-t border-rule pt-3">
              <h3 className="kicker mb-2">Tautan yang dipindai dari QR</h3>
              <ul className="space-y-2 text-sm">
                {evidence.qrCodes.map((code) => (
                  <li key={`${code.url}-${code.origin}`} className="min-w-0">
                    <a href={code.url} target="_blank" rel="noopener noreferrer nofollow" className="link break-all">
                      {displayUrl(code.url)}
                    </a>
                    <span className="ml-2 text-xs text-ink-3">{code.origin ?? 'gambar'}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Panel>
      ) : null}

      <Panel
        title="Penemuan sumber"
        aside={evidence.discoveryStatus ? (
          <span className="font-mono text-2xs text-ink-3">
            {DISCOVERY_STATUS_LABEL[evidence.discoveryStatus] ?? evidence.discoveryStatus}
          </span>
        ) : null}
      >
        {evidence.discoveryQuery ? (
          <p className="mb-3 text-sm">
            <span className="text-ink-3">Kueri: </span>
            <code className="font-mono text-xs">{evidence.discoveryQuery}</code>
          </p>
        ) : null}
        {evidence.discovery.length > 0 ? (
          <ol className="divide-y divide-rule text-sm">
            {evidence.discovery.map((result, index) => (
              <li key={`${result.url}-${index}`} className="flex items-baseline gap-3 py-2">
                <span className="font-mono text-2xs text-ink-3">{String(index + 1).padStart(2, '0')}</span>
                <span className="min-w-0 flex-1">
                  {result.purpose ? (
                    <span className="kicker mb-0.5 block">{DISCOVERY_PURPOSE_LABEL[result.purpose] ?? result.purpose}</span>
                  ) : null}
                  <span className="block truncate">{result.title ?? '(tanpa judul)'}</span>
                  <a href={result.url} target="_blank" rel="noopener noreferrer nofollow" className="link block truncate font-mono text-xs">
                    {displayUrl(result.url)}
                  </a>
                </span>
                {result.score !== null ? <span className="font-mono text-xs tabular-nums">{result.score.toFixed(2)}</span> : null}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-ink-3">Tidak ada hasil penemuan.</p>
        )}
      </Panel>

      {evidence.pages.length > 0 ? (
        <Panel title={`Halaman yang diambil · ${evidence.pages.length}`}>
          <ul className="space-y-3">
            {evidence.pages.map((page, index) => (
              <li key={`${page.url}-${index}`} className="rounded-[3px] border border-rule">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                  <a href={page.finalUrl ?? page.url} target="_blank" rel="noopener noreferrer nofollow" className="link min-w-0 flex-1 truncate font-mono text-xs">
                    {displayUrl(page.finalUrl ?? page.url)}
                  </a>
                  {page.origin ? <Tag tone="mute">{EVIDENCE_ORIGIN_LABEL[page.origin] ?? page.origin}</Tag> : null}
                  {page.status ? <span className="font-mono text-2xs text-ink-3">HTTP {page.status}</span> : null}
                  {page.contentType ? <span className="font-mono text-2xs text-ink-3">{page.contentType.split(';')[0]}</span> : null}
                  {page.error ? <Tag tone="warn">{ERROR_KIND_LABEL[page.error] ?? page.error}</Tag> : null}
                  {page.rendered ? <Tag tone="stamp">dirender browser</Tag> : null}
                </div>
                {page.text ? (
                  <details className="border-t border-rule">
                    <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-ink-2">Lihat teks halaman</summary>
                    <pre className="max-h-72 overflow-auto border-t border-rule bg-paper px-3 py-2 font-mono text-2xs leading-relaxed whitespace-pre-wrap">
                      {page.text}
                    </pre>
                  </details>
                ) : null}
                {page.purged ? <p className="border-t border-rule px-3 py-2 text-xs text-ink-3">Teks dihapus (retensi)</p> : null}
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      {evidence.judgments.length > 0 ? (
        <Panel title="Penilaian Jev" aside={<span className="font-mono text-2xs text-ink-3">advisory</span>}>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-3 md:grid-cols-2">
            {evidence.judgments.map((judgment, index) => (
              <JudgmentCard key={`${judgment.url}-${index}`} judgment={judgment} />
            ))}
          </div>
          <p className="mt-3 text-xs text-ink-3">
            Sinyal sumber resmi:{' '}
            <strong className="font-semibold text-ink-2">
              {SOURCE_MATCH_LABEL[String(screening.ai_source_match)]}
            </strong>
            . Sinyal ringan, bukan sertifikasi.
          </p>
        </Panel>
      ) : null}

      {evidence.submissionText ? (
        <Panel title="Teks kiriman (hasil baca AI)">
          <pre className="max-h-80 overflow-auto font-mono text-xs leading-relaxed whitespace-pre-wrap">{evidence.submissionText}</pre>
        </Panel>
      ) : null}

      {evidence.errors.length > 0 ? (
        <Panel title={`Galat pipeline · ${evidence.errors.length}`}>
          <ul className="space-y-1.5 font-mono text-xs">
            {evidence.errors.map((error, index) => (
              <li key={index}>
                <span className="font-semibold">{error.stage ?? '?'}</span> / {error.kind ?? '?'}
                {error.detail ? <span className="text-ink-3">: {error.detail}</span> : null}
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  )
}

function toScreening(detail: SubmissionDetail): ScreeningView | null {
  const run = detail.screening_run
  const result = run?.result_json
  if (!run || !result) {
    return null
  }
  const comparison = (result.comparison ?? null) as { field_verdicts?: Record<string, unknown> } | null
  const site = (result.site_assessment ?? null) as Record<string, unknown> | null
  return {
    state: run.state,
    outcome: typeof result.outcome === 'string' ? result.outcome : null,
    extracted: (result.extraction ?? null) as Record<string, unknown> | null,
    field_verdicts: comparison?.field_verdicts ?? null,
    sources: [],
    ai_source_match: typeof result.ai_source_match === 'boolean' ? result.ai_source_match : null,
    confidence: (result.confidence ?? null) as ScreeningView['confidence'],
    site_assessment: site ? {
      status: typeof site.status === 'string' ? site.status : 'inconclusive',
      issuer_website_candidates: Array.isArray(site.issuer_websites) ? site.issuer_websites.length : 0,
      social_sources: Array.isArray(site.social_sources) ? site.social_sources.length : 0,
      third_party_sources: Array.isArray(site.third_party_sources) ? site.third_party_sources.length : 0,
      unclassified_sources: Array.isArray(site.unclassified_sources) ? site.unclassified_sources.length : 0,
      qr_codes_found: typeof site.qr_codes_found === 'number' ? site.qr_codes_found : 0,
    } : null,
    errors: [],
    finished_at: run.finished_at,
  }
}

export default async function SubmissionEvidencePage({ params }: Props): Promise<ReactNode> {
  const { id } = await params
  const client = await moderatorApi()
  const result = await client
    .GET('/api/v1/moderation/submissions/{submission_id}', { params: { path: { submission_id: id } } })
    .catch(() => null)

  if (result?.response.status === 404 || result?.response.status === 422) {
    return (
      <div className="py-16 text-center">
        <p className="font-semibold">Kiriman tidak ditemukan.</p>
        <Link href="/moderator" className="link mt-2 inline-block text-sm">
          Kembali ke antrean
        </Link>
      </div>
    )
  }
  const detail = result?.data
  if (!detail) {
    return <LoadError what="Kiriman" />
  }

  const run = detail.screening_run
  const evidence = readEvidence(run?.result_json)
  const screening = toScreening(detail)
  const extracted = screening ? readExtracted(screening) : null
  const sourceCandidates: { url: string; label: string }[] = []
  function addSourceCandidate(url: string | null | undefined, label: string): void {
    if (url && !sourceCandidates.some((candidate) => candidate.url === url)) {
      sourceCandidates.push({ url, label })
    }
  }
  for (const site of evidence?.siteAssessment?.issuerWebsites ?? []) {
    addSourceCandidate(site.url, site.basis === 'moderator_confirmed_domain'
      ? 'Domain pernah disetujui moderator' : 'Kandidat situs dinilai AI')
  }
  const terminal = TERMINAL_STATES.has(detail.state)
  const openReports = detail.reports.filter((report) => report.status === 'open').length

  return (
    <>
      <nav aria-label="Remah roti" className="mb-4 text-sm">
        <Link href="/moderator" className="link">
          ← Antrean
        </Link>
      </nav>
      <header className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-ink pb-5">
        <h1 className="font-mono text-2xl font-semibold tracking-wide">{detail.ref}</h1>
        <StateTag state={detail.state} />
        {openReports > 0 ? <Tag tone="bad">{openReports} laporan terbuka</Tag> : null}
        <p className="w-full text-sm text-ink-2 sm:ml-auto sm:w-auto">
          Masuk {formatDateTime(detail.created_at)}
          {detail.purge_after ? <> · data tamu dihapus {formatDate(detail.purge_after)}</> : null}
        </p>
      </header>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="min-w-0 space-y-5">
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-2">
            <Panel title="Kiriman tamu">
              <dl className="space-y-4 text-sm">
                <div>
                  <dt className="text-xs font-semibold text-ink-3">URL</dt>
                  <dd className="mt-0.5">
                    {detail.submitted_url ? (
                      <a href={detail.submitted_url} target="_blank" rel="noopener noreferrer nofollow" className="link font-mono text-xs break-all">
                        {detail.submitted_url}
                      </a>
                    ) : (
                      <span className="text-ink-3">Tidak ada, hanya berkas</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-ink-3">Konteks</dt>
                  <dd className="mt-0.5 whitespace-pre-line">
                    {detail.context ? <q>{detail.context}</q> : <span className="text-ink-3">Tidak diisi</span>}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-ink-3">Kontak</dt>
                  <dd className="mt-0.5 font-mono text-xs">
                    {detail.contact_email ?? <span className="font-sans text-ink-3">Tidak ada / sudah dihapus</span>}
                  </dd>
                </div>
              </dl>
            </Panel>

            <Panel title={`Berkas unggahan · ${detail.uploads.length}`}>
              {detail.uploads.length > 0 ? (
                <ul className="divide-y divide-rule text-sm">
                  {detail.uploads.map((upload) => (
                    <li key={upload.id} className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
                      <span className="min-w-0 flex-1">
                        <a
                          href={`/api/v1/moderation/submissions/${detail.id}/uploads/${upload.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="link block truncate font-medium"
                        >
                          {upload.storage_key}
                        </a>
                        <span className="font-mono text-2xs text-ink-3">
                          {upload.detected_mime.split('/')[1]?.toUpperCase()}
                          {upload.page_count ? ` · ${upload.page_count} hlm` : ''} · {formatBytes(upload.size_bytes)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-3">Tidak ada berkas.</p>
              )}
            </Panel>
          </div>

          <section aria-labelledby="bukti-ai">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="bukti-ai" className="text-lg font-bold">
                Bukti AI <span className="text-sm font-normal text-ink-3">(pendukung, bukan vonis)</span>
              </h2>
              {run ? (
                <p className="font-mono text-2xs text-ink-3">
                  {[run.provider_version, run.model_version].filter(Boolean).join(' · ')}
                  {run.finished_at ? ` · ${formatDateTime(run.finished_at)}` : ''}
                </p>
              ) : null}
            </div>
            {run ? (
              <div className="mb-5 rounded-[3px] border border-rule bg-paper px-4 py-3 text-sm">
                <p className="font-semibold">
                  {run.state === 'complete'
                    ? (OUTCOME_COPY[evidence?.outcome ?? '']?.title ?? 'Pemeriksaan selesai')
                    : `Pemeriksaan ${STATE_LABEL[run.state]?.toLowerCase() ?? run.state}`}
                </p>
                {run.error ? <p className="mt-1 font-mono text-xs text-bad">{run.error}</p> : null}
                {evidence?.submissionPurged ? (
                  <p className="mt-1 text-xs text-ink-3">Teks kiriman sudah dihapus sesuai masa retensi.</p>
                ) : null}
              </div>
            ) : (
              <p className="rounded-[3px] border border-dashed border-rule-2 px-4 py-6 text-sm text-ink-2">
                Belum ada pemeriksaan AI untuk kiriman ini. Keputusan tetap bisa dibuat.
              </p>
            )}
            {evidence && screening ? <EvidenceSection evidence={evidence} screening={screening} /> : null}
          </section>
        </div>

        <aside className="space-y-5 xl:sticky xl:top-6 xl:self-start">
          {terminal ? (
            <div className="rounded-[3px] border border-rule bg-surface p-4 text-sm">
              <p className="font-semibold">Kiriman sudah diputuskan.</p>
              {detail.linked_opportunity_slug ? (
                <Link href={`/katalog/${detail.linked_opportunity_slug}`} className="link mt-1 inline-block">
                  Lihat entri katalog →
                </Link>
              ) : null}
            </div>
          ) : (
            <DecisionPanel
              submissionId={detail.id}
              sourceCandidates={sourceCandidates}
              extracted={extracted}
            />
          )}

          {detail.decisions.length > 0 ? (
            <Panel title="Riwayat keputusan">
              <ol className="space-y-3 text-sm">
                {detail.decisions.map((decision) => (
                  <li key={decision.id}>
                    <p className="font-semibold">{DECISION_LABEL[decision.status] ?? decision.status}</p>
                    <p className="font-mono text-2xs text-ink-3">{formatDateTime(decision.decided_at)}</p>
                    {decision.reason ? <p className="mt-1 text-ink-2">{decision.reason}</p> : null}
                  </li>
                ))}
              </ol>
            </Panel>
          ) : null}

          {detail.reports.length > 0 ? (
            <Panel title={`Laporan komunitas · ${detail.reports.length}`}>
              <ul className="space-y-3 text-sm">
                {detail.reports.map((report) => (
                  <li key={report.id}>
                    <p className="flex items-center gap-2 font-semibold">
                      {REPORT_LABEL[report.category] ?? report.category}
                      {report.status === 'open' ? <Tag tone="bad">terbuka</Tag> : null}
                    </p>
                    <p className="font-mono text-2xs text-ink-3">{formatDateTime(report.created_at)}</p>
                    {report.description ? <p className="mt-1 text-ink-2">{report.description}</p> : null}
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </aside>
      </div>
    </>
  )
}
