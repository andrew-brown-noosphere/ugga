import { useState } from 'react'
import { useAuth, SignInButton } from '@clerk/clerk-react'
import { Check, Zap, GraduationCap, Crown, Loader2 } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { createCheckout, setAuthToken } from '../lib/api'
import { useSubscription } from '../context/SubscriptionContext'
import type { SubscriptionTier, TierConfig } from '../types'
import { clsx } from 'clsx'

const TIERS: TierConfig[] = [
  {
    id: 'quarter',
    name: 'Quarter',
    price: '$9.99',
    priceSubtext: 'per quarter',
    duration: '3 months',
    features: [
      'AI-powered course recommendations',
      'Personalized degree planning',
      'Course availability alerts',
      'Prerequisite tracking',
      'Priority support',
    ],
  },
  {
    id: 'year',
    name: 'Yearly',
    price: '$24.99',
    priceSubtext: 'per year',
    duration: '12 months',
    features: [
      'Everything in Quarter plan',
      'Save 37% vs quarterly',
      'Early access to new features',
      'Exclusive study resources',
      'Schedule optimization tools',
    ],
    highlighted: true,
  },
  {
    id: 'graduation',
    name: 'Till Graduation',
    price: '$199',
    priceSubtext: 'one-time payment',
    duration: 'Until you graduate',
    features: [
      'Everything in Yearly plan',
      'Never pay again',
      'Lifetime feature updates',
      'Graduate mentor network access',
      'Career planning tools',
      'Alumni community access',
    ],
  },
]

export default function PricingPage() {
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const { subscription, isPremium } = useSubscription()
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(null)

  const checkoutMutation = useMutation({
    mutationFn: async (tier: SubscriptionTier) => {
      const token = await getToken()
      setAuthToken(token)
      return createCheckout(tier)
    },
    onSuccess: (data) => {
      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url
    },
    onError: (error) => {
      console.error('Checkout error:', error)
      alert('Failed to start checkout. Please try again.')
    },
  })

  const handleSelectTier = (tier: SubscriptionTier) => {
    setSelectedTier(tier)
    if (isSignedIn) {
      checkoutMutation.mutate(tier)
    }
  }

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          Unlock Your Academic Potential
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Get AI-powered course recommendations, personalized degree planning, and tools
          to help you graduate smarter and faster.
        </p>
      </div>

      {/* Current subscription status */}
      {isPremium && (
        <div className="card bg-green-50 border-green-200 max-w-xl mx-auto">
          <div className="flex items-center gap-3">
            <Crown className="h-6 w-6 text-green-600" />
            <div>
              <p className="font-medium text-green-900">You're a Premium member!</p>
              <p className="text-sm text-green-700">
                {subscription.tier === 'graduation'
                  ? 'You have lifetime access until graduation.'
                  : `Your ${subscription.tier} subscription is active${subscription.endDate ? ` until ${subscription.endDate.toLocaleDateString()}` : ''}.`
                }
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Pricing Cards */}
      <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
        {TIERS.map((tier) => {
          const isCurrentTier = subscription.tier === tier.id
          const isDisabled = isPremium && !isCurrentTier

          return (
            <div
              key={tier.id}
              className={clsx(
                'card relative flex flex-col',
                tier.highlighted && 'ring-2 ring-brand-500 shadow-lg',
                isCurrentTier && 'ring-2 ring-green-500'
              )}
            >
              {/* Best Value Badge */}
              {tier.highlighted && !isCurrentTier && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-brand-500 text-white text-xs font-semibold px-3 py-1 rounded-full">
                    Best Value
                  </span>
                </div>
              )}

              {/* Current Plan Badge */}
              {isCurrentTier && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-green-500 text-white text-xs font-semibold px-3 py-1 rounded-full">
                    Current Plan
                  </span>
                </div>
              )}

              {/* Header */}
              <div className="text-center pb-6 border-b border-gray-200">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-brand-100 mb-4">
                  {tier.id === 'quarter' && <Zap className="h-6 w-6 text-brand-600" />}
                  {tier.id === 'year' && <Crown className="h-6 w-6 text-brand-600" />}
                  {tier.id === 'graduation' && <GraduationCap className="h-6 w-6 text-brand-600" />}
                </div>
                <h3 className="text-xl font-bold text-gray-900">{tier.name}</h3>
                <div className="mt-4">
                  <span className="text-4xl font-bold text-gray-900">{tier.price}</span>
                  <span className="text-gray-500 ml-1">{tier.priceSubtext}</span>
                </div>
                <p className="text-sm text-gray-500 mt-1">{tier.duration}</p>
              </div>

              {/* Features */}
              <ul className="flex-1 py-6 space-y-3">
                {tier.features.map((feature, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <Check className="h-5 w-5 text-green-500 flex-shrink-0" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA Button */}
              <div className="pt-6 border-t border-gray-200">
                {isSignedIn ? (
                  <button
                    onClick={() => handleSelectTier(tier.id)}
                    disabled={checkoutMutation.isPending || isDisabled || isCurrentTier}
                    className={clsx(
                      'btn w-full',
                      tier.highlighted ? 'btn-primary' : 'btn-secondary',
                      (checkoutMutation.isPending && selectedTier === tier.id) && 'opacity-50 cursor-not-allowed',
                      isCurrentTier && 'bg-green-100 text-green-700 border-green-200 cursor-default',
                      isDisabled && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    {checkoutMutation.isPending && selectedTier === tier.id ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Loading...
                      </>
                    ) : isCurrentTier ? (
                      'Current Plan'
                    ) : (
                      `Get ${tier.name}`
                    )}
                  </button>
                ) : (
                  <SignInButton mode="modal">
                    <button
                      className={clsx(
                        'btn w-full',
                        tier.highlighted ? 'btn-primary' : 'btn-secondary'
                      )}
                    >
                      Sign in to Subscribe
                    </button>
                  </SignInButton>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* FAQ or Additional Info */}
      <div className="max-w-2xl mx-auto text-center">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Questions? We've got answers.
        </h3>
        <div className="space-y-4 text-left">
          <div className="card">
            <h4 className="font-medium text-gray-900">Can I cancel anytime?</h4>
            <p className="text-sm text-gray-600 mt-1">
              Yes! You can cancel your subscription at any time. You'll continue to have access
              until the end of your billing period.
            </p>
          </div>
          <div className="card">
            <h4 className="font-medium text-gray-900">What happens after I graduate?</h4>
            <p className="text-sm text-gray-600 mt-1">
              The "Till Graduation" plan gives you access until you complete your degree.
              After graduation, you'll maintain read-only access to your historical data.
            </p>
          </div>
          <div className="card">
            <h4 className="font-medium text-gray-900">Is there a free trial?</h4>
            <p className="text-sm text-gray-600 mt-1">
              You can view your degree plan for free. Premium features like AI recommendations,
              schedule optimization, and alerts require a subscription.
            </p>
          </div>
        </div>
      </div>

    </div>
  )
}
