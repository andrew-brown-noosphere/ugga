import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import {
  Eye,
  Globe,
  Shield,
  Users,
  Lock,
  Loader2,
  CheckCircle,
  User,
  GraduationCap,
  BookOpen,
  TrendingUp,
  Mail,
  Link as LinkIcon,
  Camera,
  Calendar,
} from 'lucide-react'
import { clsx } from 'clsx'
import {
  getVisibilitySettings,
  updateVisibilitySettings,
  getVerificationStatus,
  setAuthToken,
} from '../lib/api'
import type { VisibilitySettings } from '../types'

const VISIBILITY_OPTIONS = [
  {
    value: 'public' as const,
    label: 'Public',
    description: 'Anyone with the link can view',
    icon: Globe,
  },
  {
    value: 'verified_only' as const,
    label: 'Verified UGA',
    description: 'Only verified UGA students',
    icon: Shield,
  },
  {
    value: 'cohorts_only' as const,
    label: 'Cohorts Only',
    description: 'Only your cohort members',
    icon: Users,
  },
  {
    value: 'private' as const,
    label: 'Private',
    description: 'Only you can view',
    icon: Lock,
  },
]

const FIELD_TOGGLES = [
  { key: 'show_full_name', label: 'Full Name', icon: User },
  { key: 'show_photo', label: 'Profile Photo', icon: Camera },
  { key: 'show_bio', label: 'Bio', icon: User },
  { key: 'show_major', label: 'Major', icon: GraduationCap },
  { key: 'show_graduation_year', label: 'Graduation Year', icon: Calendar },
  { key: 'show_classification', label: 'Classification', icon: User },
  { key: 'show_completed_courses', label: 'Completed Courses', icon: BookOpen },
  { key: 'show_current_schedule', label: 'Current Schedule', icon: Calendar },
  { key: 'show_gpa', label: 'GPA', icon: TrendingUp },
  { key: 'show_degree_progress', label: 'Degree Progress', icon: TrendingUp },
  { key: 'show_email', label: 'Email Address', icon: Mail },
  { key: 'show_social_links', label: 'Social Links', icon: LinkIcon },
] as const

type FieldKey = typeof FIELD_TOGGLES[number]['key']

export default function VisibilitySettingsCard() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()
  const [localSettings, setLocalSettings] = useState<VisibilitySettings | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [saved, setSaved] = useState(false)

  const { data: verificationStatus } = useQuery({
    queryKey: ['verificationStatus'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getVerificationStatus()
    },
  })

  const { data: settings, isLoading } = useQuery({
    queryKey: ['visibilitySettings'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getVisibilitySettings()
    },
    enabled: verificationStatus?.is_verified,
  })

  useEffect(() => {
    if (settings && !localSettings) {
      setLocalSettings(settings)
    }
  }, [settings, localSettings])

  const updateMutation = useMutation({
    mutationFn: async (newSettings: Partial<VisibilitySettings>) => {
      const token = await getToken()
      setAuthToken(token)
      return updateVisibilitySettings(newSettings)
    },
    onSuccess: (data) => {
      setLocalSettings(data)
      setHasChanges(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      queryClient.invalidateQueries({ queryKey: ['visibilitySettings'] })
    },
  })

  const handleVisibilityChange = (visibility: VisibilitySettings['profile_visibility']) => {
    if (!localSettings) return
    const updated = { ...localSettings, profile_visibility: visibility }
    setLocalSettings(updated)
    setHasChanges(true)
  }

  const handleToggle = (key: FieldKey) => {
    if (!localSettings) return
    const updated = { ...localSettings, [key]: !localSettings[key] }
    setLocalSettings(updated)
    setHasChanges(true)
  }

  const handleSave = () => {
    if (localSettings) {
      updateMutation.mutate(localSettings)
    }
  }

  // Don't show if not verified
  if (!verificationStatus?.is_verified) {
    return null
  }

  if (isLoading || !localSettings) {
    return (
      <div className="card animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="h-4 bg-gray-200 rounded w-2/3" />
      </div>
    )
  }

  return (
    <div className="card border-gray-200">
      <div className="flex items-start gap-4 mb-6">
        <div className="p-3 bg-gray-100 rounded-xl">
          <Eye className="h-6 w-6 text-gray-600" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900">Profile Visibility</h3>
          <p className="text-sm text-gray-600 mt-1">
            Control who can see your public profile at{' '}
            <span className="font-mono text-brand-600">
              /u/{verificationStatus.username}
            </span>
          </p>
        </div>
      </div>

      {/* Visibility Level Selection */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Who can view your profile?
        </label>
        <div className="grid grid-cols-2 gap-3">
          {VISIBILITY_OPTIONS.map((option) => {
            const Icon = option.icon
            const isSelected = localSettings.profile_visibility === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => handleVisibilityChange(option.value)}
                className={clsx(
                  'p-3 rounded-lg border text-left transition-all',
                  isSelected
                    ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500 ring-opacity-20'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Icon
                    className={clsx(
                      'h-4 w-4',
                      isSelected ? 'text-brand-600' : 'text-gray-500'
                    )}
                  />
                  <span
                    className={clsx(
                      'font-medium',
                      isSelected ? 'text-brand-900' : 'text-gray-900'
                    )}
                  >
                    {option.label}
                  </span>
                </div>
                <p className="text-xs text-gray-500">{option.description}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* Field Visibility Toggles */}
      {localSettings.profile_visibility !== 'private' && (
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            What information to show
          </label>
          <div className="space-y-2">
            {FIELD_TOGGLES.map((field) => {
              const Icon = field.icon
              const isEnabled = localSettings[field.key]
              return (
                <button
                  key={field.key}
                  type="button"
                  onClick={() => handleToggle(field.key)}
                  className={clsx(
                    'w-full flex items-center justify-between p-3 rounded-lg border transition-colors',
                    isEnabled
                      ? 'border-green-200 bg-green-50'
                      : 'border-gray-200 bg-gray-50'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={clsx(
                        'h-4 w-4',
                        isEnabled ? 'text-green-600' : 'text-gray-400'
                      )}
                    />
                    <span
                      className={clsx(
                        'text-sm font-medium',
                        isEnabled ? 'text-green-900' : 'text-gray-500'
                      )}
                    >
                      {field.label}
                    </span>
                  </div>
                  <div
                    className={clsx(
                      'w-10 h-6 rounded-full p-1 transition-colors',
                      isEnabled ? 'bg-green-500' : 'bg-gray-300'
                    )}
                  >
                    <div
                      className={clsx(
                        'w-4 h-4 rounded-full bg-white transition-transform',
                        isEnabled ? 'translate-x-4' : 'translate-x-0'
                      )}
                    />
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Save Button */}
      {hasChanges && (
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className={clsx(
            'w-full py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2',
            updateMutation.isPending
              ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
              : 'bg-brand-600 text-white hover:bg-brand-700'
          )}
        >
          {updateMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            'Save Changes'
          )}
        </button>
      )}

      {/* Saved Confirmation */}
      {saved && (
        <div className="flex items-center justify-center gap-2 text-green-600 mt-3">
          <CheckCircle className="h-4 w-4" />
          <span className="text-sm">Settings saved</span>
        </div>
      )}
    </div>
  )
}
