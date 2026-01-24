import { useUser, useAuth as useClerkAuth } from '@clerk/clerk-react'
import { useEffect, useState } from 'react'
import { setAuthToken } from '../lib/api'

/**
 * Custom auth hook that integrates Clerk with our API.
 *
 * - Syncs Clerk token to API client for authenticated requests
 * - Provides user state and loading status
 * - Works gracefully when Clerk is not configured
 */
export function useAuth() {
  const [isClerkAvailable, setIsClerkAvailable] = useState(true)

  // Try to use Clerk hooks - will throw if not in ClerkProvider
  let clerkUser = null
  let isLoaded = true
  let isSignedIn = false
  let getToken: (() => Promise<string | null>) | null = null

  try {
    const userResult = useUser()
    const authResult = useClerkAuth()
    clerkUser = userResult.user
    isLoaded = userResult.isLoaded
    isSignedIn = userResult.isSignedIn ?? false
    getToken = authResult.getToken
  } catch {
    // Clerk not available - running without auth
    setIsClerkAvailable(false)
  }

  // Sync token to API client when auth state changes
  useEffect(() => {
    if (!isClerkAvailable || !isLoaded) return

    if (isSignedIn && getToken) {
      getToken().then((token) => {
        setAuthToken(token)
      }).catch(() => {
        setAuthToken(null)
      })
    } else {
      setAuthToken(null)
    }
  }, [isSignedIn, isLoaded, getToken, isClerkAvailable])

  return {
    user: clerkUser,
    isLoaded: isClerkAvailable ? isLoaded : true,
    isSignedIn: isClerkAvailable ? isSignedIn : false,
    isClerkAvailable,
    clerkId: clerkUser?.id ?? null,
    email: clerkUser?.primaryEmailAddress?.emailAddress ?? null,
    firstName: clerkUser?.firstName ?? null,
    lastName: clerkUser?.lastName ?? null,
  }
}

/**
 * Hook to check if running in development mode without Clerk.
 * Useful for showing dev-only UI or bypassing auth in development.
 */
export function useDevMode() {
  const { isClerkAvailable } = useAuth()
  const isDev = import.meta.env.DEV
  return isDev && !isClerkAvailable
}
