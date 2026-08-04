#!/usr/bin/env python3

import json
import os
import logging
import base64
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

# ============================================
# LOGGING CONFIGURATION
# ============================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ============================================
# OFFLINE TEST MODE - Setup environment
# ============================================

def is_running_in_aws() -> bool:
    """Check if running in AWS Lambda environment"""
    return 'AWS_EXECUTION_ENV' in os.environ or 'LAMBDA_TASK_ROOT' in os.environ

if not is_running_in_aws():
    # Running locally - set environment variables for testing
    os.environ['LATEST_TABLE'] = 'smart-garden-sensor-latest'
    os.environ['HISTORY_TABLE'] = 'smart-garden-sensor-data'
    logger.info("OFFLINE MODE: Environment variables set")

# ============================================
# MOCK CLASSES FOR OFFLINE TESTING
# ============================================

class MockTable:
    """Mock DynamoDB Table for offline testing"""
    
    def __init__(self, name: str):
        self.name = name
        self.data = {}
        self.history_data = []
        self._init_test_data()
    
    def _init_test_data(self):
        """Initialize with realistic test data"""
        # Current values for multiple sensors
        sensors = ['sensor-001', 'sensor-002', 'sensor-003']
        base_temp = [24.5, 22.1, 26.3]
        base_hum = [62.3, 55.8, 68.0]
        base_moist = [45.7, 38.2, 52.0]
        
        for i, sid in enumerate(sensors):
            self.data[sid] = {
                'sensor_id': sid,
                'temperature': base_temp[i],
                'humidity': base_hum[i],
                'soil_moisture': base_moist[i],
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'last_updated': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # Historical data (last 24 hours)
        base_time = datetime.utcnow()
        for sensor in sensors:
            for i in range(50):
                dt = base_time - timedelta(minutes=i * 5)
                # Simulate realistic variations
                temp = 20 + (i % 10) + (i % 3) * 0.5
                hum = 55 + (i % 15) + (i % 2) * 2
                moist = 40 + (i % 20) + (i % 4) * 1.5
                
                self.history_data.append({
                    'sensor_id': sensor,
                    'timestamp': dt.isoformat() + 'Z',
                    'temperature': temp,
                    'humidity': hum,
                    'soil_moisture': moist,
                    'record_id': f'record-{i:04d}'
                })
    
    def get_item(self, Key: Dict) -> Dict:
        """Mock get_item operation"""
        key = Key.get('sensor_id', '')
        item = self.data.get(key, {})
        logger.info(f"[MOCK] Retrieved from {self.name}: {key}")
        return {'Item': item}
    
    def query(self, **kwargs) -> Dict:
        """Mock query operation with filtering"""
        logger.info(f"[MOCK] Query on {self.name}")
        
        # Extract parameters
        expression_values = kwargs.get('ExpressionAttributeValues', {})
        scan_forward = kwargs.get('ScanIndexForward', False)
        limit = kwargs.get('Limit', 100)
        exclusive_start_key = kwargs.get('ExclusiveStartKey', None)
        
        # Extract sensor_id from KeyCondition
        sensor_id = 'sensor-001'  # Default
        if ':sid' in expression_values:
            sensor_id = expression_values[':sid']
        
        # Extract cutoff time if present
        cutoff_time = None
        if ':cutoff' in expression_values:
            cutoff_time = expression_values[':cutoff']
        
        # Filter data
        filtered_data = [
            item for item in self.history_data
            if item.get('sensor_id') == sensor_id
        ]
        
        # Apply time filter if cutoff provided
        if cutoff_time:
            filtered_data = [
                item for item in filtered_data
                if item.get('timestamp', '') >= cutoff_time
            ]
        
        # Sort by timestamp
        filtered_data.sort(
            key=lambda x: x.get('timestamp', ''),
            reverse=not scan_forward
        )
        
        # Apply pagination
        start_index = 0
        if exclusive_start_key:
            # Find the item in the list (simplified)
            for i, item in enumerate(filtered_data):
                if item.get('record_id') == exclusive_start_key.get('record_id'):
                    start_index = i + 1
                    break
        
        # Apply limit
        result = filtered_data[start_index:start_index + limit]
        
        # Set LastEvaluatedKey if there are more results
        last_evaluated_key = None
        if len(filtered_data) > start_index + limit:
            last_evaluated_key = {
                'sensor_id': sensor_id,
                'timestamp': result[-1].get('timestamp', ''),
                'record_id': result[-1].get('record_id', '')
            }
        
        logger.info(f"[MOCK] Returned {len(result)} items")
        return {
            'Items': result,
            'LastEvaluatedKey': last_evaluated_key
        }

class MockDynamoDB:
    """Mock DynamoDB Resource"""
    def Table(self, name: str) -> MockTable:
        return MockTable(name)

# ============================================
# INITIALIZE CLIENTS (Auto-detect mode)
# ============================================

if is_running_in_aws():
    # Running in AWS - use real services
    dynamodb = boto3.resource('dynamodb')
    table_latest = dynamodb.Table(os.environ['LATEST_TABLE'])
    table_history = dynamodb.Table(os.environ['HISTORY_TABLE'])
    logger.info("AWS MODE: Using real AWS services")
else:
    # Running locally - use mocks
    logger.info("OFFLINE MODE: Using mock AWS services")
    dynamodb = MockDynamoDB()
    table_latest = dynamodb.Table(os.environ['LATEST_TABLE'])
    table_history = dynamodb.Table(os.environ['HISTORY_TABLE'])
    logger.info("Mock services initialized")

# ============================================
# CUSTOM JSON ENCODER
# ============================================

class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat() + 'Z'
        return super(DecimalEncoder, self).default(obj)

# ============================================
# HELPER FUNCTIONS
# ============================================

def validate_sensor_id(sensor_id: str) -> bool:
    """
    Validate sensor ID format
    
    Args:
        sensor_id: Sensor ID to validate
    
    Returns:
        bool: True if valid
    """
    if not sensor_id:
        return False
    if len(sensor_id) > 100:
        return False
    # Allow: letters, numbers, hyphens, underscores
    import re
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, sensor_id))

def validate_hours(hours: int) -> int:
    """
    Validate and limit hours parameter
    
    Args:
        hours: Requested hours
    
    Returns:
        int: Validated hours (1-720)
    """
    if hours <= 0:
        return 24
    if hours > 720:  # Max 30 days
        return 720
    return hours

def validate_limit(limit: int) -> int:
    """
    Validate and limit results count
    
    Args:
        limit: Requested limit
    
    Returns:
        int: Validated limit (1-500)
    """
    if limit <= 0:
        return 100
    if limit > 500:
        return 500
    return limit

def calculate_statistics(history: List[Dict]) -> Dict:
    """
    Calculate statistics from historical data
    
    Args:
        history: List of historical data points
    
    Returns:
        Dict: Statistics for each metric
    """
    if not history:
        return {}
    
    stats = {}
    
    # Define metrics and their keys
    metrics = [
        ('temperature', '°C'),
        ('humidity', '%'),
        ('soil_moisture', '%')
    ]
    
    for metric, unit in metrics:
        values = [
            float(item.get(metric, 0))
            for item in history
            if metric in item and item.get(metric) is not None
        ]
        
        if values:
            stats[metric] = {
                'avg': round(sum(values) / len(values), 1),
                'min': round(min(values), 1),
                'max': round(max(values), 1),
                'count': len(values),
                'unit': unit
            }
    
    return stats

def sanitize_item(item: Dict) -> Dict:
    """
    Sanitize a DynamoDB item for output
    
    Args:
        item: Raw item from DynamoDB
    
    Returns:
        Dict: Sanitized item
    """
    if not item:
        return {}
    
    sanitized = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            sanitized[key] = float(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_item(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_item(v) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized

def get_pagination_token(last_evaluated_key: Dict) -> Optional[str]:
    """
    Create pagination token from LastEvaluatedKey
    
    Args:
        last_evaluated_key: DynamoDB LastEvaluatedKey
    
    Returns:
        Optional[str]: Base64 encoded pagination token
    """
    if not last_evaluated_key:
        return None
    
    try:
        token_str = json.dumps(last_evaluated_key)
        return base64.b64encode(token_str.encode('utf-8')).decode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to create pagination token: {e}")
        return None

def decode_pagination_token(token: str) -> Optional[Dict]:
    """
    Decode pagination token
    
    Args:
        token: Base64 encoded pagination token
    
    Returns:
        Optional[Dict]: Decoded ExclusiveStartKey
    """
    if not token:
        return None
    
    try:
        decoded = base64.b64decode(token).decode('utf-8')
        return json.loads(decoded)
    except Exception as e:
        logger.warning(f"Failed to decode pagination token: {e}")
        return None

def is_debug_enabled() -> bool:
    """
    Check if DEBUG mode is enabled
    
    Returns:
        bool: True if DEBUG mode is enabled
    """
    return os.environ.get('DEBUG', 'false').lower() in ['true', '1', 'yes']

# ============================================
# MAIN LAMBDA HANDLER
# ============================================

def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    Main Lambda handler for data queries
    
    Args:
        event: Lambda event (API Gateway request)
        context: Lambda context
    
    Returns:
        Dict: API Gateway response
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)[:500]}")
        
        # Extract query parameters
        params = event.get('queryStringParameters', {}) or {}
        
        # Parse and validate sensor_id
        sensor_id = params.get('sensor_id', 'sensor-001')
        if not validate_sensor_id(sensor_id):
            logger.warning(f"Invalid sensor_id: {sensor_id}")
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Invalid sensor_id format',
                    'message': 'Sensor ID must contain only letters, numbers, hyphens, and underscores'
                })
            }
        
        # Parse and validate hours
        try:
            hours = int(params.get('hours', 24))
        except (ValueError, TypeError):
            hours = 24
        hours = validate_hours(hours)
        
        # Parse and validate limit
        try:
            limit = int(params.get('limit', 100))
        except (ValueError, TypeError):
            limit = 100
        limit = validate_limit(limit)
        
        # Parse pagination token
        next_token = params.get('next_token', None)
        exclusive_start_key = None
        if next_token:
            exclusive_start_key = decode_pagination_token(next_token)
            if exclusive_start_key:
                logger.info(f"Pagination: using exclusive_start_key")
        
        logger.info(f"Query: sensor_id={sensor_id}, hours={hours}, limit={limit}")
        
        # ============================================
        # 1. RETRIEVE LATEST VALUES
        # ============================================
        latest = {}
        try:
            latest_response = table_latest.get_item(
                Key={'sensor_id': sensor_id}
            )
            latest = latest_response.get('Item', {})
            latest = sanitize_item(latest)
            logger.info(f"Retrieved latest data for {sensor_id}")
        except ClientError as e:
            logger.error(f"Error fetching latest data: {e}")
            # Continue with empty latest
        except Exception as e:
            logger.error(f"Unexpected error fetching latest data: {e}")
        
        # ============================================
        # 2. RETRIEVE HISTORICAL DATA
        # ============================================
        history = []
        next_token_next = None
        
        try:
            # Calculate cutoff time
            cutoff_time = (
                datetime.utcnow() - timedelta(hours=hours)
            ).isoformat() + 'Z'
            
            # Build query parameters
            query_params = {
                'KeyConditionExpression': 'sensor_id = :sid AND #ts >= :cutoff',
                'ExpressionAttributeNames': {
                    '#ts': 'timestamp'
                },
                'ExpressionAttributeValues': {
                    ':sid': sensor_id,
                    ':cutoff': cutoff_time
                },
                'ScanIndexForward': False,  # Newest first
                'Limit': limit
            }
            
            # Add pagination if provided
            if exclusive_start_key:
                query_params['ExclusiveStartKey'] = exclusive_start_key
            
            # Execute query
            history_response = table_history.query(**query_params)
            history = history_response.get('Items', [])
            history = [sanitize_item(item) for item in history]
            
            # Check for more results
            last_evaluated_key = history_response.get('LastEvaluatedKey')
            if last_evaluated_key:
                next_token_next = get_pagination_token(last_evaluated_key)
            
            logger.info(f"Retrieved {len(history)} historical records")
            
        except ClientError as e:
            logger.error(f"Error fetching history: {e}")
            # Continue with empty history
        except Exception as e:
            logger.error(f"Unexpected error fetching history: {e}")
        
        # ============================================
        # 3. CALCULATE STATISTICS
        # ============================================
        stats = calculate_statistics(history)
        
        # ============================================
        # 4. BUILD RESPONSE
        # ============================================
        response_body = {
            'latest': latest,
            'history': history,
            'stats': stats,
            'count': len(history),
            'sensor_id': sensor_id,
            'time_range': f'Last {hours} hours',
            'query_timestamp': datetime.utcnow().isoformat() + 'Z',
            'pagination': {
                'limit': limit,
                'has_more': next_token_next is not None,
                'next_token': next_token_next
            } if next_token_next else None,
            'metadata': {
                'api_version': '2.1',
                'source': 'lambda-query-data',
                'debug_mode': is_debug_enabled()
            }
        }
        
        # ============================================
        # 5. PREPARE RESPONSE WITH CACHING HEADERS
        # ============================================
        cache_control = 'max-age=60, s-maxage=300, stale-while-revalidate=60'
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': (
                    'Content-Type, X-Amz-Date, Authorization, '
                    'X-Api-Key, X-Amz-Security-Token'
                ),
                'Cache-Control': cache_control
            },
            'body': json.dumps(response_body, cls=DecimalEncoder)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        
        # ============================================
        # DEBUG MODE: Return detailed error information
        # ============================================
        error_response = {
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }
        
        # If DEBUG mode is enabled, include full error details
        if is_debug_enabled():
            error_response['debug'] = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'stack_trace': str(e)
            }
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(error_response)
        }

# ============================================
# OFFLINE TESTING
# ============================================

def run_offline_tests():
    """Run offline tests for the Lambda function"""
    print("=" * 60)
    print("OFFLINE TEST MODE - Query Data Lambda (v2.1 with DEBUG)")
    print("=" * 60)
    
    test_cases = [
        {
            'name': 'Normal Query',
            'params': {
                'sensor_id': 'sensor-001',
                'hours': '24',
                'limit': '50'
            },
            'expected_status': 200
        },
        {
            'name': 'Invalid Sensor ID',
            'params': {
                'sensor_id': 'sensor@invalid!',
                'hours': '24',
                'limit': '50'
            },
            'expected_status': 400
        },
        {
            'name': 'Invalid Hours',
            'params': {
                'sensor_id': 'sensor-001',
                'hours': '-5',
                'limit': '50'
            },
            'expected_status': 200  # Should default to 24
        },
        {
            'name': 'Large Limit',
            'params': {
                'sensor_id': 'sensor-001',
                'hours': '24',
                'limit': '1000'
            },
            'expected_status': 200  # Should cap at 500
        },
        {
            'name': 'No Parameters',
            'params': {},
            'expected_status': 200
        },
        {
            'name': 'Different Sensor',
            'params': {
                'sensor_id': 'sensor-002',
                'hours': '12',
                'limit': '25'
            },
            'expected_status': 200
        },
        {
            'name': 'Debug Mode Test',
            'params': {
                'sensor_id': 'sensor-001',
                'hours': '24'
            },
            'expected_status': 200,
            'debug': True
        }
    ]
    
    passed = 0
    failed = 0
    
    # Save original debug setting
    original_debug = os.environ.get('DEBUG', 'false')
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print("-" * 40)
        
        # Set debug mode for this test if specified
        if test.get('debug', False):
            os.environ['DEBUG'] = 'true'
            print("DEBUG MODE: ENABLED")
        else:
            os.environ['DEBUG'] = 'false'
        
        try:
            event = {'queryStringParameters': test['params']}
            response = lambda_handler(event, None)
            status = response.get('statusCode', 500)
            
            if status == test['expected_status']:
                print(f"✅ PASSED (status: {status})")
                
                # Parse and show response summary
                if status == 200:
                    body = json.loads(response['body'])
                    print(f"   Count: {body.get('count', 0)}")
                    if body.get('stats'):
                        stats = body['stats']
                        if 'temperature' in stats:
                            print(f"   Temp: {stats['temperature']['avg']}°C (avg)")
                    if body.get('pagination'):
                        print(f"   Has more: {body['pagination']['has_more']}")
                    if body.get('metadata', {}).get('debug_mode'):
                        print(f"   Debug mode: ON")
                passed += 1
            else:
                print(f"❌ FAILED (expected: {test['expected_status']}, got: {status})")
                if response.get('body'):
                    try:
                        error_body = json.loads(response['body'])
                        print(f"   Error: {error_body.get('error', 'Unknown')}")
                        if test.get('debug', False) and 'debug' in error_body:
                            print(f"   Debug Info: {error_body['debug']}")
                    except:
                        pass
                failed += 1
                
        except Exception as e:
            print(f"❌ FAILED with exception: {e}")
            failed += 1
    
    # Restore original debug setting
    os.environ['DEBUG'] = original_debug
    
    # Performance test
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST")
    print("=" * 60)
    
    import time
    event = {'queryStringParameters': {'sensor_id': 'sensor-001', 'hours': '24'}}
    iterations = 10
    times = []
    
    print(f"Running {iterations} iterations...")
    for i in range(iterations):
        start = time.time()
        lambda_handler(event, None)
        end = time.time()
        duration = (end - start) * 1000
        times.append(duration)
        print(f"  Iteration {i+1}: {duration:.2f}ms")
    
    print("\nResults:")
    print(f"  Average: {sum(times)/len(times):.2f}ms")
    print(f"  Min: {min(times):.2f}ms")
    print(f"  Max: {max(times):.2f}ms")
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    print("=" * 60)

# ============================================
# DEBUG MODE TEST
# ============================================

def test_debug_mode():
    """Test the DEBUG mode functionality"""
    print("\n" + "=" * 60)
    print("DEBUG MODE TEST")
    print("=" * 60)
    
    # Test with DEBUG enabled
    os.environ['DEBUG'] = 'true'
    print("\nDEBUG MODE: ENABLED")
    
    # Create an event that will trigger an error
    # (by using an invalid sensor_id format)
    event = {
        'queryStringParameters': {
            'sensor_id': 'sensor@invalid!',
            'hours': '24'
        }
    }
    
    response = lambda_handler(event, None)
    body = json.loads(response['body'])
    
    print(f"Status: {response['statusCode']}")
    print(f"Error: {body.get('error', 'Unknown')}")
    if 'debug' in body:
        print(f"Debug Info: {json.dumps(body['debug'], indent=2)}")
    
    # Test with DEBUG disabled
    os.environ['DEBUG'] = 'false'
    print("\nDEBUG MODE: DISABLED")
    
    response = lambda_handler(event, None)
    body = json.loads(response['body'])
    
    print(f"Status: {response['statusCode']}")
    print(f"Error: {body.get('error', 'Unknown')}")
    if 'debug' in body:
        print(f"Debug Info: {body['debug']}")
    else:
        print("Debug info hidden (as expected)")
    
    print("=" * 60)

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    # Run tests
    run_offline_tests()
    test_debug_mode()