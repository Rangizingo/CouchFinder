"""
CouchFinder Database Module
SQLite operations for tracking seen listings.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Set, List
from dataclasses import dataclass

from config import DATABASE_FILE


@dataclass
class Listing:
    """Represents a marketplace listing."""
    id: str
    platform: str
    title: str
    price: str
    url: str
    image_url: str = None
    location: str = None


def get_connection():
    """Get a database connection."""
    return sqlite3.connect(DATABASE_FILE)


def ensure_schema():
    """Create the listings table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            price TEXT,
            url TEXT NOT NULL,
            image_url TEXT,
            location TEXT,
            first_seen TEXT NOT NULL
        )
    """)

    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_platform ON listings(platform)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_first_seen ON listings(first_seen)")

    conn.commit()
    conn.close()


def get_seen_ids(platform: str = None) -> Set[str]:
    """
    Get set of already-seen listing IDs.

    Args:
        platform: Optional filter by platform ('facebook' or 'craigslist')

    Returns:
        Set of listing IDs
    """
    ensure_schema()  # Ensure table exists
    conn = get_connection()
    cursor = conn.cursor()

    if platform:
        cursor.execute("SELECT id FROM listings WHERE platform = ?", (platform,))
    else:
        cursor.execute("SELECT id FROM listings")

    rows = cursor.fetchall()
    conn.close()

    return set(row[0] for row in rows)


def store_listings(listings: List[Listing]) -> int:
    """
    Store new listings in the database.

    Args:
        listings: List of Listing objects to store

    Returns:
        Number of new listings stored
    """
    if not listings:
        return 0

    ensure_schema()  # Ensure table exists
    conn = get_connection()
    cursor = conn.cursor()

    stored = 0
    now = datetime.now().isoformat()

    for listing in listings:
        try:
            cursor.execute(
                """
                INSERT INTO listings (id, platform, title, price, url, image_url, location, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.id,
                    listing.platform,
                    listing.title,
                    listing.price,
                    listing.url,
                    listing.image_url,
                    listing.location,
                    now
                )
            )
            stored += 1
        except sqlite3.IntegrityError:
            # Duplicate ID, skip
            pass

    conn.commit()
    conn.close()

    return stored


def cleanup_old_listings(days: int = 7) -> int:
    """
    Remove listings older than specified days.

    Args:
        days: Number of days to keep listings

    Returns:
        Number of listings removed
    """
    ensure_schema()  # Ensure table exists
    conn = get_connection()
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("SELECT COUNT(*) FROM listings WHERE first_seen < ?", (cutoff,))
    count = cursor.fetchone()[0]

    cursor.execute("DELETE FROM listings WHERE first_seen < ?", (cutoff,))

    conn.commit()
    conn.close()

    return count


def get_listing_count() -> dict:
    """Get count of listings by platform."""
    ensure_schema()  # Ensure table exists
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT platform, COUNT(*)
        FROM listings
        GROUP BY platform
    """)

    rows = cursor.fetchall()
    conn.close()

    return {row[0]: row[1] for row in rows}
