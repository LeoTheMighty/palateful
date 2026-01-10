import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // Check if user has auth session cookie
  const authSession = request.cookies.get('appSession')

  // Protected routes
  const protectedPaths = ['/recipes', '/welcome']
  const isProtectedPath = protectedPaths.some((path) =>
    request.nextUrl.pathname.startsWith(path)
  )

  if (isProtectedPath && !authSession) {
    // Redirect to login if accessing protected route without session
    const loginUrl = new URL('/api/auth/login', request.url)
    loginUrl.searchParams.set('returnTo', request.nextUrl.pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/recipes/:path*', '/welcome'],
}
