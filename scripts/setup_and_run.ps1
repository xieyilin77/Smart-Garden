# ============================================
# SMART GARDEN MANAGER - SETUP SCRIPT (IMPROVED)
# ============================================
# This script sets up AWS IoT Core certificates and policy
# It does NOT start the simulator automatically

param(
    [string]$Region = (aws configure get region),
    [string]$ProjectRoot = $PSScriptRoot
)

# Fix encoding for PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Smart Garden - Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Use relative paths
$CertDir = Join-Path $ProjectRoot "certs"
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
Write-Host "   Project: $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# ============================================
# STEP 1: CREATE CERTIFICATES
# ============================================
Write-Host "Step 1: Creating certificates..." -ForegroundColor Yellow

if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
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

# Download Root CA
Write-Host "   Downloading Root CA..." -ForegroundColor Gray
if (-not (Test-Path (Join-Path $CertDir "root-CA.crt"))) {
    Invoke-WebRequest -Uri "https://www.amazontrust.com/repository/AmazonRootCA1.pem" -OutFile (Join-Path $CertDir "root-CA.crt")
    Write-Host "   OK: Root CA downloaded" -ForegroundColor Green
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
    python $EnvScript --online
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   WARNING: Python script failed. Creating basic .env..." -ForegroundColor Yellow
        
        # Fallback: Create basic .env
        $IotEndpoint = aws iot describe-endpoint --endpoint-type iot:Data-ATS --region $Region --query endpointAddress --output text 2>$null
        if (-not $IotEndpoint) {
            $IotEndpoint = "YOUR_IOT_ENDPOINT.iot.$Region.amazonaws.com"
        }
        
        $EnvContent = @"
# Smart Garden Configuration
AWS_IOT_ENDPOINT=$IotEndpoint
AWS_IOT_TOPIC=sensor/data
SENSOR_ID=sensor-001
SENSOR_LOCATION=indoor
SENSOR_INTERVAL=5
CERT_PATH=./certs/device-certificate.pem.crt
PRIVATE_KEY_PATH=./certs/device-private-key.pem.key
ROOT_CA_PATH=./certs/root-CA.crt
LOG_LEVEL=INFO
"@
        $EnvPath = Join-Path $ProjectRoot ".env"
        [System.IO.File]::WriteAllText($EnvPath, $EnvContent, $Utf8NoBom)
        Write-Host "   OK: Basic .env created" -ForegroundColor Green
    }
} else {
    Write-Host "   WARNING: generate_env.py not found. Skipping .env generation." -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# STEP 5: SUMMARY
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
Write-Host "   1. Start the simulator: cd src\simulator; python sensor_simulator.py --env" -ForegroundColor Gray
Write-Host "   2. Or offline: python sensor_simulator.py --offline" -ForegroundColor Gray
Write-Host "   3. Open dashboard: start src\dashboard\index.html" -ForegroundColor Gray
Write-Host "=====================================" -ForegroundColor Cyan