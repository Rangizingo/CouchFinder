"""
CouchFinder Notifier Module
Discord webhook integration for sending listing alerts.
"""

import time
import logging
import requests
from typing import List
from datetime import datetime

from config import DISCORD_WEBHOOK_URL
from database import Listing

logger = logging.getLogger(__name__)

# Discord rate limit: 30 requests per minute
RATE_LIMIT_DELAY = 2.1  # seconds between requests to stay under limit
MAX_EMBEDS_PER_MESSAGE = 10


def _get_platform_color(platform: str) -> int:
    """Get Discord embed color based on platform."""
    colors = {
        "facebook": 0x1877F2,  # Facebook blue
        "craigslist": 0x5C2D91,  # Craigslist purple
    }
    return colors.get(platform, 0x5865F2)  # Default Discord blurple


def _is_valid_url(url: str) -> bool:
    """Check if URL is valid for Discord embeds."""
    if not url:
        return False
    return url.startswith("http://") or url.startswith("https://")


def _create_embed(listing: Listing) -> dict:
    """Create a Discord embed for a listing."""
    # Ensure title is not empty
    title = (listing.title or "Listing")[:256]

    embed = {
        "title": title,
        "color": _get_platform_color(listing.platform),
        "fields": [
            {"name": "Price", "value": listing.price or "Not listed", "inline": True},
            {"name": "Platform", "value": listing.platform.capitalize(), "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Only add URL if valid (Discord rejects invalid URLs)
    if _is_valid_url(listing.url):
        embed["url"] = listing.url

    if listing.location:
        embed["description"] = f"📍 {listing.location}"

    # Only add thumbnail if URL is valid
    if _is_valid_url(listing.image_url):
        embed["thumbnail"] = {"url": listing.image_url}

    return embed


def send_listing(listing: Listing, max_retries: int = 3) -> bool:
    """
    Send a single listing to Discord.

    Args:
        listing: The listing to send
        max_retries: Number of retry attempts on failure

    Returns:
        True if sent successfully, False otherwise
    """
    if not DISCORD_WEBHOOK_URL:
        logger.error("Discord webhook URL not configured")
        return False

    payload = {
        "embeds": [_create_embed(listing)]
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=10
            )

            if response.status_code == 204:
                logger.debug(f"Sent listing: {listing.title}")
                return True
            elif response.status_code == 429:
                # Rate limited, wait and retry
                retry_after = response.json().get("retry_after", 5)
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
            else:
                logger.error(f"Discord error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            logger.error(f"Failed to send listing (attempt {attempt + 1}): {e}")
            time.sleep(1)

    return False


def send_batch(listings: List[Listing]) -> int:
    """
    Send multiple listings to Discord.

    Args:
        listings: List of listings to send

    Returns:
        Number of listings sent successfully
    """
    if not listings:
        return 0

    if not DISCORD_WEBHOOK_URL:
        logger.error("Discord webhook URL not configured")
        return 0

    sent = 0

    # Send in batches of MAX_EMBEDS_PER_MESSAGE
    for i in range(0, len(listings), MAX_EMBEDS_PER_MESSAGE):
        batch = listings[i:i + MAX_EMBEDS_PER_MESSAGE]
        embeds = [_create_embed(listing) for listing in batch]

        payload = {"embeds": embeds}

        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=10
            )

            if response.status_code == 204:
                sent += len(batch)
                logger.info(f"Sent batch of {len(batch)} listings")
            elif response.status_code == 429:
                # Rate limited
                retry_after = response.json().get("retry_after", 5)
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                # Retry this batch
                response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
                if response.status_code == 204:
                    sent += len(batch)
            else:
                logger.error(f"Discord error {response.status_code}: {response.text}")

        except requests.RequestException as e:
            logger.error(f"Failed to send batch: {e}")

        # Rate limit delay between batches
        if i + MAX_EMBEDS_PER_MESSAGE < len(listings):
            time.sleep(RATE_LIMIT_DELAY)

    return sent


def send_startup_message() -> bool:
    """Send a startup notification to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return False

    payload = {
        "embeds": [{
            "title": "🛋️ CouchFinder Started",
            "description": "Now monitoring Facebook Marketplace and Craigslist for new listings.",
            "color": 0x00FF00,
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 204
    except requests.RequestException as e:
        logger.error(f"Failed to send startup message: {e}")
        return False


def send_error_message(error: str) -> bool:
    """Send an error notification to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return False

    payload = {
        "embeds": [{
            "title": "⚠️ CouchFinder Error",
            "description": error[:2000],  # Discord description limit
            "color": 0xFF0000,
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 204
    except requests.RequestException:
        return False


def test_webhook() -> bool:
    """Test if the Discord webhook is valid and working."""
    if not DISCORD_WEBHOOK_URL:
        return False

    try:
        # GET request to webhook URL returns webhook info
        response = requests.get(DISCORD_WEBHOOK_URL, timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False
