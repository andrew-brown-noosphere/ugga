import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth, SignInButton } from '@clerk/clerk-react'
import {
  User,
  GraduationCap,
  Target,
  BookOpen,
  Calendar,
  AlertCircle,
  ChevronRight,
  Sparkles,
  Edit2,
  Save,
  Link as LinkIcon,
  Camera,
} from 'lucide-react'
import { getCurrentUser, updateUserPreferences, getPersonalizedReport, getPrograms } from '../lib/api'
import { clsx } from 'clsx'
import UGAVerificationCard from '../components/UGAVerificationCard'
import VisibilitySettingsCard from '../components/VisibilitySettingsCard'

const GOALS = [
  { value: 'fast-track', label: 'Fast-Track', description: 'Graduate as quickly as possible' },
  { value: 'specialist', label: 'Specialist', description: 'Deep expertise in your field' },
  { value: 'well-rounded', label: 'Well-Rounded', description: 'Broad educational experience' },
  { value: 'flexible', label: 'Flexible', description: 'Keep options open' },
]

const CLASSIFICATIONS = [
  { value: 'freshman', label: 'Freshman' },
  { value: 'sophomore', label: 'Sophomore' },
  { value: 'junior', label: 'Junior' },
  { value: 'senior', label: 'Senior' },
  { value: 'graduate', label: 'Graduate Student' },
]

const GRADUATION_YEARS = Array.from({ length: 10 }, (_, i) => 2024 + i)

export default function ProfilePage() {
  const { isSignedIn, isLoaded } = useAuth()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)

  // Academic fields
  const [major, setMajor] = useState('')
  const [goal, setGoal] = useState('')

  // Extended profile fields
  const [photoUrl, setPhotoUrl] = useState('')
  const [bio, setBio] = useState('')
  const [graduationYear, setGraduationYear] = useState<number | ''>('')
  const [classification, setClassification] = useState('')

  // Social links
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [githubUrl, setGithubUrl] = useState('')
  const [twitterUrl, setTwitterUrl] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')

  const { data: user, isLoading: loadingUser } = useQuery({
    queryKey: ['user'],
    queryFn: getCurrentUser,
    enabled: isSignedIn,
  })

  const { data: report } = useQuery({
    queryKey: ['user-report'],
    queryFn: getPersonalizedReport,
    enabled: isSignedIn && !!user?.major,
  })

  const { data: programs } = useQuery({
    queryKey: ['programs'],
    queryFn: () => getPrograms(),
    enabled: isSignedIn,
  })

  // Update local state when user data loads
  useEffect(() => {
    if (user) {
      setMajor(user.major || '')
      setGoal(user.goal || '')
      setPhotoUrl(user.photo_url || '')
      setBio(user.bio || '')
      setGraduationYear(user.graduation_year || '')
      setClassification(user.classification || '')
      setLinkedinUrl(user.linkedin_url || '')
      setGithubUrl(user.github_url || '')
      setTwitterUrl(user.twitter_url || '')
      setWebsiteUrl(user.website_url || '')
    }
  }, [user])

  const updateMutation = useMutation({
    mutationFn: (data: {
      major?: string
      goal?: string
      photo_url?: string
      bio?: string
      graduation_year?: number
      classification?: string
      linkedin_url?: string
      github_url?: string
      twitter_url?: string
      website_url?: string
    }) => updateUserPreferences(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user'] })
      queryClient.invalidateQueries({ queryKey: ['user-report'] })
      setEditing(false)
    },
  })

  const handleSave = () => {
    updateMutation.mutate({
      major: major || undefined,
      goal: goal || undefined,
      photo_url: photoUrl || undefined,
      bio: bio || undefined,
      graduation_year: graduationYear ? Number(graduationYear) : undefined,
      classification: classification || undefined,
      linkedin_url: linkedinUrl || undefined,
      github_url: githubUrl || undefined,
      twitter_url: twitterUrl || undefined,
      website_url: websiteUrl || undefined,
    })
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

  if (!isSignedIn) {
    return (
      <div className="space-y-6">
        <div className="card text-center py-12">
          <User className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Sign in to view your profile</h2>
          <p className="text-gray-600 mb-6">
            Track your degree progress, get personalized recommendations, and plan your courses.
          </p>
          <SignInButton mode="modal">
            <button className="btn btn-primary">Sign In</button>
          </SignInButton>
        </div>
      </div>
    )
  }

  if (loadingUser) {
    return (
      <div className="space-y-6">
        <div className="card animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-4" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
        <p className="text-gray-600">Manage your academic profile and view your degree progress</p>
      </div>

      {/* Profile Card */}
      <div className="card">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            {user?.photo_url ? (
              <img
                src={user.photo_url}
                alt={`${user.first_name} ${user.last_name}`}
                className="w-16 h-16 rounded-full object-cover"
              />
            ) : (
              <div className="w-16 h-16 rounded-full bg-brand-100 flex items-center justify-center">
                <User className="h-8 w-8 text-brand-600" />
              </div>
            )}
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {user?.first_name} {user?.last_name}
              </h2>
              <p className="text-gray-500">{user?.email}</p>
              {user?.classification && (
                <span className="inline-block mt-1 text-xs px-2 py-0.5 bg-brand-100 text-brand-700 rounded-full capitalize">
                  {user.classification}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={() => setEditing(!editing)}
            className="btn btn-secondary flex items-center gap-2"
          >
            {editing ? <Save className="h-4 w-4" /> : <Edit2 className="h-4 w-4" />}
            {editing ? 'Cancel' : 'Edit'}
          </button>
        </div>

        {editing ? (
          <div className="space-y-6">
            {/* Profile Photo */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <Camera className="h-4 w-4 inline mr-1" />
                Profile Photo URL
              </label>
              <input
                type="url"
                className="input"
                value={photoUrl}
                onChange={(e) => setPhotoUrl(e.target.value)}
                placeholder="https://example.com/your-photo.jpg"
              />
              <p className="text-xs text-gray-500 mt-1">
                Enter a URL to your profile photo (e.g., from LinkedIn, Gravatar, or uploaded elsewhere)
              </p>
            </div>

            {/* Bio */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <User className="h-4 w-4 inline mr-1" />
                Bio
              </label>
              <textarea
                className="input"
                rows={3}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Tell us a bit about yourself..."
                maxLength={1000}
              />
              <p className="text-xs text-gray-500 mt-1">{bio.length}/1000 characters</p>
            </div>

            {/* Classification and Graduation Year */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Classification
                </label>
                <select
                  className="input"
                  value={classification}
                  onChange={(e) => setClassification(e.target.value)}
                >
                  <option value="">Select classification</option>
                  {CLASSIFICATIONS.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expected Graduation
                </label>
                <select
                  className="input"
                  value={graduationYear}
                  onChange={(e) => setGraduationYear(e.target.value ? Number(e.target.value) : '')}
                >
                  <option value="">Select year</option>
                  {GRADUATION_YEARS.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Major Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                <GraduationCap className="h-4 w-4 inline mr-1" />
                Major
              </label>
              <select
                className="input"
                value={major}
                onChange={(e) => setMajor(e.target.value)}
              >
                <option value="">Select your major</option>
                {programs?.map((p) => (
                  <option key={p.id} value={p.name}>
                    {p.name} ({p.degree_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Goal Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Target className="h-4 w-4 inline mr-1" />
                Academic Goal
              </label>
              <div className="grid grid-cols-2 gap-3">
                {GOALS.map((g) => (
                  <button
                    key={g.value}
                    type="button"
                    onClick={() => setGoal(g.value)}
                    className={clsx(
                      'p-3 rounded-lg border text-left transition-colors',
                      goal === g.value
                        ? 'border-brand-500 bg-brand-50'
                        : 'border-gray-200 hover:border-gray-300'
                    )}
                  >
                    <span className="font-medium text-gray-900">{g.label}</span>
                    <p className="text-sm text-gray-500">{g.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Social Links */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <LinkIcon className="h-4 w-4 inline mr-1" />
                Social Links
              </label>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">LinkedIn</label>
                  <input
                    type="url"
                    className="input"
                    value={linkedinUrl}
                    onChange={(e) => setLinkedinUrl(e.target.value)}
                    placeholder="https://linkedin.com/in/yourprofile"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">GitHub</label>
                  <input
                    type="url"
                    className="input"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    placeholder="https://github.com/yourusername"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Twitter / X</label>
                  <input
                    type="url"
                    className="input"
                    value={twitterUrl}
                    onChange={(e) => setTwitterUrl(e.target.value)}
                    placeholder="https://twitter.com/yourusername"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Personal Website</label>
                  <input
                    type="url"
                    className="input"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    placeholder="https://yourwebsite.com"
                  />
                </div>
              </div>
            </div>

            <button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className={clsx(
                'btn btn-primary w-full',
                updateMutation.isPending && 'opacity-50 cursor-not-allowed'
              )}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Bio Display */}
            {user?.bio && (
              <div className="p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-700">{user.bio}</p>
              </div>
            )}

            {/* Academic Info Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                  <GraduationCap className="h-4 w-4" />
                  Major
                </div>
                <p className="font-medium text-gray-900">{user?.major || 'Not set'}</p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                  <Target className="h-4 w-4" />
                  Goal
                </div>
                <p className="font-medium text-gray-900">
                  {GOALS.find((g) => g.value === user?.goal)?.label || 'Not set'}
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                  <User className="h-4 w-4" />
                  Classification
                </div>
                <p className="font-medium text-gray-900 capitalize">
                  {user?.classification || 'Not set'}
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                  <Calendar className="h-4 w-4" />
                  Graduation
                </div>
                <p className="font-medium text-gray-900">
                  {user?.graduation_year || 'Not set'}
                </p>
              </div>
            </div>

            {/* Social Links Display */}
            {(user?.linkedin_url || user?.github_url || user?.twitter_url || user?.website_url) && (
              <div className="flex flex-wrap gap-3">
                {user?.linkedin_url && (
                  <a
                    href={user.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800"
                  >
                    <LinkIcon className="h-4 w-4" />
                    LinkedIn
                  </a>
                )}
                {user?.github_url && (
                  <a
                    href={user.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800"
                  >
                    <LinkIcon className="h-4 w-4" />
                    GitHub
                  </a>
                )}
                {user?.twitter_url && (
                  <a
                    href={user.twitter_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800"
                  >
                    <LinkIcon className="h-4 w-4" />
                    Twitter
                  </a>
                )}
                {user?.website_url && (
                  <a
                    href={user.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-brand-600 hover:text-brand-800"
                  >
                    <LinkIcon className="h-4 w-4" />
                    Website
                  </a>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* UGA Email Verification */}
      <UGAVerificationCard />

      {/* Profile Visibility Settings */}
      <VisibilitySettingsCard />

      {/* Degree Progress */}
      {report?.degree_progress && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <BookOpen className="h-5 w-5 text-brand-600" />
            Degree Progress
          </h3>

          <div className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600">
                {report.degree_progress.hours_completed} of {report.degree_progress.total_hours_required} hours
              </span>
              <span className="font-medium text-gray-900">
                {report.degree_progress.percent_complete.toFixed(0)}%
              </span>
            </div>
            <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-300"
                style={{ width: `${report.degree_progress.percent_complete}%` }}
              />
            </div>
          </div>

          {report.degree_progress.requirements_remaining.length > 0 && (
            <div>
              <p className="text-sm text-gray-500 mb-2">Requirements remaining:</p>
              <div className="flex flex-wrap gap-2">
                {report.degree_progress.requirements_remaining.slice(0, 5).map((req, i) => (
                  <span key={i} className="badge badge-warning">{req}</span>
                ))}
                {report.degree_progress.requirements_remaining.length > 5 && (
                  <span className="text-sm text-gray-500">
                    +{report.degree_progress.requirements_remaining.length - 5} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Recommendations */}
      {report?.recommendations && report.recommendations.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <Sparkles className="h-5 w-5 text-brand-600" />
            Recommended Courses
          </h3>

          <div className="space-y-3">
            {report.recommendations.slice(0, 5).map((rec, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <span
                  className={clsx(
                    'badge',
                    rec.priority === 'high' && 'badge-danger',
                    rec.priority === 'medium' && 'badge-warning',
                    rec.priority === 'low' && 'badge-success'
                  )}
                >
                  {rec.priority}
                </span>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{rec.course_code}</p>
                  <p className="text-sm text-gray-600">{rec.title}</p>
                  <p className="text-sm text-gray-500 mt-1">{rec.reason}</p>
                </div>
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sample Schedule */}
      {report?.sample_schedule && report.sample_schedule.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <Calendar className="h-5 w-5 text-brand-600" />
            Sample Schedule
          </h3>

          <div className="space-y-4">
            {/* Group by semester */}
            {Array.from(new Set(report.sample_schedule.map((s) => s.semester))).map((semester) => (
              <div key={semester}>
                <h4 className="font-medium text-gray-700 mb-2">{semester}</h4>
                <div className="grid gap-2">
                  {report.sample_schedule
                    .filter((s) => s.semester === semester)
                    .map((course, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-2 bg-gray-50 rounded"
                      >
                        <div>
                          <span className="font-medium">{course.course_code}</span>
                          <span className="text-gray-500 ml-2">{course.title}</span>
                        </div>
                        <span className="text-sm text-gray-500">{course.credit_hours} hrs</span>
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      {report?.disclaimer && (
        <div className="card bg-amber-50 border-amber-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800">{report.disclaimer}</p>
          </div>
        </div>
      )}

      {/* No major set prompt */}
      {!user?.major && !editing && (
        <div className="card bg-blue-50 border-blue-200">
          <div className="flex items-start gap-3">
            <GraduationCap className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-blue-900">Complete your profile</p>
              <p className="text-sm text-blue-700 mt-1">
                Set your major and academic goal to get personalized course recommendations and degree progress tracking.
              </p>
              <button
                onClick={() => setEditing(true)}
                className="btn btn-primary mt-3"
              >
                Set Up Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
