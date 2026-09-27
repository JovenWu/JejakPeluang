'use client'

import dynamic from 'next/dynamic'
import type { ReactNode } from 'react'

// The receipt token only exists in the browser (sessionStorage / URL
// fragment), so there is nothing useful to server-render here.
const SubmissionView = dynamic(() => import('./submission-view').then((mod) => mod.SubmissionView), {
  ssr: false,
  loading: () => <div className="scan-bar max-w-xs" aria-label="Memuat" />,
})

export function SubmissionViewLoader({ refCode }: { refCode: string }): ReactNode {
  return <SubmissionView refCode={refCode} />
}
