# NERON Windows Development Console Launcher
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   NERON - Launching Console" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\python.exe") {
    & .\.venv\Scripts\python.exe -m neron $args
} else {
    python -m neron $args
}
