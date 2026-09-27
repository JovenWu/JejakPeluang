import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import type { JSX } from 'react'

import {
  CategoryBadge,
  SourceMatchBadge,
  VerificationBadge,
} from '@/components/badges'
import { ReportForm } from '@/components/report-form'
import { Card, CardHeader } from '@/components/ui'
import { api } from '@/lib/api'
import { formatDate, hostOf } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Peluang',
}

const TRUST_LABELS: Record<string, string> = {
  public_source: 'Sumber publik',
  issuer_confirmed_private: 'Dikonfirmasi langsung ke penyelenggara',
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

  const meta: Array<[string, string]> = [
    ['Batas akhir', data.deadline ? formatDate(data.deadline) : 'Tanpa tenggat'],
    ['Wilayah', data.region || 'Indonesia'],
    ['Penyelenggara', data.issuer_name],
    ['Terakhir dicek', formatDate(data.checked_at || data.verified_at)],
  ]

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-10">
      <nav className="flex items-center gap-2 text-xs text-faint">
        <Link href="/peluang" className="hover:text-ink">
          Katalog
        </Link>
        <span>/</span>
        <span className="text-ink">{data.title}</span>
      </nav>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_320px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={data.category} />
            <SourceMatchBadge match={data.ai_source_match} />
            <VerificationBadge verification={data.verification} />
            {data.status !== 'published' && (
              <span className="rounded-full bg-bad-tint px-2.5 py-1 text-[11px] font-semibold leading-none text-bad">
                {data.status === 'expired' ? 'sudah lewat' : data.status}
              </span>
            )}
          </div>
          <h1 className="mt-4 font-display text-3xl font-bold leading-tight tracking-[-0.02em] sm:text-4xl">
            {data.title}
          </h1>
          <p className="mt-2 text-body">{data.issuer_name}</p>

          <dl className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
            {meta.map(([label, value]) => (
              <div key={label} className="bg-paper p-4">
                <dt className="text-[11px] font-bold uppercase tracking-[0.12em] text-faint">
                  {label}
                </dt>
                <dd className="mt-1.5 text-sm font-medium">{value}</dd>
              </div>
            ))}
          </dl>

          <section className="mt-10">
            <h2 className="font-display text-xl font-bold">Tentang program</h2>
            <p className="mt-3 whitespace-pre-line leading-7 text-body">
              {data.description}
            </p>
          </section>

          {data.eligibility && (
            <section className="mt-8">
              <h2 className="font-display text-xl font-bold">
                Syarat dan kelayakan
              </h2>
              <p className="mt-3 whitespace-pre-line leading-7 text-body">
                {data.eligibility}
              </p>
            </section>
          )}

          <Card className="mt-10">
            <CardHeader
              eyebrow="Menemukan kekeliruan?"
              hint="laporan anonim"
            />
            <div className="p-5">
              <ReportForm slug={data.slug} />
            </div>
          </Card>
        </div>

        <aside className="space-y-4 lg:pt-[52px]">
          <Card>
            <CardHeader eyebrow="Sumber" />
            <div className="p-5">
              {data.source_url ? (
                <>
                  <p className="break-all font-mono text-xs text-body">
                    {hostOf(data.source_url)}
                  </p>
                  <a
                    href={data.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-flex w-full items-center justify-center rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-paper hover:bg-accent/90"
                  >
                    Kunjungi sumber resmi
                  </a>
                  <p className="mt-3 text-xs text-faint">
                    Tautan sudah diverifikasi moderator.
                  </p>
                </>
              ) : (
                <p className="text-sm leading-6 text-body">
                  Tidak ada tautan publik. Sumber dikonfirmasi langsung ke
                  penyelenggara.
                </p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader eyebrow="Status verifikasi" />
            <dl className="space-y-3 p-5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-body">Disetujui</dt>
                <dd className="font-medium">{formatDate(data.verified_at)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-body">Terakhir dicek</dt>
                <dd className="font-medium">
                  {formatDate(data.checked_at || data.verified_at)}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-body">Dasar</dt>
                <dd className="text-right font-medium">
                  {TRUST_LABELS[data.trust_basis] ?? data.trust_basis}
                </dd>
              </div>
            </dl>
          </Card>
        </aside>
      </div>
    </div>
  )
}
