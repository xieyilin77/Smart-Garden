# ============================================
# BUILD SCRIPT - Create Lambda ZIP Files
# ============================================

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Building Lambda Packages" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LambdaDir = Join-Path $ProjectRoot "src\lambda"
$PackagesDir = Join-Path $LambdaDir "packages"

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "Lambda Dir: $LambdaDir" -ForegroundColor Gray
Write-Host "Packages Dir: $PackagesDir" -ForegroundColor Gray
Write-Host ""

if (!(Test-Path $PackagesDir)) {
    New-Item -ItemType Directory -Path $PackagesDir -Force | Out-Null
    Write-Host "Created packages directory" -ForegroundColor Green
}

Write-Host "Cleaning existing packages..." -ForegroundColor Yellow
Remove-Item "$PackagesDir\*.zip" -ErrorAction SilentlyContinue

Push-Location $LambdaDir

Write-Host ""
Write-Host "Building process-data.zip..." -ForegroundColor Yellow
if (Test-Path "process_data.py") {
    Compress-Archive -Path "process_data.py" -DestinationPath "$PackagesDir\process-data.zip" -Force
    Write-Host "process-data.zip created" -ForegroundColor Green
} else {
    Write-Host "process_data.py not found!" -ForegroundColor Red
}

Write-Host ""
Write-Host "Building query-data.zip..." -ForegroundColor Yellow
if (Test-Path "query_data.py") {
    Compress-Archive -Path "query_data.py" -DestinationPath "$PackagesDir\query-data.zip" -Force
    Write-Host "query-data.zip created" -ForegroundColor Green
} else {
    Write-Host "query_data.py not found!" -ForegroundColor Red
}

Pop-Location

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Build Summary" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $PackagesDir) {
    Get-ChildItem $PackagesDir -Filter "*.zip" | ForEach-Object {
        $size = [math]::Round($_.Length / 1KB, 2)
        Write-Host "  $($_.Name) - $size KB" -ForegroundColor Gray
    }
} else {
    Write-Host "No packages found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green