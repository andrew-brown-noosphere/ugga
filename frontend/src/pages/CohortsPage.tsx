import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import {
  Users,
  Plus,
  Copy,
  RefreshCw,
  Crown,
  LogOut,
  X,
  UserPlus,
  Lock,
  Globe,
  Heart,
} from 'lucide-react'
import {
  getMyCohorts,
  createCohort,
  joinCohortByCode,
  leaveCohort,
  getCohortMembers,
  regenerateCohortCode,
  getCurrentUser,
  setAuthToken,
} from '../lib/api'
import type { Cohort, CohortMember, CohortCreateRequest } from '../types'
import { clsx } from 'clsx'
import AuthGate from '../components/AuthGate'

const COHORTS_FEATURES = [
  'Join your fraternity or sorority to coordinate class schedules',
  'Create private groups with friends using invite codes',
  'See when your group members have overlapping free time',
  'Plan study sessions around everyone\'s availability',
]

export default function CohortsPage() {
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showJoinModal, setShowJoinModal] = useState(false)
  const [selectedCohort, setSelectedCohort] = useState<Cohort | null>(null)
  const [inviteCode, setInviteCode] = useState('')
  const [copied, setCopied] = useState(false)

  // Create form state
  const [formData, setFormData] = useState<CohortCreateRequest>({
    name: '',
    description: '',
    is_public: false,
    max_members: 20,
  })

  const { data: user } = useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getCurrentUser()
    },
    enabled: isSignedIn,
  })

  const { data: cohorts, isLoading } = useQuery({
    queryKey: ['myCohorts'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getMyCohorts()
    },
    enabled: isSignedIn,
  })

  const { data: members } = useQuery({
    queryKey: ['cohortMembers', selectedCohort?.id],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getCohortMembers(selectedCohort!.id)
    },
    enabled: !!selectedCohort,
  })

  const createMutation = useMutation({
    mutationFn: createCohort,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myCohorts'] })
      setShowCreateModal(false)
      setFormData({
        name: '',
        description: '',
        is_public: false,
        max_members: 20,
      })
    },
  })

  const joinMutation = useMutation({
    mutationFn: (code: string) => joinCohortByCode(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myCohorts'] })
      setShowJoinModal(false)
      setInviteCode('')
    },
  })

  const leaveMutation = useMutation({
    mutationFn: (cohortId: number) => leaveCohort(cohortId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myCohorts'] })
      setSelectedCohort(null)
    },
  })

  const regenerateMutation = useMutation({
    mutationFn: (cohortId: number) => regenerateCohortCode(cohortId),
    onSuccess: (data, cohortId) => {
      queryClient.invalidateQueries({ queryKey: ['myCohorts'] })
      if (selectedCohort && selectedCohort.id === cohortId) {
        setSelectedCohort({ ...selectedCohort, invite_code: data.invite_code })
      }
    },
  })

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleJoinSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (inviteCode.trim()) {
      joinMutation.mutate(inviteCode.trim())
    }
  }

  const copyInviteCode = (code: string) => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

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

  const isVerified = user?.uga_email_verified

  return (
    <AuthGate
      icon={Heart}
      title="My Cohorts"
      description="Coordinate schedules with your friends and groups"
      features={COHORTS_FEATURES}
    >
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Cohorts</h1>
          <p className="text-gray-600">Coordinate schedules with your friends and groups</p>
        </div>
        {isVerified && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowJoinModal(true)}
              className="btn btn-secondary flex items-center gap-2"
            >
              <UserPlus className="h-4 w-4" />
              Join
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn btn-primary flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Create
            </button>
          </div>
        )}
      </div>

      {/* Not verified */}
      {!isVerified && (
        <div className="card bg-amber-50 border-amber-200">
          <div className="flex items-start gap-3">
            <Users className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Verify your UGA email</p>
              <p className="text-sm text-amber-700 mt-1">
                You need to verify your @uga.edu email to create or join cohorts.
              </p>
              <a href="/profile" className="btn btn-secondary mt-3 inline-block">
                Go to Profile
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Cohorts List */}
      {isVerified && (
        <>
          {isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="card animate-pulse">
                  <div className="h-6 bg-gray-200 rounded w-2/3 mb-2" />
                  <div className="h-4 bg-gray-200 rounded w-1/2 mb-4" />
                  <div className="h-4 bg-gray-200 rounded w-full" />
                </div>
              ))}
            </div>
          ) : cohorts && cohorts.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {cohorts.map((cohort) => (
                <div
                  key={cohort.id}
                  className="card hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => setSelectedCohort(cohort)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        {cohort.is_admin && (
                          <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full flex items-center gap-1">
                            <Crown className="h-3 w-3" />
                            Admin
                          </span>
                        )}
                        {cohort.is_public ? (
                          <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full flex items-center gap-1">
                            <Globe className="h-3 w-3" />
                            Public
                          </span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full flex items-center gap-1">
                            <Lock className="h-3 w-3" />
                            Private
                          </span>
                        )}
                      </div>
                      <h3 className="font-semibold text-gray-900">{cohort.name}</h3>
                    </div>
                    <Users className="h-5 w-5 text-gray-400" />
                  </div>

                  {cohort.description && (
                    <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                      {cohort.description}
                    </p>
                  )}

                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                    <span className="flex items-center gap-1 text-sm text-gray-500">
                      <Users className="h-4 w-4" />
                      {cohort.member_count} / {cohort.max_members} members
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card text-center py-12">
              <Users className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No cohorts yet</h3>
              <p className="text-gray-600 mb-4">
                Create a cohort or join one with an invite code.
              </p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={() => setShowJoinModal(true)}
                  className="btn btn-secondary"
                >
                  Join with Code
                </button>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="btn btn-primary"
                >
                  Create Cohort
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Cohort Detail Modal */}
      {selectedCohort && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    {selectedCohort.is_admin && (
                      <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full flex items-center gap-1">
                        <Crown className="h-3 w-3" />
                        Admin
                      </span>
                    )}
                  </div>
                  <h2 className="text-xl font-bold text-gray-900">{selectedCohort.name}</h2>
                </div>
                <button
                  onClick={() => setSelectedCohort(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>

              {selectedCohort.description && (
                <p className="text-gray-600 mb-6">{selectedCohort.description}</p>
              )}

              {/* Invite Code Section */}
              {selectedCohort.invite_code && (
                <div className="bg-gray-50 rounded-lg p-4 mb-6">
                  <p className="text-sm text-gray-600 mb-2">Invite Code</p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 bg-white px-3 py-2 rounded border font-mono text-lg tracking-wider">
                      {selectedCohort.invite_code}
                    </code>
                    <button
                      onClick={() => copyInviteCode(selectedCohort.invite_code!)}
                      className="btn btn-secondary p-2"
                      title="Copy invite code"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                    {selectedCohort.is_admin && (
                      <button
                        onClick={() => regenerateMutation.mutate(selectedCohort.id)}
                        disabled={regenerateMutation.isPending}
                        className="btn btn-secondary p-2"
                        title="Generate new code"
                      >
                        <RefreshCw
                          className={clsx(
                            'h-4 w-4',
                            regenerateMutation.isPending && 'animate-spin'
                          )}
                        />
                      </button>
                    )}
                  </div>
                  {copied && (
                    <p className="text-sm text-green-600 mt-2">Copied to clipboard!</p>
                  )}
                  <p className="text-xs text-gray-500 mt-2">
                    Share this code with friends to invite them to your cohort.
                  </p>
                </div>
              )}

              {/* Members List */}
              <div className="mb-6">
                <h3 className="font-semibold text-gray-900 mb-3">
                  Members ({selectedCohort.member_count})
                </h3>
                <div className="space-y-2">
                  {members?.map((member: CohortMember) => (
                    <div
                      key={member.id}
                      className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg"
                    >
                      {member.photo_url ? (
                        <img
                          src={member.photo_url}
                          alt={member.first_name || member.username || ''}
                          className="w-8 h-8 rounded-full object-cover"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center">
                          <Users className="h-4 w-4 text-brand-600" />
                        </div>
                      )}
                      <div className="flex-1">
                        <p className="font-medium text-gray-900 text-sm">
                          {member.first_name || member.username || 'Unknown'}
                        </p>
                      </div>
                      {member.role === 'admin' && (
                        <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">
                          Admin
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              {!selectedCohort.is_admin && (
                <button
                  onClick={() => leaveMutation.mutate(selectedCohort.id)}
                  disabled={leaveMutation.isPending}
                  className="btn btn-secondary w-full flex items-center justify-center gap-2"
                >
                  <LogOut className="h-4 w-4" />
                  {leaveMutation.isPending ? 'Leaving...' : 'Leave Cohort'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <form onSubmit={handleCreateSubmit} className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900">Create Cohort</h2>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cohort Name *
                  </label>
                  <input
                    type="text"
                    required
                    className="input"
                    placeholder="e.g., The Study Squad, Alpha Phi Sisters"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    className="input"
                    rows={3}
                    placeholder="What is this cohort about?"
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({ ...formData, description: e.target.value })
                    }
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Members
                  </label>
                  <input
                    type="number"
                    className="input"
                    min={2}
                    max={100}
                    value={formData.max_members}
                    onChange={(e) =>
                      setFormData({ ...formData, max_members: parseInt(e.target.value) })
                    }
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_public"
                    checked={formData.is_public}
                    onChange={(e) =>
                      setFormData({ ...formData, is_public: e.target.checked })
                    }
                    className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                  />
                  <label htmlFor="is_public" className="text-sm text-gray-700">
                    Make this cohort public (others can find and request to join)
                  </label>
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className={clsx(
                    'btn btn-primary flex-1',
                    createMutation.isPending && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Cohort'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Join Modal */}
      {showJoinModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full">
            <form onSubmit={handleJoinSubmit} className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-gray-900">Join Cohort</h2>
                <button
                  type="button"
                  onClick={() => {
                    setShowJoinModal(false)
                    setInviteCode('')
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Invite Code
                </label>
                <input
                  type="text"
                  required
                  className="input font-mono text-lg tracking-wider text-center uppercase"
                  placeholder="ABCD1234"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                  maxLength={8}
                />
                <p className="text-sm text-gray-500 mt-2">
                  Ask a cohort admin for the invite code.
                </p>
              </div>

              {joinMutation.isError && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">
                    Invalid invite code. Please check and try again.
                  </p>
                </div>
              )}

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setShowJoinModal(false)
                    setInviteCode('')
                  }}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={joinMutation.isPending || inviteCode.length < 8}
                  className={clsx(
                    'btn btn-primary flex-1',
                    (joinMutation.isPending || inviteCode.length < 8) &&
                      'opacity-50 cursor-not-allowed'
                  )}
                >
                  {joinMutation.isPending ? 'Joining...' : 'Join Cohort'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
    </AuthGate>
  )
}
