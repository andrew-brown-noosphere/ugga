"""
SQLAlchemy database models for UGA Course Scheduler.

PostgreSQL with pgvector for:
- Course/section data storage
- Vector embeddings for semantic search (RAG)
- Instructor data with RMP integration
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Float,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    relationship,
    sessionmaker,
    Mapped,
    mapped_column,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

from src.config import settings


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Schedule(Base):
    """
    Represents a parsed schedule import/snapshot.

    Each time we import a PDF, we create a new schedule record.
    This allows tracking changes over time.
    """
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_hash: Mapped[Optional[str]] = mapped_column(String(64))
    parse_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    report_date: Mapped[Optional[str]] = mapped_column(String(50))
    total_courses: Mapped[int] = mapped_column(Integer, default=0)
    total_sections: Mapped[int] = mapped_column(Integer, default=0)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Relationships
    courses: Mapped[list["Course"]] = relationship(
        "Course", back_populates="schedule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Schedule(id={self.id}, term='{self.term}', courses={self.total_courses})>"


class Course(Base):
    """
    Represents a course (e.g., CSCI 1301).

    Includes vector embeddings for semantic search.
    """
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"), index=True)

    # Course identification
    subject: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    course_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(200))
    bulletin_url: Mapped[Optional[str]] = mapped_column(String(500))
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Extended description (can be populated from bulletin)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prerequisites: Mapped[Optional[str]] = mapped_column(Text)

    # Vector embedding for semantic search (pgvector)
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Relationships
    schedule: Mapped["Schedule"] = relationship("Schedule", back_populates="courses")
    sections: Mapped[list["Section"]] = relationship(
        "Section", back_populates="course", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_courses_subject_number", "subject", "course_number"),
        Index("ix_courses_schedule_code", "schedule_id", "course_code"),
    )

    @property
    def total_seats(self) -> int:
        return sum(s.class_size for s in self.sections)

    @property
    def available_seats(self) -> int:
        return sum(max(0, s.seats_available) for s in self.sections)

    @property
    def has_availability(self) -> bool:
        return any(s.is_available for s in self.sections)

    @property
    def embedding_text(self) -> str:
        """Text to use for generating embeddings."""
        parts = [
            f"{self.course_code}: {self.title}",
            f"Department: {self.department}" if self.department else "",
            self.description or "",
            f"Prerequisites: {self.prerequisites}" if self.prerequisites else "",
        ]
        return "\n".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<Course(id={self.id}, code='{self.course_code}', title='{self.title[:30]}')>"


class Section(Base):
    """
    Represents a specific section of a course.
    """
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    # Section identification
    crn: Mapped[str] = mapped_column(String(10), nullable=False)
    section_code: Mapped[str] = mapped_column(String(10), default="")

    # Status and details
    status: Mapped[str] = mapped_column(String(5), nullable=False)
    credit_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    credit_hours_min: Mapped[Optional[int]] = mapped_column(Integer)
    credit_hours_max: Mapped[Optional[int]] = mapped_column(Integer)

    # Instructor
    instructor: Mapped[Optional[str]] = mapped_column(String(100))

    # Term info
    part_of_term: Mapped[str] = mapped_column(String(50), default="Full Term")

    # Schedule info (days, times, location)
    days: Mapped[Optional[str]] = mapped_column(String(20))  # e.g., "M W F", "T R"
    start_time: Mapped[Optional[str]] = mapped_column(String(20))  # e.g., "09:00 am"
    end_time: Mapped[Optional[str]] = mapped_column(String(20))  # e.g., "09:50 am"
    building: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., "Boyd GSRC"
    room: Mapped[Optional[str]] = mapped_column(String(20))  # e.g., "0306"
    campus: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., "Athens", "Tifton"

    # Enrollment
    class_size: Mapped[int] = mapped_column(Integer, default=0)
    seats_available: Mapped[int] = mapped_column(Integer, default=0)
    waitlist_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    course: Mapped["Course"] = relationship("Course", back_populates="sections")

    # Indexes
    __table_args__ = (
        Index("ix_sections_crn_course", "crn", "course_id"),
        Index("ix_sections_instructor", "instructor"),
        Index("ix_sections_status_available", "status", "seats_available"),
    )

    @property
    def is_available(self) -> bool:
        return self.seats_available > 0 and self.status == 'A'

    @property
    def is_active(self) -> bool:
        return self.status == 'A'

    @property
    def is_cancelled(self) -> bool:
        return self.status == 'X'

    def __repr__(self) -> str:
        return f"<Section(id={self.id}, crn='{self.crn}', instructor='{self.instructor}')>"


class Instructor(Base):
    """
    Instructor lookup table with Rate My Professor integration.
    """
    __tablename__ = "instructors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Rate My Professor data
    rmp_id: Mapped[Optional[str]] = mapped_column(String(50))
    rmp_rating: Mapped[Optional[float]] = mapped_column(Float)
    rmp_difficulty: Mapped[Optional[float]] = mapped_column(Float)
    rmp_num_ratings: Mapped[Optional[int]] = mapped_column(Integer)
    rmp_would_take_again: Mapped[Optional[float]] = mapped_column(Float)
    rmp_last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Tags from RMP (e.g., "tough grader", "amazing lectures")
    rmp_tags: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)

    def __repr__(self) -> str:
        return f"<Instructor(id={self.id}, name='{self.name}')>"


# =============================================================================
# Faculty Directory Models (Professor Profiles)
# =============================================================================

class Department(Base):
    """
    Academic department at UGA.

    Used to organize faculty and track scraping sources.
    """
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Department identification
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # e.g., "CSCI", "CMLT"

    # Parent organization
    college: Mapped[Optional[str]] = mapped_column(String(200))  # e.g., "Franklin College of Arts and Sciences"
    school: Mapped[Optional[str]] = mapped_column(String(200))  # e.g., "School of Computing"

    # URLs for scraping
    website_url: Mapped[Optional[str]] = mapped_column(String(500))
    faculty_directory_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Contact info
    email: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    address: Mapped[Optional[str]] = mapped_column(Text)

    # Scraping metadata
    last_scraped: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    professors: Mapped[list["Professor"]] = relationship("Professor", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, name='{self.name}')>"


class Professor(Base):
    """
    Faculty member profile from department directories.

    Contains detailed information scraped from faculty pages.
    Can be linked to Instructor for RMP data and Section for teaching history.
    """
    __tablename__ = "professors"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Link to department
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), index=True)

    # Link to existing instructor record (for RMP data)
    instructor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("instructors.id"), index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Title and position
    title: Mapped[Optional[str]] = mapped_column(String(200))  # e.g., "Associate Professor"
    position_type: Mapped[Optional[str]] = mapped_column(String(50))  # professor, lecturer, instructor, emeritus
    is_department_head: Mapped[bool] = mapped_column(Boolean, default=False)

    # Contact
    email: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    office_location: Mapped[Optional[str]] = mapped_column(String(200))
    office_hours: Mapped[Optional[str]] = mapped_column(Text)

    # Profile
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    profile_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio: Mapped[Optional[str]] = mapped_column(Text)

    # Academic info
    research_areas: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    education: Mapped[Optional[str]] = mapped_column(Text)  # JSON or text description
    publications_url: Mapped[Optional[str]] = mapped_column(String(500))
    cv_url: Mapped[Optional[str]] = mapped_column(String(500))
    personal_website: Mapped[Optional[str]] = mapped_column(String(500))

    # Vector embedding for semantic search (find professors by research interest)
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Timestamps
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Profile claim (for instructors to claim their profile)
    claimed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    claim_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    claim_status: Mapped[str] = mapped_column(String(20), default="unclaimed")  # unclaimed, pending, approved
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="professors")
    instructor: Mapped[Optional["Instructor"]] = relationship("Instructor")
    courses_taught: Mapped[list["ProfessorCourse"]] = relationship("ProfessorCourse", back_populates="professor")
    claimed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[claimed_by_user_id])

    __table_args__ = (
        Index("ix_professors_name", "last_name", "first_name"),
        Index("ix_professors_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<Professor(id={self.id}, name='{self.name}', title='{self.title}')>"


class ProfessorCourse(Base):
    """
    Links professors to courses they teach.

    Can be populated from:
    - Schedule data (who taught what section)
    - Syllabus system (who uploaded syllabus for what course)
    - Department pages (listed courses)
    """
    __tablename__ = "professor_courses"

    id: Mapped[int] = mapped_column(primary_key=True)

    professor_id: Mapped[int] = mapped_column(ForeignKey("professors.id"), index=True)

    # Course can be linked by code or bulletin_course_id
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    bulletin_course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bulletin_courses.id"))

    # Teaching info
    semesters_taught: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)  # ["Fall 2024", "Spring 2024"]
    times_taught: Mapped[int] = mapped_column(Integer, default=1)
    is_primary_instructor: Mapped[bool] = mapped_column(Boolean, default=True)

    # Source of this data
    source: Mapped[str] = mapped_column(String(50), default="schedule")  # schedule, syllabus, directory

    # Relationships
    professor: Mapped["Professor"] = relationship("Professor", back_populates="courses_taught")
    bulletin_course: Mapped[Optional["BulletinCourse"]] = relationship("BulletinCourse")

    __table_args__ = (
        Index("ix_prof_course", "professor_id", "course_code"),
    )

    def __repr__(self) -> str:
        return f"<ProfessorCourse(professor_id={self.professor_id}, course='{self.course_code}')>"


# =============================================================================
# UGA Bulletin Models (Degree Programs and Requirements)
# =============================================================================

class BulletinCourse(Base):
    """
    Course catalog data from the UGA Bulletin.

    This is the canonical course information (descriptions, prerequisites, etc.)
    separate from semester-specific schedule data.
    """
    __tablename__ = "bulletin_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    bulletin_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)

    # Course identification
    subject: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    course_number: Mapped[str] = mapped_column(String(10), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    athena_title: Mapped[Optional[str]] = mapped_column(String(200))

    # Course details
    credit_hours: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(Text)
    prerequisites: Mapped[Optional[str]] = mapped_column(Text)
    corequisites: Mapped[Optional[str]] = mapped_column(Text)
    equivalent_courses: Mapped[Optional[str]] = mapped_column(Text)

    # Offering info
    semester_offered: Mapped[Optional[str]] = mapped_column(String(100))
    grading_system: Mapped[Optional[str]] = mapped_column(String(50))

    # Learning outcomes (for RAG)
    learning_outcomes: Mapped[Optional[str]] = mapped_column(Text)
    topical_outline: Mapped[Optional[str]] = mapped_column(Text)

    # Source URL
    bulletin_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Vector embedding for semantic search
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Timestamps
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Indexes
    __table_args__ = (
        Index("ix_bulletin_courses_code", "subject", "course_number"),
    )

    @property
    def embedding_text(self) -> str:
        """Text to use for generating embeddings."""
        parts = [
            f"{self.course_code}: {self.title}",
            self.description or "",
            f"Prerequisites: {self.prerequisites}" if self.prerequisites else "",
            self.learning_outcomes or "",
        ]
        return "\n".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<BulletinCourse(id={self.id}, code='{self.course_code}')>"


class Program(Base):
    """
    Degree program, minor, or certificate from the UGA Bulletin.
    """
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    bulletin_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)

    # Program identification
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    degree_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # BS, BA, MS, PHD, MINOR, CERT-UG, CERT-GM
    college_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(200))

    # Program details
    overview: Mapped[Optional[str]] = mapped_column(Text)
    total_hours: Mapped[Optional[int]] = mapped_column(Integer)
    career_info: Mapped[Optional[str]] = mapped_column(Text)
    transfer_info: Mapped[Optional[str]] = mapped_column(Text)
    contact_info: Mapped[Optional[str]] = mapped_column(Text)

    # Source URL
    bulletin_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Vector embedding for semantic search
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Timestamps
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    requirements: Mapped[list["ProgramRequirement"]] = relationship(
        "ProgramRequirement", back_populates="program", cascade="all, delete-orphan"
    )

    @property
    def embedding_text(self) -> str:
        """Text to use for generating embeddings."""
        parts = [
            f"{self.degree_type} in {self.name}",
            f"Department: {self.department}" if self.department else "",
            self.overview or "",
            self.career_info or "",
        ]
        return "\n".join(p for p in parts if p)

    def __repr__(self) -> str:
        return f"<Program(id={self.id}, degree='{self.degree_type}', name='{self.name[:30]}')>"


class ProgramRequirement(Base):
    """
    A requirement group within a degree program.

    Examples: "Foundation Courses", "Major Requirements", "General Electives"
    """
    __tablename__ = "program_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True)

    # Requirement identification
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # foundation, major, elective, gen_ed
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Requirements
    required_hours: Mapped[Optional[int]] = mapped_column(Integer)
    min_hours: Mapped[Optional[int]] = mapped_column(Integer)
    max_hours: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Selection type: "all" = all courses required, "choose" = select from list
    selection_type: Mapped[str] = mapped_column(String(20), default="all")
    courses_to_select: Mapped[Optional[int]] = mapped_column(Integer)  # for "choose X courses"

    # Relationships
    program: Mapped["Program"] = relationship("Program", back_populates="requirements")
    courses: Mapped[list["RequirementCourse"]] = relationship(
        "RequirementCourse", back_populates="requirement", cascade="all, delete-orphan"
    )
    rules: Mapped[list["RequirementRule"]] = relationship(
        "RequirementRule", back_populates="requirement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProgramRequirement(id={self.id}, name='{self.name}')>"


class RequirementCourse(Base):
    """
    A course within a requirement group.

    Can represent a specific required course or an option in a choice group.
    """
    __tablename__ = "requirement_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("program_requirements.id"), index=True)

    # Course identification (matches bulletin_courses)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    credit_hours: Mapped[Optional[int]] = mapped_column(Integer)

    # Link to bulletin course (if exists)
    bulletin_course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bulletin_courses.id"))

    # For grouped options (e.g., "CSCI electives")
    is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    group_description: Mapped[Optional[str]] = mapped_column(Text)

    # Display order within requirement
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    requirement: Mapped["ProgramRequirement"] = relationship("ProgramRequirement", back_populates="courses")
    bulletin_course: Mapped[Optional["BulletinCourse"]] = relationship("BulletinCourse")

    # Indexes
    __table_args__ = (
        Index("ix_req_courses_code", "requirement_id", "course_code"),
    )

    def __repr__(self) -> str:
        return f"<RequirementCourse(id={self.id}, code='{self.course_code}')>"


class Document(Base):
    """
    General document store for RAG.

    Can store:
    - Course bulletin pages
    - Syllabus content
    - Department information
    - Any other relevant text
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    source_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    # Vector embedding (pgvector)
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, type='{self.source_type}', title='{self.title[:30]}')>"


# =============================================================================
# Course Relationship Tables (Neo4j-ready structure)
# =============================================================================

class CoursePrerequisite(Base):
    """
    Structured prerequisite relationships between courses.

    Designed for easy Neo4j export:
    - Each row = one edge in the graph
    - group_id handles OR logic (courses in same group are alternatives)

    Example: CSCI 1302 requires (CSCI 1301) AND (MATH 2250 OR MATH 1113)
    - Row 1: course=CSCI 1302, prereq=CSCI 1301, group=1, relation=AND
    - Row 2: course=CSCI 1302, prereq=MATH 2250, group=2, relation=OR
    - Row 3: course=CSCI 1302, prereq=MATH 1113, group=2, relation=OR
    """
    __tablename__ = "course_prerequisites"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The course that has the prerequisite
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # The prerequisite course
    prerequisite_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Group ID for OR logic (same group = alternatives)
    group_id: Mapped[int] = mapped_column(Integer, default=0)

    # Relationship type
    relation_type: Mapped[str] = mapped_column(String(20), default="prerequisite")  # prerequisite, corequisite, recommended

    # Minimum grade required (if specified)
    min_grade: Mapped[Optional[str]] = mapped_column(String(5))  # e.g., "C"

    # Can be taken concurrently?
    concurrent_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Source of this relationship
    source: Mapped[str] = mapped_column(String(50), default="bulletin")  # bulletin, manual, inferred

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_prereq_course", "course_code"),
        Index("ix_prereq_prerequisite", "prerequisite_code"),
        Index("ix_prereq_pair", "course_code", "prerequisite_code"),
    )

    def __repr__(self) -> str:
        return f"<CoursePrerequisite({self.course_code} <- {self.prerequisite_code})>"


class CourseEquivalent(Base):
    """
    Equivalent courses that can substitute for each other.

    For Neo4j: bidirectional EQUIVALENT_TO relationship.
    """
    __tablename__ = "course_equivalents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The two equivalent courses (order doesn't matter semantically)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    equivalent_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Type of equivalence
    equivalence_type: Mapped[str] = mapped_column(String(30), default="full")  # full, partial, honors

    # Notes about the equivalence
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Source
    source: Mapped[str] = mapped_column(String(50), default="bulletin")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_equiv_course", "course_code"),
        Index("ix_equiv_equivalent", "equivalent_code"),
    )

    def __repr__(self) -> str:
        return f"<CourseEquivalent({self.course_code} = {self.equivalent_code})>"


class CourseUnlock(Base):
    """
    Tracks what courses are "unlocked" by completing a course.

    This is the inverse of prerequisites - computed for fast lookups.
    For Neo4j: UNLOCKS relationship (reverse of PREREQUISITE_OF).
    """
    __tablename__ = "course_unlocks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The course that was completed
    completed_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # The course that is now available
    unlocked_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Is this a direct unlock or part of an OR group?
    is_direct: Mapped[bool] = mapped_column(Boolean, default=True)

    # How many more prereqs needed for unlocked_code? (0 = fully unlocked)
    remaining_prereqs: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_unlock_completed", "completed_code"),
        Index("ix_unlock_unlocked", "unlocked_code"),
    )

    def __repr__(self) -> str:
        return f"<CourseUnlock({self.completed_code} -> {self.unlocked_code})>"


class ScheduleBulletinLink(Base):
    """
    Links schedule courses to bulletin courses.

    Enables joining current semester offerings with catalog data.
    """
    __tablename__ = "schedule_bulletin_links"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Schedule course (from PDF)
    schedule_course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)

    # Bulletin course (from catalog)
    bulletin_course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bulletin_courses.id"), index=True)

    # Normalized course code for linking
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Match confidence (1.0 = exact match)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # Link method
    link_method: Mapped[str] = mapped_column(String(30), default="exact")  # exact, fuzzy, manual

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    schedule_course: Mapped["Course"] = relationship("Course", foreign_keys=[schedule_course_id])
    bulletin_course: Mapped[Optional["BulletinCourse"]] = relationship("BulletinCourse", foreign_keys=[bulletin_course_id])

    __table_args__ = (
        Index("ix_link_schedule", "schedule_course_id"),
        Index("ix_link_bulletin", "bulletin_course_id"),
        Index("ix_link_code", "course_code"),
    )

    def __repr__(self) -> str:
        return f"<ScheduleBulletinLink({self.course_code})>"


# =============================================================================
# Payment Models (Stripe integration)
# =============================================================================

class Payment(Base):
    """
    Payment history for subscriptions.

    Tracks all successful payments made through Stripe.
    """
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Stripe identifiers
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    stripe_checkout_session_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)

    # Payment details
    amount: Mapped[int] = mapped_column(Integer)  # Amount in cents
    currency: Mapped[str] = mapped_column(String(10), default="usd")
    tier: Mapped[str] = mapped_column(String(20))  # quarter, year, graduation
    status: Mapped[str] = mapped_column(String(20))  # succeeded, pending, failed, refunded

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, tier='{self.tier}')>"


# =============================================================================
# User Account (synced with Clerk authentication)
# =============================================================================

class User(Base):
    """
    User account synced with Clerk authentication.

    Stores user profile and preferences from onboarding.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    clerk_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Profile info from Clerk
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))

    # Onboarding preferences
    major: Mapped[Optional[str]] = mapped_column(String(200))
    goal: Mapped[Optional[str]] = mapped_column(String(50))  # fast-track, specialist, well-rounded, flexible

    # Extended profile
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer)
    classification: Mapped[Optional[str]] = mapped_column(String(20))  # freshman, sophomore, junior, senior

    # Social links
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(255))
    github_url: Mapped[Optional[str]] = mapped_column(String(255))
    twitter_url: Mapped[Optional[str]] = mapped_column(String(255))
    website_url: Mapped[Optional[str]] = mapped_column(String(255))

    # Subscription (Stripe)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subscription_status: Mapped[str] = mapped_column(String(20), default="free")  # free, active, cancelled, expired
    subscription_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # quarter, year, graduation
    subscription_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="user")

    # Student progress relationships
    completed_courses: Mapped[list["UserCompletedCourse"]] = relationship(
        "UserCompletedCourse", back_populates="user", cascade="all, delete-orphan"
    )
    program_enrollments: Mapped[list["UserProgramEnrollment"]] = relationship(
        "UserProgramEnrollment", back_populates="user", cascade="all, delete-orphan"
    )
    transcript_summary: Mapped[Optional["UserTranscriptSummary"]] = relationship(
        "UserTranscriptSummary", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @property
    def is_premium(self) -> bool:
        """Check if user has an active premium subscription."""
        if self.subscription_status != "active":
            return False
        if self.subscription_end_date and self.subscription_end_date < datetime.utcnow():
            return False
        return True

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', major='{self.major}')>"


# =============================================================================
# Student Progress Tracking
# =============================================================================

class UserCompletedCourse(Base):
    """
    Records a course completed by a user.

    Supports:
    - Manual entry by student
    - Future: DegreeWorks screenshot parsing
    - Future: Transcript import
    """
    __tablename__ = "user_completed_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Course identification
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    bulletin_course_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bulletin_courses.id"), nullable=True)

    # Completion details (grade is optional for privacy)
    grade: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # A, A-, B+, B, B-, C+, C, C-, D, F, S, U, W, I, IP
    credit_hours: Mapped[int] = mapped_column(Integer, default=3)
    quality_points: Mapped[Optional[float]] = mapped_column(Float)  # grade * credit_hours for GPA

    # When completed
    semester: Mapped[Optional[str]] = mapped_column(String(20))  # "Fall 2024", "Spring 2025"
    year: Mapped[Optional[int]] = mapped_column(Integer)

    # Source tracking for future features
    source: Mapped[str] = mapped_column(String(30), default="manual")  # manual, degreeworks_ocr, athena_import
    source_confidence: Mapped[Optional[float]] = mapped_column(Float)  # 0.0-1.0 for OCR results
    source_metadata: Mapped[Optional[str]] = mapped_column(Text)  # JSON: original text, parsing details

    # Verification status
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # User confirmed accuracy

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="completed_courses")
    bulletin_course: Mapped[Optional["BulletinCourse"]] = relationship("BulletinCourse")

    __table_args__ = (
        Index("ix_user_completed_user_course", "user_id", "course_code"),
        Index("ix_user_completed_semester", "user_id", "semester"),
    )

    @property
    def is_passing(self) -> bool:
        """Check if grade is passing (C or better for most requirements). Assumes passing if no grade provided."""
        if not self.grade:
            return True  # Assume passing if grade not provided
        passing_grades = {'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'S'}
        return self.grade.upper() in passing_grades

    @property
    def grade_points(self) -> Optional[float]:
        """Convert letter grade to grade points. Returns None if no grade."""
        if not self.grade:
            return None
        grade_map = {
            'A': 4.0, 'A-': 3.7,
            'B+': 3.3, 'B': 3.0, 'B-': 2.7,
            'C+': 2.3, 'C': 2.0, 'C-': 1.7,
            'D': 1.0, 'F': 0.0
        }
        return grade_map.get(self.grade.upper(), 0.0)

    def __repr__(self) -> str:
        return f"<UserCompletedCourse(user_id={self.user_id}, course='{self.course_code}', grade='{self.grade}')>"


class UserProgramEnrollment(Base):
    """
    Tracks a user's enrollment in a degree program.

    Users can have multiple enrollments (double major, minor, etc.)
    """
    __tablename__ = "user_program_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True)

    # Enrollment details
    enrollment_type: Mapped[str] = mapped_column(String(20), default="major")  # major, minor, certificate
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    enrollment_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expected_graduation: Mapped[Optional[str]] = mapped_column(String(20))  # "Spring 2027"

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, withdrawn

    # Catalog year (important for requirement tracking)
    catalog_year: Mapped[Optional[str]] = mapped_column(String(10))  # "2024-2025"

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="program_enrollments")
    program: Mapped["Program"] = relationship("Program")

    __table_args__ = (
        Index("ix_user_program_enrollment", "user_id", "program_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserProgramEnrollment(user_id={self.user_id}, program_id={self.program_id}, type='{self.enrollment_type}')>"


class UserTranscriptSummary(Base):
    """
    Cached aggregate statistics from user's completed courses.

    Recalculated when courses are added/updated/removed.
    """
    __tablename__ = "user_transcript_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    # Credit hour totals
    total_hours_attempted: Mapped[int] = mapped_column(Integer, default=0)
    total_hours_earned: Mapped[int] = mapped_column(Integer, default=0)
    transfer_hours: Mapped[int] = mapped_column(Integer, default=0)

    # GPA calculations
    cumulative_gpa: Mapped[Optional[float]] = mapped_column(Float)
    major_gpa: Mapped[Optional[float]] = mapped_column(Float)
    total_quality_points: Mapped[float] = mapped_column(Float, default=0.0)

    # Counts by level
    hours_1000_level: Mapped[int] = mapped_column(Integer, default=0)
    hours_2000_level: Mapped[int] = mapped_column(Integer, default=0)
    hours_3000_level: Mapped[int] = mapped_column(Integer, default=0)
    hours_4000_level: Mapped[int] = mapped_column(Integer, default=0)
    hours_5000_plus: Mapped[int] = mapped_column(Integer, default=0)

    # Upper division requirement tracking
    upper_division_hours: Mapped[int] = mapped_column(Integer, default=0)  # 3000+

    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="transcript_summary")

    def __repr__(self) -> str:
        return f"<UserTranscriptSummary(user_id={self.user_id}, gpa={self.cumulative_gpa}, hours={self.total_hours_earned})>"


class RequirementRule(Base):
    """
    Flexible rule definitions for complex degree requirements.

    Supports DegreeWorks-style rules like:
    - "Any 9 hours from 4000-level CSCI courses"
    - "Minimum 2.5 GPA in major courses"
    - "Complete MATH 2250 with C or higher"
    - "Choose 2 from: CSCI 4050, 4060, 4070"
    """
    __tablename__ = "requirement_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("program_requirements.id"), index=True)

    # Rule definition
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Types: course_list, hours_from_pool, gpa_minimum, course_level,
    #        subject_hours, attribute_match, exclusion

    # Rule parameters (JSON)
    rule_config: Mapped[str] = mapped_column(Text, nullable=False)
    # Examples:
    # course_list: {"courses": ["CSCI 4050", "CSCI 4060"], "select": 2}
    # hours_from_pool: {"subjects": ["CSCI"], "min_level": 4000, "hours": 9}
    # gpa_minimum: {"gpa": 2.5, "scope": "major"}
    # course_level: {"min_level": 3000, "hours": 21}
    # exclusion: {"cannot_use": ["CSCI 1100"], "if_completed": ["CSCI 1301"]}

    # Ordering
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Description for display
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    requirement: Mapped["ProgramRequirement"] = relationship("ProgramRequirement", back_populates="rules")

    def __repr__(self) -> str:
        return f"<RequirementRule(id={self.id}, type='{self.rule_type}')>"


class UserRequirementSatisfaction(Base):
    """
    Records how user's courses satisfy program requirements.

    This is the "audit cache" - recalculated when courses or requirements change.
    Enables tracking of partial satisfaction and "best fit" allocation.
    """
    __tablename__ = "user_requirement_satisfactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("user_program_enrollments.id"), index=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("program_requirements.id"), index=True)

    # Satisfaction status
    status: Mapped[str] = mapped_column(String(20), default="incomplete")
    # Status: incomplete, in_progress, complete, waived, substituted

    # Progress tracking
    hours_required: Mapped[Optional[int]] = mapped_column(Integer)
    hours_satisfied: Mapped[int] = mapped_column(Integer, default=0)
    courses_required: Mapped[Optional[int]] = mapped_column(Integer)
    courses_satisfied: Mapped[int] = mapped_column(Integer, default=0)

    # For GPA requirements
    gpa_required: Mapped[Optional[float]] = mapped_column(Float)
    gpa_achieved: Mapped[Optional[float]] = mapped_column(Float)

    # Applied courses (JSON array of course codes)
    courses_applied_json: Mapped[Optional[str]] = mapped_column(Text)

    # Notes (for waivers, substitutions, etc.)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User")
    enrollment: Mapped["UserProgramEnrollment"] = relationship("UserProgramEnrollment")
    requirement: Mapped["ProgramRequirement"] = relationship("ProgramRequirement")
    course_applications: Mapped[list["CourseRequirementApplication"]] = relationship(
        "CourseRequirementApplication", back_populates="satisfaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_user_req_sat", "user_id", "enrollment_id", "requirement_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserRequirementSatisfaction(user={self.user_id}, req={self.requirement_id}, status='{self.status}')>"


class CourseRequirementApplication(Base):
    """
    Maps a completed course to a requirement it satisfies.

    A course can satisfy multiple requirements (if allowed) or be
    explicitly locked to one requirement (no double-counting).
    """
    __tablename__ = "course_requirement_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_completed_course_id: Mapped[int] = mapped_column(
        ForeignKey("user_completed_courses.id"), index=True
    )
    satisfaction_id: Mapped[int] = mapped_column(
        ForeignKey("user_requirement_satisfactions.id"), index=True
    )

    # How many hours from this course apply
    hours_applied: Mapped[int] = mapped_column(Integer)

    # Is this the primary application of this course?
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)

    # Override tracking
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    completed_course: Mapped["UserCompletedCourse"] = relationship("UserCompletedCourse")
    satisfaction: Mapped["UserRequirementSatisfaction"] = relationship(
        "UserRequirementSatisfaction", back_populates="course_applications"
    )

    __table_args__ = (
        Index("ix_course_app_course_sat", "user_completed_course_id", "satisfaction_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<CourseRequirementApplication(course={self.user_completed_course_id}, satisfaction={self.satisfaction_id})>"


# =============================================================================
# Database Engine and Session Management
# =============================================================================

_engine = None
_async_engine = None
_session_factory = None
_async_session_factory = None


def get_engine(url: Optional[str] = None):
    """Get or create synchronous database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            url or settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.debug,
        )
    return _engine


def get_async_engine(url: Optional[str] = None):
    """Get or create async database engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            url or settings.async_database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            echo=settings.debug,
        )
    return _async_engine


def get_session_factory(engine=None):
    """Get or create synchronous session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=engine or get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


def get_async_session_factory(engine=None):
    """Get or create async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=engine or get_async_engine(),
            expire_on_commit=False,
        )
    return _async_session_factory


def init_db(engine=None):
    """Initialize database, creating all tables and pgvector extension."""
    if engine is None:
        engine = get_engine()

    # Create pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Create tables
    Base.metadata.create_all(engine)

    # Create vector similarity indexes
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_courses_embedding
            ON courses
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_documents_embedding
            ON documents
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_bulletin_courses_embedding
            ON bulletin_courses
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_programs_embedding
            ON programs
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_professors_embedding
            ON professors
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.commit()


async def init_async_db(engine=None):
    """Initialize database asynchronously."""
    if engine is None:
        engine = get_async_engine()

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_courses_embedding
            ON courses
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_documents_embedding
            ON documents
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_bulletin_courses_embedding
            ON bulletin_courses
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_programs_embedding
            ON programs
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_professors_embedding
            ON professors
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
