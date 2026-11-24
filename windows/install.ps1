# =============================================================================
#  BeamMP EasyServer - Windows installer
#  Double-click "Install-BeamMP-Server.bat" instead of running this directly.
#
#  install.ps1             -> setup window
#  install.ps1 -Update     -> download newest server version
#  install.ps1 -Uninstall  -> remove firewall rules, shortcuts, autostart
#  install.ps1 -Unattended [-ServerName "..."] [-Update]
#                          -> no windows or questions: used by another computer's
#                             dashboard (Servers -> Other computers) over SSH
#
#  Not affiliated with the BeamMP team. BeamMP: https://beammp.com
# =============================================================================
param(
    [switch]$Update,
    [switch]$Uninstall,
    [switch]$ResetLogin,
    [switch]$Unattended,
    [string]$ServerName = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'   # makes downloads much faster
$EasyVersion  = '1.15.0'
$DefaultDir   = 'C:\BeamMP-Server'
$StateFile    = Join-Path $env:ProgramData 'BeamMP-EasyServer\install-dir.txt'
$ServerUrl    = 'https://github.com/BeamMP/BeamMP-Server/releases/latest/download/BeamMP-Server.exe'
$VcRedistUrl  = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
$KeymasterUrl = 'https://keymaster.beammp.com'
$TaskName     = 'BeamMP Server (EasyServer)'
$FwPrefix     = 'BeamMP Server (EasyServer)'
$DashTask     = 'BeamMP Dashboard (EasyServer)'
$DashPort     = 30815
$GuardTask    = 'BeamMP Guard (EasyServer)'
$PythonUrl    = 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'

# ---- run as administrator ----------------------------------------------------
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if ($Unattended) { Write-Host '  [ERROR] This needs a Windows administrator account.'; exit 1 }
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($Update)    { $argList += '-Update' }
    if ($Uninstall) { $argList += '-Uninstall' }
    if ($ResetLogin) { $argList += '-ResetLogin' }
    try {
        Start-Process powershell.exe -ArgumentList $argList -Verb RunAs
    } catch {
        Write-Host 'Administrator permission is needed (click "Yes" on the Windows prompt).' -ForegroundColor Red
        Read-Host 'Press Enter to close'
    }
    exit
}

[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
. (Join-Path $PSScriptRoot 'easyserver-common.ps1')
try { $Host.UI.RawUI.WindowTitle = "BeamMP EasyServer v$EasyVersion" } catch { }
$script:EsFailed = $false

function Step($t) { Write-Host ''; Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  [OK] $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Finish {
    if ($Unattended) { if ($script:EsFailed) { exit 1 } else { exit 0 } }
    Write-Host ''; Read-Host 'Press Enter to close'; exit
}

function Get-InstallDir {
    if (Test-Path $StateFile) {
        $d = (Get-Content $StateFile -Raw).Trim()
        if ($d -and (Test-Path $d)) { return $d }
    }
    return $DefaultDir
}

function Download-Server($dir) {
    Step 'Downloading the latest BeamMP server'
    $tmp = Join-Path $env:TEMP 'BeamMP-Server.exe.download'
    Invoke-WebRequest -Uri $ServerUrl -OutFile $tmp -UseBasicParsing
    Get-Process -Name 'BeamMP-Server' -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Milliseconds 500
    Move-Item -Force $tmp (Join-Path $dir 'BeamMP-Server.exe')
    Ok 'Server downloaded'
}

# Folders created in C:\ can be changed by EVERY user of the PC by default.
# The server folder holds programs that run as you (and the installer runs
# as administrator), so only you, administrators and SYSTEM may change it.
function Protect-EsFolder([string]$dir, [switch]$AdminOnly) {
    try {
        $full = [IO.Path]::GetFullPath($dir).TrimEnd('\')
        $bad = @($env:SystemRoot, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:USERPROFILE, $env:ProgramData, $env:PUBLIC) |
            Where-Object { $_ } | ForEach-Object { $_.TrimEnd('\') }
        if ($full -match '^[A-Za-z]:$' -or $bad -contains $full) { Warn "Not changing permissions of $full"; return }
        $me = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $grants = @('*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F', '*S-1-5-32-545:(OI)(CI)RX')
        if (-not $AdminOnly) { $grants += "*${me}:(OI)(CI)M" }
        & icacls.exe $full /inheritance:r /grant:r @grants /Q | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "icacls exit code $LASTEXITCODE" }
        # everything inside follows the folder again (removes old "Everyone can change" rights)
        if (Get-ChildItem -LiteralPath $full -Force -ErrorAction SilentlyContinue | Select-Object -First 1) {
            & icacls.exe (Join-Path $full '*') /reset /T /C /Q | Out-Null
        }
    } catch { Warn "Could not lock down the permissions of ${dir}: $($_.Exception.Message)" }
}

function Copy-EsScripts($dir) {
    $esDir = Join-Path $dir 'EasyServer'
    New-Item -ItemType Directory -Force -Path $esDir | Out-Null
    foreach ($f in 'easyserver-common.ps1', 'start-server.ps1', 'add-mods.ps1') {
        Copy-Item -Force (Join-Path $PSScriptRoot $f) (Join-Path $esDir $f)
    }
    return $esDir
}

# ---- web dashboard (portable Python, runs as you at logon) ----------------------
function Find-DashboardSource {
    foreach ($c in (Join-Path $PSScriptRoot 'dashboard'), (Join-Path (Split-Path $PSScriptRoot -Parent) 'dashboard')) {
        if (Test-Path (Join-Path $c 'dashboard.py')) { return $c }
    }
    throw 'The dashboard files are missing - download the full ZIP again.'
}

function Stop-Dashboard {
    Stop-ScheduledTask -TaskName $DashTask -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*EasyServer\dashboard\dashboard.py*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# BeamMP-only guard: the dashboard (running as you) decides who to block, this
# task (running as SYSTEM, once a minute) puts that list into Windows Firewall.
# Its script lives in a folder only administrators can change.
function Install-Guard($esDir) {
    try {
        $gDir = Split-Path $StateFile
        New-Item -ItemType Directory -Force -Path $gDir | Out-Null
        Copy-Item -Force (Join-Path $PSScriptRoot 'guard.ps1') (Join-Path $gDir 'guard.ps1')
        Protect-EsFolder $gDir -AdminOnly
        Unregister-ScheduledTask -TaskName $GuardTask -Confirm:$false -ErrorAction SilentlyContinue
        $arg = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $gDir 'guard.ps1')`" -DataDir `"$(Join-Path $esDir 'data')`""
        $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
        $t1 = New-ScheduledTaskTrigger -AtStartup
        $t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
        $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
        $who = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $GuardTask -Action $action -Trigger $t1, $t2 -Settings $set -Principal $who | Out-Null
        Ok 'BeamMP-only guard ready (switch it on in the dashboard: Settings)'
    } catch { Warn "The BeamMP-only guard couldn't be set up: $($_.Exception.Message)" }
}

# Wait until the dashboard really answers. If it doesn't, say so and show why
# (the dashboard writes its errors to EasyServer\data\dashboard.log).
function Test-Dashboard([string]$esDir) {
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        # Any program accepting connections on the port counts. (An HTTP check fails
        # when HTTPS is on: Windows PowerShell does not trust the self-signed certificate.)
        $c = New-Object System.Net.Sockets.TcpClient
        try {
            if ($c.ConnectAsync('127.0.0.1', $DashPort).Wait(2000) -and $c.Connected) {
                Ok "Dashboard is running on port $DashPort"; return $true
            }
        } catch { } finally { $c.Dispose() }
    }
    Warn "The dashboard did not start (nothing answers on port $DashPort)."
    $log = Join-Path $esDir 'data\dashboard.log'
    if (Test-Path $log) {
        Warn "Last lines of ${log}:"
        Get-Content $log -Tail 12 | ForEach-Object { Write-Host "       $_" -ForegroundColor Yellow }
    } else {
        $task = Get-ScheduledTaskInfo -TaskName $DashTask -ErrorAction SilentlyContinue
        if ($task) { Warn ("The start task's last result: 0x{0:X} at {1}" -f $task.LastTaskResult, $task.LastRunTime) }
    }
    Warn 'Please send this window to the BeamMP EasyServer issue page on GitHub.'
    return $false
}

# Downloaded programs must carry a valid digital signature from the expected company before they run.
# Stops a tampered download (or a file swapped in the temp folder) from running with admin rights.
function Assert-Signed([string]$Path, [string]$Company) {
    $sig = Get-AuthenticodeSignature -LiteralPath $Path
    $subject = if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { '' }
    if ($sig.Status -ne 'Valid' -or $subject -notmatch [regex]::Escape("O=$Company")) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        throw "$(Split-Path $Path -Leaf) is not correctly signed by $Company (status: $($sig.Status)). The download was deleted - check your internet connection and try again."
    }
}

# Change a few dashboard settings in data\dashboard.json (keeps everything else).
function Set-DashSettings([string]$esDir, [hashtable]$values) {
    $j = Join-Path $esDir 'data\dashboard.json'
    New-Item -ItemType Directory -Force -Path (Split-Path $j) | Out-Null
    $d = [ordered]@{}
    if (Test-Path $j) {
        try { (Get-Content $j -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $d[$_.Name] = $_.Value } } catch { }
    }
    foreach ($k in $values.Keys) { $d[$k] = $values[$k] }
    [IO.File]::WriteAllText($j, ($d | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding $false))
}

# Ask how friends outside the home should get in, in plain words.
# Returns 'auto' (dashboard asks the router), 'manual' (user does it) or 'later'.
function Show-PortChoice([int]$port, [bool]$dashboard, [string]$current) {
    $f = New-Object System.Windows.Forms.Form
    $f.Text = 'Letting friends join from anywhere'
    $f.Size = New-Object System.Drawing.Size(600, 560)
    $f.StartPosition = 'CenterScreen'; $f.FormBorderStyle = 'FixedDialog'
    $f.MaximizeBox = $false; $f.MinimizeBox = $false
    $f.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $y = 15
    $add = {
        param($text, $x, $w, $bold, $grey)
        $l = New-Object System.Windows.Forms.Label
        $l.Text = $text; $l.Location = New-Object System.Drawing.Point($x, $script:py)
        $l.MaximumSize = New-Object System.Drawing.Size($w, 0); $l.AutoSize = $true
        if ($bold) { $l.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold) }
        if ($grey) { $l.ForeColor = [System.Drawing.Color]::DimGray }
        $f.Controls.Add($l); $script:py += $l.Height + 6
    }
    $script:py = $y
    & $add 'How should friends outside your home get in?' 20 540 $true $false
    & $add ("Friends on your Wi-Fi can join straight away. Friends somewhere else need your router to let them through to this computer on port $port " +
            "(this is called port forwarding). Pick one - you can change it later on the dashboard's Health page.") 20 540 $false $false
    $script:py += 6
    $radio = {
        param($text, $desc)
        $r = New-Object System.Windows.Forms.RadioButton
        $r.Text = $text; $r.AutoSize = $true
        $r.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
        $r.Location = New-Object System.Drawing.Point(20, $script:py)
        $f.Controls.Add($r); $script:py += 26
        & $add $desc 40 520 $false $true
        $script:py += 8
        return $r
    }
    $autoDesc = if ($dashboard) {
        "The dashboard asks your router to open port $port for this computer - no router settings page needed. Most home routers allow this (it's called UPnP).`n" +
        "- It only opens when you invite friends (Copy invite in the dashboard, or /join in your Discord) and closes by itself 30 minutes after the last player leaves.`n" +
        "- Only this one game port is touched. Nothing else on your router changes.`n" +
        "- If your router says no, the Health page tells you and shows how to do it by hand."
    } else { 'Needs the web dashboard - tick "Install the web dashboard" on the first screen to use this.' }
    $rAuto = & $radio 'Do it for me (recommended)' $autoDesc
    $rAuto.Enabled = $dashboard
    $rMan = & $radio "I'll do it myself" ("You open your router's settings page and add the forward yourself. When the install is finished, " +
                                          "this window shows exactly what to type in, and the help page opens.")
    $rLater = & $radio 'Not now' 'Only people on your Wi-Fi can join for now. Nothing is changed on your router.'
    if ($current -eq 'manual') { $rMan.Checked = $true } elseif ($current -eq 'later' -or -not $dashboard) { $rLater.Checked = $true } else { $rAuto.Checked = $true }
    $script:py += 6
    $ok = New-Object System.Windows.Forms.Button
    $ok.Text = 'Continue'; $ok.Width = 140; $ok.Height = 36
    $ok.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
    $ok.Location = New-Object System.Drawing.Point(420, $script:py)
    $ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $f.AcceptButton = $ok; $f.Controls.Add($ok)
    $f.ClientSize = New-Object System.Drawing.Size(580, ($script:py + 50))
    [void]$f.ShowDialog()
    if ($rAuto.Checked) { return 'auto' } elseif ($rMan.Checked) { return 'manual' } else { return 'later' }
}

function Install-Dashboard($dir, [hashtable]$preset = $null) {
    Step 'Installing the web dashboard'
    $esDir = Join-Path $dir 'EasyServer'
    $pyDir = Join-Path $esDir 'python'
    $pyw = Join-Path $pyDir 'pythonw.exe'
    if (-not (Test-Path $pyw)) {
        Write-Host '  Downloading portable Python (about 10 MB)...'
        $zip = Join-Path $env:TEMP ('easyserver-python-' + [guid]::NewGuid().ToString('N') + '.zip')
        Invoke-WebRequest -Uri $PythonUrl -OutFile $zip -UseBasicParsing
        New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
        Expand-Archive -Path $zip -DestinationPath $pyDir -Force
        Remove-Item $zip -ErrorAction SilentlyContinue
        if (-not (Test-Path $pyw)) { throw 'Portable Python could not be unpacked' }
        try {
            foreach ($exe in 'python.exe', 'pythonw.exe') { Assert-Signed (Join-Path $pyDir $exe) 'Python Software Foundation' }
        } catch {
            Remove-Item -LiteralPath $pyDir -Recurse -Force -ErrorAction SilentlyContinue
            throw
        }
    }
    Ok 'Portable Python ready'
    Stop-Dashboard
    if ($preset) { Set-DashSettings $esDir $preset }
    $src = Find-DashboardSource
    $dst = Join-Path $esDir 'dashboard'
    New-Item -ItemType Directory -Force -Path $dst, (Join-Path $esDir 'data') | Out-Null
    foreach ($f in 'dashboard.py', 'webui.html', 'modscan.py', 'tlsgen.py', 'upnp.py', 'guard.py') { Copy-Item -Force (Join-Path $src $f) (Join-Path $dst $f) }
    # dashboard translations (a missing one just means that language shows English)
    $langSrc = Join-Path $src 'lang'
    if (Test-Path $langSrc) {
        New-Item -ItemType Directory -Force -Path (Join-Path $dst 'lang') | Out-Null
        Copy-Item -Force (Join-Path $langSrc '*.json') (Join-Path $dst 'lang')
    }
    # the "New in" cards on the Overview after an update
    $news = Join-Path $src 'whatsnew.json'
    if (Test-Path $news) { Copy-Item -Force $news (Join-Path $dst 'whatsnew.json') }
    # player statistics plugin, runs inside the BeamMP server
    $plug = Join-Path $dir 'Resources\Server\EasyServerStats'
    New-Item -ItemType Directory -Force -Path $plug | Out-Null
    Copy-Item -Force (Join-Path $src 'EasyServerStats\main.lua') (Join-Path $plug 'main.lua')
    # extra servers made in the dashboard get the same plugin
    Get-ChildItem -Path (Join-Path $dir 'servers') -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $p = Join-Path $_.FullName 'Resources\Server\EasyServerStats'
        New-Item -ItemType Directory -Force -Path $p | Out-Null
        Copy-Item -Force (Join-Path $src 'EasyServerStats\main.lua') (Join-Path $p 'main.lua')
    }
    Ok 'Dashboard files installed'

    # firewall: the dashboard itself only lets in your home network unless you allow more
    Get-NetFirewallRule -DisplayName "$FwPrefix Dashboard" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName "$FwPrefix Dashboard" -Direction Inbound -Protocol TCP -LocalPort $DashPort -Action Allow -Profile Any | Out-Null

    # start at logon, hidden, as you (not as admin)
    Unregister-ScheduledTask -TaskName $DashTask -Confirm:$false -ErrorAction SilentlyContinue
    $action  = New-ScheduledTaskAction -Execute $pyw -Argument "`"$(Join-Path $dst 'dashboard.py')`"" -WorkingDirectory $dst
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $DashTask -Action $action -Trigger $trigger -Settings $set -RunLevel Limited | Out-Null
    Start-ScheduledTask -TaskName $DashTask
    Ok 'Dashboard starts automatically when you log in'
    Install-Guard $esDir
    [void](Test-Dashboard $esDir)

    $url = Join-Path ([Environment]::GetFolderPath('Desktop')) 'BeamMP Dashboard.url'
    [IO.File]::WriteAllText($url, "[InternetShortcut]`r`nURL=http://localhost:$DashPort/`r`nIconFile=$env:SystemRoot\System32\shell32.dll`r`nIconIndex=13`r`n")
    Ok '"BeamMP Dashboard" shortcut is on your desktop'
}

function Remove-Firewall {
    Get-NetFirewallRule -DisplayName "$FwPrefix*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
}

function Get-Shortcuts {
    $desk = [Environment]::GetFolderPath('Desktop')
    return @{
        Start  = Join-Path $desk 'Start BeamMP Server.lnk'
        Folder = Join-Path $desk 'BeamMP Server Folder.lnk'
        Mods   = Join-Path $desk 'Drop BeamMP Mods Here.lnk'
        Dash   = Join-Path $desk 'BeamMP Dashboard.url'
    }
}

# =============================================================================
#  UNINSTALL
# =============================================================================
if ($Uninstall) {
    $dir = Get-InstallDir
    Step 'Removing BeamMP EasyServer'
    Get-Process -Name 'BeamMP-Server' -ErrorAction SilentlyContinue | Stop-Process -Force
    Stop-Dashboard
    Unregister-ScheduledTask -TaskName $DashTask -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $GuardTask -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Firewall; Ok 'Firewall rules removed'
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue; Ok 'Autostart removed'
    $sc = Get-Shortcuts
    Remove-Item $sc.Start, $sc.Folder, $sc.Mods, $sc.Dash -ErrorAction SilentlyContinue; Ok 'Shortcuts removed'
    $a = Read-Host "Also delete the server folder with your settings and mods ($dir)? (y/N)"
    if ($a -match '^[Yy]') { Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue; Ok 'Folder deleted' }
    Remove-Item -Recurse -Force (Split-Path $StateFile) -ErrorAction SilentlyContinue
    Write-Host ''; Write-Host 'BeamMP EasyServer removed.' -ForegroundColor Green
    Finish
}

# =============================================================================
#  RESET DASHBOARD LOGIN (forgot password / lost the two-step phone)
# =============================================================================
if ($ResetLogin) {
    $dir = Get-InstallDir
    Step 'Resetting the dashboard login'
    Set-EsSecret $dir 'TOTP_SECRET' ''
    Set-EsSecret $dir 'MODS_PASSWORD' ''
    $j = Join-Path $dir 'EasyServer\data\dashboard.json'
    if (Test-Path $j) {
        $d = Get-Content $j -Raw | ConvertFrom-Json
        $d.remote_enabled = $false
        [IO.File]::WriteAllText($j, ($d | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))
    }
    Stop-Dashboard
    Start-ScheduledTask -TaskName $DashTask -ErrorAction SilentlyContinue
    Ok 'Password and two-step login removed, internet access turned off'
    Write-Host '  Open http://localhost:30815 on THIS computer to create a new password.'
    Start-Sleep -Seconds 2
    Start-Process 'http://localhost:30815/'
    Finish
}

# =============================================================================
#  UPDATE
# =============================================================================
if ($Update) {
    $dir = Get-InstallDir
    Write-Host "  BeamMP EasyServer v$EasyVersion - updating $dir"
    if (-not (Test-Path (Join-Path $dir 'BeamMP-Server.exe'))) {
        Warn "No server found in $dir - run Install-BeamMP-Server.bat first."; $script:EsFailed = $true; Finish
    }
    Protect-EsFolder $dir
    if (Test-Path (Split-Path $StateFile)) { Protect-EsFolder (Split-Path $StateFile) -AdminOnly }
    try { Download-Server $dir } catch { Warn "The server download failed: $($_.Exception.Message)"; $script:EsFailed = $true; Finish }
    [void](Copy-EsScripts $dir)
    if (Test-Path (Join-Path $dir 'EasyServer\python\pythonw.exe')) {
        try { Install-Dashboard $dir } catch { Warn "Dashboard update failed: $($_.Exception.Message)"; $script:EsFailed = $true }
    }
    if ($Unattended) { Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
    Ok 'Updated. Start it again with the "Start BeamMP Server" shortcut (or from the dashboard).'
    Finish
}

# =============================================================================
#  INSTALL - setup window
# =============================================================================
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$maps = @('gridmap_v2','west_coast_usa','east_coast_usa','utah','italy','jungle_rock_island',
          'industrial','small_island','automation_test_track','hirochi_raceway',
          'johnson_valley','derby','driver_training')

# Pre-fill from an existing install
$prevDir = Get-InstallDir
$prev = @{ Name = "$env:COMPUTERNAME BeamMP Server"; AuthKey = ''; Map = 'gridmap_v2'; MaxPlayers = 8; MaxCars = 1; Port = 30814; Private = $false }
$prevCfg = Join-Path $prevDir 'ServerConfig.toml'
if (Test-Path $prevCfg) {
    $txt = [IO.File]::ReadAllText($prevCfg)
    if ($txt -match '(?m)^\s*Name\s*=\s*"(.*)"')        { $prev.Name = $matches[1] -replace '\\"','"' -replace '\\\\','\' }
    if ($txt -match '(?m)^\s*AuthKey\s*=\s*"([^"]+)"')   { $prev.AuthKey = $matches[1] }   # old plain-text key: will be moved to encrypted storage
    if ($txt -match '(?m)^\s*Map\s*=\s*"/levels/([^/]+)/') { $prev.Map = $matches[1] }
    if ($txt -match '(?m)^\s*MaxPlayers\s*=\s*(\d+)')   { $prev.MaxPlayers = [int]$matches[1] }
    if ($txt -match '(?m)^\s*MaxCars\s*=\s*(\d+)')      { $prev.MaxCars = [int]$matches[1] }
    if ($txt -match '(?m)^\s*Port\s*=\s*(\d+)')         { $prev.Port = [int]$matches[1] }
    if ($txt -match '(?m)^\s*Private\s*=\s*true')       { $prev.Private = $true }
}

if ($Unattended) {
    # The same answers as pressing Install straight away (an earlier install's settings are kept)
    $prevPorts = 'auto'
    $prevJson = Join-Path $prevDir 'EasyServer\data\dashboard.json'
    if (Test-Path $prevJson) {
        try { if (-not (Get-Content $prevJson -Raw | ConvertFrom-Json).upnp_on) { $prevPorts = 'manual' } } catch { }
    }
    $nm = ($ServerName -replace '[\x00-\x1f"]', '').Trim()
    $cfg = @{
        Name = $(if ($nm) { $nm.Substring(0, [Math]::Min(60, $nm.Length)) } else { $prev.Name })
        Key = ''; VtKey = ''; Map = $prev.Map; Players = $prev.MaxPlayers; Cars = $prev.MaxCars; Port = $prev.Port
        Dir = $prevDir; Private = $prev.Private; Auto = $true; StartNow = $true; Dash = $true; Ports = $prevPorts
    }
} else {
$font = New-Object System.Drawing.Font('Segoe UI', 10)
$form = New-Object System.Windows.Forms.Form
$form.Text = "BeamMP EasyServer v$EasyVersion"
$form.Size = New-Object System.Drawing.Size(560, 640)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = $font

$y = 15
function Add-Label($text, $bold = $false) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $text; $l.AutoSize = $true
    $l.Location = New-Object System.Drawing.Point(20, $script:y)
    if ($bold) { $l.Font = New-Object System.Drawing.Font('Segoe UI', 13, [System.Drawing.FontStyle]::Bold) }
    $form.Controls.Add($l); return $l
}
function Add-Row($label, $control, $width = 300) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $label; $l.AutoSize = $true
    $l.Location = New-Object System.Drawing.Point(20, ($script:y + 3))
    $form.Controls.Add($l)
    $control.Location = New-Object System.Drawing.Point(190, $script:y)
    $control.Width = $width
    $form.Controls.Add($control)
    $script:y += 36
}

[void](Add-Label 'Set up your BeamMP server' $true); $y += 38

$tbName = New-Object System.Windows.Forms.TextBox; $tbName.Text = $prev.Name
Add-Row 'Server name' $tbName

$haveKey = [bool](Read-EsSecretsRaw $prevDir).ContainsKey('BEAMMP_AUTH_KEY')
$haveVt  = [bool](Read-EsSecretsRaw $prevDir).ContainsKey('VT_API_KEY')
$tbKey = New-Object System.Windows.Forms.TextBox; $tbKey.UseSystemPasswordChar = $true; $tbKey.Text = $prev.AuthKey
Add-Row 'AuthKey' $tbKey

$link = New-Object System.Windows.Forms.LinkLabel
$link.Text = 'Get a free AuthKey (log in with Discord, Keys -> +)'
if ($haveKey) { $link.Text = 'Saved encrypted - leave empty to keep it. Get a new key' }
$link.AutoSize = $true
$link.Location = New-Object System.Drawing.Point(187, ($y - 8))
$link.add_LinkClicked({ Start-Process $KeymasterUrl })
$form.Controls.Add($link); $y += 24

$cbMap = New-Object System.Windows.Forms.ComboBox
$cbMap.DropDownStyle = 'DropDown'   # allows typing a mod map name
[void]$cbMap.Items.AddRange($maps); $cbMap.Text = $prev.Map
Add-Row 'Map' $cbMap

$nPlayers = New-Object System.Windows.Forms.NumericUpDown
$nPlayers.Minimum = 1; $nPlayers.Maximum = 100; $nPlayers.Value = $prev.MaxPlayers
Add-Row 'Max players' $nPlayers 80

$nCars = New-Object System.Windows.Forms.NumericUpDown
$nCars.Minimum = 1; $nCars.Maximum = 20; $nCars.Value = $prev.MaxCars
Add-Row 'Cars per player' $nCars 80

$nPort = New-Object System.Windows.Forms.NumericUpDown
$nPort.Minimum = 1024; $nPort.Maximum = 65535; $nPort.Value = $prev.Port
Add-Row 'Port' $nPort 100

$tbDir = New-Object System.Windows.Forms.TextBox; $tbDir.Text = $prevDir
Add-Row 'Install folder' $tbDir

$tbVt = New-Object System.Windows.Forms.TextBox; $tbVt.UseSystemPasswordChar = $true
Add-Row 'VirusTotal key' $tbVt
$vtLink = New-Object System.Windows.Forms.LinkLabel
$vtLink.Text = 'Optional extra virus check for mods - get a free key'
if ($haveVt) { $vtLink.Text = 'Saved encrypted - leave empty to keep it ("off" removes it)' }
$vtLink.AutoSize = $true
$vtLink.Location = New-Object System.Drawing.Point(187, ($y - 8))
$vtLink.add_LinkClicked({ Start-Process 'https://www.virustotal.com/gui/join-us' })
$form.Controls.Add($vtLink); $y += 24

$keyNote = New-Object System.Windows.Forms.Label
$keyNote.Text = 'Keys are stored encrypted (Windows DPAPI), never in plain text.'
$keyNote.AutoSize = $true; $keyNote.ForeColor = [System.Drawing.Color]::DimGray
$keyNote.Location = New-Object System.Drawing.Point(20, $y); $form.Controls.Add($keyNote); $y += 28

$chkPublic = New-Object System.Windows.Forms.CheckBox
$chkPublic.Text = 'Show in the public BeamMP server list'; $chkPublic.AutoSize = $true
$chkPublic.Checked = -not $prev.Private
$chkPublic.Location = New-Object System.Drawing.Point(20, $y); $form.Controls.Add($chkPublic); $y += 30

$chkAuto = New-Object System.Windows.Forms.CheckBox
$chkAuto.Text = 'Start the server automatically when I log in'; $chkAuto.AutoSize = $true
$chkAuto.Location = New-Object System.Drawing.Point(20, $y); $form.Controls.Add($chkAuto); $y += 30

$chkStart = New-Object System.Windows.Forms.CheckBox
$chkStart.Text = 'Start the server when setup is done'; $chkStart.AutoSize = $true; $chkStart.Checked = $true
$chkStart.Location = New-Object System.Drawing.Point(20, $y); $form.Controls.Add($chkStart); $y += 30

$chkDash = New-Object System.Windows.Forms.CheckBox
$chkDash.Text = 'Install the web dashboard (manage the server from any PC or phone)'; $chkDash.AutoSize = $true; $chkDash.Checked = $true
$chkDash.Location = New-Object System.Drawing.Point(20, $y); $form.Controls.Add($chkDash); $y += 40

$btn = New-Object System.Windows.Forms.Button
$btn.Text = 'Install'; $btn.Width = 140; $btn.Height = 38
$btn.Font = New-Object System.Drawing.Font('Segoe UI', 11, [System.Drawing.FontStyle]::Bold)
$btn.Location = New-Object System.Drawing.Point(190, $y)
$btn.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.AcceptButton = $btn
$form.Controls.Add($btn)

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = 'Cancel'; $btnCancel.Width = 100; $btnCancel.Height = 38
$btnCancel.Location = New-Object System.Drawing.Point(340, $y)
$btnCancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.CancelButton = $btnCancel
$form.Controls.Add($btnCancel)

if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { Write-Host 'Cancelled.'; exit }

$cfg = @{
    Name     = $tbName.Text.Trim()
    Key      = ($tbKey.Text -replace '\s', '')
    VtKey    = ($tbVt.Text -replace '\s', '')
    Map      = ($cbMap.Text.Trim() -replace '[\\/"]', '')
    Players  = [int]$nPlayers.Value
    Cars     = [int]$nCars.Value
    Port     = [int]$nPort.Value
    Dir      = $tbDir.Text.Trim().TrimEnd('\')
    Private  = (-not $chkPublic.Checked)
    Auto     = $chkAuto.Checked
    StartNow = $chkStart.Checked
    Dash     = $chkDash.Checked
}
if (-not $cfg.Name) { $cfg.Name = "$env:COMPUTERNAME BeamMP Server" }
if (-not $cfg.Map)  { $cfg.Map = 'gridmap_v2' }
if (-not $cfg.Dir)  { $cfg.Dir = $DefaultDir }

# How friends outside the home get in (pre-select what this computer used last time)
$prevPorts = 'auto'
$prevJson = Join-Path $cfg.Dir 'EasyServer\data\dashboard.json'
if (Test-Path $prevJson) {
    try { if (-not (Get-Content $prevJson -Raw | ConvertFrom-Json).upnp_on) { $prevPorts = 'manual' } } catch { }
}
$cfg.Ports = Show-PortChoice $cfg.Port $cfg.Dash $prevPorts
}

try {
    Write-Host ''
    Write-Host "  BeamMP EasyServer v$EasyVersion - installing to $($cfg.Dir)" -ForegroundColor White

    # ---- folders ----
    Step 'Creating the server folder'
    New-Item -ItemType Directory -Force -Path $cfg.Dir, (Join-Path $cfg.Dir 'Resources\Client'), (Join-Path $cfg.Dir 'Resources\Server') | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $StateFile) | Out-Null
    Protect-EsFolder $cfg.Dir
    Protect-EsFolder (Split-Path $StateFile) -AdminOnly
    Set-Content -Path $StateFile -Value $cfg.Dir
    Ok $cfg.Dir

    # ---- Visual C++ runtime ----
    Step 'Checking Microsoft Visual C++ Runtime'
    $vc = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
    if (-not $vc) { $vc = Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue }
    if ($vc -and $vc.Installed -eq 1) {
        Ok 'Already installed'
    } else {
        Write-Host '  Installing it (takes a minute)...'
        $vcTmp = Join-Path $env:TEMP ('vc_redist-' + [guid]::NewGuid().ToString('N') + '.exe')
        Invoke-WebRequest -Uri $VcRedistUrl -OutFile $vcTmp -UseBasicParsing
        Assert-Signed $vcTmp 'Microsoft Corporation'
        $p = Start-Process -FilePath $vcTmp -ArgumentList '/install', '/quiet', '/norestart' -Wait -PassThru
        Remove-Item $vcTmp -ErrorAction SilentlyContinue
        if ($p.ExitCode -in 0, 1638, 3010) { Ok 'Installed' } else { Warn "Installer returned code $($p.ExitCode) - the server may still work." }
    }

    # ---- server ----
    Download-Server $cfg.Dir
    $exe = Join-Path $cfg.Dir 'BeamMP-Server.exe'

    # ---- config ----
    Step 'Saving server settings'
    function Esc($s) { return ($s -replace '\\', '\\' -replace '"', '\"') }
    $priv = if ($cfg.Private) { 'true' } else { 'false' }
    $toml = @"
# BeamMP server settings - created by BeamMP EasyServer
# Change anything here, then restart the server.
# The AuthKey is NOT stored here: it is kept encrypted (Windows DPAPI).

[General]
Name = "$(Esc $cfg.Name)"
Port = $($cfg.Port)
AuthKey = "" # stored encrypted - run Install-BeamMP-Server.bat to change it
AllowGuests = true
LogChat = true
Debug = false
IP = "::"
Private = $priv
InformationPacket = true
Map = "/levels/$($cfg.Map)/info.json"
Description = "Hosted with BeamMP EasyServer"
MaxCars = $($cfg.Cars)
MaxPlayers = $($cfg.Players)
ResourceFolder = "Resources"
Tags = "Freeroam"

[Misc]
ImScaredOfUpdates = false
UpdateReminderTime = "30s"
"@
    [IO.File]::WriteAllText((Join-Path $cfg.Dir 'ServerConfig.toml'), ($toml -replace "`r?`n", "`r`n"), (New-Object Text.UTF8Encoding $false))
    Ok 'ServerConfig.toml written'

    # ---- encrypted keys ----
    Step 'Saving your keys encrypted'
    if ($cfg.Key) {
        if ($cfg.Key -match '^[A-Za-z0-9-]+$') { Set-EsSecret $cfg.Dir 'BEAMMP_AUTH_KEY' $cfg.Key; Ok "AuthKey saved encrypted ($(Hide-EsKey $cfg.Key))" }
        else { Warn 'That AuthKey has unexpected characters - not saved.' }
    }
    if ($cfg.VtKey -eq 'off') { Set-EsSecret $cfg.Dir 'VT_API_KEY' ''; Ok 'VirusTotal check turned off' }
    elseif ($cfg.VtKey) {
        if ($cfg.VtKey -match '^[a-fA-F0-9]{64}$') { Set-EsSecret $cfg.Dir 'VT_API_KEY' $cfg.VtKey.ToLowerInvariant(); Ok "VirusTotal key saved encrypted ($(Hide-EsKey $cfg.VtKey))" }
        else { Warn "That doesn't look like a VirusTotal key (64 letters/numbers) - not saved." }
    }
    if (-not (Read-EsSecretsRaw $cfg.Dir).ContainsKey('BEAMMP_AUTH_KEY')) { Warn 'No AuthKey yet - run this installer again to add it before playing online.' }

    # ---- firewall ----
    Step "Opening port $($cfg.Port) in Windows Firewall"
    Remove-Firewall
    New-NetFirewallRule -DisplayName "$FwPrefix TCP" -Direction Inbound -Protocol TCP -LocalPort $cfg.Port -Action Allow -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName "$FwPrefix UDP" -Direction Inbound -Protocol UDP -LocalPort $cfg.Port -Action Allow -Profile Any | Out-Null
    New-NetFirewallRule -DisplayName "$FwPrefix App" -Direction Inbound -Program $exe -Action Allow -Profile Any | Out-Null
    Ok 'Firewall rules added'

    # ---- shortcuts ----
    Step 'Creating desktop shortcuts'
    $sc = Get-Shortcuts
    $shell = New-Object -ComObject WScript.Shell
    $esDir = Copy-EsScripts $cfg.Dir
    $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $startPs = Join-Path $esDir 'start-server.ps1'
    $l = $shell.CreateShortcut($sc.Start)
    $l.TargetPath = $psExe
    $l.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$startPs`""
    $l.WorkingDirectory = $cfg.Dir; $l.IconLocation = "$exe,0"
    $l.Description = 'Check mods for viruses and start the BeamMP server'
    $l.Save()
    $l = $shell.CreateShortcut($sc.Folder)
    $l.TargetPath = $cfg.Dir; $l.Description = 'Server settings and mods'
    $l.Save()
    # drag & drop mod helper
    $addMods = Join-Path $esDir 'add-mods.ps1'
    $l = $shell.CreateShortcut($sc.Mods)
    $l.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $l.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$addMods`""
    $l.WorkingDirectory = $cfg.Dir
    $l.IconLocation = "$env:SystemRoot\System32\shell32.dll,45"
    $l.Description = 'Drag mod .zip files onto this icon. Double-click to open the mods folder.'
    $l.Save()
    Ok '"Start BeamMP Server", "BeamMP Server Folder" and "Drop BeamMP Mods Here" are on your desktop'

    # ---- autostart ----
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    if ($cfg.Auto) {
        Step 'Setting up autostart'
        $action  = New-ScheduledTaskAction -Execute $psExe -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startPs`"" -WorkingDirectory $cfg.Dir
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
        $set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $set -RunLevel Limited | Out-Null
        Ok 'Server will start when you log in'
    }

    # ---- dashboard ----
    $dashOk = $false
    $newPw = ''
    if ($Unattended -and $cfg.Dash -and -not (Read-EsSecretsRaw $cfg.Dir).ContainsKey('MODS_PASSWORD')) {
        $abc = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        $buf = New-Object byte[] 16
        $rng.GetBytes($buf)
        $newPw = -join ($buf | ForEach-Object { $abc[$_ % $abc.Length] })
        Set-EsSecret $cfg.Dir 'MODS_PASSWORD' $newPw
    }
    if ($cfg.Dash) {
        $preset = if ($cfg.Ports -eq 'auto') { @{ upnp_on = $true; upnp_mode = 'needed' } } else { @{ upnp_on = $false } }
        try { Install-Dashboard $cfg.Dir $preset; $dashOk = $true }
        catch { Warn "The dashboard couldn't be installed: $($_.Exception.Message). The server itself works fine." }
    }

    # ---- addresses ----
    $lan = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
            Select-Object -First 1).IPAddress
    $pub = 'unknown'
    foreach ($u in 'https://api.ipify.org', 'https://ifconfig.me/ip', 'https://icanhazip.com') {
        try {
            $ip = (Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 6).Content.Trim()
            if ($ip -match '^[0-9a-fA-F.:]{3,45}$') { $pub = $ip; break }
        } catch { }
    }

    # start through the shortcut via Explorer so it runs as you (not as admin);
    # that way the mod tool can restart it later
    if ($cfg.StartNow) {
        if ($Unattended) { Start-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }   # no desktop to start it from
        else { Start-Process explorer.exe -ArgumentList "`"$($sc.Start)`"" }
    }

    Write-Host ''
    Write-Host '  All done!' -ForegroundColor Green
    Write-Host ''
    Write-Host "  Friends on the same Wi-Fi connect to:   $($lan):$($cfg.Port)"
    Write-Host "  Friends over the internet connect to:   $($pub):$($cfg.Port)"
    if ($cfg.Ports -eq 'auto' -and $dashOk) {
        Write-Host "    -> The dashboard opens port $($cfg.Port) on your router when you invite friends" -ForegroundColor Cyan
        Write-Host '       (Copy invite, or /join in Discord) and closes it 30 minutes after the last player leaves.'
        Write-Host "       Check that your router said yes: dashboard -> Health -> Automatic port forwarding."
    } elseif ($cfg.Ports -eq 'manual' -or $cfg.Ports -eq 'auto') {
        $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1).NextHop
        Write-Host ''
        Write-Host '  Set up port forwarding on your router:' -ForegroundColor Cyan
        Write-Host "    1. Open your router's settings page: http://$(if ($gw) { $gw } else { '192.168.0.1' })  (the login is often on a sticker on the router)"
        Write-Host '    2. Find "Port forwarding" (sometimes called "Virtual server" or "NAT").'
        Write-Host "    3. Add a rule:  port $($cfg.Port)  -  protocol TCP and UDP (or Both)  -  to $lan"
        Write-Host '    4. Save. Test it on the dashboard''s Health page.'
        Write-Host '    Stuck? Search "<your router model> port forwarding".'
        if (-not $Unattended) { try { Start-Process 'https://csabika-dev.github.io/beammp-easyserver/help.html#friends-cant-join' } catch { } }
    } else {
        Write-Host "    -> Not set up yet. When you want it: dashboard -> Health -> Automatic port forwarding."
    }
    Write-Host ''
    if ($dashOk) {
        Write-Host '  Dashboard:           ' -NoNewline; Write-Host "http://localhost:$DashPort  (double-click 'BeamMP Dashboard' on your desktop)" -ForegroundColor Cyan
        Write-Host "                       other devices at home: http://$($lan):$DashPort"
        if ($newPw) {
            Write-Host "    Password:  $newPw"
            Write-Host '                       (change it in the dashboard: click your name -> My account)'
        } elseif ($Unattended) {
            Write-Host '                       Log in with the password it already had.'
        } else {
            Write-Host '                       The first time you open it, create a password.'
            Start-Sleep -Seconds 2
            Start-Process "http://localhost:$DashPort/"
        }
    }
    Write-Host '  Add mods:            drag .zip files onto "Drop BeamMP Mods Here" on your desktop'
    Write-Host '  Mods folder:         ' -NoNewline; Write-Host (Join-Path $cfg.Dir 'Resources\Client')
    Write-Host '  Update later:        Update-BeamMP-Server.bat'
    Write-Host '  Remove:              Uninstall-BeamMP-Server.bat'
} catch {
    Write-Host ''
    Write-Host "  [ERROR] $($_.Exception.Message)" -ForegroundColor Red
    $script:EsFailed = $true
    Write-Host '  If this keeps happening, open an issue on GitHub with this message.'
}
Finish
