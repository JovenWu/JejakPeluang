import type { JSX } from 'react'

import type { ScreeningView } from '@/lib/api'
import {
  CATEGORY_LABELS,
  FIELD_LABELS,
  OUTCOME_LABELS,
} from '@/lib/format'
import type { Category } from '@/lib/api'

import { SourceMatchBadge, VerdictBadge } from './badges'
import { Card, CardHeader } from './ui'

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

const SOURCE_ERROR_LABELS: Record<string, string> = {
  js_required: 'butuh JavaScript',
  empty_content: 'tidak ada teks',
}

function sourceErrorLabel(kind: string): string {
  return SOURCE_ERROR_LABELS[kind] ?? 'gagal diambil'
}

function fieldText(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : '—'
  }
  return String(value)
}

export function ScreeningResult({
  screening,
}: {
  screening: ScreeningView
}): JSX.Element {
  const extracted = screening.extracted ?? {}
  const verdicts = screening.field_verdicts ?? {}
  const outcomeLabel = screening.outcome
    ? (OUTCOME_LABELS[screening.outcome] ?? screening.outcome)
    : ''

  if (screening.state === 'failed') {
    return (
      <Card className="p-5">
        <p className="text-sm text-bad">
          Pemeriksaan gagal, coba kirim ulang nanti.
        </p>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          eyebrow="Hasil pemeriksaan"
          hint={screening.finished_at ? undefined : ''}
        />
        <div className="space-y-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-ai-tint px-2.5 py-1 text-[11px] font-semibold leading-none text-ai">
              hasil AI, bukan vonis
            </span>
            <SourceMatchBadge match={screening.ai_source_match} />
          </div>
          <p className="text-sm text-body">{outcomeLabel}</p>
          {screening.errors.length > 0 && (
            <p className="text-xs text-faint">
              sebagian pemeriksaan tidak tuntas:{' '}
              {screening.errors
                .map((error) => error.kind ?? error.stage)
                .filter(Boolean)
                .join(', ')}
            </p>
          )}
        </div>
      </Card>

      {screening.extracted && (
        <Card>
          <CardHeader eyebrow="Detail dari kiriman" />
          <dl className="divide-y divide-line">
            {FIELD_ORDER.filter((field) => field in extracted).map(
              (field) => (
                <div
                  key={field}
                  className="flex items-baseline justify-between gap-6 px-5 py-3"
                >
                  <dt className="text-sm text-body">
                    {FIELD_LABELS[field] ?? field}
                  </dt>
                  <dd className="text-right text-sm font-medium">
                    {field === 'category' &&
                    typeof extracted[field] === 'string' &&
                    extracted[field] in CATEGORY_LABELS
                      ? CATEGORY_LABELS[extracted[field] as Category]
                      : fieldText(extracted[field])}
                  </dd>
                </div>
              ),
            )}
          </dl>
        </Card>
      )}

      {screening.sources.length > 0 && (
        <Card>
          <CardHeader eyebrow="Sumber yang diperiksa" />
          <ul className="divide-y divide-line">
            {screening.sources.map((source) => (
              <li
                key={source.url}
                className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
              >
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-w-0 break-all font-mono text-xs text-body hover:text-ink hover:underline"
                >
                  {source.url}
                </a>
                <span className="shrink-0">
                  {source.error ? (
                    <span className="rounded-full bg-warn-tint px-2.5 py-1 text-[11px] font-semibold leading-none text-warn-ink">
                      {sourceErrorLabel(source.error)}
                    </span>
                  ) : source.official === true ? (
                    <span className="rounded-full bg-good-tint px-2.5 py-1 text-[11px] font-semibold leading-none text-good">
                      resmi
                    </span>
                  ) : source.official === false ? (
                    <span className="rounded-full bg-surface px-2.5 py-1 text-[11px] font-semibold leading-none text-body">
                      bukan resmi
                    </span>
                  ) : (
                    <span className="text-xs text-faint">
                      {source.status === null
                        ? 'gagal diambil'
                        : `status ${source.status}`}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {Object.keys(verdicts).length > 0 && (
        <Card>
          <CardHeader eyebrow="Perbandingan dengan sumber" />
          <ul className="divide-y divide-line">
            {Object.entries(verdicts).map(([field, raw]) => {
              const verdict = raw as {
                verdict?: string
                quote?: string | null
              }
              return (
                <li key={field} className="px-5 py-3">
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="text-sm text-body">
                      {FIELD_LABELS[field] ?? field}
                    </span>
                    <VerdictBadge verdict={verdict.verdict ?? ''} />
                  </div>
                  {verdict.quote && (
                    <p className="mt-1.5 text-xs leading-5 text-faint">
                      &ldquo;{verdict.quote}&rdquo;
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </div>
  )
}
