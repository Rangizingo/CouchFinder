"""
CouchFinder Base Scraper
Abstract base class for marketplace scrapers.
"""

from abc import ABC, abstractmethod
from typing import List

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
    def get_listings(self) -> List[Listing]:
        """
        Fetch current listings from the marketplace.

        Returns:
            List of Listing objects
        """
        pass

    @abstractmethod
    def close(self):
        """Clean up any resources (browser, connections, etc.)."""
        pass
