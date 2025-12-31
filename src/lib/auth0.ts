import { Auth0Client } from '@auth0/nextjs-auth0/server'
import { prisma } from '@/lib/prisma'

export const auth0 = new Auth0Client({
  domain: process.env.AUTH0_DOMAIN,
  clientId: process.env.AUTH0_CLIENT_ID,
  clientSecret: process.env.AUTH0_CLIENT_SECRET,
  appBaseUrl: process.env.APP_BASE_URL,
  secret: process.env.AUTH0_SECRET,
  async beforeSessionSaved(session) {
    if (session?.user?.email) {
      // Upsert user in database on every login
      await prisma.user.upsert({
        where: { auth0Id: session.user.sub },
        update: {
          email: session.user.email,
          name: session.user.name ?? null,
          picture: session.user.picture ?? null,
          emailVerified: session.user.email_verified ?? false,
        },
        create: {
          auth0Id: session.user.sub,
          email: session.user.email,
          name: session.user.name ?? null,
          picture: session.user.picture ?? null,
          emailVerified: session.user.email_verified ?? false,
          hasCompletedOnboarding: false,
        },
      })
    }

    return session
  },
})
