'use client'

import { useState } from 'react'
import { Pill } from '@/components/ui/Pill'
import { cn } from '@/lib/utils'

const CATEGORIES = ['Breakfast', 'Lunch', 'Dinner', 'Dessert'] as const

interface FilterPillsProps {
  className?: string
  onChange?: (selected: string[]) => void
}

export function FilterPills({ className, onChange }: FilterPillsProps) {
  const [selected, setSelected] = useState<string[]>([])

  const toggleCategory = (category: string) => {
    const newSelected = selected.includes(category)
      ? selected.filter((c) => c !== category)
      : [...selected, category]

    setSelected(newSelected)
    onChange?.(newSelected)
  }

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {CATEGORIES.map((category) => (
        <Pill
          key={category}
          label={category}
          active={selected.includes(category)}
          onClick={() => toggleCategory(category)}
        />
      ))}
    </div>
  )
}
