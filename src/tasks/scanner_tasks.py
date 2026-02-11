"""
Celery tasks for schedule scanning operations.

These tasks run asynchronously to:
- Scan course schedules from UGA web interface
- Update seat availability in real-time
- Process scanned data through the RAG pipeline
"""
import asyncio
import logging
from typing import Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from src.celery_app import celery_app
from src.scanners.schedule_scanner import UGAScheduleScanner, ScanProgress

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=3600,  # 1 hour soft limit
    time_limit=3900,  # 1 hour 5 min hard limit
)
def scan_term_task(self, term: str, max_pages: Optional[int] = None) -> dict:
    """
    Celery task to scan a term's schedule.

    Args:
        term: Term identifier (e.g., "Spring 2026")
        max_pages: Optional limit on pages to scan

    Returns:
        dict with scan results summary
    """
    task_id = self.request.id
    logger.info(f"Starting scan task {task_id} for term: {term}")

    async def run_scan():
        scanner = UGAScheduleScanner(headless=True)

        # Track progress for task state updates
        async def progress_callback(progress: ScanProgress):
            self.update_state(
                state="PROGRESS",
                meta={
                    "current_page": progress.current_page,
                    "total_pages": progress.total_pages,
                    "courses_found": progress.courses_found,
                    "sections_found": progress.sections_found,
                    "term": progress.term,
                    "status": progress.status,
                }
            )

        try:
            schedule = await scanner.scan_term(
                term,
                max_pages=max_pages,
                progress_callback=progress_callback
            )
            return {
                "success": True,
                "term": schedule.metadata.term,
                "total_courses": schedule.metadata.total_courses,
                "total_sections": schedule.metadata.total_sections,
                "source_url": schedule.metadata.source_url,
            }
        except Exception as e:
            logger.error(f"Scan failed for {term}: {e}")
            raise

    try:
        # Run the async scan in a new event loop
        result = asyncio.run(run_scan())
        logger.info(f"Completed scan task {task_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            return {
                "success": False,
                "term": term,
                "error": str(e),
            }


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=600,  # 10 min soft limit
    time_limit=660,  # 11 min hard limit
)
def update_seat_availability_task(self, term: str) -> dict:
    """
    Celery task to update seat availability for a term.

    This is a lighter operation than a full scan, optimized for
    frequent updates during registration periods.

    Args:
        term: Term identifier (e.g., "Spring 2026")

    Returns:
        dict with update results
    """
    task_id = self.request.id
    logger.info(f"Starting seat availability update {task_id} for term: {term}")

    async def run_update():
        scanner = UGAScheduleScanner(headless=True)
        return await scanner.update_seat_availability(term)

    try:
        availability = asyncio.run(run_update())
        result = {
            "success": True,
            "term": term,
            "sections_updated": len(availability),
        }
        logger.info(f"Completed availability update {task_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Availability update {task_id} failed: {e}")
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            return {
                "success": False,
                "term": term,
                "error": str(e),
            }


@celery_app.task
def update_all_seat_availability() -> dict:
    """
    Periodic task to update seat availability for all active terms.

    Triggered by Celery beat scheduler.
    """
    # Active terms to update
    active_terms = [
        "Spring 2026",
        "Summer 2026",
        "Fall 2026",
    ]

    results = []
    for term in active_terms:
        # Chain the tasks to run sequentially
        result = update_seat_availability_task.delay(term)
        results.append({"term": term, "task_id": result.id})

    return {
        "triggered": len(results),
        "tasks": results,
    }


@celery_app.task(
    bind=True,
    max_retries=2,
)
def scan_and_process_term(self, term: str) -> dict:
    """
    Full pipeline: scan term and process through RAG pipeline.

    This combines scanning with embedding generation for semantic search.
    """
    task_id = self.request.id
    logger.info(f"Starting full scan+process pipeline {task_id} for: {term}")

    # Step 1: Scan the term
    self.update_state(state="SCANNING", meta={"term": term, "step": "scanning"})

    async def run_pipeline():
        scanner = UGAScheduleScanner(headless=True)
        schedule = await scanner.scan_term(term)
        return schedule

    try:
        schedule = asyncio.run(run_pipeline())

        # Step 2: Process through RAG pipeline (embeddings, etc.)
        # This will be connected to the existing CourseService
        self.update_state(
            state="PROCESSING",
            meta={
                "term": term,
                "step": "processing",
                "courses": schedule.metadata.total_courses,
            }
        )

        # TODO: Call CourseService to process and store the schedule
        # await course_service.process_schedule(schedule)

        return {
            "success": True,
            "term": term,
            "total_courses": schedule.metadata.total_courses,
            "total_sections": schedule.metadata.total_sections,
            "processed": True,
        }

    except Exception as e:
        logger.error(f"Pipeline {task_id} failed: {e}")
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            return {
                "success": False,
                "term": term,
                "error": str(e),
            }
