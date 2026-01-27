"""
Seed social features data.

Seeds:
1. Study groups for each unique course code
2. Greek life cohorts (fraternities and sororities)

Run with: python -m src.scripts.seed_social
"""
import secrets
import string
from datetime import datetime

from sqlalchemy import select, text

from src.models.database import (
    get_engine, get_session_factory,
    Course, StudyGroup, Cohort
)


def generate_invite_code(length: int = 8) -> str:
    """Generate a random invite code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def seed_study_groups(session_factory):
    """Create one study group per unique course code."""
    print("Seeding study groups...")

    with session_factory() as session:
        # Get all unique course codes from current schedule
        result = session.execute(
            text("""
                SELECT DISTINCT c.course_code, c.title
                FROM courses c
                JOIN schedules s ON c.schedule_id = s.id
                WHERE s.is_current = true
                ORDER BY c.course_code
            """)
        )
        courses = result.fetchall()
        print(f"Found {len(courses)} unique courses")

        # Check existing study groups
        existing = session.execute(
            select(StudyGroup.course_code).where(StudyGroup.is_official == True)
        ).scalars().all()
        existing_set = set(existing)
        print(f"Found {len(existing_set)} existing official study groups")

        created = 0
        for course_code, title in courses:
            # Normalize course code (remove spaces)
            normalized = course_code.replace(" ", "")

            if normalized in existing_set:
                continue

            # Create study group
            group = StudyGroup(
                course_code=normalized,
                name=f"{course_code} Study Group",
                description=f"Official study group for {title}. Claim this group to become the organizer and set up meeting times!",
                organizer_id=None,  # Unclaimed
                max_members=50,
                is_active=True,
                is_official=True,
            )
            session.add(group)
            created += 1

            if created % 500 == 0:
                session.commit()
                print(f"  Created {created} study groups...")

        session.commit()
        print(f"Created {created} new study groups")


# UGA Greek Organizations
# Source: https://greek.uga.edu/
UGA_FRATERNITIES = [
    ("Alpha Epsilon Pi", "AEPi"),
    ("Alpha Gamma Rho", "AGR"),
    ("Alpha Kappa Lambda", "AKL"),
    ("Alpha Tau Omega", "ATO"),
    ("Beta Theta Pi", "Beta"),
    ("Beta Upsilon Chi", "BYX"),
    ("Chi Phi", "Chi Phi"),
    ("Chi Psi", "Chi Psi"),
    ("Delta Chi", "Delta Chi"),
    ("Delta Sigma Phi", "Delta Sig"),
    ("Delta Tau Delta", "Delt"),
    ("Kappa Alpha Order", "KA"),
    ("Kappa Sigma", "Kappa Sig"),
    ("Lambda Chi Alpha", "Lambda Chi"),
    ("Phi Delta Theta", "Phi Delt"),
    ("Phi Gamma Delta", "FIJI"),
    ("Phi Kappa Psi", "Phi Psi"),
    ("Phi Kappa Tau", "Phi Tau"),
    ("Phi Sigma Kappa", "Phi Sig"),
    ("Pi Kappa Alpha", "Pike"),
    ("Pi Kappa Phi", "Pi Kapp"),
    ("Sigma Alpha Epsilon", "SAE"),
    ("Sigma Chi", "Sigma Chi"),
    ("Sigma Nu", "Sigma Nu"),
    ("Sigma Phi Epsilon", "SigEp"),
    ("Sigma Pi", "Sigma Pi"),
    ("Tau Kappa Epsilon", "TKE"),
    ("Theta Chi", "Theta Chi"),
    ("Zeta Beta Tau", "ZBT"),
]

UGA_SORORITIES = [
    ("Alpha Chi Omega", "AXO"),
    ("Alpha Delta Pi", "ADPi"),
    ("Alpha Gamma Delta", "AGD"),
    ("Alpha Omicron Pi", "AOPi"),
    ("Alpha Xi Delta", "AXiD"),
    ("Chi Omega", "Chi O"),
    ("Delta Delta Delta", "Tri Delt"),
    ("Delta Gamma", "DG"),
    ("Delta Phi Epsilon", "DPhiE"),
    ("Delta Zeta", "DZ"),
    ("Gamma Phi Beta", "Gamma Phi"),
    ("Kappa Alpha Theta", "Theta"),
    ("Kappa Delta", "KD"),
    ("Kappa Kappa Gamma", "Kappa"),
    ("Phi Mu", "Phi Mu"),
    ("Pi Beta Phi", "Pi Phi"),
    ("Sigma Delta Tau", "SDT"),
    ("Sigma Kappa", "Sigma Kappa"),
    ("Zeta Tau Alpha", "Zeta"),
]


def seed_greek_cohorts(session_factory):
    """Create cohorts for Greek organizations."""
    print("Seeding Greek life cohorts...")

    with session_factory() as session:
        # Check existing official cohorts
        existing = session.execute(
            select(Cohort.name).where(Cohort.is_official == True)
        ).scalars().all()
        existing_set = set(existing)
        print(f"Found {len(existing_set)} existing official cohorts")

        created = 0

        # Create fraternities
        for name, nickname in UGA_FRATERNITIES:
            if name in existing_set:
                continue

            # Generate unique invite code
            invite_code = generate_invite_code()
            while session.execute(
                select(Cohort).where(Cohort.invite_code == invite_code)
            ).scalar_one_or_none():
                invite_code = generate_invite_code()

            cohort = Cohort(
                name=name,
                description=f"{name} ({nickname}) - UGA IFC Fraternity. Join to coordinate schedules with your brothers!",
                org_type="fraternity",
                is_official=True,
                created_by_id=None,
                is_public=True,  # Greek orgs are public so members can find them
                max_members=500,
                invite_code=invite_code,
            )
            session.add(cohort)
            created += 1

        # Create sororities
        for name, nickname in UGA_SORORITIES:
            if name in existing_set:
                continue

            invite_code = generate_invite_code()
            while session.execute(
                select(Cohort).where(Cohort.invite_code == invite_code)
            ).scalar_one_or_none():
                invite_code = generate_invite_code()

            cohort = Cohort(
                name=name,
                description=f"{name} ({nickname}) - UGA Panhellenic Sorority. Join to coordinate schedules with your sisters!",
                org_type="sorority",
                is_official=True,
                created_by_id=None,
                is_public=True,
                max_members=500,
                invite_code=invite_code,
            )
            session.add(cohort)
            created += 1

        session.commit()
        print(f"Created {created} Greek cohorts ({len(UGA_FRATERNITIES)} fraternities, {len(UGA_SORORITIES)} sororities)")


def main():
    """Run all seeders."""
    print("=" * 60)
    print("Seeding Social Features")
    print("=" * 60)

    engine = get_engine()
    session_factory = get_session_factory(engine)

    seed_study_groups(session_factory)
    print()
    seed_greek_cohorts(session_factory)

    print()
    print("=" * 60)
    print("Seeding complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
