# 2026-02-16-plan-gap03-mcp-server-config

**Status:** NOT_STARTED
**Created:** 2026-02-16
**Priority:** P1 (High)
**Estimated Effort:** 2-4 hours
**Source:** Research document "Optimizing Workflows Across AI Coding Platforms"

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-03 MCP Server Configuration only
NEXT REQUIRED: Mode 4 — Verify with Factory Droid after each step

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope (spec freeze)
- One step at a time
- After each step: show Evidence + Gate result
- After each step: Mode 4 verification
- If a Gate fails → STOP and report
- Maintain same session ID throughout execution

ROLE SEPARATION:
- Builder (Cascade/You): Implements code, runs self-review
- Verifier (Factory Droid): Independent audit, approves changes
- Rule: "Verifier never fixes. Builder never self-verifies."
```

---

## TASK METADATA

```text
TASK:
Configure MCP (Model Context Protocol) servers for external tool access

GOAL:
Enable Cascade/Factory to access external tools (Coolify, Supabase, Cloudflare) directly without manual command execution.

DONE WHEN (all true):
- [ ] ~/.factory/mcp.json configured with at least 2 MCP servers
- [ ] Credentials stored securely (not in mcp.json)
- [ ] MCP servers tested and functional
- [ ] Documentation updated
- [ ] Gate command passes: cat ~/.factory/mcp.json | jq '.mcpServers | keys | length' >= 2

OUT OF SCOPE:
- Building custom MCP servers (use existing)
- Modifying Coolify/Supabase APIs
- Production deployment of MCP servers
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- MCP config: ~/.factory/mcp.json
- Credentials: environment variables, NOT in config
- Security: MCP servers run locally
- Compatibility: Factory CLI supported MCP format

SESSION MANAGEMENT:
- Start: droid exec -m swe-1-5 "Start GAP-03" (captures session_id)
- Continue: droid exec --session-id <id> "Next step..."
- WARNING: Changing models mid-session loses context
- Verification uses SEPARATE session (Verifier independence)

MODEL ASSIGNMENTS (from config/models.yaml):
- Execution: swe-1-5 or gpt-5.1-codex (Stage 3 - Build)
- Verification: gpt-5.3-codex (Stage 4 - Verify)
- Documentation: claude-haiku-4-5 (Stage 5 - Ship)
```

---

## EXISTING INFRASTRUCTURE (avoid duplication)

| Component | Location | Status |
|-----------|----------|--------|
| MCP config | `~/.factory/mcp.json` | Empty `{"mcpServers": {}}` |
| Coolify API | VPS via SSH | Accessible |
| Supabase | Project configured | API keys exist |
| Cloudflare | DNS automation | API token exists |
| Factory settings | `~/.factory/settings.json` | Hooks/skills enabled |

---

## CANONICAL GATE

```text
CANONICAL GATE:
cat ~/.factory/mcp.json | jq '.mcpServers | keys'
```

---

## EXECUTION STEPS

### Step 1 — Research Available MCP Servers

```text
DO:
- Search for existing MCP server implementations
- Identify suitable servers for: Coolify, Supabase, Cloudflare, Docker
- Document server URLs/packages and requirements
- Create docs/reference/mcp-servers.md with findings

GATE:
- docs/reference/mcp-servers.md exists
- At least 3 MCP servers documented

EVIDENCE REQUIRED:
- mcp-servers.md content
- Server sources (npm, GitHub, etc.)

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review MCP server research for completeness"
- droid exec -m gemini-3-pro-preview "Review MCP server security considerations"
```

---

### Step 2 — Configure Supabase MCP Server

```text
DO:
- Install Supabase MCP server (if npm-based)
- Configure in ~/.factory/mcp.json
- Use environment variables for credentials:
  - SUPABASE_URL
  - SUPABASE_SERVICE_KEY
- Test connection

Configuration format:
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server"],
      "env": {
        "SUPABASE_URL": "${SUPABASE_URL}",
        "SUPABASE_SERVICE_KEY": "${SUPABASE_SERVICE_KEY}"
      }
    }
  }
}

GATE:
- cat ~/.factory/mcp.json | jq '.mcpServers.supabase'

EVIDENCE REQUIRED:
- mcp.json supabase config
- Test connection output (if available)

PRE-FLIGHT GATES:
- Validate JSON syntax: jq . ~/.factory/mcp.json

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit Supabase MCP configuration: Correct? Secure? List issues as JSON."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Configure Docker MCP Server

```text
DO:
- Install Docker MCP server
- Configure in ~/.factory/mcp.json
- Enable: container list, logs, restart, health check
- Test basic operations

GATE:
- cat ~/.factory/mcp.json | jq '.mcpServers.docker'

EVIDENCE REQUIRED:
- mcp.json docker config
- Docker socket access verified

PRE-FLIGHT GATES:
- Validate JSON syntax: jq . ~/.factory/mcp.json
- Check Docker socket: ls -la /var/run/docker.sock

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit Docker MCP configuration: Security? Correct socket? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Configure Filesystem MCP Server (if needed)

```text
DO:
- Evaluate if filesystem MCP server adds value beyond Cascade's native file access
- If yes, configure with restricted paths:
  - /opt/ (projects)
  - ~/.factory/ (config)
- Exclude sensitive paths: ~/.ssh, /etc

GATE:
- If configured: cat ~/.factory/mcp.json | jq '.mcpServers.filesystem'
- If skipped: document reason in mcp-servers.md

EVIDENCE REQUIRED:
- Configuration or skip rationale

PRE-FLIGHT GATES:
- Validate JSON syntax if configured: jq . ~/.factory/mcp.json

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit filesystem MCP scope: Paths restricted? Sensitive dirs excluded?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Create MCP Environment Setup Script

```text
DO:
- Create scripts/setup-mcp-env.sh
- Script checks for required env vars
- Script validates MCP server availability
- Script tests each configured server
- Follow existing script patterns

GATE:
- bash scripts/setup-mcp-env.sh --check

EVIDENCE REQUIRED:
- setup-mcp-env.sh content
- Check output

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review setup-mcp-env.sh for Fabrik patterns"
- droid exec -m gemini-3-pro-preview "Review setup-mcp-env.sh completeness"
```

---

### Step 6 — Update Documentation

```text
DO:
- Update docs/reference/mcp-servers.md with final config
- Add MCP section to docs/CONFIGURATION.md
- Add MCP troubleshooting to docs/TROUBLESHOOTING.md
- Update CHANGELOG.md

GATE:
- grep -c "MCP" docs/CONFIGURATION.md >= 1
- grep -c "MCP" docs/TROUBLESHOOTING.md >= 1

EVIDENCE REQUIRED:
- Documentation diffs
- CHANGELOG entry

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review MCP documentation"
- droid exec -m gemini-3-pro-preview "Review MCP documentation clarity"
```

---

### Step 7 — Final Verification

```text
DO:
- Run full MCP validation
- Test Cascade can see MCP tools
- Document any limitations

GATE:
- cat ~/.factory/mcp.json | jq '.mcpServers | keys | length' >= 2

EVIDENCE REQUIRED:
- Final mcp.json
- MCP server count

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Final review of MCP setup"
- droid exec -m gemini-3-pro-preview "Final review of MCP setup"
```

---

## STOP CONDITIONS

```text
STOP IF:
- No suitable MCP servers available for target services
- MCP servers require paid subscriptions
- Security concerns with credential handling

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Fewer context switches | AI completes tasks without user commands |
| Richer context | AI reads real system state |
| Automation unlocked | Chain: deploy → wait → verify |
| Security | Credentials local, never sent to AI |

---

## MCP SERVERS TO EVALUATE

| Server | Purpose | Priority |
|--------|---------|----------|
| Supabase MCP | Database queries, migrations | High |
| Docker MCP | Container management | High |
| Filesystem MCP | Extended file access | Medium |
| Cloudflare MCP | DNS management | Medium |
| SSH MCP | Remote server access | Low (security) |

---

## REPORTING FORMAT (strict)

After **every step**, the agent must output:

```text
STEP <N> STATUS: PASS / FAIL

Changed files:
- <path>

Gate output:
<pasted output>

Code Review (GPT-5.3):
<summary of findings>

Code Review (Gemini Pro):
<summary of findings>

Next:
- Proceed to Step <N+1> OR STOP
```
