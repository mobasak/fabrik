# Plan — least operator approval: the gate model rewritten to D-1110 (W-4a03df79)

Status: DRAFT
Profile: small
**Owner:** kaizen (Phase B: infra)
**Surface:** `git rev-parse HEAD` = bcf74f6e1 at authoring; `CLAUDE.md:614`, `:639`; `templates/governance/CLAUDE.md:616`;
`commands/_fragments/design-gate-panel.md:1-3`; `commands/_sources/fabrik-deploy-plan-review.md:29`, `:251-258`;
`commands/_sources/fabrik-release.md:2`, `:205-212`; `commands/assemble_commands.py:71`, `:73`;
`.claude/hooks/final_gate_stop.py:3067-3073`, `:3104`, `:4239-4262`; `tests/test_decision_panel.py:440-446`

Spec: `docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` (DRAFT, `Size: small`, `Profile: delta`;
approach B, D-1110). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source: operator
ruling D-1110 → work item W-4a03df79 (P0), routed by the coordinator. Estimated diff: ≈30 code lines across TWO code
files — the NEXT-map strings in `commands/assemble_commands.py` (2 lines) and the hook's operator-kept regex plus its
branch and message in `.claude/hooks/final_gate_stop.py` (≈25 lines); tests ≈80 lines; the rest is contract and
command text.

## What this plan is

Three inline phases; no coder is dispatched. Phases A and C are coded by kaizen in `worktree-kaizen`; Phase B is the
hook, infra's code (`docs/reference/agents/kaizen.md` § Method step 3), built by infra and carried into the same branch
so text and hook land in ONE merge (spec § Chosen approach):

- **A — the contracts and commands** (kaizen): spec § The delta D1–D4 and the new grader
  `tests/test_least_operator_approval.py`.
- **B — the hook** (infra): spec § The delta D5 — kaizen mails infra the exact diff below; infra commits it on
  `worktree-infra` and pushes; kaizen cherry-picks that one commit onto `worktree-kaizen`, its trailers intact
  (`Agent-Name: infra`).
- **C — Finish** (kaizen): the whole-plan `/fabrik-review`, CHANGELOG, INDEX, the fabrik-lib mail (I12), the gate,
  commit, push, merge request.

Phases A and B end with `/fabrik-review-scoped` on their surface; the Finish runs the ONE heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor — both contracts are governance-sync paths and the hook is enforcement) and writes one
receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I11 (11 IN) | IN as dispositioned there | Phases A–C, per the spec rows |
| I2 | spec I12, fabrik-lib's own contract (OUT-OF-SCOPE there) | IN as a mail only | Phase C step 3 |
| I3 | *"Intel's lock release is on master as of 16b8494b8 … merge master into your worktree first"* (coordinator, 2026-10-22) | IN | Phase A step 0 |
| I4 | *"the hook regex and its printed list are an infra ticket inside the plan, mailed with the exact diff"* (coordinator routing) | IN | Phase B |

Intake: 4 items — 4 IN, 0 OUT-OF-SCOPE, 0 ASK.

## What we already agreed (citations, not restatement)

- Goal, personas and the executed census: `spec § Goal`, `spec § Personas`, `spec § What exists today`.
- The delta D1–D5 and the invariants: `spec § The delta`; approach B against A and C, the field grounding and the
  three judges: `spec § Chosen approach`, `spec § Rejected alternatives`; validation: `spec § Validation`; the lock
  ordering and degradation: `spec § Lifecycle`. The approval row is minted by `/fabrik-plan-review` at its gate (a
  `Size: small` spec is approved there, not here); D-1110 is the governing row.

## Global Constraints (every phase inherits these)

- **The twin stays byte-identical.** The hub and template gate paragraphs differ only by "kept whole from (hub)
  D-054:" (`tests/test_governance_template_split.py:1306`, compared at `:1387`); the closed token list (`:1087`) and
  the `` `gate` — a **contractual human gate**, named by a token from the closed list `` pin (`:1476`) are kept
  verbatim; no D-id is written into the gate paragraph.
- **D-054's three grounds stand** — no new ground token; a panel-decided gate that splits is `ground: gate` plus the
  `Panel:` line.
- **The build writes neither CLAUDE.md before master is merged in** (Phase A step 0): intel's release of the plan-3
  lock is on master at 16b8494b8.
- **Kaizen never edits the hook** (`.claude/hooks/final_gate_stop.py`, `tests/test_decision_panel.py`): Phase B is
  infra's commit, cherry-picked unchanged.
- **No new dependency** (`core/10-python.md:30`); `re` only.
- **Tests:** one per behaviour, watched-fail-first (`core/45-testing-strategy.md:22`). Every pytest run is
  `/opt/fabrik/scripts/capped_run.sh -- timeout 300 .venv/bin/python -m pytest <files> -q --timeout=120 -p
  no:cacheprovider`, from `/opt/fabrik/.claude/worktrees/kaizen`. The merged-tree check runs the 54 test files that
  read command sources (spec § Validation), not only the edited files' own.
- Seats never mutate git state; never write outside their absolute scratch folder, `cd` to it first.
- **Execution discipline (native seats only, D-181):** each of Phases A and B ends with `/fabrik-review-scoped` (the
  floor of three native seats, stamped with `command_run.py dispatch`) and does not hand on until its closing pass
  confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku
  finder per slice (D-344), the orchestrator executing every refutation and reproduction; the slices fan out in
  parallel and their candidates merge and dedupe at the orchestrator.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | no deps-file edit | `core/10-python.md:30` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, CLAUDE.md, design-gate-panel.md) | one CHANGELOG entry | `core/40-documentation.md:134` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — the two test files) | one test per behaviour; seen red; a guard graded on five legitimate spellings | `core/45-testing-strategy.md:21`, `:22` |
| `docs/DECISIONS.md` D-1110 | the panel/operator split, the coordinator route | `docs/DECISIONS.md:1121` |
| `docs/reference/agents/kaizen.md` | code findings go to their beat, never patched by kaizen | § Method step 3 |
| `fabrik-lib` | no module carries the gate model — BUILD (edit in place) | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | untouched — governance text and a hook, no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| Name exactly ONE ground in the heading. | `CLAUDE.md:614` |

## Phase A — the contracts and commands

Appetite: 90

**Interfaces — Produces** (consumed by Phase B's hook, which keys on the class words the contract tells agents to
write): the operator-kept class phrases on a block's "Why it is yours" line — `above the ceiling`, `recurring`,
`only the operator can mint`, `customer-facing`, `public`, `no backup` — written into D1's clause exactly so.

**Consumes:** nothing from another phase.

**Steps** (sequential):

0. Merge master into `worktree-kaizen` (`git merge --no-commit origin/master`, then a trailered commit) and confirm
   `.fabrik/plan-locks/2026-10-21-plan-3-own-scrape-slice-1a.json` no longer lists either CLAUDE.md in
   `owned_paths` (`python3 -c` over the JSON; expected: neither path present).
1. Write `tests/test_least_operator_approval.py` (Behaviour Contract A1–A6 below) and run it: every case red on
   today's text, each for the reason it names (the old clause present, the new phrase absent).
2. **D1** — in `CLAUDE.md:614` and `templates/governance/CLAUDE.md:616`, replace the clause "design approval is first
   answered by the Opus + Fable panel the design-gate review commands dispatch in the operator's place, and only a
   split panel reaches the operator, its block carrying the `Panel:` line." with, identically in both files:

   > each class a coordinator can validate is first answered by the Opus + Fable panel in the operator's place —
   > design and plan approval (the design-gate review commands dispatch it), Gate 1, Gate 2 to our own VPS when the
   > plan carries a backup and a rollback, a destructive act with a verified backup first (the ad-hoc-branch
   > disposition included), a production-data window that dumps first and keeps the old volume, credentials the
   > fleet mints itself, publishing to our own surfaces, and spend inside the operator's ceiling (0 until the operator
   > sets one) — and only a split panel reaches the operator, its block carrying the `Panel:` line; the operator alone
   > decides, and the block's Why line names the class token and which of these it is, spend above the ceiling or a recurring contract, credentials only
   > the operator can mint, publishing to customers or the public (a customer-facing production deploy included), and
   > deleting data with no backup; a builder's block reaches the operator only through its coordinator.

3. **D2** — in `CLAUDE.md:639`, replace "`gate` and `owned` stay the operator's — a panel never approves a gate class
   (design approval excepted: the design-gate review commands hand it to the panel, D-613) or answers the operator's
   own question." with:

   > `owned` stays the operator's, and so do the gate classes § FINAL OUTPUT keeps for the operator (D-1110, superseding
   > this paragraph's "a panel never approves a gate class"); the panel decides every other gate class and never
   > answers the operator's own question, and a coordinator validates its two reports against the repo and the box
   > before acting on them. A coordinator asks the operator a clarifying question only when the answer materially
   > changes the work and the repo is silent, batched as one short list per session; an act Claude Code's auto-mode
   > classifier still refuses after a panel approved it goes to the operator once per class, as a settings permission
   > rule (D-1110).

4. **D3** — `commands/_fragments/design-gate-panel.md:1-3`: "(operator ruling 2026-10-06, D-613 — for design approval
   only, it supersedes D-558's "a panel never approves a gate class" and D-153's printed presentation)" becomes
   "(operator ruling 2026-10-06, D-613, widened to every gate class a coordinator can validate by D-1110 — CLAUDE.md §
   FINAL OUTPUT's gate ground holds the list; it supersedes D-153's printed presentation)".
5. **D4** — the deploy triad and release:
   - `commands/_sources/fabrik-deploy-plan-review.md:29`: "next: Gate 2 (the operator's explicit go)" → "next: Gate 2
     (the Opus + Fable panel's go for our own VPS with a backup and a rollback; the operator's for a customer-facing
     production deploy or a split)".
   - `:251-258`: before the block, one sentence — the panel (CLAUDE.md § Autonomy, two `fabrik-reviewer` seats, opus
     and fable, stamped `command_run.py dispatch --seats 2`) answers Gate 2 for a deploy to our own VPS whose plan
     carries a backup and a rollback and whose target is not customer-facing; an agreeing panel's go dispatches
     `/fabrik-deploy <plan>` with no block. The block's Why line becomes "Gate 2 — a customer-facing production deploy
     is publishing to the public, kept by the operator; or the panel split, its `Panel:` line below." and the block
     gains `- Panel: opus="<verdict>" fable="<verdict>" → split` (dropped for a customer-facing deploy). The
     `Next command:` line and `commands/assemble_commands.py:73` become "Gate 2 — the panel's go (own VPS, backup +
     rollback); the operator's for customer-facing deploys or a split: /fabrik-deploy <plan>."
   - `commands/_sources/fabrik-release.md:205-212`: the Why line becomes "Gate 2 — a store submit or a customer-facing
     deploy is publishing to the public, kept by the operator; a VPS hand-off to our own, non-customer-facing service
     goes to the panel first, and reaches you only on a split (`Panel:` line below)."; the `Next command:` line,
     `commands/assemble_commands.py:71` and the frontmatter description at `:2` ("Gate 2 (human approval, R14)") say
     "Gate 2 — the panel's go for our own VPS; the operator's for stores, customer-facing deploys or a split".
   - Read and kept: `commands/_sources/fabrik-deploy.md:240` (an OPERATOR-GATE act no agent can perform — not an
     approval) and `:359` (publishing to users — the operator's class); `fabrik-decommission.md:21` (residual R3).
6. Run `tests/test_least_operator_approval.py` green, then `tests/test_governance_template_split.py`,
   `tests/test_gate_decision_blocks.py`, `tests/test_stop_hook_deferral_exemption.py`,
   `tests/test_check_command_corpus.py`; `python3 commands/assemble_commands.py --check` (a temp-dir render, safe from a
   worktree) exits 0.
7. Commit Phase A by pathspec with trailers; `/fabrik-review-scoped` on its surface; fix what it finds.

**Behavior Contract (Phase A):**

- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the panel-decided classes (plan approval, Gate 1, Gate 2 to our own VPS, a verified backup, a dump, credentials the fleet mints, our own surfaces, the ceiling) and "only a split panel reaches the operator", and neither holds "design approval is first answered" (A1)
- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the six operator-kept phrases and "only through its coordinator" (A2)
- **Given** the hub contract, **When** the grader reads § Autonomy, **Then** it cites D-1110 and the clarifying-question and classifier sentences, and no longer holds "`gate` and `owned` stay the operator's" (A3)
- **Given** the template, **When** the grader reads it, **Then** § Autonomy's hub-only sentence is absent and the twin test still passes (A4)
- **Given** `fabrik-deploy-plan-review.md`, `fabrik-release.md` and the NEXT map, **When** the grader reads them, **Then** none holds "the operator's explicit go" or "Gate 2 — human approval", and each names the panel's go and the customer-facing case (A5)
- **Given** `design-gate-panel.md`, **When** the grader reads it, **Then** it cites D-1110 and no longer says "for design approval only" (A6)
- **Mocked:** nothing — the grader reads the real files from the tree it sits in.

## Phase B — the hook (infra)

Appetite: 60

**Consumes:** Phase A's operator-kept phrases (Interfaces above).

**Produces:** `.claude/hooks/final_gate_stop.py::_OPERATOR_GATE_RE` (new, beside `_DECISION_GATE_RE` at `:3067`), read
only by `parse_decision_block`'s gate branch (`:4239`).

**Steps** (sequential):

1. Kaizen mails infra (`mail.py send --to fabrik --to-agent infra --kind request`, the D-035 contract) the diff below
   and the Behaviour Contract B1–B5, and pings it live.
2. Infra writes B1–B5 in `tests/test_decision_panel.py` and sees B1 red on today's hook (B3–B5 pass today and are
   proven red on a mutant that drops the `not _OPERATOR_GATE_RE.search(why)` guard, run in a throwaway worktree). Two
   existing tests change by substitution, each naming the guard it keeps: `test_deploy_gate_needs_no_panel`
   (`:440-446`) becomes B1 — its Why "Gate 2, deploy to production" now needs the split panel, the guard B1 keeps;
   and `test_owned_and_gate_stay_the_operators` (`:388-393`) keeps its `owned` half and its gate half's Why becomes
   "deploy — Gate 2, a customer-facing production deploy", so it still exercises the operator-kept pass that B3 also
   covers. Then it applies the diff; runs `tests/test_decision_panel.py`,
   `tests/test_gate_decision_blocks.py` and `tests/test_final_gate_stop_hook.py` green; commits on `worktree-infra`
   with its trailers; pushes; sends kaizen the SHA.
3. Kaizen `git cherry-pick <sha>` onto `worktree-kaizen`, re-runs the three files there, and
   `/fabrik-review-scoped` on the hook's diff; a finding goes back to infra, never patched by kaizen.

The diff (spec D5; infra may reshape it, the behaviour is fixed):

```python
# :3073, after _DECISION_GATE_RE — the gate classes D-1110 keeps for the operator. A `ground: gate`
# block naming one needs no panel; every other gate class is the panel's, so in autonomy mode its
# block reaches the operator only on a SPLIT `Panel:` line. COBRA (D-253): the cheapest way past
# is to write "public" on a panel-decided block; the block then reaches the coordinator, whose job
# is to validate the class against the Question line, and the Question shows it.
_OPERATOR_GATE_RE = re.compile(
    r"\babove the (?:spend )?ceiling\b|\brecurring\b|\bonly the operator can mint\b"
    r"|\bcustomer[- ]facing\b|\bpublic\b|\bno backup\b",
    re.I,
)

# :4239-4256, the gate branch — the panel check moves from design approval alone to every
# panel-decided class:
    if ground == "gate":
        design_gate = re.search(
            r"\b(?:design|plan) approval\b", why, re.I
        ) or _DESIGN_ASK_RE.search(fields["Question"])
        if _PANEL_MODE and not _OPERATOR_GATE_RE.search(why):
            if design_gate and not _SEARCHED_EVIDENCE_RE.search(why):
                return False, (...)  # unchanged
            problem = _panel_problem(
                fields.get("Panel", ""),
                transcript_path,
                ground="a panel-decided gate (D-1110: only a split panel reaches the operator)",
                outcomes=("split",),
            )
            if problem:
                return False, problem
```

Plus: the `:3104` comment "`owned` … and `gate` (the closed list) stay the operator's" becomes "`owned` stays the
operator's, and so do the gate classes `_OPERATOR_GATE_RE` names (D-1110)"; the `:4258-4262` refusal text appends "; a
panel-decided class carries a split `Panel:` line, an operator-kept one names its class (above the ceiling ·
recurring · only the operator can mint · customer-facing · public · no backup)".

**Behavior Contract (Phase B):**

- **Given** autonomy mode and a `ground: gate` block "Gate 2, deploy to our own VPS" with no `Panel:` line, **When** the hook parses it, **Then** it is refused naming D-1110 (B1)
- **Given** autonomy mode and that block with a verified split `Panel:` line, **When** the hook parses it, **Then** it passes as `gate` (B2)
- **Given** autonomy mode and an unpaneled gate block whose Why line names an operator-kept class beside its class token — written five ways: "publish — publishing to the public", "deploy — Gate 2, a customer-facing production deploy", "spend — above the ceiling", "spend — a recurring contract", "destructive — deleting data with no backup" — **When** the hook parses each, **Then** each passes as `gate` (B3)
- **Given** autonomy mode and an unpaneled block "credentials only the operator can mint", **When** the hook parses it, **Then** it passes (B4)
- **Given** autonomy mode OFF (a project repo), **When** the hook parses the B1 block, **Then** it passes as today (B5)
- **Mocked:** nothing — the tests drive the real `parse_decision_block` over synthetic transcripts in `tmp_path`, as the file's existing cases do.

## Phase C — Finish

Appetite: 60

**Steps** (sequential):

1. The merged-tree check: merge master again if it moved, then run the 54 command-source test files (Global
   Constraints) plus the Phase A and B files; all green.
2. The whole-plan `/fabrik-review` (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice, the
   orchestrator executing every candidate), one receipt at
   `docs/development/reviews/2026-10-22-plan-1-least-operator-approval-review.md`.
3. `CHANGELOG.md` entry (`### Changed — least operator approval: the panel decides every gate class a coordinator
   can validate (2026-10-22)`); `INDEX.md` rows for the plan and the two review receipts; a `docs/DECISIONS.md` row
   only if the build takes a decision the spec did not; mail fabrik-lib the rewritten gate paragraph for its own
   contract (spec I12, `mail.py send --to fabrik-lib --kind request`); then `/fabrik-docs-review` over the edited
   contracts and command sources.
4. `python scripts/final_gate.py --check --json` green (gated on its exit code) and
   `python scripts/enforcement/check_convergence.py`; a green gate is necessary, not sufficient — the Evidence is the
   proof. Commit by pathspec with trailers; push; `merge_request.py request --review <receipt> --item W-4a03df79`.

## File Scope (owned paths)

- `CLAUDE.md`
- `templates/governance/CLAUDE.md`
- `commands/_fragments/design-gate-panel.md`
- `commands/_sources/fabrik-deploy-plan-review.md`
- `commands/_sources/fabrik-release.md`
- `commands/assemble_commands.py`
- `.claude/hooks/final_gate_stop.py`
- `tests/test_least_operator_approval.py`
- `tests/test_decision_panel.py`
- `docs/superpowers/specs/2026-10-22-least-operator-approval-design.md`
- `docs/development/plans/2026-10-22-plan-1-least-operator-approval.md`
- `docs/development/reviews/2026-10-22-plan-1-least-operator-approval-review.md`
- `docs/development/reviews/2026-10-22-plan-1-least-operator-approval-plan-review.md`

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python | no deps-file edit; stdlib `re` only | CLEAN — no dependency file in § File Scope; hunted: Global Constraints |
| FLOOR 12-FACTOR | no config, no env, no service | CLEAN — governance text, a NEXT map and a hook regex; hunted: Phase B Produces |
| MATCHED core/40-documentation | one CHANGELOG entry; INDEX rows; the contracts are the docs | CLEAN — Phase C step 3 |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red; the operator-kept regex graded on five spellings | CLEAN — A1–A6 red on HEAD (Phase A step 1); B3 carries five spellings as cases |
| RECURRENCE fail-open vs fail-closed | an unpaneled panel-decided block must be refused, an operator-kept one must pass; a project repo (autonomy off) keeps today's rule | CLEAN — B1, B3, B5 |
| RECURRENCE cost/quota/limit accounting | the spend ceiling is 0 until set, so every spend gate is operator-kept today | CLEAN — D1's clause; R2 |
| RECURRENCE boundary/sentinel/prefix collisions | `public` vs `publish` vs `unpublished`; `customer-facing` vs `customer facing` | CLEAN — word-boundary regex, the hyphen-or-space class; B3 |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A or B row | CLEAN — Self-audit mapping |

Rubric invocation (verbatim output; the File Scope plus the governance files is the changed-path set; the `#
promote-to-check_*` tail is elided here):

```text
$ python scripts/review_rubric.py --changed CLAUDE.md templates/governance/CLAUDE.md commands/_fragments/design-gate-panel.md commands/_sources/fabrik-deploy-plan-review.md commands/_sources/fabrik-release.md commands/assemble_commands.py .claude/hooks/final_gate_stop.py tests/test_decision_panel.py tests/test_least_operator_approval.py docs/development/plans/2026-10-22-plan-1-least-operator-approval.md CHANGELOG.md docs/DECISIONS.md
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

### core/40-documentation.md  (hit: CHANGELOG.md, CLAUDE.md, commands/_fragments/design-gate-panel.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_decision_panel.py, tests/test_least_operator_approval.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
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
```

## Evidence

Grounded at authoring (2026-10-22), executed.

- The two target sentences, one copy each (`spec § What exists today`, re-read): `CLAUDE.md:614` and
  `templates/governance/CLAUDE.md:616` differ only by `hub D-054` (`diff` of the two lines); `CLAUDE.md:639` holds the
  § Autonomy sentence; the template has no § Autonomy copy.
- No test pins the replaced sentences: `grep -rln "design approval is first answered\|a panel never approves a gate
  class\|stay the operator's"` over `tests/ scripts/ .claude/hooks/ commands/ templates/ docs/reference` returns 4
  files — `tests/test_decision_panel.py` (a docstring, `:441`), `commands/_fragments/design-gate-panel.md` (D3),
  `.claude/hooks/final_gate_stop.py` (D5) and `templates/governance/CLAUDE.md` (D1).
- The old model in the command corpus (`grep -n -i "gate and owned stay\|panel never approves\|operator's explicit
  go\|human approval"` over `commands/_sources/*.md commands/_fragments/*.md`, 9 lines in 6 files): the 5 in
  `fabrik-deploy-plan-review.md` (:29, :253, :258), `fabrik-release.md` (:2, :212) and `design-gate-panel.md` (:2) are
  Phase A's; `fabrik-decommission.md:21`, `fabrik-workflow-review.md:66`, `fabrik-vision.md:531` and
  `cert-execution.md:31` use "human approval" or "explicit go" for other things and are kept (R3 for decommission).
- The hook's gate branch today (`.claude/hooks/final_gate_stop.py:4239-4256`): the panel check runs only when
  `design_gate` matches; `_DECISION_GATE_RE` (`:3067-3073`) is the closed list; the refusal text (`:4258-4262`).
- Phase B's diff, prototyped before any seat saw it: applied by an anchor-keyed script
  (`apply_hook_diff.py`, the session scratchpad) to a throwaway worktree of 87cfa3895 under this run's `SCRATCH:`
  folder, then the hook suites and a probe over the Behaviour Contract inputs run there. The suites: exactly the two
  tests Phase B step 2 names go red, every other case passes —

```text
$ pytest tests/test_decision_panel.py tests/test_gate_decision_blocks.py tests/test_final_gate_stop_hook.py tests/test_final_gate_stop_deferral.py -q
FAILED tests/test_decision_panel.py::test_owned_and_gate_stay_the_operators
FAILED tests/test_decision_panel.py::test_deploy_gate_needs_no_panel - Assert...
2 failed, 414 passed, 2 skipped in 21.07s
```

  The probe (`test_zz_probe_b.py`, autonomy mode, each Why line parsed unpaneled and, for the panel-decided ones,
  with a verified split): it found that "a recurring contract" and "deleting data with no backup" alone name no token
  of the closed list and are refused as classless, so D1 tells the block to write the class token beside the
  operator-kept phrase and B3's spellings carry one; "unpublished" stays panel-decided (word boundary on `public`):

```text
KEPT     'gate — publishing to the public'                              unpaneled -> True 'gate'
KEPT     'gate — Gate 2, a customer-facing production deploy'           unpaneled -> True 'gate'
KEPT     'gate — spend above the ceiling'                               unpaneled -> True 'gate'
KEPT     'gate — a recurring contract'                                  unpaneled -> False '`ground: gate` names no gate class on its "Why it is yours" '
KEPT     'gate — deleting data with no backup'                          unpaneled -> False '`ground: gate` names no gate class on its "Why it is yours" '
KEPT     'gate — credentials only the operator can mint'                unpaneled -> True 'gate'
KEPT     'gate — Gate 2, a customer facing deploy'                      unpaneled -> True 'gate'
PANELLED 'gate — Gate 2, deploy to our own VPS'                         unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — destructive, with a verified backup'                   unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — credentials the fleet mints itself'                    unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — publish to our own surfaces'                           unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — production data window, dump first'                    unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — unpublished draft, publish later'                      unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — design approval of docs/superpowers/specs/x-design.md' unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
14 passed in 0.52s
```

- Baseline of the four suites the phases touch:

```text
$ /opt/fabrik/scripts/capped_run.sh -- timeout 300 .venv/bin/python -m pytest tests/test_decision_panel.py tests/test_governance_template_split.py tests/test_gate_decision_blocks.py tests/test_stop_hook_deferral_exemption.py -q --timeout=120 -p no:cacheprovider
162 passed in 4.61s
```

- The lock: the coordinator's message of 2026-10-22 — intel's release is on master at 16b8494b8; Phase A step 0
  re-reads the lock file after the merge.
- External: spec § Chosen approach and § External dependencies carry the three quotes (teamdynamix, reed.edu,
  claude.com/blog/auto-mode), fetched 2026-10-22.

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: the twin test → A4; the new grader → A1–A3, A5, A6; the hook
  cases → B1–B5; the merged-tree check → Phase C step 1.
- Every delta maps to a step: D1 → A2, D2 → A3, D3 → A4, D4 → A5, D5 → Phase B; I12 → Phase C step 3.
- Diff estimate ≈30 code lines in 2 code files (tests excluded): inside `Profile: small` (≤ ~400, ≤ 5).
- Cross-phase names: Phase B consumes Phase A's six operator-kept phrases; Phase A's D1 text and Phase B's regex both
  list them, and B3 grades five of them as written.
- Every touchpoint is a `path:line` in today's files, re-read at authoring.

## Residual unknowns

- **R1 — resolved.** How the hook tells a panel-decided gate from an operator-kept one: the Why line names the class,
  as the gate ground already requires, and the operator-kept phrases are a closed set (Phase B).
- **R2 — open, by design.** The spend ceiling is 0 until the operator sets it, so every spend gate is operator-kept
  today; the text needs no change when it is set (spec § Lifecycle Growth). A spend block must write "above the
  ceiling" to pass unpaneled — the D1 clause tells agents so.
- **R3 — open, kept.** `fabrik-decommission.md:21`'s confirmation gate deletes a service's data; whether its runbook
  carries a verified backup is not established here, so it stays the operator's (the most-reversible default) until
  a decommission run shows the backup.
- **R4 — open, by design.** Between merge and the next governance sync, a project's synced hook keeps the old rule;
  projects run with autonomy off (B5), so their behaviour does not change either way.
