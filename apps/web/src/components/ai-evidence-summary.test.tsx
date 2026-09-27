import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ScreeningView } from '@/lib/api'

import { AiEvidenceSummary } from './ai-evidence-summary'

function screening(overrides: Partial<ScreeningView> = {}): ScreeningView {
  return {
    state: 'complete',
    outcome: 'complete',
    extracted: null,
    field_verdicts: null,
    sources: [],
    ai_source_match: null,
    errors: [],
    finished_at: null,
    ...overrides,
  }
}

describe('AiEvidenceSummary', () => {
  it('explains when an older run has no evidence score', () => {
    render(<AiEvidenceSummary screening={screening()} />)

    expect(screen.getByText(/hasil pemeriksaan lama/)).toBeTruthy()
  })

  it('shows the support score and its evidence coverage', () => {
    render(
      <AiEvidenceSummary
        screening={screening({
          confidence: {
            score: 76,
            label: 'moderate',
            fields_available: 9,
            fields_checked: 6,
            fields_supported: 5,
            source_level: 'issuer_website_found',
            method: 'evidence-support-v1',
          },
          site_assessment: {
            status: 'issuer_website_found',
            issuer_website_candidates: 1,
            social_sources: 1,
            third_party_sources: 0,
            unclassified_sources: 0,
            qr_codes_found: 1,
          },
        })}
      />,
    )

    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('76')
    expect(screen.getByText('Sedang')).toBeTruthy()
    expect(screen.getByText(/5 dari 6 data yang dibandingkan/)).toBeTruthy()
    expect(screen.getByText(/bukan probabilitas/)).toBeTruthy()
  })
})
