#!/usr/bin/env python3
"""
Flight Price Tracker with Amadeus API
Monitors flight prices and sends webhook notifications when prices drop below threshold
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global status variable for web server
status_data = {
    "type": "startup",
    "status": "initializing",
    "message": "Starting up...",
    "routes_tracked": 0,
    "routes": [],
    "check_interval_hours": 0,
    "last_check": None,
    "next_check": None,
    "timestamp": datetime.now().isoformat()
}


class StatusHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to serve status JSON"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/' or self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(status_data, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def start_web_server(port: int = 8080):
    """Start simple HTTP server in background thread"""
    server = HTTPServer(('0.0.0.0', port), StatusHandler)
    logger.info(f"Status web server started on port {port}")
    server.serve_forever()


class AmadeusAuth:
    """Handle Amadeus API authentication"""
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = None
        self.token_expires_at = None
        self.auth_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        
    def get_access_token(self) -> str:
        """Get or refresh access token"""
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
            
        try:
            response = requests.post(
                self.auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.api_secret
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data["access_token"]
            # Set expiry 60 seconds before actual expiry for safety
            expires_in = data.get("expires_in", 1799)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info("Amadeus access token obtained")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Amadeus access token: {e}")
            raise


class FlightTracker:
    def __init__(self, amadeus_auth: AmadeusAuth, webhook_url: str):
        self.auth = amadeus_auth
        self.webhook_url = webhook_url
        self.base_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        
    def search_flights(self, departure: str, destination: str, date: str, 
                      return_date: Optional[str] = None, adults: int = 1) -> Dict:
        """Search for flights using Amadeus API"""
        params = {
            "originLocationCode": departure,
            "destinationLocationCode": destination,
            "departureDate": date,
            "adults": adults,
            "currencyCode": "USD",
            "max": 10  # Get top 10 results
        }
        
        if return_date:
            params["returnDate"] = return_date
            
        try:
            token = self.auth.get_access_token()
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            response = requests.get(self.base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching flights: {e}")
            return {}
    
    def get_best_flight(self, flights_data: Dict, allowed_airlines: Optional[List[str]] = None) -> Optional[Dict]:
        """Extract the best (cheapest) flight from search results"""
        if not flights_data or "data" not in flights_data:
            return None
            
        offers = flights_data.get("data", [])
        if not offers:
            return None
        
        # Filter by allowed airlines if specified
        if allowed_airlines:
            filtered_offers = []
            for offer in offers:
                # Check all segments for airline codes
                segments = offer.get("itineraries", [{}])[0].get("segments", [])
                if segments:
                    airline_code = segments[0].get("carrierCode", "")
                    # Get airline name from dictionaries if available
                    dictionaries = flights_data.get("dictionaries", {})
                    carriers = dictionaries.get("carriers", {})
                    airline_name = carriers.get(airline_code, airline_code)
                    
                    # Check if any allowed airline matches
                    if any(allowed.lower() in airline_name.lower() or 
                          allowed.upper() == airline_code for allowed in allowed_airlines):
                        filtered_offers.append(offer)
            
            if not filtered_offers:
                logger.info(f"No flights found matching allowed airlines: {allowed_airlines}")
                return None
            
            offers = filtered_offers
        
        # Sort by price and get cheapest
        offers.sort(key=lambda x: float(x.get("price", {}).get("total", 999999)))
        best = offers[0]
        
        # Extract relevant information
        price = float(best.get("price", {}).get("total", 0))
        
        # Get airline info
        segments = best.get("itineraries", [{}])[0].get("segments", [])
        airline_code = segments[0].get("carrierCode", "Unknown") if segments else "Unknown"
        
        # Get airline name from dictionaries
        dictionaries = flights_data.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})
        airline_name = carriers.get(airline_code, airline_code)
        
        # Get departure and arrival times
        departure_time = segments[0].get("departure", {}).get("at", "") if segments else None
        arrival_time = segments[-1].get("arrival", {}).get("at", "") if segments else None
        
        # Calculate duration
        duration = None
        for itinerary in best.get("itineraries", []):
            if itinerary.get("duration"):
                duration = itinerary["duration"]
                break
        
        return {
            "price": price,
            "airline": airline_name,
            "airline_code": airline_code,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "duration": duration,
            "segments": len(segments),
            "offer_id": best.get("id")
        }
    
    def send_webhook_notification(self, flight_info: Dict, route_info: Dict):
        """Send notification via webhook when price threshold is met"""
        payload = {
            "route": f"{route_info['departure']} → {route_info['destination']}",
            "date": route_info.get('date'),
            "return_date": route_info.get('return_date'),
            "trip_length": route_info.get('trip_length'),
            "adults": route_info.get('adults', 1),
            "price": flight_info["price"],
            "threshold": route_info["max_price"],
            "airline": flight_info["airline"],
            "departure_time": flight_info.get("departure_time"),
            "arrival_time": flight_info.get("arrival_time"),
            "duration": flight_info.get("duration"),
            "segments": flight_info.get("segments"),
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"Webhook notification sent successfully for {payload['route']}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending webhook: {e}")
    
    def check_flight_route(self, route: Dict) -> bool:
        """Check a single flight route and notify if price is below threshold"""
        departure = route["departure"]
        destination = route["destination"]
        max_price = route["max_price"]
        adults = route.get("adults", 1)
        allowed_airlines = route.get("allowed_airlines")
        must_include_dates = route.get("must_include_dates", [])
        exclude_return_dates = route.get("exclude_return_dates", [])
        
        # Convert must_include_dates to datetime objects for comparison
        required_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in must_include_dates]
        excluded_return_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in exclude_return_dates]
        
        # Handle date ranges with trip length
        if "date_range" in route:
            start_date = datetime.strptime(route["date_range"]["start"], "%Y-%m-%d")
            end_date = datetime.strptime(route["date_range"]["end"], "%Y-%m-%d")
            
            # Get trip length settings
            trip_length = route.get("trip_length_days")
            trip_flex = route.get("trip_flex_days", 0)
            
            if trip_length is not None:
                # Generate combinations of outbound dates and return dates
                date_combinations = []
                current = start_date
                while current <= end_date:
                    # Calculate return dates based on trip length and flexibility
                    min_trip = trip_length - trip_flex
                    max_trip = trip_length + trip_flex
                    
                    for days in range(min_trip, max_trip + 1):
                        return_date = current + timedelta(days=days)
                        
                        # Check if return date is excluded
                        if return_date.date() in excluded_return_dates:
                            continue
                        
                        # Check if this trip covers all required dates
                        if required_dates:
                            trip_start = current.date()
                            trip_end = return_date.date()
                            covers_required = all(
                                trip_start <= req_date <= trip_end 
                                for req_date in required_dates
                            )
                            if not covers_required:
                                continue
                        
                        date_combinations.append({
                            "outbound": current.strftime("%Y-%m-%d"),
                            "return": return_date.strftime("%Y-%m-%d"),
                            "trip_days": days
                        })
                    
                    current += timedelta(days=1)
            else:
                # No trip length specified, just check outbound dates
                date_combinations = []
                current = start_date
                while current <= end_date:
                    combo = {"outbound": current.strftime("%Y-%m-%d")}
                    if "return_date" in route:
                        return_date_obj = datetime.strptime(route["return_date"], "%Y-%m-%d")
                        
                        # Check if return date is excluded
                        if return_date_obj.date() in excluded_return_dates:
                            current += timedelta(days=1)
                            continue
                        
                        combo["return"] = route["return_date"]
                        
                        # Check if trip covers required dates
                        if required_dates:
                            trip_start = current.date()
                            trip_end = return_date_obj.date()
                            covers_required = all(
                                trip_start <= req_date <= trip_end 
                                for req_date in required_dates
                            )
                            if not covers_required:
                                current += timedelta(days=1)
                                continue
                    
                    date_combinations.append(combo)
                    current += timedelta(days=1)
        else:
            # Single date specified
            date_combinations = [{"outbound": route["date"]}]
            if "return_date" in route:
                return_date_obj = datetime.strptime(route["return_date"], "%Y-%m-%d")
                
                # Check if return date is excluded
                if return_date_obj.date() in excluded_return_dates:
                    logger.warning(f"Fixed return date is in excluded dates: {route['return_date']}")
                    return False
                
                date_combinations[0]["return"] = route["return_date"]
                
                # Validate that fixed dates cover required dates
                if required_dates:
                    trip_start = datetime.strptime(route["date"], "%Y-%m-%d").date()
                    trip_end = return_date_obj.date()
                    covers_required = all(
                        trip_start <= req_date <= trip_end 
                        for req_date in required_dates
                    )
                    if not covers_required:
                        logger.warning(f"Fixed dates don't cover required dates: {must_include_dates}")
                        return False
        
        if not date_combinations:
            logger.warning(f"No date combinations meet requirements (required: {must_include_dates}, excluded returns: {exclude_return_dates})")
            return False
        
        found_deal = False
        
        for combo in date_combinations:
            outbound = combo["outbound"]
            return_date = combo.get("return")
            trip_days = combo.get("trip_days")
            
            trip_info = f" ({trip_days} days)" if trip_days else ""
            adults_info = f" for {adults} adult(s)" if adults > 1 else ""
            logger.info(f"Checking {departure} → {destination} on {outbound}" + 
                       (f" returning {return_date}{trip_info}" if return_date else "") + adults_info)
            
            flights_data = self.search_flights(departure, destination, outbound, return_date, adults)
            
            if not flights_data:
                continue
                
            best_flight = self.get_best_flight(flights_data, allowed_airlines)
            
            if not best_flight:
                logger.warning(f"No flights found for {departure} → {destination} on {outbound}")
                continue
            
            price = best_flight["price"]
            logger.info(f"Best price: ${price} (threshold: ${max_price}) - {best_flight['airline']}")
            
            if price <= max_price:
                logger.info(f"🎉 Price alert! Flight found at ${price}")
                route_info = route.copy()
                route_info["date"] = outbound
                route_info["return_date"] = return_date
                if trip_days:
                    route_info["trip_length"] = trip_days
                self.send_webhook_notification(best_flight, route_info)
                found_deal = True
            
            # Rate limiting - Amadeus allows more requests but be respectful
            time.sleep(1)
        
        return found_deal


def load_config(config_path: str = "config.json") -> Dict:
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    """Main execution loop"""
    global status_data
    
    # Load configuration
    config_path = os.getenv("CONFIG_PATH", "config.json")
    
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        return
    
    # Initialize Amadeus authentication
    amadeus_key = os.getenv("AMADEUS_API_KEY", config.get("amadeus_api_key"))
    amadeus_secret = os.getenv("AMADEUS_API_SECRET", config.get("amadeus_api_secret"))
    webhook_url = os.getenv("WEBHOOK_URL", config.get("webhook_url"))
    web_port = int(os.getenv("WEB_PORT", config.get("web_port", 8080)))
    
    if not amadeus_key or not amadeus_secret or not webhook_url:
        logger.error("AMADEUS_API_KEY, AMADEUS_API_SECRET, and WEBHOOK_URL must be provided")
        return
    
    # Start web server in background thread
    web_thread = threading.Thread(target=start_web_server, args=(web_port,), daemon=True)
    web_thread.start()
    
    auth = AmadeusAuth(amadeus_key, amadeus_secret)
    
    # Test authentication and send startup notification
    auth_status = "success"
    auth_message = "Successfully authenticated with Amadeus API"
    try:
        auth.get_access_token()
    except Exception as e:
        auth_status = "failed"
        auth_message = f"Failed to authenticate: {str(e)}"
        logger.error(auth_message)
    
    # Get routes to monitor
    routes = config.get("routes", [])
    if not routes:
        logger.error("No routes configured")
        return
    
    check_interval = config.get("check_interval_hours", 6)
    
    # Update status data
    status_data = {
        "type": "startup",
        "status": auth_status,
        "message": auth_message,
        "routes_tracked": len(routes),
        "routes": [
            {
                "departure": r.get("departure"),
                "destination": r.get("destination"),
                "description": r.get("description", "")
            }
            for r in routes
        ],
        "check_interval_hours": check_interval,
        "last_check": None,
        "next_check": (datetime.now() + timedelta(hours=check_interval)).isoformat(),
        "timestamp": datetime.now().isoformat()
    }
    
    # Send startup notification
    try:
        response = requests.post(
            webhook_url,
            json=status_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        logger.info("Startup notification sent successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending startup notification: {e}")
    
    # Exit if authentication failed
    if auth_status == "failed":
        return
    
    tracker = FlightTracker(auth, webhook_url)
    
    logger.info(f"Starting flight tracker with {len(routes)} routes")
    
    # Check interval in seconds
    check_interval_seconds = check_interval * 3600
    
    while True:
        logger.info("=" * 60)
        logger.info("Starting new check cycle")
        
        # Update status before check
        status_data["last_check"] = datetime.now().isoformat()
        status_data["next_check"] = (datetime.now() + timedelta(hours=check_interval)).isoformat()
        
        for route in routes:
            try:
                tracker.check_flight_route(route)
            except Exception as e:
                logger.error(f"Error checking route {route.get('departure')} → {route.get('destination')}: {e}")
        
        logger.info(f"Check cycle complete. Sleeping for {check_interval} hours")
        time.sleep(check_interval_seconds)


if __name__ == "__main__":
    main()
