# =============================================================================
#  BeamMP EasyServer - start the server (used by the "Start BeamMP Server"
#  desktop shortcut and by autostart).
#   1. virus-checks the mods (bad ones go to Resources\Quarantine)
#   2. decrypts your AuthKey (it is never stored in ServerConfig.toml)
#   3. starts the server with a temporary config in your private folder and
#      wipes the key from it again as soon as the server has read it
# =============================================================================
# -Auto:   started by the dashboard, close the window when the server stops
# -Server: which server to start: "main" (default) or the id of an extra server
#          made in the dashboard (it lives in servers\<id>)
param([switch]$Auto, [string]$Server = 'main')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'easyserver-common.ps1')
$Base = Split-Path $PSScriptRoot -Parent
if ($Server -notmatch '^[a-z0-9]{1,12}$') { Write-Host "Unknown server '$Server'" -ForegroundColor Red; Start-Sleep 4; exit 1 }
if ($Server -eq 'main') {
    $Dir = $Base; $KeyName = 'BEAMMP_AUTH_KEY'; $RunName = 'ServerConfig.run.toml'
} else {
    $Dir = Join-Path $Base "servers\$Server"; $KeyName = 'BEAMMP_AUTH_KEY_' + $Server.ToUpper(); $RunName = "ServerConfig.run.$Server.toml"
}
$Exe = Join-Path $Base 'BeamMP-Server.exe'
$Cfg = Join-Path $Dir 'ServerConfig.toml'
$Host.UI.RawUI.WindowTitle = "BeamMP Server ($Server)"

if (-not (Test-Path $Exe)) { Write-Host "BeamMP-Server.exe not found in $Base" -ForegroundColor Red; Read-Host 'Press Enter'; exit 1 }
if (-not (Test-Path $Cfg)) { Write-Host "No server in $Dir" -ForegroundColor Red; Start-Sleep 4; exit 1 }
# already running? (each server runs with its own temporary config file, see below)
$running = Get-CimInstance Win32_Process -Filter "Name='BeamMP-Server.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($RunName) }
if ($running) {
    Write-Host 'This BeamMP server is already running.' -ForegroundColor Yellow; Start-Sleep 4; exit
}

Write-Host 'Checking mods for viruses...' -ForegroundColor Cyan
try {
    $n = Invoke-EsSweep $Dir $Base
    if ($n -gt 0) { Write-Host "  $n mod(s) were blocked and moved to quarantine." -ForegroundColor Red }
    else { Write-Host '  All mods OK.' -ForegroundColor Green }
} catch { Write-Host "  Mod check failed: $($_.Exception.Message)" -ForegroundColor Yellow }

# Temporary config with the key, in your private AppData folder
$runDir = Join-Path $env:LOCALAPPDATA 'BeamMP-EasyServer'
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$runCfg = Join-Path $runDir $RunName
$txt = [IO.File]::ReadAllText($Cfg)
$key = Get-EsSecret $Base $KeyName
if ($null -eq $key) {
    Write-Host 'Could not unlock your saved AuthKey (it was saved by a different Windows account).' -ForegroundColor Yellow
    Write-Host 'Run Install-BeamMP-Server.bat again from this account and re-enter the key.' -ForegroundColor Yellow
    $key = ''
}
$hasKey = $key -match '^[A-Za-z0-9-]+$'
if ($hasKey) { $txt = [regex]::Replace($txt, '(?m)^(\s*AuthKey\s*=).*$', ('$1 "' + $key + '"')) }
[IO.File]::WriteAllText($runCfg, $txt, (New-Object Text.UTF8Encoding $false))
$key = $null
$before = (Get-Item $runCfg).LastWriteTimeUtc

Write-Host 'Starting the BeamMP server... (close this window or press Ctrl+C to stop it)' -ForegroundColor Cyan
$p = Start-Process -FilePath $Exe -ArgumentList ('--config="' + $runCfg + '"') -WorkingDirectory $Dir -NoNewWindow -PassThru

# The server reads (and rewrites) its config once at startup. Wait for that,
# then remove the key from the file - the server keeps it in memory only.
if ($hasKey) {
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline -and -not $p.HasExited) {
        Start-Sleep -Milliseconds 500
        if ((Get-Item $runCfg).LastWriteTimeUtc -ne $before) { Start-Sleep -Seconds 1; break }
    }
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $t = [IO.File]::ReadAllText($runCfg)
            $t = [regex]::Replace($t, '(?m)^(\s*AuthKey\s*=).*$', '$1 "" # wiped by BeamMP EasyServer - key is kept encrypted')
            [IO.File]::WriteAllText($runCfg, $t, (New-Object Text.UTF8Encoding $false))
            break
        } catch { Start-Sleep -Milliseconds 500 }
    }
}
$p.WaitForExit()
Write-Host ''
Write-Host "The server stopped (exit code $($p.ExitCode))." -ForegroundColor Yellow
if (-not $Auto) { Read-Host 'Press Enter to close' } else { Start-Sleep -Seconds 3 }
