#!/usr/bin/env python3
"""
Mock API Server for Smart Garden testing
Simulates the API Gateway/Lambda backend locally
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import datetime
import random

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Store received data in memory
received_data = []

@app.route('/prod/data', methods=['POST'])
def receive_data():
    """Receive sensor data from API simulator"""
    try:
        data = request.get_json()
        print(f"\n📥 Received sensor data:")
        print(f"   Sensor: {data.get('sensor_id')}")
        print(f"   Temp: {data.get('temperature')}°C")
        print(f"   Humidity: {data.get('humidity')}%")
        print(f"   Soil Moisture: {data.get('soil_moisture')}%")
        
        # Store for query endpoint
        received_data.append(data)
        if len(received_data) > 100:
            received_data.pop(0)
        
        # Simulate Lambda processing
        alerts = []
        if data.get('temperature', 0) > 35:
            alerts.append(f"High temperature: {data['temperature']}°C (threshold: 35°C)")
        if data.get('temperature', 0) < 15:
            alerts.append(f"Low temperature: {data['temperature']}°C (threshold: 15°C)")
        if data.get('soil_moisture', 0) < 30:
            alerts.append(f"Low soil moisture: {data['soil_moisture']}% (threshold: 30%)")
        if data.get('humidity', 0) > 80:
            alerts.append(f"High humidity: {data['humidity']}% (threshold: 80%)")
        
        response = {
            'status': 'success',
            'message': 'Data processed successfully',
            'alerts': alerts,
            'alert_count': len(alerts),
            'timestamp': datetime.datetime.now(datetime.UTC).isoformat() + 'Z'
        }
        
        if alerts:
            print(f"   ⚠️ ALERTS: {len(alerts)} detected!")
            for alert in alerts:
                print(f"      - {alert}")
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ Error processing data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/prod/query', methods=['GET'])
def query_data():
    """Return ACTUAL received data + calculated stats"""
    try:
        # Get the 50 most recent data points
        history = received_data[-50:] if received_data else []
        
        if not history:
            # Return empty response if no data
            return jsonify({
                'latest': {},
                'history': [],
                'stats': {},
                'count': 0,
                'sensor_id': request.args.get('sensor_id', 'sensor-001'),
                'time_range': 'No data',
                'query_timestamp': datetime.datetime.now(datetime.UTC).isoformat() + 'Z'
            }), 200

        # Latest value = newest entry
        latest = history[-1]

        # Calculate statistics from REAL data
        temps = [h.get('temperature', 0) for h in history if h.get('temperature') is not None]
        hums = [h.get('humidity', 0) for h in history if h.get('humidity') is not None]
        soils = [h.get('soil_moisture', 0) for h in history if h.get('soil_moisture') is not None]

        stats = {}
        if temps:
            stats['temperature'] = {
                'avg': round(sum(temps) / len(temps), 1),
                'min': round(min(temps), 1),
                'max': round(max(temps), 1)
            }
        if hums:
            stats['humidity'] = {
                'avg': round(sum(hums) / len(hums), 1),
                'min': round(min(hums), 1),
                'max': round(max(hums), 1)
            }
        if soils:
            stats['soil_moisture'] = {
                'avg': round(sum(soils) / len(soils), 1),
                'min': round(min(soils), 1),
                'max': round(max(soils), 1)
            }

        # Return in the format dashboard.js expects
        return jsonify({
            'latest': latest,
            'history': list(reversed(history)),  # Newest first for dashboard
            'stats': stats,
            'count': len(history),
            'sensor_id': latest.get('sensor_id', 'sensor-001'),
            'time_range': f'Last {len(history)} readings',
            'query_timestamp': datetime.datetime.now(datetime.UTC).isoformat() + 'Z'
        }), 200
        
    except Exception as e:
        print(f"❌ Error in query_data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    print("=" * 60)
    print("🌱 Smart Garden - Mock API Server")
    print("=" * 60)
    print("This simulates the API Gateway/Lambda backend")
    print("Running on: http://localhost:5000")
    print("Endpoints:")
    print("  POST /prod/data  - Receive sensor data")
    print("  GET  /prod/query - Query historical data")
    print("  GET  /health     - Health check")
    print("=" * 60)
    print()
    app.run(debug=True, port=5000)