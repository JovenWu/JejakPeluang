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
  title: 'Antrean',
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

  const extracted = data.screening?.extracted
  const title =
    typeof extracted?.title === 'string' && extracted.title
      ? extracted.title
      : 'Hasil pemeriksaan'

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-10">
      <nav className="flex items-center gap-2 text-xs text-faint">
        <Link href="/antrean" className="hover:text-ink">
          Antrean
        </Link>
        <span>/</span>
        <span className="font-mono text-ink">{data.ref}</span>
      </nav>

      <div className="mt-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <VerificationBadge verification={data.verification} />
          <span className="text-xs text-faint">
            dikirim {formatDateTime(data.created_at)}
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold tracking-[-0.02em]">
          {title}
        </h1>
        {data.submitted_url && (
          <a
            href={data.submitted_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block break-all font-mono text-xs text-body hover:text-ink hover:underline"
          >
            {data.submitted_url}
          </a>
        )}
      </div>

      <div className="mt-8">
        {data.screening && <ScreeningResult screening={data.screening} />}
      </div>

      <div className="mt-6 rounded-xl border border-ai/30 bg-ai-tint/40 p-5">
        <p className="text-sm font-medium text-ai">
          Hasil AI, belum ditinjau moderator.
        </p>
        <p className="mt-1 text-sm leading-6 text-body">
          Moderator memutuskan apakah kiriman ini masuk katalog sebagai
          peluang terverifikasi.
        </p>
      </div>
    </div>
  )
}
