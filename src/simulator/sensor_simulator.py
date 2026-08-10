#!/usr/bin/env python3
"""
Smart Garden Manager - IoT Sensor Simulator
============================================

Generates realistic Smart Garden sensor data and supports three
data transmission modes:

1. Offline:
   Generate and display sensor data locally.

2. API Gateway:
   Send sensor data via HTTPS POST to Amazon API Gateway.

3. MQTT:
   Send sensor data via MQTT to AWS IoT Core using certificates.

Examples:

    # Offline - one reading every 60 seconds
    python sensor_simulator.py --offline --interval 60

    # Offline - generate only 5 readings
    python sensor_simulator.py --offline --interval 2 --max-readings 5

    # API Gateway
    python sensor_simulator.py --api --interval 60

    # API Gateway with custom URL
    python sensor_simulator.py --api \
        --api-url "https://YOUR_API.execute-api.us-west-2.amazonaws.com/prod/data"

    # AWS IoT Core / MQTT
    python sensor_simulator.py --mqtt --interval 60

    # MQTT using WebSocket port 443
    python sensor_simulator.py --mqtt --websocket --interval 60

    # Different sensor
    python sensor_simulator.py --api \
        --sensor-id sensor-002 \
        --location greenhouse \
        --interval 60

Dependencies:

    Offline:
        Python standard library only

    API Gateway:
        pip install requests

    MQTT:
        pip install AWSIoTPythonSDK

Optional:
        pip install python-dotenv
"""

import argparse
import datetime
import json
import os
import random
import sys
import time
from pathlib import Path


# ============================================================
# OPTIONAL DEPENDENCIES
# ============================================================

try:
    import requests

    REQUESTS_AVAILABLE = True

except ImportError:
    REQUESTS_AVAILABLE = False


try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True

except ImportError:
    DOTENV_AVAILABLE = False


# ============================================================
# DEFAULT CONFIGURATION
# ============================================================

# FIXED: These are now empty placeholders.
# They will be updated AFTER loading the .env file.
DEFAULT_API_URL = ""
DEFAULT_IOT_ENDPOINT = ""
DEFAULT_IOT_TOPIC = "sensor/data"
DEFAULT_INTERVAL = 60
DEFAULT_SENSOR_ID = "sensor-001"
DEFAULT_LOCATION = "indoor"
DEFAULT_CERT_PATH = "./certs/device-certificate.pem.crt"
DEFAULT_PRIVATE_KEY_PATH = "./certs/device-private-key.pem.key"
DEFAULT_ROOT_CA_PATH = "./certs/root-CA.crt"
DEFAULT_LOG_LEVEL = "INFO"


# ============================================================
# LOGGER
# ============================================================

class Logger:
    """Simple console logger."""

    LEVELS = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4
    }

    def __init__(self, level="INFO"):
        self.level = self.LEVELS.get(
            level.upper(),
            1
        )

    def _log(
        self,
        level,
        message
    ):
        if self.LEVELS.get(level, 1) >= self.level:

            timestamp = datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            print(
                f"[{timestamp}] "
                f"[{level}] "
                f"{message}"
            )

    def debug(self, message):
        self._log("DEBUG", message)

    def info(self, message):
        self._log("INFO", message)

    def warning(self, message):
        self._log("WARNING", message)

    def error(self, message):
        self._log("ERROR", message)

    def critical(self, message):
        self._log("CRITICAL", message)


logger = Logger(DEFAULT_LOG_LEVEL)


# ============================================================
# SENSOR
# ============================================================

class SmartGardenSensor:
    """
    Simulated Smart Garden sensor.

    Generates:
        - temperature
        - humidity
        - soil moisture
        - battery level
        - timestamp
    """

    def __init__(
        self,
        sensor_id="sensor-001",
        location="indoor",
        seed=None
    ):

        self.sensor_id = sensor_id
        self.location = location
        self.reading_count = 0

        if seed is not None:
            random.seed(seed)

        # ----------------------------------------------------
        # Location-specific base values
        # ----------------------------------------------------

        if location == "outdoor":

            self.base_temp = 22.0
            self.temp_range = 10.0

            self.base_humidity = 60.0
            self.humidity_range = 25.0

            self.base_moisture = 50.0
            self.moisture_range = 30.0

        elif location == "greenhouse":

            self.base_temp = 25.0
            self.temp_range = 5.0

            self.base_humidity = 70.0
            self.humidity_range = 15.0

            self.base_moisture = 65.0
            self.moisture_range = 15.0

        else:

            self.base_temp = 21.0
            self.temp_range = 3.0

            self.base_humidity = 50.0
            self.humidity_range = 10.0

            self.base_moisture = 45.0
            self.moisture_range = 20.0

        # ----------------------------------------------------
        # Trends
        # ----------------------------------------------------

        self.moisture_trend = 0
        self.temperature_trend = 0

        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------

        self.stats = {
            "total_readings": 0,
            "events": {
                "rain": 0,
                "heatwave": 0,
                "drought": 0
            }
        }

        logger.info(
            f"Sensor initialized: {self.sensor_id}"
        )

        logger.info(
            f"Location: {self.location}"
        )

    # --------------------------------------------------------
    # Time of day
    # --------------------------------------------------------

    def _calculate_time_factor(self):

        hour = datetime.datetime.now().hour

        if 6 <= hour <= 18:

            return (hour - 6) / 12

        return 0

    # --------------------------------------------------------
    # Weather events
    # --------------------------------------------------------

    def _apply_weather_events(
        self,
        temperature,
        humidity,
        moisture
    ):

        # Rain
        rain_chance = (
            0.01
            + (humidity - 50) * 0.0005
        )

        rain_chance = max(
            0.005,
            min(0.05, rain_chance)
        )

        if random.random() < rain_chance:

            rain_amount = random.uniform(
                5,
                25
            )

            moisture += rain_amount

            humidity += random.uniform(
                2,
                8
            )

            self.stats["events"]["rain"] += 1

            logger.info(
                f"Rain event: "
                f"+{rain_amount:.1f}% moisture"
            )

        # Heat wave
        if (
            random.random() < 0.005
            and humidity < 60
        ):

            heat_amount = random.uniform(
                3,
                7
            )

            temperature += heat_amount

            humidity -= random.uniform(
                2,
                5
            )

            self.stats["events"]["heatwave"] += 1

            logger.info(
                f"Heat wave: "
                f"+{heat_amount:.1f}C"
            )

        # Drought
        if (
            random.random() < 0.002
            and moisture < 40
        ):

            drought_amount = random.uniform(
                3,
                8
            )

            moisture -= drought_amount

            humidity -= random.uniform(
                1,
                3
            )

            self.stats["events"]["drought"] += 1

            logger.info(
                f"Drought event: "
                f"-{drought_amount:.1f}% moisture"
            )

        return (
            temperature,
            humidity,
            moisture
        )

    # --------------------------------------------------------
    # Trends
    # --------------------------------------------------------

    def _update_trends(self):

        # Simulated watering every 100 readings

        if (
            self.reading_count > 0
            and self.reading_count % 100 == 0
        ):

            watering = random.uniform(
                5,
                15
            )

            self.moisture_trend += watering

            logger.debug(
                f"Watering cycle: "
                f"+{watering:.1f}% moisture"
            )

        # Natural moisture decrease

        decrease = random.uniform(
            0.1,
            0.5
        )

        self.moisture_trend -= decrease

        # Temperature drift

        self.temperature_trend += random.uniform(
            -0.05,
            0.05
        )

        self.temperature_trend = max(
            -2,
            min(2, self.temperature_trend)
        )

        # Clamp moisture trend

        self.moisture_trend = max(
            -20,
            min(20, self.moisture_trend)
        )

    # --------------------------------------------------------
    # Generate sensor reading
    # --------------------------------------------------------

    def generate_reading(self):

        self.reading_count += 1

        self.stats["total_readings"] = (
            self.reading_count
        )

        time_factor = (
            self._calculate_time_factor()
        )

        noise = random.uniform(
            -0.5,
            0.5
        )

        # Temperature

        temperature = (
            self.base_temp
            + time_factor * 5.0
            + self.temperature_trend
            + noise * 2.0
            + random.gauss(0, 0.3)
        )

        temperature = max(
            15,
            min(40, temperature)
        )

        # Humidity

        humidity = (
            self.base_humidity
            - time_factor * 15.0
            + noise * 5.0
            + random.gauss(0, 1.0)
        )

        humidity = max(
            20,
            min(90, humidity)
        )

        # Soil moisture

        self._update_trends()

        moisture = (
            self.base_moisture
            + self.moisture_trend
            + random.gauss(0, 2.0)
        )

        (
            temperature,
            humidity,
            moisture
        ) = self._apply_weather_events(
            temperature,
            humidity,
            moisture
        )

        moisture = max(
            10,
            min(90, moisture)
        )

        # UTC timestamp

        timestamp = (
            datetime.datetime.utcnow()
            .isoformat()
            + "Z"
        )

        reading = {

            "sensor_id": self.sensor_id,

            "timestamp": timestamp,

            "temperature": round(
                temperature,
                1
            ),

            "humidity": round(
                humidity,
                1
            ),

            "soil_moisture": round(
                moisture,
                1
            ),

            "location": self.location,

            "reading_id": (
                f"{self.sensor_id}-"
                f"{self.reading_count:06d}"
            ),

            "battery": round(
                random.uniform(85, 100),
                1
            )
        }

        return reading

    # --------------------------------------------------------
    # Print reading
    # --------------------------------------------------------

    def print_reading(
        self,
        reading
    ):

        logger.info(
            f"READING "
            f"{self.reading_count:06d} | "
            f"T: "
            f"{reading['temperature']:5.1f}C | "
            f"H: "
            f"{reading['humidity']:5.1f}% | "
            f"M: "
            f"{reading['soil_moisture']:5.1f}% | "
            f"Batt: "
            f"{reading['battery']:4.1f}%"
        )

    def get_stats(self):

        return self.stats


# ============================================================
# API GATEWAY CLIENT
# ============================================================

class APIGatewayClient:
    """
    Sends sensor data to Amazon API Gateway
    using HTTPS POST.
    """

    def __init__(
        self,
        api_url,
        timeout=15
    ):

        self.api_url = api_url
        self.timeout = timeout

    def validate(self):

        if not self.api_url:

            logger.error(
                "API Gateway URL is not configured."
            )

            logger.info(
                "Use:"
            )

            logger.info(
                '  --api-url "https://YOUR_API_URL"'
            )

            logger.info(
                "or set:"
            )

            logger.info(
                "  SMART_GARDEN_API_URL"
            )

            return False

        if not (
            self.api_url.startswith(
                "https://"
            )
            or self.api_url.startswith(
                "http://"
            )
        ):

            logger.error(
                "Invalid API URL. "
                "URL must start with http:// or https://"
            )

            return False

        return True

    def send(
        self,
        reading
    ):

        if not REQUESTS_AVAILABLE:

            logger.error(
                "Python package 'requests' is not installed."
            )

            logger.info(
                "Install it with:"
            )

            logger.info(
                "pip install requests"
            )

            return False

        try:

            response = requests.post(
                self.api_url,
                json=reading,
                headers={
                    "Content-Type":
                    "application/json"
                },
                timeout=self.timeout
            )

            if 200 <= response.status_code < 300:

                logger.info(
                    f"API OK "
                    f"[HTTP {response.status_code}] "
                    f"reading_id="
                    f"{reading['reading_id']}"
                )

                return True

            logger.error(
                f"API request failed: "
                f"HTTP {response.status_code}"
            )

            if response.text:

                logger.error(
                    f"Response: "
                    f"{response.text[:500]}"
                )

            return False

        except requests.exceptions.Timeout:

            logger.error(
                "API request timed out."
            )

            return False

        except requests.exceptions.ConnectionError:

            logger.error(
                "Could not connect to API Gateway."
            )

            return False

        except Exception as error:

            logger.error(
                f"API request error: {error}"
            )

            return False


# ============================================================
# MQTT CLIENT
# ============================================================

class IoTMQTTClient:
    """
    MQTT client for AWS IoT Core.

    Supports:
        - MQTT port 8883
        - WebSocket port 443
    """

    def __init__(
        self,
        endpoint,
        cert_path,
        private_key_path,
        root_ca_path,
        client_id=None,
        use_websocket=False
    ):

        self.endpoint = endpoint

        self.cert_path = cert_path

        self.private_key_path = (
            private_key_path
        )

        self.root_ca_path = (
            root_ca_path
        )

        self.client_id = (
            client_id
            or f"smart-garden-{random.randint(1000, 9999)}"
        )

        self.use_websocket = (
            use_websocket
        )

        self.mqtt_client = None

        self.connected = False

        self.connection_attempts = 0

        self.max_retries = 3

    # --------------------------------------------------------
    # Certificate validation
    # --------------------------------------------------------

    def check_certificates(self):

        missing = []

        certificate_files = [

            (
                self.cert_path,
                "Device certificate"
            ),

            (
                self.private_key_path,
                "Private key"
            ),

            (
                self.root_ca_path,
                "Root CA"
            )
        ]

        for path, name in certificate_files:

            if not os.path.exists(path):

                missing.append(
                    f"{name}: {path}"
                )

        if missing:

            logger.error(
                "Missing MQTT certificate files:"
            )

            for item in missing:

                logger.error(
                    f"  {item}"
                )

            return False

        return True

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    def connect(self):

        try:

            from AWSIoTPythonSDK.MQTTLib import (
                AWSIoTMQTTClient
            )

        except ImportError:

            logger.error(
                "AWSIoTPythonSDK is not installed."
            )

            logger.info(
                "Install it with:"
            )

            logger.info(
                "pip install AWSIoTPythonSDK"
            )

            return False

        if not self.check_certificates():

            return False

        try:

            self.mqtt_client = (
                AWSIoTMQTTClient(
                    self.client_id,
                    useWebsocket=self.use_websocket
                )
            )

            if self.use_websocket:

                logger.info(
                    "Using MQTT over WebSocket "
                    "on port 443"
                )

                self.mqtt_client.configureEndpoint(
                    self.endpoint,
                    443
                )

            else:

                logger.info(
                    "Using MQTT TLS "
                    "on port 8883"
                )

                self.mqtt_client.configureEndpoint(
                    self.endpoint,
                    8883
                )

            self.mqtt_client.configureCredentials(
                self.root_ca_path,
                self.private_key_path,
                self.cert_path
            )

            self.mqtt_client.configureOfflinePublishQueueing(
                -1
            )

            self.mqtt_client.configureDrainingFrequency(
                2
            )

            self.mqtt_client.configureConnectDisconnectTimeout(
                30
            )

            self.mqtt_client.configureMQTTOperationTimeout(
                15
            )

            self.connection_attempts = 0

            while (
                self.connection_attempts
                < self.max_retries
            ):

                self.connection_attempts += 1

                try:

                    logger.info(
                        "Connecting to AWS IoT Core "
                        f"(attempt "
                        f"{self.connection_attempts}/"
                        f"{self.max_retries})..."
                    )

                    self.mqtt_client.connect()

                    self.connected = True

                    logger.info(
                        "Connected to AWS IoT Core."
                    )

                    return True

                except Exception as error:

                    logger.warning(
                        f"Connection failed: "
                        f"{error}"
                    )

                    if (
                        self.connection_attempts
                        < self.max_retries
                    ):

                        wait_seconds = (
                            2 ** self.connection_attempts
                        )

                        time.sleep(
                            wait_seconds
                        )

            return False

        except Exception as error:

            logger.error(
                f"MQTT connection error: "
                f"{error}"
            )

            return False

    # --------------------------------------------------------
    # Publish
    # --------------------------------------------------------

    def publish(
        self,
        topic,
        reading,
        qos=1
    ):

        if not self.connected:

            logger.error(
                "MQTT client is not connected."
            )

            return False

        try:

            payload = json.dumps(
                reading
            )

            self.mqtt_client.publish(
                topic,
                payload,
                qos
            )

            logger.info(
                f"MQTT OK "
                f"topic={topic} "
                f"reading_id="
                f"{reading['reading_id']}"
            )

            return True

        except Exception as error:

            logger.error(
                f"MQTT publish error: "
                f"{error}"
            )

            self.connected = False

            return False

    # --------------------------------------------------------
    # Connection status
    # --------------------------------------------------------

    def is_connected(self):

        return (
            self.connected
            and self.mqtt_client is not None
        )

    # --------------------------------------------------------
    # Disconnect
    # --------------------------------------------------------

    def disconnect(self):

        if self.mqtt_client:

            try:

                self.mqtt_client.disconnect()

            except Exception as error:

                logger.warning(
                    f"MQTT disconnect error: "
                    f"{error}"
                )

        self.connected = False

        logger.info(
            "Disconnected from AWS IoT Core."
        )


# ============================================================
# ENVIRONMENT FILE (FIXED)
# ============================================================

def load_environment_file():
    """Load .env file and update DEFAULT values"""

    if not DOTENV_AVAILABLE:
        logger.debug("python-dotenv not installed, skipping .env loading")
        return False

    current_dir = Path.cwd()

    possible_paths = [
        current_dir / ".env",                      # src/simulator/.env
        current_dir.parent / ".env",               # src/.env
        Path(__file__).resolve().parent / ".env",  # src/simulator/.env
        Path(__file__).resolve().parent.parent / ".env"  # Smart-Garden/.env
    ]

    for path in possible_paths:
        if path.exists():
            load_dotenv(
                path,
                override=True  # FIXED: override existing values
            )
            logger.info(f"Loaded environment file: {path}")
            return True

    logger.debug("No .env file found.")
    return False


# ============================================================
# UPDATE DEFAULTS FROM ENVIRONMENT (FIXED)
# ============================================================

def update_defaults_from_env():
    """Update global DEFAULT_* variables from environment"""
    global DEFAULT_API_URL, DEFAULT_IOT_ENDPOINT, DEFAULT_IOT_TOPIC
    global DEFAULT_INTERVAL, DEFAULT_SENSOR_ID, DEFAULT_LOCATION
    global DEFAULT_CERT_PATH, DEFAULT_PRIVATE_KEY_PATH, DEFAULT_ROOT_CA_PATH
    global DEFAULT_LOG_LEVEL

    # Load from environment (now available after .env loading)
    DEFAULT_API_URL = os.getenv("SMART_GARDEN_API_URL", DEFAULT_API_URL)
    DEFAULT_IOT_ENDPOINT = os.getenv("AWS_IOT_ENDPOINT", DEFAULT_IOT_ENDPOINT)
    DEFAULT_IOT_TOPIC = os.getenv("AWS_IOT_TOPIC", DEFAULT_IOT_TOPIC)

    try:
        DEFAULT_INTERVAL = int(os.getenv("SENSOR_INTERVAL", DEFAULT_INTERVAL))
    except (ValueError, TypeError):
        pass

    DEFAULT_SENSOR_ID = os.getenv("SENSOR_ID", DEFAULT_SENSOR_ID)
    DEFAULT_LOCATION = os.getenv("SENSOR_LOCATION", DEFAULT_LOCATION)
    DEFAULT_CERT_PATH = os.getenv("CERT_PATH", DEFAULT_CERT_PATH)
    DEFAULT_PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", DEFAULT_PRIVATE_KEY_PATH)
    DEFAULT_ROOT_CA_PATH = os.getenv("ROOT_CA_PATH", DEFAULT_ROOT_CA_PATH)
    DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

    # Update logger level
    global logger
    logger.level = Logger.LEVELS.get(DEFAULT_LOG_LEVEL, 1)


# ============================================================
# OFFLINE MODE
# ============================================================

def run_offline(
    sensor,
    interval,
    max_readings=None
):
    """
    Generate sensor data locally.

    No AWS service is contacted.
    """

    logger.info(
        "=" * 65
    )

    logger.info(
        "SMART GARDEN - OFFLINE MODE"
    )

    logger.info(
        "No AWS connection will be used."
    )

    logger.info(
        f"Interval: {interval} seconds"
    )

    logger.info(
        f"Sensor: {sensor.sensor_id}"
    )

    logger.info(
        f"Location: {sensor.location}"
    )

    logger.info(
        "Press CTRL+C to stop."
    )

    logger.info(
        "=" * 65
    )

    count = 0

    try:

        while (
            max_readings is None
            or count < max_readings
        ):

            reading = (
                sensor.generate_reading()
            )

            count += 1

            sensor.print_reading(
                reading
            )

            if (
                max_readings is not None
                and count >= max_readings
            ):
                break

            time.sleep(
                interval
            )

    except KeyboardInterrupt:

        logger.info(
            "Offline simulation stopped."
        )

    finally:

        logger.info(
            f"Total readings generated: "
            f"{count}"
        )


# ============================================================
# API MODE
# ============================================================

def run_api(
    sensor,
    api_url,
    interval,
    max_readings=None
):
    """
    Generate sensor data and send it to
    API Gateway using HTTPS POST.
    """

    logger.info(
        "=" * 65
    )

    logger.info(
        "SMART GARDEN - API GATEWAY MODE"
    )

    logger.info(
        f"API URL: {api_url}"
    )

    logger.info(
        f"Interval: {interval} seconds"
    )

    logger.info(
        f"Sensor: {sensor.sensor_id}"
    )

    logger.info(
        "Press CTRL+C to stop."
    )

    logger.info(
        "=" * 65
    )

    client = APIGatewayClient(
        api_url
    )

    if not client.validate():

        sys.exit(1)

    total = 0
    successful = 0
    failed = 0

    try:

        while (
            max_readings is None
            or total < max_readings
        ):

            reading = (
                sensor.generate_reading()
            )

            total += 1

            if client.send(reading):

                successful += 1

                sensor.print_reading(
                    reading
                )

            else:

                failed += 1

                logger.error(
                    f"Failed reading "
                    f"{total}"
                )

            if (
                max_readings is not None
                and total >= max_readings
            ):
                break

            time.sleep(
                interval
            )

    except KeyboardInterrupt:

        logger.info(
            "API simulation stopped."
        )

    finally:

        logger.info(
            "=" * 65
        )

        logger.info(
            "API SIMULATION STATISTICS"
        )

        logger.info(
            f"Total: {total}"
        )

        logger.info(
            f"Successful: {successful}"
        )

        logger.info(
            f"Failed: {failed}"
        )

        if total > 0:

            success_rate = (
                successful / total
            ) * 100

            logger.info(
                f"Success rate: "
                f"{success_rate:.1f}%"
            )

        logger.info(
            "=" * 65
        )


# ============================================================
# MQTT MODE
# ============================================================

def run_mqtt(
    sensor,
    endpoint,
    topic,
    cert_path,
    private_key_path,
    root_ca_path,
    interval,
    max_readings=None,
    use_websocket=False
):
    """
    Generate sensor data and send it to
    AWS IoT Core using MQTT.
    """

    logger.info(
        "=" * 65
    )

    logger.info(
        "SMART GARDEN - MQTT MODE"
    )

    logger.info(
        f"IoT Endpoint: {endpoint}"
    )

    logger.info(
        f"MQTT Topic: {topic}"
    )

    logger.info(
        f"Interval: {interval} seconds"
    )

    logger.info(
        f"Sensor: {sensor.sensor_id}"
    )

    logger.info(
        "=" * 65
    )

    mqtt_client = IoTMQTTClient(
        endpoint=endpoint,
        cert_path=cert_path,
        private_key_path=private_key_path,
        root_ca_path=root_ca_path,
        client_id=sensor.sensor_id,
        use_websocket=use_websocket
    )

    if not mqtt_client.connect():

        logger.error(
            "Could not connect to AWS IoT Core."
        )

        logger.info(
            "Check:"
        )

        logger.info(
            "1. IoT endpoint"
        )

        logger.info(
            "2. Certificate"
        )

        logger.info(
            "3. Private key"
        )

        logger.info(
            "4. Root CA"
        )

        logger.info(
            "5. IoT policy"
        )

        logger.info(
            "6. IoT Thing"
        )

        sys.exit(1)

    total = 0
    successful = 0
    failed = 0

    try:

        while (
            max_readings is None
            or total < max_readings
        ):

            # Reconnect if required

            if not mqtt_client.is_connected():

                logger.warning(
                    "MQTT connection lost. "
                    "Trying to reconnect..."
                )

                if not mqtt_client.connect():

                    logger.error(
                        "Reconnection failed."
                    )

                    time.sleep(
                        interval
                    )

                    continue

            reading = (
                sensor.generate_reading()
            )

            total += 1

            if mqtt_client.publish(
                topic,
                reading
            ):

                successful += 1

                sensor.print_reading(
                    reading
                )

            else:

                failed += 1

                logger.error(
                    f"Failed reading "
                    f"{total}"
                )

            if (
                max_readings is not None
                and total >= max_readings
            ):
                break

            time.sleep(
                interval
            )

    except KeyboardInterrupt:

        logger.info(
            "MQTT simulation stopped."
        )

    finally:

        mqtt_client.disconnect()

        logger.info(
            "=" * 65
        )

        logger.info(
            "MQTT SIMULATION STATISTICS"
        )

        logger.info(
            f"Total: {total}"
        )

        logger.info(
            f"Successful: {successful}"
        )

        logger.info(
            f"Failed: {failed}"
        )

        if total > 0:

            success_rate = (
                successful / total
            ) * 100

            logger.info(
                f"Success rate: "
                f"{success_rate:.1f}%"
            )

        logger.info(
            f"Sensor events: "
            f"{sensor.get_stats()['events']}"
        )

        logger.info(
            "=" * 65
        )


# ============================================================
# VALIDATION
# ============================================================

def validate_arguments(
    args
):

    if args.interval < 1:

        raise ValueError(
            "Interval must be at least 1 second."
        )

    if args.max_readings is not None:

        if args.max_readings < 1:

            raise ValueError(
                "max-readings must be at least 1."
            )

    if args.mode is None:

        raise ValueError(
            "Select exactly one mode: "
            "--offline, --api or --mqtt"
        )


# ============================================================
# ARGUMENT PARSER
# ============================================================

def create_parser():

    parser = argparse.ArgumentParser(

        description=(
            "Smart Garden Manager "
            "IoT Sensor Simulator"
        ),

        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),

        epilog="""

EXAMPLES

Offline testing:
    python sensor_simulator.py --offline

Offline testing every 60 seconds:
    python sensor_simulator.py --offline --interval 60

Offline test with 3 readings:
    python sensor_simulator.py --offline --interval 2 --max-readings 3

API Gateway:
    python sensor_simulator.py --api --interval 60

API Gateway with URL:
    python sensor_simulator.py --api ^
        --api-url "https://xxxxx.execute-api.us-west-2.amazonaws.com/prod/data"

MQTT / AWS IoT Core:
    python sensor_simulator.py --mqtt --interval 60

MQTT using WebSocket:
    python sensor_simulator.py --mqtt --websocket --interval 60

Greenhouse sensor:
    python sensor_simulator.py --api ^
        --sensor-id sensor-002 ^
        --location greenhouse ^
        --interval 60

Show help:
    python sensor_simulator.py --help

"""
    )

    # --------------------------------------------------------
    # MODE
    # --------------------------------------------------------

    mode_group = parser.add_mutually_exclusive_group(
        required=True
    )

    mode_group.add_argument(
        "--offline",
        dest="mode",
        action="store_const",
        const="offline",
        help=(
            "Generate data locally. "
            "No AWS connection."
        )
    )

    mode_group.add_argument(
        "--api",
        dest="mode",
        action="store_const",
        const="api",
        help=(
            "Send sensor data via "
            "HTTPS to API Gateway."
        )
    )

    mode_group.add_argument(
        "--mqtt",
        dest="mode",
        action="store_const",
        const="mqtt",
        help=(
            "Send sensor data via MQTT "
            "to AWS IoT Core."
        )
    )

    # --------------------------------------------------------
    # INTERVAL
    # --------------------------------------------------------

    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=(
            "Seconds between readings. "
            f"Default: {DEFAULT_INTERVAL}"
        )
    )

    # --------------------------------------------------------
    # SENSOR
    # --------------------------------------------------------

    parser.add_argument(
        "--sensor-id",
        type=str,
        default=DEFAULT_SENSOR_ID,
        help=(
            "Sensor identifier. "
            f"Default: {DEFAULT_SENSOR_ID}"
        )
    )

    parser.add_argument(
        "--location",
        type=str,
        choices=[
            "indoor",
            "outdoor",
            "greenhouse"
        ],
        default=DEFAULT_LOCATION,
        help=(
            "Sensor location. "
            f"Default: {DEFAULT_LOCATION}"
        )
    )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    parser.add_argument(
        "--api-url",
        type=str,
        default=DEFAULT_API_URL,
        help=(
            "API Gateway POST endpoint. "
            "Can also be provided using "
            "SMART_GARDEN_API_URL."
        )
    )

    # --------------------------------------------------------
    # MQTT
    # --------------------------------------------------------

    parser.add_argument(
        "--iot-endpoint",
        type=str,
        default=DEFAULT_IOT_ENDPOINT,
        help=(
            "AWS IoT Core endpoint."
        )
    )

    parser.add_argument(
        "--topic",
        type=str,
        default=DEFAULT_IOT_TOPIC,
        help=(
            "AWS IoT MQTT topic. "
            f"Default: {DEFAULT_IOT_TOPIC}"
        )
    )

    parser.add_argument(
        "--cert",
        type=str,
        default=DEFAULT_CERT_PATH,
        help=(
            "Device certificate path."
        )
    )

    parser.add_argument(
        "--private-key",
        type=str,
        default=DEFAULT_PRIVATE_KEY_PATH,
        help=(
            "Device private key path."
        )
    )

    parser.add_argument(
        "--root-ca",
        type=str,
        default=DEFAULT_ROOT_CA_PATH,
        help=(
            "Root CA certificate path."
        )
    )

    parser.add_argument(
        "--websocket",
        action="store_true",
        help=(
            "Use MQTT over WebSocket "
            "on port 443 instead of "
            "MQTT TLS on port 8883."
        )
    )

    # --------------------------------------------------------
    # TESTING
    # --------------------------------------------------------

    parser.add_argument(
        "--max-readings",
        type=int,
        default=None,
        help=(
            "Stop after a specified "
            "number of readings."
        )
    )

    parser.add_argument(
        "--env",
        action="store_true",
        help=(
            "Load configuration from "
            ".env file."
        )
    )

    return parser


# ============================================================
# MAIN (FIXED)
# ============================================================

def main():

    # Load .env before using configuration
    load_environment_file()

    # Update defaults from environment
    update_defaults_from_env()

    parser = create_parser()

    args = parser.parse_args()

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    try:

        validate_arguments(
            args
        )

    except ValueError as error:

        logger.error(
            str(error)
        )

        parser.print_help()

        sys.exit(1)

    # --------------------------------------------------------
    # Sensor
    # --------------------------------------------------------

    sensor = SmartGardenSensor(

        sensor_id=args.sensor_id,

        location=args.location
    )

    # --------------------------------------------------------
    # Print configuration
    # --------------------------------------------------------

    logger.info(
        "=" * 65
    )

    logger.info(
        "SMART GARDEN SENSOR SIMULATOR"
    )

    logger.info(
        f"Mode: {args.mode.upper()}"
    )

    logger.info(
        f"Sensor ID: {args.sensor_id}"
    )

    logger.info(
        f"Location: {args.location}"
    )

    logger.info(
        f"Interval: {args.interval} seconds"
    )

    logger.info(
        "=" * 65
    )

    # --------------------------------------------------------
    # OFFLINE
    # --------------------------------------------------------

    if args.mode == "offline":

        run_offline(

            sensor=sensor,

            interval=args.interval,

            max_readings=args.max_readings
        )

        return

    # --------------------------------------------------------
    # API GATEWAY
    # --------------------------------------------------------

    if args.mode == "api":

        run_api(

            sensor=sensor,

            api_url=args.api_url,

            interval=args.interval,

            max_readings=args.max_readings
        )

        return

    # --------------------------------------------------------
    # MQTT
    # --------------------------------------------------------

    if args.mode == "mqtt":

        run_mqtt(

            sensor=sensor,

            endpoint=args.iot_endpoint,

            topic=args.topic,

            cert_path=args.cert,

            private_key_path=args.private_key,

            root_ca_path=args.root_ca,

            interval=args.interval,

            max_readings=args.max_readings,

            use_websocket=args.websocket
        )

        return


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()