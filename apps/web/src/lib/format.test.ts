import { describe, expect, it } from 'vitest'

import { daysUntil, deadlineInfo, displayUrl, formatDate, hostOf, relativeTime } from './format'

describe('deadline math in WIB', () => {
  it('counts days against the Jakarta calendar, not UTC', () => {
    // 23:30 WIB on 30 Nov is still 30 Nov locally, although UTC says 30 Nov 16:30.
    const lateEvening = new Date('2026-11-30T16:30:00Z')
    expect(daysUntil('2026-11-30', lateEvening)).toBe(0)
    // 00:30 WIB on 1 Dec is 30 Nov 17:30 UTC, so the deadline has passed locally.
    const pastMidnight = new Date('2026-11-30T17:30:00Z')
    expect(daysUntil('2026-11-30', pastMidnight)).toBe(-1)
  })

  it('labels each tone', () => {
    const now = new Date('2026-09-27T03:00:00Z')
    expect(deadlineInfo(null, now)).toEqual({ tone: 'none', label: 'Tanpa tenggat' })
    expect(deadlineInfo('2026-09-26', now)).toEqual({ tone: 'closed', label: 'Sudah ditutup' })
    expect(deadlineInfo('2026-09-27', now)).toEqual({ tone: 'urgent', label: 'Berakhir hari ini' })
    expect(deadlineInfo('2026-09-28', now)).toEqual({ tone: 'urgent', label: 'Berakhir besok' })
    expect(deadlineInfo('2026-10-10', now).tone).toBe('soon')
    expect(deadlineInfo('2026-12-31', now).tone).toBe('open')
  })

  it('formats date-only values without shifting the day', () => {
    expect(formatDate('2026-11-30')).toMatch(/30 Nov 2026/)
  })
})

describe('url helpers', () => {
  it('strips www and keeps the path for display', () => {
    expect(hostOf('https://www.kemdikbud.go.id/a')).toBe('kemdikbud.go.id')
    expect(displayUrl('https://www.kemdikbud.go.id/')).toBe('kemdikbud.go.id')
    expect(displayUrl('https://lpdp.kemenkeu.go.id/beasiswa?x=1')).toBe('lpdp.kemenkeu.go.id/beasiswa?x=1')
    expect(hostOf(null)).toBe('')
  })
})

describe('relativeTime', () => {
  it('uses Indonesian units', () => {
    const now = new Date('2026-09-27T10:00:00Z')
    expect(relativeTime('2026-09-27T09:59:30Z', now)).toBe('baru saja')
    expect(relativeTime('2026-09-27T09:15:00Z', now)).toBe('45 menit lalu')
    expect(relativeTime('2026-09-27T07:00:00Z', now)).toBe('3 jam lalu')
    expect(relativeTime('2026-09-25T10:00:00Z', now)).toBe('2 hari lalu')
  })
})
