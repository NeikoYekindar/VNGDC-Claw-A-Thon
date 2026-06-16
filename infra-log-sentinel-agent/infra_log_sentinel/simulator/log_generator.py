from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import random
import time


DOMAINS = (
    "network",
    "fortigate",
    "juniper",
    "aruba",
    "linux",
    "windows",
    "vmware",
    "checkmk",
    "cacti",
    "prometheus",
    "grafana",
    "elk",
    "wazuh",
    "syslog",
)
DOMAIN_ALIASES = {
    "fortinet": "fortigate",
    "firewall": "fortigate",
    "junos": "juniper",
    "aruba_ap": "aruba",
    "aruba_controller": "aruba",
    "linux_server": "linux",
    "linuxserver": "linux",
    "windows_server": "windows",
    "windowsserver": "windows",
    "elastic": "elk",
    "elasticsearch": "elk",
    "logstash": "elk",
    "kibana": "elk",
    "real_syslog": "syslog",
    "syslog_true": "syslog",
}
SEVERITIES = ("info", "warning", "error", "critical")
ABNORMAL_SEVERITIES = ("warning", "error", "critical")
INCIDENT_SCENARIOS = (
    "broadcast_loop",
    "mac_flapping",
    "fortigate_session_spike",
    "dns_timeout",
    "linux_disk_full",
    "windows_service_crash",
    "vmware_datastore_full",
    "interface_flapping",
    "routing_issue",
    "brute_force_wazuh",
)


@dataclass(frozen=True)
class GeneratedLogLine:
    domain: str
    severity: str
    path: Path
    text: str


def generate_log_lines(
    log_root_path: Path,
    count: int,
    interval_seconds: float,
    domain: str = "all",
    severity: str = "abnormal",
) -> list[GeneratedLogLine]:
    generated = []
    for index in range(count):
        generated.append(generate_one_log_line(log_root_path, domain=domain, severity=severity))
        if index < count - 1 and interval_seconds > 0:
            time.sleep(interval_seconds)
    return generated


def generate_incident_log_lines(
    log_root_path: Path,
    scenario: str = "broadcast_loop",
) -> list[GeneratedLogLine]:
    selected_scenario = _pick_incident_scenario(scenario)
    sequence = INCIDENT_TEMPLATES[selected_scenario]
    max_offset = max((offset for offset, *_ in sequence), default=0)
    start_time = datetime.now().astimezone().replace(microsecond=0) - timedelta(seconds=max_offset)
    generated = []
    for offset_seconds, domain, severity, template in sequence:
        event_time = start_time + timedelta(seconds=offset_seconds)
        text = template(event_time)
        output_dir = log_root_path / domain
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"dynamic-{domain}.log"
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
        generated.append(
            GeneratedLogLine(
                domain=domain,
                severity=severity,
                path=output_path,
                text=text,
            )
        )
    return generated


def generate_one_log_line(log_root_path: Path, domain: str = "all", severity: str = "abnormal") -> GeneratedLogLine:
    selected_domain = _pick_domain(domain)
    selected_severity = _pick_severity(severity)
    template = random.choice(TEMPLATES[selected_domain][selected_severity])
    now = datetime.now().astimezone()
    text = template(now)

    output_dir = log_root_path / selected_domain
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"dynamic-{selected_domain}.log"
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")

    return GeneratedLogLine(
        domain=selected_domain,
        severity=selected_severity,
        path=output_path,
        text=text,
    )


def _pick_domain(domain: str) -> str:
    normalized = domain.lower().replace("-", "_").replace(" ", "_")
    normalized = DOMAIN_ALIASES.get(normalized, normalized)
    if normalized == "all":
        return random.choice(DOMAINS)
    if normalized not in DOMAINS:
        raise ValueError(f"Unsupported domain '{domain}'. Expected one of: all, {', '.join(DOMAINS)}")
    return normalized


def _pick_incident_scenario(scenario: str) -> str:
    normalized = scenario.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "broadcast": "broadcast_loop",
        "loop": "broadcast_loop",
        "mac": "mac_flapping",
        "fortigate": "fortigate_session_spike",
        "firewall": "fortigate_session_spike",
        "dns": "dns_timeout",
        "linux": "linux_disk_full",
        "disk": "linux_disk_full",
        "windows": "windows_service_crash",
        "service": "windows_service_crash",
        "vmware": "vmware_datastore_full",
        "datastore": "vmware_datastore_full",
        "interface": "interface_flapping",
        "routing": "routing_issue",
        "route": "routing_issue",
        "brute": "brute_force_wazuh",
        "wazuh": "brute_force_wazuh",
        "ssh": "brute_force_wazuh",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in INCIDENT_SCENARIOS:
        raise ValueError(
            f"Unsupported incident scenario '{scenario}'. Expected one of: {', '.join(INCIDENT_SCENARIOS)}"
        )
    return normalized


def _pick_severity(severity: str) -> str:
    normalized = severity.lower()
    if normalized == "all":
        return random.choice(SEVERITIES)
    if normalized == "abnormal":
        return random.choice(ABNORMAL_SEVERITIES)
    if normalized not in SEVERITIES:
        raise ValueError(f"Unsupported severity '{severity}'. Expected one of: all, abnormal, {', '.join(SEVERITIES)}")
    return normalized


def _iso(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def _syslog(now: datetime) -> str:
    return now.strftime("%b %d %H:%M:%S")


def _rand_ip(prefix: str = "10.255.0") -> str:
    return f"{prefix}.{random.randint(2, 254)}"


def _rand_public_ip() -> str:
    return f"203.0.113.{random.randint(10, 250)}"


def _rand_interface() -> str:
    return random.choice(["TenGigabitEthernet1/0/48", "Gi1/0/12", "Port-channel10", "Gi2/0/21"])


TEMPLATES = {
    "network": {
        "info": [
            lambda now: f"{_iso(now)} core-sw01.example.local %SYS-5-CONFIG_I: Configured from console by netadmin on vty0 (10.10.10.5)",
        ],
        "warning": [
            lambda now: f"{_iso(now)} edge-fw01.example.local %ASA-4-106023: Deny tcp src outside:{_rand_public_ip()}/443 dst inside:10.20.30.15/50432 by access-group \"OUTSIDE-IN\"",
            lambda now: f"{_iso(now)} access-sw07.example.local %PM-4-ERR_DISABLE: loopback error detected on Gi1/0/12, putting Gi1/0/12 in err-disable state",
            lambda now: f"{_iso(now)} dist-sw02.example.local %C4K_EBM-4-HOSTFLAPPING: Host 00:50:56:aa:bb:cc in vlan 120 is flapping between port Gi2/0/17 and Gi2/0/21",
        ],
        "error": [
            lambda now: f"{_iso(now)} dist-sw02.example.local %LINK-3-UPDOWN: Interface {_rand_interface()}, changed state to down",
            lambda now: f"{_iso(now)} edge-fw01.example.local %ASA-3-210007: LU allocate connection failed, memory pressure high, current memory usage {random.randint(90, 98)} percent",
        ],
        "critical": [
            lambda now: f"{_iso(now)} core-rtr01.example.local %BGP-5-ADJCHANGE: neighbor {_rand_ip()} Down BGP Notification sent",
            lambda now: f"{_iso(now)} core-rtr01.example.local %OSPF-5-ADJCHG: Process 100, Nbr {_rand_ip()} on Port-channel10 from FULL to DOWN, Neighbor Down: Dead timer expired",
            lambda now: f"{_iso(now)} core-sw01.example.local %PLATFORM-2-PS_FAIL: Power supply 2 failed or removed",
        ],
    },
    "fortigate": {
        "info": [
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=traffic subtype=forward level=notice action=accept policyid=101 srcip=10.20.30.15 dstip=198.51.100.20 service=HTTPS msg=\"Allowed outbound application traffic\"",
        ],
        "warning": [
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=traffic subtype=forward level=warning action=deny policyid=204 srcip={_rand_public_ip()} dstip=10.20.30.15 service=SSH msg=\"Deny tcp from untrusted source\"",
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=utm subtype=ips level=warning severity=warning srcip={_rand_public_ip()} dstip=10.20.30.15 msg=\"IPS signature matched and blocked\"",
        ],
        "error": [
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=event subtype=vpn level=error tunnel=branch-ipsec-01 msg=\"IPsec vpn tunnel branch-ipsec-01 down due to DPD timeout\"",
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=event subtype=system level=error msg=\"Session table usage high memory pressure current usage {random.randint(90, 98)} percent\"",
        ],
        "critical": [
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=utm subtype=virus level=critical severity=critical srcip=10.20.30.15 dstip={_rand_public_ip()} msg=\"Malware detected and blocked by antivirus profile\"",
            lambda now: f"{_iso(now)} fortigate-fw01.example.local type=event subtype=ha level=critical msg=\"HA peer lost heartbeat, firewall failover triggered\"",
        ],
    },
    "juniper": {
        "info": [
            lambda now: f"{_iso(now)} mx-rtr01.example.local mgd[1201]: UI_COMMIT_COMPLETED: commit complete by user netops",
        ],
        "warning": [
            lambda now: f"{_iso(now)} mx-rtr01.example.local rpd[1442]: warning BGP_PREFIX_THRESH_EXCEEDED: neighbor {_rand_ip()} received prefix count above threshold",
        ],
        "error": [
            lambda now: f"{_iso(now)} mx-rtr01.example.local rpd[1442]: RPD_BGP_NEIGHBOR_STATE_CHANGED: BGP neighbor {_rand_ip()} Down, reason Hold Timer Expired",
            lambda now: f"{_iso(now)} ex-sw03.example.local chassisd[981]: interface xe-0/0/5 down, optical receive power low",
        ],
        "critical": [
            lambda now: f"{_iso(now)} mx-rtr01.example.local chassisd[981]: critical power supply 1 failed or removed",
        ],
    },
    "aruba": {
        "info": [
            lambda now: f"{_iso(now)} aruba-ctrl01.example.local stm[2112]: AP aruba-ap-12 joined controller on group campus-wifi",
        ],
        "warning": [
            lambda now: f"{_iso(now)} aruba-ctrl01.example.local authmgr[2199]: warning client authentication failed for user guest from {_rand_public_ip()}",
            lambda now: f"{_iso(now)} aruba-ctrl01.example.local wms[2200]: warning high retry rate detected on SSID CorpWiFi radio 5GHz",
        ],
        "error": [
            lambda now: f"{_iso(now)} aruba-ctrl01.example.local stm[2112]: AP aruba-ap-07 disconnected from controller, heartbeat timed out",
        ],
        "critical": [
            lambda now: f"{_iso(now)} aruba-gw01.example.local cluster[3102]: critical gateway cluster failover triggered, node aruba-gw02 unreachable",
        ],
    },
    "linux": {
        "info": [
            lambda now: f"{_syslog(now)} linux-web01.example.local systemd[1]: Started nginx.service - A high performance web server.",
        ],
        "warning": [
            lambda now: f"{_syslog(now)} linux-web01.example.local sshd[1842]: Failed password for invalid user admin from {_rand_public_ip()} port 51520 ssh2",
            lambda now: f"{_syslog(now)} linux-api02.example.local kernel: EXT4-fs warning (device sda1): ext4_dx_add_entry: Directory index full",
            lambda now: f"{_syslog(now)} linux-web01.example.local kernel: TCP: request_sock_TCP: Possible SYN flooding on port 443. Sending cookies.",
        ],
        "error": [
            lambda now: f"{_syslog(now)} linux-api02.example.local systemd[1]: app-worker.service: Main process exited, code=exited, status=1/FAILURE",
            lambda now: f"{_syslog(now)} linux-web01.example.local nginx[1902]: upstream timed out (110: Connection timed out) while reading response header from upstream, client: 10.50.10.8, server: app.example.local",
        ],
        "critical": [
            lambda now: f"{_syslog(now)} linux-db01.example.local kernel: blk_update_request: critical medium error, dev sdb, sector {random.randint(8000000, 9999999)}",
            lambda now: f"{_syslog(now)} linux-api02.example.local systemd[1]: CRITICAL payment-worker.service: Main process exited, code=exited, status=1/FAILURE",
        ],
    },
    "windows": {
        "info": [
            lambda now: f"{_iso(now)} WIN-AD01.example.local Security EventID=4624 Level=Information User=svc_monitor LogonType=3 Message=\"An account was successfully logged on\"",
        ],
        "warning": [
            lambda now: f"{_iso(now)} WIN-AD01.example.local Security EventID=4625 Level=Warning User=svc_backup SourceIP=10.40.10.{random.randint(10, 99)} Message=\"An account failed to log on\"",
            lambda now: f"{_iso(now)} WIN-FILE01.example.local System EventID=2013 Level=Warning Source=Srv Message=\"The C: disk is at or near capacity. Free space is {random.randint(4, 9)} percent\"",
        ],
        "error": [
            lambda now: f"{_iso(now)} WIN-APP02.example.local Application EventID=1000 Level=Error Source=Application Error Message=\"Faulting application name: app-worker.exe, exception code: 0xc0000005\"",
            lambda now: f"{_iso(now)} WIN-APP02.example.local System EventID=6008 Level=Error Source=EventLog Message=\"The previous system shutdown was unexpected\"",
        ],
        "critical": [
            lambda now: f"{_iso(now)} WIN-DB01.example.local System EventID=7031 Level=Critical Source=Service Control Manager Message=\"The SQLAgent service terminated unexpectedly. It has done this {random.randint(2, 5)} time(s)\"",
        ],
    },
    "vmware": {
        "info": [
            lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=VmPoweredOnEvent VM=app-web-{random.randint(1, 9):02d} Host=esxi-01.example.local User=ops.user Message=\"Virtual machine powered on\"",
        ],
        "warning": [
            lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=DatastoreUsageOnDiskWarning Datastore=ds-prod-01 Usage={random.randint(84, 93)}% Message=\"Datastore usage on disk has exceeded warning threshold\"",
            lambda now: f"{_iso(now)} esxi-01.example.local hostd[10122]: warning hostd[10122] [Originator@6876 sub=Vimsvc.ha-eventmgr] Event 12345: Host memory usage is high: {random.randint(88, 96)} percent",
        ],
        "error": [
            lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=VmFailedMigrateEvent VM=app-db-02 SourceHost=esxi-01.example.local DestHost=esxi-02.example.local Message=\"vMotion migration failed due to network timeout\"",
            lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=VmPoweredOffEvent VM=legacy-app-01 User=unknown Message=\"Virtual machine powered off unexpectedly\"",
        ],
        "critical": [
            lambda now: f"{_iso(now)} esxi-03.example.local vmkernel: cpu4:2103311)ALERT: APD: All paths down for device naa.6000c29b2",
            lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=DasHostFailedEvent Host=esxi-03.example.local Cluster=prod-cluster Message=\"vSphere HA detected a host failure\"",
        ],
    },
    "checkmk": {
        "info": [
            lambda now: f"{_iso(now)} checkmk01.example.local CHECK_MK OK host=linux-web01 service=PING msg=\"OK - host ping is OK\"",
        ],
        "warning": [
            lambda now: f"{_iso(now)} checkmk01.example.local CHECK_MK WARNING host=linux-api02 service=CPU msg=\"WARNING - CPU utilization {random.randint(85, 92)} percent\"",
            lambda now: f"{_iso(now)} checkmk01.example.local CHECK_MK WARNING host=core-rtr01 service=PacketLoss msg=\"WARNING - packet loss {random.randint(5, 15)} percent\"",
        ],
        "error": [
            lambda now: f"{_iso(now)} checkmk01.example.local CHECK_MK ERROR host=core-rtr01 service=SNMP msg=\"ERROR - SNMP poller timeout after 30 seconds\"",
        ],
        "critical": [
            lambda now: f"{_iso(now)} checkmk01.example.local CHECK_MK CRITICAL host=linux-api02 service=app-worker msg=\"CRITICAL - service is down\"",
        ],
    },
    "cacti": {
        "info": [
            lambda now: f"{_iso(now)} cacti01.example.local poller[3301]: SYSTEM STATS: Time:12.5 Method:cmd.php Processes:4 Threads:8 Hosts:128 HostsPerProcess:32 DataSources:4096",
        ],
        "warning": [
            lambda now: f"{_iso(now)} cacti01.example.local threshold[3302]: WARNING traffic threshold exceeded for core-rtr01 Gi0/1 inbound utilization 89 percent",
        ],
        "error": [
            lambda now: f"{_iso(now)} cacti01.example.local poller[3301]: ERROR SNMP poller timeout for device core-rtr01.example.local after 3 retries",
        ],
        "critical": [
            lambda now: f"{_iso(now)} cacti01.example.local thold[3303]: CRITICAL host down device=dist-sw02.example.local status=down availability=0 percent",
        ],
    },
    "prometheus": {
        "info": [
            lambda now: f"{_iso(now)} prometheus01.example.local level=info component=rule_manager msg=\"Rule group evaluated\" group=infra.rules duration=18ms",
        ],
        "warning": [
            lambda now: f"{_iso(now)} prometheus01.example.local level=warn severity=warning alertname=HighMemoryUsage instance=linux-api02.example.local status=firing value={random.randint(88, 94)}",
        ],
        "error": [
            lambda now: f"{_iso(now)} prometheus01.example.local level=error severity=error alertname=TargetScrapeFailed instance=linux-api02.example.local msg=\"scrape failed: context deadline exceeded\"",
        ],
        "critical": [
            lambda now: f"{_iso(now)} prometheus01.example.local level=critical severity=critical alertname=InstanceDown instance=payment-api.example.local status=firing msg=\"Target has been down for 5 minutes\"",
        ],
    },
    "grafana": {
        "info": [
            lambda now: f"{_iso(now)} grafana01.example.local logger=ngalert level=info alertname=APIAvailability state=normal msg=\"alert rule evaluated\"",
        ],
        "warning": [
            lambda now: f"{_iso(now)} grafana01.example.local logger=ngalert level=warn severity=warning alertname=HighLatency state=alerting msg=\"p95 latency above 1200ms\"",
        ],
        "error": [
            lambda now: f"{_iso(now)} grafana01.example.local logger=ngalert level=error alertname=DatasourceError msg=\"prometheus datasource query failed\"",
        ],
        "critical": [
            lambda now: f"{_iso(now)} grafana01.example.local logger=ngalert level=critical severity=critical alertname=APIUnavailable state=alerting msg=\"service availability below SLO\"",
        ],
    },
    "elk": {
        "info": [
            lambda now: f"{_iso(now)} elastic01.example.local elasticsearch[4401]: cluster_status=green active_shards=128 msg=\"cluster health is green\"",
        ],
        "warning": [
            lambda now: f"{_iso(now)} elastic01.example.local elasticsearch[4401]: warning cluster_status=yellow unassigned_shards=2 msg=\"replica shards initializing\"",
        ],
        "error": [
            lambda now: f"{_iso(now)} logstash01.example.local logstash[4402]: ERROR pipeline blocked pipeline_id=firewall-ingest queue_backpressure=true",
        ],
        "critical": [
            lambda now: f"{_iso(now)} elastic01.example.local elasticsearch[4401]: critical cluster_status=red unassigned_shards=12 msg=\"primary shards unavailable\"",
        ],
    },
    "wazuh": {
        "info": [
            lambda now: f"{_iso(now)} wazuh01.example.local wazuh-remoted[5501]: Agent linux-web01.example.local connected from 10.50.10.21",
        ],
        "warning": [
            lambda now: f"{_iso(now)} wazuh01.example.local wazuh-analysisd[5502]: rule.level=7 severity=warning auth_failed srcip={_rand_public_ip()} user=admin msg=\"Failed password for invalid user admin\"",
        ],
        "error": [
            lambda now: f"{_iso(now)} wazuh01.example.local wazuh-syscheckd[5503]: rule.level=10 severity=error msg=\"File integrity checksum changed\" file=/etc/ssh/sshd_config",
        ],
        "critical": [
            lambda now: f"{_iso(now)} wazuh01.example.local wazuh-analysisd[5502]: rule.level=12 severity=critical msg=\"Malware detected on endpoint linux-web01.example.local\" file=/tmp/payload.bin",
        ],
    },
    "syslog": {
        "info": [
            lambda now: f"{_syslog(now)} syslog01.example.local cron[1221]: session opened for user root by UID 0",
        ],
        "warning": [
            lambda now: f"{_syslog(now)} syslog01.example.local kernel: warning interface eth0 link down on uplink bond0",
        ],
        "error": [
            lambda now: f"{_syslog(now)} syslog01.example.local app-worker[2410]: job-runner.service failed with result exit-code",
        ],
        "critical": [
            lambda now: f"{_syslog(now)} syslog01.example.local kernel: critical Out of memory: Killed process 2410 (java) total-vm:4096000kB",
        ],
    },
}


INCIDENT_TEMPLATES = {
    "broadcast_loop": [
        (0, "network", "info", lambda now: f"{_iso(now)} core-sw01.example.local %SYS-5-CONFIG_I: Configured from console by netadmin enabling access port Gi1/0/48 for temporary uplink"),
        (20, "network", "warning", lambda now: f"{_iso(now)} access-sw07.example.local %PM-4-ERR_DISABLE: loopback error detected on Gi1/0/48, putting Gi1/0/48 in err-disable state"),
        (35, "network", "warning", lambda now: f"{_iso(now)} dist-sw02.example.local %C4K_EBM-4-HOSTFLAPPING: Host 00:50:56:aa:bb:cc in vlan 120 is flapping between port Gi2/0/17 and Gi2/0/21"),
        (55, "network", "error", lambda now: f"{_iso(now)} edge-fw01.example.local %ASA-3-210007: LU allocate connection failed, memory pressure high, current memory usage 94 percent"),
        (70, "network", "critical", lambda now: f"{_iso(now)} core-rtr01.example.local %BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down BGP Notification sent"),
    ],
    "mac_flapping": [
        (0, "network", "info", lambda now: f"{_iso(now)} dist-sw02.example.local %SYS-5-CONFIG_I: Configured redundant uplink Gi2/0/21"),
        (15, "network", "warning", lambda now: f"{_iso(now)} dist-sw02.example.local %C4K_EBM-4-HOSTFLAPPING: Host 00:50:56:aa:30:01 in vlan 130 is flapping between port Gi2/0/17 and Gi2/0/21"),
        (30, "network", "error", lambda now: f"{_iso(now)} dist-sw02.example.local %LINK-3-UPDOWN: Interface Gi2/0/21, changed state to down"),
    ],
    "fortigate_session_spike": [
        (0, "fortigate", "info", lambda now: f"{_iso(now)} fortigate-fw01.example.local type=config level=notice msg=\"Configured temporary policy 182 for subnet 10.20.0.0/16\""),
        (20, "fortigate", "warning", lambda now: f"{_iso(now)} fortigate-fw01.example.local type=traffic level=warning action=deny policyid=182 srcip=203.0.113.79 dstip=10.20.30.15 service=HTTPS msg=\"Deny tcp by temporary policy\""),
        (40, "fortigate", "error", lambda now: f"{_iso(now)} fortigate-fw01.example.local type=event level=error msg=\"Session table usage high memory pressure current usage 97 percent\""),
        (60, "linux", "warning", lambda now: f"{_syslog(now)} linux-web01.example.local kernel: TCP: request_sock_TCP: Possible SYN flooding on port 443. Sending cookies."),
    ],
    "dns_timeout": [
        (0, "linux", "info", lambda now: f"{_syslog(now)} linux-dns01.example.local systemd[1]: Deployed named.service zone configuration update for app.example.local"),
        (15, "linux", "warning", lambda now: f"{_syslog(now)} linux-dns01.example.local named[1204]: DNS query timeout for app.example.local from 10.50.10.8 after configuration reload"),
        (35, "linux", "error", lambda now: f"{_syslog(now)} linux-web01.example.local nginx[1902]: upstream timed out (110: Connection timed out) while reading response header from upstream, client: 10.50.10.8, server: app.example.local"),
        (55, "linux", "error", lambda now: f"{_syslog(now)} linux-api02.example.local systemd[1]: app-worker.service: Main process exited, code=exited, status=1/FAILURE"),
    ],
    "linux_disk_full": [
        (0, "linux", "warning", lambda now: f"{_syslog(now)} linux-api02.example.local app-monitor[2201]: The /var/log disk is at or near capacity. Free space is 5 percent"),
        (20, "linux", "warning", lambda now: f"{_syslog(now)} linux-api02.example.local kernel: EXT4-fs warning (device sda1): ext4_dx_add_entry: Directory index full"),
        (40, "linux", "critical", lambda now: f"{_syslog(now)} linux-api02.example.local kernel: blk_update_request: critical medium error, dev sda1, sector 9421188"),
        (60, "linux", "error", lambda now: f"{_syslog(now)} linux-api02.example.local systemd[1]: app-worker.service: Main process exited, code=exited, status=1/FAILURE"),
    ],
    "windows_service_crash": [
        (0, "windows", "info", lambda now: f"{_iso(now)} WIN-DB01.example.local Application EventID=1033 Level=Information Source=MsiInstaller Message=\"Product: SQLAgent job plugin - deployed configuration update successfully\""),
        (20, "windows", "error", lambda now: f"{_iso(now)} WIN-DB01.example.local Application EventID=1000 Level=Error Source=Application Error Message=\"Faulting application name: sqlagent-job-plugin.dll, exception code: 0xc0000005\""),
        (40, "windows", "critical", lambda now: f"{_iso(now)} WIN-DB01.example.local System EventID=7031 Level=Critical Source=Service Control Manager Message=\"The SQLAgent service terminated unexpectedly. It has done this 3 time(s)\""),
        (65, "windows", "error", lambda now: f"{_iso(now)} WIN-DB01.example.local Application EventID=208 Level=Error Source=SQLAgent Message=\"Database job scheduler failed with result service unavailable after SQLAgent crash\""),
    ],
    "vmware_datastore_full": [
        (0, "vmware", "info", lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=TaskEvent VM=app-vm-07 User=backup Message=\"Snapshot created for backup retention change\""),
        (25, "vmware", "warning", lambda now: f"{_iso(now)} vcenter01.example.local vpxd[12001]: Event=DatastoreUsageOnDiskWarning Datastore=ds-prod-01 Usage=93% Message=\"Datastore usage on disk has exceeded warning threshold\""),
        (50, "vmware", "critical", lambda now: f"{_iso(now)} esxi-03.example.local vmkernel: cpu4:2103311)ALERT: APD: All paths down for device naa.6000c29b2"),
    ],
    "interface_flapping": [
        (0, "network", "info", lambda now: f"{_iso(now)} core-sw02.example.local %SYS-5-CONFIG_I: Configured provider handoff on ge-0/0/0"),
        (15, "network", "error", lambda now: f"{_iso(now)} core-sw02.example.local %LINK-3-UPDOWN: Interface ge-0/0/0, changed state to down"),
        (35, "network", "error", lambda now: f"{_iso(now)} core-sw02.example.local %LINK-3-UPDOWN: Interface ge-0/0/0, changed state to down"),
        (55, "network", "critical", lambda now: f"{_iso(now)} core-rtr01.example.local %OSPF-5-ADJCHG: Process 100, Nbr 10.255.0.6 on Port-channel10 from FULL to DOWN, Neighbor Down: Dead timer expired"),
    ],
    "routing_issue": [
        (0, "network", "info", lambda now: f"{_iso(now)} core-rtr01.example.local %SYS-5-CONFIG_I: Configured BGP export policy EXPORT-SERVER"),
        (20, "network", "critical", lambda now: f"{_iso(now)} core-rtr01.example.local %BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down BGP Notification sent"),
        (40, "network", "critical", lambda now: f"{_iso(now)} core-rtr01.example.local %OSPF-5-ADJCHG: Process 100, Nbr 10.255.0.6 on Port-channel10 from FULL to DOWN, Neighbor Down: Dead timer expired"),
    ],
    "brute_force_wazuh": [
        (0, "fortigate", "info", lambda now: f"{_iso(now)} fortigate-fw01.example.local type=config level=notice msg=\"Configured temporary vendor SSH access policy\""),
        (15, "linux", "warning", lambda now: f"{_syslog(now)} linux-web01.example.local sshd[1842]: Failed password for invalid user admin from 203.0.113.79 port 51520 ssh2"),
        (25, "wazuh", "warning", lambda now: f"{_iso(now)} wazuh01.example.local wazuh-analysisd[5502]: rule.level=7 severity=warning auth_failed srcip=203.0.113.79 user=admin msg=\"Failed password for invalid user admin\""),
        (35, "wazuh", "critical", lambda now: f"{_iso(now)} wazuh01.example.local wazuh-analysisd[5502]: rule.level=12 severity=critical auth_failed srcip=203.0.113.79 user=root msg=\"Multiple SSH authentication failures from same source\""),
    ],
}
