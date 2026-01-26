import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, CheckCircle2, BookOpen } from 'lucide-react'
import StreamingText from './StreamingText'
import { getProgramByMajor } from '../lib/api'
import { usePlan } from '../context/PlanContext'
import type { Program } from '../types'

interface AIStreamingModalProps {
  userName: string | null
  major: string
  goal: string
  onClose?: () => void
}

const GOAL_TEXT: Record<string, string> = {
  'fast-track': 'graduate as quickly as possible',
  'specialist': 'become a highly trained specialist',
  'well-rounded': 'become a well-rounded person',
  'flexible': 'keep your options open',
}

interface Message {
  id: string
  text: string
  isComplete: boolean
  showCursor: boolean
}

export default function AIStreamingModal({
  userName,
  major,
  goal,
  onClose,
}: AIStreamingModalProps) {
  const navigate = useNavigate()
  const { setPlan } = usePlan()
  const [messages, setMessages] = useState<Message[]>([])
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0)
  const [program, setProgram] = useState<Program | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [phase, setPhase] = useState<'greeting' | 'loading' | 'results' | 'ready'>('greeting')
  const [topCourses, setTopCourses] = useState<string[]>([])

  const displayName = userName || 'there'
  const goalText = GOAL_TEXT[goal] || 'plan your courses'

  // Fetch program data
  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getProgramByMajor(major)
        setProgram(data)

        if (data?.requirements) {
          // Get a diverse sample of courses - not just major courses!
          // Include electives and gen ed which often surprise students
          const coursesByCategory: Record<string, string[]> = {}

          for (const req of data.requirements) {
            const cat = req.category || 'other'
            if (!coursesByCategory[cat]) coursesByCategory[cat] = []
            const courses = req.courses?.slice(0, 3).map(c => c.course_code) || []
            coursesByCategory[cat].push(...courses)
          }

          // Build diverse sample: 1-2 from each category
          const diverseCourses: string[] = []

          // Prioritize showing the "surprising" requirements first
          const categoryPriority = ['gen_ed', 'elective', 'foundation', 'core', 'major']

          for (const cat of categoryPriority) {
            if (coursesByCategory[cat] && diverseCourses.length < 5) {
              // Take 1-2 from each category
              const toTake = Math.min(2, 5 - diverseCourses.length, coursesByCategory[cat].length)
              diverseCourses.push(...coursesByCategory[cat].slice(0, toTake))
            }
          }

          setTopCourses(diverseCourses)
        }
      } catch (error) {
        console.error('Failed to fetch program:', error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [major])

  // Build message sequence based on data
  const buildMessages = useCallback(() => {
    const msgs: Omit<Message, 'isComplete' | 'showCursor'>[] = []

    // Greeting
    msgs.push({
      id: 'greeting',
      text: `Hey ${displayName}! As a ${major} major who wants to ${goalText}, let's check out what you need...`,
    })

    // Loading/searching message
    msgs.push({
      id: 'searching',
      text: `Reading the ${major} degree requirements...`,
    })

    if (program) {
      const courseCount = program.requirements?.reduce((sum, r) => sum + (r.courses?.length || 0), 0) || 0
      const categoryCount = program.requirements?.length || 0

      // Results
      msgs.push({
        id: 'found',
        text: `Found ${program.total_hours || 120} credit hours across ${categoryCount} requirement areas with ${courseCount} courses to choose from.`,
      })

      // Top courses - emphasize diversity
      if (topCourses.length > 0) {
        msgs.push({
          id: 'courses',
          text: `Here are some courses across your requirements - not just ${major} classes, but also gen ed and electives that you'll need:`,
        })
      }

      // Ready
      msgs.push({
        id: 'ready',
        text: `Your personalized dashboard is ready. Let's build your plan!`,
      })
    } else {
      // Fallback if no program found
      msgs.push({
        id: 'fallback',
        text: `I've set up your dashboard. Let's explore courses together!`,
      })
    }

    return msgs.map(m => ({ ...m, isComplete: false, showCursor: false }))
  }, [displayName, major, goalText, program, topCourses])

  // Start message sequence after data loads
  useEffect(() => {
    if (!isLoading) {
      const msgs = buildMessages()
      setMessages(msgs)
      setPhase('loading')
    }
  }, [isLoading, buildMessages])

  // Handle message completion
  const handleMessageComplete = useCallback(() => {
    setMessages(prev =>
      prev.map((m, i) =>
        i === currentMessageIndex ? { ...m, isComplete: true, showCursor: false } : m
      )
    )

    // Move to next message after a brief pause
    setTimeout(() => {
      if (currentMessageIndex < messages.length - 1) {
        setCurrentMessageIndex(prev => prev + 1)
      } else {
        setPhase('ready')
      }
    }, 500)
  }, [currentMessageIndex, messages.length])

  // Navigate to plan page
  const handleGoToDashboard = () => {
    // Save plan data
    setPlan({
      major,
      goal,
      program,
      degreeProgress: program ? {
        total_hours_required: program.total_hours || 120,
        hours_completed: 0,
        percent_complete: 0,
        requirements_complete: [],
        requirements_remaining: program.requirements?.map(r => r.name) || [],
      } : null,
      recommendations: [],
      sampleSchedule: [],
      createdAt: new Date().toISOString(),
    })

    onClose?.()
    navigate('/plan')
  }

  return (
    <div className="fixed inset-0 z-50 bg-gradient-to-br from-brand-600 via-brand-700 to-brand-800 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/20 rounded-2xl mb-4">
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">GradPath</h1>
        </div>

        {/* Chat messages */}
        <div className="bg-white rounded-2xl shadow-2xl p-6 space-y-4 min-h-[300px]">
          {/* Initial loading state */}
          {isLoading && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
                <Sparkles className="h-4 w-4 text-brand-600" />
              </div>
              <div className="flex-1">
                <div className="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-3">
                  <div className="flex items-center gap-2 text-gray-600">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-brand-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-brand-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-brand-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-sm">Connecting...</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.slice(0, currentMessageIndex + 1).map((message, index) => (
            <div key={message.id} className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0">
                {message.isComplete ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : (
                  <Sparkles className="h-4 w-4 text-brand-600" />
                )}
              </div>
              <div className="flex-1">
                <div className="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-3">
                  {index === currentMessageIndex && !message.isComplete ? (
                    <StreamingText
                      text={message.text}
                      speed={20}
                      onComplete={handleMessageComplete}
                      className="text-gray-800"
                    />
                  ) : (
                    <p className="text-gray-800">{message.text}</p>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Top courses visual (after courses message) */}
          {phase === 'ready' && topCourses.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4 pl-11">
              {topCourses.map(course => (
                <span
                  key={course}
                  className="px-3 py-1.5 bg-brand-100 text-brand-700 rounded-full text-sm font-medium flex items-center gap-1"
                >
                  <BookOpen className="h-3 w-3" />
                  {course}
                </span>
              ))}
            </div>
          )}

          {/* Go to Dashboard button */}
          {phase === 'ready' && (
            <div className="pt-4">
              <button
                onClick={handleGoToDashboard}
                className="w-full py-3 bg-brand-600 text-white rounded-xl font-medium hover:bg-brand-700 transition-all flex items-center justify-center gap-2"
              >
                Go to My Plan
                <span className="text-lg">→</span>
              </button>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-white/60 mt-4">
          Not affiliated with UGA. Always verify with your academic advisor.
        </p>
      </div>
    </div>
  )
}
