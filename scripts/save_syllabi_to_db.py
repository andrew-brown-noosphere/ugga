"""Save scraped syllabi to the database."""
import asyncio
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

from src.services.syllabus_scraper_playwright import SyllabusScraperPlaywright

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection."""
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/uga_courses')
    return psycopg2.connect(database_url)


def save_syllabi_to_db(syllabi, dept_code: str, semester: str = None):
    """Save scraped syllabi to database.

    Args:
        syllabi: List of ScrapedSyllabus objects
        dept_code: Department code for source tracking
        semester: Semester for source tracking
    """
    if not syllabi:
        logger.warning("No syllabi to save")
        return 0

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Build source string
        source = f"syllabus.uga.edu/{dept_code}"
        if semester:
            source += f"/{semester}"

        # Prepare data for batch insert
        data = []
        for s in syllabi:
            data.append((
                s.course_code,
                s.course_title,
                s.section,
                s.semester,
                s.instructor_name,
                s.syllabus_url,
                s.cv_url,
                s.department,
                s.file_name,
                s.file_type,
                s.crn,
                s.grid_index,
                source,
            ))

        # Insert with ON CONFLICT DO NOTHING to avoid duplicates
        # Using a composite key of course_code, semester, instructor_name, file_name
        insert_sql = """
            INSERT INTO syllabi (
                course_code, course_title, section, semester, instructor_name,
                syllabus_url, cv_url, department, file_name, file_type, crn,
                grid_index, source, scraped_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT DO NOTHING
        """

        # Use execute_batch for efficiency
        execute_batch(cur, insert_sql, data, page_size=100)

        inserted_count = cur.rowcount
        conn.commit()

        logger.info(f"Saved {len(data)} syllabi to database ({inserted_count} new)")
        return len(data)

    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving syllabi: {e}")
        raise

    finally:
        cur.close()
        conn.close()


def clear_syllabi_for_department(dept_code: str):
    """Clear existing syllabi for a department before re-scraping.

    Args:
        dept_code: Department code
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM syllabi WHERE department = %s", (dept_code,))
        deleted = cur.rowcount
        conn.commit()
        logger.info(f"Cleared {deleted} existing syllabi for {dept_code}")
        return deleted

    except Exception as e:
        conn.rollback()
        logger.error(f"Error clearing syllabi: {e}")
        raise

    finally:
        cur.close()
        conn.close()


async def scrape_and_save_department(dept_code: str, semester_value: str = None, clear_existing: bool = False):
    """Scrape syllabi for a department and save to database.

    Args:
        dept_code: Department dropdown value (e.g., 'CS')
        semester_value: Optional semester value
        clear_existing: If True, clear existing syllabi before saving
    """
    scraper = SyllabusScraperPlaywright(headless=True)

    logger.info(f"Scraping syllabi for {dept_code}...")
    syllabi = await scraper.scrape_syllabi_for_department(dept_code, semester_value)

    if not syllabi:
        logger.warning(f"No syllabi found for {dept_code}")
        return 0

    if clear_existing:
        clear_syllabi_for_department(dept_code)

    saved = save_syllabi_to_db(syllabi, dept_code, semester_value)

    logger.info(f"Completed: {len(syllabi)} syllabi scraped, {saved} saved for {dept_code}")
    return saved


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Scrape and save syllabi to database')
    parser.add_argument('department', nargs='?', default='CS', help='Department code (default: CS)')
    parser.add_argument('--semester', '-s', help='Semester value (optional)')
    parser.add_argument('--clear', '-c', action='store_true', help='Clear existing syllabi before saving')
    parser.add_argument('--all', '-a', action='store_true', help='Scrape all major departments')

    args = parser.parse_args()

    if args.all:
        # Scrape major STEM departments
        departments = ['CS', 'MAT', 'STAT', 'PHY', 'CHM', 'BIO', 'ECN']
        for dept in departments:
            try:
                asyncio.run(scrape_and_save_department(dept, args.semester, args.clear))
            except Exception as e:
                logger.error(f"Error scraping {dept}: {e}")
    else:
        asyncio.run(scrape_and_save_department(args.department, args.semester, args.clear))


if __name__ == '__main__':
    main()
