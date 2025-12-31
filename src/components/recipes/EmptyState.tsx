'use client'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  onAddClick?: () => void
  className?: string
}

export function EmptyState({ onAddClick, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-16', className)}>
      <button
        type="button"
        onClick={onAddClick}
        className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-600 text-3xl text-white shadow-lg transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        aria-label="Add new recipe"
      >
        +
      </button>
      <p className="mt-4 text-lg text-gray-600">Add your first recipe</p>
    </div>
  )
}
