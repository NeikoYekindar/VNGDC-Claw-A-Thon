# Hardening Profiles

This directory is the source of truth for the server hardening baseline that the
agent should verify.

Structure:

- `manifest.json`: maps supported `os_type` values to profile folders.
- `ubuntu_24_04/controls.json`: Ubuntu controls the agent should check.
- `ubuntu_24_04/apply_hardening.sh`: commands used to configure Ubuntu.
- `ubuntu_24_04/post_config_verification.md`: manual verification procedure for the attached Ubuntu template.
- `ubuntu_24_04/verify_config_template.sh`: read-only verification helper for the attached Ubuntu template.
- `windows_2022/controls.json`: Windows controls the agent should check.
- `windows_2022/apply_hardening.ps1`: commands used to configure Windows.
- `juniper_junos/controls.json`: Juniper Junos switch controls the agent should check.
- `juniper_junos/apply_hardening.set`: Junos `set`/`delete` runbook for switch hardening.
- `juniper_junos/post_config_verification.md`: Junos post-change verification procedure.
- `juniper_junos/verify_config_template.junos`: read-only Junos verification template and dashboard output contract.

Update the files in this directory when you change your hardening baseline. The
agent includes the selected profile in hardening output so reports are compared
against the controls you configured.

The `apply_hardening.*` files are documentation/runbooks by default. The agent
does not execute them automatically during a check.
