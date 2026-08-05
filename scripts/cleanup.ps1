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
Write-Host "  - IoT Certificates (ALL)" -ForegroundColor Gray
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
# DELETE ALL IOT CERTIFICATES
# ============================================
Write-Host "Deleting ALL IoT Certificates..." -ForegroundColor Yellow

$certificatesJson = aws iot list-certificates --region $Region --query "certificates[].certificateId" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $certificatesJson) {
    $certificates = $certificatesJson | ConvertFrom-Json
    
    if ($certificates) {
        foreach ($certId in $certificates) {
            Write-Host "  Processing certificate: $certId" -ForegroundColor Gray
            
            $certArn = aws iot list-certificates --region $Region --query "certificates[?certificateId=='$certId'].certificateArn" --output text
            
            $policiesJson = aws iot list-attached-policies --target $certArn --region $Region --query "policies[].policyName" --output json 2>$null
            if ($policiesJson) {
                $policies = $policiesJson | ConvertFrom-Json
                foreach ($policy in $policies) {
                    Write-Host "    Detaching policy: $policy" -ForegroundColor Gray
                    aws iot detach-policy --policy-name $policy --target $certArn --region $Region 2>&1 | Out-Null
                }
            }
            
            $thingsJson = aws iot list-thing-principals --principal $certArn --region $Region --query "things" --output json 2>$null
            if ($thingsJson) {
                $things = $thingsJson | ConvertFrom-Json
                foreach ($thing in $things) {
                    Write-Host "    Detaching from thing: $thing" -ForegroundColor Gray
                    aws iot detach-thing-principal --thing-name $thing --principal $certArn --region $Region 2>&1 | Out-Null
                }
            }
            
            Write-Host "    Deactivating certificate..." -ForegroundColor Gray
            aws iot update-certificate --certificate-id $certId --new-status INACTIVE --region $Region 2>&1 | Out-Null
            
            Write-Host "    Deleting certificate..." -ForegroundColor Gray
            aws iot delete-certificate --certificate-id $certId --region $Region 2>&1 | Out-Null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Deleted certificate: $certId" -ForegroundColor Green
            } else {
                Write-Host "  Could not delete certificate: $certId" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  No certificates found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No certificates found" -ForegroundColor Gray
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

$logGroupsJson = aws logs describe-log-groups --region $Region --query "logGroups[?starts_with(logGroupName, '/aws/lambda/smart-garden')].logGroupName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $logGroupsJson) {
    $logGroups = $logGroupsJson | ConvertFrom-Json
    
    if ($logGroups) {
        foreach ($logGroup in $logGroups) {
            Write-Host "  Deleting log group: $logGroup" -ForegroundColor Gray
            aws logs delete-log-group --log-group-name $logGroup --region $Region 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    Deleted" -ForegroundColor Green
            } else {
                Write-Host "    Could not delete" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  No CloudWatch Log Groups found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No CloudWatch Log Groups found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT POLICIES
# ============================================
Write-Host "Deleting IoT Policies..." -ForegroundColor Yellow

$policyNamesJson = aws iot list-policies --region $Region --query "policies[?starts_with(policyName, 'smart-garden')].policyName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $policyNamesJson) {
    $policyNames = $policyNamesJson | ConvertFrom-Json
    
    if ($policyNames) {
        foreach ($policyName in $policyNames) {
            Write-Host "  Deleting IoT policy: $policyName" -ForegroundColor Gray
            
            $principalsJson = aws iot list-principals --policy-name $policyName --region $Region --query "principals" --output json 2>&1
            if ($principalsJson) {
                $principals = $principalsJson | ConvertFrom-Json
                foreach ($principal in $principals) {
                    Write-Host "    Detaching policy from: $principal" -ForegroundColor Gray
                    aws iot detach-policy --policy-name $policyName --target $principal --region $Region 2>&1 | Out-Null
                }
            }
            
            aws iot delete-policy --policy-name $policyName --region $Region 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Deleted IoT policy: $policyName" -ForegroundColor Green
            } else {
                Write-Host "  Could not delete IoT policy: $policyName" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  No IoT policies found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No IoT policies found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT THINGS
# ============================================
Write-Host "Deleting IoT Things..." -ForegroundColor Yellow

$thingNamesJson = aws iot list-things --region $Region --query "things[?starts_with(thingName, 'smart-garden')].thingName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $thingNamesJson) {
    $thingNames = $thingNamesJson | ConvertFrom-Json
    
    if ($thingNames) {
        foreach ($thingName in $thingNames) {
            Write-Host "  Deleting IoT thing: $thingName" -ForegroundColor Gray
            
            $principalsJson = aws iot list-thing-principals --thing-name $thingName --region $Region --query "principals" --output json 2>&1
            if ($principalsJson) {
                $principals = $principalsJson | ConvertFrom-Json
                foreach ($principal in $principals) {
                    Write-Host "    Detaching certificate: $principal" -ForegroundColor Gray
                    aws iot detach-thing-principal --thing-name $thingName --principal $principal --region $Region 2>&1 | Out-Null
                }
            }
            
            aws iot delete-thing --thing-name $thingName --region $Region 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Deleted IoT thing: $thingName" -ForegroundColor Green
            } else {
                Write-Host "  Could not delete IoT thing: $thingName" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  No IoT things found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No IoT things found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT TOPIC RULES
# ============================================
Write-Host "Deleting IoT Topic Rules..." -ForegroundColor Yellow

$ruleNamesJson = aws iot list-topic-rules --region $Region --query "rules[?starts_with(ruleName, 'smart_garden')].ruleName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $ruleNamesJson) {
    $ruleNames = $ruleNamesJson | ConvertFrom-Json
    
    if ($ruleNames) {
        foreach ($ruleName in $ruleNames) {
            Write-Host "  Deleting IoT topic rule: $ruleName" -ForegroundColor Gray
            aws iot delete-topic-rule --rule-name $ruleName --region $Region 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Deleted IoT topic rule: $ruleName" -ForegroundColor Green
            } else {
                Write-Host "  Could not delete IoT topic rule: $ruleName" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  No IoT topic rules found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No IoT topic rules found" -ForegroundColor Gray
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
        Write-Host "  Could not delete IoT authorizer" -ForegroundColor Red
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
Write-Host "  - IoT Certificates (ALL)" -ForegroundColor Gray
Write-Host "  - IoT Policies" -ForegroundColor Gray
Write-Host "  - IoT Things" -ForegroundColor Gray
Write-Host "  - IoT Topic Rules" -ForegroundColor Gray
Write-Host "  - CloudFormation stack: $StackName" -ForegroundColor Gray
Write-Host "  - S3 buckets (emptied and deleted)" -ForegroundColor Gray
Write-Host "  - CloudWatch Log Groups" -ForegroundColor Gray
Write-Host "  - Associated resources (Lambda, DynamoDB, API Gateway, IoT)" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: Some resources may take a few minutes to fully delete." -ForegroundColor Yellow