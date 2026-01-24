"""
UGA Bulletin Scraper using Firecrawl API.

Uses Firecrawl for reliable JavaScript-rendered page scraping.
"""
import asyncio
import logging
import re
import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

from firecrawl import FirecrawlApp
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.config import settings
from src.models.database import (
    BulletinCourse, Program, ProgramRequirement, RequirementCourse,
    get_engine, get_session_factory, init_db
)

logger = logging.getLogger(__name__)


@dataclass
class ScrapedCourse:
    """Parsed course data from bulletin."""
    bulletin_id: str
    subject: str
    course_number: str
    course_code: str
    title: str
    athena_title: Optional[str] = None
    credit_hours: Optional[str] = None
    description: Optional[str] = None
    prerequisites: Optional[str] = None
    corequisites: Optional[str] = None
    equivalent_courses: Optional[str] = None
    semester_offered: Optional[str] = None
    grading_system: Optional[str] = None
    learning_outcomes: Optional[str] = None
    topical_outline: Optional[str] = None
    bulletin_url: str = ""


@dataclass
class ScrapedRequirementCourse:
    """A course within a requirement."""
    course_code: str
    title: Optional[str] = None
    credit_hours: Optional[int] = None
    is_group: bool = False
    group_description: Optional[str] = None


@dataclass
class ScrapedRequirement:
    """A requirement group within a program."""
    name: str
    category: str  # foundation, major, elective, gen_ed
    required_hours: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    selection_type: str = "all"
    courses_to_select: Optional[int] = None
    courses: list[ScrapedRequirementCourse] = field(default_factory=list)


@dataclass
class ScrapedProgram:
    """Parsed program data from bulletin."""
    bulletin_id: str
    name: str
    degree_type: str
    college_code: str
    department: Optional[str] = None
    overview: Optional[str] = None
    total_hours: Optional[int] = None
    career_info: Optional[str] = None
    transfer_info: Optional[str] = None
    contact_info: Optional[str] = None
    bulletin_url: str = ""
    requirements: list[ScrapedRequirement] = field(default_factory=list)


class BulletinFirecrawlScraper:
    """Scrapes UGA Bulletin using Firecrawl API."""

    BASE_URL = "https://bulletin.uga.edu"

    def __init__(self, api_key: str = None, session_factory=None, skip_db: bool = False):
        """Initialize the Firecrawl scraper.

        Args:
            api_key: Firecrawl API key
            session_factory: SQLAlchemy session factory
            skip_db: Skip database initialization
        """
        self.api_key = api_key or settings.firecrawl_api_key
        if not self.api_key:
            raise ValueError("Firecrawl API key not provided. Set FIRECRAWL_API_KEY in .env")

        self.app = FirecrawlApp(api_key=self.api_key)
        self.skip_db = skip_db

        if not skip_db:
            if session_factory is None:
                engine = get_engine()
                init_db(engine)
                session_factory = get_session_factory(engine)
            self.session_factory = session_factory
        else:
            self.session_factory = None

    def scrape_url(self, url: str, extract_schema: dict = None) -> dict:
        """Scrape a URL and return the content.

        Args:
            url: URL to scrape
            extract_schema: Optional LLM extraction schema (used with separate extract call)

        Returns:
            Dict with 'markdown', 'html', and optionally 'extract' keys
        """
        # Use Firecrawl v2 API with keyword arguments
        result = self.app.scrape(
            url,
            formats=["markdown", "html"],
            wait_for=3000,  # Wait for JS to render
        )

        # Convert Document object to dict-like access
        return_data = {
            "markdown": getattr(result, 'markdown', None),
            "html": getattr(result, 'html', None),
            "metadata": getattr(result, 'metadata', {}),
        }

        # If we have an extract schema, use the extract method
        if extract_schema and return_data.get("markdown"):
            try:
                extract_result = self.app.extract(
                    urls=[url],
                    schema=extract_schema,
                    prompt="Extract the structured data from this academic program page."
                )
                if extract_result and hasattr(extract_result, 'data'):
                    return_data["extract"] = extract_result.data
            except Exception as e:
                logger.warning(f"Extract failed for {url}: {e}")

        return return_data

    def scrape_program(self, bulletin_id: str, college_code: str) -> Optional[ScrapedProgram]:
        """Scrape a program's details.

        Args:
            bulletin_id: Numeric program ID
            college_code: College code (e.g., ARTS)

        Returns:
            ScrapedProgram or None
        """
        url = f"{self.BASE_URL}/Program/Details/{bulletin_id}?IDc={college_code}"
        logger.info(f"Scraping program: {url}")

        try:
            # Define extraction schema for structured data
            extract_schema = {
                "type": "object",
                "properties": {
                    "program_name": {"type": "string", "description": "Full name of the degree program"},
                    "degree_type": {"type": "string", "description": "Degree type like BS, BA, MS, PHD, MINOR"},
                    "department": {"type": "string", "description": "Department name"},
                    "total_hours": {"type": "integer", "description": "Total credit hours required"},
                    "overview": {"type": "string", "description": "Program overview or description"},
                    "requirements": {
                        "type": "array",
                        "description": "List of requirement categories",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Requirement category name"},
                                "hours": {"type": "integer", "description": "Required hours for this category"},
                                "courses": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "code": {"type": "string", "description": "Course code like CSCI 1301"},
                                            "title": {"type": "string", "description": "Course title"},
                                            "credits": {"type": "integer", "description": "Credit hours"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            result = self.scrape_url(url, extract_schema=extract_schema)

            # Parse from extraction or markdown
            if result.get("extract"):
                return self._parse_extracted_program(result["extract"], bulletin_id, college_code, url)
            elif result.get("markdown"):
                return self._parse_markdown_program(result["markdown"], bulletin_id, college_code, url)
            else:
                logger.warning(f"No content returned for {url}")
                return None

        except Exception as e:
            logger.error(f"Error scraping program {bulletin_id}: {e}")
            return None

    def _parse_extracted_program(self, extract: dict, bulletin_id: str, college_code: str, url: str) -> ScrapedProgram:
        """Parse program from Firecrawl LLM extraction."""
        program = ScrapedProgram(
            bulletin_id=bulletin_id,
            name=extract.get("program_name", "Unknown"),
            degree_type=extract.get("degree_type", "UNKNOWN"),
            college_code=college_code,
            department=extract.get("department"),
            overview=extract.get("overview"),
            total_hours=extract.get("total_hours"),
            bulletin_url=url,
        )

        # Parse requirements
        for idx, req_data in enumerate(extract.get("requirements", [])):
            category = self._categorize_requirement(req_data.get("name", ""))
            req = ScrapedRequirement(
                name=req_data.get("name", f"Requirement {idx + 1}"),
                category=category,
                required_hours=req_data.get("hours"),
            )

            # Parse courses
            for course_data in req_data.get("courses", []):
                course_code = course_data.get("code", "")
                is_group = not bool(re.match(r"^[A-Z]{2,4}\s+\d", course_code))

                req.courses.append(ScrapedRequirementCourse(
                    course_code=course_code,
                    title=course_data.get("title"),
                    credit_hours=course_data.get("credits"),
                    is_group=is_group,
                ))

            program.requirements.append(req)

        return program

    def _parse_markdown_program(self, markdown: str, bulletin_id: str, college_code: str, url: str) -> ScrapedProgram:
        """Parse program from markdown content."""
        lines = markdown.split('\n')

        # Extract program name and degree from header
        name = "Unknown Program"
        degree_type = "UNKNOWN"

        for line in lines[:20]:
            # Look for degree type headers
            if line.startswith('# ') or line.startswith('## '):
                header = line.lstrip('#').strip()
                # Check for degree type at end: "COMPUTER SCIENCE BS"
                parts = header.rsplit(' ', 1)
                if len(parts) == 2 and parts[1].upper() in ['BS', 'BA', 'MS', 'MA', 'PHD', 'MINOR', 'AB', 'BBA', 'BSA']:
                    name = parts[0].title()
                    degree_type = parts[1].upper()
                    break

        program = ScrapedProgram(
            bulletin_id=bulletin_id,
            name=name,
            degree_type=degree_type,
            college_code=college_code,
            bulletin_url=url,
        )

        # Extract overview
        overview_match = re.search(r'(?:OVERVIEW|Overview)\s*\n+(.+?)(?=\n#|\n\*\*[A-Z]|\Z)', markdown, re.DOTALL)
        if overview_match:
            program.overview = overview_match.group(1).strip()[:3000]

        # Extract total hours
        hours_match = re.search(r'(\d+)\s*(?:total\s*)?hours?', markdown, re.IGNORECASE)
        if hours_match:
            program.total_hours = int(hours_match.group(1))

        # Extract requirements sections
        req_pattern = r'#+\s*([^#\n]+?)\s*\((\d+)\s*hours?\)'
        for match in re.finditer(req_pattern, markdown, re.IGNORECASE):
            req_name = match.group(1).strip()
            req_hours = int(match.group(2))

            if any(skip in req_name.lower() for skip in ['career', 'transfer', 'contact', 'entrance']):
                continue

            category = self._categorize_requirement(req_name)
            req = ScrapedRequirement(
                name=req_name,
                category=category,
                required_hours=req_hours,
            )

            # Look for course listings after this header
            start_pos = match.end()
            end_pos = start_pos + 2000  # Look ahead
            section_text = markdown[start_pos:end_pos]

            # Find course codes (e.g., CSCI 1301)
            course_matches = re.finditer(r'\b([A-Z]{2,4})\s+(\d{4}[A-Z]?)\b', section_text)
            seen_codes = set()
            for cm in course_matches:
                code = f"{cm.group(1)} {cm.group(2)}"
                if code not in seen_codes:
                    seen_codes.add(code)
                    req.courses.append(ScrapedRequirementCourse(
                        course_code=code,
                        is_group=False,
                    ))

            if req.courses:
                program.requirements.append(req)

        return program

    def _categorize_requirement(self, name: str) -> str:
        """Categorize a requirement based on its name."""
        name_lower = name.lower()

        if any(kw in name_lower for kw in ["foundation", "core"]):
            return "foundation"
        elif any(kw in name_lower for kw in ["major", "required"]):
            return "major"
        elif any(kw in name_lower for kw in ["elective"]):
            return "elective"
        elif any(kw in name_lower for kw in ["general", "social", "humanities", "arts", "language", "world"]):
            return "gen_ed"
        elif any(kw in name_lower for kw in ["science", "quantitative", "math"]):
            return "foundation"
        else:
            return "other"

    def scrape_course(self, bulletin_id: str) -> Optional[ScrapedCourse]:
        """Scrape a course's details.

        Args:
            bulletin_id: Numeric course ID

        Returns:
            ScrapedCourse or None
        """
        url = f"{self.BASE_URL}/Course/Details/{bulletin_id}"
        logger.info(f"Scraping course: {url}")

        try:
            extract_schema = {
                "type": "object",
                "properties": {
                    "course_code": {"type": "string", "description": "Course code like CSCI 3030"},
                    "title": {"type": "string", "description": "Full course title"},
                    "credit_hours": {"type": "string", "description": "Credit hours"},
                    "description": {"type": "string", "description": "Course description"},
                    "prerequisites": {"type": "string", "description": "Prerequisites"},
                    "corequisites": {"type": "string", "description": "Corequisites"},
                    "equivalent_courses": {"type": "string", "description": "Equivalent courses"},
                    "semester_offered": {"type": "string", "description": "When the course is offered"},
                    "learning_outcomes": {"type": "string", "description": "Student learning outcomes"}
                }
            }

            result = self.scrape_url(url, extract_schema=extract_schema)

            if result.get("extract"):
                return self._parse_extracted_course(result["extract"], bulletin_id, url)
            elif result.get("markdown"):
                return self._parse_markdown_course(result["markdown"], bulletin_id, url)
            else:
                logger.warning(f"No content returned for {url}")
                return None

        except Exception as e:
            logger.error(f"Error scraping course {bulletin_id}: {e}")
            return None

    def _parse_extracted_course(self, extract: dict, bulletin_id: str, url: str) -> ScrapedCourse:
        """Parse course from Firecrawl LLM extraction."""
        course_code = extract.get("course_code", "")
        match = re.match(r"([A-Z]{2,4})\s+(\d+[A-Z]*)", course_code)

        if match:
            subject = match.group(1)
            course_number = match.group(2)
        else:
            subject = "UNKN"
            course_number = "0000"

        return ScrapedCourse(
            bulletin_id=bulletin_id,
            subject=subject,
            course_number=course_number,
            course_code=f"{subject} {course_number}",
            title=extract.get("title", "Unknown Course"),
            credit_hours=extract.get("credit_hours"),
            description=extract.get("description"),
            prerequisites=extract.get("prerequisites"),
            corequisites=extract.get("corequisites"),
            equivalent_courses=extract.get("equivalent_courses"),
            semester_offered=extract.get("semester_offered"),
            learning_outcomes=extract.get("learning_outcomes"),
            bulletin_url=url,
        )

    def _parse_markdown_course(self, markdown: str, bulletin_id: str, url: str) -> ScrapedCourse:
        """Parse course from markdown content."""
        # Extract course code
        code_match = re.search(r'\b([A-Z]{2,4})\s+(\d{4}[A-Z]?)\b', markdown)
        if code_match:
            subject = code_match.group(1)
            course_number = code_match.group(2)
            course_code = f"{subject} {course_number}"
        else:
            subject = "UNKN"
            course_number = "0000"
            course_code = "UNKN 0000"

        # Extract title (usually in a header)
        title_match = re.search(r'#+\s*([A-Z][A-Z\s,]+)', markdown)
        title = title_match.group(1).strip().title() if title_match else "Unknown Course"

        # Extract description
        desc_match = re.search(r'(?:Course Description|Description)\s*\n+(.+?)(?=\n#|\n\*\*[A-Z]|\Z)', markdown, re.DOTALL | re.IGNORECASE)
        description = desc_match.group(1).strip()[:2000] if desc_match else None

        # Extract prerequisites
        prereq_match = re.search(r'(?:Prerequisite|Prerequisites?)\s*[:\n]+(.+?)(?=\n#|\n\*\*[A-Z]|\Z)', markdown, re.DOTALL | re.IGNORECASE)
        prerequisites = prereq_match.group(1).strip()[:500] if prereq_match else None

        # Extract credit hours
        hours_match = re.search(r'(\d+(?:-\d+)?)\s*(?:credit\s*)?hours?', markdown, re.IGNORECASE)
        credit_hours = hours_match.group(1) if hours_match else None

        return ScrapedCourse(
            bulletin_id=bulletin_id,
            subject=subject,
            course_number=course_number,
            course_code=course_code,
            title=title,
            credit_hours=credit_hours,
            description=description,
            prerequisites=prerequisites,
            bulletin_url=url,
        )

    def search_programs_via_crawl(self, program_type: str = "UG") -> list[tuple[str, str, str]]:
        """
        Crawl the program index to find all programs.

        Note: This is expensive. Consider caching results.

        Args:
            program_type: Program type filter (UG, GM, MINOR, etc.)

        Returns:
            List of (name, bulletin_id, college_code) tuples
        """
        url = f"{self.BASE_URL}/Program/Index"
        logger.info(f"Crawling program index: {url}")

        try:
            result = self.scrape_url(url)
            html = result.get("html", "")

            # Parse program links from HTML
            programs = []
            link_pattern = r'href="/Program/Details/(\d+)\?IDc=(\w+)"[^>]*>([^<]+)</a>'

            for match in re.finditer(link_pattern, html):
                bulletin_id = match.group(1)
                college_code = match.group(2)
                name = match.group(3).strip()
                programs.append((name, bulletin_id, college_code))

            return programs

        except Exception as e:
            logger.error(f"Error crawling program index: {e}")
            return []

    def save_program(self, scraped: ScrapedProgram) -> Program:
        """Save a scraped program to the database."""
        if self.skip_db or not self.session_factory:
            raise RuntimeError("Database not initialized")

        with self.session_factory() as session:
            # Check for existing program
            existing = session.execute(
                select(Program).where(Program.bulletin_id == scraped.bulletin_id)
            ).scalar_one_or_none()

            if existing:
                # Update existing
                existing.name = scraped.name
                existing.degree_type = scraped.degree_type
                existing.college_code = scraped.college_code
                existing.department = scraped.department
                existing.overview = scraped.overview
                existing.total_hours = scraped.total_hours
                existing.career_info = scraped.career_info
                existing.transfer_info = scraped.transfer_info
                existing.contact_info = scraped.contact_info
                existing.bulletin_url = scraped.bulletin_url
                existing.updated_at = datetime.utcnow()

                # Delete old requirements
                for req in existing.requirements:
                    session.delete(req)
                session.flush()
                program = existing
            else:
                program = Program(
                    bulletin_id=scraped.bulletin_id,
                    name=scraped.name,
                    degree_type=scraped.degree_type,
                    college_code=scraped.college_code,
                    department=scraped.department,
                    overview=scraped.overview,
                    total_hours=scraped.total_hours,
                    career_info=scraped.career_info,
                    transfer_info=scraped.transfer_info,
                    contact_info=scraped.contact_info,
                    bulletin_url=scraped.bulletin_url,
                )
                session.add(program)
                session.flush()

            # Add requirements
            for idx, scraped_req in enumerate(scraped.requirements):
                req = ProgramRequirement(
                    program_id=program.id,
                    name=scraped_req.name,
                    category=scraped_req.category,
                    display_order=idx,
                    required_hours=scraped_req.required_hours,
                    description=scraped_req.description,
                    notes=scraped_req.notes,
                    selection_type=scraped_req.selection_type,
                    courses_to_select=scraped_req.courses_to_select,
                )
                session.add(req)
                session.flush()

                # Add requirement courses
                for cidx, scraped_course in enumerate(scraped_req.courses):
                    bulletin_course = session.execute(
                        select(BulletinCourse).where(
                            BulletinCourse.course_code == scraped_course.course_code
                        )
                    ).scalar_one_or_none()

                    req_course = RequirementCourse(
                        requirement_id=req.id,
                        course_code=scraped_course.course_code,
                        title=scraped_course.title,
                        credit_hours=scraped_course.credit_hours,
                        bulletin_course_id=bulletin_course.id if bulletin_course else None,
                        is_group=scraped_course.is_group,
                        display_order=cidx,
                    )
                    session.add(req_course)

            session.commit()
            return program

    def save_course(self, scraped: ScrapedCourse) -> BulletinCourse:
        """Save a scraped course to the database."""
        if self.skip_db or not self.session_factory:
            raise RuntimeError("Database not initialized")

        with self.session_factory() as session:
            existing = session.execute(
                select(BulletinCourse).where(BulletinCourse.bulletin_id == scraped.bulletin_id)
            ).scalar_one_or_none()

            if existing:
                existing.subject = scraped.subject
                existing.course_number = scraped.course_number
                existing.course_code = scraped.course_code
                existing.title = scraped.title
                existing.athena_title = scraped.athena_title
                existing.credit_hours = scraped.credit_hours
                existing.description = scraped.description
                existing.prerequisites = scraped.prerequisites
                existing.corequisites = scraped.corequisites
                existing.equivalent_courses = scraped.equivalent_courses
                existing.semester_offered = scraped.semester_offered
                existing.grading_system = scraped.grading_system
                existing.learning_outcomes = scraped.learning_outcomes
                existing.topical_outline = scraped.topical_outline
                existing.bulletin_url = scraped.bulletin_url
                existing.updated_at = datetime.utcnow()
                course = existing
            else:
                course = BulletinCourse(
                    bulletin_id=scraped.bulletin_id,
                    subject=scraped.subject,
                    course_number=scraped.course_number,
                    course_code=scraped.course_code,
                    title=scraped.title,
                    athena_title=scraped.athena_title,
                    credit_hours=scraped.credit_hours,
                    description=scraped.description,
                    prerequisites=scraped.prerequisites,
                    corequisites=scraped.corequisites,
                    equivalent_courses=scraped.equivalent_courses,
                    semester_offered=scraped.semester_offered,
                    grading_system=scraped.grading_system,
                    learning_outcomes=scraped.learning_outcomes,
                    topical_outline=scraped.topical_outline,
                    bulletin_url=scraped.bulletin_url,
                )
                session.add(course)

            session.commit()
            return course


def scrape_programs_batch(
    program_ids: list[tuple[str, str]],  # (bulletin_id, college_code)
    api_key: str = None,
    save_to_db: bool = False,
) -> list[ScrapedProgram]:
    """
    Scrape a batch of programs.

    Args:
        program_ids: List of (bulletin_id, college_code) tuples
        api_key: Firecrawl API key
        save_to_db: Whether to save to database

    Returns:
        List of ScrapedProgram objects
    """
    scraper = BulletinFirecrawlScraper(api_key=api_key, skip_db=not save_to_db)
    programs = []

    for bulletin_id, college_code in program_ids:
        program = scraper.scrape_program(bulletin_id, college_code)
        if program:
            programs.append(program)
            if save_to_db:
                scraper.save_program(program)
            logger.info(f"Scraped: {program.name} ({program.degree_type}) - {len(program.requirements)} requirements")

    return programs


# CLI helper
if __name__ == "__main__":
    import sys
    import os

    logging.basicConfig(level=logging.INFO)

    # Test with CS program
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        print("Set FIRECRAWL_API_KEY environment variable")
        sys.exit(1)

    scraper = BulletinFirecrawlScraper(api_key=api_key, skip_db=True)

    # Test scraping CS BS program
    print("Scraping Computer Science BS program...")
    program = scraper.scrape_program("73962", "ARTS")

    if program:
        print(f"\nProgram: {program.name} ({program.degree_type})")
        print(f"Total Hours: {program.total_hours}")
        print(f"Department: {program.department}")
        print(f"Requirements: {len(program.requirements)}")
        for req in program.requirements:
            print(f"  - {req.name} ({req.required_hours} hrs)")
            for course in req.courses[:5]:
                print(f"      {course.course_code}: {course.title}")
    else:
        print("Failed to scrape program")
