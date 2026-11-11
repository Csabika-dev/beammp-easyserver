# =============================================================================
#  BeamMP EasyServer - add mods (Windows)
#  Drag mod .zip files onto the "Drop BeamMP Mods Here" desktop shortcut
#  (or onto Add-Mods.bat). Every mod is virus-checked before it is added.
#  Run it without files to open the mods folder.
# =============================================================================
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'easyserver-common.ps1')
$Dir = Get-EsInstallDir
if (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'BeamMP-Server.exe')) { $Dir = Split-Path $PSScriptRoot -Parent }
$Client = Join-Path $Dir 'Resources\Client'
$Config = Join-Path $Dir 'ServerConfig.toml'
$Exe    = Join-Path $Dir 'BeamMP-Server.exe'
$Host.UI.RawUI.WindowTitle = 'BeamMP EasyServer - Add mods'

if (-not (Test-Path $Exe)) {
    Write-Host "No BeamMP server found in $Dir - run Install-BeamMP-Server.bat first." -ForegroundColor Red
    Read-Host 'Press Enter to close'; exit
}
New-Item -ItemType Directory -Force -Path $Client | Out-Null

$files = @($args | Where-Object { $_ })
if ($files.Count -eq 0) {
    Write-Host 'Tip: drag mod .zip files onto the "Drop BeamMP Mods Here" shortcut.'
    Write-Host "Opening the mods folder: $Client"
    Write-Host 'Mods copied in by hand are virus-checked when the server starts.'
    Start-Process explorer.exe $Client
    Start-Sleep -Seconds 3; exit
}

function Get-ZipMaps($path) {
    $maps = @()
    try {
        $z = [IO.Compression.ZipFile]::OpenRead($path)
        foreach ($e in $z.Entries) { if ($e.FullName -match '^levels/([^/]+)/info\.json$') { $maps += $matches[1] } }
        $z.Dispose()
    } catch { }
    return ($maps | Sort-Object -Unique)
}

Write-Host 'Checking mods for viruses before adding them...' -ForegroundColor Cyan
$added = 0; $foundMaps = @()
foreach ($f in $files) {
    $name = Split-Path $f -Leaf
    if (Test-Path -LiteralPath $f -PathType Container) { Write-Host "  Skipped folder (zip it first): $name" -ForegroundColor Yellow; continue }
    if ($name -notmatch '\.zip$') { Write-Host "  Skipped (not a .zip): $name" -ForegroundColor Yellow; continue }
    $r = Invoke-EsModScan $f $Dir
    Write-EsResult $name $r
    if ($r.Verdict -eq 'blocked') { Write-Host "      NOT added." -ForegroundColor Red; continue }
    if ($r.Verdict -eq 'warning') {
        $a = Read-Host '      Add it anyway? Only if you trust where it came from (y/N)'
        if ($a -notmatch '^[Yy]') { Write-Host '      Not added.'; continue }
    }
    Copy-Item -LiteralPath $f -Destination (Join-Path $Client $name) -Force
    Write-Host "      Added." -ForegroundColor Green
    $added++
    $foundMaps += Get-ZipMaps $f
}

if ($added -eq 0) { Read-Host 'Nothing added. Press Enter to close'; exit }

foreach ($m in ($foundMaps | Sort-Object -Unique)) {
    $a = Read-Host "This mod contains the map '$m'. Use it as the server map now? (y/N)"
    if ($a -match '^[Yy]') {
        $txt = [IO.File]::ReadAllText($Config)
        $txt = [regex]::Replace($txt, '(?m)^\s*Map\s*=.*$', "Map = `"/levels/$m/info.json`"")
        [IO.File]::WriteAllText($Config, $txt, (New-Object Text.UTF8Encoding $false))
        Write-Host "  Map set to $m" -ForegroundColor Green
        break
    }
}

$running = Get-Process -Name 'BeamMP-Server' -ErrorAction SilentlyContinue
if ($running) {
    $a = Read-Host 'The server is running. Restart it now to load the mods? (Y/n) - players will be disconnected'
    if ($a -notmatch '^[Nn]') {
        try {
            $running | Stop-Process -Force
            Start-Sleep -Seconds 2
            $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Start BeamMP Server.lnk'
            if (Test-Path $lnk) { Start-Process explorer.exe -ArgumentList "`"$lnk`"" }
            else { Start-Process powershell.exe -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $PSScriptRoot 'start-server.ps1')`"" }
            Write-Host '  Server restarted.' -ForegroundColor Green
        } catch {
            Write-Host '  Could not restart it from here. Close the server window and start it again' -ForegroundColor Yellow
            Write-Host '  with the "Start BeamMP Server" shortcut.' -ForegroundColor Yellow
        }
    }
} else {
    Write-Host 'Mods will load the next time you start the server.'
}
Read-Host 'Done. Press Enter to close'
