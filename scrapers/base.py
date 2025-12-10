"""
CouchFinder Base Scraper
Abstract base class for marketplace scrapers.
"""

from abc import ABC, abstractmethod
from typing import List, Set, Optional

from database import Listing


class BaseScraper(ABC):
    """Abstract base class for marketplace scrapers."""

    def __init__(self, platform: str):
        """
        Initialize the scraper.

        Args:
            platform: Platform identifier (e.g., 'facebook', 'craigslist')
        """
        self.platform = platform

    @abstractmethod
    def get_listings(self, seen_ids: Optional[Set[str]] = None) -> List[Listing]:
        """
        Fetch current listings from the marketplace.

        Args:
            seen_ids: Optional set of listing IDs already in database.
                      If provided, scraper will stop early when it hits a known ID.

        Returns:
            List of Listing objects (only new ones if seen_ids provided)
        """
        pass

    @abstractmethod
    def close(self):
        """Clean up any resources (browser, connections, etc.)."""
        pass
