# ============================================
# CLEANUP SCRIPT - Delete AWS Resources
# ============================================

param(
    [string]$StackName = "smart-garden",
    [string]$Region = "us-west-2"
)

Write-Host "=====================================" -ForegroundColor Red
Write-Host "CLEANUP - Delete AWS Resources" -ForegroundColor Red
Write-Host "=====================================" -ForegroundColor Red
Write-Host ""

Write-Host "WARNING: This will delete the following resources:" -ForegroundColor Yellow
Write-Host "  - CloudFormation stack: $StackName" -ForegroundColor Gray
Write-Host "  - S3 buckets (data, website, lambda code)" -ForegroundColor Gray
Write-Host "  - DynamoDB tables" -ForegroundColor Gray
Write-Host "  - Lambda functions" -ForegroundColor Gray
Write-Host "  - API Gateway" -ForegroundColor Gray
Write-Host "  - IoT Core things and rules" -ForegroundColor Gray
Write-Host "  - IoT Policies" -ForegroundColor Gray
Write-Host "  - CloudWatch Log Groups" -ForegroundColor Gray
Write-Host ""

$confirm = Read-Host "Are you sure you want to continue? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "Cleanup cancelled." -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "Starting cleanup..." -ForegroundColor Cyan

try {
    $AccountId = aws sts get-caller-identity --query Account --output text 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "AWS CLI not configured"
    }
    Write-Host "Account ID: $AccountId" -ForegroundColor Green
} catch {
    Write-Host "AWS CLI not configured!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================
# EMPTY S3 BUCKETS
# ============================================
Write-Host "Emptying S3 buckets..." -ForegroundColor Yellow

$buckets = @(
    "smart-garden-data-$AccountId",
    "smart-garden-dashboard-$AccountId",
    "smart-garden-lambda"
)

foreach ($bucket in $buckets) {
    Write-Host "Emptying bucket: $bucket" -ForegroundColor Gray
    aws s3 rm "s3://$bucket" --recursive --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Emptied" -ForegroundColor Green
    } else {
        Write-Host "  Could not empty (may not exist)" -ForegroundColor Yellow
    }
}
Write-Host ""

# ============================================
# DELETE CLOUDWATCH LOG GROUPS
# ============================================
Write-Host "Deleting CloudWatch Log Groups..." -ForegroundColor Yellow

$logGroups = aws logs describe-log-groups --region $Region --query "logGroups[?starts_with(logGroupName, '/aws/lambda/smart-garden')].logGroupName" --output text 2>&1

if ($LASTEXITCODE -eq 0 -and $logGroups) {
    foreach ($logGroup in $logGroups) {
        Write-Host "  Deleting log group: $logGroup" -ForegroundColor Gray
        aws logs delete-log-group --log-group-name $logGroup --region $Region 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    Deleted" -ForegroundColor Green
        } else {
            Write-Host "    Could not delete" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  No CloudWatch Log Groups found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT POLICIES
# ============================================
Write-Host "Deleting IoT Policies..." -ForegroundColor Yellow

$policyName = "$StackName-iot-policy"
Write-Host "  Checking for IoT policy: $policyName" -ForegroundColor Gray

# Check if policy exists
$policyExists = aws iot get-policy --policy-name $policyName --region $Region 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Deleting IoT policy: $policyName" -ForegroundColor Gray
    
    # First, detach the policy from all principals
    $principals = aws iot list-principals --policy-name $policyName --region $Region --query "principals" --output text 2>&1
    if ($LASTEXITCODE -eq 0 -and $principals) {
        foreach ($principal in $principals) {
            Write-Host "    Detaching policy from: $principal" -ForegroundColor Gray
            aws iot detach-policy --policy-name $policyName --target $principal --region $Region 2>&1 | Out-Null
        }
    }
    
    # Delete the policy
    aws iot delete-policy --policy-name $policyName --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleted IoT policy: $policyName" -ForegroundColor Green
    } else {
        Write-Host "  Could not delete IoT policy (may have attachments)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No IoT policy found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT THINGS & CERTIFICATES
# ============================================
Write-Host "Deleting IoT Things and Certificates..." -ForegroundColor Yellow

$thingName = "$StackName-sensor"
Write-Host "  Checking for IoT thing: $thingName" -ForegroundColor Gray

# Get thing details
$thingDetails = aws iot describe-thing --thing-name $thingName --region $Region 2>&1
if ($LASTEXITCODE -eq 0) {
    # Get principal (certificate) attached to thing
    $principals = aws iot list-thing-principals --thing-name $thingName --region $Region --query "principals" --output text 2>&1
    
    if ($LASTEXITCODE -eq 0 -and $principals) {
        foreach ($principal in $principals) {
            Write-Host "  Detaching certificate: $principal" -ForegroundColor Gray
            aws iot detach-thing-principal --thing-name $thingName --principal $principal --region $Region 2>&1 | Out-Null
            
            # Extract certificate ID from ARN
            $certId = $principal -replace ".*/([^/]+)$", '$1'
            Write-Host "  Deleting certificate: $certId" -ForegroundColor Gray
            
            # Deactivate certificate first
            aws iot update-certificate --certificate-id $certId --new-status INACTIVE --region $Region 2>&1 | Out-Null
            
            # Delete certificate
            aws iot delete-certificate --certificate-id $certId --region $Region 2>&1 | Out-Null
            Write-Host "  Deleted certificate" -ForegroundColor Green
        }
    }
    
    # Delete the thing
    Write-Host "  Deleting IoT thing: $thingName" -ForegroundColor Gray
    aws iot delete-thing --thing-name $thingName --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleted IoT thing" -ForegroundColor Green
    } else {
        Write-Host "  Could not delete IoT thing" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No IoT thing found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT TOPIC RULE
# ============================================
Write-Host "Deleting IoT Topic Rule..." -ForegroundColor Yellow

$ruleName = "smart_garden_rule"
$ruleExists = aws iot get-topic-rule --rule-name $ruleName --region $Region 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Deleting IoT topic rule: $ruleName" -ForegroundColor Gray
    aws iot delete-topic-rule --rule-name $ruleName --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleted IoT topic rule" -ForegroundColor Green
    } else {
        Write-Host "  Could not delete IoT topic rule" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No IoT topic rule found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT AUTHORIZER (if exists)
# ============================================
Write-Host "Deleting IoT Authorizer..." -ForegroundColor Yellow

$authorizerName = "$StackName-authorizer"
$authorizerExists = aws iot describe-authorizer --authorizer-name $authorizerName --region $Region 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Deleting IoT authorizer: $authorizerName" -ForegroundColor Gray
    aws iot delete-authorizer --authorizer-name $authorizerName --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleted IoT authorizer" -ForegroundColor Green
    } else {
        Write-Host "  Could not delete IoT authorizer" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No IoT authorizer found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE CLOUDFORMATION STACK
# ============================================
Write-Host "Deleting CloudFormation stack..." -ForegroundColor Yellow
aws cloudformation delete-stack --stack-name $StackName --region $Region

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Stack deletion initiated" -ForegroundColor Green
} else {
    Write-Host "  Failed to delete stack" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================
# WAIT FOR STACK DELETION
# ============================================
Write-Host "Waiting for stack deletion (max 5 minutes)..." -ForegroundColor Yellow
$timeout = 300
$startTime = Get-Date

do {
    $status = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].StackStatus" --output text 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Stack deleted" -ForegroundColor Green
        break
    }
    Write-Host "  Status: $status" -ForegroundColor Gray
    Start-Sleep -Seconds 10
    $elapsed = (Get-Date) - $startTime
} while ($status -match "DELETE_IN_PROGRESS" -and $elapsed.TotalSeconds -lt $timeout)

if ($elapsed.TotalSeconds -ge $timeout) {
    Write-Host "  Timeout waiting for stack deletion" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# DELETE S3 BUCKETS
# ============================================
Write-Host "Deleting S3 buckets..." -ForegroundColor Yellow

foreach ($bucket in $buckets) {
    Write-Host "Deleting bucket: $bucket" -ForegroundColor Gray
    aws s3api delete-bucket --bucket $bucket --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Deleted" -ForegroundColor Green
    } else {
        Write-Host "  Could not delete (may not exist or not empty)" -ForegroundColor Yellow
    }
}
Write-Host ""

# ============================================
# CLEANUP SUMMARY
# ============================================
Write-Host "=====================================" -ForegroundColor Green
Write-Host "CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "The following resources have been deleted:" -ForegroundColor White
Write-Host "  - CloudFormation stack: $StackName" -ForegroundColor Gray
Write-Host "  - S3 buckets (emptied and deleted)" -ForegroundColor Gray
Write-Host "  - CloudWatch Log Groups" -ForegroundColor Gray
Write-Host "  - IoT Policies" -ForegroundColor Gray
Write-Host "  - IoT Things and Certificates" -ForegroundColor Gray
Write-Host "  - IoT Topic Rules" -ForegroundColor Gray
Write-Host "  - Associated resources (Lambda, DynamoDB, API Gateway, IoT)" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: Some resources may take a few minutes to fully delete." -ForegroundColor Yellow