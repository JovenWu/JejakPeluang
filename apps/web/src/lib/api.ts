import type { components, paths } from '@jejakpeluang/contracts/generated'
import createClient from 'openapi-fetch'

// Server components call the internal origin directly; the browser hits
// same-origin paths which Next rewrites to the API (cookies flow through).
const isServer = typeof window === 'undefined'
const baseUrl = isServer
  ? (process.env.API_INTERNAL_ORIGIN ?? 'http://localhost:8000')
  : ''

export const api = createClient<paths>({ baseUrl })

export type OpportunitySummary = components['schemas']['OpportunitySummary']
export type OpportunityDetail = components['schemas']['OpportunityDetail']
export type IncomingItem = components['schemas']['IncomingItem']
export type ScreeningView = components['schemas']['ScreeningView']
export type SubmissionStatus = components['schemas']['SubmissionStatus']
export type SubmissionCreated = components['schemas']['SubmissionCreated']
export type DedupeCheck = components['schemas']['DedupeCheck']
export type QueueItem = components['schemas']['QueueItem']
export type SubmissionDetail = components['schemas']['SubmissionDetail']
export type DecisionRequest = components['schemas']['DecisionRequest']
export type ReportRequest = components['schemas']['ReportRequest']
export type UserRead = components['schemas']['UserRead']

export type Category = OpportunitySummary['category']
export type Verification = OpportunitySummary['verification']

export const CATEGORIES: Category[] = [
  'scholarship',
  'internship',
  'competition',
]
