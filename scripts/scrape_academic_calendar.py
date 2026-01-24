"""Scrape UGA Academic Calendar and important dates."""
import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import httpx
import pdfplumber
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AcademicEvent:
    """An academic calendar event."""
    date: str
    event: str
    semester: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None


# Known UGA calendar sources
CALENDAR_SOURCES = {
    'deadlines_2026': 'https://busfin.uga.edu/wp-content/uploads/deadlines_ay_2026.pdf',
    'deadlines_2025': 'https://busfin.uga.edu/wp-content/uploads/deadlines_ay_2025.pdf',
}

# Registrar calendar URLs (public pages)
REGISTRAR_CALENDARS = {
    'academic': 'https://reg.uga.edu/calendars/academic-calendars/',
    'registration': 'https://reg.uga.edu/calendars/registration-dates/',
    'final_exams': 'https://reg.uga.edu/calendars/final-exam-schedule/',
}


async def download_pdf(url: str, output_path: str) -> bool:
    """Download a PDF file."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded {url} to {output_path}")
            return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False


def parse_deadlines_pdf(pdf_path: str) -> list[AcademicEvent]:
    """Parse the financial deadlines PDF (table format).

    Returns:
        List of AcademicEvent objects
    """
    events = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()

                for table in tables:
                    current_semester = None

                    # First row is headers
                    headers = table[0] if table else []

                    for row in table[1:]:
                        if not row:
                            continue

                        # Check for semester name
                        for cell in row:
                            if cell and ('FALL' in str(cell).upper() or 'SPRING' in str(cell).upper() or 'SUMMER' in str(cell).upper()):
                                semester_match = re.search(r'(FALL|SPRING|SUMMER)\s*(\d{4})', str(cell), re.IGNORECASE)
                                if semester_match:
                                    current_semester = f"{semester_match.group(1).title()} {semester_match.group(2)}"

                        # Extract dates from the row
                        for i, cell in enumerate(row):
                            if not cell:
                                continue

                            cell_str = str(cell).strip()

                            # Look for date patterns
                            date_patterns = [
                                r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{1,2})',
                                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{1,2})',
                                r'(\d{1,2})/(\d{1,2})/(\d{2,4})',
                            ]

                            for pattern in date_patterns:
                                matches = re.findall(pattern, cell_str, re.IGNORECASE)
                                for match in matches:
                                    if len(match) == 3 and match[0] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                                        date_str = f"{match[1]} {match[2]}"
                                    elif len(match) == 2:
                                        date_str = f"{match[0]} {match[1]}"
                                    else:
                                        date_str = cell_str

                                    # Get event description from header
                                    event_desc = headers[i] if i < len(headers) and headers[i] else "Deadline"
                                    event_desc = str(event_desc).replace('\n', ' ').strip()

                                    if date_str and event_desc:
                                        events.append(AcademicEvent(
                                            date=date_str,
                                            event=event_desc[:200],
                                            semester=current_semester,
                                            category=categorize_event(event_desc),
                                            source='busfin_deadlines',
                                        ))

        logger.info(f"Parsed {len(events)} events from deadlines PDF")
        return events

    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_path}: {e}")
        return []


async def scrape_registrar_calendar_http(url: str, name: str) -> list[AcademicEvent]:
    """Scrape the registrar's academic calendar using HTTP (no browser).

    Args:
        url: URL to the calendar page
        name: Calendar name for source tracking

    Returns:
        List of AcademicEvent objects
    """
    events = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the main content area
            content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup

            # Look for tables with calendar data
            tables = content.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                current_semester = None

                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # Check if this row is a header/semester indicator
                        row_text = row.get_text().strip()
                        semester_match = re.search(r'(Fall|Spring|Summer)\s*(\d{4})', row_text, re.IGNORECASE)
                        if semester_match:
                            current_semester = f"{semester_match.group(1).title()} {semester_match.group(2)}"

                        date_text = cells[0].get_text().strip()
                        event_text = cells[1].get_text().strip() if len(cells) > 1 else ""

                        # Check if first cell looks like a date
                        if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', date_text, re.IGNORECASE):
                            events.append(AcademicEvent(
                                date=date_text,
                                event=event_text[:200],
                                semester=current_semester,
                                category=categorize_event(event_text),
                                source=f'registrar_{name}',
                            ))

            # If no tables found, try parsing text content
            if not events:
                text = content.get_text()
                lines = text.split('\n')
                current_semester = None

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Check for semester headers
                    semester_match = re.search(r'^(Fall|Spring|Summer)\s*(\d{4})', line, re.IGNORECASE)
                    if semester_match:
                        current_semester = f"{semester_match.group(1).title()} {semester_match.group(2)}"
                        continue

                    # Look for date patterns
                    date_match = re.match(
                        r'^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:-\d{1,2})?(?:,?\s*\d{4})?)',
                        line, re.IGNORECASE
                    )
                    if date_match:
                        date_str = date_match.group(1)
                        event_text = line[len(date_str):].strip()
                        event_text = re.sub(r'^[\s,\-–:]+', '', event_text)

                        if event_text:
                            events.append(AcademicEvent(
                                date=date_str,
                                event=event_text[:200],
                                semester=current_semester,
                                category=categorize_event(event_text),
                                source=f'registrar_{name}',
                            ))

            logger.info(f"Scraped {len(events)} events from {name} registrar calendar")

    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")

    return events


async def scrape_registrar_calendar(url: str, semester: str) -> list[AcademicEvent]:
    """Scrape the registrar's academic calendar HTML page.

    Args:
        url: URL to the calendar page
        semester: Semester name (e.g., "Fall 2025")

    Returns:
        List of AcademicEvent objects
    """
    events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)

            # The registrar calendar is usually in a table or definition list
            # Try to find calendar entries

            # Method 1: Look for tables
            tables = await page.query_selector_all('table')
            for table in tables:
                rows = await table.query_selector_all('tr')
                for row in rows:
                    cells = await row.query_selector_all('td, th')
                    if len(cells) >= 2:
                        date_text = await cells[0].inner_text()
                        event_text = await cells[1].inner_text() if len(cells) > 1 else ""

                        # Check if first cell looks like a date
                        if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', date_text, re.IGNORECASE):
                            events.append(AcademicEvent(
                                date=date_text.strip(),
                                event=event_text.strip()[:200],
                                semester=semester,
                                category=categorize_event(event_text),
                                source='registrar',
                            ))

            # Method 2: Look for definition lists or structured content
            if not events:
                # Get all text and try to parse
                body_text = await page.inner_text('main, .content, article, body')
                lines = body_text.split('\n')

                for i, line in enumerate(lines):
                    line = line.strip()
                    # Look for date patterns at the start of a line
                    date_match = re.match(
                        r'^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:-\d{1,2})?(?:,?\s*\d{4})?)',
                        line, re.IGNORECASE
                    )
                    if date_match:
                        date_str = date_match.group(1)
                        event_text = line[len(date_str):].strip()
                        event_text = re.sub(r'^[\s,\-–:]+', '', event_text)

                        if event_text:
                            events.append(AcademicEvent(
                                date=date_str,
                                event=event_text[:200],
                                semester=semester,
                                category=categorize_event(event_text),
                                source='registrar',
                            ))

            logger.info(f"Scraped {len(events)} events from {semester} registrar calendar")

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")

        finally:
            await context.close()
            await browser.close()

    return events


def categorize_event(event_text: str) -> str:
    """Categorize an event based on keywords."""
    text_lower = event_text.lower()

    if any(w in text_lower for w in ['registration', 'register', 'enroll']):
        return 'registration'
    elif any(w in text_lower for w in ['drop', 'withdraw', 'add/drop', 'withdrawal']):
        return 'add_drop'
    elif any(w in text_lower for w in ['fee', 'payment', 'tuition', 'refund', 'charge']):
        return 'fees'
    elif any(w in text_lower for w in ['graduation', 'commencement', 'degree']):
        return 'graduation'
    elif any(w in text_lower for w in ['exam', 'final', 'midterm', 'reading']):
        return 'exams'
    elif any(w in text_lower for w in ['class', 'instruction', 'begin', 'end', 'last day']):
        return 'classes'
    elif any(w in text_lower for w in ['holiday', 'break', 'recess', 'closed', 'thanksgiving', 'labor day']):
        return 'holidays'
    elif any(w in text_lower for w in ['aid', 'disbursement', 'financial']):
        return 'financial_aid'
    else:
        return 'other'


async def scrape_deadlines_pdf(url: str, name: str = "deadlines") -> list[AcademicEvent]:
    """Scrape a deadlines PDF.

    Args:
        url: URL to the PDF
        name: Name for the calendar

    Returns:
        List of AcademicEvent objects
    """
    temp_path = f"/tmp/uga_{name}.pdf"

    if await download_pdf(url, temp_path):
        events = parse_deadlines_pdf(temp_path)
        return events

    return []


async def scrape_all_calendars() -> list[AcademicEvent]:
    """Scrape all known calendar sources.

    Returns:
        List of all events
    """
    all_events = []

    # Scrape registrar calendars
    for semester, url in REGISTRAR_CALENDARS.items():
        semester_name = semester.replace('_', ' ').title()
        events = await scrape_registrar_calendar(url, semester_name)
        all_events.extend(events)

    # Scrape deadlines PDFs
    for name, url in CALENDAR_SOURCES.items():
        events = await scrape_deadlines_pdf(url, name)
        all_events.extend(events)

    return all_events


def save_to_db(events: list[AcademicEvent]):
    """Save events to database."""
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/uga_courses')

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    try:
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS academic_calendar (
                id SERIAL PRIMARY KEY,
                date VARCHAR(100),
                event VARCHAR(500) NOT NULL,
                semester VARCHAR(50),
                category VARCHAR(50),
                source VARCHAR(100),
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, event, semester)
            )
        """)

        # Insert events
        for event in events:
            cur.execute("""
                INSERT INTO academic_calendar (date, event, semester, category, source)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (date, event, semester) DO UPDATE SET
                    category = EXCLUDED.category,
                    source = EXCLUDED.source,
                    scraped_at = CURRENT_TIMESTAMP
            """, (event.date, event.event, event.semester, event.category, event.source))

        conn.commit()
        logger.info(f"Saved {len(events)} events to database")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving to database: {e}")
        raise

    finally:
        cur.close()
        conn.close()


def main():
    """Main entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Scrape UGA Academic Calendars')
    parser.add_argument('--registrar', '-r', action='store_true', help='Scrape registrar calendars')
    parser.add_argument('--deadlines', '-d', action='store_true', help='Scrape deadline PDFs')
    parser.add_argument('--all', '-a', action='store_true', help='Scrape all calendars')
    parser.add_argument('--save', '-s', action='store_true', help='Save to database')
    parser.add_argument('--output', '-o', help='Output JSON file')

    args = parser.parse_args()

    events = []

    if args.registrar or args.all:
        for name, url in REGISTRAR_CALENDARS.items():
            evts = asyncio.run(scrape_registrar_calendar_http(url, name))
            events.extend(evts)

    if args.deadlines or args.all:
        for name, url in CALENDAR_SOURCES.items():
            evts = asyncio.run(scrape_deadlines_pdf(url, name))
            events.extend(evts)

    if not args.registrar and not args.deadlines and not args.all:
        # Default: scrape registrar calendars
        for name, url in REGISTRAR_CALENDARS.items():
            evts = asyncio.run(scrape_registrar_calendar_http(url, name))
            events.extend(evts)

    if args.save:
        save_to_db(events)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump([{
                'date': e.date,
                'event': e.event,
                'semester': e.semester,
                'category': e.category,
                'source': e.source
            } for e in events], f, indent=2)
        logger.info(f"Saved {len(events)} events to {args.output}")
    else:
        print(f"\n=== Found {len(events)} events ===\n")
        for event in events[:50]:
            print(f"{event.semester or 'N/A':15} {event.date or 'N/A':25} [{event.category or 'N/A':12}] {event.event[:50]}")


if __name__ == '__main__':
    main()
