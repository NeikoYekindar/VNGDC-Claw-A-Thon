# Windows Server 2022 Security Hardening Check Script
# Run via SSH (OpenSSH on Windows) or WinRM
# Outputs structured sections for AI analysis

$PASS = "[PASS]"
$FAIL = "[FAIL]"
$WARN = "[WARN]"
$INFO = "[INFO]"

function Sep($title) { Write-Host ""; Write-Host "=== $title ===" }

# ── 1. Windows Defender ────────────────────────────────────────────────────────
Sep "WINDOWS DEFENDER"
try {
  $mpStatus = Get-MpComputerStatus -ErrorAction Stop
  if ($mpStatus.AntivirusEnabled) { Write-Host "$PASS Antivirus: Enabled" }
  else { Write-Host "$FAIL Antivirus: DISABLED" }
  if ($mpStatus.RealTimeProtectionEnabled) { Write-Host "$PASS Real-time protection: Enabled" }
  else { Write-Host "$FAIL Real-time protection: DISABLED" }
  Write-Host "$INFO Antivirus signature version: $($mpStatus.AntivirusSignatureVersion)"
  Write-Host "$INFO Last signature update: $($mpStatus.AntivirusSignatureLastUpdated)"
  if ($mpStatus.AMServiceEnabled) { Write-Host "$PASS Antimalware service: Running" }
  else { Write-Host "$FAIL Antimalware service: Not running" }
} catch {
  Write-Host "$WARN Cannot query Windows Defender: $_"
}

# ── 2. Windows Firewall ────────────────────────────────────────────────────────
Sep "WINDOWS FIREWALL"
try {
  $fwProfiles = Get-NetFirewallProfile -ErrorAction Stop
  foreach ($profile in $fwProfiles) {
    $status = if ($profile.Enabled) { $PASS } else { $FAIL }
    Write-Host "$status Firewall profile '$($profile.Name)': $($profile.Enabled)"
  }
} catch {
  Write-Host "$WARN Cannot query firewall: $_"
}

# ── 3. Windows Updates ─────────────────────────────────────────────────────────
Sep "WINDOWS UPDATES"
try {
  $updateSession = New-Object -ComObject Microsoft.Update.Session
  $updateSearcher = $updateSession.CreateUpdateSearcher()
  $searchResult = $updateSearcher.Search("IsInstalled=0 and Type='Software'")
  $count = $searchResult.Updates.Count
  if ($count -eq 0) { Write-Host "$PASS No pending updates" }
  else {
    Write-Host "$FAIL $count pending updates found"
    $searchResult.Updates | Select-Object -First 10 | ForEach-Object {
      Write-Host "  - $($_.Title)"
    }
  }
} catch {
  Write-Host "$WARN Cannot query Windows Update: $_"
}

# ── 4. Password Policy ────────────────────────────────────────────────────────
Sep "PASSWORD POLICY"
try {
  $policy = net accounts 2>&1
  Write-Host $policy
} catch {
  Write-Host "$WARN Cannot retrieve password policy: $_"
}

# ── 5. Audit Policy ───────────────────────────────────────────────────────────
Sep "AUDIT POLICY"
try {
  auditpol /get /category:* 2>&1 | Select-String -Pattern "Logon|Account|Object|Policy|Privilege|System" | ForEach-Object { Write-Host "  $_" }
} catch {
  Write-Host "$WARN Cannot retrieve audit policy: $_"
}

# ── 6. Local Admin Accounts ───────────────────────────────────────────────────
Sep "LOCAL ADMIN ACCOUNTS"
try {
  $admins = Get-LocalGroupMember -Group "Administrators" -ErrorAction Stop
  Write-Host "$INFO Members of local Administrators group:"
  $admins | ForEach-Object { Write-Host "  $($_.Name) [$($_.ObjectClass)]" }
} catch {
  Write-Host "$WARN Cannot list admins: $_"
}

# Check if Guest account is enabled
try {
  $guest = Get-LocalUser -Name "Guest" -ErrorAction Stop
  if ($guest.Enabled) { Write-Host "$FAIL Guest account is ENABLED" }
  else { Write-Host "$PASS Guest account is disabled" }
} catch { Write-Host "$INFO Cannot check Guest account" }

# ── 7. RDP Configuration ──────────────────────────────────────────────────────
Sep "REMOTE DESKTOP (RDP)"
$rdpKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
try {
  $rdpEnabled = (Get-ItemProperty $rdpKey -Name "fDenyTSConnections" -ErrorAction Stop).fDenyTSConnections
  if ($rdpEnabled -eq 1) { Write-Host "$PASS RDP is disabled" }
  else { Write-Host "$WARN RDP is enabled — verify NLA is enforced" }

  $nlaKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"
  $nla = (Get-ItemProperty $nlaKey -Name "UserAuthentication" -ErrorAction SilentlyContinue).UserAuthentication
  if ($nla -eq 1) { Write-Host "$PASS NLA (Network Level Authentication): Enabled" }
  else { Write-Host "$FAIL NLA: DISABLED — enables pre-auth attacks" }
} catch {
  Write-Host "$WARN Cannot query RDP config: $_"
}

# ── 8. SMBv1 ─────────────────────────────────────────────────────────────────
Sep "SMB PROTOCOL"
try {
  $smb1 = Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -ErrorAction SilentlyContinue
  if ($smb1 -and $smb1.State -eq "Enabled") {
    Write-Host "$FAIL SMBv1 is ENABLED — critical risk (WannaCry/EternalBlue)"
  } else {
    Write-Host "$PASS SMBv1 is disabled"
  }
  $smb2 = (Get-SmbServerConfiguration -ErrorAction Stop).EnableSMB2Protocol
  Write-Host "$INFO SMBv2/3 enabled: $smb2"
} catch {
  Write-Host "$WARN Cannot query SMB config: $_"
}

# ── 9. UAC Settings ───────────────────────────────────────────────────────────
Sep "USER ACCOUNT CONTROL (UAC)"
try {
  $uacKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
  $uac = (Get-ItemProperty $uacKey -ErrorAction Stop)
  $enabled = $uac.EnableLUA
  $consent = $uac.ConsentPromptBehaviorAdmin
  if ($enabled -eq 1) { Write-Host "$PASS UAC: Enabled (EnableLUA=1)" }
  else { Write-Host "$FAIL UAC: DISABLED — critical security risk" }
  Write-Host "$INFO ConsentPromptBehaviorAdmin: $consent (2=prompt for creds, 5=prompt for consent)"
} catch {
  Write-Host "$WARN Cannot query UAC: $_"
}

# ── 10. Running Services ──────────────────────────────────────────────────────
Sep "RUNNING SERVICES"
Get-Service | Where-Object { $_.Status -eq "Running" } | Select-Object Name, DisplayName | Format-Table -AutoSize | Out-String | Write-Host

# ── 11. Open Ports ────────────────────────────────────────────────────────────
Sep "OPEN PORTS"
try {
  netstat -an | Select-String "LISTENING" | Head -30 | ForEach-Object { Write-Host "  $_" }
} catch {
  Get-NetTCPConnection -State Listen 2>/dev/null | Select-Object LocalAddress, LocalPort, OwningProcess | Sort-Object LocalPort | Format-Table | Out-String | Write-Host
}

# ── 12. BitLocker ─────────────────────────────────────────────────────────────
Sep "BITLOCKER"
try {
  $bl = Get-BitLockerVolume -ErrorAction SilentlyContinue
  if ($bl) {
    $bl | ForEach-Object { Write-Host "$INFO Drive $($_.MountPoint): ProtectionStatus=$($_.ProtectionStatus), VolumeStatus=$($_.VolumeStatus)" }
  } else {
    Write-Host "$WARN BitLocker not configured or not available"
  }
} catch {
  Write-Host "$WARN Cannot query BitLocker: $_"
}

# ── 13. PowerShell Execution Policy ──────────────────────────────────────────
Sep "POWERSHELL EXECUTION POLICY"
$policy = Get-ExecutionPolicy -List 2>/dev/null
$policy | ForEach-Object { Write-Host "  Scope: $($_.Scope) -> $($_.ExecutionPolicy)" }

# ── 14. Windows Event Log ────────────────────────────────────────────────────
Sep "EVENT LOG STATUS"
@("Security", "System", "Application") | ForEach-Object {
  try {
    $log = Get-EventLog -LogName $_ -Newest 1 -ErrorAction Stop
    Write-Host "$PASS Event log '$_': active (last entry: $($log.TimeGenerated))"
  } catch {
    Write-Host "$WARN Event log '$_': $($_.Exception.Message)"
  }
}

# ── Summary ───────────────────────────────────────────────────────────────────
Sep "CHECK COMPLETE"
Write-Host "Host      : $env:COMPUTERNAME"
Write-Host "OS        : $((Get-WmiObject Win32_OperatingSystem).Caption)"
Write-Host "Uptime    : $((Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime)"
Write-Host "Timestamp : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
