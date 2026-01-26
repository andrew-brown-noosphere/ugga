import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth, useUser, SignInButton } from '@clerk/clerk-react'
import {
  GraduationCap,
  BookOpen,
  ChevronDown,
  AlertTriangle,
  Settings,
  Target,
  Zap,
  Compass,
  Clock,
  Users,
  FileText,
  ExternalLink,
  Calendar,
  List,
  TrendingUp,
  Sparkles,
  MessageCircle,
  CheckCircle2,
  MapPin,
  AlertCircle,
  ArrowRight,
  Plus,
} from 'lucide-react'
import { usePlan } from '../context/PlanContext'
import {
  getProgramByMajor,
  getEnrichedProgram,
  getCoursePossibilities,
  getCompletedCourses,
  getQuickProgress,
  setAuthToken,
} from '../lib/api'
import type { EnrichedCourseInfo, EnrichedRequirement } from '../types'
import { clsx } from 'clsx'
import WeeklyCalendar from '../components/WeeklyCalendar'
import CourseEntryModal from '../components/CourseEntryModal'

const GOAL_INFO: Record<string, { title: string; icon: React.ElementType; description: string; color: string }> = {
  'fast-track': {
    title: 'Fast Track',
    icon: Zap,
    description: 'Shortest path to graduation',
    color: 'from-amber-500 to-orange-500',
  },
  'specialist': {
    title: 'Specialist',
    icon: Target,
    description: 'Deep expertise focus',
    color: 'from-purple-500 to-indigo-500',
  },
  'well-rounded': {
    title: 'Explorer',
    icon: Compass,
    description: 'Broad knowledge base',
    color: 'from-emerald-500 to-teal-500',
  },
  'flexible': {
    title: 'Flexible',
    icon: BookOpen,
    description: 'Keeping options open',
    color: 'from-blue-500 to-cyan-500',
  },
  'minimal': {
    title: 'Minimal Effort',
    icon: Clock,
    description: 'Path of least resistance',
    color: 'from-pink-500 to-rose-500',
  },
}

// Progress Ring Component
function ProgressRing({ progress, size = 120, strokeWidth = 8 }: { progress: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const offset = circumference - (progress / 100) * circumference

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          stroke="currentColor"
          fill="none"
          className="text-gray-200"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          stroke="url(#progressGradient)"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
        <defs>
          <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ba0c2f" />
            <stop offset="100%" stopColor="#e63946" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-gray-900">{Math.round(progress)}%</span>
        <span className="text-xs text-gray-500">Complete</span>
      </div>
    </div>
  )
}

// Insight Card Component
function InsightCard({
  icon: Icon,
  title,
  description,
  action,
  variant = 'default'
}: {
  icon: React.ElementType
  title: string
  description: string
  action?: { label: string; onClick: () => void }
  variant?: 'default' | 'warning' | 'success'
}) {
  const variants = {
    default: 'bg-white border-gray-200',
    warning: 'bg-amber-50 border-amber-200',
    success: 'bg-emerald-50 border-emerald-200',
  }
  const iconVariants = {
    default: 'bg-brand-100 text-brand-600',
    warning: 'bg-amber-100 text-amber-600',
    success: 'bg-emerald-100 text-emerald-600',
  }

  return (
    <div className={clsx('rounded-xl border p-4 transition-all hover:shadow-md', variants[variant])}>
      <div className="flex items-start gap-3">
        <div className={clsx('p-2 rounded-lg', iconVariants[variant])}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-gray-900 text-sm">{title}</h4>
          <p className="text-xs text-gray-600 mt-0.5">{description}</p>
          {action && (
            <button
              onClick={action.onClick}
              className="text-xs text-brand-600 font-medium mt-2 hover:text-brand-700 flex items-center gap-1"
            >
              {action.label} <ArrowRight className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// Course Quick Card - supports both EnrichedCourseInfo and CoursePossibility
type CourseCardData = {
  course_code: string
  title: string | null
  available_seats: number
  total_sections: number
  total_seats: number
  // Optional schedule info (different structure for each type)
  instructors?: Array<{ days?: string | null; start_time?: string | null; building?: string | null }>
  sections?: Array<{ days?: string | null; start_time?: string | null; building?: string | null }>
  // Possibility-specific
  priority_reason?: string
}

function CourseQuickCard({ course, showSchedule = false }: { course: CourseCardData; showSchedule?: boolean }) {
  const hasSeats = course.available_seats > 0
  const isOffered = course.total_sections > 0
  const fillRate = isOffered ? Math.round(((course.total_seats - course.available_seats) / course.total_seats) * 100) : 0
  const isFillingFast = fillRate > 80 && hasSeats

  // Get schedule info from either instructors or sections
  const scheduleInfo = course.instructors?.[0] || course.sections?.[0]

  return (
    <div className={clsx(
      'group rounded-lg border p-3 transition-all hover:shadow-md cursor-pointer',
      hasSeats ? 'bg-white border-gray-200 hover:border-brand-300' :
      isOffered ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'
    )}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-gray-900">{course.course_code}</span>
            {isFillingFast && (
              <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-medium flex items-center gap-0.5">
                <TrendingUp className="h-2.5 w-2.5" /> {fillRate}% full
              </span>
            )}
          </div>
          <p className="text-xs text-gray-600 truncate mt-0.5">{course.title}</p>

          {showSchedule && scheduleInfo?.days && (
            <div className="flex items-center gap-1 mt-1.5 text-[10px] text-gray-500">
              <Clock className="h-3 w-3" />
              <span>{scheduleInfo.days} {scheduleInfo.start_time}</span>
              {scheduleInfo.building && (
                <>
                  <MapPin className="h-3 w-3 ml-1" />
                  <span>{scheduleInfo.building}</span>
                </>
              )}
            </div>
          )}

          {course.priority_reason && (
            <p className="text-[10px] text-brand-600 mt-1">{course.priority_reason}</p>
          )}
        </div>

        <div className="text-right flex-shrink-0">
          {hasSeats ? (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
              {course.available_seats} seats
            </span>
          ) : isOffered ? (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
              Full
            </span>
          ) : (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
              Not offered
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// Generate semesters starting from current
function generateSemesters(startYear: number, startSemester: 'Spring' | 'Summer' | 'Fall', count: number) {
  const semesters: Array<{ label: string; key: string }> = []
  let year = startYear
  let sem = startSemester
  const order: Array<'Spring' | 'Summer' | 'Fall'> = ['Spring', 'Summer', 'Fall']
  let idx = order.indexOf(sem)

  for (let i = 0; i < count; i++) {
    const shortYear = year.toString().slice(-2)
    const shortSem = sem === 'Spring' ? 'Spr' : sem === 'Summer' ? 'Sum' : 'Fall'
    semesters.push({ label: `${shortSem} ${shortYear}`, key: `${sem}-${year}` })

    idx++
    if (idx >= order.length) {
      idx = 0
      year++
    }
    sem = order[idx]
  }
  return semesters
}

// Get current semester based on date
function getCurrentSemester(): { year: number; semester: 'Spring' | 'Summer' | 'Fall' } {
  const now = new Date()
  const month = now.getMonth() + 1 // 1-12
  const year = now.getFullYear()

  if (month >= 1 && month <= 5) return { year, semester: 'Spring' }
  if (month >= 6 && month <= 7) return { year, semester: 'Summer' }
  return { year, semester: 'Fall' }
}

// Semester Timeline Item
function SemesterBlock({
  semester,
  hours,
  isComplete = false,
  isCurrent = false
}: {
  semester: string
  hours: number
  isComplete?: boolean
  isCurrent?: boolean
}) {
  // Size based on hours: min 32px, max 48px
  const size = Math.max(32, Math.min(48, 24 + hours * 1.5))

  return (
    <div className="flex flex-col items-center">
      <div
        className={clsx(
          'rounded-full flex items-center justify-center text-sm font-medium transition-all',
          isComplete ? 'bg-emerald-500 text-white' :
          isCurrent ? 'bg-brand-600 text-white ring-4 ring-brand-200' :
          'bg-gray-200 text-gray-600'
        )}
        style={{ width: size, height: size }}
      >
        {isComplete ? <CheckCircle2 className="h-5 w-5" /> : hours}
      </div>
      <span className={clsx(
        'text-[10px] mt-1 font-medium',
        isCurrent ? 'text-brand-600' : 'text-gray-500'
      )}>
        {semester}
      </span>
    </div>
  )
}

function CourseDetailCard({ course }: { course: EnrichedCourseInfo }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors text-left"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <span className="font-mono text-sm font-semibold text-gray-900">
            {course.course_code}
          </span>
          <span className="text-sm text-gray-600 truncate">{course.title}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500 flex-shrink-0 ml-2">
          {course.instructors.length > 0 && (
            <span className="flex items-center gap-1" title="Current instructors">
              <Users className="h-3.5 w-3.5" />
              {course.instructors.length}
            </span>
          )}
          {course.syllabi.length > 0 && (
            <span className="flex items-center gap-1" title="Available syllabi">
              <FileText className="h-3.5 w-3.5" />
              {course.syllabi.length}
            </span>
          )}
          {course.available_seats > 0 ? (
            <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
              {course.available_seats} seats
            </span>
          ) : course.total_sections > 0 ? (
            <span className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
              Full
            </span>
          ) : (
            <span className="px-2 py-1 bg-gray-100 text-gray-500 rounded-full text-xs font-medium">
              Not offered
            </span>
          )}
          <ChevronDown className={clsx('h-4 w-4 text-gray-400 transition-transform', expanded && 'rotate-180')} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 py-4 bg-gray-50 border-t border-gray-100 space-y-4">
          {course.description && (
            <p className="text-sm text-gray-700">{course.description}</p>
          )}

          {course.prerequisites && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <div className="flex items-center gap-2 text-amber-700 text-xs font-medium mb-1">
                <AlertTriangle className="h-3.5 w-3.5" />
                Prerequisites
              </div>
              <p className="text-sm text-amber-800">{course.prerequisites}</p>
            </div>
          )}

          {course.instructors.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                This Semester ({course.total_sections} section{course.total_sections !== 1 ? 's' : ''})
              </h4>
              <div className="grid gap-2">
                {course.instructors.slice(0, 5).map((instructor, i) => (
                  <Link
                    key={i}
                    to={`/instructors?search=${encodeURIComponent(instructor.name)}`}
                    className={clsx(
                      'flex items-center justify-between p-2 rounded-lg transition-colors',
                      instructor.is_available
                        ? 'bg-white border border-emerald-200 hover:border-emerald-300'
                        : 'bg-white border border-gray-200 hover:border-gray-300'
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <div className={clsx(
                        'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium',
                        instructor.is_available ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'
                      )}>
                        {instructor.name.charAt(0)}
                      </div>
                      <div>
                        <span className="text-sm font-medium text-gray-900">{instructor.name}</span>
                        {instructor.days && (
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>{instructor.days} {instructor.start_time}-{instructor.end_time}</span>
                            {instructor.building && (
                              <span className="flex items-center gap-0.5">
                                <MapPin className="h-3 w-3" />
                                {instructor.building} {instructor.room}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    <span className={clsx(
                      'text-xs font-medium',
                      instructor.is_available ? 'text-emerald-600' : 'text-gray-500'
                    )}>
                      {instructor.seats_available}/{instructor.class_size}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {course.syllabi.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                Syllabi
              </h4>
              <div className="flex flex-wrap gap-2">
                {course.syllabi.map((syllabus) => (
                  syllabus.syllabus_url ? (
                    <a
                      key={syllabus.id}
                      href={syllabus.syllabus_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm text-brand-600 hover:border-brand-300 hover:bg-brand-50 transition-colors"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      {syllabus.semester || 'View'}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null
                ))}
              </div>
            </div>
          )}

          {course.bulletin_url && (
            <a
              href={course.bulletin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700"
            >
              View in UGA Bulletin <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}
    </div>
  )
}

export default function PlanPage() {
  const navigate = useNavigate()
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const { user } = useUser()
  const { plan, clearPlan, hasPlan } = usePlan()
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['major']))
  const [viewMode, setViewMode] = useState<'overview' | 'list' | 'calendar'>('overview')
  const [showCourseEntry, setShowCourseEntry] = useState(false)

  useEffect(() => {
    if (isLoaded && isSignedIn && !hasPlan) {
      navigate('/')
    }
  }, [hasPlan, navigate, isLoaded, isSignedIn])

  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  // Progress data queries
  const { data: quickProgress } = useQuery({
    queryKey: ['quickProgress'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getQuickProgress()
    },
    enabled: isSignedIn,
  })

  const { data: completedCourses } = useQuery({
    queryKey: ['completedCourses'],
    queryFn: async () => {
      const token = await getToken()
      setAuthToken(token)
      return getCompletedCourses()
    },
    enabled: isSignedIn,
  })

  const { data: basicProgram } = useQuery({
    queryKey: ['program', plan?.major],
    queryFn: () => (plan?.major ? getProgramByMajor(plan.major) : Promise.resolve(null)),
    enabled: !!plan?.major,
  })

  const { data: program } = useQuery({
    queryKey: ['enriched-program', basicProgram?.id],
    queryFn: () => (basicProgram?.id ? getEnrichedProgram(basicProgram.id) : Promise.resolve(null)),
    enabled: !!basicProgram?.id,
  })

  // Get completed course codes for prerequisite checking
  const completedCourseCodes = useMemo(() => {
    return completedCourses?.courses.map(c => c.course_code) || []
  }, [completedCourses])

  // Get filtered possibilities based on goal and prerequisites
  const { data: possibilities } = useQuery({
    queryKey: ['possibilities', basicProgram?.id, plan?.goal, completedCourseCodes],
    queryFn: () => (basicProgram?.id
      ? getCoursePossibilities(basicProgram.id, {
          goal: plan?.goal || 'flexible',
          completed: completedCourseCodes,
          limit: 100,
        })
      : Promise.resolve(null)),
    enabled: !!basicProgram?.id,
  })

  // CONDITIONAL RETURNS - after all hooks
  // Show loading
  if (!isLoaded) {
    return (
      <div className="space-y-6">
        <div className="h-48 bg-gradient-to-r from-gray-200 to-gray-300 rounded-2xl animate-pulse" />
        <div className="grid md:grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="h-32 bg-gray-200 rounded-xl animate-pulse" />)}
        </div>
      </div>
    )
  }

  // Sign-in prompt
  if (!isSignedIn) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
        <div className="w-20 h-20 bg-gradient-to-br from-brand-500 to-brand-700 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
          <GraduationCap className="h-10 w-10 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-3">Your Degree Roadmap</h1>
        <p className="text-gray-600 mb-8 max-w-md">
          Get a personalized plan to graduation with real-time course availability,
          smart scheduling, and AI-powered recommendations.
        </p>
        <SignInButton mode="modal">
          <button className="btn btn-primary text-lg px-8 py-3 shadow-lg hover:shadow-xl transition-shadow">
            Sign In to Get Started
          </button>
        </SignInButton>

        <div className="grid md:grid-cols-3 gap-6 mt-16 w-full max-w-3xl">
          {[
            { icon: Target, title: 'Smart Planning', desc: 'AI suggests your optimal course path' },
            { icon: Calendar, title: 'Live Schedule', desc: 'Real-time seat availability' },
            { icon: Sparkles, title: 'Insights', desc: 'Know which courses fill fast' },
          ].map((item, i) => (
            <div key={i} className="text-center">
              <div className="w-12 h-12 bg-brand-100 rounded-xl flex items-center justify-center mx-auto mb-3">
                <item.icon className="h-6 w-6 text-brand-600" />
              </div>
              <h3 className="font-semibold text-gray-900">{item.title}</h3>
              <p className="text-sm text-gray-500">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!plan) return null

  const goalInfo = GOAL_INFO[plan.goal] || GOAL_INFO['flexible']
  const GoalIcon = goalInfo.icon

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev)
      next.has(category) ? next.delete(category) : next.add(category)
      return next
    })
  }

  // Calculate statistics from possibilities (filtered courses)
  const possibilitiesList = possibilities?.possibilities || []
  const coursesFilling = possibilitiesList.filter(c => {
    if (c.total_seats === 0) return false
    const fillRate = (c.total_seats - c.available_seats) / c.total_seats
    return fillRate > 0.8 && c.available_seats > 0
  })
  const totalHours = program?.total_hours || 120
  const completedHours = quickProgress?.total_hours_earned || 0
  const progressPercent = quickProgress?.progress_percent || (completedHours / totalHours) * 100

  // Group requirements by category
  const requirementsByCategory = program?.requirements?.reduce(
    (acc, req) => {
      const cat = req.category || 'other'
      if (!acc[cat]) acc[cat] = []
      acc[cat].push(req)
      return acc
    },
    {} as Record<string, EnrichedRequirement[]>
  ) || {}

  const categoryLabels: Record<string, string> = {
    foundation: 'Foundation',
    major: 'Major Requirements',
    core: 'Core Courses',
    elective: 'Electives',
    gen_ed: 'General Education',
    other: 'Other',
  }
  const categoryOrder = ['major', 'core', 'foundation', 'gen_ed', 'elective', 'other']

  // Schedule blocks for calendar - now uses filtered possibilities
  const scheduleBlocks = useMemo(() => {
    if (!possibilities?.possibilities) return []
    const blocks: Array<{
      id: string; courseCode: string; title?: string; instructor: string;
      days: string; startTime: string; endTime: string;
      building?: string | null; room?: string | null; campus?: string | null;
      seatsAvailable: number; classSize: number; isAvailable: boolean;
    }> = []

    possibilities.possibilities.forEach(course => {
      course.sections.forEach(section => {
        if (!section.days || !section.start_time || !section.end_time || section.days === 'TBA') return
        blocks.push({
          id: `${course.course_code}-${section.crn}`,
          courseCode: course.course_code,
          title: course.title || undefined,
          instructor: section.instructor || 'TBD',
          days: section.days,
          startTime: section.start_time,
          endTime: section.end_time,
          building: section.building,
          room: section.room,
          campus: null,
          seatsAvailable: section.seats_available,
          classSize: section.class_size,
          isAvailable: section.seats_available > 0,
        })
      })
    })
    return blocks
  }, [possibilities])

  return (
    <div className="space-y-6 pb-8">
      {/* Hero Header */}
      <div className="relative overflow-hidden bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-8 text-white">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }} />
        </div>

        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex-1">
            <div className={clsx(
              'inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium mb-4',
              'bg-gradient-to-r', goalInfo.color, 'text-white'
            )}>
              <GoalIcon className="h-4 w-4" />
              {goalInfo.title} Track
            </div>

            {user?.firstName && (
              <p className="text-gray-400 text-lg mb-1">
                Hey {user.firstName}, here's your path to
              </p>
            )}
            <h1 className="text-3xl md:text-4xl font-bold mb-2">
              {program?.degree_type || 'BS'} in {plan.major}
            </h1>
            <p className="text-gray-400">
              {program?.college_code === 'ARTS' ? 'Franklin College of Arts & Sciences' :
               program?.college_code === 'ENG' ? 'College of Engineering' :
               program?.college_code === 'BUS' ? 'Terry College of Business' :
               'University of Georgia'}
            </p>

            <div className="flex flex-wrap gap-4 mt-6">
              <div className="bg-white/10 backdrop-blur rounded-lg px-4 py-2">
                <div className="text-2xl font-bold">{completedHours}/{totalHours}</div>
                <div className="text-xs text-gray-400">Hours Earned</div>
              </div>
              {quickProgress?.cumulative_gpa && (
                <div className="bg-white/10 backdrop-blur rounded-lg px-4 py-2">
                  <div className="text-2xl font-bold">{quickProgress.cumulative_gpa.toFixed(2)}</div>
                  <div className="text-xs text-gray-400">GPA</div>
                </div>
              )}
              <div className="bg-white/10 backdrop-blur rounded-lg px-4 py-2">
                <div className="text-2xl font-bold text-emerald-400">{possibilities?.total_eligible || 0}</div>
                <div className="text-xs text-gray-400">Your Options</div>
              </div>
              <button
                onClick={() => setShowCourseEntry(true)}
                className="bg-white/20 hover:bg-white/30 backdrop-blur rounded-lg px-4 py-2 flex items-center gap-2 transition-colors"
              >
                <Plus className="h-5 w-5" />
                <div className="text-left">
                  <div className="text-sm font-medium">Add Courses</div>
                  <div className="text-xs text-gray-300">Track your progress</div>
                </div>
              </button>
            </div>
          </div>

          <div className="flex flex-col items-center">
            <ProgressRing progress={progressPercent || 5} size={140} strokeWidth={10} />
            <p className="text-sm text-gray-400 mt-2">Degree Progress</p>
          </div>
        </div>

        <button
          onClick={() => { clearPlan(); navigate('/') }}
          className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors"
        >
          <Settings className="h-5 w-5" />
        </button>
      </div>

      {/* Smart Insights */}
      <div className="grid md:grid-cols-3 gap-4">
        {coursesFilling.length > 0 && (
          <InsightCard
            icon={TrendingUp}
            title={`${coursesFilling.length} Courses Filling Fast`}
            description={`${coursesFilling.slice(0, 2).map(c => c.course_code).join(', ')} are over 80% full`}
            variant="warning"
            action={{ label: 'View all', onClick: () => setViewMode('list') }}
          />
        )}
        <InsightCard
          icon={Sparkles}
          title="Ask AI Assistant"
          description="Get personalized course guidance"
          action={{ label: 'Start chat', onClick: () => navigate('/chat') }}
        />
        <InsightCard
          icon={Calendar}
          title={`${scheduleBlocks.length} Scheduled Sections`}
          description="View all available times in calendar"
          variant="success"
          action={{ label: 'Open calendar', onClick: () => setViewMode('calendar') }}
        />
      </div>

      {/* Semester Timeline */}
      <div className="card">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Clock className="h-5 w-5 text-brand-600" />
          Your Path to Graduation
        </h3>
        {(() => {
          const current = getCurrentSemester()
          const remainingHours = totalHours - completedHours
          const hoursPerSemester = 15
          const semestersNeeded = Math.ceil(remainingHours / hoursPerSemester)
          const semesters = generateSemesters(current.year, current.semester, Math.min(semestersNeeded + 1, 10))
          const graduationSem = semesters[semesters.length - 1]

          return (
            <>
              <div className="flex items-center justify-between overflow-x-auto pb-2">
                <div className="flex items-center gap-2 min-w-max">
                  {semesters.map((sem, i) => {
                    const isLast = i === semesters.length - 1
                    const semHours = isLast
                      ? remainingHours - (hoursPerSemester * (semesters.length - 1))
                      : hoursPerSemester
                    return (
                      <div key={sem.key} className="flex items-center">
                        <SemesterBlock
                          semester={sem.label}
                          hours={Math.max(0, Math.min(18, semHours))}
                          isComplete={false}
                          isCurrent={i === 0}
                        />
                        {i < semesters.length - 1 && <div className="w-8 h-0.5 bg-gray-200 mx-1" />}
                      </div>
                    )
                  })}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Estimated graduation: {graduationSem?.label} at {hoursPerSemester} credits/semester
              </p>
            </>
          )
        })()}
      </div>

      {/* View Toggle */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          {viewMode === 'overview' ? 'Course Overview' :
           viewMode === 'calendar' ? 'Weekly Schedule' : 'All Requirements'}
        </h2>
        <div className="flex rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm">
          {(['overview', 'list', 'calendar'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={clsx(
                'px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5',
                viewMode === mode
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-600 hover:bg-gray-50',
                mode !== 'overview' && 'border-l border-gray-200'
              )}
            >
              {mode === 'overview' && <Sparkles className="h-4 w-4" />}
              {mode === 'list' && <List className="h-4 w-4" />}
              {mode === 'calendar' && <Calendar className="h-4 w-4" />}
              <span className="hidden sm:inline capitalize">{mode}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Overview Mode */}
      {viewMode === 'overview' && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Your Options This Semester */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                Your Options This Semester
              </h3>
              <span className="text-sm text-gray-500">{possibilitiesList.length} courses</span>
            </div>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {possibilitiesList.slice(0, 8).map((course, i) => (
                <CourseQuickCard key={`${course.course_code}-${i}`} course={course} showSchedule />
              ))}
              {possibilitiesList.length > 8 && (
                <button
                  onClick={() => setViewMode('list')}
                  className="w-full py-2 text-sm text-brand-600 hover:text-brand-700 font-medium"
                >
                  View all {possibilitiesList.length} options
                </button>
              )}
            </div>
          </div>

          {/* Filling Fast */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-amber-500" />
                Register Soon
              </h3>
              <span className="text-sm text-gray-500">Filling fast</span>
            </div>
            {coursesFilling.length > 0 ? (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {coursesFilling.slice(0, 8).map((course, i) => (
                  <CourseQuickCard key={`${course.course_code}-${i}`} course={course} showSchedule />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <TrendingUp className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No courses filling up fast yet</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Calendar Mode */}
      {viewMode === 'calendar' && (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Showing all {scheduleBlocks.length} scheduled sections for your degree plan courses.
          </p>
          <WeeklyCalendar scheduleBlocks={scheduleBlocks} />
        </div>
      )}

      {/* List Mode */}
      {viewMode === 'list' && (
        <div className="space-y-4">
          {categoryOrder
            .filter(cat => requirementsByCategory[cat])
            .map(category => {
              const requirements = requirementsByCategory[category]
              const isExpanded = expandedCategories.has(category)
              const categoryHours = requirements.reduce((sum, r) => sum + (r.required_hours || 0), 0)
              const categoryAvailable = requirements.flatMap(r => r.courses).filter(c => c.available_seats > 0).length

              return (
                <div key={category} className="card overflow-hidden p-0">
                  <button
                    onClick={() => toggleCategory(category)}
                    className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className={clsx(
                        'w-10 h-10 rounded-lg flex items-center justify-center',
                        category === 'major' ? 'bg-brand-100 text-brand-600' :
                        category === 'core' ? 'bg-purple-100 text-purple-600' :
                        category === 'gen_ed' ? 'bg-blue-100 text-blue-600' :
                        'bg-gray-100 text-gray-600'
                      )}>
                        <BookOpen className="h-5 w-5" />
                      </div>
                      <div className="text-left">
                        <span className="font-semibold text-gray-900">
                          {categoryLabels[category] || category}
                        </span>
                        <div className="text-xs text-gray-500">
                          {categoryHours} hours • {categoryAvailable} available
                        </div>
                      </div>
                    </div>
                    <ChevronDown className={clsx(
                      'h-5 w-5 text-gray-400 transition-transform',
                      isExpanded && 'rotate-180'
                    )} />
                  </button>

                  {isExpanded && (
                    <div className="px-5 pb-5 space-y-4 border-t border-gray-100">
                      {requirements.map(req => (
                        <div key={req.id} className="pt-4">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-medium text-gray-700">{req.name}</span>
                            {req.required_hours && (
                              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                                {req.required_hours} hrs
                              </span>
                            )}
                          </div>
                          <div className="space-y-2">
                            {req.courses?.slice(0, 15).map((course, i) => (
                              course.is_group ? (
                                <div key={`${course.course_code}-${i}`} className="px-4 py-2 bg-gray-50 rounded-lg text-sm text-gray-600 italic">
                                  {course.group_description || course.course_code}
                                </div>
                              ) : (
                                <CourseDetailCard key={`${course.course_code}-${i}`} course={course} />
                              )
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid md:grid-cols-3 gap-4">
        <Link
          to="/courses"
          className="card hover:shadow-lg transition-all group flex items-center gap-4 hover:border-brand-300"
        >
          <div className="p-3 bg-brand-100 rounded-xl group-hover:bg-brand-200 transition-colors">
            <BookOpen className="h-6 w-6 text-brand-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 group-hover:text-brand-600">
              Browse Courses
            </h3>
            <p className="text-sm text-gray-500">Explore all available courses</p>
          </div>
        </Link>
        <Link
          to="/chat"
          className="card hover:shadow-lg transition-all group flex items-center gap-4 hover:border-brand-300"
        >
          <div className="p-3 bg-purple-100 rounded-xl group-hover:bg-purple-200 transition-colors">
            <MessageCircle className="h-6 w-6 text-purple-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 group-hover:text-purple-600">
              Ask AI Assistant
            </h3>
            <p className="text-sm text-gray-500">Get course recommendations</p>
          </div>
        </Link>
        <Link
          to="/instructors"
          className="card hover:shadow-lg transition-all group flex items-center gap-4 hover:border-brand-300"
        >
          <div className="p-3 bg-emerald-100 rounded-xl group-hover:bg-emerald-200 transition-colors">
            <Users className="h-6 w-6 text-emerald-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 group-hover:text-emerald-600">
              Find Instructors
            </h3>
            <p className="text-sm text-gray-500">View ratings and syllabi</p>
          </div>
        </Link>
      </div>

      {/* Disclaimer */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs text-gray-500">
        <strong>Disclaimer:</strong> This tool is not affiliated with or endorsed by UGA. Always verify course scheduling with your academic advisor.
      </div>

      {/* Course Entry Modal */}
      <CourseEntryModal
        isOpen={showCourseEntry}
        onClose={() => setShowCourseEntry(false)}
      />
    </div>
  )
}
