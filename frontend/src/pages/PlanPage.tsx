import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuth, useUser } from '@clerk/clerk-react'
import {
  BookOpen,
  ChevronDown,
  Settings,
  Target,
  Zap,
  Compass,
  Clock,
  Users,
  Calendar,
  List,
  TrendingUp,
  Sparkles,
  MessageCircle,
  CheckCircle2,
  MapPin,
  ArrowRight,
  Plus,
  Mail,
  CheckCircle,
} from 'lucide-react'
import { usePlan } from '../context/PlanContext'
import {
  getProgramByMajor,
  getEnrichedProgram,
  getCoursePossibilities,
  getCompletedCourses,
  getQuickProgress,
  setAuthToken,
  joinWaitlist,
} from '../lib/api'
import type { EnrichedRequirement } from '../types'
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
            <stop offset="0%" stopColor="#b45309" />
            <stop offset="100%" stopColor="#d97706" />
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

export default function PlanPage() {
  const navigate = useNavigate()
  const { isSignedIn, isLoaded, getToken } = useAuth()
  const { user } = useUser()
  const { plan, clearPlan, hasPlan } = usePlan()
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['major']))
  const [viewMode, setViewMode] = useState<'requirements' | 'calendar'>('requirements')
  const [showCourseEntry, setShowCourseEntry] = useState(false)
  const [waitlistEmail, setWaitlistEmail] = useState('')
  const [waitlistSubmitted, setWaitlistSubmitted] = useState(false)
  const [selectedSection, setSelectedSection] = useState<{
    id: string  // courseCode-crn
    crn: string
    courseCode: string
    title?: string
    instructor: string
    days: string
    startTime: string
    endTime: string
    building?: string | null
    room?: string | null
    seatsAvailable: number
    classSize: number
  } | null>(null)


  // Waitlist mutation
  const waitlistMutation = useMutation({
    mutationFn: async (email: string) => {
      return joinWaitlist(email)
    },
    onSuccess: () => {
      setWaitlistSubmitted(true)
    },
  })

  // Removed redirect that was causing infinite loop when signed in without plan
  // The plan page now handles this state by showing onboarding prompt

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

  // Schedule blocks for calendar - must be before conditional returns
  const scheduleBlocks = useMemo(() => {
    if (!possibilities?.possibilities) return []
    const blocks: Array<{
      id: string; crn: string; courseCode: string; title?: string; instructor: string;
      days: string; startTime: string; endTime: string;
      building?: string | null; room?: string | null; campus?: string | null;
      seatsAvailable: number; classSize: number; isAvailable: boolean;
    }> = []

    // Helper to parse time like "09:00 am" to decimal hours
    const parseTime = (timeStr: string): number => {
      const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(am|pm)/i)
      if (!match) return 0
      let hours = parseInt(match[1], 10)
      const minutes = parseInt(match[2], 10)
      const isPM = match[3].toLowerCase() === 'pm'
      if (isPM && hours !== 12) hours += 12
      if (!isPM && hours === 12) hours = 0
      return hours + minutes / 60
    }

    possibilities.possibilities.forEach(course => {
      course.sections.forEach(section => {
        if (!section.days || !section.start_time || !section.end_time || section.days === 'TBA') return

        // Filter out sections outside calendar display range (7am-9pm)
        const startHour = parseTime(section.start_time)
        const endHour = parseTime(section.end_time)
        if (startHour < 7 || endHour > 21) return

        blocks.push({
          id: `${course.course_code}-${section.crn}`,
          crn: section.crn,
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

  // Waitlist signup for non-signed-in users
  if (!isSignedIn) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
        {/* Hero Logo */}
        <div className="w-20 h-20 bg-amber-100 border-2 border-amber-200 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
          <Compass className="h-10 w-10 text-amber-700" />
        </div>

        {/* Headlines */}
        <h1 className="text-4xl md:text-5xl font-bold text-amber-950 mb-3" style={{ fontFamily: 'Georgia, serif' }}>
          Find Your Path
        </h1>
        <p className="text-xl text-green-700 font-medium mb-4">
          Smart course planning, made locally
        </p>
        <p className="text-gray-600 mb-8 max-w-lg leading-relaxed">
          We've done the homework on every course, professor, and syllabus — so you can focus on what matters.
          Tell us your goals, we'll map your journey.
        </p>

        {/* Waitlist Form */}
        {!waitlistSubmitted ? (
          <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-amber-100 p-6 mb-10">
            <p className="text-amber-900 mb-4 font-medium">
              Grab a spot — we'll be in touch soon!
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (waitlistEmail.trim() && !waitlistMutation.isPending) {
                  waitlistMutation.mutate(waitlistEmail.trim())
                }
              }}
              className="flex flex-col sm:flex-row gap-3"
            >
              <div className="relative flex-1">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-amber-400" />
                <input
                  type="email"
                  required
                  value={waitlistEmail}
                  onChange={(e) => setWaitlistEmail(e.target.value)}
                  placeholder="your.email@uga.edu"
                  className="w-full pl-10 pr-4 py-3 border border-amber-200 rounded-xl bg-amber-50/50 focus:ring-2 focus:ring-amber-400 focus:border-amber-400 focus:bg-white transition-all"
                />
              </div>
              <button
                type="submit"
                disabled={waitlistMutation.isPending}
                className={clsx(
                  'px-6 py-3 rounded-xl font-medium transition-all shadow-md',
                  waitlistMutation.isPending
                    ? 'bg-amber-200 text-amber-500 cursor-not-allowed'
                    : 'bg-amber-700 text-white hover:bg-amber-800 hover:shadow-lg'
                )}
              >
                {waitlistMutation.isPending ? 'Joining...' : 'Get Early Access'}
              </button>
            </form>
            {waitlistMutation.isError && (
              <p className="text-red-500 text-sm mt-2">Something went wrong. Try again?</p>
            )}
          </div>
        ) : (
          <div className="w-full max-w-md bg-green-50 rounded-2xl border border-green-200 p-6 mb-10">
            <div className="flex items-center justify-center gap-2 mb-2">
              <CheckCircle className="h-6 w-6 text-green-600" />
              <span className="text-green-800 font-semibold text-lg">You're on the list!</span>
            </div>
            <p className="text-green-700">
              We'll reach out soon to help you plan your path.
            </p>
          </div>
        )}

        {/* Value Props - Athens indie style */}
        <div className="grid md:grid-cols-3 gap-6 w-full max-w-4xl mb-12">
          {[
            {
              icon: Sparkles,
              title: 'Real Data, Real Insights',
              desc: 'Every course, professor, and syllabus analyzed — actual information, not generic advice.',
              color: 'bg-amber-100 text-amber-700'
            },
            {
              icon: Compass,
              title: 'Your Goals, Your Schedule',
              desc: 'Fast-track graduation or explore broadly — we plan around what matters to you.',
              color: 'bg-green-100 text-green-700'
            },
            {
              icon: Users,
              title: 'Better Together',
              desc: 'Find study partners, sync schedules with friends, build your crew.',
              color: 'bg-cyan-100 text-cyan-700'
            },
          ].map((item, i) => (
            <div key={i} className="bg-white rounded-2xl border border-amber-100 p-6 shadow-md hover:shadow-lg transition-all">
              <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center mb-4', item.color)}>
                <item.icon className="h-6 w-6" />
              </div>
              <h3 className="font-semibold text-amber-950 mb-2">{item.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>

        {/* Tagline */}
        <p className="text-amber-600 text-sm font-medium">
          GradPath — Your compass to graduation
        </p>
      </div>
    )
  }

  // Signed-in user without a plan - prompt them to create one
  if (!plan) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
        <div className="w-20 h-20 bg-amber-100 border-2 border-amber-200 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
          <Compass className="h-10 w-10 text-amber-700" />
        </div>
        <h1 className="text-3xl font-bold text-amber-950 mb-3" style={{ fontFamily: 'Georgia, serif' }}>
          Let's Build Your Plan
        </h1>
        <p className="text-gray-600 mb-8 max-w-lg">
          Welcome! To get started, tell us about your major and goals so we can create a personalized degree plan for you.
        </p>
        <Link
          to="/programs"
          className="px-6 py-3 bg-amber-700 text-white rounded-xl font-medium hover:bg-amber-800 transition-colors shadow-md hover:shadow-lg flex items-center gap-2"
        >
          <Sparkles className="h-5 w-5" />
          Choose Your Major
        </Link>
      </div>
    )
  }

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

  return (
    <div className="space-y-6 pb-8">
      {/* Hero Header */}
      <div className="relative overflow-hidden bg-gradient-to-br from-amber-900 via-amber-800 to-amber-900 rounded-2xl p-8 text-white">
        {/* Background pattern - organic feel */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='52' height='26' viewBox='0 0 52 26' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M10 10c0-2.21-1.79-4-4-4-3.314 0-6-2.686-6-6h2c0 2.21 1.79 4 4 4 3.314 0 6 2.686 6 6 0 2.21 1.79 4 4 4 3.314 0 6 2.686 6 6 0 2.21 1.79 4 4 4v2c-3.314 0-6-2.686-6-6 0-2.21-1.79-4-4-4-3.314 0-6-2.686-6-6zm25.464-1.95l8.486 8.486-1.414 1.414-8.486-8.486 1.414-1.414z' /%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
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
            action={{ label: 'View all', onClick: () => setViewMode('requirements') }}
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
          {viewMode === 'requirements' ? 'Degree Requirements' : 'Weekly Schedule'}
        </h2>
        <div className="flex rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm">
          {(['requirements', 'calendar'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={clsx(
                'px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5',
                viewMode === mode
                  ? 'bg-brand-600 text-white'
                  : 'text-gray-600 hover:bg-gray-50',
                mode === 'calendar' && 'border-l border-gray-200'
              )}
            >
              {mode === 'requirements' && <List className="h-4 w-4" />}
              {mode === 'calendar' && <Calendar className="h-4 w-4" />}
              <span className="hidden sm:inline capitalize">{mode}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Calendar Mode */}
      {viewMode === 'calendar' && (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Showing all {scheduleBlocks.length} available sections. Click for details.
          </p>
          <WeeklyCalendar
            scheduleBlocks={scheduleBlocks}
            onBlockClick={(block) => setSelectedSection(block)}
          />
        </div>
      )}

      {/* Requirements Mode */}
      {viewMode === 'requirements' && (
        <div className="space-y-4">
          {categoryOrder
            .filter(cat => requirementsByCategory[cat])
            .map(category => {
              const requirements = requirementsByCategory[category]
              const isExpanded = expandedCategories.has(category)
              const categoryHours = requirements.reduce((sum, r) => sum + (r.required_hours || 0), 0)
              const categoryAvailable = requirements.flatMap(r => r.courses).filter(c => c.available_seats > 0).length

              return (
                <div key={category} className="card p-0">
                  <button
                    onClick={() => toggleCategory(category)}
                    className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors rounded-t-2xl"
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
                    <div className="px-5 pb-5 space-y-6 border-t border-gray-100">
                      {requirements.map(req => {
                        // Group courses by subject prefix
                        const coursesBySubject: Record<string, typeof req.courses> = {}
                        req.courses?.forEach(course => {
                          if (course.is_group) return
                          const subject = course.course_code.replace(/[0-9]/g, '').trim()
                          if (!coursesBySubject[subject]) coursesBySubject[subject] = []
                          coursesBySubject[subject]!.push(course)
                        })
                        const groupCourses = req.courses?.filter(c => c.is_group) || []
                        const subjects = Object.keys(coursesBySubject).sort()

                        return (
                          <div key={req.id} className="pt-4">
                            <div className="flex items-center justify-between mb-4">
                              <span className="text-base font-semibold text-gray-900">{req.name}</span>
                              {req.required_hours && (
                                <span className="text-sm text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
                                  {req.required_hours} hours required
                                </span>
                              )}
                            </div>

                            {/* Group descriptions */}
                            {groupCourses.length > 0 && (
                              <div className="mb-4 space-y-2">
                                {groupCourses.map((course, i) => (
                                  <div key={`group-${i}`} className="px-4 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                                    {course.group_description || course.course_code}
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Courses grouped by subject */}
                            <div className="space-y-4">
                              {subjects.map(subject => {
                                const courses = coursesBySubject[subject] || []
                                const availableCount = courses.filter(c => c.available_seats > 0).length

                                return (
                                  <div key={subject}>
                                    <div className="flex items-center gap-2 mb-2">
                                      <span className="text-sm font-medium text-gray-700">{subject}</span>
                                      <span className="text-xs text-gray-400">
                                        {courses.length} courses • {availableCount} available
                                      </span>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                      {courses.map((course, i) => {
                                        const hasSeats = course.available_seats > 0
                                        const isOffered = course.total_sections > 0
                                        const courseNum = course.course_code.replace(/[^0-9]/g, '')

                                        return (
                                          <Link
                                            key={`${course.course_code}-${i}`}
                                            to={`/courses?search=${encodeURIComponent(course.course_code)}`}
                                            className={clsx(
                                              'px-3 py-1.5 rounded-lg text-sm font-mono transition-all hover:shadow-md',
                                              hasSeats
                                                ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                                                : isOffered
                                                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                                            )}
                                            title={`${course.title || course.course_code}${hasSeats ? ` - ${course.available_seats} seats` : isOffered ? ' - Full' : ' - Not offered'}`}
                                          >
                                            {courseNum}
                                            {hasSeats && (
                                              <span className="ml-1 text-xs opacity-75">
                                                ({course.available_seats})
                                              </span>
                                            )}
                                          </Link>
                                        )
                                      })}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )
                      })}
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

      {/* Section Details Modal */}
      {selectedSection && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setSelectedSection(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-xl font-bold text-gray-900">{selectedSection.courseCode}</h3>
                {selectedSection.title && (
                  <p className="text-gray-600">{selectedSection.title}</p>
                )}
                <p className="text-sm text-gray-500">CRN: {selectedSection.crn}</p>
              </div>
              <button
                onClick={() => setSelectedSection(null)}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="space-y-3 mb-6">
              <div className="flex items-center gap-2 text-gray-700">
                <Users className="h-4 w-4 text-gray-400" />
                <span>{selectedSection.instructor}</span>
              </div>
              <div className="flex items-center gap-2 text-gray-700">
                <Clock className="h-4 w-4 text-gray-400" />
                <span>{selectedSection.days} · {selectedSection.startTime} - {selectedSection.endTime}</span>
              </div>
              {selectedSection.building && (
                <div className="flex items-center gap-2 text-gray-700">
                  <MapPin className="h-4 w-4 text-gray-400" />
                  <span>{selectedSection.building}{selectedSection.room ? ` ${selectedSection.room}` : ''}</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <div className={clsx(
                  'px-2 py-1 rounded-full text-sm font-medium',
                  selectedSection.seatsAvailable > 0
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                )}>
                  {selectedSection.seatsAvailable > 0
                    ? `${selectedSection.seatsAvailable} seats available`
                    : 'No seats available'}
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setSelectedSection(null)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
