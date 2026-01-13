#!/bin/bash
# Sync Windsurf extensions to documentation
# Used by pre-commit hook to keep extensions list current

set -e

EXTENSIONS_FILE="docs/reference/EXTENSIONS.md"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")

# Get extensions list
EXTENSIONS=$(windsurf --list-extensions 2>/dev/null || true)

if [ -z "$EXTENSIONS" ]; then
    echo "Warning: Could not get extensions list (windsurf CLI not available)"
    exit 0
fi

# Count extensions
COUNT=$(echo "$EXTENSIONS" | grep -v "^Extensions installed" | grep -v "^$" | wc -l)

# Generate install commands
INSTALL_CMDS=$(echo "$EXTENSIONS" | grep -v "^Extensions installed" | grep -v "^$" | sed 's/^/windsurf --install-extension /')

# Categorize extensions
PYTHON_EXT=$(echo "$EXTENSIONS" | grep -E "^(ms-python|charliermarsh)" | sort || true)
DOCKER_EXT=$(echo "$EXTENSIONS" | grep -E "^ms-azuretools" | sort || true)
GIT_EXT=$(echo "$EXTENSIONS" | grep -E "^(eamodio|github)" | sort || true)
AI_EXT=$(echo "$EXTENSIONS" | grep -E "^(anthropic|codeium|factory|traycer)" | sort || true)
MARKDOWN_EXT=$(echo "$EXTENSIONS" | grep -E "^(bierner|bpruitt|davidanson|vstirbu)" | sort || true)
WEB_EXT=$(echo "$EXTENSIONS" | grep -E "^(bradlc|prettier)" | sort || true)
OTHER_EXT=$(echo "$EXTENSIONS" | grep -v "^Extensions installed" | grep -v "^$" | \
    grep -v -E "^(ms-python|charliermarsh|ms-azuretools|eamodio|github|anthropic|codeium|factory|traycer|bierner|bpruitt|davidanson|vstirbu|bradlc|prettier)" | sort || true)

# Generate markdown
cat > "$EXTENSIONS_FILE" << EOF
# Windsurf Extensions

**Last Updated:** ${TIMESTAMP}
**Total:** ${COUNT} extensions

## Quick Install (All Extensions)

\`\`\`bash
${INSTALL_CMDS}
\`\`\`

## Extensions by Category

### AI & Copilot
$(echo "$AI_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

### Python Development
$(echo "$PYTHON_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

### Docker & Containers
$(echo "$DOCKER_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

### Git & GitHub
$(echo "$GIT_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

### Markdown & Documentation
$(echo "$MARKDOWN_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

### Web Development
$(echo "$WEB_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

### Other
$(echo "$OTHER_EXT" | sed 's/^/- `/' | sed 's/$/`/' || echo "None")

---

## How This File Is Updated

This file is automatically updated by the \`sync-extensions\` pre-commit hook.

To manually update:
\`\`\`bash
./scripts/sync_extensions.sh
\`\`\`

To install all extensions on a new machine:
\`\`\`bash
# Copy the install commands above, or run:
cat docs/reference/EXTENSIONS.md | grep "windsurf --install-extension" | bash
\`\`\`
EOF

# Check if file changed
if git diff --quiet "$EXTENSIONS_FILE" 2>/dev/null; then
    echo "Extensions unchanged"
else
    echo "Updated $EXTENSIONS_FILE ($COUNT extensions)"
    git add "$EXTENSIONS_FILE"
fi
