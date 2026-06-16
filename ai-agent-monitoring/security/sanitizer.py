"""
Output sanitizer — strips secrets and sensitive patterns from command output
before logging or including in reports.
"""

import re

# Patterns to redact
_PATTERNS = [
    (re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*\S+'), r'\1=***REDACTED***'),
    (re.compile(r'(?i)(token|api_key|apikey|secret|private_key)\s*[=:]\s*\S+'), r'\1=***REDACTED***'),
    (re.compile(r'(?i)(Authorization:\s*)(\S+)'), r'\1***REDACTED***'),
    (re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----', re.DOTALL), '***PRIVATE_KEY_REDACTED***'),
    (re.compile(r'(?i)postgres(?:ql)?://[^@]+@'), 'postgresql://***@'),
    (re.compile(r'(?i)mysql://[^@]+@'), 'mysql://***@'),
    (re.compile(r'(?i)mongodb(\+srv)?://[^@]+@'), r'mongodb\1://***@'),
    (re.compile(r'(?i)redis://:([^@]+)@'), 'redis://:***@'),
    # AWS keys
    (re.compile(r'(?i)(AKIA[0-9A-Z]{16})'), '***AWS_KEY_REDACTED***'),
    # Generic long hex/base64 tokens (>=32 chars)
    (re.compile(r'\b[A-Za-z0-9+/]{40,}={0,2}\b'), '***TOKEN_REDACTED***'),
]

# Dangerous command fragments that should never appear in output
_BLOCKED_CMD_FRAGMENTS = [
    "rm -rf", "mkfs", "dd if=", "reboot", "shutdown",
    "kill -9", "iptables -F", "iptables --flush",
    "> /dev/sda", "format c:",
]


def sanitize(text: str) -> str:
    """Remove secrets from text before logging/reporting."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def is_safe_output(text: str) -> bool:
    """Return False if the text contains dangerous command fragments."""
    lower = text.lower()
    return not any(frag.lower() in lower for frag in _BLOCKED_CMD_FRAGMENTS)
