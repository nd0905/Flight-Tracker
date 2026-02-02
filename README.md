# Flight Price Tracker

A Python-based flight price monitoring system that uses **Amadeus API** (or SerpAPI) to track flight prices and sends webhook notifications when prices drop below your specified threshold.

> **⚠️ Note:** This project was vibe coded and likely has bugs. Use at your own discretion and please report any issues you encounter!

## Amadeus API Version (Current - Recommended)

Uses the official Amadeus for Developers API with 2,000 free API calls per month.

### Features

- Monitor multiple flight routes simultaneously
- Support for both one-way and round-trip flights
- Flexible date ranges (search across multiple dates)
- Strict date matching for specific travel dates
- Webhook notifications when price thresholds are met
- Runs continuously in a Docker container
- Distroless Docker image for security

## Configuration

### Get Amadeus API Credentials

1. Sign up at [Amadeus for Developers](https://developers.amadeus.com)
2. Create a new app in your dashboard
3. Copy your API Key and API Secret
4. Free tier: 2,000 API calls/month

Create a `config.json` file from the example:

```bash
cp config.json.example config.json
# Edit config.json with your credentials and routes
```

Configuration example:

```json
{
  "amadeus_api_key": "YOUR_AMADEUS_API_KEY",
  "amadeus_api_secret": "YOUR_AMADEUS_API_SECRET",
  "webhook_url": "YOUR_WEBHOOK_URL_HERE",
  "check_interval_hours": 168,
  "routes": [
    {
      "departure": "SFO",
      "destination": "JFK",
      "date": "2024-03-15",
      "return_date": "2024-03-20",
      "max_price": 300,
      "description": "San Francisco to New York"
    },
    {
      "departure": "LAX",
      "destination": "ORD",
      "date_range": {
        "start": "2024-04-01",
        "end": "2024-04-07"
      },
      "max_price": 250,
      "description": "LA to Chicago - Flexible dates"
    }
  ]
}
```

### Configuration Options

- `amadeus_api_key`: Your Amadeus API key
- `amadeus_api_secret`: Your Amadeus API secret
- `webhook_url`: URL to send notifications (Discord, Slack, custom endpoint, etc.)
- `web_port`: Port for status web server (default: 8080)
- `check_interval_hours`: How often to check prices (default: 6 hours)
- `routes`: Array of flight routes to monitor

### Route Options

- `departure`: IATA airport code (e.g., "SFO", "LAX")
- `destination`: IATA airport code
- `date`: Specific departure date (YYYY-MM-DD) for one-way or outbound
- `return_date`: (Optional) Return date for round-trip
- `date_range`: (Optional) Instead of `date`, provide `start` and `end` dates to check multiple dates
- `trip_length_days`: (Optional) For date ranges with round trips - desired trip length in days
- `trip_flex_days`: (Optional) Flexibility in trip length (default: 0). If `trip_length_days` is 5 and `trip_flex_days` is 2, it will check trips of 3-7 days
- `must_include_dates`: (Optional) Array of dates (YYYY-MM-DD) that must fall within the trip. The script will only check date combinations where the trip includes all specified dates. Reduces API calls by filtering out invalid combinations before searching.
- `adults`: (Optional) Number of adult passengers (default: 1)
- `allowed_airlines`: (Optional) Array of airline names to filter results. Only flights from these airlines will be considered. Uses partial matching (e.g., "United" matches "United Airlines")
- `max_price`: Maximum price threshold in USD (total for all passengers)
- `description`: (Optional) Human-readable description

### Date Range Examples

**Fixed dates:**
```json
{
  "departure": "SFO",
  "destination": "JFK",
  "date": "2024-03-15",
  "return_date": "2024-03-20",
  "max_price": 300
}
```

**Flexible departure, fixed trip length:**
```json
{
  "departure": "LAX",
  "destination": "ORD",
  "date_range": {
    "start": "2024-04-01",
    "end": "2024-04-07"
  },
  "trip_length_days": 7,
  "trip_flex_days": 0,
  "max_price": 250
}
```
Checks departures from Apr 1-7, each with exactly 7 day return.

**Must include specific dates (e.g., for a wedding/event):**
```json
{
  "departure": "BOS",
  "destination": "LAX",
  "date_range": {
    "start": "2024-07-10",
    "end": "2024-07-15"
  },
  "trip_length_days": 4,
  "trip_flex_days": 2,
  "must_include_dates": ["2024-07-13", "2024-07-14"],
  "max_price": 400
}
```
Only checks trips that include both July 13th and 14th (e.g., wedding weekend). This dramatically reduces API calls - instead of checking all 30 combinations (6 dates × 5 trip lengths), it only checks valid combinations where the trip spans those required dates.

**Flexible departure and trip length with airline filter:**
```json
{
  "departure": "MIA",
  "destination": "SEA",
  "date_range": {
    "start": "2024-05-10",
    "end": "2024-05-15"
  },
  "trip_length_days": 5,
  "trip_flex_days": 2,
  "adults": 2,
  "allowed_airlines": ["United", "Delta", "American"],
  "max_price": 700
}
```
Checks departures from May 10-15, with trips of 3-7 days (5±2), for 2 adults, only on major carriers.

**Flexible one-way departure:**
```json
{
  "departure": "DEN",
  "destination": "BOS",
  "date_range": {
    "start": "2024-06-01",
    "end": "2024-06-05"
  },
  "max_price": 200
}
```
Checks one-way flights across the date range.

## Docker Usage

### Build the image:
```bash
docker build -t flight-tracker .
```

### Run with environment variables:
```bash
docker run -d \
  -e AMADEUS_API_KEY="your_key_here" \
  -e AMADEUS_API_SECRET="your_secret_here" \
  -e WEBHOOK_URL="your_webhook_url" \
  -p 8080:8080 \
  -v $(pwd)/config.json:/app/config.json:ro \
  --name flight-tracker \
  flight-tracker
```

### Run with config file only:
```bash
docker run -d \
  -p 8080:8080 \
  -v $(pwd)/config.json:/app/config.json:ro \
  --name flight-tracker \
  flight-tracker
```

### Check status:
```bash
curl http://localhost:8080/status
```

## Webhook Payload

When a flight meets your price threshold, a POST request is sent to your webhook URL:

```json
{
  "route": "SFO → JFK",
  "date": "2024-03-15",
  "return_date": "2024-03-20",
  "trip_length": 5,
  "adults": 2,
  "price": 570,
  "threshold": 600,
  "airline": "United",
  "departure_time": "08:00",
  "arrival_time": "16:30",
  "duration": "5h 30m",
  "timestamp": "2024-02-02T10:30:00"
}
```

Note: `trip_length` will only be present when using `trip_length_days` in the route configuration. `price` is the total for all passengers.

## Example Webhook Integrations

### Discord
Use a Discord webhook URL directly in the config.

### Slack
Use a Slack incoming webhook URL.

### Home Assistant
Create an automation triggered by a webhook.

### Custom Endpoint
Any HTTP endpoint that accepts JSON POST requests.

## Development

Run locally without Docker:

```bash
pip install -r requirements.txt
export AMADEUS_API_KEY="your_key"
export AMADEUS_API_SECRET="your_secret"
export WEBHOOK_URL="your_webhook"
python flight_tracker.py
```

## SerpAPI Version (Legacy)

The original SerpAPI version is still available as `flight_tracker_serpapi.py`. It uses Google Flights data via SerpAPI but has a more limited free tier (250 calls/month).

## Notes

- Amadeus test environment may have limited data; use production credentials for real bookings
- The script includes rate limiting to be respectful to the API
- Airport codes must be valid IATA codes
- Prices are in USD
- The container runs continuously and checks at the specified interval
- Use environment variables to override config.json values for sensitive data

## API Comparison

| Feature | Amadeus (Current) | SerpAPI (Legacy) |
|---------|------------------|------------------|
| Free tier | 2,000 calls/month | 250 calls/month |
| Data source | Official airlines | Google Flights |
| Price accuracy | High | Very High |
| Setup complexity | Medium | Easy |

## License

MIT License
