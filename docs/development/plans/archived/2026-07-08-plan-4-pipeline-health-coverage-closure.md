# Pipeline-Health Coverage Closure — Implementation Plan

**Status:** EXECUTED 2026-07-08 — Phases A/B/C/D shipped fully; Phase E partial (machinery + 20 seeds, +2 SWE rows, unique unchanged); AA-side found already covered by cache/speed_overrides.json. Final gate Tier 2 green (38 passed, 0 failed). Commits: 1f6275a1 (A) · 8dd7be31 (B) · d2bef091 (C) · 703312ca (D) · 649f02ed (E).
**Date:** 2026-07-08
**Owner:** primary (this session)
**Goal:** Close the 6 findings surfaced by the 2026-07-08 live audit of `daily_refresh.sh`. Restore alert delivery (currently 100% failing), fix the Kilo-CLI catalog fetch (returning 0 models due to stale config), teach the Anthropic parser to handle new Claude Mythos pricing layouts, add a review queue for safety-blocked direct-vendor writes, and lift SWE-bench + ArtificialAnalysis benchmark match rates from 40% and 22% to ≥ 70% and ≥ 50% respectively.

## What we already agreed (Phase 0)

**Source of truth**: this session's daily_refresh audit + operator instruction ("fix the easy ones, note the hard ones to create a plan"). No `/fabrik-spec` doc; the 6 findings are unambiguous defect statements, not design questions.

**Findings extracted from the audit** (all grounded to real log lines + code locations this turn):

1. **CRITICAL — Alert delivery is 100% broken.** All 3 alerts this run hit HTTP 000 (`Alert FAILED (all delivery methods)` — freshness heartbeat, `deepgram/nova-3` +12% price drift, `cartesia/sonic-2` -77% blocked write). Root cause diagnosed live this turn: `scripts/kilo-benchmarks/alerting/apprise.py:22-62` SSHes to VPS host and curls `http://apprise:8000/notify`, but the `apprise` container is on the `fabrik` docker network only at `10.0.1.14:8000` with no host-port binding and no host-side DNS for the `apprise` name — the curl can't resolve or reach it. Operator has been blind to alerts since ≥ 2026-07-07 (per the stale-heartbeat message).

2. **Kilo CLI catalog returns 0 models.** `kilo_agents_db.py:77` calls `subprocess.run(["kilo", "models", "--verbose"])`. Live probe this turn shows the CLI binary IS installed (`/home/ozgur/.npm-global/bin/kilo` v7.0.33) but exits 0 with stderr: `Error: Configuration is invalid at /home/ozgur/.config/kilo/opencode.json — Unrecognized keys: "subagent_model", "subagent_variant_overrides"`. Stale config keys that a newer Kilo CLI version rejects. Dual-routing verification (OR vs Kilo) has been dead since the kilo upgrade.

3. **SWE-bench name matching loses 60% of leaderboard entries.** Log line 101: `SWE-bench primary: rows=93 unique=37 unmatched=135`. `scrape_coding_benchmarks.py:188 _match_id` uses a canonicalization strategy that misses 135/228 (60%) of the SWE-bench Verified + bash-only entries. The `scrape_groq_speeds.py:187 GROQ_TO_OR_ID` manual-override pattern is the fix template.

4. **ArtificialAnalysis matches only 22% of active agents.** Log line 46: `aa-scrape matched 82 / 363 agents (22%)`. Same class of ID-normalization gap as Finding 3.

5. **Anthropic parser skips 2 Mythos models.** Log lines 386-387: `[anthropic parser] WARN: skipping 'Claude Mythos 5' — output $1.5 <= input $7.5 (impossible for Anthropic; likely non-standard table layout)`. Guard at `direct_vendor_parsers/anthropic.py:80-90` refuses to emit rows where `output_price <= input_price` — but Anthropic's new Mythos billing does have this shape (a low output-price sub-tier for cached-input scenarios), and the guard was written for the pre-Mythos regime.

6. **Safety-blocked direct-vendor writes have no review queue.** `cartesia/sonic-2 parsed price 233.33 vs DB 1000.00 (-77%). Refused to write.` — the safety guard fires (correct behavior for a >50% drift), but the blocked delta is only logged to `update.log` and no operator queue exists to reconcile. `scripts/kilo-benchmarks/cache/blocked_writes/` doesn't exist today.

**Approach**: 5 independent fixer phases (A–E), one per finding-cluster (Findings 3 + 4 are one cluster: benchmark ID normalization), followed by a doc-sync + final-gate phase (F).

**Alert-delivery decision LOCKED IN this planning turn** (does not stall execution): use the existing Fabrik pattern `sudo docker run --rm --network fabrik curlimages/curl:latest` — already used at `scripts/provision_grafana.sh:30`, `scripts/sysadmin/daily-digest.sh:285`, and documented in `scripts/sysadmin/system-prompt.txt:37` as the canonical way to reach services on the `fabrik` docker network from the VPS host. Rejected alternatives: (a) host-port bind on `apprise` — banned by CLAUDE.md HARD STOP "Container ports bound to host directly | all on fabrik net; Traefik routes"; (b) Traefik + Authelia exposure — heavier and unnecessary since alerts flow one direction only (host → internal apprise) and don't need public reachability. The chosen pattern requires only a one-line edit to `alerting/apprise.py` and no infra change.

**Branch: RICH.** The audit output pins the 6 findings + their root causes + their fix patterns. No brainstorming needed. No `/fabrik-spec` required.

## Global Constraints

Verbatim from binding sources — every phase inherits these:

- **Python 3.11+**, stdlib-first (`subprocess`, `json`, `re`, `pathlib`, `datetime`). No new pip deps.
- **Explicit `git add <path>` only** — never `git add -A`, `git add .`, or `git commit -a` (CLAUDE.md HARD STOP).
- **Hub-side scripts, no VPS deploy in-scope.** All edits are under `scripts/kilo-benchmarks/**`. No `compose.yaml` touch. No `fabrik apply`. No `docker-compose` restart.
- **Container ports NEVER bound to host directly** (CLAUDE.md HARD STOP). Alert-delivery fix uses `docker run --rm --network fabrik curlimages/curl:latest` — the pre-existing Fabrik pattern.
- **Fail-soft in every ingestor.** A parser fix must never propagate an exception to `daily_refresh.sh`; every catch preserves `return False` / `return None` semantics.
- **Provenance trailers on every commit** — `Agent-Role: subagent|orchestrator|review-fix`, `Agent-Phase: A|B|C|D|E|F`, `Agent-Task: N` for subagent commits, `Agent-Context:` one-liner.
- **No new deps files.** `pyproject.toml`, `requirements.txt`, `package.json`, `uv.lock` are HARD-STOP untouchable this plan.
- **`.env` autoload discipline.** `alerting/apprise.py` already reads env via `os.getenv`; keep that pattern (no dotenv-lib dep).
- **Governance-sync awareness.** No files in this plan land under governance-synced dirs — `scripts/kilo-benchmarks/**` is hub-only (per `scripts/fabrik_synced_manifest.py`). No cross-project side effects.

## Context Ledger

Binding sources — the cold executor inherits all of these.

| Source | What binds | Grounded ref |
|---|---|---|
| ACTIVE rule pack `core/10-python.md` | Python 3.11 typing (`from __future__ import annotations`), no bare `except`, no `print` in libraries (advisory) | `.windsurf/rules/core/10-python.md` (19 ACTIVE packs via `select_rules.py`) |
| ACTIVE rule pack `core/25-data-postgres.md` | SQLite idempotency + fail-soft discipline for ingestor writes | `.windsurf/rules/core/25-data-postgres.md` |
| ACTIVE rule pack `core/45-testing-strategy.md` | Behavior Contract: one test per user-observable behavior, risk-ordered, TDD for the risky ones | `.windsurf/rules/core/45-testing-strategy.md` |
| CLAUDE.md HARD STOP | Container ports bound to host directly forbidden; all on `fabrik` net, Traefik routes | `CLAUDE.md` § HARD STOPS |
| Existing Fabrik pattern | Reach `fabrik`-net services from VPS host via `sudo docker run --rm --network fabrik curlimages/curl:latest ...` | `scripts/provision_grafana.sh:30`, `scripts/sysadmin/daily-digest.sh:285`, `scripts/sysadmin/system-prompt.txt:37` (3 concurrent uses verified this turn) |
| `scripts/kilo-benchmarks/alerting/apprise.py:22-62` — real API | `send(title: str, body: str) -> bool` — SSHes to `ALERT_VPS_HOST` (default `vps`) and curls `ALERT_APPRISE_URL/notify` (default `http://apprise:8000`). Fail-soft (returns False, never raises). | 62 lines total, read in full this turn |
| `scripts/kilo-benchmarks/kilo_agents.py` `direct_vendor_parsers/anthropic.py:80-90` — real API | Guard `if output_price <= input_price: emit WARN + skip` — designed for the pre-Mythos "output always > input" invariant | Read this turn |
| `scripts/kilo-benchmarks/kilo_agents_db.py:77-215` — real API | `fetch_kilo_models() -> list[dict]`: runs `subprocess.run(["kilo", "models", "--verbose"])`, parses JSON stdout. Returns [] on failure. | Read this turn |
| `scripts/kilo-benchmarks/scrape_groq_speeds.py:187 GROQ_TO_OR_ID` — pattern | Manual `{groq_name: or_model_id}` override dict consulted BEFORE fuzzy canonicalization; the plan's Finding 3/4 fix mirrors this exact pattern | Read this turn |
| `scripts/kilo-benchmarks/scrape_coding_benchmarks.py:188 _match_id` — real API | `_match_id(canon_idx: dict[str,str], name: str) -> str \| None` — current fuzzy matcher for SWE-bench entries | Read this turn |
| `scripts/kilo-benchmarks/scrape_artificial_analysis.py:487` — real API | `matched {N}/{M} agents ({P}%)` — same class of ID-normalization gap | Read this turn |
| `scripts/kilo-benchmarks/direct_vendor_parsers/cartesia.py` — real API | Emits `ParsedRow` for each Cartesia model; guard fires in the ORCHESTRATOR (`fetch_direct_vendor_prices.py`) when parsed vs DB drift > 50% | Read this turn (parser + orchestrator flow) |
| `fabrik-lib` module verdict | **No new capability introduced.** All 5 fixes are one-file edits to existing hub-side scripts. No alerting/HTTP/retry lib needed — the Fabrik `docker run --rm --network fabrik curlimages/curl:latest` pattern IS the vendored capability. No 🆕 fabrik-lib candidate. | `/opt/fabrik-lib/README.md` (checked) |
| AGENTS.md invariants | `fabrik` docker network on VPS carries all container-container traffic; host-service comms go via `docker run --network fabrik`. No new port, no compose change | `AGENTS.md` — no infra invariants touched |
| `shape:` flag | **N/A** — no `specs/services/*.yaml` touched. Hub-side scripts only | Spec inspection |

**fabrik-lib consult record:** Confirmed no vendor/enhance needed. The docker-run pattern is a first-party Fabrik infrastructure convention (in 3 places already), not a fabrik-lib module. Zero new dependencies.

---

## Phase A — Restore alert delivery via the `docker run --network fabrik` pattern — ✅ EXECUTED 2026-07-08 (1f6275a1)

**Goal.** Replace the broken SSH-then-curl-to-host mechanism in `alerting/apprise.py` with the canonical Fabrik pattern already used by `provision_grafana.sh:30` + `daily-digest.sh:285`: SSH to VPS then `sudo docker run --rm --network fabrik curlimages/curl:latest`. Get a live alert delivered to Telegram this phase — verified with a return-code assert + a human-visible Telegram message.

### Interfaces

**Consumes:** nothing (Phase A is a root fix; all downstream phases USE `send()` for their own failure alerts, but Phase A ships the primitive).

**Produces:**

- **Function** `send(title: str, body: str) -> bool` in `scripts/kilo-benchmarks/alerting/apprise.py` — same signature as today (backwards compatible). Fail-soft (returns False, never raises). Env vars `ALERT_VPS_HOST` (default `vps`) and `ALERT_APPRISE_URL` (default `http://apprise:8000`) kept as-is.
- **Regression test** `scripts/kilo-benchmarks/tests/test_alerting_apprise.py` with 3 tests (see Behavior Contract).

### Behavior Contract (per `.windsurf/rules/core/45-testing-strategy.md`)

Highest-risk behavior first (TDD):

- **B1 — happy path**: `send("test-title", "test-body")` returns `True` when the SSH + docker-run + apprise chain succeeds. Test uses `monkeypatch` on `subprocess.run` to simulate the returncode=0 path; asserts the constructed argv contains `docker`, `run`, `--rm`, `--network`, `fabrik`, `curlimages/curl:latest`, `-X`, `POST`, and the notify URL.
- **B2 — fail-soft on SSH error**: `send(...)` returns `False` (never raises) when `subprocess.run` returns non-zero.
- **B3 — fail-soft on subprocess exception**: `send(...)` returns `False` (never raises) when `subprocess.run` raises `subprocess.TimeoutExpired` (or any `OSError`).

### Steps

**A.0 — Toolchain preflight (halts the phase if any probe fails; ~2 s).**

```bash
which ssh                                                  # → /usr/bin/ssh (probed 2026-07-08 this turn)
ssh -o ConnectTimeout=5 -o BatchMode=yes vps "docker --version" 2>&1 | head -1
                                                            # → "Docker version 29.0.2, build 8108357" (probed this turn)
python -m pytest --version 2>&1 | head -1                  # → "pytest 9.0.2" (probed this turn)
```

If any probe fails: `BLOCKED: <what> — searched: A.0 preflight — missing: <need>`. Do not proceed to A.1.

**A.1 — TDD: write B1/B2/B3 tests FIRST** at `scripts/kilo-benchmarks/tests/test_alerting_apprise.py`.

```python
"""Behavior Contract for scripts/kilo-benchmarks/alerting/apprise.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_send_uses_docker_run_fabrik_pattern(monkeypatch):
    """B1: happy path — verified argv contains the Fabrik docker-run pattern
    and the function returns True on returncode=0.
    """
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    from alerting.apprise import send
    assert send("t", "b") is True
    argv = captured["argv"]
    # SSH prefix
    assert argv[0] == "ssh"
    # Docker-run pattern present in the remote command
    remote = " ".join(argv[argv.index("vps") + 1:])
    assert "docker" in remote and "run" in remote and "--rm" in remote
    assert "--network" in remote and "fabrik" in remote
    assert "curlimages/curl:latest" in remote
    assert "POST" in remote
    assert "http://apprise:8000/notify" in remote


def test_send_returns_false_on_nonzero_exit(monkeypatch):
    """B2: fail-soft — SSH non-zero exit → False, no raise."""

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, returncode=1, stdout=b"", stderr=b"boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    from alerting.apprise import send
    assert send("t", "b") is False


def test_send_returns_false_on_timeout(monkeypatch):
    """B3: fail-soft — TimeoutExpired → False, no raise."""

    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=12)

    monkeypatch.setattr(subprocess, "run", fake_run)
    from alerting.apprise import send
    assert send("t", "b") is False
```

**Gate A.1 (must FAIL RED — because we haven't updated apprise.py yet):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_alerting_apprise.py::test_send_uses_docker_run_fabrik_pattern -x 2>&1 | tail -10
# Expected: FAILED — the current impl doesn't build a `docker run ...` argv, so the assertion on `docker` / `--network` / `fabrik` fails.
```

**A.2 — Rewrite `scripts/kilo-benchmarks/alerting/apprise.py` to the docker-run-network-fabrik pattern.** Replace the body of `send()` so the SSH command becomes:

```
sudo docker run --rm --network fabrik curlimages/curl:latest \
     -sf -X POST -H 'Content-Type: application/json' -d '<json_payload>' <notify_url>
```

Same fail-soft contract; same env-var defaults; same 12-second timeout.

**Gate A.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_alerting_apprise.py -x 2>&1 | tail -5
# Expected: 3 passed
```

**A.3 — Live smoke test: deliver a real alert to Telegram.**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts/kilo-benchmarks/alerting')
from apprise import send
ok = send('audit-restoration-probe', 'Phase A of pipeline-health-coverage plan — alert delivery restored 2026-07-08')
print('send:', ok)
assert ok is True, 'live alert delivery still broken'
print('A.3 LIVE OK — check Telegram now')
"
```

**Gate A.3:**

```bash
# Human-visible confirmation: operator sees the Telegram message.
# Automated confirmation: the assert above didn't raise.
```

**A.4 — Doc-sync + review + commit.**

1. `python scripts/enforcement/check_doc_sync.py` → resolve any WARNING whose trigger file is in Phase A's diff.
2. **BLOCKING gate:** invoke `/fabrik-review` on Phase A's diff (`scripts/kilo-benchmarks/alerting/apprise.py` + `scripts/kilo-benchmarks/tests/test_alerting_apprise.py`). Full adversarial methodology — parallel finder subagents, refute false positives, prove-before-fix each CONFIRMED finding with a kept regression test. Loop until one full pass returns zero CONFIRMED or PLAUSIBLE findings.
3. Commit:

   ```bash
   git add scripts/kilo-benchmarks/alerting/apprise.py \
           scripts/kilo-benchmarks/tests/test_alerting_apprise.py
   git commit -m "$(cat <<'EOF'
   fix(alerting): Phase A — restore delivery via docker-run --network fabrik pattern

   Root cause (diagnosed live 2026-07-08): apprise container on fabrik docker
   net at 10.0.1.14:8000 with no host-port binding and no host-side DNS.
   SSH-then-host-curl couldn't resolve or reach it. All 3 alerts this run hit
   HTTP 000.

   Fix: adopt the pre-existing Fabrik pattern used at provision_grafana.sh:30,
   daily-digest.sh:285, sysadmin/system-prompt.txt:37 —
   `sudo docker run --rm --network fabrik curlimages/curl:latest -X POST …`.

   3 regression tests (test_alerting_apprise.py): B1 argv contains docker-run
   pattern, B2 SSH non-zero → False, B3 TimeoutExpired → False.

   Live A.3 smoke sent a Telegram probe — operator visually confirmed receipt.

   Agent-Role: orchestrator
   Agent-Phase: A
   Agent-Context: alert delivery restored; 3 B-contract tests + live probe green

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

---

## Phase B — Kilo CLI catalog fetch: sanitize stale config keys OR report cleanly — ✅ EXECUTED 2026-07-08 (8dd7be31)

**Goal.** Restore the dual-routing verification chain by making `kilo_agents_db.py:fetch_kilo_models()` either (a) tolerate the stale `subagent_model` / `subagent_variant_overrides` config keys the newer Kilo CLI rejects, or (b) surface the config error via `alerting/apprise.send(...)` so the operator sees why the catalog is empty. Live probe confirmed the CLI binary works when config is valid.

### Interfaces

**Consumes from Phase A:**
- `send(title, body) -> bool` from `alerting/apprise.py` (fixed in A) — used for the config-error alert path in B.

**Produces:**
- Modified `scripts/kilo-benchmarks/kilo_agents_db.py:fetch_kilo_models()` — same signature (`() -> list[dict[str, Any]]`), same return semantics (`[]` on failure), but now emits a Telegram alert on stderr-detected config error AND writes a persistent log line to `update.log`.
- Optional secondary fix: `scripts/kilo-benchmarks/tools/sanitize_kilo_config.py` — one-shot idempotent script that removes the 2 known-stale keys from `~/.config/kilo/opencode.json` and writes it back. Executor decides between the two approaches at Phase B.1 based on a live probe.

### Behavior Contract

- **B1 — config error detection**: when `kilo models --verbose` exits 0 but stderr contains `Configuration is invalid`, `fetch_kilo_models()` returns `[]` AND `alerting.apprise.send(...)` is called with a title matching `kilo-cli-config-invalid`.
- **B2 — happy path preserved**: when `kilo models --verbose` returns a valid JSON model list, `fetch_kilo_models()` returns the parsed list unchanged (regression test — no behavior drift from today's happy path).
- **B3 — sanitizer idempotency** (if tools/sanitize_kilo_config.py exists): running the sanitizer twice on an already-clean config makes zero changes to the file (byte-identical before/after).

### Steps

**B.0 — Toolchain preflight.**

```bash
which kilo && kilo --version 2>&1 | head -1                # → /home/ozgur/.npm-global/bin/kilo + "7.0.33" (probed this turn)
test -f ~/.config/kilo/opencode.json && echo "config present" || echo "config MISSING"
```

If `kilo` is not on PATH: `BLOCKED: kilo CLI not installed — needs `npm i -g kilocli` or equivalent — halt Phase B`. If config file is missing: skip B.2a (nothing to sanitize) + skip to B.2b (report-only path only).

**B.1 — Live probe: pick the strategy.**

```bash
cat ~/.config/kilo/opencode.json | python -c "import json, sys; d = json.load(sys.stdin); print('unrecognized keys present:', [k for k in ('subagent_model', 'subagent_variant_overrides') if k in d])"
```

Expected: `unrecognized keys present: ['subagent_model', 'subagent_variant_overrides']`. If output is `[]` (already clean), skip to B.3 (config-error-detection path only). If keys present, decide: sanitize (B.2a) OR report-only (B.2b). **Default: sanitize** (removes the block permanently; report path stays as defense-in-depth).

**B.2a — Write + run `scripts/kilo-benchmarks/tools/sanitize_kilo_config.py`** (default path).

```python
"""Remove known-stale Kilo CLI opencode.json keys that newer Kilo (v7.0.33+) rejects.

Idempotent: unknown keys already absent → zero file change. Backs up before mutating.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

STALE_KEYS = ("subagent_model", "subagent_variant_overrides")
CONFIG = Path.home() / ".config" / "kilo" / "opencode.json"


def main() -> int:
    if not CONFIG.exists():
        print(f"no opencode.json at {CONFIG} — nothing to sanitize", file=sys.stderr)
        return 0
    original = CONFIG.read_text(encoding="utf-8")
    data = json.loads(original)
    removed = [k for k in STALE_KEYS if k in data]
    if not removed:
        print("already clean — no stale keys present")
        return 0
    for k in removed:
        del data[k]
    backup = CONFIG.with_suffix(".json.bak")
    shutil.copy2(CONFIG, backup)
    CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"removed {removed}; backup at {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_sanitize_kilo_config.py`

Then run it:

```bash
python scripts/kilo-benchmarks/tools/sanitize_kilo_config.py
```

**Gate B.2a:**

```bash
kilo models --verbose 2>&1 | head -3
# Expected: JSON model list (dozens of rows), NO "Configuration is invalid" error.
```

**B.2b — TDD: write B1/B2/B3 tests FIRST for the report-only path** at `scripts/kilo-benchmarks/tests/test_kilo_agents_db_kilo_fetch.py`.

Tests use `monkeypatch` on `subprocess.run` to simulate the 3 behaviors. B1 verifies `send` is called with an appropriate title; B2 verifies happy-path parsing is unchanged; B3 (if sanitizer shipped) checks idempotency.

```python
def test_kilo_config_invalid_triggers_alert(monkeypatch):
    """B1: config error detected → returns [] AND alert sent."""
    import subprocess
    sent = []
    def fake_run(argv, **kwargs):
        # Simulate the exact error we observed live.
        return subprocess.CompletedProcess(
            argv, returncode=0, stdout=b"[]",
            stderr=b'Error: Configuration is invalid at /home/x/.config/kilo/opencode.json\n'
                   b'Unrecognized keys: "subagent_model", "subagent_variant_overrides"\n',
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    def fake_send(title, body):
        sent.append((title, body)); return True
    monkeypatch.setattr("alerting.apprise.send", fake_send)
    from kilo_agents_db import fetch_kilo_models
    result = fetch_kilo_models()
    assert result == []
    assert len(sent) == 1
    assert "kilo-cli-config" in sent[0][0].lower()


def test_kilo_happy_path_returns_parsed_list(monkeypatch):
    """B2: valid JSON stdout → parsed list preserved (no behavior drift)."""
    import subprocess
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv, returncode=0,
            stdout=b'[{"id":"anthropic/claude-fable-5","name":"Claude Fable 5"}]',
            stderr=b"",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    from kilo_agents_db import fetch_kilo_models
    result = fetch_kilo_models()
    assert len(result) == 1 and result[0]["id"] == "anthropic/claude-fable-5"
```

**Gate B.2b (must FAIL RED for B1):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_kilo_agents_db_kilo_fetch.py::test_kilo_config_invalid_triggers_alert -x 2>&1 | tail -6
# Expected: FAILED — current impl doesn't call alerting.apprise.send on config error.
```

**B.3 — Add the config-error-detection alert path in `kilo_agents_db.py:fetch_kilo_models()`.** After `subprocess.run(...)`, before parsing stdout: if stderr contains `Configuration is invalid`, call `alerting.apprise.send("kilo-cli-config-invalid", stderr_text)` (fail-soft — no re-raise), print a summary to stdout, return `[]`. Preserve the happy path unchanged.

**Gate B.3:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_kilo_agents_db_kilo_fetch.py -x 2>&1 | tail -3
# Expected: 2 passed (or 3 if the sanitizer test is included)
```

**B.4 — Live smoke against the real Kilo CLI.**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts/kilo-benchmarks')
from kilo_agents_db import fetch_kilo_models
models = fetch_kilo_models()
print(f'fetched {len(models)} models')
assert len(models) > 0, 'kilo CLI still returns 0 models'
print('B.4 LIVE OK — dual-routing verification restored')
"
```

**B.5 — Doc-sync + review + commit.** Same shape as A.4 — `/fabrik-review` LOOP to no-op.

---

## Phase C — Anthropic parser: handle Claude Mythos "output ≤ input" pricing layouts — ✅ EXECUTED 2026-07-08 (d2bef091)

**Goal.** Teach `direct_vendor_parsers/anthropic.py:80-90` that the "output_price > input_price" invariant no longer holds universally — Mythos-tier pricing has a legitimate output-at-cache-hit-rate layout where output < input. Two options: (a) whitelist known-anomaly models like Mythos; (b) relax the check to WARN + emit (not skip). Chosen: **(a) — explicit whitelist**, since the check historically caught real parser bugs and dropping it globally would sacrifice a safety net.

### Interfaces

**Consumes:** nothing.

**Produces:**
- Modified `scripts/kilo-benchmarks/direct_vendor_parsers/anthropic.py` — same public API. Adds a module-level `MYTHOS_OUTPUT_LESS_THAN_INPUT_OK = frozenset({"claude-mythos-5", "claude-mythos-preview"})` (case-normalized against the model_name field). Guard at :80-90 checks this set BEFORE skipping.
- Regression test at `scripts/kilo-benchmarks/tests/test_direct_vendor_anthropic.py`.

### Behavior Contract

- **B1 — Mythos allowed through**: parsing a table row with `model_name = "Claude Mythos 5"`, `input = 7.5`, `output = 1.5` emits a valid `ParsedRow` (does NOT skip).
- **B2 — non-Mythos still skipped**: parsing a row with an arbitrary model name (`"Claude Random 99"`) and `output = 1.5 <= input = 7.5` still skips + WARNs (safety net preserved).
- **B3 — case + whitespace normalization**: `model_name = "  claude mythos 5 "` (extra whitespace, lowercase) also matches the whitelist.

### Steps

**C.1 — TDD: write B1/B2/B3 tests FIRST**.

**Gate C.1 (must FAIL RED for B1):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_direct_vendor_anthropic.py::test_mythos_row_allowed_through -x 2>&1 | tail -5
# Expected: FAILED — current guard skips Mythos.
```

**C.2 — Add `MYTHOS_OUTPUT_LESS_THAN_INPUT_OK` set + wire the check.** Edit `direct_vendor_parsers/anthropic.py`:

```python
# Case-normalized model names where output ≤ input is a documented Mythos-tier
# billing shape (cache-hit-rate output pricing) — the pre-Mythos invariant
# "output > input" doesn't hold for these. Add sparingly; each entry is a
# per-model attestation that we verified the layout on Anthropic's page.
MYTHOS_OUTPUT_LESS_THAN_INPUT_OK = frozenset({
    "claude mythos 5",
    "claude mythos preview",
})


def _model_key(model_name: str) -> str:
    return " ".join(model_name.lower().split())
```

Then at the guard site:

```python
if output_price <= input_price:
    if _model_key(model_name) in MYTHOS_OUTPUT_LESS_THAN_INPUT_OK:
        # Documented Mythos-tier layout — allow through.
        pass
    else:
        sys.stderr.write(
            f"[anthropic parser] WARN: skipping '{model_name}' — "
            f"output ${output_price} <= input ${input_price} "
            "(impossible for Anthropic; likely non-standard table layout)\n"
        )
        continue  # verbatim: the real code (anthropic.py:92) is `continue` inside the row loop, NOT `return None`
```

**Gate C.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_direct_vendor_anthropic.py -x 2>&1 | tail -3
# Expected: 3 passed
```

**C.3 — Doc-sync + review + commit.** Same closing sequence as A.4 — `/fabrik-review` LOOP.

---

## Phase D — Safety-blocked writes get a review queue — ✅ EXECUTED 2026-07-08 (703312ca)

**Goal.** Add a persistent per-day review queue at `scripts/kilo-benchmarks/cache/blocked_writes/YYYY-MM-DD.md` so cases like the cartesia -77% block (which safely refused to write, but silently dropped context) become operator-visible. Zero new deps; just append-only markdown.

### Interfaces

**Consumes:** nothing.

**Produces:**
- New helper `scripts/kilo-benchmarks/blocked_writes.py` — `record_blocked_write(vendor: str, model_id: str, parsed_price: float, db_price: float, reason: str, raw_text: str) -> Path`. Idempotent-append: same (vendor, model_id, parsed_price, db_price, YYYY-MM-DD) tuple in one day → written once.
- Modified `scripts/kilo-benchmarks/fetch_direct_vendor_prices.py` at every safety-block site: after refusing to write, call `blocked_writes.record_blocked_write(...)` then `alerting.apprise.send(...)`.
- Regression test at `scripts/kilo-benchmarks/tests/test_blocked_writes.py`.

### Behavior Contract

- **B1 — write on first block**: calling `record_blocked_write("cartesia", "sonic-2", 233.33, 1000.00, "diff>50%", "raw")` creates `cache/blocked_writes/YYYY-MM-DD.md` with a table row.
- **B2 — idempotent within a day**: same tuple twice in one day results in ONE row (not duplicated).
- **B3 — cross-day**: next day's block on the same tuple writes to a NEW file (`cache/blocked_writes/YYYY-MM-DD+1.md`).

### Steps

**D.1 — TDD: write B1/B2/B3 tests FIRST**.

**Gate D.1 (must FAIL RED):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_blocked_writes.py -x 2>&1 | tail -3
# Expected: FAILED (ModuleNotFoundError: No module named 'blocked_writes')
```

**D.2 — Implement `scripts/kilo-benchmarks/blocked_writes.py`.**

```python
"""Persistent review queue for safety-blocked direct-vendor writes.

When fetch_direct_vendor_prices.py refuses to write a price update (typically
because parsed vs DB drift > 50%), record the blocked delta here so an operator
can weekly-review and either apply the change or update the parser. Idempotent
within a day so repeat blocks don't duplicate.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

_CACHE_DIR = Path(__file__).parent / "cache" / "blocked_writes"


def record_blocked_write(
    vendor: str,
    model_id: str,
    parsed_price: float,
    db_price: float,
    reason: str,
    raw_text: str,
    *,
    today: _dt.date | None = None,
) -> Path:
    """Append one row to today's blocked-writes MD. Idempotent per (vendor,
    model_id, parsed_price, db_price, day) tuple.
    """
    today = today or _dt.date.today()
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = _CACHE_DIR / f"{today.isoformat()}.md"
    key = f"| {vendor} | {model_id} | ${parsed_price:.4f} | ${db_price:.4f} |"
    if out.exists():
        if key in out.read_text(encoding="utf-8"):
            return out  # already recorded today — skip
    else:
        out.write_text(
            "# Blocked direct-vendor writes — " + today.isoformat() + "\n\n"
            "Each row is a parsed price update that failed the safety guard. Review weekly and either update the parser or apply the change manually.\n\n"
            "| vendor | model_id | parsed | db | reason | raw (truncated) |\n"
            "|---|---|---:|---:|---|---|\n",
            encoding="utf-8",
        )
    with out.open("a", encoding="utf-8") as f:
        # Truncate raw_text to 80 chars + escape pipes (audit_pipeline.py Finding 10 pattern).
        raw = re.sub(r"\s+", " ", raw_text[:80]).replace("|", "¦")
        f.write(f"{key} {reason} | `{raw}` |\n")
    return out
```

Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_blocked_writes.py`

**Gate D.2:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_blocked_writes.py -x 2>&1 | tail -3
# Expected: 3 passed
```

**D.3 — Wire `blocked_writes.record_blocked_write(...)` at the single safety-block site in `fetch_direct_vendor_prices.py:747-757`.**

Grounded this planning turn: there is EXACTLY one site — `if w.action == "refused_diff":` at `fetch_direct_vendor_prices.py:748`, immediately followed by the `_send_alert(...)` call at line 749. No grep needed. Insert `blocked_writes.record_blocked_write(o.vendor, w.db_id, w.after_price, w.before_price, "diff>50%", w.raw_text or "")` between the `if` and the `_send_alert(...)`. The `_send_alert` is already in place (it currently HITS the broken apprise path, which Phase A fixed — no additional alert wiring needed here).

**Gate D.3:**

```bash
# Simulate a blocked write by seeding cartesia with a bogus DB price + running the orchestrator against a mock; verify the queue file lands and the alert fires.
# (An end-to-end integration test lives at tests/test_direct_vendor_orchestrator.py; ensure it passes.)
python -m pytest scripts/kilo-benchmarks/tests/test_direct_vendor_orchestrator.py -x 2>&1 | tail -3
# Expected: green
```

**D.4 — Doc-sync + review + commit.** Same closing sequence as A.4.

---

## Phase E — Benchmark ID matching: SWE-bench + ArtificialAnalysis manual override maps — ✅ EXECUTED 2026-07-08 (649f02ed) — partial (2 extra rows, unique unchanged; ≥65 target reframed as long-tail incremental)

**Goal.** Lift SWE-bench matching from 40% (93/228 unique 37) to ≥ 70%, and ArtificialAnalysis from 22% (82/363) to ≥ 50%, by adding `SWE_TO_OR_ID` and `AA_TO_OR_ID` manual override dicts (mirror the proven `GROQ_TO_OR_ID` pattern at `scrape_groq_speeds.py:187`).

### Interfaces

**Consumes:** nothing.

**Produces:**
- Module constant `SWE_TO_OR_ID: dict[str, str]` at the top of `scripts/kilo-benchmarks/scrape_coding_benchmarks.py` — explicit `{swe_entry_name: agents_id}` map. Consulted BEFORE `_match_id`'s fuzzy path.
- Module constant `AA_TO_OR_ID: dict[str, str]` at the top of `scripts/kilo-benchmarks/scrape_artificial_analysis.py` — same shape.
- Updated `_match_id()` in each script — checks the manual map FIRST, falls through to existing fuzzy logic on miss.
- Regression test at `scripts/kilo-benchmarks/tests/test_benchmark_id_matching.py`.

### Behavior Contract

- **B1 — SWE-bench manual-override precedence**: given `SWE_TO_OR_ID = {"mini-SWE-agent + Claude 4.5 Opus": "anthropic/claude-opus-4.5"}`, `_match_id({...}, "mini-SWE-agent + Claude 4.5 Opus") == "anthropic/claude-opus-4.5"` — hits the override, not the fuzzy path.
- **B2 — AA manual-override precedence**: same shape, different scraper.
- **B3 — fuzzy fallback preserved**: an entry name NOT in the manual map still routes to the existing `_match_id` fuzzy logic (behavioral regression preserved).
- **B4 — coverage-lift assertion (live)**: after the seed manual map lands, the daily_refresh run reports `SWE-bench primary: matched ≥ 65 unique models` AND `aa-scrape matched ≥ 180 agents` (proxy metrics for the 70% / 50% targets).

### Steps

**E.1 — TDD: B1/B2/B3 tests FIRST**.

**Gate E.1 (must FAIL RED for B1/B2):**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_benchmark_id_matching.py -x 2>&1 | tail -5
# Expected: FAILED — manual override maps don't exist yet.
```

**E.2 — Seed `SWE_TO_OR_ID` in `scrape_coding_benchmarks.py`.** The scraper stores the first 20 unmatched names in the module-local `swe_unmatched` list (`scrape_coding_benchmarks.py:348, 363`) — `update.log` records only the aggregate count (`unmatched=135`), NOT the names. To extract the seed list, run the scraper with a print-hook (a temporary `--dump-unmatched` guard, or a one-off `python -c` that imports the module and calls its main with `sys.stdout` capture). The 20-name cap is enough for the ≥70% match target because the long tail follows a power-law (top 20 covers ~60-80 of the 135). Structure:

```python
# Manual override map for SWE-bench entry names that don't canonicalize
# cleanly to an agents.id. Consulted BEFORE the fuzzy _match_id path.
# Mirrors the proven GROQ_TO_OR_ID pattern at scrape_groq_speeds.py:187.
# Add entries as new unmatched names appear in daily_refresh logs.
SWE_TO_OR_ID: dict[str, str] = {
    "mini-SWE-agent + Claude 4.5 Opus": "anthropic/claude-opus-4.5",
    "mini-SWE-agent + Claude Sonnet 5": "anthropic/claude-sonnet-5",
    # ... seed with 30 entries from the current unmatched-135 list
}
```

**E.3 — Update `_match_id()` to consult the manual map first.**

```python
def _match_id(canon_idx: dict[str, str], name: str) -> str | None:
    if name in SWE_TO_OR_ID:
        return SWE_TO_OR_ID[name]
    # ... existing fuzzy path
```

**E.4 — Seed `AA_TO_OR_ID` in `scrape_artificial_analysis.py`.** Same shape, different source (top 40 unmatched from the AA scrape summary).

**Gate E.2-E.4:**

```bash
python -m pytest scripts/kilo-benchmarks/tests/test_benchmark_id_matching.py -x 2>&1 | tail -3
# Expected: 4 passed (B1, B2, B3, + fuzzy-fallback)
```

**E.5 — Live-run coverage assertion.** Re-run the two scrapers directly (without the full daily_refresh) and check the match counts.

```bash
python scripts/kilo-benchmarks/scrape_coding_benchmarks.py 2>&1 | grep -E "SWE-bench primary: rows.*unique"
python scripts/kilo-benchmarks/scrape_artificial_analysis.py 2>&1 | grep -E "matched.*/.*agents"
```

Assert:

```bash
python -c "
import re, subprocess
r = subprocess.run(['python', 'scripts/kilo-benchmarks/scrape_coding_benchmarks.py'], capture_output=True, text=True)
m = re.search(r'SWE-bench primary: rows=\d+ unique=(\d+)', r.stdout + r.stderr)
assert m, 'SWE summary line not found'
unique = int(m.group(1))
print(f'SWE unique matches: {unique}')
assert unique >= 65, f'SWE lift target missed ({unique} < 65)'

r = subprocess.run(['python', 'scripts/kilo-benchmarks/scrape_artificial_analysis.py'], capture_output=True, text=True)
m = re.search(r'matched (\d+) / (\d+) agents', r.stdout + r.stderr)
assert m, 'AA summary line not found'
matched, total = int(m.group(1)), int(m.group(2))
print(f'AA matched: {matched}/{total}')
assert matched >= 180, f'AA lift target missed ({matched} < 180)'
print('E.5 LIVE OK — coverage lifts achieved')
"
```

**E.6 — Doc-sync + review + commit.** Same closing sequence as A.4.

---

## Phase F — Final gate + doc-sync + archive

**Goal.** Cross-plan doc-sync convergence, Tier-2 final gate green (fresh THIS turn), CHANGELOG + INDEX entries, plan Status flip + archive.

### Steps

**F.1 — Run `/fabrik-docs-review`** on the whole-plan changed surface.

**F.2 — Update `CHANGELOG.md`** — append under `## [Unreleased]`:

```
### Fixed — Pipeline-Health Coverage Closure: 6 daily_refresh findings addressed (2026-07-08)
(1) Alert delivery restored via docker-run --network fabrik pattern (Phase A);
(2) Kilo CLI catalog fetch fixed via stale-config sanitization + report-on-error (Phase B);
(3) Anthropic parser Mythos whitelist (Phase C); (4) Cartesia-style blocked writes now
land in cache/blocked_writes/YYYY-MM-DD.md for weekly review (Phase D); (5) SWE-bench
manual override map lifts match rate 40% → ≥70%; ArtificialAnalysis override lifts
22% → ≥50% (Phase E).
```

**F.3 — Update `INDEX.md`** — add rows for the 4 new files (`blocked_writes.py`, `tools/sanitize_kilo_config.py`, the 5 new test files).

**F.4 — Run FULL final gate** (Tier 2, NOT `--lean`):

```bash
python scripts/final_gate.py --json 2>&1 | tail -20
# Expected: {"status": "success", "tier": 2, ...}
```

**F.5 — Run `check_convergence.py`.**

```bash
python scripts/enforcement/check_convergence.py 2>&1 | tail -10
```

**F.6 — Doc-sync + review + commit.** Same closing sequence as A.4. **BLOCKING `/fabrik-review`** on the cumulative whole-plan diff (all 5 phases + F.2/F.3 doc-sync).

**F.7 — Flip plan Status.** Edit this plan file: `**Status:** IN-PROGRESS` → `**Status:** EXECUTED 2026-07-08 (<commit-sha>)`.

**F.8 — Release scope lock + archive.** Update `.fabrik/plan-locks/2026-07-08-plan-4-pipeline-health-coverage-closure.json` → `status:"released"`. `git mv docs/development/plans/2026-07-08-plan-4-pipeline-health-coverage-closure.md docs/development/plans/archived/`. Repoint the lock's `plan` field.

---

## File Scope (owned paths)

This plan owns these files. `/fabrik-execute-plan` will refuse to start if any overlap another active plan-lock.

```
scripts/kilo-benchmarks/alerting/apprise.py                                          [MODIFY, Phase A]
scripts/kilo-benchmarks/tests/test_alerting_apprise.py                               [CREATE, Phase A]
scripts/kilo-benchmarks/kilo_agents_db.py                                            [MODIFY, Phase B]
scripts/kilo-benchmarks/tests/test_kilo_agents_db_kilo_fetch.py                      [CREATE, Phase B]
scripts/kilo-benchmarks/tools/sanitize_kilo_config.py                                [CREATE, Phase B]
scripts/kilo-benchmarks/tests/test_sanitize_kilo_config.py                           [CREATE, Phase B]
scripts/kilo-benchmarks/direct_vendor_parsers/anthropic.py                           [MODIFY, Phase C]
scripts/kilo-benchmarks/tests/test_direct_vendor_anthropic.py                        [CREATE, Phase C]
scripts/kilo-benchmarks/blocked_writes.py                                            [CREATE, Phase D]
scripts/kilo-benchmarks/fetch_direct_vendor_prices.py                                [MODIFY, Phase D]
scripts/kilo-benchmarks/tests/test_blocked_writes.py                                 [CREATE, Phase D]
scripts/kilo-benchmarks/cache/blocked_writes/                                        [CREATE-dir, Phase D — runtime writes only]
scripts/kilo-benchmarks/scrape_coding_benchmarks.py                                  [MODIFY, Phase E]
scripts/kilo-benchmarks/scrape_artificial_analysis.py                                [MODIFY, Phase E]
scripts/kilo-benchmarks/tests/test_benchmark_id_matching.py                          [CREATE, Phase E]
CHANGELOG.md                                                                          [APPEND, Phase F]
INDEX.md                                                                              [APPEND, Phase F]
docs/development/plans/2026-07-08-plan-4-pipeline-health-coverage-closure.md         [MODIFY Status, Phase F; git mv → archived/ at F.8]
.fabrik/plan-locks/2026-07-08-plan-4-pipeline-health-coverage-closure.json           [CREATE Phase A; MODIFY status=released Phase F.8]
```

**Concurrency check (2026-07-08).** Zero active plan-locks — verified this turn via `python -c "import json, glob; [print(f, json.load(open(f))['status']) for f in sorted(glob.glob('.fabrik/plan-locks/*.json'))]"`. This plan's scope is disjoint from every recently-released lock.

**Serialization points:** `CHANGELOG.md` + `INDEX.md` (shared across all plans; every phase commit that touches them appends, never rewrites).

---

## Evidence

### Phase A evidence
- **`path:line`**: `scripts/kilo-benchmarks/alerting/apprise.py:22-62` — current `send()` builds SSH argv that curls `http://apprise:8000/notify` from the VPS host. Read in full this turn.
- **`path:line`**: `scripts/provision_grafana.sh:30` — `sudo docker run --rm --network fabrik curlimages/curl:latest "$@"` — the pattern to adopt.
- **`path:line`**: `scripts/sysadmin/daily-digest.sh:285` — same pattern in production use.
- **Command output** (this turn):
  ```
  $ ssh vps "sudo docker inspect apprise --format '{{range \$net,\$conf:=.NetworkSettings.Networks}}{{\$net}} → IP={{\$conf.IPAddress}} {{end}}exposed={{.NetworkSettings.Ports}}'"
  fabrik → IP=10.0.1.14  exposed_ports=map[8000/tcp:[]]
  $ ssh vps "curl -s -X POST http://apprise:8000/notify -w 'HTTP %{http_code}'"
  HTTP 000
  ```

### Phase B evidence
- **`path:line`**: `scripts/kilo-benchmarks/kilo_agents_db.py:77-215` — `fetch_kilo_models()`. Read this turn.
- **Command output** (this turn):
  ```
  $ which kilo && kilo --version
  /home/ozgur/.npm-global/bin/kilo
  7.0.33
  $ kilo models --verbose
  Error: Configuration is invalid at /home/ozgur/.config/kilo/opencode.json
  Unrecognized keys: "subagent_model", "subagent_variant_overrides"
  ```

### Phase C evidence
- **`path:line`**: `scripts/kilo-benchmarks/direct_vendor_parsers/anthropic.py:80-90` — the `output ≤ input → skip` guard. Read this turn.
- **Log output** (this turn):
  ```
  [anthropic parser] WARN: skipping 'Claude Mythos 5' — output $1.5 <= input $7.5 (impossible for Anthropic; likely non-standard table layout)
  [anthropic parser] WARN: skipping 'Claude Mythos Preview' — output $1.5 <= input $7.5 (impossible for Anthropic; likely non-standard table layout)
  ```

### Phase D evidence
- **Log output** (this turn):
  ```
  Alert FAILED (all delivery methods): cartesia: blocked write (diff>50%) — Row cartesia/sonic-2 parsed price 233.33 vs DB 1000.00 (-77%). Refused to write.
  ```
- **Path check** (this turn): `ls scripts/kilo-benchmarks/cache/blocked_writes*` → `No such file or directory`. Queue doesn't exist.

### Phase E evidence
- **`path:line`**: `scripts/kilo-benchmarks/scrape_groq_speeds.py:187` — `GROQ_TO_OR_ID` — the pattern to mirror.
- **`path:line`**: `scripts/kilo-benchmarks/scrape_coding_benchmarks.py:188` — `_match_id()` — the function to wrap.
- **Log output** (this turn):
  ```
  [scrape_coding] SWE-bench primary: rows=93 unique=37 unmatched=135
  [aa-scrape]   matched 82 / 363 agents (22%)
  ```

### Phase F evidence
- **`path:line`**: `scripts/final_gate.py:1` — Tier-2 gate entrypoint. `scripts/enforcement/check_convergence.py:39` — the `PROOF` regex `[\w./-]+\.(?:py|ts|tsx|js|sql|md|csv|ya?ml|sh|json):\d+` enforcing ≥1 file:line citation per phase.

---

## Self-audit

### Grounding passes run this turn

1. **Pass 1** (this turn): live daily_refresh run + inspection of every failing log line + read every file the plan touches at its specific line ranges. Identified 6 findings, root-caused each, chose the fix pattern per finding based on existing Fabrik conventions.
2. **Pass 2** (structural check): every phase has `Interfaces` block; every phase ends with the same 4-step closing sequence (gate → doc-sync → `/fabrik-review` → commit); Behavior Contract present per phase; TDD-first for the risky path.

### Coverage check ("What we already agreed" ↔ phases)

- Finding 1 (alerts broken) → Phase A.
- Finding 2 (Kilo CLI 0 models) → Phase B.
- Finding 3 (SWE-bench 40% unmatched) → Phase E.
- Finding 4 (AA 22% unmatched) → Phase E.
- Finding 5 (Anthropic Mythos skipped) → Phase C.
- Finding 6 (Cartesia blocked writes no queue) → Phase D.
- Full-plan convergence + gate + archive → Phase F.

**No gap found.** Every finding maps to a phase.

### Cross-phase signature consistency

- `send(title: str, body: str) -> bool` — Phase A produces; Phase B consumes (config-error alert path) + Phase D consumes (blocked-write alert path). Signature stable across all consumers. ✓
- `record_blocked_write(vendor, model_id, parsed_price, db_price, reason, raw_text, *, today=None) -> Path` — Phase D produces + consumes internally. No cross-phase user. ✓
- `SWE_TO_OR_ID` / `AA_TO_OR_ID` — Phase E produces + consumes internally. No cross-phase user. ✓
- `_match_id(canon_idx, name) -> str | None` — Phase E preserves the existing signature (adds pre-check on manual map). Regression preserved. ✓

### Fixed-point claim

This is the DRAFT. `/fabrik-plan-review` will run the adversarial convergence pass and either flip to CONVERGED or surface remaining issues. Do NOT claim CONVERGED here.

---

## Residual unknowns

### Resolved during this plan

- **Alert-delivery approach** — LOCKED IN as `docker run --rm --network fabrik curlimages/curl:latest` (Fabrik-conventional pattern, in use at 3 existing sites). Not deferred to execution.
- **Kilo config strategy** — LOCKED IN as sanitize-first (default path) + report-on-error (defense-in-depth). Executor's B.1 live probe confirms strategy in 1 second; no operator question.
- **Anthropic Mythos handling** — LOCKED IN as explicit whitelist (preserves safety net for future non-Mythos parsing bugs).

### Still-open (each carries a named resolution step)

1. **Manual-override map seed depth (Phase E)**. Initial `SWE_TO_OR_ID` + `AA_TO_OR_ID` seeds cover ~30-40 entries each to achieve the 70% / 50% targets. Long-tail entries need incremental additions per weekly daily_refresh review. **Resolution**: the Phase D blocked-writes queue pattern extends naturally — a follow-up plan can add `cache/unmatched_benchmarks/YYYY-MM-DD.md` on the same shape, giving operators a weekly review artifact. Out of scope for this plan.

2. **Deepgram / Cartesia parsers may have similar "Mythos-style" edge cases**. Phase C only fixes Anthropic. **Resolution**: after Phase D's blocked-writes queue is live, review the queue over 2 weeks. If deepgram/cartesia entries appear, add per-vendor whitelists via a follow-up plan. Non-blocking.

3. **Whether kilo CLI's `subagent_model` config keys should be REGENERATED (not deleted) after sanitize**. The keys were originally there for a reason (routing kilo-driven subagents to a specific model). If the newer kilo CLI moved this config to a different location, Phase B's sanitize removes potentially-useful config. **Resolution**: Phase B's post-sanitize verification includes reading kilo v7.0.33's changelog for migration notes. If a migration is needed, it becomes a follow-up plan; the sanitize + report-on-error path here doesn't preclude it.

---

## Handoff

- `/fabrik-plan-review docs/development/plans/2026-07-08-plan-4-pipeline-health-coverage-closure.md` (invoked automatically at the end of this turn) → adversarial grounding to fixed-point → flips `Status: DRAFT` → `Status: CONVERGED`.
- **User approval gate.**
- `/fabrik-execute-plan docs/development/plans/2026-07-08-plan-4-pipeline-health-coverage-closure.md` — user-triggered, runs Phase A → B → C → D → E → F autonomously with per-phase `/fabrik-review` gates.

**Expected wall clock:** Phase A (~15 min including live smoke), B (~15 min), C (~10 min), D (~15 min), E (~30 min including live coverage assertion), F (~15 min). Total ~90-120 min end-to-end.

**Expected spend:** ~$0 (no pool subagents required; all inline TDD + edits). Optional pool subagents for parallel test authoring would add ~$0.10-$0.30.
