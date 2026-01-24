"""
UGA Syllabus System Scraper using Playwright.

Scrapes syllabi from syllabus.uga.edu using browser automation.
The system uses ASP.NET WebForms with postbacks, so we need real browser interaction.

IMPORTANT: The correct flow for this system is:
1. Navigate to Browse.aspx
2. Select "View by Department" radio button
3. Click Submit
4. Select department from dropdown (triggers postback)
5. Select semester from dropdown (triggers postback, reveals buttons)
6. Click "View information for all courses in department" button
7. Parse the gridFileList table
8. Click each syllabus link to download PDF
9. Extract text content from PDF
"""
import asyncio
import hashlib
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import fitz  # PyMuPDF
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


@dataclass
class ScrapedSyllabus:
    """Parsed syllabus metadata."""
    course_code: str
    course_title: Optional[str] = None
    section: Optional[str] = None
    semester: Optional[str] = None
    instructor_name: Optional[str] = None
    syllabus_url: Optional[str] = None
    cv_url: Optional[str] = None
    department: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    crn: Optional[str] = None
    grid_index: Optional[int] = None  # For postback reference


class SyllabusScraperPlaywright:
    """Scrapes UGA Syllabus System using Playwright (free)."""

    BASE_URL = "https://syllabus.uga.edu"

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def _create_stealth_page(self, browser):
        """Create a page with stealth settings to avoid detection."""
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        return page, context

    async def get_departments(self) -> list[dict]:
        """Get list of departments from the syllabus system.

        Returns:
            List of {name, value} dicts for department dropdown
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            page, context = await self._create_stealth_page(browser)

            try:
                # Go to browse page
                await page.goto(f"{self.BASE_URL}/Browse.aspx", wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)

                # Click DEP radio button and submit
                await page.click('input#RadioButtonList1_0')
                await page.wait_for_timeout(500)
                await page.click('input#Button1')
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)

                # Get department dropdown options
                departments = []
                options = await page.query_selector_all('select#ddlDept option')

                for opt in options:
                    value = await opt.get_attribute('value')
                    text = await opt.inner_text()
                    if value and text and value != '-1':
                        departments.append({'name': text.strip(), 'value': value})

                logger.info(f"Found {len(departments)} departments")
                return departments

            except Exception as e:
                logger.error(f"Error getting departments: {e}")
                return []

            finally:
                await context.close()
                await browser.close()

    async def get_semesters(self, dept_value: str) -> list[dict]:
        """Get available semesters for a department.

        Args:
            dept_value: Department dropdown value (e.g., 'CS')

        Returns:
            List of {name, value} dicts for semester dropdown
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            page, context = await self._create_stealth_page(browser)

            try:
                await page.goto(f"{self.BASE_URL}/Browse.aspx", wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)

                await page.click('input#RadioButtonList1_0')
                await page.wait_for_timeout(500)
                await page.click('input#Button1')
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)

                # Select department
                await page.select_option('select#ddlDept', dept_value)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(3000)

                # Get semester options
                semesters = []
                options = await page.query_selector_all('select#ddlSemesters option')

                for opt in options:
                    value = await opt.get_attribute('value')
                    text = await opt.inner_text()
                    if value and text and value != '-1':
                        semesters.append({'name': text.strip(), 'value': value})

                logger.info(f"Found {len(semesters)} semesters for {dept_value}")
                return semesters

            except Exception as e:
                logger.error(f"Error getting semesters: {e}")
                return []

            finally:
                await context.close()
                await browser.close()

    async def scrape_syllabi_for_department(
        self,
        dept_value: str,
        semester_value: str = None,
        dept_name: str = None
    ) -> list[ScrapedSyllabus]:
        """Scrape all syllabi for a department.

        Args:
            dept_value: Department dropdown value (e.g., 'CS')
            semester_value: Optional semester value (if None, uses latest available)
            dept_name: Department name for logging

        Returns:
            List of ScrapedSyllabus objects
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            page, context = await self._create_stealth_page(browser)

            try:
                logger.info(f"Scraping syllabi for {dept_name or dept_value}...")

                # Navigate and submit
                await page.goto(f"{self.BASE_URL}/Browse.aspx", wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)

                await page.click('input#RadioButtonList1_0')
                await page.wait_for_timeout(500)
                await page.click('input#Button1')
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)

                # Select department
                await page.select_option('select#ddlDept', dept_value)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(3000)

                # Select semester
                if semester_value:
                    await page.select_option('select#ddlSemesters', semester_value)
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(3000)
                else:
                    # Get semester options first
                    options = await page.query_selector_all('select#ddlSemesters option')
                    semester_to_select = None
                    semester_text = None

                    # Find the latest semester (last option that's not -1)
                    for opt in reversed(options):
                        value = await opt.get_attribute('value')
                        text = await opt.inner_text()
                        if value and value != '-1':
                            semester_to_select = value
                            semester_text = text.strip()
                            break

                    if semester_to_select:
                        logger.info(f"Selecting semester: {semester_text}")
                        await page.select_option('select#ddlSemesters', semester_to_select)
                        await page.wait_for_load_state('networkidle')
                        await page.wait_for_timeout(3000)

                # Click view button
                view_btn = await page.query_selector('#Button_ViewAll_Course')
                if not view_btn:
                    logger.error("View button not found!")
                    return []

                await view_btn.click()
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(5000)

                # Parse the grid
                grid = await page.query_selector('#gridFileList')
                if not grid:
                    logger.warning("Grid not found - no syllabi available")
                    return []

                rows = await grid.query_selector_all('tr')
                logger.info(f"Found {len(rows) - 1} syllabus entries")

                syllabi = []
                for i, row in enumerate(rows[1:]):  # Skip header
                    cells = await row.query_selector_all('td')
                    if len(cells) >= 7:
                        instructor = (await cells[0].inner_text()).strip()
                        course = (await cells[1].inner_text()).strip()
                        semester = (await cells[2].inner_text()).strip()
                        file_type = (await cells[3].inner_text()).strip()
                        days_times = (await cells[4].inner_text()).strip()
                        crn = (await cells[5].inner_text()).strip()

                        file_link = await cells[6].query_selector('a')
                        file_name = None
                        grid_index = None

                        if file_link:
                            file_name = (await file_link.inner_text()).strip()
                            link_href = await file_link.get_attribute('href')
                            # Extract grid index from postback
                            match = re.search(r"Select\$(\d+)", link_href or "")
                            if match:
                                grid_index = int(match.group(1))

                        # Skip entries with no syllabus file
                        if not file_name or file_name == '--':
                            continue

                        # Parse course code
                        course_code = course.strip()

                        syllabi.append(ScrapedSyllabus(
                            course_code=course_code,
                            semester=semester if semester else None,
                            instructor_name=instructor if instructor and instructor != '--' else None,
                            department=dept_value,
                            file_name=file_name,
                            file_type=file_type if file_type else None,
                            crn=crn if crn and crn.strip() else None,
                            grid_index=grid_index,
                        ))

                logger.info(f"Parsed {len(syllabi)} syllabi with files for {dept_name or dept_value}")
                return syllabi

            except Exception as e:
                logger.error(f"Error scraping syllabi for {dept_name or dept_value}: {e}")
                return []

            finally:
                await context.close()
                await browser.close()

    async def scrape_department_page(self, dept_code: str) -> list[ScrapedSyllabus]:
        """Scrape syllabi from a department's own syllabus page.

        Some departments maintain their own syllabus listings which are easier to scrape.

        Args:
            dept_code: Department code (e.g., "CSCI")

        Returns:
            List of ScrapedSyllabus
        """
        dept_pages = {
            'CSCI': 'https://www.cs.uga.edu/computer-science-course-syllabi',
            'STAT': 'https://www.stat.uga.edu/syllabus-center',
            'PHIL': 'https://www.phil.uga.edu/course-syllabi',
            'MATH': 'https://www.math.uga.edu/undergraduate/course-syllabi',
        }

        if dept_code not in dept_pages:
            logger.warning(f"No known syllabus page for {dept_code}")
            return []

        url = dept_pages[dept_code]
        logger.info(f"Scraping {dept_code} syllabus page: {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)

                syllabi = []
                content = await page.content()

                # Find all course mentions
                course_pattern = rf'({dept_code}\s*\d{{4}}[A-Z]?)'

                # Get all links that might be syllabi
                links = await page.query_selector_all('a')

                for link in links:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()

                    if not href:
                        continue

                    # Check if it's a course link or syllabus link
                    course_match = re.search(course_pattern, text, re.IGNORECASE)
                    if not course_match:
                        course_match = re.search(course_pattern, href, re.IGNORECASE)

                    if course_match:
                        code = course_match.group(1).upper()
                        code = re.sub(r'([A-Z]+)\s*(\d+)', r'\1 \2', code)  # Normalize spacing

                        if not href.startswith('http'):
                            href = urljoin(url, href)

                        syllabi.append(ScrapedSyllabus(
                            course_code=code,
                            course_title=text.strip() if text and dept_code not in text else None,
                            department=dept_code,
                            syllabus_url=href if '.pdf' in href.lower() else None,
                        ))

                # Deduplicate by course code
                seen = set()
                unique = []
                for s in syllabi:
                    if s.course_code not in seen:
                        seen.add(s.course_code)
                        unique.append(s)

                logger.info(f"Found {len(unique)} courses with syllabi for {dept_code}")
                return unique

            except Exception as e:
                logger.error(f"Error scraping {dept_code} syllabi: {e}")
                return []

            finally:
                await browser.close()

    async def analyze_system(self) -> dict:
        """Analyze the UGA syllabus system structure.

        Returns:
            Dict with system analysis
        """
        findings = {
            'system': 'syllabus.uga.edu',
            'technology': 'ASP.NET WebForms',
            'departments': [],
            'sample_courses': [],
            'semesters': [],
            'recommendations': [],
        }

        # Get departments
        logger.info("Getting department list...")
        departments = await self.get_departments()
        findings['departments'] = departments[:10]  # First 10
        findings['total_departments'] = len(departments)

        # Get semesters for CS as sample
        if any(d['value'] == 'CS' for d in departments):
            logger.info("Getting semesters for CS...")
            semesters = await self.get_semesters('CS')
            findings['semesters'] = semesters
            findings['sample_department'] = 'School of Computing'

            # Get sample syllabi
            if semesters:
                logger.info("Getting sample syllabi...")
                syllabi = await self.scrape_syllabi_for_department('CS', semesters[-1]['value'])
                findings['sample_courses'] = [
                    {
                        'course': s.course_code,
                        'semester': s.semester,
                        'instructor': s.instructor_name,
                        'file': s.file_name
                    }
                    for s in syllabi[:10]
                ]
                findings['total_syllabi'] = len(syllabi)

        findings['recommendations'] = [
            "Central system works - use department + semester + button flow",
            "PDF files are served via postback, not direct URLs",
            "Store grid_index for future download capability",
            "Consider caching syllabus metadata in database",
        ]

        return findings

    @staticmethod
    def extract_pdf_text(pdf_path: str) -> str:
        """Extract text from a PDF file using PyMuPDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        try:
            doc = fitz.open(pdf_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute SHA-256 hash of content for change detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def download_and_extract_syllabus(
        self,
        dept_value: str,
        semester_value: str,
        grid_index: int,
        timeout_ms: int = 30000
    ) -> Optional[str]:
        """Download a syllabus PDF and extract its text content.

        Args:
            dept_value: Department dropdown value
            semester_value: Semester dropdown value
            grid_index: Row index in the grid (for postback)
            timeout_ms: Download timeout in milliseconds

        Returns:
            Extracted text content or None if failed
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            page, context = await self._create_stealth_page(browser)

            try:
                # Navigate to grid page
                await page.goto(f"{self.BASE_URL}/Browse.aspx", wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(1500)

                await page.click('input#RadioButtonList1_0')
                await page.wait_for_timeout(300)
                await page.click('input#Button1')
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(1500)

                await page.select_option('select#ddlDept', dept_value)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)

                await page.select_option('select#ddlSemesters', semester_value)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)

                view_btn = await page.query_selector('#Button_ViewAll_Course')
                if not view_btn:
                    logger.error("View button not found")
                    return None

                await view_btn.click()
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(3000)

                # Find the link for this grid index
                grid = await page.query_selector('#gridFileList')
                if not grid:
                    logger.error("Grid not found")
                    return None

                rows = await grid.query_selector_all('tr')
                if grid_index + 1 >= len(rows):
                    logger.error(f"Grid index {grid_index} out of range")
                    return None

                row = rows[grid_index + 1]  # +1 for header
                cells = await row.query_selector_all('td')
                if len(cells) < 7:
                    logger.error("Row doesn't have enough cells")
                    return None

                file_link = await cells[6].query_selector('a')
                if not file_link:
                    logger.error("No download link found")
                    return None

                # Set up download handler
                with tempfile.TemporaryDirectory() as tmp_dir:
                    async with page.expect_download(timeout=timeout_ms) as download_info:
                        await file_link.click()

                    download = await download_info.value
                    pdf_path = os.path.join(tmp_dir, download.suggested_filename)
                    await download.save_as(pdf_path)

                    logger.info(f"Downloaded: {download.suggested_filename}")

                    # Extract text
                    content = self.extract_pdf_text(pdf_path)
                    if content:
                        logger.info(f"Extracted {len(content)} chars from PDF")
                    return content

            except Exception as e:
                logger.error(f"Error downloading syllabus: {e}")
                return None

            finally:
                await context.close()
                await browser.close()

    async def _navigate_to_grid(self, page, dept_value: str, semester_value: str = None) -> str:
        """Navigate to syllabus grid and return the actual semester used."""
        await page.goto(f"{self.BASE_URL}/Browse.aspx", wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(1500)

        await page.click('input#RadioButtonList1_0')
        await page.wait_for_timeout(300)
        await page.click('input#Button1')
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(1500)

        await page.select_option('select#ddlDept', dept_value)
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(2000)

        actual_semester = semester_value
        if not actual_semester:
            options = await page.query_selector_all('select#ddlSemesters option')
            for opt in reversed(options):
                value = await opt.get_attribute('value')
                if value and value != '-1':
                    actual_semester = value
                    break

        if actual_semester:
            await page.select_option('select#ddlSemesters', actual_semester)
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(2000)

        view_btn = await page.query_selector('#Button_ViewAll_Course')
        if view_btn:
            await view_btn.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)

        return actual_semester

    async def scrape_syllabi_with_content(
        self,
        dept_value: str,
        semester_value: str = None,
        dept_name: str = None,
        existing_hashes: dict = None,
        max_syllabi: int = None,
        delay_between_downloads: float = 2.0
    ) -> list[dict]:
        """Scrape syllabi metadata AND content for a department.

        Two-pass approach for reliability:
        1. First pass: collect all metadata from grid
        2. Second pass: download each PDF with fresh page navigation

        Args:
            dept_value: Department dropdown value
            semester_value: Semester value (None = latest)
            dept_name: Department name for logging
            existing_hashes: Dict of {cache_key: content_hash} for change detection
            max_syllabi: Maximum number to scrape (None = all)
            delay_between_downloads: Seconds between downloads to avoid rate limiting

        Returns:
            List of dicts with syllabus data including content
        """
        existing_hashes = existing_hashes or {}
        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )

            try:
                logger.info(f"Scraping syllabi with content for {dept_name or dept_value}...")

                # Pass 1: Collect metadata
                page, context = await self._create_stealth_page(browser)
                actual_semester = await self._navigate_to_grid(page, dept_value, semester_value)

                grid = await page.query_selector('#gridFileList')
                if not grid:
                    logger.warning("No syllabi grid found")
                    await context.close()
                    return results

                rows = await grid.query_selector_all('tr')
                metadata_list = []

                for i, row in enumerate(rows[1:]):  # Skip header
                    cells = await row.query_selector_all('td')
                    if len(cells) < 7:
                        continue

                    instructor = (await cells[0].inner_text()).strip()
                    course = (await cells[1].inner_text()).strip()
                    semester = (await cells[2].inner_text()).strip()
                    file_type = (await cells[3].inner_text()).strip()
                    crn = (await cells[5].inner_text()).strip()

                    file_link = await cells[6].query_selector('a')
                    if not file_link:
                        continue

                    file_name = (await file_link.inner_text()).strip()
                    if not file_name or file_name == '--':
                        continue

                    metadata_list.append({
                        'row_index': i,
                        'instructor': instructor,
                        'course': course,
                        'semester': semester,
                        'file_type': file_type,
                        'crn': crn,
                        'file_name': file_name,
                    })

                await context.close()
                logger.info(f"Found {len(metadata_list)} syllabi with files")

                if max_syllabi:
                    metadata_list = metadata_list[:max_syllabi]

                # Pass 2: Download each PDF
                for idx, meta in enumerate(metadata_list):
                    cache_key = f"{meta['course']}:{meta['semester']}:{meta['instructor']}"

                    # Skip if unchanged (check hash)
                    if cache_key in existing_hashes:
                        logger.debug(f"Skipping (cached): {meta['course']}")
                        continue

                    try:
                        page, context = await self._create_stealth_page(browser)
                        await self._navigate_to_grid(page, dept_value, actual_semester)

                        grid = await page.query_selector('#gridFileList')
                        if not grid:
                            await context.close()
                            continue

                        rows = await grid.query_selector_all('tr')
                        if meta['row_index'] + 1 >= len(rows):
                            await context.close()
                            continue

                        row = rows[meta['row_index'] + 1]
                        cells = await row.query_selector_all('td')
                        file_link = await cells[6].query_selector('a')

                        if not file_link:
                            await context.close()
                            continue

                        with tempfile.TemporaryDirectory() as tmp_dir:
                            async with page.expect_download(timeout=30000) as download_info:
                                await file_link.click()

                            download = await download_info.value
                            pdf_path = os.path.join(tmp_dir, download.suggested_filename)
                            await download.save_as(pdf_path)

                            content = self.extract_pdf_text(pdf_path)
                            if not content:
                                logger.warning(f"No content from {meta['file_name']}")
                                await context.close()
                                continue

                            content_hash = self.compute_content_hash(content)

                            results.append({
                                'course_code': meta['course'],
                                'course_title': None,
                                'section': None,
                                'semester': meta['semester'],
                                'instructor_name': meta['instructor'] if meta['instructor'] != '--' else None,
                                'department': dept_value,
                                'file_name': meta['file_name'],
                                'file_type': meta['file_type'],
                                'crn': meta['crn'] if meta['crn'].strip() else None,
                                'content': content,
                                'content_hash': content_hash,
                            })
                            logger.info(f"[{idx+1}/{len(metadata_list)}] {meta['course']} ({len(content)} chars)")

                        await context.close()
                        await asyncio.sleep(delay_between_downloads)

                    except Exception as e:
                        logger.error(f"Error downloading {meta['course']}: {e}")
                        try:
                            await context.close()
                        except:
                            pass

                logger.info(f"Completed: {len(results)} syllabi extracted")
                return results

            except Exception as e:
                logger.error(f"Error in scrape_syllabi_with_content: {e}")
                return results

            finally:
                await browser.close()


# Sync wrappers
def get_departments_sync() -> list[dict]:
    """Get departments (sync wrapper)."""
    scraper = SyllabusScraperPlaywright()
    return asyncio.run(scraper.get_departments())


def scrape_department_syllabi_sync(dept_value: str, semester_value: str = None) -> list[ScrapedSyllabus]:
    """Scrape department syllabi (sync wrapper)."""
    scraper = SyllabusScraperPlaywright()
    return asyncio.run(scraper.scrape_syllabi_for_department(dept_value, semester_value))


def analyze_system_sync() -> dict:
    """Analyze the system (sync wrapper)."""
    scraper = SyllabusScraperPlaywright()
    return asyncio.run(scraper.analyze_system())


def scrape_syllabi_with_content_sync(
    dept_value: str,
    semester_value: str = None,
    existing_hashes: dict = None,
    max_syllabi: int = None
) -> list[dict]:
    """Scrape syllabi with content (sync wrapper)."""
    scraper = SyllabusScraperPlaywright()
    return asyncio.run(scraper.scrape_syllabi_with_content(
        dept_value, semester_value, existing_hashes=existing_hashes, max_syllabi=max_syllabi
    ))


# Database operations
def get_existing_hashes(dept_value: str = None) -> dict:
    """Load existing content hashes from database for change detection.

    Args:
        dept_value: Optional department filter

    Returns:
        Dict of {cache_key: content_hash}
    """
    from src.services.course_service import CourseService
    from sqlalchemy import text

    svc = CourseService()
    hashes = {}

    with svc.session_factory() as session:
        query = "SELECT course_code, semester, instructor_name, content_hash FROM syllabi WHERE content_hash IS NOT NULL"
        params = {}
        if dept_value:
            query += " AND department = :dept"
            params["dept"] = dept_value

        result = session.execute(text(query), params)
        for row in result:
            cache_key = f"{row[0]}:{row[1]}:{row[2]}"
            hashes[cache_key] = row[3]

    return hashes


def save_syllabi_content(syllabi: list[dict]) -> int:
    """Save scraped syllabi with content to database.

    Updates existing or inserts new based on course_code + semester + instructor_name.

    Args:
        syllabi: List of syllabus dicts from scrape_syllabi_with_content

    Returns:
        Number of syllabi saved/updated
    """
    from src.services.course_service import CourseService
    from sqlalchemy import text
    from datetime import datetime, timezone

    if not syllabi:
        return 0

    svc = CourseService()
    saved = 0
    now = datetime.now(timezone.utc)

    with svc.session_factory() as session:
        for s in syllabi:
            # Check if exists
            existing = session.execute(
                text("""
                    SELECT id, content_hash FROM syllabi
                    WHERE course_code = :course_code
                    AND semester = :semester
                    AND (instructor_name = :instructor_name OR (instructor_name IS NULL AND :instructor_name IS NULL))
                """),
                {
                    'course_code': s['course_code'],
                    'semester': s['semester'],
                    'instructor_name': s['instructor_name'],
                }
            ).fetchone()

            if existing:
                # Update if hash changed
                if existing[1] != s['content_hash']:
                    session.execute(
                        text("""
                            UPDATE syllabi SET
                                content = :content,
                                content_hash = :content_hash,
                                content_scraped_at = :scraped_at,
                                file_name = :file_name
                            WHERE id = :id
                        """),
                        {
                            'id': existing[0],
                            'content': s['content'],
                            'content_hash': s['content_hash'],
                            'scraped_at': now,
                            'file_name': s['file_name'],
                        }
                    )
                    saved += 1
            else:
                # Insert new
                session.execute(
                    text("""
                        INSERT INTO syllabi (
                            course_code, semester, instructor_name, department,
                            file_name, file_type, crn, content, content_hash, content_scraped_at
                        ) VALUES (
                            :course_code, :semester, :instructor_name, :department,
                            :file_name, :file_type, :crn, :content, :content_hash, :scraped_at
                        )
                    """),
                    {
                        'course_code': s['course_code'],
                        'semester': s['semester'],
                        'instructor_name': s['instructor_name'],
                        'department': s['department'],
                        'file_name': s['file_name'],
                        'file_type': s['file_type'],
                        'crn': s['crn'],
                        'content': s['content'],
                        'content_hash': s['content_hash'],
                        'scraped_at': now,
                    }
                )
                saved += 1

        session.commit()

    return saved


def scrape_and_save_department(
    dept_value: str,
    semester_value: str = None,
    max_syllabi: int = None
) -> dict:
    """Scrape syllabi with content and save to database.

    Args:
        dept_value: Department code
        semester_value: Optional semester
        max_syllabi: Max to scrape

    Returns:
        Dict with stats: {scraped, saved, skipped}
    """
    # Load existing hashes for change detection
    existing_hashes = get_existing_hashes(dept_value)
    logger.info(f"Loaded {len(existing_hashes)} existing hashes for {dept_value}")

    # Scrape with content
    syllabi = scrape_syllabi_with_content_sync(
        dept_value,
        semester_value,
        existing_hashes=existing_hashes,
        max_syllabi=max_syllabi
    )

    # Save to database
    saved = save_syllabi_content(syllabi)

    return {
        'department': dept_value,
        'scraped': len(syllabi),
        'saved': saved,
        'skipped': len(existing_hashes),
    }


# CLI
if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    if len(sys.argv) > 1:
        if sys.argv[1] == '--analyze':
            print("Analyzing UGA syllabus system...")
            findings = analyze_system_sync()
            print(json.dumps(findings, indent=2, default=str))

        elif sys.argv[1] == '--departments':
            print("Getting departments...")
            departments = get_departments_sync()
            for d in departments:
                print(f"  {d['value']}: {d['name']}")

        elif sys.argv[1] == '--content':
            # Scrape syllabi with content and save to DB
            if len(sys.argv) < 3:
                print("Usage: python syllabus_scraper_playwright.py --content <DEPT_CODE> [--max N]")
                sys.exit(1)

            dept = sys.argv[2].upper()
            max_syllabi = None

            # Parse --max flag
            if '--max' in sys.argv:
                max_idx = sys.argv.index('--max')
                if max_idx + 1 < len(sys.argv):
                    max_syllabi = int(sys.argv[max_idx + 1])

            print(f"Scraping syllabi with content for {dept}...")
            stats = scrape_and_save_department(dept, max_syllabi=max_syllabi)
            print(f"\nResults:")
            print(f"  Scraped: {stats['scraped']}")
            print(f"  Saved: {stats['saved']}")
            print(f"  Existing: {stats['skipped']}")

        elif sys.argv[1] == '--content-all':
            # Batch scrape all departments
            max_per_dept = None
            if '--max' in sys.argv:
                max_idx = sys.argv.index('--max')
                if max_idx + 1 < len(sys.argv):
                    max_per_dept = int(sys.argv[max_idx + 1])

            print("Getting all departments...")
            departments = get_departments_sync()
            print(f"Found {len(departments)} departments")

            total_scraped = 0
            total_saved = 0

            for dept in departments:
                print(f"\n=== {dept['name']} ({dept['value']}) ===")
                try:
                    stats = scrape_and_save_department(dept['value'], max_syllabi=max_per_dept)
                    total_scraped += stats['scraped']
                    total_saved += stats['saved']
                    print(f"  Scraped: {stats['scraped']}, Saved: {stats['saved']}")
                except Exception as e:
                    print(f"  Error: {e}")

            print(f"\n=== TOTAL ===")
            print(f"  Total scraped: {total_scraped}")
            print(f"  Total saved: {total_saved}")

        else:
            dept = sys.argv[1].upper()
            semester = sys.argv[2] if len(sys.argv) > 2 else None
            print(f"Scraping syllabi metadata for {dept}...")
            syllabi = scrape_department_syllabi_sync(dept, semester)
            print(f"Found {len(syllabi)} syllabi")
            for s in syllabi[:20]:
                print(f"  {s.course_code}: {s.semester} - {s.instructor_name} - {s.file_name}")
    else:
        print("Usage:")
        print("  python syllabus_scraper_playwright.py --analyze")
        print("  python syllabus_scraper_playwright.py --departments")
        print("  python syllabus_scraper_playwright.py --content <DEPT> [--max N]  # Scrape with content, save to DB")
        print("  python syllabus_scraper_playwright.py --content-all [--max N]     # Batch all departments")
        print("  python syllabus_scraper_playwright.py <DEPT_CODE> [SEMESTER]      # Metadata only")
        print("")
        print("Examples:")
        print("  python syllabus_scraper_playwright.py --content CS --max 10")
        print("  python syllabus_scraper_playwright.py --content-all --max 5")
        print("  python syllabus_scraper_playwright.py CS")
