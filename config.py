"""
CouchFinder Configuration
Loads settings from environment variables and defines constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory (where this script lives)
BASE_DIR = Path(__file__).parent.resolve()

# Discord webhooks (separate channels for each platform)
# Hardcoded for automatic setup - repo is private
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_WEBHOOK_CRAIGSLIST = os.getenv(
    "DISCORD_WEBHOOK_CRAIGSLIST",
    "https://discord.com/api/webhooks/1448061060501209230/mp2Cl13jbuo3R96wB72rq0bRjByGkyDGbulLA48bEUOkPBpVYiJ1juOAUyFeTqukBCOV"
)
DISCORD_WEBHOOK_FACEBOOK = os.getenv(
    "DISCORD_WEBHOOK_FACEBOOK",
    "https://discord.com/api/webhooks/1448060837939122178/siZ9df0Gb1mjyHMWcDM4aW6G7dMnwYQTpaFQqfeEwGNQzvrUAbz10DrqZakb5KBHdvSz"
)

# Location
LOCATION_ZIP = os.getenv("LOCATION_ZIP", "43215")
LOCATION_RADIUS_MILES = int(os.getenv("LOCATION_RADIUS_MILES", "100"))

# Price range
MIN_PRICE = int(os.getenv("MIN_PRICE", "0"))
MAX_PRICE = int(os.getenv("MAX_PRICE", "1000"))

# Timing
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))

# File paths
DATABASE_FILE = BASE_DIR / os.getenv("DATABASE_FILE", "couchfinder.db")
LOG_FILE = BASE_DIR / os.getenv("LOG_FILE", "couchfinder.log")
BROWSER_DATA_DIR = BASE_DIR / os.getenv("BROWSER_DATA_DIR", "browser_data")

# Browser settings
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

# Search terms for sectionals only
SEARCH_TERMS = [
    "sectional",
    "L-shaped",
    "U-shaped",
    "modular sofa",
]

# Extended search terms (not currently used, kept for reference)
EXTENDED_SEARCH_TERMS = [
    "couch",
    "sofa",
    "loveseat",
    "futon",
    "sleeper sofa",
    "chaise",
    "recliner sofa",
]

# Craigslist settings
CRAIGSLIST_BASE_URL = "https://columbus.craigslist.org"
CRAIGSLIST_CATEGORIES = ["fua"]  # furniture by owner (dealers less common for used)

# Facebook Marketplace settings
FACEBOOK_MARKETPLACE_URL = "https://www.facebook.com/marketplace/columbus"

# User agent for requests
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
