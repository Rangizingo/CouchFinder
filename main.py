"""
CouchFinder - Marketplace Monitor
Main entry point and orchestration loop.
"""

import sys
import time
import signal
import logging
import argparse
from datetime import datetime

# Setup logging first
from config import LOG_FILE, CHECK_INTERVAL_SECONDS, DISCORD_WEBHOOK_CRAIGSLIST, DISCORD_WEBHOOK_FACEBOOK

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("CouchFinder")

# Now import other modules
from database import ensure_schema, get_seen_ids, store_listings, cleanup_old_listings, get_listing_count
from notifier import send_batch, send_startup_message, send_error_message, test_webhook
from scrapers import CraigslistScraper, FacebookScraper


# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    if not running:
        # Second Ctrl+C = force exit immediately
        logger.info("Force exit...")
        sys.exit(1)
    logger.info("Shutdown signal received, stopping... (press Ctrl+C again to force)")
    running = False


def check_dependencies():
    """Check and install missing dependencies."""
    try:
        import playwright
    except ImportError:
        logger.info("Installing playwright...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])

    # Check if Chromium is installed
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Just check if we can reference chromium
            _ = p.chromium
    except Exception:
        logger.info("Installing Playwright Chromium browser...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def run_monitor(skip_facebook: bool = False):
    """
    Main monitoring loop.

    Args:
        skip_facebook: If True, only monitor Craigslist (useful for testing)
    """
    global running

    logger.info("=" * 50)
    logger.info("CouchFinder Starting")
    logger.info("=" * 50)

    # Ensure database schema exists
    logger.info("Initializing database...")
    ensure_schema()

    # Verify Discord webhooks
    if not DISCORD_WEBHOOK_CRAIGSLIST and not DISCORD_WEBHOOK_FACEBOOK:
        logger.error("No Discord webhooks configured in .env")
        return

    if not test_webhook():
        logger.warning("Discord webhook test failed - notifications may not work")

    # Initialize scrapers
    # Initialize Craigslist FIRST to avoid asyncio conflicts
    # (Facebook's playwright can create asyncio issues for sync playwright)
    scrapers = []

    logger.info("Initializing Craigslist scraper...")
    cl_scraper = CraigslistScraper()
    # Initialize browser now to get playwright instance
    cl_scraper._initialize_browser()
    scrapers.append(cl_scraper)

    if not skip_facebook:
        logger.info("Initializing Facebook scraper...")
        try:
            # Share playwright instance from Craigslist to avoid conflicts
            fb_scraper = FacebookScraper(playwright_instance=cl_scraper.playwright)
            scrapers.insert(0, fb_scraper)  # Facebook first in scrape order
        except Exception as e:
            logger.error(f"Failed to initialize Facebook scraper: {e}")
            logger.info("Continuing with Craigslist only")

    if not scrapers:
        logger.error("No scrapers available, exiting")
        return

    # Send startup notification
    send_startup_message()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Monitoring started. Check interval: {CHECK_INTERVAL_SECONDS}s")
    logger.info("Press Ctrl+C to stop")

    check_count = 0
    last_cleanup = datetime.now()

    try:
        while running:
            check_count += 1
            logger.info(f"--- Check #{check_count} at {datetime.now().strftime('%H:%M:%S')} ---")

            total_new = 0

            for scraper in scrapers:
                try:
                    # Get seen IDs upfront so scraper can stop early
                    seen_ids = get_seen_ids(scraper.platform)

                    # Get new listings (scraper will stop early when it hits known IDs)
                    new_listings = scraper.get_listings(seen_ids)

                    if not new_listings:
                        logger.debug(f"{scraper.platform}: No new listings")
                        continue

                    logger.info(f"{scraper.platform}: {len(new_listings)} new listings")

                    # Send notifications
                    sent = send_batch(new_listings)
                    logger.info(f"Sent {sent} notifications to Discord")

                    # Store in database
                    stored = store_listings(new_listings)
                    logger.info(f"Stored {stored} listings in database")

                    total_new += len(new_listings)

                except Exception as e:
                    logger.error(f"Error scraping {scraper.platform}: {e}", exc_info=True)

            # Summary
            counts = get_listing_count()
            logger.info(f"Total new this check: {total_new} | DB totals: {counts}")

            # Daily cleanup (every 24 hours)
            hours_since_cleanup = (datetime.now() - last_cleanup).total_seconds() / 3600
            if hours_since_cleanup >= 24:
                removed = cleanup_old_listings(days=7)
                logger.info(f"Cleanup: removed {removed} old listings")
                last_cleanup = datetime.now()

            # Wait for next check (use short sleeps so Ctrl+C responds quickly)
            if running:
                logger.debug(f"Sleeping {CHECK_INTERVAL_SECONDS}s until next check...")
                for _ in range(CHECK_INTERVAL_SECONDS):
                    if not running:
                        break
                    time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        send_error_message(f"CouchFinder crashed: {str(e)}")
    finally:
        # Cleanup
        logger.info("Shutting down scrapers...")
        for scraper in scrapers:
            try:
                scraper.close()
            except Exception as e:
                logger.error(f"Error closing {scraper.platform}: {e}")

        logger.info("CouchFinder stopped")


def main():
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="CouchFinder - Marketplace Monitor")
    parser.add_argument(
        "--skip-facebook",
        action="store_true",
        help="Skip Facebook Marketplace (Craigslist only)",
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check and install dependencies, then exit",
    )

    args = parser.parse_args()

    if args.check_deps:
        check_dependencies()
        print("Dependencies checked/installed")
        return

    run_monitor(skip_facebook=args.skip_facebook)


if __name__ == "__main__":
    main()
