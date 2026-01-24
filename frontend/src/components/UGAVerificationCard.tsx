import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import {
  Shield,
  Mail,
  CheckCircle,
  Loader2,
  Copy,
  ExternalLink,
  AlertCircle,
} from 'lucide-react'
import { clsx } from 'clsx'
import {
  getVerificationStatus,
  sendVerificationCode,
  confirmVerification,
  setAuthToken,
} from '../lib/api'

export default function UGAVerificationCard() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  const [step, setStep] = useState<'initial' | 'code_sent' | 'verified'>('initial')
  const [ugaEmail, setUgaEmail] = useState('')
  const [code, setCode] = useState('')
  const [customUsername, setCustomUsername] = useState('')
  const [useCustomUsername, setUseCustomUsername] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: status, isLoading } = useQuery({
    queryKey: ['verificationStatus'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getVerificationStatus()
    },
  })

  const sendCodeMutation = useMutation({
    mutationFn: async (email: string) => {
      const token = await getToken()
      setAuthToken(token)
      return sendVerificationCode(email)
    },
    onSuccess: () => {
      setStep('code_sent')
      setError(null)
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to send verification code')
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return confirmVerification(
        ugaEmail,
        code,
        useCustomUsername ? customUsername : undefined
      )
    },
    onSuccess: () => {
      setStep('verified')
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['verificationStatus'] })
      queryClient.invalidateQueries({ queryKey: ['user'] })
    },
    onError: (err: Error) => {
      setError(err.message || 'Invalid verification code')
    },
  })

  const handleSendCode = (e: React.FormEvent) => {
    e.preventDefault()
    if (!ugaEmail.endsWith('@uga.edu')) {
      setError('Please enter a valid @uga.edu email address')
      return
    }
    setError(null)
    sendCodeMutation.mutate(ugaEmail)
  }

  const handleConfirm = (e: React.FormEvent) => {
    e.preventDefault()
    if (code.length !== 6) {
      setError('Please enter a 6-digit code')
      return
    }
    setError(null)
    confirmMutation.mutate()
  }

  const copyProfileLink = () => {
    if (status?.profile_url) {
      navigator.clipboard.writeText(`${window.location.origin}${status.profile_url}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) {
    return (
      <div className="card animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="h-4 bg-gray-200 rounded w-2/3" />
      </div>
    )
  }

  // Already verified
  if (status?.is_verified) {
    return (
      <div className="card border-green-200 bg-green-50">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-green-100 rounded-xl">
            <CheckCircle className="h-6 w-6 text-green-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-green-900 flex items-center gap-2">
              UGA Email Verified
              <span className="text-xs px-2 py-0.5 bg-green-200 text-green-800 rounded-full">
                @{status.username}
              </span>
            </h3>
            <p className="text-sm text-green-700 mt-1">
              {status.uga_email}
            </p>

            <div className="mt-4 flex items-center gap-3">
              <div className="flex-1 flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-green-200">
                <span className="text-sm text-gray-600 truncate">
                  {window.location.origin}{status.profile_url}
                </span>
              </div>
              <button
                onClick={copyProfileLink}
                className="px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
              >
                {copied ? (
                  <>
                    <CheckCircle className="h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy Link
                  </>
                )}
              </button>
              <a
                href={status.profile_url || '#'}
                className="px-3 py-2 border border-green-300 text-green-700 rounded-lg hover:bg-green-100 transition-colors flex items-center gap-2"
              >
                <ExternalLink className="h-4 w-4" />
                View
              </a>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card border-brand-200 bg-brand-50">
      <div className="flex items-start gap-4">
        <div className="p-3 bg-brand-100 rounded-xl">
          <Shield className="h-6 w-6 text-brand-600" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-brand-900">Verify Your UGA Email</h3>
          <p className="text-sm text-brand-700 mt-1">
            Verify your @uga.edu email to get a shareable profile and connect with other students.
          </p>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-red-500 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {step === 'initial' && (
            <form onSubmit={handleSendCode} className="mt-4 space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  UGA Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="email"
                    value={ugaEmail}
                    onChange={(e) => setUgaEmail(e.target.value.toLowerCase())}
                    placeholder="yourname@uga.edu"
                    className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={sendCodeMutation.isPending || !ugaEmail.endsWith('@uga.edu')}
                className={clsx(
                  'w-full py-2 rounded-lg font-medium transition-colors',
                  ugaEmail.endsWith('@uga.edu') && !sendCodeMutation.isPending
                    ? 'bg-brand-600 text-white hover:bg-brand-700'
                    : 'bg-gray-200 text-gray-500 cursor-not-allowed'
                )}
              >
                {sendCodeMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                    Sending...
                  </>
                ) : (
                  'Send Verification Code'
                )}
              </button>
            </form>
          )}

          {step === 'code_sent' && (
            <form onSubmit={handleConfirm} className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Verification Code
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Enter the 6-digit code sent to {ugaEmail}
                </p>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  maxLength={6}
                  className="w-full px-4 py-3 text-center text-2xl tracking-widest border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 font-mono"
                />
              </div>

              <div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={useCustomUsername}
                    onChange={(e) => setUseCustomUsername(e.target.checked)}
                    className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                  />
                  Choose a custom username
                </label>
                {useCustomUsername && (
                  <div className="mt-2">
                    <input
                      type="text"
                      value={customUsername}
                      onChange={(e) => setCustomUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                      placeholder="your_username"
                      maxLength={30}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Letters, numbers, and underscores only. Starts with a letter.
                    </p>
                  </div>
                )}
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setStep('initial')
                    setCode('')
                    setError(null)
                  }}
                  className="flex-1 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={confirmMutation.isPending || code.length !== 6}
                  className={clsx(
                    'flex-1 py-2 rounded-lg font-medium transition-colors',
                    code.length === 6 && !confirmMutation.isPending
                      ? 'bg-brand-600 text-white hover:bg-brand-700'
                      : 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  )}
                >
                  {confirmMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                      Verifying...
                    </>
                  ) : (
                    'Verify'
                  )}
                </button>
              </div>

              <button
                type="button"
                onClick={() => sendCodeMutation.mutate(ugaEmail)}
                disabled={sendCodeMutation.isPending}
                className="w-full text-sm text-brand-600 hover:text-brand-800"
              >
                Didn't receive the code? Send again
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
