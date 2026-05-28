# Copilot Instructions for Flight Tracker

## Build & Test Commands

### Install Dependencies
```bash
make install
# Creates .venv and installs requirements + pytest
```

### Run Tests
```bash
# Run locally (auto-creates venv if needed)
make test
# Run within Docker container
make test-docker
```

### Build Docker Images
```bash
# Production image (multi-stage with distroless base)
make build

# Test image (for running tests in Docker)
make build-test
```

### Run Locally
```bash
# Requires environment variables:
# AMADEUS_API_KEY, AMADEUS_API_SECRET, WEBHOOK_URL
make run
```

### Run in Docker
```bash
# Uses config.json mounted read-only
make run-docker

# Stop the container
make stop

# View logs
make logs

# Remove venv and caches
make clean
```

## High-Level Architecture

### Core Components

**Flight Tracker** (`flight_tracker.py` - 766 lines)
- Single entry point that orchestrates the entire system
- Three main subsystems run concurrently via threading:
  1. **Main loop** - Periodically checks flight routes and sends notifications
  2. **Web server** - HTTP handler for `/status` and `/flights` endpoints (runs on port 8080 by default)
  3. **Config watcher** - Polls config.json for changes and triggers hot-reload

### Key Classes

1. **AmadeusAuth** - Handles OAuth2 token lifecycle
   - Fetches and caches access tokens
   - Automatically refreshes before expiry
   - Token expiry safety margin: 60 seconds

2. **FlightTracker** - Main business logic for flight searching and notifications
   - `search_flights()` - Queries Amadeus API
   - `get_all_flights()` - Parses API response into structured format, applies airline filters, sorts by price
   - `get_best_flight()` - Returns cheapest option
   - `check_flight_route()` - Orchestrates a single route check (handles date ranges, trip length logic, webhook sending)
   - `send_webhook_notification()` - Posts to webhook URL

3. **StatusHandler** - Simple HTTP request handler (BaseHTTPRequestHandler)
   - `/` or `/status` - Returns tracking status and API usage estimates (JSON)
   - `/flights` - Returns all flight prices from last check cycle (JSON)
   - `/calendar` - Browsable HTML calendar with destinations and price ranges per date
   - Suppresses default logging via `log_message()` override

### Helper Functions (Calendar)

- **`build_calendar_data()`** - Groups `flights_data` by outbound date, producing per-date entries with destination and price range
- **`build_calendar_html()`** - Renders a full HTML page with monthly grid calendars; uses Python's `calendar` module for month layout

### Global State (Thread-Safe Expectations)

- **status_data** - Dict updated by main loop, read by StatusHandler
- **flights_data** - Dict of flights found, structured by route; updated by main loop, read by StatusHandler
- Routes and check intervals can change via config hot-reload without restarting

### Flow Diagram

```
main()
├─ Load config.json
├─ Start web_server thread (HTTP handler)
├─ Initialize AmadeusAuth
├─ Start config_watcher thread (polls config.json)
└─ Main loop:
   ├─ For each route in config:
   │  └─ check_flight_route():
   │     ├─ Generate date combinations (handle ranges, trip lengths, required dates)
   │     ├─ For each date combo:
   │     │  ├─ search_flights(departure, destination, dates)
   │     │  ├─ get_all_flights() → parse + filter
   │     │  └─ Compare price to threshold
   │     ├─ Track best price across all combos
   │     └─ If best < threshold: send_webhook_notification()
   ├─ Update status_data and flights_data
   ├─ Sleep for check_interval_hours (or until config change)
   └─ On config change: validate and restart with new config
```

## Key Conventions

### Date/Trip Logic
- **`date_range` + `trip_length_days`** - Generates all combinations of departure dates within range and return dates based on trip length
- **`trip_flex_days`** - Adds flexibility around desired trip length (e.g., trip_length=5 with flex=2 checks 3-7 day trips)
- **`must_include_dates`** - Array of dates that must fall within the trip; dramatically reduces API calls by filtering invalid combos before searching
- **`exclude_return_dates`** - Skip specific return dates (e.g., avoid returning on a specific day)
- Dates are ISO 8601 format (YYYY-MM-DD)
- Single date mode: `"date"` and optional `"return_date"`
- Flexible date mode: `"date_range"` with `"start"` and `"end"`

### Webhook Behavior (Smart Notifications)
- Collects ALL flight results from search (up to 10 per date combo per Amadeus API limit)
- Stores all prices in global `flights_data` (accessible via `/flights` endpoint)
- Only sends webhook for the BEST (cheapest) price per route per check cycle
- Webhook only fires if price < max_price threshold
- Payload includes specific date combination with the lowest price

### Configuration Hot-Reload
- Config changes detected by file modification time (via `config_watcher` thread)
- Validation checks: required keys exist (api_key, secret, webhook_url, routes)
- API credentials changes require manual restart (warning logged)
- New routes/intervals take effect immediately at next check cycle
- Success notification sent via webhook after reload

### Rate Limiting
- 1 second sleep between each API call to be respectful to Amadeus
- Amadeus free tier: 2,000 calls/month (about 66 calls/day)
- Status endpoint calculates API usage estimates for planning

### Airline Filtering
- Partial matching on airline name (case-insensitive) or exact match on airline code
- Example: `"United"` matches "United Airlines", but `"UA"` matches code "UA"

### Environment Variables
- Sensitive data overrides config.json:
  - `AMADEUS_API_KEY`, `AMADEUS_API_SECRET`, `WEBHOOK_URL`
  - `WEB_PORT` (default: 8080)
  - `CONFIG_PATH` (default: "config.json")

### Logging & Monitoring
- Python logging module (not print statements)
- All operations logged at appropriate levels (info, warning, error)
- Logging setup with timestamp + level + message format
- Check cycles marked with "=" separator for readability
- Web server logs suppressed via `log_message()` override

### Testing Conventions
- Unit tests in `test_flight_tracker.py` use unittest + unittest.mock
- Helper functions: `_amadeus_offer()` and `_amadeus_response()` construct mock API responses
- Date utilities: `_near_date()` generates dates for testing
- Mock external dependencies (requests, file I/O)
- Test sections separated by "── Class Name ──────" comments

### Docker & Deployment
- Multi-stage Docker build (builder stage + distroless runtime)
- Uses distroless Python 3.14 image for security (no shell, minimal attack surface)
- Python dependencies installed in builder, copied to runtime
- Config mounted as read-only volume
- Environment variables used for secrets instead of baking into image
- Port 8080 exposed for web server

### API Response Parsing
- Amadeus API returns `data` array of offers and `dictionaries.carriers` lookup
- Extract from itinerary[0].segments[0] for basic flight info
- Handle ISO 8601 durations (e.g., "PT2H30M" = 2h 30m)
- Segments count indicates direct (1) vs connecting flights (>1)

### Data Structure Conventions
- Flight info dict keys: `price`, `airline`, `airline_code`, `departure_time`, `arrival_time`, `duration`, `segments`, `offer_id`
- Route info dict keys: `departure`, `destination`, `date`, `return_date`, `max_price`, `adults`, `allowed_airlines`, `description`, etc.
- Status updates include: `type`, `status`, `message`, `routes_tracked`, `check_interval_hours`, `last_check`, `next_check`

## Directory Structure

```
Flight-Tracker/
├── flight_tracker.py          # Main application (766 lines)
├── test_flight_tracker.py     # Unit tests
├── requirements.txt           # Python dependencies (currently just requests)
├── config.json.example        # Configuration template
├── Makefile                   # Build and test targets
├── Dockerfile                 # Multi-stage production build
├── Dockerfile.test            # Test runner image
├── API_DOCUMENTATION.md       # Detailed endpoint documentation
├── README.md                  # Project overview
├── HOMEASSISTANT_SETUP.md     # Home Assistant integration guide
├── .github/
│   ├── copilot-instructions.md  # This file
│   ├── workflows/
│   │   ├── test.yml           # CI test workflow
│   │   └── release.yml        # Tag + test + Docker + GitHub Release (on PR merge with VERSION bump)
│   └── dependabot.yml         # Dependency scanning
```

## Testing Requirements

Every code change must include corresponding tests. Run the full suite before considering a task done:

```bash
make test
# or directly via venv: .venv/bin/python -m pytest test_flight_tracker.py -v
```

### Running a single test
```bash
.venv/bin/python -m pytest test_flight_tracker.py::TestClassName::test_method_name -v
```

### Test conventions
- Tests live in `test_flight_tracker.py` using `unittest` + `unittest.mock`
- Use `@patch` to mock external calls (`requests.get`, `requests.post`, `time.sleep`)
- Use helper functions `_amadeus_offer()` and `_amadeus_response()` to build mock API data
- Use `_near_date(offset_days)` to generate dates relative to now (avoids hardcoded dates expiring)
- When testing functions that read global state (`flights_data`, `status_data`), save/restore in `setUp`/`tearDown`
- Test sections are separated by `# ── Section Name ──────` comments

### What to test
- New functions or endpoints: add a dedicated test class
- Bug fixes: add a test that would have caught the bug
- Changed behavior: update existing tests to match new behavior

## Documentation Requirements

When making changes to this project, always update documentation:

1. **README.md** — Update if the change affects user-facing behavior (new features, changed endpoints, configuration options, usage instructions, or Docker setup).
2. **CHANGELOG.md** — Append an entry under an `## [Unreleased]` section describing what was added, changed, or fixed. Use [Keep a Changelog](https://keepachangelog.com/) format:
   ```markdown
   ## [Unreleased]
   ### Added
   - Description of new feature

   ### Changed
   - Description of change

   ### Fixed
   - Description of bug fix
   ```
3. **This file (`.github/copilot-instructions.md`)** — Update if the change introduces new architecture, conventions, or patterns that future sessions need to know about.

## Versioning

This project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):

- **MAJOR** — Breaking changes (e.g., removing endpoints, changing config format incompatibly)
- **MINOR** — New functionality added in a backwards-compatible manner (e.g., new endpoints, new config options)
- **PATCH** — Backwards-compatible bug fixes

The current version lives in the `VERSION` file at the repository root (plain text, single line, no `v` prefix).

### When to bump the version

| Change type | Version bump | Example |
|---|---|---|
| New endpoint or feature | MINOR | Adding `/calendar` |
| New config option | MINOR | Adding `exclude_return_dates` |
| Bug fix | PATCH | Fixing date parsing edge case |
| Breaking API/config change | MAJOR | Removing an endpoint or renaming config keys |

### Release process

1. Update `VERSION` file with the new version number
2. Move `## [Unreleased]` entries in `CHANGELOG.md` under a new `## [X.Y.Z] - YYYY-MM-DD` heading
3. Merge the PR — the `release.yml` workflow automatically detects the VERSION change, creates a `vX.Y.Z` tag, runs tests, builds/pushes the Docker image to GHCR, and creates a GitHub Release with auto-generated notes

**Important:** Always bump `VERSION` and update `CHANGELOG.md` in the same PR as the code change. The automation handles tagging and releasing.


## Notes for Copilot Sessions

- The application is intentionally simple (single file) to avoid complex dependencies
- Thread safety is implicit (main loop updates globals before StatusHandler reads them)
- Amadeus API is hit during main loop only; web endpoints serve cached data
- Default to "test" environment in Amadeus (production URL: `api.amadeus.com`)
- When modifying date logic, test with `must_include_dates` and `exclude_return_dates` edge cases
- Status endpoint serves startup info before first check completes
- Flights and calendar endpoints are empty until first check cycle completes
- The `/calendar` endpoint serves HTML (not JSON) — it's meant for browser viewing
