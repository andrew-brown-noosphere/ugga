#!/usr/bin/env python3
"""
Scrape all bulletin course details from programs.
"""
import asyncio
import logging
import re
import sys
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from sqlalchemy import select

# Add project root to path
sys.path.insert(0, '/Users/andrewbrown/Sites/uga-course-scheduler')

from src.models.database import get_engine, get_session_factory, init_db, Program, BulletinCourse
from src.services.bulletin_scraper import BulletinScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/bulletin_courses_scrape.log')
    ]
)
logger = logging.getLogger(__name__)


async def collect_all_course_ids():
    """Collect all unique course bulletin IDs from all programs."""
    engine = get_engine()
    Session = get_session_factory(engine)

    all_bulletin_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()

        with Session() as session:
            programs = session.execute(select(Program)).scalars().all()
            program_urls = [(p.bulletin_url, p.name) for p in programs if p.bulletin_url]

        logger.info(f"Collecting course IDs from {len(program_urls)} programs...")

        for i, (url, name) in enumerate(program_urls, 1):
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(2000)

                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')

                course_links = soup.find_all('a', href=re.compile(r'/Course/Details/\d+'))

                for link in course_links:
                    href = link.get('href', '')
                    match = re.search(r'/Course/Details/(\d+)', href)
                    if match:
                        all_bulletin_ids.add(match.group(1))

                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"  Error collecting from {name}: {e}")

        await browser.close()

    return all_bulletin_ids


async def scrape_all_courses():
    """Scrape all bulletin courses."""
    engine = get_engine()
    init_db(engine)
    Session = get_session_factory(engine)

    # Collect all course IDs
    all_ids = await collect_all_course_ids()

    # Check which ones we already have
    with Session() as session:
        existing = session.execute(
            select(BulletinCourse.bulletin_id)
        ).scalars().all()
        existing_ids = set(existing)

    new_ids = list(all_ids - existing_ids)
    logger.info(f"Found {len(new_ids)} new courses to scrape")

    if not new_ids:
        logger.info("No new courses to scrape!")
        return

    # Scrape courses
    async with BulletinScraper() as scraper:
        success = 0
        failed = 0

        for i, bulletin_id in enumerate(new_ids, 1):
            try:
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{len(new_ids)} ({success} success, {failed} failed)")

                course = await scraper.scrape_course(bulletin_id)

                if course:
                    scraper.save_course(course)
                    success += 1
                else:
                    failed += 1

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"Error scraping course {bulletin_id}: {e}")
                failed += 1

        logger.info(f"\n=== COMPLETE ===")
        logger.info(f"Success: {success}")
        logger.info(f"Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(scrape_all_courses())
