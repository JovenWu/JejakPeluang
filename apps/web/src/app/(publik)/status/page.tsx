import type { Metadata } from 'next'
import Link from 'next/link'
import type { ReactNode } from 'react'

import { StatusLookup } from '@/components/status-lookup'

export const metadata: Metadata = { title: 'Status kiriman' }

export default function StatusPage(): ReactNode {
  return (
    <div className="mx-auto grid max-w-5xl gap-12 px-4 py-12 sm:px-6 sm:py-16 md:grid-cols-[1fr_1fr]">
      <div>
        <p className="kicker mb-3">Status kiriman</p>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Buka lagi hasil pemeriksaan Anda</h1>
        <p className="mt-4 max-w-md leading-relaxed text-ink-2">
          Gunakan nomor rujukan dan token resi yang muncul setelah Anda mengirim. Jika Anda mengunduh resi .txt, tautan di
          dalamnya langsung membuka halaman ini.
        </p>
        <div className="mt-10">
          <StatusLookup />
        </div>
      </div>
      <aside className="space-y-5 text-sm md:border-l md:border-rule md:pl-12">
        <div>
          <h2 className="font-semibold">Token hilang?</h2>
          <p className="mt-1 leading-relaxed text-ink-2">
            Demi keamanan, token tidak bisa dipulihkan atau dikirim ulang. Jika kiriman Anda sudah selesai dicek AI,
            hasilnya tetap terlihat di{' '}
            <Link href="/antrean" className="link">
              antrean publik
            </Link>{' '}
            sampai moderator memutuskan.
          </p>
        </div>
        <div>
          <h2 className="font-semibold">Tidak ada notifikasi</h2>
          <p className="mt-1 leading-relaxed text-ink-2">
            Kami tidak mengirim email atau SMS. Halaman status adalah satu-satunya saluran kabar kiriman Anda.
          </p>
        </div>
        <div>
          <h2 className="font-semibold">Masa simpan</h2>
          <p className="mt-1 leading-relaxed text-ink-2">
            Berkas, email, dan teks kiriman dihapus 30 hari setelah dikirim, atau 7 hari setelah moderator memutuskan.
          </p>
        </div>
      </aside>
    </div>
  )
}
