import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Auth0Provider } from '@auth0/nextjs-auth0/client'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'Palateful - Your Personal Recipe Book',
  description: 'Organize and discover your favorite recipes',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <Auth0Provider>{children}</Auth0Provider>
      </body>
    </html>
  )
}
