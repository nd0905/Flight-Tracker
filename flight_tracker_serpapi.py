#!/usr/bin/env python3
"""
Flight Price Tracker with SerpAPI
Monitors flight prices and sends webhook notifications when prices drop below threshold
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FlightTracker:
    def __init__(self, serpapi_key: str, webhook_url: str):
        self.serpapi_key = serpapi_key
        self.webhook_url = webhook_url
        self.base_url = "https://serpapi.com/search"
        
    def search_flights(self, departure: str, destination: str, date: str, 
                      return_date: Optional[str] = None, adults: int = 1) -> Dict:
        """Search for flights using SerpAPI Google Flights"""
        params = {
            "engine": "google_flights",
            "departure_id": departure,
            "arrival_id": destination,
            "outbound_date": date,
            "currency": "USD",
            "hl": "en",
            "adults": adults,
            "api_key": self.serpapi_key
        }
        
        if return_date:
            params["return_date"] = return_date
            params["type"] = "1"  # Round trip
        else:
            params["type"] = "2"  # One way
            
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching flights: {e}")
            return {}
    
    def get_best_flight(self, flights_data: Dict, allowed_airlines: Optional[List[str]] = None) -> Optional[Dict]:
        """Extract the best (cheapest) flight from search results"""
        if not flights_data or "best_flights" not in flights_data:
            return None
            
        best_flights = flights_data.get("best_flights", [])
        if not best_flights:
            return None
        
        # Filter by allowed airlines if specified
        if allowed_airlines:
            filtered_flights = []
            for flight in best_flights:
                if flight.get("flights"):
                    airline = flight["flights"][0].get("airline", "").lower()
                    # Check if any allowed airline matches
                    if any(allowed.lower() in airline for allowed in allowed_airlines):
                        filtered_flights.append(flight)
            
            if not filtered_flights:
                logger.info(f"No flights found matching allowed airlines: {allowed_airlines}")
                return None
            
            best_flights = filtered_flights
            
        best = best_flights[0]
        return {
            "price": best.get("price"),
            "airline": best["flights"][0].get("airline") if best.get("flights") else "Unknown",
            "departure_time": best["flights"][0].get("departure_airport", {}).get("time") if best.get("flights") else None,
            "arrival_time": best["flights"][0].get("arrival_airport", {}).get("time") if best.get("flights") else None,
            "duration": best.get("total_duration"),
            "booking_token": best.get("booking_token"),
            "flights": best.get("flights", [])
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
            
            # Rate limiting - be respectful to the API
            time.sleep(2)
        
        return found_deal


def load_config(config_path: str = "config.json") -> Dict:
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    """Main execution loop"""
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
    
    # Initialize tracker
    serpapi_key = os.getenv("SERPAPI_KEY", config.get("serpapi_key"))
    webhook_url = os.getenv("WEBHOOK_URL", config.get("webhook_url"))
    
    if not serpapi_key or not webhook_url:
        logger.error("SERPAPI_KEY and WEBHOOK_URL must be provided")
        return
    
    tracker = FlightTracker(serpapi_key, webhook_url)
    
    # Get routes to monitor
    routes = config.get("routes", [])
    if not routes:
        logger.error("No routes configured")
        return
    
    logger.info(f"Starting flight tracker with {len(routes)} routes")
    
    # Check interval in seconds (default: 6 hours)
    check_interval = config.get("check_interval_hours", 6) * 3600
    
    while True:
        logger.info("=" * 60)
        logger.info("Starting new check cycle")
        
        for route in routes:
            try:
                tracker.check_flight_route(route)
            except Exception as e:
                logger.error(f"Error checking route {route.get('departure')} → {route.get('destination')}: {e}")
        
        logger.info(f"Check cycle complete. Sleeping for {check_interval/3600} hours")
        time.sleep(check_interval)


if __name__ == "__main__":
    main()
