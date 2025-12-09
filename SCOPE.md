# CouchFinder - Project Scope & Development Checklist

## Overview

**Goal:** Build a real-time marketplace monitoring tool that alerts the user via Discord when new couch/sofa listings appear on Facebook Marketplace and Craigslist within 100 miles of Columbus, OH (43215).

**Success Criteria:**
- Detects new listings within ~1 minute of posting
- Sends Discord notification with title, price, image, and direct link
- Runs 24/7 on home server as a daemon
- Handles Facebook login persistence and Craigslist RSS parsing

---

## Requirements Summary

| Setting | Value |
|---------|-------|
| **Platforms** | Facebook Marketplace, Craigslist (Columbus) |
| **Location** | 43215, 100-mile radius |
| **Price Range** | $0 - $1,000 |
| **Polling Interval** | ~60 seconds |
| **Notification** | Discord webhook (with image + link) |
| **Auth Method** | Manual login, persistent browser session |
| **Runtime** | Home server, always-on daemon |
| **Language** | Python 3.10+ |

### Search Terms
```
couch, sofa, sectional, loveseat, love seat, chesterfield, davenport,
settee, divan, sleeper sofa, sofa bed, futon, chaise, chaise lounge,
L-shaped, U-shaped, modular, recliner sofa, reclining couch
```

---

## Architecture

```
CouchFinder/
├── main.py                 # Entry point, daemon loop, orchestration
├── config.py               # Settings, search terms, constants
├── database.py             # SQLite operations for seen listings
├── notifier.py             # Discord webhook integration
├── scrapers/
│   ├── __init__.py
│   ├── base.py             # Abstract base scraper class
│   ├── craigslist.py       # RSS-based Craigslist scraper
│   └── facebook.py         # Playwright-based FB Marketplace scraper
├── requirements.txt        # Dependencies
├── .env.example            # Environment variable template
├── .env                    # Actual config (gitignored)
├── .gitignore              # Ignore sensitive files
├── browser_data/           # Persistent Playwright session (gitignored)
├── couchfinder.db          # SQLite database (gitignored)
└── couchfinder.log         # Log file (gitignored)
```

### Data Flow
```
┌─────────────┐     ┌─────────────┐
│  Craigslist │     │  Facebook   │
│    RSS      │     │ Marketplace │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └─────────┬─────────┘
                 │
         ┌───────▼───────┐
         │   Scrapers    │
         │  (normalize)  │
         └───────┬───────┘
                 │
         ┌───────▼───────┐
         │   Database    │
         │ (dedup check) │
         └───────┬───────┘
                 │
         ┌───────▼───────┐
         │   Notifier    │
         │   (Discord)   │
         └───────────────┘
```

---

## Development Phases & Checklist

### Phase 1: Project Foundation
*Setup project structure, configuration, and core utilities*

- [ ] **1.1** Create `.gitignore` with standard Python ignores + sensitive files (browser_data/, *.db, *.log, .env, __pycache__)
- [ ] **1.2** Create `requirements.txt` with dependencies:
  - playwright>=1.40.0
  - playwright-stealth>=1.0.0
  - beautifulsoup4>=4.12.0
  - requests>=2.31.0
  - feedparser>=6.0.0
  - python-dotenv>=1.0.0
  - aiohttp>=3.9.0 (for async Discord webhooks)
- [ ] **1.3** Create `.env.example` with all configuration variables documented
- [ ] **1.4** Create `config.py` with:
  - Environment variable loading
  - Search terms list
  - Location settings (zip, radius)
  - Price range
  - Check interval
  - Discord webhook URL
  - Database/log file paths
  - URL templates for both platforms

### Phase 2: Data Layer
*Database operations for tracking seen listings*

- [ ] **2.1** Create `database.py` with SQLite operations:
  - `ensure_schema()` - Create listings table if not exists
  - Table schema: id (TEXT PK), platform (TEXT), title (TEXT), price (TEXT), url (TEXT), image_url (TEXT), first_seen (TEXT)
- [ ] **2.2** Add `get_seen_ids(platform)` - Returns set of seen listing IDs for a platform
- [ ] **2.3** Add `store_listings(listings)` - Bulk insert new listings with duplicate handling
- [ ] **2.4** Add `cleanup_old_listings(days)` - Remove listings older than N days to prevent DB bloat

### Phase 3: Notification System
*Discord webhook integration*

- [ ] **3.1** Create `notifier.py` with Discord webhook class
- [ ] **3.2** Implement `send_listing(listing)` - Send single listing as Discord embed with:
  - Title
  - Price
  - Image thumbnail
  - Direct link button
  - Platform badge (FB/CL)
  - Timestamp
- [ ] **3.3** Implement `send_batch(listings)` - Send multiple listings (max 10 embeds per message)
- [ ] **3.4** Add rate limiting (respect Discord's 30 requests/minute limit)
- [ ] **3.5** Add error handling with retry logic for failed webhooks

### Phase 4: Scraper Base Class
*Abstract interface for scrapers*

- [ ] **4.1** Create `scrapers/__init__.py`
- [ ] **4.2** Create `scrapers/base.py` with abstract `BaseScraper` class:
  - `__init__(config)` - Accept configuration
  - `get_listings()` -> List[Listing] - Abstract method
  - `Listing` dataclass: id, platform, title, price, url, image_url, location

### Phase 5: Craigslist Scraper
*RSS-based scraper (simpler, no auth needed)*

- [ ] **5.1** Create `scrapers/craigslist.py` implementing `BaseScraper`
- [ ] **5.2** Implement RSS URL builder:
  - Base: `https://columbus.craigslist.org/search/fua` (furniture by owner)
  - Also: `https://columbus.craigslist.org/search/fud` (furniture by dealer)
  - Add query params: `?query={term}&min_price=0&max_price=1000&format=rss`
- [ ] **5.3** Implement `get_listings()`:
  - Fetch RSS feed for each search term
  - Parse with feedparser
  - Extract: id (from link), title, price (parse from title), url, image (from enclosure)
  - Normalize to Listing dataclass
- [ ] **5.4** Add deduplication within single scrape (same listing may match multiple terms)
- [ ] **5.5** Add error handling for network failures

### Phase 6: Facebook Marketplace Scraper
*Playwright-based scraper with persistent auth*

- [ ] **6.1** Create `scrapers/facebook.py` implementing `BaseScraper`
- [ ] **6.2** Implement Playwright setup:
  - Persistent context in `browser_data/`
  - Stealth plugin for anti-detection
  - Custom viewport (1920x1080) and user agent
  - Headless=False for initial login, can switch to True after
- [ ] **6.3** Implement `is_logged_in(page)` check
- [ ] **6.4** Implement `wait_for_manual_login(page)` - Prompts user, waits for successful login
- [ ] **6.5** Implement search URL builder:
  - Base: `https://www.facebook.com/marketplace/columbus/search`
  - Params: `?query={term}&minPrice=0&maxPrice=1000&daysSinceListed=1&sortBy=creation_date_descend`
  - Location radius via Facebook's location settings
- [ ] **6.6** Implement `get_listings()`:
  - Navigate to search URL for each term
  - Wait for listings to load
  - Parse listing cards with BeautifulSoup
  - Extract: id (from URL), title, price, url, image_url, location
  - Handle infinite scroll if needed (or just first page for speed)
- [ ] **6.7** Add deduplication within single scrape
- [ ] **6.8** Add error handling:
  - Login detection (redirect to login page)
  - Timeout handling
  - Save debug HTML on failures
- [ ] **6.9** Implement graceful browser cleanup

### Phase 7: Main Orchestration
*Entry point and daemon loop*

- [ ] **7.1** Create `main.py` with initialization sequence:
  1. Load configuration
  2. Setup logging (file + console)
  3. Ensure database schema
  4. Initialize scrapers
  5. Initialize notifier
- [ ] **7.2** Implement initial startup notification to Discord ("CouchFinder started, monitoring...")
- [ ] **7.3** Implement main monitoring loop:
  ```python
  while True:
      for scraper in scrapers:
          listings = scraper.get_listings()
          seen_ids = db.get_seen_ids(scraper.platform)
          new_listings = [l for l in listings if l.id not in seen_ids]
          if new_listings:
              notifier.send_batch(new_listings)
              db.store_listings(new_listings)
      sleep(CHECK_INTERVAL)
  ```
- [ ] **7.4** Add per-iteration error handling (don't crash loop on single failure)
- [ ] **7.5** Add logging for each check cycle (timestamp, counts, errors)
- [ ] **7.6** Add graceful shutdown handler (SIGINT/SIGTERM)
- [ ] **7.7** Add command-line argument for headless mode toggle

### Phase 8: Polish & Deployment
*Final touches for production use*

- [ ] **8.1** Create `CLAUDE.md` with project documentation for future maintenance
- [ ] **8.2** Add startup check for Playwright browser installation (auto-install if missing)
- [ ] **8.3** Add startup check for Discord webhook validity (test ping)
- [ ] **8.4** Add daily database cleanup job (remove listings older than 7 days)
- [ ] **8.5** Test full flow end-to-end
- [ ] **8.6** Create systemd service file (or equivalent) for daemon deployment

---

## Configuration Reference

### Environment Variables (.env)

```bash
# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Location
LOCATION_ZIP=43215
LOCATION_RADIUS_MILES=100

# Price
MIN_PRICE=0
MAX_PRICE=1000

# Timing
CHECK_INTERVAL_SECONDS=60

# Paths
DATABASE_FILE=couchfinder.db
LOG_FILE=couchfinder.log
BROWSER_DATA_DIR=browser_data

# Behavior
HEADLESS=false
```

### Search Terms (in config.py)

```python
SEARCH_TERMS = [
    "couch",
    "sofa",
    "sectional",
    "loveseat",
    "love seat",
    "chesterfield",
    "davenport",
    "settee",
    "divan",
    "sleeper sofa",
    "sofa bed",
    "futon",
    "chaise",
    "chaise lounge",
    "L-shaped",
    "U-shaped",
    "modular",
    "recliner sofa",
    "reclining couch",
]
```

---

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,           -- Unique ID (URL or platform-specific ID)
    platform TEXT NOT NULL,        -- 'facebook' or 'craigslist'
    title TEXT NOT NULL,
    price TEXT,                    -- Stored as text to handle "Free", "$500", etc.
    url TEXT NOT NULL,
    image_url TEXT,
    location TEXT,
    first_seen TEXT NOT NULL       -- ISO timestamp
);

CREATE INDEX IF NOT EXISTS idx_platform ON listings(platform);
CREATE INDEX IF NOT EXISTS idx_first_seen ON listings(first_seen);
```

---

## Discord Embed Format

```json
{
  "embeds": [{
    "title": "Leather Sectional Sofa",
    "url": "https://facebook.com/marketplace/item/123",
    "description": "📍 Columbus, OH",
    "color": 5814783,
    "thumbnail": {
      "url": "https://image-url.jpg"
    },
    "fields": [
      {"name": "Price", "value": "$450", "inline": true},
      {"name": "Platform", "value": "Facebook", "inline": true}
    ],
    "timestamp": "2025-01-15T10:30:00Z"
  }]
}
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Facebook blocks scraping | High | High | Stealth plugin, persistent session, human-like delays |
| Facebook DOM changes | Medium | Medium | Flexible selectors, error logging, manual review |
| Rate limiting (Discord) | Low | Low | Built-in rate limiter |
| Session expires | Medium | Medium | Login detection, alert user to re-login |
| Duplicate notifications | Low | Low | Database deduplication |
| Database bloat | Low | Low | Daily cleanup of old entries |

---

## Development Workflow

1. Complete task (e.g., 1.1)
2. User tests functionality
3. Mark task complete in this document
4. Proceed to next task
5. Repeat until production-ready

---

## Sources & References

- [Facebook Marketplace Playwright Scraper (GitHub)](https://github.com/passivebot/facebook-marketplace-scraper)
- [How to Scrape Facebook Marketplace - Scrapfly](https://scrapfly.io/blog/posts/how-to-scrape-facebook)
- [Craigslist RSS Feed Guide - Tech Junkie](https://www.techjunkie.com/monitor-craigslist-new-posts/)
- [craigsfeed - Craigslist RSS Generator (GitHub)](https://github.com/sa7mon/craigsfeed)
- Reference implementation: `C:\Users\pblanco\Documents\AI\userinterviews_monitor`
