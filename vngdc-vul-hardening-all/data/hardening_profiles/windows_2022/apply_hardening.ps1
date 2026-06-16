# Windows Server 2022 hardening commands configured for this agent baseline.
# Review before running on production. The agent does not execute this file
# automatically during checks.

Set-MpPreference -DisableRealtimeMonitoring $false
Set-MpPreference -DisableBehaviorMonitoring $false
Set-MpPreference -DisableBlockAtFirstSeen $false
Set-MpPreference -PUAProtection Enabled

Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True

net accounts /maxpwage:90 /minpwage:1 /minpwlen:14 /uniquepw:24

auditpol /set /category:* /success:enable /failure:enable

Disable-LocalUser -Name Guest

# Keep RDP disabled unless operationally required. If enabled, enforce NLA.
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 1
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name UserAuthentication -Value 1

Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart
Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force

Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name EnableLUA -Value 1
Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force

wevtutil sl Security /ms:134217728
wevtutil sl System /ms:67108864
wevtutil sl Application /ms:67108864
