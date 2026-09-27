import type { Metadata } from 'next'
import type { JSX } from 'react'

import { ModerationDetail } from '@/components/moderation-detail'

export const metadata: Metadata = {
  title: 'tinjauan',
  robots: { index: false, follow: false },
}

export default async function AdminDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<JSX.Element> {
  const { id } = await params
  return <ModerationDetail id={id} />
}
