# Review — uses_claude_cli + llm-dispatch (the 3-layer claude-p+OpenRouter design)

Surface: my commits `46a87619` (Layer 1) + `f9cac924` (Layer 3) on `/opt/fabrik`, `fef5610` (Layer 2) on
`/opt/fabrik-lib`, plus this review's fix-delta. Scope: `spec_loader.py`, `orchestrator/deployer_ssh.py`,
`tests/orchestrator/test_deployer_ssh.py`, `.windsurf/rules/ai/00-ai-model-selection.md`,
`specs/services/seo.yaml`; `/opt/fabrik-lib/llm-dispatch/*`. **HUB review** → synced files (`ai/00`,
`spec_loader`, `deployer_ssh`) reviewed HARDER through a fleet lens. Pool finders returned empty this
session (deepseek); native Opus carried all rounds.

## Rubric (from `review_rubric.py --changed <paths>`)

```
FLOOR: core/35-security-auth · core/25-data-postgres · core/30-ops · 12-FACTOR (all twelve)
MATCHED: core/10-python (deployer_ssh, spec_loader, llm_dispatch, tests)
```

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| Boundary / incomplete-validation — 10-python/30-ops | **FIXED(1)** | **A:** `_assert_claude_cli_mounts` checked only `.claude:ro`, not the *also-required* `.claude.json:ro` (watchdog.py:818 — `claude -p` exits "config file not found" without it). A compose with one mount passed but died at runtime. Now requires BOTH (`all(t in compose_content for t in targets)`) + regression test |
| External-tool contract (claude CLI flags) — 10-python | **FIXED(1)** | **B:** `llm_dispatch.call_claude_cli` omitted `--output-format text` that the proven reference (claude-evaluator) sets; a shared module must not rely on the CLI default. Added. (stdin-passing itself is CORRECT — claude-evaluator proves `claude -p` reads stdin) |
| Test quality (red-on-revert) | **FIXED(2)** | **C:** the passing test asserted only one mount (would false-pass the A bug) → now asserts BOTH + a dedicated `test_requires_both_mounts_not_just_the_first` (reverting A → red). **H:** no test proved the validator was WIRED into a deploy path → added `test_uses_claude_cli_requires_mount_in_compose` (drives `_deploy_local`) |
| fail-open vs fail-closed | CLEAN | `_assert…` raises when the mount is missing (blocks deploy); `call_claude_cli` raises on non-zero/empty (→ escalate); `dispatch` raises `LLMUnavailable` when nothing serves. Flag OFF → no-op (default False, no existing service affected) |
| security — mounting operator OAuth (35-security-auth, fleet lens) | **FIXED(1)** | The flag mounts the operator's ACTIVE Claude OAuth (RO) into a container — RCE could read it. Acceptable under the single-operator threat model (rotatable/revocable) + mirrors the watchdog, but the flag description now carries the exposure caution |
| cost / quota edges | CLEAN | claude leg = subscription (no $-cap); paid OpenRouter leg budgeted via the injected `openrouter_fn` (cost-budget wrapped) — documented in the module README; no hardcoded caps |
| 12-Factor (config via mount, stdout, no daemon) | CLEAN | mount is the sanctioned OAuth pattern (not a config-in-code violation); module is stdlib subprocess, no daemon/logfile; auth is env-layer (mount), never a code branch |
| cross-file contract (ctx.spec dict, shape access) | CLEAN | `ctx.spec` is the raw dict (`_build_env_content` uses `.get`); `shape = spec.get("shape") or {}` tolerates absent shape; `claude_cli_home` non-str is gated by the Pydantic `str` field upstream |
| ai/00 fleet reference (synced rule) | CLEAN | names `fabrik-lib/llm-dispatch` (a vendor target, not a project path) + `shape.uses_claude_cli`; `check_doc_links` green; backward-compatible (adds guidance, contradicts no pack) |
| behavior-without-a-test | **FIXED(2)** | see C/H above — both the both-mounts invariant and the deploy-path wiring now covered |

## Pass Ledger

```
Pass 1 — native Opus adversarial (pool empty) | found: 4 (A incomplete-mount-check · B missing --output-format ·
         C one-mount test · H no wiring test) + security note | fixed: 5 | → not done (changed code)
Pass 2 — native Opus confirming on the fix-delta | found: 0 | fixed: 0 | → EXIT (no-op; every checklist row
         CLEAN/FIXED; 108 deployer + 8 module tests pass; mypy clean; both regressions red-on-revert)
```

## Step verdict + gates

**Per-step verdict** (grounded at `path:line`): the mount validator (`deployer_ssh.py:618` `_assert_claude_cli_mounts`)
now requires both targets — FIXED; `call_claude_cli` (`llm_dispatch.py`) pins `--output-format text` — FIXED;
tests (`test_deployer_ssh.py` TestClaudeCliMounts + TestDeployLocal) cover both-mounts + wiring — FIXED. Every
Coverage Checklist row is CLEAN or FIXED.

```
python scripts/final_gate.py --check --json  →  {"status": "success"}
python -m pytest tests/orchestrator/test_deployer_ssh.py -q  →  108 passed
(fabrik-lib) python -m pytest llm-dispatch -q                →  8 passed
```

**Converged:** Pass 2 raised zero candidates and changed nothing; the last code-changing pass (Pass 1) was
re-confirmed by Pass 2. Total findings: **5 → 5 FIXED** (2 real correctness bugs A/B, 2 test-quality C/H, 1
fleet-lens security caution). No REFUTED (all raised findings were real).
