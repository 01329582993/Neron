# PowerShell script to package Neron for Windows
param (
    [string]$OutputDir = "build/windows",
    [switch]$RunBuild
)

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Neron Windows Packaging Engine                        " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$pythonCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Run Python builder to generate .spec and .iss files
Write-Host "[*] Generating PyInstaller spec and InnoSetup script..." -ForegroundColor Yellow
python -c @"
from neron.packaging import PackageBuilder, PackagingConfig
builder = PackageBuilder()
cfg = PackagingConfig(target_os='windows')
res = builder.build_windows_artifacts(cfg, '$OutputDir')
print(f'[OK] Generated spec: {res[\"spec_file\"]}')
print(f'[OK] Generated InnoSetup: {res[\"inno_setup_file\"]}')
"@

if ($RunBuild) {
    Write-Host "[*] Executing PyInstaller build..." -ForegroundColor Yellow
    python -m PyInstaller "$OutputDir/neron.spec" --noconfirm --distpath "$OutputDir/dist"
    Write-Host "[OK] PyInstaller build complete." -ForegroundColor Green
}

Write-Host "[SUCCESS] Windows packaging artifacts ready in $OutputDir" -ForegroundColor Green
