import type { ReactNode } from 'react'

interface Props {
  what: string
}

export function LoadError({ what }: Props): ReactNode {
  return (
    <div role="alert" className="border-y border-rule py-10">
      <p className="font-semibold">{what} tidak dapat dimuat.</p>
      <p className="mt-1 text-sm text-ink-2">Server sedang tidak merespons. Muat ulang halaman ini dalam beberapa saat.</p>
    </div>
  )
}
