import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { cache, type ReactNode } from 'react'

import { LoadError } from '@/components/load-error'
import { ReportForm } from '@/components/report-form'
import { Stamp, tierFor } from '@/components/stamp'
import { Deadline } from '@/components/tags'
import { api } from '@/lib/api'
import { CATEGORY_LABEL, displayUrl, formatDate, hostOf } from '@/lib/format'

export const dynamic = 'force-dynamic'

interface Props {
  params: Promise<{ slug: string }>
}

const load = cache(async (slug: string) =>
  api.GET('/api/v1/opportunities/{slug}', { params: { path: { slug } } }).catch(() => null),
)

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const result = await load((await params).slug)
  return { title: result?.data?.title ?? 'Entri katalog' }
}

const STATUS_NOTICE: Record<string, { title: string; body: string }> = {
  expired: {
    title: 'Entri ini sudah kedaluwarsa',
    body: 'Masa pendaftaran telah lewat. Informasi di bawah disimpan sebagai arsip.',
  },
  needs_review: {
    title: 'Sedang ditinjau ulang',
    body: 'Moderator sedang memeriksa ulang entri ini, misalnya karena ada laporan. Pastikan di sumber resmi sebelum mendaftar.',
  },
}

export default async function OpportunityPage({ params }: Props): Promise<ReactNode> {
  const { slug } = await params
  const result = await load(slug)
  if (result?.response.status === 404) {
    notFound()
  }
  const item = result?.data
  if (!item) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <LoadError what="Entri" />
      </div>
    )
  }

  const notice = STATUS_NOTICE[item.status]
  const privateSource = item.trust_basis === 'issuer_confirmed_private'

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
      <nav aria-label="Remah roti" className="mb-6 flex flex-wrap gap-x-2 text-sm text-ink-3">
        <Link href="/katalog" className="link">
          Katalog
        </Link>
        <span aria-hidden>/</span>
        <Link href={`/katalog?category=${item.category}`} className="link">
          {CATEGORY_LABEL[item.category]}
        </Link>
      </nav>

      {notice ? (
        <div role="status" className="mb-8 rounded-[3px] border border-warn bg-warn-tint px-5 py-4 text-sm">
          <p className="font-semibold text-warn">{notice.title}</p>
          <p className="mt-1 text-ink-2">{notice.body}</p>
        </div>
      ) : null}

      <div className="grid gap-10 [grid-template-areas:'head'_'aside'_'body'] lg:grid-cols-[1fr_22rem] lg:grid-rows-[auto_1fr] lg:gap-x-16 lg:gap-y-0 lg:[grid-template-areas:'head_aside'_'body_aside']">
        <div className="[grid-area:head]">
          <header className="border-b border-ink pb-6">
            <p className="kicker mb-2">{CATEGORY_LABEL[item.category]}</p>
            <h1 className="text-3xl leading-tight font-extrabold tracking-tight sm:text-4xl">{item.title}</h1>
            <p className="mt-3 text-lg text-ink-2">{item.issuer_name}</p>
          </header>

          <dl className="grid grid-cols-2 border-b border-rule sm:grid-cols-4">
            <div className="border-r border-rule py-4 pr-4">
              <dt className="kicker">Tenggat</dt>
              <dd className="mt-1 text-sm">
                <Deadline deadline={item.deadline} />
              </dd>
            </div>
            <div className="py-4 pl-4 sm:border-r sm:border-rule sm:pr-4">
              <dt className="kicker">Wilayah</dt>
              <dd className="mt-1 text-sm font-medium">{item.region ?? 'Tidak disebut'}</dd>
            </div>
            <div className="border-t border-r border-rule py-4 pr-4 sm:border-t-0 sm:pl-4">
              <dt className="kicker">Jenis</dt>
              <dd className="mt-1 text-sm font-medium">{CATEGORY_LABEL[item.category]}</dd>
            </div>
            <div className="border-t border-rule py-4 pl-4 sm:border-t-0">
              <dt className="kicker">Terakhir dicek</dt>
              <dd className="mt-1 font-mono text-sm">{formatDate(item.checked_at)}</dd>
            </div>
          </dl>
        </div>

        <article className="[grid-area:body]" aria-labelledby="tentang">
          <section aria-labelledby="tentang" className="lg:mt-10">
            <h2 id="tentang" className="mb-3 text-lg font-bold">
              Tentang program
            </h2>
            <p className="prose-body">{item.description}</p>
          </section>

          <section aria-labelledby="syarat" className="mt-10">
            <h2 id="syarat" className="mb-3 text-lg font-bold">
              Syarat pendaftar
            </h2>
            <p className="prose-body">{item.eligibility}</p>
          </section>

          <details className="group mt-14 border-t border-rule pt-5">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between text-sm font-semibold marker:hidden">
              Menemukan kekeliruan? Laporkan secara anonim
              <span aria-hidden className="font-mono text-ink-3 transition-transform group-open:rotate-45">
                +
              </span>
            </summary>
            <div className="pt-4">
              <ReportForm slug={item.slug} />
            </div>
          </details>
        </article>

        <aside className="[grid-area:aside] lg:sticky lg:top-6 lg:self-start">
          <section aria-labelledby="catatan-verifikasi" className="rounded-[3px] border border-ink bg-surface">
            <div className="flex items-start justify-between gap-4 border-b border-rule p-5">
              <div>
                <h2 id="catatan-verifikasi" className="kicker">
                  Catatan verifikasi
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-ink-2">
                  {privateSource
                    ? 'Penerbit mengonfirmasi langsung kepada moderator. Pengumumannya tidak dipublikasikan di web.'
                    : 'Moderator mencocokkan entri ini dengan halaman sumber aslinya sebelum ditayangkan.'}
                </p>
              </div>
              <Stamp tier={tierFor(item.trust_basis)} date={item.verified_at} size="lg" />
            </div>
            <dl className="divide-y divide-rule text-sm">
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-ink-3">Disetujui</dt>
                <dd className="font-mono">{formatDate(item.verified_at)}</dd>
              </div>
              <div className="flex justify-between gap-4 px-5 py-3">
                <dt className="text-ink-3">Dasar</dt>
                <dd className="text-right font-medium">{privateSource ? 'Konfirmasi penerbit' : 'Sumber publik'}</dd>
              </div>
              {item.ai_source_match !== null ? (
                <div className="flex justify-between gap-4 px-5 py-3">
                  <dt className="text-ink-3">Sinyal AI</dt>
                  <dd className="text-right text-ink-2">
                    {item.ai_source_match ? 'Halaman resmi ditemukan' : 'Halaman resmi tidak dikenali'}
                  </dd>
                </div>
              ) : null}
            </dl>
            <div className="border-t border-rule p-5">
              {item.source_url ? (
                <>
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-stamp w-full"
                  >
                    Buka sumber asli ↗
                  </a>
                  <p className="mt-3 text-xs text-ink-3">
                    Anda akan menuju <strong className="font-semibold text-ink-2">{hostOf(item.source_url)}</strong>
                  </p>
                  <p className="mt-1 font-mono text-2xs leading-relaxed break-all text-ink-3">{displayUrl(item.source_url)}</p>
                </>
              ) : (
                <p className="text-sm text-ink-2">
                  <strong className="text-ink">Sumber privat.</strong> Tidak ada tautan publik. Ikuti instruksi pendaftaran
                  dari penerbit secara langsung.
                </p>
              )}
            </div>
          </section>
          <p className="mt-4 text-xs leading-relaxed text-ink-3">
            Verifikasi memastikan pengumuman ini sesuai sumbernya, bukan jaminan diterima, dan JejakPeluang tidak
            berafiliasi dengan penerbit.
          </p>
        </aside>
      </div>
    </div>
  )
}
