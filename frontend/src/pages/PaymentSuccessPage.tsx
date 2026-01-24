import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle, Sparkles, ArrowRight } from 'lucide-react'
import { useSubscription } from '../context/SubscriptionContext'

export default function PaymentSuccessPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { refresh } = useSubscription()

  const sessionId = searchParams.get('session_id')

  // Refresh subscription status on mount
  useEffect(() => {
    refresh()
  }, [refresh])

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-center max-w-md mx-auto">
        {/* Success animation */}
        <div className="relative mb-8">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-32 h-32 bg-green-100 rounded-full animate-ping opacity-25" />
          </div>
          <div className="relative inline-flex items-center justify-center w-24 h-24 bg-green-100 rounded-full">
            <CheckCircle className="h-12 w-12 text-green-600" />
          </div>
        </div>

        {/* Success message */}
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          Welcome to Premium!
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          Your subscription is now active. You have full access to all AI-powered
          features to help you plan your academic journey.
        </p>

        {/* What's unlocked */}
        <div className="card bg-brand-50 border-brand-200 mb-8">
          <h3 className="font-semibold text-brand-900 flex items-center gap-2 mb-4">
            <Sparkles className="h-5 w-5" />
            Here's what you've unlocked:
          </h3>
          <ul className="space-y-2 text-left text-brand-800">
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-600" />
              AI-powered course recommendations
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-600" />
              Personalized degree planning
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-600" />
              Course availability alerts
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-600" />
              Schedule optimization tools
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-600" />
              Priority support
            </li>
          </ul>
        </div>

        {/* CTA buttons */}
        <div className="space-y-3">
          <button
            onClick={() => navigate('/plan')}
            className="btn btn-primary w-full flex items-center justify-center gap-2"
          >
            Go to My Plan
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            onClick={() => navigate('/profile')}
            className="btn btn-secondary w-full"
          >
            View My Profile
          </button>
        </div>

        {/* Session ID for debugging (optional, only in dev) */}
        {sessionId && import.meta.env.DEV && (
          <p className="text-xs text-gray-400 mt-8">
            Session: {sessionId.slice(0, 20)}...
          </p>
        )}
      </div>
    </div>
  )
}
