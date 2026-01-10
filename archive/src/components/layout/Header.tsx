import { auth0 } from '@/lib/auth0'
import { LogoutButton } from '@/components/auth/LogoutButton'
import { cn } from '@/lib/utils'

interface HeaderProps {
  className?: string
}

export async function Header({ className }: HeaderProps) {
  const session = await auth0.getSession()

  return (
    <header className={cn('border-b border-gray-200 bg-white', className)}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <h1 className="text-2xl font-bold text-gray-900">Palateful</h1>
        {session?.user && (
          <div className="flex items-center gap-4">
            {session.user.picture && (
              <img
                src={session.user.picture}
                alt={session.user.name ?? 'User'}
                className="h-8 w-8 rounded-full"
              />
            )}
            <span className="text-sm text-gray-600">{session.user.name}</span>
            <LogoutButton />
          </div>
        )}
      </div>
    </header>
  )
}
