import { describe, expect, it } from 'vitest'

import type { ScreeningView } from './api'
import { degradedCopy, headlineText, readExtracted, readVerdicts, summarize } from './screening'

function screening(overrides: Partial<ScreeningView>): ScreeningView {
  return {
    state: 'complete',
    outcome: 'complete',
    extracted: null,
    field_verdicts: null,
    sources: [],
    ai_source_match: null,
    errors: [],
    finished_at: '2026-09-27T10:00:00Z',
    ...overrides,
  }
}

describe('summarize', () => {
  it('reports running until the run finishes', () => {
    expect(summarize(screening({ state: 'processing', outcome: null })).headline).toBe('running')
    expect(summarize(null).headline).toBe('running')
  })

  it('prefers conflicts over an official match', () => {
    const view = screening({
      ai_source_match: true,
      field_verdicts: {
        title: { verdict: 'supported', quote: 'Beasiswa Unggulan' },
        deadline: { verdict: 'conflicting', quote: '30 Oktober 2026' },
      },
      sources: [{ url: 'https://a.go.id', status: 200, official: true }],
    })
    const summary = summarize(view)
    expect(summary).toMatchObject({ headline: 'conflict', supported: 1, conflicting: 1, compared: 2, officialSources: 1 })
    expect(headlineText(summary, view)).toBe('1 data berbeda dari sumber')
  })

  it('never produces safe/scam wording', () => {
    const outcomes = ['complete', 'no_public_source', 'no_content', 'provider_unavailable', 'manual_review_required']
    for (const outcome of outcomes) {
      for (const match of [true, false, null]) {
        const view = screening({ outcome, ai_source_match: match })
        const text = headlineText(summarize(view), view).toLowerCase()
        expect(text).not.toMatch(/\b(aman|penipuan|scam|safe|palsu)\b/)
      }
    }
  })
})

describe('degradedCopy', () => {
  it('distinguishes an unreachable link from an unreadable page', () => {
    const unreachable = screening({
      outcome: 'no_content',
      sources: [{ url: 'https://x.id', status: null, official: null, error: 'dns_blocked' }],
    })
    expect(degradedCopy(unreachable).title).toBe('Tautan tidak bisa dibuka')
    const jsOnly = screening({
      outcome: 'no_content',
      sources: [{ url: 'https://x.id', status: 200, official: null, error: 'js_required' }],
    })
    expect(degradedCopy(jsOnly).title).toBe('Isi kiriman tidak bisa dibaca')
  })
})

describe('readers', () => {
  it('drops malformed extraction and verdict values', () => {
    const view = screening({
      extracted: { title: '  ', issuer: 'Kemendikbud', requested_data: ['KTP', 3, ''] },
      field_verdicts: { title: { verdict: 'nonsense' }, issuer: { verdict: 'supported', quote: null } },
    })
    expect(readExtracted(view)).toMatchObject({ title: null, issuer: 'Kemendikbud', requested_data: ['KTP'] })
    expect(readVerdicts(view)).toEqual({ issuer: { verdict: 'supported', quote: null } })
  })
})
