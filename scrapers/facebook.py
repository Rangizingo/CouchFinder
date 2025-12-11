"""
CouchFinder Facebook Marketplace Scraper
Playwright-based scraper with persistent authentication.
"""

import re
import logging
import time
from typing import List, Set, Optional, Tuple
from urllib.parse import urlencode, quote_plus

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

from .base import BaseScraper
from database import Listing
from config import (
    FACEBOOK_MARKETPLACE_URL,
    SEARCH_TERMS,
    MIN_PRICE,
    MAX_PRICE,
    LOCATION_RADIUS_MILES,
    BROWSER_DATA_DIR,
    HEADLESS,
    USER_AGENT,
)

# Keywords that indicate the listing is actually a sofa/couch (not boots, cushions, etc.)
FURNITURE_KEYWORDS = [
    "sectional", "sofa", "couch", "loveseat", "chaise", "recliner",
    "furniture", "seating", "living room", "seat sofa", "modular"
]

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    """Scraper for Facebook Marketplace using Playwright."""

    def __init__(self, playwright_instance=None):
        """
        Initialize Facebook scraper.

        Args:
            playwright_instance: Optional shared Playwright instance to avoid conflicts
        """
        super().__init__("facebook")
        self._owns_playwright = playwright_instance is None
        self.playwright = playwright_instance
        self.context = None
        self.page = None
        self._initialized = False
        self._headless = True  # Start headless by default

    def _initialize_browser(self, headless: bool = True):
        """Initialize Playwright with persistent context.

        Args:
            headless: Whether to run browser in headless mode
        """
        if self._initialized:
            return

        self._headless = headless
        logger.info(f"Initializing Facebook Marketplace browser (headless={headless})...")

        # Start playwright if we don't have a shared instance
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self._owns_playwright = True

        # Ensure browser data directory exists
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Launch persistent context (saves cookies/session)
        self.context = self.playwright.chromium.launch_persistent_context(
            str(BROWSER_DATA_DIR),
            headless=headless,
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        # Get or create page
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

        # Apply stealth to avoid detection
        stealth = Stealth()
        stealth.apply_stealth_sync(self.page)

        self._initialized = True
        logger.info("Browser initialized")

    def _relaunch_visible(self):
        """Close headless browser and relaunch with visible window for login."""
        logger.info("Relaunching browser with visible window for login...")

        # Close current context - storage_state saves cookies automatically for persistent context
        if self.context:
            try:
                # Force cookie flush by saving storage state before closing
                self.context.storage_state(path=str(BROWSER_DATA_DIR / "storage_state.json"))
            except Exception as e:
                logger.debug(f"Could not save storage state: {e}")
            self.context.close()
            self.context = None

        self._initialized = False
        self._initialize_browser(headless=False)

    def _can_access_marketplace(self) -> bool:
        """Check if we can access Facebook Marketplace (logged in or not)."""
        try:
            # Navigate to marketplace
            self.page.goto(FACEBOOK_MARKETPLACE_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Dismiss any login popup that appears
            self._dismiss_login_popup()

            # Check if we got redirected to a login page
            current_url = self.page.url

            # Hard block - redirected to login or checkpoint page
            if "/login" in current_url.lower() or "checkpoint" in current_url.lower():
                logger.debug(f"Redirected to login: {current_url}")
                return False

            # If URL starts with marketplace path, we're good
            if "/marketplace" in current_url.lower():
                return True

            # Fallback: check page content for marketplace items
            content = self.page.content()
            if "/marketplace/item/" in content:
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking marketplace access: {e}")
            return False

    def wait_for_manual_login(self, timeout_minutes: int = 5) -> bool:
        """
        Wait for user to manually log in.

        Args:
            timeout_minutes: Maximum time to wait for login

        Returns:
            True if login successful, False if timeout
        """
        logger.info("=" * 50)
        logger.info("FACEBOOK LOGIN REQUIRED")
        logger.info("Please log in to Facebook in the browser window.")
        logger.info(f"You have {timeout_minutes} minutes to complete login.")
        logger.info("=" * 50)

        print("\n" + "=" * 50)
        print("FACEBOOK LOGIN REQUIRED")
        print("Please log in to Facebook in the browser window.")
        print(f"You have {timeout_minutes} minutes to complete login.")
        print("Press ENTER here after you've logged in...")
        print("=" * 50 + "\n")

        # Navigate to Facebook login
        self.page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")

        # Wait for user to press Enter (no more auto-refreshing!)
        timeout_seconds = timeout_minutes * 60
        check_interval = 10  # Check every 10 seconds
        elapsed = 0

        while elapsed < timeout_seconds:
            time.sleep(check_interval)
            elapsed += check_interval

            try:
                current_url = self.page.url
                # Only check URL, don't navigate - let user complete login
                # If they're on facebook.com but not login page, they logged in
                if "facebook.com" in current_url and "login" not in current_url.lower():
                    # Give a moment for page to settle
                    time.sleep(3)
                    # Now verify marketplace access
                    self.page.goto(FACEBOOK_MARKETPLACE_URL, wait_until="domcontentloaded")
                    time.sleep(2)
                    if "login" not in self.page.url.lower():
                        logger.info("Login successful!")
                        print("Login successful!")
                        return True
            except Exception:
                pass

        logger.error("Login timeout")
        return False

    def _build_search_url(self, query: str) -> str:
        """Build Facebook Marketplace search URL."""
        # Facebook Marketplace URL structure
        # https://www.facebook.com/marketplace/columbus/search?query=couch&minPrice=0&maxPrice=1000&daysSinceListed=1&sortBy=creation_date_descend

        params = {
            "query": query,
            "minPrice": MIN_PRICE,
            "maxPrice": MAX_PRICE,
            "daysSinceListed": 7,  # Last 7 days
            "sortBy": "creation_date_descend",  # Newest first
        }

        return f"{FACEBOOK_MARKETPLACE_URL}/search?{urlencode(params)}"

    def _extract_id(self, url: str) -> str:
        """Extract listing ID from Facebook URL."""
        # URLs look like: /marketplace/item/1234567890/
        match = re.search(r'/item/(\d+)', url)
        if match:
            return f"fb_{match.group(1)}"
        # Fallback
        return f"fb_{hash(url)}"

    def _parse_listings(self, html: str, db_seen_ids: Optional[Set[str]] = None) -> Tuple[List[Listing], bool]:
        """Parse listing cards from page HTML with early stop optimization.

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

        # Facebook's structure changes frequently, try multiple selectors
        # Look for links to marketplace items
        item_links = soup.find_all("a", href=re.compile(r"/marketplace/item/\d+"))

        page_seen_ids = set()  # Dedupe within this page

        for link in item_links:
            try:
                href = link.get("href", "")
                listing_id = self._extract_id(href)

                # Dedupe within page
                if listing_id in page_seen_ids:
                    continue
                page_seen_ids.add(listing_id)

                # Early stop: if we hit a listing already in DB, stop parsing
                # (results are sorted newest-first, so everything below is older)
                if db_seen_ids and listing_id in db_seen_ids:
                    logger.debug(f"Early stop: hit known listing {listing_id}")
                    early_stopped = True
                    break

                # Build full URL
                if href.startswith("/"):
                    url = f"https://www.facebook.com{href}"
                else:
                    url = href

                # Try to find title and price within the card
                # These selectors may need adjustment as FB changes their DOM
                card = link.find_parent("div")

                title = "Facebook Listing"
                price = None
                image_url = None
                location = None

                if card:
                    # Look for text content
                    spans = card.find_all("span")
                    for span in spans:
                        text = span.get_text(strip=True)
                        # Price detection
                        if text.startswith("$") or "Free" in text:
                            price = text
                        # Title is usually the longest meaningful text
                        elif len(text) > 10 and not text.startswith("$"):
                            if len(text) > len(title) or title == "Facebook Listing":
                                title = text

                    # Look for location
                    for span in spans:
                        text = span.get_text(strip=True)
                        if "," in text and len(text) < 50:  # City, State format
                            location = text
                            break

                    # Look for image
                    img = card.find("img")
                    if img:
                        image_url = img.get("src")

                # Filter: title must contain a furniture keyword to avoid false positives
                # (e.g., "U-Shape" matching boots, cushions, stair balusters, etc.)
                title_lower = title.lower()
                if not any(kw in title_lower for kw in FURNITURE_KEYWORDS):
                    logger.debug(f"Filtered out non-furniture listing: {title[:50]}")
                    continue

                listings.append(Listing(
                    id=listing_id,
                    platform=self.platform,
                    title=title[:200],
                    price=price,
                    url=url,
                    image_url=image_url,
                    location=location or "Columbus, OH area",
                ))

            except Exception as e:
                logger.debug(f"Error parsing listing card: {e}")
                continue

        return listings, early_stopped

    def get_listings(self, seen_ids: Optional[Set[str]] = None) -> List[Listing]:
        """
        Fetch current listings from Facebook Marketplace.

        Args:
            seen_ids: Optional set of listing IDs already in database.
                      If provided, scraper will stop early when it hits a known ID.

        Returns:
            List of Listing objects (only new ones if seen_ids provided)
        """
        # Initialize browser on first call (lazy init to avoid asyncio conflicts)
        # Start headless by default
        if not self._initialized:
            self._initialize_browser(headless=True)

        # Check if we can access marketplace (don't require login - just dismiss popup)
        if not self._can_access_marketplace():
            logger.warning("Cannot access Facebook Marketplace")
            # Only relaunch for login if we hit a hard block (checkpoint)
            self._relaunch_visible()
            if not self.wait_for_manual_login():
                logger.error("Facebook login failed, skipping Facebook scrape")
                return []
            # After successful login, we can continue with the visible browser

        all_listings = []
        page_seen_ids = set()  # Dedupe across search terms within this cycle

        for term in SEARCH_TERMS:
            try:
                url = self._build_search_url(term)
                logger.info(f"Searching Facebook: {term}")

                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for listings to load
                time.sleep(3)

                # Click sort dropdown and select "Date listed: Newest first"
                # Facebook ignores the URL sortBy parameter, so we must click it
                self._select_newest_sort()

                # Scroll to load more (optional, can be slow)
                # self._scroll_page()

                # Get page content
                html = self.page.content()

                # Parse listings with early stop if seen_ids provided
                listings, early_stopped = self._parse_listings(html, seen_ids)

                if early_stopped:
                    logger.info(f"Facebook '{term}': early stop triggered, {len(listings)} new listings")
                else:
                    logger.debug(f"Facebook '{term}': {len(listings)} listings parsed")

                # Deduplicate across search terms
                for listing in listings:
                    if listing.id not in page_seen_ids:
                        page_seen_ids.add(listing.id)
                        all_listings.append(listing)

            except PlaywrightTimeout as e:
                logger.error(f"Timeout searching for '{term}': {e}")
            except Exception as e:
                logger.error(f"Error searching for '{term}': {e}")

            # Small delay between searches to avoid rate limiting
            time.sleep(1)

        logger.info(f"Facebook: Found {len(all_listings)} listings")
        return all_listings

    def _dismiss_login_popup(self):
        """Dismiss the 'See more on Facebook' login popup if present."""
        try:
            # Look for the X close button on the login popup
            close_selectors = [
                '[aria-label="Close"]',
                'div[aria-label="Close"]',
                'i[aria-label="Close"]',
                'svg[aria-label="Close"]',
                'div[role="dialog"] [role="button"]:first-child',  # First button in dialog (usually X)
                'div[role="dialog"] div[role="button"]:has(svg)',  # X button in dialog
            ]

            for selector in close_selectors:
                try:
                    close_btn = self.page.locator(selector).first
                    if close_btn.is_visible(timeout=1000):
                        close_btn.click()
                        logger.info("Dismissed login popup")
                        time.sleep(1)
                        return True
                except Exception:
                    continue

            # Also try pressing Escape key to close any modal
            self.page.keyboard.press("Escape")
            time.sleep(0.5)

            # Check if there's still a dialog and try clicking outside it
            try:
                dialog = self.page.locator('div[role="dialog"]').first
                if dialog.is_visible(timeout=500):
                    # Click outside the dialog to dismiss
                    self.page.mouse.click(10, 10)
                    time.sleep(0.5)
                    logger.info("Clicked outside dialog to dismiss")
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"No login popup to dismiss: {e}")

        return False

    def _select_newest_sort(self):
        """Click the sort dropdown and select 'Date listed: Newest first'."""
        try:
            # First dismiss any login popup that might be blocking
            self._dismiss_login_popup()
            # Look for the sort dropdown - Facebook uses various selectors
            # Try clicking on "Sort by" or the current sort option
            sort_button = None

            # Try multiple selectors for the sort button
            selectors = [
                'span:has-text("Sort by")',
                'span:has-text("Suggested")',
                '[aria-label*="Sort"]',
                'div[role="button"]:has-text("Sort")',
            ]

            for selector in selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible(timeout=2000):
                        sort_button = element
                        break
                except Exception:
                    continue

            if sort_button:
                sort_button.click()
                time.sleep(1)

                # Now click "Date listed: Newest first"
                newest_option = self.page.locator('span:has-text("Date listed: Newest first")').first
                if newest_option.is_visible(timeout=3000):
                    newest_option.click()
                    time.sleep(2)  # Wait for results to reload
                    logger.debug("Selected 'Date listed: Newest first' sort option")
                else:
                    logger.warning("Could not find 'Date listed: Newest first' option")
            else:
                logger.warning("Could not find sort dropdown button")

        except Exception as e:
            logger.warning(f"Could not select newest sort: {e}")

    def _scroll_page(self, scroll_count: int = 3):
        """Scroll page to load more listings."""
        for _ in range(scroll_count):
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

    def _save_debug_html(self, filename: str = "debug_facebook.html"):
        """Save current page HTML for debugging."""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.page.content())
            logger.debug(f"Saved debug HTML to {filename}")
        except Exception as e:
            logger.error(f"Failed to save debug HTML: {e}")

    def close(self):
        """Close browser and clean up."""
        try:
            if self.context:
                try:
                    # Force cookie flush by saving storage state before closing
                    self.context.storage_state(path=str(BROWSER_DATA_DIR / "storage_state.json"))
                    logger.debug("Saved storage state before closing")
                except Exception as e:
                    logger.debug(f"Could not save storage state: {e}")
                self.context.close()
                self.context = None
            if self._owns_playwright and self.playwright:
                self.playwright.stop()
                self.playwright = None
            self._initialized = False
            logger.info("Facebook browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
