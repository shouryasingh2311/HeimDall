# HeimDall - 1-Command Windows Native Launcher (No Docker required)
$ErrorActionPreference = "Stop"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "🛡️   Starting HeimDall Observability Platform (Native Windows)" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# 1. Ensure Python 3.11+ is available
try {
    $pythonCmd = (Get-Command python -ErrorAction Stop).Source
} catch {
    Write-Error "Python is not installed or not in PATH. Please install Python 3.11+."
    exit 1
}

# 2. Setup Virtual Environment automatically if missing
if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
}

$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
$venvPip = Join-Path (Get-Location) ".venv\Scripts\pip.exe"

# 3. Install backend dependencies if not already installed
if (-not (Test-Path ".venv\Lib\site-packages\fastapi")) {
    Write-Host "==> Installing backend dependencies..." -ForegroundColor Yellow
    & $venvPip install -e . --quiet
}

# 4. Build Frontend UI if not already compiled
if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "==> Building frontend UI distribution..." -ForegroundColor Yellow
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location frontend
        npm install --silent
        npm run build --silent
        Pop-Location
    } else {
        Write-Warning "npm not found in PATH; skipping frontend build. Using pre-existing dist if available."
    }
}

# 5. Bootstrap certificates and demo credentials if needed
$runtimeDir = ".heimdal\demo"
if (-not (Test-Path "$runtimeDir\saas.json")) {
    Write-Host "==> Bootstrapping TLS certificates and demo tokens in $runtimeDir..." -ForegroundColor Yellow
    & $venvPython -m scripts.security.bootstrap --runtime $runtimeDir
}

# Extract credentials
$operatorJson = Get-Content "$runtimeDir\operator-alpha.json" -Raw | ConvertFrom-Json
$collectorJson = Get-Content "$runtimeDir\collector-alpha.json" -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "🛡️   HEIMDALL IS READY" -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "  Operations Dashboard:  https://localhost:8443" -ForegroundColor White
Write-Host "  Scenario Verifier:     http://localhost:9001/scenarios" -ForegroundColor White
Write-Host "  Proof / Local Audit:   http://localhost:9001/audit" -ForegroundColor White
Write-Host ""
Write-Host "  Tenant ID:             $($operatorJson.tenant_id)" -ForegroundColor Yellow
Write-Host "  Operator Token:        $($operatorJson.token)" -ForegroundColor Yellow
Write-Host "  Collector Local Token: $($collectorJson.local_token)" -ForegroundColor Yellow
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Gray
Write-Host ""

# 6. Launch processes in parallel jobs
$saasJob = Start-Job -ScriptBlock {
    param($py, $dir)
    & $py -m backend.saas.main --runtime $dir --dashboard frontend/dist
} -ArgumentList $venvPython, $runtimeDir

$collectorJob = Start-Job -ScriptBlock {
    param($py, $dir)
    & $py -m backend.collector.daemon --runtime $dir --scenarios
} -ArgumentList $venvPython, $runtimeDir

try {
    while ($true) {
        Receive-Job $saasJob
        Receive-Job $collectorJob
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`nStopping HeimDall services..." -ForegroundColor Yellow
    Stop-Job $saasJob -ErrorAction SilentlyContinue
    Stop-Job $collectorJob -ErrorAction SilentlyContinue
    Remove-Job $saasJob -ErrorAction SilentlyContinue
    Remove-Job $collectorJob -ErrorAction SilentlyContinue
}
