import type { JSX } from 'react'

export function SiteFooter(): JSX.Element {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-2 px-5 py-6 text-xs text-faint">
        <span className="font-display font-bold text-ink">JejakPeluang</span>
        <span>AI menyiapkan bukti, moderator yang memutuskan.</span>
      </div>
    </footer>
  )
}
