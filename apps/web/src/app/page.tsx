import Link from 'next/link'
import type { JSX } from 'react'

import { CATEGORIES } from '@/lib/api'
import { CATEGORY_LABELS } from '@/lib/format'

export default function Home(): JSX.Element {
  return (
    <div className="space-y-20 pb-8">
      <section className="space-y-6 pt-8">
        <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl">
          cek dulu,
          <br />
          baru daftar.
        </h1>
        <p className="max-w-md text-muted">
          tempel tautan atau unggah poster peluang. AI membaca isinya,
          mencari sumber resmi, dan membandingkan detailnya.
        </p>
        <div className="flex gap-4">
          <Link
            href="/cek"
            className="bg-ink px-4 py-2 text-paper hover:bg-ink/80"
          >
            cek sekarang →
          </Link>
          <Link href="/peluang" className="px-4 py-2 underline underline-offset-4 hover:text-muted">
            lihat katalog
          </Link>
        </div>
      </section>

      <section>
        <h2 className="text-xs text-muted lowercase">kategori.</h2>
        <div className="mt-3 divide-y divide-line border-y border-line">
          {CATEGORIES.map((category) => (
            <Link
              key={category}
              href={`/peluang?category=${category}`}
              className="group flex items-baseline justify-between py-4"
            >
              <span className="text-lg">{CATEGORY_LABELS[category]}.</span>
              <span className="text-muted group-hover:text-ink">→</span>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-xs text-muted lowercase">cara kerja.</h2>
        <ol className="mt-3 space-y-2 text-muted">
          <li>1. tempel tautan atau unggah poster pengumuman</li>
          <li>2. AI mengekstrak detail dan mencari sumber resminya</li>
          <li>3. hasil tampil seketika; moderator meninjau sebelum masuk katalog</li>
        </ol>
      </section>
    </div>
  )
}
