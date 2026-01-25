import axios from 'axios'
import type {
  Course,
  CourseFilters,
  Schedule,
  ScheduleStats,
  Program,
  CourseInfo,
  CalendarResponse,
  User,
  PersonalizedReport,
  EnrichedProgram,
  Professor,
  ProfessorListItem,
  ProfessorCourse,
  Syllabus,
  ClaimProfileResponse,
  PossibilitiesResponse,
  SubscriptionTier,
  CheckoutResponse,
  PortalResponse,
  SubscriptionStatusResponse,
  PaymentHistoryResponse,
  // Progress types
  CompletedCourse,
  CompletedCourseCreate,
  CompletedCoursesResponse,
  TranscriptSummary,
  ProgramEnrollment,
  ProgramEnrollmentCreate,
  DegreeAudit,
  QuickProgress,
} from '../types'

// In production, API is served from same origin. In dev, use localhost:8000
const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000')

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Auth token management
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete api.defaults.headers.common['Authorization']
  }
}

// Courses
export async function getCourses(filters: CourseFilters = {}): Promise<Course[]> {
  const params = new URLSearchParams()
  if (filters.search) params.append('search', filters.search)
  if (filters.subject) params.append('subject', filters.subject)
  if (filters.instructor) params.append('instructor', filters.instructor)
  if (filters.has_availability !== undefined) {
    params.append('has_availability', String(filters.has_availability))
  }
  if (filters.limit) params.append('limit', String(filters.limit))
  if (filters.offset) params.append('offset', String(filters.offset))

  const { data } = await api.get(`/courses?${params}`)
  return data
}

export async function getCourse(courseCode: string): Promise<Course> {
  const { data } = await api.get(`/courses/${encodeURIComponent(courseCode)}`)
  return data
}

export async function getCourseInfo(courseCode: string): Promise<CourseInfo> {
  const { data } = await api.get(`/courses/${encodeURIComponent(courseCode)}/info`)
  return data
}

// Subjects
export async function getSubjects(): Promise<string[]> {
  const { data } = await api.get('/subjects')
  return data
}

// Schedules
export async function getCurrentSchedule(): Promise<Schedule | null> {
  const { data } = await api.get('/schedules/current')
  return data
}

export async function getScheduleStats(): Promise<ScheduleStats> {
  const { data } = await api.get('/stats')
  return data
}

// Instructors
export async function getInstructors(search?: string): Promise<string[]> {
  const params = search ? `?search=${encodeURIComponent(search)}` : ''
  const { data } = await api.get(`/instructors${params}`)
  return data.map((i: { name: string }) => i.name)
}

// Sections
export async function getSection(crn: string) {
  const { data } = await api.get(`/sections/${crn}`)
  return data
}

// Programs
export async function getPrograms(degreeType?: string): Promise<Program[]> {
  const params = degreeType ? `?degree_type=${degreeType}` : ''
  const { data } = await api.get(`/programs${params}`)
  return data
}

export async function getProgram(programId: number): Promise<Program> {
  const { data } = await api.get(`/programs/${programId}`)
  return data
}

export async function getProgramByMajor(majorName: string): Promise<Program | null> {
  try {
    const { data } = await api.get(`/programs/by-major/${encodeURIComponent(majorName)}`)
    return data
  } catch {
    return null
  }
}

export async function getEnrichedProgram(programId: number): Promise<EnrichedProgram> {
  const { data } = await api.get(`/programs/${programId}/enriched`)
  return data
}

// Calendar
export async function getCalendarEvents(options?: {
  semester?: string
  category?: string
  limit?: number
}): Promise<CalendarResponse> {
  const params = new URLSearchParams()
  if (options?.semester) params.append('semester', options.semester)
  if (options?.category) params.append('category', options.category)
  if (options?.limit) params.append('limit', String(options.limit))
  const { data } = await api.get(`/calendar?${params}`)
  return data
}

export async function getUpcomingEvents(limit = 10): Promise<CalendarResponse> {
  const { data } = await api.get(`/calendar/upcoming?limit=${limit}`)
  return data
}

// Search
export async function searchCourses(query: string): Promise<Course[]> {
  const { data } = await api.get(`/search?q=${encodeURIComponent(query)}`)
  return data
}

export async function semanticSearch(query: string, limit = 10) {
  const { data } = await api.post('/search/semantic', { query, limit })
  return data
}

// Health check
export async function healthCheck(): Promise<{ status: string; version: string }> {
  const { data } = await api.get('/health')
  return data
}

// User endpoints
export async function getCurrentUser(): Promise<User> {
  const { data } = await api.get('/users/me')
  return data
}

export async function updateUserPreferences(preferences: {
  major?: string
  goal?: string
  photo_url?: string
  bio?: string
  graduation_year?: number
  classification?: string
  linkedin_url?: string
  github_url?: string
  twitter_url?: string
  website_url?: string
}): Promise<User> {
  const { data } = await api.put('/users/me', preferences)
  return data
}

export async function getPersonalizedReport(): Promise<PersonalizedReport> {
  const { data } = await api.get('/users/me/report')
  return data
}

// Professor/Instructor endpoints
export async function getProfessors(options?: {
  search?: string
  department?: string
  limit?: number
  offset?: number
}): Promise<ProfessorListItem[]> {
  const params = new URLSearchParams()
  if (options?.search) params.append('search', options.search)
  if (options?.department) params.append('department', options.department)
  if (options?.limit) params.append('limit', String(options.limit))
  if (options?.offset) params.append('offset', String(options.offset))
  const { data } = await api.get(`/instructors?${params}`)
  return data
}

export async function getProfessor(professorId: number): Promise<Professor> {
  const { data } = await api.get(`/instructors/${professorId}`)
  return data
}

export async function getProfessorCourses(professorId: number): Promise<ProfessorCourse[]> {
  const { data } = await api.get(`/instructors/${professorId}/courses`)
  return data
}

export async function getProfessorSyllabi(professorId: number): Promise<Syllabus[]> {
  const { data } = await api.get(`/instructors/${professorId}/syllabi`)
  return data
}

export async function claimProfile(
  professorId: number,
  email: string
): Promise<ClaimProfileResponse> {
  const { data } = await api.post(`/instructors/${professorId}/claim`, { email })
  return data
}

export async function updateProfessorProfile(
  professorId: number,
  updates: {
    office_hours?: string
    bio?: string
    research_areas?: string[]
    personal_website?: string
  }
): Promise<Professor> {
  const { data } = await api.put(`/instructors/${professorId}/profile`, updates)
  return data
}

// Course Possibilities endpoints
export async function getCoursePossibilities(
  programId: number,
  options?: {
    goal?: string
    completed?: string[]
    limit?: number
  }
): Promise<PossibilitiesResponse> {
  const params = new URLSearchParams()
  if (options?.goal) params.append('goal', options.goal)
  if (options?.completed?.length) {
    params.append('completed', options.completed.join(','))
  }
  if (options?.limit) params.append('limit', String(options.limit))

  const { data } = await api.get(`/programs/${programId}/possibilities?${params}`)
  return data
}

// =============================================================================
// Payment & Subscription endpoints
// =============================================================================

export async function createCheckout(tier: SubscriptionTier): Promise<CheckoutResponse> {
  const { data } = await api.post('/payments/checkout', { tier })
  return data
}

export async function getSubscriptionStatus(): Promise<SubscriptionStatusResponse> {
  const { data } = await api.get('/payments/status')
  return data
}

export async function createPortalSession(): Promise<PortalResponse> {
  const { data } = await api.post('/payments/portal')
  return data
}

export async function getPaymentHistory(limit = 10): Promise<PaymentHistoryResponse> {
  const { data } = await api.get(`/payments/history?limit=${limit}`)
  return data
}

// =============================================================================
// Student Progress endpoints
// =============================================================================

// Completed Courses
export async function getCompletedCourses(semester?: string): Promise<CompletedCoursesResponse> {
  const params = semester ? `?semester=${encodeURIComponent(semester)}` : ''
  const { data } = await api.get(`/progress/courses${params}`)
  return data
}

export async function addCompletedCourse(course: CompletedCourseCreate): Promise<CompletedCourse> {
  const { data } = await api.post('/progress/courses', course)
  return data
}

export async function addCompletedCoursesBulk(courses: CompletedCourseCreate[]): Promise<CompletedCoursesResponse> {
  const { data } = await api.post('/progress/courses/bulk', { courses })
  return data
}

export async function updateCompletedCourse(
  courseId: number,
  updates: {
    grade?: string
    credit_hours?: number
    semester?: string
    year?: number
  }
): Promise<CompletedCourse> {
  const { data } = await api.put(`/progress/courses/${courseId}`, updates)
  return data
}

export async function deleteCompletedCourse(courseId: number): Promise<void> {
  await api.delete(`/progress/courses/${courseId}`)
}

// Transcript Summary
export async function getTranscriptSummary(): Promise<TranscriptSummary> {
  const { data } = await api.get('/progress/summary')
  return data
}

// Program Enrollments
export async function getProgramEnrollments(activeOnly = true): Promise<{ enrollments: ProgramEnrollment[] }> {
  const { data } = await api.get(`/progress/enrollments?active_only=${activeOnly}`)
  return data
}

export async function enrollInProgram(enrollment: ProgramEnrollmentCreate): Promise<ProgramEnrollment> {
  const { data } = await api.post('/progress/enrollments', enrollment)
  return data
}

// Degree Audit
export async function runDegreeAudit(enrollmentId?: number): Promise<DegreeAudit> {
  const params = enrollmentId ? `?enrollment_id=${enrollmentId}` : ''
  const { data } = await api.get(`/progress/audit${params}`)
  return data
}

export async function runWhatIfAnalysis(
  hypotheticalCourses: CompletedCourseCreate[],
  enrollmentId?: number
): Promise<DegreeAudit> {
  const params = enrollmentId ? `?enrollment_id=${enrollmentId}` : ''
  const { data } = await api.post(`/progress/audit/what-if${params}`, {
    hypothetical_courses: hypotheticalCourses,
  })
  return data
}

export async function getQuickProgress(): Promise<QuickProgress> {
  const { data } = await api.get('/progress/quick')
  return data
}

// =============================================================================
// AI Chat endpoints
// =============================================================================

import type {
  ChatResponse,
  ChatMessage,
  VerificationStatus,
  SendVerificationResponse,
  ConfirmVerificationResponse,
  VisibilitySettings,
  PublicProfile,
  ProfileSearchResult,
} from '../types'

// =============================================================================
// Profile & Verification endpoints
// =============================================================================

export async function getVerificationStatus(): Promise<VerificationStatus> {
  const { data } = await api.get('/profile/verify/status')
  return data
}

export async function sendVerificationCode(ugaEmail: string): Promise<SendVerificationResponse> {
  const { data } = await api.post('/profile/verify/send', { uga_email: ugaEmail })
  return data
}

export async function confirmVerification(
  ugaEmail: string,
  code: string,
  username?: string
): Promise<ConfirmVerificationResponse> {
  const { data } = await api.post('/profile/verify/confirm', {
    uga_email: ugaEmail,
    code,
    username,
  })
  return data
}

export async function getVisibilitySettings(): Promise<VisibilitySettings> {
  const { data } = await api.get('/profile/visibility')
  return data
}

export async function updateVisibilitySettings(
  settings: Partial<VisibilitySettings>
): Promise<VisibilitySettings> {
  const { data } = await api.put('/profile/visibility', settings)
  return data
}

export async function getPublicProfile(username: string): Promise<PublicProfile> {
  const { data } = await api.get(`/profile/u/${encodeURIComponent(username)}`)
  return data
}

export async function searchProfiles(query: string, limit = 20): Promise<ProfileSearchResult[]> {
  const { data } = await api.get(`/profile/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  return data
}

// =============================================================================
// AI Chat endpoints
// =============================================================================

export async function sendChatMessage(
  message: string,
  history?: ChatMessage[]
): Promise<ChatResponse> {
  const { data } = await api.post('/chat', {
    message,
    history: history?.map((m) => ({ role: m.role, content: m.content })),
  })
  return data
}

export async function checkChatHealth(): Promise<{ status: string; model?: string }> {
  const { data } = await api.get('/chat/health')
  return data
}

export default api
