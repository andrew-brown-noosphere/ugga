import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  Calendar,
  GraduationCap,
  ArrowRight,
  Clock,
  CheckCircle,
  AlertCircle,
  ChevronRight,
  Settings,
  Sparkles,
  Search,
  Zap,
  Heart,
  Users2,
} from 'lucide-react'
import { getProgramByMajor, getUpcomingEvents } from '../lib/api'
import { useOnboarding } from '../App'
import type { Program, CalendarEvent } from '../types'

export default function HomePage() {
  const { hasCompletedOnboarding, openOnboarding } = useOnboarding()
  const [userMajor, setUserMajor] = useState<string | null>(null)

  useEffect(() => {
    const major = localStorage.getItem('ugga_user_major')
    setUserMajor(major)
  }, [])

  const { data: program, isLoading: programLoading } = useQuery({
    queryKey: ['program', userMajor],
    queryFn: () => (userMajor ? getProgramByMajor(userMajor) : Promise.resolve(null)),
    enabled: !!userMajor && hasCompletedOnboarding,
  })

  const { data: calendarData } = useQuery({
    queryKey: ['upcoming-events'],
    queryFn: () => getUpcomingEvents(8),
  })

  const handleChangeMajor = () => {
    localStorage.removeItem('ugga_user_major')
    localStorage.removeItem('ugga_onboarding_complete')
    openOnboarding()
  }

  // Show landing page for new users
  if (!hasCompletedOnboarding) {
    return (
      <div className="space-y-8">
        {/* Hero Section */}
        <div className="bg-gradient-to-br from-brand-600 via-brand-700 to-indigo-800 rounded-2xl p-8 md:p-12 text-white relative overflow-hidden">
          {/* Background decoration */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />

          <div className="relative max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-white/20 rounded-full text-sm mb-6">
              <Sparkles className="h-4 w-4" />
              AI-Powered Course Planning
            </div>

            <h1 className="text-3xl md:text-4xl font-bold mb-4">
              Plan Your Perfect Semester at UGA
            </h1>
            <p className="text-lg text-white/80 mb-8">
              Get personalized course recommendations based on your major and goals.
              Never miss a deadline with smart scheduling assistance.
            </p>

            <div className="flex flex-wrap gap-4">
              <button
                onClick={openOnboarding}
                className="px-6 py-3 bg-white text-brand-700 font-semibold rounded-xl hover:bg-gray-100 transition-colors flex items-center gap-2"
              >
                Get Started
                <ArrowRight className="h-5 w-5" />
              </button>
              <Link
                to="/courses"
                className="px-6 py-3 bg-white/10 text-white font-medium rounded-xl hover:bg-white/20 transition-colors"
              >
                Browse Courses
              </Link>
            </div>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          <FeatureCard
            icon={Heart}
            title="Plan with Your Crew"
            description="Coordinate schedules with your frat, sorority, or friend group."
          />
          <FeatureCard
            icon={Users2}
            title="Study Groups"
            description="Find study partners in your classes and collaborate together."
          />
          <FeatureCard
            icon={Zap}
            title="Smart Recommendations"
            description="Get AI-powered course suggestions based on your goals."
          />
          <FeatureCard
            icon={GraduationCap}
            title="Degree Tracking"
            description="See your progress towards graduation at a glance."
          />
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          <QuickAction
            title="Join a Cohort"
            description="Plan schedules with your friends"
            href="/cohorts"
            icon={Heart}
          />
          <QuickAction
            title="Find Study Groups"
            description="Connect with classmates"
            href="/study-groups"
            icon={Users2}
          />
          <QuickAction
            title="Search Courses"
            description="Browse the course catalog"
            href="/courses"
            icon={Search}
          />
          <QuickAction
            title="Explore Programs"
            description="View degree requirements"
            href="/programs"
            icon={BookOpen}
          />
        </div>
      </div>
    )
  }

  // Show personalized dashboard for returning users
  return (
    <div className="space-y-8">
      {/* Personalized Header */}
      <div className="bg-gradient-to-r from-brand-600 to-brand-700 rounded-2xl p-8 text-white">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-2">
              Welcome back{userMajor && userMajor !== 'Undeclared' ? `, ${userMajor} student` : ''}!
            </h1>
            <p className="text-indigo-100">
              {userMajor === 'Undeclared'
                ? "Explore courses and find your path"
                : `Track your progress and plan your courses`}
            </p>
          </div>
          <button
            onClick={handleChangeMajor}
            className="text-indigo-200 hover:text-white text-sm flex items-center gap-1"
          >
            <Settings className="h-4 w-4" />
            Change Major
          </button>
        </div>

      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Main Content - Course Requirements */}
        <div className="lg:col-span-2 space-y-6">
          {/* Degree Requirements Section */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-100 rounded-lg">
                  <GraduationCap className="h-5 w-5 text-indigo-600" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {userMajor && userMajor !== 'Undeclared'
                    ? `${userMajor} Requirements`
                    : 'Explore Programs'}
                </h2>
              </div>
              <Link
                to="/programs"
                className="text-sm text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
              >
                View All
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>

            {programLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-4 bg-gray-200 rounded w-1/3 mb-2" />
                    <div className="h-3 bg-gray-100 rounded w-full" />
                  </div>
                ))}
              </div>
            ) : program ? (
              <ProgramRequirements program={program} />
            ) : (
              <NoProgramMatch major={userMajor} />
            )}
          </div>

          {/* Quick Actions */}
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            <QuickAction
              title="Your Cohorts"
              description="Coordinate with your crew"
              href="/cohorts"
              icon={Heart}
            />
            <QuickAction
              title="Study Groups"
              description="Find study partners"
              href="/study-groups"
              icon={Users2}
            />
            <QuickAction
              title="Search Courses"
              description="Browse the catalog"
              href="/courses"
              icon={BookOpen}
            />
            <QuickAction
              title="Degree Planner"
              description="Build your schedule"
              href="/planner"
              icon={Calendar}
            />
          </div>
        </div>

        {/* Sidebar - Upcoming Deadlines */}
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-amber-100 rounded-lg">
                <Clock className="h-5 w-5 text-amber-600" />
              </div>
              <h2 className="text-lg font-semibold text-gray-900">Upcoming Deadlines</h2>
            </div>

            {calendarData?.events && calendarData.events.length > 0 ? (
              <div className="space-y-3">
                {calendarData.events.slice(0, 6).map((event) => (
                  <DeadlineItem key={event.id} event={event} />
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">No upcoming deadlines found.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function FeatureCard({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ElementType
  title: string
  description: string
}) {
  return (
    <div className="card">
      <div className="p-3 bg-brand-100 rounded-lg w-fit mb-4">
        <Icon className="h-6 w-6 text-brand-600" />
      </div>
      <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
  )
}

function ProgramRequirements({ program }: { program: Program }) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['foundation']))

  const toggleCategory = (category: string) => {
    const newSet = new Set(expandedCategories)
    if (newSet.has(category)) {
      newSet.delete(category)
    } else {
      newSet.add(category)
    }
    setExpandedCategories(newSet)
  }

  // Group requirements by category
  const requirementsByCategory = program.requirements.reduce(
    (acc, req) => {
      if (!acc[req.category]) acc[req.category] = []
      acc[req.category].push(req)
      return acc
    },
    {} as Record<string, typeof program.requirements>
  )

  const categoryLabels: Record<string, string> = {
    foundation: 'Foundation Courses',
    major: 'Major Requirements',
    elective: 'Electives',
    gen_ed: 'General Education',
  }

  const categoryOrder = ['foundation', 'major', 'gen_ed', 'elective']

  return (
    <div className="space-y-4">
      {program.total_hours && (
        <div className="flex items-center gap-2 text-sm text-gray-600 mb-4">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <span>Total: {program.total_hours} credit hours required</span>
        </div>
      )}

      {categoryOrder
        .filter((cat) => requirementsByCategory[cat])
        .map((category) => (
          <div key={category} className="border border-gray-100 rounded-lg overflow-hidden">
            <button
              onClick={() => toggleCategory(category)}
              className="w-full px-4 py-3 bg-gray-50 flex items-center justify-between hover:bg-gray-100 transition-colors"
            >
              <span className="font-medium text-gray-900">
                {categoryLabels[category] || category}
              </span>
              <ChevronRight
                className={`h-4 w-4 text-gray-400 transition-transform ${
                  expandedCategories.has(category) ? 'rotate-90' : ''
                }`}
              />
            </button>

            {expandedCategories.has(category) && (
              <div className="p-4 space-y-3">
                {requirementsByCategory[category].map((req) => (
                  <div key={req.id}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">{req.name}</span>
                      {req.required_hours && (
                        <span className="text-xs text-gray-500">{req.required_hours} hrs</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {req.courses.slice(0, 8).map((course, i) => (
                        <Link
                          key={`${course.course_code}-${i}`}
                          to={`/courses?search=${encodeURIComponent(course.course_code)}`}
                          className="px-2 py-1 bg-gray-100 hover:bg-indigo-100 text-xs font-mono rounded text-gray-700 hover:text-indigo-700 transition-colors"
                        >
                          {course.course_code}
                        </Link>
                      ))}
                      {req.courses.length > 8 && (
                        <span className="px-2 py-1 text-xs text-gray-500">
                          +{req.courses.length - 8} more
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

      <Link
        to={`/programs`}
        className="inline-flex items-center text-sm text-indigo-600 hover:text-indigo-700"
      >
        View full program details
        <ArrowRight className="h-4 w-4 ml-1" />
      </Link>
    </div>
  )
}

function NoProgramMatch({ major }: { major: string | null }) {
  return (
    <div className="text-center py-6">
      <div className="inline-flex items-center justify-center w-12 h-12 bg-gray-100 rounded-full mb-4">
        <AlertCircle className="h-6 w-6 text-gray-400" />
      </div>
      <h3 className="text-gray-900 font-medium mb-2">
        {major === 'Undeclared'
          ? 'Explore your options'
          : `${major} program details coming soon`}
      </h3>
      <p className="text-sm text-gray-500 mb-4">
        {major === 'Undeclared'
          ? "Browse programs to find the right fit for you."
          : "We're still gathering requirement data for this program."}
      </p>
      <div className="flex justify-center gap-3">
        <Link to="/programs" className="btn btn-primary text-sm">
          Browse Programs
        </Link>
        <Link to="/courses" className="btn btn-secondary text-sm">
          Explore Courses
        </Link>
      </div>
    </div>
  )
}

function DeadlineItem({ event }: { event: CalendarEvent }) {
  const getCategoryColor = (category: string | null) => {
    switch (category) {
      case 'fees':
        return 'bg-red-100 text-red-700'
      case 'academic':
        return 'bg-blue-100 text-blue-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors">
      <div className="flex-shrink-0 w-10 text-center">
        <div className="text-xs font-medium text-gray-500 uppercase">
          {event.date?.split(' ')[0] || 'TBD'}
        </div>
        <div className="text-lg font-bold text-gray-900">
          {event.date?.match(/\d+/)?.[0] || '-'}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{event.event}</p>
        <div className="flex items-center gap-2 mt-1">
          {event.semester && (
            <span className="text-xs text-gray-500">{event.semester}</span>
          )}
          {event.category && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${getCategoryColor(event.category)}`}>
              {event.category}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function QuickAction({
  title,
  description,
  href,
  icon: Icon,
}: {
  title: string
  description: string
  href: string
  icon: React.ElementType
}) {
  return (
    <Link to={href} className="card hover:shadow-lg transition-shadow group">
      <div className="flex items-start space-x-4">
        <div className="bg-indigo-100 p-3 rounded-lg group-hover:bg-indigo-200 transition-colors">
          <Icon className="h-6 w-6 text-indigo-600" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 group-hover:text-indigo-600 transition-colors">
            {title}
          </h3>
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        </div>
      </div>
    </Link>
  )
}
