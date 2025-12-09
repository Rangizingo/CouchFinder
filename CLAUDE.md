# CouchFinder

Real-time marketplace monitor for couches/sofas on Facebook Marketplace and Craigslist. Sends Discord notifications when new listings appear.

## Features

- Monitors Facebook Marketplace and Craigslist Columbus
- Searches for couches, sofas, sectionals, loveseats, futons, etc.
- Filters by price range ($0-$1000) and date (last 7 days)
- Sends Discord notifications with title, price, image, and link
- SQLite database prevents duplicate notifications
- Persistent browser session (login once, stays logged in)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
python -m playwright install chromium

# Configure
cp .env.example .env
# Edit .env with your Discord webhook URL

# Run
python main.py
```

## Usage

```bash
# Full monitoring (Facebook + Craigslist)
python main.py

# Craigslist only (no Facebook)
python main.py --skip-facebook

# Check/install dependencies
python main.py --check-deps
```

## First Run - Facebook Login

On first run:
1. Browser window opens to Facebook login
2. Log in manually (you have 5 minutes)
3. Session saves to `browser_data/` for future runs
4. Subsequent runs use saved session automatically

## Configuration

### Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_WEBHOOK_URL` | (required) | Discord webhook for notifications |
| `CHECK_INTERVAL_SECONDS` | 60 | How often to check for new listings |
| `MIN_PRICE` | 0 | Minimum price filter |
| `MAX_PRICE` | 1000 | Maximum price filter |
| `LOCATION_ZIP` | 43215 | Center of search area |
| `LOCATION_RADIUS_MILES` | 100 | Search radius |
| `HEADLESS` | false | Run browser without window |

### Search Terms (config.py)

Primary terms searched:
- couch, sofa, sectional, loveseat
- futon, sleeper sofa, chaise, recliner sofa

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

1. **Initialization**: Starts Playwright browser, loads saved Facebook session
2. **Scraping**: Searches each term on both platforms
3. **Deduplication**: Checks SQLite DB for already-seen listing IDs
4. **Notification**: Sends new listings to Discord as embeds
5. **Storage**: Saves new listing IDs to prevent future duplicates
6. **Loop**: Waits `CHECK_INTERVAL_SECONDS`, repeats

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

### High CPU/memory usage
- Both scrapers use Chromium browsers
- Consider increasing `CHECK_INTERVAL_SECONDS`

## Dependencies

- `playwright` - Browser automation
- `playwright-stealth` - Anti-detection for Facebook
- `beautifulsoup4` - HTML parsing
- `requests` - Discord webhook calls
- `python-dotenv` - Environment variable loading
