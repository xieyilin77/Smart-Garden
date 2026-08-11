# ============================================
# SMART GARDEN MANAGER - SETUP SCRIPT (FIXED)
# ============================================
# This script sets up AWS IoT Core certificates and policy
# It does NOT start the simulator automatically

param(
    [string]$Region = (aws configure get region),
    [string]$ProjectRoot = $PSScriptRoot
)

# FIXED: Get the actual project root (parent of scripts folder)
$ProjectRoot = Split-Path -Parent $PSScriptRoot

# Fix encoding for PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Smart Garden - Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# FIXED: Use the correct path for certificates (src/simulator/certs/)
$CertDir = Join-Path $ProjectRoot "src\simulator\certs"
$PolicyFile = Join-Path $ProjectRoot "iot-policy.json"

# Check AWS CLI
$AccountId = aws sts get-caller-identity --query Account --output text 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: AWS CLI not configured!" -ForegroundColor Red
    Write-Host "Run: aws configure" -ForegroundColor Yellow
    exit 1
}

if (-not $Region) {
    $Region = "us-west-2"
}

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "   Account: $AccountId" -ForegroundColor Gray
Write-Host "   Region: $Region" -ForegroundColor Gray
Write-Host "   Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "   Cert Dir: $CertDir" -ForegroundColor Gray
Write-Host ""

# ============================================
# STEP 1: CREATE CERTIFICATES
# ============================================
Write-Host "Step 1: Creating certificates..." -ForegroundColor Yellow

# Create certificate directory if it doesn't exist
if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
    Write-Host "   Created certificate directory: $CertDir" -ForegroundColor Green
}

# Check if certificates already exist
$existingCerts = Get-ChildItem $CertDir -Filter "*.crt" | Where-Object { $_.Name -ne "root-CA.crt" }
if ($existingCerts) {
    Write-Host "   WARNING: Certificates already exist in $CertDir" -ForegroundColor Yellow
    $regen = Read-Host "   Regenerate? (y/n)"
    if ($regen -ne "y") {
        Write-Host "   OK: Using existing certificates" -ForegroundColor Green
    } else {
        # Delete existing certificates
        Remove-Item (Join-Path $CertDir "*.crt") -Exclude "root-CA.crt" -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $CertDir "*.key") -Force -ErrorAction SilentlyContinue
        
        # Generate new certificates
        $CertOutput = aws iot create-keys-and-certificate --set-as-active `
            --certificate-pem-outfile (Join-Path $CertDir "device-certificate.pem.crt") `
            --public-key-outfile (Join-Path $CertDir "device-public-key.pem.key") `
            --private-key-outfile (Join-Path $CertDir "device-private-key.pem.key") `
            --region $Region 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   ERROR: Failed to create certificates!" -ForegroundColor Red
            Write-Host "   $CertOutput" -ForegroundColor Red
            exit 1
        }
        
        $CertArn = $CertOutput | ConvertFrom-Json | Select-Object -ExpandProperty certificateArn
        Write-Host "   OK: Certificates created: $CertArn" -ForegroundColor Green
    }
} else {
    # Generate certificates
    $CertOutput = aws iot create-keys-and-certificate --set-as-active `
        --certificate-pem-outfile (Join-Path $CertDir "device-certificate.pem.crt") `
        --public-key-outfile (Join-Path $CertDir "device-public-key.pem.key") `
        --private-key-outfile (Join-Path $CertDir "device-private-key.pem.key") `
        --region $Region 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ERROR: Failed to create certificates!" -ForegroundColor Red
        Write-Host "   $CertOutput" -ForegroundColor Red
        exit 1
    }
    
    $CertArn = $CertOutput | ConvertFrom-Json | Select-Object -ExpandProperty certificateArn
    Write-Host "   OK: Certificates created: $CertArn" -ForegroundColor Green
}

# Download Root CA (save to the correct directory)
Write-Host "   Downloading Root CA..." -ForegroundColor Gray
$rootCaPath = Join-Path $CertDir "root-CA.crt"
if (-not (Test-Path $rootCaPath)) {
    Invoke-WebRequest -Uri "https://www.amazontrust.com/repository/AmazonRootCA1.pem" -OutFile $rootCaPath
    Write-Host "   OK: Root CA downloaded to $rootCaPath" -ForegroundColor Green
} else {
    Write-Host "   OK: Root CA already exists" -ForegroundColor Green
}
Write-Host ""

# ============================================
# STEP 2: CREATE IOT POLICY (WITH MINIMAL PERMISSIONS)
# ============================================
Write-Host "Step 2: Creating IoT policy..." -ForegroundColor Yellow

# Create minimal policy
$PolicyContent = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect",
        "iot:Publish",
        "iot:Subscribe",
        "iot:Receive"
      ],
      "Resource": [
        "arn:aws:iot:${Region}:${AccountId}:client/smart-garden-*",
        "arn:aws:iot:${Region}:${AccountId}:topic/sensor/data",
        "arn:aws:iot:${Region}:${AccountId}:topicfilter/sensor/data"
      ]
    }
  ]
}
"@

# Write policy file with UTF8 without BOM
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($PolicyFile, $PolicyContent, $Utf8NoBom)

Write-Host "   OK: Policy file created: $PolicyFile" -ForegroundColor Green

# Delete existing policy if it exists
aws iot delete-policy --policy-name smart-garden-iot-policy --region $Region 2>$null

# Create new policy
aws iot create-policy `
    --policy-name smart-garden-iot-policy `
    --policy-document "file://$PolicyFile" `
    --region $Region 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "   ERROR: Failed to create policy!" -ForegroundColor Red
    exit 1
}
Write-Host "   OK: Policy created: smart-garden-iot-policy" -ForegroundColor Green

# ============================================
# STEP 3: ATTACH POLICY TO CERTIFICATE
# ============================================
Write-Host "Step 3: Attaching policy to certificate..." -ForegroundColor Yellow

if ($CertArn) {
    aws iot attach-policy --policy-name smart-garden-iot-policy --target $CertArn --region $Region 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ERROR: Failed to attach policy!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   OK: Policy attached to certificate" -ForegroundColor Green
} else {
    Write-Host "   WARNING: No certificate ARN found. Please attach manually." -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# STEP 4: GENERATE .env FILE
# ============================================
Write-Host "Step 4: Generating .env file..." -ForegroundColor Yellow

# Use the Python script for better .env generation
$EnvScript = Join-Path $ProjectRoot "scripts/generate_env.py"
if (Test-Path $EnvScript) {
    Write-Host "   Running generate_env.py..." -ForegroundColor Gray
    python $EnvScript --online
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   WARNING: Python script failed. Creating basic .env..." -ForegroundColor Yellow
        
        # Fallback: Create basic .env with correct paths
        $IotEndpoint = aws iot describe-endpoint --endpoint-type iot:Data-ATS --region $Region --query endpointAddress --output text 2>$null
        if (-not $IotEndpoint) {
            $IotEndpoint = "YOUR_IOT_ENDPOINT.iot.$Region.amazonaws.com"
        }
        
        # FIXED: Use correct paths for src/simulator/certs/
        $EnvContent = @"
# Smart Garden Configuration
# ============================================
# AWS IoT Core Configuration
AWS_IOT_ENDPOINT=$IotEndpoint
AWS_IOT_TOPIC=sensor/data
IOT_THING_NAME=smart-garden-sensor

# Sensor Configuration
SENSOR_ID=sensor-001
SENSOR_LOCATION=indoor
SENSOR_INTERVAL=5

# Certificate Paths (relative to project root)
CERT_PATH=./src/simulator/certs/device-certificate.pem.crt
PRIVATE_KEY_PATH=./src/simulator/certs/device-private-key.pem.key
ROOT_CA_PATH=./src/simulator/certs/root-CA.crt

# Logging
LOG_LEVEL=INFO
DEBUG=false
"@
        $EnvPath = Join-Path $ProjectRoot ".env"
        [System.IO.File]::WriteAllText($EnvPath, $EnvContent, $Utf8NoBom)
        Write-Host "   OK: Basic .env created at $EnvPath" -ForegroundColor Green
    }
} else {
    Write-Host "   WARNING: generate_env.py not found. Creating basic .env..." -ForegroundColor Yellow
    
    # Fallback: Create basic .env
    $IotEndpoint = aws iot describe-endpoint --endpoint-type iot:Data-ATS --region $Region --query endpointAddress --output text 2>$null
    if (-not $IotEndpoint) {
        $IotEndpoint = "YOUR_IOT_ENDPOINT.iot.$Region.amazonaws.com"
    }
    
    $EnvContent = @"
# Smart Garden Configuration
# ============================================
# AWS IoT Core Configuration
AWS_IOT_ENDPOINT=$IotEndpoint
AWS_IOT_TOPIC=sensor/data
IOT_THING_NAME=smart-garden-sensor

# Sensor Configuration
SENSOR_ID=sensor-001
SENSOR_LOCATION=indoor
SENSOR_INTERVAL=5

# Certificate Paths (relative to project root)
CERT_PATH=./src/simulator/certs/device-certificate.pem.crt
PRIVATE_KEY_PATH=./src/simulator/certs/device-private-key.pem.key
ROOT_CA_PATH=./src/simulator/certs/root-CA.crt

# Logging
LOG_LEVEL=INFO
DEBUG=false
"@
    $EnvPath = Join-Path $ProjectRoot ".env"
    [System.IO.File]::WriteAllText($EnvPath, $EnvContent, $Utf8NoBom)
    Write-Host "   OK: Basic .env created at $EnvPath" -ForegroundColor Green
}
Write-Host ""

# ============================================
# STEP 5: VERIFY FILES
# ============================================
Write-Host "Step 5: Verifying files..." -ForegroundColor Yellow

# Check certificates
$certFiles = @(
    "device-certificate.pem.crt",
    "device-private-key.pem.key",
    "root-CA.crt"
)

$allFound = $true
foreach ($file in $certFiles) {
    $filePath = Join-Path $CertDir $file
    if (Test-Path $filePath) {
        Write-Host "   OK: $file found" -ForegroundColor Green
    } else {
        Write-Host "   MISSING: $file" -ForegroundColor Red
        $allFound = $false
    }
}

# Check .env file
$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
    Write-Host "   OK: .env file found at $envPath" -ForegroundColor Green
} else {
    Write-Host "   MISSING: .env file at $envPath" -ForegroundColor Red
    $allFound = $false
}

Write-Host ""

# ============================================
# STEP 6: SUMMARY
# ============================================
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Created Resources:" -ForegroundColor Cyan
Write-Host "   Certificates: $CertDir" -ForegroundColor Gray
Write-Host "   IoT Policy: smart-garden-iot-policy" -ForegroundColor Gray
Write-Host "   .env file: $(Join-Path $ProjectRoot ".env")" -ForegroundColor Gray
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "   1. Start MQTT simulator:" -ForegroundColor White
Write-Host "      cd src\simulator" -ForegroundColor Gray
Write-Host "      python sensor_simulator.py --mqtt --env --interval 60" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Start API simulator:" -ForegroundColor White
Write-Host "      cd src\simulator" -ForegroundColor Gray
Write-Host "      python sensor_simulator.py --api --env --interval 60" -ForegroundColor Gray
Write-Host ""
Write-Host "   3. Start offline simulator:" -ForegroundColor White
Write-Host "      cd src\simulator" -ForegroundColor Gray
Write-Host "      python sensor_simulator.py --offline --interval 60" -ForegroundColor Gray
Write-Host ""
Write-Host "   4. Open dashboard:" -ForegroundColor White
Write-Host "      start src\dashboard\index.html" -ForegroundColor Gray
Write-Host "=====================================" -ForegroundColor Cyan