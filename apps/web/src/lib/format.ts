import type { components } from '@jejakpeluang/contracts/generated'

export type Category = components['schemas']['OpportunitySummary']['category']
export type Status = components['schemas']['OpportunitySummary']['status']

const CATEGORY_LABELS: Record<Category, string> = {
  scholarship: 'Beasiswa',
  internship: 'Magang',
  competition: 'Kompetisi',
}

const DEADLINE_SOON_DAYS = 14
const DAY_MS = 86_400_000

export function categoryLabel(category: Category): string {
  return CATEGORY_LABELS[category]
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('id-ID', {
    dateStyle: 'medium',
    timeZone: 'UTC',
  }).format(new Date(value))
}

export function formatDeadline(deadline: string): string {
  return formatDate(`${deadline}T00:00:00Z`)
}

export function daysUntilDeadline(deadline: string): number {
  return Math.ceil((Date.parse(`${deadline}T00:00:00Z`) - Date.now()) / DAY_MS)
}

export function isDeadlineSoon(deadline: string | null, status: Status): boolean {
  if (deadline === null || status !== 'published') {
    return false
  }
  const days = daysUntilDeadline(deadline)
  return days >= 0 && days <= DEADLINE_SOON_DAYS
}

export function deadlineCountdown(deadline: string): string {
  const days = daysUntilDeadline(deadline)
  if (days <= 0) {
    return 'hari ini'
  }
  if (days === 1) {
    return 'besok'
  }
  return `${days} hari lagi`
}
