"""
Schedule Analyzer for UGA Course Scheduler.

Analyzes student schedules for:
- Walking time conflicts between back-to-back classes
- Daily route optimization
- Campus zone clustering
- Time gap analysis
"""
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from src.models.campus_graph import (
    CampusGraph, Building, GeoLocation,
    build_campus_graph_from_schedule, ATHENS_BUILDING_COORDS
)


@dataclass
class ScheduleSlot:
    """A single class in a student's schedule."""
    crn: str
    course_code: str
    title: str
    days: str  # e.g., "MWF", "TR"
    start_time: str  # e.g., "09:55 am"
    end_time: str  # e.g., "10:50 am"
    building: str
    room: str
    campus: str
    instructor: Optional[str] = None

    def parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse time string to datetime."""
        if not time_str:
            return None
        try:
            # Handle various formats
            time_str = time_str.strip().lower()
            for fmt in ["%I:%M %p", "%H:%M", "%I:%M%p"]:
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    @property
    def start_datetime(self) -> Optional[datetime]:
        return self.parse_time(self.start_time)

    @property
    def end_datetime(self) -> Optional[datetime]:
        return self.parse_time(self.end_time)

    def overlaps_day(self, other: "ScheduleSlot") -> bool:
        """Check if two slots share any day."""
        days1 = set(self.days) if self.days else set()
        days2 = set(other.days) if other.days else set()
        return bool(days1 & days2)

    def minutes_between(self, other: "ScheduleSlot") -> Optional[int]:
        """Get minutes between end of this class and start of other."""
        end = self.end_datetime
        start = other.start_datetime

        if not end or not start:
            return None

        diff = start - end
        return int(diff.total_seconds() / 60)


@dataclass
class WalkingConflict:
    """A potential conflict due to walking time between classes."""
    from_class: ScheduleSlot
    to_class: ScheduleSlot
    gap_minutes: int  # Time between classes
    walk_minutes: int  # Estimated walking time
    distance_meters: float
    day: str
    severity: str  # "warning", "critical"
    message: str


@dataclass
class DailyRoute:
    """A student's route through campus for one day."""
    day: str  # M, T, W, R, F
    classes: list[ScheduleSlot]
    total_walking_minutes: int
    total_distance_meters: float
    conflicts: list[WalkingConflict]


class ScheduleAnalyzer:
    """Analyzes student schedules for walking time issues."""

    # Minimum gap (minutes) needed between classes in different buildings
    MIN_GAP_SAME_BUILDING = 5
    MIN_GAP_ADJACENT_BUILDING = 8
    MIN_GAP_DEFAULT = 10

    def __init__(self, campus_graph: Optional[CampusGraph] = None):
        if campus_graph:
            self.graph = campus_graph
        else:
            # Load from saved data or build empty
            self.graph = self._load_or_build_graph()

    def _load_or_build_graph(self) -> CampusGraph:
        """Load campus graph from saved data or build new one."""
        data_path = Path(__file__).parent.parent.parent / "data" / "campus_buildings.json"
        if data_path.exists():
            with open(data_path) as f:
                buildings_data = json.load(f)
            return build_campus_graph_from_schedule(buildings_data)
        else:
            # Return empty graph with known coordinates
            graph = CampusGraph()
            for name, (lat, lon) in ATHENS_BUILDING_COORDS.items():
                building = Building(
                    id=name.lower().replace(" ", "_"),
                    name=name,
                    location=GeoLocation(lat, lon)
                )
                graph.add_building(building)
            return graph

    def analyze_schedule(self, slots: list[ScheduleSlot]) -> dict:
        """
        Analyze a student's schedule for potential issues.

        Returns dict with:
        - conflicts: list of WalkingConflict
        - daily_routes: dict of day -> DailyRoute
        - summary: overall statistics
        """
        conflicts = []
        daily_routes = {}

        # Group by day
        days = ["M", "T", "W", "R", "F"]
        for day in days:
            day_classes = [s for s in slots if s.days and day in s.days]
            if not day_classes:
                continue

            # Sort by start time
            day_classes.sort(key=lambda s: s.start_datetime or datetime.min)

            # Check consecutive pairs
            day_conflicts = []
            total_walk = 0
            total_dist = 0.0

            for i in range(len(day_classes) - 1):
                curr = day_classes[i]
                next_class = day_classes[i + 1]

                gap = curr.minutes_between(next_class)
                if gap is None:
                    continue

                # Get walking time
                walk_time = self.graph.walking_time(curr.building, next_class.building)

                if walk_time:
                    # Get distance too
                    b1 = self.graph.get_building(curr.building)
                    b2 = self.graph.get_building(next_class.building)
                    dist = b1.location.distance_to(b2.location) if (b1 and b2 and b1.location and b2.location) else 0

                    total_walk += walk_time
                    total_dist += dist

                    # Check if it's a problem
                    if gap < walk_time:
                        severity = "critical" if gap < walk_time - 5 else "warning"
                        conflict = WalkingConflict(
                            from_class=curr,
                            to_class=next_class,
                            gap_minutes=gap,
                            walk_minutes=walk_time,
                            distance_meters=dist,
                            day=day,
                            severity=severity,
                            message=self._format_conflict_message(curr, next_class, gap, walk_time)
                        )
                        day_conflicts.append(conflict)
                        conflicts.append(conflict)

            daily_routes[day] = DailyRoute(
                day=day,
                classes=day_classes,
                total_walking_minutes=total_walk,
                total_distance_meters=total_dist,
                conflicts=day_conflicts
            )

        # Build summary
        summary = {
            "total_conflicts": len(conflicts),
            "critical_conflicts": len([c for c in conflicts if c.severity == "critical"]),
            "warning_conflicts": len([c for c in conflicts if c.severity == "warning"]),
            "busiest_day": max(daily_routes.values(), key=lambda r: len(r.classes)).day if daily_routes else None,
            "most_walking_day": max(daily_routes.values(), key=lambda r: r.total_walking_minutes).day if daily_routes else None,
            "total_weekly_walking_minutes": sum(r.total_walking_minutes for r in daily_routes.values()),
            "total_weekly_distance_km": sum(r.total_distance_meters for r in daily_routes.values()) / 1000,
        }

        return {
            "conflicts": conflicts,
            "daily_routes": daily_routes,
            "summary": summary
        }

    def _format_conflict_message(
        self,
        from_class: ScheduleSlot,
        to_class: ScheduleSlot,
        gap: int,
        walk_time: int
    ) -> str:
        """Format a human-readable conflict message."""
        diff = walk_time - gap

        if gap <= 0:
            return (
                f"⚠️ Classes overlap! {from_class.course_code} ends at {from_class.end_time} "
                f"but {to_class.course_code} starts at {to_class.start_time}."
            )

        return (
            f"🚶 Tight transition: {from_class.course_code} ({from_class.building}) → "
            f"{to_class.course_code} ({to_class.building}). "
            f"You have {gap} min but need ~{walk_time} min to walk. "
            f"You might be {diff} min late!"
        )

    def suggest_alternatives(
        self,
        conflict: WalkingConflict,
        available_sections: list[dict]
    ) -> list[dict]:
        """
        Suggest alternative sections that would resolve a conflict.

        Args:
            conflict: The walking conflict to resolve
            available_sections: List of all available sections for the courses

        Returns:
            List of alternative sections that would work better
        """
        suggestions = []

        # Find sections for the "to" class that are in closer buildings
        # or at later times
        problem_course = conflict.to_class.course_code

        for section in available_sections:
            if section.get("course_code") != problem_course:
                continue

            # Check if this section is in a closer building
            alt_building = section.get("building")
            if not alt_building:
                continue

            walk_time = self.graph.walking_time(conflict.from_class.building, alt_building)
            if walk_time and walk_time < conflict.walk_minutes:
                suggestions.append({
                    "section": section,
                    "reason": f"Closer building ({alt_building}) - only {walk_time} min walk",
                    "saves_minutes": conflict.walk_minutes - walk_time
                })

            # Check if this section starts later
            alt_start = section.get("start_time")
            if alt_start:
                # Simple comparison - would need proper parsing for accuracy
                if alt_start > conflict.to_class.start_time:
                    suggestions.append({
                        "section": section,
                        "reason": f"Later start time ({alt_start}) gives more travel time",
                        "new_gap": "varies"
                    })

        return suggestions

    def get_daily_map_data(self, route: DailyRoute) -> dict:
        """
        Get data for rendering a daily route on a map.

        Returns GeoJSON-compatible data for the route.
        """
        points = []
        lines = []

        for i, slot in enumerate(route.classes):
            building = self.graph.get_building(slot.building)
            if building and building.location:
                points.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [building.location.longitude, building.location.latitude]
                    },
                    "properties": {
                        "order": i + 1,
                        "course": slot.course_code,
                        "building": slot.building,
                        "room": slot.room,
                        "time": f"{slot.start_time} - {slot.end_time}"
                    }
                })

                # Add line to next class
                if i < len(route.classes) - 1:
                    next_slot = route.classes[i + 1]
                    next_building = self.graph.get_building(next_slot.building)
                    if next_building and next_building.location:
                        # Check if this is a conflict
                        is_conflict = any(
                            c.from_class.crn == slot.crn and c.to_class.crn == next_slot.crn
                            for c in route.conflicts
                        )
                        lines.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [
                                    [building.location.longitude, building.location.latitude],
                                    [next_building.location.longitude, next_building.location.latitude]
                                ]
                            },
                            "properties": {
                                "from_course": slot.course_code,
                                "to_course": next_slot.course_code,
                                "is_conflict": is_conflict,
                                "walk_minutes": building.walking_time_to(next_building)
                            }
                        })

        return {
            "type": "FeatureCollection",
            "features": points + lines
        }
