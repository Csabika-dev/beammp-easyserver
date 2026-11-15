# BeamMP EasyServer - BeamMP-only guard, Windows firewall part.
#
# The dashboard runs as you (no admin rights), so it can't change Windows
# Firewall. It writes the addresses it wants blocked to data\guard-block.txt and
# this script - run every minute by the "BeamMP Guard (EasyServer)" task as
# SYSTEM - turns that list into two firewall rules (TCP + UDP, game ports only).
#
# The installer copies this file to a folder only administrators can change, so
# the task never runs anything you (or a program running as you) could edit.
# Everything read from guard-block.txt is checked: only plain IP addresses and
# port numbers get through, and the rules only ever BLOCK, only the game ports.
param([Parameter(Mandatory = $true)][string]$DataDir)

$ErrorActionPreference = 'Stop'
$RuleName  = 'BeamMP Server (EasyServer) Guard'
$ListFile  = Join-Path $DataDir 'guard-block.txt'
# the "I ran" note goes next to this script (only admins can write there), never into the data folder:
# SYSTEM writing into a folder you control could be tricked into overwriting other files
$StatusFile = Join-Path $PSScriptRoot 'guard-status.txt'

$ports = @()
$ips = New-Object System.Collections.Generic.List[string]
if (Test-Path -LiteralPath $ListFile -PathType Leaf) {
    $lines = Get-Content -LiteralPath $ListFile -TotalCount 5001 -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
        $l = "$line".Trim()
        if ($l -match '^ports=([0-9,]*)$') {
            foreach ($p in ($Matches[1] -split ',')) {
                $n = 0
                if ([int]::TryParse($p, [ref]$n) -and $n -ge 1024 -and $n -le 65535) { $ports += $n }
            }
            continue
        }
        $a = $null
        # only full addresses: 1.2.3.4 or an IPv6 address - nothing that Windows would read as a range
        if (($l -match '^\d{1,3}(\.\d{1,3}){3}$' -or ($l -match '^[0-9A-Fa-f:]+$' -and $l.Contains(':'))) -and
            [System.Net.IPAddress]::TryParse($l, [ref]$a)) {
            $b = $a.GetAddressBytes()
            $private = $a.IsIPv6LinkLocal -or [System.Net.IPAddress]::IsLoopback($a) -or
                ($b.Length -eq 4 -and ($b[0] -eq 10 -or ($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31) -or ($b[0] -eq 192 -and $b[1] -eq 168)))
            if (-not $private -and $ips.Count -lt 5000) { $ips.Add($a.ToString()) }
        }
    }
}
$ports = @($ports | Sort-Object -Unique | Select-Object -First 64)
$want = ''
if ($ports.Count -and $ips.Count) {
    $text = ($ports -join ',') + '|' + (($ips | Sort-Object -Unique) -join ',')
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $want = 'list ' + (($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($text)) | ForEach-Object { $_.ToString('x2') }) -join '')
}

# only touch the firewall when the list changed
$have = ''
$existing = @(Get-NetFirewallRule -DisplayName "$RuleName*" -ErrorAction SilentlyContinue)
if ($existing.Count) { $have = "$($existing[0].Description)" }
if ($have -ne $want) {
    $existing | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    if ($want) {
        $list = @($ips | Sort-Object -Unique)
        foreach ($proto in 'TCP', 'UDP') {
            New-NetFirewallRule -DisplayName "$RuleName $proto" -Description $want -Direction Inbound -Action Block `
                -Protocol $proto -LocalPort $ports -RemoteAddress $list -Profile Any | Out-Null
        }
    }
}
Set-Content -LiteralPath $StatusFile -Value ("{0} {1}" -f [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(), $ips.Count) -Encoding ascii
