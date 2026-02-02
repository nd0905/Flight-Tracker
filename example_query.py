#!/usr/bin/env python3
"""
Example script showing how to query the Flight Tracker API
and display all available flight options
"""

import requests
import json
from datetime import datetime

# Configuration
FLIGHT_TRACKER_URL = "http://localhost:8080"

def get_flight_data():
    """Fetch all flight data from the tracker"""
    try:
        response = requests.get(f"{FLIGHT_TRACKER_URL}/flights")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching flight data: {e}")
        return None

def format_duration(duration_str):
    """Convert ISO 8601 duration to readable format"""
    if not duration_str:
        return "Unknown"
    # Simple parser for PT2H15M format
    duration_str = duration_str.replace('PT', '')
    hours = 0
    minutes = 0
    if 'H' in duration_str:
        parts = duration_str.split('H')
        hours = int(parts[0])
        duration_str = parts[1] if len(parts) > 1 else ''
    if 'M' in duration_str:
        minutes = int(duration_str.replace('M', ''))
    return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

def format_time(iso_time):
    """Convert ISO time to readable format"""
    if not iso_time:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %I:%M %p')
    except:
        return iso_time

def display_flights(data):
    """Display all flights in a readable format"""
    if not data or 'routes' not in data:
        print("No flight data available")
        return
    
    print("\n" + "="*80)
    print(f"FLIGHT TRACKER DATA")
    print(f"Last Updated: {format_time(data.get('last_updated', 'Never'))}")
    print("="*80)
    
    for route in data['routes']:
        print(f"\n📍 ROUTE: {route['departure']} → {route['destination']}")
        if route.get('description'):
            print(f"   {route['description']}")
        print(f"   Threshold: ${route['max_price']}")
        print(f"   Best Price: ${route.get('best_price', 'N/A')}")
        print(f"   Flights Found: {route.get('flights_found', 0)}")
        print(f"   Last Checked: {format_time(route.get('last_checked', ''))}")
        
        if not route.get('flights'):
            print("   No flights available")
            continue
        
        print(f"\n   {'Price':<10} {'Airline':<20} {'Dates':<25} {'Duration':<12} {'Type':<10}")
        print(f"   {'-'*10} {'-'*20} {'-'*25} {'-'*12} {'-'*10}")
        
        # Show up to 10 flights per route
        for i, flight in enumerate(route['flights'][:10], 1):
            price = f"${flight['price']:.2f}"
            airline = flight['airline'][:19]  # Truncate long names
            dates = f"{flight['outbound_date']}"
            if flight.get('return_date'):
                dates += f" - {flight['return_date']}"
            duration = format_duration(flight.get('duration'))
            flight_type = "Direct" if flight.get('segments', 0) == 1 else f"{flight['segments']-1} stop(s)"
            
            print(f"   {price:<10} {airline:<20} {dates:<25} {duration:<12} {flight_type:<10}")
        
        if len(route['flights']) > 10:
            print(f"\n   ... and {len(route['flights']) - 10} more flights")
        
        print()

def find_cheapest_overall(data):
    """Find the absolute cheapest flight across all routes"""
    if not data or 'routes' not in data:
        return None
    
    cheapest = None
    cheapest_route = None
    
    for route in data['routes']:
        for flight in route.get('flights', []):
            if cheapest is None or flight['price'] < cheapest['price']:
                cheapest = flight
                cheapest_route = route
    
    return cheapest, cheapest_route

def find_direct_flights(data, max_price=None):
    """Find all direct flights, optionally under a price threshold"""
    direct_flights = []
    
    if not data or 'routes' not in data:
        return direct_flights
    
    for route in data['routes']:
        for flight in route.get('flights', []):
            if flight.get('segments', 0) == 1:
                if max_price is None or flight['price'] <= max_price:
                    direct_flights.append({
                        'route': f"{route['departure']} → {route['destination']}",
                        'flight': flight
                    })
    
    return sorted(direct_flights, key=lambda x: x['flight']['price'])

def main():
    print("Fetching flight data from Flight Tracker...")
    data = get_flight_data()
    
    if not data:
        print("Failed to fetch data")
        return
    
    # Display all flights
    display_flights(data)
    
    # Find and highlight cheapest overall
    cheapest, route = find_cheapest_overall(data)
    if cheapest:
        print("\n" + "="*80)
        print("🏆 BEST DEAL OVERALL")
        print("="*80)
        print(f"Route: {route['departure']} → {route['destination']}")
        print(f"Price: ${cheapest['price']:.2f}")
        print(f"Airline: {cheapest['airline']}")
        print(f"Dates: {cheapest['outbound_date']}", end="")
        if cheapest.get('return_date'):
            print(f" - {cheapest['return_date']}", end="")
        print(f"\nDuration: {format_duration(cheapest.get('duration'))}")
        print(f"Type: {'Direct' if cheapest.get('segments', 0) == 1 else f'{cheapest[\"segments\"]-1} stop(s)'}")
        print()
    
    # Show direct flights under $500
    print("\n" + "="*80)
    print("✈️  DIRECT FLIGHTS UNDER $500")
    print("="*80)
    direct = find_direct_flights(data, max_price=500)
    if direct:
        for i, item in enumerate(direct[:5], 1):  # Show top 5
            flight = item['flight']
            print(f"{i}. ${flight['price']:.2f} - {item['route']} - {flight['airline']}")
    else:
        print("No direct flights found under $500")
    print()

if __name__ == "__main__":
    main()
