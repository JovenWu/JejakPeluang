import type { ReactNode } from 'react'

import type { ScreeningView } from '@/lib/api'
import { displayUrl, formatDate, formatDateTime } from '@/lib/format'
import {
  COMPARED_FIELDS,
  type ComparedField,
  ERROR_KIND_LABEL,
  ERROR_STAGE_LABEL,
  EXTRACTED_CATEGORY_LABEL,
  type Extracted,
  FIELD_LABEL,
  headlineText,
  degradedCopy,
  readExtracted,
  readVerdicts,
  SOURCE_ERROR_LABEL,
  summarize,
} from '@/lib/screening'

import { AiEvidenceSummary } from './ai-evidence-summary'
import { HEADLINE_TONE, Tag, VerdictTag } from './tags'

interface Props {
  screening: ScreeningView
}

function extractedValue(extracted: Extracted | null, field: ComparedField): string | null {
  const value = extracted?.[field] ?? null
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : null
  }
  if (typeof value !== 'string' || !value) {
    return null
  }
  if (field === 'deadline' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return formatDate(value)
  }
  if (field === 'category') {
    return EXTRACTED_CATEGORY_LABEL[value] ?? value
  }
  return value
}

const DRAFT_FIELDS: ComparedField[] = [
  'title',
  'issuer',
  'category',
  'deadline',
  'region',
  'description',
  'eligibility',
  'fees',
  'requested_data',
]

const HEADLINE_BAR: Record<string, string> = {
  ok: 'border-ok',
  bad: 'border-bad',
  warn: 'border-warn',
  mute: 'border-ink-3',
  stamp: 'border-stamp',
}

export function ScreeningReport({ screening }: Props): ReactNode {
  const summary = summarize(screening)
  const extracted = readExtracted(screening)
  const verdicts = readVerdicts(screening)
  const tone = HEADLINE_TONE[summary.headline]
  const degraded = degradedCopy(screening)
  const hasCatalogDraft = extracted !== null && DRAFT_FIELDS.some((field) => extractedValue(extracted, field) !== null)
  const rows = COMPARED_FIELDS.filter((field) => verdicts[field] || extractedValue(extracted, field))

  return (
    <div className="space-y-10">
      <section aria-labelledby="ringkasan" className={`border-l-4 pl-4 ${HEADLINE_BAR[tone]}`}>
        <p className="kicker mb-1">Ringkasan pemeriksaan</p>
        <h2 id="ringkasan" className="text-xl font-bold tracking-tight sm:text-2xl">
          {headlineText(summary, screening)}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-2">
          {summary.headline === 'degraded' || summary.headline === 'failed'
            ? degraded.body
            : `${summary.supported} dari ${summary.compared} data yang dibandingkan cocok dengan sumber web.${
                summary.officialSources > 0
                  ? ` AI menilai ${summary.officialSources} halaman sebagai pengumuman penerbit.`
                  : ' Belum ada halaman yang dinilai AI sebagai pengumuman penerbit.'
              }`}
        </p>
        {screening.finished_at ? (
          <p className="mt-2 font-mono text-2xs text-ink-3">Selesai {formatDateTime(screening.finished_at)}</p>
        ) : null}
      </section>

      <AiEvidenceSummary screening={screening} />

      {hasCatalogDraft ? (
        <section aria-labelledby="draf-katalog">
          <h3 id="draf-katalog" className="kicker mb-1">Draf entri katalog dari AI</h3>
          <p className="mb-3 text-sm text-ink-3">
            Dirangkum dari teks kiriman, OCR gambar atau PDF, dan tujuan QR yang terbaca. Kolom kosong berarti belum ditemukan.
          </p>
          <dl className="grid gap-px overflow-hidden rounded-[3px] border border-rule bg-rule sm:grid-cols-2">
            {DRAFT_FIELDS.map((field) => {
              const value = extractedValue(extracted, field)
              const wide = field === 'region' || field === 'description' || field === 'eligibility'
              return (
                <div key={field} className={`min-w-0 bg-surface p-4 ${wide ? 'sm:col-span-2' : ''}`}>
                  <dt className="kicker mb-1">{FIELD_LABEL[field]}</dt>
                  <dd className="text-sm leading-relaxed">
                    {value ?? <span className="text-ink-3">Belum terbaca</span>}
                  </dd>
                </div>
              )
            })}
          </dl>
        </section>
      ) : null}

      {rows.length > 0 ? (
        <section aria-labelledby="perbandingan">
          <h3 id="perbandingan" className="kicker mb-3">
            Dibandingkan dengan sumber web
          </h3>
          <table className="w-full border-collapse text-sm">
            <thead className="sr-only sm:not-sr-only">
              <tr className="border-b border-ink text-left">
                <th scope="col" className="kicker py-2 pr-4 font-normal">Data</th>
                <th scope="col" className="kicker py-2 pr-4 font-normal">Di kiriman</th>
                <th scope="col" className="kicker py-2 pr-4 font-normal">Hasil</th>
                <th scope="col" className="kicker py-2 font-normal">Kutipan sumber</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((field) => {
                const verdict = verdicts[field]
                const value = extractedValue(extracted, field)
                return (
                  <tr key={field} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 border-b border-rule py-3 align-top sm:table-row sm:py-0">
                    <th scope="row" className="text-left font-semibold sm:w-28 sm:py-3 sm:pr-4">
                      {FIELD_LABEL[field]}
                    </th>
                    <td className="col-span-2 row-start-2 sm:py-3 sm:pr-4">
                      {value ?? <span className="text-ink-3">Tidak disebut</span>}
                    </td>
                    <td className="col-start-2 row-start-1 text-right sm:w-32 sm:py-3 sm:pr-4 sm:text-left">
                      {verdict ? <VerdictTag verdict={verdict.verdict} /> : <span className="text-ink-3">-</span>}
                    </td>
                    <td className="col-span-2 text-ink-2 sm:py-3">
                      {verdict?.quote ? (
                        <q className="font-mono text-xs leading-relaxed before:text-ink-3 after:text-ink-3">{verdict.quote}</q>
                      ) : (
                        <span className="hidden text-ink-3 sm:inline">-</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      {screening.sources.length > 0 ? (
        <section aria-labelledby="sumber">
          <h3 id="sumber" className="kicker mb-3">
            Halaman yang dibuka AI · {screening.sources.length}
          </h3>
          <ol className="divide-y divide-rule border-y border-rule">
            {screening.sources.map((source, index) => (
              <li key={`${source.url}-${index}`} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-3">
                <span className="font-mono text-2xs text-ink-3 tabular-nums">{String(index + 1).padStart(2, '0')}</span>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow ugc"
                  className="link min-w-0 basis-[calc(100%-2.5rem)] truncate font-mono text-xs sm:basis-0 sm:flex-1"
                >
                  {displayUrl(source.url)}
                </a>
                <span className="flex flex-wrap items-center gap-2 pl-9 sm:pl-0">
                  {source.origin === 'qr_code' ? <Tag tone="stamp">Tautan dari QR</Tag> : null}
                  {source.error ? (
                    <Tag tone="warn">{SOURCE_ERROR_LABEL[source.error] ?? source.error}</Tag>
                  ) : null}
                  {source.official === true ? <Tag tone="ok">Kandidat pengumuman penerbit</Tag> : null}
                  {source.official === false ? <Tag tone="mute">Bukan pengumuman penerbit</Tag> : null}
                  {source.official === null && !source.error ? <Tag tone="mute">Belum dinilai</Tag> : null}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {screening.errors.length > 0 ? (
        <p className="text-xs leading-relaxed text-ink-3">
          Tahap yang terkendala:{' '}
          {screening.errors
            .map((error) => {
              const stage = ERROR_STAGE_LABEL[error.stage ?? ''] ?? 'pemeriksaan'
              const kind = ERROR_KIND_LABEL[error.kind ?? '']
              return kind ? `${stage} (${kind})` : stage
            })
            .join(' · ')}
        </p>
      ) : null}

      <p className="rounded-[3px] bg-sunk px-4 py-3 text-sm leading-relaxed text-ink-2">
        Ini hasil pembacaan AI, <strong className="font-semibold text-ink">bukan vonis aman atau penipuan</strong>. AI hanya
        melaporkan apa yang tertulis dan apa yang ditemukan di web. Keputusan masuk katalog selalu dibuat moderator.
      </p>
    </div>
  )
}

const STEPS = ['Membaca isi kiriman', 'Mencari halaman sumber di web', 'Membandingkan data per kolom', 'Menilai apakah sumber resmi']

export function ScreeningPending({ state }: { state: string | null | undefined }): ReactNode {
  const active = state === 'processing' ? 1 : 0
  return (
    <section aria-live="polite" aria-busy="true" className="space-y-5">
      <div>
        <p className="kicker mb-1">Pemeriksaan AI</p>
        <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
          {state === 'processing' ? 'AI sedang memeriksa…' : 'Menunggu giliran diperiksa…'}
        </h2>
        <p className="mt-1 text-sm text-ink-2">Biasanya selesai dalam kurang dari satu menit. Halaman ini diperbarui sendiri.</p>
      </div>
      <div className="scan-bar" />
      <ol className="space-y-2 text-sm">
        {STEPS.map((step, index) => (
          <li key={step} className={`flex items-center gap-3 ${index <= active ? 'text-ink' : 'text-ink-3'}`}>
            <span className="font-mono text-2xs tabular-nums">{String(index + 1).padStart(2, '0')}</span>
            {step}
          </li>
        ))}
      </ol>
    </section>
  )
}
