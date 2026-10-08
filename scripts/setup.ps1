# NERON Windows Bootstrap Script
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   NERON - Setting Up Development Environment" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Check Python version
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python 3.10+ is required but was not found in PATH." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Found Python: $pythonVersion" -ForegroundColor Green

# 2. Check virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

# 3. Activate virtual environment
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# 4. Install / Upgrade dependencies
Write-Host "[*] Installing project in editable mode with development dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -e ".[all]"

# 5. Run initial self-test
Write-Host "[*] Running initial verification test..." -ForegroundColor Yellow
python -m pytest tests/

Write-Host "=========================================" -ForegroundColor Green
Write-Host "   NERON Setup Complete!" -ForegroundColor Green
Write-Host "   Run '.\scripts\dev.ps1' to launch Neron Console." -ForegroundColor Green
Write-Host "   Run '.\scripts\test.ps1' to execute test suite." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
