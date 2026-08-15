# T04 — Rewrite the rotation doc as the login-once reference + operator rollout runbook

## Scope
Rewrite `docs/workstation/claude-account-rotation.md` in place (Doc Sync Matrix: extend the
existing doc, never a second) to describe the login-once architecture: the per-window dir
model, the seeding contract, the two-variable carrier, the carrier-presence monitor, the
reload-never-login recovery rule, the DR rule (fleet-dir restore = one `/login`, never a file
restore), and the **M2/M3 operator runbook**: hub per-window env recipe, the staged login
batches (3–4 dirs per account per day, ~15 total), the grant-eviction abort signal (a relogin
prompt in an untouched dir → stop, regroup to fewer dirs/account), and the named successor plan
(M4 retirement sweep incl. the sound-system step + the VPS follow-up with its M4+30d deadline).
Update `docs/workstation/hooks-index.md`: the SessionStart drift-check row (removed at T01) and
the tick row's fleet-mode semantics. DO-NOT: do not document the retirement as done — it is the
successor plan; keep the legacy sections marked "until retirement".

Depends: T03
Parallel: ⛓️
Complexity: simple
Gate: .venv/bin/python scripts/enforcement/check_doc_sync.py
Docs: docs/workstation/claude-account-rotation.md (rewrite) + docs/workstation/hooks-index.md rows

## Touches
- docs/workstation/claude-account-rotation.md — PRIMARY PATH (in-place rewrite)
- docs/workstation/hooks-index.md — SessionStart + tick rows

## Behavior Contract
- **Given** the rewritten rotation doc, **When** its claims are checked against the shipped T01–T03 behavior, **Then** every named command, path, and env var exists as documented (docs/workstation/claude-account-rotation.md:1)

## Context Files
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
- docs/workstation/claude-account-rotation.md
- docs/workstation/hooks-index.md
- .windsurf/rules/core/40-documentation.md
