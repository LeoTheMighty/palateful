'use client'

import { cn } from '@/lib/utils'

interface PillProps {
  label: string
  active?: boolean
  onClick?: () => void
  className?: string
}

export function Pill({ label, active = false, onClick, className }: PillProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        active
          ? 'bg-blue-600 text-white hover:bg-blue-700'
          : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
        className
      )}
    >
      {label}
    </button>
  )
}
