import type { components, paths } from '@jejakpeluang/contracts/generated'
import createClient from 'openapi-fetch'

import type { Category, Status } from './format'

export type OpportunitySummary = components['schemas']['OpportunitySummary']
export type OpportunityDetail = components['schemas']['OpportunityDetail']

const client = createClient<paths>({
  baseUrl: process.env.API_INTERNAL_ORIGIN ?? 'http://localhost:8000',
})

export interface CatalogueQuery {
  category?: Category | null
  q?: string | null
}

export interface CataloguePage {
  items: OpportunitySummary[]
  total: number
}

export async function listOpportunities(query: CatalogueQuery = {}): Promise<CataloguePage> {
  const { data, error } = await client.GET('/api/v1/opportunities', {
    params: {
      query: {
        category: query.category ?? null,
        q: query.q ?? null,
        limit: 20,
        offset: 0,
      },
    },
  })
  if (error || !data) {
    throw new Error('Katalog belum dapat dimuat')
  }
  return { items: data.items, total: data.total }
}

export async function getOpportunity(slug: string): Promise<OpportunityDetail | null> {
  const { data, error, response } = await client.GET('/api/v1/opportunities/{slug}', {
    params: { path: { slug } },
  })
  if (response.status === 404) {
    return null
  }
  if (error || !data) {
    throw new Error('Peluang belum dapat dimuat')
  }
  return data
}

export type { Category, Status }
