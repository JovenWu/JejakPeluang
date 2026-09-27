// Loose readers for the moderator-only `result_json` payload. The backend
// schema is versioned and fields disappear after the retention purge, so
// every accessor tolerates missing or malformed data.

type Json = Record<string, unknown>

function obj(value: unknown): Json | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Json) : null
}

function str(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export interface DiscoveryResult {
  url: string
  title: string | null
  score: number | null
}

export interface EvidencePage {
  url: string
  finalUrl: string | null
  status: number | null
  contentType: string | null
  fetchedAt: string | null
  text: string | null
  purged: boolean
  rendered: boolean
  error: string | null
}

export interface JudgmentAnswer {
  name: string
  kind: 'noul' | 'choice' | 'score'
  value: number | null
  // Upper bound of `value`: 1 for probabilities, the top legend level for scores.
  max: number
  choice: string | null
}

export interface Judgment {
  url: string
  answers: JudgmentAnswer[]
}

export interface RunError {
  stage: string | null
  kind: string | null
  detail: string | null
}

export interface Evidence {
  outcome: string | null
  submissionText: string | null
  submissionPurged: boolean
  discoveryStatus: string | null
  discoveryQuery: string | null
  discovery: DiscoveryResult[]
  pages: EvidencePage[]
  notes: string | null
  judgments: Judgment[]
  errors: RunError[]
}

export function readEvidence(result: Json | null | undefined): Evidence | null {
  if (!result) {
    return null
  }
  const discovery = obj(result.discovery)
  const comparison = obj(result.comparison)
  const list = (value: unknown): Json[] => (Array.isArray(value) ? value.map(obj).filter((v): v is Json => v !== null) : [])
  return {
    outcome: str(result.outcome),
    submissionText: str(result.submission_text),
    submissionPurged: !('submission_text' in result),
    discoveryStatus: str(discovery?.status),
    discoveryQuery: str(discovery?.query),
    discovery: list(discovery?.results).map((item) => ({
      url: str(item.url) ?? '',
      title: str(item.title),
      score: num(item.score),
    })),
    pages: list(result.evidence).map((item) => ({
      url: str(item.url) ?? '',
      finalUrl: str(item.final_url),
      status: num(item.status),
      contentType: str(item.content_type),
      fetchedAt: str(item.fetched_at),
      text: str(item.text),
      purged: item.text_purged === true,
      rendered: item.rendered === true,
      error: str(item.extract_error) ?? str(item.fetch_error),
    })),
    notes: str(comparison?.notes),
    judgments: list(result.judgments).map((item) => {
      const answers = obj(item.answers) ?? {}
      return {
        url: str(item.url) ?? '',
        answers: Object.entries(answers).flatMap(([name, raw]): JudgmentAnswer[] => {
          const answer = obj(raw)
          if (!answer) {
            return []
          }
          if (answer.type === 'noul') {
            return [{ name, kind: 'noul', value: num(answer.noul), max: 1, choice: null }]
          }
          if (answer.type === 'choice') {
            return [{ name, kind: 'choice', value: num(answer.confidence), max: 1, choice: str(answer.choice) }]
          }
          if (answer.type === 'score') {
            const value = num(answer.score)
            const legend = obj(answer.legend) ?? {}
            const levels = Object.keys(legend).length
            const max = levels > 1 ? levels - 1 : 3
            const nearest = value === null ? null : str(legend[String(Math.round(value))])
            return [{ name, kind: 'score', value, max, choice: nearest }]
          }
          return []
        }),
      }
    }),
    errors: list(result.errors).map((item) => ({
      stage: str(item.stage),
      kind: str(item.kind),
      detail: str(item.detail),
    })),
  }
}

export const JUDGMENT_LABEL: Record<string, string> = {
  official_announcement: 'Pengumuman resmi',
  doc_kind: 'Jenis dokumen',
  source_authority: 'Otoritas sumber',
  deadline_corroborated: 'Tenggat terkonfirmasi',
}

export const DOC_KIND_LABEL: Record<string, string> = {
  official_listing: 'halaman resmi',
  aggregator_repost: 'agregator / repost',
  aggregator: 'agregator',
  social_post: 'unggahan medsos',
  unrelated: 'tidak terkait',
  insufficient_evidence: 'teks tak cukup',
}
