"""
Celery tasks for embedding generation and seat availability alerts.

These tasks run asynchronously to:
- Generate embeddings for courses, programs, and documents
- Monitor seat availability changes and send alerts
- Process bulletin data through the RAG pipeline
"""
import logging
from datetime import datetime
from typing import Optional

from celery import shared_task

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


# =============================================================================
# Embedding Tasks
# =============================================================================

@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=1800,  # 30 min soft limit
    time_limit=1860,
)
def embed_all_courses_task(self, force: bool = False) -> dict:
    """
    Generate embeddings for all courses in current schedule.

    Args:
        force: Re-embed even if already has embedding

    Returns:
        dict with embedding results
    """
    task_id = self.request.id
    logger.info(f"Starting course embedding task {task_id}")

    try:
        from src.services.embedding_service import create_embedding_service
        svc = create_embedding_service()

        self.update_state(state="EMBEDDING", meta={"type": "courses"})
        count = svc.embed_courses(force=force)

        result = {
            "success": True,
            "type": "courses",
            "embedded_count": count,
        }
        logger.info(f"Completed course embedding: {count} courses")
        return result

    except Exception as e:
        logger.error(f"Course embedding failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=1800,
    time_limit=1860,
)
def embed_bulletin_courses_task(self, force: bool = False) -> dict:
    """
    Generate embeddings for all bulletin courses (catalog).

    Args:
        force: Re-embed even if already has embedding

    Returns:
        dict with embedding results
    """
    task_id = self.request.id
    logger.info(f"Starting bulletin course embedding task {task_id}")

    try:
        from src.services.embedding_service import create_embedding_service
        svc = create_embedding_service()

        self.update_state(state="EMBEDDING", meta={"type": "bulletin_courses"})
        count = svc.embed_bulletin_courses(force=force)

        result = {
            "success": True,
            "type": "bulletin_courses",
            "embedded_count": count,
        }
        logger.info(f"Completed bulletin embedding: {count} courses")
        return result

    except Exception as e:
        logger.error(f"Bulletin embedding failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=600,
    time_limit=660,
)
def embed_programs_task(self, force: bool = False) -> dict:
    """
    Generate embeddings for all degree programs.

    Args:
        force: Re-embed even if already has embedding

    Returns:
        dict with embedding results
    """
    task_id = self.request.id
    logger.info(f"Starting program embedding task {task_id}")

    try:
        from src.services.embedding_service import create_embedding_service
        svc = create_embedding_service()

        self.update_state(state="EMBEDDING", meta={"type": "programs"})
        count = svc.embed_programs(force=force)

        result = {
            "success": True,
            "type": "programs",
            "embedded_count": count,
        }
        logger.info(f"Completed program embedding: {count} programs")
        return result

    except Exception as e:
        logger.error(f"Program embedding failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=1800,
    time_limit=1860,
)
def embed_syllabi_task(self, limit: Optional[int] = None) -> dict:
    """
    Import and embed syllabi documents.

    Args:
        limit: Max syllabi to process (None = all)

    Returns:
        dict with import results
    """
    task_id = self.request.id
    logger.info(f"Starting syllabi embedding task {task_id}")

    try:
        from src.services.embedding_service import create_embedding_service
        svc = create_embedding_service()

        self.update_state(state="IMPORTING", meta={"type": "syllabi"})
        imported = svc.import_syllabi_to_documents(embed=True, limit=limit)

        self.update_state(state="EMBEDDING", meta={"type": "syllabi", "imported": imported})
        embedded = svc.embed_documents_batch(source_type="syllabus")

        result = {
            "success": True,
            "type": "syllabi",
            "imported_count": imported,
            "embedded_count": embedded,
        }
        logger.info(f"Completed syllabi processing: {imported} imported, {embedded} embedded")
        return result

    except Exception as e:
        logger.error(f"Syllabi embedding failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task
def embed_all_content() -> dict:
    """
    Daily task to embed all new content.

    Chains embedding tasks for all content types.
    """
    logger.info("Starting daily embedding pipeline")

    results = []

    # Trigger each embedding task
    tasks = [
        ("courses", embed_all_courses_task.delay(force=False)),
        ("bulletin", embed_bulletin_courses_task.delay(force=False)),
        ("programs", embed_programs_task.delay(force=False)),
        ("syllabi", embed_syllabi_task.delay()),
    ]

    for name, task in tasks:
        results.append({"type": name, "task_id": task.id})

    return {
        "triggered": len(results),
        "tasks": results,
    }


# =============================================================================
# Seat Availability Alert Tasks
# =============================================================================

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=300,
    time_limit=360,
)
def check_seat_alerts_task(self) -> dict:
    """
    Check for seat availability changes and send alerts.

    This task:
    1. Gets all active seat alerts from database
    2. Checks current availability for each watched section
    3. Sends notifications when seats become available
    4. Updates alert status
    """
    task_id = self.request.id
    logger.info(f"Starting seat alert check {task_id}")

    try:
        from sqlalchemy import select, and_
        from src.models.database import (
            get_session_factory, Section, SeatAlert, User
        )

        session_factory = get_session_factory()
        alerts_triggered = 0
        alerts_checked = 0

        with session_factory() as session:
            # Get active alerts
            alerts = session.execute(
                select(SeatAlert)
                .where(and_(
                    SeatAlert.is_active == True,
                    SeatAlert.triggered_at.is_(None),
                ))
            ).scalars().all()

            alerts_checked = len(alerts)
            logger.info(f"Checking {alerts_checked} active seat alerts")

            for alert in alerts:
                # Get current section data
                section = session.execute(
                    select(Section).where(Section.crn == alert.crn)
                ).scalar_one_or_none()

                if not section:
                    continue

                should_trigger = False

                # Check if seats became available
                if alert.alert_type == "seats_available":
                    if section.seats_available > 0:
                        should_trigger = True

                # Check if seats dropped below threshold
                elif alert.alert_type == "seats_below":
                    if section.seats_available <= alert.threshold:
                        should_trigger = True

                # Check if any change in availability
                elif alert.alert_type == "any_change":
                    if section.seats_available != alert.last_known_seats:
                        should_trigger = True

                if should_trigger:
                    # Get user for notification
                    user = session.get(User, alert.user_id)

                    if user:
                        # Send notification
                        _send_seat_alert_notification(
                            user=user,
                            alert=alert,
                            section=section,
                        )

                        # Mark alert as triggered
                        alert.triggered_at = datetime.utcnow()
                        alert.is_active = False
                        alerts_triggered += 1

                        logger.info(
                            f"Triggered alert for {user.email}: "
                            f"{section.course_code} has {section.seats_available} seats"
                        )

                # Update last known seats
                alert.last_known_seats = section.seats_available
                alert.last_checked_at = datetime.utcnow()

            session.commit()

        result = {
            "success": True,
            "alerts_checked": alerts_checked,
            "alerts_triggered": alerts_triggered,
        }
        logger.info(f"Seat alert check complete: {result}")
        return result

    except Exception as e:
        logger.error(f"Seat alert check failed: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    soft_time_limit=600,
    time_limit=660,
)
def track_seat_changes_task(self) -> dict:
    """
    Track seat availability changes for trending/analytics.

    Records historical seat data for:
    - Popular course tracking
    - Fill rate analysis
    - Registration pattern insights
    """
    task_id = self.request.id
    logger.info(f"Starting seat change tracking {task_id}")

    try:
        from sqlalchemy import select, text
        from src.models.database import (
            get_session_factory, Section, Schedule, SeatHistory
        )

        session_factory = get_session_factory()

        with session_factory() as session:
            # Get current schedule
            current_schedule = session.execute(
                select(Schedule).where(Schedule.is_current == True)
            ).scalar_one_or_none()

            if not current_schedule:
                return {"success": True, "message": "No current schedule"}

            # Get all sections with their current availability
            sections = session.execute(
                select(Section)
                .join(Section.course)
                .where(Section.course.has(schedule_id=current_schedule.id))
            ).scalars().all()

            records_created = 0
            now = datetime.utcnow()

            for section in sections:
                # Create history record
                history = SeatHistory(
                    section_id=section.id,
                    crn=section.crn,
                    seats_available=section.seats_available,
                    class_size=section.class_size,
                    waitlist_count=section.waitlist_count,
                    recorded_at=now,
                )
                session.add(history)
                records_created += 1

            session.commit()

            logger.info(f"Recorded {records_created} seat history entries")
            return {
                "success": True,
                "records_created": records_created,
                "schedule": current_schedule.term,
            }

    except Exception as e:
        logger.error(f"Seat tracking failed: {e}")
        return {"success": False, "error": str(e)}


def _send_seat_alert_notification(user, alert, section) -> bool:
    """
    Send notification to user about seat availability.

    Supports multiple notification channels:
    - Email (primary)
    - Push notification (if enabled)
    - SMS (if enabled and verified)
    """
    try:
        # Email notification
        if user.email:
            _send_email_alert(user, alert, section)

        # Push notification (if user has push enabled)
        if getattr(user, 'push_enabled', False):
            _send_push_alert(user, alert, section)

        return True

    except Exception as e:
        logger.error(f"Failed to send notification to {user.id}: {e}")
        return False


def _send_email_alert(user, alert, section):
    """Send email alert about seat availability."""
    try:
        from src.config import settings

        # Check if email service is configured
        if not settings.resend_api_key:
            logger.warning("Resend API key not configured, skipping email")
            return

        import resend
        resend.api_key = settings.resend_api_key

        subject = f"Seats Available: {section.course_code}"

        html_content = f"""
        <h2>Seats Available!</h2>
        <p>Good news! The class you're watching now has seats available:</p>

        <table style="border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Course:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{section.course_code}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>CRN:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{section.crn}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Section:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{section.section_code}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Instructor:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{section.instructor or 'TBA'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Available Seats:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd; color: green; font-weight: bold;">
                    {section.seats_available} / {section.class_size}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Schedule:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {section.days or 'TBA'} {section.start_time or ''} - {section.end_time or ''}
                </td>
            </tr>
        </table>

        <p>
            <a href="https://athena.uga.edu"
               style="background-color: #BA0C2F; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 4px; display: inline-block;">
                Register Now on Athena
            </a>
        </p>

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            You received this alert because you set up a seat notification on UGA Course Scheduler.
            <br>This alert has been deactivated. Set up a new alert if you still need to watch this class.
        </p>
        """

        resend.Emails.send({
            "from": "UGA Course Scheduler <alerts@coursescheduler.uga.edu>",
            "to": user.email,
            "subject": subject,
            "html": html_content,
        })

        logger.info(f"Sent email alert to {user.email} for {section.crn}")

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        raise


def _send_push_alert(user, alert, section):
    """Send push notification about seat availability."""
    # TODO: Implement push notifications (web push, mobile)
    logger.info(f"Push notification for {user.id}: {section.crn} has seats")
    pass
