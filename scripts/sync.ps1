# NERON Automatic Git Synchronization Script
param(
    [string]$Message = "",
    [switch]$Watch = $false,
    [int]$IntervalSeconds = 60
)

function Sync-Repository {
    param([string]$commitMsg)

    $status = git status --porcelain
    if ($status) {
        Write-Host "[*] Changes detected. Staging and committing..." -ForegroundColor Yellow
        git add .
        if (-not $commitMsg) {
            $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            $commitMsg = "auto-sync: $timestamp"
        }
        git commit -m $commitMsg
        Write-Host "[*] Pushing updates to origin main..." -ForegroundColor Yellow
        git push origin main
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Repository successfully synced with GitHub!" -ForegroundColor Green
        } else {
            Write-Host "[FAIL] Git push encountered an error." -ForegroundColor Red
        }
    } else {
        Write-Host "[OK] Working tree clean. Pushing any unpushed commits..." -ForegroundColor Cyan
        git push origin main
    }
}

if ($Watch) {
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "   NERON - Auto-Sync Watcher Active" -ForegroundColor Cyan
    Write-Host "   Checking for changes every $IntervalSeconds seconds..." -ForegroundColor Cyan
    Write-Host "   Press Ctrl+C to stop." -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    while ($true) {
        Sync-Repository -commitMsg $Message
        Start-Sleep -Seconds $IntervalSeconds
    }
} else {
    Sync-Repository -commitMsg $Message
}
