"""
Campus Knowledge Graph for UGA.

Models the physical layout of UGA campuses to enable:
- Walking distance/time calculations between buildings
- Daily route optimization for students
- Schedule conflict detection (back-to-back classes across campus)
- Campus zone clustering for better scheduling

Schema follows JSON-LD patterns for semantic interoperability.
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class CampusZone(Enum):
    """Major zones within Athens campus for clustering."""
    NORTH = "north"           # North Campus (historic, humanities)
    SOUTH = "south"           # South Campus (sciences, engineering)
    EAST = "east"             # East Campus (vet, ag, health sciences)
    WEST = "west"             # West Campus (intramural fields area)
    CENTRAL = "central"       # Central (main library, student center)
    HEALTH_SCIENCES = "health_sciences"  # Health sciences complex


@dataclass
class GeoLocation:
    """Geographic coordinates for a location."""
    latitude: float
    longitude: float

    def distance_to(self, other: "GeoLocation") -> float:
        """Calculate distance in meters using Haversine formula."""
        import math
        R = 6371000  # Earth's radius in meters

        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = math.radians(other.latitude - self.latitude)
        dlon = math.radians(other.longitude - self.longitude)

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c


@dataclass
class Room:
    """A room within a building."""
    number: str
    building_id: str
    capacity: Optional[int] = None
    room_type: Optional[str] = None  # classroom, lab, lecture_hall, etc.
    floor: Optional[int] = None
    accessible: bool = True


@dataclass
class ParkingLocation:
    """A parking deck or lot on campus."""
    id: str
    name: str
    location: Optional[GeoLocation] = None
    campus: str = "Athens"
    parking_type: str = "deck"  # deck, lot, street
    permit_required: Optional[str] = None  # e.g., "C", "E", "R", "Any"
    total_spaces: Optional[int] = None
    accessible_spaces: Optional[int] = None
    ev_charging: bool = False
    hourly_rate: Optional[float] = None  # For visitor parking
    nearby_buildings: list[str] = field(default_factory=list)

    def walking_time_to(self, building: "Building", walk_speed_mps: float = 1.4) -> Optional[int]:
        """Estimate walking time to a building."""
        if not self.location or not building.location:
            return None
        distance = self.location.distance_to(building.location)
        adjusted = distance * 1.2
        return int(adjusted / walk_speed_mps / 60) + 1


@dataclass
class BusStop:
    """A bus stop on campus."""
    id: str
    name: str
    location: Optional[GeoLocation] = None
    routes: list[str] = field(default_factory=list)  # Route names/numbers
    nearby_buildings: list[str] = field(default_factory=list)
    shelter: bool = False
    accessible: bool = True


@dataclass
class BusRoute:
    """A campus or city bus route."""
    id: str
    name: str
    short_name: str  # e.g., "East-West", "Orbit"
    operator: str = "UGA Campus Transit"  # or "Athens Transit"
    stops: list[str] = field(default_factory=list)  # Stop IDs in order
    frequency_minutes: Optional[int] = None  # How often during peak
    first_departure: Optional[str] = None  # e.g., "7:00 am"
    last_departure: Optional[str] = None  # e.g., "10:00 pm"
    days_of_operation: str = "MTWRF"  # M, T, W, R, F, S, U
    color: Optional[str] = None  # For map display


@dataclass
class Building:
    """A building on campus."""
    id: str                    # Unique identifier
    name: str                  # Full name
    short_name: Optional[str] = None  # Abbreviation
    campus: str = "Athens"
    zone: Optional[CampusZone] = None
    location: Optional[GeoLocation] = None
    address: Optional[str] = None

    # Building characteristics
    floors: int = 1
    has_elevator: bool = True
    accessible: bool = True

    # Rooms in this building
    rooms: list[Room] = field(default_factory=list)

    # Activity metrics (computed from schedule)
    total_sections: int = 0
    total_courses: int = 0
    peak_hours: list[str] = field(default_factory=list)  # Busiest times

    def walking_time_to(self, other: "Building", walk_speed_mps: float = 1.4) -> Optional[int]:
        """
        Estimate walking time to another building in minutes.
        Default walk speed is 1.4 m/s (~3 mph, average walking pace).
        """
        if not self.location or not other.location:
            return None

        distance = self.location.distance_to(other.location)
        # Add 20% for non-straight paths, crosswalks, etc.
        adjusted_distance = distance * 1.2

        seconds = adjusted_distance / walk_speed_mps
        return int(seconds / 60) + 1  # Round up to nearest minute


@dataclass
class Campus:
    """A UGA campus location."""
    id: str
    name: str
    city: str
    state: str = "GA"
    buildings: list[Building] = field(default_factory=list)

    # Campus bounds for mapping
    center: Optional[GeoLocation] = None
    bounds: Optional[dict] = None  # {north, south, east, west}


@dataclass
class WalkingPath:
    """A walking path between two buildings."""
    from_building: str
    to_building: str
    distance_meters: float
    estimated_minutes: int
    accessible: bool = True
    indoor_path: bool = False  # Can you stay indoors?
    notes: Optional[str] = None


@dataclass
class StudentScheduleLocation:
    """A location in a student's schedule."""
    course_code: str
    crn: str
    building: str
    room: str
    campus: str
    days: str
    start_time: str
    end_time: str

    def conflicts_with(self, other: "StudentScheduleLocation", min_travel_minutes: int = 10) -> bool:
        """Check if this conflicts with another location (not enough travel time)."""
        if self.days != other.days:
            # TODO: Check for overlapping days
            return False

        # TODO: Parse times and check for conflicts
        return False


class CampusGraph:
    """
    Knowledge graph of UGA campus for schedule optimization.

    Provides:
    - Building lookup and metadata
    - Walking time calculations
    - Schedule conflict detection
    - Daily route optimization
    - Parking recommendations
    - Bus route integration
    """

    def __init__(self):
        self.campuses: dict[str, Campus] = {}
        self.buildings: dict[str, Building] = {}
        self.walking_paths: list[WalkingPath] = []
        self.parking: dict[str, ParkingLocation] = {}
        self.bus_stops: dict[str, BusStop] = {}
        self.bus_routes: dict[str, BusRoute] = {}

    def add_building(self, building: Building):
        """Add a building to the graph."""
        self.buildings[building.id] = building

    def get_building(self, name: str) -> Optional[Building]:
        """Get building by name or ID."""
        # Try exact match
        if name in self.buildings:
            return self.buildings[name]

        # Try case-insensitive search
        name_lower = name.lower()
        for bldg_id, bldg in self.buildings.items():
            if bldg.name.lower() == name_lower or bldg_id.lower() == name_lower:
                return bldg
            if bldg.short_name and bldg.short_name.lower() == name_lower:
                return bldg

        return None

    def walking_time(self, from_building: str, to_building: str) -> Optional[int]:
        """Get walking time between two buildings in minutes."""
        bldg1 = self.get_building(from_building)
        bldg2 = self.get_building(to_building)

        if not bldg1 or not bldg2:
            return None

        # Check for pre-computed path
        for path in self.walking_paths:
            if (path.from_building == from_building and path.to_building == to_building) or \
               (path.from_building == to_building and path.to_building == from_building):
                return path.estimated_minutes

        # Calculate from coordinates
        return bldg1.walking_time_to(bldg2)

    def find_schedule_conflicts(
        self,
        locations: list[StudentScheduleLocation],
        min_travel_minutes: int = 10
    ) -> list[tuple[StudentScheduleLocation, StudentScheduleLocation, int]]:
        """
        Find back-to-back classes that may have travel time issues.

        Returns list of (location1, location2, travel_time_needed) tuples.
        """
        conflicts = []

        # Sort by day and time
        # TODO: Implement proper time parsing

        for i, loc1 in enumerate(locations):
            for loc2 in locations[i+1:]:
                # Check if same day and consecutive
                if loc1.building != loc2.building:
                    travel_time = self.walking_time(loc1.building, loc2.building)
                    if travel_time and travel_time > min_travel_minutes:
                        conflicts.append((loc1, loc2, travel_time))

        return conflicts

    def optimize_daily_route(
        self,
        locations: list[StudentScheduleLocation]
    ) -> list[StudentScheduleLocation]:
        """
        Suggest optimal ordering of classes to minimize walking.
        (For when students have flexibility in section choice)
        """
        # TODO: Implement TSP-style optimization
        return locations

    def get_buildings_by_zone(self, zone: CampusZone) -> list[Building]:
        """Get all buildings in a campus zone."""
        return [b for b in self.buildings.values() if b.zone == zone]

    def add_parking(self, parking: ParkingLocation):
        """Add a parking location to the graph."""
        self.parking[parking.id] = parking

    def add_bus_stop(self, stop: BusStop):
        """Add a bus stop to the graph."""
        self.bus_stops[stop.id] = stop

    def add_bus_route(self, route: BusRoute):
        """Add a bus route to the graph."""
        self.bus_routes[route.id] = route

    def find_nearest_parking(
        self,
        building_name: str,
        permit_type: Optional[str] = None,
        max_results: int = 3
    ) -> list[tuple[ParkingLocation, int]]:
        """
        Find nearest parking to a building.

        Args:
            building_name: Building to park near
            permit_type: Filter by permit type (C, E, R, etc.)
            max_results: Maximum results to return

        Returns:
            List of (ParkingLocation, walking_minutes) tuples
        """
        building = self.get_building(building_name)
        if not building:
            return []

        results = []
        for parking in self.parking.values():
            if permit_type and parking.permit_required and permit_type not in parking.permit_required:
                continue

            walk_time = parking.walking_time_to(building)
            if walk_time:
                results.append((parking, walk_time))

        results.sort(key=lambda x: x[1])
        return results[:max_results]

    def find_bus_options(
        self,
        from_building: str,
        to_building: str,
        max_walk_to_stop: int = 5
    ) -> list[dict]:
        """
        Find bus options between two buildings.

        Args:
            from_building: Starting building
            to_building: Destination building
            max_walk_to_stop: Max walking minutes to consider a stop

        Returns:
            List of route options with stops and estimated times
        """
        from_bldg = self.get_building(from_building)
        to_bldg = self.get_building(to_building)

        if not from_bldg or not to_bldg:
            return []

        options = []

        # Find stops near origin
        origin_stops = []
        for stop in self.bus_stops.values():
            if stop.location and from_bldg.location:
                dist = from_bldg.location.distance_to(stop.location)
                walk_time = int(dist * 1.2 / 1.4 / 60) + 1
                if walk_time <= max_walk_to_stop:
                    origin_stops.append((stop, walk_time))

        # Find stops near destination
        dest_stops = []
        for stop in self.bus_stops.values():
            if stop.location and to_bldg.location:
                dist = to_bldg.location.distance_to(stop.location)
                walk_time = int(dist * 1.2 / 1.4 / 60) + 1
                if walk_time <= max_walk_to_stop:
                    dest_stops.append((stop, walk_time))

        # Find routes that connect origin stops to destination stops
        for origin_stop, walk_to in origin_stops:
            for dest_stop, walk_from in dest_stops:
                # Find common routes
                common_routes = set(origin_stop.routes) & set(dest_stop.routes)
                for route_id in common_routes:
                    route = self.bus_routes.get(route_id)
                    if route:
                        options.append({
                            "route": route,
                            "board_at": origin_stop,
                            "exit_at": dest_stop,
                            "walk_to_stop": walk_to,
                            "walk_from_stop": walk_from,
                            "estimated_total": walk_to + walk_from + (route.frequency_minutes or 10)
                        })

        return sorted(options, key=lambda x: x["estimated_total"])

    def to_jsonld(self) -> dict:
        """Export graph as JSON-LD for semantic web compatibility."""
        return {
            "@context": {
                "@vocab": "https://schema.org/",
                "uga": "https://uga.edu/ontology/",
                "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
            },
            "@type": "uga:CampusGraph",
            "campuses": [
                {
                    "@type": "uga:Campus",
                    "name": campus.name,
                    "buildings": [
                        {
                            "@type": "uga:Building",
                            "name": bldg.name,
                            "geo:lat": bldg.location.latitude if bldg.location else None,
                            "geo:long": bldg.location.longitude if bldg.location else None,
                        }
                        for bldg in campus.buildings
                    ]
                }
                for campus in self.campuses.values()
            ]
        }


# Athens campus building coordinates from OpenStreetMap
# Comprehensive list for walking time calculations
ATHENS_BUILDING_COORDS = {
    # Major Academic Buildings
    "Aderhold Hall": (33.9418, -83.3730),
    "Baldwin Hall": (33.9537, -83.3722),
    "Park Hall": (33.9533, -83.3752),
    "Zell B Miller Learning Center": (33.9517, -83.3758),
    "Science Learning Center": (33.9427, -83.3763),
    "Journalism": (33.9522, -83.3740),
    "Journalism Building": (33.9522, -83.3740),
    "Driftmier Eng Ctr": (33.9388, -83.3750),
    "Driftmier Engineering Center": (33.9388, -83.3750),
    "Geography Geology": (33.9487, -83.3754),
    "Geography and Geology Building": (33.9487, -83.3754),
    "Caldwell Hall": (33.9549, -83.3753),
    "Conner Hall": (33.9475, -83.3738),
    "Correll Hall": (33.9528, -83.3774),

    # Cedar Street Buildings
    "Cedar Street Building A": (33.9468, -83.3726),
    "Cedar Street Building B": (33.9480, -83.3727),
    "Cedar Street Building C": (33.9485, -83.3741),
    "Cedar Street Building D": (33.9482, -83.3748),

    # Arts & Music
    "Main Art Building": (33.9404, -83.3691),
    "Lamar Dodd School of Art": (33.9404, -83.3691),
    "Fine Arts Building": (33.9525, -83.3759),
    "Fine Arts": (33.9525, -83.3759),
    "Music Building": (33.9413, -83.3687),
    "Hugh Hodgson School of Music": (33.9413, -83.3687),
    "Perfoming Arts Center": (33.9420, -83.3696),

    # Sciences
    "Chemistry Storage Building": (33.9486, -83.3734),
    "Physics Building": (33.9481, -83.3761),
    "Physics": (33.9481, -83.3761),
    "Psychology Building": (33.9525, -83.3729),
    "Psychology": (33.9525, -83.3729),
    "Ecology": (33.9443, -83.3733),
    "Ecology Annex": (33.9461, -83.3738),
    "Life Sci F.Davison": (33.9432, -83.3724),
    "Fred C. Davison Life Sciences Complex": (33.9432, -83.3724),
    "Miller Plant Sci": (33.9424, -83.3751),
    "Miller Plant Science": (33.9424, -83.3751),

    # Health & Pharmacy
    "Pharmacy South": (33.9434, -83.3759),
    "Robt C Wilson Phar": (33.9442, -83.3754),
    "Wilson Pharmacy Building": (33.9442, -83.3754),
    "College of Veterinary Medicine": (33.9408, -83.3749),
    "University Health Center": (33.9359, -83.3722),

    # Humanities & Social Sciences
    "Peabody Hall": (33.9549, -83.3735),
    "LeConte Hall": (33.9534, -83.3734),
    "Leconte Hall": (33.9534, -83.3734),
    "Dawson Hall": (33.9471, -83.3757),
    "Gilbert Hall": (33.9555, -83.3761),
    "Sanford Hall": (33.9537, -83.3750),
    "Brooks Hall": (33.9542, -83.3752),
    "Denmark Hall": (33.9547, -83.3756),
    "Candler Hall": (33.9561, -83.3761),
    "Moore Hall": (33.9565, -83.3758),
    "Meigs Hall": (33.9566, -83.3763),
    "Holmes-Hunter Academic Building": (33.9572, -83.3754),
    "Joseph E. Brown Hall": (33.9533, -83.3760),
    "Joe Brown": (33.9533, -83.3760),

    # Law & Business
    "Hirsch Hall": (33.9547, -83.3745),
    "Alexander Campbell King Law Library": (33.9550, -83.3748),
    "Law School": (33.9547, -83.3745),

    # Engineering & Agriculture
    "Forest Resources-1": (33.9441, -83.3747),
    "Forest Resources 1": (33.9441, -83.3747),
    "Poultry Science Building": (33.9467, -83.3745),
    "Food Science Building": (33.9461, -83.3722),

    # Student Services & Libraries
    "Tate Student Center": (33.9505, -83.3753),
    "UGA Main Library": (33.9540, -83.3737),
    "Richard B. Russell Special Collections Library": (33.9540, -83.3782),
    "Shirley Mathis McBay Science Library": (33.9460, -83.3753),
    "University of Georgia Bookstore": (33.9515, -83.3748),

    # Residence & Dining
    "Brumby Hall": (33.9497, -83.3829),
    "Creswell Hall": (33.9500, -83.3800),
    "Russell Hall": (33.9500, -83.3815),
    "Bolton Dining Commons": (33.9510, -83.3775),
    "Snelling Dining Commons": (33.9447, -83.3764),
    "Oglethorpe Dining Commons": (33.9471, -83.3795),

    # Athletics
    "Ramsey Center": (33.9378, -83.3714),
    "Ramsey Stu Ctr Pa": (33.9378, -83.3714),
    "Stegeman Coliseum": (33.9428, -83.3781),
    "Butts-Mehre Heritage Hall": (33.9421, -83.3813),

    # Historic & Administrative
    "Old College": (33.9558, -83.3745),
    "New College": (33.9562, -83.3749),
    "UGA Chapel": (33.9567, -83.3752),
    "Memorial Hall": (33.9513, -83.3736),
    "Demosthenian Hall": (33.9569, -83.3752),
    "Phi Kappa Hall": (33.9571, -83.3742),

    # Other Academic
    "Barrow Hall": (33.9465, -83.3736),
    "Amos Hall": (33.9523, -83.3774),
    "Boyd Graduate Research Center": (33.9460, -83.3751),
    "Boyd Research & Education CTR": (33.9460, -83.3751),
    "Marine Science Building": (33.9453, -83.3761),
    "Environmental Health Sciences": (33.9434, -83.3748),
    "Soule Hall": (33.9462, -83.3760),
    "Hardman Hall": (33.9451, -83.3742),
    "Tucker Hall": (33.9427, -83.3711),
    "Payne Hall": (33.9517, -83.3719),
    "Reed Hall": (33.9510, -83.3727),
    "Milledge Hall": (33.9516, -83.3723),
    "Instructional Plaza": (33.9524, -83.3735),

    # Gwinnett Campus
    "Uga Gwinnett": (33.9700, -84.0100),  # Approximate - different city
}

# UGA Parking Decks and Lots from OpenStreetMap
UGA_PARKING = {
    # Parking Decks
    "Carlton Street Deck": {
        "coords": (33.9412, -83.3780),
        "type": "deck",
        "permit": "C,E",
        "nearby": ["Stegeman Coliseum", "Driftmier Engineering Center"]
    },
    "North Campus Parking Deck": {
        "coords": (33.9562, -83.3726),
        "type": "deck",
        "permit": "C,E,V",
        "nearby": ["UGA Main Library", "Park Hall", "Old College"]
    },
    "Hull Street Parking Deck": {
        "coords": (33.9530, -83.3788),
        "type": "deck",
        "permit": "C,E",
        "nearby": ["Journalism", "Correll Hall", "Tate Student Center"]
    },
    "East Campus Parking Deck": {
        "coords": (33.9381, -83.3693),
        "type": "deck",
        "permit": "C,E",
        "nearby": ["Georgia Museum of Art", "Hugh Hodgson School of Music"]
    },
    "East Campus Village Deck": {
        "coords": (33.9384, -83.3663),
        "type": "deck",
        "permit": "R",
        "nearby": ["East Campus Residence Halls"]
    },
    "South Campus Parking Deck": {
        "coords": (33.9455, -83.3775),
        "type": "deck",
        "permit": "C,E",
        "nearby": ["Science Learning Center", "Chemistry", "Boyd Graduate Research Center"]
    },
    "Intramural Field Parking Deck": {
        "coords": (33.9325, -83.3723),
        "type": "deck",
        "permit": "C,E",
        "nearby": ["Ramsey Center", "Intramural Fields"]
    },
    "West Campus Deck": {
        "coords": (33.9488, -83.3818),
        "type": "deck",
        "permit": "R",
        "nearby": ["Brumby Hall", "Russell Hall", "Creswell Hall"]
    },
    "West Campus Deck II": {
        "coords": (33.9484, -83.3827),
        "type": "deck",
        "permit": "R",
        "nearby": ["Brumby Hall", "Russell Hall"]
    },
    "Tate Center Parking Deck": {
        "coords": (33.9506, -83.3763),
        "type": "deck",
        "permit": "V",
        "hourly_rate": 2.00,
        "nearby": ["Tate Student Center", "Journalism", "Memorial Hall"]
    },
    "Clarke County Courthouse Parking Deck": {
        "coords": (33.9602, -83.3739),
        "type": "deck",
        "permit": "V",
        "hourly_rate": 1.50,
        "nearby": ["Downtown", "Holmes-Hunter Academic Building"]
    },
    "East Broad Street Parking Deck": {
        "coords": (33.9596, -83.3713),
        "type": "deck",
        "permit": "V",
        "nearby": ["Downtown", "North Campus"]
    },
    "Performing Arts Center Deck": {
        "coords": (33.9422, -83.3701),
        "type": "deck",
        "permit": "C,E,V",
        "nearby": ["Performing Arts Center", "Georgia Museum of Art"]
    },
}

# UGA Campus Transit Routes
UGA_BUS_ROUTES = {
    "east_west": {
        "name": "East-West Route",
        "short_name": "East-West",
        "operator": "UGA Campus Transit",
        "frequency": 10,
        "hours": ("7:00 am", "6:00 pm"),
        "days": "MTWRF",
        "color": "#CC0000",
        "major_stops": ["Tate Center", "Science Library", "Ramsey Center", "East Campus"]
    },
    "orbit": {
        "name": "Orbit Route",
        "short_name": "Orbit",
        "operator": "UGA Campus Transit",
        "frequency": 12,
        "hours": ("7:30 am", "6:00 pm"),
        "days": "MTWRF",
        "color": "#003399",
        "major_stops": ["Bolton Dining", "Brumby Hall", "Tate Center", "South Campus"]
    },
    "ag_hill": {
        "name": "Ag Hill Route",
        "short_name": "Ag Hill",
        "operator": "UGA Campus Transit",
        "frequency": 15,
        "hours": ("7:30 am", "5:30 pm"),
        "days": "MTWRF",
        "color": "#006600",
        "major_stops": ["Tate Center", "Conner Hall", "Poultry Science", "Four Towers"]
    },
    "vet_med": {
        "name": "Vet Med Route",
        "short_name": "Vet Med",
        "operator": "UGA Campus Transit",
        "frequency": 20,
        "hours": ("7:30 am", "5:30 pm"),
        "days": "MTWRF",
        "color": "#9933CC",
        "major_stops": ["Tate Center", "Vet Med", "Coverdell Center"]
    },
    "milledge": {
        "name": "Milledge Avenue Route",
        "short_name": "Milledge",
        "operator": "UGA Campus Transit",
        "frequency": 15,
        "hours": ("7:00 am", "10:00 pm"),
        "days": "MTWRF",
        "color": "#FF6600",
        "major_stops": ["Tate Center", "Five Points", "Milledge Ave"]
    },
    "night_campus": {
        "name": "Night Campus Route",
        "short_name": "Night Campus",
        "operator": "UGA Campus Transit",
        "frequency": 20,
        "hours": ("6:00 pm", "12:00 am"),
        "days": "MTWRFSU",
        "color": "#333333",
        "major_stops": ["Tate Center", "Main Library", "Brumby Hall", "East Campus"]
    },
}


def build_campus_graph_from_schedule(buildings_json: dict) -> CampusGraph:
    """Build a CampusGraph from the scanned building data."""
    graph = CampusGraph()

    for bldg_name, data in buildings_json.items():
        # Skip placeholder buildings
        if bldg_name in ("TBA", "No Classroom Required"):
            continue

        # Get coordinates if known
        coords = ATHENS_BUILDING_COORDS.get(bldg_name)
        location = GeoLocation(coords[0], coords[1]) if coords else None

        # Determine zone based on building (simplified)
        zone = None
        if any(name in bldg_name.lower() for name in ["science", "chemistry", "physics", "biology"]):
            zone = CampusZone.SOUTH
        elif any(name in bldg_name.lower() for name in ["art", "music", "main"]):
            zone = CampusZone.NORTH
        elif any(name in bldg_name.lower() for name in ["health", "pharmacy", "nursing"]):
            zone = CampusZone.HEALTH_SCIENCES

        building = Building(
            id=bldg_name.lower().replace(" ", "_"),
            name=bldg_name,
            campus=data["campuses"][0] if data["campuses"] else "Athens",
            zone=zone,
            location=location,
            total_sections=data["total_sections"],
            total_courses=data["courses_offered"],
            rooms=[Room(number=r, building_id=bldg_name) for r in data["rooms"]]
        )

        graph.add_building(building)

    # Add parking locations
    for parking_id, pdata in UGA_PARKING.items():
        coords = pdata.get("coords")
        parking = ParkingLocation(
            id=parking_id.lower().replace(" ", "_"),
            name=parking_id,
            location=GeoLocation(coords[0], coords[1]) if coords else None,
            parking_type=pdata.get("type", "deck"),
            permit_required=pdata.get("permit"),
            hourly_rate=pdata.get("hourly_rate"),
            nearby_buildings=pdata.get("nearby", [])
        )
        graph.add_parking(parking)

    # Add bus routes
    for route_id, rdata in UGA_BUS_ROUTES.items():
        route = BusRoute(
            id=route_id,
            name=rdata["name"],
            short_name=rdata["short_name"],
            operator=rdata.get("operator", "UGA Campus Transit"),
            frequency_minutes=rdata.get("frequency"),
            first_departure=rdata["hours"][0] if "hours" in rdata else None,
            last_departure=rdata["hours"][1] if "hours" in rdata else None,
            days_of_operation=rdata.get("days", "MTWRF"),
            color=rdata.get("color")
        )
        graph.add_bus_route(route)

    return graph
