import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import type { Program, CourseRecommendation, ScheduleItem, DegreeProgress } from '../types'

interface PlanData {
  major: string
  goal: string
  program: Program | null
  degreeProgress: DegreeProgress | null
  recommendations: CourseRecommendation[]
  sampleSchedule: ScheduleItem[]
  createdAt: string
}

interface PlanContextType {
  plan: PlanData | null
  setPlan: (plan: PlanData) => void
  clearPlan: () => void
  hasPlan: boolean
}

const PlanContext = createContext<PlanContextType | null>(null)

const STORAGE_KEY = 'ugga_user_plan'

export function PlanProvider({ children }: { children: ReactNode }) {
  const [plan, setPlanState] = useState<PlanData | null>(null)
  const [isLoaded, setIsLoaded] = useState(false)

  // Load from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        setPlanState(JSON.parse(stored))
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    }
    setIsLoaded(true)
  }, [])

  const setPlan = (newPlan: PlanData) => {
    setPlanState(newPlan)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newPlan))
    // Also update the individual keys for backward compatibility
    localStorage.setItem('ugga_user_major', newPlan.major)
    localStorage.setItem('ugga_user_goal', newPlan.goal)
    localStorage.setItem('ugga_onboarding_complete', 'true')
  }

  const clearPlan = () => {
    setPlanState(null)
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem('ugga_user_major')
    localStorage.removeItem('ugga_user_goal')
    localStorage.removeItem('ugga_onboarding_complete')
  }

  // Don't render children until we've loaded from localStorage
  if (!isLoaded) {
    return null
  }

  return (
    <PlanContext.Provider value={{ plan, setPlan, clearPlan, hasPlan: !!plan }}>
      {children}
    </PlanContext.Provider>
  )
}

export function usePlan() {
  const context = useContext(PlanContext)
  if (!context) {
    throw new Error('usePlan must be used within a PlanProvider')
  }
  return context
}
