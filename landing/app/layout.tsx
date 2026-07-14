import React from "react"
import type { Metadata } from 'next'
import { Geist, Geist_Mono, IBM_Plex_Sans } from 'next/font/google'
import { Courier_Prime } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import './globals.css'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });
const _courierPrime = Courier_Prime({ weight: ["400", "700"], subsets: ["latin"] });
const _ibmPlexSans = IBM_Plex_Sans({ weight: ["300", "400", "500", "600"], subsets: ["latin"] });

export const metadata: Metadata = {
  title: 'diffAI — Professional document redlines',
  description: 'Compare versions of contracts and documents (DOCX, PDF, Excel) and get faithful redline PDFs in seconds. 100% local processing on Mac and Windows.',
  keywords: ['redline', 'document comparison', 'diffAI', 'compare contracts', 'DOCX', 'PDF', 'contract review'],
  authors: [{ name: 'diffAI' }],
  openGraph: {
    title: 'diffAI — Professional document redlines',
    description: 'Compare contract versions and get faithful redline PDFs in seconds, with 100% local processing.',
    type: 'website',
    url: 'https://diffai.app',
    siteName: 'diffAI',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'diffAI — Professional document redlines',
    description: 'Compare contract versions and get faithful redline PDFs in seconds, with 100% local processing.',
  },
  icons: {
    icon: [{ url: '/icon.svg', type: 'image/svg+xml' }],
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`font-sans antialiased`}>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
