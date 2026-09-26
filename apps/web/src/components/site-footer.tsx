import type { JSX } from 'react'

export function SiteFooter(): JSX.Element {
  return (
    <footer className="mt-auto border-t border-line bg-surface">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-4 py-6 sm:px-6">
        <p className="font-display text-sm font-semibold text-ink">
          Jejak<span className="text-primary-ink">Peluang</span>
        </p>
        <p className="measure text-sm leading-relaxed text-ink-soft" id="verifikasi">
          Setiap entri diperiksa moderator dan ditautkan ke sumber aslinya. Verifikasi
          menandakan sumber telah dicek, bukan jaminan atas penyelenggaraan. Selalu rujuk
          sumber asli sebelum mendaftar.
        </p>
      </div>
    </footer>
  )
}
