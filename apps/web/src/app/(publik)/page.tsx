import Link from 'next/link'
import type { ReactNode } from 'react'

import { CheckForm } from '@/components/check-form'
import { CatalogueRow, IncomingRow } from '@/components/feed-row'
import { Tag, VerdictTag } from '@/components/tags'
import { api } from '@/lib/api'
import { formatCount } from '@/lib/format'

export const dynamic = 'force-dynamic'

const PIPELINE = [
  { n: '01', title: 'Baca', body: 'AI membaca teks dari tautan, poster, atau PDF Anda: judul, penerbit, tenggat, biaya, dan data yang diminta.' },
  { n: '02', title: 'Cari sumber', body: 'Mencari halaman penerbit di web, lalu membukanya lewat pengambil halaman yang aman.' },
  { n: '03', title: 'Bandingkan', body: 'Setiap data dicocokkan dengan halaman sumber, disertai kutipan persis dari halaman itu.' },
  { n: '04', title: 'Moderator', body: 'Manusia memeriksa bukti. Hanya yang lolos yang masuk katalog dengan cap verifikasi.' },
]

function Specimen(): ReactNode {
  const rows = [
    { field: 'Penerbit', value: 'Kemendikbudristek', verdict: 'supported' as const, quote: 'Kementerian Pendidikan Tinggi, Sains…' },
    { field: 'Batas akhir', value: '30 Nov 2026', verdict: 'conflicting' as const, quote: 'paling lambat 30 Oktober 2026' },
    { field: 'Biaya', value: 'Rp150.000', verdict: null, quote: null },
  ]
  return (
    <figure aria-label="Contoh hasil pemeriksaan" className="relative rounded-[3px] border border-rule bg-surface">
      <figcaption className="flex items-center justify-between border-b border-rule px-4 py-2.5">
        <span className="kicker">Seperti ini hasilnya</span>
        <span className="text-2xs text-ink-3">ilustrasi</span>
      </figcaption>
      <div className="border-l-4 border-bad px-4 pt-4 pb-3">
        <p className="font-bold">1 data berbeda dari sumber</p>
        <p className="mt-0.5 text-xs text-ink-2">Halaman resmi ditemukan · kemdikbud.go.id</p>
      </div>
      <ul className="divide-y divide-rule border-t border-rule">
        {rows.map((row) => (
          <li key={row.field} className="grid grid-cols-[4.75rem_minmax(0,1fr)_auto] items-start gap-x-3 px-4 py-2.5 text-sm">
            <span className="text-ink-3">{row.field}</span>
            <span>
              <span className="font-medium">{row.value}</span>
              {row.quote ? <q className="mt-0.5 block font-mono text-2xs text-ink-2">{row.quote}</q> : null}
              {row.verdict ? null : <span className="mt-0.5 block text-2xs text-ink-3">tertulis di poster</span>}
            </span>
            {row.verdict ? <VerdictTag verdict={row.verdict} /> : <Tag tone="mute">Dikutip</Tag>}
          </li>
        ))}
      </ul>
    </figure>
  )
}

export default async function HomePage(): Promise<ReactNode> {
  const [incoming, catalogue] = await Promise.all([
    api.GET('/api/v1/opportunities/incoming', { params: { query: { limit: 4 } } }).catch(() => null),
    api.GET('/api/v1/opportunities', { params: { query: { limit: 4 } } }).catch(() => null),
  ])
  const incomingData = incoming?.data
  const catalogueData = catalogue?.data

  return (
    <>
      <section className="border-b border-rule">
        <div className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-12 px-4 pt-10 pb-14 sm:px-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-16 lg:pt-16">
          <div>
            <p className="kicker mb-4">Beasiswa · Magang · Lomba</p>
            <h1 className="max-w-[16ch] text-[2.25rem] leading-[1.05] font-extrabold tracking-[-0.03em] sm:text-5xl">
              Dapat info dari grup? Cek dulu sebelum daftar.
            </h1>
            <p className="mt-5 max-w-[56ch] text-[1.0625rem] leading-relaxed text-ink-2">
              Tempel tautannya atau unggah posternya. Dalam kurang dari semenit, AI mencari halaman resmi penerbit dan
              menunjukkan data mana yang cocok, lengkap dengan kutipan sumbernya.
            </p>
            <div className="mt-8">
              <CheckForm />
            </div>
          </div>
          <aside className="space-y-6 lg:pt-12">
            <Specimen />
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[3px] border border-rule bg-rule text-sm">
              <div className="bg-paper p-4">
                <dt className="text-ink-3">AI tidak pernah</dt>
                <dd className="mt-1 font-semibold">menyebut “aman” atau “penipuan”</dd>
              </div>
              <div className="bg-paper p-4">
                <dt className="text-ink-3">Katalog hanya diisi</dt>
                <dd className="mt-1 font-semibold">oleh moderator manusia</dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>

      <section aria-labelledby="cara-kerja" className="border-b border-rule">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <h2 id="cara-kerja" className="kicker mb-8">
            Apa yang terjadi setelah Anda menekan “Periksa”
          </h2>
          <ol className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0">
            {PIPELINE.map((step, index) => (
              <li key={step.n} className={`lg:px-6 ${index === 0 ? 'lg:pl-0' : 'lg:border-l lg:border-rule'}`}>
                <p className="font-mono text-sm text-stamp">{step.n}</p>
                <h3 className="mt-2 text-lg font-bold">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <div className="mx-auto grid max-w-6xl gap-14 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:gap-12">
        <section aria-labelledby="baru-dicek">
          <div className="mb-2 flex items-baseline justify-between gap-4 border-b border-ink pb-3">
            <h2 id="baru-dicek" className="text-lg font-bold">
              Baru dicek AI
            </h2>
            <Link href="/antrean" className="link text-sm font-semibold">
              {incomingData ? `Semua ${formatCount(incomingData.total)}` : 'Buka antrean'} →
            </Link>
          </div>
          <p className="mb-2 text-sm text-ink-3">Belum ditinjau moderator. Baca sebagai bukti, bukan rekomendasi.</p>
          {incomingData && incomingData.items.length > 0 ? (
            <ul>
              {incomingData.items.map((item) => (
                <IncomingRow key={item.ref} item={item} />
              ))}
            </ul>
          ) : (
            <p className="py-6 text-sm text-ink-3">{incomingData ? 'Antrean sedang kosong.' : 'Antrean tidak dapat dimuat saat ini.'}</p>
          )}
        </section>

        <section aria-labelledby="katalog-terbaru">
          <div className="mb-2 flex items-baseline justify-between gap-4 border-b border-ink pb-3">
            <h2 id="katalog-terbaru" className="text-lg font-bold">
              Terverifikasi di katalog
            </h2>
            <Link href="/katalog" className="link text-sm font-semibold">
              {catalogueData ? `Semua ${formatCount(catalogueData.total)}` : 'Buka katalog'} →
            </Link>
          </div>
          <p className="mb-2 text-sm text-ink-3">Diperiksa moderator terhadap sumber aslinya.</p>
          {catalogueData && catalogueData.items.length > 0 ? (
            <ul>
              {catalogueData.items.map((item) => (
                <CatalogueRow key={item.slug} item={item} />
              ))}
            </ul>
          ) : (
            <p className="py-6 text-sm text-ink-3">
              {catalogueData ? 'Belum ada entri terverifikasi.' : 'Katalog tidak dapat dimuat saat ini.'}
            </p>
          )}
        </section>
      </div>
    </>
  )
}
