# MCP Kilo Server Setup Guide

**Last Updated:** 2026-06-16
**Status:** ✅ Ready for Testing

This guide explains how to enable Traycer Epic to consult Kilo CLI agents for planning via MCP (Model Context Protocol).

---

## What Was Implemented

### 1. MCP Server Wrapper (`/opt/fabrik/scripts/mcp_kilo_server.py`)

A FastMCP-based server that exposes 4 Kilo CLI tools to Traycer:

| Tool | Agent | Default Tier | Use Case |
|------|-------|--------------|----------|
| `kilo_review` | orchestrator | premium | Architecture/dependency review |
| `kilo_ask` | ask | standard | Verification/Q&A |
| `kilo_plan` | plan | premium | Planning consultation |
| `kilo_general` | general | economy | Quick checks |

**Features:**
- Async subprocess execution (5-minute timeout)
- JSON output format
- File attachment support
- Error handling with structured responses
- Tiered model selection (premium tier default for planning)

### 2. MCP Configuration (`~/.traycer/mcp.json`)

**Critical:** Config location is `~/.traycer/mcp.json` (**Traycer-specific config**)

**⚠️ Common Mistake:**
- ✅ Correct: `~/.traycer/mcp.json` (Traycer MCP config)
- ❌ Wrong: `~/.factory/mcp.json` (Kilo/Droid config, different system)
- ❌ Wrong: `/opt/fabrik/.factory/mcp.json` (project dir)

Registered `kilo-code` MCP server with correct format:

```json
{
  "mcpServers": {
    "kilo-code": {
      "type": "stdio",
      "command": "/opt/fabrik/.venv/bin/python",
      "args": ["/opt/fabrik/scripts/mcp_kilo_server.py"],
      "env": {},
      "disabled": false
    }
  }
}
```

**Required fields:**
- `"type": "stdio"` - Communication protocol (mandatory)
- `"disabled": false` - Enable the server (mandatory)
- `"command"` - Full path to Python interpreter in fabrik venv
- `"args"` - Full path to MCP server script
- `"env"` - Environment variables (empty object if none)

### 3. Dependencies Installed

✅ `mcp` Python SDK (v1.26.0) in `/opt/fabrik/.venv`

---

## How Traycer Uses It

### Step 1: Traycer Lists Available Tools

In Epic chat, Traycer can now discover Kilo tools:

```
list_mcp_server_tools(server="kilo-code")
```

**Expected Response:**
```json
{
  "tools": [
    {
      "name": "kilo_review",
      "description": "Run Kilo architecture/sequencing review using orchestrator agent",
      "inputSchema": {
        "type": "object",
        "properties": {
          "prompt": {"type": "string"},
          "files": {"type": "array", "items": {"type": "string"}},
          "strategy": {"type": "string", "default": "premium"}
        }
      }
    },
    ...
  ]
}
```

### Step 2: Traycer Calls kilo_review

During Epic planning, Traycer calls:

```python
kilo_review(
    prompt="Review WordPress deployment architecture for ocoron.com. Check: 1) Security hardening, 2) Container isolation, 3) Backup strategy, 4) Scalability",
    files=[
        "/opt/wpf/specs/sites/ocoron.com.yaml",
        "/opt/wpf/templates/base/compose.yaml.j2"
    ],
    strategy="premium"
)
```

**This executes:**
```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent orchestrator \
  --strategy premium \
  --output json \
  --plan "[prompt]" \
  --file /opt/wpf/specs/sites/ocoron.com.yaml \
  --file /opt/wpf/templates/base/compose.yaml.j2
```

### Step 3: Kilo Returns JSON Response

```json
{
  "verdict": "PASS",
  "summary": "Architecture review complete. Found 3 improvement areas.",
  "issues": [
    {
      "severity": "MAJOR",
      "category": "SECURITY",
      "file": "ocoron.com.yaml",
      "lines": "45-50",
      "why": "Missing WP_ENVIRONMENT_TYPE definition",
      "fix_hint": "Add deployment.environment: production"
    }
  ],
  "cost": 3.24,
  "model": "kilo/anthropic/claude-sonnet-4.6"
}
```

### Step 4: Traycer Applies Recommendations

Traycer:
1. Parses JSON response
2. Applies MAJOR/BLOCKER fixes to Epic specs
3. Updates Epic Brief with rationale
4. Runs verification with `kilo_ask`
5. Presents final plan to user

---

## Verification Steps

### Step 1: Verify MCP Config Location and Format

**Check config exists at correct location:**
```bash
cat ~/.factory/mcp.json
```

**Expected output should include:**
```json
{
  "mcpServers": {
    "kilo-code": {
      "type": "stdio",
      "command": "/opt/fabrik/.venv/bin/python",
      "args": ["/opt/fabrik/scripts/mcp_kilo_server.py"],
      "env": {},
      "disabled": false
    }
  }
}
```

**Common mistakes:**
- ❌ Config at `/opt/fabrik/.factory/mcp.json` (WRONG - project dir)
- ✅ Config at `~/.factory/mcp.json` (CORRECT - user home dir)
- ❌ Missing `"type": "stdio"` field
- ❌ Missing `"disabled": false` field

### Step 2: Verify MCP Server Works Standalone

Test the server directly:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
  /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/mcp_kilo_server.py
```

**Expected:** JSON response listing 4 tools (kilo_review, kilo_ask, kilo_plan, kilo_general)

**If errors:**
```bash
# Test mcp SDK import
/opt/fabrik/.venv/bin/python -c "from mcp.server.fastmcp import FastMCP; print('OK')"
# Should print: OK

# Test kilo_code_review.py exists
ls -la /opt/fabrik/scripts/kilo_code_review.py
# Should show the file
```

### Step 3: Verify MCP Config Format

**Validate JSON syntax:**
```bash
cat ~/.factory/mcp.json | python3 -m json.tool > /dev/null && echo "✅ Valid JSON" || echo "❌ Invalid JSON"
```

**Check kilo-code entry:**
```bash
cat ~/.factory/mcp.json | python3 -m json.tool | grep -A 8 '"kilo-code"'
```

**Expected:**
```json
"kilo-code": {
  "type": "stdio",
  "command": "/opt/fabrik/.venv/bin/python",
  "args": [
    "/opt/fabrik/scripts/mcp_kilo_server.py"
  ],
  "env": {},
  "disabled": false
}
```

### Test 2: Restart Traycer

**Windows 11 Pro (Windsurf Extension):**
1. Close Windsurf IDE completely
2. Re-open Windsurf
3. Traycer extension will reload MCP config

**Or restart Traycer daemon:**
```bash
# If Traycer has a daemon process
pkill -f traycer
# Traycer auto-restarts on next Epic action
```

### Test 3: Verify in Traycer Epic Chat

In Traycer Epic mode, run:

```
list_mcp_server_tools(server="kilo-code")
```

**Expected:** 4 tools listed (kilo_review, kilo_ask, kilo_plan, kilo_general)

**If tools not found:**
- Check `~/.factory/mcp.json` has `kilo-code` entry
- Verify Traycer restarted after config change
- Check Traycer logs for MCP server connection errors

### Test 4: Run Sample Consultation

In Traycer Epic chat:

```
kilo_ask(
    prompt="Quick test: verify this is working",
    strategy="economy"
)
```

**Expected:** JSON response from Kilo within 30-60 seconds

---

## Usage Examples

### Architecture Review (WordPress Deployment)

```python
kilo_review(
    prompt="""
Review this WordPress deployment plan for:
1. Security hardening (WP config, file permissions)
2. Container isolation (restart policies, networks)
3. Backup strategy (volume mounts, retention)
4. Scalability (multiple sites, resource limits)

Flag any BLOCKER or MAJOR issues.
""",
    files=[
        "/opt/wpf/specs/sites/ocoron.com.yaml",
        "/opt/wpf/templates/base/compose.yaml.j2",
        "/opt/wpf/templates/defaults.yaml"
    ],
    strategy="premium"
)
```

**Cost:** ~$3 (Strong tier)

### Verification Pass

```python
kilo_ask(
    prompt="""
Verify previous issues fixed:
- WP_ENVIRONMENT_TYPE=production added
- Database restart policy: unless-stopped
- Backup volume mount configured

Confirm no new issues introduced.
""",
    files=["/opt/wpf/specs/sites/ocoron.com.yaml"],
    strategy="standard"
)
```

**Cost:** ~$0.50 (Balanced tier)

### Phase Sequencing Review

```python
kilo_plan(
    prompt="""
Review this epic phase plan for dependency correctness:

Phase 0: Regression baseline + container resolver
Phase 1: ResolvedSpec wrapper + manifest generators
Phase 2: Stage decomposition + idempotency tracking
Phase 3: Infrastructure provisioner
Phase 4: Capability system integration

Are dependencies correct? Any missing prerequisites?
""",
    files=["/tmp/traycer-epics/epic-123/specs/phase-plan.md"],
    strategy="premium"
)
```

**Cost:** ~$3 (Strong tier)

---

## Cost Management

### Per Epic Planning Session

**Recommended workflow:**
1. Architecture review: `kilo_review` @ premium (~$3)
2. Verification: `kilo_ask` @ standard (~$0.50)
3. **Total:** ~$3.50 per Epic

**Monthly capacity (Traycer Pro+ $50/month):**
- ~14 Epic planning sessions with Kilo
- Or mix: 5 Epics with Kilo + 39 regular YOLO phases

### Tier Selection Guide

| Task Complexity | Tool | Strategy | Estimated Cost |
|----------------|------|----------|----------------|
| Critical architecture | `kilo_review` | premium | ~$3 |
| Standard verification | `kilo_ask` | standard | ~$0.50 |
| Quick sanity check | `kilo_general` | economy | ~$0.02 |

---

## Traycer Epic Workflow Integration

### Before (Manual Planning)

1. Traycer generates Epic Brief + Specs
2. User manually reviews
3. User finds issues → rewrites plan
4. Repeat until satisfied

### After (Kilo-Assisted Planning)

1. Traycer generates Epic Brief + Specs
2. **Traycer calls `kilo_review` automatically**
3. Kilo returns structured feedback (JSON)
4. **Traycer applies fixes + updates specs**
5. **Traycer calls `kilo_ask` for verification**
6. Traycer presents final plan with quality score

**User benefits:**
- Faster planning cycles
- Higher quality specs (AI-reviewed)
- Automatic issue detection
- Transparent cost tracking

---

## Troubleshooting

### Error: "Kilo CLI not found"

**Cause:** MCP server can't find `/opt/fabrik/scripts/kilo_code_review.py`

**Fix:**
```bash
ls -la /opt/fabrik/scripts/kilo_code_review.py
# Should show file with execute permissions
```

### Error: "Kilo review timed out"

**Cause:** Kilo CLI took > 5 minutes (usually model unavailable)

**Fix:**
1. Check Kilo authentication: `kilo auth status`
2. Test Kilo directly: `python /opt/fabrik/scripts/kilo_code_review.py review --help`
3. Reduce file attachments (large files slow review)

### Error: "mcp package not installed"

**Cause:** MCP SDK missing from fabrik venv

**Fix:**
```bash
cd /opt/fabrik
source .venv/bin/activate
pip install mcp
```

### Traycer doesn't see tools

**Cause:** Traycer didn't reload MCP config

**Fix:**
1. Verify `~/.factory/mcp.json` has `kilo-code` entry
2. Fully close and restart Windsurf IDE
3. Check Traycer logs for MCP connection errors

---

## Next Steps

### 1. Test in Traycer Epic Chat

Run this test prompt:

```
list_mcp_server_tools(server="kilo-code")
```

**Expected:** See 4 Kilo tools listed

### 2. Run Simple Consultation

```
kilo_ask(
    prompt="Test: verify this MCP integration is working correctly",
    strategy="economy"
)
```

**Expected:** JSON response within 30s

### 3. Re-run WordPress Epic Planning

Paste the original epic finalization prompt to Traycer. It should now:
1. Load epic specs/tickets
2. Self-critique plan
3. **Call `kilo_review` automatically** ← NEW
4. Apply Kilo feedback
5. **Call `kilo_ask` for verification** ← NEW
6. Present final locked plan

**Cost:** ~$3.50 for full consultation workflow

---

## Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `/opt/fabrik/scripts/mcp_kilo_server.py` | **Created** | MCP server wrapper for Kilo CLI |
| `~/.factory/mcp.json` | **Updated** | Registered `kilo-code` server |
| `/opt/fabrik/.venv/` | **Updated** | Installed `mcp` package |

---

## References

- **Kilo CLI:** `/opt/fabrik/scripts/kilo_code_review.py`
- **MCP Config:** `~/.factory/mcp.json`
- **Traycer Integration Guide:** `/opt/fabrik/docs/traycer/epic-kilo-integration.md`
- **MCP SDK Docs:** https://github.com/anthropics/anthropic-mcp

---

## Summary

✅ **MCP server created and registered**
✅ **Dependencies installed**
✅ **Configuration updated**

**Status:** Ready for testing

**Test command for Traycer Epic:**
```
list_mcp_server_tools(server="kilo-code")
```

**Next:** Restart Traycer, verify tools appear, run epic planning with Kilo consultation
