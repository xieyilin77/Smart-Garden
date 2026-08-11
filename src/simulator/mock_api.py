#!/usr/bin/env python3
"""
Mock API Server for Smart Garden testing
Simulates the API Gateway/Lambda backend locally
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Store received data in memory
received_data = []


def to_float(value):
    """Safely convert any value to float, handling comma decimal separator"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Replace comma with dot for decimal conversion
        value = value.replace(',', '.')
        try:
            return float(value)
        except ValueError:
            return 0.0
    # Try to convert from other types
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


@app.route('/prod/data', methods=['POST'])
def receive_data():
    """Receive sensor data from API simulator"""
    try:
        data = request.get_json()
        print("\n📥 Received sensor data:")
        print(f"   Sensor: {data.get('sensor_id')}")
        print(f"   Temp: {data.get('temperature')}°C")
        print(f"   Humidity: {data.get('humidity')}%")
        print(f"   Soil Moisture: {data.get('soil_moisture')}%")

        # Clean and convert all numeric values
        clean_data = {
            'sensor_id': str(data.get('sensor_id', 'sensor-001')),
            'timestamp': data.get('timestamp', datetime.datetime.now(datetime.UTC).isoformat() + 'Z'),
            'temperature': to_float(data.get('temperature', 0)),
            'humidity': to_float(data.get('humidity', 0)),
            'soil_moisture': to_float(data.get('soil_moisture', 0)),
            'location': data.get('location', 'indoor'),
            'battery': to_float(data.get('battery', 100.0)),
            'reading_id': data.get('reading_id', f"sensor-001-{len(received_data)+1:06d}")
        }
        
        print(f"📊 Cleaned: T={clean_data['temperature']:.1f}°C, "
              f"H={clean_data['humidity']:.1f}%, "
              f"M={clean_data['soil_moisture']:.1f}%")

        # Store for query endpoint
        received_data.append(clean_data)
        if len(received_data) > 100:
            received_data.pop(0)

        # Simulate Lambda processing with correct thresholds
        alerts = []
        
        temp = clean_data['temperature']
        humidity = clean_data['humidity']
        soil_moisture = clean_data['soil_moisture']
        
        # Low soil moisture (< 30%)
        if soil_moisture < 30:
            alerts.append(
                f"Low soil moisture: {soil_moisture:.1f}% "
                f"(threshold: 30%)"
            )
        
        # High soil moisture (> 80%)
        if soil_moisture > 80:
            alerts.append(
                f"High soil moisture: {soil_moisture:.1f}% "
                f"(threshold: 80%)"
            )
        
        # High temperature (> 35°C)
        if temp > 35:
            alerts.append(
                f"High temperature: {temp:.1f}°C "
                f"(threshold: 35°C)"
            )
        
        # Low temperature (< 5°C)
        if temp < 5:
            alerts.append(
                f"Low temperature: {temp:.1f}°C "
                f"(threshold: 5°C)"
            )
        
        # Low humidity (< 40%)
        if humidity < 40:
            alerts.append(
                f"Low humidity: {humidity:.1f}% "
                f"(threshold: 40%)"
            )
        
        # High humidity (> 90%)
        if humidity > 90:
            alerts.append(
                f"High humidity: {humidity:.1f}% "
                f"(threshold: 90%)"
            )

        response = {
            'status': 'success',
            'message': 'Data processed successfully',
            'alerts': alerts,
            'alert_count': len(alerts),
            'timestamp': datetime.datetime.now(
                datetime.UTC
            ).isoformat() + 'Z'
        }

        if alerts:
            print(f"   ⚠️ ALERTS: {len(alerts)} detected!")
            for alert in alerts:
                print(f"      - {alert}")

        return jsonify(response), 200

    except Exception as e:
        print(f"❌ Error processing data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/prod/query', methods=['GET'])
def query_data():
    """Return ACTUAL received data + calculated stats"""
    try:
        print(f"📊 Query called - {len(received_data)} records in memory")
        
        history = received_data[-100:] if received_data else []

        if not history:
            print("⚠️ No data in memory!")
            return jsonify({
                'latest': {},
                'history': [],
                'stats': {},
                'count': 0,
                'sensor_id': request.args.get('sensor_id', 'sensor-001'),
                'time_range': 'No data',
                'query_timestamp': datetime.datetime.now(
                    datetime.UTC
                ).isoformat() + 'Z'
            }), 200

        # Latest value = newest entry (last in list)
        latest = history[-1]
        print(f"📊 Latest: temp={latest.get('temperature')}°C, "
              f"humidity={latest.get('humidity')}%, "
              f"moisture={latest.get('soil_moisture')}%")

        # Calculate statistics from REAL data
        temps = []
        hums = []
        soils = []
        
        for h in history:
            temp = h.get('temperature')
            if temp is not None:
                try:
                    temps.append(float(temp))
                except (ValueError, TypeError):
                    pass
            
            hum = h.get('humidity')
            if hum is not None:
                try:
                    hums.append(float(hum))
                except (ValueError, TypeError):
                    pass
            
            moist = h.get('soil_moisture')
            if moist is not None:
                try:
                    soils.append(float(moist))
                except (ValueError, TypeError):
                    pass

        stats = {}
        
        if temps:
            stats['temperature'] = {
                'avg': round(sum(temps) / len(temps), 1),
                'min': round(min(temps), 1),
                'max': round(max(temps), 1)
            }
            print(f"📊 Temp stats: avg={stats['temperature']['avg']}°C")
        else:
            print("⚠️ No temperature data found!")
        
        if hums:
            stats['humidity'] = {
                'avg': round(sum(hums) / len(hums), 1),
                'min': round(min(hums), 1),
                'max': round(max(hums), 1)
            }
            print(f"📊 Humidity stats: avg={stats['humidity']['avg']}%")
        else:
            print("⚠️ No humidity data found!")
        
        if soils:
            stats['soil_moisture'] = {
                'avg': round(sum(soils) / len(soils), 1),
                'min': round(min(soils), 1),
                'max': round(max(soils), 1)
            }
            print(f"📊 Soil stats: avg={stats['soil_moisture']['avg']}%")
        else:
            print("⚠️ No soil moisture data found!")

        return jsonify({
            'latest': latest,
            'history': list(reversed(history)),
            'stats': stats,
            'count': len(history),
            'sensor_id': latest.get('sensor_id', 'sensor-001'),
            'time_range': f'Last {len(history)} readings',
            'query_timestamp': datetime.datetime.now(
                datetime.UTC
            ).isoformat() + 'Z'
        }), 200

    except Exception as e:
        print(f"❌ Error in query_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


@app.route('/reset', methods=['POST'])
def reset_data():
    """Reset stored data (for testing)"""
    global received_data
    received_data = []
    print("🔄 Data reset!")
    return jsonify({'status': 'reset', 'message': 'All data cleared'}), 200


@app.route('/count', methods=['GET'])
def get_count():
    """Get number of stored records"""
    return jsonify({'count': len(received_data)}), 200


if __name__ == '__main__':
    print("=" * 60)
    print("🌱 Smart Garden - Mock API Server (FIXED)")
    print("=" * 60)
    print("Running on: http://localhost:5000")
    print()
    print("Endpoints:")
    print("  POST /prod/data  - Receive sensor data")
    print("  GET  /prod/query - Query historical data")
    print("  GET  /health     - Health check")
    print("  POST /reset      - Reset all data")
    print("  GET  /count      - Get record count")
    print()
    print("Thresholds (matching process_data.py):")
    print("  🌡️  Temperature:  < 5°C or > 35°C")
    print("  💧  Humidity:     < 40% or > 90%")
    print("  🌱  Soil Moisture: < 30% or > 80%")
    print("=" * 60)
    print()
    app.run(debug=True, port=5000)