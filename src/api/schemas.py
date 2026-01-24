"""
Pydantic schemas for API request/response models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SectionResponse(BaseModel):
    """API response for a course section."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    crn: str
    section_code: str
    status: str
    credit_hours: int
    instructor: Optional[str] = None
    part_of_term: str
    class_size: int
    seats_available: int
    waitlist_count: int
    is_available: bool
    is_active: bool
    # Schedule info
    days: Optional[str] = None  # e.g., "M W F", "T R"
    start_time: Optional[str] = None  # e.g., "09:00 am"
    end_time: Optional[str] = None  # e.g., "09:50 am"
    building: Optional[str] = None  # e.g., "Boyd GSRC"
    room: Optional[str] = None  # e.g., "0306"
    campus: Optional[str] = None  # e.g., "Athens"


class CourseResponse(BaseModel):
    """API response for a course."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    course_number: str
    course_code: str
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    prerequisites: Optional[str] = None
    bulletin_url: Optional[str] = None
    sections: list[SectionResponse] = []
    total_seats: int
    available_seats: int
    has_availability: bool


class CourseListResponse(BaseModel):
    """API response for course listing (without full section details)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    course_number: str
    course_code: str
    title: str
    department: Optional[str] = None
    section_count: int
    total_seats: int
    available_seats: int
    has_availability: bool


class InstructorResponse(BaseModel):
    """API response for an instructor."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rmp_rating: Optional[float] = None
    rmp_difficulty: Optional[float] = None
    rmp_num_ratings: Optional[int] = None
    rmp_would_take_again: Optional[float] = None


class ScheduleResponse(BaseModel):
    """API response for schedule metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    term: str
    source_url: str
    parse_date: datetime
    report_date: Optional[str] = None
    total_courses: int
    total_sections: int
    is_current: bool


class StatsResponse(BaseModel):
    """API response for schedule statistics."""
    term: str
    total_courses: int
    total_sections: int
    available_sections: int
    total_seats: int
    available_seats: int
    instructor_count: int
    parse_date: str


class SearchFilters(BaseModel):
    """Query parameters for course search."""
    subject: Optional[str] = Field(None, description="Filter by subject code (e.g., CSCI)")
    search: Optional[str] = Field(None, description="Search in title, course code, department")
    instructor: Optional[str] = Field(None, description="Filter by instructor name")
    has_availability: Optional[bool] = Field(None, description="Filter by seat availability")
    part_of_term: Optional[str] = Field(None, description="Filter by part of term")
    limit: int = Field(100, ge=1, le=500, description="Maximum results")
    offset: int = Field(0, ge=0, description="Pagination offset")


class ImportRequest(BaseModel):
    """Request to import a schedule from URL."""
    url: str = Field(..., description="URL of the PDF to import")


class ImportResponse(BaseModel):
    """Response from schedule import."""
    schedule_id: int
    term: str
    courses_imported: int
    sections_imported: int
    warnings: int
    errors: int


class SubjectListResponse(BaseModel):
    """API response for list of subjects."""
    subjects: list[str]
    count: int


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""
    items: list
    total: int
    limit: int
    offset: int
    has_more: bool


# =============================================================================
# Semantic Search / RAG Schemas
# =============================================================================

class SemanticSearchRequest(BaseModel):
    """Request for semantic course search."""
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(10, ge=1, le=50, description="Maximum results")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity score")


class SemanticCourseResult(BaseModel):
    """Course result with similarity score."""
    course_code: str
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    section_count: int
    available_seats: int
    similarity: float


class SemanticSearchResponse(BaseModel):
    """Response from semantic search."""
    query: str
    results: list[SemanticCourseResult]
    total: int


class RAGContextRequest(BaseModel):
    """Request for RAG context retrieval."""
    query: str = Field(..., description="User question or query")
    max_courses: int = Field(5, ge=1, le=20)
    max_documents: int = Field(3, ge=0, le=10)


class RAGCourseContext(BaseModel):
    """Course context for RAG."""
    course_code: str
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    sections: int
    available_seats: int
    similarity: float


class RAGDocumentContext(BaseModel):
    """Document context for RAG."""
    title: str
    content: str
    source_type: str
    similarity: float


class RAGContextResponse(BaseModel):
    """Response with RAG context."""
    query: str
    courses: list[RAGCourseContext]
    documents: list[RAGDocumentContext]


class EmbedCoursesRequest(BaseModel):
    """Request to embed courses."""
    schedule_id: Optional[int] = Field(None, description="Schedule to embed (None = current)")
    force: bool = Field(False, description="Re-embed even if already has embedding")


# =============================================================================
# Program Schemas
# =============================================================================

class RequirementCourseResponse(BaseModel):
    """Course within a requirement group."""
    course_code: str
    title: Optional[str] = None
    credit_hours: Optional[int] = None
    is_group: bool = False
    group_description: Optional[str] = None


class ProgramRequirementResponse(BaseModel):
    """A requirement group within a program."""
    id: int
    name: str
    category: str
    required_hours: Optional[int] = None
    description: Optional[str] = None
    selection_type: str
    courses_to_select: Optional[int] = None
    courses: list[RequirementCourseResponse] = []


class ProgramResponse(BaseModel):
    """Full program with requirements."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    bulletin_id: str
    name: str
    degree_type: str
    college_code: str
    department: Optional[str] = None
    overview: Optional[str] = None
    total_hours: Optional[int] = None
    bulletin_url: str
    requirements: list[ProgramRequirementResponse] = []


class ProgramListResponse(BaseModel):
    """Program listing without full requirements."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    degree_type: str
    college_code: str
    department: Optional[str] = None
    total_hours: Optional[int] = None


# =============================================================================
# Enriched Program Schemas (courses with instructors and syllabi)
# =============================================================================

class CourseInstructorInfo(BaseModel):
    """Instructor teaching a course this semester."""
    name: str
    section_crn: str
    seats_available: int
    class_size: int
    is_available: bool
    # Schedule info
    days: Optional[str] = None  # e.g., "M W F", "T R"
    start_time: Optional[str] = None  # e.g., "09:00 am"
    end_time: Optional[str] = None  # e.g., "09:50 am"
    building: Optional[str] = None  # e.g., "Boyd GSRC"
    room: Optional[str] = None  # e.g., "0306"
    campus: Optional[str] = None  # e.g., "Athens"


class CourseSyllabusInfo(BaseModel):
    """Syllabus available for a course."""
    id: int
    semester: Optional[str] = None
    instructor_name: Optional[str] = None
    syllabus_url: Optional[str] = None


class EnrichedCourseInfo(BaseModel):
    """Course with bulletin data, current instructors, and syllabi."""
    course_code: str
    title: Optional[str] = None
    credit_hours: Optional[int] = None
    is_group: bool = False
    group_description: Optional[str] = None
    # Bulletin data
    description: Optional[str] = None
    prerequisites: Optional[str] = None
    bulletin_url: Optional[str] = None
    # Current semester data
    instructors: list[CourseInstructorInfo] = []
    total_sections: int = 0
    available_sections: int = 0
    total_seats: int = 0
    available_seats: int = 0
    # Syllabi
    syllabi: list[CourseSyllabusInfo] = []


class EnrichedRequirementResponse(BaseModel):
    """Requirement group with enriched course data."""
    id: int
    name: str
    category: str
    required_hours: Optional[int] = None
    description: Optional[str] = None
    selection_type: str
    courses_to_select: Optional[int] = None
    courses: list[EnrichedCourseInfo] = []


class EnrichedProgramResponse(BaseModel):
    """Full program with enriched course data including instructors and syllabi."""
    id: int
    bulletin_id: str
    name: str
    degree_type: str
    college_code: str
    department: Optional[str] = None
    overview: Optional[str] = None
    total_hours: Optional[int] = None
    bulletin_url: str
    requirements: list[EnrichedRequirementResponse] = []


# =============================================================================
# Calendar Schemas
# =============================================================================

class CalendarEventResponse(BaseModel):
    """Academic calendar event."""
    id: int
    event: str
    date: Optional[str] = None
    semester: Optional[str] = None
    category: Optional[str] = None
    source: str


class CalendarResponse(BaseModel):
    """Response with calendar events."""
    events: list[CalendarEventResponse]
    total: int


# =============================================================================
# User Schemas
# =============================================================================

class UserResponse(BaseModel):
    """User profile response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    clerk_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    major: Optional[str] = None
    goal: Optional[str] = None
    # Extended profile
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    graduation_year: Optional[int] = None
    classification: Optional[str] = None
    # Social links
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    twitter_url: Optional[str] = None
    website_url: Optional[str] = None
    created_at: datetime


class UserUpdateRequest(BaseModel):
    """Request to update user preferences."""
    major: Optional[str] = Field(None, max_length=200)
    goal: Optional[str] = Field(None, pattern="^(fast-track|specialist|well-rounded|flexible)$")
    # Extended profile
    photo_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=1000)
    graduation_year: Optional[int] = Field(None, ge=2020, le=2035)
    classification: Optional[str] = Field(None, pattern="^(freshman|sophomore|junior|senior|graduate)$")
    # Social links
    linkedin_url: Optional[str] = Field(None, max_length=255)
    github_url: Optional[str] = Field(None, max_length=255)
    twitter_url: Optional[str] = Field(None, max_length=255)
    website_url: Optional[str] = Field(None, max_length=255)


class DegreeProgressResponse(BaseModel):
    """Degree progress summary."""
    total_hours_required: int
    hours_completed: int
    percent_complete: float
    requirements_complete: list[str]
    requirements_remaining: list[str]


class CourseRecommendationResponse(BaseModel):
    """AI-generated course recommendation."""
    course_code: str
    title: str
    reason: str
    priority: str  # high, medium, low


class ScheduleItemResponse(BaseModel):
    """Sample schedule item."""
    course_code: str
    title: str
    semester: str
    credit_hours: int


class PersonalizedReportResponse(BaseModel):
    """Personalized degree report for user."""
    user: UserResponse
    program: Optional[ProgramResponse] = None
    degree_progress: Optional[DegreeProgressResponse] = None
    recommendations: list[CourseRecommendationResponse] = []
    sample_schedule: list[ScheduleItemResponse] = []
    disclaimer: str


# =============================================================================
# Professor Schemas
# =============================================================================

class ProfessorResponse(BaseModel):
    """Professor profile response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    office_location: Optional[str] = None
    office_hours: Optional[str] = None
    photo_url: Optional[str] = None
    profile_url: Optional[str] = None
    bio: Optional[str] = None
    research_areas: Optional[list[str]] = None
    education: Optional[str] = None
    cv_url: Optional[str] = None
    personal_website: Optional[str] = None
    department_name: Optional[str] = None
    # RMP data if linked
    rmp_rating: Optional[float] = None
    rmp_difficulty: Optional[float] = None
    rmp_num_ratings: Optional[int] = None
    # Claim status
    claim_status: str = "unclaimed"
    is_claimed: bool = False


class ClaimProfileRequest(BaseModel):
    """Request to claim an instructor profile."""
    email: str  # Must be @uga.edu


class ClaimProfileResponse(BaseModel):
    """Response after submitting a claim request."""
    success: bool
    message: str
    claim_status: str


class ProfessorProfileUpdate(BaseModel):
    """Update profile fields (for claimed profiles)."""
    office_hours: Optional[str] = None
    bio: Optional[str] = None
    research_areas: Optional[list[str]] = None
    personal_website: Optional[str] = None


class ProfessorListResponse(BaseModel):
    """Professor listing without full details."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    department_name: Optional[str] = None
    photo_url: Optional[str] = None
    rmp_rating: Optional[float] = None


class ProfessorCourseResponse(BaseModel):
    """Course taught by a professor."""
    course_code: str
    title: Optional[str] = None
    semesters_taught: Optional[list[str]] = None
    times_taught: int = 1


# =============================================================================
# Syllabus Schemas
# =============================================================================

class SyllabusResponse(BaseModel):
    """Syllabus information for a course."""
    id: int
    course_code: str
    course_title: Optional[str] = None
    section: Optional[str] = None
    semester: Optional[str] = None
    instructor_name: Optional[str] = None
    syllabus_url: Optional[str] = None
    cv_url: Optional[str] = None
    department: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None


class SyllabusListResponse(BaseModel):
    """List of syllabi."""
    syllabi: list[SyllabusResponse]
    total: int


# =============================================================================
# AI Chat Schemas
# =============================================================================

class ChatMessageSchema(BaseModel):
    """A message in the chat history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Request for AI chat."""
    message: str = Field(..., min_length=1, max_length=2000, description="The user's question")
    history: Optional[list[ChatMessageSchema]] = Field(None, description="Previous conversation messages")
    max_courses: int = Field(8, ge=1, le=20, description="Max courses in context")
    max_documents: int = Field(5, ge=0, le=10, description="Max documents in context")


class ChatSourceSchema(BaseModel):
    """A source used in generating the response."""
    type: str  # "course" or "document"
    code: Optional[str] = None  # For courses
    title: str
    source_type: Optional[str] = None  # For documents
    similarity: float


class ChatResponse(BaseModel):
    """Response from AI chat."""
    answer: str
    sources: list[ChatSourceSchema]
    model: str


# =============================================================================
# Course Possibilities Schemas
# =============================================================================

class PossibilitySectionResponse(BaseModel):
    """Section data for a course possibility."""
    crn: str
    instructor: Optional[str] = None
    days: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    seats_available: int
    class_size: int


class CoursePossibilityResponse(BaseModel):
    """A course that the student can potentially take this semester."""
    course_code: str
    title: str
    credit_hours: int
    category: str  # foundation, major, elective, gen_ed
    requirement_name: str

    # Availability
    total_sections: int
    available_sections: int
    total_seats: int
    available_seats: int

    # Prerequisite status
    prerequisites_met: bool
    missing_prerequisites: list[str] = []

    # Priority (based on goal)
    priority_score: float
    priority_reason: str

    # Sections for calendar
    sections: list[PossibilitySectionResponse] = []


class PossibilitiesResponse(BaseModel):
    """Response containing course possibilities for a student."""
    possibilities: list[CoursePossibilityResponse]
    total_available: int
    total_eligible: int
    filters_applied: dict


# =============================================================================
# Payment/Subscription Schemas
# =============================================================================

class CreateCheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session."""
    tier: str = Field(..., pattern="^(quarter|year|graduation)$", description="Subscription tier")


class CheckoutResponse(BaseModel):
    """Response with Stripe checkout URL."""
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    """Response with Stripe customer portal URL."""
    portal_url: str


class SubscriptionStatusResponse(BaseModel):
    """Current subscription status for a user."""
    status: str  # free, active, cancelled, expired
    tier: Optional[str] = None  # quarter, year, graduation
    end_date: Optional[datetime] = None
    is_premium: bool


class PaymentHistoryItem(BaseModel):
    """A single payment record."""
    id: int
    amount: int  # cents
    currency: str
    tier: str
    status: str
    created_at: datetime


class PaymentHistoryResponse(BaseModel):
    """List of payment history."""
    payments: list[PaymentHistoryItem]
    total: int


# =============================================================================
# Student Progress Schemas
# =============================================================================

class CompletedCourseCreate(BaseModel):
    """Request to add a completed course."""
    course_code: str = Field(..., pattern=r"^[A-Z]{2,4}\s*\d{4}[A-Z]?$", description="Course code (e.g., CSCI 1301)")
    grade: Optional[str] = Field(None, pattern=r"^[A-DF][+-]?|S|U|W|I|IP$", description="Grade received (optional for privacy)")
    credit_hours: int = Field(3, ge=1, le=6, description="Credit hours")
    semester: Optional[str] = Field(None, description="Semester (e.g., Fall 2024)")
    year: Optional[int] = Field(None, ge=2000, le=2040, description="Year completed")


class CompletedCourseBulkCreate(BaseModel):
    """Request to add multiple completed courses."""
    courses: list[CompletedCourseCreate]


class CompletedCourseUpdate(BaseModel):
    """Request to update a completed course."""
    grade: Optional[str] = Field(None, pattern=r"^[A-DF][+-]?|S|U|W|I|IP$")
    credit_hours: Optional[int] = Field(None, ge=1, le=6)
    semester: Optional[str] = None
    year: Optional[int] = Field(None, ge=2000, le=2040)


class CompletedCourseResponse(BaseModel):
    """Response for a completed course."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_code: str
    grade: Optional[str] = None  # Optional for privacy
    credit_hours: int
    quality_points: Optional[float] = None
    semester: Optional[str] = None
    year: Optional[int] = None
    source: str
    verified: bool
    is_passing: bool
    grade_points: Optional[float] = None  # None if no grade provided
    created_at: datetime


class CompletedCoursesResponse(BaseModel):
    """Response with list of completed courses."""
    courses: list[CompletedCourseResponse]
    total: int


class TranscriptSummaryResponse(BaseModel):
    """Transcript summary with GPA and hours."""
    model_config = ConfigDict(from_attributes=True)

    total_hours_attempted: int
    total_hours_earned: int
    transfer_hours: int
    cumulative_gpa: Optional[float] = None
    major_gpa: Optional[float] = None
    total_quality_points: float
    hours_1000_level: int
    hours_2000_level: int
    hours_3000_level: int
    hours_4000_level: int
    hours_5000_plus: int
    upper_division_hours: int
    calculated_at: datetime


class ProgramEnrollmentCreate(BaseModel):
    """Request to enroll in a program."""
    program_id: int
    enrollment_type: str = Field("major", pattern="^(major|minor|certificate)$")
    is_primary: bool = True
    catalog_year: Optional[str] = None


class ProgramEnrollmentResponse(BaseModel):
    """Response for a program enrollment."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    program_id: int
    program_name: Optional[str] = None
    enrollment_type: str
    is_primary: bool
    status: str
    catalog_year: Optional[str] = None
    expected_graduation: Optional[str] = None
    enrollment_date: Optional[datetime] = None


class ProgramEnrollmentsResponse(BaseModel):
    """Response with list of program enrollments."""
    enrollments: list[ProgramEnrollmentResponse]


# =============================================================================
# Degree Audit Schemas
# =============================================================================

class CourseApplicationResponse(BaseModel):
    """A course applied to a requirement."""
    course_code: str
    grade: Optional[str] = None  # Optional for privacy
    credit_hours: int
    is_passing: bool


class RequirementResultResponse(BaseModel):
    """Result of evaluating a single requirement."""
    requirement_id: int
    requirement_name: str
    category: str
    status: str  # incomplete, in_progress, complete
    hours_required: Optional[int] = None
    hours_satisfied: int
    courses_required: Optional[int] = None
    courses_satisfied: int
    gpa_required: Optional[float] = None
    gpa_achieved: Optional[float] = None
    progress_percent: float
    courses_applied: list[CourseApplicationResponse] = []
    remaining_courses: list[str] = []
    description: str


class DegreeAuditResponse(BaseModel):
    """Complete degree audit result."""
    program_id: int
    program_name: str
    degree_type: str
    overall_status: str  # incomplete, in_progress, complete
    overall_progress_percent: float
    total_hours_required: int
    total_hours_earned: int
    cumulative_gpa: Optional[float] = None
    requirements: list[RequirementResultResponse]
    recommended_next_courses: list[str] = []


class WhatIfRequest(BaseModel):
    """Request for what-if analysis."""
    hypothetical_courses: list[CompletedCourseCreate]


class QuickProgressResponse(BaseModel):
    """Quick progress summary."""
    has_progress: bool
    total_hours_earned: int = 0
    total_hours_required: Optional[int] = None
    cumulative_gpa: Optional[float] = None
    upper_division_hours: Optional[int] = None
    program_name: Optional[str] = None
    progress_percent: float = 0
