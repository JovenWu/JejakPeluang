import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { LoadError } from '@/components/load-error'
import { ScreeningPending, ScreeningReport } from '@/components/screening-report'
import { Stamp } from '@/components/stamp'
import { api } from '@/lib/api'
import { displayUrl, formatDateTime } from '@/lib/format'
import { isScreeningDone, readExtracted } from '@/lib/screening'

export const dynamic = 'force-dynamic'

interface Props {
  params: Promise<{ ref: string }>
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { ref } = await params
  return { title: `${decodeURIComponent(ref)} · dicek AI`, robots: { index: false } }
}

export default async function IncomingDetailPage({ params }: Props): Promise<ReactNode> {
  const ref = decodeURIComponent((await params).ref).toUpperCase()
  const result = await api
    .GET('/api/v1/opportunities/incoming/{ref}', { params: { path: { ref } } })
    .catch(() => null)

  if (result?.response.status === 404) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <p className="kicker mb-3">{ref}</p>
        <h1 className="text-3xl font-extrabold tracking-tight">Kiriman ini sudah keluar dari antrean</h1>
        <p className="mt-4 leading-relaxed text-ink-2">
          Kiriman keluar dari antrean publik setelah moderator memutuskan: disetujui, ditolak, atau kedaluwarsa. Jika
          disetujui, entrinya kini ada di katalog.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/katalog" className="btn btn-primary">
            Cari di katalog
          </Link>
          <Link href="/antrean" className="btn btn-ghost">
            Kembali ke antrean
          </Link>
        </div>
      </div>
    )
  }

  const item = result?.data
  if (!item) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
        <LoadError what="Kiriman" />
      </div>
    )
  }

  const title = readExtracted(item.screening)?.title

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
      <nav aria-label="Remah roti" className="mb-6 text-sm">
        <Link href="/antrean" className="link">
          ← Antrean
        </Link>
      </nav>
      <header className="flex flex-wrap items-start justify-between gap-6 border-b border-ink pb-6">
        <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
          <p className="kicker mb-2">
            {item.ref} · dikirim {formatDateTime(item.created_at)}
          </p>
          <h1 className="text-2xl leading-tight font-extrabold tracking-tight sm:text-3xl">
            {title ?? 'Judul tidak terbaca dari kiriman'}
          </h1>
          {item.submitted_url ? (
            <p className="mt-3 text-sm text-ink-2">
              Tautan yang dikirim:{' '}
              <a
                href={item.submitted_url}
                target="_blank"
                rel="noopener noreferrer nofollow ugc"
                className="font-mono text-xs break-all text-ink underline decoration-rule-2 hover:decoration-ink"
              >
                {displayUrl(item.submitted_url)}
              </a>
            </p>
          ) : (
            <p className="mt-3 text-sm text-ink-3">Dikirim sebagai berkas, tanpa tautan.</p>
          )}
        </div>
        <Stamp tier="ai" size="lg" />
      </header>

      <p className="my-6 rounded-[3px] border border-dashed border-ink-3 px-4 py-3 text-sm text-ink-2">
        Kiriman tamu yang belum ditinjau moderator. Tautan di atas belum diverifikasi. Jangan masukkan data pribadi atau
        membayar apa pun hanya berdasarkan halaman ini.
      </p>

      <div className="mt-10">
        {item.screening && isScreeningDone(item.screening) ? (
          <ScreeningReport screening={item.screening} />
        ) : (
          <ScreeningPending state={item.screening?.state} />
        )}
      </div>
    </div>
  )
}
