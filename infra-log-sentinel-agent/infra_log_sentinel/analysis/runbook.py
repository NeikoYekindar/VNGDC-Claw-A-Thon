from __future__ import annotations

from dataclasses import dataclass
import re

from infra_log_sentinel.models import LogEvent


@dataclass(frozen=True)
class DiagnosticCommand:
    phase: str
    command: str
    purpose: str


def recommend_commands(event: LogEvent) -> list[DiagnosticCommand]:
    entities = _extract_entities(event)
    event_type = event.event_type
    domain = event.domain

    if event_type in {"interface_down", "switch_port_errdisable"}:
        interface = entities.get("interface", "<interface>")
        return [
            _cmd("Verify", f"show interface {interface} status", "Confirm admin/oper status and speed/duplex."),
            _cmd("Verify", f"show interface {interface} counters errors", "Check CRC, input errors, drops, and link flaps."),
            _cmd("Investigate", f"show logging | include {interface}", "Review nearby interface state changes."),
            _cmd("Investigate", f"show spanning-tree interface {interface} detail", "Check STP loop or protection events."),
            _cmd("Remediate", f"conf t ; interface {interface} ; shutdown ; no shutdown", "Bounce the port only after cabling/peer validation."),
        ]

    if event_type == "routing_neighbor_down":
        neighbor = entities.get("ip", "<neighbor-ip>")
        return [
            _cmd("Verify", f"show ip bgp summary | include {neighbor}", "Check BGP neighbor state if this is BGP."),
            _cmd("Verify", f"show ip ospf neighbor | include {neighbor}", "Check OSPF adjacency state if this is OSPF."),
            _cmd("Investigate", f"ping {neighbor} source <loopback-or-interface>", "Validate transport reachability from the routing source."),
            _cmd("Investigate", f"traceroute {neighbor}", "Find underlay path or next-hop issue."),
            _cmd("Investigate", f"show logging | include {neighbor}", "Correlate routing and physical events."),
        ]

    if event_type == "firewall_deny":
        src_ip = entities.get("src_ip", "<source-ip>")
        dst_ip = entities.get("dst_ip", "<destination-ip>")
        if domain == "fortigate":
            return [
                _cmd("Verify", f"diagnose firewall iprope lookup 100004 {src_ip} 0 {dst_ip} 443 6", "Check Fortigate policy lookup for the denied flow."),
                _cmd("Investigate", f"diagnose sniffer packet any 'host {src_ip} or host {dst_ip}' 4 50", "Sample packets for the affected source/destination."),
                _cmd("Investigate", f"diagnose sys session filter src {src_ip} ; diagnose sys session list", "Inspect sessions from the source IP."),
                _cmd("Remediate", "review Fortigate policy hit count and approved change request before editing policy", "Avoid policy changes until expected traffic is validated."),
            ]
        return [
            _cmd("Verify", f"show access-list | include {src_ip}|{dst_ip}", "Find the ACL entry matching the flow."),
            _cmd("Investigate", f"packet-tracer input outside tcp {src_ip} 443 {dst_ip} 50432", "Simulate ASA policy decision for the denied traffic."),
            _cmd("Investigate", f"show conn address {src_ip}", "Check whether related sessions exist."),
            _cmd("Remediate", "review firewall change request and application owner approval", "Only adjust ACL after validating expected traffic."),
        ]

    if event_type == "mac_flapping":
        mac = entities.get("mac", "<mac-address>")
        vlan = entities.get("vlan", "<vlan-id>")
        return [
            _cmd("Verify", f"show mac address-table address {mac}", "Identify current learned ports."),
            _cmd("Investigate", f"show spanning-tree vlan {vlan} detail", "Check topology changes and loop symptoms."),
            _cmd("Investigate", "show etherchannel summary", "Validate port-channel consistency."),
            _cmd("Remediate", "trace cabling and NIC teaming configuration", "Fix loop, duplicate patching, or teaming mismatch."),
        ]

    if event_type == "possible_syn_flood":
        return [
            _cmd("Verify", "ss -ant state syn-recv | head -50", "List half-open TCP sessions."),
            _cmd("Investigate", "sudo netstat -s | grep -i syn", "Check SYN retransmit and cookie counters."),
            _cmd("Investigate", "sudo tcpdump -nn 'tcp[tcpflags] & tcp-syn != 0' -c 100", "Sample SYN sources."),
            _cmd("Remediate", "sudo sysctl -w net.ipv4.tcp_syncookies=1", "Ensure SYN cookies are enabled during attack surge."),
        ]

    if event_type == "authentication_failure":
        user = entities.get("user", "<user>")
        src_ip = entities.get("src_ip", entities.get("ip", "<source-ip>"))
        if domain == "wazuh":
            return [
                _cmd("Verify", f"sudo grep -E 'auth_failed|sshd|{src_ip}' /var/ossec/logs/alerts/alerts.log | tail -80", "Check Wazuh alert evidence for SSH authentication failures."),
                _cmd("Investigate", f"sudo grep '{src_ip}' /var/ossec/logs/alerts/alerts.json | tail -20", "Review source IP context and rule metadata."),
                _cmd("Investigate", f"sudo grep -R '{user}' /var/ossec/logs/alerts/ -n | tail -50", "Correlate repeated failures for the same account."),
                _cmd("Investigate", f"sudo grep '{src_ip}' /var/log/auth.log | tail -50", "Validate raw SSH failures on the affected Linux host when available."),
                _cmd("Remediate", f"block source {src_ip} at firewall/WAF after confirming abuse", "Contain brute-force traffic only after validating the source and business impact."),
            ]
        if domain == "network":
            return [
                _cmd("Verify", f"show logging | include {user}|{src_ip}", "Find related VPN or device authentication events."),
                _cmd("Investigate", f"show vpn-sessiondb anyconnect filter name {user}", "Check active or failed VPN sessions for the user."),
                _cmd("Investigate", f"show aaa-server | include {src_ip}|FAILED|ERROR", "Check AAA/RADIUS/TACACS health."),
                _cmd("Remediate", f"block source {src_ip} or reset user session after validation", "Contain abuse only after confirming the login source."),
            ]
        if domain == "windows":
            return [
                _cmd("Verify", "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625; StartTime=(Get-Date).AddHours(-1)} | Select-Object -First 20", "Review failed logons."),
                _cmd("Investigate", f"Search-ADAccount -LockedOut | Where-Object {{$_.SamAccountName -like '*{user}*'}}", "Check lockout state."),
                _cmd("Investigate", f"Get-ADUser {user} -Properties LockedOut,BadLogonCount,LastBadPasswordAttempt", "Inspect account status."),
                _cmd("Remediate", f"Unlock-ADAccount -Identity {user}", "Unlock only after validating the login source."),
            ]
        return [
            _cmd("Verify", f"sudo grep '{src_ip}' /var/log/auth.log | tail -50", "Find related SSH/auth events."),
            _cmd("Investigate", f"sudo lastb -a | grep '{src_ip}' | head", "Review failed login history."),
            _cmd("Investigate", f"sudo faillock --user {user}", "Check lockout or brute-force counters."),
            _cmd("Remediate", f"sudo ufw deny from {src_ip}", "Block source only after confirming abuse."),
        ]

    if event_type == "capacity_warning":
        datastore = entities.get("datastore", "<datastore-name>")
        if domain == "vmware":
            return [
                _cmd("Verify", f"Get-Datastore {datastore} | Select Name,FreeSpaceGB,CapacityGB", "Check datastore free space."),
                _cmd("Investigate", f"Get-VM -Datastore {datastore} | Select Name,UsedSpaceGB,ProvisionedSpaceGB", "Find top VM consumers."),
                _cmd("Investigate", f"Get-Snapshot -VM (Get-VM -Datastore {datastore}) | Select VM,Name,SizeGB,Created", "Locate old snapshots."),
                _cmd("Remediate", "remove stale snapshots or expand datastore capacity", "Free space or add capacity before exhaustion."),
            ]
        return [
            _cmd("Verify", "df -h", "Check filesystem usage."),
            _cmd("Investigate", "sudo du -xh / | sort -h | tail -20", "Find largest directories."),
            _cmd("Investigate", "sudo journalctl --disk-usage", "Check journal space usage."),
            _cmd("Remediate", "sudo journalctl --vacuum-time=14d", "Trim old journal logs when approved."),
        ]

    if event_type == "dns_timeout":
        domain_name = entities.get("domain", "app.example.local")
        return [
            _cmd("Verify", "systemctl status named systemd-resolved --no-pager", "Check DNS resolver service health."),
            _cmd("Investigate", "journalctl -u named -u systemd-resolved --since '1 hour ago' --no-pager | tail -120", "Review resolver errors around the impact window."),
            _cmd("Investigate", f"dig @{event.source or '127.0.0.1'} {domain_name} +time=2 +tries=1", "Measure DNS response from the affected resolver."),
            _cmd("Investigate", "rndc status && rndc recursing", "Check BIND recursion load when rndc is available."),
            _cmd("Remediate", "reduce DNS debug logging or fail over clients to secondary resolver after validation", "Lower resolver load without masking the root cause."),
        ]

    if event_type == "application_timeout":
        return [
            _cmd("Verify", "curl -vk --max-time 5 https://app.example.local/health", "Check application reachability from a client path."),
            _cmd("Investigate", "journalctl -u nginx --since '1 hour ago' --no-pager | tail -120", "Review web proxy timeout logs."),
            _cmd("Investigate", "ss -antp | grep -E ':80|:443' | head -80", "Inspect active web/backend connections."),
            _cmd("Investigate", "dig app.example.local +time=2 +tries=1", "Validate whether DNS resolution contributes to the timeout."),
            _cmd("Remediate", "restart or fail over the impacted app tier only after dependency health is confirmed", "Avoid restarting the symptom tier before checking DNS/network dependencies."),
        ]

    if event_type == "service_failure":
        service = entities.get("service", "<service-name>")
        if domain == "windows":
            return [
                _cmd("Verify", f"Get-Service {service}", "Check service status."),
                _cmd("Investigate", "Get-WinEvent -FilterHashtable @{LogName='System'; Id=7031; StartTime=(Get-Date).AddHours(-2)}", "Review recent service crash events."),
                _cmd("Investigate", f"Get-EventLog -LogName Application -Newest 50 | Where-Object {{$_.Message -like '*{service}*'}}", "Correlate application errors."),
                _cmd("Remediate", f"Restart-Service {service}", "Restart after confirming dependencies and change window."),
            ]
        return [
            _cmd("Verify", f"systemctl status {service}", "Check service status and exit code."),
            _cmd("Investigate", f"journalctl -u {service} --since '1 hour ago' -n 100", "Review service logs before restart."),
            _cmd("Investigate", "systemctl list-dependencies --failed", "Check failed dependencies."),
            _cmd("Remediate", f"sudo systemctl restart {service}", "Restart after root cause review."),
        ]

    if event_type == "storage_path_issue":
        disk = entities.get("disk", "<disk-or-naa-id>")
        if domain == "windows":
            return [
                _cmd("Verify", "Get-WinEvent -FilterHashtable @{LogName='System'; Id=51; StartTime=(Get-Date).AddHours(-2)}", "Review disk paging operation warnings."),
                _cmd("Investigate", "Get-Disk | Select Number,FriendlyName,HealthStatus,OperationalStatus", "Check disk health status."),
                _cmd("Investigate", "Get-PhysicalDisk | Select FriendlyName,HealthStatus,OperationalStatus,MediaType", "Inspect physical disk health."),
                _cmd("Remediate", "schedule disk diagnostics and storage path validation", "Avoid disruptive repair before backup and owner approval."),
            ]
        if domain == "vmware":
            return [
                _cmd("Verify", f"esxcli storage core path list -d {disk}", "Check ESXi storage path states."),
                _cmd("Investigate", f"esxcli storage nmp device list -d {disk}", "Inspect multipathing policy and APD/PDL state."),
                _cmd("Investigate", "esxcfg-mpath -b", "List all paths and runtime status."),
                _cmd("Remediate", "rescan storage adapters after SAN/network validation", "Rescan only after confirming storage fabric health."),
            ]
        return [
            _cmd("Verify", "lsblk -o NAME,SIZE,MODEL,SERIAL,STATE", "Map Linux block device to hardware."),
            _cmd("Investigate", f"dmesg -T | egrep '{disk}|blk_update|medium error' | tail -50", "Review kernel disk errors."),
            _cmd("Investigate", f"sudo smartctl -a /dev/{disk}", "Check SMART health for the disk."),
            _cmd("Remediate", f"sudo multipath -ll /dev/{disk}", "Validate multipath before failover or replacement."),
        ]

    if event_type in {"host_failure", "vm_unexpected_poweroff"}:
        host = entities.get("host", "<esxi-host>")
        vm = entities.get("vm", "<vm-name>")
        return [
            _cmd("Verify", f"Get-VMHost {host} | Select Name,ConnectionState,PowerState", "Check host connectivity and power state."),
            _cmd("Investigate", f"Test-Connection {host} -Count 4", "Check management network reachability."),
            _cmd("Investigate", f"Get-VIEvent -Entity (Get-VMHost {host}) -MaxSamples 50", "Review recent vCenter host events."),
            _cmd("Investigate", f"Get-VM {vm} | Select Name,PowerState,VMHost", "Check affected VM placement and power state."),
        ]

    if event_type == "resource_pressure":
        if domain == "network":
            return [
                _cmd("Verify", "show processes cpu sorted 5sec", "Identify high CPU processes."),
                _cmd("Verify", "show memory statistics", "Check memory pressure."),
                _cmd("Investigate", "show platform resources", "Review hardware forwarding/control-plane usage."),
                _cmd("Remediate", "shift traffic or rate-limit abusive flows after validation", "Reduce pressure while root cause is investigated."),
            ]
        if domain == "fortigate":
            return [
                _cmd("Verify", "get system performance status", "Check Fortigate CPU, memory, session, and uptime counters."),
                _cmd("Verify", "diagnose sys session stat", "Validate current session table pressure."),
                _cmd("Investigate", "diagnose sys top 5 20", "Identify high CPU processes."),
                _cmd("Investigate", "diagnose firewall iprope stats | head -80", "Check policy/session processing pressure."),
                _cmd("Remediate", "rate-limit or narrow the abnormal source/policy after confirming business impact", "Reduce firewall pressure without cutting legitimate traffic."),
            ]
        if domain == "vmware":
            host = event.source or entities.get("host", "<esxi-host>")
            return [
                _cmd("Verify", f"Get-VMHost {host} | Select Name,ConnectionState,PowerState,MemoryUsageGB,MemoryTotalGB", "Check ESXi host memory pressure from vCenter."),
                _cmd("Investigate", f"Get-Stat -Entity (Get-VMHost {host}) -Stat mem.usage.average -Start (Get-Date).AddHours(-2)", "Review memory usage trend over the last two hours."),
                _cmd("Investigate", f"Get-VM -Location (Get-VMHost {host}) | Sort-Object MemoryGB -Descending | Select -First 10 Name,PowerState,MemoryGB", "Find the largest VM memory consumers on the host."),
                _cmd("Investigate", f"Get-Stat -Entity (Get-VMHost {host}) -Stat mem.vmmemctl.average,mem.swapused.average -Start (Get-Date).AddHours(-2)", "Check ballooning and swapping symptoms."),
                _cmd("Remediate", "migrate high-memory VMs, rebalance cluster load, or add host memory capacity after validation", "Reduce pressure without disrupting workloads."),
            ]
        return [
            _cmd("Verify", "top -o %CPU", "Identify top CPU consumers."),
            _cmd("Verify", "free -m", "Check memory pressure."),
            _cmd("Investigate", "vmstat 1 5", "Check run queue, swap, and IO wait."),
            _cmd("Remediate", "scale service or restart faulty process after validation", "Reduce resource pressure safely."),
        ]

    if event_type == "power_supply_failure":
        return [
            _cmd("Verify", "show environment power", "Check PSU state and redundancy."),
            _cmd("Verify", "show inventory | include Power|PID|SN", "Identify failed PSU part and serial."),
            _cmd("Investigate", "show logging | include PS_FAIL|Power supply", "Review nearby hardware events."),
            _cmd("Investigate", "show platform", "Check chassis, module, and environmental state."),
            _cmd("Remediate", "replace or reseat failed PSU after confirming redundant power", "Restore hardware redundancy safely."),
        ]

    if event_type == "vm_migration_failed":
        vm = entities.get("vm", "<vm-name>")
        return [
            _cmd("Verify", f"Get-VM {vm} | Select Name,PowerState,VMHost", "Check VM current placement and power state."),
            _cmd("Investigate", "Get-VMHostNetworkAdapter -VMKernel | Where-Object {$_.VMotionEnabled -eq $true}", "Validate vMotion vmkernel adapters."),
            _cmd("Investigate", f"Get-VIEvent -Entity (Get-VM {vm}) -MaxSamples 50", "Review failed migration task details."),
            _cmd("Investigate", "Test-VMHostNetworkAdapter -VMHost <source-host> -Destination <dest-vmotion-ip>", "Validate vMotion network reachability."),
            _cmd("Remediate", "retry migration after fixing vMotion network/storage/host compatibility", "Avoid repeated vMotion failures during maintenance."),
        ]

    if event_type == "application_crash":
        return [
            _cmd("Verify", "Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=(Get-Date).AddHours(-2)}", "Review application crash events."),
            _cmd("Investigate", "Get-ChildItem C:\\ProgramData\\Microsoft\\Windows\\WER\\ReportArchive | Sort-Object LastWriteTime -Descending | Select-Object -First 10", "Find Windows Error Reporting crash dumps."),
            _cmd("Investigate", "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10", "Check recent patch changes."),
            _cmd("Remediate", "restart affected application service after dump/log capture", "Restore service after preserving evidence."),
        ]

    if event_type == "unexpected_shutdown":
        return [
            _cmd("Verify", "Get-WinEvent -FilterHashtable @{LogName='System'; Id=6008; StartTime=(Get-Date).AddHours(-24)}", "Review unexpected shutdown events."),
            _cmd("Investigate", "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1074,6006,6008; StartTime=(Get-Date).AddHours(-24)}", "Correlate power and shutdown events."),
            _cmd("Investigate", "Get-EventLog -LogName System -Source Microsoft-Windows-Kernel-Power -Newest 20", "Check kernel power events."),
            _cmd("Remediate", "validate UPS/iLO/iDRAC/hypervisor reset history before closing incident", "Confirm whether shutdown was infrastructure or OS initiated."),
        ]

    return [
        _cmd("Verify", f"grep -n '{_safe_grep(event.event_type)}' <log-file> | tail -20", "Find surrounding log context."),
        _cmd("Investigate", f"grep -n '{_safe_grep(event.source)}' <log-file> | tail -50", "Correlate nearby events from the same source."),
        _cmd("Remediate", "follow the service/domain runbook for the affected component", "Use approved operational procedure."),
    ]


def commands_as_text(event: LogEvent, limit: int = 4) -> str:
    return "\n".join(
        f"- {item.phase}: `{item.command}` - {item.purpose}"
        for item in recommend_commands(event)[:limit]
    )


def _cmd(phase: str, command: str, purpose: str) -> DiagnosticCommand:
    return DiagnosticCommand(phase=phase, command=command, purpose=purpose)


def _extract_entities(event: LogEvent) -> dict[str, str]:
    text = f"{event.raw} {event.message}"
    entities: dict[str, str] = {}

    _set_if_match(entities, "interface", text, r"Interface\s+([A-Za-z][\w./-]+)")
    _set_if_match(entities, "interface", text, r"\bon\s+([A-Za-z]{1,4}\d+(?:/\d+){1,3})\b")
    _set_if_match(entities, "interface", text, r"\b([A-Za-z]+GigabitEthernet\d+(?:/\d+){1,3})\b")
    _set_if_match(entities, "ip", text, r"\b(?:neighbor|Nbr)\s+(\d{1,3}(?:\.\d{1,3}){3})\b")
    _set_if_match(entities, "src_ip", text, r"\bsrc\s+\w+:(\d{1,3}(?:\.\d{1,3}){3})")
    _set_if_match(entities, "dst_ip", text, r"\bdst\s+\w+:(\d{1,3}(?:\.\d{1,3}){3})")
    _set_if_match(entities, "src_ip", text, r"\bfrom\s+(\d{1,3}(?:\.\d{1,3}){3})\b")
    _set_if_match(entities, "user", text, r"\bUser=([^\s]+)")
    _set_if_match(entities, "user", text, r"\buser\s+['\"]?([^'\"\s]+)")
    _set_if_match(entities, "service", text, r"\b([A-Za-z0-9_.-]+\.service)\b")
    _set_if_match(entities, "service", text, r"\bThe\s+([A-Za-z0-9_.-]+)\s+service\b")
    _set_if_match(entities, "disk", text, r"\bdev\s+([A-Za-z0-9_/-]+)\b")
    _set_if_match(entities, "disk", text, r"\bdevice\s+(naa\.[A-Za-z0-9.]+)\b")
    _set_if_match(entities, "datastore", text, r"\bDatastore=([^\s]+)")
    _set_if_match(entities, "host", text, r"\bHost=([^\s]+)")
    _set_if_match(entities, "vm", text, r"\bVM=([^\s]+)")
    _set_if_match(entities, "mac", text, r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
    _set_if_match(entities, "vlan", text, r"\bvlan\s+(\d+)\b")

    if event.domain == "windows" and "service" not in entities and "SQLAgent" in text:
        entities["service"] = "SQLAgent"

    return entities


def _set_if_match(entities: dict[str, str], key: str, text: str, pattern: str) -> None:
    if key in entities:
        return
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match:
        entities[key] = match.group(1)


def _safe_grep(value: str) -> str:
    return value.replace("'", "").replace('"', "")[:80]
