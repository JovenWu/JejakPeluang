import Link from 'next/link'
import type { JSX } from 'react'

import type { Category } from '@/lib/catalogue'
import { categoryLabel } from '@/lib/format'

export interface CategoryFilterProps {
  active: Category | null
  q: string
}

const CATEGORIES: Category[] = ['scholarship', 'internship', 'competition']

function filterHref(category: Category | null, q: string): string {
  const params = new URLSearchParams()
  if (category !== null) {
    params.set('category', category)
  }
  if (q.length > 0) {
    params.set('q', q)
  }
  const query = params.toString()
  return query.length > 0 ? `/?${query}` : '/'
}

function chipClass(active: boolean): string {
  const base = 'inline-flex items-center rounded-full border px-3 py-1.5 text-sm font-medium transition-colors duration-150 motion-reduce:transition-none'
  if (active) {
    return `${base} border-primary-ink bg-primary-tint text-primary-ink`
  }
  return `${base} border-line bg-paper text-ink-soft hover:border-primary-line hover:text-primary-ink`
}

export function CategoryFilter({ active, q }: CategoryFilterProps): JSX.Element {
  return (
    <nav aria-label="Filter kategori" className="flex flex-wrap items-center gap-2">
      <Link
        aria-current={active === null ? 'page' : undefined}
        className={chipClass(active === null)}
        href={filterHref(null, q)}
      >
        Semua
      </Link>
      {CATEGORIES.map((category) => (
        <Link
          aria-current={active === category ? 'page' : undefined}
          className={chipClass(active === category)}
          href={filterHref(category, q)}
          key={category}
        >
          {categoryLabel(category)}
        </Link>
      ))}
    </nav>
  )
}
