#!/usr/bin/env python3
"""Check for hardcoded secrets and credentials."""

import re
from pathlib import Path

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?:aws_secret|AWS_SECRET)[^=]*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", "AWS Secret Key"),
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API Key"),
    (r"sk-ant-[a-zA-Z0-9\-]{32,}", "Anthropic API Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Key"),
    (r"rk_live_[a-zA-Z0-9]{24,}", "Stripe Restricted Key"),
    (r"postgresql://[^:]+:[^@\s]+@", "DB URL with password"),
    (r"mongodb(\+srv)?://[^:]+:[^@\s]+@", "MongoDB URL with password"),
    (r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    (r"Bearer\s+[a-zA-Z0-9\-_\.]{20,}", "Bearer Token"),
    (r'(?:password|secret|api_key|token)\s*[:=]\s*[\'"][^\'"]{8,}[\'"]', "Hardcoded credential"),
]

SKIP_PATTERNS = [
    r"\.env\.example$",
    r"/test_[^/]+\.py$",
    r"fixtures/",
    r"mocks/",
    r"check_secrets\.py$",  # Skip self to avoid false positives on patterns
]


def check_file(file_path: Path) -> list:
    """Check a file for hardcoded secrets."""
    from .validate_conventions import CheckResult, Severity

    results = []
    if any(re.search(p, str(file_path), re.I) for p in SKIP_PATTERNS):
        return results
    if file_path.suffix.lower() in (".jpg", ".png", ".gif", ".pdf", ".zip"):
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    for pattern, desc in SECRET_PATTERNS:
        for match in re.finditer(pattern, content, re.I):
            line_num = content[: match.start()].count("\n") + 1
            secret = match.group()
            masked = secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "***"
            results.append(
                CheckResult(
                    check_name="secrets",
                    severity=Severity.ERROR,
                    message=f"{desc}: {masked}",
                    file_path=str(file_path),
                    line_number=line_num,
                    fix_hint="Use env vars. Store in .env, document in .env.example",
                )
            )
    return results
