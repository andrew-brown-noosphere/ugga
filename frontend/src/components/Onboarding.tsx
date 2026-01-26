import { useState } from 'react'
import { useUser } from '@clerk/clerk-react'
import {
  Sparkles,
  Search,
  ChevronRight,
  ChevronLeft,
  GraduationCap,
  Target,
  Zap,
  BookOpen,
  Compass,
  X,
  Coffee,
} from 'lucide-react'
import AIStreamingModal from './AIStreamingModal'

interface OnboardingProps {
  onComplete: () => void
  onClose?: () => void
}

// Popular majors for quick selection
const POPULAR_MAJORS = [
  'Computer Science',
  'Biology',
  'Psychology',
  'Business Administration',
  'Engineering',
  'Nursing',
  'Communications',
  'Political Science',
]

// All majors (simplified list)
const ALL_MAJORS = [
  'Undeclared',
  'Accounting',
  'Advertising',
  'African American Studies',
  'Agribusiness',
  'Agricultural Education',
  'Anthropology',
  'Art',
  'Biology',
  'Business Administration',
  'Chemistry',
  'Communications',
  'Computer Science',
  'Criminal Justice',
  'Economics',
  'Education',
  'Engineering',
  'English',
  'Environmental Science',
  'Finance',
  'History',
  'International Affairs',
  'Journalism',
  'Management',
  'Marketing',
  'Mathematics',
  'Music',
  'Nursing',
  'Philosophy',
  'Physics',
  'Political Science',
  'Psychology',
  'Public Health',
  'Sociology',
  'Statistics',
  'Theatre',
]

// Academic goals
const GOALS = [
  {
    id: 'fast-track',
    title: 'Graduate as quickly as possible',
    description: 'Optimize your course load to finish your degree efficiently',
    icon: Zap,
  },
  {
    id: 'specialist',
    title: 'Become a highly trained specialist',
    description: 'Focus on advanced courses and depth in your major',
    icon: Target,
  },
  {
    id: 'well-rounded',
    title: 'Become a well-rounded person',
    description: 'Explore diverse subjects and broaden your horizons',
    icon: Compass,
  },
  {
    id: 'flexible',
    title: 'Keep my options open',
    description: 'Balance requirements while exploring different paths',
    icon: BookOpen,
  },
  {
    id: 'minimal',
    title: 'Honestly, I just want to party',
    description: "Let's make this as painless as possible",
    icon: Coffee,
  },
]

export default function Onboarding({ onComplete: _onComplete, onClose }: OnboardingProps) {
  const [step, setStep] = useState<1 | 2 | 'streaming'>(1)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMajor, setSelectedMajor] = useState<string | null>(null)
  const [selectedGoal, setSelectedGoal] = useState<string | null>(null)

  // Get user's first name from Clerk (if signed in)
  const { user } = useUser()
  const userName = user?.firstName || null

  const filteredMajors = ALL_MAJORS.filter((major) =>
    major.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleContinueToGoals = () => {
    if (selectedMajor) {
      setStep(2)
    }
  }

  const handleStartStreaming = () => {
    if (selectedGoal) {
      setStep('streaming')
    }
  }

  const handleBack = () => {
    if (step === 2) setStep(1)
  }

  // Show AI streaming modal
  if (step === 'streaming' && selectedMajor && selectedGoal) {
    return (
      <AIStreamingModal
        userName={userName}
        major={selectedMajor}
        goal={selectedGoal}
        onClose={onClose}
      />
    )
  }

  return (
    <div className="fixed inset-0 z-50 bg-gradient-to-br from-brand-600 via-brand-700 to-brand-800 flex items-center justify-center p-4 overflow-y-auto">
      {/* Close button */}
      {onClose && (
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-white/70 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
        >
          <X className="h-6 w-6" />
        </button>
      )}

      <div className="w-full max-w-lg my-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/20 rounded-2xl mb-4">
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Welcome to GradPath</h1>
          <p className="text-white/80">Let's personalize your experience</p>
        </div>

        {/* Progress indicator */}
        <div className="flex justify-center gap-2 mb-6">
          <div className={`h-2 w-16 rounded-full transition-all ${step === 1 || step === 2 ? 'bg-white' : 'bg-white/30'}`} />
          <div className={`h-2 w-16 rounded-full transition-all ${step === 2 ? 'bg-white' : 'bg-white/30'}`} />
        </div>

        {/* Step 1: Major Selection */}
        {step === 1 && (
          <div className="bg-white rounded-2xl shadow-2xl p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-brand-100 rounded-lg">
                <GraduationCap className="h-5 w-5 text-brand-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">What's your major?</h2>
                <p className="text-sm text-gray-500">We'll tailor course recommendations for you</p>
              </div>
            </div>

            {/* Search */}
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search majors..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none transition-all"
              />
            </div>

            {/* Popular majors */}
            {!searchQuery && (
              <div className="mb-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  Popular
                </p>
                <div className="flex flex-wrap gap-2">
                  {POPULAR_MAJORS.map((major) => (
                    <button
                      key={major}
                      onClick={() => setSelectedMajor(major)}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                        selectedMajor === major
                          ? 'bg-brand-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {major}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Major list */}
            <div className="max-h-48 overflow-y-auto border border-gray-100 rounded-xl">
              {filteredMajors.length === 0 ? (
                <div className="p-4 text-center text-gray-500">No majors found</div>
              ) : (
                filteredMajors.map((major) => (
                  <button
                    key={major}
                    onClick={() => setSelectedMajor(major)}
                    className={`w-full px-4 py-3 text-left flex items-center justify-between hover:bg-gray-50 transition-colors ${
                      selectedMajor === major ? 'bg-brand-50' : ''
                    } ${major === 'Undeclared' ? 'border-b border-gray-100' : ''}`}
                  >
                    <span
                      className={`font-medium ${
                        selectedMajor === major ? 'text-brand-600' : 'text-gray-900'
                      }`}
                    >
                      {major}
                    </span>
                    {selectedMajor === major && (
                      <div className="w-5 h-5 bg-brand-600 rounded-full flex items-center justify-center">
                        <svg
                          className="w-3 h-3 text-white"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={3}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      </div>
                    )}
                  </button>
                ))
              )}
            </div>

            {/* Continue button */}
            <button
              onClick={handleContinueToGoals}
              disabled={!selectedMajor}
              className={`w-full mt-6 py-3 px-4 rounded-xl font-medium flex items-center justify-center gap-2 transition-all ${
                selectedMajor
                  ? 'bg-brand-600 text-white hover:bg-brand-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              Continue
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Step 2: Goal Selection */}
        {step === 2 && (
          <div className="bg-white rounded-2xl shadow-2xl p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-brand-100 rounded-lg">
                <Target className="h-5 w-5 text-brand-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">What's your goal?</h2>
                <p className="text-sm text-gray-500">This helps us prioritize your recommendations</p>
              </div>
            </div>

            {/* Goal options */}
            <div className="space-y-3">
              {GOALS.map((goal) => {
                const Icon = goal.icon
                return (
                  <button
                    key={goal.id}
                    onClick={() => setSelectedGoal(goal.id)}
                    className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                      selectedGoal === goal.id
                        ? 'border-brand-600 bg-brand-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`p-2 rounded-lg ${
                          selectedGoal === goal.id ? 'bg-brand-100' : 'bg-gray-100'
                        }`}
                      >
                        <Icon
                          className={`h-5 w-5 ${
                            selectedGoal === goal.id ? 'text-brand-600' : 'text-gray-500'
                          }`}
                        />
                      </div>
                      <div className="flex-1">
                        <h3
                          className={`font-medium ${
                            selectedGoal === goal.id ? 'text-brand-700' : 'text-gray-900'
                          }`}
                        >
                          {goal.title}
                        </h3>
                        <p className="text-sm text-gray-500 mt-0.5">{goal.description}</p>
                      </div>
                      {selectedGoal === goal.id && (
                        <div className="w-5 h-5 bg-brand-600 rounded-full flex items-center justify-center flex-shrink-0">
                          <svg
                            className="w-3 h-3 text-white"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={3}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        </div>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Navigation buttons */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={handleBack}
                className="flex-1 py-3 px-4 rounded-xl font-medium flex items-center justify-center gap-2 bg-gray-100 text-gray-700 hover:bg-gray-200 transition-all"
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </button>
              <button
                onClick={handleStartStreaming}
                disabled={!selectedGoal}
                className={`flex-1 py-3 px-4 rounded-xl font-medium flex items-center justify-center gap-2 transition-all ${
                  selectedGoal
                    ? 'bg-brand-600 text-white hover:bg-brand-700'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                Let's Go!
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        <p className="text-center text-xs text-white/60 mt-4">
          You can change your preferences anytime
        </p>
      </div>
    </div>
  )
}
