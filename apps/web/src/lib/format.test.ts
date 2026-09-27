import { describe, expect, it } from 'vitest'

import {
  CATEGORY_LABELS,
  formatDate,
  hostOf,
  VERDICT_LABELS,
} from './format'

describe('format helpers', () => {
  it('labels every category', () => {
    expect(CATEGORY_LABELS.scholarship).toBe('beasiswa')
    expect(CATEGORY_LABELS.internship).toBe('magang')
    expect(CATEGORY_LABELS.competition).toBe('lomba')
  })

  it('labels every backend verdict', () => {
    for (const verdict of [
      'supported',
      'conflicting',
      'not_found',
      'unreadable',
    ]) {
      expect(VERDICT_LABELS[verdict]).toBeTruthy()
    }
  })

  it('formats iso dates for Indonesian readers', () => {
    expect(formatDate('2026-11-30')).toContain('Nov')
    expect(formatDate(null)).toBe('')
  })

  it('extracts the host from a url', () => {
    expect(hostOf('https://kemdikbud.go.id/path?x=1')).toBe(
      'kemdikbud.go.id',
    )
    expect(hostOf('bukan url')).toBe('bukan url')
    expect(hostOf(null)).toBe('')
  })
})
