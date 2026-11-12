# =============================================================================
#  BeamMP EasyServer - wake helper installer (Windows)
#
#  Installs a tiny background program that wakes your BeamMP server computer
#  up (Wake-on-LAN) when you press "Wake up" in the phone app or use /start in
#  Discord while it sleeps. Run it on a PC at home that stays on.
#  It runs in the background as a Windows task, even when nobody is logged in.
#
#    Install-Wake-Helper.bat                     (double-click)
#    install-wake-helper.ps1 -Uninstall          remove it
# =============================================================================
param([switch]$Uninstall, [string]$Code = '')

$Dir       = Join-Path $env:ProgramData 'BeamMP-Wake'
$TaskName  = 'BeamMP Wake Helper (EasyServer)'
$RepoRaw   = 'https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main'
$PythonUrl = 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($Uninstall) { $argList += '-Uninstall' }
    if ($Code) { $argList += @('-Code', $Code) }
    try { Start-Process powershell.exe -ArgumentList $argList -Verb RunAs }
    catch { Write-Host 'Administrator permission is needed (click "Yes" on the Windows prompt).' -ForegroundColor Red; Read-Host 'Press Enter to close' }
    exit
}
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$Host.UI.RawUI.WindowTitle = 'BeamMP wake helper'
function Ok($t)   { Write-Host "  [OK] $t" -ForegroundColor Green }
function Fail($t) { Write-Host "  [ERROR] $t" -ForegroundColor Red; Read-Host 'Press Enter to close'; exit 1 }
function Stop-Helper {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*easyserver_wake.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($Uninstall) {
    Stop-Helper
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $Dir -ErrorAction SilentlyContinue
    Ok 'Wake helper removed'; Read-Host 'Press Enter to close'; exit
}

Write-Host '==> BeamMP wake helper' -ForegroundColor Cyan
Stop-Helper
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
# only administrators and Windows itself may read the settings (they can hold the Discord bot token)
& icacls.exe $Dir /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null

$py = Join-Path $Dir 'python\python.exe'
if (-not (Test-Path $py)) {
    Write-Host '  Downloading portable Python (about 10 MB)...'
    $zip = Join-Path $env:TEMP 'beammp-wake-python.zip'
    try { Invoke-WebRequest -Uri $PythonUrl -OutFile $zip -UseBasicParsing } catch { Fail "Download failed: $($_.Exception.Message)" }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $Dir 'python') -Force
    Remove-Item $zip -ErrorAction SilentlyContinue
    if (-not (Test-Path $py)) { Fail 'Portable Python could not be unpacked' }
}
Ok 'Portable Python ready'

$prog = Join-Path $Dir 'easyserver_wake.py'
$local = Join-Path $PSScriptRoot 'easyserver_wake.py'
if (Test-Path $local) { Copy-Item -Force $local $prog }
else {
    try { Invoke-WebRequest -Uri "$RepoRaw/wake/easyserver_wake.py" -OutFile "$prog.tmp" -UseBasicParsing } catch { Fail "Download failed: $($_.Exception.Message)" }
    if (-not ((Get-Content "$prog.tmp" -TotalCount 3) -join ' ').Contains('BeamMP EasyServer - wake helper')) { Fail "The download doesn't look right" }
    Move-Item -Force "$prog.tmp" $prog
}
Ok 'Program installed'

Write-Host ''
$cfg = Join-Path $Dir 'config.json'
$setupArgs = @($prog, 'setup', '--config', $cfg)
if ($Code) { $setupArgs += @('--code', $Code) }
& $py @setupArgs
if (-not (Test-Path $cfg)) { Fail "Setup didn't finish" }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
$action  = New-ScheduledTaskAction -Execute $py -Argument "`"$prog`" run --config `"$cfg`" --log `"$(Join-Path $Dir 'helper.log')`"" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -AtStartup
$set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
$prin    = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $set -Principal $prin | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 4
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*easyserver_wake.py*' }
if (-not $running) { Fail "The helper didn't start - see $(Join-Path $Dir 'helper.log')" }
Ok 'Wake helper is running and starts by itself with Windows'
Write-Host ''
Write-Host "  Now press 'Test the helper' in the dashboard (Settings -> Sleep & wake-up)."
Write-Host "  Log: $(Join-Path $Dir 'helper.log')"
Write-Host '  This PC must stay on (set Windows to never sleep on this PC), ideally with a network cable.'
Write-Host '  Remove: run install-wake-helper.ps1 -Uninstall'
Read-Host 'Press Enter to close'
