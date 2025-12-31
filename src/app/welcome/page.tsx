'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'

export default function WelcomePage() {
  const router = useRouter()

  const handleStartFromScratch = async () => {
    // Mark onboarding as complete
    await fetch('/api/user/complete-onboarding', { method: 'POST' })
    router.push('/recipes')
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-blue-50 to-white px-4">
      <div className="w-full max-w-2xl text-center">
        <h1 className="mb-4 text-4xl font-bold text-gray-900">
          Welcome to Palate!
        </h1>
        <p className="mb-12 text-lg text-gray-600">
          How would you like to get started?
        </p>

        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border-2 border-gray-200 bg-white p-8 shadow-md transition-colors hover:border-blue-400">
            <h2 className="mb-4 text-2xl font-semibold">Import Recipes</h2>
            <p className="mb-6 text-gray-600">
              Bring in your existing recipes from various sources
            </p>
            <Button variant="outline" className="w-full" disabled>
              Coming Soon
            </Button>
          </div>

          <div className="rounded-lg border-2 border-gray-200 bg-white p-8 shadow-md transition-colors hover:border-blue-400">
            <h2 className="mb-4 text-2xl font-semibold">Start from Scratch</h2>
            <p className="mb-6 text-gray-600">
              Begin building your recipe collection from the ground up
            </p>
            <Button variant="primary" className="w-full" onClick={handleStartFromScratch}>
              Let&apos;s Go
            </Button>
          </div>
        </div>
      </div>
    </main>
  )
}
