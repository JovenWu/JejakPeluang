import './globals.css'

import type { Metadata, Viewport } from 'next'
import { IBM_Plex_Mono, Plus_Jakarta_Sans } from 'next/font/google'
import type { ReactNode } from 'react'

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-jakarta',
  display: 'swap',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-plex-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'JejakPeluang · Cek dulu sebelum daftar',
    template: '%s · JejakPeluang',
  },
  description:
    'Tempel tautan atau unggah poster beasiswa, magang, atau lomba. AI mencocokkan isinya dengan sumber resmi dalam hitungan detik; moderator memverifikasi sebelum masuk katalog.',
  icons: {
    icon: [{ url: '/icon.svg', type: 'image/svg+xml' }],
    shortcut: ['/icon.svg'],
  },
}

export const viewport: Viewport = {
  themeColor: '#f4f3ef',
}

interface Props {
  children: ReactNode
}

export default function RootLayout({ children }: Props): ReactNode {
  return (
    <html lang="id" className={`${jakarta.variable} ${plexMono.variable}`}>
      <body className="antialiased">
        <a href="#konten" className="skip-link">
          Langsung ke konten
        </a>
        {children}
      </body>
    </html>
  )
}
