"""
database.py

SQLite data access layer:
- manage resource categories (resource_categories)
- manage individual resource records (resources)
- provide small helper functions for teaching structured storage concepts.
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

DB_NAME = "resources.db"


def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the SQLite database.
    """
    return sqlite3.connect(DB_NAME)


def create_tables() -> None:
    """
    Create the resource_categories and resources tables if they do not exist.
    Existing data is preserved between runs.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Category table: stores the resource taxonomy
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS resource_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT UNIQUE NOT NULL
            );
            """
        )

        # Resource table: stores each individual need/offer record
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent TEXT,
                user_type TEXT,
                resource_description TEXT,
                quantity TEXT,
                time_text TEXT,
                location_text TEXT,
                resource_category TEXT,
                latitude REAL,
                longitude REAL,
                original_text TEXT,
                status TEXT,                     -- available / matched / expired
                provider_start_time_utc TEXT,
                provider_end_time_utc TEXT,
                seeker_start_time_utc TEXT,
                seeker_end_time_utc TEXT,
                expiry_time_utc TEXT
            );
            """
        )

        conn.commit()


def seed_default_categories() -> None:
    """
    Seed a small set of default resource categories (taxonomy), inserting only when missing.
    """
    default_categories = [
        "equipment",
        "space",
        "storage",
        "event_support",
        "transportation",
        "materials",
        "food_support",
        "childcare",
        "volunteer_help",
        "other",
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        for resource_type in default_categories:
            cursor.execute(
                """
                INSERT OR IGNORE INTO resource_categories (resource_type)
                VALUES (?)
                """,
                (resource_type,),
            )
        conn.commit()


def get_all_categories() -> List[str]:
    """
    Return a list of all resource category names currently in the database.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT resource_type FROM resource_categories ORDER BY resource_type;")
        rows = cursor.fetchall()

    return [row[0] for row in rows]


def insert_category_if_not_exists(resource_type: str) -> None:
    """
    Insert a new category record if the given category name does not already exist.
    """
    if not resource_type:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO resource_categories (resource_type)
            VALUES (?)
            """,
            (resource_type,),
        )
        conn.commit()


def insert_resource(resource: Dict[str, Any]) -> int:
    """
    Insert one resource record into the resources table and return the inserted row id.

    Expected keys include:
      intent, user_type, resource_description, quantity,
      time_text, location_text, resource_category,
      latitude, longitude, original_text,
      status, provider_start_time_utc, provider_end_time_utc,
      seeker_start_time_utc, seeker_end_time_utc, expiry_time_utc
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO resources (
                intent,
                user_type,
                resource_description,
                quantity,
                time_text,
                location_text,
                resource_category,
                latitude,
                longitude,
                original_text,
                status,
                provider_start_time_utc,
                provider_end_time_utc,
                seeker_start_time_utc,
                seeker_end_time_utc,
                expiry_time_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resource.get("intent"),
                resource.get("user_type"),
                resource.get("resource_description"),
                resource.get("quantity"),
                resource.get("time_text"),
                resource.get("location_text"),
                resource.get("resource_category"),
                resource.get("latitude"),
                resource.get("longitude"),
                resource.get("original_text"),
                resource.get("status", "available"),
                resource.get("provider_start_time_utc"),
                resource.get("provider_end_time_utc"),
                resource.get("seeker_start_time_utc"),
                resource.get("seeker_end_time_utc"),
                resource.get("expiry_time_utc"),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_resources_row_count() -> int:
    """Return the number of rows in the resources table (used to decide whether to seed fake data)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM resources;")
        return cursor.fetchone()[0]


def fetch_all_providers() -> List[Dict[str, Any]]:
    """
    Fetch all provider records (user_type == provider or intent == offer).
    Returns a list of dictionaries used later for semantic matching.
    """
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Before each fetch, update expired status based on expiry_time_utc
        cursor.execute(
            """
            UPDATE resources
            SET status = 'expired'
            WHERE expiry_time_utc IS NOT NULL
              AND status IS NOT 'expired'
              AND datetime(expiry_time_utc) < datetime('now');
            """
        )

        cursor.execute(
            """
            SELECT
                id,
                intent,
                user_type,
                resource_description,
                quantity,
                time_text,
                location_text,
                resource_category,
                latitude,
                longitude,
                original_text,
                status,
                provider_start_time_utc,
                provider_end_time_utc,
                seeker_start_time_utc,
                seeker_end_time_utc,
                expiry_time_utc
            FROM resources
            WHERE (user_type = 'provider' OR intent = 'offer')
              AND (status IS NULL OR status = 'available')
            """
        )
        rows = cursor.fetchall()

    providers: List[Dict[str, Any]] = []
    for row in rows:
        providers.append(
            {
                "id": row["id"],
                "intent": row["intent"],
                "user_type": row["user_type"],
                "resource_description": row["resource_description"],
                "quantity": row["quantity"],
                "time_text": row["time_text"],
                "location_text": row["location_text"],
                "resource_category": row["resource_category"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "original_text": row["original_text"],
                "status": row["status"],
                "provider_start_time_utc": row["provider_start_time_utc"],
                "provider_end_time_utc": row["provider_end_time_utc"],
                "seeker_start_time_utc": row["seeker_start_time_utc"],
                "seeker_end_time_utc": row["seeker_end_time_utc"],
                "expiry_time_utc": row["expiry_time_utc"],
            }
        )

    return providers


def seed_fake_provider_records() -> None:
    """
    Seed a few fake provider ("offer") records into the resources table.
    These are used to demonstrate matching behavior in class.
    """
    fake_providers = [
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Community center offering 8 folding tables for neighborhood events",
            "quantity": "8 tables",
            "time_text": "next two weeks",
            "location_text": "near downtown Ann Arbor main plaza",
            "resource_category": "equipment",
            "latitude": 42.2805,
            "longitude": -83.7440,
            "original_text": (
                "We are a local community center in downtown Ann Arbor. "
                "We can offer 8 folding tables for neighborhood events "
                "near the main plaza in the next two weeks."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Small warehouse providing temporary storage space for community groups",
            "quantity": "space for ~20 large boxes",
            "time_text": "over the next month",
            "location_text": "east side of Ann Arbor near US-23",
            "resource_category": "storage",
            "latitude": 42.2730,
            "longitude": -83.7070,
            "original_text": (
                "Our small warehouse on the east side of Ann Arbor can provide temporary "
                "storage space for around 20 large boxes for community groups over the next month."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Resident group lending around 40 folding chairs",
            "quantity": "40 chairs",
            "time_text": "weekends",
            "location_text": "near the central library in Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2790,
            "longitude": -83.7390,
            "original_text": (
                "A resident group close to the Ann Arbor central library can lend "
                "around 40 folding chairs for weekend community activities."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Community group offering folding tables and chairs near the central library",
            "quantity": "4 folding tables and 30 chairs",
            "time_text": "Saturday afternoons",
            "location_text": "right next to the central library in Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2792,
            "longitude": -83.7388,
            "original_text": (
                "A small community group right next to the Ann Arbor central library "
                "can offer 4 folding tables and about 30 chairs for weekend workshops."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Church hall lending folding tables and chairs for community events",
            "quantity": "6 tables and 50 chairs",
            "time_text": "weekends",
            "location_text": "near Washtenaw and Stadium, Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2720,
            "longitude": -83.7350,
            "original_text": (
                "Our church hall near Washtenaw and Stadium can lend 6 folding tables and 50 chairs "
                "for community events on weekends."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "School PTA offering portable whiteboards and folding tables for workshops",
            "quantity": "4 whiteboards and 5 tables",
            "time_text": "after school hours on weekdays",
            "location_text": "near Burns Park Elementary area",
            "resource_category": "equipment",
            "latitude": 42.2670,
            "longitude": -83.7280,
            "original_text": (
                "The PTA near Burns Park Elementary can offer 4 portable whiteboards and 5 folding tables "
                "for community workshops after school on weekdays."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Neighborhood association lending chairs and small tables for block parties",
            "quantity": "30 chairs and 4 tables",
            "time_text": "summer weekends",
            "location_text": "near Lawton area, Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2760,
            "longitude": -83.7520,
            "original_text": (
                "Our neighborhood association in the Lawton area can lend 30 chairs and 4 small tables "
                "for block parties on summer weekends."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Community center offering tables, chairs, and basic A/V equipment",
            "quantity": "10 tables, 60 chairs, 1 projector",
            "time_text": "weekday evenings and Saturdays",
            "location_text": "downtown Ann Arbor near Liberty Street",
            "resource_category": "equipment",
            "latitude": 42.2795,
            "longitude": -83.7460,
            "original_text": (
                "A community center near Liberty Street in downtown Ann Arbor can offer 10 tables, 60 chairs, "
                "and a projector for events on weekday evenings and Saturdays."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Campus org lending folding chairs and tables for student events",
            "quantity": "20 chairs and 3 tables",
            "time_text": "during term time",
            "location_text": "University of Michigan Central Campus",
            "resource_category": "equipment",
            "latitude": 42.2785,
            "longitude": -83.7385,
            "original_text": (
                "A campus organization on Central Campus can lend 20 folding chairs and 3 tables "
                "for student-led community events during term time."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Student group providing volunteers to help set up and clean up events",
            "quantity": "6 volunteers",
            "time_text": "Saturday mornings",
            "location_text": "near North Campus, Ann Arbor",
            "resource_category": "volunteer_help",
            "latitude": 42.2935,
            "longitude": -83.7160,
            "original_text": (
                "Our student group on North Campus can provide about 6 volunteers "
                "to help set up and clean up small community events on Saturday mornings."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Local restaurant offering leftover food trays for community gatherings",
            "quantity": "food for ~30 people",
            "time_text": "weekday evenings",
            "location_text": "near State Street, Ann Arbor",
            "resource_category": "food_support",
            "latitude": 42.2775,
            "longitude": -83.7415,
            "original_text": (
                "A small restaurant near State Street can donate leftover food trays "
                "on weekday evenings to support community gatherings."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Community member offering car rides to elders for appointments",
            "quantity": "rides for 3 people per week",
            "time_text": "weekday afternoons",
            "location_text": "west side of Ann Arbor",
            "resource_category": "transportation",
            "latitude": 42.2800,
            "longitude": -83.7640,
            "original_text": (
                "A community member on the west side of Ann Arbor can offer rides "
                "to about 3 elders per week for medical or community appointments "
                "on weekday afternoons."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Makerspace offering tools and materials for small repair events",
            "quantity": "basic tools and supplies",
            "time_text": "first Sunday of each month",
            "location_text": "near downtown Ann Arbor",
            "resource_category": "materials",
            "latitude": 42.2810,
            "longitude": -83.7485,
            "original_text": (
                "A neighborhood makerspace near downtown Ann Arbor can offer tools "
                "and basic materials for small community repair events on the first Sunday of each month."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Parent group offering childcare during evening workshops",
            "quantity": "childcare for up to 10 kids",
            "time_text": "Tuesday and Thursday evenings",
            "location_text": "near Burns Park area",
            "resource_category": "childcare",
            "latitude": 42.2685,
            "longitude": -83.7260,
            "original_text": (
                "A parent group near Burns Park can provide informal childcare "
                "for up to 10 kids during community workshops on Tuesday and Thursday evenings."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Local business lending portable sound system for events",
            "quantity": "one portable sound system",
            "time_text": "weekends",
            "location_text": "near Kerrytown, Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2855,
            "longitude": -83.7470,
            "original_text": (
                "A local business near Kerrytown can lend a portable sound system "
                "for small outdoor or indoor community events on weekends."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Neighborhood association offering meeting room with projector",
            "quantity": "room for 20 people",
            "time_text": "weekday evenings",
            "location_text": "near Packard Street, Ann Arbor",
            "resource_category": "space",
            "latitude": 42.2655,
            "longitude": -83.7320,
            "original_text": (
                "A neighborhood association near Packard Street can offer a small meeting room "
                "with a projector for up to 20 people on weekday evenings."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Community garden sharing tools and compost for neighborhood projects",
            "quantity": "shared tools and compost",
            "time_text": "most weekends",
            "location_text": "near Allen Creek",
            "resource_category": "materials",
            "latitude": 42.2818,
            "longitude": -83.7610,
            "original_text": (
                "A community garden near Allen Creek can share gardening tools and compost "
                "for neighborhood greening projects on most weekends."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Campus group lending folding tables and display boards",
            "quantity": "5 tables and 6 display boards",
            "time_text": "during exam-free weeks",
            "location_text": "central campus of University of Michigan",
            "resource_category": "equipment",
            "latitude": 42.2780,
            "longitude": -83.7380,
            "original_text": (
                "A campus organization on central campus can lend 5 folding tables "
                "and 6 display boards for community info fairs during exam-free weeks."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Community kitchen offering access to ovens and counter space",
            "quantity": "shared kitchen access",
            "time_text": "Sunday afternoons",
            "location_text": "near South University Avenue",
            "resource_category": "space",
            "latitude": 42.2738,
            "longitude": -83.7345,
            "original_text": (
                "A small community kitchen near South University Avenue "
                "can share ovens and counter space for neighborhood cooking events on Sunday afternoons."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Local nonprofit lending laptops for digital literacy workshops",
            "quantity": "10 laptops",
            "time_text": "weekday mornings",
            "location_text": "downtown Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2809,
            "longitude": -83.7483,
            "original_text": (
                "A local nonprofit in downtown Ann Arbor can lend 10 laptops "
                "for small digital literacy workshops on weekday mornings."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Neighborhood hub offering bulletin board and flyer printing help",
            "quantity": "printing support and bulletin board space",
            "time_text": "business hours",
            "location_text": "near Main Street, Ann Arbor",
            "resource_category": "event_support",
            "latitude": 42.2815,
            "longitude": -83.7488,
            "original_text": (
                "A neighborhood hub near Main Street can help print flyers and provide "
                "bulletin board space for promoting community events during business hours."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Faith community lending chairs and tables for neighborhood use",
            "quantity": "60 chairs and 10 tables",
            "time_text": "most weekends",
            "location_text": "near Washtenaw Avenue",
            "resource_category": "equipment",
            "latitude": 42.2705,
            "longitude": -83.7225,
            "original_text": (
                "A faith community near Washtenaw Avenue can lend about 60 chairs "
                "and 10 tables for neighborhood events on most weekends."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "offer",
            "user_type": "provider",
            "resource_description": "Multi-purpose community room for small workshops and meetings",
            "quantity": "space for ~25 people",
            "time_text": "weekday evenings",
            "location_text": "near City Hall, downtown Ann Arbor",
            "resource_category": "space",
            "latitude": 42.2808,
            "longitude": -83.7480,
            "original_text": (
                "We manage a multi-purpose community room near Ann Arbor City Hall "
                "that can host small workshops and meetings in the evenings."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        for r in fake_providers:
            cursor.execute(
                """
                INSERT INTO resources (
                    intent,
                    user_type,
                    resource_description,
                    quantity,
                    time_text,
                    location_text,
                    resource_category,
                    latitude,
                    longitude,
                    original_text,
                    status,
                    provider_start_time_utc,
                    provider_end_time_utc,
                    seeker_start_time_utc,
                    seeker_end_time_utc,
                    expiry_time_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["intent"],
                    r["user_type"],
                    r["resource_description"],
                    r["quantity"],
                    r["time_text"],
                    r["location_text"],
                    r["resource_category"],
                    r["latitude"],
                    r["longitude"],
                    r["original_text"],
                    r["status"],
                    r["provider_start_time_utc"],
                    r["provider_end_time_utc"],
                    r["seeker_start_time_utc"],
                    r["seeker_end_time_utc"],
                    r["expiry_time_utc"],
                ),
            )
        conn.commit()


def seed_fake_seeker_records() -> None:
    """
    Seed a few fake seeker ("need") records to demonstrate that the database
    can store both offers and needs in the same schema.
    These records are not used for provider matching (fetch_all_providers filters them out).
    """
    fake_seekers = [
        {
            "intent": "need",
            "user_type": "seeker",
            "resource_description": "Small community workshop needing folding tables and chairs",
            "quantity": "3 folding tables and 25 chairs",
            "time_text": "this Saturday afternoon",
            "location_text": "near the central library in Ann Arbor",
            "resource_category": "equipment",
            "latitude": 42.2791,
            "longitude": -83.7389,
            "original_text": (
                "We are organizing a small community workshop this Saturday afternoon "
                "and need around 3 folding tables and 25 chairs near the central library in Ann Arbor."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "need",
            "user_type": "seeker",
            "resource_description": "Neighborhood group seeking temporary storage for event materials",
            "quantity": "space for 15 boxes",
            "time_text": "for the next two weeks",
            "location_text": "near downtown Ann Arbor",
            "resource_category": "storage",
            "latitude": 42.2803,
            "longitude": -83.7450,
            "original_text": (
                "A neighborhood group near downtown Ann Arbor is looking for temporary storage "
                "for about 15 boxes of event materials for the next two weeks."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
        {
            "intent": "need",
            "user_type": "seeker",
            "resource_description": "Resident organizing a movie night needing a community room",
            "quantity": "space for ~20 people",
            "time_text": "one Friday evening next month",
            "location_text": "anywhere close to central campus",
            "resource_category": "space",
            "latitude": 42.2785,
            "longitude": -83.7395,
            "original_text": (
                "A resident is organizing a small movie night and needs a community room "
                "for around 20 people on a Friday evening next month near central campus."
            ),
            "status": "available",
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
        },
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        for r in fake_seekers:
            cursor.execute(
                """
                INSERT INTO resources (
                    intent,
                    user_type,
                    resource_description,
                    quantity,
                    time_text,
                    location_text,
                    resource_category,
                    latitude,
                    longitude,
                    original_text,
                    status,
                    provider_start_time_utc,
                    provider_end_time_utc,
                    seeker_start_time_utc,
                    seeker_end_time_utc,
                    expiry_time_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["intent"],
                    r["user_type"],
                    r["resource_description"],
                    r["quantity"],
                    r["time_text"],
                    r["location_text"],
                    r["resource_category"],
                    r["latitude"],
                    r["longitude"],
                    r["original_text"],
                    r["status"],
                    r["provider_start_time_utc"],
                    r["provider_end_time_utc"],
                    r["seeker_start_time_utc"],
                    r["seeker_end_time_utc"],
                    r["expiry_time_utc"],
                ),
            )
        conn.commit()

def update_resource_status(resource_id: int, status: str) -> bool:
    """
    Update the status of a resource record by id (available / matched / expired).
    Returns True if at least one row was updated.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE resources SET status = ? WHERE id = ?;",
            (status, resource_id),
        )
        conn.commit()
        return cursor.rowcount > 0

