# =====================================================================
#  VidyaPath - share on your local network
#  Anyone on the SAME WIFI can then open the site on their phone or laptop.
#  Right-click this file > "Run with PowerShell"
# =====================================================================

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "VidyaPath - local network sharing" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "main.py")) {
    Write-Host "ERROR: main.py is not in this folder." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "ERROR: no virtual environment found." -ForegroundColor Red
    Write-Host "Run start-local.ps1 first to set everything up." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

# ---- Find this machine's address on the local network ----------------
$ip = $null
try {
    $ip = (Get-NetIPAddress -AddressFamily IPv4 |
           Where-Object {
               $_.IPAddress -notlike "127.*" -and
               $_.IPAddress -notlike "169.254.*" -and
               $_.PrefixOrigin -ne "WellKnown"
           } |
           Sort-Object -Property InterfaceMetric |
           Select-Object -First 1).IPAddress
} catch { }

if (-not $ip) {
    Write-Host "Could not detect your network address automatically." -ForegroundColor Yellow
    Write-Host "Run 'ipconfig' and look for the IPv4 Address." -ForegroundColor Yellow
    $ip = Read-Host "Enter it here"
}

# ---- Pick a free port ------------------------------------------------
function Test-PortFree($port) {
    try {
        $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $port)
        $l.Start(); $l.Stop(); return $true
    } catch { return $false }
}

$port = 0
foreach ($p in @(8010, 8020, 8030, 8090, 5055)) {
    if (Test-PortFree $p) { $port = $p; break }
}
if ($port -eq 0) {
    Write-Host "ERROR: no free port available." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# ---- Admin credentials ----------------------------------------------
Write-Host "Admin account for this session" -ForegroundColor Cyan
$adminEmail = Read-Host "  Admin email"
if ([string]::IsNullOrWhiteSpace($adminEmail)) { $adminEmail = "admin@local.test" }
$adminPass = Read-Host "  Admin password, 8 characters or more"
if ($adminPass.Length -lt 8) {
    $adminPass = "localtest123"
    Write-Host "  Too short, using localtest123" -ForegroundColor Yellow
}

$env:ADMIN_EMAIL    = $adminEmail
$env:ADMIN_PASSWORD = $adminPass
$env:COOKIE_SECURE  = "0"
$env:JWT_SECRET     = "local-network-testing-secret"

$url = "http://" + $ip + ":" + $port

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "  SHARE THIS ADDRESS WITH YOUR TESTERS" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "     $url" -ForegroundColor White
Write-Host ""
Write-Host "  They must be on the SAME WIFI as this computer." -ForegroundColor DarkGray
Write-Host "  Works on phones, tablets and other laptops." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Admin panel:  $url/admin" -ForegroundColor DarkGray
Write-Host "  Admin login:  $adminEmail" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  NOTE: Windows may show a firewall prompt the first time." -ForegroundColor Yellow
Write-Host "        Tick 'Private networks' and click Allow." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Keep this window open. Ctrl+C stops the server." -ForegroundColor DarkGray
Write-Host ""

# --host 0.0.0.0 is what makes it reachable from other devices
& $venvPy -m uvicorn main:app --host 0.0.0.0 --port $port

Write-Host ""
Read-Host "Server stopped. Press Enter to close"
