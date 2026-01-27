import { useMemo } from 'react'
import { MapPin, Clock } from 'lucide-react'
import { clsx } from 'clsx'

interface ScheduleBlock {
  id: string
  crn: string
  courseCode: string
  title?: string
  instructor: string
  days: string
  startTime: string
  endTime: string
  building?: string | null
  room?: string | null
  campus?: string | null
  seatsAvailable: number
  classSize: number
  isAvailable: boolean
}

interface WeeklyCalendarProps {
  scheduleBlocks: ScheduleBlock[]
  onBlockClick?: (block: ScheduleBlock) => void
}

// Color palette for courses
const COURSE_COLORS = [
  { bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-800' },
  { bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-800' },
  { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-800' },
  { bg: 'bg-orange-100', border: 'border-orange-300', text: 'text-orange-800' },
  { bg: 'bg-pink-100', border: 'border-pink-300', text: 'text-pink-800' },
  { bg: 'bg-cyan-100', border: 'border-cyan-300', text: 'text-cyan-800' },
  { bg: 'bg-yellow-100', border: 'border-yellow-300', text: 'text-yellow-800' },
  { bg: 'bg-red-100', border: 'border-red-300', text: 'text-red-800' },
]

// Day letters to column mapping
const DAY_MAP: Record<string, number> = {
  'M': 0,
  'T': 1,
  'W': 2,
  'R': 3,  // Thursday
  'F': 4,
}

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
const DAY_ABBREVIATIONS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

// Time range for the calendar (7am to 9pm)
const START_HOUR = 7
const END_HOUR = 21

function parseTime(timeStr: string): number {
  // Parse time like "09:00 am" or "01:30 pm" to decimal hours
  const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(am|pm)/i)
  if (!match) return 0

  let hours = parseInt(match[1], 10)
  const minutes = parseInt(match[2], 10)
  const isPM = match[3].toLowerCase() === 'pm'

  if (isPM && hours !== 12) hours += 12
  if (!isPM && hours === 12) hours = 0

  return hours + minutes / 60
}

function formatTimeLabel(hour: number): string {
  const h = hour % 12 || 12
  const ampm = hour < 12 ? 'am' : 'pm'
  return `${h}${ampm}`
}

export default function WeeklyCalendar({ scheduleBlocks, onBlockClick }: WeeklyCalendarProps) {
  // Assign colors to each unique course
  const courseColors = useMemo(() => {
    const colors: Record<string, typeof COURSE_COLORS[0]> = {}
    const uniqueCourses = [...new Set(scheduleBlocks.map(b => b.courseCode))]
    uniqueCourses.forEach((course, i) => {
      colors[course] = COURSE_COLORS[i % COURSE_COLORS.length]
    })
    return colors
  }, [scheduleBlocks])

  // Parse days string into array of day columns
  const parseDays = (days: string): number[] => {
    const result: number[] = []
    // Handle space-separated days like "M W F" or "T R"
    const dayTokens = days.split(/\s+/)
    for (const day of dayTokens) {
      if (day in DAY_MAP) {
        result.push(DAY_MAP[day])
      }
    }
    return result
  }

  // Calculate block positions
  const positionedBlocks = useMemo(() => {
    const blocks: Array<{
      block: ScheduleBlock
      dayColumn: number
      startPercent: number
      heightPercent: number
      color: typeof COURSE_COLORS[0]
    }[]> = Array(5).fill(null).map(() => [])

    scheduleBlocks.forEach(block => {
      if (!block.days || !block.startTime || !block.endTime) return
      if (block.days === 'TBA') return

      const dayColumns = parseDays(block.days)
      const startHour = parseTime(block.startTime)
      const endHour = parseTime(block.endTime)

      if (startHour < START_HOUR || endHour > END_HOUR) return

      const totalHours = END_HOUR - START_HOUR
      const startPercent = ((startHour - START_HOUR) / totalHours) * 100
      const heightPercent = ((endHour - startHour) / totalHours) * 100

      dayColumns.forEach(dayColumn => {
        blocks[dayColumn].push({
          block,
          dayColumn,
          startPercent,
          heightPercent,
          color: courseColors[block.courseCode],
        })
      })
    })

    return blocks
  }, [scheduleBlocks, courseColors])

  // Generate time labels
  const timeLabels = useMemo(() => {
    const labels: { hour: number; label: string }[] = []
    for (let hour = START_HOUR; hour <= END_HOUR; hour++) {
      labels.push({ hour, label: formatTimeLabel(hour) })
    }
    return labels
  }, [])

  // Filter out blocks that don't have schedule data
  const hasScheduledBlocks = scheduleBlocks.some(b => b.days && b.days !== 'TBA' && b.startTime && b.endTime)

  if (!hasScheduledBlocks) {
    return (
      <div className="card bg-gray-50 text-center py-8">
        <Clock className="h-12 w-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">No scheduled classes to display</p>
        <p className="text-sm text-gray-400 mt-1">
          Schedule data will appear here once courses with meeting times are added
        </p>
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="flex border-b border-gray-200">
        {/* Time column header */}
        <div className="w-16 flex-shrink-0 bg-gray-50 border-r border-gray-200" />

        {/* Day headers */}
        {DAY_NAMES.map((day, i) => (
          <div
            key={day}
            className={clsx(
              'flex-1 py-3 px-2 text-center font-medium text-gray-700 bg-gray-50',
              i < DAY_NAMES.length - 1 && 'border-r border-gray-200'
            )}
          >
            <span className="hidden sm:inline">{day}</span>
            <span className="sm:hidden">{DAY_ABBREVIATIONS[i]}</span>
          </div>
        ))}
      </div>

      {/* Calendar body */}
      <div className="flex" style={{ height: `${(END_HOUR - START_HOUR) * 48}px` }}>
        {/* Time labels */}
        <div className="w-16 flex-shrink-0 border-r border-gray-200 bg-gray-50 relative">
          {timeLabels.map(({ hour, label }) => (
            <div
              key={hour}
              className="absolute w-full text-right pr-2 text-xs text-gray-500"
              style={{
                top: `${((hour - START_HOUR) / (END_HOUR - START_HOUR)) * 100}%`,
                transform: 'translateY(-50%)',
              }}
            >
              {label}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {DAY_NAMES.map((_, dayIndex) => (
          <div
            key={dayIndex}
            className={clsx(
              'flex-1 relative',
              dayIndex < DAY_NAMES.length - 1 && 'border-r border-gray-200'
            )}
          >
            {/* Hour grid lines */}
            {timeLabels.map(({ hour }) => (
              <div
                key={hour}
                className="absolute w-full border-t border-gray-100"
                style={{
                  top: `${((hour - START_HOUR) / (END_HOUR - START_HOUR)) * 100}%`,
                }}
              />
            ))}

            {/* Course blocks */}
            {positionedBlocks[dayIndex].map((positioned, i) => (
              <div
                key={`${positioned.block.id}-${dayIndex}-${i}`}
                className={clsx(
                  'absolute left-1 right-1 rounded-md border overflow-hidden cursor-pointer transition-shadow hover:shadow-md',
                  positioned.color.bg,
                  positioned.color.border,
                  !positioned.block.isAvailable && 'opacity-60'
                )}
                style={{
                  top: `${positioned.startPercent}%`,
                  height: `${positioned.heightPercent}%`,
                  minHeight: '24px',
                }}
                onClick={() => onBlockClick?.(positioned.block)}
                title={`${positioned.block.courseCode} - ${positioned.block.title || ''}\n${positioned.block.instructor}\n${positioned.block.startTime} - ${positioned.block.endTime}`}
              >
                <div className={clsx('p-1 h-full overflow-hidden', positioned.color.text)}>
                  <div className="font-medium text-xs truncate">
                    {positioned.block.courseCode}
                  </div>
                  {positioned.heightPercent > 8 && (
                    <>
                      <div className="text-xs truncate opacity-80">
                        {positioned.block.instructor}
                      </div>
                      {positioned.heightPercent > 12 && positioned.block.building && (
                        <div className="text-xs truncate opacity-70 flex items-center gap-0.5">
                          <MapPin className="h-2.5 w-2.5" />
                          {positioned.block.building}
                          {positioned.block.room && ` ${positioned.block.room}`}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="border-t border-gray-200 px-4 py-3 bg-gray-50">
        <div className="flex flex-wrap gap-3">
          {Object.entries(courseColors).map(([course, color]) => (
            <div key={course} className="flex items-center gap-1.5">
              <div className={clsx('w-3 h-3 rounded', color.bg, color.border, 'border')} />
              <span className="text-xs text-gray-600">{course}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
