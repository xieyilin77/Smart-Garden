# ============================================
# SMART GARDEN MANAGER - DEPLOY SCRIPT
# ============================================

param(
    [string]$Email = "",
    [string]$Region = "us-west-2"
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Smart Garden Manager - Deployment" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# 1. AWS PROFILE SETUP
# ============================================
$availableProfiles = aws configure list-profiles 2>$null
if ($availableProfiles -match "smart-garden") {
    $env:AWS_PROFILE = "smart-garden"
    Write-Host "Using AWS Profile: smart-garden" -ForegroundColor Cyan
} else {
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
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text 2>$null
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

$STACK_NAME = "smart-garden"
$ENVIRONMENT_NAME = "smart-garden"

# Bucket names
$DATA_BUCKET = "smart-garden-data"
$WEBSITE_BUCKET = "smart-garden-dashboard"
# NOTE: The Lambda bucket is created by this script and referenced in CloudFormation.
# The bucket name must match the S3LambdaCodeBucketName parameter in smart-garden.yaml
$LAMBDA_CODE_BUCKET = "smart-garden-lambda-$ACCOUNT_ID"

Write-Host ""
Write-Host "Account ID: $ACCOUNT_ID" -ForegroundColor Cyan
Write-Host "Region: $Region" -ForegroundColor Cyan
Write-Host "Email: $Email" -ForegroundColor Cyan
Write-Host "Stack: $STACK_NAME" -ForegroundColor Cyan
Write-Host "Data Bucket: $DATA_BUCKET" -ForegroundColor Cyan
Write-Host "Website Bucket: $WEBSITE_BUCKET" -ForegroundColor Cyan
Write-Host "Lambda Bucket: $LAMBDA_CODE_BUCKET" -ForegroundColor Cyan
Write-Host ""

# ============================================
# 3. CHECK EXISTING FILES
# ============================================
Write-Host "Checking project files..." -ForegroundColor Yellow

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LambdaDir = Join-Path $ProjectRoot "src\lambda"
$DashboardPath = Join-Path $ProjectRoot "src\dashboard"
$TemplatePath = Join-Path $ProjectRoot "templates\smart-garden.yaml"

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
    } else {
        Write-Host "  MISSING: $(Split-Path $file -Leaf)" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host "ERROR: Please make sure all files exist!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================
# 4. CREATE LAMBDA PACKAGES
# ============================================
Write-Host "Creating Lambda packages..." -ForegroundColor Yellow

$PackagesDir = Join-Path $LambdaDir "packages"
if (-not (Test-Path $PackagesDir)) {
    New-Item -ItemType Directory -Path $PackagesDir -Force | Out-Null
}

Remove-Item (Join-Path $PackagesDir "*.zip") -Force -ErrorAction SilentlyContinue

function Create-LambdaZip {
    param($SourceFile, $ZipName)
    
    if (-not (Test-Path $SourceFile)) {
        Write-Host "  ERROR: $SourceFile not found!" -ForegroundColor Red
        return $false
    }
    
    $tempDir = Join-Path $env:TEMP "lambda_$(Get-Random)"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    Copy-Item $SourceFile $tempDir
    
    $zipPath = Join-Path $PackagesDir $ZipName
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -Force
    
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-Host "  OK: $ZipName created" -ForegroundColor Green
    return $true
}

if (-not (Create-LambdaZip (Join-Path $LambdaDir "process_data.py") "process-data.zip")) { exit 1 }
if (-not (Create-LambdaZip (Join-Path $LambdaDir "query_data.py") "query-data.zip")) { exit 1 }

Write-Host ""

# ============================================
# 5. CREATE LAMBDA CODE BUCKET
# ============================================
Write-Host "Creating Lambda code bucket in region $Region..." -ForegroundColor Yellow

# Check if bucket exists and get its region
$bucketExists = $false
$existingRegion = aws s3api get-bucket-location --bucket $LAMBDA_CODE_BUCKET --query "LocationConstraint" --output text 2>$null

if ($LASTEXITCODE -eq 0) {
    # If LocationConstraint is null or "None", bucket is in us-east-1
    if (-not $existingRegion -or $existingRegion -eq "None") {
        $existingRegion = "us-east-1"
    }
    
    if ($existingRegion -eq $Region) {
        Write-Host "  OK: Bucket exists in correct region ($Region)" -ForegroundColor Green
        $bucketExists = $true
    } else {
        Write-Host "  WARNING: Bucket exists in $existingRegion but should be in $Region" -ForegroundColor Yellow
        Write-Host "  Deleting bucket to recreate in correct region..." -ForegroundColor Yellow
        aws s3 rb "s3://$LAMBDA_CODE_BUCKET" --force --region $existingRegion 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK: Bucket deleted" -ForegroundColor Green
            $bucketExists = $false
        } else {
            Write-Host "  ERROR: Failed to delete bucket" -ForegroundColor Red
            Write-Host "  Please delete the bucket manually and try again" -ForegroundColor Yellow
            exit 1
        }
    }
}

if (-not $bucketExists) {
    Write-Host "  Creating bucket: $LAMBDA_CODE_BUCKET in $Region" -ForegroundColor Gray
    
    # IMPORTANT: LocationConstraint is REQUIRED for all regions EXCEPT us-east-1
    if ($Region -eq "us-east-1") {
        aws s3api create-bucket --bucket $LAMBDA_CODE_BUCKET --region $Region
    } else {
        aws s3api create-bucket `
            --bucket $LAMBDA_CODE_BUCKET `
            --region $Region `
            --create-bucket-configuration LocationConstraint=$Region
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to create bucket" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: Bucket created in $Region" -ForegroundColor Green
}
Write-Host ""

# ============================================
# 6. UPLOAD LAMBDA CODE
# ============================================
Write-Host "Uploading Lambda code to S3..." -ForegroundColor Yellow

# Delete old files first
aws s3 rm "s3://$LAMBDA_CODE_BUCKET/lambda/" --recursive --region $Region 2>&1

# Upload new files
aws s3 sync "$PackagesDir\" "s3://$LAMBDA_CODE_BUCKET/lambda/" --exclude ".gitkeep" --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Upload failed" -ForegroundColor Red
    exit 1
}

# VERIFY
Write-Host "  Verifying upload..." -ForegroundColor Gray
$files = aws s3 ls "s3://$LAMBDA_CODE_BUCKET/lambda/" --region $Region 2>&1
Write-Host "  Files in bucket:" -ForegroundColor Gray
Write-Host $files -ForegroundColor Gray

if ($files -match "process-data.zip" -and $files -match "query-data.zip") {
    Write-Host "  OK: Lambda code uploaded and verified" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Upload verification failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================
# 7. CHECK IF STACK EXISTS
# ============================================
Write-Host "Checking CloudFormation stack..." -ForegroundColor Yellow

$stackExists = $false
$stackStatus = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $Region --query "Stacks[0].StackStatus" --output text 2>$null

if ($LASTEXITCODE -eq 0) {
    if ($stackStatus -match "FAILED|ROLLBACK") {
        Write-Host "  WARNING: Stack in failed state. Deleting..." -ForegroundColor Yellow
        aws cloudformation delete-stack --stack-name $STACK_NAME --region $Region
        aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $Region
        $stackExists = $false
    } elseif ($stackStatus -eq "CREATE_IN_PROGRESS" -or $stackStatus -eq "UPDATE_IN_PROGRESS") {
        Write-Host "  WARNING: Stack is currently being created/updated. Waiting..." -ForegroundColor Yellow
        aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $Region
        $stackExists = $true
    } else {
        $stackExists = $true
        Write-Host "  INFO: Stack exists with status: $stackStatus" -ForegroundColor Gray
    }
} else {
    Write-Host "  INFO: Stack does not exist" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# 8. DEPLOY CLOUDFORMATION
# ============================================
Write-Host "Deploying CloudFormation stack..." -ForegroundColor Yellow

if (-not $stackExists) {
    Write-Host "  Creating new stack (takes 3-5 minutes)..." -ForegroundColor Gray
    
    aws cloudformation create-stack `
        --stack-name $STACK_NAME `
        --template-body "file://$TemplatePath" `
        --parameters `
            ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT_NAME `
            ParameterKey=S3DataBucketName,ParameterValue=$DATA_BUCKET `
            ParameterKey=S3WebsiteBucketName,ParameterValue=$WEBSITE_BUCKET `
            ParameterKey=S3LambdaCodeBucketName,ParameterValue=$LAMBDA_CODE_BUCKET `
            ParameterKey=EmailAddress,ParameterValue=$Email `
            ParameterKey=EnableEmailNotifications,ParameterValue=true `
            ParameterKey=EnableCloudFront,ParameterValue=true `
            ParameterKey=EnableCloudWatchAlarms,ParameterValue=true `
        --capabilities CAPABILITY_NAMED_IAM `
        --region $Region

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create stack!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "  Waiting for stack creation..." -ForegroundColor Yellow
    aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $Region
    
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
} else {
    Write-Host "  Updating existing stack..." -ForegroundColor Gray
    
    aws cloudformation update-stack `
        --stack-name $STACK_NAME `
        --template-body "file://$TemplatePath" `
        --parameters `
            ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT_NAME `
            ParameterKey=S3DataBucketName,ParameterValue=$DATA_BUCKET `
            ParameterKey=S3WebsiteBucketName,ParameterValue=$WEBSITE_BUCKET `
            ParameterKey=S3LambdaCodeBucketName,ParameterValue=$LAMBDA_CODE_BUCKET `
            ParameterKey=EmailAddress,ParameterValue=$Email `
            ParameterKey=EnableEmailNotifications,ParameterValue=true `
            ParameterKey=EnableCloudFront,ParameterValue=true `
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
}

Write-Host "  OK: Stack deployed!" -ForegroundColor Green
Write-Host ""

# ============================================
# 9. GET OUTPUTS
# ============================================
Write-Host "Stack Outputs:" -ForegroundColor Yellow

$apiUrl = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $Region --query "Stacks[0].Outputs[?OutputKey=='APIGatewayURL'].OutputValue" --output text 2>$null
$websiteUrl = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $Region --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" --output text 2>$null
$cloudFrontUrl = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $Region --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" --output text 2>$null
$iotTopic = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $Region --query "Stacks[0].Outputs[?OutputKey=='IoTTopic'].OutputValue" --output text 2>$null
$s3WebsiteBucket = aws cloudformation describe-stacks --stack-name $STACK_NAME --region $Region --query "Stacks[0].Outputs[?OutputKey=='S3WebsiteBucket'].OutputValue" --output text 2>$null

if ($websiteUrl -and $websiteUrl -ne "None") {
    Write-Host "  Website URL: $websiteUrl" -ForegroundColor Green
}
if ($cloudFrontUrl -and $cloudFrontUrl -ne "None") {
    Write-Host "  CloudFront URL: https://$cloudFrontUrl" -ForegroundColor Green
}
if ($apiUrl -and $apiUrl -ne "None") {
    Write-Host "  API Gateway: $apiUrl" -ForegroundColor Green
}
if ($iotTopic -and $iotTopic -ne "None") {
    Write-Host "  IoT Topic: $iotTopic" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# 9.5 VERIFY BUCKET REGIONS (NEW)
# ============================================
Write-Host "Verifying all buckets are in region $Region..." -ForegroundColor Yellow

# Check Website Bucket
$websiteBucketRegion = aws s3api get-bucket-location --bucket $WEBSITE_BUCKET --query "LocationConstraint" --output text 2>$null
if (-not $websiteBucketRegion -or $websiteBucketRegion -eq "None") { 
    $websiteBucketRegion = "us-east-1" 
}

if ($websiteBucketRegion -ne $Region) {
    Write-Host "  WARNING: Website bucket is in $websiteBucketRegion (should be $Region)" -ForegroundColor Yellow
    Write-Host "  This may cause issues with CloudFront" -ForegroundColor Yellow
} else {
    Write-Host "  OK: Website bucket is in $Region" -ForegroundColor Green
}

# Check Data Bucket
$dataBucketRegion = aws s3api get-bucket-location --bucket $DATA_BUCKET --query "LocationConstraint" --output text 2>$null
if (-not $dataBucketRegion -or $dataBucketRegion -eq "None") { 
    $dataBucketRegion = "us-east-1" 
}

if ($dataBucketRegion -ne $Region) {
    Write-Host "  WARNING: Data bucket is in $dataBucketRegion (should be $Region)" -ForegroundColor Yellow
} else {
    Write-Host "  OK: Data bucket is in $Region" -ForegroundColor Green
}

# Check Lambda Code Bucket
$lambdaBucketRegion = aws s3api get-bucket-location --bucket $LAMBDA_CODE_BUCKET --query "LocationConstraint" --output text 2>$null
if (-not $lambdaBucketRegion -or $lambdaBucketRegion -eq "None") { 
    $lambdaBucketRegion = "us-east-1" 
}

if ($lambdaBucketRegion -ne $Region) {
    Write-Host "  WARNING: Lambda bucket is in $lambdaBucketRegion (should be $Region)" -ForegroundColor Yellow
    Write-Host "  This may cause issues with Lambda deployment" -ForegroundColor Yellow
} else {
    Write-Host "  OK: Lambda bucket is in $Region" -ForegroundColor Green
}
Write-Host ""

# ============================================
# 10. UPLOAD DASHBOARD
# ============================================
Write-Host "Uploading dashboard..." -ForegroundColor Yellow

if (Test-Path $DashboardPath) {
    $uploadBucket = $s3WebsiteBucket
    if (-not $uploadBucket -or $uploadBucket -eq "None") {
        $uploadBucket = $WEBSITE_BUCKET
    }
    
    # Update dashboard.js with API URL
    $DashboardJsPath = Join-Path $DashboardPath "dashboard.js"
    if ((Test-Path $DashboardJsPath) -and $apiUrl -and $apiUrl -ne "None") {
        Write-Host "  Updating dashboard.js..." -ForegroundColor Gray
        $content = Get-Content $DashboardJsPath -Raw
        $content = $content -replace "const API_URL = '.*?';", "const API_URL = '$apiUrl';"
        $content = $content -replace "window.USE_MOCK_DATA = true;", "window.USE_MOCK_DATA = false;"
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($DashboardJsPath, $content, $utf8NoBom)
        Write-Host "  OK: dashboard.js updated" -ForegroundColor Green
    }
    
    Write-Host "  Uploading to s3://$uploadBucket..." -ForegroundColor Gray
    aws s3 sync $DashboardPath "s3://$uploadBucket" --cache-control "max-age=3600" --region $Region
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: Dashboard uploaded" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Dashboard upload had issues" -ForegroundColor Yellow
    }
} else {
    Write-Host "  WARNING: Dashboard directory not found" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# 11. COMPLETION
# ============================================
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETED!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. CONFIRM EMAIL:" -ForegroundColor White
Write-Host "   Check your email ($Email) and confirm the SNS subscription!"
Write-Host ""
Write-Host "2. OPEN DASHBOARD:" -ForegroundColor White
if ($cloudFrontUrl -and $cloudFrontUrl -ne "None") {
    Write-Host "   https://$cloudFrontUrl" -ForegroundColor Green
} elseif ($websiteUrl -and $websiteUrl -ne "None") {
    Write-Host "   $websiteUrl" -ForegroundColor Green
} else {
    Write-Host "   http://$WEBSITE_BUCKET.s3-website-$Region.amazonaws.com" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "3. START SENSOR SIMULATOR:" -ForegroundColor White
Write-Host "   cd src\simulator" -ForegroundColor Gray
Write-Host "   python sensor_simulator.py" -ForegroundColor Gray
Write-Host ""
Write-Host "4. AWS Console:" -ForegroundColor White
Write-Host "   https://console.aws.amazon.com/cloudformation/home?region=$Region#/stacks" -ForegroundColor Gray
Write-Host "=====================================" -ForegroundColor Cyan