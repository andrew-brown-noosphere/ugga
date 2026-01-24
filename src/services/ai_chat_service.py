"""
AI Chat Service using Anthropic Claude with RAG context.

Provides conversational AI responses about UGA courses, programs, and academic planning.
Supports personalized responses when user context is provided.
"""
import anthropic
from typing import Optional
from dataclasses import dataclass

from src.config import settings
from src.services.embedding_service import create_embedding_service
from src.services.progress_service import ProgressService


@dataclass
class ChatMessage:
    """A message in the chat history."""
    role: str  # "user" or "assistant"
    content: str


@dataclass
class ChatResponse:
    """Response from the AI chat."""
    answer: str
    sources: list[dict]  # Courses and documents used for context
    model: str


SYSTEM_PROMPT = """You are an AI academic advisor for the University of Georgia (UGA). You help students with:
- Finding courses that match their interests
- Understanding degree requirements
- Planning their academic schedule
- Learning about professors and their courses
- Answering questions about prerequisites and course content

IMPORTANT GUIDELINES:
1. Base your answers on the provided context (courses, syllabi, program data, student profile)
2. If the context doesn't contain enough information, say so honestly
3. Always mention specific course codes (e.g., CSCI 1302) when recommending courses
4. Include relevant details like prerequisites, credit hours, and availability when helpful
5. Be concise but thorough
6. If asked about a specific professor, use the data provided about them
7. Remind students to verify information with their academic advisor for official decisions
8. When student profile data is available, personalize your recommendations based on their completed courses and degree progress
9. Check prerequisites against the student's completed courses when recommending classes

DISCLAIMER: Always include this at the end of responses involving academic planning:
"Note: This is AI-generated guidance. Please verify with your academic advisor and the official UGA Bulletin."

You have access to:
- Current semester course schedules with availability
- Course descriptions and prerequisites from the UGA Bulletin
- Syllabus content from various courses
- Degree program requirements
- Professor information and ratings
- Student's academic profile (when logged in): completed courses, major, GPA, degree progress"""


class AIChatService:
    """Service for AI-powered chat about UGA academics."""

    def __init__(self):
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.embedding_service = create_embedding_service()
        self.progress_service = ProgressService()
        self.model = "claude-sonnet-4-20250514"

    def _get_user_context(self, user_id: int) -> tuple[str, set[str]]:
        """
        Build user context string from their academic profile.

        Returns:
            Tuple of (context_string, set_of_completed_course_codes)
        """
        from sqlalchemy import select
        from src.models.database import (
            get_session_factory, User, Program,
            UserProgramEnrollment, UserTranscriptSummary
        )

        context_parts = []
        completed_codes = set()

        session_factory = get_session_factory()
        with session_factory() as session:
            # Get user info
            user = session.get(User, user_id)
            if not user:
                return "", completed_codes

            context_parts.append("## Your Academic Profile\n")

            if user.first_name:
                context_parts.append(f"**Name:** {user.first_name} {user.last_name or ''}\n")

            # Get completed courses
            completed_courses = self.progress_service.get_completed_courses(user_id)
            completed_codes = {c.course_code for c in completed_courses}

            if completed_courses:
                # Group by semester for cleaner display
                courses_by_semester = {}
                for course in completed_courses:
                    sem_key = course.semester or "Unknown"
                    if sem_key not in courses_by_semester:
                        courses_by_semester[sem_key] = []
                    grade_str = f" ({course.grade})" if course.grade else ""
                    courses_by_semester[sem_key].append(f"{course.course_code}{grade_str}")

                context_parts.append(f"**Completed Courses:** {len(completed_courses)} courses\n")
                for semester, courses in sorted(courses_by_semester.items(), reverse=True):
                    context_parts.append(f"- {semester}: {', '.join(courses)}\n")
            else:
                context_parts.append("**Completed Courses:** None recorded yet\n")

            # Get transcript summary
            summary = self.progress_service.get_transcript_summary(user_id)
            if summary:
                context_parts.append(f"\n**Academic Standing:**\n")
                context_parts.append(f"- Total Hours Earned: {summary.total_hours_earned}\n")
                if summary.cumulative_gpa is not None:
                    context_parts.append(f"- Cumulative GPA: {summary.cumulative_gpa:.2f}\n")
                context_parts.append(f"- Upper Division Hours: {summary.upper_division_hours}\n")

            # Get program enrollment
            enrollment = self.progress_service.get_primary_enrollment(user_id)
            if enrollment:
                # Get program details
                program = session.get(Program, enrollment.program_id)
                if program:
                    context_parts.append(f"\n**Major:** {program.name} ({program.degree_type})\n")
                    if program.total_hours:
                        hours_remaining = program.total_hours - (summary.total_hours_earned if summary else 0)
                        context_parts.append(f"- Required Hours: {program.total_hours}\n")
                        context_parts.append(f"- Hours Remaining: {max(0, hours_remaining)}\n")
                    if enrollment.catalog_year:
                        context_parts.append(f"- Catalog Year: {enrollment.catalog_year}\n")
            elif user.major:
                context_parts.append(f"\n**Major (from profile):** {user.major}\n")

            context_parts.append("\n")

        return "".join(context_parts), completed_codes

    def _extract_course_codes(self, query: str) -> list[str]:
        """Extract course codes mentioned in the query (e.g., CSCI 1302, CHEM 2211)."""
        import re
        # Match patterns like "CSCI 1302", "CHEM 2211L", "BCMB 3100"
        pattern = r'\b([A-Z]{2,4})\s*(\d{4}[A-Z]?)\b'
        matches = re.findall(pattern, query.upper())
        return [f"{subj} {num}" for subj, num in matches]

    def _get_courses_by_codes(self, codes: list[str]) -> list[dict]:
        """Get bulletin course details for specific course codes."""
        from sqlalchemy import select
        from src.models.database import get_session_factory, BulletinCourse, Course

        if not codes:
            return []

        session_factory = get_session_factory()
        courses_info = []

        with session_factory() as session:
            for code in codes:
                # Try bulletin first (has prerequisites)
                bulletin = session.execute(
                    select(BulletinCourse).where(BulletinCourse.course_code == code)
                ).scalar_one_or_none()

                if bulletin:
                    # Check if offered this semester
                    current = session.execute(
                        select(Course).where(Course.course_code == code)
                    ).scalar_one_or_none()

                    courses_info.append({
                        "course_code": bulletin.course_code,
                        "title": bulletin.title,
                        "description": bulletin.description,
                        "prerequisites": bulletin.prerequisites,
                        "corequisites": bulletin.corequisites,
                        "credit_hours": bulletin.credit_hours,
                        "offered_this_semester": current is not None,
                        "source": "bulletin",
                    })

        return courses_info

    def _detect_credit_hours_query(self, query: str) -> int | None:
        """Detect if query is asking about specific credit hours."""
        import re
        query_lower = query.lower()

        # Match patterns like "1 credit", "one credit", "1-credit", "2 hour course"
        patterns = [
            (r'\b(one|1)\s*(credit|hour|hr)', 1),
            (r'\b(two|2)\s*(credit|hour|hr)', 2),
            (r'\b(three|3)\s*(credit|hour|hr)', 3),
            (r'\b(\d+)\s*-?\s*(credit|hour|hr)', None),  # Generic number
        ]

        for pattern, hours in patterns:
            match = re.search(pattern, query_lower)
            if match:
                if hours is not None:
                    return hours
                else:
                    return int(match.group(1))
        return None

    def _get_courses_by_credit_hours(self, credit_hours: int, exclude_prefix: str | None = None, limit: int = 15) -> list[dict]:
        """Get courses filtered by credit hours."""
        from sqlalchemy import text
        from src.models.database import get_session_factory

        session_factory = get_session_factory()
        with session_factory() as session:
            exclude_clause = ""
            if exclude_prefix:
                exclude_clause = f"AND c.course_code NOT LIKE '{exclude_prefix}%'"

            result = session.execute(text(f'''
                SELECT DISTINCT c.course_code, c.title, c.department, s.credit_hours,
                       COUNT(s.id) as section_count,
                       SUM(s.seats_available) as available_seats
                FROM courses c
                JOIN sections s ON s.course_id = c.id
                JOIN schedules sch ON c.schedule_id = sch.id
                WHERE s.credit_hours = :credit_hours
                AND sch.is_current = true
                AND s.status = 'A'
                {exclude_clause}
                GROUP BY c.course_code, c.title, c.department, s.credit_hours
                HAVING SUM(s.seats_available) > 0
                ORDER BY section_count DESC, available_seats DESC
                LIMIT :limit
            '''), {"credit_hours": credit_hours, "limit": limit})

            courses = []
            for row in result:
                courses.append({
                    "course_code": row[0],
                    "title": row[1],
                    "department": row[2],
                    "credit_hours": row[3],
                    "sections": row[4],
                    "available_seats": row[5],
                })
            return courses

    def _build_context(self, query: str, max_courses: int = 8, max_documents: int = 5) -> tuple[str, list[dict]]:
        """Build context string from RAG retrieval."""
        sources = []
        context_parts = []

        # Extract and include any specifically mentioned course codes
        mentioned_codes = self._extract_course_codes(query)
        if mentioned_codes:
            mentioned_courses = self._get_courses_by_codes(mentioned_codes)
            if mentioned_courses:
                context_parts.append("## Courses Mentioned in Question\n")
                for course in mentioned_courses:
                    offered = "✓ Offered this semester" if course.get("offered_this_semester") else "Not in current schedule"
                    prereqs = course.get("prerequisites") or "None listed"
                    coreqs = course.get("corequisites") or "None"

                    course_info = f"""
### {course['course_code']} - {course['title']}
- **Prerequisites:** {prereqs}
- **Corequisites:** {coreqs}
- **Credit Hours:** {course.get('credit_hours', 'N/A')}
- **Status:** {offered}
- **Description:** {(course.get('description') or 'No description')[:300]}...
"""
                    context_parts.append(course_info)
                    sources.append({
                        "type": "course",
                        "code": course["course_code"],
                        "title": course["title"],
                        "similarity": 1.0,  # Direct mention
                    })
                context_parts.append("\n")

        # Check for credit hours specific query
        credit_hours = self._detect_credit_hours_query(query)
        if credit_hours:
            # Detect if PEDB should be excluded
            exclude_prefix = "PEDB" if "pedb" in query.lower() or "physical education" in query.lower() else None

            credit_courses = self._get_courses_by_credit_hours(credit_hours, exclude_prefix)
            if credit_courses:
                context_parts.append(f"## {credit_hours}-Credit Courses Currently Available\n")
                for course in credit_courses:
                    course_info = f"- **{course['course_code']}**: {course['title']} ({course['sections']} sections, {course['available_seats']} seats available)\n"
                    context_parts.append(course_info)
                    sources.append({
                        "type": "course",
                        "code": course["course_code"],
                        "title": course["title"],
                        "similarity": 1.0,  # Direct match
                    })
                context_parts.append("\n")

        # Get RAG context
        try:
            rag_context = self.embedding_service.get_rag_context(
                query=query,
                max_courses=max_courses,
                max_documents=max_documents,
            )

            # Format course context
            if rag_context.get("courses"):
                context_parts.append("## Relevant Courses\n")
                for course in rag_context["courses"]:
                    course_info = f"""
### {course['course_code']} - {course['title']}
- Department: {course.get('department', 'N/A')}
- Sections: {course.get('sections', 0)} | Available Seats: {course.get('available_seats', 0)}
- Description: {course.get('description', 'No description available')}
"""
                    context_parts.append(course_info)
                    sources.append({
                        "type": "course",
                        "code": course["course_code"],
                        "title": course["title"],
                        "similarity": course.get("similarity", 0),
                    })

            # Format document context (syllabi, etc.)
            if rag_context.get("documents"):
                context_parts.append("\n## Related Documents (Syllabi, etc.)\n")
                for doc in rag_context["documents"]:
                    doc_info = f"""
### {doc['title']}
Source: {doc.get('source_type', 'document')}
Content excerpt: {doc.get('content', '')[:500]}...
"""
                    context_parts.append(doc_info)
                    sources.append({
                        "type": "document",
                        "title": doc["title"],
                        "source_type": doc.get("source_type"),
                        "similarity": doc.get("similarity", 0),
                    })

        except Exception as e:
            context_parts.append(f"[Note: Could not retrieve full context: {str(e)}]")

        return "\n".join(context_parts), sources

    def chat(
        self,
        message: str,
        history: Optional[list[ChatMessage]] = None,
        user_id: Optional[int] = None,
        max_courses: int = 8,
        max_documents: int = 5,
    ) -> ChatResponse:
        """
        Generate an AI response to a student question.

        Args:
            message: The user's question
            history: Optional conversation history
            user_id: Optional user ID for personalized context
            max_courses: Maximum courses to include in context
            max_documents: Maximum documents to include in context

        Returns:
            ChatResponse with answer and sources
        """
        # Build context from RAG
        context, sources = self._build_context(message, max_courses, max_documents)

        # Add user context if authenticated
        user_context = ""
        completed_codes: set[str] = set()
        if user_id:
            user_context, completed_codes = self._get_user_context(user_id)

        # Build messages for Claude
        messages = []

        # Add history if provided
        if history:
            for msg in history[-10:]:  # Limit to last 10 messages
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        # Add current message with context
        context_sections = []
        if user_context:
            context_sections.append(user_context)
        context_sections.append(context)

        full_context = "\n".join(context_sections)

        # Add prerequisite check hint if user has completed courses
        prereq_note = ""
        if completed_codes:
            prereq_note = f"\n\nNote: The student has completed {len(completed_codes)} courses. When recommending courses, check if prerequisites are satisfied by their completed coursework."

        user_message = f"""Here is relevant context from the UGA course database:

{full_context}
{prereq_note}
---

Student Question: {message}

Please provide a helpful, personalized response based on the context above."""

        messages.append({
            "role": "user",
            "content": user_message,
        })

        # Call Claude
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        answer = response.content[0].text

        return ChatResponse(
            answer=answer,
            sources=sources,
            model=self.model,
        )

    def quick_answer(self, question: str) -> str:
        """Get a quick answer without returning sources."""
        response = self.chat(question)
        return response.answer


# Singleton instance
_chat_service: Optional[AIChatService] = None


def get_chat_service() -> AIChatService:
    """Get or create the chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = AIChatService()
    return _chat_service
