# ============================================
# SMART GARDEN MANAGER - COMPLETE SETUP SCRIPT
# ============================================
# This script performs all steps to set up and run the Smart Garden Simulator:
# 1. Create X.509 certificates for AWS IoT Core
# 2. Create IoT policy with full permissions
# 3. Attach policy to certificate
# 4. Verify the configuration
# 5. Create .env file with configuration
# 6. Start the sensor simulator
# ============================================

# ============================================
# STEP 1: CREATE CERTIFICATES
# ============================================

# Navigate to project root
cd C:\Users\yilin\Downloads\CapstoneProject\Smart-Garden

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "STEP 1: CREATE CERTIFICATES" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

# Create the certs directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "./certs" | Out-Null
Write-Host "✅ ./certs/ directory created" -ForegroundColor Green

# Generate new X.509 certificates for AWS IoT Core
# These certificates will be used to authenticate the device with AWS IoT Core
Write-Host "`nGenerating new certificates..." -ForegroundColor Cyan
$CERT_OUTPUT = aws iot create-keys-and-certificate --set-as-active `
    --certificate-pem-outfile ./certs/device-certificate.pem.crt `
    --public-key-outfile ./certs/device-public-key.pem.key `
    --private-key-outfile ./certs/device-private-key.pem.key `
    --region us-west-2

# Check if certificate creation was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create certificates!" -ForegroundColor Red
    Write-Host "Please check your AWS CLI configuration and permissions." -ForegroundColor Yellow
    exit 1
}

# Extract the Certificate ARN from the JSON output
# The ARN is needed to attach policies to this certificate
$CERT_ARN = $CERT_OUTPUT | ConvertFrom-Json | Select-Object -ExpandProperty certificateArn
Write-Host "✅ Certificate ARN: $CERT_ARN" -ForegroundColor Green

# Download the Amazon Root CA certificate
# This is required to verify the server certificate during TLS handshake
Write-Host "`nDownloading Root CA certificate..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "https://www.amazontrust.com/repository/AmazonRootCA1.pem" -OutFile "./certs/root-CA.crt"
Write-Host "✅ Root CA certificate downloaded" -ForegroundColor Green

# Display all certificate files in the certs directory
Write-Host "`nCertificate files:" -ForegroundColor Cyan
Get-ChildItem ./certs/

# ============================================
# STEP 2: CREATE IOT POLICY
# ============================================

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "STEP 2: CREATE IOT POLICY" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

# Create the IoT policy JSON file if it doesn't exist
# This policy defines what actions the device is allowed to perform
if (-not (Test-Path "./iot-policy.json")) {
    Write-Host "Creating iot-policy.json..." -ForegroundColor Cyan
    @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:*",
      "Resource": "*"
    }
  ]
}
"@ | Out-File -FilePath "iot-policy.json" -Encoding utf8 -Force
    Write-Host "✅ iot-policy.json created" -ForegroundColor Green
} else {
    Write-Host "✅ iot-policy.json already exists" -ForegroundColor Green
}

# Check if the policy already exists in AWS IoT Core
Write-Host "`nChecking if policy already exists..." -ForegroundColor Cyan
$POLICY_EXISTS = aws iot get-policy --policy-name smart-garden-iot-policy --region us-west-2 2>$null

if ($LASTEXITCODE -eq 0) {
    # If the policy exists, delete it to avoid conflicts
    Write-Host "⚠️ Policy 'smart-garden-iot-policy' already exists" -ForegroundColor Yellow
    Write-Host "Deleting existing policy..." -ForegroundColor Cyan
    aws iot delete-policy --policy-name smart-garden-iot-policy --region us-west-2
    Write-Host "✅ Existing policy deleted" -ForegroundColor Green
}

# Create the IoT policy from the JSON file
Write-Host "`nCreating new IoT policy..." -ForegroundColor Cyan
aws iot create-policy `
    --policy-name smart-garden-iot-policy `
    --policy-document file://iot-policy.json `
    --region us-west-2

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create IoT policy!" -ForegroundColor Red
    Write-Host "Please check the policy document syntax." -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Policy 'smart-garden-iot-policy' created successfully" -ForegroundColor Green

# ============================================
# STEP 3: ATTACH POLICY TO CERTIFICATE
# ============================================

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "STEP 3: ATTACH POLICY TO CERTIFICATE" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

# The policy must be attached to the certificate so the device can authenticate
Write-Host "Attaching policy to certificate..." -ForegroundColor Cyan
aws iot attach-policy --policy-name smart-garden-iot-policy --target $CERT_ARN --region us-west-2

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to attach policy to certificate!" -ForegroundColor Red
    Write-Host "Please check the certificate ARN and policy name." -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Policy successfully attached to certificate" -ForegroundColor Green

# ============================================
# STEP 4: VERIFY CONFIGURATION
# ============================================

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "STEP 4: VERIFY CONFIGURATION" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

# Verify that the policy is correctly attached to the certificate
Write-Host "`nAttached Policies:" -ForegroundColor Cyan
aws iot list-attached-policies --target $CERT_ARN --region us-west-2 --query "policies[].policyName" --output table

# Display the Certificate ARN for reference
Write-Host "`nCertificate ARN:" -ForegroundColor Cyan
Write-Host $CERT_ARN -ForegroundColor Green

# ============================================
# STEP 5: CREATE .ENV FILE
# ============================================

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "STEP 5: CREATE .ENV FILE" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

# Get the AWS IoT Core endpoint for the current region
# This is required for the device to connect to AWS IoT Core
Write-Host "Retrieving IoT Endpoint..." -ForegroundColor Cyan
$IOT_ENDPOINT = aws iot describe-endpoint --endpoint-type iot:Data-ATS --region us-west-2 --query "endpointAddress" --output text
Write-Host "✅ IoT Endpoint: $IOT_ENDPOINT" -ForegroundColor Green

# Create the .env file with all configuration parameters
# This file is used by the sensor simulator to connect to AWS IoT Core
Write-Host "`nCreating .env file..." -ForegroundColor Cyan
@"
# Smart Garden Simulator Configuration
# ===================================
# AWS IoT Core endpoint for MQTT connection
AWS_IOT_ENDPOINT=$IOT_ENDPOINT

# MQTT topic for publishing sensor data
AWS_IOT_TOPIC=sensor/data

# Unique identifier for this sensor
SENSOR_ID=sensor-001

# Sensor location (indoor, outdoor, greenhouse)
SENSOR_LOCATION=indoor

# Interval between readings in seconds
SENSOR_INTERVAL=10

# Paths to the X.509 certificate files
CERT_PATH=./certs/device-certificate.pem.crt
PRIVATE_KEY_PATH=./certs/device-private-key.pem.key
ROOT_CA_PATH=./certs/root-CA.crt

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
"@ | Out-File -FilePath ".env" -Encoding utf8

Write-Host "✅ .env file created successfully" -ForegroundColor Green

# Display the contents of the .env file for verification
Write-Host "`n.env file contents:" -ForegroundColor Cyan
Get-Content .env

# ============================================
# STEP 6: START SENSOR SIMULATOR
# ============================================

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "STEP 6: START SENSOR SIMULATOR" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

Write-Host "`nStarting sensor simulator in ONLINE mode..." -ForegroundColor Cyan
Write-Host "Press CTRL+C to stop the simulator" -ForegroundColor Yellow
Write-Host ""
Write-Host "Expected output:" -ForegroundColor Gray
Write-Host "  [INFO] Connected to AWS IoT Core successfully" -ForegroundColor Gray
Write-Host "  [INFO] OK [001] T: 23.1C | H: 54.3% | M: 46.2%" -ForegroundColor Gray
Write-Host ""

# Navigate to the simulator directory
cd C:\Users\yilin\Downloads\CapstoneProject\Smart-Garden\src\simulator

# Start the sensor simulator with the .env file configuration
# The simulator will generate realistic sensor data and publish it to AWS IoT Core
python sensor_simulator.py --env

# ============================================
# FALLBACK: OFFLINE MODE
# ============================================
# If the online mode doesn't work, you can run the simulator in offline mode:
# python sensor_simulator.py --offline
# This will send data directly to your API Gateway endpoint without using AWS IoT Core