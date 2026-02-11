"""
UGA Schedule of Classes Web Scanner.

Scans the schedule from reg.uga.edu by downloading the official CSV export.
This is much faster and more reliable than page scraping.

Features:
- Downloads official CSV from UGA registrar
- Parses building and room data for campus mapping
- Supports all available terms (Spring, Summer, Fall)
- Real-time seat availability updates
"""
import asyncio
import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from src.models.course import Course, CourseSection, Schedule, ScheduleMetadata

logger = logging.getLogger(__name__)


@dataclass
class ScanProgress:
    """Progress update during scanning."""
    sections_found: int
    courses_found: int
    term: str
    status: str = "in_progress"
    error: Optional[str] = None


@dataclass
class BuildingInfo:
    """Building and room information for campus mapping."""
    name: str
    room: str
    campus: str


class UGAScheduleScanner:
    """Scans UGA Schedule of Classes using CSV export."""

    BASE_URL = "https://reg.uga.edu/registration/schedule-of-classes/"

    # CSV download URLs by term
    CSV_URLS = {
        "Spring 2026": "https://apps.reg.uga.edu/soc/spring.csv",
        "Summer 2026": "https://apps.reg.uga.edu/soc/summer.csv",
        "Fall 2026": "https://apps.reg.uga.edu/soc/fall.csv",
    }

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None

    async def get_available_terms(self) -> list[str]:
        """Get list of available terms."""
        return list(self.CSV_URLS.keys())

    async def scan_term(
        self,
        term: str,
        progress_callback: Optional[callable] = None
    ) -> Schedule:
        """
        Scan all courses for a given term by downloading the CSV.

        Args:
            term: Term identifier (e.g., "Spring 2026")
            progress_callback: Optional async callback for progress updates

        Returns:
            Schedule object with all courses and sections
        """
        csv_url = self.CSV_URLS.get(term)
        if not csv_url:
            raise ValueError(f"Unknown term: {term}. Available: {list(self.CSV_URLS.keys())}")

        logger.info(f"Downloading CSV for {term} from {csv_url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(csv_url)
            response.raise_for_status()
            csv_content = response.text

        logger.info(f"Downloaded {len(csv_content)} bytes, parsing...")

        # Parse CSV
        courses, total_sections = self._parse_csv(csv_content)

        # Build schedule
        metadata = ScheduleMetadata(
            term=term,
            source_url=csv_url,
            parse_date=datetime.now(),
            report_date=datetime.now().strftime("%m/%d/%Y"),
            total_courses=len(courses),
            total_sections=total_sections
        )

        schedule = Schedule(metadata=metadata, courses=list(courses.values()))

        logger.info(
            f"Completed {term}: {metadata.total_courses} courses, "
            f"{metadata.total_sections} sections"
        )

        if progress_callback:
            await progress_callback(ScanProgress(
                sections_found=total_sections,
                courses_found=len(courses),
                term=term,
                status="complete"
            ))

        return schedule

    def _parse_csv(self, csv_content: str) -> tuple[dict[str, Course], int]:
        """
        Parse the CSV content from UGA registrar.

        Actual CSV columns from apps.reg.uga.edu:
        - SCHEDULE_OFFERING.SUBJECT, SCHEDULE_OFFERING.COURSE_NUMBER
        - SCHEDULE_OFFERING.TITLE_LONG_DESC
        - SCHEDULE_OFFERING.COURSE_REFERENCE_NUMBER (CRN)
        - SCHEDULE_OFFERING.MAX_CREDITS
        - Time, Building, MEETING_TIME.BUILDING_DESC, Room
        - SCHEDULE_OFFERING.PRIMARY_INSTRUCTOR_FIRST_NAME/LAST_NAME
        - SCHEDULE_OFFERING.CAMPUS_DESC
        - SCHEDULE_OFFERING.MAXIMUM_ENROLLMENT, SCHEDULE_OFFERING.SEATS_AVAILABLE
        - MEETING_TIME.MONDAY_IND through SUNDAY_IND for days

        Returns:
            Tuple of (courses dict, total sections count)
        """
        courses: dict[str, Course] = {}
        total_sections = 0

        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            try:
                # Extract fields from actual UGA CSV columns
                subject = row.get('SCHEDULE_OFFERING.SUBJECT', '')
                course_number = row.get('SCHEDULE_OFFERING.COURSE_NUMBER', '')
                title = row.get('SCHEDULE_OFFERING.TITLE_LONG_DESC', row.get('SCHEDULE_OFFERING.TITLE_SHORT_DESC', ''))
                crn = row.get('SCHEDULE_OFFERING.COURSE_REFERENCE_NUMBER', '')
                credits = row.get('SCHEDULE_OFFERING.MAX_CREDITS', row.get('SCHEDULE_OFFERING.MIN_CREDITS', ''))
                time_str = row.get('Time', '')
                building_code = row.get('Building', '')
                building_name = row.get('MEETING_TIME.BUILDING_DESC', '')
                room = row.get('Room', '')
                instructor_first = row.get('SCHEDULE_OFFERING.PRIMARY_INSTRUCTOR_FIRST_NAME', '')
                instructor_last = row.get('SCHEDULE_OFFERING.PRIMARY_INSTRUCTOR_LAST_NAME', '')
                campus = row.get('SCHEDULE_OFFERING.CAMPUS_DESC', row.get('MEETING_TIME.COURSE_CAMPUS_DESC', ''))
                part_of_term = row.get('STVPTRM.STVPTRM_DESC', 'Full Term')
                max_seats = row.get('SCHEDULE_OFFERING.MAXIMUM_ENROLLMENT', '0')
                avail_seats = row.get('SCHEDULE_OFFERING.SEATS_AVAILABLE', '0')
                department = row.get('SCHEDULE_OFFERING.DEPARTMENT_DESC', '')
                college = row.get('SCHEDULE_OFFERING.COLLEGE_DESC', '')
                section = row.get('MEETING_TIME.SECTION', '')

                # Build days string from individual indicators
                days = self._build_days_string(row)

                # Build instructor name
                instructor = f"{instructor_first} {instructor_last}".strip() if instructor_first or instructor_last else None

                # Use building name if available, otherwise code
                building = building_name if building_name else building_code

                # Skip if missing essential fields
                if not subject or not course_number:
                    continue

                # Parse time
                start_time, end_time = self._parse_time(time_str)

                # Parse numeric values
                try:
                    credit_hours = int(float(credits)) if credits else 0
                except ValueError:
                    credit_hours = 0

                try:
                    class_size = int(max_seats) if max_seats else 0
                    seats_available = int(avail_seats) if avail_seats else 0
                except ValueError:
                    class_size = 0
                    seats_available = 0

                # Clean building/room
                building = building.strip() if building else None
                room = room.strip() if room else None

                # Create section
                section_obj = CourseSection(
                    crn=str(crn).strip(),
                    section=str(section).strip() if section else "",
                    status="A" if seats_available > 0 else "C",
                    credit_hours=credit_hours,
                    instructor=instructor.strip() if instructor else None,
                    part_of_term=part_of_term.strip() if part_of_term else "Full Term",
                    class_size=class_size,
                    seats_available=seats_available,
                    days=days.strip() if days else None,
                    start_time=start_time,
                    end_time=end_time,
                    building=building,
                    room=room,
                    campus=campus.strip() if campus else None,
                )

                # Add to course (create if doesn't exist)
                course_key = f"{subject} {course_number}"
                if course_key not in courses:
                    courses[course_key] = Course(
                        subject=subject,
                        course_number=course_number,
                        title=title.strip() if title else "",
                        department="",  # Not provided
                    )

                courses[course_key].sections.append(section_obj)
                total_sections += 1

            except Exception as e:
                logger.debug(f"Error parsing row: {e}")
                continue

        return courses, total_sections

    def _build_days_string(self, row: dict) -> Optional[str]:
        """Build days string from individual day indicators (M, T, W, R, F, S, U)."""
        days = []
        day_map = [
            ('MEETING_TIME.MONDAY_IND', 'M'),
            ('MEETING_TIME.TUESDAY_IND', 'T'),
            ('MEETING_TIME.WEDNESDAY_IND', 'W'),
            ('MEETING_TIME.THURSDAY_IND', 'R'),
            ('MEETING_TIME.FRIDAY_IND', 'F'),
            ('MEETING_TIME.SATURDAY_IND', 'S'),
            ('MEETING_TIME.SUNDAY_IND', 'U'),
        ]

        for col, day_char in day_map:
            val = row.get(col, '').strip()
            # CSV uses the day letter itself as indicator (M, T, W, R, F, S, U)
            # or could be 1, Y, etc.
            if val and val.upper() in ('M', 'T', 'W', 'R', 'F', 'S', 'U', '1', 'Y', 'YES', 'TRUE', 'X'):
                days.append(day_char)

        return ''.join(days) if days else None

    def _parse_course_id(self, course_id: str) -> tuple[str, str]:
        """Parse 'AAEC 2580' into ('AAEC', '2580')."""
        if not course_id:
            return "", ""
        match = re.match(r'^([A-Z]{2,5})\s+(\d{4}[A-Z]?L?)$', course_id.strip())
        if match:
            return match.group(1), match.group(2)
        return "", ""

    def _parse_time(self, time_str: str) -> tuple[Optional[str], Optional[str]]:
        """Parse '11:35 am-12:55 pm' into ('11:35 am', '12:55 pm')."""
        if not time_str or time_str.upper() == 'TBA':
            return None, None

        # Handle various separators
        time_str = time_str.replace('\n', ' ').replace('  ', ' ').strip()

        # Try to split on dash
        parts = re.split(r'\s*-\s*', time_str)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

        return time_str.strip(), None

    async def update_seat_availability(self, term: str) -> dict[str, dict]:
        """
        Quick scan to update only seat availability.
        Returns dict of CRN -> {class_size, seats_available, building, room}
        """
        schedule = await self.scan_term(term)
        availability: dict[str, dict] = {}

        for course in schedule.courses:
            for section in course.sections:
                availability[section.crn] = {
                    'class_size': section.class_size,
                    'seats_available': section.seats_available,
                    'building': section.building,
                    'room': section.room,
                }

        logger.info(f"Updated availability for {len(availability)} sections")
        return availability

    async def get_all_buildings(self, term: str) -> dict[str, set[str]]:
        """
        Get all unique buildings and their rooms for campus mapping.
        Returns dict of building_name (campus) -> set of room numbers
        """
        schedule = await self.scan_term(term)
        buildings: dict[str, set[str]] = {}

        for course in schedule.courses:
            for section in course.sections:
                if section.building:
                    key = f"{section.building} ({section.campus})" if section.campus else section.building
                    if key not in buildings:
                        buildings[key] = set()
                    if section.room:
                        buildings[key].add(section.room)

        logger.info(f"Found {len(buildings)} buildings")
        return buildings

    # === Browser-based methods (fallback or for additional data) ===

    async def _create_browser(self):
        """Create browser with stealth settings."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self._context = await self._browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await self._context.new_page()
        return page

    async def _close_browser(self):
        """Close browser resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_csv_download_urls(self) -> dict[str, str]:
        """
        Get current CSV download URLs from the website.
        Useful for discovering new terms or updated URLs.
        """
        page = await self._create_browser()
        urls = {}

        try:
            await page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)

            # Find download links
            download_links = await page.query_selector_all('a[href*=".csv"]')
            for link in download_links:
                href = await link.get_attribute('href')
                title = await link.get_attribute('title') or ''

                # Extract term from title or URL
                if 'spring' in href.lower():
                    urls['Spring 2026'] = href
                elif 'summer' in href.lower():
                    urls['Summer 2026'] = href
                elif 'fall' in href.lower():
                    urls['Fall 2026'] = href

            return urls

        finally:
            await self._close_browser()


# Convenience function
async def scan_schedule(term: str) -> Schedule:
    """Scan UGA schedule for a term."""
    scanner = UGAScheduleScanner(headless=True)
    return await scanner.scan_term(term)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    term = sys.argv[1] if len(sys.argv) > 1 else "Spring 2026"

    async def main():
        scanner = UGAScheduleScanner(headless=True)

        print(f"\n=== Scanning {term} ===\n")
        schedule = await scanner.scan_term(term)

        print(f"\n=== Scan Results ===")
        print(f"Term: {schedule.metadata.term}")
        print(f"Total Courses: {schedule.metadata.total_courses}")
        print(f"Total Sections: {schedule.metadata.total_sections}")

        print(f"\n=== Sample Courses ===")
        for course in schedule.courses[:10]:
            print(f"\n{course.course_code}: {course.title}")
            print(f"  Sections: {len(course.sections)}")
            for section in course.sections[:2]:
                location = f"{section.building} {section.room}" if section.building else "TBA"
                print(f"    - CRN {section.crn}: {section.instructor or 'TBD'}, "
                      f"{section.days or 'TBA'} {section.start_time or ''}-{section.end_time or ''}, "
                      f"{location}, "
                      f"{section.seats_available}/{section.class_size} seats")

        # Also show building summary
        print(f"\n=== Building Summary (Top 20) ===")
        buildings = await scanner.get_all_buildings(term)
        for bldg, rooms in sorted(buildings.items(), key=lambda x: -len(x[1]))[:20]:
            print(f"  {bldg}: {len(rooms)} rooms")

    asyncio.run(main())
