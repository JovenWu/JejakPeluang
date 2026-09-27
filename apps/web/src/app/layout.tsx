import type { Metadata } from 'next'
import type { JSX, ReactNode } from 'react'

import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'

import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'JejakPeluang',
    template: '%s · JejakPeluang',
  },
  description:
    'Cek peluang beasiswa, magang, dan lomba. AI mencari sumber resmi dan membandingkan detailnya.',
}

export default function RootLayout({ children }: { children: ReactNode }): JSX.Element {
  return (
    <html lang="id">
      <body className="flex min-h-screen flex-col font-sans text-sm leading-6">
        <SiteHeader />
        <main className="mx-auto w-full max-w-3xl flex-1 px-5">{children}</main>
        <SiteFooter />
      </body>
    </html>
  )
}
