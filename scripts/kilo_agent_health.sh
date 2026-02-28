#!/bin/bash
# Kilo Agent Health Check Utility
# Verifies integrity of generated Kilo CLI agents

set -e

AGENT_DIR="${HOME}/.traycer/cli-agents"
ERRORS=0
WARNINGS=0

echo "=================================================="
echo "KILO AGENT HEALTH CHECK"
echo "=================================================="
echo ""

# Check if agent directory exists
if [ ! -d "$AGENT_DIR" ]; then
    echo "❌ ERROR: Agent directory not found: $AGENT_DIR"
    echo "Run: python scripts/generate_kilo_agents.py"
    exit 1
fi

echo "Agent directory: $AGENT_DIR"
AGENT_COUNT=$(find "$AGENT_DIR" -name "*.sh" -type f | wc -l)
echo "Total agents: $AGENT_COUNT"
echo ""

# Check each agent script
echo "Checking agent scripts..."
echo "--------------------------------------------------"

for agent in "$AGENT_DIR"/*.sh; do
    [ -e "$agent" ] || continue
    
    basename=$(basename "$agent")
    issues=()
    
    # Check if executable
    if [ ! -x "$agent" ]; then
        issues+=("not executable")
    fi
    
    # Check shebang
    if ! head -n1 "$agent" | grep -q "^#!/bin/sh"; then
        issues+=("missing/incorrect shebang")
    fi
    
    # Check for required components
    if ! grep -q "TRAYCER_PROMPT" "$agent"; then
        issues+=("missing TRAYCER_PROMPT handling")
    fi
    
    if ! grep -q "exit" "$agent"; then
        issues+=("missing exit statement")
    fi
    
    # Check shell syntax
    if ! sh -n "$agent" 2>/dev/null; then
        issues+=("shell syntax error")
    fi
    
    # Report results
    if [ ${#issues[@]} -eq 0 ]; then
        echo "  ✓ $basename"
    else
        echo "  ❌ $basename"
        for issue in "${issues[@]}"; do
            echo "     - $issue"
        done
        ((ERRORS++))
    fi
done

echo ""
echo "=================================================="
echo "SUMMARY"
echo "=================================================="
echo "Total agents: $AGENT_COUNT"
echo "Healthy: $((AGENT_COUNT - ERRORS))"
echo "Issues: $ERRORS"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo "✅ All agents are healthy"
    exit 0
else
    echo "❌ Found $ERRORS agents with issues"
    echo "Run: python scripts/generate_kilo_agents.py"
    exit 1
fi
