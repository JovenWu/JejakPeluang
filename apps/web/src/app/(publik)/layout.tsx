import type { ReactNode } from 'react'

import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'

interface Props {
  children: ReactNode
}

export default function PublicLayout({ children }: Props): ReactNode {
  return (
    <>
      <SiteHeader />
      <main id="konten">{children}</main>
      <SiteFooter />
    </>
  )
}
