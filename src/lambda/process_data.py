#!/usr/bin/env python3
"""
Smart Garden Manager - Data Processing Lambda
===============================================
AWS Lambda function for processing IoT sensor data.
"""

import json
import os
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, List, Tuple
import boto3
from botocore.exceptions import ClientError

# ============================================
# LOGGING CONFIGURATION
# ============================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]

logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# ============================================
# AWS CLIENTS
# ============================================

dynamodb = boto3.resource('dynamodb')
table_latest = dynamodb.Table(os.environ.get
                              ('LATEST_TABLE', 'smart-garden-sensor-latest'))
table_history = dynamodb.Table(os.environ.get
                               ('HISTORY_TABLE', 'smart-garden-sensor-data'))

sns = boto3.client('sns')
sns_topic_arn = os.environ.get('SNS_TOPIC_ARN', '')

s3 = boto3.client('s3')
data_bucket = os.environ.get('DATA_BUCKET', '')

# ============================================
# THRESHOLDS
# ============================================

THRESHOLDS = {
    'soil_moisture_low': float(os.getenv('THRESHOLD_MOISTURE_LOW', '30')),
    'soil_moisture_high': float(os.getenv('THRESHOLD_MOISTURE_HIGH', '80')),
    'temperature_high': float(os.getenv('THRESHOLD_TEMP_HIGH', '35')),
    'temperature_low': float(os.getenv('THRESHOLD_TEMP_LOW', '5')),
    'humidity_low': float(os.getenv('THRESHOLD_HUMIDITY_LOW', '40')),
    'humidity_high': float(os.getenv('THRESHOLD_HUMIDITY_HIGH', '90')),
}

# ============================================
# HELPER FUNCTIONS
# ============================================


def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format with Z suffix"""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat() + 'Z'
        return super().default(obj)


def safe_decimal(value) -> Decimal:
    """Safely convert any number to Decimal"""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal('0')

# ============================================
# LAMBDA HANDLER
# ============================================


def lambda_handler(event, context):
    """
    Main Lambda handler for processing sensor data
    """
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    logger.info(f"Processing request {request_id}")

    try:
        # Parse data from event
        data = parse_event(event)
        logger.debug(f"Parsed data: {json.dumps(data, default=str)}")

        # Validate data
        is_valid, error_message = validate_data(data)
        if not is_valid:
            logger.warning(f"Invalid data: {error_message}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Invalid data',
                    'message': error_message,
                    'request_id': request_id
                })
            }

        # Extract values
        sensor_id = str(data.get('sensor_id', 'sensor-001'))
        temperature = safe_decimal(data.get('temperature', 0))
        humidity = safe_decimal(data.get('humidity', 0))
        soil_moisture = safe_decimal(data.get('soil_moisture', 0))
        timestamp = data.get('timestamp', get_utc_timestamp())

        logger.info(
            f"Processing {sensor_id}: "
            f"T={float(temperature):.1f}C, "
            f"H={float(humidity):.1f}%, "
            f"M={float(soil_moisture):.1f}%"
        )

        # Latest Item for DynamoDB
        latest_item = {
            'sensor_id': sensor_id,
            'temperature': temperature,
            'humidity': humidity,
            'soil_moisture': soil_moisture,
            'timestamp': timestamp,
            'last_updated': get_utc_timestamp()
        }

        if 'location' in data:
            latest_item['location'] = str(data['location'])
        if 'battery' in data:
            latest_item['battery'] = safe_decimal(data['battery'])

        # Store latest in DynamoDB
        try:
            table_latest.put_item(Item=latest_item)
            logger.info(f"Latest data stored for {sensor_id}")
        except ClientError as e:
            logger.error(f"Failed to store latest data: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Database error',
                    'message': 'Failed to store latest data',
                    'request_id': request_id
                })
            }

        # History Item for DynamoDB
        history_item = {
            'sensor_id': sensor_id,
            'timestamp': timestamp,
            'temperature': temperature,
            'humidity': humidity,
            'soil_moisture': soil_moisture,
            'record_id': str(uuid.uuid4())
        }

        if 'location' in data:
            history_item['location'] = str(data['location'])
        if 'battery' in data:
            history_item['battery'] = safe_decimal(data['battery'])

        # Store history in DynamoDB
        try:
            table_history.put_item(Item=history_item)
            logger.info(f"History data stored for {sensor_id}")
        except ClientError as e:
            logger.error(f"Failed to store history data: {e}")

        # S3 archiving
        try:
            if data_bucket:
                archive_to_s3(data, timestamp)
        except Exception as e:
            logger.error(f"S3 archiving failed: {e}")

        # Check thresholds
        alerts = check_thresholds(data)
        if alerts:
            logger.info(f"Alerts detected: {len(alerts)}")
            for alert in alerts:
                logger.warning(f"Alert: {alert}")
            if sns_topic_arn:
                send_alerts(alerts, data)

        # Success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Data processed successfully',
                'sensor_id': sensor_id,
                'alerts': alerts,
                'alert_count': len(alerts),
                'timestamp': timestamp,
                'request_id': request_id
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e) if DEBUG_MODE else 'An unexpected error occurred',
                'request_id': request_id
            })
        }

# ============================================
# HELPER FUNCTIONS
# ============================================


def parse_event(event: Dict) -> Dict:
    """Parse event from different sources"""
    if isinstance(event, dict):
        if 'sensor_id' in event and ('temperature' in event or 'soil_moisture' in event):
            return event

    if isinstance(event, dict) and 'body' in event:
        try:
            body = event['body']
            if isinstance(body, str):
                return json.loads(body)
            return body
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse body: {e}")
            return event

    return event


def validate_data(data: Dict) -> Tuple[bool, Optional[str]]:
    """Validate sensor data"""
    required_fields = ['sensor_id', 'temperature', 'humidity', 'soil_moisture']

    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

    try:
        temp = float(data['temperature'])
        humidity = float(data['humidity'])
        moisture = float(data['soil_moisture'])

        if not (-50 <= temp <= 100):
            return False, f"Invalid temperature: {temp}"
        if not (0 <= humidity <= 100):
            return False, f"Invalid humidity: {humidity}"
        if not (0 <= moisture <= 100):
            return False, f"Invalid soil moisture: {moisture}"

    except (ValueError, TypeError) as e:
        return False, f"Invalid numeric value: {e}"

    return True, None


def check_thresholds(data: Dict) -> List[str]:
    """Check data against thresholds"""
    alerts = []

    temperature = float(data.get('temperature', 0))
    humidity = float(data.get('humidity', 0))
    soil_moisture = float(data.get('soil_moisture', 0))

    if soil_moisture < THRESHOLDS['soil_moisture_low']:
        alerts.append(f"Low soil moisture: {soil_moisture:.1f}% (threshold: {THRESHOLDS['soil_moisture_low']}%)")

    if soil_moisture > THRESHOLDS['soil_moisture_high']:
        alerts.append(f"High soil moisture: {soil_moisture:.1f}% (threshold: {THRESHOLDS['soil_moisture_high']}%)")

    if temperature > THRESHOLDS['temperature_high']:
        alerts.append(f"High temperature: {temperature:.1f}C (threshold: {THRESHOLDS['temperature_high']}C)")

    if temperature < THRESHOLDS['temperature_low']:
        alerts.append(f"Low temperature: {temperature:.1f}C (threshold: {THRESHOLDS['temperature_low']}C)")

    if humidity < THRESHOLDS['humidity_low']:
        alerts.append(f"Low humidity: {humidity:.1f}% (threshold: {THRESHOLDS['humidity_low']}%)")

    if humidity > THRESHOLDS['humidity_high']:
        alerts.append(f"High humidity: {humidity:.1f}% (threshold: {THRESHOLDS['humidity_high']}%)")

    return alerts


def send_alerts(alerts: List[str], data: Dict) -> bool:
    """Send alerts via SNS"""
    if not alerts or not sns_topic_arn:
        return True

    try:
        alert_message = (
            "SMART GARDEN ALERT\n"
            "====================\n"
            f"Sensor: {data.get('sensor_id', 'unknown')}\n"
            f"Time: {data.get('timestamp', get_utc_timestamp())}\n\n"
            "ALERTS DETECTED:\n"
        )

        for i, alert in enumerate(alerts, 1):
            alert_message += f"  {i}. {alert}\n"

        alert_message += (
            "\nCURRENT VALUES:\n"
            f"  - Temperature: {data.get('temperature', 0):.1f}C\n"
            f"  - Humidity: {data.get('humidity', 0):.1f}%\n"
            f"  - Soil Moisture: {data.get('soil_moisture', 0):.1f}%\n"
        )

        response = sns.publish(
            TopicArn=sns_topic_arn,
            Subject=f"Smart Garden Alert - {len(alerts)} issue(s)",
            Message=alert_message
        )

        logger.info(f"Alert sent: {response.get('MessageId', 'unknown')}")
        return True

    except Exception as e:
        logger.error(f"Failed to send SNS alert: {e}")
        return False


def archive_to_s3(data: Dict, timestamp: str) -> str:
    """Archive data to S3"""
    if not data_bucket:
        return ""

    try:
        sensor_id = data.get('sensor_id', 'unknown')
        ts = datetime.now(timezone.utc)
        date_path = ts.strftime("%Y/%m/%d")
        time_path = ts.strftime("%H-%M-%S-%f")
        key = f"raw-data/{sensor_id}/{date_path}/{time_path}.json"

        json_line = json.dumps(data, cls=DecimalEncoder) + '\n'

        s3.put_object(
            Bucket=data_bucket,
            Key=key,
            Body=json_line.encode('utf-8'),
            ContentType='application/jsonl'
        )

        logger.debug(f"Data archived to S3: {key}")
        return key

    except Exception as e:
        logger.error(f"Failed to archive to S3: {e}")
        return ""
