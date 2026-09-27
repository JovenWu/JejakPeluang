import type { paths } from '@jejakpeluang/contracts/generated'
import createClient from 'openapi-fetch'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

import { API_ORIGIN, type UserRead } from './api'

// Server-side client that forwards the moderator's session cookie. Only
// GETs go through here, so the API's CSRF Origin check never applies.
export async function moderatorApi(): Promise<ReturnType<typeof createClient<paths>>> {
  const jar = await cookies()
  return createClient<paths>({
    baseUrl: API_ORIGIN,
    cache: 'no-store',
    headers: { cookie: jar.toString() },
  })
}

export async function requireModerator(): Promise<UserRead> {
  const client = await moderatorApi()
  const { data, response } = await client.GET('/api/v1/users/me')
  if (response.status === 401 || response.status === 403) {
    redirect('/moderator/masuk')
  }
  if (!data) {
    throw new Error(`users/me failed with HTTP ${response.status}`)
  }
  if (data.role !== 'moderator') {
    redirect('/moderator/masuk?galat=peran')
  }
  return data
}
