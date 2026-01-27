import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, Filter, ChevronDown, ChevronUp, Users, Clock, BookOpen, AlertCircle } from 'lucide-react'
import { getCourses, getCourse, getSubjects } from '../lib/api'
import type { Course, CourseFilters } from '../types'
import { clsx } from 'clsx'
import AuthGate from '../components/AuthGate'

const COURSES_FEATURES = [
  'Search 6,900+ courses by keyword, subject, or instructor',
  'See real-time seat availability and section details',
  'View course descriptions, prerequisites, and credit hours',
  'Find courses with open seats that fit your schedule',
]

export default function CoursesPage() {
  const [filters, setFilters] = useState<CourseFilters>({
    limit: 50,
  })
  const [showFilters, setShowFilters] = useState(false)
  const [expandedCourse, setExpandedCourse] = useState<number | null>(null)

  const { data: courses, isLoading } = useQuery({
    queryKey: ['courses', filters],
    queryFn: () => getCourses(filters),
  })

  const { data: subjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: getSubjects,
  })

  const handleSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    setFilters({
      ...filters,
      search: formData.get('search') as string,
    })
  }

  return (
    <AuthGate
      icon={BookOpen}
      title="Course Catalog"
      description="Search and explore thousands of UGA courses with real-time availability"
      features={COURSES_FEATURES}
    >
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Course Catalog</h1>
        <p className="text-gray-600">Search and filter courses for the current semester</p>
      </div>

      {/* Search and Filters */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              name="search"
              placeholder="Search by course name, code, or description..."
              className="input pl-10"
              defaultValue={filters.search}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Search
          </button>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            className="btn btn-secondary flex items-center"
          >
            <Filter className="h-4 w-4 mr-2" />
            Filters
            {showFilters ? (
              <ChevronUp className="h-4 w-4 ml-2" />
            ) : (
              <ChevronDown className="h-4 w-4 ml-2" />
            )}
          </button>
        </form>

        {/* Filter panel */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Subject
              </label>
              <select
                className="input"
                value={filters.subject || ''}
                onChange={(e) =>
                  setFilters({ ...filters, subject: e.target.value || undefined })
                }
              >
                <option value="">All Subjects</option>
                {subjects?.map((subject) => (
                  <option key={subject} value={subject}>
                    {subject}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Availability
              </label>
              <select
                className="input"
                value={
                  filters.has_availability === undefined
                    ? ''
                    : filters.has_availability
                    ? 'true'
                    : 'false'
                }
                onChange={(e) =>
                  setFilters({
                    ...filters,
                    has_availability:
                      e.target.value === '' ? undefined : e.target.value === 'true',
                  })
                }
              >
                <option value="">All</option>
                <option value="true">Has Open Seats</option>
                <option value="false">No Open Seats</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Instructor
              </label>
              <input
                type="text"
                className="input"
                placeholder="Search by instructor..."
                value={filters.instructor || ''}
                onChange={(e) =>
                  setFilters({ ...filters, instructor: e.target.value || undefined })
                }
              />
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      <div className="space-y-4">
        {isLoading ? (
          // Loading skeleton
          [...Array(5)].map((_, i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-1/3 mb-2" />
              <div className="h-4 bg-gray-200 rounded w-2/3" />
            </div>
          ))
        ) : courses?.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-gray-500">No courses found matching your criteria</p>
          </div>
        ) : (
          courses?.map((course) => (
            <CourseCard
              key={course.id}
              course={course}
              expanded={expandedCourse === course.id}
              onToggle={() =>
                setExpandedCourse(expandedCourse === course.id ? null : course.id)
              }
            />
          ))
        )}
      </div>

      {/* Load more */}
      {courses && courses.length >= (filters.limit || 50) && (
        <div className="text-center">
          <button
            onClick={() =>
              setFilters({ ...filters, limit: (filters.limit || 50) + 50 })
            }
            className="btn btn-secondary"
          >
            Load More
          </button>
        </div>
      )}
    </div>
    </AuthGate>
  )
}

function CourseCard({
  course,
  expanded,
  onToggle,
}: {
  course: Course
  expanded: boolean
  onToggle: () => void
}) {
  // Fetch full course details when expanded
  const { data: fullCourse, isLoading: loadingDetails } = useQuery({
    queryKey: ['course', course.course_code],
    queryFn: () => getCourse(course.course_code),
    enabled: expanded, // Only fetch when expanded
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  // Use full course data if available, otherwise fall back to list data
  const displayCourse = fullCourse || course

  return (
    <div className="card">
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold text-gray-900">
              {course.course_code}
            </h3>
            {course.has_availability ? (
              <span className="badge badge-success">Open</span>
            ) : (
              <span className="badge badge-danger">Full</span>
            )}
          </div>
          <p className="text-gray-700 mt-1">{course.title}</p>
          {course.department && (
            <p className="text-sm text-gray-500 mt-1">{course.department}</p>
          )}
        </div>

        <div className="flex items-center gap-4 text-sm text-gray-500">
          <div className="flex items-center">
            <Users className="h-4 w-4 mr-1" />
            {course.available_seats}/{course.total_seats}
          </div>
          <div className="flex items-center">
            <Clock className="h-4 w-4 mr-1" />
            {(course as any).section_count ?? course.sections?.length ?? 0} sections
          </div>
          {expanded ? (
            <ChevronUp className="h-5 w-5" />
          ) : (
            <ChevronDown className="h-5 w-5" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="mt-4 pt-4 border-t">
          {loadingDetails ? (
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-3/4" />
              <div className="h-4 bg-gray-200 rounded w-1/2" />
            </div>
          ) : (
            <>
              {/* Course Description */}
              {displayCourse.description && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <BookOpen className="h-4 w-4 text-brand-600" />
                    <span className="font-medium text-gray-900">Description</span>
                  </div>
                  <p className="text-gray-600 text-sm">{displayCourse.description}</p>
                </div>
              )}

              {/* Prerequisites */}
              {displayCourse.prerequisites && (
                <div className="mb-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-amber-600" />
                    <span className="font-medium text-amber-800">Prerequisites</span>
                  </div>
                  <p className="text-amber-700 text-sm mt-1">{displayCourse.prerequisites}</p>
                </div>
              )}

              {/* Sections table */}
              {displayCourse.sections && displayCourse.sections.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="pb-2 font-medium">CRN</th>
                        <th className="pb-2 font-medium">Section</th>
                        <th className="pb-2 font-medium">Instructor</th>
                        <th className="pb-2 font-medium">Credits</th>
                        <th className="pb-2 font-medium">Seats</th>
                        <th className="pb-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {displayCourse.sections.map((section) => (
                        <tr key={section.id} className="border-b last:border-0">
                          <td className="py-2 font-mono">{section.crn}</td>
                          <td className="py-2">{section.section_code || '-'}</td>
                          <td className="py-2">
                            {section.instructor ? (
                              <Link
                                to={`/instructors?search=${encodeURIComponent(section.instructor)}`}
                                className="text-brand-600 hover:text-brand-800 hover:underline"
                              >
                                {section.instructor}
                              </Link>
                            ) : (
                              <span className="text-gray-400">TBD</span>
                            )}
                          </td>
                          <td className="py-2">{section.credit_hours}</td>
                          <td className="py-2">
                            <span
                              className={clsx(
                                section.seats_available > 0
                                  ? 'text-green-600'
                                  : 'text-red-600'
                              )}
                            >
                              {section.seats_available}/{section.class_size}
                            </span>
                            {section.waitlist_count > 0 && (
                              <span className="text-gray-400 ml-1">
                                (+{section.waitlist_count} waitlist)
                              </span>
                            )}
                          </td>
                          <td className="py-2">
                            {section.is_available ? (
                              <span className="badge badge-success">Open</span>
                            ) : section.status === 'X' ? (
                              <span className="badge badge-danger">Cancelled</span>
                            ) : (
                              <span className="badge badge-warning">Full</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
