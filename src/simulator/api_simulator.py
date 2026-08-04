#!/usr/bin/env python3
"""
Smart Garden Manager - API Simulator
Sends sensor data directly to API Gateway (no IoT certificates needed!)
"""

import json
import time
import random
import datetime
import os
import argparse
import requests

# ============================================
# CONFIGURATION - Load from environment or use defaults
# ============================================

# Your API Gateway URL from the deployment
# Can be set via environment variable: API_GATEWAY_URL
# Or via command line: --api-url
DEFAULT_API_URL = os.getenv(
    "API_GATEWAY_URL",
    "https://3mzxjm13j8.execute-api.us-west-2.amazonaws.com/prod/data"
)

# Sensor configuration - can be overridden via command line
SENSOR_ID = os.getenv("SENSOR_ID", "sensor-001")
LOCATION = os.getenv("SENSOR_LOCATION", "indoor")
INTERVAL = int(os.getenv("SENSOR_INTERVAL", "10"))  # seconds between readings

# ============================================
# SENSOR CLASS
# ============================================

class SmartGardenSensor:
    def __init__(self, sensor_id='sensor-001', location='indoor'):
        self.sensor_id = sensor_id
        self.location = location
        self.reading_count = 0
        self.base_temp = 22.0
        self.base_humidity = 55.0
        self.base_moisture = 45.0
        
    def generate_reading(self):
        """Generate realistic sensor data"""
        self.reading_count += 1
        
        # Add some randomness
        temp = self.base_temp + random.uniform(-3, 3) + random.gauss(0, 0.5)
        humidity = self.base_humidity + random.uniform(-10, 10) + random.gauss(0, 1)
        moisture = self.base_moisture + random.uniform(-15, 15) + random.gauss(0, 2)
        
        # Clamp values
        temp = max(15, min(40, temp))
        humidity = max(20, min(90, humidity))
        moisture = max(10, min(80, moisture))
        
        # Current time (UTC)
        timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
        
        reading = {
            'sensor_id': self.sensor_id,
            'timestamp': timestamp,
            'temperature': round(temp, 1),
            'humidity': round(humidity, 1),
            'soil_moisture': round(moisture, 1),
            'location': self.location,
            'reading_id': f"{self.sensor_id}-{self.reading_count:06d}",
            'battery': round(random.uniform(85, 100), 1)
        }
        
        return reading

# ============================================
# SEND DATA TO API
# ============================================

def send_to_api(reading, api_url, verbose=False):
    """Send sensor data to API Gateway"""
    try:
        if verbose:
            print(f"  Sending to: {api_url}")
        
        response = requests.post(
            api_url,
            json=reading,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            alerts = result.get('alerts', [])
            if alerts:
                print(f"  ⚠️ ALERTS: {len(alerts)} detected!")
                for alert in alerts:
                    print(f"     - {alert}")
            return True, response.status_code, result
        else:
            print(f"  ❌ Error: HTTP {response.status_code}")
            if verbose:
                print(f"  Response: {response.text[:200]}")
            return False, response.status_code, None
            
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Connection error - API not reachable")
        if verbose:
            print(f"     URL: {api_url}")
            print("     Tip: Make sure API Gateway is deployed")
        return False, 0, None
    except requests.exceptions.Timeout:
        print(f"  ❌ Timeout error - API took too long to respond")
        return False, 0, None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False, 0, None

# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description='API Sensor Simulator - Sends data to API Gateway',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  API_GATEWAY_URL  - API Gateway URL
  SENSOR_ID        - Sensor ID (default: sensor-001)
  SENSOR_LOCATION  - Location (indoor/outdoor/greenhouse)
  SENSOR_INTERVAL  - Interval in seconds (default: 10)

Examples:
  # Use default settings
  python api_simulator.py
  
  # Custom interval
  python api_simulator.py --interval 5
  
  # Use environment variable for API URL
  export API_GATEWAY_URL="https://your-api-url.com/prod/data"
  python api_simulator.py
  
  # Verbose mode for debugging
  python api_simulator.py --verbose
        """
    )
    parser.add_argument(
        '--interval', 
        type=int, 
        default=INTERVAL,
        help=f'Interval in seconds (default: {INTERVAL})'
    )
    parser.add_argument(
        '--sensor-id', 
        type=str, 
        default=SENSOR_ID,
        help=f'Sensor ID (default: {SENSOR_ID})'
    )
    parser.add_argument(
        '--location', 
        type=str, 
        default=LOCATION,
        choices=['indoor', 'outdoor', 'greenhouse'],
        help=f'Location (default: {LOCATION})'
    )
    parser.add_argument(
        '--api-url', 
        type=str, 
        default=DEFAULT_API_URL,
        help='API Gateway URL (overrides environment variable)'
    )
    parser.add_argument(
        '--count', 
        type=int, 
        default=None,
        help='Number of readings to send (default: infinite)'
    )
    parser.add_argument(
        '--verbose', 
        '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Send a single test reading and exit'
    )
    
    args = parser.parse_args()
    
    # Override with environment variable if not set via command line
    if args.api_url == DEFAULT_API_URL and os.getenv("API_GATEWAY_URL"):
        args.api_url = os.getenv("API_GATEWAY_URL")
    
    print("=" * 60)
    print("🌱 Smart Garden - API Sensor Simulator")
    print("=" * 60)
    print(f"📡 API URL: {args.api_url}")
    print(f"🔑 Sensor ID: {args.sensor_id}")
    print(f"📍 Location: {args.location}")
    print(f"⏱️  Interval: {args.interval}s")
    if args.verbose:
        print(f"🔍 Verbose mode: ENABLED")
    print("=" * 60)
    print()
    
    # Test API connection first
    print("Testing API connection...")
    test_sensor = SmartGardenSensor(args.sensor_id, args.location)
    test_reading = test_sensor.generate_reading()
    ok, status, _ = send_to_api(test_reading, args.api_url, args.verbose)
    
    if not ok:
        print()
        print("❌ API connection test failed!")
        print()
        print("Troubleshooting tips:")
        print("  1. Make sure the API Gateway is deployed")
        print("  2. Check the API URL is correct")
        print("  3. Verify AWS credentials are configured")
        print("  4. Check that the Lambda function is working")
        print()
        print(f"Current API URL: {args.api_url}")
        print()
        sys.exit(1)
    
    print("✅ API connection test successful!")
    print()
    
    if args.test:
        print("Test mode: Single reading sent successfully")
        return
    
    # Create sensor
    sensor = SmartGardenSensor(args.sensor_id, args.location)
    
    sent = 0
    success = 0
    failed = 0
    
    print("Starting data stream...")
    print("Press CTRL+C to stop")
    print()
    
    try:
        while args.count is None or sent < args.count:
            # Generate reading
            reading = sensor.generate_reading()
            sent += 1
            
            # Display
            print(f"[{sent:4d}] T: {reading['temperature']:5.1f}°C | "
                  f"H: {reading['humidity']:5.1f}% | "
                  f"M: {reading['soil_moisture']:5.1f}%", end=" ")
            
            # Send to API
            ok, status, result = send_to_api(reading, args.api_url, args.verbose)
            
            if ok:
                success += 1
                print(f"✅ OK (200)")
            else:
                failed += 1
                print(f"❌ FAILED")
                
                # If verbose, show more details
                if args.verbose and result:
                    print(f"     Response: {json.dumps(result, indent=2)}")
            
            # Wait
            if args.count is None or sent < args.count:
                time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping...")
    
    # Summary
    print()
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total readings: {sent}")
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    if sent > 0:
        print(f"Success rate: {(success/sent)*100:.1f}%")
    print("=" * 60)
    
    # Show API URL for reference
    print()
    print(f"API URL: {args.api_url}")
    print("Use this URL in your dashboard.js file.")
    print("=" * 60)

if __name__ == "__main__":
    main()