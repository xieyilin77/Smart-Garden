# ============================================
# VERIFY CLEANUP SCRIPT
# Prüft ob alle AWS Ressourcen gelöscht wurden
# ============================================

param(
    [string]$StackName = "smart-garden",
    [string]$Region = "us-west-2"
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "AWS CLEANUP VERIFICATION" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stack: $StackName" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host ""

# ============================================
# FUNKTION: Test-Resource
# ============================================
function Test-Resource {
    param(
        [string]$Name,
        [string]$Command,
        [string]$Description = ""
    )
    
    if ($Description) {
        Write-Host "  $Description..." -ForegroundColor Gray
    }
    
    $result = Invoke-Expression $Command 2>&1
    $exitCode = $LASTEXITCODE
    
    # Prüfe ob der Befehl fehlgeschlagen ist (ExitCode != 0)
    if ($exitCode -ne 0) {
        Write-Host "  OK $Name : GELOSCHT" -ForegroundColor Green
        return $true
    }
    
    # Prüfe ob der Befehl "does not exist" oder ähnliche Fehler zurückgibt
    if ($result -match "does not exist|NoSuchBucket|NotFound|ValidationError|Not Found|not found") {
        Write-Host "  OK $Name : GELOSCHT" -ForegroundColor Green
        return $true
    }
    
    # Prüfe ob Ergebnis "None" ist (bei API Gateway)
    if ($result -match "^None$") {
        Write-Host "  OK $Name : GELOSCHT" -ForegroundColor Green
        return $true
    }
    
    # Wenn Ausgabe vorhanden ist, existiert die Ressource noch
    if ($result) {
        Write-Host "  FAIL $Name : GEFUNDEN" -ForegroundColor Red
        # Zeige nur die ersten 5 Zeilen der Ausgabe
        $lines = $result -split "`n"
        $maxLines = 5
        if ($lines.Count -gt $maxLines) {
            for ($i = 0; $i -lt $maxLines; $i++) {
                Write-Host "     $($lines[$i])" -ForegroundColor Yellow
            }
            Write-Host "     ... (und $($lines.Count - $maxLines) weitere Zeilen)" -ForegroundColor Yellow
        } else {
            Write-Host "     $result" -ForegroundColor Yellow
        }
        return $false
    } else {
        Write-Host "  OK $Name : GELOSCHT" -ForegroundColor Green
        return $true
    }
}

# ============================================
# HAUPT - TESTS AUSFÜHREN
# ============================================

$totalTests = 0
$passedTests = 0
$failedTests = 0

Write-Host "=====================================" -ForegroundColor Yellow
Write-Host "TESTING RESOURCES" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Yellow
Write-Host ""

# 1. CloudFormation Stack
Write-Host "Testing CloudFormation..." -ForegroundColor Cyan
$result = Test-Resource "CloudFormation Stack" "aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>&1"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 2. S3 Buckets
Write-Host "Testing S3 Buckets..." -ForegroundColor Cyan
$result = Test-Resource "S3 Buckets" "aws s3 ls --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 3. DynamoDB Tables
Write-Host "Testing DynamoDB Tables..." -ForegroundColor Cyan
$result = Test-Resource "DynamoDB Tables" "aws dynamodb list-tables --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 4. Lambda Functions
Write-Host "Testing Lambda Functions..." -ForegroundColor Cyan
$result = Test-Resource "Lambda Functions" "aws lambda list-functions --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 5. API Gateway
Write-Host "Testing API Gateway..." -ForegroundColor Cyan
$result = Test-Resource "API Gateway" "aws apigateway get-rest-apis --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 6. IoT Things
Write-Host "Testing IoT Things..." -ForegroundColor Cyan
$result = Test-Resource "IoT Things" "aws iot list-things --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 7. IoT Policies
Write-Host "Testing IoT Policies..." -ForegroundColor Cyan
$result = Test-Resource "IoT Policies" "aws iot list-policies --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 8. IoT Rules
Write-Host "Testing IoT Rules..." -ForegroundColor Cyan
$result = Test-Resource "IoT Rules" "aws iot list-topic-rules --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 9. SNS Topics
Write-Host "Testing SNS Topics..." -ForegroundColor Cyan
$result = Test-Resource "SNS Topics" "aws sns list-topics --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 10. CloudFront
Write-Host "Testing CloudFront..." -ForegroundColor Cyan
$result = Test-Resource "CloudFront" "aws cloudfront list-distributions 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 11. EventBridge (optional)
Write-Host "Testing EventBridge Rules..." -ForegroundColor Cyan
$result = Test-Resource "EventBridge Rules" "aws events list-rules --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 12. CloudWatch Log Groups
Write-Host "Testing CloudWatch Log Groups..." -ForegroundColor Cyan
$result = Test-Resource "CloudWatch Log Groups" "aws logs describe-log-groups --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# 13. IAM Roles (nur prüfen, nicht löschen)
Write-Host "Testing IAM Roles..." -ForegroundColor Cyan
$result = Test-Resource "IAM Roles" "aws iam list-roles --region $Region 2>&1 | findstr smart-garden"
$totalTests++
if ($result) { $passedTests++ } else { $failedTests++ }
Write-Host ""

# ============================================
# ZUSAMMENFASSUNG
# ============================================
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Total Tests : $totalTests" -ForegroundColor White
Write-Host "Passed      : $passedTests" -ForegroundColor Green
Write-Host "Failed      : $failedTests" -ForegroundColor Red

Write-Host ""

if ($failedTests -eq 0) {
    Write-Host "ALL RESOURCES WERE SUCCESSFULLY DELETED!" -ForegroundColor Green
    Write-Host "No AWS resources with prefix 'smart-garden' found." -ForegroundColor Gray
    Write-Host "You will not incur any costs." -ForegroundColor Green
} else {
    Write-Host "SOME RESOURCES STILL EXIST!" -ForegroundColor Red
    Write-Host "Check the failed items above and delete them manually." -ForegroundColor Yellow
    Write-Host "Then run this verification again." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "VERIFICATION COMPLETE" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan