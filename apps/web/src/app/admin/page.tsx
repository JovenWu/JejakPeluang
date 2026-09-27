import type { Metadata } from 'next'
import type { JSX } from 'react'

import { QueueView } from '@/components/queue-view'

export const metadata: Metadata = {
  title: 'antrean moderator',
  robots: { index: false, follow: false },
}

export default function AdminPage(): JSX.Element {
  return <QueueView />
}
