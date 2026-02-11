import { Link, useLocation } from 'react-router-dom'
import { BookOpen, Calendar, GraduationCap, Compass, Target, Users, User, Crown, Users2, Heart, Coffee } from 'lucide-react'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/clerk-react'
import { clsx } from 'clsx'
import { useSubscription } from '../context/SubscriptionContext'

interface LayoutProps {
  children: React.ReactNode
}

const navigation = [
  { name: 'My Plan', href: '/plan', icon: Target },
  { name: 'Cohorts', href: '/cohorts', icon: Heart },
  { name: 'Study Groups', href: '/study-groups', icon: Users2 },
  { name: 'Courses', href: '/courses', icon: BookOpen },
  { name: 'Programs', href: '/programs', icon: GraduationCap },
  { name: 'Faculty', href: '/instructors', icon: Users },
  { name: 'Planner', href: '/planner', icon: Calendar },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { isPremium } = useSubscription()

  return (
    <div className="min-h-screen bg-amber-50/50">
      {/* Header - Warm indie coffee shop vibe */}
      <header className="bg-amber-900 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2.5">
              <div className="flex items-center justify-center w-9 h-9 bg-amber-100 rounded-xl">
                <Compass className="h-5 w-5 text-amber-800" />
              </div>
              <span className="text-amber-50 text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>GradPath</span>
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
                      'flex items-center px-3 py-2 rounded-xl text-sm font-medium transition-all',
                      isActive
                        ? 'bg-amber-100/20 text-amber-50'
                        : 'text-amber-200/80 hover:bg-amber-100/10 hover:text-amber-50'
                    )}
                  >
                    <item.icon className="h-4 w-4 mr-1.5" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>

            {/* Profile area */}
            <div className="hidden md:flex items-center gap-3">
              {/* Auth */}
              <SignedOut>
                <SignInButton mode="modal">
                  <button className="flex items-center px-4 py-2 rounded-xl text-sm font-medium text-amber-200/80 hover:bg-amber-100/10 hover:text-amber-50 transition-all">
                    <User className="h-4 w-4 mr-2" />
                    Sign In
                  </button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                {!isPremium && (
                  <Link
                    to="/pricing"
                    className="flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-yellow-400 text-amber-900 hover:bg-yellow-300 transition-colors"
                  >
                    <Crown className="h-4 w-4 mr-1.5" />
                    Upgrade
                  </Link>
                )}
                {isPremium && (
                  <span className="flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-green-600/30 text-green-100">
                    <Crown className="h-3 w-3 mr-1" />
                    Premium
                  </span>
                )}
                <Link
                  to="/profile"
                  className={clsx(
                    'flex items-center px-3 py-2 rounded-xl text-sm font-medium transition-all',
                    location.pathname === '/profile'
                      ? 'bg-amber-100/20 text-amber-50'
                      : 'text-amber-200/80 hover:bg-amber-100/10 hover:text-amber-50'
                  )}
                >
                  <User className="h-4 w-4 mr-1.5" />
                  Profile
                </Link>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
            </div>
          </div>
        </div>

        {/* Mobile navigation */}
        <nav className="md:hidden border-t border-amber-800/50">
          <div className="flex justify-around py-2 overflow-x-auto">
            {navigation.slice(0, 5).map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={clsx(
                    'flex flex-col items-center px-3 py-2 text-xs min-w-fit',
                    isActive ? 'text-amber-50' : 'text-amber-300/60'
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

      {/* Footer - Cozy, local feel */}
      <footer className="bg-amber-950 border-t border-amber-900 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col items-center space-y-3">
            <div className="flex items-center space-x-2 text-amber-200">
              <Coffee className="h-4 w-4" />
              <span className="text-sm font-medium">Made with care in Athens, GA</span>
            </div>
            <p className="text-center text-amber-300/60 text-sm">
              GradPath - Your compass to graduation
            </p>
            <p className="text-center text-amber-300/40 text-xs">
              Independent student tool, trained on public data. Not affiliated with any university.
            </p>
            <p className="text-center text-amber-300/40 text-xs">
              © 2026 ClassicCityAI.com
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
