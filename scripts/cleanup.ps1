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

# ============================================
# VALIDATE AWS CLI CONFIGURATION
# ============================================
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
# DELETE SMART GARDEN IOT CERTIFICATES ONLY
# ============================================
Write-Host "Deleting Smart Garden IoT Certificates..." -ForegroundColor Yellow

$thingNamesJson = aws iot list-things --region $Region --query "things[?starts_with(thingName, 'smart-garden')].thingName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $thingNamesJson -and $thingNamesJson -ne "null" -and $thingNamesJson -ne "[]") {
    try {
        $thingNames = $thingNamesJson | ConvertFrom-Json
        
        if ($thingNames -and $thingNames.Count -gt 0) {
            Write-Host "  Found $($thingNames.Count) Smart Garden things" -ForegroundColor Gray
            
            foreach ($thingName in $thingNames) {
                Write-Host "  Processing certificates for thing: $thingName" -ForegroundColor Gray
                
                $principalsJson = aws iot list-thing-principals --thing-name $thingName --region $Region --query "principals" --output json 2>&1
                
                if ($LASTEXITCODE -eq 0 -and $principalsJson -and $principalsJson -ne "null" -and $principalsJson -ne "[]") {
                    try {
                        $principals = $principalsJson | ConvertFrom-Json
                        
                        foreach ($principal in $principals) {
                            if ($principal -match 'certificate/([^/]+)$') {
                                $certId = $matches[1]
                                Write-Host "    Processing certificate: $certId" -ForegroundColor Gray
                                
                                if (-not $DryRun) {
                                    # Policies detachen
                                    $policiesJson = aws iot list-attached-policies --target $principal --region $Region --query "policies[].policyName" --output json 2>&1
                                    if ($LASTEXITCODE -eq 0 -and $policiesJson -and $policiesJson -ne "null" -and $policiesJson -ne "[]") {
                                        try {
                                            $policies = $policiesJson | ConvertFrom-Json
                                            foreach ($policy in $policies) {
                                                Write-Host "      Detaching policy: $policy" -ForegroundColor Gray
                                                aws iot detach-policy --policy-name $policy --target $principal --region $Region 2>&1 | Out-Null
                                            }
                                        } catch {
                                            Write-Host "      No policies to detach" -ForegroundColor Gray
                                        }
                                    }
                                    
                                    # Certificate deaktivieren
                                    Write-Host "      Deactivating certificate..." -ForegroundColor Gray
                                    aws iot update-certificate --certificate-id $certId --new-status INACTIVE --region $Region 2>&1 | Out-Null
                                    
                                    # Certificate löschen
                                    Write-Host "      Deleting certificate..." -ForegroundColor Gray
                                    aws iot delete-certificate --certificate-id $certId --region $Region 2>&1 | Out-Null
                                    
                                    if ($LASTEXITCODE -eq 0) {
                                        Write-Host "    ✅ Deleted certificate: $certId" -ForegroundColor Green
                                    } else {
                                        Write-Host "    ❌ Could not delete certificate: $certId" -ForegroundColor Red
                                    }
                                } else {
                                    Write-Host "    🔍 [DRY RUN] Would delete certificate: $certId" -ForegroundColor Cyan
                                }
                            }
                        }
                    } catch {
                        Write-Host "    Error parsing principals: $_" -ForegroundColor Yellow
                    }
                } else {
                    Write-Host "    No certificates attached to thing: $thingName" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "  No Smart Garden things found" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  Error: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No Smart Garden things found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# EMPTY AND DELETE S3 BUCKETS
# ============================================
Write-Host "Emptying and deleting S3 buckets..." -ForegroundColor Yellow

# List of buckets to delete (with account ID suffix)
$buckets = @(
    "smart-garden-data-$AccountId",
    "smart-garden-dashboard-$AccountId",
    "smart-garden-lambda-$AccountId"
)

foreach ($bucket in $buckets) {
    Write-Host "Processing bucket: $bucket" -ForegroundColor Gray
    
    # 1. Check if bucket exists
    Write-Host "  Checking if bucket exists..." -ForegroundColor Gray
    aws s3api head-bucket --bucket $bucket --region $Region 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Bucket does not exist, skipping" -ForegroundColor Yellow
        continue
    }
    Write-Host "  Bucket exists" -ForegroundColor Green
    
    # 2. Check and handle versioning (if enabled)
    Write-Host "  Checking versioning configuration..." -ForegroundColor Gray
    $versioning = aws s3api get-bucket-versioning --bucket $bucket --region $Region 2>&1
    if ($LASTEXITCODE -eq 0 -and $versioning -match '"Status": "Enabled"') {
        Write-Host "  Versioning is enabled - removing all versions..." -ForegroundColor Yellow
        
        # Delete all object versions
        Write-Host "    Deleting all object versions..." -ForegroundColor Gray
        $versions = aws s3api list-object-versions --bucket $bucket --region $Region --query "Versions[].{Key:Key,VersionId:VersionId}" --output json 2>&1
        if ($LASTEXITCODE -eq 0 -and $versions -and $versions -ne "null" -and $versions -ne "[]") {
            try {
                $versionsList = $versions | ConvertFrom-Json
                $versionCount = $versionsList.Count
                Write-Host "    Found $versionCount versions to delete" -ForegroundColor Gray
                foreach ($v in $versionsList) {
                    aws s3api delete-object --bucket $bucket --key $v.Key --version-id $v.VersionId --region $Region 2>&1 | Out-Null
                }
                Write-Host "    Deleted all versions" -ForegroundColor Green
            } catch {
                Write-Host "    Could not delete versions" -ForegroundColor Yellow
            }
        }
        
        # Delete all delete markers
        Write-Host "    Deleting all delete markers..." -ForegroundColor Gray
        $markers = aws s3api list-object-versions --bucket $bucket --region $Region --query "DeleteMarkers[].{Key:Key,VersionId:VersionId}" --output json 2>&1
        if ($LASTEXITCODE -eq 0 -and $markers -and $markers -ne "null" -and $markers -ne "[]") {
            try {
                $markersList = $markers | ConvertFrom-Json
                $markerCount = $markersList.Count
                Write-Host "    Found $markerCount delete markers" -ForegroundColor Gray
                foreach ($m in $markersList) {
                    aws s3api delete-object --bucket $bucket --key $m.Key --version-id $m.VersionId --region $Region 2>&1 | Out-Null
                }
                Write-Host "    Deleted all delete markers" -ForegroundColor Green
            } catch {
                Write-Host "    Could not delete delete markers" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "  Versioning is not enabled" -ForegroundColor Gray
    }
    
    # 3. Empty the bucket contents (with retry logic)
    Write-Host "  Emptying bucket contents..." -ForegroundColor Gray
    $maxRetries = 3
    $retryCount = 0
    $emptied = $false
    
    while ($retryCount -lt $maxRetries -and -not $emptied) {
        $retryCount++
        Write-Host "    Attempt $retryCount/$maxRetries..." -ForegroundColor Gray
        
        # Delete all objects in the bucket
        aws s3 rm "s3://$bucket" --recursive --region $Region 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    Bucket emptied successfully" -ForegroundColor Green
            $emptied = $true
        } else {
            Write-Host "    Failed to empty bucket, retrying..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }
    
    # 4. If bucket couldn't be emptied, force delete it
    if (-not $emptied) {
        Write-Host "  WARNING: Could not empty bucket after $maxRetries attempts" -ForegroundColor Red
        Write-Host "  Attempting force deletion with --force..." -ForegroundColor Yellow
        
        # Force delete using s3 rb with --force flag
        aws s3 rb "s3://$bucket" --force --region $Region 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Bucket force-deleted successfully" -ForegroundColor Green
            continue
        }
    }
    
    # 5. Delete the bucket (only if successfully emptied)
    if ($emptied) {
        Write-Host "  Deleting bucket..." -ForegroundColor Gray
        aws s3api delete-bucket --bucket $bucket --region $Region 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Bucket deleted successfully" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: Could not delete bucket (may contain objects)" -ForegroundColor Yellow
            
            # Final attempt: Force delete
            Write-Host "  Attempting force delete..." -ForegroundColor Yellow
            aws s3 rb "s3://$bucket" --force --region $Region 2>&1 | Out-Null
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Bucket force-deleted" -ForegroundColor Green
            } else {
                Write-Host "  Could not delete bucket. Please check manually in AWS Console." -ForegroundColor Red
            }
        }
    }
}
Write-Host ""

# ============================================
# DELETE CLOUDWATCH LOG GROUPS (BEFORE STACK DELETION)
# ============================================
Write-Host "Deleting CloudWatch Log Groups (before stack deletion)..." -ForegroundColor Yellow

# Find all log groups with "smart-garden" in the name
$logGroupsJson = aws logs describe-log-groups --region $Region --query "logGroups[?contains(logGroupName, 'smart-garden') || contains(logGroupName, 'smart_garden')].logGroupName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $logGroupsJson -and $logGroupsJson -ne "null" -and $logGroupsJson -ne "[]") {
    try {
        $logGroups = $logGroupsJson | ConvertFrom-Json
        
        if ($logGroups) {
            Write-Host "  Found $($logGroups.Count) log groups to delete" -ForegroundColor Gray
            
            foreach ($logGroup in $logGroups) {
                Write-Host "  Deleting log group: $logGroup" -ForegroundColor Gray
                
                # Multiple attempts to delete (sometimes needs retry)
                $retryCount = 0
                $maxRetries = 3
                $deleted = $false
                
                while ($retryCount -lt $maxRetries -and -not $deleted) {
                    $retryCount++
                    aws logs delete-log-group --log-group-name $logGroup --region $Region 2>&1 | Out-Null
                    
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "    Deleted (attempt $retryCount)" -ForegroundColor Green
                        $deleted = $true
                    } else {
                        Write-Host "    Retry $retryCount/$maxRetries..." -ForegroundColor Yellow
                        Start-Sleep -Seconds 2
                    }
                }
                
                if (-not $deleted) {
                    Write-Host "    Could not delete after $maxRetries attempts" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  No CloudWatch Log Groups found" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  Error parsing log groups: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No CloudWatch Log Groups found" -ForegroundColor Gray
}
Write-Host ""

# ============================================
# DELETE IOT POLICIES
# ============================================
Write-Host "Deleting IoT Policies..." -ForegroundColor Yellow

# Get all IoT policies with "smart-garden" prefix
$policyNamesJson = aws iot list-policies --region $Region --query "policies[?starts_with(policyName, 'smart-garden')].policyName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $policyNamesJson -and $policyNamesJson -ne "null" -and $policyNamesJson -ne "[]") {
    try {
        $policyNames = $policyNamesJson | ConvertFrom-Json
        
        if ($policyNames) {
            foreach ($policyName in $policyNames) {
                Write-Host "  Deleting IoT policy: $policyName" -ForegroundColor Gray
                
                # Detach all principals from the policy
                $principalsJson = aws iot list-principals --policy-name $policyName --region $Region --query "principals" --output json 2>&1
                if ($LASTEXITCODE -eq 0 -and $principalsJson -and $principalsJson -ne "null" -and $principalsJson -ne "[]") {
                    try {
                        $principals = $principalsJson | ConvertFrom-Json
                        if ($principals) {
                            foreach ($principal in $principals) {
                                Write-Host "    Detaching policy from: $principal" -ForegroundColor Gray
                                aws iot detach-policy --policy-name $policyName --target $principal --region $Region 2>&1 | Out-Null
                            }
                        }
                    } catch {
                        Write-Host "    No principals to detach" -ForegroundColor Gray
                    }
                } else {
                    Write-Host "    No principals attached" -ForegroundColor Gray
                }
                
                # Delete the policy
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
    } catch {
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

# Get all IoT things with "smart-garden" prefix
$thingNamesJson = aws iot list-things --region $Region --query "things[?starts_with(thingName, 'smart-garden')].thingName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $thingNamesJson -and $thingNamesJson -ne "null" -and $thingNamesJson -ne "[]") {
    try {
        $thingNames = $thingNamesJson | ConvertFrom-Json
        
        if ($thingNames) {
            foreach ($thingName in $thingNames) {
                Write-Host "  Deleting IoT thing: $thingName" -ForegroundColor Gray
                
                # Detach all principals from the thing
                $principalsJson = aws iot list-thing-principals --thing-name $thingName --region $Region --query "principals" --output json 2>&1
                if ($LASTEXITCODE -eq 0 -and $principalsJson -and $principalsJson -ne "null" -and $principalsJson -ne "[]") {
                    try {
                        $principals = $principalsJson | ConvertFrom-Json
                        foreach ($principal in $principals) {
                            Write-Host "    Detaching certificate: $principal" -ForegroundColor Gray
                            aws iot detach-thing-principal --thing-name $thingName --principal $principal --region $Region 2>&1 | Out-Null
                        }
                    } catch {
                        # No principals to detach - continue
                    }
                }
                
                # Delete the thing
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
    } catch {
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

# Get all IoT topic rules with "smart_garden" prefix
$ruleNamesJson = aws iot list-topic-rules --region $Region --query "rules[?starts_with(ruleName, 'smart_garden')].ruleName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $ruleNamesJson -and $ruleNamesJson -ne "null" -and $ruleNamesJson -ne "[]") {
    try {
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
    } catch {
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
aws iot describe-authorizer --authorizer-name $authorizerName --region $Region 2>&1
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
# DELETE CLOUDWATCH LOG GROUPS (AFTER STACK DELETION)
# ============================================
Write-Host "Deleting remaining CloudWatch Log Groups (after stack deletion)..." -ForegroundColor Yellow

# Try again to delete log groups now that the stack is gone
$logGroupsJson = aws logs describe-log-groups --region $Region --query "logGroups[?contains(logGroupName, 'smart-garden') || contains(logGroupName, 'smart_garden')].logGroupName" --output json 2>&1

if ($LASTEXITCODE -eq 0 -and $logGroupsJson -and $logGroupsJson -ne "null" -and $logGroupsJson -ne "[]") {
    try {
        $logGroups = $logGroupsJson | ConvertFrom-Json
        
        if ($logGroups) {
            Write-Host "  Found $($logGroups.Count) remaining log groups" -ForegroundColor Gray
            
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
            Write-Host "  No remaining CloudWatch Log Groups found" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  No remaining CloudWatch Log Groups found" -ForegroundColor Gray
    }
} else {
    Write-Host "  No remaining CloudWatch Log Groups found" -ForegroundColor Gray
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
Write-Host ""
Write-Host "To verify everything is deleted, run:" -ForegroundColor Cyan
Write-Host "  .\verify-cleanup.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "=====================================" -ForegroundColor Green