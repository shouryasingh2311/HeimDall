"""Mask known credential formats in the local display preview."""

import re

PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)"
)
URI_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", re.IGNORECASE)
AUTH_SCHEME = re.compile(r"\b(Bearer|Basic)\s+[^\s,;\"'<>]+", re.IGNORECASE)
ASSIGNMENT = re.compile(
    r"""(?ix)(\b(?:password|passwd|pwd|secret|token|(?:db|database)[_-]password|
             (?:api|access|secret|aws[_-]secret[_-]access)[_-]key|
             (?:access|refresh|auth)[_-]token)\b["']?\s*[:=]\s*)
        (?:"[^"\r\n]*(?:"|\Z)|'[^'\r\n]*(?:'|\Z)|[^\s,;}\]]+)"""
)


def scrub_preview(text: str) -> str:
    text = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    text = URI_CREDENTIALS.sub(r"\1[REDACTED]@", text)
    text = AUTH_SCHEME.sub(r"\1 [REDACTED]", text)
    return ASSIGNMENT.sub(r"\1[REDACTED]", text)
