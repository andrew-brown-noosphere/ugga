"""
Robust PDF parser for UGA Schedule of Classes.

Handles the complex format of UGA's online class schedule PDFs including:
- Course lines with subject, number, title, department, URL
- Section lines with CRN, section, status, credits, instructor, term, capacity
- Multi-section courses
- Variable credit hours (e.g., "1 - 3")
- Missing instructors/sections
- Negative seat availability (waitlist)
- Courses spanning multiple pages
"""
import re
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import pdfplumber

from src.models.course import Course, CourseSection, Schedule, ScheduleMetadata

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a PDF."""
    schedule: Schedule
    errors: list[str]
    warnings: list[str]


class UGAPDFParser:
    """Parser for UGA Schedule of Classes PDFs."""

    # Known UGA departments (extracted from actual PDFs)
    # Ordered by specificity (longest first for greedy matching)
    KNOWN_DEPARTMENTS = [
        # Full names
        "Workforce Ed & Instruct Tech",
        "Comm Sci and Special Ed",
        "Lifelong Ed, Admin, and Policy",
        "Finan Plan Hous and Cons",
        "Ag Leadership, Edu, and",  # truncated in PDF
        "Food Science and Technology",
        "Math, Sci, & Social Studies Ed",
        "Educational Theory and Pract",
        "Language and Literacy Educ",
        "Nonprofit Mgmt and Lead",
        "Counseling and Human Dev",
        "Large Animal Medicine",
        "Small Animal Medicine",
        "Management Information",
        "Educational Psychology",
        "Nutritional Sciences",
        "School of Accounting",
        "Biomedical Sciences",
        "New Media Institute",
        "Population Health",
        "Student Success &",
        "Political Science",
        "Executive MBA",
        "Anthropology",
        "Music Education",
        "Human Resources",
        "Public Health",
        "Marketing",
        "Finance",
        "Psychology",
        "Kinesiology",
        "Geography",
        "Sociology",
        "Economics",
        "Statistics",
        "Engineering",
        "School of Art",
        # Generic patterns
    ]

    # Patterns for identifying line types
    HEADER_PATTERNS = [
        r'^Online Class Schedule For The Term',
        r'^Report ID: Schedule of Online Classes',
        r'^Report Run Date:',
        r'^SUBJECT COURSE NO TITLE',
        r'^CLS SEATS$',
        r'^CRN SEC STAT CREDIT',
        r'^Grey text that is crossed out',
    ]

    FOOTER_PATTERN = r'^Report ID: Schedule of Online Classes.*Page: \d+ of \d+'

    # Parts of term we recognize
    TERM_PATTERNS = [
        'Full Term',
        'EMBA Term 1', 'EMBA Term 2',
        'PMBA Term 1', 'PMBA Term 2',
        'Law Term',
        'First Half', 'Second Half',
        'Maymester', 'Summer',
    ]

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self._current_course: Optional[Course] = None
        self._courses: dict[str, Course] = {}  # Key: course_code

        # Build department regex - sort by length (longest first)
        sorted_depts = sorted(self.KNOWN_DEPARTMENTS, key=len, reverse=True)
        escaped_depts = [re.escape(d) for d in sorted_depts]
        self._dept_pattern = re.compile(r'\s+(' + '|'.join(escaped_depts) + r')$', re.IGNORECASE)

    def parse_file(self, file_path: str | Path, source_url: str = "") -> ParseResult:
        """Parse a UGA schedule PDF file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.errors = []
        self.warnings = []
        self._courses = {}
        self._current_course = None

        metadata = ScheduleMetadata(
            term="",
            source_url=source_url,
            parse_date=datetime.now(),
        )

        with pdfplumber.open(file_path) as pdf:
            logger.info(f"Parsing PDF with {len(pdf.pages)} pages")

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    self.warnings.append(f"Page {page_num}: No text extracted")
                    continue

                lines = text.split('\n')
                self._parse_page_lines(lines, page_num, metadata)

        # Finalize
        courses = list(self._courses.values())
        metadata.total_courses = len(courses)
        metadata.total_sections = sum(len(c.sections) for c in courses)

        schedule = Schedule(metadata=metadata, courses=courses)

        logger.info(
            f"Parsed {metadata.total_courses} courses with "
            f"{metadata.total_sections} sections"
        )

        return ParseResult(
            schedule=schedule,
            errors=self.errors,
            warnings=self.warnings
        )

    def _parse_page_lines(
        self,
        lines: list[str],
        page_num: int,
        metadata: ScheduleMetadata
    ) -> None:
        """Parse lines from a single page."""
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            # Extract metadata from first page
            if page_num == 1:
                if 'For The Term' in line:
                    match = re.search(r'Term\s*(\w+\s*\d{4})', line)
                    if match:
                        metadata.term = match.group(1)
                elif 'Report Run Date:' in line:
                    match = re.search(r'Report Run Date:\s*(.+)', line)
                    if match:
                        metadata.report_date = match.group(1).strip()

            # Skip headers and footers
            if self._is_header_or_footer(line):
                continue

            # Try to parse as course line
            course = self._try_parse_course_line(line)
            if course:
                self._add_or_merge_course(course)
                continue

            # Try to parse as section line
            section = self._try_parse_section_line(line, page_num, line_num)
            if section and self._current_course:
                self._current_course.sections.append(section)
                continue

            # If we couldn't parse the line and it's not empty/header
            if len(line) > 10 and not self._is_header_or_footer(line):
                self.warnings.append(
                    f"Page {page_num}, line {line_num}: Could not parse: {line[:80]}"
                )

    def _is_header_or_footer(self, line: str) -> bool:
        """Check if line is a header or footer to skip."""
        for pattern in self.HEADER_PATTERNS:
            if re.match(pattern, line):
                return True
        if re.match(self.FOOTER_PATTERN, line):
            return True
        return False

    def _try_parse_course_line(self, line: str) -> Optional[Course]:
        """Try to parse a line as a course definition."""
        # Course lines start with: SUBJECT (2-5 uppercase letters) + space + COURSE_NUM (4 digits + optional letter)
        # Section lines start with 5-digit CRN, so we can distinguish them

        # Skip if line starts with a digit (likely a section line)
        if line and line[0].isdigit():
            return None

        # Check for bulletin URL format (original format)
        if 'bulletin.uga.edu' in line:
            parts = line.split('http')
            if len(parts) == 2:
                text_part = parts[0].strip()
                url = 'http' + parts[1].strip()
                match = re.match(r'^([A-Z]{2,5})\s+(\d{4}[A-Z]?)\s+(.+)', text_part)
                if match:
                    subject = match.group(1)
                    course_num = match.group(2)
                    remainder = match.group(3).strip()
                    title, department = self._split_title_department(remainder)
                    return Course(
                        subject=subject,
                        course_number=course_num,
                        title=title,
                        department=department,
                        bulletin_url=url,
                    )

        # Parse format without URL: "AAEC 2580 Appl Microeconomic Principles Agricultural and Applied Econ"
        match = re.match(r'^([A-Z]{2,5})\s+(\d{4}[A-Z]?[L]?)\s+(.+)', line)
        if not match:
            return None

        subject = match.group(1)
        course_num = match.group(2)
        remainder = match.group(3).strip()

        # Make sure this isn't actually a section line that got mismatched
        # Section lines have patterns like "0 A 3.0" after the CRN
        if re.match(r'^\d+\s+[A-Z]\s+\d+\.\d+', remainder):
            return None

        # Try to split title and department using known departments
        title, department = self._split_title_department(remainder)

        return Course(
            subject=subject,
            course_number=course_num,
            title=title,
            department=department,
            bulletin_url=None,
        )

    def _split_title_department(self, text: str) -> tuple[str, str]:
        """Split combined title+department text into separate parts."""
        # Try matching known departments
        match = self._dept_pattern.search(text)
        if match:
            department = match.group(1)
            title = text[:match.start()].strip()
            return title, department

        # Fallback: look for common department indicators
        dept_indicators = [
            r'\s+(School of \w+)$',
            r'\s+(College of \w+)$',
            r'\s+(Dept\.? of \w+)$',
            r'\s+(\w+ Sciences?)$',
            r'\s+(\w+ Education)$',
            r'\s+(\w+ Psychology)$',
            r'\s+(\w+ Studies)$',
        ]

        for pattern in dept_indicators:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return text[:match.start()].strip(), match.group(1)

        # Last fallback: if we have many words, assume last 2-4 are department
        words = text.split()
        if len(words) > 4:
            # Look for a word that's likely a department start
            for i in range(len(words) - 1, 1, -1):
                word = words[i]
                # Department names often contain these
                if word.lower() in ['ed', 'tech', 'sci', 'and', '&']:
                    continue
                # Check if this could be department start
                if word[0].isupper() and len(word) > 2:
                    # Check if remaining words look like a department
                    potential_dept = ' '.join(words[i:])
                    if len(potential_dept) >= 8:  # Reasonable department name length
                        return ' '.join(words[:i]), potential_dept

            # Ultimate fallback
            title = ' '.join(words[:-3]) if len(words) > 3 else ' '.join(words[:-2])
            dept = ' '.join(words[-3:]) if len(words) > 3 else ' '.join(words[-2:])
            return title, dept

        return text, ""

    # Campus names we recognize
    CAMPUS_NAMES = ['Athens', 'Tifton', 'Griffin', 'Gwinnett', 'Online', 'Washington']

    # Day pattern - single letters that represent days
    DAY_LETTERS = set(['M', 'T', 'W', 'R', 'F', 'S', 'U'])  # U = Sunday

    def _try_parse_section_line(
        self,
        line: str,
        page_num: int,
        line_num: int
    ) -> Optional[CourseSection]:
        """
        Try to parse a line as a section definition.

        PDF Format example:
        61007 0 A 3.0 - 3.0 T R 11:35 am-12:55 pm 1011 0104 Athens Colson 1 100 36

        Tokenization:
        61007, 0, A, 3.0, -, 3.0, T, R, 11:35, am-12:55, pm, 1011, 0104, Athens, Colson, 1, 100, 36
        CRN   SEC ST CRED      DAYS    TIME (split)         BLDG  ROOM  CAMPUS INSTR   T SIZE AVL
        """
        # Section lines start with a 5-digit CRN
        if not re.match(r'^\d{5}\s', line):
            return None

        # Tokenize the line
        tokens = line.split()
        if len(tokens) < 5:
            return None

        try:
            crn = tokens[0]
            idx = 1

            # Section number (optional, 1-3 alphanumeric chars)
            section = ""
            if idx + 1 < len(tokens):
                current = tokens[idx]
                next_tok = tokens[idx + 1]
                if next_tok in ['A', 'X']:
                    if current not in ['A', 'X']:
                        section = current
                        idx += 1
                    elif current == next_tok:
                        section = current
                        idx += 1

            # Status (A or X)
            if idx >= len(tokens):
                return None
            status = tokens[idx]
            if status not in ['A', 'X']:
                self.warnings.append(
                    f"Page {page_num}, line {line_num}: Unexpected status '{status}' in: {line[:60]}"
                )
                return None
            idx += 1

            # Credit hours - can be "3" or "1 - 3" or "1.0 - 3.0"
            if idx >= len(tokens):
                return None
            credit_str = tokens[idx]
            idx += 1

            while idx < len(tokens) and tokens[idx] == '-':
                idx += 1
                if idx < len(tokens):
                    credit_str = f"{credit_str} - {tokens[idx]}"
                    idx += 1

            credit_hours = self._parse_credits(credit_str)

            # Parse from the end: SIZE AVL are last two, then TERM (1 digit), INSTRUCTOR, CAMPUS
            # Last two tokens are SIZE and AVL
            class_size = 0
            seats_available = 0
            try:
                seats_available = int(tokens[-1])
                class_size = int(tokens[-2])
            except (ValueError, IndexError):
                pass

            # Third from last is TERM (single digit like "1")
            part_of_term = "Full Term"

            # Fourth from last is INSTRUCTOR
            instructor = None
            instructor_idx = len(tokens) - 4
            if instructor_idx >= idx:
                instructor = tokens[instructor_idx]

            # Fifth from last is CAMPUS
            campus = None
            campus_idx = len(tokens) - 5
            if campus_idx >= idx:
                potential_campus = tokens[campus_idx]
                if potential_campus in self.CAMPUS_NAMES:
                    campus = potential_campus

            # Now parse the middle portion: DAYS TIME BLDG ROOM
            # Start from idx (after credits) and go until campus_idx
            middle_end = campus_idx if campus else instructor_idx
            middle_tokens = tokens[idx:middle_end] if middle_end > idx else []

            days = None
            start_time = None
            end_time = None
            building = None
            room = None

            if middle_tokens:
                # Collect day letters (M, T, W, R, F, S, U or TBA)
                day_tokens = []
                time_parts = []
                location_tokens = []

                i = 0
                # First, collect day letters
                while i < len(middle_tokens):
                    tok = middle_tokens[i]
                    if tok in self.DAY_LETTERS:
                        day_tokens.append(tok)
                        i += 1
                    elif tok == 'TBA':
                        day_tokens.append(tok)
                        i += 1
                    else:
                        break

                # Next, collect time parts - they contain : or am/pm patterns
                # Time format when split: "11:35" "am-12:55" "pm"
                while i < len(middle_tokens):
                    tok = middle_tokens[i]
                    # Check if this looks like a time component
                    if ':' in tok or tok.lower() in ['am', 'pm'] or '-' in tok and ('am' in tok.lower() or 'pm' in tok.lower()):
                        time_parts.append(tok)
                        i += 1
                    else:
                        break

                # Remaining tokens before campus are building/room
                while i < len(middle_tokens):
                    tok = middle_tokens[i]
                    if tok not in self.CAMPUS_NAMES:
                        location_tokens.append(tok)
                    i += 1

                # Process days
                if day_tokens:
                    days = ' '.join(day_tokens)

                # Process time - reassemble from parts
                if time_parts:
                    time_str = ' '.join(time_parts)
                    # Try to extract start and end time from combined string
                    # Format: "11:35 am-12:55 pm" or "11:35" "am-12:55" "pm" -> "11:35 am-12:55 pm"
                    time_match = re.search(
                        r'(\d{1,2}:\d{2})\s*([ap]m)?\s*-\s*(\d{1,2}:\d{2})\s*([ap]m)?',
                        time_str,
                        re.IGNORECASE
                    )
                    if time_match:
                        start_h = time_match.group(1)
                        start_ampm = time_match.group(2) or ''
                        end_h = time_match.group(3)
                        end_ampm = time_match.group(4) or ''

                        # If we have the am/pm in the middle part (like "am-12:55"), extract it
                        if not start_ampm:
                            # Look for am/pm before the dash
                            prefix_match = re.search(r'([ap]m)\s*-', time_str, re.IGNORECASE)
                            if prefix_match:
                                start_ampm = prefix_match.group(1)

                        if start_ampm:
                            start_time = f"{start_h} {start_ampm}"
                        else:
                            start_time = start_h
                        if end_ampm:
                            end_time = f"{end_h} {end_ampm}"
                        else:
                            end_time = end_h

                # Process building and room
                if len(location_tokens) >= 2:
                    building = location_tokens[0]
                    room = location_tokens[1]
                elif len(location_tokens) == 1:
                    building = location_tokens[0]

            return CourseSection(
                crn=crn,
                section=section,
                status=status,
                credit_hours=credit_hours,
                instructor=instructor,
                part_of_term=part_of_term,
                class_size=class_size,
                seats_available=seats_available,
                days=days,
                start_time=start_time,
                end_time=end_time,
                building=building,
                room=room,
                campus=campus,
            )

        except (IndexError, ValueError) as e:
            self.warnings.append(
                f"Page {page_num}, line {line_num}: Parse error: {e} - {line[:50]}"
            )
            return None

    def _parse_credits(self, credit_str: str) -> int:
        """Parse credit hours, handling variable credits like '1 - 3' or '3.0 - 3.0'."""
        try:
            if '-' in credit_str:
                # Variable credits - take the max
                parts = credit_str.split('-')
                return int(float(parts[-1].strip()))
            return int(float(credit_str))
        except (ValueError, TypeError):
            return 0

    def _add_or_merge_course(self, course: Course) -> None:
        """Add a new course or merge with existing (for courses spanning pages)."""
        course_code = course.course_code
        if course_code in self._courses:
            # Course already exists (likely spanning pages)
            self._current_course = self._courses[course_code]
            logger.debug(f"Merging sections for {course_code}")
        else:
            self._courses[course_code] = course
            self._current_course = course


def parse_uga_schedule(file_path: str | Path, source_url: str = "") -> ParseResult:
    """Convenience function to parse a UGA schedule PDF."""
    parser = UGAPDFParser()
    return parser.parse_file(file_path, source_url)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "schedule_spring.pdf"

    result = parse_uga_schedule(pdf_path, "https://apps.reg.uga.edu/soc/OnlineSOCspring.pdf")

    print(f"\n=== Parse Results ===")
    print(f"Term: {result.schedule.metadata.term}")
    print(f"Total Courses: {result.schedule.metadata.total_courses}")
    print(f"Total Sections: {result.schedule.metadata.total_sections}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")

    if result.errors:
        print(f"\n=== Errors ===")
        for err in result.errors[:10]:
            print(f"  - {err}")

    if result.warnings:
        print(f"\n=== Warnings (first 10) ===")
        for warn in result.warnings[:10]:
            print(f"  - {warn}")

    print(f"\n=== Sample Courses ===")
    for course in result.schedule.courses[:5]:
        print(f"\n{course.course_code}: {course.title}")
        print(f"  Department: {course.department}")
        print(f"  Sections: {len(course.sections)}")
        for section in course.sections[:3]:
            print(f"    - CRN {section.crn} (sec {section.section}): "
                  f"{section.instructor or 'TBD'}, "
                  f"{section.seats_available}/{section.class_size} seats, "
                  f"{section.credit_hours} hrs")
