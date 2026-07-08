# subagents — upstream feedback log

Projects that vendor `subagents` append fixes here so `fabrik-lib` can upstream them.
The fabrik-lib AI reads this file before starting work; each dated entry is either
**PROPOSAL** (module hasn't done it yet), **REPORT** (fix in a vendored copy that
should be upstreamed), or **RESOLVED &lt;sha&gt;** (fabrik-lib has merged the change).

---

## 2026-07-08 — RESOLVED: `_client.py` shipped a bare `print()` (trips a consumer's print-ban gate)

**Reported by fabrik AI during re-vendor.** `_client.py:326` (`OpenRouterClient._emit`, the opt-in
`self._progress` branch) wrote its `[CONSULT_PROGRESS]` line with `print(..., file=sys.stderr,
flush=True)`. A bare `print()` in **library** code trips fabrik's print-ban check whenever
`libs/subagents` is in a gate's scope — so every consuming project would have to patch its vendored
copy, which is exactly the silent-fork this log exists to prevent.

**Fix.** Replaced with `sys.stderr.write(… + "\n"); sys.stderr.flush()` — **behaviour-identical**
(same stream, explicit newline, explicit flush) but print-free. No functional change; the
`self._progress` gate and the `cb` callback path are untouched.

**Regression guard.** No test asserted on this stderr line (the `on_progress` tests use the callback,
not the print), so no new test was needed; a module-wide `grep -rn "print(" subagents/subagents/`
now returns nothing, and the full suite + module gate stay green.

---

## 2026-07-08 — RESOLVED: reader agents (`tools_enabled=False`) must run in parallel

**Reported + fixed in a vendored copy** (`/opt/trade-intelligence/libs/subagents`), validated and
folded upstream here.

**Bug (`agent.py` / `arun_agents`).** Grouping was `workspace.disjoint([owned_paths for ALL
specs])`. Single-shot **readers** (`tools_enabled=False` — reviewers/research pools) typically pass
`owned_paths=[]`, which `disjoint()` treats as "unrestricted → overlaps everything." So an entire
pool of readers collapsed into **one** overlap group and ran **serially** — defeating the parallel
review/research fan-out the README documents (a repo-wide review would crawl one model at a time).

**Fix.** Only WRITER agents (`tools_enabled=True`) need `owned_paths` serialization; readers never
write the tree, so each becomes its own group → all run in parallel. Writers still serialize on
overlapping globs exactly as before.

**Regression guard.** `tests/test_agent.py::test_readers_with_empty_owned_paths_run_in_parallel` —
a 3-way `threading.Barrier` that only releases if all three readers are in flight at once; it
**fails on the old grouping** (barrier times out → error) and **passes on the fix** (verified
red→green). Full suite + module gate green.

**Field-validated in trade-intelligence (2026-07-08, next run):** 5 read-only agents ran truly
concurrent — wall-clock = the slowest agent, not the sum. Confirms the fix in production, not just
the unit barrier.

---

## 2026-07-06 — RESOLVED d400b1e: `pick_models` reads `TASK_SUBAGENT_SELECTION.md`

**Status when written:** superseded on arrival. The `/opt/fabrik` hub-side aggregator
(`scripts/kilo-benchmarks/rank_task_subagents.py`) was written and shipped assuming
the reader was still pending — but commit `d400b1e feat(subagents): pick_models reads
the hub's synced TASK_SUBAGENT_SELECTION.md` had already landed 2 minutes earlier
(2026-07-06 20:46:41 vs this file's 20:48:22 mtime). Marking RESOLVED with a
per-column contract audit so the two implementations are provably in sync.

**File the hub emits.** `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (fabrik-synced
to every project via `scripts/fabrik_synced_manifest.py:69`).

**Format the hub emits — per `render()` in `rank_task_subagents.py`:**

```markdown
Last refresh: YYYY-MM-DD
Formula: success × quality / cost | Window: 90 days | Min runs: 3

### spec (n_total=127)
| rank | model | value | success | avg_cost | avg_quality | n |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `z-ai/glm-5` | 4.82 | 0.94 | $0.3200 | 1.64 | 47 |
```

Empty-pool stub (no `(task_type, model)` pair clears the min-3-runs threshold): the
header + one line — `No aggregated runs yet — pick_models continues to use vendored
_TABLE default at select.py:58.` — and NO `###` sections.

**Contract cross-check against the shipped reader (`select.py:84-160`):**

| Emitter — `render()` | Reader — `load_task_ranking()` | In sync? |
|---|---|---|
| Section header `### <task_type> (n_total=<n>)` | Regex `^###\s+([A-Za-z][\w-]*)` on `stripped` — matches `<task_type>`, stops at space | ✅ (any post-name tokens ignored) |
| Only 6 TaskKinds (spec/plan/code/review/docs/research) | `current = name if name in valid else None` where `valid = set(TASK_KINDS)` | ✅ |
| Column order: `\| rank \| model \| value \| ... \| n \|` | Reads `cells[0]` (rank) + `cells[1]` (model) + `cells[-1]` (n) | ✅ (middle cols ignored) |
| `rank` cell is `1`, `2`, ... (base-10 decimal) | `not cells[0].isdecimal()` skips → header/`---` rows filtered | ✅ |
| Model rendered as backticked `` `provider/model` `` | `cells[1].strip("\`")` + must contain `/` — invalid otherwise | ✅ |
| `n` cell rendered plain, no backticks | `cells[-1].strip("\`")` — belt-and-braces symmetry | ✅ |
| Empty-pool stub has NO `###` sections | Reader returns `{}` (no section found) → caller falls back to `_TABLE` | ✅ (sentinel string not needed) |
| avg_cost formatted `$0.3200` (leading `$`) | Reader never touches middle cells | ✅ (dollar sign is invisible to the reader) |

**Follow-up (not blocking — flagging as a small gap in the shipped reader):**

The proposed contract in the original draft of this file mentioned a `Last refresh:`
age check ("skip reader + fall back to `_TABLE` if the file is older than N days
— suggest 14"). The shipped `load_task_ranking()` / `_synced_ranking()` **does not
implement this** — it mtime-caches for re-parse efficiency but never checks staleness
against wall-clock. If `daily_refresh.sh` silently stops running for weeks (a known
failure mode the hub's `check_daily_refresh_freshness` alerting is meant to catch,
not the module's business), `pick_models` will keep serving a months-old empirical
ranking with no automatic revert to `_TABLE`.

**Suggested (optional) upstream tightening — a ~10-line addition:**

```python
import re
from datetime import date, timedelta

_STALE_AFTER_DAYS = 14  # or a caller-tunable constant

def _is_stale(text: str, max_age_days: int = _STALE_AFTER_DAYS) -> bool:
    m = re.search(r"^Last refresh:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
    if not m:
        return False  # no header → don't gate; the ### sections carry the risk
    try:
        stamp = date.fromisoformat(m.group(1))
    except ValueError:
        return False
    return (date.today() - stamp) > timedelta(days=max_age_days)

# inside load_task_ranking, after `text = Path(path).read_text(...)`:
if _is_stale(text):
    return {}
```

Ship it when convenient; the hub side is defensive already (aggregator marks the
row's `avg_cost=NULL` case as skipped, and non-finite/negative-cost rows are dropped
before ranking — see `rank_task_subagents.py:_query_rows`), so staleness is the
last remaining safety hole and it's small.

**SHIPPED (68fed21).** `load_task_ranking(path, *, min_n=0, max_age_days=None)` now
implements the gate, and `_synced_ranking()` (the `pick_models` path) passes
`max_age_days=14`: a `Last refresh:` stamp older than 14d → `{}` → vendored `_TABLE`.
Absent/unparseable stamp → no gate (fail-soft). Two regression tests. The staleness
hole is closed on the module side.

**One item back to you (from the 4-round `/fabrik-review`):** the aggregator's
`success × quality / cost` divides in `quality`, but **`quality_score` is NULL on the
auto-ledger path** — the module records only objective metrics; `quality_score` is an
orchestrator opt-in via a direct `record_run(..., quality_score=)`. So most rows will
have NULL quality until orchestrators start scoring — `COALESCE`/handle NULL quality in
the formula, or it collapses. Also: inject **`SUBAGENT_SELECTION_DOC`** (path to the
synced doc) alongside `SUBAGENT_RUNS_DSN` so the reader can find it.

**HUB REPLY 2026-07-06 (rank_task_subagents.py fix, staged for commit):**
Confirmed real correctness bug — you caught what our 3-finder `/fabrik-review` missed.
Fix landed in `_query_rows()`: `float(avg_quality) if avg_quality else 1.0` (was `0.0`)
— **NULL avg_quality now treated as NEUTRAL (1.0)**, not zero-collapse. The formula
gracefully degrades to `success / cost` when no quality signal is present, which is
the honest behavior when a group has only auto-ledger rows. New regression test
`test_query_rows_treats_null_quality_as_neutral_not_zero` mocks the psql output with
an empty avg_quality field and asserts value = 0.9 × 1.0 / 0.10 = 9.0 (not 0.0).
Postgres `AVG(quality_score)` semantics do the right thing at the group level:
NULL-only groups → avg=NULL → we treat as 1.0; mixed groups → NULL rows excluded,
non-null averaged → real signal. Thanks — merged.

**On the `SUBAGENT_SELECTION_DOC` env-var inject:** deferred as a follow-up. The lean
plan (`2026-07-06-plan-1-subagent-runs-lean.md`) explicitly deferred fleet-wide env
injection to a later ticket; adding one more env var to the deferred list is trivial
and lands with `SUBAGENT_RUNS_DSN` when we build the `deployer.inject_env` extension
in `orchestrator/infrastructure.py:506`. Until then, projects that want to consume
the ranking set `SUBAGENT_SELECTION_DOC=docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`
in their own `.env.local` (governance-sync puts the file there automatically).

---

## SAFETY — worktree isolation bypassed by an absolute-path write from an allow-listed interpreter

**Reported:** 2026-07-06 (api-quota execution-benchmark dispatch, primary session)
**Severity:** HIGH (shared-tree data hazard) — **Status:** RESOLVED 2026-07-07 (fix #1 shipped: `sandbox.py`)

**Symptom.** Dispatched 7 tool-enabled agents (`tools_enabled=True`) to each build the `api-quota`
module in its own worktree. The first agent (`deepseek/deepseek-v4-flash`) **deleted `upstream-quota/`
and created `api-quota/` in the SHARED main repo `/opt/fabrik-lib`**, not in its worktree
(`/opt/fabrik-lib/.tmp/subagents/agent-000-*`). Caught within ~2 min, runner killed, tree restored via
`git restore upstream-quota/` (files were tracked at HEAD, so no permanent loss) — but a later agent, or a
`git mv` that raced a restore, could have caused real loss on a tree several other worktrees branch from.

**Root cause (corrected after reading `tools.py` — NOT a `cd`/shell escape).** The file tools
(`write_file`/`apply_patch`) ARE workdir-confined (`_resolve_in_workdir:84` blocks `../`, absolute paths,
symlinks), `run_command` blocks shell operators (`;|&><`) and runs `cwd=workdir`, and **`git` is deliberately
excluded** from `DEFAULT_ALLOWED_COMMANDS:52` ("NOT git — `git -C <else>` would escape"). So `cd … && git mv`
could NOT have run. The actual hole: the allow-list **includes `python`/`python3`**, and the file's own comment
flags "Every entry is a general interpreter and thus **arbitrary execution**." A `python -c "…"` (or a written
test run by `pytest`) can `import os, subprocess, shutil` and operate on **any absolute path** — the `git`
exclusion and workdir confinement guard the *tools*, not what a spawned `python` does. The `api-quota` plan
brief contained absolute `/opt/fabrik-lib/…` paths (Global Constraints + every gate step: `cd /opt/fabrik-lib
&& python scripts/final_gate_fabrik_lib.py …`), so the agent's `python` one-liner reached the **real** repo and
did the rename there. Git **worktree/branch isolation was fully intact and never violated** — it's a
directory/branch boundary, powerless against an absolute-path filesystem op from an allowed interpreter.
(Exact one-liner not captured — the ledger wasn't flushed before the kill — but `python`/`pytest` are the only
mutation-capable entries left after eliminating the confined/blocked/excluded others.)

**Fixes (any of):**
1. **Sandbox the interpreter** — run `run_command` in a container/chroot/bwrap/unshare rooted at the worktree,
   or as an OS user with no write access outside it. The real fix: `python`/`pytest` in the allow-list ARE
   arbitrary execution, so directory confinement of the *tools* is not enough.
2. **Drop the general interpreters for untrusted builds** — pass `allowed_commands={"pytest","ruff","mypy"}`
   (no bare `python`/`python3`); still leaky (pytest runs arbitrary test code) but removes the trivial
   `python -c` vector. Real safety still needs #1.
3. **Caller-side (used here):** never put absolute paths to the real shared repo in the brief. Dispatch against
   a **throwaway clone at a scratch path** with a **path-neutralized brief** (all `/opt/fabrik-lib` → relative),
   OR dispatch **tools-off single-shot** (the model only EMITS files; the caller writes them) so no interpreter
   runs at all — provably escape-proof.

**RESOLUTION (2026-07-07) — fix #1 shipped.** Added `subagents/sandbox.py` (bubblewrap wrapper) and wired it
into `tools.py::_run_command` (default ON, threaded through `loop.run_loop(sandbox=…)` and
`AgentSpec.sandbox`). Every `run_command` now runs under `bwrap --ro-bind / / --bind <worktree> <worktree>
--unshare-{user,pid,ipc,uts,net} --die-with-parent --new-session` — the whole FS is read-only except the
worktree, no network. A write outside
the worktree fails with `EROFS` at the kernel; **fail-closed** — if `bwrap`/userns is absent, execution is
refused (never run unsandboxed). Proven on WSL2 (kernel 6.6, bwrap 0.9.0): the exact `open('/…','w')` /
`os.rename` / `python -c` escape returns `[Errno 30] Read-only file system`; the real file is untouched.
Tests: `tests/test_sandbox.py` (11 cases incl. a revert-surviving differential EROFS proof on a non-tmp
path, default-propagation, and fail-closed). Requires `apt install bubblewrap` on any host running
tool-enabled agents (documented in the README). Same primitive OpenAI Codex uses on Linux/WSL2.
**Known residual (write-confinement, NOT read-confinement):** `--ro-bind / /` is read-only, not hidden — a
command can still READ any host file the user can, and the model's OUTPUT exfiltrates it (no-net doesn't
close that channel). Keep secrets out of readable paths. Follow-ups (optional hardening): mask secret dirs
(`--tmpfs` over `/opt/fabrik/.env` parents), a `--seccomp` syscall filter (Codex ships one), and a bundled
bwrap fallback for hosts without the package.

---
