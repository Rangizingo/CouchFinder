"""
Visual Test Script for CouchFinder Scrapers
Opens a visible browser and goes through scraping motions without saving to DB or notifying Discord.
"""

import time
import re
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

from config import (
    FACEBOOK_MARKETPLACE_URL,
    CRAIGSLIST_BASE_URL,
    CRAIGSLIST_CATEGORIES,
    SEARCH_TERMS,
    MIN_PRICE,
    MAX_PRICE,
    BROWSER_DATA_DIR,
    USER_AGENT,
)


def test_facebook(playwright):
    """Test Facebook Marketplace scraping with visible browser."""
    print("\n" + "=" * 60)
    print("TESTING FACEBOOK MARKETPLACE")
    print("=" * 60)

    # Ensure browser data directory exists
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Launch visible browser with persistent context (to use saved login)
    context = playwright.chromium.launch_persistent_context(
        str(BROWSER_DATA_DIR),
        headless=False,  # VISIBLE
        viewport={"width": 1920, "height": 1080},
        user_agent=USER_AGENT,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )

    page = context.pages[0] if context.pages else context.new_page()

    # Apply stealth
    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    try:
        # Check if logged in
        print("\nNavigating to Facebook Marketplace...")
        page.goto(FACEBOOK_MARKETPLACE_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if "login" in page.url.lower():
            print("\n*** NOT LOGGED IN - Please log in manually ***")
            print("Waiting 60 seconds for you to log in...")
            time.sleep(60)

        # Test search with first term only (to keep it quick)
        test_term = SEARCH_TERMS[0] if SEARCH_TERMS else "sectional"

        # Build search URL (same as scraper)
        params = {
            "query": test_term,
            "minPrice": MIN_PRICE,
            "maxPrice": MAX_PRICE,
            "daysSinceListed": 7,
            "sortBy": "creation_date_descend",  # Newest first
        }
        search_url = f"{FACEBOOK_MARKETPLACE_URL}/search?{urlencode(params)}"

        print(f"\nSearch URL: {search_url}")
        print(f"\nSearching for: '{test_term}'")
        print(f"Price range: ${MIN_PRICE} - ${MAX_PRICE}")
        print(f"Sort parameter: sortBy=creation_date_descend")
        print("\nNavigating to search results...")

        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # First, dismiss any login popup that might be blocking
        print("\nChecking for login popup to dismiss...")
        popup_dismissed = False
        close_selectors = [
            '[aria-label="Close"]',
            'div[aria-label="Close"]',
            'svg[aria-label="Close"]',
            'div[role="dialog"] div[role="button"]:has(svg)',
        ]

        for selector in close_selectors:
            try:
                close_btn = page.locator(selector).first
                if close_btn.is_visible(timeout=1000):
                    print(f"Found close button with selector: {selector}")
                    close_btn.click()
                    print("Dismissed login popup!")
                    time.sleep(1)
                    popup_dismissed = True
                    break
            except Exception:
                continue

        if not popup_dismissed:
            # Try Escape key as fallback
            print("Trying Escape key to close any modal...")
            page.keyboard.press("Escape")
            time.sleep(0.5)

        # Facebook ignores URL sort parameter, so we need to click the dropdown
        print("\nAttempting to click sort dropdown and select 'Date listed: Newest first'...")

        sort_clicked = False
        selectors = [
            'span:has-text("Sort by")',
            'span:has-text("Suggested")',
            '[aria-label*="Sort"]',
            'div[role="button"]:has-text("Sort")',
        ]

        for selector in selectors:
            try:
                element = page.locator(selector).first
                if element.is_visible(timeout=2000):
                    print(f"Found sort button with selector: {selector}")
                    element.click()
                    time.sleep(1)
                    sort_clicked = True
                    break
            except Exception:
                continue

        if sort_clicked:
            # Click "Date listed: Newest first"
            try:
                newest_option = page.locator('span:has-text("Date listed: Newest first")').first
                if newest_option.is_visible(timeout=3000):
                    newest_option.click()
                    print("Clicked 'Date listed: Newest first'!")
                    time.sleep(3)  # Wait for results to reload
                else:
                    print("Could not find 'Date listed: Newest first' option")
            except Exception as e:
                print(f"Error clicking newest option: {e}")
        else:
            print("Could not find sort dropdown button")

        print("\n*** VISUALLY VERIFY: Are results NOW sorted by newest? ***")
        print("Look at the listing dates in the browser.")
        print("\nCurrent URL:", page.url)

        # Parse and show what we found
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        item_links = soup.find_all("a", href=re.compile(r"/marketplace/item/\d+"))

        seen_ids = set()
        listings_found = []
        for link in item_links:
            href = link.get("href", "")
            match = re.search(r'/item/(\d+)', href)
            if match:
                listing_id = match.group(1)
                if listing_id not in seen_ids:
                    seen_ids.add(listing_id)
                    listings_found.append(listing_id)

        print(f"\nFound {len(listings_found)} unique listings on this page")

        print("\nPausing 30 seconds so you can inspect the browser...")
        time.sleep(30)

    finally:
        context.close()


def test_craigslist(playwright):
    """Test Craigslist scraping with visible browser."""
    print("\n" + "=" * 60)
    print("TESTING CRAIGSLIST")
    print("=" * 60)

    # Launch visible browser
    browser = playwright.chromium.launch(
        headless=False,  # VISIBLE
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )

    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=USER_AGENT,
    )

    page = context.new_page()

    try:
        # Test search with first term only
        test_term = SEARCH_TERMS[0] if SEARCH_TERMS else "sectional"
        category = CRAIGSLIST_CATEGORIES[0] if CRAIGSLIST_CATEGORIES else "fua"

        # Build search URL (same as scraper)
        params = {
            "query": test_term,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
            "sort": "date",  # Sort by newest
            "searchNearby": 0,
            "postedToday": 0,
        }
        search_url = f"{CRAIGSLIST_BASE_URL}/search/{category}?{urlencode(params)}"

        print(f"\nSearch URL: {search_url}")
        print(f"\nSearching for: '{test_term}'")
        print(f"Price range: ${MIN_PRICE} - ${MAX_PRICE}")
        print(f"Sort parameter: sort=date")
        print("\nNavigating to search results...")

        page.goto(search_url, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Scroll like the scraper does
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1)

        print("\n*** VISUALLY VERIFY: Are results sorted by newest? ***")
        print("Look at the listing dates in the browser.")
        print("\nCurrent URL:", page.url)

        # Parse and show what we found
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="gallery-card")

        print(f"\nFound {len(cards)} listings on this page")

        # Show first few listings with their info
        print("\nFirst 5 listings:")
        for i, card in enumerate(cards[:5]):
            link = card.find("a", class_="posting-title")
            if link:
                title_elem = link.find("span", class_="label")
                title = title_elem.get_text(strip=True) if title_elem else "No title"
                price_elem = card.find("span", class_="priceinfo")
                price = price_elem.get_text(strip=True) if price_elem else "No price"
                print(f"  {i+1}. {title[:50]} - {price}")

        print("\nPausing 30 seconds so you can inspect the browser...")
        time.sleep(30)

    finally:
        context.close()
        browser.close()


def main():
    print("=" * 60)
    print("COUCHFINDER VISUAL SCRAPER TEST - FACEBOOK ONLY")
    print("=" * 60)
    print(f"\nSearch terms configured: {SEARCH_TERMS}")
    print(f"Price range: ${MIN_PRICE} - ${MAX_PRICE}")
    print("\nThis will open a visible browser window so you can verify:")
    print("1. The search URL being used")
    print("2. Login popup dismissal")
    print("3. Whether results are sorted by newest")

    input("\nPress ENTER to start testing...")

    with sync_playwright() as playwright:
        test_facebook(playwright)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
