"""
CouchFinder Craigslist Scraper
Playwright-based scraper for Craigslist listings.
"""

import re
import logging
import time
from typing import List, Set, Optional, Tuple
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

from .base import BaseScraper
from database import Listing
from config import (
    CRAIGSLIST_BASE_URL,
    CRAIGSLIST_CATEGORIES,
    SEARCH_TERMS,
    MIN_PRICE,
    MAX_PRICE,
    USER_AGENT,
    HEADLESS,
)

logger = logging.getLogger(__name__)


class CraigslistScraper(BaseScraper):
    """Scraper for Craigslist using Playwright (Craigslist blocks direct requests)."""

    def __init__(self, playwright_instance=None):
        """
        Initialize Craigslist scraper.

        Args:
            playwright_instance: Optional shared Playwright instance
        """
        super().__init__("craigslist")
        self._owns_playwright = playwright_instance is None
        self.playwright = playwright_instance
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False

    def _initialize_browser(self):
        """Initialize Playwright browser."""
        if self._initialized:
            return

        logger.info("Initializing Craigslist browser...")

        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self._owns_playwright = True

        # Use regular browser (not persistent context needed for CL - no login)
        self.browser = self.playwright.chromium.launch(
            headless=True,  # Craigslist works fine headless
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
        )

        self.page = self.context.new_page()
        self._initialized = True
        logger.info("Craigslist browser initialized")

    def _build_search_url(self, category: str, query: str) -> str:
        """Build search URL for a query."""
        params = {
            "query": query,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
            "sort": "date",  # Sort by newest
            "searchNearby": 0,  # Columbus only (set to 1 for nearby areas)
            "postedToday": 0,  # Not just today
        }
        # Note: Craigslist doesn't have a "last 7 days" param directly,
        # but sorting by date + our DB deduplication handles freshness
        return f"{CRAIGSLIST_BASE_URL}/search/{category}?{urlencode(params)}"

    def _extract_price(self, text: str) -> str:
        """Extract price from text."""
        match = re.search(r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', text)
        if match:
            return f"${match.group(1)}"
        return None

    def _extract_id(self, url: str) -> str:
        """Extract listing ID from Craigslist URL."""
        match = re.search(r'/(\d+)\.html', url)
        if match:
            return f"cl_{match.group(1)}"
        return f"cl_{hash(url)}"

    def _parse_listings_from_html(self, html: str, db_seen_ids: Optional[Set[str]] = None) -> Tuple[List[Listing], bool]:
        """Parse listings from search results HTML with early stop optimization.

        Args:
            html: Page HTML content
            db_seen_ids: Set of listing IDs already in database. If provided,
                         stops parsing when a known ID is encountered.

        Returns:
            Tuple of (list of new Listing objects, whether early stop was triggered)
        """
        soup = BeautifulSoup(html, "html.parser")
        listings = []
        early_stopped = False

        # Craigslist uses gallery-card divs for search results
        cards = soup.find_all("div", class_="gallery-card")

        for card in cards:
            try:
                # Find the posting link (a.posting-title)
                link = card.find("a", class_="posting-title")
                if not link:
                    # Fallback to any link with href containing the listing ID
                    link = card.find("a", href=re.compile(r'/\d+\.html'))
                if not link:
                    continue

                href = link.get("href", "")
                if not href:
                    continue

                # Build full URL if relative
                if href.startswith("/"):
                    url = f"{CRAIGSLIST_BASE_URL}{href}"
                else:
                    url = href

                listing_id = self._extract_id(url)

                # Early stop: if we hit a listing already in DB, stop parsing
                # (results are sorted newest-first, so everything below is older)
                if db_seen_ids and listing_id in db_seen_ids:
                    logger.debug(f"Early stop: hit known listing {listing_id}")
                    early_stopped = True
                    break

                # Extract title from span.label inside the link
                title_elem = link.find("span", class_="label")
                title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
                if not title:
                    title = "Craigslist Listing"

                # Extract price from span.priceinfo
                price_elem = card.find("span", class_="priceinfo")
                price = price_elem.get_text(strip=True) if price_elem else None

                # Extract image from the gallery (check multiple attributes for lazy-loading)
                img = card.find("img")
                image_url = None
                if img:
                    # Try data-src first (lazy-loaded), then src
                    image_url = img.get("data-src") or img.get("src")
                    # Skip placeholder/data URLs
                    if image_url and (image_url.startswith("data:") or "blank" in image_url.lower()):
                        image_url = None

                # Location is not always present, default to Columbus
                location = "Columbus, OH"

                listings.append(Listing(
                    id=listing_id,
                    platform=self.platform,
                    title=title[:200],
                    price=price,
                    url=url,
                    image_url=image_url,
                    location=location,
                ))

            except Exception as e:
                logger.debug(f"Error parsing Craigslist listing: {e}")
                continue

        return listings, early_stopped

    def get_listings(self, seen_ids: Optional[Set[str]] = None) -> List[Listing]:
        """
        Fetch current listings from Craigslist.

        Args:
            seen_ids: Optional set of listing IDs already in database.
                      If provided, scraper will stop early when it hits a known ID.

        Returns:
            List of Listing objects (only new ones if seen_ids provided)
        """
        # Lazy init browser on first call
        if not self._initialized:
            self._initialize_browser()

        page_seen_ids = set()  # Dedupe across search terms within this cycle
        all_listings = []

        for category in CRAIGSLIST_CATEGORIES:
            for term in SEARCH_TERMS:
                try:
                    url = self._build_search_url(category, term)
                    logger.info(f"Searching Craigslist: {term}")

                    self.page.goto(url, wait_until="networkidle", timeout=30000)
                    # Wait for images to load
                    time.sleep(2)
                    # Scroll to trigger lazy-loading
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    time.sleep(1)

                    html = self.page.content()
                    listings, early_stopped = self._parse_listings_from_html(html, seen_ids)

                    if early_stopped:
                        logger.info(f"Craigslist '{term}': early stop triggered, {len(listings)} new listings")
                    else:
                        logger.debug(f"Craigslist '{term}': {len(listings)} listings parsed")

                    # Deduplicate across search terms
                    for listing in listings:
                        if listing.id not in page_seen_ids:
                            page_seen_ids.add(listing.id)
                            all_listings.append(listing)

                except PlaywrightTimeout as e:
                    logger.error(f"Timeout searching for '{term}': {e}")
                except Exception as e:
                    logger.error(f"Error searching for '{term}': {e}")

                # Small delay between requests
                time.sleep(0.5)

        logger.info(f"Craigslist: Found {len(all_listings)} new listings")
        return all_listings

    def close(self):
        """Close browser and clean up."""
        try:
            if self.context:
                self.context.close()
                self.context = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self._owns_playwright and self.playwright:
                self.playwright.stop()
                self.playwright = None
            self._initialized = False
            logger.info("Craigslist browser closed")
        except Exception as e:
            logger.error(f"Error closing Craigslist browser: {e}")
