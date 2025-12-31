import { auth0 } from '@/lib/auth0'
import { prisma } from '@/lib/prisma'
import { NextResponse } from 'next/server'

export async function POST() {
  const session = await auth0.getSession()

  if (!session?.user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    await prisma.user.update({
      where: { auth0Id: session.user.sub },
      data: { hasCompletedOnboarding: true },
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Failed to complete onboarding:', error)
    return NextResponse.json({ error: 'Failed to update user' }, { status: 500 })
  }
}
