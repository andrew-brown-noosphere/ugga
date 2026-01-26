"""
UGA Bulletin Scraper Service.

Scrapes degree programs, requirements, and course catalog data from bulletin.uga.edu
using Playwright for JavaScript-rendered content.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from playwright.async_api import async_playwright, Page, Browser
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import select

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
    degree_type: str  # BS, BA, MS, PHD, MINOR, CERT-UG, CERT-GM
    college_code: str
    department: Optional[str] = None
    overview: Optional[str] = None
    total_hours: Optional[int] = None
    career_info: Optional[str] = None
    transfer_info: Optional[str] = None
    contact_info: Optional[str] = None
    bulletin_url: str = ""
    requirements: list[ScrapedRequirement] = field(default_factory=list)


class BulletinScraper:
    """Scrapes UGA Bulletin for programs and courses."""

    BASE_URL = "https://bulletin.uga.edu"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    # Program type mappings
    PROGRAM_TYPES = {
        "UG": ["BS", "BA", "AB", "BBA", "BSA", "BSED", "BFA", "BLA", "BM", "BSW"],
        "GM": ["MS", "MA", "MBA", "MPA", "MPH", "MED", "MFA", "MACC", "MPACC", "MAB"],
        "MINOR": ["MINOR"],
        "CERT-UG": ["CERT-UG"],
        "CERT-GM": ["CERT-GM"],
        "PR": ["PHD", "EDD", "DMA", "JD", "PHARMD", "DVM"],
    }

    def __init__(self, session_factory=None, headless: bool = True, skip_db: bool = False):
        """Initialize the scraper.

        Args:
            session_factory: SQLAlchemy session factory
            headless: Run browser in headless mode
            skip_db: Skip database initialization (for testing scraping only)
        """
        self.skip_db = skip_db
        if not skip_db:
            if session_factory is None:
                engine = get_engine()
                init_db(engine)
                session_factory = get_session_factory(engine)
            self.session_factory = session_factory
        else:
            self.session_factory = None
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def __aenter__(self):
        """Async context manager entry."""
        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=self.headless)
        context = await self._browser.new_context(user_agent=self.USER_AGENT)
        self._page = await context.new_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._browser:
            await self._browser.close()

    async def _wait_for_content(self, timeout: int = 5000):
        """Wait for dynamic content to load."""
        await self._page.wait_for_timeout(timeout)

    async def search_programs(
        self,
        keyword: str = "",
        program_types: list[str] = None
    ) -> list[tuple[str, str, str]]:
        """
        Search for programs and return list of (name, bulletin_id, college_code).

        Args:
            keyword: Search keyword
            program_types: List of program types to filter (UG, GM, MINOR, etc.)

        Returns:
            List of (program_name, bulletin_id, college_code) tuples
        """
        await self._page.goto(f"{self.BASE_URL}/Program/Index", timeout=30000)
        await self._wait_for_content(2000)

        # Enter search keyword if provided
        if keyword:
            search_input = await self._page.query_selector("#searchKeyword")
            if search_input:
                await search_input.fill(keyword)

        # Check program type checkboxes if specified
        if program_types:
            for ptype in program_types:
                checkbox = await self._page.query_selector(f'input[value="{ptype}"]')
                if checkbox:
                    await checkbox.check()

        # Click search button
        search_btn = await self._page.query_selector('button:has-text("SEARCH")')
        if search_btn:
            await search_btn.click()
            await self._wait_for_content(3000)

        # Extract program links
        links = await self._page.query_selector_all('a[href*="/Program/Details"]')
        programs = []

        for link in links:
            href = await link.get_attribute("href")
            name = (await link.inner_text()).strip()

            # Parse bulletin_id and college_code from URL
            # Format: /Program/Details/73962?IDc=ARTS
            match = re.search(r"/Program/Details/(\d+)\?IDc=(\w+)", href)
            if match:
                bulletin_id = match.group(1)
                college_code = match.group(2)
                programs.append((name, bulletin_id, college_code))

        return programs

    async def scrape_program(self, bulletin_id: str, college_code: str) -> Optional[ScrapedProgram]:
        """
        Scrape a single program's details.

        Args:
            bulletin_id: The numeric ID from the URL
            college_code: The college code (e.g., ARTS, CAES)

        Returns:
            ScrapedProgram object or None if failed
        """
        url = f"{self.BASE_URL}/Program/Details/{bulletin_id}?IDc={college_code}"
        logger.info(f"Scraping program: {url}")

        try:
            await self._page.goto(url, timeout=30000)
            await self._wait_for_content(2000)

            # Get page content
            html = await self._page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Extract program name and degree type from header
            header = soup.find("h3", class_="red") or soup.find("h2")
            if not header:
                logger.warning(f"Could not find program header for {bulletin_id}")
                return None

            header_text = header.get_text(strip=True)
            # Header format: "COMPUTER SCIENCE BS" or "ACCOUNTING MINOR"
            parts = header_text.rsplit(" ", 1)
            if len(parts) == 2:
                name = parts[0].title()
                degree_type = parts[1].upper()
            else:
                name = header_text.title()
                degree_type = "UNKNOWN"

            program = ScrapedProgram(
                bulletin_id=bulletin_id,
                name=name,
                degree_type=degree_type,
                college_code=college_code,
                bulletin_url=url,
            )

            # Extract overview
            overview_section = soup.find("h3", id="OVERVIEW")
            if overview_section:
                overview_content = overview_section.find_next("div", class_="panel")
                if overview_content:
                    program.overview = overview_content.get_text(strip=True)[:5000]

            # Extract department from contact info
            contact_section = soup.find("h3", id="CONTACT")
            if contact_section:
                contact_content = contact_section.find_next("div", class_="panel")
                if contact_content:
                    program.contact_info = contact_content.get_text(strip=True)[:2000]
                    # Try to extract department name
                    dept_match = re.search(r"Department of ([^,\n]+)", program.contact_info)
                    if dept_match:
                        program.department = dept_match.group(1).strip()

            # Extract total hours - first check header, then look for "Total Major Hours" section
            hours_match = re.search(r"(\d+)\s*hours?", header_text, re.IGNORECASE)
            if hours_match:
                program.total_hours = int(hours_match.group(1))

            # Also look for "Total Major Hours (X hours)" section
            total_hours_header = soup.find("h4", string=re.compile(r"Total.*Hours", re.IGNORECASE))
            if total_hours_header:
                total_text = total_hours_header.get_text(strip=True)
                total_match = re.search(r"\((\d+)\s*hours?\)", total_text, re.IGNORECASE)
                if total_match:
                    program.total_hours = int(total_match.group(1))

            # Extract career info
            career_section = soup.find("h3", string=re.compile("CAREER", re.IGNORECASE))
            if career_section:
                career_content = career_section.find_next("div", class_="panel")
                if career_content:
                    program.career_info = career_content.get_text(strip=True)[:3000]

            # Extract transfer info
            transfer_section = soup.find("h3", string=re.compile("TRANSFER", re.IGNORECASE))
            if transfer_section:
                transfer_content = transfer_section.find_next("div", class_="panel")
                if transfer_content:
                    program.transfer_info = transfer_content.get_text(strip=True)[:2000]

            # Extract requirements
            program.requirements = await self._extract_requirements(soup)

            return program

        except Exception as e:
            logger.error(f"Error scraping program {bulletin_id}: {e}")
            return None

    async def _extract_requirements(self, soup: BeautifulSoup) -> list[ScrapedRequirement]:
        """Extract program requirements from parsed HTML."""
        requirements = []

        # Find ALL h4 elements that look like requirements
        # These include: "I. Foundation Courses (9 Hours)", "Required Courses (19 hours)", etc.
        all_h4s = soup.find_all("h4")

        for header in all_h4s:
            header_text = header.get_text(strip=True)

            # Skip non-requirement headers
            skip_keywords = [
                "overview", "contact", "career", "transfer", "entrance",
                "other learning", "student organization", "available graduate",
                "four-year", "college-wide", "university-wide", "franklin college"
            ]
            if any(skip in header_text.lower() for skip in skip_keywords):
                continue

            # Only process headers that have hours or are numbered requirements
            has_hours = re.search(r"\((\d+)(?:-\d+)?\s*hours?\)", header_text, re.IGNORECASE)
            is_numbered = re.match(r"^[IVX]+\.\s+", header_text)  # Roman numerals
            is_major_req = any(kw in header_text.lower() for kw in ["required", "elective", "major"])

            if not (has_hours or is_numbered or is_major_req):
                continue

            # Skip "Total Major Hours" - it's a summary, not a requirement
            if "total" in header_text.lower() and "hours" in header_text.lower():
                continue

            # Parse header for name and hours
            hours_match = re.search(r"\((\d+)(?:-\d+)?\s*hours?\)", header_text, re.IGNORECASE)
            required_hours = int(hours_match.group(1)) if hours_match else None

            # Clean up the name - remove hours, roman numerals, and &nbsp;
            name = re.sub(r"\s*\(\d+(?:-\d+)?\s*hours?\)", "", header_text).strip()
            name = re.sub(r"^[IVX]+\.\s+", "", name).strip()
            name = name.replace("\xa0", " ").strip()  # Remove &nbsp;

            # Determine category
            category = self._categorize_requirement(name)

            req = ScrapedRequirement(
                name=name,
                category=category,
                required_hours=required_hours,
            )

            # Find the associated course tables
            # Structure varies:
            # 1. <button><h4>...</h4></button><div class="panel">tables...</div>
            # 2. <h4 class="red">...</h4> followed by tables as siblings
            # 3. <h4>...</h4> with tables in next panel
            parent = header.parent
            tables_found = []
            desc_parts = []

            # Case 1: h4 is in a button, look for next sibling panel
            if parent and parent.name == "button":
                panel = parent.find_next_sibling("div", class_="panel")
                if panel:
                    # Check if this panel contains nested h4.red requirements
                    # If so, skip this accordion header - we'll process the nested ones separately
                    nested_reqs = panel.find_all("h4", class_="red")
                    if nested_reqs:
                        # This is a parent container, skip it
                        continue

                    tables_found = panel.find_all("table", class_="custom-table")
                    for p in panel.find_all("p"):
                        text = p.get_text(strip=True)
                        if text and len(text) > 10 and "hours" not in text.lower()[:20]:
                            desc_parts.append(text)

            # Case 2: h4.red - tables are siblings within the same parent panel
            if not tables_found and "red" in (header.get("class") or []):
                # Find tables that come after this h4 until the next h4.red
                # h6 elements are sub-headers within this requirement, so don't stop at them
                current = header.find_next_sibling()
                while current:
                    # Only stop at another h4.red (another major requirement section)
                    if current.name == "h4" and "red" in (current.get("class") or []):
                        break
                    if current.name == "table" and "custom-table" in (current.get("class") or []):
                        tables_found.append(current)
                    if current.name == "p":
                        text = current.get_text(strip=True)
                        if text and len(text) > 10:
                            desc_parts.append(text)
                    current = current.find_next_sibling()

            # Case 3: Look in the next panel
            if not tables_found:
                panel = header.find_next("div", class_="panel")
                if panel:
                    tables_found = panel.find_all("table", class_="custom-table")

            # Extract courses from found tables
            for table in tables_found:
                req.courses.extend(self._extract_courses_from_table(table))

            # Set description
            if desc_parts:
                req.description = " | ".join(desc_parts[:3])[:2000]

            # Check for selection requirements
            if req.description:
                choose_match = re.search(r"(?:select|choose)\s+(\d+)", req.description, re.IGNORECASE)
                if choose_match:
                    req.selection_type = "choose"
                    req.courses_to_select = int(choose_match.group(1))

            # Only add if we found courses or it's a known requirement type
            if req.courses or required_hours:
                requirements.append(req)

        return requirements

    def _categorize_requirement(self, name: str) -> str:
        """Categorize a requirement based on its name."""
        name_lower = name.lower()

        if any(kw in name_lower for kw in ["foundation", "core"]):
            return "foundation"
        elif any(kw in name_lower for kw in ["major", "required"]):
            return "major"
        elif any(kw in name_lower for kw in ["elective"]):
            return "elective"
        elif any(kw in name_lower for kw in ["general", "social", "humanities", "arts", "language"]):
            return "gen_ed"
        elif any(kw in name_lower for kw in ["science", "quantitative", "math"]):
            return "foundation"
        else:
            return "other"

    def _extract_courses_from_table(self, table) -> list[ScrapedRequirementCourse]:
        """Extract courses from a requirement table."""
        courses = []

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                # First cell has course code link
                link = cells[0].find("a")
                if link:
                    course_code = link.get_text(strip=True)
                    # Clean up course code (e.g., "CSCI 3030" from "CSCI 3030 ")
                    course_code = re.sub(r"\s+", " ", course_code).strip()
                else:
                    # Might be a group/elective entry
                    course_code = cells[0].get_text(strip=True)

                # Second cell has title
                title = cells[1].get_text(strip=True) if len(cells) > 1 else None

                # Third cell has credit hours
                credit_hours = None
                if len(cells) > 2:
                    try:
                        credit_hours = int(cells[2].get_text(strip=True))
                    except (ValueError, TypeError):
                        pass

                # Check if it's a group (e.g., "CSCI electives")
                is_group = "elective" in course_code.lower() or not re.match(r"^[A-Z]{2,4}\s+\d", course_code)

                courses.append(ScrapedRequirementCourse(
                    course_code=course_code,
                    title=title,
                    credit_hours=credit_hours,
                    is_group=is_group,
                ))

        return courses

    async def scrape_course(self, bulletin_id: str) -> Optional[ScrapedCourse]:
        """
        Scrape a single course's details from the bulletin.

        Args:
            bulletin_id: The numeric course ID from the URL

        Returns:
            ScrapedCourse object or None if failed
        """
        url = f"{self.BASE_URL}/Course/Details/{bulletin_id}"
        logger.info(f"Scraping course: {url}")

        try:
            await self._page.goto(url, timeout=30000)
            await self._wait_for_content(2000)

            html = await self._page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Get course code from li.crn (e.g., "GRMN 2002")
            code_elem = soup.find("li", class_="crn")
            if not code_elem:
                logger.warning(f"Could not find course code for {bulletin_id}")
                return None

            course_code = code_elem.get_text(strip=True)
            # Parse subject and number
            match = re.match(r"([A-Z]{2,4})\s+(\d+[A-Z]*)", course_code)
            if not match:
                logger.warning(f"Could not parse course code: {course_code}")
                return None

            subject = match.group(1)
            course_number = match.group(2)

            # Get title from h1.black.courses
            title_header = soup.find("h1", class_="courses")
            title = title_header.get_text(strip=True) if title_header else course_code

            # Get credit hours from li.credit-number
            hours_elem = soup.find("li", class_="credit-number")
            credit_hours = hours_elem.get_text(strip=True) if hours_elem else None

            course = ScrapedCourse(
                bulletin_id=bulletin_id,
                subject=subject,
                course_number=course_number,
                course_code=f"{subject} {course_number}",
                title=title,
                credit_hours=credit_hours,
                bulletin_url=url,
            )

            # Helper to find field by label in p.large-mws
            def get_field_after_label(label: str) -> Optional[str]:
                """Extract a field value by its p.large-mws label."""
                label_elem = soup.find("p", class_="large-mws", string=label)
                if label_elem:
                    # Get the next sibling p element
                    next_p = label_elem.find_next_sibling("p")
                    if next_p:
                        return next_p.get_text(strip=True)[:5000]
                return None

            # Helper to find list after label
            def get_list_after_label(label: str) -> Optional[str]:
                """Extract list items as text after a p.large-mws label."""
                label_elem = soup.find("p", class_="large-mws", string=label)
                if label_elem:
                    ul = label_elem.find_next_sibling("ul")
                    if ul:
                        items = [li.get_text(strip=True) for li in ul.find_all("li")]
                        return " | ".join(items)[:5000]
                return None

            # Course Description
            course.description = get_field_after_label("Course Description")

            # Athena Title
            course.athena_title = get_field_after_label("Athena Title")

            # Prerequisites
            course.prerequisites = get_field_after_label("Prerequisite")

            # Corequisites
            course.corequisites = get_field_after_label("Corequisite")

            # Equivalent Courses
            course.equivalent_courses = get_field_after_label("Equivalent Courses")

            # Semester Offered
            course.semester_offered = get_field_after_label("Semester Course Offered")

            # Grading System
            course.grading_system = get_field_after_label("Grading System")

            # Student Learning Outcomes (it's a ul list)
            course.learning_outcomes = get_list_after_label("Student learning Outcomes")

            # Topical Outline (it's a ul list)
            course.topical_outline = get_list_after_label("Topical Outline")

            return course

        except Exception as e:
            logger.error(f"Error scraping course {bulletin_id}: {e}")
            return None

    def save_program(self, scraped: ScrapedProgram) -> Program:
        """Save a scraped program to the database."""
        with self.session_factory() as session:
            # Check for existing program
            existing = session.execute(
                select(Program).where(Program.bulletin_id == scraped.bulletin_id)
            ).scalar_one_or_none()

            if existing:
                # Update existing program
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
                # Create new program
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
                    # Try to link to bulletin_course
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
        with self.session_factory() as session:
            # Check for existing course
            existing = session.execute(
                select(BulletinCourse).where(BulletinCourse.bulletin_id == scraped.bulletin_id)
            ).scalar_one_or_none()

            if existing:
                # Update existing course
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


async def scrape_all_programs(
    program_types: list[str] = None,
    limit: int = None,
    save_to_db: bool = True
) -> list[ScrapedProgram]:
    """
    Scrape all programs of specified types.

    Args:
        program_types: List of program types (UG, GM, MINOR, etc.)
        limit: Maximum number of programs to scrape
        save_to_db: Whether to save to database

    Returns:
        List of ScrapedProgram objects
    """
    if program_types is None:
        # All program types: Undergraduate, Graduate, Minors, Certificates, Professional
        program_types = ["UG", "GM", "MINOR", "CERT-UG", "CERT-GM", "PR"]

    async with BulletinScraper() as scraper:
        # Search each type separately to avoid pagination issues
        program_list = []
        seen_ids = set()

        for ptype in program_types:
            logger.info(f"Searching for {ptype} programs...")
            results = await scraper.search_programs(program_types=[ptype])
            for item in results:
                # Deduplicate by bulletin_id
                if item[1] not in seen_ids:
                    program_list.append(item)
                    seen_ids.add(item[1])
            logger.info(f"  Found {len(results)} {ptype} programs ({len(program_list)} total unique)")
            await asyncio.sleep(1)  # Be nice to the server

        logger.info(f"Total unique programs found: {len(program_list)}")

        if limit:
            program_list = program_list[:limit]

        programs = []
        for name, bulletin_id, college_code in program_list:
            logger.info(f"Scraping: {name} ({bulletin_id})")
            program = await scraper.scrape_program(bulletin_id, college_code)

            if program:
                programs.append(program)
                if save_to_db:
                    scraper.save_program(program)
                logger.info(f"  -> {len(program.requirements)} requirements")

            # Small delay to be nice to the server
            await asyncio.sleep(0.5)

        return programs


async def scrape_courses_from_programs(programs: list[ScrapedProgram], save_to_db: bool = True) -> list[ScrapedCourse]:
    """
    Scrape all courses referenced in programs.

    Args:
        programs: List of scraped programs
        save_to_db: Whether to save to database

    Returns:
        List of ScrapedCourse objects
    """
    # Collect unique course bulletin IDs
    course_ids = set()
    for program in programs:
        for req in program.requirements:
            for course in req.courses:
                if not course.is_group:
                    # Extract bulletin ID from course code if possible
                    # This requires scraping the course search
                    pass

    # For now, we'll need to search for courses separately
    # TODO: Implement course ID extraction from program pages

    return []


# CLI helper for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    async def main():
        # Test scraping a single program
        async with BulletinScraper() as scraper:
            # Search for CS programs
            programs = await scraper.search_programs(keyword="Computer Science", program_types=["UG"])
            print(f"Found {len(programs)} programs")

            for name, bid, college in programs[:5]:
                print(f"  {name}: {bid} ({college})")

            # Scrape the first one
            if programs:
                name, bid, college = programs[0]
                program = await scraper.scrape_program(bid, college)
                if program:
                    print(f"\nProgram: {program.name} ({program.degree_type})")
                    print(f"Department: {program.department}")
                    print(f"Total Hours: {program.total_hours}")
                    print(f"Requirements: {len(program.requirements)}")
                    for req in program.requirements:
                        print(f"  - {req.name} ({req.required_hours} hrs): {len(req.courses)} courses")

    asyncio.run(main())
