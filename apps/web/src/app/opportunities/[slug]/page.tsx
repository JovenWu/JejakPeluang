import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { JSX } from 'react'

import { IconAlert, IconArrowLeft, IconExternal } from '@/components/icons'
import { StatusBadge } from '@/components/status-badge'
import { TrustBadge } from '@/components/trust-badge'
import { getOpportunity } from '@/lib/catalogue'
import { categoryLabel, deadlineCountdown, formatDate, formatDeadline, isDeadlineSoon } from '@/lib/format'

export const dynamic = 'force-dynamic'

interface DetailProps {
  params: Promise<{ slug: string }>
}

export async function generateMetadata({ params }: DetailProps): Promise<Metadata> {
  const { slug } = await params
  try {
    const item = await getOpportunity(slug)
    if (item === null) {
      return { title: 'Peluang tidak ditemukan' }
    }
    return { title: item.title, description: item.description.slice(0, 160) }
  } catch {
    return { title: 'Detail peluang' }
  }
}

export default async function OpportunityDetailPage({ params }: DetailProps): Promise<JSX.Element> {
  const { slug } = await params
  const item = await getOpportunity(slug)
  if (item === null) {
    notFound()
  }

  const deadlineSoon = isDeadlineSoon(item.deadline, item.status)
  const deadlineText = item.deadline === null ? 'Belum diumumkan' : formatDeadline(item.deadline)
  const deadlineSuffix = deadlineSoon && item.deadline !== null
    ? ` (${deadlineCountdown(item.deadline)})`
    : ''

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10" id="konten">
      <Link
        className="inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-ink-soft hover:text-primary-ink"
        href="/"
      >
        <IconArrowLeft className="size-4" />
        Kembali ke katalog
      </Link>

      <div className="mt-6 flex flex-col gap-3">
        <p className="text-sm font-medium text-ink-soft">
          Penerbit: <span className="text-ink">{item.issuer_name}</span>
        </p>
        <h1 className="text-2xl sm:text-3xl">{item.title}</h1>
        <div className="flex flex-wrap items-center gap-1.5">
          <TrustBadge basis={item.trust_basis} />
          <StatusBadge status={item.status} />
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-1 gap-x-6 gap-y-4 rounded-xl border border-line bg-surface p-5 sm:grid-cols-2">
        <div>
          <dt className="text-sm font-medium text-ink-soft">Kategori</dt>
          <dd className="mt-0.5 text-sm font-medium text-ink">{categoryLabel(item.category)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-ink-soft">Tenggat</dt>
          <dd className={`mt-0.5 text-sm font-medium ${deadlineSoon ? 'text-caution-ink' : 'text-ink'}`}>
            {deadlineText}{deadlineSuffix}
          </dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-ink-soft">Diperiksa</dt>
          <dd className="mt-0.5 text-sm font-medium text-ink">{formatDate(item.checked_at)}</dd>
        </div>
        <div>
          <dt className="text-sm font-medium text-ink-soft">Diverifikasi</dt>
          <dd className="mt-0.5 text-sm font-medium text-ink">{formatDate(item.verified_at)}</dd>
        </div>
        {item.region !== null && (
          <div>
            <dt className="text-sm font-medium text-ink-soft">Wilayah</dt>
            <dd className="mt-0.5 text-sm font-medium text-ink">{item.region}</dd>
          </div>
        )}
      </dl>

      <section className="mt-8">
        <h2 className="text-lg">Deskripsi</h2>
        <p className="measure mt-2 text-base leading-relaxed text-ink">{item.description}</p>
      </section>

      <section className="mt-6">
        <h2 className="text-lg">Syarat pendaftar</h2>
        <p className="measure mt-2 text-base leading-relaxed text-ink">{item.eligibility}</p>
      </section>

      <div className="mt-8 flex flex-col gap-4 border-t border-line pt-6">
        {item.source_url && (
          <a
            className="inline-flex w-fit items-center gap-2 rounded-lg bg-primary-strong px-4 py-2.5 text-sm font-medium text-paper transition-colors duration-150 hover:bg-primary-ink motion-reduce:transition-none"
            href={item.source_url}
            rel="noopener noreferrer"
            target="_blank"
          >
            Sumber asli
            <IconExternal className="size-4" />
          </a>
        )}
        <p className="inline-flex items-start gap-2 text-sm leading-relaxed text-ink-soft">
          <IconAlert className="mt-0.5 size-4 shrink-0 text-caution-ink" />
          Verifikasi moderator menandakan sumber telah diperiksa, bukan jaminan atas
          penyelenggaraan. Selalu rujuk sumber asli sebelum mendaftar.
        </p>
      </div>
    </main>
  )
}
