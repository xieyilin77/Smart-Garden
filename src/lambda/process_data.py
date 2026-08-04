#!/usr/bin/env python3
"""
Smart Garden Manager - Data Processing Lambda
===============================================
AWS Lambda function for processing IoT sensor data.

Features:
    - Parses data from IoT Core and API Gateway
    - Stores current values in DynamoDB
    - Archives historical data in S3 (with batching)
    - Threshold-based alerting via SNS
    - Comprehensive error handling and logging
    - Offline testing mode

Environment Variables:
    LATEST_TABLE: DynamoDB table name for latest values
    HISTORY_TABLE: DynamoDB table name for historical data
    DATA_BUCKET: S3 bucket name for data archive
    SNS_TOPIC_ARN: SNS topic ARN for alerts
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
    DEBUG: Enable debug mode (true/false)
"""

import json
import os
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
import boto3
from botocore.exceptions import ClientError

# ============================================
# LOGGING CONFIGURATION
# ============================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEBUG_MODE = os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]

logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# Add structured logging for AWS
if DEBUG_MODE:
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# ============================================
# OFFLINE TEST MODE - Setup environment
# ============================================

def is_running_in_aws() -> bool:
    """Check if running in AWS Lambda environment"""
    return 'AWS_EXECUTION_ENV' in os.environ or 'LAMBDA_TASK_ROOT' in os.environ

if not is_running_in_aws():
    # Running locally - set environment variables for testing
    os.environ.setdefault('LATEST_TABLE', 'smart-garden-sensor-latest')
    os.environ.setdefault('HISTORY_TABLE', 'smart-garden-sensor-data')
    os.environ.setdefault('DATA_BUCKET', 'smart-garden-data-123456789')
    os.environ.setdefault('SNS_TOPIC_ARN', 'arn:aws:sns:eu-central-1:123456789:smart-garden-alerts')
    os.environ.setdefault('BATCH_SIZE', '100')
    os.environ.setdefault('BATCH_INTERVAL', '300')
    logger.info("OFFLINE MODE: Environment variables set")

# ============================================
# CUSTOM JSON ENCODER FOR DECIMAL
# ============================================

class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat() + 'Z'
        return super().default(obj)

# ============================================
# MOCK CLASSES FOR OFFLINE TESTING
# ============================================

class MockTable:
    """Mock DynamoDB Table for offline testing"""

    def __init__(self, name):
        self.name = name
        self.data = {}
        self.history = []

    def put_item(self, Item):
        key = Item.get('sensor_id', 'unknown')
        self.data[key] = Item
        if 'timestamp' in Item:
            self.history.append(Item)
        logger.debug(f"[MOCK] Saved to {self.name}: {key}")
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

    def get_item(self, Key):
        key = Key.get('sensor_id', '')
        item = self.data.get(key, {})
        logger.debug(f"[MOCK] Retrieved from {self.name}: {key}")
        return {'Item': item}

    def query(self, **kwargs):
        logger.debug(f"[MOCK] Query on {self.name}")
        return {'Items': []}


class MockDynamoDB:
    """Mock DynamoDB Resource"""
    def Table(self, name):
        return MockTable(name)


class MockS3:
    """Mock S3 Client"""
    
    def __init__(self):
        self.objects = {}
    
    def put_object(self, **kwargs):
        key = kwargs.get('Key', 'unknown')
        body = kwargs.get('Body', '')
        self.objects[key] = body
        logger.debug(f"[MOCK] Archived to S3: {key} (size: {len(body)} bytes)")
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}
    
    def get_object(self, **kwargs):
        key = kwargs.get('Key', '')
        return {'Body': self.objects.get(key, '')}


class MockSNS:
    """Mock SNS Client"""
    
    def __init__(self):
        self.messages = []
    
    def publish(self, **kwargs):
        message = kwargs.get('Message', '')
        subject = kwargs.get('Subject', '')
        self.messages.append({'subject': subject, 'message': message})
        logger.debug(f"[MOCK] Alert sent: {subject}")
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}


# ============================================
# INITIALIZE CLIENTS (Auto-detect mode)
# ============================================

if is_running_in_aws():
    # Running in AWS - use real services
    dynamodb = boto3.resource('dynamodb')
    s3 = boto3.client('s3')
    sns = boto3.client('sns')
    table_latest = dynamodb.Table(os.environ['LATEST_TABLE'])
    table_history = dynamodb.Table(os.environ['HISTORY_TABLE'])
    data_bucket = os.environ['DATA_BUCKET']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    logger.info("AWS MODE: Using real AWS services")
else:
    # Running locally - use mocks
    logger.info("OFFLINE MODE: Using mock AWS services")
    dynamodb = MockDynamoDB()
    s3 = MockS3()
    sns = MockSNS()
    table_latest = dynamodb.Table(os.environ['LATEST_TABLE'])
    table_history = dynamodb.Table(os.environ['HISTORY_TABLE'])
    data_bucket = os.environ['DATA_BUCKET']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    logger.info("Mock services initialized")

# ============================================
# THRESHOLD CONFIGURATION
# ============================================

THRESHOLDS = {
    'soil_moisture_low': float(os.getenv('THRESHOLD_MOISTURE_LOW', '30')),
    'soil_moisture_high': float(os.getenv('THRESHOLD_MOISTURE_HIGH', '80')),
    'temperature_high': float(os.getenv('THRESHOLD_TEMP_HIGH', '35')),
    'temperature_low': float(os.getenv('THRESHOLD_TEMP_LOW', '5')),
    'humidity_low': float(os.getenv('THRESHOLD_HUMIDITY_LOW', '40')),
    'humidity_high': float(os.getenv('THRESHOLD_HUMIDITY_HIGH', '90')),
}

BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
BATCH_INTERVAL = int(os.getenv('BATCH_INTERVAL', '300'))


# ============================================
# HELPER FUNCTIONS
# ============================================

def parse_event(event: Dict) -> Dict:
    """
    Parse event from different sources.
    
    Supports:
    - IoT Core: Direct JSON with sensor data
    - API Gateway: JSON wrapped in 'body' field
    - SQS: Records array with body field
    
    Args:
        event: Lambda event
    
    Returns:
        dict: Parsed data
    """
    # Case 1: Direct sensor data
    if isinstance(event, dict):
        if 'sensor_id' in event and ('temperature' in event or 'soil_moisture' in event):
            return event
    
    # Case 2: API Gateway wrapping
    if isinstance(event, dict) and 'body' in event:
        try:
            body = event['body']
            if isinstance(body, str):
                return json.loads(body)
            return body
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse body: {e}")
            return event
    
    # Case 3: SQS records
    if isinstance(event, dict) and 'Records' in event:
        for record in event['Records']:
            if 'body' in record:
                try:
                    body = json.loads(record['body'])
                    if 'sensor_id' in body:
                        return body
                except json.JSONDecodeError:
                    continue
    
    # Case 4: Fallback - return event as is
    return event

def validate_data(data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate sensor data
    
    Args:
        data: Sensor data to validate
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
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
    """
    Check data against thresholds
    
    Args:
        data: Sensor data
    
    Returns:
        List[str]: List of alert messages
    """
    alerts = []
    
    temperature = float(data.get('temperature', 0))
    humidity = float(data.get('humidity', 0))
    soil_moisture = float(data.get('soil_moisture', 0))
    
    # Soil moisture alerts
    if soil_moisture < THRESHOLDS['soil_moisture_low']:
        alerts.append(
            f"Low soil moisture: {soil_moisture:.1f}% "
            f"(threshold: {THRESHOLDS['soil_moisture_low']}%)"
        )
    
    if soil_moisture > THRESHOLDS['soil_moisture_high']:
        alerts.append(
            f"High soil moisture: {soil_moisture:.1f}% "
            f"(threshold: {THRESHOLDS['soil_moisture_high']}%)"
        )
    
    # Temperature alerts
    if temperature > THRESHOLDS['temperature_high']:
        alerts.append(
            f"High temperature: {temperature:.1f}C "
            f"(threshold: {THRESHOLDS['temperature_high']}C)"
        )
    
    if temperature < THRESHOLDS['temperature_low']:
        alerts.append(
            f"Low temperature: {temperature:.1f}C "
            f"(threshold: {THRESHOLDS['temperature_low']}C)"
        )
    
    # Humidity alerts
    if humidity < THRESHOLDS['humidity_low']:
        alerts.append(
            f"Low humidity: {humidity:.1f}% "
            f"(threshold: {THRESHOLDS['humidity_low']}%)"
        )
    
    if humidity > THRESHOLDS['humidity_high']:
        alerts.append(
            f"High humidity: {humidity:.1f}% "
            f"(threshold: {THRESHOLDS['humidity_high']}%)"
        )
    
    return alerts

def send_alerts(alerts: List[str], data: Dict) -> bool:
    """
    Send alerts via SNS
    
    Args:
        alerts: List of alert messages
        data: Original sensor data
    
    Returns:
        bool: True if alerts were sent successfully
    """
    if not alerts:
        return True
    
    try:
        alert_message = (
            "SMART GARDEN ALERT\n"
            "====================\n"
            f"Sensor: {data.get('sensor_id', 'unknown')}\n"
            f"Time: {data.get('timestamp', datetime.utcnow().isoformat() + 'Z')}\n\n"
            "ALERTS DETECTED:\n"
        )
        
        for i, alert in enumerate(alerts, 1):
            alert_message += f"  {i}. {alert}\n"
        
        alert_message += (
            "\nCURRENT VALUES:\n"
            f"  - Temperature: {data.get('temperature', 0):.1f}C\n"
            f"  - Humidity: {data.get('humidity', 0):.1f}%\n"
            f"  - Soil Moisture: {data.get('soil_moisture', 0):.1f}%\n"
            f"  - Location: {data.get('location', 'unknown')}\n"
        )
        
        # Add battery if available
        if 'battery' in data:
            alert_message += f"  - Battery: {data['battery']:.1f}%\n"
        
        response = sns.publish(
            TopicArn=sns_topic_arn,
            Subject=f"Smart Garden Alert - {len(alerts)} issue(s)",
            Message=alert_message
        )
        
        logger.info(f"Alert sent: {response.get('MessageId', 'unknown')}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to send SNS alert: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending alert: {e}")
        return False

def archive_to_s3(data: Dict, timestamp: str) -> str:
    """
    Archive data to S3 with daily batching
    
    Args:
        data: Sensor data to archive
        timestamp: ISO timestamp
    
    Returns:
        str: S3 key of the archived data
    """
    try:
        # Parse timestamp for date grouping
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y/%m/%d')
        except (ValueError, TypeError):
            date_str = datetime.utcnow().strftime('%Y/%m/%d')
        
        sensor_id = data.get('sensor_id', 'unknown')
        key = f"raw-data/{sensor_id}/{date_str}/data.jsonl"
        
        # Append data in JSON Lines format
        json_line = json.dumps(data) + '\n'
        
        try:
            # Try to get existing file and append
            existing = s3.get_object(Bucket=data_bucket, Key=key)['Body'].read().decode('utf-8')
            content = existing + json_line
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                content = json_line
            else:
                logger.warning(f"S3 get error: {e}")
                content = json_line
        
        s3.put_object(
            Bucket=data_bucket,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='application/jsonl'
        )
        
        logger.debug(f"Data archived to S3: {key}")
        return key
        
    except Exception as e:
        logger.error(f"Failed to archive to S3: {e}")
        # Archive as individual file as fallback
        try:
            fallback_key = f"raw-data/{data.get('sensor_id', 'unknown')}/{timestamp.replace(':', '-')}.json"
            s3.put_object(
                Bucket=data_bucket,
                Key=fallback_key,
                Body=json.dumps(data, indent=2),
                ContentType='application/json'
            )
            logger.info(f"Archived to fallback key: {fallback_key}")
            return fallback_key
        except Exception as e2:
            logger.error(f"Fallback archiving also failed: {e2}")
            return ""


# ============================================
# MAIN LAMBDA HANDLER
# ============================================

def lambda_handler(event, context):
    """
    Main Lambda handler for processing sensor data
    
    Args:
        event: Lambda event (IoT Core or API Gateway)
        context: Lambda context
    
    Returns:
        dict: API Gateway response
    """
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    logger.info(f"Processing request {request_id}")
    
    try:
        # Parse data (supports multiple input formats)
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
        sensor_id = data.get('sensor_id', 'sensor-001')
        temperature = Decimal(str(data.get('temperature', 0)))
        humidity = Decimal(str(data.get('humidity', 0)))
        soil_moisture = Decimal(str(data.get('soil_moisture', 0)))
        timestamp = data.get('timestamp', datetime.utcnow().isoformat() + 'Z')
        
        logger.info(
            f"Processing {sensor_id}: "
            f"T={float(temperature):.1f}C, "
            f"H={float(humidity):.1f}%, "
            f"M={float(soil_moisture):.1f}%"
        )
        
        # 1. Store latest values in DynamoDB
        latest_item = {
            'sensor_id': sensor_id,
            'temperature': temperature,
            'humidity': humidity,
            'soil_moisture': soil_moisture,
            'timestamp': timestamp,
            'last_updated': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Add optional fields if present
        for field in ['location', 'battery', 'reading_id']:
            if field in data:
                latest_item[field] = data[field]
        
        try:
            table_latest.put_item(Item=latest_item)
            logger.debug(f"Latest data stored for {sensor_id}")
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
        
        # 2. Store historical data in DynamoDB
        history_item = {
            'sensor_id': sensor_id,
            'timestamp': timestamp,
            'temperature': temperature,
            'humidity': humidity,
            'soil_moisture': soil_moisture,
            'record_id': str(uuid.uuid4())
        }
        
        # Add optional fields
        for field in ['location', 'battery', 'reading_id']:
            if field in data:
                history_item[field] = data[field]
        
        try:
            table_history.put_item(Item=history_item)
            logger.debug(f"History data stored for {sensor_id}")
        except ClientError as e:
            logger.error(f"Failed to store history data: {e}")
            # Continue processing even if history storage fails
        
        # 3. Archive to S3
        try:
            s3_key = archive_to_s3(data, timestamp)
            if s3_key:
                logger.debug(f"Data archived to S3: {s3_key}")
        except Exception as e:
            logger.error(f"Failed to archive to S3: {e}")
            # Continue processing even if archiving fails
        
        # 4. Check thresholds and send alerts
        alerts = check_thresholds(data)
        if alerts:
            logger.info(f"Alerts detected: {len(alerts)}")
            for alert in alerts:
                logger.warning(f"Alert: {alert}")
            
            if sns_topic_arn:
                send_alerts(alerts, data)
        
        # 5. Return success response
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
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Invalid JSON',
                'message': str(e),
                'request_id': request_id
            })
        }
        
    except ValueError as e:
        logger.error(f"Value error: {e}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Invalid data format',
                'message': str(e),
                'request_id': request_id
            })
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
# OFFLINE TESTING
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("OFFLINE TEST MODE - Process Data Lambda")
    print("=" * 60)
    
    # Test 1: IoT Core format (direct JSON)
    test_data_1 = {
        'sensor_id': 'test-sensor-001',
        'temperature': 25.5,
        'humidity': 60.0,
        'soil_moisture': 35.0,
        'location': 'indoor',
        'battery': 87.5
    }
    
    # Test 2: Alert-triggering data (low moisture)
    test_data_2 = {
        'sensor_id': 'test-sensor-002',
        'temperature': 22.0,
        'humidity': 45.0,
        'soil_moisture': 25.0,
        'location': 'greenhouse'
    }
    
    # Test 3: API Gateway format (body wrapper)
    test_data_3 = {
        'body': json.dumps({
            'sensor_id': 'test-sensor-003',
            'temperature': 22.0,
            'humidity': 55.0,
            'soil_moisture': 70.0
        })
    }
    
    # Test 4: Multiple alerts
    test_data_4 = {
        'sensor_id': 'test-sensor-004',
        'temperature': 38.0,
        'humidity': 25.0,
        'soil_moisture': 15.0,
        'location': 'outdoor'
    }
    
    # Test 5: Invalid data
    test_data_5 = {
        'sensor_id': 'test-sensor-005',
        'temperature': 'invalid',
        'humidity': 60.0,
        'soil_moisture': 40.0
    }
    
    test_cases = [
        ('IoT Core Format (Normal)', test_data_1),
        ('IoT Core Format (Alert: Low Moisture)', test_data_2),
        ('API Gateway Format', test_data_3),
        ('IoT Core Format (Multiple Alerts)', test_data_4),
        ('Invalid Data Test', test_data_5)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_data in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {test_name}")
        print(f"{'='*60}")
        print("\nTest Data:")
        print(json.dumps(test_data, indent=2, default=str))
        print("\nSimulating Lambda execution...")
        print("-" * 50)
        
        try:
            result = lambda_handler(test_data, None)
            print("\nLambda Response:")
            print(json.dumps(json.loads(result['body']), indent=2, default=str))
            
            if result['statusCode'] == 200:
                print(f"\nTest '{test_name}' PASSED")
                passed += 1
            else:
                print(f"\nTest '{test_name}' FAILED (status: {result['statusCode']})")
                failed += 1
                
        except Exception as e:
            print(f"\nTest '{test_name}' FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"TEST SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)