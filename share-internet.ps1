# =====================================================================
#  VidyaPath - share over the internet
#
#  Creates a temporary public web address for your local server, so
#  anyone anywhere can open it. No account needed, nothing installed
#  system-wide.
#
#  Run start-local.ps1 or share-local.ps1 FIRST, in another window.
#  Then right-click this file > "Run with PowerShell"
# =====================================================================

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "VidyaPath - public sharing" -ForegroundColor Cyan
Write-Host ""

# ---- Which port is the server on? ------------------------------------
$port = 0
foreach ($p in @(8010, 8020, 8030, 8090, 5055, 8000)) {
    try {
        $test = [System.Net.Sockets.TcpClient]::new()
        $test.Connect("127.0.0.1", $p)
        $test.Close()
        $port = $p
        break
    } catch { }
}

if ($port -eq 0) {
    Write-Host "ERROR: no VidyaPath server is running." -ForegroundColor Red
    Write-Host ""
    Write-Host "Start it first, in a separate PowerShell window:" -ForegroundColor Yellow
    Write-Host "  & $PSScriptRoot\start-local.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Leave that window open, then run this script again." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Found your server running on port $port" -ForegroundColor Green
Write-Host ""

# ---- Find cloudflared, or fetch it -----------------------------------
$exe = Join-Path $PSScriptRoot "cloudflared.exe"

if (-not (Test-Path $exe)) {
    # Maybe it is already somewhere obvious
    $candidates = @(
        (Join-Path $env:USERPROFILE "Downloads\cloudflared.exe"),
        (Join-Path $env:USERPROFILE "Downloads\cloudflared-windows-amd64.exe"),
        (Join-Path $env:USERPROFILE "Desktop\cloudflared.exe")
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($found) {
        Write-Host "Found cloudflared in $found" -ForegroundColor Green
        Copy-Item $found $exe
    }
    else {
        Write-Host "cloudflared is not here yet." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "It is a small free tool from Cloudflare that gives your" -ForegroundColor DarkGray
        Write-Host "computer a temporary public web address. It is a single" -ForegroundColor DarkGray
        Write-Host "file, it installs nothing, and deleting it removes it." -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "Download from the official Cloudflare release page:" -ForegroundColor DarkGray
        Write-Host "https://github.com/cloudflare/cloudflared/releases/latest" -ForegroundColor White
        Write-Host ""
        $answer = Read-Host "Download it automatically now? (y/n)"

        if ($answer -ne "y") {
            Write-Host ""
            Write-Host "No problem. Download it yourself, put cloudflared.exe" -ForegroundColor Yellow
            Write-Host "in this folder, then run this script again." -ForegroundColor Yellow
            Read-Host "Press Enter to close"
            exit 0
        }

        $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        Write-Host ""
        Write-Host "Downloading (about 20 MB, may take a minute)..." -ForegroundColor Cyan
        try {
            $ProgressPreference = "SilentlyContinue"
            Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
            Write-Host "Downloaded." -ForegroundColor Green
        } catch {
            Write-Host ""
            Write-Host "ERROR: download failed." -ForegroundColor Red
            Write-Host $_.Exception.Message -ForegroundColor DarkGray
            Write-Host ""
            Write-Host "Download it manually instead, from:" -ForegroundColor Yellow
            Write-Host "https://github.com/cloudflare/cloudflared/releases/latest" -ForegroundColor White
            Write-Host "Save cloudflared.exe into this folder and run this again." -ForegroundColor Yellow
            Read-Host "Press Enter to close"
            exit 1
        }
    }
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "  Starting the tunnel" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Watch for a line containing:  trycloudflare.com" -ForegroundColor Yellow
Write-Host "  THAT is the address to send your friend." -ForegroundColor Yellow
Write-Host ""
Write-Host "  It usually appears inside a box a few lines down." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Keep this window AND the server window open." -ForegroundColor DarkGray
Write-Host "  Closing either one ends the tunnel." -ForegroundColor DarkGray
Write-Host ""
Write-Host "---------------------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

& $exe tunnel --url "http://localhost:$port"

Write-Host ""
Read-Host "Tunnel closed. Press Enter to exit"
