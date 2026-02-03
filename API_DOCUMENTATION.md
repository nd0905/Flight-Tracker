# Flight Tracker API Documentation

The Flight Tracker includes a built-in web server that exposes flight data through HTTP endpoints.

## Endpoints

### GET `/status`

Returns the current status of the Flight Tracker service, including API usage estimates.

**URL:** `http://localhost:8080/status` (or use your configured `web_port`)

**Response Example:**
```json
{
  "type": "startup",
  "status": "success",
  "message": "Successfully authenticated with Amadeus API",
  "routes_tracked": 4,
  "routes": [
    {
      "departure": "DEN",
      "destination": "ORD",
      "description": "Denver to Chicago O'Hare - Christmas 2026"
    }
  ],
  "check_interval_hours": 168,
  "api_requests_per_check": 45,
  "api_requests_per_route": [
    {
      "route": "DEN → ORD",
      "requests": 30
    },
    {
      "route": "LAX → JFK",
      "requests": 1
    }
  ],
  "estimated_monthly_requests": 194,
  "last_check": "2024-01-15T14:30:00.123456",
  "next_check": "2024-01-22T14:30:00.123456",
  "timestamp": "2024-01-15T14:30:00.123456"
}
```

**Response Fields:**

- `api_requests_per_check`: Total number of API calls that will be made in each check cycle
- `api_requests_per_route`: Breakdown of API calls per route
- `estimated_monthly_requests`: Approximate API calls per month based on check interval (assumes 720 hours/month)

### GET `/flights`

Returns all flight price data collected during the last check cycle.

**URL:** `http://localhost:8080/flights` (or use your configured `web_port`)

**Response Example:**
```json
{
  "last_updated": "2024-01-15T14:30:00.123456",
  "routes": [
    {
      "departure": "DEN",
      "destination": "ORD",
      "description": "Denver to Chicago O'Hare - Christmas 2026",
      "max_price": 400,
      "last_checked": "2024-01-15T14:30:00.123456",
      "best_price": 325.00,
      "flights_found": 45,
      "flights": [
        {
          "departure_airport": "DEN",
          "destination_airport": "ORD",
          "outbound_date": "2026-12-20",
          "return_date": "2026-12-28",
          "trip_days": 8,
          "adults": 1,
          "price": 325.00,
          "airline": "United Airlines",
          "airline_code": "UA",
          "departure_time": "2026-12-20T08:30:00",
          "arrival_time": "2026-12-28T17:45:00",
          "duration": "PT2H15M",
          "segments": 1,
          "checked_at": "2024-01-15T14:30:00.123456"
        },
        {
          "departure_airport": "DEN",
          "destination_airport": "ORD",
          "outbound_date": "2026-12-20",
          "return_date": "2026-12-28",
          "trip_days": 8,
          "adults": 1,
          "price": 350.00,
          "airline": "American Airlines",
          "airline_code": "AA",
          "departure_time": "2026-12-20T10:15:00",
          "arrival_time": "2026-12-28T19:30:00",
          "duration": "PT2H45M",
          "segments": 1,
          "checked_at": "2024-01-15T14:30:00.123456"
        }
      ]
    }
  ]
}
```

**Response Fields:**

- `last_updated`: ISO 8601 timestamp of when the flight data was last updated
- `routes`: Array of route objects, each containing:
  - `departure`: Origin airport code
  - `destination`: Destination airport code
  - `description`: Human-readable description of the route
  - `max_price`: Price threshold for notifications
  - `last_checked`: ISO 8601 timestamp of when this route was last checked
  - `best_price`: Lowest price found across all flights for this route
  - `flights_found`: Total number of flights found for this route
  - `flights`: Array of flight objects, each containing:
    - `departure_airport`: Origin airport code
    - `destination_airport`: Destination airport code
    - `outbound_date`: Departure date (YYYY-MM-DD)
    - `return_date`: Return date (YYYY-MM-DD) or null for one-way
    - `trip_days`: Length of trip in days or null
    - `adults`: Number of adult passengers
    - `price`: Total price in USD
    - `airline`: Full airline name
    - `airline_code`: IATA airline code
    - `departure_time`: ISO 8601 timestamp of departure
    - `arrival_time`: ISO 8601 timestamp of arrival
    - `duration`: ISO 8601 duration format (e.g., "PT2H15M" = 2 hours 15 minutes)
    - `segments`: Number of flight segments (1 = direct, >1 = has stops)
    - `checked_at`: ISO 8601 timestamp of when this flight was checked

## Usage Examples

### Command Line (curl)

Get current status:
```bash
curl http://localhost:8080/status
```

Get all flight prices:
```bash
curl http://localhost:8080/flights
```

Get best price for a specific route using jq:
```bash
curl -s http://localhost:8080/flights | \
  jq '.routes[] | select(.departure == "DEN" and .destination == "ORD") | .best_price'
```

List all flights under $400:
```bash
curl -s http://localhost:8080/flights | \
  jq '.routes[].flights[] | select(.price < 400)'
```

### Python

```python
import requests

# Get all flight data
response = requests.get('http://localhost:8080/flights')
data = response.json()

# Find cheapest flight across all routes
all_flights = []
for route in data['routes']:
    all_flights.extend(route['flights'])

cheapest = min(all_flights, key=lambda x: x['price'])
print(f"Cheapest flight: ${cheapest['price']} - {cheapest['airline']}")
print(f"Route: {cheapest['departure_airport']} → {cheapest['destination_airport']}")
print(f"Dates: {cheapest['outbound_date']} to {cheapest['return_date']}")
```

### JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

async function getFlights() {
  const response = await fetch('http://localhost:8080/flights');
  const data = await response.json();
  
  // Find all direct flights
  const directFlights = [];
  data.routes.forEach(route => {
    route.flights.forEach(flight => {
      if (flight.segments === 1) {
        directFlights.push(flight);
      }
    });
  });
  
  console.log(`Found ${directFlights.length} direct flights`);
}

getFlights();
```

## Integration with Home Assistant

### REST Sensor for Flight Prices

Add this to your `configuration.yaml`:

```yaml
sensor:
  - platform: rest
    name: "Flight Tracker Status"
    resource: "http://FLIGHT_TRACKER_IP:8080/status"
    method: GET
    scan_interval: 3600
    json_attributes_path: "$"
    json_attributes:
      - routes_tracked
      - last_check
      - next_check
    value_template: "{{ value_json.status }}"
  
  - platform: rest
    name: "Flight Prices"
    resource: "http://FLIGHT_TRACKER_IP:8080/flights"
    method: GET
    scan_interval: 3600
    json_attributes_path: "$"
    json_attributes:
      - last_updated
      - routes
    value_template: "{{ value_json.routes | length }}"
```

### Template Sensor for Cheapest Flight

```yaml
template:
  - sensor:
      - name: "Cheapest Flight Price"
        state: >
          {% set flights = state_attr('sensor.flight_prices', 'routes') %}
          {% if flights %}
            {% set all_prices = [] %}
            {% for route in flights %}
              {% for flight in route.flights %}
                {% set _ = all_prices.append(flight.price) %}
              {% endfor %}
            {% endfor %}
            {{ all_prices | min | round(2) }}
          {% else %}
            unavailable
          {% endif %}
        unit_of_measurement: "USD"
        
      - name: "Total Flights Found"
        state: >
          {% set flights = state_attr('sensor.flight_prices', 'routes') %}
          {% if flights %}
            {{ flights | sum(attribute='flights_found') }}
          {% else %}
            0
          {% endif %}
```

### Lovelace Dashboard Card

Display all flight prices in a table:

```yaml
type: custom:flex-table-card
title: Flight Prices
entities:
  include: sensor.flight_prices
columns:
  - name: Route
    data: routes
    modify: |
      x.departure + ' → ' + x.destination
  - name: Best Price
    data: routes
    modify: |
      '$' + x.best_price.toFixed(2)
  - name: Flights Found
    data: routes
    modify: x.flights_found
  - name: Last Checked
    data: routes
    modify: |
      new Date(x.last_checked).toLocaleString()
```

## Webhook Behavior

The Flight Tracker will:

1. **Collect all flight prices** for each route during a check cycle
2. **Store all prices** in memory, accessible via the `/flights` endpoint
3. **Send a webhook notification ONLY for the best (cheapest) price** that is below the threshold
4. **Send only one notification per route per check cycle**, even if multiple date combinations are below the threshold

This means:
- You can query `/flights` to see all available flights and their prices
- You'll only receive one webhook notification per route with the absolute best deal
- The notification will include the specific date combination with the lowest price

## Notes

- Flight data is stored in memory and reset when the service restarts
- Data is updated every time a check cycle completes (based on `check_interval_hours`)
- The `/flights` endpoint always returns the most recent data from the last completed check
- CORS is enabled on all endpoints (`Access-Control-Allow-Origin: *`)
- The web server runs on the port specified in `web_port` config (default: 8080)
