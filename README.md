# Auto Monitor Bot


<img width="932" height="598" alt="2026-07-07_16-53" src="https://github.com/user-attachments/assets/d297c871-8088-4aba-8087-bafc34b17d65" />



<img width="842" height="332" alt="2026-07-07_16-53_1" src="https://github.com/user-attachments/assets/482f1f62-53c5-4989-bfd0-4ae72c5dc946" />




<img width="682" height="784" alt="2026-07-07_16-54_1" src="https://github.com/user-attachments/assets/40248071-6bba-4669-bcef-c94d0c185dda" />
<img width="1256" height="1432" alt="2026-07-07_16-54_2" src="https://github.com/user-attachments/assets/701b7f8b-e3dc-4715-86ed-e05aabf0dfb5" />


Telegram bot for monitoring car listings on OLX.ua. Sends instant notifications when new cars matching your filters appear.

## Features

- **Real-time monitoring** — checks OLX every 2 minutes for new listings
- **Flexible filters** — brand, model, year, price (USD), mileage, condition
- **Price analysis** — compares each listing against market median, shows if the deal is good or overpriced
- **Smart deduplication** — never sends the same listing twice
- **Dual parser** — primary OLX REST API + Playwright headless browser as automatic fallback
- **Daily stats** — summary of all new listings found per day
- **Multi-user** — each user manages their own independent filters

## Tech Stack

| Layer | Technology |
|---|---|
| Bot framework | aiogram 3.7 (async) |
| Task queue | Celery 5 + Redis |
| Database | PostgreSQL 16 + SQLAlchemy async |
| Migrations | Alembic |
| Primary parser | OLX REST API via httpx |
| Fallback parser | Playwright (headless Chromium) |
| Monitoring | Flower |
| Deployment | Docker Compose |

## Architecture

```
Telegram User
     │
     ▼
 aiogram Bot  ──── PostgreSQL (users, filters, listings, price history)
                         │
                    Celery Beat
                    (every 2 min)
                         │
                    Celery Worker
                    ┌────┴────┐
                    │         │
               OLX API    Playwright
               (primary)  (fallback)
                    └────┬────┘
                    Deduplication
                         │
                    Price Analysis
                         │
                  Telegram Notification
```

## Setup

### Requirements

- Docker + Docker Compose
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))

### Environment

Create `.env` file:

```env
BOT_TOKEN=your_telegram_bot_token
POSTGRES_URL=postgresql://postgres:password@db:5432/auto_monitor
REDIS_URL=redis://redis:6379/0
```

### Run

```bash
docker compose build
docker compose up -d
docker compose exec bot alembic upgrade head
```

### Flower (task monitoring)

Available at `http://localhost:5555`

## How It Works

1. User creates a filter via the bot (brand, model, year range, price range, mileage, condition)
2. On filter creation, existing listings are silently marked as "seen" to prevent notification flood
3. Every 2 minutes Celery fetches new listings from OLX API for each active filter
4. If OLX API returns no results, Playwright renders the page in a headless browser as fallback
5. New listings are deduplicated against the database
6. Each new listing is compared against market median price (fetched from 50 sample listings)
7. Notification is sent to the user with full listing details and price analysis

## Project Structure

```
├── bot/
│   ├── handlers/       # Telegram command and callback handlers
│   ├── keyboards/      # Inline keyboard builders
│   └── states.py       # FSM states for filter wizard
├── models/             # SQLAlchemy ORM models
├── parser/
│   └── olx.py          # OLX REST API parser + Playwright fallback
├── services/
│   ├── duplicate_checker.py
│   ├── notifier.py
│   └── price_analyzer.py
├── tasks/
│   ├── celery_app.py   # Celery configuration and beat schedule
│   └── monitor.py      # Monitor, seed, cleanup, daily stats tasks
├── config/
│   └── settings.py     # Pydantic settings
├── migrations/         # Alembic migrations
├── docker-compose.yml
└── Dockerfile
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `CHECK_INTERVAL` | 120 | Seconds between OLX checks |
| `MAX_PAGES` | 3 | OLX pages to scan per filter (50 listings/page) |
| `PHOTOS_LIMIT` | 4 | Max photos per notification |
| `MARKET_SAMPLE_SIZE` | 50 | Listings used for price median calculation |
| `DAILY_STATS_HOUR` | 20 | Hour to send daily stats (UTC) |
| `CLEANUP_DAYS` | 30 | Days to keep old listings in DB |
