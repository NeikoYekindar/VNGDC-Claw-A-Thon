# Juniper Junos Post-Configuration Verification

Use this procedure after applying the Junos hardening baseline in
`apply_hardening.set`.

## 1. Pre-Change Safety

1. Open a persistent console or out-of-band session before changing management
   access.
2. Enter configuration mode:

```text
configure
```

3. Load the reviewed hardening commands:

```text
load set apply_hardening.set
show | compare
```

4. Commit safely:

```text
commit confirmed 5 comment "Apply VNGDC Junos hardening baseline"
```

5. Confirm the commit only after SSH and monitoring are verified:

```text
commit
```

If access breaks, wait for automatic rollback or run:

```text
rollback 1
commit
```

## 2. Management Services

Expected:

- SSH is enabled.
- Telnet is absent.
- Plain HTTP is absent.
- HTTPS exists only when J-Web is approved.

Commands:

```text
show configuration system services | display set | no-more
show system connections | match ":22|:23|:80|:443"
```

## 3. Authentication

Expected:

- Root authentication uses encrypted password or SSH key.
- No local user uses plain-text password.
- Retry limits are configured.
- Admin class idle timeout is configured where applicable.

Commands:

```text
show configuration system root-authentication | display set | no-more
show configuration system login | display set | no-more
show configuration system authentication-order | display set | no-more
```

## 4. Logging And Audit

Expected:

- Remote syslog/SIEM target is configured.
- Interactive commands are logged.
- Authorization/authentication events are logged.

Commands:

```text
show configuration system syslog | display set | no-more
show log messages | last 20
show log interactive-commands | last 20
```

## 5. Time Synchronization

Expected:

- Approved NTP server is configured.
- Timezone is explicit.
- Clock is synchronized.

Commands:

```text
show configuration system ntp | display set | no-more
show configuration system time-zone | display set | no-more
show ntp status
show system uptime
```

## 6. SNMP

Expected:

- Default `public` and `private` communities are absent.
- SNMPv2 communities, if used, are restricted to approved collectors.
- SNMPv3 is preferred for production monitoring.

Commands:

```text
show configuration snmp | display set | no-more
show snmp statistics
```

## 7. Control Plane Protection

Expected:

- A firewall filter is applied to `lo0`.
- SSH and management protocols are restricted to approved source prefixes.

Commands:

```text
show configuration interfaces lo0 | display set | no-more
show configuration firewall family inet | display set | no-more
show firewall filter <protect-re-filter>
```

## 8. Configuration Management

Expected:

- Configuration archive is configured if a backup repository is available.
- Login banner warns about authorized use and monitoring.
- Commit history is readable for audit.

Commands:

```text
show configuration system archival | display set | no-more
show configuration system login announcement | display set | no-more
show system commit | no-more
```

## 9. Agent Verification

From the VNGDC dashboard, create the switch as:

- OS Type: `Juniper Junos Switch`
- Port: SSH management port, usually `22`
- Username: read-only or operations account allowed to run `show` commands

Run `Run Hardening Check`. A passing report should show:

- `0 FAIL`
- WARN items reviewed and accepted by policy
- Device information collected from Junos CLI

## 10. Evidence To Keep

Save or attach these outputs to the change record:

- `show | compare` before commit
- `show configuration | display set | no-more` after commit
- `show system commit | no-more`
- VNGDC dashboard XLSX report
