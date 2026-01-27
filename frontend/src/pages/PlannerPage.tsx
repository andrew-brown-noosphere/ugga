import { useState } from 'react'
import { CheckCircle, Circle, Clock, Plus, X, AlertCircle, GraduationCap } from 'lucide-react'
import { clsx } from 'clsx'
import AuthGate from '../components/AuthGate'

const PLANNER_FEATURES = [
  'Track your progress toward degree completion',
  'Mark courses as completed, in-progress, or planned',
  'See which requirements you still need to fulfill',
  'Identify courses with unmet prerequisites',
]

// Mock data for now - will connect to API
const mockProgram = {
  name: 'Computer Science',
  degree_type: 'BS',
  total_hours: 120,
}

const mockRequirements = [
  {
    id: 1,
    name: 'Foundation Courses',
    category: 'foundation',
    required_hours: 9,
    completed_hours: 9,
    courses: [
      { code: 'ENGL 1101', status: 'completed' },
      { code: 'ENGL 1102', status: 'completed' },
      { code: 'MATH 2250', status: 'completed' },
    ],
  },
  {
    id: 2,
    name: 'Major Requirements',
    category: 'major',
    required_hours: 42,
    completed_hours: 15,
    courses: [
      { code: 'CSCI 1301', status: 'completed' },
      { code: 'CSCI 1302', status: 'completed' },
      { code: 'CSCI 1730', status: 'in_progress' },
      { code: 'CSCI 2610', status: 'planned' },
      { code: 'CSCI 2670', status: 'available' },
      { code: 'CSCI 2720', status: 'available' },
      { code: 'CSCI 3030', status: 'locked' },
    ],
  },
  {
    id: 3,
    name: 'Major Electives',
    category: 'elective',
    required_hours: 23,
    completed_hours: 0,
    courses: [
      { code: 'CSCI 4050', status: 'locked' },
      { code: 'CSCI 4060', status: 'locked' },
      { code: 'CSCI 4150', status: 'locked' },
    ],
  },
]

type CourseStatus = 'completed' | 'in_progress' | 'planned' | 'available' | 'locked'

export default function PlannerPage() {
  const [completedCourses, setCompletedCourses] = useState<string[]>([
    'ENGL 1101', 'ENGL 1102', 'MATH 2250', 'CSCI 1301', 'CSCI 1302'
  ])
  // TODO: Implement planned courses feature
  const [_plannedCourses, _setPlannedCourses] = useState<string[]>(['CSCI 2610'])
  const [newCourse, setNewCourse] = useState('')

  const totalCompleted = mockRequirements.reduce(
    (acc, req) => acc + req.completed_hours,
    0
  )
  const progress = (totalCompleted / mockProgram.total_hours) * 100

  const addCompletedCourse = (e: React.FormEvent) => {
    e.preventDefault()
    if (newCourse && !completedCourses.includes(newCourse.toUpperCase())) {
      setCompletedCourses([...completedCourses, newCourse.toUpperCase()])
      setNewCourse('')
    }
  }

  const removeCourse = (course: string) => {
    setCompletedCourses(completedCourses.filter((c) => c !== course))
  }

  return (
    <AuthGate
      icon={GraduationCap}
      title="Degree Planner"
      description="Track your progress and plan your path to graduation"
      features={PLANNER_FEATURES}
    >
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Degree Planner</h1>
          <p className="text-gray-600">
            {mockProgram.degree_type} in {mockProgram.name}
          </p>
        </div>
        <button className="btn btn-primary">Change Program</button>
      </div>

      {/* Progress Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Overall Progress</h2>
          <span className="text-2xl font-bold text-uga-red">
            {Math.round(progress)}%
          </span>
        </div>
        <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-uga-red transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between text-sm text-gray-500">
          <span>{totalCompleted} hours completed</span>
          <span>{mockProgram.total_hours - totalCompleted} hours remaining</span>
        </div>
      </div>

      {/* Add completed courses */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Completed Courses</h2>
        <form onSubmit={addCompletedCourse} className="flex gap-2 mb-4">
          <input
            type="text"
            value={newCourse}
            onChange={(e) => setNewCourse(e.target.value)}
            placeholder="Add course (e.g., CSCI 1301)"
            className="input flex-1"
          />
          <button type="submit" className="btn btn-primary">
            <Plus className="h-4 w-4" />
          </button>
        </form>
        <div className="flex flex-wrap gap-2">
          {completedCourses.map((course) => (
            <span
              key={course}
              className="inline-flex items-center px-3 py-1 rounded-full bg-green-100 text-green-800 text-sm"
            >
              {course}
              <button
                onClick={() => removeCourse(course)}
                className="ml-2 hover:text-green-600"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* Requirements */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Requirements</h2>
        {mockRequirements.map((req) => (
          <RequirementCard key={req.id} requirement={req} />
        ))}
      </div>

      {/* Legend */}
      <div className="card">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Legend</h3>
        <div className="flex flex-wrap gap-4 text-sm">
          <LegendItem status="completed" label="Completed" />
          <LegendItem status="in_progress" label="In Progress" />
          <LegendItem status="planned" label="Planned" />
          <LegendItem status="available" label="Available" />
          <LegendItem status="locked" label="Prerequisites Needed" />
        </div>
      </div>
    </div>
    </AuthGate>
  )
}

function RequirementCard({
  requirement,
}: {
  requirement: (typeof mockRequirements)[0]
}) {
  const progress = (requirement.completed_hours / requirement.required_hours) * 100

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900">{requirement.name}</h3>
        <span className="text-sm text-gray-500">
          {requirement.completed_hours}/{requirement.required_hours} hours
        </span>
      </div>

      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-4">
        <div
          className="h-full bg-green-500 transition-all duration-500"
          style={{ width: `${Math.min(100, progress)}%` }}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {requirement.courses.map((course) => (
          <CourseChip
            key={course.code}
            code={course.code}
            status={course.status as CourseStatus}
          />
        ))}
      </div>
    </div>
  )
}

function CourseChip({ code, status }: { code: string; status: CourseStatus }) {
  const statusConfig = {
    completed: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      icon: CheckCircle,
    },
    in_progress: {
      bg: 'bg-blue-100',
      text: 'text-blue-800',
      icon: Clock,
    },
    planned: {
      bg: 'bg-purple-100',
      text: 'text-purple-800',
      icon: Circle,
    },
    available: {
      bg: 'bg-yellow-100',
      text: 'text-yellow-800',
      icon: Circle,
    },
    locked: {
      bg: 'bg-gray-100',
      text: 'text-gray-500',
      icon: AlertCircle,
    },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span
      className={clsx(
        'inline-flex items-center px-3 py-1 rounded-full text-sm',
        config.bg,
        config.text
      )}
    >
      <Icon className="h-3 w-3 mr-1" />
      {code}
    </span>
  )
}

function LegendItem({ status, label }: { status: CourseStatus; label: string }) {
  return (
    <div className="flex items-center">
      <CourseChip code="" status={status} />
      <span className="ml-1 text-gray-600">{label}</span>
    </div>
  )
}
