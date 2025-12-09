"""
CouchFinder Notifier Module
Discord webhook integration for sending listing alerts.
"""

import time
import logging
import requests
from typing import List
from datetime import datetime

from config import DISCORD_WEBHOOK_URL, DISCORD_WEBHOOK_CRAIGSLIST, DISCORD_WEBHOOK_FACEBOOK
from database import Listing

logger = logging.getLogger(__name__)

# Discord rate limit: 30 requests per minute
RATE_LIMIT_DELAY = 2.1  # seconds between requests to stay under limit
MAX_EMBEDS_PER_MESSAGE = 10


def _get_webhook_url(platform: str) -> str:
    """Get the appropriate webhook URL for a platform.

    Falls back to main DISCORD_WEBHOOK_URL if platform-specific not set.
    """
    if platform == "craigslist" and DISCORD_WEBHOOK_CRAIGSLIST:
        return DISCORD_WEBHOOK_CRAIGSLIST
    elif platform == "facebook" and DISCORD_WEBHOOK_FACEBOOK:
        return DISCORD_WEBHOOK_FACEBOOK
    return DISCORD_WEBHOOK_URL


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

    Listings are grouped by platform and sent to platform-specific webhooks
    if configured, otherwise to the main webhook.

    Args:
        listings: List of listings to send

    Returns:
        Number of listings sent successfully
    """
    if not listings:
        return 0

    # Group listings by platform
    by_platform = {}
    for listing in listings:
        platform = listing.platform
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(listing)

    sent = 0

    # Send each platform's listings to its webhook
    for platform, platform_listings in by_platform.items():
        webhook_url = _get_webhook_url(platform)

        if not webhook_url:
            logger.error(f"No webhook URL configured for {platform}")
            continue

        # Send in batches of MAX_EMBEDS_PER_MESSAGE
        for i in range(0, len(platform_listings), MAX_EMBEDS_PER_MESSAGE):
            batch = platform_listings[i:i + MAX_EMBEDS_PER_MESSAGE]
            embeds = [_create_embed(listing) for listing in batch]

            payload = {"embeds": embeds}

            try:
                response = requests.post(
                    webhook_url,
                    json=payload,
                    timeout=10
                )

                if response.status_code == 204:
                    sent += len(batch)
                    logger.info(f"Sent batch of {len(batch)} {platform} listings")
                elif response.status_code == 429:
                    # Rate limited
                    retry_after = response.json().get("retry_after", 5)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    # Retry this batch
                    response = requests.post(webhook_url, json=payload, timeout=10)
                    if response.status_code == 204:
                        sent += len(batch)
                else:
                    logger.error(f"Discord error {response.status_code}: {response.text}")

            except requests.RequestException as e:
                logger.error(f"Failed to send {platform} batch: {e}")

            # Rate limit delay between batches
            if i + MAX_EMBEDS_PER_MESSAGE < len(platform_listings):
                time.sleep(RATE_LIMIT_DELAY)

    return sent


def send_startup_message() -> bool:
    """Send a startup notification to both platform channels."""
    payload = {
        "embeds": [{
            "title": "🛋️ CouchFinder Started",
            "description": "Now monitoring for new listings.",
            "color": 0x00FF00,
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

    success = False
    # Send to each platform channel
    for platform in ["craigslist", "facebook"]:
        webhook_url = _get_webhook_url(platform)
        if not webhook_url:
            continue
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 204:
                success = True
        except requests.RequestException as e:
            logger.error(f"Failed to send startup message to {platform}: {e}")

    return success


def send_error_message(error: str) -> bool:
    """Send an error notification to both platform channels."""
    payload = {
        "embeds": [{
            "title": "⚠️ CouchFinder Error",
            "description": error[:2000],  # Discord description limit
            "color": 0xFF0000,
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

    success = False
    for platform in ["craigslist", "facebook"]:
        webhook_url = _get_webhook_url(platform)
        if not webhook_url:
            continue
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 204:
                success = True
        except requests.RequestException:
            pass

    return success


def test_webhook() -> bool:
    """Test if at least one Discord webhook is valid and working."""
    for platform in ["craigslist", "facebook"]:
        webhook_url = _get_webhook_url(platform)
        if not webhook_url:
            continue
        try:
            # GET request to webhook URL returns webhook info
            response = requests.get(webhook_url, timeout=10)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass

    return False
