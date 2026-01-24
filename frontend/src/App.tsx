import { useState, createContext, useContext } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import OnboardingModal from './components/Onboarding'
import ChatPanel from './components/ChatPanel'
import HomePage from './pages/HomePage'
import CoursesPage from './pages/CoursesPage'
import PlannerPage from './pages/PlannerPage'
import ProgramsPage from './pages/ProgramsPage'
import PlanPage from './pages/PlanPage'
import InstructorsPage from './pages/InstructorsPage'
import InstructorPage from './pages/InstructorPage'
import ProfilePage from './pages/ProfilePage'
import PublicProfilePage from './pages/PublicProfilePage'
import PricingPage from './pages/PricingPage'
import PaymentSuccessPage from './pages/PaymentSuccessPage'
import { PlanProvider, usePlan } from './context/PlanContext'
import { SubscriptionProvider } from './context/SubscriptionContext'

// Context for onboarding modal state
interface OnboardingContextType {
  showOnboarding: boolean
  openOnboarding: () => void
  closeOnboarding: () => void
  hasCompletedOnboarding: boolean
}

const OnboardingContext = createContext<OnboardingContextType | null>(null)

export function useOnboarding() {
  const context = useContext(OnboardingContext)
  if (!context) throw new Error('useOnboarding must be used within OnboardingProvider')
  return context
}

function AppContent() {
  const [showOnboarding, setShowOnboarding] = useState(false)
  const { hasPlan } = usePlan()

  const openOnboarding = () => setShowOnboarding(true)
  const closeOnboarding = () => setShowOnboarding(false)

  // Onboarding is "complete" if user has a plan
  const hasCompletedOnboarding = hasPlan

  const handleOnboardingComplete = () => {
    // Plan is saved by AIStreamingModal, just close the modal
    setShowOnboarding(false)
  }

  return (
    <OnboardingContext.Provider value={{ showOnboarding, openOnboarding, closeOnboarding, hasCompletedOnboarding }}>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/planner" element={<PlannerPage />} />
          <Route path="/programs" element={<ProgramsPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/instructors" element={<InstructorsPage />} />
          <Route path="/instructors/:id" element={<InstructorPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/u/:username" element={<PublicProfilePage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/payment/success" element={<PaymentSuccessPage />} />
        </Routes>
      </Layout>

      {/* Onboarding Modal */}
      {showOnboarding && (
        <OnboardingModal onComplete={handleOnboardingComplete} onClose={closeOnboarding} />
      )}

      {/* AI Chat Panel - Available on all pages */}
      <ChatPanel />
    </OnboardingContext.Provider>
  )
}

function App() {
  return (
    <PlanProvider>
      <SubscriptionProvider>
        <AppContent />
      </SubscriptionProvider>
    </PlanProvider>
  )
}

export default App
