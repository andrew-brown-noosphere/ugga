import { Link, useLocation } from 'react-router-dom'
import { BookOpen, Calendar, Search, GraduationCap, Sparkles, Target, Users, User, Crown, Users2, Heart } from 'lucide-react'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/clerk-react'
import { clsx } from 'clsx'
import { useSubscription } from '../context/SubscriptionContext'

interface LayoutProps {
  children: React.ReactNode
}

const navigation = [
  { name: 'My Plan', href: '/plan', icon: Target },
  { name: 'Programs', href: '/programs', icon: GraduationCap },
  { name: 'Courses', href: '/courses', icon: BookOpen },
  { name: 'Faculty', href: '/instructors', icon: Users },
  { name: 'Planner', href: '/planner', icon: Calendar },
  { name: 'Study Groups', href: '/study-groups', icon: Users2 },
  { name: 'Cohorts', href: '/cohorts', icon: Heart },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { isPremium } = useSubscription()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-brand-600 to-brand-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2">
              <div className="flex items-center justify-center w-9 h-9 bg-white/20 rounded-lg">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <span className="text-white text-xl font-bold tracking-tight">GradPath</span>
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex space-x-1">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={clsx(
                      'flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-white/20 text-white'
                        : 'text-white/80 hover:bg-white/10 hover:text-white'
                    )}
                  >
                    <item.icon className="h-4 w-4 mr-2" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>

            {/* Search and Profile (desktop) */}
            <div className="hidden md:flex items-center gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search courses..."
                  className="pl-10 pr-4 py-2 rounded-lg bg-white/10 border border-white/20 text-white placeholder-white/60 focus:bg-white focus:text-gray-900 focus:placeholder-gray-400 transition-colors w-64"
                />
              </div>

              {/* Auth */}
              <SignedOut>
                <SignInButton mode="modal">
                  <button className="flex items-center px-4 py-2 rounded-lg text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white transition-colors">
                    <User className="h-4 w-4 mr-2" />
                    Sign In
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                {!isPremium && (
                  <Link
                    to="/pricing"
                    className="flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-amber-400 text-amber-900 hover:bg-amber-300 transition-colors"
                  >
                    <Crown className="h-4 w-4 mr-1.5" />
                    Upgrade
                  </Link>
                )}
                {isPremium && (
                  <span className="flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-green-500/20 text-green-100">
                    <Crown className="h-3 w-3 mr-1" />
                    Premium
                  </span>
                )}
                <Link
                  to="/profile"
                  className={clsx(
                    'flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    location.pathname === '/profile'
                      ? 'bg-white/20 text-white'
                      : 'text-white/80 hover:bg-white/10 hover:text-white'
                  )}
                >
                  <User className="h-4 w-4 mr-2" />
                  Profile
                </Link>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
            </div>
          </div>
        </div>

        {/* Mobile navigation */}
        <nav className="md:hidden border-t border-white/20">
          <div className="flex justify-around py-2">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={clsx(
                    'flex flex-col items-center px-3 py-2 text-xs',
                    isActive ? 'text-white' : 'text-white/60'
                  )}
                >
                  <item.icon className="h-5 w-5 mb-1" />
                  {item.name}
                </Link>
              )
            })}
          </div>
        </nav>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-gray-500 text-sm">
            GradPath - Smart Course Planning
          </p>
          <p className="text-center text-gray-400 text-xs mt-1">
            Not affiliated with the University of Georgia. Always consult your academic advisor.
          </p>
        </div>
      </footer>
    </div>
  )
}
