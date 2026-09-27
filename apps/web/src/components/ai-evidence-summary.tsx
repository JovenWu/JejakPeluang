import type { ReactNode } from 'react'

import type { ScreeningView } from '@/lib/api'
import { CONFIDENCE_LABEL, siteAssessmentCopy } from '@/lib/screening'

interface Props {
  screening: ScreeningView
}

export function AiEvidenceSummary({ screening }: Props): ReactNode {
  const confidence = screening.confidence
  const site = screening.site_assessment
  if (!confidence && !site) {
    return (
      <section aria-labelledby="ai-evidence-summary" className="rounded-[3px] border border-rule bg-surface p-4 sm:p-5">
        <p id="ai-evidence-summary" className="kicker mb-1">Dukungan bukti AI</p>
        <p className="text-sm leading-relaxed text-ink-2">
          Skor dukungan dan pemetaan situs belum tersedia pada hasil pemeriksaan lama ini. Kiriman baru memakai laporan
          yang lebih lengkap.
        </p>
      </section>
    )
  }
  const score = confidence?.score ?? null
  const label = confidence ? CONFIDENCE_LABEL[confidence.label] : 'Belum cukup bukti'

  return (
    <section aria-labelledby="ai-evidence-summary" className="rounded-[3px] border border-rule bg-surface p-4 sm:p-5">
      <div className="grid gap-5 sm:grid-cols-[8rem_minmax(0,1fr)]">
        <div>
          <p id="ai-evidence-summary" className="kicker mb-1">Dukungan bukti AI</p>
          {score === null ? (
            <p className="text-sm font-semibold">Belum ada skor</p>
          ) : (
            <p className="font-mono text-3xl leading-none font-bold tabular-nums">
              {score}<span className="ml-1 text-sm font-medium text-ink-3">/100</span>
            </p>
          )}
          <p className="mt-1 text-xs text-ink-2">{label}</p>
        </div>
        <div className="min-w-0">
          {score !== null ? (
            <>
              <div
                role="progressbar"
                aria-label="Dukungan bukti AI"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={score}
                className="h-1.5 overflow-hidden rounded-full bg-rule"
              >
                <span className="block h-full bg-stamp" style={{ width: `${score}%` }} />
              </div>
              <p className="mt-2 text-sm leading-relaxed text-ink-2">
                {confidence?.fields_supported ?? 0} dari {confidence?.fields_checked ?? 0} data yang dibandingkan didukung sumber.{' '}
                Cakupan: {confidence?.fields_checked ?? 0} dari {confidence?.fields_available ?? 0} kolom katalog yang terbaca.
              </p>
            </>
          ) : (
            <p className="text-sm leading-relaxed text-ink-2">
              Belum ada cukup perbandingan sumber untuk menghitung indeks dukungan bukti.
            </p>
          )}
        </div>
      </div>
      <p className="mt-4 border-t border-rule pt-3 text-xs leading-relaxed text-ink-3">
        Indeks ini menggabungkan kecocokan data, cakupan kolom, dan tingkat sumber yang ditemukan. Ini bukan probabilitas
        kebenaran atau keaslian peluang. Situs atau akun yang dinilai AI tetap perlu diperiksa moderator.
      </p>
      {site ? (
        <div className="mt-4 border-t border-rule pt-3">
          <h3 className="kicker mb-1">Situs dan kanal yang ditemukan</h3>
          <p className="text-sm leading-relaxed text-ink-2">{siteAssessmentCopy(site.status)}</p>
          <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-2xs text-ink-3">
            <span>{site.issuer_website_candidates} kandidat situs</span>
            <span>{site.social_sources} kanal sosial</span>
            <span>{site.third_party_sources} sumber pihak ketiga</span>
            <span>{site.unclassified_sources} belum dinilai</span>
            {site.qr_codes_found > 0 ? <span>{site.qr_codes_found} tautan QR terbaca</span> : null}
          </p>
        </div>
      ) : null}
    </section>
  )
}
