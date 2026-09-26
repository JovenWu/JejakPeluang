import type { Metadata } from 'next'
import type { JSX } from 'react'

import { CategoryFilter } from '@/components/category-filter'
import { EmptyState } from '@/components/empty-state'
import { OpportunityCard } from '@/components/opportunity-card'
import { SearchForm } from '@/components/search-form'
import type { Category } from '@/lib/catalogue'
import { listOpportunities } from '@/lib/catalogue'
import { categoryLabel } from '@/lib/format'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Katalog peluang terverifikasi',
}

interface HomeProps {
  searchParams: Promise<{ category?: string | string[]; q?: string | string[] }>
}

const VALID_CATEGORIES: Category[] = ['scholarship', 'internship', 'competition']

function firstParam(value: string | string[] | undefined): string {
  const raw = Array.isArray(value) ? value[0] : value
  return raw?.trim() ?? ''
}

function parseCategory(value: string | string[] | undefined): Category | null {
  const raw = firstParam(value)
  if (raw.length === 0) {
    return null
  }
  return VALID_CATEGORIES.includes(raw as Category) ? (raw as Category) : null
}

export default async function Home({ searchParams }: HomeProps): Promise<JSX.Element> {
  const params = await searchParams
  const category = parseCategory(params.category)
  const q = firstParam(params.q)
  const { items, total } = await listOpportunities({
    category,
    q: q.length > 0 ? q : null,
  })
  const filtered = category !== null || q.length > 0

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-10" id="konten">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl sm:text-3xl">Peluang terverifikasi</h1>
        <p className="measure text-sm leading-relaxed text-ink-soft sm:text-base">
          Katalog nasional beasiswa, magang, dan kompetisi untuk pelajar Indonesia.
          Setiap entri diperiksa moderator dan ditautkan ke sumber aslinya.
        </p>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <CategoryFilter active={category} q={q} />
        <SearchForm category={category} q={q} />
      </div>
      {items.length === 0 ? (
        <div className="mt-8">
          <EmptyState filtered={filtered} />
        </div>
      ) : (
        <>
          <p aria-live="polite" className="mt-6 text-sm text-ink-soft">
            Menampilkan {items.length} dari {total} peluang
            {category !== null && ` dalam kategori ${categoryLabel(category)}`}
            {q.length > 0 && ` untuk pencarian "${q}"`}.
          </p>
          <ul className="mt-4 grid list-none grid-cols-[repeat(auto-fit,minmax(min(100%,17rem),1fr))] gap-4 p-0 sm:gap-5">
            {items.map((item, index) => (
              <li key={item.slug}>
                <OpportunityCard index={index} opportunity={item} />
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  )
}
