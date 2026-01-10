import { auth0 } from '@/lib/auth0'
import { NextRequest } from 'next/server'

// Handle all Auth0 routes (login, callback, logout)
export const GET = (req: NextRequest) => auth0.middleware(req)
export const POST = (req: NextRequest) => auth0.middleware(req)
