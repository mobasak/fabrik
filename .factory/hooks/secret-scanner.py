#!/usr/bin/env python3
"""
Fabrik Secret Scanner Hook - PostToolUse

Scans code for hardcoded secrets and credentials.
Blocks commits of files containing secrets.

Exit codes:
- 0: No secrets found
- 2: Secrets detected, block with feedback
"""

import json
import os
import re
import sys

# Secret patterns to detect
SECRET_PATTERNS = [
    # AWS
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r'aws_secret_access_key\s*=\s*[\'"][A-Za-z0-9/+=]{40}[\'"]', "AWS Secret Key"),
    # Google
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    # OpenAI
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API Key"),
    # Anthropic
    (r"sk-ant-[a-zA-Z0-9\-]{32,}", "Anthropic API Key"),
    # GitHub
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}", "GitHub Fine-grained PAT"),
    # GitLab
    (r"glpat-[a-zA-Z0-9\-]{20}", "GitLab Personal Access Token"),
    # Stripe
    (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Secret Key"),
    (r"rk_live_[a-zA-Z0-9]{24,}", "Stripe Restricted Key"),
    # Database URLs with passwords
    (r"postgresql://[^:]+:[^@]+@", "Database URL with password"),
    (r"mysql://[^:]+:[^@]+@", "Database URL with password"),
    (r"mongodb://[^:]+:[^@]+@", "Database URL with password"),
    # Generic secrets
    (
        r'(?:password|passwd|pwd|secret|token|api_key|apikey)\s*[:=]\s*[\'"][^\'"]{8,}[\'"]',
        "Hardcoded credential",
    ),
]

# Files to skip
SKIP_PATTERNS = [
    r"\.env\.example$",
    r"\.env\.sample$",
    r"test.*\.py$",
    r".*_test\.py$",
    r".*\.test\.(ts|js)$",
    r"fixtures/",
    r"mocks/",
]


def should_skip(file_path: str) -> bool:
    """Check if file should be skipped."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return True
    return False


def scan_content(content: str) -> list[tuple[str, str]]:
    """Scan content for secrets."""
    found = []

    for pattern, description in SECRET_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # Mask the actual secret
            for match in matches:
                if len(match) > 8:
                    masked = match[:4] + "..." + match[-4:]
                else:
                    masked = "***"
                found.append((description, masked))

    return found


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only check Write/Edit operations
    if tool_name not in ["Write", "Edit"]:
        sys.exit(0)

    if not file_path:
        sys.exit(0)

    # Skip certain files
    if should_skip(file_path):
        sys.exit(0)

    # Skip binary files
    if file_path.endswith((".jpg", ".png", ".gif", ".pdf", ".zip", ".tar", ".gz", ".ico")):
        sys.exit(0)

    # Get content
    if tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        if os.path.exists(file_path):
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                sys.exit(0)  # Binary file
        else:
            sys.exit(0)

    # Scan for secrets
    secrets = scan_content(content)

    if secrets:
        print(f"❌ Potential secrets detected in {file_path}:", file=sys.stderr)
        print("", file=sys.stderr)
        for description, masked in secrets:
            print(f"  • {description}: {masked}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Fabrik Security Policy:", file=sys.stderr)
        print("  - Use environment variables for all credentials", file=sys.stderr)
        print("  - Store secrets in .env (gitignored)", file=sys.stderr)
        print("  - Document vars in .env.example (no real values)", file=sys.stderr)
        print("  - Use os.getenv('VAR_NAME') in code", file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
