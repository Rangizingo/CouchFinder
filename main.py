"""
CouchFinder - Marketplace Monitor
Main entry point and orchestration loop.

Auto-installs all dependencies on first run.
"""

import sys
import os
import subprocess
from pathlib import Path

# Get base directory before any other imports
BASE_DIR = Path(__file__).parent.resolve()


def ensure_dependencies():
    """
    Auto-install all dependencies. Run BEFORE other imports.
    Returns True if restart is needed (new packages installed).
    """
    needs_restart = False

    # Required packages from requirements.txt
    required_packages = [
        ("playwright", "playwright>=1.40.0"),
        ("playwright_stealth", "playwright-stealth>=2.0.0"),
        ("bs4", "beautifulsoup4>=4.12.0"),
        ("requests", "requests>=2.31.0"),
        ("dotenv", "python-dotenv>=1.0.0"),
    ]

    for import_name, pip_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            print(f"Installing {pip_name}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            needs_restart = True

    # Check Playwright Chromium browser
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch to verify it's installed
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        print("Installing Playwright Chromium browser (this may take a minute)...")
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL
        )
        needs_restart = True

    return needs_restart


def ensure_env_file():
    """Create .env file if it doesn't exist, prompt for webhook URLs."""
    env_file = BASE_DIR / ".env"
    env_example = BASE_DIR / ".env.example"

    if env_file.exists():
        return

    print("\n" + "=" * 50)
    print("FIRST TIME SETUP - Discord Webhook Configuration")
    print("=" * 50)
    print("\nNo .env file found. Let's set up your Discord webhooks.")
    print("(You can edit .env later to change these)\n")

    # Get webhook URLs from user
    print("Create webhooks in Discord: Server Settings > Integrations > Webhooks")
    print()

    craigslist_webhook = input("Craigslist Discord webhook URL: ").strip()
    facebook_webhook = input("Facebook Discord webhook URL: ").strip()

    # Create .env content
    env_content = f"""# Discord webhook URLs for notifications
# Platform-specific webhooks - each platform goes to its own channel
DISCORD_WEBHOOK_CRAIGSLIST={craigslist_webhook}
DISCORD_WEBHOOK_FACEBOOK={facebook_webhook}

# Main webhook (leave empty - not used when platform-specific are set)
DISCORD_WEBHOOK_URL=

# Location settings
LOCATION_ZIP=43215
LOCATION_RADIUS_MILES=100

# Price range
MIN_PRICE=0
MAX_PRICE=1000

# How often to check for new listings (in seconds)
CHECK_INTERVAL_SECONDS=60

# File paths (relative to script directory)
DATABASE_FILE=couchfinder.db
LOG_FILE=couchfinder.log
BROWSER_DATA_DIR=browser_data

# Set to true to run browser in headless mode (no visible window)
# Keep false for initial setup to allow manual Facebook login
HEADLESS=false
"""

    with open(env_file, "w") as f:
        f.write(env_content)

    print(f"\nCreated {env_file}")
    print("You can edit this file anytime to change settings.\n")


# === AUTO-SETUP ON IMPORT ===
# This runs before anything else when main.py is executed

if __name__ == "__main__":
    # Step 1: Install missing pip packages and playwright browser
    print("Checking dependencies...")
    if ensure_dependencies():
        print("Dependencies installed. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # Step 2: Ensure .env exists
    ensure_env_file()

# === NOW SAFE TO IMPORT EVERYTHING ===

import time
import signal
import logging
import argparse
from datetime import datetime

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

    args = parser.parse_args()
    run_monitor(skip_facebook=args.skip_facebook)


if __name__ == "__main__":
    main()
