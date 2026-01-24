"""
UGA Faculty Directory Scraper.

Scrapes professor profiles from department websites.
Uses Firecrawl for reliable JavaScript-rendered page scraping.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

from firecrawl import FirecrawlApp
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.config import settings
from src.models.database import (
    Department, Professor, ProfessorCourse, Instructor,
    get_engine, get_session_factory, init_db
)

logger = logging.getLogger(__name__)


# Known UGA department faculty directory URLs
# Format: (department_name, code, college, directory_url)
KNOWN_DEPARTMENTS = [
    # Franklin College - Arts & Sciences
    ("Computer Science", "CSCI", "Franklin College of Arts and Sciences", "https://www.cs.uga.edu/directory/faculty"),
    ("Mathematics", "MATH", "Franklin College of Arts and Sciences", "https://www.math.uga.edu/directory/faculty"),
    ("Statistics", "STAT", "Franklin College of Arts and Sciences", "https://www.stat.uga.edu/directory/faculty"),
    ("Physics", "PHYS", "Franklin College of Arts and Sciences", "https://www.physast.uga.edu/people/faculty"),
    ("Chemistry", "CHEM", "Franklin College of Arts and Sciences", "https://www.chem.uga.edu/directory/faculty"),
    ("Biology", "BIOL", "Franklin College of Arts and Sciences", "https://www.biology.uga.edu/directory/faculty"),
    ("English", "ENGL", "Franklin College of Arts and Sciences", "https://www.english.uga.edu/directory/faculty"),
    ("History", "HIST", "Franklin College of Arts and Sciences", "https://history.uga.edu/directory/faculty"),
    ("Philosophy", "PHIL", "Franklin College of Arts and Sciences", "https://www.phil.uga.edu/directory/faculty"),
    ("Psychology", "PSYC", "Franklin College of Arts and Sciences", "https://psychology.uga.edu/directory/faculty"),
    ("Sociology", "SOCI", "Franklin College of Arts and Sciences", "https://sociology.uga.edu/directory/faculty"),
    ("Political Science", "POLS", "Franklin College of Arts and Sciences", "https://spia.uga.edu/faculty-directory/"),
    ("Economics", "ECON", "Franklin College of Arts and Sciences", "https://www.terry.uga.edu/directory/economics/"),
    ("Comparative Literature", "CMLT", "Franklin College of Arts and Sciences", "https://www.cmlt.uga.edu/directory/faculty"),

    # Terry College of Business
    ("Management", "MGMT", "Terry College of Business", "https://www.terry.uga.edu/directory/management/"),
    ("Marketing", "MKTG", "Terry College of Business", "https://www.terry.uga.edu/directory/marketing/"),
    ("Finance", "FINA", "Terry College of Business", "https://www.terry.uga.edu/directory/finance/"),
    ("Accounting", "ACCT", "Terry College of Business", "https://www.terry.uga.edu/directory/accounting/"),
    ("Management Information Systems", "MIST", "Terry College of Business", "https://www.terry.uga.edu/directory/mis/"),

    # College of Engineering
    ("Electrical Engineering", "ELEE", "College of Engineering", "https://engineering.uga.edu/people"),
    ("Computer Engineering", "ENGR", "College of Engineering", "https://engineering.uga.edu/people"),

    # Grady College of Journalism
    ("Journalism", "JOUR", "Grady College of Journalism", "https://grady.uga.edu/faculty-staff/"),
    ("Advertising", "ADPR", "Grady College of Journalism", "https://grady.uga.edu/faculty-staff/"),

    # College of Education
    ("Educational Psychology", "EPSY", "Mary Frances Early College of Education", "https://coe.uga.edu/directory"),
]


@dataclass
class ScrapedProfessor:
    """Parsed professor data from directory."""
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    office: Optional[str] = None
    photo_url: Optional[str] = None
    profile_url: Optional[str] = None
    research_areas: list[str] = field(default_factory=list)
    bio: Optional[str] = None
    is_department_head: bool = False


class FacultyScraper:
    """Scrapes UGA faculty directories using Firecrawl."""

    def __init__(self, api_key: str = None, session_factory=None):
        """Initialize the faculty scraper.

        Args:
            api_key: Firecrawl API key
            session_factory: SQLAlchemy session factory
        """
        self.api_key = api_key or settings.firecrawl_api_key
        if not self.api_key:
            raise ValueError("Firecrawl API key not provided. Set FIRECRAWL_API_KEY in .env")

        self.app = FirecrawlApp(api_key=self.api_key)

        if session_factory is None:
            engine = get_engine()
            init_db(engine)
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    def scrape_directory(self, url: str) -> list[ScrapedProfessor]:
        """Scrape a faculty directory page.

        Args:
            url: Faculty directory URL

        Returns:
            List of ScrapedProfessor objects
        """
        logger.info(f"Scraping faculty directory: {url}")

        try:
            result = self.app.scrape(
                url,
                formats=["markdown"],
                wait_for=3000,
            )

            markdown = getattr(result, 'markdown', None)
            if not markdown:
                logger.warning(f"No content returned for {url}")
                return []

            return self._parse_directory(markdown, url)

        except Exception as e:
            logger.error(f"Error scraping directory {url}: {e}")
            return []

    def _parse_directory(self, markdown: str, base_url: str) -> list[ScrapedProfessor]:
        """Parse faculty listing from markdown.

        This handles common patterns in UGA department directories.
        """
        professors = []
        lines = markdown.split('\n')

        current_prof = None

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Pattern 1: UGA style - **[![Name](img)**Name**](profile_url)**
            # Example: **[![Thomas Cerbu](image.png)**Thomas Cerbu**](https://www.cmlt.uga.edu/directory/people/thomas-cerbu)**
            uga_pattern = re.search(
                r'\*\*\[!\[([^\]]+)\]\(([^)]+)\)\*\*([^*]+)\*\*\]\(([^)]+)\)\*\*',
                line
            )
            if uga_pattern:
                name = uga_pattern.group(3).strip()
                photo_url = uga_pattern.group(2)
                profile_url = uga_pattern.group(4)

                if photo_url and not photo_url.startswith('http'):
                    photo_url = urljoin(base_url, photo_url)
                if profile_url and not profile_url.startswith('http'):
                    profile_url = urljoin(base_url, profile_url)

                # Save previous professor
                if current_prof and current_prof.name:
                    professors.append(current_prof)

                current_prof = ScrapedProfessor(
                    name=name,
                    profile_url=profile_url,
                    photo_url=photo_url,
                )
                continue

            # Pattern 2: Simple linked name - [Name](profile_url)
            simple_link = re.match(r'\[([A-Z][a-z]+(?:\s+[A-Z][a-z\'-]+)+)\]\(([^)]+)\)', line)
            if simple_link and not line.startswith('Skip') and 'directory' in line.lower():
                # Save previous professor
                if current_prof and current_prof.name:
                    professors.append(current_prof)

                name = simple_link.group(1).strip()
                profile_url = simple_link.group(2)
                if profile_url and not profile_url.startswith('http'):
                    profile_url = urljoin(base_url, profile_url)

                current_prof = ScrapedProfessor(
                    name=name,
                    profile_url=profile_url,
                )
                continue

            # Pattern 3: Bold name - **Name**
            bold_name = re.match(r'^\*\*([A-Z][a-z]+(?:\s+[A-Z][a-z\'-]+)+)\*\*$', line)
            if bold_name:
                # Save previous professor
                if current_prof and current_prof.name:
                    professors.append(current_prof)

                current_prof = ScrapedProfessor(name=bold_name.group(1).strip())
                continue

            # Look for title (usually in italics _Title_ or contains keywords)
            if current_prof:
                # Italic title: _Associate Professor_
                italic_title = re.match(r'^_([^_]+)_$', line)
                if italic_title:
                    current_prof.title = italic_title.group(1).strip()
                    if 'Head' in line or 'Chair' in line or 'Director' in line:
                        current_prof.is_department_head = True
                    continue

                # Title with keywords
                title_keywords = ['Professor', 'Lecturer', 'Instructor', 'Director', 'Chair', 'Head', 'Dean', 'Coordinator']
                if any(kw in line for kw in title_keywords) and len(line) < 200 and not current_prof.title:
                    current_prof.title = line.strip('*_').strip()
                    if 'Head' in line or 'Chair' in line:
                        current_prof.is_department_head = True
                    continue

                # Look for email link [email](mailto:email)
                email_link = re.search(r'\[([^\]]+@[^\]]+)\]\(mailto:', line)
                if email_link:
                    current_prof.email = email_link.group(1)
                    continue

                # Look for plain email
                email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.edu)', line)
                if email_match and not current_prof.email:
                    current_prof.email = email_match.group(1)
                    continue

                # Look for phone
                phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', line)
                if phone_match and not current_prof.phone:
                    current_prof.phone = phone_match.group(0)
                    continue

        # Don't forget the last professor
        if current_prof and current_prof.name:
            professors.append(current_prof)

        return professors

    def scrape_profile(self, url: str) -> Optional[ScrapedProfessor]:
        """Scrape an individual professor's profile page for detailed info.

        Args:
            url: Professor's profile page URL

        Returns:
            ScrapedProfessor with detailed info
        """
        logger.info(f"Scraping professor profile: {url}")

        try:
            result = self.app.scrape(
                url,
                formats=["markdown"],
                wait_for=2000,
            )

            markdown = getattr(result, 'markdown', None)
            if not markdown:
                return None

            return self._parse_profile(markdown, url)

        except Exception as e:
            logger.error(f"Error scraping profile {url}: {e}")
            return None

    def _parse_profile(self, markdown: str, url: str) -> ScrapedProfessor:
        """Parse a professor's profile page."""
        # Extract name from first header
        name_match = re.search(r'#\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', markdown)
        name = name_match.group(1) if name_match else "Unknown"

        prof = ScrapedProfessor(name=name, profile_url=url)

        # Extract email
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@uga\.edu)', markdown)
        if email_match:
            prof.email = email_match.group(1)

        # Extract title
        title_match = re.search(r'((?:Associate |Assistant |Full |Distinguished |Regents |Research )?Professor[^.\n]*)', markdown)
        if title_match:
            prof.title = title_match.group(1).strip()

        # Extract research areas
        research_section = re.search(r'(?:Research\s*(?:Areas?|Interests?)|Specialization)[:\s]*\n*(.*?)(?=\n#|\n\*\*|\Z)',
                                    markdown, re.IGNORECASE | re.DOTALL)
        if research_section:
            areas_text = research_section.group(1)
            # Split by bullets, newlines, or semicolons
            areas = re.split(r'[•\n;,]', areas_text)
            prof.research_areas = [a.strip().strip('-*').strip() for a in areas if a.strip() and len(a.strip()) > 3]

        # Extract bio/about
        bio_section = re.search(r'(?:About|Biography|Bio)[:\s]*\n*(.*?)(?=\n#|\n\*\*Research|\Z)',
                               markdown, re.IGNORECASE | re.DOTALL)
        if bio_section:
            prof.bio = bio_section.group(1).strip()[:2000]

        # Extract photo
        img_match = re.search(r'!\[[^\]]*\]\(([^)]+(?:\.jpg|\.jpeg|\.png|\.gif)[^)]*)\)', markdown, re.IGNORECASE)
        if img_match:
            photo_url = img_match.group(1)
            if not photo_url.startswith('http'):
                photo_url = urljoin(url, photo_url)
            prof.photo_url = photo_url

        return prof

    def get_or_create_department(self, name: str, code: str = None,
                                  college: str = None, directory_url: str = None) -> Department:
        """Get or create a department record.

        Args:
            name: Department name
            code: Subject code (e.g., CSCI)
            college: College name
            directory_url: Faculty directory URL

        Returns:
            Department object
        """
        with self.session_factory() as session:
            dept = session.execute(
                select(Department).where(Department.name == name)
            ).scalar_one_or_none()

            if not dept:
                dept = Department(
                    name=name,
                    code=code,
                    college=college,
                    faculty_directory_url=directory_url,
                )
                session.add(dept)
                session.commit()
                session.refresh(dept)

            return dept

    def save_professor(self, scraped: ScrapedProfessor, department_id: int) -> Professor:
        """Save a scraped professor to the database.

        Args:
            scraped: ScrapedProfessor data
            department_id: Department ID

        Returns:
            Professor object
        """
        with self.session_factory() as session:
            # Check for existing professor by email or name+department
            existing = None
            if scraped.email:
                existing = session.execute(
                    select(Professor).where(Professor.email == scraped.email)
                ).scalar_one_or_none()

            if not existing:
                existing = session.execute(
                    select(Professor).where(
                        Professor.name == scraped.name,
                        Professor.department_id == department_id
                    )
                ).scalar_one_or_none()

            # Parse name into first/last
            name_parts = scraped.name.split()
            first_name = name_parts[0] if name_parts else None
            last_name = name_parts[-1] if len(name_parts) > 1 else None

            # Determine position type
            position_type = None
            if scraped.title:
                title_lower = scraped.title.lower()
                if 'professor' in title_lower:
                    position_type = 'professor'
                elif 'lecturer' in title_lower:
                    position_type = 'lecturer'
                elif 'instructor' in title_lower:
                    position_type = 'instructor'
                elif 'emeritus' in title_lower:
                    position_type = 'emeritus'

            if existing:
                # Update existing record
                existing.title = scraped.title or existing.title
                existing.email = scraped.email or existing.email
                existing.phone = scraped.phone or existing.phone
                existing.office_location = scraped.office or existing.office_location
                existing.photo_url = scraped.photo_url or existing.photo_url
                existing.profile_url = scraped.profile_url or existing.profile_url
                existing.bio = scraped.bio or existing.bio
                existing.research_areas = scraped.research_areas or existing.research_areas
                existing.is_department_head = scraped.is_department_head or existing.is_department_head
                existing.position_type = position_type or existing.position_type
                existing.updated_at = datetime.utcnow()
                session.commit()
                return existing
            else:
                # Create new record
                prof = Professor(
                    department_id=department_id,
                    name=scraped.name,
                    first_name=first_name,
                    last_name=last_name,
                    title=scraped.title,
                    position_type=position_type,
                    is_department_head=scraped.is_department_head,
                    email=scraped.email,
                    phone=scraped.phone,
                    office_location=scraped.office,
                    photo_url=scraped.photo_url,
                    profile_url=scraped.profile_url,
                    bio=scraped.bio,
                    research_areas=scraped.research_areas if scraped.research_areas else None,
                )
                session.add(prof)
                session.commit()
                session.refresh(prof)
                return prof

    def scrape_all_departments(self, scrape_profiles: bool = False) -> dict:
        """Scrape all known department directories.

        Args:
            scrape_profiles: Whether to also scrape individual profile pages

        Returns:
            Dict with statistics
        """
        stats = {
            'departments': 0,
            'professors': 0,
            'errors': 0,
        }

        for dept_name, code, college, url in KNOWN_DEPARTMENTS:
            logger.info(f"Processing department: {dept_name}")

            try:
                # Get or create department
                dept = self.get_or_create_department(
                    name=dept_name,
                    code=code,
                    college=college,
                    directory_url=url,
                )
                stats['departments'] += 1

                # Scrape directory
                professors = self.scrape_directory(url)
                logger.info(f"Found {len(professors)} faculty members in {dept_name}")

                for prof in professors:
                    # Optionally scrape full profile
                    if scrape_profiles and prof.profile_url:
                        detailed = self.scrape_profile(prof.profile_url)
                        if detailed:
                            # Merge data
                            prof.bio = detailed.bio or prof.bio
                            prof.research_areas = detailed.research_areas or prof.research_areas
                            if not prof.email:
                                prof.email = detailed.email

                    # Save to database
                    self.save_professor(prof, dept.id)
                    stats['professors'] += 1

                # Update department scrape time
                with self.session_factory() as session:
                    d = session.get(Department, dept.id)
                    d.last_scraped = datetime.utcnow()
                    session.commit()

            except Exception as e:
                logger.error(f"Error processing {dept_name}: {e}")
                stats['errors'] += 1

        return stats


def scrape_department(dept_name: str, url: str, code: str = None,
                      college: str = None) -> dict:
    """Convenience function to scrape a single department.

    Args:
        dept_name: Department name
        url: Faculty directory URL
        code: Subject code
        college: College name

    Returns:
        Statistics dict
    """
    scraper = FacultyScraper()

    dept = scraper.get_or_create_department(
        name=dept_name,
        code=code,
        college=college,
        directory_url=url,
    )

    professors = scraper.scrape_directory(url)
    saved = 0

    for prof in professors:
        scraper.save_professor(prof, dept.id)
        saved += 1

    return {
        'department': dept_name,
        'professors_found': len(professors),
        'professors_saved': saved,
    }


# CLI helper
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    if len(sys.argv) > 1:
        # Scrape single department
        url = sys.argv[1]
        dept_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
        result = scrape_department(dept_name, url)
        print(f"Scraped {result['professors_saved']} professors from {result['department']}")
    else:
        # Scrape all known departments
        scraper = FacultyScraper()
        stats = scraper.scrape_all_departments()
        print(f"\nScraped {stats['departments']} departments")
        print(f"Total professors: {stats['professors']}")
        print(f"Errors: {stats['errors']}")
