import { auth0 } from '@/lib/auth0'
import { redirect } from 'next/navigation'
import { LoginButton } from '@/components/auth/LoginButton'
import { prisma } from '@/lib/prisma'

export default async function Home() {
  const session = await auth0.getSession()

  // If authenticated, check onboarding status and redirect
  if (session?.user) {
    const user = await prisma.user.findUnique({
      where: { auth0Id: session.user.sub },
      select: { hasCompletedOnboarding: true },
    })

    if (user && !user.hasCompletedOnboarding) {
      redirect('/welcome')
    } else {
      redirect('/recipes')
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-blue-50 to-white">
      <div className="text-center">
        <h1 className="mb-4 text-6xl font-bold text-gray-900">Palateful</h1>
        <p className="mb-8 text-xl text-gray-600">Your personal recipe book</p>
        <LoginButton />
      </div>
    </main>
  )
}
