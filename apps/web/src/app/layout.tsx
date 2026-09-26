import type { Metadata } from 'next'
import { Inter, Space_Grotesk } from 'next/font/google'
import type { JSX, ReactNode } from 'react'

import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
  weight: ['500', '600', '700'],
})

export const metadata: Metadata = {
  title: {
    default: 'JejakPeluang: Katalog Peluang Terverifikasi',
    template: '%s · JejakPeluang',
  },
  description:
    'Katalog nasional beasiswa, magang, dan kompetisi untuk pelajar Indonesia. Setiap entri diverifikasi moderator dan ditautkan ke sumber aslinya.',
}

export interface RootLayoutProps {
  children: ReactNode
}

export default function RootLayout({ children }: RootLayoutProps): JSX.Element {
  return (
    <html
      lang="id"
      className={`${inter.variable} ${spaceGrotesk.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <a className="skip-link" href="#konten">
          Langsung ke konten
        </a>
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  )
}
