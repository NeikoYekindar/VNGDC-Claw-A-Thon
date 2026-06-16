from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any


BASE_TIME = datetime(2026, 6, 14, 9, 0, tzinfo=timezone.utc)


SCENARIOS: dict[str, dict[str, Any]] = {
    "broadcast_loop": {
        "title": "Broadcast loop on Aruba access switch",
        "severity": "critical",
        "alert_source": "fortigate-fw01",
        "alert_message": "Firewall CPU high and session table spike observed for VLAN 20 users.",
        "root_cause": "Broadcast loop on Aruba switch port 1/1/48 after a recent port enable change.",
        "impact": "Internet access is slow for VLAN 20 and firewall CPU is saturated.",
        "change": "Enabled Aruba access switch port 1/1/48 for a temporary uplink.",
        "logs": [
            ("aruba-access-01", "Aruba", "STP topology change detected on VLAN 20 after port 1/1/48 transitioned forwarding."),
            ("core-sw01", "Juniper", "MAC flapping detected between ae1 and ge-0/0/24 for multiple VLAN 20 clients."),
            ("fortigate-fw01", "Fortigate", "Session count exceeded baseline; CPU entered conserve warning threshold."),
            ("elk", "ELK", "Unrelated application warning from app01 retrying backend request."),
        ],
        "metrics": [
            ("aruba-access-01", "broadcast_pps", 184000, 1200, "pps"),
            ("core-sw01", "mac_move_rate", 320, 2, "moves/min"),
            ("fortigate-fw01", "cpu_percent", 94, 35, "%"),
            ("fortigate-fw01", "session_count", 780000, 160000, "sessions"),
        ],
        "keywords": ("broadcast", "stp", "mac flapping", "port 1/1/48", "session"),
        "verification": (
            "Check STP state and loop guard on Aruba port 1/1/48.",
            "Shut or isolate port 1/1/48 in a controlled change window and confirm broadcast pps drops.",
            "Confirm MAC move rate returns to baseline on core-sw01.",
        ),
        "actions": (
            "Disable or quarantine Aruba port 1/1/48 after verification.",
            "Enable loop guard/BPDU guard on access ports.",
            "Review temporary uplink change approval and cabling map.",
        ),
    },
    "mac_flapping": {
        "title": "MAC flapping on core switch",
        "severity": "error",
        "alert_source": "core-sw01",
        "alert_message": "MAC move rate is above threshold on VLAN 30.",
        "root_cause": "Layer-2 path instability causing MAC flapping between core and access links.",
        "impact": "Intermittent packet loss for VLAN 30 clients.",
        "change": "Added a redundant access uplink without confirming LACP/STP design.",
        "logs": [
            ("core-sw01", "Juniper", "MAC address 00:50:56:aa:30:01 moved repeatedly between ae2 and ge-0/0/18."),
            ("aruba-access-02", "Aruba", "Uplink 1/1/24 changed state to forwarding outside configured LACP bundle."),
            ("wazuh", "Wazuh", "Unrelated user login succeeded on linux-api02."),
        ],
        "metrics": [
            ("core-sw01", "mac_move_rate", 210, 3, "moves/min"),
            ("core-sw01", "packet_loss", 7.5, 0.2, "%"),
        ],
        "keywords": ("mac moved", "mac flapping", "lacp", "forwarding", "packet loss"),
        "verification": (
            "Verify LACP membership and STP role for ae2 and ge-0/0/18.",
            "Trace the flapping MAC to the access switch and endpoint segment.",
        ),
        "actions": (
            "Remove the stray uplink from forwarding path after validation.",
            "Standardize LACP/STP configuration on redundant uplinks.",
        ),
    },
    "fortigate_session_spike": {
        "title": "Fortigate session spike",
        "severity": "critical",
        "alert_source": "fortigate-fw01",
        "alert_message": "Fortigate session count and CPU are above critical threshold.",
        "root_cause": "Abnormal east-west scan traffic created a firewall session spike.",
        "impact": "Firewall latency increased and new sessions are delayed.",
        "change": "Temporary allow policy added for subnet 10.20.0.0/16 to server zone.",
        "logs": [
            ("fortigate-fw01", "Fortigate", "Policy 182 matched unusually high number of short-lived sessions."),
            ("elk", "ELK", "Connection attempts from 10.20.8.14 to many server ports increased sharply."),
            ("core-sw01", "Juniper", "No interface errors detected on firewall uplink."),
        ],
        "metrics": [
            ("fortigate-fw01", "session_count", 920000, 180000, "sessions"),
            ("fortigate-fw01", "cpu_percent", 97, 38, "%"),
            ("fortigate-fw01", "new_sessions_per_second", 22000, 2500, "sessions/s"),
        ],
        "keywords": ("policy 182", "short-lived sessions", "connection attempts", "new_sessions"),
        "verification": (
            "Review top session sources and destination ports on Fortigate.",
            "Validate whether policy 182 should allow this traffic pattern.",
        ),
        "actions": (
            "Rate-limit or block the abnormal source after validation.",
            "Rollback or narrow the temporary allow policy.",
        ),
    },
    "dns_timeout": {
        "title": "DNS server timeout",
        "severity": "error",
        "alert_source": "app-monitor",
        "alert_message": "Application DNS lookups are timing out.",
        "root_cause": "Primary DNS server is timing out due to resolver process saturation.",
        "impact": "Applications relying on name resolution show intermittent failures.",
        "change": "DNS logging level changed to debug on dns01.",
        "logs": [
            ("dns01", "Linux", "named query worker queue saturated; recursive lookup timeout observed."),
            ("app01", "ELK", "getaddrinfo timeout for api.internal.example.local."),
            ("windows-dc01", "Windows", "No AD replication error detected."),
        ],
        "metrics": [
            ("dns01", "dns_query_latency_ms", 4200, 45, "ms"),
            ("dns01", "cpu_percent", 88, 30, "%"),
            ("app01", "dns_error_rate", 19, 0.1, "%"),
        ],
        "keywords": ("dns", "named", "query", "timeout", "latency"),
        "verification": (
            "Check named worker queue and debug logging overhead on dns01.",
            "Query secondary DNS and compare latency.",
        ),
        "actions": (
            "Reduce DNS debug logging after validation.",
            "Fail traffic over to secondary resolver if latency remains high.",
        ),
    },
    "linux_disk_full": {
        "title": "Linux server disk full",
        "severity": "critical",
        "alert_source": "linux-api02",
        "alert_message": "/var is above 98 percent disk usage.",
        "root_cause": "Application log rotation failure filled /var on linux-api02.",
        "impact": "API service cannot write logs and may fail requests.",
        "change": "Application debug logging enabled during troubleshooting.",
        "logs": [
            ("linux-api02", "Linux", "No space left on device while writing /var/log/app/api.log."),
            ("linux-api02", "Linux", "logrotate skipped api.log because file handle remained open."),
            ("elk", "ELK", "Unrelated nginx access log volume normal on web01."),
        ],
        "metrics": [
            ("linux-api02", "disk_used_percent", 99, 62, "%"),
            ("linux-api02", "inode_used_percent", 71, 55, "%"),
        ],
        "keywords": ("no space", "logrotate", "debug logging", "disk"),
        "verification": (
            "Run du on /var and confirm api.log growth.",
            "Check logrotate status and open deleted files.",
        ),
        "actions": (
            "Compress/truncate verified oversized logs safely.",
            "Restart or reload the application after logrotate fix if needed.",
            "Restore normal logging level.",
        ),
    },
    "windows_service_crash": {
        "title": "Windows service crash",
        "severity": "critical",
        "alert_source": "WIN-DB01",
        "alert_message": "SQLAgent service terminated unexpectedly multiple times.",
        "root_cause": "SQLAgent crash loop after a recent job plugin update.",
        "impact": "Scheduled database jobs are not running.",
        "change": "Updated SQL maintenance job plugin on WIN-DB01.",
        "logs": [
            ("WIN-DB01", "Windows", "EventID=7031 SQLAgent service terminated unexpectedly."),
            ("WIN-DB01", "Windows", "Application error references SQL job plugin dll load failure."),
            ("fortigate-fw01", "Fortigate", "Unrelated VPN tunnel keepalive normal."),
        ],
        "metrics": [
            ("WIN-DB01", "service_restart_count", 5, 0, "count"),
            ("WIN-DB01", "cpu_percent", 42, 35, "%"),
        ],
        "keywords": ("eventid=7031", "sqlagent", "plugin", "dll", "terminated"),
        "verification": (
            "Review Windows Application and System events around SQLAgent crash time.",
            "Check plugin version and dependency dll loading.",
        ),
        "actions": (
            "Disable or rollback the new job plugin after verification.",
            "Restart SQLAgent after confirming dependencies.",
        ),
    },
    "vmware_datastore_full": {
        "title": "VMware datastore full",
        "severity": "critical",
        "alert_source": "vcenter01",
        "alert_message": "Datastore ds-prod-01 usage exceeded critical threshold.",
        "root_cause": "Snapshot growth filled VMware datastore ds-prod-01.",
        "impact": "VMs on ds-prod-01 are at risk of stun or write failure.",
        "change": "Backup job changed to retain VMware snapshots for 48 hours.",
        "logs": [
            ("vcenter01", "VMware", "Datastore ds-prod-01 free space below 2 percent."),
            ("vcenter01", "VMware", "VM app-vm-07 snapshot delta file growing rapidly."),
            ("linux-api02", "Linux", "Unrelated auth warning from sudo command."),
        ],
        "metrics": [
            ("vcenter01", "datastore_used_percent", 99, 72, "%"),
            ("vcenter01", "snapshot_delta_gb", 860, 40, "GB"),
        ],
        "keywords": ("datastore", "snapshot", "delta", "free space"),
        "verification": (
            "List snapshots and delta file sizes for VMs on ds-prod-01.",
            "Confirm backup retention change and active consolidation tasks.",
        ),
        "actions": (
            "Free datastore space or migrate VMs after verification.",
            "Consolidate snapshots in a controlled window.",
            "Fix backup snapshot retention policy.",
        ),
    },
    "interface_flapping": {
        "title": "Interface flapping",
        "severity": "error",
        "alert_source": "core-sw02",
        "alert_message": "WAN interface ge-0/0/0 is flapping.",
        "root_cause": "Physical layer instability on WAN interface ge-0/0/0.",
        "impact": "Intermittent WAN packet loss and route reconvergence.",
        "change": "Provider handoff was moved to a new patch panel port.",
        "logs": [
            ("core-sw02", "Juniper", "Interface ge-0/0/0 link down."),
            ("core-sw02", "Juniper", "Interface ge-0/0/0 link up; FEC errors increased."),
            ("grafana", "Metrics", "Unrelated memory usage normal on app02."),
        ],
        "metrics": [
            ("core-sw02", "link_flap_count", 18, 0, "count/hour"),
            ("core-sw02", "crc_errors", 4400, 5, "errors/hour"),
            ("core-sw02", "packet_loss", 12.4, 0.1, "%"),
        ],
        "keywords": ("link down", "link up", "crc", "fec", "flap"),
        "verification": (
            "Check optics/cable levels and CRC/FEC counters on ge-0/0/0.",
            "Validate provider handoff and patch panel change.",
        ),
        "actions": (
            "Move traffic to backup WAN if loss persists.",
            "Replace cable/optic or revert patch panel move after validation.",
        ),
    },
    "routing_issue": {
        "title": "Routing issue",
        "severity": "critical",
        "alert_source": "core-rtr01",
        "alert_message": "Subnet 10.60.0.0/16 is unreachable from server zone.",
        "root_cause": "Route policy change withdrew the 10.60.0.0/16 prefix.",
        "impact": "Applications cannot reach the payment subnet.",
        "change": "Updated BGP export policy on core-rtr01.",
        "logs": [
            ("core-rtr01", "Juniper", "BGP route 10.60.0.0/16 withdrawn after policy EXPORT-SERVER changed."),
            ("fortigate-fw01", "Fortigate", "No deny log for traffic to 10.60.0.0/16."),
            ("app01", "ELK", "Connection timeout to payment-api.internal."),
        ],
        "metrics": [
            ("core-rtr01", "route_count_server_vrf", 1220, 1221, "routes"),
            ("app01", "payment_api_error_rate", 34, 0.2, "%"),
        ],
        "keywords": ("bgp", "withdrawn", "export", "route", "timeout"),
        "verification": (
            "Compare BGP export policy diff before and after the change.",
            "Check route table for 10.60.0.0/16 in server VRF.",
        ),
        "actions": (
            "Rollback or correct the BGP export policy after validation.",
            "Add a temporary approved route only if rollback is not possible.",
        ),
    },
    "brute_force_wazuh": {
        "title": "Brute force attack detected by Wazuh",
        "severity": "critical",
        "alert_source": "wazuh",
        "alert_message": "Multiple SSH authentication failures detected against linux-web01.",
        "root_cause": "External brute force attack against SSH on linux-web01.",
        "impact": "Increased authentication noise and account lockout risk.",
        "change": "Temporary firewall rule exposed SSH to the internet for vendor support.",
        "logs": [
            ("wazuh", "Wazuh", "Brute force rule fired for linux-web01 from 203.0.113.79."),
            ("linux-web01", "Linux", "sshd failed password for invalid user admin from 203.0.113.79."),
            ("fortigate-fw01", "Fortigate", "Policy vendor-ssh allowed inbound SSH from internet."),
        ],
        "metrics": [
            ("linux-web01", "ssh_failures_per_min", 180, 1, "failures/min"),
            ("fortigate-fw01", "ssh_session_count", 140, 2, "sessions"),
        ],
        "keywords": ("brute force", "failed password", "vendor-ssh", "ssh", "internet"),
        "verification": (
            "Confirm whether vendor SSH exposure is still required.",
            "Check for successful login from suspicious sources.",
        ),
        "actions": (
            "Restrict SSH source IPs or disable vendor-ssh rule after validation.",
            "Block offending IPs and review affected accounts.",
            "Enforce key-based auth and MFA for administrative access.",
        ),
    },
}


def list_scenarios() -> list[str]:
    return sorted(SCENARIOS)


def generate_incident(scenario: str | None = None) -> dict[str, Any]:
    scenario_key = _normalize_scenario(scenario)
    spec = SCENARIOS[scenario_key]
    base = BASE_TIME + timedelta(minutes=list_scenarios().index(scenario_key) * 15)
    incident_id = f"RCA-{scenario_key.replace('_', '-').upper()}-{base.strftime('%Y%m%d%H%M')}"

    recent_changes = [
        {
            "time": _iso(base - timedelta(minutes=7)),
            "source": "change-calendar",
            "summary": spec["change"],
            "type": "change",
        }
    ]
    logs = []
    for index, (source, system, message) in enumerate(spec["logs"], start=1):
        logs.append(
            {
                "time": _iso(base - timedelta(minutes=5) + timedelta(minutes=index)),
                "source": source,
                "system": system,
                "message": message,
            }
        )

    metrics = []
    for index, (source, name, value, baseline, unit) in enumerate(spec["metrics"], start=1):
        metrics.append(
            {
                "time": _iso(base - timedelta(minutes=4) + timedelta(minutes=index)),
                "source": source,
                "name": name,
                "value": value,
                "baseline": baseline,
                "unit": unit,
                "status": "abnormal" if _is_abnormal(value, baseline) else "normal",
            }
        )

    return {
        "incident_id": incident_id,
        "scenario": scenario_key,
        "alert": {
            "time": _iso(base),
            "source": spec["alert_source"],
            "severity": spec["severity"],
            "message": spec["alert_message"],
        },
        "logs": logs,
        "metrics": metrics,
        "topology": _topology_for(spec),
        "recent_changes": recent_changes,
        "baseline": {
            "description": "Synthetic baseline generated for RCA MVP.",
            "normal_metric_sources": [metric[0] for metric in spec["metrics"]],
        },
        "ground_truth_root_cause": spec["root_cause"],
    }


def _normalize_scenario(scenario: str | None) -> str:
    if not scenario:
        return "broadcast_loop"
    normalized = scenario.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "fortigate": "fortigate_session_spike",
        "firewall_cpu": "fortigate_session_spike",
        "linux_disk": "linux_disk_full",
        "windows_service": "windows_service_crash",
        "vmware": "vmware_datastore_full",
        "bruteforce": "brute_force_wazuh",
        "brute_force": "brute_force_wazuh",
        "wazuh": "brute_force_wazuh",
        "routing": "routing_issue",
        "interface": "interface_flapping",
        "dns": "dns_timeout",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SCENARIOS:
        return "broadcast_loop"
    return normalized


def _topology_for(spec: dict[str, Any]) -> dict[str, Any]:
    sources = sorted({spec["alert_source"], *[item[0] for item in spec["logs"]]})
    return {
        "nodes": [{"id": source, "role": _role_for_source(source)} for source in sources],
        "edges": [
            {"from": "core-sw01", "to": "fortigate-fw01", "relation": "routed-uplink"},
            {"from": "core-sw01", "to": "aruba-access-01", "relation": "access-uplink"},
            {"from": "core-sw01", "to": "linux-api02", "relation": "server-vlan"},
            {"from": "vcenter01", "to": "app-vm-07", "relation": "datastore-hosting"},
        ],
    }


def _role_for_source(source: str) -> str:
    if "fortigate" in source:
        return "firewall"
    if "sw" in source or "rtr" in source or "aruba" in source:
        return "network"
    if "WIN" in source or "windows" in source:
        return "windows"
    if "vcenter" in source:
        return "vmware"
    if "wazuh" in source:
        return "security"
    return "server"


def _is_abnormal(value: float | int, baseline: float | int) -> bool:
    if baseline == 0:
        return value > 0
    return value >= baseline * 2 or value - baseline >= 20


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def scenario_spec(scenario: str | None) -> dict[str, Any]:
    return deepcopy(SCENARIOS[_normalize_scenario(scenario)])
