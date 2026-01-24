"""
UGA Faculty Directory Scraper using Playwright.

Free alternative to Firecrawl - uses browser automation for JavaScript rendering.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.models.database import (
    Department, Professor, Instructor,
    get_engine, get_session_factory, init_db
)

logger = logging.getLogger(__name__)


# Known UGA department faculty directory URLs
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
    ("Geography", "GEOG", "Franklin College of Arts and Sciences", "https://geography.uga.edu/directory/faculty"),
    ("Linguistics", "LING", "Franklin College of Arts and Sciences", "https://www.linguistics.uga.edu/directory/faculty"),

    # Terry College of Business
    ("Management", "MGMT", "Terry College of Business", "https://www.terry.uga.edu/directory/management/"),
    ("Marketing", "MKTG", "Terry College of Business", "https://www.terry.uga.edu/directory/marketing/"),
    ("Finance", "FINA", "Terry College of Business", "https://www.terry.uga.edu/directory/finance/"),
    ("Accounting", "ACCT", "Terry College of Business", "https://www.terry.uga.edu/directory/accounting/"),
    ("Management Information Systems", "MIST", "Terry College of Business", "https://www.terry.uga.edu/directory/mis/"),

    # College of Engineering
    ("Engineering", "ENGR", "College of Engineering", "https://engineering.uga.edu/people"),

    # Grady College of Journalism
    ("Journalism", "JOUR", "Grady College of Journalism", "https://grady.uga.edu/faculty-staff/"),

    # College of Education
    ("Education", "EDUC", "Mary Frances Early College of Education", "https://coe.uga.edu/directory"),
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


class FacultyScraperPlaywright:
    """Scrapes UGA faculty directories using Playwright (free)."""

    def __init__(self, session_factory=None, headless: bool = True):
        """Initialize the faculty scraper.

        Args:
            session_factory: SQLAlchemy session factory
            headless: Run browser in headless mode
        """
        self.headless = headless

        if session_factory is None:
            engine = get_engine()
            init_db(engine)
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    async def scrape_directory(self, url: str) -> list[ScrapedProfessor]:
        """Scrape a faculty directory page.

        Args:
            url: Faculty directory URL

        Returns:
            List of ScrapedProfessor objects
        """
        logger.info(f"Scraping faculty directory: {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)  # Extra wait for JS

                # Get page content
                content = await page.content()
                professors = await self._parse_page(page, url, content)

                return professors

            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return []

            finally:
                await browser.close()

    async def _parse_page(self, page: Page, base_url: str, html: str) -> list[ScrapedProfessor]:
        """Parse faculty from page using multiple strategies."""
        professors = []

        # Strategy 1: Look for faculty cards/items with structured data
        # Common selectors for UGA department sites
        selectors = [
            '.faculty-item',
            '.person-card',
            '.directory-item',
            '.views-row',
            '.faculty-listing .item',
            '.people-listing article',
            'article.person',
            '.card.faculty',
        ]

        for selector in selectors:
            try:
                items = await page.query_selector_all(selector)
                if items and len(items) > 2:
                    logger.info(f"Found {len(items)} items with selector: {selector}")
                    for item in items:
                        prof = await self._parse_faculty_card(item, base_url)
                        if prof and prof.name:
                            professors.append(prof)
                    if professors:
                        return professors
            except Exception:
                continue

        # Strategy 2: Parse from HTML patterns
        professors = self._parse_html_patterns(html, base_url)
        if professors:
            return professors

        # Strategy 3: Look for any links with faculty-like patterns
        professors = await self._parse_links(page, base_url)

        return professors

    async def _parse_faculty_card(self, element, base_url: str) -> Optional[ScrapedProfessor]:
        """Parse a single faculty card element."""
        try:
            # Get name
            name = None
            for name_sel in ['h2', 'h3', 'h4', '.name', '.title a', 'a.name', '.field-name']:
                try:
                    name_el = await element.query_selector(name_sel)
                    if name_el:
                        name = await name_el.inner_text()
                        name = name.strip()
                        if name and len(name) > 2:
                            break
                except:
                    continue

            if not name:
                return None

            prof = ScrapedProfessor(name=name)

            # Get title
            for title_sel in ['.position', '.title', '.job-title', '.field-title', 'p:first-of-type']:
                try:
                    title_el = await element.query_selector(title_sel)
                    if title_el:
                        title = await title_el.inner_text()
                        if 'Professor' in title or 'Lecturer' in title or 'Instructor' in title:
                            prof.title = title.strip()
                            break
                except:
                    continue

            # Get email
            try:
                email_el = await element.query_selector('a[href^="mailto:"]')
                if email_el:
                    href = await email_el.get_attribute('href')
                    prof.email = href.replace('mailto:', '').strip()
            except:
                pass

            # Get photo
            try:
                img_el = await element.query_selector('img')
                if img_el:
                    src = await img_el.get_attribute('src')
                    if src:
                        if not src.startswith('http'):
                            src = urljoin(base_url, src)
                        prof.photo_url = src
            except:
                pass

            # Get profile link
            try:
                link_el = await element.query_selector('a[href*="directory"], a[href*="people"], a[href*="faculty"]')
                if link_el:
                    href = await link_el.get_attribute('href')
                    if href:
                        if not href.startswith('http'):
                            href = urljoin(base_url, href)
                        prof.profile_url = href
            except:
                pass

            return prof

        except Exception as e:
            logger.debug(f"Error parsing faculty card: {e}")
            return None

    def _parse_html_patterns(self, html: str, base_url: str) -> list[ScrapedProfessor]:
        """Parse faculty from HTML using regex patterns."""
        professors = []

        # Pattern for UGA-style faculty listings
        # Look for image + name + title + email patterns

        # Pattern 1: Name in link with image
        pattern1 = re.findall(
            r'<img[^>]+src="([^"]+)"[^>]*>.*?'
            r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>.*?'
            r'(?:<[^>]+>)*([^<]*(?:Professor|Lecturer|Instructor|Director)[^<]*)'
            r'.*?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.edu)',
            html, re.DOTALL | re.IGNORECASE
        )

        for match in pattern1[:50]:  # Limit to 50
            photo_url, profile_url, name, title, email = match
            name = re.sub(r'<[^>]+>', '', name).strip()

            if not name or len(name) < 3:
                continue

            if not photo_url.startswith('http'):
                photo_url = urljoin(base_url, photo_url)
            if not profile_url.startswith('http'):
                profile_url = urljoin(base_url, profile_url)

            professors.append(ScrapedProfessor(
                name=name,
                title=title.strip(),
                email=email,
                photo_url=photo_url,
                profile_url=profile_url,
            ))

        # Pattern 2: Simpler - just name and email
        if not professors:
            # Find all emails
            emails = re.findall(r'([a-zA-Z0-9._%+-]+@uga\.edu)', html)

            # For each email, try to find nearby name
            for email in set(emails):
                # Look for name near email in HTML
                pattern = rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)[^@]*{re.escape(email)}'
                match = re.search(pattern, html)
                if match:
                    name = match.group(1).strip()
                    if len(name) > 3 and len(name) < 50:
                        professors.append(ScrapedProfessor(name=name, email=email))

        return professors

    async def _parse_links(self, page: Page, base_url: str) -> list[ScrapedProfessor]:
        """Parse faculty from page links as last resort."""
        professors = []

        try:
            # Get all links that might be faculty profiles
            links = await page.query_selector_all('a[href*="people"], a[href*="directory"], a[href*="faculty"]')

            for link in links[:100]:  # Limit
                try:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    text = text.strip()

                    # Check if text looks like a name (2-4 capitalized words)
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$', text):
                        if not href.startswith('http'):
                            href = urljoin(base_url, href)

                        professors.append(ScrapedProfessor(
                            name=text,
                            profile_url=href,
                        ))
                except:
                    continue

        except Exception as e:
            logger.debug(f"Error parsing links: {e}")

        return professors

    def get_or_create_department(self, name: str, code: str = None,
                                  college: str = None, directory_url: str = None) -> Department:
        """Get or create a department record."""
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
        """Save a scraped professor to the database."""
        with self.session_factory() as session:
            # Check for existing
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

            # Parse name
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

            if existing:
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

    async def scrape_all_departments(self) -> dict:
        """Scrape all known department directories."""
        stats = {
            'departments': 0,
            'professors': 0,
            'errors': 0,
        }

        for dept_name, code, college, url in KNOWN_DEPARTMENTS:
            logger.info(f"Processing department: {dept_name}")

            try:
                dept = self.get_or_create_department(
                    name=dept_name,
                    code=code,
                    college=college,
                    directory_url=url,
                )
                stats['departments'] += 1

                professors = await self.scrape_directory(url)
                logger.info(f"Found {len(professors)} faculty in {dept_name}")

                for prof in professors:
                    self.save_professor(prof, dept.id)
                    stats['professors'] += 1

                # Update scrape time
                with self.session_factory() as session:
                    d = session.get(Department, dept.id)
                    d.last_scraped = datetime.utcnow()
                    session.commit()

            except Exception as e:
                logger.error(f"Error processing {dept_name}: {e}")
                stats['errors'] += 1

        return stats


async def scrape_department(dept_name: str, url: str, code: str = None,
                            college: str = None) -> dict:
    """Scrape a single department."""
    scraper = FacultyScraperPlaywright()

    dept = scraper.get_or_create_department(
        name=dept_name,
        code=code,
        college=college,
        directory_url=url,
    )

    professors = await scraper.scrape_directory(url)
    saved = 0

    for prof in professors:
        scraper.save_professor(prof, dept.id)
        saved += 1

    return {
        'department': dept_name,
        'professors_found': len(professors),
        'professors_saved': saved,
    }


async def scrape_all() -> dict:
    """Scrape all known departments."""
    scraper = FacultyScraperPlaywright()
    return await scraper.scrape_all_departments()


# Sync wrappers for easier use
def scrape_department_sync(dept_name: str, url: str, code: str = None, college: str = None) -> dict:
    """Synchronous wrapper for scrape_department."""
    return asyncio.run(scrape_department(dept_name, url, code, college))


def scrape_all_sync() -> dict:
    """Synchronous wrapper for scrape_all."""
    return asyncio.run(scrape_all())


# CLI
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    if len(sys.argv) > 1:
        url = sys.argv[1]
        dept_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
        result = scrape_department_sync(dept_name, url)
        print(f"Scraped {result['professors_saved']} professors from {result['department']}")
    else:
        print("Scraping all known departments (FREE with Playwright)...")
        stats = scrape_all_sync()
        print(f"\nDepartments: {stats['departments']}")
        print(f"Professors: {stats['professors']}")
        print(f"Errors: {stats['errors']}")
