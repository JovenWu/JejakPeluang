import Link from 'next/link'
import type { ReactNode } from 'react'

import { Wordmark } from './site-header'

export function SiteFooter(): ReactNode {
  return (
    <footer className="mt-24 border-t border-rule">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-10 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="space-y-3">
          <Wordmark />
          <p className="max-w-sm text-sm leading-relaxed text-ink-2">
            Pemeriksa independen untuk info beasiswa, magang, dan lomba. Bukan penerbit program, tidak berafiliasi
            dengan instansi mana pun, dan tidak memungut biaya.
          </p>
        </div>
        <div>
          <h2 className="kicker mb-3">Cara kami memeriksa</h2>
          <ul className="space-y-2 text-sm text-ink-2">
            <li>AI membaca kiriman dan mencocokkannya dengan halaman web publik.</li>
            <li>AI tidak pernah menyatakan “aman” atau “penipuan”.</li>
            <li>Hanya moderator yang bisa memasukkan entri ke katalog.</li>
          </ul>
        </div>
        <div>
          <h2 className="kicker mb-3">Tautan</h2>
          <ul className="space-y-2 text-sm">
            <li>
              <Link className="link" href="/">
                Cek sebuah peluang
              </Link>
            </li>
            <li>
              <Link className="link" href="/status">
                Lihat status kiriman
              </Link>
            </li>
            <li>
              <Link className="link" href="/moderator">
                Konsol moderator
              </Link>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  )
}
