# Log and Report Format

## Input folders

```text
infra-log-sentinel-demo/
├── network/
├── windows/
├── linux/
└── vmware/
```

## Normalized event schema

```json
{
  "timestamp": "2026-06-12T09:01:22+07:00",
  "domain": "network",
  "source": "core-sw01.example.local",
  "severity": "critical",
  "event_type": "interface_down",
  "message": "Interface TenGigabitEthernet1/0/48 changed state to down",
  "raw": "original raw log line",
  "probable_cause": "Likely uplink failure, cable/SFP issue, peer shutdown, or recent change",
  "impact": "Possible connectivity loss for downstream segment",
  "recommended_action": "Check interface state, optics, peer device, logs around the same timestamp, and recent change records"
}
```

## Severity rules for MVP

- `critical`: outage, service stopped repeatedly, host failure, all paths down, disk/media error, HA failure, BGP/OSPF down, power failure.
- `error`: failed service, application crash, unexpected shutdown, login failure bursts, migration failed.
- `warning`: high resource usage, disk near full, datastore warning, failed login, packet drops, timeout, path warning.
- `info`: successful login, normal service start, snapshot created, scheduled jobs.

## Daily PDF report sections

1. Executive Summary
2. Severity Breakdown
3. Events By Domain: Network, Windows, Linux, VMware
4. Top Critical Events
5. Repeated Issues
6. Recommended Actions
7. Raw Evidence Appendix

## Telegram alert format

```text
[CRITICAL] Network Alert
Source: core-sw01.example.local
Event: interface_down
Summary: Uplink port TenGigabitEthernet1/0/48 is down.
Impact: Possible connectivity loss for downstream segment.
Action: Check interface status, cable/SFP, peer device, and recent changes.
```
