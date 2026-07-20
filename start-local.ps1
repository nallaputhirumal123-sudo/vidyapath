# =====================================================================
#  VidyaPath - local test server
#  Right-click this file > "Run with PowerShell"
# =====================================================================

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot
Write-Host ""
Write-Host "VidyaPath local setup" -ForegroundColor Cyan
Write-Host "Working folder: $PSScriptRoot" -ForegroundColor DarkGray
Write-Host ""

# ---- Are the app files actually here? --------------------------------
if (-not (Test-Path "main.py")) {
    Write-Host "ERROR: main.py is not in this folder." -ForegroundColor Red
    Write-Host "Put start-local.ps1 in the same folder as main.py and index.html." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

# ---- Refuse to run inside a Windows system folder --------------------
if ($PSScriptRoot -like "*\Windows\*") {
    Write-Host "ERROR: This folder is inside C:\Windows." -ForegroundColor Red
    Write-Host "Move the project to C:\Users\$env:USERNAME\vidyapath and retry." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

# ---- Find a usable Python -------------------------------------------
Write-Host "Checking Python..." -ForegroundColor Cyan

$pyExe  = $null
$pyArgs = @()
$pyVer  = ""

foreach ($try in @(
        @{ exe = "py";     args = @("-3.12") },
        @{ exe = "py";     args = @("-3.11") },
        @{ exe = "py";     args = @("-3.13") },
        @{ exe = "python"; args = @() }
    )) {
    try {
        $out = & $try.exe @($try.args + @("--version")) 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $pyExe  = $try.exe
            $pyArgs = $try.args
            $pyVer  = "$out"
            break
        }
    } catch { }
}

if (-not $pyExe) {
    Write-Host "ERROR: No Python found." -ForegroundColor Red
    Write-Host "Install it from python.org/downloads and tick 'Add Python to PATH'." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "  Using: $pyExe $pyArgs  ($pyVer)" -ForegroundColor Green

if ($pyVer -match "3\.1[456]") {
    Write-Host ""
    Write-Host "  NOTE: This Python is very new. Some packages may not install." -ForegroundColor Yellow
    Write-Host "  If the next step fails, install Python 3.12 from python.org," -ForegroundColor Yellow
    Write-Host "  delete the .venv folder, and run this script again." -ForegroundColor Yellow
}
Write-Host ""

# ---- Virtual environment --------------------------------------------
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $pyExe @($pyArgs + @("-m", "venv", ".venv"))
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not create the virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to close"
        exit 1
    }
}
else {
    Write-Host "Virtual environment already exists, reusing it." -ForegroundColor DarkGray
}

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "ERROR: Virtual environment looks broken." -ForegroundColor Red
    Write-Host "Delete the .venv folder and run this script again." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

# ---- Dependencies ----------------------------------------------------
Write-Host "Installing dependencies. First run takes a minute or two..." -ForegroundColor Cyan
Write-Host ""

& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements-local.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Dependency install failed." -ForegroundColor Red
    Write-Host "This is almost always a too-new Python version." -ForegroundColor Yellow
    Write-Host "Install Python 3.12 from python.org, delete the .venv folder," -ForegroundColor Yellow
    Write-Host "then run this script again." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}
Write-Host ""

# ---- Admin credentials ----------------------------------------------
Write-Host "Set up your local admin account" -ForegroundColor Cyan

$adminEmail = Read-Host "  Admin email"
if ([string]::IsNullOrWhiteSpace($adminEmail)) {
    $adminEmail = "admin@local.test"
    Write-Host "  Blank, so using admin@local.test" -ForegroundColor Yellow
}

$adminPass = Read-Host "  Admin password, 8 characters or more"
if ($adminPass.Length -lt 8) {
    $adminPass = "localtest123"
    Write-Host "  Too short, so using localtest123" -ForegroundColor Yellow
}

$env:ADMIN_EMAIL    = $adminEmail
$env:ADMIN_PASSWORD = $adminPass
$env:COOKIE_SECURE  = "0"
$env:JWT_SECRET     = "local-development-secret-not-for-production"

# ---- Find a free port -------------------------------------------------
# Port 8000 is avoided: Splunk, and several other tools, claim it by default.
function Test-PortFree($port) {
    try {
        $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        $l.Start(); $l.Stop()
        return $true
    } catch { return $false }
}

$port = 0
foreach ($p in @(8010, 8020, 8030, 8090, 5055)) {
    if (Test-PortFree $p) { $port = $p; break }
}
if ($port -eq 0) {
    Write-Host "ERROR: Could not find a free port to use." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

$url = "http://localhost:$port"

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Starting server on port $port" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Student site:  $url"        -ForegroundColor White
Write-Host "  Admin panel:   $url/admin"  -ForegroundColor White
Write-Host ""
Write-Host "  Admin login:   $adminEmail" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press Ctrl+C to stop the server." -ForegroundColor DarkGray
Write-Host ""

Start-Sleep -Seconds 3
Start-Process $url

& $venvPy -m uvicorn main:app --reload --port $port

Write-Host ""
Read-Host "Server stopped. Press Enter to close"
