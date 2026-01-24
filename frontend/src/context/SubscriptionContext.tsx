import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from '@clerk/clerk-react'
import { getSubscriptionStatus, setAuthToken } from '../lib/api'
import type { SubscriptionState, SubscriptionStatus, SubscriptionTier } from '../types'

interface SubscriptionContextType {
  subscription: SubscriptionState
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
  isPremium: boolean
}

const defaultSubscription: SubscriptionState = {
  status: 'free',
  tier: null,
  endDate: null,
  isPremium: false,
}

const SubscriptionContext = createContext<SubscriptionContextType | null>(null)

export function SubscriptionProvider({ children }: { children: ReactNode }) {
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const [subscription, setSubscription] = useState<SubscriptionState>(defaultSubscription)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSubscription = useCallback(async () => {
    // Wait for Clerk to load before checking auth
    if (!isLoaded || !isSignedIn) {
      setSubscription(defaultSubscription)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const token = await getToken()
      setAuthToken(token)

      const status = await getSubscriptionStatus()
      setSubscription({
        status: status.status as SubscriptionStatus,
        tier: status.tier as SubscriptionTier | null,
        endDate: status.end_date ? new Date(status.end_date) : null,
        isPremium: status.is_premium,
      })
    } catch (err) {
      console.error('Failed to fetch subscription status:', err)
      setError('Failed to load subscription status')
      // Keep existing state on error
    } finally {
      setIsLoading(false)
    }
  }, [isLoaded, isSignedIn, getToken])

  // Fetch subscription on mount and when auth changes
  useEffect(() => {
    fetchSubscription()
  }, [fetchSubscription])

  const value: SubscriptionContextType = {
    subscription,
    isLoading,
    error,
    refresh: fetchSubscription,
    isPremium: subscription.isPremium,
  }

  return (
    <SubscriptionContext.Provider value={value}>
      {children}
    </SubscriptionContext.Provider>
  )
}

export function useSubscription() {
  const context = useContext(SubscriptionContext)
  if (!context) {
    throw new Error('useSubscription must be used within a SubscriptionProvider')
  }
  return context
}
