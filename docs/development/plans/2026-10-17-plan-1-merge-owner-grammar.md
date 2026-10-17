# Plan — merge-owner row grammar: the exact label, bold allowed (W-5d3ed438)

Status: EXECUTED 2026-10-17
Whole-plan review: docs/development/reviews/2026-10-17-plan-1-merge-owner-grammar-review.md
Profile: small
**Owner:** intel
**Surface:** `git rev-parse HEAD` = 0cbf8d780 at authoring; `scripts/decisions.py:55-69`, `scripts/docs_updater.py:1220-1240`, `.claude/hooks/session_orient.py:205-244` (the six patterns and their comment blocks); `tests/test_session_orient_hook.py` (71 test functions, `_OWNER_CASES` at `:1271-1306`, the literal pins at `:879-920`)

Spec: `docs/superpowers/specs/2026-10-17-merge-owner-grammar-design.md` (DRAFT, `Size: small`, `Profile: delta`; approach A,
D-934). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source: the wave-1 review of
plan `2026-09-30-plan-1-merge-request-loop`, pass 3 → work item W-5d3ed438, assigned by the coordinator. Estimated
diff: ≈30 code lines across THREE code files — six patterns (≈2 lines each) and three comment blocks (≈5 lines each);
tests ≈60 lines in `tests/test_session_orient_hook.py`; two doc sentences.

## What this plan is

Two inline phases the orchestrator codes itself in the `worktree-intel` worktree; no coder is dispatched:

- **A — the grammar**: the six patterns, their comments, the parity pins, the shared fixture rows and the two doc
  sentences (spec § The delta D1–D4).
- **B — Finish**: the whole-plan `/fabrik-review` (the hook and `docs_updater.py` are fleet-synced, a governance-sync
  path), CHANGELOG, the backlog row, the gate, commit, push, merge request.

Phase A ends with `/fabrik-review-scoped` on its surface; the Finish runs the ONE heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and writes one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I4 (4 IN) | IN as dispositioned there | Phase A, per the spec rows |
| I2 | *"Plan it as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"each grader watched red first"* | IN | Phase A step 1; A2's `**Merge owner:**` spelling and A5, green today, are proven red on a mutant in a throwaway worktree |
| I4 | *"`decisions.py --merge-owner .` must still print coordinator"* | IN | Phase A step 6; Evidence |
| I5 | *"The session_orient.py hook is fleet-synced (governance-sync path) → full /fabrik-review at execution"* | IN | Phase B step 1 |
| I6 | *"tests capped `timeout 300 prlimit --as=8589934592 -- <pytest> --timeout=120`, foreground, one file at a time"* | IN | Global Constraints |

Intake: 6 items — 6 IN, 0 OUT-OF-SCOPE, 0 ASK.

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; today's code and the executed census: `spec § What exists today`.
- The delta D1–D4, including the exact bold tokens (one optional `**` on each side of the colon) and the hook's guard
  order: `spec § The delta`; why A
  against the field research, and the panel: `spec § Chosen approach`; rejected B, C, D and a structured field:
  `spec § Rejected alternatives`; validation V1–V5: `spec § Validation`; the rollout window and the D trigger:
  `spec § Lifecycle`. The approval row is minted by `/fabrik-plan-review` at its gate (a `Size: small` spec is approved
  there, not here); D-934 is the design row.

## Global Constraints (every phase inherits these)

- **Every existing declaration reads as today.** The ledger is immutable; the real reader, `decisions.py --merge-owner`,
  run over every `/opt/*/docs/DECISIONS.md` gives the same owner and exit code per ledger from the base SHA's copy and
  from the edited one, run back to back (Phase A step 6).
- **Three copies, one grammar.** The hook cannot import the scripts; the same pattern text goes into all three files,
  and the parity test pins it. The hook's one deliberate divergence — the `(?!UNDECLARED…)` guard inside its owner
  regex — stays, AFTER `(?-i:MERGE OWNER)(?:\*\*)?:(?:\*\*)?\s*`.
- **Changed beyond the phrase:** `_SUPERSEDES_PREFIX`'s lookahead only, `(?=(?-i:MERGE OWNER:))` →
  `(?=(?-i:MERGE OWNER))` (spec D2), so a supersedes clause can precede the colon-outside bold label.
- **Unchanged:** the rest of `_SUPERSEDES_PREFIX`, the capture group `([A-Za-z0-9][A-Za-z0-9_.@-]*)`, the `UNDECLARED` token, `re.I`
  on the compile (the supersedes clause and the token stay case-insensitive), `_ADOPT_NAME_RE`, every reader function.
- **No new dependency** (`core/10-python.md:30`); `re` only.
- **Tests:** one per behaviour, watched-fail-first (`core/45-testing-strategy.md:22`), through the existing three-reader
  parametrized test `test_the_three_owner_readers_pick_the_highest_id_row` (`tests/test_session_orient_hook.py:1319`);
  the case rule is graded by five spellings a different author would write, as executable cases
  (`core/45-testing-strategy.md`, the GUARD row of the BANNED table). Every pytest run is
  `timeout 300 prlimit --as=8589934592 -- .venv/bin/python -m pytest <one file> -q --timeout=120 -p no:cacheprovider`,
  foreground, one file at a time; red-on-revert runs in a throwaway worktree (`git worktree add --detach
  <scratch>/probe HEAD`), never the shared checkout.
- Seats never mutate git state; never read `~/.claude*`; seat scratch paths are absolute and each seat `cd`s to its own
  scratch first.
- **Execution discipline (native seats only, D-181):** Phase A ends with `/fabrik-review-scoped` (the floor of three
  native seats on different angles, stamped with `command_run.py dispatch`) and does not hand on until its closing pass
  confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku
  finder per slice (D-344), the orchestrator executing every refutation and reproduction; the three source files are
  independent slices and fan out in parallel, their candidates merged and deduped by the orchestrator.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR — TOOLING surface; MATCHED via the rubric) | no deps-file edit | `core/10-python.md:30` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — test_session_orient_hook.py) | one test per behaviour; watched-fail-first; a guard graded on five legitimate spellings | `core/45-testing-strategy.md:21`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, DECISIONS.md, this plan) | one CHANGELOG entry | `core/40-documentation.md:134` |
| `docs/workstation/hooks-index.md` (the hooks authority) | the `session_orient.py` row states the owner grammar | `docs/workstation/hooks-index.md:16` |
| `docs/reference/multi-agent-operating-model.md` | the reader-facing statement of who agent-1 is | `docs/reference/multi-agent-operating-model.md:122-126` |
| `fabrik-lib` | no module parses the hub ledger — BUILD (edit in place) | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | untouched — hub scripts and a hook, no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |

## Phase A — the grammar — ✅ EXECUTED 2026-10-17 (3ae906f45)

Appetite: 75

**Interfaces — Produces** (consumed by the readers that already call these symbols; no signature changes):
- `scripts/decisions.py::MERGE_OWNER_RE` (`:61-63`) and `::_UNDECLARED_RE` (`:64-69`) — the phrase becomes
  `(?-i:MERGE OWNER)(?:\*\*)?:(?:\*\*)?\s*`, and `_SUPERSEDES_PREFIX` (`:60`) the lookahead above; read by `_merge_owner` (`:666`, `:669`), whose only caller is `main` (`:731-732`).
- `scripts/docs_updater.py::MERGE_OWNER_RE` (`:1232-1234`) and `::_UNDECLARED_RE` (`:1235-1240`) — the same; read by
  `read_merge_owner` (`:1592`, `:1595`), called at `:1609` (the PLANS header), `:2266` (the adoption status) and `:2535`
  (the `--adopt` row gate).
- `.claude/hooks/session_orient.py::_MERGE_OWNER_RE` (`:228-233`) and `::_UNDECLARED_RE` (`:239-244`) — the same, the
  owner regex reading `(?-i:MERGE OWNER)(?:\*\*)?:(?:\*\*)?\s*(?!UNDECLARED…)(capture)`; read by `_owner_in` (`:327`, `:330`).
- The three comment blocks (`scripts/decisions.py:49-59`, `scripts/docs_updater.py:1220-1230`,
  `.claude/hooks/session_orient.py:205-226`) — the sentence "A bare row with no prefix keeps the case-insensitive
  phrase it always had." is replaced by the one rule: the label is upper-case-exact on every row, one optional `**`
  on each side of its colon, and the first token after it is the owner; and the hook's `:211` ("Case-insensitive because the phrase match is, so `undeclared` cannot sneak
  past it.") becomes: the `UNDECLARED` token stays case-insensitive, the label does not.

**Consumes:** nothing from another phase.

**Steps** (sequential):
1. Write the Phase A graders (Behaviour Contract below) in `tests/test_session_orient_hook.py` — the new
   `_OWNER_CASES` rows, the flipped `bare-row-lowercase-phrase` row, and the updated literal pins — and run the file;
   see A1, A1b, A3, A3b, A4, A6, A9 and A8's three new supersedes spellings, and four of A2's five spellings, red
   against today's grammar (`/opt/fabrik/.tmp/runs/4e90716e-696b-4ddf-90ab-70e30f51f294/fabrik-plan-review-2026-10-17T16-41-08-0330/probes/option_a.py` and
   `option_a_spellings.py` ran every case). Two are green today: A2's `**Merge owner:**` spelling (today its closing
   `**` blocks the capture) and A5 (`\s*` already refuses an asterisk after the colon); their red is proven on mutants
   once step 2 lands — the mutants change the EDITED grammar, so they run in a tree that holds the edit: take
   `git worktree add --detach <scratch>/probe HEAD` (or, should the session's guard refuse it, `git archive HEAD | tar
   -x -C <scratch>/probe`), copy the edited `tests/test_session_orient_hook.py` and the three edited sources into it,
   then apply each mutant there and run the test file from inside it — the graders resolve paths from the tree they
   sit in (`tests/test_session_orient_hook.py:17`), so a copied single file would grade the live checkout instead.
   Mutants: the `(?-i:…)` removed, so `**Merge owner:** rotated` reads `rotated` and that case fails; `\**` written
   for each `(?:\*\*)?` in all three files, so A5 fails; the hook's guard moved before the bold token, so A6 fails.
2. Edit the six patterns (D1, D2), keeping the hook's guard after the bold token; run `ruff format` on the three
   files (the edited single-line compiles pass 100 characters and re-wrap).
3. Edit the three comment blocks and the hook's `:211`, and the stale comments in the test file
   (`tests/test_session_orient_hook.py:722`, "Case-insensitive: the phrase match is", and `:1301`).
4. Run `tests/test_session_orient_hook.py` green, then — one file at a time — `tests/test_decisions_helper.py`,
   `tests/test_docs_updater_adopt.py` and `tests/test_stop_hook_merge_requests.py` (the readers' own suites, no fixture
   change expected per the census in Evidence); `ruff check` and `ruff format --check` on the four files.
5. The two doc sentences (D4): `docs/reference/multi-agent-operating-model.md:122-126` and
   `docs/workstation/hooks-index.md:16`, each saying the bold label is read by the hub's readers at once and by a
   project's synced copies after its next sync.
6. Execute: `python3 scripts/decisions.py --merge-owner .` prints `coordinator`. Then compare the base reader with the
   edited one, back to back over every ledger on the box, with a two-row control ledger that the base must read as
   `alpha` and the edit as `beta` — two identical readers fail the control, so an empty diff cannot pass by accident.
   `<base SHA>` is the commit Phase A starts from (`git rev-parse HEAD` before step 1). Write the driver below to
   `<scratch>/owners_diff.py`, then run, one command per line:

   ```bash
   git show <base SHA>:scripts/decisions.py > <scratch>/base_decisions.py
   python3 <scratch>/owners_diff.py <scratch>/base_decisions.py scripts/decisions.py
   ```

   It prints the control, the base tallies (52 ledgers, 9 `rc=0`, 43 `rc=3` at authoring), `diff: none` and `PASS`,
   exit 0; `--merge-owner` needs no other file than `decisions.py` (`scripts/decisions.py:651-680`). Paste its output
   in Evidence.

   ```python
   """usage: owners_diff.py <base decisions.py> <edited decisions.py>
   Run both readers' --merge-owner over every /opt/*/docs/DECISIONS.md back to back, and over a two-row control ledger.
   Exit 0 only when the control separates them (base alpha, edited beta) and every real ledger reads the same in both."""
   import subprocess
   import sys
   import tempfile
   from collections import Counter
   from pathlib import Path


   def owner(reader, repo):
       p = subprocess.run([sys.executable, reader, "--merge-owner", str(repo)], capture_output=True, text=True)
       return f"{p.stdout.strip()} rc={p.returncode}"


   base, edited = sys.argv[1], sys.argv[2]
   with tempfile.TemporaryDirectory() as d:
       (Path(d) / "docs").mkdir()
       (Path(d) / "docs/DECISIONS.md").write_text(
           "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
           "| D-001 | x | op | MERGE OWNER: alpha | y | z |\n| D-002 | x | op | **MERGE OWNER:** beta | y | z |\n",
           encoding="utf-8",
       )
       control = (owner(base, d), owner(edited, d))
   print(f"control: base {control[0]!r}, edited {control[1]!r}")
   repos = sorted(p.parent.parent for p in Path("/opt").glob("*/docs/DECISIONS.md"))
   before = {r: owner(base, r) for r in repos}
   after = {r: owner(edited, r) for r in repos}
   tally = Counter(v.rsplit(" ", 1)[1] for v in before.values())
   print(f"ledgers {len(repos)}: base tallies {dict(sorted(tally.items()))}")
   diffs = [f"{r}: {before[r]} -> {after[r]}" for r in repos if before[r] != after[r]]
   print("\n".join(diffs) if diffs else "diff: none")
   ok = control == ("alpha rc=0", "beta rc=0") and not diffs and set(tally) <= {"rc=0", "rc=3"}
   print("PASS" if ok else "FAIL")
   sys.exit(0 if ok else 1)
   ```

7. `/fabrik-review-scoped` on Phase A's surface; fix what it finds.

**Behavior Contract (Phase A):**

- **Given** a ledger whose D-002 is `**MERGE OWNER:** beta` above `MERGE OWNER: alpha`, **When** the three readers resolve the owner, **Then** each returns `beta` (A1, spec V1)
- **Given** a higher-id row `**MERGE OWNER**: beta` — the bold closing before the colon — **When** the three readers resolve, **Then** each returns `beta` (A1b, spec V1)
- **Given** a higher-id row opening `Merge owner: rotated weekly` — and the same with `merge owner:`, `Merge Owner:`, `MERGE owner:`, `**Merge owner:**` — **When** the three readers resolve, **Then** each returns `alpha` (A2, spec V2; five spellings)
- **Given** a higher-id row `**MERGE OWNER:** UNDECLARED — un-adopted`, **When** the three readers resolve, **Then** each reports undeclared (A3, spec V3)
- **Given** a higher-id row `Merge owner: UNDECLARED` above `MERGE OWNER: alpha`, **When** the three readers resolve, **Then** each returns `alpha` — the un-adoption row obeys the same case rule, and its test comment names the cost spec § Lifecycle Failure states (A3b, spec D2)
- **Given** the existing case `bare-row-lowercase-phrase` (`merge owner: beta`), **When** the three readers resolve, **Then** each returns `alpha`, the row now prose (A4)
- **Given** `MERGE OWNER:*beta*`, `MERGE OWNER:***beta` and `**MERGE OWNER**:*beta*` as the higher-id row, **When** the three readers resolve, **Then** each returns `alpha` — the bold allowance is at most one `**` on each side of the colon, never a run (A5)
- **Given** the three source files, **When** the parity test reads their pattern text, **Then** each holds `(?-i:MERGE OWNER)(?:\*\*)?:(?:\*\*)?\s*` in its owner and un-adoption regex and `(?=(?-i:MERGE OWNER))` in `_SUPERSEDES_PREFIX`, and the hook's guard follows the phrase — the `prefix` (`:896`), `phrase` (`:897`), `uses` (`:903`) and `undeclared` (`:912`) literals updated; red today, and red on a mutant that moves the hook's guard before the bold token, which no reader output shows (A6)
- **Given** every other existing `_OWNER_CASES` row, **When** the three readers resolve, **Then** each keeps its answer (A7, spec V5)
- **Given** `supersedes D-001: **MERGE OWNER:** beta`, `**Supersedes D-001.** **MERGE OWNER:** beta` and `supersedes D-001: **MERGE OWNER**: beta`, added to `_SUPERSEDES_SPELLINGS` (`tests/test_session_orient_hook.py:1256-1266`), **When** the three readers resolve, **Then** each returns `beta` (A8, spec V1)
- **Given** a higher-id row `**MERGE OWNER:** rotated weekly`, **When** the three readers resolve, **Then** each returns `rotated` — the documented first-token limit (A9, spec § Goal)
- **Mocked:** nothing — the three-reader test runs the real hook, the real `docs_updater.read_merge_owner` and a real `decisions.py --merge-owner` subprocess over a synthetic ledger in `tmp_path`.

## Phase B — Finish — ✅ EXECUTED 2026-10-17 (155c07fcd)

Appetite: 60

**Steps** (sequential):
1. The whole-plan `/fabrik-review` (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice, the
   orchestrator executing every candidate), one receipt at
   `docs/development/reviews/2026-10-17-plan-1-merge-owner-grammar-review.md`.
2. `CHANGELOG.md` entry (`### Fixed — a merge-owner row is read only from the exact label, bold allowed (2026-10-17)`);
   the `docs/STRATEGIC_BACKLOG.md:52` row resolved with the commit; a `docs/DECISIONS.md` row only if the build takes a
   decision the spec did not (D-934 is the design row; the approval row is `/fabrik-plan-review`'s); `INDEX.md` rows
   for the two review receipts; then `/fabrik-docs-review` over the two edited docs and the changed comments.
3. `python scripts/final_gate.py --check --json` green (gated on its exit code); commit by pathspec with trailers; push;
   `merge_request.py request --review <receipt> --item W-5d3ed438`.

## File Scope (owned paths)

- `scripts/decisions.py`
- `scripts/docs_updater.py`
- `.claude/hooks/session_orient.py`
- `tests/test_session_orient_hook.py`
- `docs/reference/multi-agent-operating-model.md`
- `docs/workstation/hooks-index.md`
- `docs/superpowers/specs/2026-10-17-merge-owner-grammar-design.md`
- `docs/development/plans/2026-10-17-plan-1-merge-owner-grammar.md`
- `docs/development/reviews/2026-10-17-plan-1-merge-owner-grammar-review.md`
- `docs/development/reviews/2026-10-17-plan-1-merge-owner-grammar-plan-review.md`

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python | no deps-file edit; stdlib `re` only | CLEAN — no dependency file in § File Scope; hunted: Global Constraints |
| FLOOR 12-FACTOR | no config, no env, no service | CLEAN — the change is a regex in hub scripts and a hook; hunted: Phase A Interfaces |
| MATCHED core/40-documentation | one CHANGELOG entry; the two doc sentences; D-934 with the spec | CLEAN — Phase B step 2, Phase A step 5, the spec commit 0cbf8d780 |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red; the case rule graded on five spellings | CLEAN — A1–A9 (with A1b, A3b) map spec § Validation and § Goal (Self-audit); A2's bold spelling and A5 red on a mutant, A6 also on a guard-order mutant |
| RECURRENCE fail-open vs fail-closed | a row the grammar no longer reads falls back to the next declaration, never to an invented owner | CLEAN — A2, A4; spec § Lifecycle Failure |
| RECURRENCE cost/quota/limit accounting | none | CLEAN — no seat, quota or limit touched |
| RECURRENCE boundary/sentinel/prefix collisions | `**` vs `*` vs `***`; `**` before or after the colon; `**` before `UNDECLARED` vs the hook's guard; the supersedes prefix's own `[\s*]*` and its colon-less lookahead | CLEAN — A1b, A3, A5, A6, A8; `option_a.py` and `option_a_spellings.py` (the review's run folder `probes/`): 21 cases and 13 spellings, 0 wrong, 52 ledgers unchanged |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A row | CLEAN — Self-audit mapping |

Rubric invocation (verbatim output; the File Scope is the changed-path set):

```text
$ python scripts/review_rubric.py --changed scripts/decisions.py scripts/docs_updater.py .claude/hooks/session_orient.py tests/test_session_orient_hook.py docs/reference/multi-agent-operating-model.md docs/workstation/hooks-index.md docs/superpowers/specs/2026-10-17-merge-owner-grammar-design.md docs/development/plans/2026-10-17-plan-1-merge-owner-grammar.md CHANGELOG.md docs/DECISIONS.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: CHANGELOG.md, docs/DECISIONS.md, docs/development/plans/2026-10-17-plan-1-merge-owner-grammar.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_session_orient_hook.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 36 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `alembic upgrade head` `lifespan` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
```

## Evidence

Grounded at authoring (2026-10-17), executed. Three grounding seats ran (an Opus `fabrik-reviewer` census of every
production reader, a Sonnet `fabrik-reviewer` census of every test fixture and literal pin, a Haiku `fabrik-reviewer`
sweep of every prose statement of the rule); their findings are folded into the spec and Phase A, each re-executed
below.

- Today's grammar on the two gaps (`scripts/decisions.py:60-69`, imported with `python3 -B`):

```text
$ python3 -B owner_probe.py
'**MERGE OWNER:** coordinator — bold-wrapped label'      owner=None           undeclared=False
'**MERGE OWNER: coordinator** — bold-wrapped whole'      owner='coordinator'  undeclared=False
'Merge owner: rotated weekly between agents'             owner='rotated'      undeclared=False
'merge owner: agent-1'                                   owner='agent-1'      undeclared=False
```

- The grammar as planned BEFORE the design panel (one optional `**` after the colon only), with the bold token
  tightened to `(?:\*\*)?` after the Opus seat showed `\**` also accepts `MERGE OWNER:*a*` and `MERGE OWNER:***a`
  (`bold_probe.py`, run folder; 7 of its 11 case rows shown), and its owner diff over every ledger. The grammar as
  planned now — one optional `**` on each side of the colon — is probed by `option_a.py` (21 cases, 0 wrong, 52
  ledgers unchanged) and `option_a_spellings.py` (13 spellings, 0 wrong), § Coverage Checklist:

```text
$ python3 -B bold_probe.py
'Merge owner: a'                         owner=None     undeclared=False hook_owner=None
'**MERGE OWNER:** a'                     owner='a'      undeclared=False hook_owner='a'
'supersedes D-1: **MERGE OWNER:** b'     owner='b'      undeclared=False hook_owner='b'
'MERGE OWNER:*a*'                        owner=None     undeclared=False hook_owner=None
'MERGE OWNER:***a'                       owner=None     undeclared=False hook_owner=None
'MERGE OWNER:** UNDECLARED'              owner='UNDECLARED' undeclared=True  hook_owner=None
'**MERGE OWNER: a**'                     owner='a'      undeclared=False hook_owner='a'
ledgers 52: changed 0 []
```

- The census of declarations (`owner_census.py`): `ledgers: 52 · rows mentioning a merge owner: 50`; 9 open with the
  upper-case label, 4 with a supersedes prefix (one of them, hub D-874, declares), 37 mid-prose; 0 in another case; 0
  bold-wrapped. `python3 scripts/decisions.py --merge-owner .` prints `coordinator`, rc 0.
- Readers (the Opus seat, re-checked): the six symbols are used only inside their own files — `decisions.py:666`,
  `:669` (`_merge_owner`), `docs_updater.py:1592`, `:1595` (`read_merge_owner`, called at `:1609`, `:2266`, `:2535`),
  `session_orient.py:327`, `:330` (`_owner_in`); four programs run `decisions.py --merge-owner` (`scripts/work.py:2140`,
  `scripts/merge_request.py:304`, `.claude/hooks/final_gate_stop.py:2268-2271`, `scripts/check_commit_trailers.py:636`);
  no seventh copy of the grammar.
- Fixtures (the Sonnet seat, re-checked): 161 test lines mentioning a merge owner examined; one case changes its answer,
  `tests/test_session_orient_hook.py:1302`; in the literal pins (`:879-920`) the `phrase` (`:897`), `uses` (`:903`) and `undeclared` (`:912`) literals move to the new phrase; no test fixture uses
  `**MERGE OWNER:**` with the colon inside the bold.
- Prose (the Haiku seat): 63 lines examined outside the frozen specs and plans; two state the rule —
  `docs/reference/multi-agent-operating-model.md:122-126`, `docs/workstation/hooks-index.md:16` — plus the backlog row
  `docs/STRATEGIC_BACKLOG.md:52` that names this gap.
- Baseline of the owner tests today:

```text
$ timeout 300 prlimit --as=8589934592 -- .venv/bin/python -m pytest tests/test_session_orient_hook.py -q --timeout=120 -k "owner or grammar or merge" -p no:cacheprovider
44 passed, 57 deselected in 5.47s
```

- External: field research fetched 2026-10-17 and byte-checked with curl — https://git-scm.com/docs/git-interpret-trailers,
  https://www.rfc-editor.org/rfc/rfc9110.txt, https://raw.githubusercontent.com/npryce/adr-tools/master/src/_adr_status
  (spec § Chosen approach carries every quote).

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: V1 → A1, A1b, A8, V2 → A2, V3 → A3, V4 → Phase A step 6, V5 →
  A7; A3b (a mixed-case un-adoption, spec D2), A4 (the flipped pin), A5 (the bold token's tightness) and A6 (the parity
  pin) come from the grounding seats; A1b, A8 and A9 (the first-token limit, spec § Goal) from the design panel.
- Every item in What we already agreed maps to Phase A (D1–D4) or Phase B (review, CHANGELOG, backlog row, merge
  request).
- Diff estimate ≈30 code lines in 3 code files (tests excluded): inside `Profile: small` (≤ ~400, ≤ 5).
- Cross-phase names: no symbol is produced in one phase and consumed in another; the six regex names are unchanged.
- Every touchpoint is a `path:line` in today's files, re-read by the grounding seats.

## Residual unknowns

- **R1 — resolved.** The bold token's width: one optional `(?:\*\*)?` on each side of the colon, not `\**` (Evidence;
  the design panel's colon-outside spelling).
- **R2 — resolved.** No reader beyond the three files parses the label; the four subprocess callers take the winning
  row only (Evidence).
- **R3 — open, by design.** Between merge and the next governance sync, a project's synced `docs_updater.py` and
  `session_orient.py` keep the old grammar while the hub-absolute readers use the new one; spec § Lifecycle names the
  window and the census shows it holds no row today.

## Execution notes

Executed 2026-10-17 by `/fabrik-execute-plan` on worktree-intel, base `fafc2db2d` (the step-8 baseline; lean gate
`success`, nothing red at start).

**Phase A.**
- Step 1 — the graders written first and watched red against today's grammar, exactly the planned set:

```text
$ timeout 300 prlimit --as=8589934592 -- .venv/bin/python -m pytest tests/test_session_orient_hook.py -q --timeout=120 -p no:cacheprovider -k "owner_readers or grammar_tracks"
14 failed, 27 passed, 76 deselected in 4.82s
```

  (A6 the parity pins, A4, A2 ×4, A1, A1b, A3, A3b, A9, A8 ×3; A2's `**Merge owner:**` and A5 ×3 green today.)
- Step 2 — the six patterns and the supersedes lookahead edited; `ruff format` run on `scripts/decisions.py` and
  `scripts/docs_updater.py` only. **Deviation:** `.claude/hooks/session_orient.py` was already not
  `ruff format`-clean at HEAD (`ruff format --check` rc 1 before any edit), and formatting it re-wrapped untouched
  code in `main()` and `_mcp_line()`, so the hook's edit is the three pattern lines alone, unformatted — the
  pre-existing format debt is the hook's, not this change's.
- The mutants, run after step 2 in a throwaway worktree at HEAD with the edited test file and three sources copied
  in, each turn their named case red, and the restored tree is green:

```text
$ python3 -B mutants.py <probe>
no-case-group: files changed 3, failed 8, named case red: True
star-run: files changed 3, failed 4, named case red: True
guard-first: files changed 1, failed 1, named case red: True
restored: 41 passed, 76 deselected in 5.32s
```

- Step 4 — the readers' suites, one file at a time: `tests/test_session_orient_hook.py` 117 passed,
  `tests/test_decisions_helper.py` 38 passed, `tests/test_docs_updater_adopt.py` 147 passed,
  `tests/test_stop_hook_merge_requests.py` 30 passed; `ruff check` clean on the four files, `ruff format --check`
  clean on the three that were clean before.
- Step 6 — `python3 scripts/decisions.py --merge-owner .` prints `coordinator` (rc 0), and the driver:

```text
$ python3 owners_diff.py base_decisions.py scripts/decisions.py
control: base 'alpha rc=0', edited 'beta rc=0'
ledgers 52: base tallies {'rc=0': 9, 'rc=3': 43}
diff: none
PASS
```

## Pass Ledger

Written by `/fabrik-plan-review`; the candidates and their dispositions are in
`docs/development/reviews/2026-10-17-plan-1-merge-owner-grammar-plan-review.md`.

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (O: spec What exists/Chosen/Delta/Validation/Decisions + plan Global Constraints/Phase A/File Scope/Digest/Checklist/Evidence) + sonnet×1 (S: every other section of both) · all axes; shape: agent-tool | found: 16, new: 16, confirmed: 11, fixed: 11, unexecuted: 0, edits: 20 | method: citation + re-derivation — full pass; the orchestrator executed every candidate (`pass1_verify.py`, `rule_cases.py`, the real-reader owner loop) | a72b988a… → 5c6a9983… (plan); spec fc30bdb7… → 8a4602fa… |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-1 fix hunks + one hop; shape: agent-tool | found: 7, new: 7, confirmed: 3, fixed: 3, unexecuted: 0, edits: 4 | method: re-derivation — the 13 pass-1 ledger rows re-executed (all CLOSED; the step-6 loop run as a python driver and against a broken-prefix mutant, `rule_cases.py` re-run, the pins probed on edited copies); 3 confirmed, all own-fix of pass 1 (the step-6 loop broke when pasted, its live-ledger window, A3b missing from step 1's red list) | 0a097a56… → 9c91b6e4… (plan); spec 8a4602fa… → 8a4602fa… |
| Pass 3 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-2 fix hunks; shape: agent-tool | found: 5, new: 5, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — the 6 pass-2 rows re-executed (step 6's two loops run against a base copy and an edited copy: 52 lines, 9 `rc=0`, 43 `rc=3`, diff empty); 2 confirmed, both own-fix of pass 2 (the fix script corrupted the text around step 6; `<base SHA>` undefined); scope-growth stop fired (own-fix 3/3 → 2/2) | 90129f68… → 04726964… (plan); spec 8a4602fa… → 8a4602fa… |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the pass-3 fixed set (the scope-growth stop's remainder round); standing clean since Pass 1: every other class; shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the fixed set re-derived from the pin (steps 1–7 consecutive, one step 6, the Phase A heading, eight `- **Given**` rows A1–A7 with A3b; the pin diffed against d908e2058: exactly the four intended hunks; `<base SHA>` defined); load-bearing claims re-derived (the six touchpoint lines, `rule_cases.py` 11/0, 52 ledgers, intake 6/6 and 4/4, V1–V5 mapping) | 5470f1f7… → 5470f1f7… ✓ (plan); spec 8a4602fa… → 8a4602fa… ✓ |
| Pass 5 | opus×1 + sonnet×1 (round-1 owners) · the design panel's delta round over its 8 accepted changes; shape: agent-tool | found: 8, new: 8, confirmed: 6, fixed: 6, unexecuted: 0, edits: 7 | method: re-derivation — every A1–A9 case and the 9 existing supersedes spellings run against today's and the edited grammar (26 cases, 0 wrong); step 6's embedded driver extracted and run (PASS today-vs-edited, FAIL today-vs-today and against a broken-prefix mutant); the updated parity pins true on edited copies, false today; 7 of 8 accepted changes made, 6 defects confirmed in the fold (own-fix: the panel fold) | 826f27e6… → 4e976958… (plan); spec 918e920a… → c56d97d6… |
| Pass 6 | opus×1 + sonnet×1 (round-1 owners) · the pass-5 fixed set (the scope-growth stop's remainder round); standing clean since Pass 1: every other class; shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the fixed set re-derived from the pin (step 1's red/green lists against every case, the three named mutants on edited copies, D2's wording, the A5 wording, the D-738 citation, the Self-audit ids against 11 `- **Given**` rows) | e0482c47… → e0482c47… ✓ (plan); spec c56d97d6… → c56d97d6… ✓ |
