import type { components, paths } from '@jejakpeluang/contracts/generated'
import createClient from 'openapi-fetch'

// Server components call the API origin directly; the browser uses
// same-origin paths that next.config rewrites to the API, so the
// moderator cookie and the CSRF Origin check both work unchanged.
const isServer = typeof window === 'undefined'

export const API_ORIGIN = process.env.API_INTERNAL_ORIGIN ?? 'http://localhost:8000'

export const api = createClient<paths>({
  baseUrl: isServer ? API_ORIGIN : '',
  cache: 'no-store',
})

type Schemas = components['schemas']

export type OpportunitySummary = Schemas['OpportunitySummary']
export type OpportunityDetail = Schemas['OpportunityDetail']
export type IncomingItem = Schemas['IncomingItem']
export type ScreeningView = Schemas['ScreeningView']
export type SourceCheck = Schemas['SourceCheck']
export type SubmissionStatus = Schemas['SubmissionStatus']
export type SubmissionCreated = Schemas['SubmissionCreated']
export type DedupeCheck = Schemas['DedupeCheck']
export type QueueItem = Schemas['QueueItem']
export type SubmissionDetail = Schemas['SubmissionDetail']
export type DecisionRequest = Schemas['DecisionRequest']
export type DecisionFields = Schemas['DecisionFields']
export type ReportRequest = Schemas['ReportRequest']
export type UserRead = Schemas['UserRead']

export type Category = OpportunitySummary['category']
export type TrustBasis = OpportunitySummary['trust_basis']

export const CATEGORIES: Category[] = ['scholarship', 'internship', 'competition']

export function isCategory(value: unknown): value is Category {
  return typeof value === 'string' && (CATEGORIES as string[]).includes(value)
}

// FastAPI returns `detail` as a string, a list of validation errors, or an
// object (e.g. the 409 duplicate payload). Collapse it into one sentence.
export function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown }
    if (typeof first.msg === 'string') {
      return first.msg
    }
  }
  return fallback
}

export async function readDetail(response: Response): Promise<unknown> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return body.detail
  } catch {
    return undefined
  }
}
