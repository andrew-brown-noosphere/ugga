import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import {
  Users,
  Plus,
  MapPin,
  Clock,
  Calendar,
  User,
  ChevronRight,
  X,
  Search,
  BookOpen,
  Users2,
} from 'lucide-react'
import {
  getStudyGroups,
  createStudyGroup,
  joinStudyGroup,
  leaveStudyGroup,
  getCurrentUser,
  setAuthToken,
} from '../lib/api'
import type { StudyGroup, StudyGroupCreateRequest } from '../types'
import { clsx } from 'clsx'
import AuthGate from '../components/AuthGate'

const STUDY_GROUPS_FEATURES = [
  'Find study groups for any of your courses',
  'Claim and organize groups with meeting times and locations',
  'Connect with classmates preparing for exams',
  'Coordinate study sessions and share resources',
]

const MEETING_DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

export default function StudyGroupsPage() {
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [courseFilter, setCourseFilter] = useState('')
  const [selectedGroup, setSelectedGroup] = useState<StudyGroup | null>(null)

  // Create form state
  const [formData, setFormData] = useState<StudyGroupCreateRequest>({
    course_code: '',
    name: '',
    description: '',
    meeting_day: '',
    meeting_time: '',
    meeting_location: '',
    max_members: 10,
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

  const { data: studyGroups, isLoading } = useQuery({
    queryKey: ['studyGroups', courseFilter],
    queryFn: async () => {
      if (isSignedIn) {
        const token = await getToken()
        setAuthToken(token)
      }
      return getStudyGroups({
        course_code: courseFilter || undefined,
        active_only: true,
      })
    },
  })

  const createMutation = useMutation({
    mutationFn: createStudyGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studyGroups'] })
      setShowCreateModal(false)
      setFormData({
        course_code: '',
        name: '',
        description: '',
        meeting_day: '',
        meeting_time: '',
        meeting_location: '',
        max_members: 10,
      })
    },
  })

  const joinMutation = useMutation({
    mutationFn: (groupId: number) => joinStudyGroup(groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studyGroups'] })
    },
  })

  const leaveMutation = useMutation({
    mutationFn: (groupId: number) => leaveStudyGroup(groupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['studyGroups'] })
    },
  })

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
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
      icon={Users2}
      title="Study Groups"
      description="Connect with classmates and study together"
      features={STUDY_GROUPS_FEATURES}
    >
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Study Groups</h1>
          <p className="text-gray-600">Find or create study groups for your courses</p>
        </div>
        {isVerified && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Create Group
          </button>
        )}
      </div>

      {/* Search/Filter */}
      <div className="card">
        <div className="flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Filter by course code (e.g., CSCI 1302)"
              value={courseFilter}
              onChange={(e) => setCourseFilter(e.target.value)}
              className="input pl-10"
            />
          </div>
          {courseFilter && (
            <button
              onClick={() => setCourseFilter('')}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Not verified */}
      {!isVerified && (
        <div className="card bg-amber-50 border-amber-200">
          <div className="flex items-start gap-3">
            <Users className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Verify your UGA email</p>
              <p className="text-sm text-amber-700 mt-1">
                You need to verify your @uga.edu email to create or join study groups.
              </p>
              <a href="/profile" className="btn btn-secondary mt-3 inline-block">
                Go to Profile
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Study Groups List */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-2/3 mb-2" />
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-4" />
              <div className="h-4 bg-gray-200 rounded w-full" />
            </div>
          ))}
        </div>
      ) : studyGroups && studyGroups.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {studyGroups.map((group) => (
            <div
              key={group.id}
              className="card hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setSelectedGroup(group)}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 bg-brand-100 text-brand-700 rounded-full">
                      {group.course_code}
                    </span>
                    {group.is_member && (
                      <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                        Joined
                      </span>
                    )}
                    {group.is_organizer && (
                      <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">
                        Organizer
                      </span>
                    )}
                  </div>
                  <h3 className="font-semibold text-gray-900">{group.name}</h3>
                </div>
                <ChevronRight className="h-5 w-5 text-gray-400" />
              </div>

              {group.description && (
                <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                  {group.description}
                </p>
              )}

              <div className="flex flex-wrap gap-4 mt-4 text-sm text-gray-500">
                {group.meeting_day && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    {group.meeting_day}
                  </span>
                )}
                {group.meeting_time && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {group.meeting_time}
                  </span>
                )}
                {group.meeting_location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    {group.meeting_location}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                <span className="flex items-center gap-1 text-sm text-gray-500">
                  <Users className="h-4 w-4" />
                  {group.member_count} / {group.max_members} members
                </span>
                <span className="text-xs text-gray-400">
                  by {group.organizer_first_name || group.organizer_username}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <BookOpen className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No study groups found</h3>
          <p className="text-gray-600">
            {courseFilter
              ? `No active study groups for "${courseFilter}". Be the first to create one!`
              : 'No active study groups yet. Create one to get started!'}
          </p>
        </div>
      )}

      {/* Group Detail Modal */}
      {selectedGroup && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <span className="text-xs px-2 py-0.5 bg-brand-100 text-brand-700 rounded-full">
                    {selectedGroup.course_code}
                  </span>
                  <h2 className="text-xl font-bold text-gray-900 mt-2">
                    {selectedGroup.name}
                  </h2>
                </div>
                <button
                  onClick={() => setSelectedGroup(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>

              {selectedGroup.description && (
                <p className="text-gray-600 mb-6">{selectedGroup.description}</p>
              )}

              <div className="space-y-3 mb-6">
                {selectedGroup.meeting_day && (
                  <div className="flex items-center gap-3 text-gray-700">
                    <Calendar className="h-5 w-5 text-gray-400" />
                    <span>{selectedGroup.meeting_day}</span>
                  </div>
                )}
                {selectedGroup.meeting_time && (
                  <div className="flex items-center gap-3 text-gray-700">
                    <Clock className="h-5 w-5 text-gray-400" />
                    <span>{selectedGroup.meeting_time}</span>
                  </div>
                )}
                {selectedGroup.meeting_location && (
                  <div className="flex items-center gap-3 text-gray-700">
                    <MapPin className="h-5 w-5 text-gray-400" />
                    <span>{selectedGroup.meeting_location}</span>
                  </div>
                )}
                <div className="flex items-center gap-3 text-gray-700">
                  <Users className="h-5 w-5 text-gray-400" />
                  <span>
                    {selectedGroup.member_count} / {selectedGroup.max_members} members
                  </span>
                </div>
                <div className="flex items-center gap-3 text-gray-700">
                  <User className="h-5 w-5 text-gray-400" />
                  <span>
                    Organized by {selectedGroup.organizer_first_name || selectedGroup.organizer_username}
                  </span>
                </div>
              </div>

              {isVerified && (
                <div className="flex gap-3">
                  {selectedGroup.is_member ? (
                    <>
                      {!selectedGroup.is_organizer && (
                        <button
                          onClick={() => {
                            leaveMutation.mutate(selectedGroup.id)
                            setSelectedGroup(null)
                          }}
                          disabled={leaveMutation.isPending}
                          className="btn btn-secondary flex-1"
                        >
                          {leaveMutation.isPending ? 'Leaving...' : 'Leave Group'}
                        </button>
                      )}
                      {selectedGroup.is_organizer && (
                        <button className="btn btn-secondary flex-1" disabled>
                          You&apos;re the organizer
                        </button>
                      )}
                    </>
                  ) : selectedGroup.member_count < selectedGroup.max_members ? (
                    <button
                      onClick={() => {
                        joinMutation.mutate(selectedGroup.id)
                        setSelectedGroup(null)
                      }}
                      disabled={joinMutation.isPending}
                      className="btn btn-primary flex-1"
                    >
                      {joinMutation.isPending ? 'Joining...' : 'Join Group'}
                    </button>
                  ) : (
                    <button className="btn btn-secondary flex-1" disabled>
                      Group is full
                    </button>
                  )}
                </div>
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
                <h2 className="text-xl font-bold text-gray-900">Create Study Group</h2>
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
                    Course Code *
                  </label>
                  <input
                    type="text"
                    required
                    className="input"
                    placeholder="e.g., CSCI 1302"
                    value={formData.course_code}
                    onChange={(e) =>
                      setFormData({ ...formData, course_code: e.target.value })
                    }
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Group Name *
                  </label>
                  <input
                    type="text"
                    required
                    className="input"
                    placeholder="e.g., Monday Night Study Crew"
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
                    placeholder="What's the focus of this study group?"
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({ ...formData, description: e.target.value })
                    }
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Meeting Day
                    </label>
                    <select
                      className="input"
                      value={formData.meeting_day}
                      onChange={(e) =>
                        setFormData({ ...formData, meeting_day: e.target.value })
                      }
                    >
                      <option value="">Select day</option>
                      {MEETING_DAYS.map((day) => (
                        <option key={day} value={day}>
                          {day}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Meeting Time
                    </label>
                    <input
                      type="text"
                      className="input"
                      placeholder="e.g., 7:00 PM"
                      value={formData.meeting_time}
                      onChange={(e) =>
                        setFormData({ ...formData, meeting_time: e.target.value })
                      }
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Meeting Location
                  </label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g., MLC Room 123, Science Library 2nd floor"
                    value={formData.meeting_location}
                    onChange={(e) =>
                      setFormData({ ...formData, meeting_location: e.target.value })
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
                    max={50}
                    value={formData.max_members}
                    onChange={(e) =>
                      setFormData({ ...formData, max_members: parseInt(e.target.value) })
                    }
                  />
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
                  {createMutation.isPending ? 'Creating...' : 'Create Group'}
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
