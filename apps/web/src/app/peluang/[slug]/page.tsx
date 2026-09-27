import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import { SourceMatchBadge, VerificationBadge } from '@/components/badges'
import { ReportForm } from '@/components/report-form'
import { api } from '@/lib/api'
import { CATEGORY_LABELS, formatDate } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'peluang',
}

export default async function OpportunityPage({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<JSX.Element> {
  const { slug } = await params
  const { data, response } = await api.GET('/api/v1/opportunities/{slug}', {
    params: { path: { slug } },
  })
  if (response.status === 404 || !data) {
    notFound()
  }

  const rows: Array<[string, string | null]> = [
    ['penyelenggara', data.issuer_name],
    ['kategori', CATEGORY_LABELS[data.category]],
    ['wilayah', data.region],
    ['batas akhir', data.deadline ? formatDate(data.deadline) : null],
    ['diverifikasi', formatDate(data.verified_at)],
  ]

  return (
    <div className="space-y-10 pb-8">
      <div className="space-y-3">
        <Link href="/peluang" className="text-xs text-muted hover:text-ink">
          ← peluang
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight">{data.title}</h1>
        <div className="flex flex-wrap items-center gap-3">
          <VerificationBadge verification={data.verification} />
          <SourceMatchBadge match={data.ai_source_match} />
          {data.status !== 'published' && (
            <span className="text-xs text-bad">
              {data.status === 'expired' ? 'sudah lewat' : data.status}
            </span>
          )}
        </div>
      </div>

      <dl className="divide-y divide-line border-y border-line">
        {rows
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label} className="flex justify-between gap-6 py-2">
              <dt className="text-muted">{label}</dt>
              <dd className="text-right">{value}</dd>
            </div>
          ))}
      </dl>

      <section className="space-y-3">
        <h2 className="text-xs text-muted lowercase">detail.</h2>
        <p className="whitespace-pre-line text-muted">{data.description}</p>
        {data.eligibility && (
          <p className="text-muted">
            <span className="text-ink">syarat: </span>
            {data.eligibility}
          </p>
        )}
      </section>

      {data.source_url ? (
        <a
          href={data.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block bg-ink px-4 py-2 text-paper hover:bg-ink/80"
        >
          buka sumber resmi →
        </a>
      ) : (
        <p className="text-xs text-muted">
          sumber dikonfirmasi langsung ke penyelenggara, tidak ada tautan publik.
        </p>
      )}

      <div className="border-t border-line pt-8">
        <ReportForm slug={data.slug} />
      </div>
    </div>
  )
}
