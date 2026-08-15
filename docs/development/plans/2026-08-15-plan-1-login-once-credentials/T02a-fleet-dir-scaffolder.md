# T02a — Fleet-dir scaffolder: `--new-dir`, seeding contract, `--sync-mcp`, carrier monitor

## Scope
The M1 machinery in `claude_rotate.py`. (1) `--new-dir <slug> <account-email>`: create
`~/.claude-fleet/<slug>/` mode 0700; seed `.claude.json` as a COPY of `~/.claude.json` (no
credential bytes — login replaces the OAuth section); symlink `settings.json`, `agents/`,
`commands/`, `skills/`, `projects/` → the canonical `~/.claude/` entries; append the
`assignments.json` row `{slug: {account: <email>, created: <iso>, identity: "pending-login"}}`;
write the project's `.claude/settings.local.json` carrier with BOTH env vars
(`CLAUDE_CONFIG_DIR` + `CLAUDE_QUOTA_HOME`, per the spec's Mechanism payload) when a repo path
is given. (2) `--sync-mcp`: re-copy the MCP `mcpServers` section of `~/.claude.json` into every
fleet dir's `.claude.json` (the R7 de-fork helper). (3) Carrier-presence monitor: a check,
wired into `--status`, that WARNs for every `assignments.json` project whose
`.claude/settings.local.json` is missing (B3 fail-open guard). DO-NOT: no login automation of
any kind; `--new-dir` never copies or writes credential bytes; the fleet gitignore is T02b's.

Depends: T01
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_claude_fleet.py -q
Docs: none (T04 owns the doc rewrite)

## Touches
- scripts/sysadmin/claude_rotate.py — PRIMARY PATH (--new-dir, --sync-mcp, carrier check)
- scripts/aro-wake/claude_rotate.py — byte-identical twin
- tests/test_claude_fleet.py — NEW test module (fleet-dir behaviors, tmp_path-isolated)

## Behavior Contract
- **Given** `--new-dir seo sarp@ocoron.com` with a repo path, **When** it runs, **Then** the dir carries a seeded `.claude.json`, the five symlinks, an assignments row, the two-variable carrier file, and zero credential bytes (scripts/sysadmin/claude_rotate.py:1599)
- **Given** an existing fleet dir, **When** `--new-dir` targets the same slug, **Then** it refuses and exits non-zero (check-before-create; never overwrite)
- **Given** a mapped project whose carrier file is missing, **When** `--status` runs, **Then** the output WARNs naming that project (scripts/sysadmin/claude_rotate.py:985)
- **Given** `--sync-mcp` after an MCP roster edit in `~/.claude.json`, **When** it runs, **Then** every fleet dir's `.claude.json` carries the new roster and its OAuth section is untouched

## Context Files
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
- .windsurf/rules/core/45-testing-strategy.md
