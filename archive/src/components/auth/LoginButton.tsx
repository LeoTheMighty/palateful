'use client'

import { cn } from '@/lib/utils'

interface LoginButtonProps {
  className?: string
}

export function LoginButton({ className }: LoginButtonProps) {
  return (
    <a
      href="/api/auth/login"
      className={cn(
        'inline-flex items-center justify-center rounded-lg bg-blue-600 px-6 py-3 text-lg font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        className
      )}
    >
      Sign In
    </a>
  )
}
