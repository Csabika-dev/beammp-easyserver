# =============================================================================
#  BeamMP EasyServer - shared helpers for Windows (dot-sourced by the others)
#   - encrypted key storage (Windows DPAPI, tied to your Windows account)
#   - mod safety check (built-in checks + Microsoft Defender + VirusTotal)
# =============================================================================
Add-Type -AssemblyName System.Security
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Script:StateFile = Join-Path $env:ProgramData 'BeamMP-EasyServer\install-dir.txt'
$Script:Entropy   = [Text.Encoding]::UTF8.GetBytes('BeamMP-EasyServer-v1')

function Get-EsInstallDir {
    if (Test-Path $Script:StateFile) {
        $d = (Get-Content $Script:StateFile -Raw).Trim()
        if ($d) { return $d }
    }
    return 'C:\BeamMP-Server'
}
function Get-EsDataDir([string]$Dir) { return (Join-Path $Dir 'EasyServer') }

# ---------------------------------------------------------------------------
#  Encrypted keys. Stored in <server>\EasyServer\secrets.dat, encrypted with
#  Windows DPAPI for the current user: only your Windows account on this PC
#  can decrypt them. Copying the file to another PC/account gives nothing.
# ---------------------------------------------------------------------------
function Get-EsSecretsFile([string]$Dir) { return (Join-Path (Get-EsDataDir $Dir) 'secrets.dat') }

function Read-EsSecretsRaw([string]$Dir) {
    $map = @{}
    $f = Get-EsSecretsFile $Dir
    if (Test-Path $f) {
        foreach ($line in [IO.File]::ReadAllLines($f)) {
            $i = $line.IndexOf('=')
            if ($i -gt 0) { $map[$line.Substring(0, $i)] = $line.Substring($i + 1) }
        }
    }
    return $map
}

function Set-EsSecret([string]$Dir, [string]$Name, [string]$Value) {
    $map = Read-EsSecretsRaw $Dir
    if ([string]::IsNullOrEmpty($Value)) {
        $map.Remove($Name)
    } else {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
        $enc = [Security.Cryptography.ProtectedData]::Protect($bytes, $Script:Entropy, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        $map[$Name] = [Convert]::ToBase64String($enc)
    }
    $f = Get-EsSecretsFile $Dir
    New-Item -ItemType Directory -Force -Path (Split-Path $f) | Out-Null
    $lines = @('# BeamMP EasyServer - encrypted with Windows DPAPI. Useless on any other PC/account.')
    foreach ($k in ($map.Keys | Sort-Object)) { if ($k -notlike '#*') { $lines += "$k=$($map[$k])" } }
    [IO.File]::WriteAllLines($f, $lines)
}

function Get-EsSecret([string]$Dir, [string]$Name) {
    $map = Read-EsSecretsRaw $Dir
    if (-not $map.ContainsKey($Name)) { return '' }
    try {
        $plain = [Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($map[$Name]), $Script:Entropy, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        return [Text.Encoding]::UTF8.GetString($plain)
    } catch {
        # encrypted by another Windows account (or another PC)
        return $null
    }
}

function Hide-EsKey([string]$k) { if ($k.Length -gt 6) { return '****' + $k.Substring($k.Length - 4) } return '****' }

# ---------------------------------------------------------------------------
#  Mod safety check
# ---------------------------------------------------------------------------
$Script:BlockedExt = @('exe','dll','scr','com','pif','cpl','sys','drv','ocx','msi','msp','mst',
    'bat','cmd','ps1','psm1','psd1','vbs','vbe','jse','wsf','wsh','wsc','hta','lnk','url','reg',
    'inf','jar','appx','msix','application','gadget','chm','sh','bash','elf','so','dylib','app',
    'apk','deb','rpm','run','bin','iso','img','vhd','vhdx','docm','xlsm','pptm')
$Script:ArchiveExt = @('zip','rar','7z','tar','gz','bz2','xz','cab','zst')
$Script:MagicSafeExt = @('txt','json','jbeam','lua','md','cs','ini','csv','html','css','js')
$Script:LuaRules = @(
    @('\bos\.execute\s*\(', 'runs system commands (os.execute)'),
    @('\bio\.popen\s*\(', 'runs system commands (io.popen)'),
    @('\bffi\.load\s*\(', 'loads native code (ffi.load)'),
    @('\bpackage\.loadlib\s*\(', 'loads native code (package.loadlib)'),
    @('require\s*\(?\s*["'']socket', 'opens network connections (socket)'),
    @('\b(loadstring|load)\s*\(\s*["''][A-Za-z0-9+/=\\]{400,}', 'runs hidden encoded code'),
    @('(\\x[0-9a-fA-F]{2}){80,}|(\\\d{2,3}){120,}', 'contains a large block of encoded bytes'),
    @('https?://[^\s"'']+\.(exe|dll|bat|ps1|scr|msi)\b', 'links to a program download'),
    @('\bos\.remove\s*\(\s*["''][A-Za-z]:\\', 'deletes files on the PC')
)
$Script:ScanVersion = 1

function New-EsResult { return [pscustomobject]@{ Verdict = 'clean'; Reasons = New-Object System.Collections.ArrayList; Checks = New-Object System.Collections.ArrayList; Notes = New-Object System.Collections.ArrayList; VT = $false } }
function Add-EsFlag($r, [string]$level, [string]$msg) {
    $order = @{ clean = 0; warning = 1; blocked = 2 }
    if ($order[$level] -gt $order[$r.Verdict]) { $r.Verdict = $level }
    if (-not $r.Reasons.Contains($msg)) { [void]$r.Reasons.Add($msg) }
}

function Test-EsEntryEncrypted($entry) {
    $p = $entry.GetType().GetProperty('IsEncrypted')
    if ($p) { return [bool]$p.GetValue($entry) }
    $f = $entry.GetType().GetField('_generalPurposeBitFlag', [Reflection.BindingFlags]'NonPublic,Instance')
    if ($f) { return (([int]$f.GetValue($entry)) -band 1) -eq 1 }
    return $false
}

function Invoke-EsBuiltinCheck([string]$Path, $r) {
    [void]$r.Checks.Add('built-in')
    try { $zip = [IO.Compression.ZipFile]::OpenRead($Path) } catch { Add-EsFlag $r 'blocked' 'not a valid .zip file'; return }
    try {
        $total = [int64]0; $hasMod = $false
        if ($zip.Entries.Count -gt 200000) { Add-EsFlag $r 'blocked' 'contains an absurd number of files'; return }
        foreach ($e in $zip.Entries) {
            $name = $e.FullName.Replace('\', '/')
            $low = $name.ToLowerInvariant()
            $base = ($low -split '/')[-1]
            $ext = ''; if ($base.Contains('.')) { $ext = ($base -split '\.')[-1] }
            $total += $e.Length
            if ($name.StartsWith('/') -or $low -match '^[a-z]:' -or ("/$name/" -match '/\.\./')) { Add-EsFlag $r 'blocked' "tries to write outside the mod folder: $name" }
            if (Test-EsEntryEncrypted $e) { Add-EsFlag $r 'blocked' "has password-protected files that can't be checked: $name"; continue }
            if ($name.EndsWith('/')) { continue }
            if ($low -match '^(vehicles|levels|art|ui|lua|scripts|settings|gameplay|mods)/' -or $ext -in @('jbeam','dae')) { $hasMod = $true }
            if ($Script:BlockedExt -contains $ext) { Add-EsFlag $r 'blocked' "contains a program/script file: $name" }
            elseif ($base -match '\.(exe|scr|bat|cmd|vbs|pif|com)\.[a-z0-9]{1,4}$') { Add-EsFlag $r 'blocked' "has a disguised file name: $name" }
            if ($Script:ArchiveExt -contains $ext) { Add-EsFlag $r 'warning' "contains another archive that wasn't checked: $name" }
            if ($e.Length -gt 50MB -and $e.CompressedLength -gt 0 -and ($e.Length / $e.CompressedLength) -gt 250) { Add-EsFlag $r 'blocked' "looks like a 'zip bomb' (fills up the disk): $name" }
            try {
                if (($Script:MagicSafeExt -notcontains $ext) -and $e.Length -ge 4) {
                    $s = $e.Open(); $buf = New-Object byte[] 4; $n = $s.Read($buf, 0, 4); $s.Dispose()
                    if ($n -ge 2 -and $buf[0] -eq 0x4D -and $buf[1] -eq 0x5A) { Add-EsFlag $r 'blocked' "$name is really a Windows program" }
                    elseif ($n -eq 4 -and $buf[0] -eq 0x7F -and $buf[1] -eq 0x45 -and $buf[2] -eq 0x4C -and $buf[3] -eq 0x46) { Add-EsFlag $r 'blocked' "$name is really a Linux program" }
                    elseif ($n -eq 4 -and (($buf[0] -eq 0xCF -and $buf[1] -eq 0xFA) -or ($buf[0] -eq 0xCA -and $buf[1] -eq 0xFE))) { Add-EsFlag $r 'blocked' "$name is really a macOS/Java program" }
                }
                if ($ext -eq 'lua' -and $e.Length -lt 8MB) {
                    $sr = New-Object IO.StreamReader($e.Open())
                    $code = $sr.ReadToEnd(); $sr.Dispose()
                    foreach ($rule in $Script:LuaRules) { if ($code -match $rule[0]) { Add-EsFlag $r 'warning' "Lua script $name $($rule[1])" } }
                }
            } catch { Add-EsFlag $r 'blocked' "damaged or unreadable file inside: $name" }
        }
        if ($total -gt 12GB) { Add-EsFlag $r 'blocked' "unpacks to more than 12 GB - looks like a 'zip bomb'" }
        if (-not $hasMod -and $zip.Entries.Count -gt 0 -and $r.Verdict -ne 'blocked') { Add-EsFlag $r 'warning' "doesn't look like a BeamNG mod (no vehicles/, levels/, ui/... folders)" }
    } finally { $zip.Dispose() }
}

function Invoke-EsDefenderCheck([string]$Path, $r) {
    $mp = Join-Path $env:ProgramFiles 'Windows Defender\MpCmdRun.exe'
    if (-not (Test-Path $mp)) { [void]$r.Notes.Add('Microsoft Defender not found - skipped'); return }
    try {
        $out = & $mp -Scan -ScanType 3 -File $Path -DisableRemediation 2>&1
        $code = $LASTEXITCODE
    } catch { [void]$r.Notes.Add('Microsoft Defender could not run'); return }
    if ($code -eq 0) { [void]$r.Checks.Add('Microsoft Defender') }
    elseif ($code -eq 2) {
        [void]$r.Checks.Add('Microsoft Defender')
        $threat = ($out | Where-Object { $_ -match 'Threat\s*:' } | Select-Object -First 1)
        if (-not $threat) { $threat = 'threat found' }
        Add-EsFlag $r 'blocked' ("Microsoft Defender: " + ($threat -replace '^\s*Threat\s*:\s*', ''))
    } else { [void]$r.Notes.Add("Microsoft Defender skipped (code $code - another antivirus may be active)") }
}

function Invoke-EsVtRequest([string]$Method, [string]$Url, [string]$Key) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers @{ 'x-apikey' = $Key; 'accept' = 'application/json' } -UseBasicParsing -TimeoutSec 60
}

function Set-EsVtVerdict($stats, [string]$sha, $r) {
    $mal = [int]$stats.malicious; $sus = [int]$stats.suspicious
    $link = "https://www.virustotal.com/gui/file/$sha"
    if ($mal -ge 2) { Add-EsFlag $r 'blocked' "VirusTotal: $mal antivirus engines say it's malicious ($link)" }
    elseif (($mal + $sus) -ge 1) { Add-EsFlag $r 'warning' "VirusTotal: $($mal + $sus) engine(s) flagged it - probably a false alarm ($link)" }
}

function Invoke-EsVirusTotalCheck([string]$Path, [string]$Sha, [string]$Key, $r, [int]$UploadMaxMB = 200) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $api = 'https://www.virustotal.com/api/v3'
    try {
        try {
            $d = Invoke-EsVtRequest 'GET' "$api/files/$Sha" $Key
            [void]$r.Checks.Add('VirusTotal'); $r.VT = $true
            Set-EsVtVerdict $d.data.attributes.last_analysis_stats $Sha $r
            return
        } catch {
            $status = 0
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
            if ($status -eq 401) { [void]$r.Notes.Add('VirusTotal skipped: the API key is wrong'); return }
            if ($status -eq 429) { [void]$r.Notes.Add('VirusTotal skipped: free limit reached, try later'); return }
            if ($status -ne 404) { [void]$r.Notes.Add("VirusTotal skipped: can't reach it (no internet?)"); return }
        }
        $sizeMB = (Get-Item -LiteralPath $Path).Length / 1MB
        if ($sizeMB -gt $UploadMaxMB) { [void]$r.Notes.Add(("VirusTotal skipped: new file is {0:N0} MB (upload limit {1} MB)" -f $sizeMB, $UploadMaxMB)); return }
        $url = "$api/files"
        if ($sizeMB -gt 32) { $url = (Invoke-EsVtRequest 'GET' "$api/files/upload_url" $Key).data }
        Add-Type -AssemblyName System.Net.Http
        $client = New-Object System.Net.Http.HttpClient
        $client.Timeout = [TimeSpan]::FromMinutes(30)
        $client.DefaultRequestHeaders.Add('x-apikey', $Key)
        $form = New-Object System.Net.Http.MultipartFormDataContent
        $fs = [IO.File]::OpenRead($Path)
        try {
            $content = New-Object System.Net.Http.StreamContent($fs)
            $form.Add($content, 'file', [IO.Path]::GetFileName($Path))
            $resp = $client.PostAsync($url, $form).Result
            $body = $resp.Content.ReadAsStringAsync().Result | ConvertFrom-Json
        } finally { $fs.Dispose(); $client.Dispose() }
        $id = $body.data.id
        Write-Host '    uploaded to VirusTotal, waiting for the result (up to 5 minutes)...'
        $deadline = (Get-Date).AddMinutes(5)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 20
            $a = Invoke-EsVtRequest 'GET' "$api/analyses/$id" $Key
            if ($a.data.attributes.status -eq 'completed') {
                [void]$r.Checks.Add('VirusTotal'); $r.VT = $true
                Set-EsVtVerdict $a.data.attributes.stats $Sha $r
                return
            }
        }
        [void]$r.Notes.Add('VirusTotal: still analysing after 5 minutes - other checks used')
    } catch { [void]$r.Notes.Add('VirusTotal skipped: ' + $_.Exception.Message) }
}

# Cache so unchanged mods aren't re-scanned at every server start
function Get-EsCacheFile([string]$Dir) { return (Join-Path (Get-EsDataDir $Dir) 'scancache.txt') }
function Get-EsFileId([string]$Path) { $i = Get-Item -LiteralPath $Path; return ('{0}|{1}|{2}' -f $i.Name, $i.Length, $i.LastWriteTimeUtc.Ticks) }

function Invoke-EsModScan([string]$Path, [string]$Dir, [switch]$Quiet) {
    $vtKey = Get-EsSecret $Dir 'VT_API_KEY'
    $cacheFile = Get-EsCacheFile $Dir
    $id = Get-EsFileId $Path
    if (Test-Path $cacheFile) {
        foreach ($line in [IO.File]::ReadAllLines($cacheFile)) {
            $p = $line -split "`t"
            if ($p.Count -ge 5 -and $p[0] -eq $id -and [int]$p[1] -eq $Script:ScanVersion -and ($p[3] -eq '1' -or -not $vtKey -or $p[2] -eq 'blocked')) {
                $r = New-EsResult; $r.Verdict = $p[2]; $r.VT = ($p[3] -eq '1')
                foreach ($x in ($p[4] -split ' ;; ')) { if ($x) { [void]$r.Reasons.Add($x) } }
                [void]$r.Checks.Add('earlier check')
                return $r
            }
        }
    }
    $r = New-EsResult
    Invoke-EsBuiltinCheck $Path $r
    if ($r.Verdict -ne 'blocked') { Invoke-EsDefenderCheck $Path $r }
    if ($r.Verdict -ne 'blocked' -and $vtKey) {
        $sha = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        Invoke-EsVirusTotalCheck $Path $sha $vtKey $r
    }
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $cacheFile) | Out-Null
        $vt = '0'; if ($r.VT) { $vt = '1' }
        $keep = @()
        if (Test-Path $cacheFile) { $keep = @([IO.File]::ReadAllLines($cacheFile) | Where-Object { -not $_.StartsWith("$id`t") } | Select-Object -Last 1500) }
        $keep += ($id, $Script:ScanVersion, $r.Verdict, $vt, ($r.Reasons -join ' ;; ')) -join "`t"
        [IO.File]::WriteAllLines($cacheFile, [string[]]$keep)
    } catch { }
    return $r
}

function Write-EsResult([string]$Name, $r) {
    $color = @{ clean = 'Green'; warning = 'Yellow'; blocked = 'Red' }[$r.Verdict]
    $label = @{ clean = 'OK     '; warning = 'WARNING'; blocked = 'BLOCKED' }[$r.Verdict]
    Write-Host ("  [{0}] {1}   (checked by: {2})" -f $label, $Name, ($r.Checks -join ', ')) -ForegroundColor $color
    foreach ($x in $r.Reasons) { Write-Host "      - $x" -ForegroundColor $color }
    foreach ($x in $r.Notes) { Write-Host "      note: $x" -ForegroundColor DarkGray }
}

# Scan every mod in the mods folder; move blocked ones to Resources\Quarantine
function Invoke-EsSweep([string]$Dir, [string]$Base = '') {
    # $Dir = the server folder, $Base = the install folder with the keys and scan cache
    if (-not $Base) { $Base = $Dir }
    $client = Join-Path $Dir 'Resources\Client'
    $quar = Join-Path $Dir 'Resources\Quarantine'
    $blocked = 0
    if (-not (Test-Path $client)) { return 0 }
    foreach ($f in (Get-ChildItem -LiteralPath $client -Filter *.zip -File)) {
        $r = Invoke-EsModScan $f.FullName $Base
        if ($r.Verdict -eq 'blocked') {
            New-Item -ItemType Directory -Force -Path $quar | Out-Null
            $dest = Join-Path $quar $f.Name
            Move-Item -LiteralPath $f.FullName -Destination $dest -Force
            [IO.File]::WriteAllText("$dest.why.txt", "Blocked by the BeamMP EasyServer mod safety check:`r`n- " + ($r.Reasons -join "`r`n- "))
            Write-EsResult $f.Name $r
            Write-Host "      -> moved to $quar" -ForegroundColor Red
            $blocked++
        } elseif ($r.Verdict -eq 'warning' -and -not ($r.Checks -contains 'earlier check')) {
            Write-EsResult $f.Name $r
        }
    }
    return $blocked
}
