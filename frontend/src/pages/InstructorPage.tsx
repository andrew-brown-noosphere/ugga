import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  User,
  Mail,
  Phone,
  MapPin,
  Clock,
  Globe,
  FileText,
  Star,
  BookOpen,
  GraduationCap,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  ThumbsUp,
  UserPlus,
  UserCheck,
} from 'lucide-react'
import { getProfessor, getProfessorCourses, getProfessorSyllabi, claimProfile, likeInstructor, unlikeInstructor, getInstructorLikeStats, followInstructor, unfollowInstructor, getInstructorFollowStats, setAuthToken } from '../lib/api'
import { useAuth, SignInButton } from '@clerk/clerk-react'
import { clsx } from 'clsx'

export default function InstructorPage() {
  const { id } = useParams<{ id: string }>()
  const professorId = parseInt(id || '0')
  const { isSignedIn, getToken } = useAuth()
  const queryClient = useQueryClient()
  const [showClaimModal, setShowClaimModal] = useState(false)
  const [claimEmail, setClaimEmail] = useState('')
  const [claimError, setClaimError] = useState('')
  const [claimSuccess, setClaimSuccess] = useState('')
  const [claiming, setClaiming] = useState(false)

  const { data: professor, isLoading } = useQuery({
    queryKey: ['professor', professorId],
    queryFn: () => getProfessor(professorId),
    enabled: professorId > 0,
  })

  // Get like stats
  const { data: likeStats } = useQuery({
    queryKey: ['instructorLikeStats', professorId],
    queryFn: () => getInstructorLikeStats(professorId),
    enabled: professorId > 0,
  })

  // Like mutation
  const likeMutation = useMutation({
    mutationFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      if (likeStats?.user_has_liked) {
        return unlikeInstructor(professorId)
      }
      return likeInstructor(professorId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['instructorLikeStats', professorId] })
    },
  })

  // Get follow stats
  const { data: followStats } = useQuery({
    queryKey: ['instructorFollowStats', professorId],
    queryFn: () => getInstructorFollowStats(professorId),
    enabled: professorId > 0,
  })

  // Follow mutation
  const followMutation = useMutation({
    mutationFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      if (followStats?.is_following) {
        return unfollowInstructor(professorId)
      }
      return followInstructor(professorId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['instructorFollowStats', professorId] })
    },
  })

  const { data: courses } = useQuery({
    queryKey: ['professor-courses', professorId],
    queryFn: () => getProfessorCourses(professorId),
    enabled: professorId > 0,
  })

  const { data: syllabi } = useQuery({
    queryKey: ['professor-syllabi', professorId],
    queryFn: () => getProfessorSyllabi(professorId),
    enabled: professorId > 0,
  })

  const handleClaimSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setClaimError('')
    setClaimSuccess('')

    if (!claimEmail.toLowerCase().endsWith('@uga.edu')) {
      setClaimError('Email must be a @uga.edu address')
      return
    }

    setClaiming(true)
    try {
      const result = await claimProfile(professorId, claimEmail)
      setClaimSuccess(result.message)
      setShowClaimModal(false)
    } catch (err: any) {
      setClaimError(err.response?.data?.detail || 'Failed to submit claim')
    } finally {
      setClaiming(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="card animate-pulse">
          <div className="flex gap-6">
            <div className="w-32 h-32 bg-gray-200 rounded-lg" />
            <div className="flex-1 space-y-3">
              <div className="h-8 bg-gray-200 rounded w-1/3" />
              <div className="h-4 bg-gray-200 rounded w-1/4" />
              <div className="h-4 bg-gray-200 rounded w-1/2" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!professor) {
    return (
      <div className="card text-center py-12">
        <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500">Instructor not found</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="card">
        <div className="flex flex-col md:flex-row gap-6">
          {/* Photo */}
          <div className="flex-shrink-0">
            {professor.photo_url ? (
              <img
                src={professor.photo_url}
                alt={professor.name}
                className="w-32 h-32 rounded-lg object-cover"
              />
            ) : (
              <div className="w-32 h-32 rounded-lg bg-gray-100 flex items-center justify-center">
                <User className="h-16 w-16 text-gray-300" />
              </div>
            )}
          </div>

          {/* Info */}
          <div className="flex-1">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{professor.name}</h1>
                {professor.title && (
                  <p className="text-lg text-gray-600">{professor.title}</p>
                )}
                {professor.department_name && (
                  <p className="text-gray-500">{professor.department_name}</p>
                )}
              </div>

              <div className="flex items-start gap-4">
                {/* Like & Follow buttons */}
                <div className="flex items-center gap-2">
                  {isSignedIn ? (
                    <>
                      <button
                        onClick={() => likeMutation.mutate()}
                        disabled={likeMutation.isPending}
                        className={clsx(
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                          likeStats?.user_has_liked
                            ? 'bg-brand-100 text-brand-700 hover:bg-brand-200'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        )}
                      >
                        <ThumbsUp className={clsx('h-4 w-4', likeStats?.user_has_liked && 'fill-current')} />
                        {likeStats?.total_likes || 0}
                      </button>
                      <button
                        onClick={() => followMutation.mutate()}
                        disabled={followMutation.isPending}
                        className={clsx(
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                          followStats?.is_following
                            ? 'bg-brand-600 text-white hover:bg-brand-700'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        )}
                      >
                        {followStats?.is_following ? (
                          <>
                            <UserCheck className="h-4 w-4" />
                            Following
                          </>
                        ) : (
                          <>
                            <UserPlus className="h-4 w-4" />
                            Follow
                          </>
                        )}
                      </button>
                    </>
                  ) : (
                    <SignInButton mode="modal">
                      <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200">
                        <ThumbsUp className="h-4 w-4" />
                        {likeStats?.total_likes || 0}
                      </button>
                    </SignInButton>
                  )}
                </div>

                {/* RMP Rating */}
                {professor.rmp_rating && (
                  <div className="text-center">
                    <div className="flex items-center gap-1 text-lg font-semibold">
                      <Star className="h-5 w-5 text-yellow-400 fill-yellow-400" />
                      <span>{professor.rmp_rating.toFixed(1)}</span>
                    </div>
                    <p className="text-xs text-gray-500">
                      {professor.rmp_num_ratings} ratings
                    </p>
                    {professor.rmp_difficulty && (
                      <p className="text-xs text-gray-500">
                        {professor.rmp_difficulty.toFixed(1)} difficulty
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Contact Info */}
            <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-600">
              {professor.email && (
                <a
                  href={`mailto:${professor.email}`}
                  className="flex items-center gap-1 hover:text-brand-600"
                >
                  <Mail className="h-4 w-4" />
                  {professor.email}
                </a>
              )}
              {professor.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-4 w-4" />
                  {professor.phone}
                </span>
              )}
              {professor.office_location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-4 w-4" />
                  {professor.office_location}
                </span>
              )}
            </div>

            {/* Links */}
            <div className="mt-3 flex flex-wrap gap-3">
              {professor.profile_url && (
                <a
                  href={professor.profile_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-brand-600 hover:underline flex items-center gap-1"
                >
                  <ExternalLink className="h-3 w-3" />
                  Faculty Profile
                </a>
              )}
              {professor.personal_website && (
                <a
                  href={professor.personal_website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-brand-600 hover:underline flex items-center gap-1"
                >
                  <Globe className="h-3 w-3" />
                  Personal Website
                </a>
              )}
              {professor.cv_url && (
                <a
                  href={professor.cv_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-brand-600 hover:underline flex items-center gap-1"
                >
                  <FileText className="h-3 w-3" />
                  CV
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Claim Banner */}
        {!professor.is_claimed && (
          <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-medium text-blue-900">Is this your profile?</h3>
                <p className="text-sm text-blue-700 mt-1">
                  Claim this profile to add office hours, update your bio, and more.
                </p>
              </div>
              {isSignedIn ? (
                <button
                  onClick={() => setShowClaimModal(true)}
                  className="btn btn-primary"
                >
                  Claim Profile
                </button>
              ) : (
                <p className="text-sm text-blue-600">Sign in to claim</p>
              )}
            </div>

            {claimSuccess && (
              <div className="mt-3 p-3 bg-green-50 rounded border border-green-200 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <span className="text-sm text-green-700">{claimSuccess}</span>
              </div>
            )}
          </div>
        )}

        {professor.claim_status === 'pending' && (
          <div className="mt-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-yellow-600" />
              <span className="text-yellow-800">Profile claim pending review</span>
            </div>
          </div>
        )}
      </div>

      {/* Office Hours & Bio */}
      {(professor.office_hours || professor.bio) && (
        <div className="card">
          {professor.office_hours && (
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Clock className="h-5 w-5 text-brand-600" />
                Office Hours
              </h2>
              <p className="mt-2 text-gray-600">{professor.office_hours}</p>
            </div>
          )}

          {professor.bio && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <User className="h-5 w-5 text-brand-600" />
                About
              </h2>
              <p className="mt-2 text-gray-600 whitespace-pre-wrap">{professor.bio}</p>
            </div>
          )}
        </div>
      )}

      {/* Research Areas */}
      {professor.research_areas && professor.research_areas.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-brand-600" />
            Research Areas
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {professor.research_areas.map((area, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
              >
                {area}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Courses Taught */}
      {courses && courses.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-brand-600" />
            Courses Taught
          </h2>
          <div className="mt-4 grid gap-3">
            {courses.map((course) => (
              <Link
                key={course.course_code}
                to={`/courses?search=${encodeURIComponent(course.course_code)}`}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div>
                  <span className="font-medium text-gray-900">{course.course_code}</span>
                  {course.title && (
                    <span className="text-gray-600 ml-2">{course.title}</span>
                  )}
                </div>
                <div className="text-sm text-gray-500">
                  {course.times_taught}x
                  {course.semesters_taught && course.semesters_taught.length > 0 && (
                    <span className="ml-2">
                      (last: {course.semesters_taught[0]})
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Syllabi */}
      {syllabi && syllabi.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <FileText className="h-5 w-5 text-brand-600" />
            Available Syllabi
          </h2>
          <div className="mt-4 grid gap-2">
            {syllabi.map((syllabus) => (
              <div
                key={syllabus.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <FileText className="h-4 w-4 text-gray-400" />
                  <div>
                    <Link
                      to={`/courses?search=${encodeURIComponent(syllabus.course_code)}`}
                      className="font-medium text-brand-600 hover:text-brand-800 hover:underline"
                    >
                      {syllabus.course_code}
                    </Link>
                    {syllabus.course_title && (
                      <span className="text-gray-600 ml-2">{syllabus.course_title}</span>
                    )}
                    {syllabus.semester && (
                      <span className="text-gray-500 ml-2 text-sm">({syllabus.semester})</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {syllabus.syllabus_url ? (
                    <a
                      href={syllabus.syllabus_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary text-sm flex items-center gap-1"
                    >
                      View Syllabus
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : syllabus.has_content ? (
                    <span className="badge badge-success">Available</span>
                  ) : (
                    <span className="badge badge-secondary">No link</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Claim Modal */}
      {showClaimModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <h2 className="text-xl font-semibold text-gray-900">Claim This Profile</h2>
            <p className="text-gray-600 mt-2">
              Enter your UGA email address to claim this profile. We'll verify your identity before approving the claim.
            </p>

            <form onSubmit={handleClaimSubmit} className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                UGA Email Address
              </label>
              <input
                type="email"
                className="input"
                placeholder="yourname@uga.edu"
                value={claimEmail}
                onChange={(e) => setClaimEmail(e.target.value)}
                required
              />

              {claimError && (
                <p className="mt-2 text-sm text-red-600">{claimError}</p>
              )}

              <div className="mt-6 flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowClaimModal(false)}
                  className="btn btn-secondary flex-1"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={claiming}
                  className={clsx(
                    'btn btn-primary flex-1',
                    claiming && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {claiming ? 'Submitting...' : 'Submit Claim'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
