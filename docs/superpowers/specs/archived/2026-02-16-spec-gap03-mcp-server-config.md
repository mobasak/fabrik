# GAP-03 MCP Server Config — Spec-Level Implementation Plan

**Version:** 1.1.0
**Revision Date:** 2026-02-17
**Status:** SPEC (not implementation)
**Compliance:** GAP-03 v1.0
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap03-mcp-server-config.md`

---

## Implementation Readiness Checklist

> **Pre-implementation step:** Before starting, verify repo paths exist and run the canonical gate on a clean checkout. Check boxes as verified.

- [ ] **Spec-Level Implementation Plan (implementable specs) attached**
- [ ] Repo grounding paths verified (all referenced files/dirs either exist or are explicitly CREATE)
- [ ] Required Artifacts list complete (CREATE/MODIFY + exact paths)
- [ ] Deterministic Gate is **one exact command** (copy/paste) and passes on a clean checkout
- [ ] DONE WHEN criteria are measurable and mapped to artifacts + gate output
- [ ] Failure modes/rollback defined (even if minimal)

---

## Artifacts Table

| Path | Action | Purpose | Gate Coverage |
|------|--------|---------|---------------|
| `/home/ozgur/.factory/mcp.json` | MODIFY | Add MCP server configs | Canonical gate |
| `/home/ozgur/.factory/mcp.json.bak` | CREATE | Backup before changes | `test -f /home/ozgur/.factory/mcp.json.bak` |
| `docs/reference/mcp-config.md` | CREATE | MCP documentation | `test -f docs/reference/mcp-config.md` |
| `CHANGELOG.md` | MODIFY | Document GAP-03 | Manual verify |

---

## Config Validation Command

```bash
# Validate MCP config structure and required keys
python -c "
import json, sys
from pathlib import Path

config_path = Path('/home/ozgur/.factory/mcp.json')
if not config_path.exists():
    sys.exit('ERROR: /home/ozgur/.factory/mcp.json not found')

try:
    config = json.loads(config_path.read_text())
except json.JSONDecodeError as e:
    sys.exit(f'ERROR: Invalid JSON: {e}')

# Required top-level key
if 'mcpServers' not in config:
    sys.exit('ERROR: Missing mcpServers key')

# Validate each server has required fields
required_server_fields = ['command', 'args']
for name, server in config.get('mcpServers', {}).items():
    missing = [f for f in required_server_fields if f not in server]
    if missing:
        print(f'WARNING: Server {name} missing optional fields: {missing}')

server_count = len(config.get('mcpServers', {}))
if server_count < 2:
    sys.exit(f'ERROR: Need 2+ servers, found {server_count}')

print(f'✓ MCP config valid ({server_count} servers)')
"
```

---

## Config Path Precedence

| Priority | Path | Purpose |
|----------|------|---------|
| 1 | `/home/ozgur/.factory/mcp.json` | User-level config (primary) |
| 2 | `/etc/factory/mcp.json` | System-level (future) |

**Note:** Only `/home/ozgur/.factory/mcp.json` is currently supported by Factory CLI.

---

## Sample MCP Config (Canonical Fixture)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/opt/fabrik", "/opt"],
      "env": {},
      "readOnly": true
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "${DB_CONNECTION_STRING}"
      }
    }
  }
}
```

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (External to Repo)

```
/home/ozgur/.factory/
├── settings.json               # Factory CLI settings (EXISTS)
├── mcp.json                    # MCP server config (EXISTS but empty/minimal)
└── droids/                     # Custom droids (GAP-06 scope)
```

### B. GAP-03 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `/home/ozgur/.factory/settings.json` | **FOUND** | `/home/ozgur/.factory/` | **VERIFY** — settings exist |
| `/home/ozgur/.factory/mcp.json` | **FOUND** (empty) | `/home/ozgur/.factory/` | **MODIFY** — add MCP servers |
| MCP server documentation | **NOT FOUND** | `docs/reference/` | **CREATE** required |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| MCP server not running | Start server first | Document as prerequisite |
| API key missing | Add to env vars | Use local-only server |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `/home/ozgur/.factory/mcp.json` | **MODIFY** | GAP-03 DONE WHEN: 2+ servers | Existing structure | **M** |
| `docs/reference/mcp-config.md` | **CREATE** | Documentation | — | **M** (~80 lines) |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** |

**Explicitly NOT created/modified:**
- `/home/ozgur/.factory/settings.json` — Only mcp.json changes
- Repo source code — MCP is external to repo
- Credentials in files — Env vars only

---

## 3. Interface & Contract Specification

### A. mcp.json Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "mcpServers": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["command"],
        "properties": {
          "command": { "type": "string" },
          "args": { "type": "array", "items": { "type": "string" } },
          "env": { "type": "object" }
        }
      }
    }
  }
}
```

### B. Recommended MCP Servers

| Server | Purpose | Security Level |
|--------|---------|----------------|
| `filesystem` | Local file access | Low (read-only paths) |
| `postgres` | Database queries | Medium (read-only) |
| `web-search` | Internet search | Low |
| `github` | Repository access | Medium (token required) |

### C. Example mcp.json Configuration

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/opt/fabrik"],
      "env": {}
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "${DB_URL}"
      }
    }
  }
}
```

### D. Security Constraints (MANDATORY)

| Constraint | Implementation |
|------------|----------------|
| **No hardcoded credentials** | Use `${ENV_VAR}` syntax |
| **Read-only by default** | Filesystem limited to specific paths |
| **No write to system dirs** | Exclude `/etc`, `/usr`, `/home` from write |
| **Audit logging** | Enable MCP request logging |
| **Least privilege** | Each server has minimal scope |

---

## 4. Golden Paths (2 Required)

### Golden Path 1: Add Filesystem MCP Server

**Command:**
```bash
python -c "import json; print(json.load(open('/home/ozgur/.factory/mcp.json'))['mcpServers']['filesystem'])"
```

**Expected output:**
```json
{
  "command": "npx",
  "args": ["-y", "@anthropic/mcp-server-filesystem", "/opt/fabrik"]
}
```

---

### Golden Path 2: Verify MCP Server Running

**Command:**
```bash
# In Factory/Windsurf, use MCP resource listing
list_resources ServerName="filesystem"
```

**Expected output:**
```
Available resources from filesystem server:
- file:///opt/fabrik/README.md
- file:///opt/fabrik/AGENTS.md
...
```

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **mcp.json invalid JSON** | `python -c "json.load(...)"` fails | Print JSON error | Restore backup |
| 2 | **MCP server not installed** | `npx @anthropic/mcp-server-*` fails | Print install command | None |
| 3 | **Env var not set** | `${VAR}` remains literal | Print required env vars | None |
| 4 | **Permission denied** | Server cannot read path | Adjust path permissions | Remove server entry |
| 5 | **Port conflict** | Server fails to start | Use different port | None |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
python -c "
import json, sys
config = json.load(open('/home/ozgur/.factory/mcp.json'))
servers = list(config.get('mcpServers', {}).keys())
if len(servers) < 2:
    sys.exit(f'Need 2+ servers, found {len(servers)}')
print('Servers:', servers)
print('PASS')
"
```

**Expected PASS output:**
```
true
"filesystem"
"postgres"
PASS
```

**Expected FAIL output:**
```
false
```

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

After **every step**, builder/verifier MUST output:

```text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [ ] No hardcoded credentials
- [ ] Env vars used for secrets
- [ ] Read-only where possible

Security Review:
- [ ] No secrets in config file
- [ ] Paths are scoped appropriately
- [ ] Least privilege applied

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| Factory CLI | MCP servers become available |
| Windsurf | Resources accessible via tools |
| Environment | Env vars must be set |

### Invariants (Hard Rules)

- **MUST NOT:** Hardcode any credentials in mcp.json
- **MUST NOT:** Enable write access to system directories
- **MUST:** Use env var substitution for secrets
- **MUST:** Document security model in reference doc

### Security Model

```
┌─────────────────────────────────────────┐
│ MCP Security Layers                     │
├─────────────────────────────────────────┤
│ 1. Credentials: ENV VARS ONLY           │
│ 2. Filesystem: /opt/* paths only        │
│ 3. Database: Read-only queries          │
│ 4. Network: HTTPS required              │
│ 5. Logging: All requests logged         │
└─────────────────────────────────────────┘
```

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Backup Existing Config

```text
DO:
- Create backup of existing mcp.json: cp /home/ozgur/.factory/mcp.json /home/ozgur/.factory/mcp.json.bak
- Verify backup is valid JSON

GATE:
test -f /home/ozgur/.factory/mcp.json.bak && python -c "import json; json.load(open('/home/ozgur/.factory/mcp.json.bak'))"

EVIDENCE REQUIRED:
- Backup file exists at /home/ozgur/.factory/mcp.json.bak
- python validates JSON successfully

SELF-REVIEW (Builder):
- [ ] Backup created
- [ ] Backup is valid JSON
- [ ] Original file preserved

MODE 4 VERIFICATION:
- Verifier confirms backup exists and is valid
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Add Filesystem MCP Server

```text
DO:
- Add filesystem server to /home/ozgur/.factory/mcp.json
- Use schema from Section 3.A
- Scope to /opt/fabrik and /opt/* paths only
- Set readOnly: true (no write access)

GATE:
python -c "import json; print(json.load(open('/home/ozgur/.factory/mcp.json'))['mcpServers']['filesystem'])"

EVIDENCE REQUIRED:
- Filesystem server entry exists
- Paths are scoped correctly
- readOnly is true

SELF-REVIEW (Builder):
- [ ] No hardcoded credentials
- [ ] Paths scoped to /opt/* only
- [ ] readOnly: true configured

SECURITY REVIEW:
- [ ] No write access to system directories
- [ ] No access to /home, /etc, /usr

MODE 4 VERIFICATION:
- Verifier audits: Scoped correctly? Read-only? Security constraints?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Add Second MCP Server (postgres or web-search)

```text
DO:
- Add a second MCP server (choose postgres or web-search)
- Use env var substitution for credentials: ${DB_PASSWORD}
- Configure connection parameters from env vars
- Set appropriate permissions (read-only for queries)

GATE:
python -c "import json; c=json.load(open('/home/ozgur/.factory/mcp.json')); print(len(c['mcpServers']), 'servers')"
# Expected: 2 or more

EVIDENCE REQUIRED:
- Second server entry exists
- Credentials use env var syntax
- python shows 2+ servers

SELF-REVIEW (Builder):
- [ ] No hardcoded credentials
- [ ] Env var substitution used for secrets
- [ ] Appropriate permissions set

SECURITY REVIEW:
- [ ] No plaintext passwords
- [ ] Database queries are read-only if postgres
- [ ] HTTPS required for web-search

MODE 4 VERIFICATION:
- Verifier audits: Credentials secure? Permissions correct?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create Documentation

```text
DO:
- Create docs/reference/mcp-config.md
- Document:
  - Available MCP servers
  - Security model (env vars, scoped paths, read-only)
  - Setup instructions for each server
  - Required environment variables
  - Troubleshooting common issues

GATE:
test -f docs/reference/mcp-config.md && head -5 docs/reference/mcp-config.md

EVIDENCE REQUIRED:
- mcp-config.md file exists
- Contains security section
- Contains setup instructions

SELF-REVIEW (Builder):
- [ ] Documentation follows Fabrik standards
- [ ] Security constraints clearly documented
- [ ] Setup instructions are complete
- [ ] Required env vars listed

MODE 4 VERIFICATION:
- Verifier audits: Complete? Clear? Security documented?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Verify MCP Servers Work

```text
DO:
- Test filesystem server: list available resources
- Test second server: run a test query/request
- Verify Factory CLI recognizes servers
- Update CHANGELOG.md

GATE (CANONICAL):
python -c "import json; c=json.load(open('/home/ozgur/.factory/mcp.json')); assert len(c['mcpServers'])>=2; print('PASS')"

EVIDENCE REQUIRED:
- Both servers respond to test commands
- Factory CLI shows servers available
- CHANGELOG updated

SELF-REVIEW (Builder):
- [ ] Filesystem server lists /opt/fabrik files
- [ ] Second server responds correctly
- [ ] No credential errors

MODE 4 VERIFICATION (FINAL):
- Verifier audits: Servers work? Security maintained? Ready to use?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- /home/ozgur/.factory/mcp.json doesn't exist or is corrupt
- Factory CLI doesn't support MCP servers
- Required env vars not documented

ON STOP:
- Restore from backup: cp /home/ozgur/.factory/mcp.json.bak /home/ozgur/.factory/mcp.json
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `docs/reference/mcp-config.md` |
| Files to MODIFY | `/home/ozgur/.factory/mcp.json`, `CHANGELOG.md` |
| Canonical Gate | 2+ MCP servers configured |
| Security | No hardcoded credentials, env vars only |

**All sections complete.** Ready for Mode 3 (Build) execution.
