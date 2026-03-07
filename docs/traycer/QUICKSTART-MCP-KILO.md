# Traycer Epic + Kilo MCP Integration - Quick Start

**Last Updated:** 2026-03-07
**Status:** ✅ Configured and Ready for Testing

---

## ✅ What's Configured

### 1. MCP Server Script
**Location:** `/opt/fabrik/scripts/mcp_kilo_server.py`
**Status:** ✅ Created and tested
**Tools Exposed:** 4 Kilo agents (kilo_review, kilo_ask, kilo_plan, kilo_general)

### 2. MCP Configuration
**Location:** `~/.traycer/mcp.json` (**CRITICAL: Traycer-specific config**)
**Status:** ✅ Registered with correct format

**⚠️ Common Mistake:** The config is at `~/.traycer/mcp.json`, NOT `~/.factory/mcp.json`

```json
"kilo-code": {
  "type": "stdio",
  "command": "/opt/fabrik/.venv/bin/python",
  "args": ["/opt/fabrik/scripts/mcp_kilo_server.py"],
  "env": {},
  "disabled": false
}
```

**Critical fields:**
- ✅ `"type": "stdio"` - Required by Traycer
- ✅ `"disabled": false` - Enable the server
- ✅ Full path to Python in fabrik venv
- ✅ Full path to MCP server script

### 3. Dependencies
**Status:** ✅ Installed
- `mcp` SDK v1.26.0 in `/opt/fabrik/.venv`

---

## 🚀 Next Steps (For User)

### Step 1: Verify Configuration

Run this verification script:

```bash
cd /opt/fabrik

# Verify config location and format
echo "=== Checking MCP Config ==="
cat ~/.factory/mcp.json | python3 -m json.tool | grep -A 8 '"kilo-code"'

# Verify MCP server works standalone
echo ""
echo "=== Testing MCP Server ==="
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
  /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/mcp_kilo_server.py

# Verify mcp SDK
echo ""
echo "=== Checking MCP SDK ==="
/opt/fabrik/.venv/bin/python -c "from mcp.server.fastmcp import FastMCP; print('✅ MCP SDK OK')"
```

**Expected output:**
```
=== Checking MCP Config ===
"kilo-code": {
  "type": "stdio",
  "command": "/opt/fabrik/.venv/bin/python",
  ...
}

=== Testing MCP Server ===
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {"name": "kilo_review", ...},
      {"name": "kilo_ask", ...},
      ...
    ]
  }
}

=== Checking MCP SDK ===
✅ MCP SDK OK
```

### Step 2: Restart Traycer

**Windows 11 Pro (Windsurf IDE):**
1. Close Windsurf completely
2. Re-open Windsurf
3. Traycer extension auto-reloads MCP config

**Verification:** Traycer should connect to `kilo-code` server on startup

### Step 3: Test in Traycer Epic Chat

In Traycer Epic mode, run:

```
list_mcp_server_tools(server="kilo-code")
```

**Expected response:**
```json
{
  "tools": [
    {"name": "kilo_review", "description": "Run Kilo architecture/sequencing review..."},
    {"name": "kilo_ask", "description": "Run Kilo verification/Q&A..."},
    {"name": "kilo_plan", "description": "Run Kilo planning consultation..."},
    {"name": "kilo_general", "description": "Run Kilo general analysis..."}
  ]
}
```

**If tools not found:**
- Check Traycer logs for MCP connection errors
- Verify config at `~/.factory/mcp.json` (NOT `/opt/fabrik/.factory/mcp.json`)
- Ensure Traycer was fully restarted after config update

### Step 4: Run Sample Consultation

Test with simple query:

```
kilo_ask(
    prompt="Test: verify MCP integration is working correctly",
    strategy="economy"
)
```

**Expected:** JSON response with Kilo review results within 30-60 seconds

---

## 📋 Common Issues

### Issue 1: "Server kilo-code not found"

**Cause:** Traycer not restarted or wrong config location

**Fix:**
1. Verify config at `~/.factory/mcp.json` (user home):
   ```bash
   cat ~/.factory/mcp.json | grep -A 8 "kilo-code"
   ```
2. Fully close and restart Windsurf IDE
3. Check Traycer extension loaded

### Issue 2: MCP server crashes on startup

**Cause:** Missing dependencies or wrong paths

**Fix:**
```bash
# Test imports
/opt/fabrik/.venv/bin/python -c "from mcp.server.fastmcp import FastMCP"

# Test Kilo CLI exists
ls -la /opt/fabrik/scripts/kilo_code_review.py

# Reinstall mcp if needed
cd /opt/fabrik
source .venv/bin/activate
pip install --upgrade mcp
```

### Issue 3: Config at wrong location

**Cause:** Config created at `/opt/fabrik/.factory/mcp.json` instead of `~/.factory/mcp.json`

**Fix:**
```bash
# Remove wrong location if exists
rm -f /opt/fabrik/.factory/mcp.json

# Verify correct location has entry
cat ~/.factory/mcp.json | python3 -m json.tool | grep "kilo-code"
```

### Issue 4: Missing "type": "stdio" field

**Cause:** Config uses old format without required fields

**Fix:**
```bash
# Check current format
cat ~/.factory/mcp.json | python3 -m json.tool | grep -A 8 "kilo-code"

# Should show:
# "type": "stdio",
# "disabled": false,
```

If missing, manually add those fields or re-run setup.

---

## 📊 How Traycer Uses Kilo

### Workflow: Epic Planning with Kilo Consultation

**1. User requests Epic planning:**
```
"Create WordPress deployment plan for ocoron.com"
```

**2. Traycer generates initial draft:**
- Epic Brief (50 lines)
- Specs (architecture, deployment, content)
- Tickets (12 actionable items)

**3. Traycer calls kilo_review (automatic):**
```python
kilo_review(
    prompt="Review WordPress deployment architecture. Check: 1) Security hardening, 2) Container isolation, 3) Backup strategy, 4) Scalability",
    files=[
        "/opt/fabrik/specs/sites/ocoron.com.yaml",
        "/opt/fabrik/templates/wordpress/base/compose-coolify.yaml.j2"
    ],
    strategy="premium"
)
```

**4. Kilo responds (JSON):**
```json
{
  "verdict": "PASS",
  "issues": [
    {
      "severity": "MAJOR",
      "category": "SECURITY",
      "file": "ocoron.com.yaml",
      "why": "Missing WP_ENVIRONMENT_TYPE definition",
      "fix_hint": "Add deployment.environment: production"
    }
  ],
  "cost": 3.24
}
```

**5. Traycer applies fixes:**
- Updates specs with MAJOR fixes
- Updates Epic Brief with rationale
- Regenerates affected tickets

**6. Traycer calls kilo_ask (verification):**
```python
kilo_ask(
    prompt="Verify fixes applied: WP_ENVIRONMENT_TYPE added, restart policy set",
    files=["/opt/fabrik/specs/sites/ocoron.com.yaml"],
    strategy="standard"
)
```

**7. Traycer presents final plan:**
```
📊 Final Plan Summary:
- Epic Brief: 48 lines
- Specs: 3 files (deployment, theme, content)
- Tickets: 12 tickets (7 MVP, 5 stretch)
- Kilo Cost: $3.72 (2 consultations)
- Quality Score: PRODUCTION_READY

✅ Improvements Applied:
1. Added WP_ENVIRONMENT_TYPE=production
2. Set db restart policy: unless-stopped
3. Added backup volume mount

Would you like to proceed with this plan?
```

---

## 💰 Cost Budget

### Per Epic Planning Session

**Recommended workflow:**
- Architecture review: `kilo_review` @ premium (~$3)
- Verification: `kilo_ask` @ standard (~$0.50)
- **Total: ~$3.50 per Epic**

**Monthly capacity (Traycer Pro+ $50):**
- ~14 Epic planning sessions with Kilo
- Or mix: 5 Epics + 39 regular phases

### Tier Selection

| Traycer Action | Kilo Tool | Strategy | Cost |
|----------------|-----------|----------|------|
| Initial architecture review | `kilo_review` | premium | ~$3 |
| Security audit | `kilo_plan` | premium | ~$3 |
| Verification pass | `kilo_ask` | standard | ~$0.50 |
| Quick check | `kilo_general` | economy | ~$0.02 |

---

## 📁 Files Summary

| File | Status | Purpose |
|------|--------|---------|
| `/opt/fabrik/scripts/mcp_kilo_server.py` | ✅ Created | MCP server wrapper |
| `~/.factory/mcp.json` | ✅ Updated | MCP server registration |
| `/opt/fabrik/.venv/` | ✅ Updated | Installed mcp SDK |
| `/opt/fabrik/docs/traycer/mcp-kilo-setup-guide.md` | ✅ Created | Detailed setup guide |
| `/opt/fabrik/docs/traycer/epic-kilo-integration.md` | ✅ Created | Integration workflow |
| `/opt/fabrik/docs/traycer/QUICKSTART-MCP-KILO.md` | ✅ Created | This file |

---

## 🎯 Ready to Use

Once you complete Step 1-3 above:

1. ✅ MCP server is running
2. ✅ Traycer can connect to kilo-code
3. ✅ Epic planning uses Kilo consultation automatically

**Test command in Traycer Epic:**
```
list_mcp_server_tools(server="kilo-code")
```

**Expected:** 4 tools listed

**Then proceed with WordPress Epic planning:**
```
[Paste your epic finalization prompt]
```

Traycer will now automatically consult Kilo during planning and show cost/improvements in the final plan.

---

## 📚 References

- **Detailed Setup:** `/opt/fabrik/docs/traycer/mcp-kilo-setup-guide.md`
- **Integration Guide:** `/opt/fabrik/docs/traycer/epic-kilo-integration.md`
- **Kilo CLI:** `/opt/fabrik/scripts/kilo_code_review.py`
- **MCP Server:** `/opt/fabrik/scripts/mcp_kilo_server.py`
- **MCP Config:** `~/.factory/mcp.json`
