import Link from 'next/link'
import type { JSX } from 'react'

import { VerificationBadge, VerdictBadge } from '@/components/badges'
import { BUTTON_GHOST, BUTTON_PRIMARY, Card, Eyebrow } from '@/components/ui'
import type { Category } from '@/lib/api'

const CATEGORY_CARDS: Array<{
  value: Category
  title: string
  description: string
  style: string
}> = [
  {
    value: 'scholarship',
    title: 'Beasiswa',
    description: 'Bantuan biaya kuliah, tunjangan hidup, dan program afirmasi.',
    style: 'bg-good-tint text-good',
  },
  {
    value: 'internship',
    title: 'Magang',
    description: 'Program magang resmi dari perusahaan dan kampus.',
    style: 'bg-accent-tint text-accent',
  },
  {
    value: 'competition',
    title: 'Kompetisi',
    description: 'Lomba dan olimpiade untuk pelajar dan mahasiswa.',
    style: 'bg-ai-tint text-ai',
  },
]

const STEPS: Array<[string, string]> = [
  [
    'Tempel tautan atau unggah poster',
    'Bisa juga menambahkan konteks, misalnya dari grup WhatsApp.',
  ],
  [
    'AI memeriksa dalam hitungan detik',
    'Mengekstrak detail, mencari sumber resmi, lalu membandingkan.',
  ],
  [
    'Moderator memutuskan katalog',
    'Hasil AI langsung tampil untukmu, tapi hanya manusia yang menerbitkan.',
  ],
]

export default function Home(): JSX.Element {
  return (
    <div>
      <section className="border-b border-line bg-surface">
        <div className="mx-auto grid w-full max-w-5xl gap-10 px-5 py-16 sm:py-20 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <div className="space-y-6">
            <Eyebrow>Pembanding peluang independen</Eyebrow>
            <h1 className="font-display text-4xl font-bold tracking-[-0.02em] sm:text-5xl">
              Temukan peluang yang benar-benar{' '}
              <span className="text-accent">terverifikasi.</span>
            </h1>
            <p className="max-w-md text-base leading-7 text-body">
              Tempel tautan beasiswa, magang, atau kompetisi apa pun. AI
              membaca isinya, mencari sumber resminya, dan membandingkan
              detailnya dalam hitungan detik.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/cek" className={BUTTON_PRIMARY}>
                Cek peluang sekarang
              </Link>
              <Link href="/peluang" className={BUTTON_GHOST}>
                Lihat katalog
              </Link>
            </div>
          </div>

          <Card className="p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-body">
                Contoh hasil pemeriksaan
              </p>
              <VerificationBadge verification="ai_checked" />
            </div>
            <p className="mt-3 font-display text-lg font-bold leading-snug">
              Beasiswa Unggulan 2026
            </p>
            <p className="mt-0.5 text-xs text-body">kemdikbud.go.id</p>
            <ul className="mt-4 space-y-2.5 border-t border-line pt-4">
              {[
                ['Judul', 'supported'],
                ['Batas akhir', 'conflicting'],
                ['Biaya pendaftaran', 'not_found'],
              ].map(([field, verdict]) => (
                <li
                  key={field}
                  className="flex items-center justify-between gap-4"
                >
                  <span className="text-xs text-body">{field}</span>
                  <VerdictBadge verdict={verdict} />
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-line pt-3 text-[11px] leading-4 text-faint">
              Setiap detail dibandingkan dengan sumber publik, bukan sekadar
              dibaca.
            </p>
          </Card>
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-5 py-14">
        <div className="flex items-baseline justify-between gap-4">
          <Eyebrow>Kategori</Eyebrow>
          <Link href="/peluang" className="text-sm text-accent hover:underline">
            Semua peluang
          </Link>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {CATEGORY_CARDS.map((category) => (
            <Link
              key={category.value}
              href={`/peluang?category=${category.value}`}
              className="group rounded-xl border border-line bg-paper p-5 hover:border-accent"
            >
              <span
                className={`inline-flex h-9 w-9 items-center justify-center rounded-lg text-sm font-bold ${category.style}`}
              >
                {category.title[0]}
              </span>
              <p className="mt-4 font-display text-xl font-bold">
                {category.title}
              </p>
              <p className="mt-1 text-sm leading-6 text-body">
                {category.description}
              </p>
              <p className="mt-3 text-sm font-semibold text-accent">
                Jelajahi
                <span className="ml-1 inline-block transition-transform group-hover:translate-x-0.5">
                  →
                </span>
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto w-full max-w-5xl px-5 py-14">
          <Eyebrow>Cara kerja</Eyebrow>
          <div className="mt-6 grid gap-8 sm:grid-cols-3">
            {STEPS.map(([title, body], index) => (
              <div key={title}>
                <p className="font-mono text-xs font-semibold text-accent">
                  {String(index + 1).padStart(2, '0')}
                </p>
                <p className="mt-2 font-semibold">{title}</p>
                <p className="mt-1 text-sm leading-6 text-body">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-5xl px-5 py-14">
        <Eyebrow>Dua tingkat kepercayaan</Eyebrow>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Card className="p-5">
            <VerificationBadge verification="ai_checked" />
            <p className="mt-3 text-sm leading-6 text-body">
              Sudah diperiksa AI terhadap sumber publik dan menunggu tinjauan
              moderator. Tampil di antrean, belum dianggap benar.
            </p>
          </Card>
          <Card className="p-5">
            <VerificationBadge verification="moderator_verified" />
            <p className="mt-3 text-sm leading-6 text-body">
              Ditinjau dan disetujui moderator sebelum masuk katalog. Bukti AI
              menjadi bahan pertimbangan, bukan vonis.
            </p>
          </Card>
        </div>
      </section>
    </div>
  )
}
