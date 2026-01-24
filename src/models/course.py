"""Data models for UGA course information."""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import json


@dataclass
class CourseSection:
    """Represents a specific section of a course."""
    crn: str
    section: str
    status: str  # A = Active, X = Cancelled, etc.
    credit_hours: int
    instructor: Optional[str]
    part_of_term: str
    class_size: int
    seats_available: int
    # Schedule info
    days: Optional[str] = None  # e.g., "M W F", "T R"
    start_time: Optional[str] = None  # e.g., "09:00 am"
    end_time: Optional[str] = None  # e.g., "09:50 am"
    building: Optional[str] = None  # e.g., "Boyd GSRC"
    room: Optional[str] = None  # e.g., "0306"
    campus: Optional[str] = None  # e.g., "Athens"

    @property
    def is_available(self) -> bool:
        return self.seats_available > 0 and self.status == 'A'

    @property
    def schedule_display(self) -> str:
        """Human-readable schedule string."""
        if not self.days or self.days == 'TBA':
            return "TBA"
        time_str = f"{self.start_time}-{self.end_time}" if self.start_time and self.end_time else ""
        return f"{self.days} {time_str}".strip()

    def to_dict(self) -> dict:
        return {
            "crn": self.crn,
            "section": self.section,
            "status": self.status,
            "credit_hours": self.credit_hours,
            "instructor": self.instructor,
            "part_of_term": self.part_of_term,
            "class_size": self.class_size,
            "seats_available": self.seats_available,
            "is_available": self.is_available,
            "days": self.days,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "building": self.building,
            "room": self.room,
            "campus": self.campus,
            "schedule_display": self.schedule_display,
        }


@dataclass
class Course:
    """Represents a UGA course."""
    subject: str
    course_number: str
    title: str
    department: str
    bulletin_url: Optional[str] = None
    sections: list[CourseSection] = field(default_factory=list)

    @property
    def course_code(self) -> str:
        return f"{self.subject} {self.course_number}"

    @property
    def total_seats(self) -> int:
        return sum(s.class_size for s in self.sections)

    @property
    def available_seats(self) -> int:
        return sum(s.seats_available for s in self.sections if s.seats_available > 0)

    @property
    def has_availability(self) -> bool:
        return any(s.is_available for s in self.sections)

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "course_number": self.course_number,
            "course_code": self.course_code,
            "title": self.title,
            "department": self.department,
            "bulletin_url": self.bulletin_url,
            "sections": [s.to_dict() for s in self.sections],
            "total_seats": self.total_seats,
            "available_seats": self.available_seats,
            "has_availability": self.has_availability
        }


@dataclass
class ScheduleMetadata:
    """Metadata about a parsed schedule."""
    term: str
    source_url: str
    parse_date: datetime
    report_date: Optional[str] = None
    total_courses: int = 0
    total_sections: int = 0

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "source_url": self.source_url,
            "parse_date": self.parse_date.isoformat(),
            "report_date": self.report_date,
            "total_courses": self.total_courses,
            "total_sections": self.total_sections
        }


@dataclass
class Schedule:
    """Complete parsed schedule."""
    metadata: ScheduleMetadata
    courses: list[Course] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "courses": [c.to_dict() for c in self.courses]
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def get_courses_by_subject(self, subject: str) -> list[Course]:
        return [c for c in self.courses if c.subject.upper() == subject.upper()]

    def get_courses_by_instructor(self, instructor: str) -> list[Course]:
        instructor_lower = instructor.lower()
        return [
            c for c in self.courses
            if any(s.instructor and instructor_lower in s.instructor.lower()
                   for s in c.sections)
        ]

    def search_courses(self, query: str) -> list[Course]:
        query_lower = query.lower()
        return [
            c for c in self.courses
            if query_lower in c.title.lower()
            or query_lower in c.course_code.lower()
            or query_lower in c.department.lower()
        ]
