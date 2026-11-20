# HeimDall - Zero-Git Remote One-Liner Installer (Windows)
$ErrorActionPreference = "Stop"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "🛡️   Downloading & Launching HeimDall Observability Platform" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

$destDir = Join-Path $HOME "HeimDall"

if (-not (Test-Path $destDir)) {
    Write-Host "==> Downloading HeimDall from GitHub..." -ForegroundColor Yellow
    $zipPath = Join-Path $env:TEMP "heimdall-main.zip"
    Invoke-WebRequest -Uri "https://github.com/shouryasingh2311/HeimDall/archive/refs/heads/main.zip" -OutFile $zipPath
    Write-Host "==> Extracting files to $destDir..." -ForegroundColor Yellow
    Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
    Move-Item -Path (Join-Path $env:TEMP "HeimDall-main") -Destination $destDir -Force
    Remove-Item -Path $zipPath -Force
}

Set-Location $destDir

# If Docker is available, launch via Docker Compose; otherwise use native launcher
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "==> Docker detected! Starting via Docker Compose..." -ForegroundColor Green
    docker compose up
} else {
    Write-Host "==> Starting via Native Launcher..." -ForegroundColor Green
    & .\start.ps1
}
