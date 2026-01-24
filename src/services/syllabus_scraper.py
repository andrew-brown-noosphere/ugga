"""
UGA Syllabus System Scraper (Prototype).

Scrapes syllabi from syllabus.uga.edu.
The system uses ASP.NET WebForms with postbacks, so we need Playwright
for JavaScript rendering and form interactions.

This is a minimal prototype to demonstrate feasibility.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from firecrawl import FirecrawlApp

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScrapedSyllabus:
    """Parsed syllabus metadata."""
    course_code: str
    section: Optional[str] = None
    semester: Optional[str] = None
    instructor_name: Optional[str] = None
    syllabus_url: Optional[str] = None
    cv_url: Optional[str] = None
    department: Optional[str] = None


class SyllabusScraper:
    """Scrapes UGA Syllabus System.

    The UGA syllabus system (syllabus.uga.edu) is an ASP.NET WebForms app
    that requires JavaScript to navigate. This scraper attempts to extract
    syllabus links and metadata.
    """

    BASE_URL = "https://syllabus.uga.edu"

    def __init__(self, api_key: str = None):
        """Initialize the syllabus scraper.

        Args:
            api_key: Firecrawl API key
        """
        self.api_key = api_key or settings.firecrawl_api_key
        if not self.api_key:
            raise ValueError("Firecrawl API key required")

        self.app = FirecrawlApp(api_key=self.api_key)

    def scrape_browse_page(self) -> dict:
        """Scrape the main browse page to understand structure.

        Returns:
            Dict with page structure information
        """
        url = f"{self.BASE_URL}/Browse.aspx"
        logger.info(f"Scraping browse page: {url}")

        try:
            result = self.app.scrape(
                url,
                formats=["markdown", "html"],
                wait_for=3000,
            )

            markdown = getattr(result, 'markdown', '')
            html = getattr(result, 'html', '')

            return {
                'url': url,
                'markdown': markdown,
                'html_length': len(html),
                'links_found': self._extract_links(markdown),
            }

        except Exception as e:
            logger.error(f"Error scraping browse page: {e}")
            return {'error': str(e)}

    def _extract_links(self, markdown: str) -> list[str]:
        """Extract navigation links from markdown."""
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown)
        return [(text, url) for text, url in links if 'syllabus' in url.lower() or 'aspx' in url.lower()]

    def scrape_department_syllabi(self, dept_code: str) -> list[ScrapedSyllabus]:
        """Attempt to scrape syllabi for a specific department.

        Note: This may not work well due to the ASP.NET postback architecture.
        The system requires JavaScript form submissions that Firecrawl may not handle.

        Args:
            dept_code: Department code (e.g., "CSCI")

        Returns:
            List of ScrapedSyllabus objects
        """
        # Try department-specific syllabi pages that some departments maintain
        dept_pages = {
            'CSCI': 'https://www.cs.uga.edu/computer-science-course-syllabi',
            'STAT': 'https://www.stat.uga.edu/syllabus-center',
            'PHIL': 'https://www.phil.uga.edu/course-syllabi',
        }

        if dept_code not in dept_pages:
            logger.warning(f"No known syllabus page for {dept_code}")
            return []

        url = dept_pages[dept_code]
        logger.info(f"Scraping department syllabi: {url}")

        try:
            result = self.app.scrape(
                url,
                formats=["markdown"],
                wait_for=2000,
            )

            markdown = getattr(result, 'markdown', '')
            return self._parse_department_syllabi(markdown, dept_code)

        except Exception as e:
            logger.error(f"Error scraping {dept_code} syllabi: {e}")
            return []

    def _parse_department_syllabi(self, markdown: str, dept_code: str) -> list[ScrapedSyllabus]:
        """Parse syllabi from a department page.

        Args:
            markdown: Page markdown content
            dept_code: Department code

        Returns:
            List of ScrapedSyllabus
        """
        syllabi = []

        # Look for course links - pattern: [DEPT XXXX](url) or DEPT XXXX ... [link](url)
        course_pattern = rf'({dept_code}\s*\d{{4}}[A-Z]?)'

        for match in re.finditer(course_pattern, markdown, re.IGNORECASE):
            course_code = match.group(1).upper().replace(' ', ' ')
            # Normalize spacing
            course_code = re.sub(r'([A-Z]+)\s*(\d+)', r'\1 \2', course_code)

            syllabi.append(ScrapedSyllabus(
                course_code=course_code,
                department=dept_code,
            ))

        # Deduplicate
        seen = set()
        unique = []
        for s in syllabi:
            if s.course_code not in seen:
                seen.add(s.course_code)
                unique.append(s)

        return unique

    def scrape_central_system(self, dept_name: str = None) -> dict:
        """Attempt to scrape from the central syllabus.uga.edu system.

        The central system uses ASP.NET postbacks which are difficult to automate.
        This method documents what we can extract and the limitations.

        Args:
            dept_name: Optional department name to filter

        Returns:
            Dict with findings and limitations
        """
        findings = {
            'system': 'syllabus.uga.edu',
            'technology': 'ASP.NET WebForms',
            'accessible_pages': [],
            'limitations': [],
            'recommendations': [],
        }

        # Try main pages
        pages_to_check = [
            '/Browse.aspx',
            '/ViewByDeptPublic.aspx',
            '/ViewByInstPublic.aspx',
        ]

        for page in pages_to_check:
            url = f"{self.BASE_URL}{page}"
            try:
                result = self.app.scrape(url, formats=["markdown"], wait_for=2000)
                markdown = getattr(result, 'markdown', '')

                if markdown and len(markdown) > 100:
                    findings['accessible_pages'].append({
                        'url': url,
                        'content_length': len(markdown),
                        'has_data': 'syllabus' in markdown.lower() or 'course' in markdown.lower(),
                    })
            except Exception as e:
                findings['limitations'].append(f"{page}: {str(e)}")

        # Analysis
        findings['limitations'].extend([
            "ASP.NET postbacks require ViewState which changes per session",
            "Dropdown selections trigger server-side callbacks",
            "No public API available",
            "PDF links are dynamically generated",
        ])

        findings['recommendations'].extend([
            "Use Playwright with browser automation for full access",
            "Scrape department-maintained syllabus pages instead (more reliable)",
            "Consider building a browser extension for users to contribute syllabi",
            "Contact UGA IT about API access for research purposes",
        ])

        return findings


def analyze_syllabus_system() -> dict:
    """Analyze the UGA syllabus system and return findings.

    This is a diagnostic function to understand what's possible.
    """
    scraper = SyllabusScraper()
    return scraper.scrape_central_system()


def scrape_department_syllabi(dept_code: str) -> list[ScrapedSyllabus]:
    """Scrape syllabi for a department (from their maintained page).

    Args:
        dept_code: e.g., "CSCI", "STAT"

    Returns:
        List of ScrapedSyllabus
    """
    scraper = SyllabusScraper()
    return scraper.scrape_department_syllabi(dept_code)


# CLI helper
if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        dept = sys.argv[1].upper()
        print(f"Scraping syllabi for {dept}...")
        syllabi = scrape_department_syllabi(dept)
        print(f"Found {len(syllabi)} courses")
        for s in syllabi[:10]:
            print(f"  - {s.course_code}")
    else:
        print("Analyzing UGA syllabus system...")
        findings = analyze_syllabus_system()
        print(json.dumps(findings, indent=2))
