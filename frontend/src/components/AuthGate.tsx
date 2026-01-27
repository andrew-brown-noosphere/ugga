import { useState } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { useMutation } from '@tanstack/react-query'
import { Mail, CheckCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { clsx } from 'clsx'
import { joinWaitlist } from '../lib/api'

interface AuthGateProps {
  children: React.ReactNode
  icon: LucideIcon
  title: string
  description: string
  features: string[]
}

/**
 * Wraps a page to require authentication.
 * Shows a marketing landing page with waitlist signup when not logged in.
 */
export default function AuthGate({
  children,
  icon: Icon,
  title,
  description,
  features,
}: AuthGateProps) {
  const { isSignedIn, isLoaded } = useAuth()
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const waitlistMutation = useMutation({
    mutationFn: (email: string) => joinWaitlist(email),
    onSuccess: () => setSubmitted(true),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (email.trim() && !waitlistMutation.isPending) {
      waitlistMutation.mutate(email.trim())
    }
  }

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

  // Not authenticated - show marketing landing with waitlist
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

      {/* Waitlist signup */}
      <div className="card bg-amber-50 border-amber-200">
        {!submitted ? (
          <>
            <div className="text-center mb-4">
              <h3 className="font-semibold text-amber-900">Join the Waitlist</h3>
              <p className="text-sm text-amber-700 mt-1">
                We're launching to a small group first. Get early access!
              </p>
            </div>
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-amber-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your.email@uga.edu"
                  className="w-full pl-10 pr-4 py-3 border border-amber-200 rounded-xl bg-white focus:ring-2 focus:ring-amber-400 focus:border-amber-400 transition-all"
                />
              </div>
              <button
                type="submit"
                disabled={waitlistMutation.isPending}
                className={clsx(
                  'px-6 py-3 rounded-xl font-medium transition-all shadow-md whitespace-nowrap',
                  waitlistMutation.isPending
                    ? 'bg-amber-200 text-amber-500 cursor-not-allowed'
                    : 'bg-amber-700 text-white hover:bg-amber-800 hover:shadow-lg'
                )}
              >
                {waitlistMutation.isPending ? 'Joining...' : 'Get Early Access'}
              </button>
            </form>
            {waitlistMutation.isError && (
              <p className="text-red-500 text-sm mt-2 text-center">
                Something went wrong. Try again?
              </p>
            )}
          </>
        ) : (
          <div className="text-center py-4">
            <div className="flex items-center justify-center gap-2 mb-2">
              <CheckCircle className="h-6 w-6 text-green-600" />
              <span className="text-green-800 font-semibold text-lg">You're on the list!</span>
            </div>
            <p className="text-green-700">
              We'll reach out within 24 hours to get you set up.
            </p>
          </div>
        )}
      </div>

      <p className="text-center text-sm text-gray-500 mt-6">
        GradPath is currently in beta. We're refining features based on student feedback.
      </p>
    </div>
  )
}
