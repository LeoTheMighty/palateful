'use client'

import { EmptyState } from '@/components/recipes/EmptyState'
import { FilterPills } from '@/components/recipes/FilterPills'
import { SortPills } from '@/components/recipes/SortPills'

export function RecipeContent() {
  // Future: Fetch user's recipes from database
  const recipes: unknown[] = []

  const handleAddRecipe = () => {
    // Future: Open recipe creation modal/page
    console.log('Add recipe clicked')
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Filter by</h2>
        <FilterPills />
      </div>

      <div className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Sort by</h2>
        <SortPills />
      </div>

      <div className="rounded-lg bg-white shadow">
        {recipes.length === 0 ? (
          <EmptyState onAddClick={handleAddRecipe} />
        ) : (
          <div className="grid gap-6 p-6 md:grid-cols-2 lg:grid-cols-3">
            {/* Future: Recipe cards will go here */}
          </div>
        )}
      </div>
    </main>
  )
}
