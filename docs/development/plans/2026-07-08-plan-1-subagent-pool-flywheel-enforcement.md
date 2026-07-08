# Subagent pool adoption + enforced flywheel scoring

Status: CONVERGED
Spec: `docs/superpowers/specs/2026-07-08-subagent-usage-enforcement-design.md` (CONVERGED)
Date: 2026-07-08
Converged: 2026-07-08 (/fabrik-plan-review — 2 passes to an edit-free md5-verified no-op; all path:line re-grounded, gates confirmed WSL-runnable)

Flip fabrik from "native-default, pool gated" to **pool-default for gradeable fan-out**, with
**fleet-synced enforcement** that a pool run is scored + recorded, and **default DSN provisioning** so
`record_agent_run` writes without hand-wiring. Root cause: prose governance + an unset DSN meant the pool
was never used and nothing recorded, despite the module being built + dogfood-proven (2026-07-08:
`pick_models("review",n=3)`→`run_agents`, ~$0.0014, 3 rows in `fabrik_analytics.subagent_runs`).

## What we already agreed (from the CONVERGED spec + this conversation)

- **Runtime rule:** everything decomposable → a subagent. **Pool** (`run_agents`, ≤$1.5/Mtok) for gradeable
  text/code fan-out (finders, grounders, reconcilers, auditors, implementers) → feeds the flywheel.
  **Native Claude subagent** for GUI (`fabrik-gui`) + authoritative/high-risk (auth/schema/migrations) +
  the decide/refute/merge → no flywheel row by nature.
- **Enforcement = fleet-synced, not prose:** `record_agent_run` writes a **local receipt** on `True`;
  `scripts/enforcement/check_subagent_flywheel.py` (synced) reconciles ledger ↔ receipts locally and WARNs
  on an unreceipted pool run. Local because the writer role is **INSERT-only** (`postgres.py:865-866`) — the gate
  can't `SELECT subagent_runs`.
- **Operator DECISIONS (approved this turn):** (1) `path:line` grounders (`plan-after-chat`/`data-contract`)
  → pool + a native ~20% citation verify-sample; (2) enforcement teeth → **warn-then-fail** (WARN now,
  hard-fail on a dated flag).
- **Vendor verdict:** pool = VENDOR as-is (`libs/subagents` @ `90e0d0d6`, byte-identical). Receipt +
  `audit_unrecorded` = fabrik-lib **VENDOR+ENHANCE** (module owns ledger + `record_agent_run`) — upstream +
  re-vendor, don't fork. Check = BUILD glue. DSN = provisioning glue.
- **Cross-repo:** the receipt ENHANCE lands in `/opt/fabrik-lib` (fabrik-lib AI) via `UPSTREAM_FEEDBACK.md`;
  the `subagent_runs` role/grants are the coding-selection AI's.

## Global Constraints (verbatim — every phase inherits)

- **NEVER route to the pool:** auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys ·
  security controls · deploy/infra → native/human only.
- **`record_agent_run` fail-opens to `False`** (missing `psycopg` / GRANT gap / unreachable DB) — the receipt
  is written **only on `True`**; assert the row/receipt, never trust the return.
- **Cross-repo HARD STOP:** the only write into `/opt/fabrik-lib` is appending
  `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md`. The module build + re-vendor is the fabrik-lib AI's.
- **Fabrik-synced files** (`.windsurf/rules/**`, `scripts/enforcement/**`, `CLAUDE.md`) are edited in
  `/opt/fabrik` only (they overwrite project copies on sync); never edit a project's copy.
- **Explicit-path commits only** (never `git add -A`); provenance trailers on every AI commit.
- **Gates run from WSL dev** (`python scripts/…`, `pytest`, `python -c …`) — never a `fabrik …` shell-out
  (hub-side CLI, absent from project PATH).
- **Command files are user-level** (`~/.claude/commands/*.md`) — live immediately, NOT repo-gated/committed.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | the runtime rule + flywheel contract this plan flips to pool-default | `select_rules.py` → ACTIVE (19 packs); this pack is edited in Phase B |
| `libs/subagents` (VENDORED @ `90e0d0d6`) | `run_agents`/`pick_models`/`record_agent_run`/`results_table`/`Ledger` — vendor, don't build | `agent.py:364 run_agents`, `:286/292 ledger`, `ledger.py:44 Ledger/:65 append`, `pg_ledger.py:132 record_agent_run` |
| `libs/subagents` **ENHANCE** (receipt + `audit_unrecorded`) | new module capability — upstream via UPSTREAM_FEEDBACK, re-vendor | `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` (exists) |
| `scripts/final_gate.py` | the enforcement runner to extend | `:140 run_optional_check(advisory=)`, registration site `:628` |
| `scripts/fabrik_synced_manifest.py` | what propagates fleet-wide (the enforcement's teeth) | `ENFORCEMENT_DIR = "scripts/enforcement"`, `.windsurf/rules` |
| `src/fabrik/drivers/postgres.py` | INSERT-only writer role (why the check is local); VPS provisioning already exists | `:785 create_subagent_ins_role`, `:860 GRANT INSERT (no SELECT)` |
| `src/fabrik/scaffold.py` | `.env.example` template — DSN provisioning home | `:1022 (.env.example write)` |
| `mcp_tools.py` | browser MCPs reachable via `allow_unlisted` (why pool GUI is possible-but-not-default) | `:370 allow_unlisted` |

No new external API (OpenRouter grounded live via the dogfood). No new fabrik-lib **module** (the ENHANCE is
to the existing `subagents` module).

## One-Test Rule

**Why:** the entire plan exists to make "a pool run must be scored + recorded" *enforceable* — so the
highest-risk behavior is the enforcement check correctly distinguishing an **unrecorded** pool run (must
flag) from a recorded one or native-only work (must NOT flag). If that detection is wrong, the enforcement is
either toothless (misses gaps) or a false-positive nuisance (blocks clean work) — both defeat the goal.

**Contract:**
- **Given:** a `.tmp/subagents/ledger.jsonl` containing one pool-run entry whose `agent_id` has **no**
  matching line in `.tmp/subagents/receipts.jsonl`.
- **When:** `check_subagent_flywheel.py` runs (calling `audit_unrecorded(ledger_path)`).
- **Then:** it reports exactly that one unreceipted run (advisory WARN, non-fatal). And the inverse: with
  `ledger == receipts` (every run receipted) OR **no ledger at all** (native-only / no pool use), the check
  passes clean with **zero** findings.

---

## Phase A — fabrik-lib ENHANCE proposal (cross-repo coordination; blocks Phase D)

**Files:** `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` (append only — the one sanctioned cross-repo write).
**Responsibility:** specify the receipt + audit interface precisely so the fabrik-lib AI builds the right
thing, then it lands in canonical + is re-vendored. **The build itself is the fabrik-lib AI's, not this plan's.**

**Interfaces — Produces (the contract Phase D consumes, once vendored):**
- `record_agent_run(spec, result, *, quality_score, project, dsn=None, connect=None, receipt_dir=None) -> bool`
  — on a `True` write, appends one line to the receipts JSONL:
  `{"agent_id": <spec/result agent_id>, "ts": <iso>, "recorded": true, "project": <project>}`. Keyed by
  `agent_id` **only** — `task_type`/`model` live on the ledger record (`agent_record` = `_SPEC_FIELDS` incl.
  both + `_RESULT_FIELDS` incl. `agent_id`, `ledger.py:123`), which `audit_unrecorded` **returns**, so the WARN
  reads them from the ledger side; the receipt need not duplicate them. No-op on `False`; the receipt write is
  **fail-open** (a post-`True` disk error never raises → at worst one phantom advisory WARN, acceptable at
  `advisory=True`). `receipt_dir=None` → `<cwd>/.tmp/subagents/receipts.jsonl`; since `record_agent_run` has no
  repo context, **`run_agents`-callers (Phase E) pass `receipt_dir=<repo>/.tmp/subagents` explicitly** — the
  same dir as the ledger — so receipts never depend on cwd.
- `audit_unrecorded(ledger_path: str, receipts_path: str | None = None) -> list[dict]` — returns the ledger
  entries whose `agent_id` has **no** matching receipt (= pool runs that ran but were never scored+recorded).
  Receipts default co-located with the ledger (`.tmp/subagents/receipts.jsonl`).

**Steps:**
1. Append an `UPSTREAM_FEEDBACK.md` entry (symptom + proposed API + why): "the enforcement gate cannot
   `SELECT subagent_runs` (writer role INSERT-only), so it needs a **local** signal that a run was recorded —
   propose `record_agent_run` write a receipt on `True` + an `audit_unrecorded(ledger_path)` helper. Both are
   generic to any pool consumer; they belong in the module (it owns the ledger + `record_agent_run`)."
   Include the exact interface above + the receipt line schema.
2. **Gate:** `grep -c "audit_unrecorded" /opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` → `≥1`.
3. Record the **BLOCKING dependency** in Residual unknowns: Phase D's check cannot ship until the fabrik-lib
   AI lands the ENHANCE in canonical AND it is re-vendored (`python -c "from libs.subagents import
   audit_unrecorded"` exits 0). Until then, Phase D ships the wrapper guarded (`try/except ImportError`).

**Phase A closing sequence:**
1. Gate above → green.
2. `python scripts/enforcement/check_doc_sync.py` (no repo doc change here — the write is cross-repo).
3. **`/fabrik-review`** on the UPSTREAM entry (prose correctness: interface unambiguous, schema complete) →
   loop to no-op.
4. No commit (cross-repo file; not in this repo).

---

## Phase B — Flip `62-using-subagents.md` to pool-default (fleet-synced)

**Files:** `/opt/fabrik/.windsurf/rules/core/62-using-subagents.md` (synced fleet-wide).
**Responsibility:** replace the "phased + gated / NOT default-on / Step-3" framing with the runtime rule +
the per-command map (pool-default for gradeable fan-out; native for GUI/authoritative/decide).

**Interfaces — Produces:** the § Dispatch policy runtime rule + the per-command runtime map that Phase E wires.

**Steps:**
1. Rewrite § Dispatch policy: pool is the **default** worker for pool-suitable fan-out; delete
   "gated/Step-3/not-default-on." Keep the NEVER-route list + the pool-vs-native table (already present).
2. Add/confirm the per-command runtime map (from the spec) as a table in the pack.
3. Keep the § Report every pool run (results_table + record_agent_run) — already correct.
4. **Gate:** `grep -iE "NOT default-on|Step 3|phased \+ gated" .windsurf/rules/core/62-using-subagents.md`
   → **no matches** (the gated language is gone); `grep -c "default worker" …` → `≥1`.
5. Doc-sync: `CHANGELOG.md` entry (governance change).

**Phase B closing sequence:** (1) gate green; (2) `check_doc_sync.py` + CHANGELOG; (3) **`/fabrik-review`** on
the 62 diff → no-op; (4) commit `.windsurf/rules/core/62-using-subagents.md` + `CHANGELOG.md` (explicit paths,
provenance).

---

## Phase C — `SUBAGENT_RUNS_DSN` provisioning (record by default)

**Files:** `src/fabrik/scaffold.py` (`.env.example` template), `/opt/fabrik/.env` (WSL dev — backed up first),
`.env.example` (repo). **Responsibility:** every project + WSL dev has the writer DSN so `record_agent_run`
writes without hand-wiring. VPS is already provisioned (`postgres.py:782 create_subagent_ins_role` + `inject_env`).

**Interfaces — Produces:** env vars `SUBAGENT_RUNS_DSN` (INSERT-only writer DSN) + `SUBAGENT_PROJECT`.

**Steps:**
1. Add `SUBAGENT_RUNS_DSN=` + `SUBAGENT_PROJECT=` (commented placeholders + a one-line comment) to the
   scaffolder's `.env.example` writer (`scaffold.py:~1022`) so new projects carry them.
2. Provision `/opt/fabrik/.env` (WSL dev) with the `subagent_smoke_writer` DSN — **coordinate with the
   coding-selection AI** (they own the role); **back up `.env` first** (`cp .env backups/.env.backup.$(date …)`).
3. Verify (read-only) the VPS deploy path injects `SUBAGENT_RUNS_DSN`/`SUBAGENT_PROJECT` (`grep -n
   "SUBAGENT_RUNS_DSN\|inject_env" src/fabrik/drivers/*.py`) — assert, don't re-implement.
4. **Gate (Python does NOT auto-load `.env` — load it into the process first):** `set -a; . .env; set +a;
   python -c "from libs.subagents import record_agent_run, AgentSpec, AgentResult;
   s=AgentSpec(task='t',model='minimax/minimax-m3',task_type='review');
   r=AgentResult(agent_id='provision-smoke',text='',diff='',status='done',provider='x',cost_usd=0.0,turns=1);
   print(record_agent_run(s,r,quality_score=5,project='provision-smoke'))"` → **`True`**. Then the SELECT-back —
   the writer role is **INSERT-only**, so read via **superuser** (toolchain preflight: `sudo -n -u postgres
   psql` must work passwordless — **verified available on this WSL dev**; a fresh env lacking it uses the
   coding-selection AI's read path): `sudo -n -u postgres psql -d fabrik_analytics -tAc "SELECT count(*) FROM
   subagent_runs WHERE project='provision-smoke'"` → **`1`**.
5. Doc-sync: `docs/CONFIGURATION.md` + `.env.example` (new env vars, per the Doc Sync Matrix); `CHANGELOG.md`.

**Phase C closing sequence:** (1) gate green (row lands); (2) `check_doc_sync.py` + CONFIGURATION + `.env.example`
+ CHANGELOG; (3) **`/fabrik-review`** on the scaffold diff → no-op; (4) commit `src/fabrik/scaffold.py` +
`.env.example` + `docs/CONFIGURATION.md` + `CHANGELOG.md` (NOT `.env` — gitignored).

---

## Phase D — `check_subagent_flywheel.py` + wire `final_gate` (fleet-synced, WARN)

**Files:** `scripts/enforcement/check_subagent_flywheel.py` (new, fleet-synced), `scripts/final_gate.py`
(register), `tests/test_check_subagent_flywheel.py`. **Depends on Phase A** (`audit_unrecorded` vendored).
**Responsibility:** WARN when the pool ledger has unreceipted runs.

**Interfaces — Consumes:** `libs.subagents.audit_unrecorded(ledger_path)` (Phase A). **Produces:** the check
script + a `run_optional_check(..., advisory=True)` registration.

**Steps (highest-risk test FIRST):**
1. **Write the failing test** `tests/test_check_subagent_flywheel.py`: given a ledger with one entry + no
   receipt → the check reports the unreceipted run (exit non-zero / advisory message); given ledger==receipts
   → clean. **Run it red** (check doesn't exist yet).
2. Implement `check_subagent_flywheel.py`: locate `.tmp/subagents/ledger.jsonl`; if absent → pass (no pool
   use). Call `audit_unrecorded(ledger_path)` **guarded** — `try: from libs.subagents import audit_unrecorded
   / except ImportError:` → skip with an actionable "ENHANCE not vendored yet" message (so it ships before
   Phase A lands). If unreceipted runs → emit the list (advisory). Carry the `# AFTER-EDIT:` coupling header.
3. **Run the test green.**
4. Register in `final_gate.py:~628`: `run_optional_check("scripts/enforcement/check_subagent_flywheel.py",
   "Subagent Flywheel (pool runs recorded)", advisory=True)`. **Teeth = warn-then-fail:** `advisory=True` now
   + a dated `# TODO(2026-07-22): flip advisory=False` comment (the operator-approved escalation).
5. **Gate:** `pytest tests/test_check_subagent_flywheel.py -q` green; `python scripts/final_gate.py --check
   --json` includes the check and stays `"status":"success"` (advisory WARN doesn't fail).
6. Doc-sync: `INDEX.md` (new file); `CHANGELOG.md`.

**Phase D closing sequence:** (1) gates green; (2) `check_doc_sync.py` + INDEX + CHANGELOG; (3)
**`/fabrik-review`** on the check + registration + test → no-op; (4) commit
`scripts/enforcement/check_subagent_flywheel.py` + `scripts/final_gate.py` +
`tests/test_check_subagent_flywheel.py` + `INDEX.md` + `CHANGELOG.md` (explicit paths, provenance).

---

## Phase E — Wire the pool into the commands (per the runtime map)

**Files:** `~/.claude/commands/*.md` (user-level — live, NOT repo-committed): `fabrik-review`,
`fabrik-repo-review`, `fabrik-execute-plan`, `fabrik-docs-review`, `fabrik-rules-review`, `fabrik-spec-review`,
`fabrik-plan-review`, `fabrik-plan-after-chat`, `fabrik-data-contract`, `fabrik-spec`. **Responsibility:**
each pool-suitable command's dispatch step **calls** `run_agents` + `record_agent_run` (not "you may"),
per the Phase-B runtime map; native for GUI/authoritative/decide.

**Interfaces — Consumes:** the Phase-B runtime map + Phase-A `record_agent_run` receipt semantics.

**Steps:**
1. For each command in the map, rewrite its fan-out step to **dispatch the pool by default** for the
   gradeable unit (finders/grounders/reconcilers/auditors/implementers): `pick_models(task_type)` →
   `run_agents([...])` → judge → `record_agent_run(spec, result, quality_score)` + `results_table`. Reserve
   native (`fabrik-reviewer`/Opus) for auth/schema/high-blast-radius + the decide-merge.
2. For `plan-after-chat` + `data-contract`: pool grounders + a native **~20% citation verify-sample** (the
   approved default).
3. Leave `fabrik-ui-design(-review)` native (`fabrik-gui`).
4. **Gate:** per command, `grep -c "run_agents\|record_agent_run" ~/.claude/commands/<cmd>.md` → `≥1` for
   each pool command; `grep -c "record_agent_run" ~/.claude/commands/fabrik-ui-design.md` → context is native
   (no pool-record instruction).
5. Doc-sync: none in-repo (user-level files); note the change in `CHANGELOG.md` (governance-adjacent).

**Phase E closing sequence:** (1) grep gates green; (2) CHANGELOG note; (3) **`/fabrik-review`** on the command
diffs (consistency vs 62 + the runtime map; no stray `record_run`; native/pool correct) → no-op; (4) command
files are user-level (no commit) — commit only the `CHANGELOG.md` note.

---

## Final phase gate (after E)

- `python scripts/final_gate.py --check --json` → `"status":"success"`; `python
  scripts/enforcement/check_convergence.py` → pass.
- `/fabrik-docs-review` — converge all subagent/flywheel docs to the new pool-default reality (62, CLAUDE.md,
  the flywheel workflow, the specs) to a no-op.

## File Scope (owned paths)

- `.windsurf/rules/core/62-using-subagents.md`
- `scripts/enforcement/check_subagent_flywheel.py` (new)
- `scripts/final_gate.py`
- `src/fabrik/scaffold.py`
- `.env.example`, `docs/CONFIGURATION.md`, `INDEX.md`, `CHANGELOG.md`
- `tests/test_check_subagent_flywheel.py` (new)
- **cross-repo (append-only, not owned here):** `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md`
- **user-level (not repo):** `~/.claude/commands/*.md` (10 files)
- **not committed:** `/opt/fabrik/.env` (gitignored; backed up)

## Evidence

- **A/D:** the writer role is INSERT-only → local reconciliation required. `postgres.py:865-866` `GRANT INSERT ON
  public.subagent_runs` (grep confirmed, no SELECT). Ledger cumulative append-only: `ledger.py:65` mode `"a"`,
  `agent.py:292` fixed `.tmp/subagents/ledger.jsonl`.
- **B:** 62 is ACTIVE (`select_rules.py` → 19 packs incl. `core/62-using-subagents.md`).
- **C:** VPS provisioning exists — `postgres.py:782 create_subagent_ins_role`. Scaffold `.env.example` writer
  at `scaffold.py:1022`.
- **D:** registration pattern — `final_gate.py:628 run_optional_check(...)`, `:140` signature with `advisory`.
- **Live proof the pipeline works:** dogfood 2026-07-08 — 3 `subagent_runs` rows (`project='pool-dogfood'`,
  quality 4–5), `record_agent_run` returned `True` via the `subagent_smoke_writer` role; `results_table`
  rendered cost/latency/out_tokens.

## Self-audit

- Coverage: each "What we already agreed" item maps to a phase — runtime rule → B+E; enforcement (receipt) →
  A+D; INSERT-only-local → D; DSN provisioning → C; the two DECISIONS → E (verify-sample) + D (warn-then-fail
  `advisory=True` + dated flip). No gap.
- Cross-phase signatures: `audit_unrecorded(ledger_path)` (A.Produces) == D.Consumes; `SUBAGENT_RUNS_DSN`
  (C.Produces) used by the record path in D's gate + E. Consistent.
- Grounding: all `path:line` in the Context Ledger + Evidence read live this session; dogfood rows exist.

## Residual unknowns

- **[BLOCKING → Phase D]** the receipt + `audit_unrecorded` ENHANCE must be built by the fabrik-lib AI in
  canonical AND re-vendored before Phase D's check is fully live. Resolution: Phase A's UPSTREAM proposal →
  fabrik-lib AI builds → re-vendor → `python -c "from libs.subagents import audit_unrecorded"` exits 0. Phase
  D ships guarded (`ImportError` → skip) so it isn't blocked from landing.
- **[OPEN → Phase C]** WSL-dev `SUBAGENT_RUNS_DSN`: reuse `subagent_smoke_writer` (exists) or a dedicated dev
  writer? Resolution: confirm with the coding-selection AI at Phase C start.
- **[RESOLVED — Phase A interface, 2026-07-08]** receipt file path/format finalized with the fabrik-lib AI:
  `record_agent_run(…, receipt_dir=None)` → `<cwd>/.tmp/subagents/receipts.jsonl`; `run_agents`-callers pass
  `receipt_dir=<repo>/.tmp/subagents` explicitly (never cwd-dependent); line
  `{agent_id, ts, recorded:true, project}` keyed by `agent_id` only; fail-open write. See Phase A Interfaces.
