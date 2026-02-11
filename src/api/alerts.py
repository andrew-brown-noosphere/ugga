"""
Seat Alert API endpoints.

Allows users to:
- Create alerts for seat availability changes
- List their active alerts
- Delete alerts
- View alert history
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_

from src.models.database import User, SeatAlert, Section, Course, get_session_factory
from src.api.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# =============================================================================
# Schemas
# =============================================================================

class SeatAlertCreate(BaseModel):
    """Request to create a seat alert."""
    crn: str = Field(..., description="Course Reference Number")
    course_code: str = Field(..., description="Course code (e.g., CSCI 1302)")
    section_code: Optional[str] = Field(None, description="Section code")
    term: str = Field(..., description="Term (e.g., Spring 2026)")
    alert_type: str = Field(
        "seats_available",
        pattern="^(seats_available|seats_below|any_change)$",
        description="Type of alert"
    )
    threshold: int = Field(1, ge=1, le=100, description="Threshold for seats_below type")


class SeatAlertResponse(BaseModel):
    """Response for a seat alert."""
    id: int
    crn: str
    course_code: str
    section_code: Optional[str]
    term: str
    alert_type: str
    threshold: int
    last_known_seats: int
    is_active: bool
    triggered_at: Optional[datetime]
    created_at: datetime

    # Current section info (if available)
    current_seats: Optional[int] = None
    class_size: Optional[int] = None
    instructor: Optional[str] = None
    days: Optional[str] = None
    start_time: Optional[str] = None

    class Config:
        from_attributes = True


class SeatAlertsResponse(BaseModel):
    """List of seat alerts."""
    alerts: list[SeatAlertResponse]
    total: int
    active_count: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=SeatAlertsResponse)
async def get_seat_alerts(
    active_only: bool = Query(True, description="Only return active alerts"),
    user: User = Depends(get_current_user),
):
    """Get user's seat alerts."""
    session_factory = get_session_factory()

    with session_factory() as session:
        query = select(SeatAlert).where(SeatAlert.user_id == user.id)

        if active_only:
            query = query.where(SeatAlert.is_active == True)

        query = query.order_by(SeatAlert.created_at.desc())
        alerts = list(session.execute(query).scalars().all())

        # Enrich with current section data
        responses = []
        for alert in alerts:
            # Get current section info
            section = session.execute(
                select(Section).where(Section.crn == alert.crn)
            ).scalar_one_or_none()

            response = SeatAlertResponse(
                id=alert.id,
                crn=alert.crn,
                course_code=alert.course_code,
                section_code=alert.section_code,
                term=alert.term,
                alert_type=alert.alert_type,
                threshold=alert.threshold,
                last_known_seats=alert.last_known_seats,
                is_active=alert.is_active,
                triggered_at=alert.triggered_at,
                created_at=alert.created_at,
            )

            if section:
                response.current_seats = section.seats_available
                response.class_size = section.class_size
                response.instructor = section.instructor
                response.days = section.days
                response.start_time = section.start_time

            responses.append(response)

        active_count = len([a for a in alerts if a.is_active])

        return SeatAlertsResponse(
            alerts=responses,
            total=len(alerts),
            active_count=active_count,
        )


@router.post("", response_model=SeatAlertResponse)
async def create_seat_alert(
    data: SeatAlertCreate,
    user: User = Depends(get_current_user),
):
    """
    Create a seat alert.

    Alert types:
    - seats_available: Notify when seats become available (from 0)
    - seats_below: Notify when seats drop to or below threshold
    - any_change: Notify on any seat count change
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        # Check if user already has an active alert for this CRN
        existing = session.execute(
            select(SeatAlert).where(and_(
                SeatAlert.user_id == user.id,
                SeatAlert.crn == data.crn,
                SeatAlert.is_active == True,
            ))
        ).scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="You already have an active alert for this section"
            )

        # Check alert limit (prevent abuse)
        active_count = session.execute(
            select(SeatAlert).where(and_(
                SeatAlert.user_id == user.id,
                SeatAlert.is_active == True,
            ))
        ).scalars().all()

        max_alerts = 20  # Limit per user
        if len(active_count) >= max_alerts:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {max_alerts} active alerts allowed"
            )

        # Get current seat count
        section = session.execute(
            select(Section).where(Section.crn == data.crn)
        ).scalar_one_or_none()

        current_seats = section.seats_available if section else 0

        # Create alert
        alert = SeatAlert(
            user_id=user.id,
            crn=data.crn,
            course_code=data.course_code,
            section_code=data.section_code,
            term=data.term,
            alert_type=data.alert_type,
            threshold=data.threshold,
            last_known_seats=current_seats,
        )

        session.add(alert)
        session.commit()
        session.refresh(alert)

        response = SeatAlertResponse(
            id=alert.id,
            crn=alert.crn,
            course_code=alert.course_code,
            section_code=alert.section_code,
            term=alert.term,
            alert_type=alert.alert_type,
            threshold=alert.threshold,
            last_known_seats=alert.last_known_seats,
            is_active=alert.is_active,
            triggered_at=alert.triggered_at,
            created_at=alert.created_at,
        )

        if section:
            response.current_seats = section.seats_available
            response.class_size = section.class_size
            response.instructor = section.instructor
            response.days = section.days
            response.start_time = section.start_time

        return response


@router.delete("/{alert_id}")
async def delete_seat_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
):
    """Delete a seat alert."""
    session_factory = get_session_factory()

    with session_factory() as session:
        alert = session.execute(
            select(SeatAlert).where(and_(
                SeatAlert.id == alert_id,
                SeatAlert.user_id == user.id,
            ))
        ).scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        session.delete(alert)
        session.commit()

        return {"status": "deleted"}


@router.post("/{alert_id}/deactivate")
async def deactivate_seat_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
):
    """Deactivate a seat alert without deleting it."""
    session_factory = get_session_factory()

    with session_factory() as session:
        alert = session.execute(
            select(SeatAlert).where(and_(
                SeatAlert.id == alert_id,
                SeatAlert.user_id == user.id,
            ))
        ).scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.is_active = False
        session.commit()

        return {"status": "deactivated"}


@router.post("/{alert_id}/reactivate")
async def reactivate_seat_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
):
    """Reactivate a previously triggered or deactivated alert."""
    session_factory = get_session_factory()

    with session_factory() as session:
        alert = session.execute(
            select(SeatAlert).where(and_(
                SeatAlert.id == alert_id,
                SeatAlert.user_id == user.id,
            ))
        ).scalar_one_or_none()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        # Get current seat count
        section = session.execute(
            select(Section).where(Section.crn == alert.crn)
        ).scalar_one_or_none()

        if section:
            alert.last_known_seats = section.seats_available

        alert.is_active = True
        alert.triggered_at = None
        alert.notification_sent = False
        session.commit()

        return {"status": "reactivated"}


# =============================================================================
# Quick Alert (One-click from course listing)
# =============================================================================

@router.post("/quick/{crn}")
async def quick_seat_alert(
    crn: str,
    user: User = Depends(get_current_user),
):
    """
    Create a quick alert for a section by CRN.

    Automatically determines course code and term from the section.
    Sets alert type to "seats_available" by default.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        # Get section info
        section = session.execute(
            select(Section).where(Section.crn == crn)
        ).scalar_one_or_none()

        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        # Get course info
        course = session.get(Course, section.course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check for existing alert
        existing = session.execute(
            select(SeatAlert).where(and_(
                SeatAlert.user_id == user.id,
                SeatAlert.crn == crn,
                SeatAlert.is_active == True,
            ))
        ).scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="You already have an active alert for this section"
            )

        # Get term from schedule
        from src.models.database import Schedule
        schedule = session.get(Schedule, course.schedule_id)
        term = schedule.term if schedule else "Unknown"

        # Create alert
        alert = SeatAlert(
            user_id=user.id,
            crn=crn,
            course_code=course.course_code,
            section_code=section.section_code,
            term=term,
            alert_type="seats_available",
            threshold=1,
            last_known_seats=section.seats_available,
        )

        session.add(alert)
        session.commit()

        return {
            "status": "created",
            "alert_id": alert.id,
            "message": f"Alert created for {course.course_code} (CRN: {crn}). "
                      f"You'll be notified when seats become available.",
        }
