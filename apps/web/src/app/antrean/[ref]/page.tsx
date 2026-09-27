import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import { VerificationBadge } from '@/components/badges'
import { ScreeningResult } from '@/components/screening-result'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'antrean',
}

export default async function IncomingDetailPage({
  params,
}: {
  params: Promise<{ ref: string }>
}): Promise<JSX.Element> {
  const { ref } = await params
  const { data, response } = await api.GET(
    '/api/v1/opportunities/incoming/{ref}',
    { params: { path: { ref } } },
  )
  if (response.status === 404 || !data) {
    notFound()
  }

  return (
    <div className="space-y-8 pb-8">
      <div className="space-y-3">
        <Link href="/antrean" className="text-xs text-muted hover:text-ink">
          ← antrean
        </Link>
        <div>
          <p className="font-mono text-xs text-muted">{data.ref}</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            {typeof data.screening?.extracted?.title === 'string' &&
            data.screening.extracted.title
              ? data.screening.extracted.title
              : 'hasil pemeriksaan.'}
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <VerificationBadge verification={data.verification} />
          <span className="text-xs text-muted">
            dikirim {formatDateTime(data.created_at)}
          </span>
        </div>
        {data.submitted_url && (
          <a
            href={data.submitted_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block break-all font-mono text-xs underline underline-offset-4 hover:text-muted"
          >
            {data.submitted_url}
          </a>
        )}
      </div>

      {data.screening && <ScreeningResult screening={data.screening} />}

      <p className="border border-line p-4 text-xs text-muted">
        hasil AI, belum ditinjau moderator. moderator memutuskan apakah ini
        masuk katalog.
      </p>
    </div>
  )
}
