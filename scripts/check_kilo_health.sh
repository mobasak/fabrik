#!/bin/bash
# Kilo CLI Health Check
# Verifies Kilo CLI is available and working (WSL binary, not Windows)
#
# This script is called by pre-commit to detect broken Kilo installations early.
# It explicitly checks the WSL npm-global path to avoid picking up Windows binaries.

set -e

# Priority order: KILO_PATH env var > WSL npm-global > which kilo
KILO_PATH="${KILO_PATH:-$HOME/.npm-global/bin/kilo}"

# Check if the preferred path exists and is executable
if [ -x "$KILO_PATH" ]; then
    if "$KILO_PATH" --version >/dev/null 2>&1; then
        echo "Kilo CLI OK: $("$KILO_PATH" --version) at $KILO_PATH"
        exit 0
    else
        echo "ERROR: Kilo CLI at $KILO_PATH failed to run"
        echo "This may indicate a platform mismatch (Windows binary in WSL)"
        echo "Fix: npm install -g @kilocode/cli in WSL"
        exit 1
    fi
fi

# Fallback: try which kilo
KILO_WHICH=$(which kilo 2>/dev/null || true)
if [ -n "$KILO_WHICH" ] && [ -x "$KILO_WHICH" ]; then
    # Check if it's a Windows path (contains /mnt/c/)
    if [[ "$KILO_WHICH" == /mnt/c/* ]]; then
        echo "ERROR: Kilo CLI found at Windows path: $KILO_WHICH"
        echo "This will not work in WSL. Install Kilo in WSL:"
        echo "  npm install -g @kilocode/cli"
        echo "Or set KILO_PATH to the WSL binary location"
        exit 1
    fi

    if "$KILO_WHICH" --version >/dev/null 2>&1; then
        echo "Kilo CLI OK: $("$KILO_WHICH" --version) at $KILO_WHICH"
        exit 0
    fi
fi

echo "ERROR: Kilo CLI not found"
echo "Install with: npm install -g @kilocode/cli"
echo "Or set KILO_PATH environment variable"
exit 1
