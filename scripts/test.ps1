# ============================================
# TEST SCRIPT for Smart Garden Manager
# Windows PowerShell Version - Fully Fixed
# ============================================

# Fix Unicode/Encoding issues with Python output
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Smart Garden Manager - Test Suite" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# CONFIGURATION
# ============================================

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LambdaDir = Join-Path $ProjectRoot "src\lambda"
$DashboardDir = Join-Path $ProjectRoot "src\dashboard"
$SimulatorDir = Join-Path $ProjectRoot "src\simulator"
$TemplatesDir = Join-Path $ProjectRoot "templates"

$STACK_NAME = "smart-garden"
$REGION = aws configure get region 2>&1
if ($LASTEXITCODE -ne 0 -or -not $REGION) {
    $REGION = "us-west-2" 
}

# ============================================
# FUNCTION: Test Result Display
# ============================================

function Write-TestResult {
    param(
        [string]$TestName,
        [bool]$Passed,
        [string]$Message = ""
    )
    
    if ($Passed) {
        Write-Host "  [PASSED] $TestName" -ForegroundColor Green
        if ($Message) {
            Write-Host "           $Message" -ForegroundColor Gray
        }
    } else {
        Write-Host "  [FAILED] $TestName" -ForegroundColor Red
        if ($Message) {
            Write-Host "           $Message" -ForegroundColor Red
        }
    }
}

# ============================================
# SECTION 1: OFFLINE TESTS
# ============================================

Write-Host "=====================================" -ForegroundColor Yellow
Write-Host "SECTION 1: OFFLINE TESTS" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Yellow
Write-Host ""

# ------------------------------------------------------------
# Test 1: Check Project Structure
# ------------------------------------------------------------
Write-Host "Testing Project Structure..." -ForegroundColor Cyan

$allStructureTestsPassed = $true

$dirs = @(
    $TemplatesDir,
    $LambdaDir,
    $DashboardDir,
    $SimulatorDir
)

foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "  [OK] $(Split-Path $dir -Leaf) directory" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $(Split-Path $dir -Leaf) directory" -ForegroundColor Red
        $allStructureTestsPassed = $false
    }
}

$files = @(
    "smart-garden.yaml",
    "process_data.py",
    "query_data.py",
    "index.html",
    "style.css",
    "dashboard.js",
    "sensor_simulator.py"
)

foreach ($file in $files) {
    $path = ""
    switch ($file) {
        "smart-garden.yaml" { $path = Join-Path $TemplatesDir $file }
        "process_data.py" { $path = Join-Path $LambdaDir $file }
        "query_data.py" { $path = Join-Path $LambdaDir $file }
        "index.html" { $path = Join-Path $DashboardDir $file }
        "style.css" { $path = Join-Path $DashboardDir $file }
        "dashboard.js" { $path = Join-Path $DashboardDir $file }
        "sensor_simulator.py" { $path = Join-Path $SimulatorDir $file }
    }
    
    if (Test-Path $path) {
        Write-Host "  [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $file" -ForegroundColor Red
        $allStructureTestsPassed = $false
    }
}

if ($allStructureTestsPassed) {
    Write-TestResult "Project Structure" $true
} else {
    Write-TestResult "Project Structure" $false "Missing files or directories"
}
Write-Host ""

# ------------------------------------------------------------
# Test 2: Check Python Files Syntax
# ------------------------------------------------------------
Write-Host "Testing Python Syntax..." -ForegroundColor Cyan

$pythonFiles = @(
    (Join-Path $LambdaDir "process_data.py"),
    (Join-Path $LambdaDir "query_data.py"),
    (Join-Path $SimulatorDir "sensor_simulator.py")
)

$allPythonValid = $true
foreach ($file in $pythonFiles) {
    if (Test-Path $file) {
        $result = python -m py_compile $file 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] $(Split-Path $file -Leaf) - Valid syntax" -ForegroundColor Green
        } else {
            Write-Host "  [ERROR] $(Split-Path $file -Leaf) - Invalid syntax" -ForegroundColor Red
            $allPythonValid = $false
        }
    } else {
        Write-Host "  [MISSING] $(Split-Path $file -Leaf)" -ForegroundColor Red
        $allPythonValid = $false
    }
}

if ($allPythonValid) {
    Write-TestResult "Python Syntax" $true
} else {
    Write-TestResult "Python Syntax" $false "Some files have syntax errors"
}
Write-Host ""

# ------------------------------------------------------------
# Test 3: Check Lambda Files Import
# ------------------------------------------------------------
Write-Host "Testing Lambda Files Import..." -ForegroundColor Cyan

$processTestPassed = $false
$processFile = Join-Path $LambdaDir "process_data.py"
if (Test-Path $processFile) {
    Write-Host "  Testing process_data.py (offline mode)..." -ForegroundColor Gray
    $result = python -c @"
import sys
import os
sys.path.insert(0, r'$LambdaDir')
os.environ['LATEST_TABLE'] = 'smart-garden-sensor-latest'
os.environ['HISTORY_TABLE'] = 'smart-garden-sensor-data'
os.environ['DATA_BUCKET'] = 'smart-garden-data-123'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:test'
try:
    from process_data import lambda_handler
    print('OK')
except Exception as e:
    print('ERROR: ' + str(e))
"@ 2>&1
    
    if ($LASTEXITCODE -eq 0 -and $result -match "OK") {
        $processTestPassed = $true
        Write-Host "  [OK] process_data.py imports successfully" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] process_data.py import failed" -ForegroundColor Red
        Write-Host "         $result" -ForegroundColor Gray
    }
} else {
    Write-Host "  [MISSING] process_data.py" -ForegroundColor Red
}

$queryTestPassed = $false
$queryFile = Join-Path $LambdaDir "query_data.py"
if (Test-Path $queryFile) {
    Write-Host "  Testing query_data.py (offline mode)..." -ForegroundColor Gray
    $result = python -c @"
import sys
import os
sys.path.insert(0, r'$LambdaDir')
os.environ['LATEST_TABLE'] = 'smart-garden-sensor-latest'
os.environ['HISTORY_TABLE'] = 'smart-garden-sensor-data'
try:
    from query_data import lambda_handler
    print('OK')
except Exception as e:
    print('ERROR: ' + str(e))
"@ 2>&1
    
    if ($LASTEXITCODE -eq 0 -and $result -match "OK") {
        $queryTestPassed = $true
        Write-Host "  [OK] query_data.py imports successfully" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] query_data.py import failed" -ForegroundColor Red
        Write-Host "         $result" -ForegroundColor Gray
    }
} else {
    Write-Host "  [MISSING] query_data.py" -ForegroundColor Red
}

if ($processTestPassed -and $queryTestPassed) {
    Write-TestResult "Lambda Import" $true
} else {
    Write-TestResult "Lambda Import" $false "Some imports failed"
}
Write-Host ""

# ------------------------------------------------------------
# Test 4: Check Dashboard Mock Mode
# ------------------------------------------------------------
Write-Host "Checking Dashboard Mock Mode..." -ForegroundColor Cyan

$dashboardJsPath = Join-Path $DashboardDir "dashboard.js"
if (Test-Path $dashboardJsPath) {
    $content = Get-Content $dashboardJsPath -Raw
    if ($content -match 'window\.USE_MOCK_DATA\s*=\s*true') {
        Write-TestResult "Dashboard Mock Mode" $true "Mock mode is ENABLED (offline development)"
    } elseif ($content -match 'window\.USE_MOCK_DATA\s*=\s*false') {
        Write-TestResult "Dashboard Mock Mode" $true "Mock mode is DISABLED (AWS mode)"
    } else {
        Write-TestResult "Dashboard Mock Mode" $false "Could not determine mock mode"
    }
} else {
    Write-TestResult "Dashboard Mock Mode" $false "dashboard.js not found"
}
Write-Host ""

# ------------------------------------------------------------
# Test 5: Test Sensor Simulator (FIXED)
# ------------------------------------------------------------
Write-Host "Testing Sensor Simulator..." -ForegroundColor Cyan

$simulatorPath = Join-Path $SimulatorDir "sensor_simulator.py"
if (Test-Path $simulatorPath) {
    Write-Host "  Running quick test (2 readings)..." -ForegroundColor Gray
    
    # Create temporary Python script to avoid inline syntax issues
    $tempScript = @"
import sys
sys.path.insert(0, r'$SimulatorDir')
try:
    from sensor_simulator import SmartGardenSensor
    sensor = SmartGardenSensor('test-sensor', 'indoor')
    count = 0
    for i in range(2):
        reading = sensor.generate_reading()
        count += 1
    print('OK:' + str(count))
except Exception as e:
    print('ERROR: ' + str(e))
"@
    
    $tempFile = Join-Path $env:TEMP "sim_test.py"
    $tempScript | Out-File -FilePath $tempFile -Encoding UTF8 -Force
    
    $result = python $tempFile 2>&1
    $exitCode = $LASTEXITCODE
    
    Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    
    if ($exitCode -eq 0 -and $result -match "OK:2") {
        Write-TestResult "Sensor Simulator" $true "Simulator runs successfully"
    } else {
        Write-TestResult "Sensor Simulator" $false "Simulator failed"
        Write-Host "  Error: $result" -ForegroundColor Gray
    }
} else {
    Write-TestResult "Sensor Simulator" $false "sensor_simulator.py not found"
}
Write-Host ""

# ============================================
# SECTION 2: AWS TESTS (Optional)
# ============================================

Write-Host "=====================================" -ForegroundColor Yellow
Write-Host "SECTION 2: AWS TESTS" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Yellow
Write-Host ""

# ------------------------------------------------------------
# Test 6: Check AWS CLI
# ------------------------------------------------------------
Write-Host "Testing AWS CLI Configuration..." -ForegroundColor Cyan

$awsConfigured = $false
aws sts get-caller-identity 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    $awsConfigured = $true
    $accountId = aws sts get-caller-identity --query Account --output text 2>&1
    Write-TestResult "AWS CLI" $true "Account: $accountId"
} else {
    Write-TestResult "AWS CLI" $false "Not configured or credentials expired"
    Write-Host "  Run: aws configure" -ForegroundColor Yellow
}
Write-Host ""

# ------------------------------------------------------------
# Test 7: Check CloudFormation Stack
# ------------------------------------------------------------
if ($awsConfigured) {
    Write-Host "Testing CloudFormation Stack..." -ForegroundColor Cyan
    
    $stackInfo = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION 2>&1
    if ($LASTEXITCODE -eq 0) {
        $stackStatus = aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].StackStatus' --output text --region $REGION 2>&1
        Write-TestResult "CloudFormation Stack" $true "Status: $stackStatus"
        
        $websiteUrl = aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' --output text --region $REGION 2>&1
        if ($websiteUrl -and $websiteUrl -ne "None") {
            Write-Host "  Website: https://$websiteUrl" -ForegroundColor Gray
        }
    } else {
        Write-TestResult "CloudFormation Stack" $false "Stack not deployed"
        Write-Host "  Run: .\scripts\deploy.ps1" -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping CloudFormation test (AWS CLI not configured)" -ForegroundColor Yellow
}
Write-Host ""

# ------------------------------------------------------------
# Test 8: Test API Gateway
# ------------------------------------------------------------
if ($awsConfigured) {
    Write-Host "Testing API Gateway..." -ForegroundColor Cyan
    
    $apiUrl = aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`APIGatewayURL`].OutputValue' --output text --region $REGION 2>&1
    
    if ($LASTEXITCODE -eq 0 -and $apiUrl -and $apiUrl -ne "None") {
        Write-Host "  API URL: $apiUrl" -ForegroundColor Gray
        try {
            $response = Invoke-RestMethod -Uri "$apiUrl?sensor_id=sensor-001&hours=24" -Method Get -TimeoutSec 10 -ErrorAction SilentlyContinue
            if ($response) {
                Write-TestResult "API Gateway" $true "API is reachable"
            }
        } catch {
            Write-TestResult "API Gateway" $false "API not reachable"
        }
    } else {
        Write-TestResult "API Gateway" $false "API URL not found"
    }
} else {
    Write-Host "Skipping API Gateway test (AWS CLI not configured)" -ForegroundColor Yellow
}
Write-Host ""

# ------------------------------------------------------------
# Test 9: Check DynamoDB Tables
# ------------------------------------------------------------
if ($awsConfigured) {
    Write-Host "Checking DynamoDB Tables..." -ForegroundColor Cyan
    
    $tables = @("smart-garden-sensor-latest", "smart-garden-sensor-data")
    $allTablesExist = $true
    
    foreach ($table in $tables) {
        $tableInfo = aws dynamodb describe-table --table-name $table --region $REGION 2>&1
        if ($LASTEXITCODE -eq 0) {
            $status = aws dynamodb describe-table --table-name $table --query "Table.TableStatus" --output text --region $REGION 2>&1
            Write-Host "  [OK] $table - Status: $status" -ForegroundColor Green
        } else {
            Write-Host "  [MISSING] $table" -ForegroundColor Red
            $allTablesExist = $false
        }
    }
    
    if ($allTablesExist) {
        Write-TestResult "DynamoDB Tables" $true
    } else {
        Write-TestResult "DynamoDB Tables" $false "Some tables missing"
    }
} else {
    Write-Host "Skipping DynamoDB test (AWS CLI not configured)" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# SECTION 3: SUMMARY
# ============================================

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Offline Tests:" -ForegroundColor Green
Write-Host "  - Project Structure: Checked" -ForegroundColor Gray
Write-Host "  - Python Syntax: Checked" -ForegroundColor Gray
Write-Host "  - Lambda Import: Tested" -ForegroundColor Gray
Write-Host "  - Dashboard Mock Mode: Checked" -ForegroundColor Gray
Write-Host "  - Sensor Simulator: Tested" -ForegroundColor Gray
Write-Host ""

if ($awsConfigured) {
    Write-Host "AWS Tests:" -ForegroundColor Green
    Write-Host "  - AWS CLI: Configured" -ForegroundColor Gray
    Write-Host "  - CloudFormation: Checked" -ForegroundColor Gray
    Write-Host "  - API Gateway: Tested" -ForegroundColor Gray
    Write-Host "  - DynamoDB: Checked" -ForegroundColor Gray
} else {
    Write-Host "AWS Tests: Skipped (AWS CLI not configured)" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# RECOMMENDATIONS
# ============================================

Write-Host "=====================================" -ForegroundColor Yellow
Write-Host "RECOMMENDATIONS" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Yellow
Write-Host ""

if (-not $awsConfigured) {
    Write-Host "1. Configure AWS CLI:" -ForegroundColor White
    Write-Host "   aws configure" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "2. For offline development:" -ForegroundColor White
Write-Host "   cd src\simulator" -ForegroundColor Gray
Write-Host "   python sensor_simulator.py --offline" -ForegroundColor Gray
Write-Host ""

Write-Host "3. Open dashboard (offline):" -ForegroundColor White
Write-Host "   start src\dashboard\index.html" -ForegroundColor Gray
Write-Host ""

Write-Host "4. Deploy to AWS (when account is ready):" -ForegroundColor White
Write-Host "   cd scripts" -ForegroundColor Gray
Write-Host "   .\deploy.ps1" -ForegroundColor Gray
Write-Host ""

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "TEST COMPLETED" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan