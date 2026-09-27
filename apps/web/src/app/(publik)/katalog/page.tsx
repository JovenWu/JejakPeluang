import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { CatalogueRow } from '@/components/feed-row'
import { LoadError } from '@/components/load-error'
import { Pagination, readOffset } from '@/components/pagination'
import { api, CATEGORIES, type Category, isCategory } from '@/lib/api'
import { CATEGORY_LABEL } from '@/lib/format'

export const metadata: Metadata = { title: 'Katalog terverifikasi' }
export const dynamic = 'force-dynamic'

const LIMIT = 20

interface Query {
  category?: string
  q?: string
  offset?: string
}

interface Props {
  searchParams: Promise<Query>
}

function hrefWith(current: { category?: Category; q?: string }, patch: { category?: Category | null; offset?: number }): string {
  const params = new URLSearchParams()
  const category = patch.category === null ? undefined : (patch.category ?? current.category)
  if (category) {
    params.set('category', category)
  }
  if (current.q) {
    params.set('q', current.q)
  }
  if (patch.offset) {
    params.set('offset', String(patch.offset))
  }
  const query = params.toString()
  return query ? `/katalog?${query}` : '/katalog'
}

export default async function CataloguePage({ searchParams }: Props): Promise<ReactNode> {
  const raw = await searchParams
  const category = isCategory(raw.category) ? raw.category : undefined
  const q = raw.q?.trim().slice(0, 120) || undefined
  const offset = readOffset(raw.offset)
  const current = { category, q }

  const { data } = await api
    .GET('/api/v1/opportunities', { params: { query: { limit: LIMIT, offset, category, q } } })
    .catch(() => ({ data: undefined }))

  const tabs: { label: string; value: Category | null }[] = [
    { label: 'Semua', value: null },
    ...CATEGORIES.map((value) => ({ label: CATEGORY_LABEL[value], value })),
  ]

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
      <header className="border-b border-ink pb-8">
        <p className="kicker mb-3">Katalog</p>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Peluang yang sudah diverifikasi moderator</h1>
        <p className="mt-4 max-w-2xl leading-relaxed text-ink-2">
          Setiap entri diperiksa manusia terhadap sumber aslinya dan diberi cap tanggal verifikasi. Diurutkan dari tenggat
          terdekat.
        </p>
      </header>

      <div className="flex flex-col gap-4 border-b border-rule py-5 lg:flex-row lg:items-center lg:justify-between">
        <nav aria-label="Filter jenis">
          <ul className="flex flex-wrap gap-1.5">
            {tabs.map((tab) => {
              const active = (tab.value ?? undefined) === category
              return (
                <li key={tab.label}>
                  <Link
                    href={hrefWith(current, { category: tab.value })}
                    aria-current={active ? 'page' : undefined}
                    className={`inline-flex min-h-11 items-center rounded-[3px] border px-3.5 text-sm font-semibold transition-colors ${
                      active ? 'border-ink bg-ink text-paper' : 'border-rule-2 text-ink-2 hover:border-ink hover:text-ink'
                    }`}
                  >
                    {tab.label}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
        <form role="search" action="/katalog" className="flex w-full gap-2 lg:w-auto">
          {category ? <input type="hidden" name="category" value={category} /> : null}
          <label htmlFor="q" className="sr-only">
            Cari judul
          </label>
          <input
            id="q"
            name="q"
            type="search"
            defaultValue={q}
            placeholder="Cari judul, mis. “beasiswa S1”"
            className="field min-w-0 flex-1 lg:w-72 lg:flex-none"
          />
          <button type="submit" className="btn btn-primary">
            Cari
          </button>
        </form>
      </div>

      {q ? (
        <p className="mt-4 text-sm text-ink-2">
          Hasil untuk <strong className="text-ink">“{q}”</strong> ·{' '}
          <Link href={hrefWith({ category }, {})} className="link">
            hapus pencarian
          </Link>
        </p>
      ) : null}

      {data ? (
        <>
          {data.items.length > 0 ? (
            <ul className="mt-2">
              {data.items.map((item) => (
                <CatalogueRow key={item.slug} item={item} />
              ))}
            </ul>
          ) : (
            <div className="border-b border-rule py-14 text-center">
              <p className="font-semibold">{q || category ? 'Tidak ada entri yang cocok.' : 'Katalog masih kosong.'}</p>
              <p className="mt-1 text-sm text-ink-2">
                {q || category ? (
                  <Link href="/katalog" className="link">
                    Tampilkan semua entri
                  </Link>
                ) : (
                  'Moderator sedang meninjau kiriman baru.'
                )}{' '}
                Punya info peluang?{' '}
                <Link href="/" className="link">
                  Kirim untuk dicek
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
            noun="entri"
            hrefFor={(next) => hrefWith(current, { offset: next })}
          />
        </>
      ) : (
        <div className="mt-6">
          <LoadError what="Katalog" />
        </div>
      )}
    </div>
  )
}
