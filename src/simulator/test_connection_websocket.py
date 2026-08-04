import ssl
import time
import os
from pathlib import Path
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# ============================================
# KONFIGURATION - With relative paths
# ============================================

# Projekt-Root
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent

# Konfiguration
endpoint = "a3m8wm6nquocq7-ats.iot.us-west-2.amazonaws.com"
port = 443
client_id = "test-client-443"

# Certificates paths - RELATIV!
certs_dir = project_root / "certs"
cert_path = str(certs_dir / "d6180d354a19211ba9de8e2876dd45a55a96cf1a8ff71505dcfe3a86e62fb344-certificate.pem.crt")
key_path = str(certs_dir / "d6180d354a19211ba9de8e2876dd45a55a96cf1a8ff71505dcfe3a86e62fb344-private.pem.key")
ca_path = str(certs_dir / "AmazonRootCA1.pem")

print("🔧 Verbindungstest zu AWS IoT Core (Port 443 mit WebSocket)")
print(f"Endpoint: {endpoint}")
print(f"Port: {port}")
print(f"Client ID: {client_id}")

try:
    # MQTT Client mit WebSocket
    mqtt_client = AWSIoTMQTTClient(client_id, useWebsocket=True)
    mqtt_client.configureEndpoint(endpoint, port)
    mqtt_client.configureCredentials(ca_path, key_path, cert_path)
    
    mqtt_client.configureConnectDisconnectTimeout(30)
    mqtt_client.configureMQTTOperationTimeout(15)
    
    print("📡 Versuche zu verbinden...")
    mqtt_client.connect()
    print("✅ Verbindung erfolgreich!")
    
    mqtt_client.disconnect()
    print("✅ Verbindung getrennt")
    
except Exception as e:
    print(f"❌ Fehler: {e}")
    import traceback
    traceback.print_exc()