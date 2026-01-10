'use client'

import { cn } from '@/lib/utils'

interface LogoutButtonProps {
  className?: string
}

export function LogoutButton({ className }: LogoutButtonProps) {
  return (
    <a
      href="/api/auth/logout"
      className={cn(
        'inline-flex items-center justify-center rounded-lg border-2 border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2',
        className
      )}
    >
      Sign Out
    </a>
  )
}
