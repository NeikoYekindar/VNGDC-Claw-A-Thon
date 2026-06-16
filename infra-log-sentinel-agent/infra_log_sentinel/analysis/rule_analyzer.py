from __future__ import annotations


CISCO_SEVERITY = {
    "0": "critical",
    "1": "critical",
    "2": "critical",
    "3": "error",
    "4": "warning",
    "5": "info",
    "6": "info",
    "7": "info",
}


def classify_severity(raw_text: str, domain: str) -> str:
    text = raw_text.lower()

    windows_level = _extract_windows_level(text)
    if windows_level:
        return windows_level

    if any(
        keyword in text
        for keyword in [
            "severity=critical",
            "level=critical",
            "critical -",
            "critical",
            "alert",
            "all paths down",
            "host failure",
            "host connection and power state lost",
            "power supply 2 failed",
            "service terminated unexpectedly",
            "critical medium error",
            "dead timer expired",
            "bgp notification sent",
            "cluster_status=red",
            "instancedown",
            "host down",
            "malware detected",
        ]
    ):
        return "critical"

    cisco_level = _extract_cisco_level(raw_text)
    if cisco_level:
        return cisco_level

    if any(keyword in text for keyword in ["failed password", "auth_failed"]):
        return "warning"

    if any(
        keyword in text
        for keyword in [
            "severity=error",
            "level=error",
            "error -",
            "error",
            "failed",
            "failure",
            "faulting application",
            "unexpected",
            "aborted connection",
            "timed out",
            "exit-code",
            "login failed",
            "scrape failed",
            "snmp poller timeout",
            "pipeline blocked",
        ]
    ):
        return "error"

    if any(
        keyword in text
        for keyword in [
            "severity=warning",
            "level=warning",
            "level=warn",
            "warning -",
            "warning",
            "deny",
            "failed password",
            "locked out",
            "near capacity",
            "usage is high",
            "flapping",
            "memory usage is high",
            "path state changed to dead",
            "possible syn flooding",
            "cluster_status=yellow",
            "threshold exceeded",
        ]
    ):
        return "warning"

    return "info"


def detect_event_type(raw_text: str, domain: str) -> str:
    text = raw_text.lower()
    if "interface" in text and "down" in text:
        return "interface_down"
    if ("bgp" in text or "ospf" in text) and "down" in text:
        return "routing_neighbor_down"
    if any(
        keyword in text
        for keyword in ["failed password", "auth_failed", "failed to log on", "login failed"]
    ):
        return "authentication_failure"
    if any(keyword in text for keyword in ["disk is at or near capacity", "datastore usage", "traffic threshold exceeded"]):
        return "capacity_warning"
    if "cluster_status=red" in text:
        return "search_cluster_red"
    if "pipeline blocked" in text:
        return "log_pipeline_blocked"
    if "file integrity" in text or "checksum changed" in text:
        return "file_integrity_change"
    if "malware" in text or "virus" in text or "ips signature" in text:
        return "security_threat_detected"
    if "vpn tunnel" in text and "down" in text:
        return "vpn_tunnel_down"
    if "ap " in text and "disconnected" in text:
        return "wireless_ap_down"
    if "gateway cluster failover" in text:
        return "wireless_gateway_failover"
    if "packet loss" in text:
        return "network_packet_loss"
    if "snmp poller timeout" in text or "scrape failed" in text or "targetscrapefailed" in text:
        return "monitoring_polling_failure"
    if "datasource" in text and "failed" in text:
        return "monitoring_datasource_failure"
    if "instancedown" in text or "target has been down" in text or "service is down" in text:
        return "service_failure"
    if any(keyword in text for keyword in ["service terminated", "main process exited", "failed with result"]):
        return "service_failure"
    if "dns query timeout" in text:
        return "dns_timeout"
    if "upstream timed out" in text or "connection timed out" in text:
        return "application_timeout"
    if any(
        keyword in text
        for keyword in ["host connection and power state lost", "host failure", "host down", "dashostfailedevent"]
    ):
        return "host_failure"
    if any(
        keyword in text
        for keyword in ["all paths down", "medium error", "paging operation", "path state changed to dead"]
    ):
        return "storage_path_issue"
    if any(keyword in text for keyword in ["cpu utilization", "memory usage", "memory pressure", "out of memory"]):
        return "resource_pressure"
    if "power supply" in text or "ps_fail" in text:
        return "power_supply_failure"
    if "deny tcp" in text:
        return "firewall_deny"
    if "err-disable" in text or "loopback error" in text:
        return "switch_port_errdisable"
    if "hostflapping" in text or "flapping" in text:
        return "mac_flapping"
    if "possible syn flooding" in text:
        return "possible_syn_flood"
    if "snapshot created" in text:
        return "vm_snapshot_created"
    if "powered off unexpectedly" in text:
        return "vm_unexpected_poweroff"
    if "vmotion migration failed" in text or "failed migrate" in text:
        return "vm_migration_failed"
    if "faulting application" in text:
        return "application_crash"
    if "previous system shutdown was unexpected" in text:
        return "unexpected_shutdown"
    if "powered on" in text:
        return "vm_powered_on"
    return f"{domain}_general_event"


def explain_event(event_type: str, severity: str, source: str) -> tuple[str, str, str]:
    guidance = {
        "interface_down": (
            "Likely physical link, SFP/cable, peer shutdown, or recent network change.",
            "Traffic through the affected uplink or access segment may be interrupted.",
            "Check interface status, optical levels, peer device logs, cabling, and recent change records.",
        ),
        "routing_neighbor_down": (
            "Routing adjacency lost because of transport failure, timer expiry, policy mismatch, or peer issue.",
            "Route convergence or reachability to dependent prefixes may be affected.",
            "Verify underlay connectivity, routing timers, neighbor state, recent config changes, and route table.",
        ),
        "authentication_failure": (
            "Invalid credential, expired password, service account issue, or possible brute force attempt.",
            "Repeated failures may lock accounts or indicate unauthorized access attempts.",
            "Check source IP, account status, password rotation, and related security events.",
        ),
        "capacity_warning": (
            "Disk or datastore usage crossed the warning threshold.",
            "Services may fail if free space continues to decrease.",
            "Clean up old files, validate backup retention, expand capacity, and monitor growth trend.",
        ),
        "service_failure": (
            "A critical service or process exited unexpectedly.",
            "Application availability or scheduled jobs may be degraded.",
            "Check service logs, recent deployments, dependency health, and restart policy.",
        ),
        "vpn_tunnel_down": (
            "VPN tunnel went down due to peer, DPD, routing, policy, or internet transport issue.",
            "Branch or partner connectivity through the tunnel may be interrupted.",
            "Check IPsec phase status, peer reachability, DPD timers, firewall policy, and recent changes.",
        ),
        "wireless_ap_down": (
            "Wireless access point lost controller connectivity or stopped heartbeating.",
            "Users attached to the AP may lose Wi-Fi service or roam to weaker coverage.",
            "Check AP power, switch port, controller reachability, radio health, and AP event history.",
        ),
        "wireless_gateway_failover": (
            "Wireless gateway cluster performed failover because a peer became unreachable.",
            "Wireless client sessions may be interrupted during convergence.",
            "Check cluster peer heartbeat, uplink health, controller logs, and failover reason.",
        ),
        "monitoring_polling_failure": (
            "Monitoring system could not scrape or poll the target in time.",
            "Alert visibility may be degraded, or the monitored target may be unreachable.",
            "Check target reachability, SNMP/exporter health, timeout settings, and monitoring server load.",
        ),
        "monitoring_datasource_failure": (
            "Dashboard or alerting layer cannot query its monitoring datasource.",
            "Dashboards and alerts may be stale or unavailable.",
            "Check datasource health, credentials, network path, query timeout, and backend metrics.",
        ),
        "search_cluster_red": (
            "Elasticsearch cluster is red because primary shards are unavailable.",
            "Search, indexing, and log analytics may be partially or fully unavailable.",
            "Check shard allocation, disk watermarks, node health, cluster routing, and recent index changes.",
        ),
        "log_pipeline_blocked": (
            "Log ingestion pipeline is blocked or under backpressure.",
            "Log delivery may lag, causing delayed alerting and incomplete RCA evidence.",
            "Check Logstash pipeline workers, queue depth, Elasticsearch ingest capacity, and failed outputs.",
        ),
        "security_threat_detected": (
            "Security control detected malware, IPS, or antivirus activity.",
            "Endpoint or network segment may be at risk until containment is confirmed.",
            "Validate scope, isolate affected endpoint if needed, collect indicators, and review related alerts.",
        ),
        "file_integrity_change": (
            "File integrity monitoring detected an unexpected file change.",
            "Configuration drift or unauthorized modification may affect security posture.",
            "Validate change ticket, compare file diff, check actor/process, and inspect nearby auth events.",
        ),
        "network_packet_loss": (
            "Monitoring detected packet loss on a host, link, or network path.",
            "Applications may experience latency, retries, or intermittent failures.",
            "Check interface counters, path latency, congestion, routing changes, and device health.",
        ),
        "dns_timeout": (
            "DNS service or zone response timed out, often after DNS configuration, reload, or dependency issue.",
            "Applications depending on name resolution may see connection failures or delayed responses.",
            "Check DNS service health, zone reload logs, resolver latency, and recent DNS changes.",
        ),
        "application_timeout": (
            "Application dependency timed out while waiting for an upstream response.",
            "End users may see slow requests, failed logins, or partial service outage.",
            "Check upstream health, DNS resolution, network path, and application dependency metrics.",
        ),
        "host_failure": (
            "Hypervisor or host connectivity was lost.",
            "VM workloads may be restarted by HA or become unavailable.",
            "Check host management network, power, storage connectivity, and vCenter alarms.",
        ),
        "storage_path_issue": (
            "Storage path, disk, or block device reported errors.",
            "VMs or applications may experience latency, IO errors, or outages.",
            "Check storage fabric, multipath state, datastore health, disk SMART status, and recent storage changes.",
        ),
        "resource_pressure": (
            "CPU or memory usage is above normal operating range.",
            "Performance degradation or packet drops may occur under sustained pressure.",
            "Identify top consumers, validate capacity, and consider scaling or traffic redistribution.",
        ),
        "firewall_deny": (
            "Firewall policy denied traffic matching the logged flow.",
            "Application connectivity may fail if the deny is unexpected.",
            "Validate source/destination, expected policy, recent ACL changes, and application owner request.",
        ),
        "switch_port_errdisable": (
            "Switch port was disabled due to loopback or protection mechanism.",
            "Connected endpoint or downstream switch may lose connectivity.",
            "Check cabling loop, endpoint behavior, STP, port-security, and errdisable recovery settings.",
        ),
        "mac_flapping": (
            "MAC address is moving between ports, often caused by loop, teaming issue, or mispatch.",
            "Layer 2 instability can cause intermittent connectivity.",
            "Check physical topology, port-channel configuration, STP state, and endpoint NIC teaming.",
        ),
        "possible_syn_flood": (
            "High volume of TCP SYN requests may indicate attack or connection surge.",
            "Service latency or connection drops may occur.",
            "Check traffic source, firewall/WAF counters, SYN cookies, and application load.",
        ),
        "power_supply_failure": (
            "Network device reported a power supply failure or removal.",
            "Device redundancy may be reduced; a second power event can cause outage.",
            "Check PSU status, input power, redundancy state, and hardware replacement workflow.",
        ),
        "vm_unexpected_poweroff": (
            "VM powered off unexpectedly outside a normal maintenance window.",
            "Application hosted on the VM may be unavailable.",
            "Check vCenter tasks/events, guest OS logs, HA activity, and owner change records.",
        ),
        "vm_migration_failed": (
            "vMotion failed because of network timeout, host issue, storage latency, or compatibility mismatch.",
            "Maintenance or workload evacuation may be blocked.",
            "Check vMotion vmkernel connectivity, host compatibility, datastore reachability, and recent tasks.",
        ),
        "application_crash": (
            "Application process crashed because of code defect, dependency issue, memory fault, or bad input.",
            "Application availability or background processing may be degraded.",
            "Review application event logs, dump files, recent deployments, and restart policy.",
        ),
        "unexpected_shutdown": (
            "System shutdown was not graceful; possible power, OS crash, or manual reset event.",
            "Applications on the server may have experienced interruption or data risk.",
            "Check system event logs, hardware management logs, UPS/power events, and application consistency.",
        ),
    }
    default = (
        "The event should be reviewed with surrounding logs for context.",
        "Impact depends on the affected component and service dependency.",
        "Correlate with nearby events, validate current health, and follow the relevant runbook.",
    )
    return guidance.get(event_type, default)


def _extract_windows_level(text: str) -> str | None:
    if "level=critical" in text:
        return "critical"
    if "level=error" in text:
        return "error"
    if "level=warning" in text:
        return "warning"
    if "level=information" in text:
        return "info"
    return None


def _extract_cisco_level(raw_text: str) -> str | None:
    marker = raw_text.split("%", 1)
    if len(marker) < 2:
        return None
    parts = marker[1].split("-", 2)
    if len(parts) < 2:
        return None
    return CISCO_SEVERITY.get(parts[1])
