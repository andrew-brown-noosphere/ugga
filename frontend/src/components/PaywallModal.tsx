import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, SignInButton } from '@clerk/clerk-react'
import { useMutation } from '@tanstack/react-query'
import { X, Lock, Zap, Crown, GraduationCap, Check, Loader2 } from 'lucide-react'
import { createCheckout, setAuthToken } from '../lib/api'
import type { SubscriptionTier } from '../types'
import { clsx } from 'clsx'

interface PaywallModalProps {
  isOpen: boolean
  onClose: () => void
  feature?: string
}

const QUICK_TIERS = [
  {
    id: 'quarter' as SubscriptionTier,
    name: 'Quarter',
    price: '$9.99',
    icon: Zap,
  },
  {
    id: 'year' as SubscriptionTier,
    name: 'Year',
    price: '$24.99',
    icon: Crown,
    recommended: true,
  },
  {
    id: 'graduation' as SubscriptionTier,
    name: 'Graduation',
    price: '$199',
    icon: GraduationCap,
  },
]

export default function PaywallModal({ isOpen, onClose, feature }: PaywallModalProps) {
  const navigate = useNavigate()
  const { isSignedIn, getToken } = useAuth()
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier>('year')

  const checkoutMutation = useMutation({
    mutationFn: async (tier: SubscriptionTier) => {
      const token = await getToken()
      setAuthToken(token)
      return createCheckout(tier)
    },
    onSuccess: (data) => {
      window.location.href = data.checkout_url
    },
    onError: (error) => {
      console.error('Checkout error:', error)
      alert('Failed to start checkout. Please try again.')
    },
  })

  const handleSubscribe = () => {
    if (isSignedIn) {
      checkoutMutation.mutate(selectedTier)
    }
  }

  const handleViewPlans = () => {
    onClose()
    navigate('/pricing')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        {/* Header with gradient */}
        <div className="bg-gradient-to-br from-brand-600 to-brand-700 px-6 py-8 text-white text-center relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1 rounded-full hover:bg-white/20 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/20 rounded-full mb-4">
            <Lock className="h-8 w-8" />
          </div>

          <h2 className="text-2xl font-bold mb-2">Upgrade to Premium</h2>
          <p className="text-white/80">
            {feature
              ? `Unlock ${feature} and more with a premium subscription.`
              : 'Get full access to AI-powered course planning tools.'
            }
          </p>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Quick tier selection */}
          <div className="space-y-3 mb-6">
            {QUICK_TIERS.map((tier) => {
              const Icon = tier.icon
              const isSelected = selectedTier === tier.id

              return (
                <button
                  key={tier.id}
                  onClick={() => setSelectedTier(tier.id)}
                  className={clsx(
                    'w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left',
                    isSelected
                      ? 'border-brand-500 bg-brand-50'
                      : 'border-gray-200 hover:border-gray-300'
                  )}
                >
                  <div className={clsx(
                    'w-10 h-10 rounded-full flex items-center justify-center',
                    isSelected ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-600'
                  )}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900">{tier.name}</span>
                      {tier.recommended && (
                        <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">
                          Recommended
                        </span>
                      )}
                    </div>
                    <span className="text-sm text-gray-500">{tier.price}</span>
                  </div>
                  <div className={clsx(
                    'w-5 h-5 rounded-full border-2 flex items-center justify-center',
                    isSelected
                      ? 'border-brand-500 bg-brand-500'
                      : 'border-gray-300'
                  )}>
                    {isSelected && <Check className="h-3 w-3 text-white" />}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Features */}
          <div className="mb-6">
            <p className="text-sm font-medium text-gray-700 mb-2">What you'll get:</p>
            <ul className="space-y-2">
              {[
                'AI course recommendations',
                'Personalized degree planning',
                'Course availability alerts',
                'Priority support',
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="h-4 w-4 text-green-500" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* CTA Buttons */}
          <div className="space-y-3">
            {isSignedIn ? (
              <button
                onClick={handleSubscribe}
                disabled={checkoutMutation.isPending}
                className={clsx(
                  'btn btn-primary w-full',
                  checkoutMutation.isPending && 'opacity-50 cursor-not-allowed'
                )}
              >
                {checkoutMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Loading...
                  </>
                ) : (
                  `Subscribe to ${QUICK_TIERS.find(t => t.id === selectedTier)?.name}`
                )}
              </button>
            ) : (
              <SignInButton mode="modal">
                <button className="btn btn-primary w-full">
                  Sign in to Subscribe
                </button>
              </SignInButton>
            )}

            <button
              onClick={handleViewPlans}
              className="btn btn-secondary w-full"
            >
              View All Plans
            </button>
          </div>

        </div>
      </div>
    </div>
  )
}
