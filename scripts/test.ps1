# NERON Windows Test Runner Script
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   NERON - Running Automated Test Suite" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$testCmd = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $testCmd = ".\.venv\Scripts\python.exe"
}

& $testCmd -m pytest tests/ -v
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "[OK] All tests passed cleanly!" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Test suite reported failures." -ForegroundColor Red
    exit 1
}
