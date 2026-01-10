import { Header } from '@/components/layout/Header'
import { RecipeContent } from '@/components/recipes/RecipeContent'

export default async function RecipesPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <RecipeContent />
    </div>
  )
}
