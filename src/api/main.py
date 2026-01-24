"""
FastAPI application for UGA Course Scheduler API.

Provides endpoints for:
- Course search and listing
- Section details
- Instructor information
- Schedule metadata and statistics
- PDF import
"""
import os
import tempfile
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    CourseResponse,
    CourseListResponse,
    SectionResponse,
    InstructorResponse,
    ScheduleResponse,
    StatsResponse,
    SubjectListResponse,
    ImportRequest,
    ImportResponse,
    PossibilitiesResponse,
    CoursePossibilityResponse,
    PossibilitySectionResponse,
)
from src.services.course_service import CourseService, create_service
from src.models.database import Course, Section, Schedule, Instructor
from src.api.users import router as users_router
from src.api.instructors import router as instructors_router
from src.api.payments import router as payments_router
from src.api.progress import router as progress_router


# Service dependency
_service: Optional[CourseService] = None


def get_service() -> CourseService:
    """Dependency to get CourseService instance."""
    global _service
    if _service is None:
        _service = create_service()
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - initialize service on startup."""
    global _service
    os.makedirs("data", exist_ok=True)
    _service = create_service()
    yield
    _service = None


# Create FastAPI app
app = FastAPI(
    title="UGA Course Scheduler API",
    description="""
API for accessing UGA course schedule data.

Features:
- Search and filter courses by subject, title, instructor
- View section details including availability
- Track instructor information
- Import schedule PDFs

Built for smart schedule planning with future integrations planned for:
- Rate My Professor data
- AI-powered schedule recommendations
- Social features
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users_router)
app.include_router(instructors_router)
app.include_router(payments_router)
app.include_router(progress_router)


# =============================================================================
# Health & Info Endpoints
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    """API root - health check and basic info."""
    return {
        "name": "UGA Course Scheduler API",
        "version": "0.1.0",
        "status": "healthy",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check(service: CourseService = Depends(get_service)):
    """Detailed health check."""
    try:
        schedule = service.get_current_schedule()
        return {
            "status": "healthy",
            "database": "connected",
            "current_schedule": schedule.term if schedule else None,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# =============================================================================
# Schedule Endpoints
# =============================================================================

@app.get("/schedules", response_model=list[ScheduleResponse], tags=["Schedules"])
async def list_schedules(service: CourseService = Depends(get_service)):
    """List all imported schedules."""
    with service.session_factory() as session:
        from sqlalchemy import select
        schedules = session.execute(
            select(Schedule).order_by(Schedule.parse_date.desc())
        ).scalars().all()
        return [ScheduleResponse.model_validate(s) for s in schedules]


@app.get("/schedules/current", response_model=ScheduleResponse, tags=["Schedules"])
async def get_current_schedule(service: CourseService = Depends(get_service)):
    """Get the current (most recent) schedule."""
    schedule = service.get_current_schedule()
    if not schedule:
        raise HTTPException(status_code=404, detail="No schedule found")
    return ScheduleResponse.model_validate(schedule)


@app.get("/schedules/stats", response_model=StatsResponse, tags=["Schedules"])
async def get_schedule_stats(service: CourseService = Depends(get_service)):
    """Get statistics for the current schedule."""
    stats = service.get_stats()
    if not stats:
        raise HTTPException(status_code=404, detail="No schedule found")
    return StatsResponse(**stats)


@app.post("/schedules/import", response_model=ImportResponse, tags=["Schedules"])
async def import_schedule(
    request: ImportRequest,
    background_tasks: BackgroundTasks,
    service: CourseService = Depends(get_service),
):
    """
    Import a schedule from a PDF URL.

    Downloads the PDF and parses it into the database.
    """
    try:
        # Download PDF
        async with httpx.AsyncClient() as client:
            response = await client.get(request.url, follow_redirects=True, timeout=60.0)
            response.raise_for_status()

        # Save to temp file and import
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        try:
            schedule, result = service.import_pdf(temp_path, request.url)
            return ImportResponse(
                schedule_id=schedule.id,
                term=schedule.term,
                courses_imported=schedule.total_courses,
                sections_imported=schedule.total_sections,
                warnings=len(result.warnings),
                errors=len(result.errors),
            )
        finally:
            os.unlink(temp_path)

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# =============================================================================
# Course Endpoints
# =============================================================================

@app.get("/courses", response_model=list[CourseListResponse], tags=["Courses"])
async def list_courses(
    subject: Optional[str] = Query(None, description="Filter by subject code"),
    search: Optional[str] = Query(None, description="Search in title/code/department"),
    instructor: Optional[str] = Query(None, description="Filter by instructor"),
    has_availability: Optional[bool] = Query(None, description="Filter by availability"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: CourseService = Depends(get_service),
):
    """
    List courses with optional filters.

    Returns a paginated list of courses without full section details.
    Use /courses/{course_code} for detailed section information.
    """
    courses = service.get_courses(
        subject=subject,
        search=search,
        instructor=instructor,
        has_availability=has_availability,
        limit=limit,
        offset=offset,
    )

    return [
        CourseListResponse(
            id=c.id,
            subject=c.subject,
            course_number=c.course_number,
            course_code=c.course_code,
            title=c.title,
            department=c.department,
            section_count=len(c.sections),
            total_seats=c.total_seats,
            available_seats=c.available_seats,
            has_availability=c.has_availability,
        )
        for c in courses
    ]


@app.get("/courses/{course_code}", response_model=CourseResponse, tags=["Courses"])
async def get_course(
    course_code: str,
    service: CourseService = Depends(get_service),
):
    """
    Get detailed information about a specific course.

    Includes all section details with availability information.
    Also includes description and prerequisites from bulletin if available.
    """
    # Normalize course code (e.g., "csci1301" -> "CSCI 1301")
    code = course_code.upper().replace("-", " ")
    if " " not in code:
        # Try to insert space (e.g., "CSCI1301" -> "CSCI 1301")
        import re
        code = re.sub(r"([A-Z]+)(\d+)", r"\1 \2", code)

    course = service.get_course_by_code(code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_code}")

    # Get bulletin course data for description/prerequisites
    description = course.description
    prerequisites = course.prerequisites
    bulletin_url = course.bulletin_url

    with service.session_factory() as session:
        from sqlalchemy import select
        from src.models.database import BulletinCourse

        bulletin = session.execute(
            select(BulletinCourse).where(BulletinCourse.course_code == code)
        ).scalar_one_or_none()

        if bulletin:
            description = bulletin.description or description
            prerequisites = bulletin.prerequisites or prerequisites
            bulletin_url = bulletin.bulletin_url or bulletin_url

    return CourseResponse(
        id=course.id,
        subject=course.subject,
        course_number=course.course_number,
        course_code=course.course_code,
        title=course.title,
        department=course.department,
        description=description,
        prerequisites=prerequisites,
        bulletin_url=bulletin_url,
        sections=[
            SectionResponse(
                id=s.id,
                crn=s.crn,
                section_code=s.section_code,
                status=s.status,
                credit_hours=s.credit_hours,
                instructor=s.instructor,
                part_of_term=s.part_of_term,
                class_size=s.class_size,
                seats_available=s.seats_available,
                waitlist_count=s.waitlist_count,
                is_available=s.is_available,
                is_active=s.is_active,
            )
            for s in course.sections
        ],
        total_seats=course.total_seats,
        available_seats=course.available_seats,
        has_availability=course.has_availability,
    )


@app.get("/subjects", response_model=SubjectListResponse, tags=["Courses"])
async def list_subjects(service: CourseService = Depends(get_service)):
    """Get list of all subject codes in the current schedule."""
    subjects = service.get_subjects()
    return SubjectListResponse(subjects=subjects, count=len(subjects))


# =============================================================================
# Section Endpoints
# =============================================================================

@app.get("/sections/{crn}", response_model=SectionResponse, tags=["Sections"])
async def get_section(
    crn: str,
    service: CourseService = Depends(get_service),
):
    """Get detailed information about a specific section by CRN."""
    section = service.get_section_by_crn(crn)
    if not section:
        raise HTTPException(status_code=404, detail=f"Section not found: {crn}")

    return SectionResponse(
        id=section.id,
        crn=section.crn,
        section_code=section.section_code,
        status=section.status,
        credit_hours=section.credit_hours,
        instructor=section.instructor,
        part_of_term=section.part_of_term,
        class_size=section.class_size,
        seats_available=section.seats_available,
        waitlist_count=section.waitlist_count,
        is_available=section.is_available,
        is_active=section.is_active,
    )


# =============================================================================
# Instructor Endpoints (legacy - now handled by instructors router)
# =============================================================================
# Note: Full instructor/professor endpoints are in src/api/instructors.py
# The router provides: GET /instructors, GET /instructors/{id},
# GET /instructors/{id}/courses, GET /instructors/{id}/syllabi, etc.


# =============================================================================
# Semantic Search / RAG Endpoints
# =============================================================================

from src.api.schemas import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticCourseResult,
    RAGContextRequest,
    RAGContextResponse,
    RAGCourseContext,
    RAGDocumentContext,
    EmbedCoursesRequest,
)

# Lazy-loaded embedding service
_embedding_service = None


def get_embedding_service():
    """Get or create embedding service."""
    global _embedding_service
    if _embedding_service is None:
        from src.services.embedding_service import create_embedding_service
        _embedding_service = create_embedding_service()
    return _embedding_service


@app.post("/search/semantic", response_model=SemanticSearchResponse, tags=["Search"])
async def semantic_search(request: SemanticSearchRequest):
    """
    Search courses using natural language semantic similarity.

    Requires OpenAI API key and PostgreSQL with pgvector.
    """
    try:
        embedding_service = get_embedding_service()
        results = embedding_service.search_courses_semantic(
            query=request.query,
            limit=request.limit,
            threshold=request.threshold,
        )

        return SemanticSearchResponse(
            query=request.query,
            results=[
                SemanticCourseResult(
                    course_code=course.course_code,
                    title=course.title,
                    department=course.department,
                    description=course.description,
                    section_count=len(course.sections) if course.sections else 0,
                    available_seats=course.available_seats,
                    similarity=score,
                )
                for course, score in results
            ],
            total=len(results),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/search/rag-context", response_model=RAGContextResponse, tags=["Search"])
async def get_rag_context(request: RAGContextRequest):
    """
    Get context for RAG (Retrieval Augmented Generation).

    Returns relevant courses and documents for use in LLM prompts.
    """
    try:
        embedding_service = get_embedding_service()
        context = embedding_service.get_rag_context(
            query=request.query,
            max_courses=request.max_courses,
            max_documents=request.max_documents,
        )

        return RAGContextResponse(
            query=request.query,
            courses=[RAGCourseContext(**c) for c in context.get("courses", [])],
            documents=[RAGDocumentContext(**d) for d in context.get("documents", [])],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context retrieval failed: {str(e)}")


# =============================================================================
# AI Chat Endpoint
# =============================================================================

from src.api.schemas import ChatRequest, ChatResponse as ChatResponseSchema, ChatSourceSchema

# Lazy-loaded chat service
_chat_service = None


def get_chat_service():
    """Get or create chat service."""
    global _chat_service
    if _chat_service is None:
        from src.services.ai_chat_service import get_chat_service as create_chat_service
        _chat_service = create_chat_service()
    return _chat_service


from src.api.auth import get_optional_user

@app.post("/chat", response_model=ChatResponseSchema, tags=["AI Chat"])
async def chat_with_ai(
    request: ChatRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    """
    Chat with an AI academic advisor about UGA courses and programs.

    The AI uses RAG (Retrieval Augmented Generation) to provide accurate,
    context-aware responses based on current course data, syllabi, and
    program requirements.

    When authenticated, the AI also has access to your academic profile:
    - Your completed courses
    - Your major and degree progress
    - Your GPA and hours earned

    This enables personalized recommendations like "What should I take next?"

    Example questions:
    - "What courses cover machine learning?"
    - "What are the prerequisites for CSCI 4720?"
    - "What should I take next semester?" (personalized when logged in)
    - "Am I on track to graduate?" (personalized when logged in)
    """
    try:
        chat_service = get_chat_service()

        # Convert history if provided
        history = None
        if request.history:
            from src.services.ai_chat_service import ChatMessage
            history = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in request.history
            ]

        # Get user_id if authenticated
        user_id = user.get("id") if user else None

        # Get AI response
        response = chat_service.chat(
            message=request.message,
            history=history,
            user_id=user_id,
            max_courses=request.max_courses,
            max_documents=request.max_documents,
        )

        return ChatResponseSchema(
            answer=response.answer,
            sources=[
                ChatSourceSchema(
                    type=s["type"],
                    code=s.get("code"),
                    title=s["title"],
                    source_type=s.get("source_type"),
                    similarity=s["similarity"],
                )
                for s in response.sources
            ],
            model=response.model,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.post("/admin/embed-courses", tags=["Admin"])
async def embed_courses(
    request: EmbedCoursesRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate embeddings for courses.

    This is an admin endpoint that triggers embedding generation.
    Runs in background for large datasets.
    """
    try:
        embedding_service = get_embedding_service()

        # Run embedding in background
        def run_embedding():
            count = embedding_service.embed_courses(
                schedule_id=request.schedule_id,
                force=request.force,
            )
            return count

        background_tasks.add_task(run_embedding)

        return {
            "status": "started",
            "message": "Embedding generation started in background",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# =============================================================================
# Program Endpoints
# =============================================================================

from src.api.schemas import (
    ProgramResponse,
    ProgramListResponse,
    ProgramRequirementResponse,
    RequirementCourseResponse,
    CalendarEventResponse,
    CalendarResponse,
    EnrichedProgramResponse,
    EnrichedRequirementResponse,
    EnrichedCourseInfo,
    CourseInstructorInfo,
    CourseSyllabusInfo,
)
from src.models.database import Program, ProgramRequirement, RequirementCourse, BulletinCourse


@app.get("/programs", response_model=list[ProgramListResponse], tags=["Programs"])
async def list_programs(
    degree_type: Optional[str] = Query(None, description="Filter by degree type (BS, BA, etc.)"),
    search: Optional[str] = Query(None, description="Search in program name"),
    limit: int = Query(100, ge=1, le=500),
    service: CourseService = Depends(get_service),
):
    """List all degree programs."""
    with service.session_factory() as session:
        from sqlalchemy import select
        query = select(Program)

        if degree_type:
            query = query.where(Program.degree_type == degree_type.upper())
        if search:
            query = query.where(Program.name.ilike(f"%{search}%"))

        query = query.order_by(Program.name).limit(limit)
        programs = session.execute(query).scalars().all()

        return [
            ProgramListResponse(
                id=p.id,
                name=p.name,
                degree_type=p.degree_type,
                college_code=p.college_code,
                department=p.department,
                total_hours=p.total_hours,
            )
            for p in programs
        ]


@app.get("/programs/{program_id}", response_model=ProgramResponse, tags=["Programs"])
async def get_program(
    program_id: int,
    service: CourseService = Depends(get_service),
):
    """Get detailed program information with requirements."""
    with service.session_factory() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        query = (
            select(Program)
            .options(
                joinedload(Program.requirements)
                .joinedload(ProgramRequirement.courses)
            )
            .where(Program.id == program_id)
        )
        program = session.execute(query).unique().scalar_one_or_none()

        if not program:
            raise HTTPException(status_code=404, detail=f"Program not found: {program_id}")

        return ProgramResponse(
            id=program.id,
            bulletin_id=program.bulletin_id,
            name=program.name,
            degree_type=program.degree_type,
            college_code=program.college_code,
            department=program.department,
            overview=program.overview,
            total_hours=program.total_hours,
            bulletin_url=program.bulletin_url,
            requirements=[
                ProgramRequirementResponse(
                    id=r.id,
                    name=r.name,
                    category=r.category,
                    required_hours=r.required_hours,
                    description=r.description,
                    selection_type=r.selection_type,
                    courses_to_select=r.courses_to_select,
                    courses=[
                        RequirementCourseResponse(
                            course_code=c.course_code,
                            title=c.title,
                            credit_hours=c.credit_hours,
                            is_group=c.is_group,
                            group_description=c.group_description,
                        )
                        for c in sorted(r.courses, key=lambda x: x.display_order)
                    ]
                )
                for r in sorted(program.requirements, key=lambda x: x.display_order)
            ]
        )


@app.get("/programs/by-major/{major_name}", response_model=Optional[ProgramResponse], tags=["Programs"])
async def get_program_by_major(
    major_name: str,
    service: CourseService = Depends(get_service),
):
    """
    Find a program matching a major name with fuzzy matching.

    Tries exact match first, then partial match, then keyword matching.
    Returns None if no suitable match found.
    """
    with service.session_factory() as session:
        from sqlalchemy import select, or_, func
        from sqlalchemy.orm import joinedload

        # Normalize the search term
        search_term = major_name.lower().strip()

        # Try exact match on name (case-insensitive)
        query = (
            select(Program)
            .options(
                joinedload(Program.requirements)
                .joinedload(ProgramRequirement.courses)
            )
            .where(func.lower(Program.name).contains(search_term))
            .order_by(
                # Prefer shorter names (more specific matches)
                func.length(Program.name)
            )
        )
        programs = session.execute(query).unique().scalars().all()

        if not programs:
            # Try searching by keywords
            keywords = search_term.split()
            conditions = [Program.name.ilike(f"%{kw}%") for kw in keywords]
            query = (
                select(Program)
                .options(
                    joinedload(Program.requirements)
                    .joinedload(ProgramRequirement.courses)
                )
                .where(or_(*conditions) if len(conditions) > 1 else conditions[0])
                .order_by(func.length(Program.name))
            )
            programs = session.execute(query).unique().scalars().all()

        if not programs:
            return None

        # Return the best match (shortest name that matches)
        program = programs[0]

        return ProgramResponse(
            id=program.id,
            bulletin_id=program.bulletin_id,
            name=program.name,
            degree_type=program.degree_type,
            college_code=program.college_code,
            department=program.department,
            overview=program.overview,
            total_hours=program.total_hours,
            bulletin_url=program.bulletin_url,
            requirements=[
                ProgramRequirementResponse(
                    id=r.id,
                    name=r.name,
                    category=r.category,
                    required_hours=r.required_hours,
                    description=r.description,
                    selection_type=r.selection_type,
                    courses_to_select=r.courses_to_select,
                    courses=[
                        RequirementCourseResponse(
                            course_code=c.course_code,
                            title=c.title,
                            credit_hours=c.credit_hours,
                            is_group=c.is_group,
                            group_description=c.group_description,
                        )
                        for c in sorted(r.courses, key=lambda x: x.display_order)
                    ]
                )
                for r in sorted(program.requirements, key=lambda x: x.display_order)
            ]
        )


@app.get("/programs/{program_id}/enriched", response_model=EnrichedProgramResponse, tags=["Programs"])
async def get_enriched_program(
    program_id: int,
    service: CourseService = Depends(get_service),
):
    """
    Get program with enriched course data including:
    - Bulletin descriptions and prerequisites
    - Current semester instructors
    - Available syllabi
    """
    with service.session_factory() as session:
        from sqlalchemy import select, text
        from sqlalchemy.orm import joinedload

        # Get program with requirements and courses
        query = (
            select(Program)
            .options(
                joinedload(Program.requirements)
                .joinedload(ProgramRequirement.courses)
            )
            .where(Program.id == program_id)
        )
        program = session.execute(query).unique().scalar_one_or_none()

        if not program:
            raise HTTPException(status_code=404, detail=f"Program not found: {program_id}")

        # Collect all course codes from requirements
        all_course_codes = set()
        for req in program.requirements:
            for course in req.courses:
                if not course.is_group:
                    all_course_codes.add(course.course_code)

        # Fetch bulletin data for all courses
        bulletin_data = {}
        if all_course_codes:
            bulletin_result = session.execute(
                select(BulletinCourse).where(BulletinCourse.course_code.in_(all_course_codes))
            )
            for bc in bulletin_result.scalars():
                bulletin_data[bc.course_code] = {
                    "description": bc.description,
                    "prerequisites": bc.prerequisites,
                    "bulletin_url": bc.bulletin_url,
                }

        # Fetch current semester section data (instructors + schedule)
        section_data = {}
        if all_course_codes:
            # Get sections for courses in the current schedule
            section_result = session.execute(
                text("""
                    SELECT c.course_code, s.crn, s.instructor, s.seats_available, s.class_size, s.status,
                           s.days, s.start_time, s.end_time, s.building, s.room, s.campus
                    FROM sections s
                    JOIN courses c ON s.course_id = c.id
                    JOIN schedules sch ON c.schedule_id = sch.id
                    WHERE sch.is_current = true
                    AND c.course_code = ANY(:codes)
                    AND s.status = 'A'
                    ORDER BY c.course_code, s.instructor
                """),
                {"codes": list(all_course_codes)}
            )
            for row in section_result:
                code = row[0]
                if code not in section_data:
                    section_data[code] = {"instructors": [], "total_sections": 0, "available_sections": 0, "total_seats": 0, "available_seats": 0}

                section_data[code]["total_sections"] += 1
                section_data[code]["total_seats"] += row[4]
                section_data[code]["available_seats"] += row[3]
                if row[3] > 0:
                    section_data[code]["available_sections"] += 1

                # Add instructor (one entry per section with schedule data)
                instructor_name = row[2] or "TBD"
                section_data[code]["instructors"].append({
                    "name": instructor_name,
                    "section_crn": row[1],
                    "seats_available": row[3],
                    "class_size": row[4],
                    "is_available": row[3] > 0,
                    "days": row[6],
                    "start_time": row[7],
                    "end_time": row[8],
                    "building": row[9],
                    "room": row[10],
                    "campus": row[11],
                })

        # Fetch syllabi for all courses
        syllabi_data = {}
        if all_course_codes:
            syllabi_result = session.execute(
                text("""
                    SELECT id, course_code, semester, instructor_name, syllabus_url
                    FROM syllabi
                    WHERE course_code = ANY(:codes)
                    ORDER BY course_code, semester DESC
                """),
                {"codes": list(all_course_codes)}
            )
            for row in syllabi_result:
                code = row[1]
                if code not in syllabi_data:
                    syllabi_data[code] = []
                syllabi_data[code].append({
                    "id": row[0],
                    "semester": row[2],
                    "instructor_name": row[3],
                    "syllabus_url": row[4],
                })

        # Build enriched response
        enriched_requirements = []
        for req in sorted(program.requirements, key=lambda x: x.display_order):
            enriched_courses = []
            for course in sorted(req.courses, key=lambda x: x.display_order):
                code = course.course_code
                bulletin = bulletin_data.get(code, {})
                sections = section_data.get(code, {})
                syllabi = syllabi_data.get(code, [])

                enriched_courses.append(EnrichedCourseInfo(
                    course_code=code,
                    title=course.title,
                    credit_hours=course.credit_hours,
                    is_group=course.is_group,
                    group_description=course.group_description,
                    description=bulletin.get("description"),
                    prerequisites=bulletin.get("prerequisites"),
                    bulletin_url=bulletin.get("bulletin_url"),
                    instructors=[CourseInstructorInfo(**i) for i in sections.get("instructors", [])],
                    total_sections=sections.get("total_sections", 0),
                    available_sections=sections.get("available_sections", 0),
                    total_seats=sections.get("total_seats", 0),
                    available_seats=sections.get("available_seats", 0),
                    syllabi=[CourseSyllabusInfo(**s) for s in syllabi[:5]],  # Limit to 5 most recent
                ))

            enriched_requirements.append(EnrichedRequirementResponse(
                id=req.id,
                name=req.name,
                category=req.category,
                required_hours=req.required_hours,
                description=req.description,
                selection_type=req.selection_type,
                courses_to_select=req.courses_to_select,
                courses=enriched_courses,
            ))

        return EnrichedProgramResponse(
            id=program.id,
            bulletin_id=program.bulletin_id,
            name=program.name,
            degree_type=program.degree_type,
            college_code=program.college_code,
            department=program.department,
            overview=program.overview,
            total_hours=program.total_hours,
            bulletin_url=program.bulletin_url,
            requirements=enriched_requirements,
        )


@app.get("/programs/{program_id}/possibilities", response_model=PossibilitiesResponse, tags=["Programs"])
async def get_course_possibilities(
    program_id: int,
    goal: str = Query("flexible", description="Student goal: fast-track, specialist, well-rounded, flexible"),
    completed: Optional[str] = Query(None, description="Comma-separated completed course codes"),
    limit: int = Query(50, ge=1, le=200, description="Maximum courses to return"),
    service: CourseService = Depends(get_service),
):
    """
    Get course possibilities for a student based on their goal and progress.

    Returns prioritized courses the student CAN take (prerequisites met)
    and SHOULD take (aligned with their goal type).

    Filters out:
    - Courses with no available seats
    - Courses where prerequisites are not met
    - Already completed courses
    """
    from src.services.possibilities_service import PossibilitiesService, GoalType

    # Parse goal
    try:
        goal_type = GoalType(goal)
    except ValueError:
        goal_type = GoalType.FLEXIBLE

    # Parse completed courses
    completed_list = []
    if completed:
        completed_list = [c.strip().upper() for c in completed.split(",") if c.strip()]

    # Get possibilities
    possibilities_service = PossibilitiesService(service.session_factory)
    result = possibilities_service.get_possibilities(
        program_id=program_id,
        goal=goal_type,
        completed_courses=completed_list,
        limit=limit,
    )

    return PossibilitiesResponse(
        possibilities=[
            CoursePossibilityResponse(
                course_code=p.course_code,
                title=p.title,
                credit_hours=p.credit_hours,
                category=p.category,
                requirement_name=p.requirement_name,
                total_sections=p.total_sections,
                available_sections=p.available_sections,
                total_seats=p.total_seats,
                available_seats=p.available_seats,
                prerequisites_met=p.prerequisites_met,
                missing_prerequisites=p.missing_prerequisites,
                priority_score=p.priority_score,
                priority_reason=p.priority_reason,
                sections=[
                    PossibilitySectionResponse(
                        crn=s.crn,
                        instructor=s.instructor,
                        days=s.days,
                        start_time=s.start_time,
                        end_time=s.end_time,
                        building=s.building,
                        room=s.room,
                        seats_available=s.seats_available,
                        class_size=s.class_size,
                    )
                    for s in p.sections
                ],
            )
            for p in result.possibilities
        ],
        total_available=result.total_available,
        total_eligible=result.total_eligible,
        filters_applied=result.filters_applied,
    )


# =============================================================================
# Calendar Endpoints
# =============================================================================

@app.get("/calendar", response_model=CalendarResponse, tags=["Calendar"])
async def get_calendar_events(
    semester: Optional[str] = Query(None, description="Filter by semester"),
    category: Optional[str] = Query(None, description="Filter by category (fees, academic, etc.)"),
    limit: int = Query(50, ge=1, le=200),
    service: CourseService = Depends(get_service),
):
    """Get academic calendar events."""
    with service.session_factory() as session:
        from sqlalchemy import select, text

        # Check if academic_calendar table exists
        result = session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'academic_calendar')"
        ))
        if not result.scalar():
            return CalendarResponse(events=[], total=0)

        # Build query
        query = "SELECT id, event, date, semester, category, source FROM academic_calendar WHERE 1=1"
        params = {}

        if semester:
            query += " AND semester ILIKE :semester"
            params["semester"] = f"%{semester}%"
        if category:
            query += " AND category ILIKE :category"
            params["category"] = f"%{category}%"

        query += " ORDER BY id LIMIT :limit"
        params["limit"] = limit

        result = session.execute(text(query), params)
        rows = result.fetchall()

        events = [
            CalendarEventResponse(
                id=row[0],
                event=row[1],
                date=row[2],
                semester=row[3],
                category=row[4],
                source=row[5],
            )
            for row in rows
        ]

        return CalendarResponse(events=events, total=len(events))


@app.get("/calendar/upcoming", response_model=CalendarResponse, tags=["Calendar"])
async def get_upcoming_events(
    limit: int = Query(10, ge=1, le=50),
    service: CourseService = Depends(get_service),
):
    """
    Get upcoming calendar events.

    Filters to show fee deadlines and important academic dates for current/future semesters.
    """
    from datetime import datetime

    with service.session_factory() as session:
        from sqlalchemy import text

        # Check if academic_calendar table exists
        result = session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'academic_calendar')"
        ))
        if not result.scalar():
            return CalendarResponse(events=[], total=0)

        # Determine current semester based on date
        now = datetime.now()
        current_year = now.year
        # Spring: Jan-May, Summer: May-Aug, Fall: Aug-Dec
        if now.month <= 5:
            current_semester = f"Spring {current_year}"
            next_semester = f"Summer {current_year}"
        elif now.month <= 8:
            current_semester = f"Summer {current_year}"
            next_semester = f"Fall {current_year}"
        else:
            current_semester = f"Fall {current_year}"
            next_semester = f"Spring {current_year + 1}"

        # Get fee deadlines and important dates for current/upcoming semesters
        query = """
            SELECT id, event, date, semester, category, source
            FROM academic_calendar
            WHERE (category = 'fees' OR source LIKE '%deadline%' OR event ILIKE '%deadline%' OR event ILIKE '%last day%')
            AND event NOT LIKE 'MARK%'
            AND event NOT LIKE 'Juniors%'
            AND event NOT LIKE 'Seniors%'
            AND (semester = :current_semester OR semester = :next_semester
                 OR semester LIKE :future_spring OR semester LIKE :future_fall)
            ORDER BY
                CASE
                    WHEN semester = :current_semester THEN 1
                    WHEN semester = :next_semester THEN 2
                    ELSE 3
                END,
                id
            LIMIT :limit
        """

        result = session.execute(text(query), {
            "limit": limit,
            "current_semester": current_semester,
            "next_semester": next_semester,
            "future_spring": f"Spring {current_year + 1}%",
            "future_fall": f"Fall {current_year + 1}%",
        })
        rows = result.fetchall()

        events = [
            CalendarEventResponse(
                id=row[0],
                event=row[1],
                date=row[2],
                semester=row[3],
                category=row[4],
                source=row[5],
            )
            for row in rows
        ]

        return CalendarResponse(events=events, total=len(events))


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats(service: CourseService = Depends(get_service)):
    """Get overall schedule statistics."""
    stats = service.get_stats()
    if not stats:
        raise HTTPException(status_code=404, detail="No schedule found")
    return StatsResponse(**stats)


# =============================================================================
# Professor Endpoints
# =============================================================================

from src.api.schemas import (
    ProfessorResponse,
    ProfessorListResponse,
    ProfessorCourseResponse,
    SyllabusResponse,
    SyllabusListResponse,
)
from src.models.database import Professor, ProfessorCourse, Department


@app.get("/professors", response_model=list[ProfessorListResponse], tags=["Professors"])
async def list_professors(
    search: Optional[str] = Query(None, description="Search by name"),
    department: Optional[str] = Query(None, description="Filter by department code"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: CourseService = Depends(get_service),
):
    """List professors with optional filters."""
    with service.session_factory() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        query = select(Professor).options(joinedload(Professor.department), joinedload(Professor.instructor))

        if search:
            query = query.where(Professor.name.ilike(f"%{search}%"))
        if department:
            query = query.join(Department).where(Department.code == department.upper())

        query = query.order_by(Professor.last_name, Professor.first_name).limit(limit).offset(offset)
        professors = session.execute(query).unique().scalars().all()

        return [
            ProfessorListResponse(
                id=p.id,
                name=p.name,
                title=p.title,
                email=p.email,
                department_name=p.department.name if p.department else None,
                photo_url=p.photo_url,
                rmp_rating=p.instructor.rmp_rating if p.instructor else None,
            )
            for p in professors
        ]


@app.get("/professors/{professor_id}", response_model=ProfessorResponse, tags=["Professors"])
async def get_professor(
    professor_id: int,
    service: CourseService = Depends(get_service),
):
    """Get detailed professor profile."""
    with service.session_factory() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        query = (
            select(Professor)
            .options(
                joinedload(Professor.department),
                joinedload(Professor.instructor),
                joinedload(Professor.courses_taught),
            )
            .where(Professor.id == professor_id)
        )
        professor = session.execute(query).unique().scalar_one_or_none()

        if not professor:
            raise HTTPException(status_code=404, detail=f"Professor not found: {professor_id}")

        return ProfessorResponse(
            id=professor.id,
            name=professor.name,
            first_name=professor.first_name,
            last_name=professor.last_name,
            title=professor.title,
            email=professor.email,
            phone=professor.phone,
            office_location=professor.office_location,
            office_hours=professor.office_hours,
            photo_url=professor.photo_url,
            profile_url=professor.profile_url,
            bio=professor.bio,
            research_areas=professor.research_areas,
            education=professor.education,
            cv_url=professor.cv_url,
            personal_website=professor.personal_website,
            department_name=professor.department.name if professor.department else None,
            rmp_rating=professor.instructor.rmp_rating if professor.instructor else None,
            rmp_difficulty=professor.instructor.rmp_difficulty if professor.instructor else None,
            rmp_num_ratings=professor.instructor.rmp_num_ratings if professor.instructor else None,
        )


@app.get("/professors/{professor_id}/courses", response_model=list[ProfessorCourseResponse], tags=["Professors"])
async def get_professor_courses(
    professor_id: int,
    service: CourseService = Depends(get_service),
):
    """Get courses taught by a professor."""
    with service.session_factory() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        query = (
            select(ProfessorCourse)
            .options(joinedload(ProfessorCourse.bulletin_course))
            .where(ProfessorCourse.professor_id == professor_id)
            .order_by(ProfessorCourse.course_code)
        )
        courses = session.execute(query).unique().scalars().all()

        return [
            ProfessorCourseResponse(
                course_code=c.course_code,
                title=c.bulletin_course.title if c.bulletin_course else None,
                semesters_taught=c.semesters_taught,
                times_taught=c.times_taught,
            )
            for c in courses
        ]


@app.get("/professors/by-name/{name}", response_model=Optional[ProfessorResponse], tags=["Professors"])
async def get_professor_by_name(
    name: str,
    service: CourseService = Depends(get_service),
):
    """Find a professor by name with fuzzy matching."""
    with service.session_factory() as session:
        from sqlalchemy import select, func
        from sqlalchemy.orm import joinedload

        # Try exact match first
        query = (
            select(Professor)
            .options(joinedload(Professor.department), joinedload(Professor.instructor))
            .where(func.lower(Professor.name) == name.lower())
        )
        professor = session.execute(query).unique().scalar_one_or_none()

        if not professor:
            # Try partial match
            query = (
                select(Professor)
                .options(joinedload(Professor.department), joinedload(Professor.instructor))
                .where(Professor.name.ilike(f"%{name}%"))
                .order_by(func.length(Professor.name))
            )
            professor = session.execute(query).unique().scalars().first()

        if not professor:
            return None

        return ProfessorResponse(
            id=professor.id,
            name=professor.name,
            first_name=professor.first_name,
            last_name=professor.last_name,
            title=professor.title,
            email=professor.email,
            phone=professor.phone,
            office_location=professor.office_location,
            office_hours=professor.office_hours,
            photo_url=professor.photo_url,
            profile_url=professor.profile_url,
            bio=professor.bio,
            research_areas=professor.research_areas,
            education=professor.education,
            cv_url=professor.cv_url,
            personal_website=professor.personal_website,
            department_name=professor.department.name if professor.department else None,
            rmp_rating=professor.instructor.rmp_rating if professor.instructor else None,
            rmp_difficulty=professor.instructor.rmp_difficulty if professor.instructor else None,
            rmp_num_ratings=professor.instructor.rmp_num_ratings if professor.instructor else None,
        )


# =============================================================================
# Syllabus Endpoints
# =============================================================================

@app.get("/syllabi", response_model=SyllabusListResponse, tags=["Syllabi"])
async def list_syllabi(
    course_code: Optional[str] = Query(None, description="Filter by course code"),
    instructor: Optional[str] = Query(None, description="Filter by instructor name"),
    semester: Optional[str] = Query(None, description="Filter by semester"),
    department: Optional[str] = Query(None, description="Filter by department"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: CourseService = Depends(get_service),
):
    """List syllabi with optional filters."""
    with service.session_factory() as session:
        from sqlalchemy import text

        query = "SELECT * FROM syllabi WHERE 1=1"
        params = {}

        if course_code:
            query += " AND course_code ILIKE :course_code"
            params["course_code"] = f"%{course_code}%"
        if instructor:
            query += " AND instructor_name ILIKE :instructor"
            params["instructor"] = f"%{instructor}%"
        if semester:
            query += " AND semester ILIKE :semester"
            params["semester"] = f"%{semester}%"
        if department:
            query += " AND department = :department"
            params["department"] = department.upper()

        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total = session.execute(text(count_query), params).scalar()

        # Get paginated results
        query += " ORDER BY course_code LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        result = session.execute(text(query), params)
        rows = result.fetchall()
        cols = result.keys()

        syllabi = [
            SyllabusResponse(
                id=row[0],
                course_code=row[1],
                course_title=row[2],
                section=row[3],
                semester=row[4],
                instructor_name=row[5],
                syllabus_url=row[6],
                cv_url=row[7],
                department=row[8],
                file_name=row[12],
                file_type=row[13],
            )
            for row in rows
        ]

        return SyllabusListResponse(syllabi=syllabi, total=total)


@app.get("/syllabi/course/{course_code}", response_model=SyllabusListResponse, tags=["Syllabi"])
async def get_syllabi_for_course(
    course_code: str,
    service: CourseService = Depends(get_service),
):
    """Get all syllabi for a specific course."""
    with service.session_factory() as session:
        from sqlalchemy import text

        # Normalize course code
        code = course_code.upper().replace("-", " ")
        if " " not in code:
            import re
            code = re.sub(r"([A-Z]+)(\d+)", r"\1 \2", code)

        result = session.execute(
            text("SELECT * FROM syllabi WHERE course_code = :code ORDER BY semester DESC"),
            {"code": code}
        )
        rows = result.fetchall()

        syllabi = [
            SyllabusResponse(
                id=row[0],
                course_code=row[1],
                course_title=row[2],
                section=row[3],
                semester=row[4],
                instructor_name=row[5],
                syllabus_url=row[6],
                cv_url=row[7],
                department=row[8],
                file_name=row[12],
                file_type=row[13],
            )
            for row in rows
        ]

        return SyllabusListResponse(syllabi=syllabi, total=len(syllabi))


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """Run the API server."""
    import uvicorn
    from src.config import settings
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
