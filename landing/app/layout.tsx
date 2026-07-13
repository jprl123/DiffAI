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
  title: 'diffAI — Redline profissional de documentos',
  description: 'Compare versões de contratos e documentos (DOCX, PDF, Excel) e gere PDFs redline fiéis em segundos. Processamento 100% local no Mac e no Windows.',
  keywords: ['redline', 'comparação de documentos', 'diffAI', 'comparar contratos', 'DOCX', 'PDF', 'revisão contratual'],
  authors: [{ name: 'diffAI' }],
  openGraph: {
    title: 'diffAI — Redline profissional de documentos',
    description: 'Compare versões de contratos e gere PDFs redline fiéis em segundos, com processamento 100% local.',
    type: 'website',
    url: 'https://diffai.app',
    siteName: 'diffAI',
    locale: 'pt_BR',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'diffAI — Redline profissional de documentos',
    description: 'Compare versões de contratos e gere PDFs redline fiéis em segundos, com processamento 100% local.',
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
    <html lang="pt-BR">
      <body className={`font-sans antialiased`}>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
