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
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_WEBHOOK_CRAIGSLIST = os.getenv("DISCORD_WEBHOOK_CRAIGSLIST", "")
DISCORD_WEBHOOK_FACEBOOK = os.getenv("DISCORD_WEBHOOK_FACEBOOK", "")

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

# Search terms for couches/sofas (prioritized - most common first)
SEARCH_TERMS = [
    "couch",
    "sofa",
    "sectional",
    "loveseat",
    "futon",
    "sleeper sofa",
    "chaise",
    "recliner sofa",
]

# Extended search terms (used for more thorough searches)
EXTENDED_SEARCH_TERMS = [
    "love seat",
    "chesterfield",
    "davenport",
    "settee",
    "divan",
    "sofa bed",
    "chaise lounge",
    "L-shaped",
    "U-shaped",
    "modular",
    "reclining couch",
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
