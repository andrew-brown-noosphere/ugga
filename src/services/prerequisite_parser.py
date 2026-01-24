"""
Prerequisite Parser Service.

Parses prerequisite text from UGA Bulletin into structured relationships.
Designed to populate CoursePrerequisite and CourseEquivalent tables
for later Neo4j export.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from src.models.database import (
    BulletinCourse, CoursePrerequisite, CourseEquivalent, CourseUnlock,
    get_engine, get_session_factory, init_db
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedPrerequisite:
    """A parsed prerequisite relationship."""
    course_code: str
    relation_type: str = "prerequisite"  # prerequisite, corequisite, recommended
    group_id: int = 0  # Same group_id = OR alternatives
    min_grade: Optional[str] = None
    concurrent_allowed: bool = False


@dataclass
class ParsedEquivalent:
    """A parsed equivalence relationship."""
    course_code: str
    equivalent_code: str
    equivalence_type: str = "full"  # full, partial, honors


@dataclass
class PrerequisiteParseResult:
    """Result of parsing a prerequisite string."""
    prerequisites: list[ParsedPrerequisite] = field(default_factory=list)
    corequisites: list[ParsedPrerequisite] = field(default_factory=list)
    equivalents: list[ParsedEquivalent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PrerequisiteParser:
    """
    Parses prerequisite and equivalent course text into structured data.

    Handles common patterns:
    - "CSCI 1301" (simple prerequisite)
    - "CSCI 1301 or CSCI 1301H" (OR group)
    - "CSCI 1301 and MATH 2250" (AND - separate groups)
    - "CSCI 1301 with a minimum grade of C" (grade requirement)
    - "(CSCI 1301 or CSCI 1301H) and MATH 2250" (nested groups)
    - "Not open to students with credit in CSCI 3030E" (equivalent)
    """

    # Course code pattern: 2-4 letter subject + 4 digit number + optional letter
    COURSE_PATTERN = r'\b([A-Z]{2,4})\s*(\d{4}[A-Z]?(?:[/-]\d{4}[A-Z]?)?)\b'

    # Grade pattern
    GRADE_PATTERN = r'(?:minimum\s+)?grade\s+(?:of\s+)?([A-DF][+-]?)'

    def __init__(self, session_factory=None):
        """Initialize the parser."""
        if session_factory is None:
            engine = get_engine()
            init_db(engine)
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    def parse(self, text: str, course_code: str = None) -> PrerequisiteParseResult:
        """
        Parse a prerequisite/corequisite text string.

        Args:
            text: The prerequisite text to parse
            course_code: The course this prerequisite is for (for equivalents)

        Returns:
            PrerequisiteParseResult with structured data
        """
        if not text:
            return PrerequisiteParseResult()

        result = PrerequisiteParseResult()
        text = text.strip()

        # Extract equivalents first ("Not open to students with credit in...")
        result.equivalents = self._extract_equivalents(text, course_code)

        # Split into prerequisite and corequisite sections
        prereq_text, coreq_text = self._split_prereq_coreq(text)

        # Parse prerequisites
        if prereq_text:
            result.prerequisites = self._parse_requirements(prereq_text, "prerequisite")

        # Parse corequisites
        if coreq_text:
            result.corequisites = self._parse_requirements(coreq_text, "corequisite")

        return result

    def _split_prereq_coreq(self, text: str) -> tuple[str, str]:
        """Split text into prerequisite and corequisite parts."""
        coreq_markers = [
            r'corequisite[s]?\s*[:;]?\s*',
            r'concurrent(?:ly)?\s+(?:with|enrollment)\s*[:;]?\s*',
            r'must\s+be\s+taken\s+(?:with|concurrently)',
        ]

        for marker in coreq_markers:
            match = re.search(marker, text, re.IGNORECASE)
            if match:
                prereq_part = text[:match.start()].strip()
                coreq_part = text[match.end():].strip()
                return prereq_part, coreq_part

        return text, ""

    def _extract_equivalents(self, text: str, course_code: str) -> list[ParsedEquivalent]:
        """Extract equivalent courses from text."""
        equivalents = []

        if not course_code:
            return equivalents

        # Pattern: "Not open to students with credit in X, Y, Z"
        not_open_pattern = r'not\s+open\s+to\s+students\s+with\s+credit\s+in\s+(.+?)(?:\.|$)'
        match = re.search(not_open_pattern, text, re.IGNORECASE)

        if match:
            equiv_text = match.group(1)
            # Extract course codes
            for code_match in re.finditer(self.COURSE_PATTERN, equiv_text):
                equiv_code = f"{code_match.group(1)} {code_match.group(2)}"
                if equiv_code != course_code:
                    equivalents.append(ParsedEquivalent(
                        course_code=course_code,
                        equivalent_code=equiv_code,
                        equivalence_type=self._determine_equiv_type(course_code, equiv_code),
                    ))

        return equivalents

    def _determine_equiv_type(self, code1: str, code2: str) -> str:
        """Determine the type of equivalence between two courses."""
        # Check if one is honors version
        if code1.rstrip('H') == code2.rstrip('H'):
            return "honors"
        # Check if one is online/special version
        if code1.rstrip('E') == code2.rstrip('E'):
            return "online"
        return "full"

    def _parse_requirements(self, text: str, relation_type: str) -> list[ParsedPrerequisite]:
        """Parse a requirements string into structured prerequisites."""
        requirements = []
        current_group = 0

        # Clean up the text
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove common non-course phrases
        text = re.sub(r'permission\s+of\s+(?:the\s+)?(?:department|instructor)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'admission\s+to\s+[^,;.]+', '', text, flags=re.IGNORECASE)

        # Check for grade requirement that applies to all
        global_grade = None
        grade_match = re.search(self.GRADE_PATTERN, text, re.IGNORECASE)
        if grade_match:
            global_grade = grade_match.group(1).upper()

        # Tokenize by AND (creates new groups) and OR (same group)
        # Handle parentheses for grouping
        tokens = self._tokenize_requirements(text)

        for token_group in tokens:
            for i, course_code in enumerate(token_group):
                requirements.append(ParsedPrerequisite(
                    course_code=course_code,
                    relation_type=relation_type,
                    group_id=current_group,
                    min_grade=global_grade,
                ))
            current_group += 1

        return requirements

    def _tokenize_requirements(self, text: str) -> list[list[str]]:
        """
        Tokenize requirements text into groups.

        Returns list of groups, where each group is a list of alternative courses.
        Groups are ANDed together, courses within a group are ORed.
        """
        groups = []

        # Split by AND first (handles "X and Y")
        and_parts = re.split(r'\s+and\s+|\s*[;&]\s*', text, flags=re.IGNORECASE)

        for part in and_parts:
            part = part.strip()
            if not part:
                continue

            # Within each AND part, split by OR
            or_parts = re.split(r'\s+or\s+|\s*/\s*', part, flags=re.IGNORECASE)

            group = []
            for or_part in or_parts:
                or_part = or_part.strip()
                # Extract course codes from this part
                for match in re.finditer(self.COURSE_PATTERN, or_part):
                    course_code = f"{match.group(1)} {match.group(2)}"
                    group.append(course_code)

            if group:
                groups.append(group)

        return groups

    def parse_and_save(self, course_code: str, prereq_text: str, coreq_text: str = None, equiv_text: str = None) -> PrerequisiteParseResult:
        """
        Parse prerequisite text and save to database.

        Args:
            course_code: The course code (e.g., "CSCI 1302")
            prereq_text: Prerequisite text
            coreq_text: Corequisite text (optional)
            equiv_text: Equivalent courses text (optional)

        Returns:
            PrerequisiteParseResult
        """
        # Combine texts for parsing
        full_text = prereq_text or ""
        if coreq_text:
            full_text += f" Corequisite: {coreq_text}"
        if equiv_text:
            full_text += f" {equiv_text}"

        result = self.parse(full_text, course_code)

        with self.session_factory() as session:
            # Delete existing relationships for this course
            session.execute(
                delete(CoursePrerequisite).where(CoursePrerequisite.course_code == course_code)
            )
            session.execute(
                delete(CourseEquivalent).where(CourseEquivalent.course_code == course_code)
            )

            # Save prerequisites
            for prereq in result.prerequisites:
                db_prereq = CoursePrerequisite(
                    course_code=course_code,
                    prerequisite_code=prereq.course_code,
                    group_id=prereq.group_id,
                    relation_type=prereq.relation_type,
                    min_grade=prereq.min_grade,
                    concurrent_allowed=prereq.concurrent_allowed,
                    source="bulletin",
                )
                session.add(db_prereq)

            # Save corequisites
            for coreq in result.corequisites:
                db_prereq = CoursePrerequisite(
                    course_code=course_code,
                    prerequisite_code=coreq.course_code,
                    group_id=coreq.group_id,
                    relation_type="corequisite",
                    concurrent_allowed=True,
                    source="bulletin",
                )
                session.add(db_prereq)

            # Save equivalents
            for equiv in result.equivalents:
                db_equiv = CourseEquivalent(
                    course_code=equiv.course_code,
                    equivalent_code=equiv.equivalent_code,
                    equivalence_type=equiv.equivalence_type,
                    source="bulletin",
                )
                session.add(db_equiv)

            session.commit()

        return result

    def process_all_bulletin_courses(self) -> dict:
        """
        Process all bulletin courses and extract prerequisite relationships.

        Returns:
            Statistics dict
        """
        stats = {
            "courses_processed": 0,
            "prerequisites_created": 0,
            "equivalents_created": 0,
            "errors": 0,
        }

        with self.session_factory() as session:
            courses = session.execute(select(BulletinCourse)).scalars().all()

            for course in courses:
                try:
                    result = self.parse_and_save(
                        course.course_code,
                        course.prerequisites or "",
                        course.corequisites or "",
                        course.equivalent_courses or "",
                    )
                    stats["courses_processed"] += 1
                    stats["prerequisites_created"] += len(result.prerequisites) + len(result.corequisites)
                    stats["equivalents_created"] += len(result.equivalents)
                except Exception as e:
                    logger.error(f"Error processing {course.course_code}: {e}")
                    stats["errors"] += 1

        # Rebuild unlock index
        self.rebuild_unlock_index()

        return stats

    def rebuild_unlock_index(self):
        """
        Rebuild the CourseUnlock index from prerequisites.

        This creates the inverse relationship for fast "what does completing X unlock?" queries.
        """
        with self.session_factory() as session:
            # Clear existing unlocks
            session.execute(delete(CourseUnlock))

            # Get all prerequisites
            prereqs = session.execute(select(CoursePrerequisite)).scalars().all()

            # Group by course to count total prereqs
            course_prereq_counts = {}
            for prereq in prereqs:
                if prereq.course_code not in course_prereq_counts:
                    course_prereq_counts[prereq.course_code] = set()
                course_prereq_counts[prereq.course_code].add(prereq.group_id)

            # Create unlock entries
            for prereq in prereqs:
                total_groups = len(course_prereq_counts.get(prereq.course_code, set()))
                remaining = total_groups - 1  # This prereq satisfies one group

                unlock = CourseUnlock(
                    completed_code=prereq.prerequisite_code,
                    unlocked_code=prereq.course_code,
                    is_direct=(prereq.group_id == 0),
                    remaining_prereqs=remaining,
                )
                session.add(unlock)

            session.commit()

    def get_prerequisites_for(self, course_code: str) -> list[dict]:
        """Get structured prerequisites for a course."""
        with self.session_factory() as session:
            prereqs = session.execute(
                select(CoursePrerequisite)
                .where(CoursePrerequisite.course_code == course_code)
                .order_by(CoursePrerequisite.group_id)
            ).scalars().all()

            # Group by group_id
            groups = {}
            for p in prereqs:
                if p.group_id not in groups:
                    groups[p.group_id] = {
                        "relation": "AND",
                        "courses": [],
                        "type": p.relation_type,
                    }
                groups[p.group_id]["courses"].append({
                    "code": p.prerequisite_code,
                    "min_grade": p.min_grade,
                    "concurrent": p.concurrent_allowed,
                })

            # Convert to list with OR within groups
            result = []
            for group_id, group in sorted(groups.items()):
                if len(group["courses"]) > 1:
                    result.append({
                        "type": group["type"],
                        "logic": "OR",
                        "options": group["courses"],
                    })
                else:
                    result.append({
                        "type": group["type"],
                        "logic": "SINGLE",
                        "course": group["courses"][0],
                    })

            return result

    def get_courses_unlocked_by(self, course_code: str) -> list[dict]:
        """Get courses that are unlocked by completing a course."""
        with self.session_factory() as session:
            unlocks = session.execute(
                select(CourseUnlock)
                .where(CourseUnlock.completed_code == course_code)
                .order_by(CourseUnlock.remaining_prereqs)
            ).scalars().all()

            return [
                {
                    "code": u.unlocked_code,
                    "remaining_prereqs": u.remaining_prereqs,
                    "fully_unlocked": u.remaining_prereqs == 0,
                }
                for u in unlocks
            ]


# CLI helper
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    parser = PrerequisiteParser()

    # Test parsing
    test_cases = [
        "CSCI 1301",
        "CSCI 1301 or CSCI 1301H",
        "CSCI 1301 and MATH 2250",
        "(CSCI 1301 or CSCI 1301H) and (MATH 2250 or MATH 1113)",
        "ENGL 1050H or ENGL 1102 or ENGL 1102E",
        "CSCI 1302 with a minimum grade of C",
        "Not open to students with credit in CSCI 3030E, CSCI 3030H",
    ]

    print("=== Prerequisite Parser Tests ===\n")
    for text in test_cases:
        print(f"Input: {text}")
        result = parser.parse(text, "TEST 1000")
        print(f"  Prerequisites: {[(p.course_code, p.group_id) for p in result.prerequisites]}")
        print(f"  Corequisites: {[(c.course_code, c.group_id) for c in result.corequisites]}")
        print(f"  Equivalents: {[(e.course_code, e.equivalent_code) for e in result.equivalents]}")
        print()
