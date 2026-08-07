# Run Craxle on your own machine, against a LOCAL database.
#
# Why this file exists: `python -m uvicorn main:app` reads .env, and .env
# points DATABASE_URL at the live Railway Postgres. So the obvious way to
# "just run it locally" puts every click you make onto the school's real
# data — real classes, real children, real fees.
#
# This runs the same app against vidyapath.db, a SQLite file in this folder.
# Nothing you do here can reach production.
#
#     .\run-local.ps1              start it on http://127.0.0.1:8012
#     .\run-local.ps1 -Port 9000   somewhere else
#     .\run-local.ps1 -Fresh       start from an empty database
#
# Ctrl+C stops it.

param(
    [int]$Port = 8012,
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No virtualenv found at .venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "Create one with:  python -m venv .venv"
    exit 1
}

if ($Fresh -and (Test-Path ".\vidyapath.db")) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Move-Item ".\vidyapath.db" ".\vidyapath.$stamp.db"
    Write-Host "Old database kept as vidyapath.$stamp.db" -ForegroundColor DarkGray
}

# Is the port free, and if not, say WHY.
#
# uvicorn reports a taken port as "[WinError 10013] An attempt was made to
# access a socket in a way forbidden by its access permissions", which reads
# like a firewall or an admin-rights problem and is usually neither — it is
# another copy of this already running, or a preview server, on the same
# port. Naming the process that holds it turns a five-minute hunt into one
# line, and moving to the next free port means the common case does not stop
# at all.
function Test-PortFree([int]$p) {
    -not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Test-PortFree $Port)) {
    $held = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    $who = "another program"
    if ($held) {
        $proc = Get-Process -Id $held.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) { $who = "$($proc.ProcessName) (pid $($proc.Id))" }
    }
    Write-Host "Port $Port is already in use by $who." -ForegroundColor Yellow

    $next = $Port
    while ($next -lt ($Port + 20) -and -not (Test-PortFree $next)) { $next++ }
    if ($next -ge ($Port + 20)) {
        Write-Host "No free port between $Port and $($Port + 19). Stop the " `
                   "other program, or pass -Port." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using $next instead." -ForegroundColor Yellow
    $Port = $next
}

# The local database, and nothing from .env.
#
# DOTENV_PATH points at a file that does not exist, which is how db.py is told
# to ignore .env entirely. Without it the DATABASE_URL below would be read and
# then overwritten by the one in .env, which is the whole problem this script
# exists to avoid.
$env:DATABASE_URL = "sqlite:///./vidyapath.db"
$env:ALLOW_SQLITE = "1"
$env:DOTENV_PATH  = "nonexistent.env"
$env:JOBS_ENABLED = "0"
$env:COOKIE_SECURE = "0"
if (-not $env:JWT_SECRET) { $env:JWT_SECRET = "d" * 40 }

Write-Host ""
Write-Host "  Craxle - LOCAL" -ForegroundColor Green
Write-Host "  database  vidyapath.db (this folder, not Railway)" -ForegroundColor DarkGray
Write-Host "  site      http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "  board     http://127.0.0.1:$Port/craxlearn" -ForegroundColor Cyan
Write-Host "  admin     http://127.0.0.1:$Port/admin" -ForegroundColor Cyan
Write-Host ""

& $py -m uvicorn main:app --host 127.0.0.1 --port $Port --reload
