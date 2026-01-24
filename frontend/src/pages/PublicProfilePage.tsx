import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import {
  User,
  GraduationCap,
  Calendar,
  BookOpen,
  TrendingUp,
  ExternalLink,
  Shield,
  ArrowLeft,
  Lock,
} from 'lucide-react'
import { getPublicProfile, setAuthToken } from '../lib/api'

export default function PublicProfilePage() {
  const { username } = useParams<{ username: string }>()
  const { getToken, isSignedIn } = useAuth()

  const {
    data: profile,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['publicProfile', username],
    queryFn: async () => {
      if (isSignedIn) {
        const token = await getToken()
        setAuthToken(token)
      }
      return getPublicProfile(username!)
    },
    enabled: !!username,
  })

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="card animate-pulse">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-20 h-20 rounded-full bg-gray-200" />
            <div className="flex-1">
              <div className="h-6 bg-gray-200 rounded w-1/3 mb-2" />
              <div className="h-4 bg-gray-200 rounded w-1/4" />
            </div>
          </div>
          <div className="space-y-4">
            <div className="h-4 bg-gray-200 rounded w-full" />
            <div className="h-4 bg-gray-200 rounded w-2/3" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="card text-center py-12">
          <Lock className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Profile Not Found</h2>
          <p className="text-gray-600 mb-6">
            This profile doesn't exist or is set to private.
          </p>
          <Link to="/" className="btn btn-primary">
            Go Home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back Link */}
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to home
      </Link>

      {/* Profile Card */}
      <div className="card">
        <div className="flex items-start gap-4 mb-6">
          {profile.photo_url ? (
            <img
              src={profile.photo_url}
              alt={profile.display_name || profile.username}
              className="w-20 h-20 rounded-full object-cover"
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-brand-100 flex items-center justify-center">
              <User className="h-10 w-10 text-brand-600" />
            </div>
          )}
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-gray-900">
                {profile.display_name || `@${profile.username}`}
              </h1>
              {profile.is_verified && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                  <Shield className="h-3 w-3" />
                  Verified
                </span>
              )}
            </div>
            <p className="text-gray-500">@{profile.username}</p>
            {profile.is_own_profile && (
              <Link
                to="/profile"
                className="inline-flex items-center gap-1 mt-2 text-sm text-brand-600 hover:text-brand-800"
              >
                Edit your profile
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </div>
        </div>

        {/* Bio */}
        {profile.bio && (
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <p className="text-gray-700">{profile.bio}</p>
          </div>
        )}

        {/* Academic Info Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {profile.major && (
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <GraduationCap className="h-4 w-4" />
                Major
              </div>
              <p className="font-medium text-gray-900 text-sm">{profile.major}</p>
            </div>
          )}
          {profile.classification && (
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <User className="h-4 w-4" />
                Classification
              </div>
              <p className="font-medium text-gray-900 capitalize text-sm">
                {profile.classification}
              </p>
            </div>
          )}
          {profile.graduation_year && (
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <Calendar className="h-4 w-4" />
                Graduation
              </div>
              <p className="font-medium text-gray-900 text-sm">{profile.graduation_year}</p>
            </div>
          )}
          {profile.completed_courses_count !== null && (
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <BookOpen className="h-4 w-4" />
                Courses
              </div>
              <p className="font-medium text-gray-900 text-sm">
                {profile.completed_courses_count} completed
              </p>
            </div>
          )}
        </div>

        {/* Progress and GPA */}
        {(profile.degree_progress_percent !== null || profile.gpa !== null) && (
          <div className="grid grid-cols-2 gap-4 mb-6">
            {profile.degree_progress_percent !== null && (
              <div className="p-4 border border-brand-200 bg-brand-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-brand-600 mb-2">
                  <TrendingUp className="h-4 w-4" />
                  Degree Progress
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold text-brand-700">
                    {profile.degree_progress_percent.toFixed(0)}%
                  </span>
                </div>
                <div className="mt-2 w-full h-2 bg-brand-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-600 rounded-full transition-all duration-300"
                    style={{ width: `${profile.degree_progress_percent}%` }}
                  />
                </div>
              </div>
            )}
            {profile.gpa !== null && (
              <div className="p-4 border border-green-200 bg-green-50 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-green-600 mb-2">
                  <GraduationCap className="h-4 w-4" />
                  Cumulative GPA
                </div>
                <span className="text-3xl font-bold text-green-700">
                  {profile.gpa.toFixed(2)}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Social Links */}
        {(profile.linkedin_url ||
          profile.github_url ||
          profile.twitter_url ||
          profile.website_url) && (
          <div className="pt-4 border-t border-gray-200">
            <p className="text-sm text-gray-500 mb-3">Connect</p>
            <div className="flex flex-wrap gap-3">
              {profile.linkedin_url && (
                <a
                  href={profile.linkedin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-[#0077B5] text-white rounded-lg hover:bg-[#006299] transition-colors text-sm"
                >
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                  </svg>
                  LinkedIn
                </a>
              )}
              {profile.github_url && (
                <a
                  href={profile.github_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors text-sm"
                >
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                  </svg>
                  GitHub
                </a>
              )}
              {profile.twitter_url && (
                <a
                  href={profile.twitter_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
                >
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                  </svg>
                  X / Twitter
                </a>
              )}
              {profile.website_url && (
                <a
                  href={profile.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-sm"
                >
                  <ExternalLink className="h-4 w-4" />
                  Website
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="text-center text-sm text-gray-500">
        <p>
          Powered by{' '}
          <Link to="/" className="text-brand-600 hover:text-brand-800">
            UGA Course Scheduler
          </Link>
        </p>
      </div>
    </div>
  )
}
