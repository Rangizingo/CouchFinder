# CouchFinder

Real-time marketplace monitor for sectionals on Facebook Marketplace and Craigslist. Sends Discord notifications when new listings appear.

## Features

- Monitors Facebook Marketplace and Craigslist Columbus
- Searches for sectionals (sectional, L-shaped, U-shaped, modular sofa)
- Filters by price range ($0-$1000) and date (last 7 days)
- **Early stop optimization**: Stops parsing when it hits a known listing (faster cycles)
- **Sorted by newest first**: Facebook and Craigslist results sorted by date listed
- Sends Discord notifications with title, price, image, and link
- SQLite database prevents duplicate notifications
- Persistent browser session (login once, stays logged in)

## Quick Start

```bash
# Just run it - everything auto-installs on first run!
python main.py
```

On first run, the script will:
1. Auto-install all Python dependencies (playwright, beautifulsoup4, etc.)
2. Auto-install Playwright Chromium browser
3. Prompt you for Discord webhook URLs (creates .env file)
4. Start monitoring

## Usage

```bash
# Full monitoring (Facebook + Craigslist)
python main.py

# Craigslist only (no Facebook)
python main.py --skip-facebook
```

## First Run - Facebook Login

The Facebook scraper runs **headless by default**. A visible browser window only opens when login is required:

1. If not logged in, browser window opens to Facebook login
2. Log in manually (you have 5 minutes)
3. Session saves to `browser_data/` for future runs
4. Subsequent runs stay headless (no visible window)

## Configuration

### Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_WEBHOOK_CRAIGSLIST` | (required) | Webhook for Craigslist channel |
| `DISCORD_WEBHOOK_FACEBOOK` | (required) | Webhook for Facebook channel |
| `CHECK_INTERVAL_SECONDS` | 60 | How often to check for new listings |
| `MIN_PRICE` | 0 | Minimum price filter |
| `MAX_PRICE` | 1000 | Maximum price filter |
| `LOCATION_ZIP` | 43215 | Center of search area |
| `LOCATION_RADIUS_MILES` | 100 | Search radius |
| `HEADLESS` | false | Run browser without window |

**Note:** Each platform sends notifications to its own Discord channel. Craigslist listings go only to the Craigslist webhook, Facebook listings go only to the Facebook webhook.

### Search Terms (config.py)

Current search terms (sectionals only):
- sectional
- L-shaped
- U-shaped
- modular sofa

## Project Structure

```
CouchFinder/
├── main.py              # Entry point, monitoring loop
├── config.py            # Settings, search terms
├── database.py          # SQLite for tracking seen listings
├── notifier.py          # Discord webhook integration
├── scrapers/
│   ├── __init__.py
│   ├── base.py          # Abstract scraper interface
│   ├── craigslist.py    # Playwright-based CL scraper
│   └── facebook.py      # Playwright-based FB scraper
├── requirements.txt     # Python dependencies
├── .env.example         # Config template
├── .env                 # Your config (gitignored)
├── browser_data/        # Saved browser session (gitignored)
├── couchfinder.db       # SQLite database (gitignored)
└── couchfinder.log      # Log file (gitignored)
```

## How It Works

1. **Initialization**: Starts Playwright browser (headless), loads saved Facebook session
2. **Query DB**: Gets all previously-seen listing IDs for the platform
3. **Scraping**: For each search term:
   - Loads search results sorted by "Date listed: Newest first"
   - Parses listings top-to-bottom (newest first)
   - **Early stop**: When a known listing ID is hit, stops parsing (everything below is older)
   - Collects only NEW listings above that point
4. **Deduplication**: Dedupes across search terms (same listing may appear in multiple searches)
5. **Notification**: Sends new listings to Discord as embeds
6. **Storage**: Saves new listing IDs to database
7. **Loop**: Waits `CHECK_INTERVAL_SECONDS` (60s), repeats

**Cycle time**: ~20 seconds when no new listings (early stop kicks in immediately), ~2 minutes on first run or when many new listings.

## Database Schema

```sql
CREATE TABLE listings (
    id TEXT PRIMARY KEY,      -- Unique listing ID (fb_123 or cl_456)
    platform TEXT NOT NULL,   -- 'facebook' or 'craigslist'
    title TEXT NOT NULL,
    price TEXT,
    url TEXT NOT NULL,
    image_url TEXT,
    location TEXT,
    first_seen TEXT NOT NULL  -- ISO timestamp
);
```

Old listings (>7 days) are automatically cleaned up daily.

## Troubleshooting

### Facebook not finding listings
- Delete `browser_data/` folder and restart to re-login
- Facebook may have changed their DOM structure

### Discord notifications failing
- Verify webhook URL in `.env`
- Test: `python -c "from notifier import test_webhook; print(test_webhook())"`

### Craigslist not working
- Check if columbus.craigslist.org is accessible
- Craigslist blocks direct HTTP requests; we use Playwright browser

### Craigslist images not showing in Discord
- The scraper handles lazy-loaded images by checking `data-src` attribute
- Scrolls page to trigger image loading before scraping
- Placeholder/blank images are automatically filtered out

### High CPU/memory usage
- Both scrapers use Chromium browsers
- Consider increasing `CHECK_INTERVAL_SECONDS`

## Dependencies

- `playwright` - Browser automation
- `playwright-stealth` - Anti-detection for Facebook
- `beautifulsoup4` - HTML parsing
- `requests` - Discord webhook calls
- `python-dotenv` - Environment variable loading
