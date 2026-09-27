import type { JSX } from 'react'

import type { ScreeningView } from '@/lib/api'
import {
  CATEGORY_LABELS,
  FIELD_LABELS,
  OUTCOME_LABELS,
} from '@/lib/format'
import type { Category } from '@/lib/api'

import { SourceMatchBadge, VerdictBadge } from './badges'

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

function fieldText(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : '-'
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

  return (
    <div className="space-y-10">
      {screening.state === 'failed' && (
        <p className="text-muted">
          pemeriksaan gagal, silakan coba lagi nanti.
        </p>
      )}

      {screening.state === 'complete' && (
        <>
          <div>
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-xs text-muted lowercase">hasil.</h2>
              <SourceMatchBadge match={screening.ai_source_match} />
            </div>
            <p className="mt-2 text-xs text-muted">{outcomeLabel}</p>
          </div>

          {screening.extracted && (
            <section>
              <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
                detail dari kiriman.
              </h3>
              <dl className="divide-y divide-line">
                {FIELD_ORDER.filter((field) => field in extracted).map(
                  (field) => (
                    <div
                      key={field}
                      className="flex justify-between gap-6 py-2"
                    >
                      <dt className="text-muted">
                        {FIELD_LABELS[field] ?? field}
                      </dt>
                      <dd className="text-right">
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
            </section>
          )}

          {screening.sources.length > 0 && (
            <section>
              <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
                sumber yang diperiksa.
              </h3>
              <ul className="divide-y divide-line">
                {screening.sources.map((source) => (
                  <li
                    key={source.url}
                    className="flex items-baseline justify-between gap-4 py-2"
                  >
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate underline underline-offset-4 hover:text-muted"
                    >
                      {source.url}
                    </a>
                    <span className="shrink-0 text-xs">
                      {source.official === true && (
                        <span className="text-good">resmi</span>
                      )}
                      {source.official === false && (
                        <span className="text-muted">bukan resmi</span>
                      )}
                      {source.official === null && (
                        <span className="text-muted">
                          {source.status === null
                            ? 'gagal diambil'
                            : `status ${source.status}`}
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {Object.keys(verdicts).length > 0 && (
            <section>
              <h3 className="border-b border-line pb-2 text-xs text-muted lowercase">
                perbandingan dengan sumber.
              </h3>
              <ul className="divide-y divide-line">
                {Object.entries(verdicts).map(([field, raw]) => {
                  const verdict = raw as {
                    verdict?: string
                    quote?: string | null
                  }
                  return (
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
                  )
                })}
              </ul>
            </section>
          )}

          {screening.errors.length > 0 && (
            <p className="text-xs text-muted">
              sebagian pemeriksaan tidak tuntas:{' '}
              {screening.errors
                .map((error) => error.stage)
                .filter(Boolean)
                .join(', ')}
            </p>
          )}
        </>
      )}
    </div>
  )
}
