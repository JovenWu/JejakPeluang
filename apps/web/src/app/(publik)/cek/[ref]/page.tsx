import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { SubmissionViewLoader } from '@/components/submission-view-loader'

interface Props {
  params: Promise<{ ref: string }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ref } = await params
  return { title: `Kiriman ${decodeURIComponent(ref)}`, robots: { index: false } }
}

export default async function SubmissionPage({ params }: Props): Promise<ReactNode> {
  const { ref } = await params
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
      <SubmissionViewLoader refCode={decodeURIComponent(ref).toUpperCase()} />
    </div>
  )
}
