'use client'

import { useState } from 'react'
import { Pill } from '@/components/ui/Pill'
import { cn } from '@/lib/utils'

const SORT_OPTIONS = ['Surprise me', 'Best', 'Newest', 'Least Tried', 'Most Tried'] as const

interface SortPillsProps {
  className?: string
  defaultValue?: string
  onChange?: (selected: string) => void
}

export function SortPills({ className, defaultValue = 'Surprise me', onChange }: SortPillsProps) {
  const [selected, setSelected] = useState<string>(defaultValue)

  const selectOption = (option: string) => {
    setSelected(option)
    onChange?.(option)
  }

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {SORT_OPTIONS.map((option) => (
        <Pill
          key={option}
          label={option}
          active={selected === option}
          onClick={() => selectOption(option)}
        />
      ))}
    </div>
  )
}
