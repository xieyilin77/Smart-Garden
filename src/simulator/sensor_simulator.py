#!/usr/bin/env python3
"""
Smart Garden Manager - IoT Sensor Simulator
============================================
Simulates environmental sensor data and sends it to AWS IoT Core.

Features:
    - Generates realistic temperature, humidity, and soil moisture data
    - Simulates time-of-day effects
    - Random weather events (rain, heat wave) - IMPROVED
    - Configurable sending interval
    - MQTT communication with AWS IoT Core
    - Environment variable support for configuration
    - WebSocket support (port 443) for firewall-friendly connections

Installation:
    pip install AWSIoTPythonSDK python-dotenv

Usage:
    # Online mode (send to AWS IoT Core)
    python sensor_simulator.py
    
    # Online mode with WebSocket (port 443)
    python sensor_simulator.py --websocket
    
    # Offline test mode (print data only, no AWS connection)
    python sensor_simulator.py --offline
    
    # Custom interval (e.g., 60 seconds)
    python sensor_simulator.py --interval 60
    
    # Use environment variables from .env file
    python sensor_simulator.py --env
"""

import json
import time
import random
import datetime
import os
import sys
import argparse
from pathlib import Path

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("[WARNING] python-dotenv not installed. Install with: pip install python-dotenv")

# ============================================
# GLOBAL CONFIGURATION
# ============================================

# Load from environment variables with fallbacks
""" ENDPOINT = "a3m8wm6nquocq7-ats.iot.us-west-2.amazonaws.com"
TOPIC = os.getenv("AWS_IOT_TOPIC", "sensor/data")
INTERVAL = int(os.getenv("SENSOR_INTERVAL", "5"))
SENSOR_ID = os.getenv("SENSOR_ID", "sensor-001")
LOCATION = os.getenv("SENSOR_LOCATION", "indoor") """

ENDPOINT = "a2u02wa7p3xh8b-ats.iot.us-west-2.amazonaws.com"  # <-- DEIN ENDPOINT
TOPIC = "sensor/data"
INTERVAL = 5
SENSOR_ID = "sensor-001"
LOCATION = "indoor"
USE_WEBSOCKET = False
CERT_PATH = "C:/Users/yilin/Downloads/CapstoneProject/Smart-Garden/src/simulator/certs/device-certificate.pem.crt"
PRIVATE_KEY_PATH = "C:/Users/yilin/Downloads/CapstoneProject/Smart-Garden/src/simulator/certs/device-private-key.pem.key"
ROOT_CA_PATH = "C:/Users/yilin/Downloads/CapstoneProject/Smart-Garden/src/simulator/certs/root-CA.crt"

# WebSocket configuration - can be overridden by command line
USE_WEBSOCKET = os.getenv("USE_WEBSOCKET", "false").lower() in ["true", "1", "yes"]

# Paths to certificates (must be downloaded from AWS IoT Core)
CERT_PATH = os.getenv("CERT_PATH", "./certs/device-certificate.pem.crt")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "./certs/device-private-key.pem.key")
ROOT_CA_PATH = os.getenv("ROOT_CA_PATH", "./certs/root-CA.crt")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]


# ============================================
# LOGGING HELPER
# ============================================

class Logger:
    """Simple logging helper with levels"""
    
    LEVELS = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4
    }
    
    def __init__(self, level="INFO"):
        self.level = self.LEVELS.get(level.upper(), 1)
    
    def _log(self, level, message, *args, **kwargs):
        if self.LEVELS.get(level, 1) >= self.level:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")
            if args or kwargs:
                print(f"  Details: {args if args else kwargs}")
    
    def debug(self, message, *args, **kwargs):
        self._log("DEBUG", message, *args, **kwargs)
    
    def info(self, message, *args, **kwargs):
        self._log("INFO", message, *args, **kwargs)
    
    def warning(self, message, *args, **kwargs):
        self._log("WARNING", message, *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        self._log("ERROR", message, *args, **kwargs)
    
    def critical(self, message, *args, **kwargs):
        self._log("CRITICAL", message, *args, **kwargs)


# Initialize logger
logger = Logger(LOG_LEVEL)


# ============================================
# SENSOR CLASS
# ============================================

class SmartGardenSensor:
    """
    Simulated Smart Garden Sensor
    Generates realistic environmental data with natural variations
    """
    
    def __init__(self, sensor_id='sensor-001', location='indoor', seed=None):
        """
        Initialize the sensor with base parameters
        
        Args:
            sensor_id: Unique sensor identifier
            location: Sensor location (indoor/outdoor/greenhouse)
            seed: Random seed for reproducible tests (optional)
        """
        self.sensor_id = sensor_id
        self.location = location
        self.reading_count = 0
        
        # Set random seed if provided
        if seed is not None:
            random.seed(seed)
        
        # Base values depending on location
        if location == 'outdoor':
            self.base_temp = 22.0
            self.temp_range = 10.0
            self.base_humidity = 60.0
            self.humidity_range = 25.0
            self.base_moisture = 50.0
            self.moisture_range = 30.0
        elif location == 'greenhouse':
            self.base_temp = 25.0
            self.temp_range = 5.0
            self.base_humidity = 70.0
            self.humidity_range = 15.0
            self.base_moisture = 65.0
            self.moisture_range = 15.0
        else:  # indoor
            self.base_temp = 21.0
            self.temp_range = 3.0
            self.base_humidity = 50.0
            self.humidity_range = 10.0
            self.base_moisture = 45.0
            self.moisture_range = 20.0
        
        # Trends for slow changes
        self.moisture_trend = 0
        self.temperature_trend = 0
        
        # Stats tracking
        self.stats = {
            'total_readings': 0,
            'events': {'rain': 0, 'heatwave': 0, 'drought': 0}
        }
        
        logger.info(f"Sensor initialized: {sensor_id}")
        logger.info(f"Location: {location}")
        logger.info(f"Base temperature: {self.base_temp}C")
        logger.info(f"Base humidity: {self.base_humidity}%")
        logger.info(f"Base soil moisture: {self.base_moisture}%")
        logger.debug(f"Temperature range: {self.temp_range}")
        logger.debug(f"Humidity range: {self.humidity_range}")
        logger.debug(f"Moisture range: {self.moisture_range}")
    
    def _calculate_time_factor(self):
        """Calculate time of day effect (6-18 is warmer)"""
        hour = datetime.datetime.now().hour
        if 6 <= hour <= 18:
            return (hour - 6) / 12  # 0.0 to 1.0
        return 0
    
    def _apply_weather_events(self, temperature, humidity, moisture):
        """
        Apply random weather events - IMPROVED VERSION
        
        Args:
            temperature: Current temperature
            humidity: Current humidity
            moisture: Current soil moisture
        
        Returns:
            tuple: (temperature, humidity, moisture)
        """
        # Rain event (probability based on humidity)
        rain_chance = 0.01 + (humidity - 50) * 0.0005
        rain_chance = max(0.005, min(0.05, rain_chance))
        
        if random.random() < rain_chance:
            rain_amount = random.uniform(5, 25)
            moisture += rain_amount
            humidity += random.uniform(2, 8)
            self.stats['events']['rain'] += 1
            logger.info(f"🌧️ Rain event: +{rain_amount:.1f}% moisture")
        
        # Heat wave event (low humidity triggers this)
        if random.random() < 0.005 and humidity < 60:
            heat_amount = random.uniform(3, 7)
            temperature += heat_amount
            humidity -= random.uniform(2, 5)
            self.stats['events']['heatwave'] += 1
            logger.info(f"☀️ Heat wave: +{heat_amount:.1f}°C")
        
        # Drought event (long dry period simulation)
        if random.random() < 0.002 and moisture < 40:
            drought_amount = random.uniform(3, 8)
            moisture -= drought_amount
            humidity -= random.uniform(1, 3)
            self.stats['events']['drought'] += 1
            logger.info(f"🏜️ Drought event: -{drought_amount:.1f}% moisture")
        
        return temperature, humidity, moisture
    
    def _update_trends(self):
        """Update soil moisture and temperature trends"""
        # Simulate watering cycle every 100 readings
        if self.reading_count > 0 and self.reading_count % 100 == 0:
            watering = random.uniform(5, 15)
            self.moisture_trend += watering
            logger.debug(f"💧 Watering cycle: +{watering:.1f}% moisture")
        
        # Natural decrease
        decrease = random.uniform(0.1, 0.5)
        self.moisture_trend -= decrease
        
        # Temperature drift (slow changes)
        self.temperature_trend += random.uniform(-0.05, 0.05)
        self.temperature_trend = max(-2, min(2, self.temperature_trend))
        
        # Clamp moisture trend
        self.moisture_trend = max(-20, min(20, self.moisture_trend))
    
    def generate_reading(self):
        """
        Generate a new sensor reading with realistic variations
        
        Returns:
            dict: Sensor values and metadata
        """
        self.reading_count += 1
        self.stats['total_readings'] = self.reading_count
        
        # Time of day effect
        time_factor = self._calculate_time_factor()
        
        # Natural variations
        noise = random.uniform(-0.5, 0.5)
        
        # Calculate temperature
        temperature = (self.base_temp + 
                      time_factor * 5.0 + 
                      self.temperature_trend +
                      noise * 2.0 +
                      random.gauss(0, 0.3))
        temperature = max(15, min(40, temperature))
        
        # Calculate humidity (inverse to temperature)
        humidity = (self.base_humidity - 
                   time_factor * 15.0 + 
                   noise * 5.0 +
                   random.gauss(0, 1.0))
        humidity = max(20, min(90, humidity))
        
        # Update and calculate soil moisture
        self._update_trends()
        
        moisture = (self.base_moisture + 
                   self.moisture_trend +
                   random.gauss(0, 2.0))
        
        # Apply weather events
        temperature, humidity, moisture = self._apply_weather_events(
            temperature, humidity, moisture
        )
        
        # Clamp values
        moisture = max(10, min(90, moisture))
        
        # Current time (UTC)
        timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
        
        # Compose reading with all fields
        reading = {
            'sensor_id': self.sensor_id,
            'timestamp': timestamp,
            'temperature': round(temperature, 1),
            'humidity': round(humidity, 1),
            'soil_moisture': round(moisture, 1),
            'location': self.location,
            'reading_id': f"{self.sensor_id}-{self.reading_count:06d}",
            'battery': round(random.uniform(85, 100), 1)  # Simulated battery level
        }
        
        return reading

    def print_reading(self, reading):
        """
        Print a formatted reading to console
        
        Args:
            reading (dict): Sensor reading to print
        """
        logger.info(
            f"READING {self.reading_count:6d} | "
            f"T: {reading['temperature']:5.1f}C | "
            f"H: {reading['humidity']:5.1f}% | "
            f"M: {reading['soil_moisture']:5.1f}% | "
            f"Batt: {reading.get('battery', 0):4.1f}%"
        )
    
    def get_stats(self):
        """Get current statistics"""
        return self.stats


# ============================================
# MQTT CLIENT (for AWS IoT Core)
# ============================================

class IoTMQTTClient:
    """MQTT Client for AWS IoT Core with WebSocket support"""
    
    def __init__(self, endpoint, cert_path, private_key_path, root_ca_path, 
                 client_id=None, keep_alive=300, use_websocket=False):
        """
        Initialize the MQTT client
        
        Args:
            endpoint: AWS IoT Core endpoint
            cert_path: Path to device certificate
            private_key_path: Path to private key
            root_ca_path: Path to root CA certificate
            client_id: MQTT client ID
            keep_alive: Keep alive interval in seconds
            use_websocket: Use WebSocket (port 443) instead of MQTT (port 8883)
        """
        self.endpoint = endpoint
        self.cert_path = cert_path
        self.private_key_path = private_key_path
        self.root_ca_path = root_ca_path
        self.client_id = client_id or f"sensor-{random.randint(1000, 9999)}"
        self.keep_alive = keep_alive
        self.use_websocket = use_websocket
        self.mqtt_client = None
        self.connected = False
        self.connection_attempts = 0
        self.max_retries = 3
    
    def _check_certificates(self):
        """Check if all certificate files exist"""
        missing = []
        for path, name in [
            (self.cert_path, "Device certificate"),
            (self.private_key_path, "Private key"),
            (self.root_ca_path, "Root CA")
        ]:
            if not os.path.exists(path):
                missing.append(f"{name}: {path}")
        
        if missing:
            logger.error("Missing certificate files:")
            for m in missing:
                logger.error(f"  {m}")
            return False
        return True
    
    def connect(self):
        """Connect to AWS IoT Core broker"""
        try:
            from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
            
            if not self._check_certificates():
                return False
            
            # Create client with WebSocket option
            self.mqtt_client = AWSIoTMQTTClient(
                self.client_id, 
                useWebsocket=self.use_websocket
            )
            
            if self.use_websocket:
                logger.info("Using WebSocket connection (port 443)")
                self.mqtt_client.configureEndpoint(self.endpoint, 443)
            else:
                logger.info("Using MQTT connection (port 8883)")
                self.mqtt_client.configureEndpoint(self.endpoint, 8883)
            
            # Certificate configuration for both MQTT and WebSocket
            self.mqtt_client.configureCredentials(
                self.root_ca_path, 
                self.private_key_path, 
                self.cert_path
            )
            
            self.mqtt_client.configureOfflinePublishQueueing(-1)
            self.mqtt_client.configureDrainingFrequency(2)
            self.mqtt_client.configureConnectDisconnectTimeout(30)
            self.mqtt_client.configureMQTTOperationTimeout(15)
            
            # Connect with retry
            while self.connection_attempts < self.max_retries:
                self.connection_attempts += 1
                try:
                    logger.info(f"Connecting to AWS IoT Core (attempt {self.connection_attempts})...")
                    self.mqtt_client.connect()
                    self.connected = True
                    logger.info("Connected to AWS IoT Core successfully")
                    return True
                except Exception as e:
                    logger.warning(f"Connection attempt {self.connection_attempts} failed: {e}")
                    if self.connection_attempts < self.max_retries:
                        time.sleep(2 ** self.connection_attempts)
                    else:
                        raise
            
            return False
            
        except ImportError:
            logger.error("AWSIoTPythonSDK not installed!")
            logger.info("Installation: pip install AWSIoTPythonSDK")
            return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def is_connected(self):
        """Check if client is connected"""
        return self.connected and self.mqtt_client is not None
    
    def publish(self, topic, payload, qos=1):
        """
        Publish a message to an MQTT topic
        
        Args:
            topic: MQTT topic to publish to
            payload: Message payload (dict will be converted to JSON)
            qos: Quality of Service level (0, 1, or 2)
        
        Returns:
            bool: True if publish was successful
        """
        if not self.is_connected():
            logger.error("Not connected to AWS IoT Core")
            return False
        
        try:
            # Convert payload to JSON string if it's a dict
            if isinstance(payload, dict):
                payload_str = json.dumps(payload)
            else:
                payload_str = str(payload)
            
            # Publish the message
            self.mqtt_client.publish(topic, payload_str, qos)
            logger.debug(f"Published to {topic}: {payload_str[:100]}...")
            return True
            
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from AWS IoT Core broker"""
        if self.is_connected():
            try:
                self.mqtt_client.disconnect()
                self.connected = False
                logger.info("Disconnected from AWS IoT Core")
            except Exception as e:
                logger.warning(f"Disconnect error: {e}")


# ============================================
# OFFLINE SIMULATOR (no AWS connection)
# ============================================

def run_offline_simulation(sensor_id='sensor-001', interval=5, location='indoor', 
                           max_readings=None):
    """
    Run the sensor simulator in offline mode.
    Generates data and prints it to console only (no AWS connection).
    
    Args:
        sensor_id: Sensor identifier
        interval: Seconds between readings
        location: Sensor location
        max_readings: Maximum number of readings (None for infinite)
    """
    logger.info("=" * 60)
    logger.info("Smart Garden Manager - Offline Simulator")
    logger.info("=" * 60)
    logger.info("Running in OFFLINE mode - No AWS connection")
    logger.info("Data will be printed to console only")
    logger.info("=" * 60)
    
    # Create sensor
    sensor = SmartGardenSensor(sensor_id, location)
    
    logger.info(f"Generating data every {interval} seconds...")
    logger.info("Press CTRL+C to stop")
    logger.info("=" * 60)
    
    readings_sent = 0
    
    try:
        while max_readings is None or readings_sent < max_readings:
            # Generate sensor data
            reading = sensor.generate_reading()
            readings_sent += 1
            
            # Print the reading
            sensor.print_reading(reading)
            
            # Print debug info in verbose mode
            if DEBUG_MODE and readings_sent % 10 == 0:
                stats = sensor.get_stats()
                logger.debug(f"Stats: {stats}")
            
            # Wait until next reading
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping simulation...")
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Simulation finished")
    logger.info(f"Total readings generated: {readings_sent}")
    logger.info("=" * 60)


# ============================================
# ONLINE SIMULATOR (with AWS connection)
# ============================================

def run_online_simulation(
    endpoint, 
    topic, 
    cert_path, 
    private_key_path, 
    root_ca_path,
    sensor_id='sensor-001', 
    interval=5, 
    location='indoor',
    max_readings=None,
    use_websocket=False
):
    """
    Run the sensor simulator in online mode.
    Generates data and sends it to AWS IoT Core via MQTT.
    
    Args:
        endpoint: AWS IoT Core endpoint
        topic: MQTT topic
        cert_path: Path to device certificate
        private_key_path: Path to private key
        root_ca_path: Path to root CA certificate
        sensor_id: Sensor identifier
        interval: Seconds between readings
        location: Sensor location
        max_readings: Maximum number of readings (None for infinite)
        use_websocket: Use WebSocket connection (port 443)
    """
    logger.info("=" * 60)
    logger.info("Smart Garden Manager - Online Simulator")
    logger.info("=" * 60)
    if use_websocket:
        logger.info("🌐 Running in ONLINE mode with WEBSOCKET (port 443)")
    else:
        logger.info("📡 Running in ONLINE mode with MQTT (port 8883)")
    logger.info("=" * 60)
    
    # Check configuration
    if endpoint == "YOUR_IOT_ENDPOINT.iot.region.amazonaws.com":
        logger.warning("Please configure the ENDPOINT first!")
        logger.info("Set environment variable AWS_IOT_ENDPOINT or edit the file")
        logger.info("Example: AWS_IOT_ENDPOINT=a1b2c3d4e5f6-ats.iot.region.amazonaws.com")
        sys.exit(1)
    
    # Create and connect MQTT client with WebSocket option
    mqtt_client = IoTMQTTClient(
        endpoint, 
        cert_path, 
        private_key_path, 
        root_ca_path,
        use_websocket=use_websocket
    )
    
    if not mqtt_client.connect():
        logger.error("Cannot connect to AWS IoT Core")
        logger.info("Tips:")
        logger.info("  1. Make sure certificates are downloaded and paths are correct")
        logger.info("  2. Check that the IoT policy is attached to the certificate")
        logger.info("  3. Verify the endpoint is correct")
        logger.info("  4. Try using WebSocket mode: --websocket")
        sys.exit(1)
    
    # Create sensor
    sensor = SmartGardenSensor(sensor_id, location)
    
    logger.info(f"Sending data every {interval} seconds...")
    logger.info(f"Topic: {topic}")
    logger.info(f"Client ID: {mqtt_client.client_id}")
    logger.info("Press CTRL+C to stop")
    logger.info("=" * 60)
    
    # Statistics
    total = 0
    success = 0
    failed = 0
    
    try:
        while max_readings is None or total < max_readings:
            # Generate sensor data
            reading = sensor.generate_reading()
            total += 1
            
            # Publish data using the publish method
            if mqtt_client.publish(topic, reading):
                success += 1
                logger.info(
                    f"OK [{total:6d}] "
                    f"T: {reading['temperature']:5.1f}C | "
                    f"H: {reading['humidity']:5.1f}% | "
                    f"M: {reading['soil_moisture']:5.1f}%"
                )
            else:
                failed += 1
                logger.error(f"FAIL [{total:6d}] Failed to send reading")
                
                # Try to reconnect if connection lost
                if not mqtt_client.is_connected():
                    logger.warning("Connection lost, attempting to reconnect...")
                    if mqtt_client.connect():
                        logger.info("Reconnected successfully")
                    else:
                        logger.error("Reconnection failed")
            
            # Wait until next reading
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("Stopping simulation...")
    
    finally:
        # Disconnect
        mqtt_client.disconnect()
        
        # Show statistics
        logger.info("=" * 60)
        logger.info("STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total sent: {total}")
        logger.info(f"Successful: {success}")
        logger.info(f"Failed: {failed}")
        if total > 0:
            rate = (success / total) * 100
            logger.info(f"Success rate: {rate:.1f}%")
        
        # Show sensor stats
        stats = sensor.get_stats()
        logger.info(f"Events: {stats['events']}")
        logger.info("Simulation finished")


# ============================================
# CONFIGURATION VALIDATION
# ============================================

def validate_configuration():
    """Validate the configuration and suggest fixes"""
    issues = []
    warnings = []
    
    # Check endpoint
    if ENDPOINT == "YOUR_IOT_ENDPOINT.iot.region.amazonaws.com":
        warnings.append("AWS IoT endpoint not configured")
        warnings.append("  Set AWS_IOT_ENDPOINT environment variable")
    
    # Check certificate paths
    for path, name in [
        (CERT_PATH, "Certificate"),
        (PRIVATE_KEY_PATH, "Private Key"),
        (ROOT_CA_PATH, "Root CA")
    ]:
        if not os.path.exists(path):
            warnings.append(f"{name} file not found: {path}")
    
    # Check interval
    if INTERVAL < 1:
        issues.append(f"Invalid interval: {INTERVAL} (must be >= 1)")
    
    # Check sensor ID
    if not SENSOR_ID or len(SENSOR_ID) > 100:
        issues.append(f"Invalid sensor ID: {SENSOR_ID}")
    
    return issues, warnings


# ============================================
# MAIN PROGRAM
# ============================================

def main():
    """
    Main function: Parse arguments and start the simulation
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Smart Garden Manager - IoT Sensor Simulator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Online mode with default settings
  python sensor_simulator.py
  
  # Online mode with WebSocket (port 443) - recommended for firewalls
  python sensor_simulator.py --websocket
  
  # Offline mode for testing
  python sensor_simulator.py --offline
  
  # Send data every 30 seconds
  python sensor_simulator.py --interval 30
  
  # Use greenhouse location
  python sensor_simulator.py --location greenhouse
  
  # Load configuration from .env file
  python sensor_simulator.py --env
        """
    )
    parser.add_argument(
        '--offline',
        action='store_true',
        help='Run in offline mode (print data only, no AWS connection)'
    )
    parser.add_argument(
        '--websocket',
        action='store_true',
        help='Use WebSocket connection (port 443) instead of MQTT (port 8883)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=INTERVAL,
        help=f'Interval between readings in seconds (default: {INTERVAL})'
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
        help=f'Sensor location (default: {LOCATION})'
    )
    parser.add_argument(
        '--env',
        action='store_true',
        help='Load configuration from .env file'
    )
    parser.add_argument(
        '--max-readings',
        type=int,
        default=None,
        help='Maximum number of readings to send (for testing)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration and exit'
    )
    
    args = parser.parse_args()
    
    # Load .env file if requested or if available
    if args.env:
        if DOTENV_AVAILABLE:
            # Try to find .env file in current or parent directories
            env_path = Path.cwd() / '.env'
            if not env_path.exists():
                env_path = Path.cwd().parent / '.env'
            if env_path.exists():
                load_dotenv(env_path)
                logger.info(f"Loaded .env from: {env_path}")
                # Reload configuration from environment - NO global needed!
                # Just update the variables in the current scope
                endpoint = os.getenv("AWS_IOT_ENDPOINT", ENDPOINT)
                topic = os.getenv("AWS_IOT_TOPIC", TOPIC)
                interval = int(os.getenv("SENSOR_INTERVAL", str(INTERVAL)))
                sensor_id = os.getenv("SENSOR_ID", SENSOR_ID)
                location = os.getenv("SENSOR_LOCATION", LOCATION)
                use_websocket = os.getenv("USE_WEBSOCKET", "false").lower() in ["true", "1", "yes"]
                cert_path = os.getenv("CERT_PATH", CERT_PATH)
                private_key_path = os.getenv("PRIVATE_KEY_PATH", PRIVATE_KEY_PATH)
                root_ca_path = os.getenv("ROOT_CA_PATH", ROOT_CA_PATH)
            else:
                logger.warning(f".env file not found in {Path.cwd()} or parent")
                endpoint = ENDPOINT
                topic = TOPIC
                interval = INTERVAL
                sensor_id = SENSOR_ID
                location = LOCATION
                use_websocket = USE_WEBSOCKET
                cert_path = CERT_PATH
                private_key_path = PRIVATE_KEY_PATH
                root_ca_path = ROOT_CA_PATH
        else:
            logger.warning("python-dotenv not installed. Install with: pip install python-dotenv")
            endpoint = ENDPOINT
            topic = TOPIC
            interval = INTERVAL
            sensor_id = SENSOR_ID
            location = LOCATION
            use_websocket = USE_WEBSOCKET
            cert_path = CERT_PATH
            private_key_path = PRIVATE_KEY_PATH
            root_ca_path = ROOT_CA_PATH
    else:
        # Use global configuration
        endpoint = ENDPOINT
        topic = TOPIC
        interval = INTERVAL
        sensor_id = SENSOR_ID
        location = LOCATION
        use_websocket = USE_WEBSOCKET
        cert_path = CERT_PATH
        private_key_path = PRIVATE_KEY_PATH
        root_ca_path = ROOT_CA_PATH
    
    # Command line argument overrides environment
    if args.websocket:
        use_websocket = True
    if args.interval != INTERVAL:
        interval = args.interval
    if args.sensor_id != SENSOR_ID:
        sensor_id = args.sensor_id
    if args.location != LOCATION:
        location = args.location
    
    # Validate configuration
    issues, warnings = validate_configuration()
    
    if warnings:
        for w in warnings:
            logger.warning(w)
    
    if issues:
        for i in issues:
            logger.error(i)
        sys.exit(1)
    
    if args.validate:
        logger.info("Configuration validation passed")
        logger.info(f"Endpoint: {endpoint}")
        logger.info(f"Topic: {topic}")
        logger.info(f"WebSocket: {use_websocket}")
        sys.exit(0)
    
    # Run in appropriate mode
    if args.offline:
        run_offline_simulation(
            sensor_id=sensor_id,
            interval=interval,
            location=location,
            max_readings=args.max_readings
        )
    else:
        run_online_simulation(
            endpoint=endpoint,
            topic=topic,
            cert_path=cert_path,
            private_key_path=private_key_path,
            root_ca_path=root_ca_path,
            sensor_id=sensor_id,
            interval=interval,
            location=location,
            max_readings=args.max_readings,
            use_websocket=use_websocket
        )


if __name__ == "__main__":
    main()
