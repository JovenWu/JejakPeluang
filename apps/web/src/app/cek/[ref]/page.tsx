import type { Metadata } from 'next'
import type { JSX } from 'react'

import { StatusPoll } from '@/components/status-poll'

export const metadata: Metadata = {
  title: 'hasil cek',
}

export default async function CheckStatusPage({
  params,
  searchParams,
}: {
  params: Promise<{ ref: string }>
  searchParams: Promise<{ new?: string }>
}): Promise<JSX.Element> {
  const { ref } = await params
  const query = await searchParams
  return <StatusPoll refId={ref} isNew={query.new === '1'} />
}
