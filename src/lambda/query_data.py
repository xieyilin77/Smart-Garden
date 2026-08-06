#!/usr/bin/env python3
"""
Smart Garden Manager - Query Data Lambda
========================================
Gibt Sensor-Daten aus DynamoDB zurück
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError

# ============================================
# LOGGING
# ============================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ============================================
# AWS CLIENTS
# ============================================

dynamodb = boto3.resource('dynamodb')
table_latest = dynamodb.Table(os.environ.get('LATEST_TABLE', 'smart-garden-sensor-latest'))
table_history = dynamodb.Table(os.environ.get('HISTORY_TABLE', 'smart-garden-sensor-data'))

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

def sanitize_item(item: Dict) -> Dict:
    """Convert Decimal to float recursively"""
    if not item:
        return {}
    sanitized = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            sanitized[key] = float(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_item(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_item(v) if isinstance(v, dict) else v for v in value]
        else:
            sanitized[key] = value
    return sanitized

def calculate_stats(history: List[Dict]) -> Dict:
    """
    Calculate statistics from history data
    THIS IS THE KEY FIX - stats were empty before!
    """
    if not history:
        return {}
    
    # Initialize value lists
    temps = []
    hums = []
    soils = []
    
    for item in history:
        # Extract values - handle both string and numeric types
        temp = item.get('temperature')
        hum = item.get('humidity')
        moist = item.get('soil_moisture')
        
        # Convert to float if possible
        try:
            if temp is not None:
                temps.append(float(temp))
        except (ValueError, TypeError):
            pass
        
        try:
            if hum is not None:
                hums.append(float(hum))
        except (ValueError, TypeError):
            pass
        
        try:
            if moist is not None:
                soils.append(float(moist))
        except (ValueError, TypeError):
            pass
    
    stats = {}
    
    # Temperature stats
    if temps:
        stats['temperature'] = {
            'avg': round(sum(temps) / len(temps), 1),
            'min': round(min(temps), 1),
            'max': round(max(temps), 1)
        }
    
    # Humidity stats
    if hums:
        stats['humidity'] = {
            'avg': round(sum(hums) / len(hums), 1),
            'min': round(min(hums), 1),
            'max': round(max(hums), 1)
        }
    
    # Soil moisture stats
    if soils:
        stats['soil_moisture'] = {
            'avg': round(sum(soils) / len(soils), 1),
            'min': round(min(soils), 1),
            'max': round(max(soils), 1)
        }
    
    return stats

# ============================================
# LAMBDA HANDLER
# ============================================

def lambda_handler(event: Dict, context: Any) -> Dict:
    """
    Main Lambda handler for querying sensor data
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)[:500]}")
        
        # Parse query parameters
        params = event.get('queryStringParameters', {}) or {}
        sensor_id = params.get('sensor_id', 'sensor-001')
        
        try:
            hours = int(params.get('hours', 24))
        except (ValueError, TypeError):
            hours = 24
        hours = max(1, min(720, hours))
        
        try:
            limit = int(params.get('limit', 100))
        except (ValueError, TypeError):
            limit = 100
        limit = max(1, min(500, limit))
        
        logger.info(f"Query: sensor_id={sensor_id}, hours={hours}, limit={limit}")
        
        # 1. Get LATEST data
        latest = {}
        try:
            latest_response = table_latest.get_item(Key={'sensor_id': sensor_id})
            latest = sanitize_item(latest_response.get('Item', {}))
            logger.info(f"Retrieved latest data for {sensor_id}: {latest}")
        except Exception as e:
            logger.error(f"Error fetching latest data: {e}")
        
        # 2. Get HISTORY data - FIXED QUERY
        history = []
        try:
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat() + 'Z'
            logger.info(f"Cutoff time: {cutoff_time}")
            
            # FIXED: Using correct ExpressionAttributeNames
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
            
            logger.info(f"Query params: {query_params}")
            
            history_response = table_history.query(**query_params)
            history = [sanitize_item(item) for item in history_response.get('Items', [])]
            
            logger.info(f"Retrieved {len(history)} historical records")
            if history:
                logger.info(f"First record sample: {json.dumps(history[0], default=str)}")
            
        except Exception as e:
            logger.error(f"Error fetching history: {e}", exc_info=True)
        
        # 3. Calculate STATS - THE FIX!
        stats = calculate_stats(history)
        logger.info(f"Calculated stats: {json.dumps(stats, default=str)}")
        
        # 4. Build response
        response_body = {
            'latest': latest,
            'history': history,
            'stats': stats,
            'count': len(history),
            'sensor_id': sensor_id,
            'time_range': f'Last {hours} hours',
            'query_timestamp': get_utc_timestamp(),
            'metadata': {
                'api_version': '2.1',
                'source': 'lambda-query-data',
                'debug_mode': False
            }
        }
        
        # Return response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key'
            },
            'body': json.dumps(response_body, cls=DecimalEncoder)
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
                'message': str(e)
            })
        }