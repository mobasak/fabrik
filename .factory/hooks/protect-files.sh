#!/bin/bash
# Fabrik File Protection Hook - PreToolUse
#
# Blocks edits to sensitive files that should not be modified by AI.
# Exit code 2 blocks the operation.

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Skip if no file path
if [ -z "$file_path" ]; then
  exit 0
fi

# Protected file patterns (never modify)
# Note: .env.example is allowed (not matched by these patterns)
protected_patterns=(
  "\.env$"
  "\.env\.local$"
  "\.env\.production$"
  "\.env\.development$"
  "\.git/"
  "node_modules/"
  "__pycache__/"
  "\.pyc$"
  "\.pem$"
  "\.key$"
  "\.p12$"
  "\.crt$"
  "credentials\.json"
  "secrets\.json"
  "\.ssh/"
  "id_rsa"
  "\.gnupg/"
)

# Check if file matches any protected pattern
for pattern in "${protected_patterns[@]}"; do
  if echo "$file_path" | grep -qE "$pattern"; then
    echo "❌ Cannot modify protected file: $file_path" >&2
    echo "This file is protected by Fabrik security policy." >&2
    echo "" >&2
    echo "If you need to modify credentials:" >&2
    echo "1. Edit the file manually" >&2
    echo "2. Store secrets in environment variables" >&2
    echo "3. Use .env.example for documentation (no real secrets)" >&2
    exit 2
  fi
done

exit 0
