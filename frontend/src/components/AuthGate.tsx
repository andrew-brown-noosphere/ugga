import { useAuth, SignInButton } from '@clerk/clerk-react'
import { Lock } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface AuthGateProps {
  children: React.ReactNode
  icon: LucideIcon
  title: string
  description: string
  features: string[]
}

/**
 * Wraps a page to require authentication.
 * Shows a marketing landing page when not logged in.
 */
export default function AuthGate({
  children,
  icon: Icon,
  title,
  description,
  features,
}: AuthGateProps) {
  const { isSignedIn, isLoaded } = useAuth()

  // Loading state
  if (!isLoaded) {
    return (
      <div className="space-y-6">
        <div className="card animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-4" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      </div>
    )
  }

  // Authenticated - show actual content
  if (isSignedIn) {
    return <>{children}</>
  }

  // Not authenticated - show marketing landing
  return (
    <div className="max-w-2xl mx-auto py-12">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-100 rounded-2xl mb-4">
          <Icon className="h-8 w-8 text-amber-700" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-3" style={{ fontFamily: 'Georgia, serif' }}>
          {title}
        </h1>
        <p className="text-lg text-gray-600">
          {description}
        </p>
      </div>

      <div className="card mb-8">
        <h2 className="font-semibold text-gray-900 mb-4">What you'll get:</h2>
        <ul className="space-y-3">
          {features.map((feature, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="flex-shrink-0 w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-sm">
                ✓
              </span>
              <span className="text-gray-700">{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="card bg-amber-50 border-amber-200 text-center">
        <div className="flex items-center justify-center gap-2 text-amber-800 mb-3">
          <Lock className="h-4 w-4" />
          <span className="font-medium">Sign in to access</span>
        </div>
        <p className="text-sm text-amber-700 mb-4">
          Create a free account to explore all features
        </p>
        <SignInButton mode="modal">
          <button className="btn btn-primary">
            Sign In to Continue
          </button>
        </SignInButton>
      </div>

      <p className="text-center text-sm text-gray-500 mt-6">
        GradPath is currently in beta. We're refining features based on student feedback.
      </p>
    </div>
  )
}
