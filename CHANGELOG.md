# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.6] - 2026-06-03

### Fixed
- Config hot-reload now works reliably in Docker containers by using content-hash detection as a fallback when mtime changes are not propagated (e.g. single-file bind mounts with atomic editor saves)
- Removed `:ro` flag from Docker config mount so filesystem metadata updates propagate correctly

## [1.1.5] - 2026-05-28

### Changed
- Calendar now always shows 12 months from the current month, regardless of flight data
- Day cells clip overflowing text by default; full details revealed on hover with expanded card
- Updated calendar tests to use relative future dates instead of hardcoded ones

### Added
- Past-date validation: routes with departure dates in the past are skipped with a warning
- Date ranges partially in the past only check future dates (past dates within the range are skipped)

## [1.1.4] - 2026-05-28

### Changed
- Makefile now uses a Python virtual environment (`.venv`) for all local targets (`install`, `test`, `run`)
- `make test` auto-creates the venv and installs deps if not present
- Added `make clean` target to remove venv and caches
- Added `.venv` to `.gitignore`

## [1.1.3] - 2026-05-28

### Fixed
- Division-by-zero in config reload when `check_interval_hours` is 0
- Replaced broken `test_calculate_total_api_requests` test that referenced nonexistent keys

### Added
- Tests for `calculate_total_api_requests` covering single date, date range, trip length with flex, and multiple routes
- Tests for `build_calendar_data` (date grouping, trip days range, multiple routes)
- Tests for `build_calendar_html` (HTML output, trip days display, empty state)
- Tests for `/calendar` endpoint (status code, content type)
- Testing requirements section in copilot instructions

## [1.1.2] - 2026-05-28

### Fixed
- `/status` endpoint now includes `api_requests_per_check`, `api_requests_per_route`, and `estimated_monthly_requests` from startup (previously only appeared after config reload)
- `calculate_total_api_requests()` now correctly computes date combinations from route config instead of looking for nonexistent `outbound_dates`/`return_dates` keys

## [1.1.1] - 2026-05-27

### Fixed
- Calendar layout: months now wrap into rows instead of stretching in a single line
- Calendar day cells expand on hover to show full content instead of truncating
- Added trip length (day range) display to calendar entries

### Added
- Auto-tag workflow: merging a PR with a VERSION bump automatically creates a git tag and triggers a release

## [1.1.0] - 2026-05-27

### Added
- `/calendar` endpoint — browsable HTML calendar showing destinations and price ranges per date
- CHANGELOG.md for tracking version history
- VERSION file for tracking current version
- `.github/copilot-instructions.md` for AI assistant context

## [1.0.1] - Initial tracked release

### Notes
- Existing functionality: flight price monitoring via Amadeus API, webhook notifications, `/status` and `/flights` JSON endpoints, config hot-reload, Docker support
