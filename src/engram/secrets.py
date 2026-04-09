"""Deterministic secret detection — regex scanner for commit-time rejection.

Runs in <1ms. Catches common secret patterns. This is enforcement, not advisory.
"""

from __future__ import annotations

import re

# Patterns adapted from common secret scanners (truffleHog, detect-secrets)
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key", re.compile(r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[:=]\s*\S{20,}")),
    ("Generic API Key (sk-...)", re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b")),
    ("Generic API Key (key-...)", re.compile(r"\bkey-[a-zA-Z0-9]{20,}\b")),
    ("Bearer Token", re.compile(r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", re.IGNORECASE)),
    ("JWT Token", re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b")),
    ("Private Key Header", re.compile(r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH)?\s*PRIVATE KEY-----")),
    ("Connection String", re.compile(r"(?i)(mongodb|postgres|mysql|redis|amqp)://\S+:\S+@\S+")),
    ("GitHub Token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}\b")),
    ("Slack Token", re.compile(r"\bxox[bpors]-[a-zA-Z0-9\-]{10,}\b")),
    (
        "Generic Password Assignment",
        re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    ),
]


def scan_for_secrets(content: str) -> str | None:
    """Scan content for secret patterns.

    Returns a description of the first match found, or None if clean.
    """
    for name, pattern in _SECRET_PATTERNS:
        match = pattern.search(content)
        if match:
            # Show a truncated preview so the user knows what triggered it
            snippet = match.group()
            if len(snippet) > 20:
                snippet = snippet[:10] + "..." + snippet[-5:]
            return f"{name} (pattern: {snippet})"
    return None
