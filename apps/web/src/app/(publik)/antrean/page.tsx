import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { IncomingRow } from '@/components/feed-row'
import { LoadError } from '@/components/load-error'
import { Pagination, readOffset } from '@/components/pagination'
import { Stamp } from '@/components/stamp'
import { api } from '@/lib/api'

export const metadata: Metadata = { title: 'Antrean · baru dicek AI' }
export const dynamic = 'force-dynamic'

const LIMIT = 20

interface Props {
  searchParams: Promise<{ offset?: string }>
}

export default async function IncomingPage({ searchParams }: Props): Promise<ReactNode> {
  const offset = readOffset((await searchParams).offset)
  const { data } = await api
    .GET('/api/v1/opportunities/incoming', { params: { query: { limit: LIMIT, offset } } })
    .catch(() => ({ data: undefined }))

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
      <header className="grid gap-6 border-b border-ink pb-8 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <p className="kicker mb-3">Antrean publik</p>
          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Baru dicek AI, menunggu moderator</h1>
          <p className="mt-4 max-w-2xl leading-relaxed text-ink-2">
            Kiriman dari siapa saja yang sudah selesai diperiksa AI. Belum ada manusia yang memverifikasinya, jadi gunakan
            sebagai bukti untuk menilai sendiri, bukan sebagai rekomendasi. Setelah disetujui, entri pindah ke{' '}
            <Link href="/katalog" className="link">
              katalog
            </Link>
            .
          </p>
        </div>
        <Stamp tier="ai" size="lg" />
      </header>

      {data ? (
        <>
          {data.items.length > 0 ? (
            <ul>
              {data.items.map((item) => (
                <IncomingRow key={item.ref} item={item} />
              ))}
            </ul>
          ) : (
            <div className="border-b border-rule py-14 text-center">
              <p className="font-semibold">Antrean sedang kosong.</p>
              <p className="mt-1 text-sm text-ink-2">
                Semua kiriman sudah ditinjau.{' '}
                <Link href="/" className="link">
                  Kirim peluang untuk dicek
                </Link>
                .
              </p>
            </div>
          )}
          <Pagination
            total={data.total}
            offset={offset}
            limit={LIMIT}
            shown={data.items.length}
            noun="kiriman"
            hrefFor={(next) => (next > 0 ? `/antrean?offset=${next}` : '/antrean')}
          />
        </>
      ) : (
        <LoadError what="Antrean" />
      )}
    </div>
  )
}
