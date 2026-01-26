// Course types
export interface Section {
  id: number
  crn: string
  section_code: string
  status: string
  credit_hours: number
  instructor: string | null
  part_of_term: string
  class_size: number
  seats_available: number
  waitlist_count: number
  is_available: boolean
  // Schedule info
  days: string | null  // e.g., "M W F", "T R"
  start_time: string | null  // e.g., "09:00 am"
  end_time: string | null  // e.g., "09:50 am"
  building: string | null  // e.g., "Boyd GSRC"
  room: string | null  // e.g., "0306"
  campus: string | null  // e.g., "Athens"
}

export interface Course {
  id: number
  subject: string
  course_number: string
  title: string
  department: string | null
  course_code: string
  description: string | null
  prerequisites: string | null
  sections: Section[]
  total_seats: number
  available_seats: number
  has_availability: boolean
}

export interface Schedule {
  id: number
  term: string
  parse_date: string
  total_courses: number
  total_sections: number
  is_current: boolean
}

// Program types
export interface RequirementCourse {
  course_code: string
  title: string | null
  credit_hours: number | null
  is_group: boolean
}

export interface Requirement {
  id: number
  name: string
  category: string
  required_hours: number | null
  description: string | null
  selection_type: string
  courses: RequirementCourse[]
}

export interface Program {
  id: number
  bulletin_id: string
  name: string
  degree_type: string
  college_code: string
  department: string | null
  overview: string | null
  total_hours: number | null
  bulletin_url: string | null
  requirements: Requirement[]
}

// Search/filter types
export interface CourseFilters {
  search?: string
  subject?: string
  instructor?: string
  has_availability?: boolean
  limit?: number
  offset?: number
}

export interface ScheduleStats {
  term: string
  total_courses: number
  total_sections: number
  available_sections: number
  total_seats: number
  available_seats: number
  instructor_count: number
  parse_date: string
}

// Prerequisite types
export interface PrerequisiteOption {
  code: string
  min_grade: string | null
  concurrent: boolean
}

export interface PrerequisiteGroup {
  type: string
  logic: 'OR' | 'SINGLE'
  options?: PrerequisiteOption[]
  course?: PrerequisiteOption
}

export interface CourseInfo {
  code: string
  title: string
  description: string | null
  prerequisites_text: string | null
  prerequisites_structured: PrerequisiteGroup[]
  credit_hours: string | null
  semester_offered: string | null
  sections_available: number
  total_seats: number
  available_seats: number
  instructors: string[]
}

// Calendar types
export interface CalendarEvent {
  id: number
  event: string
  date: string | null
  semester: string | null
  category: string | null
  source: string
}

export interface CalendarResponse {
  events: CalendarEvent[]
  total: number
}

// User types
export interface User {
  id: number
  clerk_id: string
  email: string
  first_name: string | null
  last_name: string | null
  major: string | null
  goal: string | null
  // Extended profile
  photo_url: string | null
  bio: string | null
  graduation_year: number | null
  classification: string | null
  // Social links
  linkedin_url: string | null
  github_url: string | null
  twitter_url: string | null
  website_url: string | null
  instagram_url: string | null
  tiktok_url: string | null
  bluesky_url: string | null
  // Verification
  uga_email: string | null
  uga_email_verified: boolean
  username: string | null
  created_at: string
}

export interface UserUpdateRequest {
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
  instagram_url?: string
  tiktok_url?: string
  bluesky_url?: string
}

export interface DegreeProgress {
  total_hours_required: number
  hours_completed: number
  percent_complete: number
  requirements_complete: string[]
  requirements_remaining: string[]
}

export interface CourseRecommendation {
  course_code: string
  title: string
  reason: string
  priority: 'high' | 'medium' | 'low'
}

export interface ScheduleItem {
  course_code: string
  title: string
  semester: string
  credit_hours: number
}

export interface PersonalizedReport {
  user: User
  program: Program | null
  degree_progress: DegreeProgress | null
  recommendations: CourseRecommendation[]
  sample_schedule: ScheduleItem[]
  disclaimer: string
}

// Enriched Program types (courses with instructors and syllabi)
export interface CourseInstructorInfo {
  name: string
  section_crn: string
  seats_available: number
  class_size: number
  is_available: boolean
  // Schedule info
  days: string | null  // e.g., "M W F", "T R"
  start_time: string | null  // e.g., "09:00 am"
  end_time: string | null  // e.g., "09:50 am"
  building: string | null  // e.g., "Boyd GSRC"
  room: string | null  // e.g., "0306"
  campus: string | null  // e.g., "Athens"
}

export interface CourseSyllabusInfo {
  id: number
  semester: string | null
  instructor_name: string | null
  syllabus_url: string | null
}

export interface EnrichedCourseInfo {
  course_code: string
  title: string | null
  credit_hours: number | null
  is_group: boolean
  group_description: string | null
  // Bulletin data
  description: string | null
  prerequisites: string | null
  bulletin_url: string | null
  // Current semester data
  instructors: CourseInstructorInfo[]
  total_sections: number
  available_sections: number
  total_seats: number
  available_seats: number
  // Syllabi
  syllabi: CourseSyllabusInfo[]
}

export interface EnrichedRequirement {
  id: number
  name: string
  category: string
  required_hours: number | null
  description: string | null
  selection_type: string
  courses_to_select: number | null
  courses: EnrichedCourseInfo[]
}

export interface EnrichedProgram {
  id: number
  bulletin_id: string
  name: string
  degree_type: string
  college_code: string
  department: string | null
  overview: string | null
  total_hours: number | null
  bulletin_url: string
  requirements: EnrichedRequirement[]
}

// Professor/Instructor types
export interface Professor {
  id: number
  name: string
  first_name: string | null
  last_name: string | null
  title: string | null
  email: string | null
  phone: string | null
  office_location: string | null
  office_hours: string | null
  photo_url: string | null
  profile_url: string | null
  bio: string | null
  research_areas: string[] | null
  education: string | null
  cv_url: string | null
  personal_website: string | null
  department_name: string | null
  rmp_rating: number | null
  rmp_difficulty: number | null
  rmp_num_ratings: number | null
  claim_status: string
  is_claimed: boolean
}

export interface ProfessorListItem {
  id: number
  name: string
  title: string | null
  email: string | null
  department_name: string | null
  photo_url: string | null
  rmp_rating: number | null
}

export interface ProfessorCourse {
  course_code: string
  title: string | null
  semesters_taught: string[] | null
  times_taught: number
}

export interface Syllabus {
  id: number
  course_code: string
  course_title: string | null
  semester: string | null
  instructor_name: string | null
  syllabus_url: string | null
  has_content: boolean
}

export interface ClaimProfileResponse {
  success: boolean
  message: string
  claim_status: string
}

// =============================================================================
// Course Possibilities Types
// =============================================================================

export interface PossibilitySection {
  crn: string
  instructor: string | null
  days: string | null
  start_time: string | null
  end_time: string | null
  building: string | null
  room: string | null
  seats_available: number
  class_size: number
}

export interface CoursePossibility {
  course_code: string
  title: string
  credit_hours: number
  category: string
  requirement_name: string
  total_sections: number
  available_sections: number
  total_seats: number
  available_seats: number
  prerequisites_met: boolean
  missing_prerequisites: string[]
  priority_score: number
  priority_reason: string
  sections: PossibilitySection[]
}

export interface PossibilitiesResponse {
  possibilities: CoursePossibility[]
  total_available: number
  total_eligible: number
  filters_applied: Record<string, unknown>
}

// =============================================================================
// Subscription & Payment Types
// =============================================================================

export type SubscriptionStatus = 'free' | 'active' | 'cancelled' | 'expired'
export type SubscriptionTier = 'quarter' | 'year' | 'graduation'

export interface SubscriptionState {
  status: SubscriptionStatus
  tier: SubscriptionTier | null
  endDate: Date | null
  isPremium: boolean
}

export interface CheckoutResponse {
  checkout_url: string
  session_id: string
}

export interface PortalResponse {
  portal_url: string
}

export interface SubscriptionStatusResponse {
  status: SubscriptionStatus
  tier: SubscriptionTier | null
  end_date: string | null
  is_premium: boolean
}

export interface PaymentHistoryItem {
  id: number
  amount: number
  currency: string
  tier: SubscriptionTier
  status: string
  created_at: string
}

export interface PaymentHistoryResponse {
  payments: PaymentHistoryItem[]
  total: number
}

export interface TierConfig {
  id: SubscriptionTier
  name: string
  price: string
  priceSubtext: string
  duration: string
  features: string[]
  highlighted?: boolean
}

// =============================================================================
// Student Progress Types
// =============================================================================

export interface CompletedCourse {
  id: number
  course_code: string
  grade: string | null  // Optional for privacy
  credit_hours: number
  quality_points: number | null
  semester: string | null
  year: number | null
  source: string
  verified: boolean
  is_passing: boolean
  grade_points: number | null  // Null if no grade provided
  created_at: string
}

export interface CompletedCourseCreate {
  course_code: string
  grade?: string  // Optional for privacy - GPA won't be calculated without grades
  credit_hours?: number
  semester?: string
  year?: number
}

export interface CompletedCoursesResponse {
  courses: CompletedCourse[]
  total: number
}

export interface TranscriptSummary {
  total_hours_attempted: number
  total_hours_earned: number
  transfer_hours: number
  cumulative_gpa: number | null
  major_gpa: number | null
  total_quality_points: number
  hours_1000_level: number
  hours_2000_level: number
  hours_3000_level: number
  hours_4000_level: number
  hours_5000_plus: number
  upper_division_hours: number
  calculated_at: string
}

export interface ProgramEnrollment {
  id: number
  program_id: number
  program_name: string | null
  enrollment_type: string
  is_primary: boolean
  status: string
  catalog_year: string | null
  expected_graduation: string | null
  enrollment_date: string | null
}

export interface ProgramEnrollmentCreate {
  program_id: number
  enrollment_type?: string
  is_primary?: boolean
  catalog_year?: string
}

// =============================================================================
// Degree Audit Types
// =============================================================================

export type SatisfactionStatus = 'incomplete' | 'in_progress' | 'complete'

export interface CourseApplication {
  course_code: string
  grade: string
  credit_hours: number
  is_passing: boolean
}

export interface RequirementResult {
  requirement_id: number
  requirement_name: string
  category: string
  status: SatisfactionStatus
  hours_required: number | null
  hours_satisfied: number
  courses_required: number | null
  courses_satisfied: number
  gpa_required: number | null
  gpa_achieved: number | null
  progress_percent: number
  courses_applied: CourseApplication[]
  remaining_courses: string[]
  description: string
}

export interface DegreeAudit {
  program_id: number
  program_name: string
  degree_type: string
  overall_status: SatisfactionStatus
  overall_progress_percent: number
  total_hours_required: number
  total_hours_earned: number
  cumulative_gpa: number | null
  requirements: RequirementResult[]
  recommended_next_courses: string[]
}

export interface WhatIfRequest {
  hypothetical_courses: CompletedCourseCreate[]
}

export interface QuickProgress {
  has_progress: boolean
  total_hours_earned: number
  total_hours_required: number | null
  cumulative_gpa: number | null
  upper_division_hours: number | null
  program_name: string | null
  progress_percent: number
}

// Grade options for course entry
export const GRADE_OPTIONS = [
  'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F', 'S', 'U', 'W', 'I', 'IP'
] as const

export type Grade = typeof GRADE_OPTIONS[number]

// =============================================================================
// AI Chat Types
// =============================================================================

export interface ChatSource {
  type: string
  code: string | null
  title: string | null
  source_type: string | null
  similarity: number
}

export interface ChatResponse {
  answer: string
  sources: ChatSource[]
  model: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// =============================================================================
// Profile Sharing Types
// =============================================================================

export interface VerificationStatus {
  uga_email: string | null
  is_verified: boolean
  username: string | null
  profile_url: string | null
  verified_at: string | null
}

export interface SendVerificationResponse {
  success: boolean
  message: string
  expires_in_seconds: number
}

export interface ConfirmVerificationResponse {
  success: boolean
  username: string
  profile_url: string
  message: string
}

export interface VisibilitySettings {
  profile_visibility: 'public' | 'verified_only' | 'cohorts_only' | 'private'
  show_full_name: boolean
  show_photo: boolean
  show_bio: boolean
  show_major: boolean
  show_graduation_year: boolean
  show_classification: boolean
  show_completed_courses: boolean
  show_current_schedule: boolean
  show_gpa: boolean
  show_degree_progress: boolean
  show_email: boolean
  show_social_links: boolean
}

export interface PublicProfile {
  id: number
  username: string
  display_name: string | null
  photo_url: string | null
  bio: string | null
  major: string | null
  graduation_year: number | null
  classification: string | null
  completed_courses_count: number | null
  degree_progress_percent: number | null
  gpa: number | null
  linkedin_url: string | null
  github_url: string | null
  twitter_url: string | null
  website_url: string | null
  instagram_url: string | null
  tiktok_url: string | null
  bluesky_url: string | null
  is_verified: boolean
  is_own_profile: boolean
  is_following: boolean
  is_liked: boolean
}

export interface ProfileSearchResult {
  username: string
  display_name: string
  photo_url: string | null
  major: string | null
}

// =============================================================================
// Study Groups Types
// =============================================================================

export interface StudyGroup {
  id: number
  course_code: string
  name: string
  description: string | null
  meeting_day: string | null
  meeting_time: string | null
  meeting_location: string | null
  organizer_id: number
  organizer_username: string | null
  organizer_first_name: string | null
  max_members: number
  member_count: number
  is_active: boolean
  is_member: boolean
  is_organizer: boolean
  created_at: string
}

export interface StudyGroupMember {
  id: number
  user_id: number
  username: string | null
  first_name: string | null
  photo_url: string | null
  joined_at: string
}

export interface StudyGroupCreateRequest {
  course_code: string
  name: string
  description?: string
  meeting_day?: string
  meeting_time?: string
  meeting_location?: string
  max_members?: number
}

export interface StudyGroupUpdateRequest {
  name?: string
  description?: string
  meeting_day?: string
  meeting_time?: string
  meeting_location?: string
  max_members?: number
  is_active?: boolean
}

// =============================================================================
// Cohorts Types
// =============================================================================

export interface Cohort {
  id: number
  name: string
  description: string | null
  created_by_id: number
  created_by_username: string | null
  is_public: boolean
  max_members: number
  invite_code: string | null  // Only visible to members
  member_count: number
  is_member: boolean
  is_admin: boolean
  created_at: string
}

export interface CohortMember {
  id: number
  user_id: number
  username: string | null
  first_name: string | null
  photo_url: string | null
  role: string
  joined_at: string
}

export interface CohortCreateRequest {
  name: string
  description?: string
  is_public?: boolean
  max_members?: number
}

export interface CohortUpdateRequest {
  name?: string
  description?: string
  is_public?: boolean
  max_members?: number
}

// =============================================================================
// Social (Follows & Likes) Types
// =============================================================================

export interface FollowUser {
  id: number
  user_id: number
  username: string | null
  first_name: string | null
  photo_url: string | null
  created_at: string
}

export interface UserFollowStats {
  follower_count: number
  following_count: number
  is_following: boolean
}

export interface ProfileLikeStats {
  like_count: number
  is_liked: boolean
}
