# ============================================
# SMART GARDEN MANAGER - DEPLOY SCRIPT
# ============================================

param(
    [string]$Email = "",
    [string]$Region = "",
    [bool]$EnableCloudFront = $false
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Smart Garden Manager - Deployment" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# 1. AWS PROFILE SETUP
# ============================================

$availableProfiles = aws configure list-profiles 2>$null

if ($availableProfiles -contains "smart-garden") {
    $env:AWS_PROFILE = "smart-garden"
    Write-Host "Using AWS Profile: smart-garden" -ForegroundColor Cyan
}
else {
    Write-Host "WARNING: Profile 'smart-garden' not found." -ForegroundColor Yellow
    Write-Host "Using default AWS profile instead." -ForegroundColor Yellow
    Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
}

Write-Host ""

# ============================================
# 2. CONFIGURATION
# ============================================

$ErrorActionPreference = "Continue"

# Check AWS CLI
$ACCOUNT_ID = aws sts get-caller-identity `
    --query Account `
    --output text 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: AWS CLI not configured!" -ForegroundColor Red
    exit 1
}

if (-not $Region) {
    $Region = aws configure get region

    if (-not $Region) {
        $Region = "us-west-2"
    }
}

# Prompt for email if not provided as parameter
if (-not $Email) {
    $Email = Read-Host "Enter your email for SNS alerts"
}

if (-not $Email) {
    Write-Host "ERROR: Email is required!" -ForegroundColor Red
    exit 1
}

# Convert the PowerShell boolean to the string expected by
# the CloudFormation parameter.
$CloudFrontParameter = if ($EnableCloudFront) { "true" } else { "false" }

$STACK_NAME = "smart-garden"
$ENVIRONMENT_NAME = "smart-garden"

# Bucket names (base names without account ID)
$DATA_BUCKET_BASE = "smart-garden-data"
$WEBSITE_BUCKET_BASE = "smart-garden-dashboard"

# Lambda bucket (includes account ID because it needs to be globally unique)
$LAMBDA_CODE_BUCKET = "smart-garden-lambda-$ACCOUNT_ID"

Write-Host ""
Write-Host "Account ID: $ACCOUNT_ID" -ForegroundColor Cyan
Write-Host "Region: $Region" -ForegroundColor Cyan
Write-Host "Email: $Email" -ForegroundColor Cyan
Write-Host "CloudFront: $CloudFrontParameter" -ForegroundColor Cyan
Write-Host "Stack: $STACK_NAME" -ForegroundColor Cyan
Write-Host "Data Bucket Base: $DATA_BUCKET_BASE" -ForegroundColor Cyan
Write-Host "Website Bucket Base: $WEBSITE_BUCKET_BASE" -ForegroundColor Cyan
Write-Host "Lambda Bucket: $LAMBDA_CODE_BUCKET" -ForegroundColor Cyan
Write-Host ""

# ============================================
# 3. PROJECT PATHS
# ============================================

$ProjectRoot = Split-Path -Parent $PSScriptRoot

$LambdaDir = Join-Path $ProjectRoot "src\lambda"
$DashboardPath = Join-Path $ProjectRoot "src\dashboard"
$TemplatePath = Join-Path $ProjectRoot "templates\smart-garden.yaml"

$DashboardConfigPath = Join-Path $DashboardPath "config.js"

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Dashboard: $DashboardPath" -ForegroundColor Gray
Write-Host "Template: $TemplatePath" -ForegroundColor Gray
Write-Host ""

# ============================================
# 4. CHECK EXISTING FILES
# ============================================

Write-Host "Checking project files..." -ForegroundColor Yellow

$requiredFiles = @(
    (Join-Path $LambdaDir "process_data.py"),
    (Join-Path $LambdaDir "query_data.py"),
    (Join-Path $DashboardPath "index.html"),
    (Join-Path $DashboardPath "style.css"),
    (Join-Path $DashboardPath "dashboard.js"),
    $TemplatePath
)

$allFilesExist = $true

foreach ($file in $requiredFiles) {

    if (Test-Path $file) {
        Write-Host "  OK: $(Split-Path $file -Leaf)" -ForegroundColor Green
    }
    else {
        Write-Host "  MISSING: $(Split-Path $file -Leaf)" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host "ERROR: Please make sure all required files exist!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================
# 5. CREATE LAMBDA PACKAGES
# ============================================

Write-Host "Creating Lambda packages..." -ForegroundColor Yellow

$PackagesDir = Join-Path $LambdaDir "packages"

if (-not (Test-Path $PackagesDir)) {
    New-Item -ItemType Directory -Path $PackagesDir -Force | Out-Null
}

Remove-Item `
    (Join-Path $PackagesDir "*.zip") `
    -Force `
    -ErrorAction SilentlyContinue

function Create-LambdaZip {
    param(
        $SourceFile,
        $ZipName
    )

    if (-not (Test-Path $SourceFile)) {
        Write-Host "  ERROR: $SourceFile not found!" -ForegroundColor Red
        return $false
    }

    $tempDir = Join-Path $env:TEMP "lambda_$(Get-Random)"

    New-Item `
        -ItemType Directory `
        -Path $tempDir `
        -Force | Out-Null

    Copy-Item $SourceFile $tempDir

    $zipPath = Join-Path $PackagesDir $ZipName

    Compress-Archive `
        -Path "$tempDir\*" `
        -DestinationPath $zipPath `
        -Force

    Remove-Item `
        $tempDir `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue

    Write-Host "  OK: $ZipName created" -ForegroundColor Green

    return $true
}

if (-not (Create-LambdaZip `
    (Join-Path $LambdaDir "process_data.py") `
    "process-data.zip")) {

    exit 1
}

if (-not (Create-LambdaZip `
    (Join-Path $LambdaDir "query_data.py") `
    "query-data.zip")) {

    exit 1
}

Write-Host ""

# ============================================
# 6. CREATE LAMBDA CODE BUCKET
# ============================================

Write-Host "Creating Lambda code bucket in region $Region..." -ForegroundColor Yellow

$bucketExists = $false

$existingRegion = aws s3api get-bucket-location `
    --bucket $LAMBDA_CODE_BUCKET `
    --query "LocationConstraint" `
    --output text 2>$null

if ($LASTEXITCODE -eq 0) {

    if (-not $existingRegion -or $existingRegion -eq "None") {
        $existingRegion = "us-east-1"
    }

    if ($existingRegion -eq $Region) {

        Write-Host `
            "  OK: Bucket exists in correct region ($Region)" `
            -ForegroundColor Green

        $bucketExists = $true
    }
    else {

        Write-Host `
            "  WARNING: Bucket exists in $existingRegion but should be in $Region" `
            -ForegroundColor Yellow

        Write-Host `
            "  Deleting bucket to recreate in correct region..." `
            -ForegroundColor Yellow

        aws s3 rb `
            "s3://$LAMBDA_CODE_BUCKET" `
            --force `
            --region $existingRegion 2>&1

        if ($LASTEXITCODE -eq 0) {

            Write-Host "  OK: Bucket deleted" -ForegroundColor Green
            $bucketExists = $false
        }
        else {

            Write-Host `
                "  ERROR: Failed to delete bucket" `
                -ForegroundColor Red

            Write-Host `
                "  Please delete the bucket manually and try again" `
                -ForegroundColor Yellow

            exit 1
        }
    }
}

if (-not $bucketExists) {

    Write-Host `
        "  Creating bucket: $LAMBDA_CODE_BUCKET in $Region" `
        -ForegroundColor Gray

    if ($Region -eq "us-east-1") {

        aws s3api create-bucket `
            --bucket $LAMBDA_CODE_BUCKET `
            --region $Region
    }
    else {

        aws s3api create-bucket `
            --bucket $LAMBDA_CODE_BUCKET `
            --region $Region `
            --create-bucket-configuration LocationConstraint=$Region
    }

    if ($LASTEXITCODE -ne 0) {

        Write-Host `
            "  ERROR: Failed to create bucket" `
            -ForegroundColor Red

        exit 1
    }

    Write-Host `
        "  OK: Bucket created in $Region" `
        -ForegroundColor Green
}

Write-Host ""

# ============================================
# 7. UPLOAD LAMBDA CODE
# ============================================

Write-Host "Uploading Lambda code to S3..." -ForegroundColor Yellow

aws s3 rm `
    "s3://$LAMBDA_CODE_BUCKET/lambda/" `
    --recursive `
    --region $Region 2>&1

aws s3 sync `
    "$PackagesDir\" `
    "s3://$LAMBDA_CODE_BUCKET/lambda/" `
    --exclude ".gitkeep" `
    --region $Region

if ($LASTEXITCODE -ne 0) {

    Write-Host `
        "  ERROR: Upload failed" `
        -ForegroundColor Red

    exit 1
}

Write-Host "  Verifying upload..." -ForegroundColor Gray

$files = aws s3 ls `
    "s3://$LAMBDA_CODE_BUCKET/lambda/" `
    --region $Region 2>&1

Write-Host "  Files in bucket:" -ForegroundColor Gray
Write-Host $files -ForegroundColor Gray

if ($files -match "process-data.zip" -and
    $files -match "query-data.zip") {

    Write-Host `
        "  OK: Lambda code uploaded and verified" `
        -ForegroundColor Green
}
else {

    Write-Host `
        "  ERROR: Upload verification failed!" `
        -ForegroundColor Red

    exit 1
}

Write-Host ""

# ============================================
# 8. CHECK CLOUDFORMATION STACK
# ============================================

Write-Host "Checking CloudFormation stack..." -ForegroundColor Yellow

$stackExists = $false

$stackStatus = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --region $Region `
    --query "Stacks[0].StackStatus" `
    --output text 2>$null

if ($LASTEXITCODE -eq 0) {

    if ($stackStatus -match "FAILED|ROLLBACK") {

        Write-Host `
            "  WARNING: Stack in failed state. Deleting..." `
            -ForegroundColor Yellow

        aws cloudformation delete-stack `
            --stack-name $STACK_NAME `
            --region $Region

        aws cloudformation wait stack-delete-complete `
            --stack-name $STACK_NAME `
            --region $Region

        $stackExists = $false
    }
    elseif ($stackStatus -eq "CREATE_IN_PROGRESS" -or
            $stackStatus -eq "UPDATE_IN_PROGRESS") {

        Write-Host `
            "  WARNING: Stack is currently being created/updated. Waiting..." `
            -ForegroundColor Yellow

        aws cloudformation wait stack-create-complete `
            --stack-name $STACK_NAME `
            --region $Region

        $stackExists = $true
    }
    else {

        $stackExists = $true

        Write-Host `
            "  INFO: Stack exists with status: $stackStatus" `
            -ForegroundColor Gray
    }
}
else {

    Write-Host `
        "  INFO: Stack does not exist" `
        -ForegroundColor Gray
}

Write-Host ""

# ============================================
# 9. DEPLOY CLOUDFORMATION
# ============================================

Write-Host "Deploying CloudFormation stack..." -ForegroundColor Yellow

if ($EnableCloudFront) {
    Write-Host "  CloudFront mode: ENABLED (presentation/production-style)" -ForegroundColor Green
}
else {
    Write-Host "  CloudFront mode: DISABLED (development/cost-saving)" -ForegroundColor Yellow
}

Write-Host ""

if (-not $stackExists) {

    Write-Host `
        "  Creating new stack (takes 3-5 minutes)..." `
        -ForegroundColor Gray

    aws cloudformation create-stack `
        --stack-name $STACK_NAME `
        --template-body "file://$TemplatePath" `
        --parameters `
            ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT_NAME `
            ParameterKey=S3DataBucketName,ParameterValue=$DATA_BUCKET_BASE `
            ParameterKey=S3WebsiteBucketName,ParameterValue=$WEBSITE_BUCKET_BASE `
            ParameterKey=S3LambdaCodeBucketName,ParameterValue=$LAMBDA_CODE_BUCKET `
            ParameterKey=EmailAddress,ParameterValue=$Email `
            ParameterKey=EnableEmailNotifications,ParameterValue=true `
            ParameterKey=EnableCloudFront,ParameterValue=$CloudFrontParameter `
            ParameterKey=EnableCloudWatchAlarms,ParameterValue=true `
        --capabilities CAPABILITY_NAMED_IAM `
        --region $Region

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create stack!" -ForegroundColor Red
        exit 1
    }

    Write-Host "  Waiting for stack creation..." -ForegroundColor Yellow
 
    aws cloudformation wait stack-create-complete `
        --stack-name $STACK_NAME `
        --region $Region

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Stack creation failed!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Error details:" -ForegroundColor Yellow
        aws cloudformation describe-stack-events `
            --stack-name $STACK_NAME `
            --region $Region `
            --max-items 10 `
            --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].[LogicalResourceId,ResourceStatusReason]" `
            --output table
        exit 1
    }
}
else {

    Write-Host "  Updating existing stack..." -ForegroundColor Gray

    aws cloudformation update-stack `
        --stack-name $STACK_NAME `
        --template-body "file://$TemplatePath" `
        --parameters `
            ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT_NAME `
            ParameterKey=S3DataBucketName,ParameterValue=$DATA_BUCKET_BASE `
            ParameterKey=S3WebsiteBucketName,ParameterValue=$WEBSITE_BUCKET_BASE `
            ParameterKey=S3LambdaCodeBucketName,ParameterValue=$LAMBDA_CODE_BUCKET `
            ParameterKey=EmailAddress,ParameterValue=$Email `
            ParameterKey=EnableEmailNotifications,ParameterValue=true `
            ParameterKey=EnableCloudFront,ParameterValue=$CloudFrontParameter `
            ParameterKey=EnableCloudWatchAlarms,ParameterValue=true `
        --capabilities CAPABILITY_NAMED_IAM `
        --region $Region

    if ($LASTEXITCODE -ne 0) {
        if ($LASTEXITCODE -eq 1) {
            Write-Host "  INFO: No updates needed" -ForegroundColor Gray
        } else {
            Write-Host "ERROR: Stack update failed!" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host "  Waiting for stack update to complete..." -ForegroundColor Yellow
    aws cloudformation wait stack-update-complete `
        --stack-name $STACK_NAME `
        --region $Region
        
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Stack update failed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "  OK: Stack deployed!" -ForegroundColor Green
Write-Host ""

# ============================================
# 10. GET CLOUDFORMATION OUTPUTS
# ============================================

Write-Host "Reading CloudFormation outputs..." -ForegroundColor Yellow

$apiUrl = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='APIGatewayURL'].OutputValue" `
    --output text 2>$null

$websiteUrl = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" `
    --output text 2>$null

$cloudFrontUrl = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" `
    --output text 2>$null

$iotTopic = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='IoTTopic'].OutputValue" `
    --output text 2>$null

# CRITICAL: Get the ACTUAL bucket name from CloudFormation outputs
$s3WebsiteBucket = aws cloudformation describe-stacks `
    --stack-name $STACK_NAME `
    --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" `
    --output text 2>$null

# Fallback: Construct bucket name with account ID
if (-not $s3WebsiteBucket -or $s3WebsiteBucket -eq "None") {
    $s3WebsiteBucket = "$WEBSITE_BUCKET_BASE-$ACCOUNT_ID"
    Write-Host "  WARNING: Using constructed bucket name: $s3WebsiteBucket" -ForegroundColor Yellow
} else {
    Write-Host "  Using CloudFormation output: $s3WebsiteBucket" -ForegroundColor Gray
}

# ============================================
# 11. VALIDATE API URL
# ============================================

if (-not $apiUrl -or $apiUrl -eq "None") {

    Write-Host `
        "ERROR: API Gateway URL was not returned by CloudFormation!" `
        -ForegroundColor Red

    Write-Host `
        "Check the APIGatewayURL output in CloudFormation." `
        -ForegroundColor Yellow

    exit 1
}

Write-Host ""
Write-Host "CloudFormation Outputs:" -ForegroundColor Yellow

Write-Host "  API Gateway: $apiUrl" -ForegroundColor Green
Write-Host "  Website Bucket: $s3WebsiteBucket" -ForegroundColor Green

if ($websiteUrl -and $websiteUrl -ne "None") {

    Write-Host "  Website URL: $websiteUrl" -ForegroundColor Green
}

if ($cloudFrontUrl -and $cloudFrontUrl -ne "None") {

    Write-Host "  CloudFront URL: https://$cloudFrontUrl" -ForegroundColor Green
}

if ($iotTopic -and $iotTopic -ne "None") {

    Write-Host "  IoT Topic: $iotTopic" -ForegroundColor Gray
}

Write-Host ""

# ============================================
# 12. GENERATE config.js AUTOMATICALLY
# ============================================

Write-Host "Generating dashboard config.js..." -ForegroundColor Yellow

$configContent = @"
/*
 * ============================================
 * SMART GARDEN MANAGER - GENERATED CONFIG
 * ============================================
 *
 * This file is generated automatically by
 * scripts/deploy.ps1.
 *
 * DO NOT manually edit the API URL here.
 * Run deploy.ps1 again after the API changes.
 *
 * Generated:
 * $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
 * Region:
 * $Region
 * ============================================
 */

window.SMART_GARDEN_CONFIG = {
    API_URL: '$apiUrl',
    SENSOR_ID: 'sensor-001',
    REQUEST_TIMEOUT: 15000,
    REFRESH_INTERVAL: 10000
};

// Online AWS mode
window.USE_MOCK_DATA = false;

console.log('============================================');
console.log('Smart Garden Manager configuration loaded');
console.log('============================================');
console.log('API URL:', window.SMART_GARDEN_CONFIG.API_URL);
console.log('Sensor ID:', window.SMART_GARDEN_CONFIG.SENSOR_ID);
console.log('Mock Data:', window.USE_MOCK_DATA);
"@

$utf8NoBom = New-Object System.Text.UTF8Encoding $false

[System.IO.File]::WriteAllText(
    $DashboardConfigPath,
    $configContent,
    $utf8NoBom
)

if (Test-Path $DashboardConfigPath) {

    Write-Host "  OK: config.js generated successfully" -ForegroundColor Green
    Write-Host "  API URL configured automatically:" -ForegroundColor Gray
    Write-Host "  $apiUrl" -ForegroundColor Gray
}
else {

    Write-Host "ERROR: Failed to generate config.js!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================
# 13. VERIFY DASHBOARD FILES
# ============================================

Write-Host "Verifying dashboard files..." -ForegroundColor Yellow

$dashboardFiles = @(
    "index.html",
    "style.css",
    "dashboard.js",
    "config.js"
)

$dashboardFilesValid = $true

foreach ($fileName in $dashboardFiles) {

    $filePath = Join-Path $DashboardPath $fileName

    if (Test-Path $filePath) {

        Write-Host "  OK: $fileName" -ForegroundColor Green
    }
    else {

        Write-Host "  MISSING: $fileName" -ForegroundColor Red
        $dashboardFilesValid = $false
    }
}

if (-not $dashboardFilesValid) {

    Write-Host "ERROR: Dashboard files are incomplete!" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================
# 14. VERIFY dashboard.js DOES NOT CONTAIN
#     A HARD-CODED API URL
# ============================================

Write-Host "Checking dashboard.js configuration..." -ForegroundColor Yellow

$DashboardJsPath = Join-Path $DashboardPath "dashboard.js"

$dashboardJsContent = Get-Content `
    $DashboardJsPath `
    -Raw

if ($dashboardJsContent -match "execute-api\.[a-z0-9-]+\.amazonaws\.com") {

    Write-Host "WARNING: dashboard.js still contains a hard-coded API URL!" -ForegroundColor Yellow
    Write-Host "Please replace the configuration section with the config.js version." -ForegroundColor Yellow
}
else {

    Write-Host "  OK: No hard-coded API Gateway URL found in dashboard.js" -ForegroundColor Green
}

Write-Host ""

# ============================================
# 15. VERIFY BUCKET REGIONS
# ============================================

Write-Host "Verifying all buckets are in region $Region..." -ForegroundColor Yellow

# Website Bucket
$websiteBucketRegion = aws s3api get-bucket-location `
    --bucket $s3WebsiteBucket `
    --query "LocationConstraint" `
    --output text 2>$null

if (-not $websiteBucketRegion -or $websiteBucketRegion -eq "None") {
    $websiteBucketRegion = "us-east-1"
}

if ($websiteBucketRegion -ne $Region) {
    Write-Host "  WARNING: Website bucket is in $websiteBucketRegion (should be $Region)" -ForegroundColor Yellow
} else {
    Write-Host "  OK: Website bucket is in $Region" -ForegroundColor Green
}

# Data Bucket
$dataBucket = "$DATA_BUCKET_BASE-$ACCOUNT_ID"
$dataBucketRegion = aws s3api get-bucket-location `
    --bucket $dataBucket `
    --query "LocationConstraint" `
    --output text 2>$null

if (-not $dataBucketRegion -or $dataBucketRegion -eq "None") {
    $dataBucketRegion = "us-east-1"
}

if ($dataBucketRegion -ne $Region) {
    Write-Host "  WARNING: Data bucket is in $dataBucketRegion (should be $Region)" -ForegroundColor Yellow
} else {
    Write-Host "  OK: Data bucket is in $Region" -ForegroundColor Green
}

# Lambda Bucket
$lambdaBucketRegion = aws s3api get-bucket-location `
    --bucket $LAMBDA_CODE_BUCKET `
    --query "LocationConstraint" `
    --output text 2>$null

if (-not $lambdaBucketRegion -or $lambdaBucketRegion -eq "None") {
    $lambdaBucketRegion = "us-east-1"
}

if ($lambdaBucketRegion -ne $Region) {
    Write-Host "  WARNING: Lambda bucket is in $lambdaBucketRegion (should be $Region)" -ForegroundColor Yellow
} else {
    Write-Host "  OK: Lambda bucket is in $Region" -ForegroundColor Green
}

Write-Host ""

# ============================================
# 16. UPLOAD DASHBOARD (FIXED)
# ============================================

Write-Host "Uploading dashboard..." -ForegroundColor Yellow

if (Test-Path $DashboardPath) {
    
    # Use the CloudFormation bucket name
    $uploadBucket = $s3WebsiteBucket

    # Verify the bucket exists
    Write-Host "  Verifying bucket: $uploadBucket" -ForegroundColor Gray
    $bucketExists = aws s3api head-bucket --bucket $uploadBucket --region $Region 2>$null
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Bucket $uploadBucket does not exist!" -ForegroundColor Red
        Write-Host "  Available buckets:" -ForegroundColor Yellow
        
        # List all buckets to help debug
        aws s3api list-buckets --query "Buckets[?contains(Name, 'dashboard')].Name" --output table 2>&1
        
        exit 1
    }
    
    Write-Host "  Uploading dashboard files to s3://$uploadBucket..." -ForegroundColor Gray
    
    # First, ensure the bucket has the correct website configuration
    Write-Host "  Setting website configuration..." -ForegroundColor Gray
    aws s3 website "s3://$uploadBucket" `
        --index-document index.html `
        --error-document error.html `
        --region $Region 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to configure S3 website!" -ForegroundColor Red
    exit 1
}

    # Set CORS configuration for the bucket (important for browser access)
    Write-Host "  Setting CORS configuration..." -ForegroundColor Gray
    $corsConfig = @'
{
    "CORSRules": [
        {
            "AllowedOrigins": ["*"],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedHeaders": ["*"],
            "MaxAgeSeconds": 3000
        }
    ]
}
'@
    $corsFile = Join-Path $env:TEMP "cors-config.json"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($corsFile, $corsConfig, $utf8NoBom)
    
    aws s3api put-bucket-cors `
        --bucket $uploadBucket `
        --cors-configuration "file://$corsFile" `
        --region $Region 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to configure S3 CORS!" -ForegroundColor Red
    exit 1
}

    
    Remove-Item $corsFile -Force -ErrorAction SilentlyContinue

    # Upload all dashboard files with proper content types
    Write-Host "  Uploading files..." -ForegroundColor Gray
    
    # Upload HTML
    $uploadFailed = $false

aws s3 cp "$DashboardPath\index.html" "s3://$uploadBucket/index.html" `
    --content-type "text/html" `
    --cache-control "no-cache" `
    --region $Region
if ($LASTEXITCODE -ne 0) { $uploadFailed = $true }

aws s3 cp "$DashboardPath\style.css" "s3://$uploadBucket/style.css" `
    --content-type "text/css" `
    --cache-control "max-age=3600" `
    --region $Region
if ($LASTEXITCODE -ne 0) { $uploadFailed = $true }

aws s3 cp "$DashboardPath\dashboard.js" "s3://$uploadBucket/dashboard.js" `
    --content-type "application/javascript" `
    --cache-control "no-cache" `
    --region $Region
if ($LASTEXITCODE -ne 0) { $uploadFailed = $true }

aws s3 cp "$DashboardPath\config.js" "s3://$uploadBucket/config.js" `
    --content-type "application/javascript" `
    --cache-control "no-cache" `
    --region $Region
if ($LASTEXITCODE -ne 0) { $uploadFailed = $true }

if ($uploadFailed) {
    Write-Host "ERROR: One or more dashboard files failed to upload!" -ForegroundColor Red
    exit 1
}

Write-Host "  OK: Dashboard uploaded" -ForegroundColor Green else {
        Write-Host "  ERROR: Dashboard upload failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ERROR: Dashboard directory not found" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================
# 17. VERIFY config.js IN S3
# ============================================

Write-Host "Verifying config.js upload..." -ForegroundColor Yellow

# Wait a moment for S3 to propagate
Start-Sleep -Seconds 2

$configExists = aws s3api head-object `
    --bucket $uploadBucket `
    --key "config.js" `
    --region $Region 2>$null

if ($LASTEXITCODE -eq 0) {

    Write-Host "  OK: config.js exists in S3" -ForegroundColor Green
    
    # Get the actual content for verification
    $verifyFile = "$env:TEMP\config-verify-$([System.DateTime]::Now.Ticks).js"
    aws s3api get-object `
        --bucket $uploadBucket `
        --key "config.js" `
        --region $Region `
        $verifyFile 2>&1
    
    if ($LASTEXITCODE -eq 0 -and (Test-Path $verifyFile)) {
        Write-Host "  OK: config.js content verified" -ForegroundColor Green
        Write-Host "  API URL in config.js:" -ForegroundColor Gray
        Get-Content $verifyFile | Select-String "API_URL" -Context 0,0 | ForEach-Object { 
            Write-Host "    $($_.Line.Trim())" -ForegroundColor Gray
        }
        Remove-Item $verifyFile -Force -ErrorAction SilentlyContinue
    }
} else {

    Write-Host "  ERROR: config.js was not uploaded correctly!" -ForegroundColor Red
    Write-Host "  Attempting direct upload..." -ForegroundColor Yellow
    
    # Try direct upload as fallback
    aws s3 cp "$DashboardConfigPath" "s3://$uploadBucket/config.js" `
        --content-type "application/javascript" `
        --cache-control "no-cache" `
        --region $Region
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: config.js uploaded directly" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Failed to upload config.js" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# ============================================
# 18. INVALIDATE CLOUDFRONT CACHE (if enabled)
# ============================================

if ($EnableCloudFront -and $cloudFrontUrl -and $cloudFrontUrl -ne "None") {
    Write-Host "Invalidating CloudFront cache..." -ForegroundColor Yellow
    
    # Get the distribution ID
    $distributionId = aws cloudfront list-distributions `
        --query "DistributionList.Items[?Origins.Items[0].DomainName=='$s3WebsiteBucket.s3.$Region.amazonaws.com'].Id" `
        --output text 2>$null
    
    if ($distributionId -and $distributionId -ne "None") {
        Write-Host "  Distribution ID: $distributionId" -ForegroundColor Gray
        
        $invalidationId = aws cloudfront create-invalidation `
            --distribution-id $distributionId `
            --paths "/*" `
            --query "Invalidation.Id" `
            --output text 2>$null
        
        if ($invalidationId -and $invalidationId -ne "None") {
            Write-Host "  OK: Invalidation created: $invalidationId" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: Could not create invalidation" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  WARNING: Could not find CloudFront distribution" -ForegroundColor Yellow
    }
    Write-Host ""
}

# ============================================
# 19. COMPLETION
# ============================================

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETED!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Deployment Summary:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Region:" -ForegroundColor White
Write-Host "  $Region" -ForegroundColor Gray

Write-Host ""
Write-Host "CloudFront:" -ForegroundColor White
if ($EnableCloudFront) {
    Write-Host "  ENABLED" -ForegroundColor Green
}
else {
    Write-Host "  DISABLED" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "API Gateway:" -ForegroundColor White
Write-Host "  $apiUrl" -ForegroundColor Green

Write-Host ""
Write-Host "Dashboard:" -ForegroundColor White
if ($cloudFrontUrl -and $cloudFrontUrl -ne "None") {
    Write-Host "  https://$cloudFrontUrl" -ForegroundColor Green
}
elseif ($websiteUrl -and $websiteUrl -ne "None") {
    Write-Host "  $websiteUrl" -ForegroundColor Green
}
else {
    Write-Host "  http://$s3WebsiteBucket.s3-website-$Region.amazonaws.com" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Dashboard Configuration:" -ForegroundColor White
Write-Host "  $DashboardConfigPath" -ForegroundColor Gray
Write-Host "  API URL generated automatically" -ForegroundColor Green

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""

Write-Host "1. CONFIRM EMAIL:" -ForegroundColor White
Write-Host "   Check your email ($Email) and confirm the SNS subscription!"

Write-Host ""
Write-Host "2. OPEN DASHBOARD:" -ForegroundColor White

if ($cloudFrontUrl -and $cloudFrontUrl -ne "None") {
    Write-Host "   https://$cloudFrontUrl" -ForegroundColor Green
}
elseif ($websiteUrl -and $websiteUrl -ne "None") {
    Write-Host "   $websiteUrl" -ForegroundColor Green
}
else {
    Write-Host "   http://$s3WebsiteBucket.s3-website-$Region.amazonaws.com" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "3. START SENSOR SIMULATOR:" -ForegroundColor White
Write-Host "   cd src\simulator" -ForegroundColor Gray
Write-Host "   python sensor_simulator.py --api --interval 60" -ForegroundColor Gray
Write-Host "   or: python sensor_simulator.py --mqtt --interval 60" -ForegroundColor Gray
Write-Host "   offline: python sensor_simulator.py --offline --interval 60" -ForegroundColor Gray

Write-Host ""
Write-Host "4. TROUBLESHOOTING:" -ForegroundColor White
Write-Host "   If dashboard shows errors, check browser console (F12)" -ForegroundColor Gray
Write-Host "   Verify API URL in config.js matches CloudFormation output" -ForegroundColor Gray

Write-Host ""
Write-Host "5. AWS CONSOLE:" -ForegroundColor White
Write-Host "   https://console.aws.amazon.com/cloudformation/home?region=$Region#/stacks" -ForegroundColor Gray

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan