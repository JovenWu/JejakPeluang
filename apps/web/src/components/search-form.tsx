import type { JSX } from 'react'

import type { Category } from '@/lib/catalogue'
import { IconSearch } from './icons'

export interface SearchFormProps {
  category: Category | null
  q: string
}

export function SearchForm({ category, q }: SearchFormProps): JSX.Element {
  return (
    <form action="/" className="flex w-full gap-2 sm:w-auto" role="search">
      {category !== null && <input name="category" type="hidden" value={category} />}
      <label className="sr-only" htmlFor="pencarian">
        Cari peluang
      </label>
      <div className="relative flex-1 sm:w-64">
        <IconSearch className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
        <input
          className="w-full rounded-lg border border-line bg-paper py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-faint placeholder:opacity-100 focus:border-primary"
          defaultValue={q}
          id="pencarian"
          name="q"
          placeholder="Cari judul peluang"
          type="search"
        />
      </div>
      <button
        className="rounded-lg bg-primary-strong px-4 py-2 text-sm font-medium text-paper transition-colors duration-150 hover:bg-primary-ink motion-reduce:transition-none"
        type="submit"
      >
        Cari
      </button>
    </form>
  )
}
