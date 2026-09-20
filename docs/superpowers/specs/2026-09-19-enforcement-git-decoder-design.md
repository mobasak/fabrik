# Design — a shared git-output decoder for `scripts/enforcement/`

**Status:** CONVERGED
**Owner:** infra
**Surface:** `scripts/enforcement/` (fleet-synced to ~46 repos, 50 on-disk copies) — one new module plus a migration of 85 call sites across 35 files
**Lane:** rule 1 (a governance-sync path is a public contract for ~46 repos) — right-now is refused; the build takes the full `/fabrik-review` and a forced `sync_enforcement_to_projects.py --force`
**Origin:** web-ecommerce-factory `01M2X0ZQX8YMZX022R9TC1E3M6`, whose reported crash was fixed in one file at `e33dcdd63` (D-308); this spec is the routed remainder.

## Intake Inventory

The operator dispatched one line; the rest of this run's denominator comes from the review that
produced it. Every item is dispositioned here — nothing is silently subset.

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"the shared git-output decoder for `scripts/enforcement/`"* | IN SCOPE — the spec's subject | § Chosen approach |
| I2 | *"85 of 88 `subprocess.run(text=True)` call sites across 35 scripts still decode strictly"* | RE-MEASURED and corrected: **87** sites, **2** guarded, **85** unguarded across **35** files, over **78** `.py` files (AST walk, 2026-09-19). The delta from 88/3 is this session's own fix, which removed a `text=True` site | § The problem, measured |
| I3 | *"17 of them reading file content or commit messages (the same crash class)"* | IN SCOPE, and it is the staging boundary — **RE-MEASURED: the CONTENT class is 15 sites; the brief's 17 also counted `check_subagent_flywheel.py:230` (reached through the MULTI-USE adapter, not a site of its own) and `check_plan_tickets.py:1063` (a MIXED RECORD — `%B` plus `--name-only`). Stage 1 carries 16: the 15 plus the adapter** | § Sequencing |
| I4 | *"a measured trigger population of 63 non-UTF-8-but-git-says-text files in 2 of 45 repos"* | CONFIRMED, and the grounding found the population is **larger than the file count suggests** — two further triggers below | § Triggers |
| I5 | *"generalises `check_script_headers.py`'s existing bytes-then-decode `_git` helper"* | ADOPTED as the base, with three corrections the brief did not carry | § Chosen approach |
| I6 | *"ships a lint rule as its cobra guard"* | ADOPTED, with its own cobra written down | § Cobra |
| I7 | *"it is rule-1 work on a sync path"* | CONFIRMED against the live filter | the `Lane:` field in this spec's own front matter |
| I8 | The NEEDS-A-PROBE sites are not git at all — **6, not the 5 of the brief**: jscpd, ruff JSON ×2, `ruff --version`, mutmut, a `review_rubric.py` subprocess | EXCLUDED from the git decoder; they get their own ruling. ⚠️ The 6 is load-bearing — D10 subtracts it, and a 5 undercounts the cobra allowlist by one | § Out of scope |
| I9 | `check_lint_ratchet.py:229` feeds `git show` output to `json.loads` | IN SCOPE as a named exception | § The one parsing consumer |
| I10 | Three duplicated `_git` helpers (`check_doc_sync.py:70`, `check_subagent_flywheel.py:104`, `check_script_headers.py:206`) | IN SCOPE — PARTLY IN SCOPE — see § A polymorphic `_git` helper: ONE collapses (`check_doc_sync.py:70` → `git_paths`), ONE becomes an ADAPTER (`check_subagent_flywheel.py:104`, RULING 3), and `check_script_headers.py:206` is NOT in the 85 and is NOT touched | § Chosen approach |
| I11 | A comment shipped in `check_secrets.py` at `e33dcdd63` attributes path quoting to *"git's DEFAULT config"* | CORRECTION OWED — executed below; the code is right, the explanation is incomplete | § Corrections this spec owes |
| I12 | `check_script_headers.py:206` passes no `stdin=` | **OUT OF SCOPE for this migration** — real, and it is the same hang class, but that helper is not among the 85 (it already captures BYTES) and this design does not touch it; recorded so the next reader finds it rather than re-deriving it | § A polymorphic `_git` helper |

## Constraints Digest

Computed set, not everything: `review_rubric.py --changed scripts/enforcement/…` reports
`## MATCHED — none (no pack glob hits the changed paths; the FLOOR still arms you)`, so the
must-read set is the FLOOR (`core/10-python.md` + the twelve 12-Factor axes) plus the AVAILABLE
pack whose description matches this work (`core/45-testing-strategy.md`, testing).

| # | Rule (VERBATIM) | Source | Bearing here |
|---|---|---|---|
| C1 | *"**`uv`** is the mandated Python package manager."* … *"Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it."* | `core/10-python.md` (FLOOR, via `review_rubric.py`) | The decoder adds NO dependency — stdlib `subprocess` + `codecs` only |
| C2 | *"`logging.getLogger(__name__)` / `print()`"* → *"`structlog.get_logger()` imported from scaffold `logger.py`"* | `.windsurf/rules/core/10-python.md:315` (BAN table) | SCOPED OUT, stated: these are CLI gates whose stdout IS their contract — `final_gate.run_optional_check` reads it. 12-Factor XI (*"unbuffered stdout only"*) governs instead. The decoder must not introduce a logger |
| C3 | *"**Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered … **lean-but-complete, NOT 100%-line-coverage dogma**"* | `.windsurf/rules/core/45-testing-strategy.md:19` | The migration's behaviours are the decode classes, not the 85 edits — one test per class, not per call site |
| C4 | *"**Watched-fail-first** … a non-trivial behavior's test proves something only if it has been SEEN RED"* | `.windsurf/rules/core/45-testing-strategy.md:21` | Every decoder behaviour ships red-first; the migration's per-site edits do not (C5) |
| C5 | *"**Refactor** \| Zero new tests. **Existing integration/E2E tests must pass.** Replace brittle unit tests with integration tests if encountered."* | `.windsurf/rules/core/45-testing-strategy.md:32` | ⚠️ The tension this spec must rule on: the 85 edits ARE a refactor (C5 says zero new tests) but the decoder underneath them is a BEHAVIOUR change (C3/C4 say red-first). Ruled in § Testing |
| C6 | *"`datetime.utcnow()`"* → *"`datetime.now(UTC)` — deprecated and naive"* | `.windsurf/rules/core/10-python.md:318` (BAN table) | No datetime surface here; recorded as read, `unconstrained` |

## The problem, measured

All figures AST-derived (`ast.parse` + `ast.walk` over `Call` nodes named `run` carrying a literal
`text=True`/`universal_newlines=True`), **2026-09-19**, against the live tree. Grep was refused as
the tool: a grep survey of this same population produced two false positives by matching `errors=`
inside a comment and inside an unrelated local, and a file-count subtraction produced "4 exposed"
against a true 85.

| Metric | Value |
|---|---|
| `.py` files directly under `scripts/enforcement/` | 78 |
| `subprocess.run(text=True)` call sites | 87 |
| …carrying a per-call `errors=`/`encoding=` | 2 (both in `check_secrets.py`, from `e33dcdd63`) |
| …unguarded | **85, across 35 files** |
| Files with ≥1 such site | 36 (1 fully guarded) |

A strict UTF-8 decode raises `UnicodeDecodeError` from `subprocess._translate_newlines` whenever
git returns bytes that are not valid UTF-8. It is a `ValueError`, so it is neither
`CalledProcessError` nor `FileNotFoundError` and the narrow fail-open arms these scripts share do
not catch it.

### ⚠️ It is TWO failure classes, not one — and the quieter one is the worse one

Round zero of this spec's own review measured what happens next, per call site (AST: is the `run`
call lexically inside a `try` whose handler CATCHES `ValueError` — bare, `Exception`,
`BaseException`, or `ValueError` itself?). ⚠️ **The predicate must name `ValueError`:**
`UnicodeDecodeError` IS one (this section's own first line says so), and `check_lint_ratchet.py:116`
and `:229` sit in `except (OSError, ValueError)` — so the split is **63 / 22 across 12 files**, and
`:229` is a CONTENT site that degrades SILENTLY while its docstring claims its fallback *"can only
ever be REACHED when HEAD carries no baseline at all"*. A non-UTF-8 HEAD blob reaches it too.
⚠️ **The
method's limit, stated because it under-counts the WORSE class:** lexical containment cannot see a
CROSS-FRAME catch. Review found at least 5 further sites across 2 more files that this table puts
in CRASH and that are SILENT at invocation time — `check_mutation.py:103-109` wraps `_main()` in
`except Exception: … return 0` (*"advisory must never break a commit"*), and
`check_retired_terms.py:94-96` does the same at its `__main__` guard. The true split is nearer
**58 / 27 across 14 files** (D7/D6 shifted by those 5 sites and 2 files). The table below is a FLOOR and it errs in the direction that makes
the silent class look smaller than it is.

| Outcome | Sites | Files | What the operator sees |
|---|---|---|---|
| **CRASH** — nothing catches it | **63** of 85 | — | The check dies with a traceback; `final_gate` reports a failure. LOUD, and self-announcing |
| **SILENT DEGRADE** — a broad `except` swallows it | **22** of 85 | 12 | The helper returns `None`/`[]` and the check goes LENIENT. No traceback, no warning, a green gate |

The 12: `check_convergence`, `check_doc_sprawl`, `check_doc_sync`, `check_lint_ratchet`,
`check_plan_tickets`, `check_plans`, `check_routing_policy`, `check_rule_grounding`,
`check_stage_artifacts`, `check_structure`, `check_subagent_flywheel`, `check_ticket_breadth`.
⚠️ The fourth draft's table read 65 / 20 / 11 and omitted `check_lint_ratchet` — the uncorrected
figure from before the `ValueError` predicate was adopted three paragraphs above, which is exactly
the file the predicate ADDS (`:116` and `:229` sit under `except (OSError, ValueError)`). Stage 1's
acceptance keys on this list, so the stale version exempted the one CONTENT site this document
itself calls a silent degrader.

The worked example is `check_subagent_flywheel.py:109` — `except Exception: return None` — whose
caller at `:231` reads that `None` as *"couldn't read the commits (git failure) → fail-safe, don't
block"*. A non-UTF-8 commit message therefore does not crash that gate; it makes it **stop
blocking**, exactly the shape D-308 ruled against ("I could not look" reading as "nothing to
find"). The reported incident was a CRASH, which is why it was reported at all; the 22 silent
sites are the ones nobody will ever file.

**This splits two design consequences the crash framing hides.** (a) SEQUENCING: the silent 22
outrank part of the crash 63, because a crash is self-reporting and a lenient gate is not.
(b) VALIDATION: "assert none raises" would PASS on all 22 while they are still broken — which is
why § Validation's second half (each check still reports what it reported) is load-bearing rather
than belt-and-braces. ⚠️ It is NOT stated as an equality — see § Validation's three assertions;
the positive one (the check must NAME the artefact) is what catches a site that stops raising by
scanning nothing, and an equality would green exactly that site.

Measured impact when the CRASH class fired: the entire "Secrets (Zero Hardcoding)" leg of
`final_gate` returned a traceback in the reporting repo.

### Triggers — three, not one, and the grounding found two of them

1. **Git's text heuristic.** A file whose first bytes hold no NUL is diffed AS TEXT even when it is
   an uncompressed PDF, an `.ico`, a font or latin-1 prose. ⚠️ The 8000-byte window everyone cites
   is **executed truth, not a documented contract** — `gitattributes(5)` says only *"gets its
   contents inspected, and if it looks like text and is smaller than `core.bigFileThreshold`, it is
   treated as text"* (fetched 2026-09-19). The design must therefore tolerate whatever git calls
   text, never depend on the constant. Live population: **63 files in 2 of 45 repos** (62 in
   web-ecommerce-factory), over 102,145 tracked files.
2. **`.gitattributes` `diff` SET — stronger, and documented.** The same page: *"A path to which the
   `diff` attribute is set is treated as text, even when they contain byte values that normally
   never appear in text files, such as NUL."* Executed: one `*.bin diff` line makes a NUL-bearing
   blob diff `1 1` and a strict decode raise. This needs no unusual file at all. Live population:
   **0 of 45 repos** set a `diff` attribute today (only 2 have any `.gitattributes`), so it is
   latent — but it is one line away in any of them, and it is the trigger a reviewer would not
   predict from the file census alone.
3. **Paths, not content.** With `core.quotePath=false` a non-ASCII path byte arrives raw and a
   strict decode raises. ⚠️ And the inverse belief is also wrong: executed, with
   `core.quotePath=false` a **tab, a backslash and a `"` are STILL quoted** — only the non-ASCII
   byte goes raw. `-z` is what actually disables quoting, on any config. Live population: **0 of 45**
   repos hold an invalid-UTF-8 path; two hold non-ASCII paths that are valid UTF-8.

**Commit messages** (`git log --format=%B`, 2 sites) are a fourth surface: **0 of ~27,000 commits**
across 45 repos fail to decode. Latent.

### Classification of the 85 unguarded sites

| Class | Sites | Meaning |
|---|---|---|
| CONTENT / commit message | 15 | The live crash class — `git diff` without `--name-only`/`--name-status`/`--numstat`, and `git show <rev>:<path>`. ⚠️ NOT `git log --format=%B`: `check_plan_tickets.py:1063` pairs `%B` with `--name-only` and is MIXED, and `check_subagent_flywheel.py:230` reaches git through the MULTI-USE helper — it is CONTENT by shape and migrates in Stage 1 (§ The one helper), it is simply not counted at a site of its own |
| PATH-ONLY | 37 | Not safe, differently triggered (trigger 3). Two of them FORCE `core.quotePath=false`, so they do not even depend on a user setting |
| MIXED RECORD | 13 | 8 × `status --porcelain`, `check_test_coverage.py:43`, `check_changelog.py:79` (⚠️ a `--numstat` line CONTAINS a path), `check_plan_tickets.py:1063`, plus two found late — `check_phase_tests.py:134` (`--name-status -z`, an alternating status/path parser) and `check_corpus_weight.py:209` (`ls-tree -r -l`, 4th field a size) |
| METADATA — ASCII-safe | 7 | `rev-parse --verify/--abbrev-ref`, `merge-base` |
| METADATA — PATH-BEARING | 6 | 4 × `rev-parse --show-toplevel` + the two `--name-only` `ls-tree` sites (`check_plans.py:55`, `check_test_proposal.py:160`) — ⚠️ NOT ASCII-guaranteed (executed); Stage 2, not Stage 3. The third draft said 5, counting neither `--name-only` site; `check_corpus_weight.py:209` (`ls-tree -r -l`, 4th field a size) is a MIXED RECORD and is counted THERE, once |
| MULTI-USE `_git(args)` helper | 1 | `check_subagent_flywheel.py:107` wraps `["git", *args]` for 5 callers spanning three shapes (metadata, paths, content), so its codec is a property of the CALLER, not of the call site. It is the answer to "does every site map to exactly one verb": **no, one does not** — see § The one helper below |
| NOT GIT | 6 | jscpd, ruff JSON ×2, **`ruff --version`**, mutmut, a `review_rubric.py` subprocess (I8). The second draft said 5 and its table summed to 84 |

Corrected partition, re-derived by AST on 2026-09-20 and summing to its own denominator:
**15 CONTENT + 37 PATH-ONLY + 13 MIXED + 7 META-safe + 6 META-path + 6 NOT-GIT + 1 MULTI-USE = 85.**
The "12 METADATA sites" of earlier drafts is superseded by 7 META-safe + 6 META-path; no section
uses the old phrase any more.

⚠️ **The third draft's partition summed to 92, and its own table summed to 99** — it carried
`44 PATH-ONLY` in the sum line against `51` in the table, and neither reached 85. Three satellite
counts disagreed with the table too (`5 NOT-GIT` at § Cobra vs `6` here; `11 MIXED-RECORD` at
§ Testing vs `13` here). Two causes, both mechanical and both worth naming because the next
re-derivation will hit them: (a) `ast.literal_eval` fails on a STARRED UNPACK, so the five sites
built as `["git", *args]` (10 counting every starred form) and the three built as `subprocess.run(cmd, …)` over a list of literal
command lists read as "non-git" and were counted in the wrong row — `check_phase_tests.py:134` is
`git diff --name-status … -z`, not a non-git call; (b) a `--name-only` diff and a bare
`git diff -- <path>` share the verb and differ entirely in what they emit.

### The one helper — the only place the four-verb API does not close

`check_subagent_flywheel.py:107` is a `_git(args)` wrapper whose argv arrives from 5 callers
spanning THREE shapes — `:119` (`merge-base`) and `:154` (`show -s --format=%at`) are metadata,
`:130` and `:136` (both `--name-only`) are paths, and `:230` (`log --format=%B`) is content — so
no single verb is correct for the SITE.

⚠️ **RULING 3 — the wrapper is an ADAPTER and SURVIVES; it is not deleted and its callers do not
move.** Reading the callers whole is what settles this, and two earlier drafts did not: `_git`
returns `str | None`, and **all five callers branch on `None` as their fail-safe contract** —
`:119` `(_git([...]) or "").strip()`, `:131` `if staged is None: return None  # fail-safe no-block`,
`:155` `except (TypeError, ValueError)` around `(_git(...) or "").strip()`, `:231`
`if msg is None: return True  # fail-safe, don't block`. That `None` is load-bearing in a gate whose
whole docstring is about never false-blocking. Deleting the wrapper would rewrite five fail-safe
branches; splitting its callers across stages would leave the deleted name referenced from whichever
stage had not run yet — a `NameError` in a fleet-synced gate across every reachable copy (D13).

Instead its BODY is re-implemented ONCE, on `git_records`:
```python
def _git(args: list[str]) -> str | None:
    try:
        rc, out = git_records(args, cwd=PROJECT_ROOT)   # args EXCLUDES "git" — see § The argv convention
    except Exception:  # noqa: BLE001 — this gate's own invariant: a git failure never crashes it
        return None
    return out if rc == 0 else None
```
⚠️ The `except` stays BROAD deliberately. The current body catches bare `Exception` with the
comment *"a git failure must never crash the gate"*; narrowing it to `GitUnavailableError` would let
any other failure propagate out of a gate whose docstring forbids exactly that. The adapter's job is
to preserve the caller contract, not to tighten it.
`git_records` is the right verb precisely because it makes no shape assumption — `surrogateescape`,
never `-z`, the caller keeps its parser — which is what `text=True` already did for these five,
minus the strictness AND minus the universal-newline translation that `text=True` also performs
(correction 2 below). ⚠️ **That second delta is real in general and EMPTY for these five callers,
which is stated here so the builder does not hunt for a test that cannot go red.** Driven against
the live code: `:231`'s matcher is `re.search(r"(?:^|\s)NO[-_]POOL\s*:", msg, re.I)` and `\r`
satisfies `\s`, so a `\r\n` message matches identically translated or not; the other four callers
are `(… or "").strip()`, `splitlines()` + `strip()`, and `float(… .strip())`, all of which absorb a
stray `\r`. So the adapter's red-first test asserts the DECODE behaviour (a non-UTF-8 commit message
returns a string rather than raising), not the newline delta — there is no newline assertion to be
seen red at any of the five.
So the adapter is semantics-preserving for all three shapes, no caller
changes, and the file migrates in ONE stage. It is counted once, as MULTI-USE, and it is the only
site in the census whose verb is a property of the wrapper rather than of the call.

⚠️ `check_doc_sync.py:74` is NOT such a helper and the fourth draft was wrong to pair it with this
one. Executed — all four of its callers are path-shaped:
```
$ command grep -n '_git(' scripts/enforcement/check_doc_sync.py
70:def _git(args: list[str]) -> list[str]:
83:    return _git(["diff", "--cached", "--name-only"])
87:    return _git(["diff", "--cached", "--diff-filter=ADR", "--name-only"])
93:    return _git(["diff", base_range, "--name-only"])
97:    return _git(["diff", base_range, "--diff-filter=ADR", "--name-only"])
```
Its `show`/`-U0` calls at `:153`, `:222`, `:258` and `:488` are direct `subprocess.run`s that never
reach `_git`. So `check_doc_sync.py:74` is single-shape `git_paths`, its helper COLLAPSES rather
than splits (consistent with § A polymorphic `_git` helper is SPLIT), and it is counted in
PATH-ONLY. Dismantling it would be a pointless edit at 4 call sites.

## Derivations — every number in this spec, and the command that produces it

⚠️ **This section exists because the numbers were the defect generator.** Four review rounds
confirmed 49 defects; the single largest class was a count corrected in one place and left stale in
the two-to-five others that restated it (a wrap-aware sweep finds 17 instances of the crash/silent
pair alone). A number stated as prose is a second source of truth for something the tree already
knows. So the prose below cites a row ID and the row carries the command: **re-run it rather than
trusting it**, and when the tree moves the row moves with it. The one derivation the third draft
wrote this way — the cobra exemption set — was also the only fix of its round to survive the next
one intact.

All rows executed 2026-09-20 against `/opt/fabrik` at `2d157514f`. `<AST>` is an `ast.walk` over
`scripts/enforcement/*.py` selecting `subprocess.run(…)` calls with `text=True` (or
`universal_newlines=True`) and no `errors=`/`encoding=` — **never grep**, and never
`ast.literal_eval` alone: it fails on a starred unpack, so the `["git", *args]` and variable-`cmd`
sites must be resolved from source or the census miscounts (it did, three drafts running).

| ID | What | Value | How |
|---|---|---|---|
| D1 | unguarded sites / files | **85 / 35** | `<AST>` |
| D2 | of those, pass `cwd=` | **38** | `<AST>`, count `cwd` in keywords |
| D3 | of those, pass `timeout=` | **20** | `<AST>`, count `timeout` in keywords |
| D4 | of those, pass `check=True` | **8** | `<AST>`, `check` is `Constant(True)` |
| D5 | read `.returncode` near the call | **34 of the 79 migrating** | `<AST>` ∩ `Attribute(attr="returncode")` within a 12-line forward window. ⚠️ The population is the MIGRATING set, and the window is load-bearing: widen it to 13 and `check_lint_ratchet.py:52` joins (its read is at `:65`), giving 35 of all 85 — but that site is NOT-GIT and never migrates, so the migrating count is 34 at either width. Prose cites D5; it does not restate the number |
| D6 | SILENT — a handler catches `ValueError` | **22 across 12 files** | `<AST>` inside a `Try` whose handler names `ValueError`/`Exception`/`BaseException`/bare |
| D7 | CRASH — the remainder | **63** | D1 − D6 |
| D8 | five-verb `subprocess.*` calls | **102 across 40 files** | `ast.walk` for `run`/`Popen`/`check_output`/`call`/`check_call` |
| D9 | migrating (D1 minus the 6 NOT-GIT) | **79** | D1 − § Out of scope's 6 |
| D10 | cobra exemptions | **24 across 15 files** | D8 − D9 = 23 across 14 files, **+1** for `git_output.py`'s own call, which is a 15th file |
| D11 | sites already catching `OSError` (gain a folded timeout) | **45** | `<AST>` under a handler naming `OSError`/`Exception`/bare |
| D12 | sites catching `TimeoutExpired` but NOT `OSError` (lose one) | **1** — `check_mutation.py:171`, NOT-GIT | same walk, inverted predicate |
| D14 | files gaining the `git_output` import | **33 of 78** | the distinct files of D9. ⚠️ NOT D1's 35: `check_duplicates.py` and `check_rule_grounding.py` hold only NOT-GIT sites, so they never migrate and never import |
| D13 | reachable on-disk copies | **47** | `ls -d /opt/*/scripts/enforcement` = 50, minus `/opt/fabrik-lib` (`sync_enforcement_to_projects.py:2445` `exclude_folders`) and its two linked worktrees (`.git` is a FILE — rejected at `:2468`, reported at `:2473`); a `--dry-run` reports 46 projects, + `/opt/fabrik` = 47 |

⚠️ **D10 is the row most likely to be copied wrong, and it has been three times** (stated as "4
files", then "17 calls in 12 files", both wrong). The subtraction is from **D9, not D1**: the 6
NOT-GIT sites are OUT OF SCOPE, so they never migrate and stay exempt. Subtracting D1 assumes they
migrate and undercounts the allowlist by exactly 6 — a guard built to that number reds the tree on
day one, on `check_duplicates.py:20`, `check_lint_ratchet.py:52`/`:116`/`:203`,
`check_mutation.py:171` and `check_rule_grounding.py:136`.


## Approaches

**A — per-call `errors=` on 85 sites.** Smallest diff per edit, no new import surface, no module to
sync. Rejected: it is 85 independent chances to pick the wrong codec, and the codec choice is
exactly what is hard — `errors="replace"` on a PATH is silently destructive (see C-row FB2 below),
and nothing would stop the next script repeating it.

**B — one `run_git()` returning bytes, decode at the call site.** Honest about what git returns and
leaves the codec to whoever knows the context. Rejected as the primary: it preserves the decision
at every call site, which is the defect, and it makes the migration 85 *judgement* edits rather
than 85 mechanical ones.

**C — named functions that encode the decision — RECOMMENDED, with THREE shapes, not two.** The
first draft of this spec proposed two (`git_text` / `git_paths`) and review found the hole by
execution: **13 of the 85 sites carry paths AND a non-path field in ONE stream** (the MIXED RECORD
row of § Classification — this paragraph read 11 for three drafts because it was written before
`check_phase_tests.py:134` and `check_corpus_weight.py:209` were found), so neither verb fits —
eight `git status --porcelain`, `check_test_coverage.py:43` (`--name-status`),
`check_changelog.py:79` (`--numstat`), `check_phase_tests.py:134` (`--name-status -z`),
`check_corpus_weight.py:209` (`ls-tree -r -l`, 4th field a size), and the worst case
`check_plan_tickets.py:1063` (`git log --name-only --format=%x01%H%x02%B%x02`), which reads a
commit BODY and PATHS in the same call. The shapes are therefore:

⚠️ **FOUR shapes, not three**, and one shared signature — D2 of the 85 sites pass `cwd=` (38) and
D3 pass `timeout=` (20), which a one-argument signature silently drops:

```python
def git_text|git_paths|git_records|git_meta(
    args: list[str], *, cwd: Path | None = None, timeout: float | None = None,
) -> tuple[int, str] | tuple[int, list[str]]: ...
```

| Function | For | Decode | `-z` |
|---|---|---|---|
| `git_text(args)` | content — `show <rev>:<path>`, `diff` without a name filter, `log --format=%B` | `errors="replace"` | never |
| `git_paths(args)` | PURE path lists — `--name-only`, `ls-files` | `surrogateescape`, split NUL, **trailing empty element DROPPED** | **forced — INSERTED** (before the first `--`; see the rule below) |

⚠️ **`ls-tree` is NOT a `git_meta` verb — the CLASS and the VERB are different questions, and
conflating them is a real fork a builder would have to invent.** All three `ls-tree` sites sit in a
METADATA or MIXED *class* for STAGING, and each takes the verb its OUTPUT shape names:
`check_plans.py:55` and `check_test_proposal.py:160` are `--name-only`, i.e. pure path lists →
**`git_paths`**; `check_corpus_weight.py:209` is `-r -l`, whose 4th field is a size →
**`git_records`**. None is `git_meta`. The distinction matters because the verbs differ in RETURN
TYPE and in `-z`: routing a `--name-only ls-tree` through `git_meta` yields a single
`tuple[int, str]` with no `-z`, so under default `core.quotePath` a non-ASCII path arrives C-quoted
and `check_test_proposal.py:160`'s dict keys never match the real file — silently, and Stage 2's
"the count must not fall" cannot see it because the count does not fall. Executed, both shapes are
`-z`-clean: `git ls-tree --name-only HEAD -z -- <p>` and `git ls-tree -r --name-only HEAD docs/ -z`
both rc 0, NUL-separated. (The "breaks 11 sites" arithmetic behind `git_meta` is the 7 META-safe
plus the 4 `rev-parse --show-toplevel` — it never included the `ls-tree` sites, which is the clue
the table row was wrong.)

⚠️ **"Forced" needs an insertion POINT, and only one of the two readings works.** `git_paths`
INSERTS `-z` before the first `--` in `args`, or at the end when there is none; it never prepends.
The two halves of that rule are load-bearing for different reasons and both were learned by
execution — the *never prepends* half here, the *before the first `--`* half three paragraphs down.
Two PATH-ONLY sites open their argv with
git's GLOBAL options (`check_structure.py:157` `["-c","core.quotePath=false","-C",root,"ls-files",…]`
and `check_doc_sprawl.py:395`), and a prepended flag lands before the subcommand. Executed:
`git -z -c core.quotePath=false ls-files` → rc **129** (`unknown option: -z`); the appended form →
rc 0. ⚠️ **But "append" means append to the OPTIONS, not to the argv: `-z` goes BEFORE any `--`
separator.** After `--`, git reads it as a PATHSPEC, silently and at rc 0. Executed on a fresh
scratch repo:
```
$ git ls-files -z -- 'docs/*.md' | cat -A     # before --
docs/one.md^@docs/two.md^@
$ git ls-files -- 'docs/*.md' -z | cat -A     # after --  ← rc 0, NOT NUL-separated
docs/one.md$
docs/two.md$
```
The fourth draft asserted the after-`--` form was safe on a probe that already carried `-z` before
the `--`, so it proved idempotency and nothing else — the exact proxy-for-evidence defect this
document keeps re-paying. **So the rule is: `git_paths` inserts `-z` immediately before the first
`--` in `args`, or at the end when there is none.** `-z` IS idempotent, which matters because
`check_lint_ratchet.py:94` and `check_phase_tests.py:134` already pass it.
| `git_records(args)` | MIXED records — status+path, counts+path, body+paths | `surrogateescape`; caller keeps its parser | never |
| `git_meta(args)` | `rev-parse`, `merge-base`, version strings — ⚠️ NOT `ls-tree`, see below | `surrogateescape` | never |

⚠️ **Why `git_meta` had to exist, executed:** `git rev-parse -z --show-toplevel` does not reject
`-z` — it **echoes `-z` as the first line of output, at rc 0**, silently corrupting the answer;
`git merge-base -z` exits **129**. Routing those through `git_paths` breaks 11 sites, one loudly
and the rest silently. And it decodes `surrogateescape`, not "ASCII-guaranteed":
`rev-parse --show-toplevel` emits the repo's own filesystem path RAW — `core.quotePath` does not
apply — so a repo under a non-UTF-8 directory raises on a strict decode (executed).

⚠️ **THE PRINT RULE — the second draft got this wrong in the other direction.** `surrogateescape`
yields a `str` carrying lone surrogates and `sys.stdout` is strict, so printing one raises
`UnicodeEncodeError`: `check_review_coverage.py:130` builds a NOTE from a `status --porcelain` path
and prints it ~2,900 lines later at `:3072`. `surrogateescape` alone therefore MOVES the crash from
decode to print. The decoder exports `safe(s) -> s.encode("utf-8","backslashreplace").decode("utf-8")`
and the rule is: **a value from `git_paths`, `git_records` or `git_meta` never reaches stdout
without `safe()`.** Only `git_text`'s `replace` output is print-clean by construction.

⚠️ **That rule is not applicable by reading the call site, and the builder must not try.** The
worked example is the proof: `:130` builds the note and `:3072` prints it, 2,942 lines apart and
across two function boundaries, with the value travelling inside a collected `notes` list. A
proximity search finds nothing — executed over the 13 MIXED and 6 META-path sites with a 60-line
window: 15 of the 16 that resolved showed ZERO nearby print, including the known-positive one. So
the rule ships with its DERIVATION, which is a dataflow question, not a grep: for each migrated
site, follow the returned value forward through assignments, `append`/`extend` into a collection,
returns out of the enclosing function, **and passage as an ARGUMENT into a callee** — that last
edge is not optional and the worked-example file needs it: the same `:103` porcelain path also
flows into `paths.append(root / rel)` at `:133` and thence into `_grade(p, root)` at `:3074`,
which builds `f"{rel}: {e}"` at `:2984` and is printed at `:3078`. A builder tracing only
assignments and collections wraps `:3072`, misses `:3078`, and Stage 2's own fixture then fails with the
`UnicodeEncodeError` the rule exists to prevent. Follow every edge until the value either reaches
a `print`/`sys.stdout.write`/an f-string that one consumes — wrap in `safe()` there, at the PRINT, never at the call site — or is
compared/parsed only, which needs nothing. Stage 1 and Stage 2 each owe this trace per site as
part of their acceptance, and the `-U0` fixture below is what proves it: a path carrying a raw
non-UTF-8 byte must make the check PRINT that path, not raise `UnicodeEncodeError`.

**The contract, which the first draft never stated and a builder cannot invent:** all four return
a tuple whose first element is the exit code (`git_paths` returns `tuple[int, list[str]]`, the
other three `tuple[int, str]`), and they RAISE `GitUnavailableError` when git produced NO ANSWER (RULING 1 below states the
predicate exactly: non-execution OR a timeout).

⚠️ **RULING 1 — the predicate is "git produced NO ANSWER", not "git could not be executed".**
The earlier wording said NON-EXECUTION ONLY while the mirror below described a folded timeout, and
a builder could not tell which. The precedent settles it by execution — `check_script_headers.py`
at `:219-220` is `except (subprocess.TimeoutExpired, OSError) as exc: raise GitUnavailableError(…)`
— so a TIMEOUT raises alongside a failed exec. This design follows the precedent there and departs
from it at `:221-226`, where the precedent ALSO raises on a failing exit: **a non-zero exit is an
ANSWER and is RETURNED** (D5, D4 in § Derivations). So: no answer ⇒ raise; an answer of any exit code ⇒ return.

⚠️ **RULING 2 — `GitUnavailableError` SUBCLASSES `OSError`, unlike the precedent.**
`check_script_headers.py:77` declares `class GitUnavailableError(Exception)`, and generalising that
verbatim is a fleet-wide fail-open→crash regression: a plain-`Exception` type is invisible to every
narrow handler in the directory, so on a box with no git those gates stop failing open and start
producing tracebacks. `check_review_hygiene.py:915` is
`except (subprocess.CalledProcessError, FileNotFoundError, OSError): return []`; `check_doc_sync.py`
catches `(OSError, SubprocessError)`. Subclassing `OSError` is also semantically right rather than a
dodge — the condition being wrapped IS an `OSError` today (`FileNotFoundError` from the exec).

**MIRROR — name the shape this breaks, DERIVED rather than asserted (D11, D12).** Folding the
timeout in moves it across the `OSError` boundary, so two populations change and the derivation
names both. **D11 — 45 sites already catch `OSError`** (directly, bare, or via `Exception`), so a
folded timeout would be swallowed there rather than raised. ⚠️ **But the REALISED cost today is
ZERO sites, and saying "45" without that is alarming a builder about nothing.** Two reasons, both
executed: 20 of the 45 catch `Exception`, which already swallows `TimeoutExpired`, so nothing
changes for them; and of the 14 whose handler covers `OSError` but not a timeout, **none passes
`timeout=`** — all 20 sites that do are either bare-`Exception` (15), already
`(OSError, SubprocessError)` (4), or the NOT-GIT `check_mutation.py:171` (1). **The decoder's
`timeout` therefore defaults to `None`**, exactly as those sites behave today; the D11 mirror is
LATENT and activates only if a future change gives the decoder a default timeout. That is the
honest cost: a property to remember when someone sets one, not a regression shipping now. **D12 — exactly ONE site catches `TimeoutExpired` without `OSError`**
and so would lose its timeout arm: `check_mutation.py:171`, which is a NOT-GIT site (mutmut) and
never migrates. **So no git site loses a timeout arm.** An earlier draft asserted "4 sites" here
and had the direction backwards; the derivation is cheap and the assertion was wrong twice.
`check_lint_ratchet.py:229`'s `except (OSError, ValueError)` still sees an unavailable git, which
keeps § The one parsing consumer true.

⚠️ **RULING 2 IS NOT FREE AT EVERY SITE, and two need an explicit edit.** `FileNotFoundError` is a
SUBCLASS of `OSError`, not a superclass, so a handler naming only `FileNotFoundError` does NOT catch
`GitUnavailableError(OSError)` — it catches strictly less than before. Derived: exactly two MIGRATING
sites sit under such a handler — `check_env_vars.py:203` (`except (CalledProcessError,
FileNotFoundError)`) and `check_review_coverage.py:103` (`:110`, verbatim
`except (subprocess.CalledProcessError, FileNotFoundError): return [], notes, []`). A third,
`check_duplicates.py:69`, is a NOT-GIT site and never migrates. Both migrating handlers gain
`OSError` (or `GitUnavailableError` by name) in the same edit; without it those two fleet-synced
gates stop failing open on a box with no git — the exact regression this ruling exists to prevent.
Both are also among D4's `check=True` sites, whose mandated rewrite addresses only the
`CalledProcessError` arm, so the two edits are made together. The functions
do NOT raise on a non-zero exit — **D5 of the migrating sites read `.returncode` near the call**,
and at least
three use a non-zero exit AS THE ANSWER (`check_corpus_weight.py:184` falls through `origin/master`
→ `origin/main` on rc 1; `check_test_proposal.py:142` returns `None` on rc 128 in a commitless repo;
and `check_mutation.py:59`, which is the near-miss: it never reads `.returncode` at all — `.stdout.strip() or "HEAD~1"` makes EMPTY OUTPUT the signal, so it migrates cleanly either way). A raising-on-exit decoder would delete that
branch at every one of D5's sites. The exit code is therefore in the RETURN, not in a `check=` kwarg and not in
an exception. ⚠️ **And the return carries stdout only — `tuple[int, str]`, no `stderr`.** One
migrating site consumes it: `check_phase_tests.py:141` does
`raise RuntimeError(r.stderr.strip()[:200])` on a failing exit, and it is the ONLY `.stderr` read
of a subprocess result among the 79 (every other `.stderr` in the directory is `sys.stderr`, or
lives in the out-of-scope `check_script_headers.py`). **RULING 5: the return stays two-element and
that one site downgrades its diagnostic to the exit code** — `RuntimeError(f"git diff failed: rc={rc}")`.
Growing every verb's return to three elements to serve one caller is the over-engineering FIX
DIRECTIVE 5 forbids; the downgrade is a stated, accepted loss at a named site, not a silent one.
Stage 2b's acceptance is amended to assert that site's new message, because its
record-set comparison is structurally blind to it. Where stderr still earns its keep is the
no-answer path: `GitUnavailableError`'s message carries it, which is what makes RULING 4's
`LANGUAGE=C` worth having. The signature is exactly `git_*(args, *, cwd=None, timeout=None)` as § Approaches C
states, with no fifth parameter and no fifth `git_*` VERB — and no `env=` either: RULING 4 makes
`LANGUAGE=C` internal to every call rather than a caller's argument. The module also exports `safe()` and the
`GitUnavailableError` type, which are not verbs and are both REQUIRED. (The third draft ended this paragraph with
"all three return `str`" and a `git_status(args) -> tuple[int, str]`, both residue of the
superseded three-function draft; `git_status` is not part of this design.)

⚠️ **The 8 sites that pass `check=True` are a THIRD exit-code shape and they are dispositioned
here, because "no `check=` parameter" alone would leave a builder guessing.** Executed by AST over
the 85: `check_env_vars.py:203`, `check_plan_tickets.py:1063`, `check_review_coverage.py:103`,
`check_review_hygiene.py:908`, `check_structure.py:157`, `validate_conventions.py:227`, `:233`,
`:239` — and NONE of them is among D5, so 42 of the 79 migrating (D5 + D4) are
exit-code-sensitive, not 34. Each relies on `CalledProcessError` reaching a handler
(`validate_conventions.py:248` `except subprocess.CalledProcessError: return []`;
`check_review_hygiene.py:915` catches it with `FileNotFoundError` and `OSError`). The decoder does
NOT raise on a failing exit, so those handlers go unreachable on migration. **The rule: at each of
the 8, replace the implicit raise with an explicit test on the returned code that preserves the
handler's own answer** — `rc, out = git_paths([...])` then `if rc != 0: return []`. This is a
behaviour-preserving edit, but it is an EDIT, and it is what makes those 8 red-first tests rather
than refactors.

## Chosen approach — generalise the precedent, with three corrections

`scripts/enforcement/check_script_headers.py:206` is the base, quoted because its comments carry
incidents this design must not re-pay:

- *"Path lists are read with `-z` (NUL-separated, NEVER quoted): git's default C-quotes any path
  with a non-ASCII byte … and `core.quotepath=false` still quotes a tab, a backslash or a `"`"* —
  re-verified by execution here.
- *"LOSSLESS decoding: `errors="replace"` turned a non-UTF-8 byte into U+FFFD, which re-encoded to
  DIFFERENT bytes for `cat-file`, so every such path was a false "staged deletion" (FB2)"* —
  confirmed against the Python docs (fetched 2026-09-19): only `surrogateescape` is *"lossless and
  reversible"*; `replace` and `backslashreplace` are lossy. PEP 383.
- *"a git that ANSWERS with a failure … read as 'nothing staged' — a convincing green for a check
  that could not ask (EY1)"* — the same ruling D-308 reached independently from the other end.

**The three corrections the precedent does not yet have**, each executed in this session:

1. **`stdin=subprocess.DEVNULL`.** It passes none. A repo-config `diff.<driver>.textconv` reading
   fd 0 hung a gate to its 120s cap with stdin a live pipe. (I12)
2. **Never `text=True`, even with `errors=`.** Text mode also performs universal-newline
   translation, which rewrites a `\r` inside a PATH to `\n` after `-z` un-quoted it — two distinct
   tracked files then decode to the same string and one silently vanishes. Only a manual
   `.decode()` avoids it. The precedent already decodes manually; the rule must be written down so
   a migration does not "simplify" it back.
3. **A named error type, raised when git produced NO ANSWER — a failing exit is RETURNED, never raised.**
   (RULING 1 is the full statement: non-execution OR a timeout raises; any exit code returns. This
   line read "NON-EXECUTION ONLY" through the fifth draft, which contradicted RULING 1's timeout arm.)
   (The second draft said "and a failing exit" here while § Approaches C said the opposite; resolved
   in favour of returning, because D5 of the migrating sites read `.returncode` and three use a non-zero
   exit AS the answer.) `GitUnavailableError`
   already exists in the precedent; the decoder exports it so every consumer can choose LOUD over
   silently-clean, which D-308 makes mandatory for any gate whose absence of output reads as a pass.

### The argv convention — `args` EXCLUDES the executable

**Every `git_*` call passes the arguments AFTER `git`; the decoder prepends `"git"` itself.** This
sentence exists because the fourth draft never stated it and the fifth contradicted itself inside
one document: the API table names subcommands (`show <rev>:<path>`, `--name-only`, `ls-files`,
`rev-parse`), the `-z` rule reasons about "a prepended flag landing before the SUBCOMMAND", and a
worked code block passed `["git", *args]`. Under the other reading that block yields
`git git merge-base …` → rc 1 → the adapter returns `None` → all five flywheel callers take their
"fail-safe, don't block" branch, so the gate stops enforcing at rc 0. Executed:
`['git','git','merge-base','HEAD','HEAD']` → rc 1, `git: 'git' is not a git command`.

Two consequences a builder must apply, not infer. **(a)** The two surviving wrappers
(`check_subagent_flywheel.py:107`, `check_doc_sync.py:74`) already take git-less args from their
callers and prepend `"git"` themselves — so their bodies pass `args` straight through and DROP the
prepend. **(b)** ⚠️ **Essentially EVERY migrating site drops a leading `"git"` — this is the rule, not an
exception, and a builder who skims it leaves a doubled `git` behind.** Derived over the 79: 67 pass
a literal list beginning `"git"`, 8 more are starred forms leading with `"git"`
(`check_doc_sprawl:395`, `check_doc_sync:74`/`:222`/`:488`, `check_plan_tickets:2567`,
`check_stage_artifacts:419`, `check_subagent_flywheel:107`, `check_ticket_breadth:435`),
`check_phase_tests:134` builds `args = ["git","diff",…]` then splats it, and the three variable-`cmd`
sites (`check_citations_resolve:144`, `check_env_vars:203`, `check_lint_ratchet:158`) all resolve to
git-leading literals. `check_structure.py:157` is merely the clearest to read
(`["git", "-c", "core.quotePath=false", "-C", root, "ls-files", …]` becomes
`["-c", "core.quotePath=false", "-C", root, "ls-files", …]`) — global options before the subcommand
are unaffected by the `-z` rule. Global options
before the subcommand are unaffected by the `-z` rule, which inserts before the first `--` or else
at the end.

### ⚠️ A polymorphic `_git` helper is SPLIT, never collapsed

I10 called collapsing the three duplicated `_git` helpers *"most of the value"*. For ONE of them it
is — `check_doc_sync.py:70` collapses onto `git_paths`. The other two do not, for different reasons,
and I10's row is amended to say so. For
`check_subagent_flywheel.py:107` it is a trap: that ONE `subprocess.run` serves five argv shapes
from five call sites — `merge-base` (meta), two `--name-only` (paths), `show -s --format=%at`
(meta) and `log --format=%B` (content). No single verb is correct, and `git_paths` would make
`merge-base -z` exit 129, which the helper turns into `None`, which its caller at `:231` reads as
*"fail-safe, don't block"* — the exact silent degradation this spec exists to close. **Rule: a
polymorphic helper is re-implemented as an ADAPTER over `git_records`, never collapsed onto one
verb and never deleted out from under its callers** — § The one helper carries the body and
RULING 3 carries the reasoning.

⚠️ **`check_script_headers.py:206` is polymorphic too, and an earlier draft called it
"single-shape".** Read at source, its callers are `ls-files -s -z` at `:243` (a MIXED RECORD —
`<mode> <sha> <stage>\t<path>`), `rev-parse --show-toplevel` at `:295` (META) and two `--name-only
-z` at `:300`/`:314` (PATH): three shapes, the same trap — so "single-shape" was wrong. ⚠️ **But it
is NOT in the 85 and this migration does NOT touch it.** It already captures BYTES and decodes
explicitly; it is the precedent this design generalises, not a defect to fix. It therefore stays in
the cobra exemption set (D10), belongs to no stage, and unifying it onto the shared module is a
LATER, optional change that would drop the exemption set by one. Recording it here so the next
reader does not re-derive "single-shape" from a helper that is not: three shapes, and two contracts
this design deliberately departs from — it RAISES on a failing exit (`:221-226`, where the decoder
returns) and it carries `sep` and `timeout=20` of its own.
⚠️ **And it surfaces the one genuine API gap in this design.** It passes
`env={**os.environ, "LANGUAGE": "C"}`, whose own comment calls it load-bearing (*git's fatal
messages in English, EZ6*), and the mandated signature `git_*(args, *, cwd=None, timeout=None)` has
nowhere to carry it — collapsing the helper would silently drop it, which is the same defect class
this spec already caught for `cwd=` and `timeout=`. **RULING 4: the decoder sets `LANGUAGE=C`
ITSELF, on every call, and exposes no `env=` parameter.** Predictable stderr is a property of
"decode git output reliably", not a caller preference; making it internal generalises the
precedent's own lesson instead of re-deriving it per site, and keeps the signature closed.
`check_doc_sync.py:70` is genuinely single-shape (all four callers `--name-only`) and does collapse,
onto `git_paths`.

### ⚠️ The `-z` trap — this migration is NOT mechanical

The first draft called the 85 edits *"mechanical"* and *"the least by risk"*. Review disproved
both by execution. `-z` does not merely un-quote: it changes the RECORD SHAPE, and for a rename it
changes the FIELD ORDER.

```
git status --porcelain        R  old.txt -> new.txt
git status --porcelain -z     R  new.txt\0old.txt\0      ← two fields, new BEFORE old
git diff --name-status        R100\told.txt\tnew.txt
git diff --name-status -z     R100\0old.txt\0new.txt\0
```

Two live parsers were driven against real git output and both regress SILENTLY:

- `check_plan_tickets.py:1063` — its parser does `record.split("\x02", 2)` then `splitlines()` then
  `f.strip()`. ⚠️ `str.strip()` does NOT strip NUL (`"\x00".isspace()` is False), so under a forced
  `-z` a membership test flips **True → False** and every `Agent-Task` trailer WARN stops firing.
  Green gate, no traceback — the silent class again.
- `check_convergence.py:534` — slices `line[:2]` and `line[3:]`. Under `-z` the rename's old path
  arrives as an orphan record with no status prefix, so the slice cuts into the filename and the
  `" -> "` branch at `:560` becomes dead code that still READS as live.

Consequence for this design: **`git_paths` forces `-z` and is therefore only safe for calls whose
output is a pure path list.** Every mixed-record site goes to `git_records`, which does NOT force
`-z` and leaves the caller's parser untouched. And the migration of those 13 is a REVIEWED parser
change, not a mechanical edit — which is why § Testing and § Cost below were both re-ruled.

### Where it lives — and the MIRROR

A new `scripts/enforcement/git_output.py`, synced with the directory (verified: the sync copies
`scripts/enforcement` RECURSIVELY via `rglob("*")`, so a new file needs no manifest edit).

⚠️ **The first draft's import claim was FALSE and is corrected here, because it would have failed
on day one.** It said `scripts/enforcement/` is on `sys.path` by construction so a bare
`from git_output import git_text` works. Executed, in a package tree matching the live one:

| invocation | bare import | two-arm import |
|---|---|---|
| `python scripts/enforcement/mod.py` | OK | OK |
| `python -m scripts.enforcement.mod` | **ModuleNotFoundError** | OK |
| `import scripts.enforcement.mod` (pytest) | **ModuleNotFoundError** | OK |

Both failing forms are LIVE: `scripts/final_gate.py:2226` and `:2302` invoke these by dotted module
name, and `final_gate.py` is itself synced, so the `-m` form runs in all 50 copies. The mandated
import is therefore the two-arm form `check_secrets.py:11-14` already uses:

```python
try:
    from .git_output import git_text
except ImportError:  # standalone run (final_gate executes `python <path>`)
    from git_output import git_text  # type: ignore[no-redef]
```

⚠️ And the dotted form `from scripts.enforcement.git_output import …` is NOT an option:
`tests/enforcement/test_flip_gate_matrix.py:94-97` raises `RuntimeError` for any gate containing
`from scripts.enforcement`.

**MIRROR, stated because it is the change's real cost: D14 (33) fleet-synced scripts gain an import they
did not have, in a directory where three different import idioms are currently in use** (the
two-arm form, the dotted form, and a `sys.path.insert` in `check_pack_reachability.py:52-57`). The
build picks one — the two-arm form — and says so, or the next author picks a fourth.

Rejected alternative: extending `validate_conventions.py`. It is already imported by several of
these scripts, which is the attraction — but it is a CONVENTIONS validator, and hanging process
plumbing off it is the kind of second-purpose that makes a module impossible to name later.

## The one parsing consumer

`check_lint_ratchet.py:229` feeds `git show HEAD:<path>` straight to `json.loads`. A replacement
character inside a JSON string value would corrupt it silently. Ruling: it uses `git_text()` like
every other content site, and the SAFETY comes from its existing wrapper — `except (OSError,
ValueError)` catches `json.JSONDecodeError` and falls back to the working-tree copy. That fallback
is what makes `replace` tolerable there, so the build writes that reasoning into a comment at the
call site. It is not a different codec; it is a documented exception.

## Sequencing

One migration, not three — but with the acceptance evidence staged, because the classes differ in
how they can be proven.

### THE ACCEPTANCE RULE — stated ONCE, applied by every stage below

⚠️ **Three rounds of review found a defect in a per-stage acceptance clause each time, always the
same defect: a correction landed in one stage's bullet and not its siblings'.** So the rule lives
here, once, and each stage names only its own fixture ingredient and population.

**A stage closes when, for EVERY check holding one of its sites:**
1. **it does not raise** — necessary, never sufficient;
2. **it EVIDENCES the decode** (§ Validation's assertion 2) — binding on EVERY check in the stage,
   because a check that stops raising by scanning nothing has not been fixed and is
   indistinguishable from a fixed one under assertion 1 alone. ⚠️ **But HOW it is discharged is
   keyed on the site's arm from step 3, not stated once for all sites** — an earlier draft said
   "NAMES the planted artefact in its output" universally, and that is unsatisfiable at three of
   the four arms:
   - **CRASH arm** — the artefact is named or acted on in stdout. The plain reading.
   - **VERDICT arm** — the lane transition IS the evidence (rc 1 → rc 0, or the reverse).
   - **SILENT arm** — the artefact may be UNNAMEABLE: at `check_lint_ratchet.py:229`, executed on
     step 3b's mandated fixture, a correct migration leaves rc and stdout byte-identical
     (`lint-ratchet: OK — 0 == baseline`) while the call-boundary payload moves from the
     worktree-fallback dict to the HEAD one carrying `a\udcffb`. Discharge it there with the
     step-3 call-boundary PAIR: pre-value ≠ post-value, and the post-value is sourced from the
     decoded stream.
   - **EXCLUSION (3c) and META** — the artefact DISAPPEARS, and the call boundary, respectively;
3. **findings unrelated to the artefact are unchanged** (§ Validation's assertion 3), compared with
   the artefact's own lines filtered out. ⚠️ **Where the artefact's presence moves a COUNT or
   SUMMARY line that does not NAME it, the name-substring filter cannot remove that line and
   assertion 3 fails on a CORRECT migration — so run it against an ARTEFACT-FREE fixture variant
   instead, and let the artefact fixture carry assertions 1 and 2 only.** ⚠️ **The variant must
   still REACH the site: build it by replacing the artefact with a BENIGN TWIN at the same surface
   — the same file still staged or committed, with valid-UTF-8 content, at a path **git emits
   UNQUOTED** — and NEVER by deleting it.**

   ⚠️ **"Unquoted" is stricter than "ASCII", and the difference is a live trap.** `core.quotePath
   false` does NOT suppress C-quoting for a backslash, a tab, a control character or a `"` — this
   document relies on exactly that fact twice (`check_doc_links.py:117`, `check_test_proposal.py:160`)
   — so the obvious twin, Stage 2's own ingredient path minus the bad byte, still arrives as
   `"ba\\d.py"` WITH the quotes in the string and fails the entry guard's extension or prefix test.
   Executed: a `ba\d.py` twin does not reach `check_env_example.py:65`, `src/a/ba\d.py` does not
   reach `check_test_coverage.py:55`, `src/a\b/models.py` does not reach `check_schema_sync.py:85`,
   and `scripts/ba\d.py` does not reach `check_changelog.py:173`; the plain `bad.py` / `src/a/bad.py`
   / `src/ab/models.py` twins reach all four. A quoted twin is as vacuous as the deletion this clause
   bans, reached through a different door.

   ⚠️ **So there is a PROOF OBLIGATION: the run must be shown to REACH THE SITE — its argv actually
   executed — not merely to exit 0.** It is an ADDITIONAL necessary condition, never a replacement
   for the ingredients: **every fixture ingredient stays NORMATIVE**, and (b2), (e) and Stage 2b's
   `diff.renames copies` keep their "without it, INERT" force. Discharge reach with a three-line
   PATH shim that logs argv — every git invocation in `scripts/enforcement/` is a bare-name
   `["git", …]` (no absolute paths, no `shutil.which`, and the only two `env=` uses preserve `PATH`),
   so it works on any check untouched.

   ⚠️ **But reach does NOT catch an inert ingredient, and an earlier draft claimed it did and
   demoted the ingredients on that claim.** Executed against `check_doc_links.py:117`'s fixed argv
   with and without (b2): the argv logs are IDENTICAL and BOTH streams are non-empty —
   `b'"docs/ba\\377d.md"\n'` versus `b'docs/ba\xffd.md\n'` — and only the strict decode differs
   (no raise / raises). The same holds for the other three: without `diff.renames copies`,
   `status --porcelain` returns a non-empty `R`+`A` and simply no `C`; without (e),
   `log --format=%B` returns a non-empty `b'subj \xc3\xbf bad\n'` that decodes cleanly; and Stage 2b's
   own committed-only case satisfies reach literally while every stream is empty. **Reach separates
   0 of the 4.** A site whose argv is fixed — `ls-files`, `status --porcelain`, every unscoped
   record site — cannot vary its log by construction, so the shim is measuring the wrong thing.

   ⚠️ **The discriminator is the PRE-MIGRATION RAISE, which is what watched-fail-first already
   means — so state it as a REGISTER and assert it per ingredient before any stage opens:**

   | ingredient | at least one site or bare command that MUST raise (or be present) pre-migration |
   |---|---|
   | (a) non-UTF-8 content | `git show HEAD:<planted>` raises |
   | (b2) `core.quotePath false` | `git ls-files` over the planted path raises |
   | (e) `i18n.commitEncoding` | `git log --format=%B` raises |
   | `diff.renames copies` | a `C` record is present in `status --porcelain` |
   | STATE — `HEAD` | `git show HEAD:<planted>` raises (same probe as (a)) |
   | STATE — INDEX | `git diff --cached -- <planted>` raises — ⚠️ **scoped to the artefact**, or an unrelated ASCII staged delta satisfies it while every CONTENT site scans a clean stream |
   | STATE — WORKTREE (untracked) | `git ls-files --others --exclude-standard` raises |
   | STATE — WORKTREE (untracked AND gitignored) | `git ls-files --others --ignored --exclude-standard` raises |

   ⚠️ **`--others --exclude-standard` and `--others --ignored --exclude-standard` are DISJOINT
   sets, which is why the worktree leg is two rows and needs two artefacts.** Executed: with an
   untracked non-ignored `ba\xffd.md` and a gitignored ASCII `dump/stray.md`, the first probe
   RAISES on `b'ba\xffd.md\n'` while the second returns `b'dump/stray.md\n'` and decodes cleanly —
   so a single untracked artefact greens the first row while `check_structure.py:157`, the only
   EXCLUSION site (3c) and the reason the untracked leg matters, scans an ASCII-only stream. The
   gitignored artefact 3c already calls for (`dump/ba\xffd.txt`) is the second one.

   ⚠️ **So the STATE rows need FOUR DISTINCT artefacts, not one file moved between states** —
   executed: staging the artefact removes it from `--others`, so a single file can satisfy at most
   two legs and the third reads green on absence. Plant the same bad bytes at three paths, one
   committed, one staged, one untracked. And an earlier draft had these three as ONE row probing
   `diff --cached --name-status` for non-emptiness, which discriminated for none of them: a rename
   pair in an unrelated ASCII directory made it green while the CONTENT leg and the untracked leg
   were both inert — and the untracked leg is what `check_structure.py:169` (the only EXCLUSION
   site) and the five `--others --exclude-standard` consumers depend on.

   The register is asserted once, on the fixture, before the first site is migrated. An empty entry
   means that ingredient is inert and every site depending on it would have closed on a vacuous
   green — which is exactly how (b2), (e) and copy detection were each found, one round at a time,
   by someone executing them. This is cheaper than the shim and it is the property the section
   actually wants. Assertion 3's comparison means something only once the register is green AND the
   site is reached — and note which of the two is doing the work: the register is the discriminator,
   reach is the weaker companion condition. ⚠️ An earlier draft ended this paragraph by offering
   "a recorded argv" as an equal-power way to assert vacuity; it is not, per the executed evidence
   just above, and a builder taking that route accepts every inert fixture. Step 1's entry guard is frequently satisfied BY the artefact, so a
   deletion drops the check out before its call site and assertion 3 then compares two runs that
   decoded nothing — a vacuous green, and the cardinal false positive this whole section exists to
   prevent. Executed at `check_env_example.py:65`: with the staged `app.py` deleted, `:107` returns
   0 with empty stdout before the `.py` filter at `:111` is reached and assertion 3 passes on both
   sides; with a benign twin staged, both runs reach `:65` and the comparison means something. This
   is the half of Stage 2b's own device the generalisation must carry with it — its variant keeps
   the rename and the copy precisely so that *"the pre-migration run does succeed"*. This generalises the
   device Stage 2b already invents for itself (its rename+copy-only variant) to every arm that
   needs it. Executed at `check_doc_links.py:286`: a correct migration turns
   `OK — 0 broken of 1 refs across 3 docs` into `… 2 refs across 4 docs` at rc 0 — the only line
   that moved is a count carrying no path, so the filter leaves it and the equality test reds.
   The arms that already carried an explicit carve-out (VERDICT, and EXCLUSION at 3c) are instances
   of this same rule, not exceptions to it.

⚠️ **And the fixture PLANTS THE ARTEFACT WHERE EACH CHECK ACTUALLY LOOKS. That placement is
DERIVED per site, never enumerated in this document** — an enumeration was tried and was wrong for
5 of the 15 CONTENT sites in one draft, which is the same failure mode this spec already paid for
with its counts and its cobra predicate. A generic `bad.md` is invisible to most CONTENT sites: they
are `git diff --cached` scoped to a specific path or a type filter, and several refuse to run at all
unless an unrelated precondition is met. **The derivation, per site:**

> 1. Read the site's argv and the ENTRY GUARD of the function that reaches it. The guard is as
>    load-bearing as the argv: `check_changelog.py:219-223` returns 0 before `:173` is reached
>    unless a *significant* file is staged (`SIGNIFICANT_DIRS` / `SIGNIFICANT_FILES`, `:39-64` —
>    and note `docker-compose.yml` is NOT in that set while `check_compose_services` accepts it);
>    `check_env_example.py:111` filters staged files to `.py`; `check_schema_sync.py:230` filters on
>    `MODEL_FILE_PATTERNS` (`:30-35`); `check_test_coverage.py:140` takes only `src/**/*.py`.
> 2. Plant the bad bytes in the path that reaches the DECODE, which is frequently NOT the file the
>    check is named after — `check_env_example`, `check_schema_sync` and `check_test_coverage` all
>    decode a staged SOURCE file, not a `.env.example`, a schema or a test.
> 3. **WATCH THE SITE'S OWN OBSERVABLE CHANGE on that fixture before migrating it** (Completion
>    Contract 1) — ⚠️ **not "watch it red", which is true for only one of the three failure modes
>    this spec already classifies (D6/D7).** The observable is keyed on that classification, and no
>    new taxonomy is invented for it:
>    - **CRASH site (one of D7's 63).** Pre-migration RAISES on the fixture; post-migration does
>      not raise AND satisfies assertion 2. Watch the RAISE. This is the arm the phrase "watch it
>      red" was written for.
>    - **SILENT site (one of D6's 22).** Pre-migration returns a WRONG answer QUIETLY, so stdout can
>      be byte-identical before and after and no red exists to watch. **Assert the returned value at
>      the CALL BOUNDARY**, not stdout. Executed at `check_lint_ratchet.py:229`, whose
>      `except (OSError, ValueError)` swallows the `UnicodeDecodeError` (a `ValueError`): the whole
>      check prints identically at rc 0 before and after, while the helper returns
>      `('worktree-fallback', None)` pre-migration and `('HEAD', {...})` post. A builder told to
>      "watch it red" here discards a CORRECT placement because it cannot go red.
>    - **VERDICT site — the decode feeds a gate decision.** The observable is the LANE, and it may
>      legitimately move toward GREEN. Executed at `check_convergence.py:768`: a plan committed
>      `Status: EXECUTED` with a raw byte reds pre-migration (`FAILED … claims EXECUTED but cites no
>      review artifact`, rc 1) because `_head_text` swallows to `""` at `:776` and the `EXECUTED`
>      match at `:922-924` fails; post-migration it decodes, `:925 continue` fires, and the check
>      correctly drops to `ADVISORY` at rc 0. **Fewer findings is the CORRECT outcome there**, and
>      assertion 3 must not read it as regression — that site's acceptance is the rc 1 → rc 0 lane
>      transition, stated as such.
>
>    **Picking the arm is MECHANICAL — run the site on the fixture BEFORE and AFTER, and let what
>    moved choose:**
>    - the PRE run raises ⇒ **CRASH**;
>    - else the EXIT CODE differs ⇒ **VERDICT**;
>    - else (rc unchanged) ⇒ **SILENT**, and the observable is the call-boundary value; a stdout
>      delta, where one exists, CORROBORATES it but does not select the arm.
>
>    ⚠️ **The boundary is `rc` ALONE, and "rc or stdout" was wrong.** A correctly migrated PATH-ONLY
>    site routinely changes stdout while leaving rc untouched — executed at `check_doc_links.py:117`
>    with a `docs/ba\d.md` carrying NO broken link: pre-migration `OK — 0 broken of 1 refs across 1
>    docs`, post `… across 2 docs`, rc 0 both times. Under "rc or stdout" that selects VERDICT,
>    whose discharge is a lane transition that does not exist there, while the SILENT route that
>    does hold (`"docs/ba\\d.md"` → `docs/ba\d.md` at the call boundary) is barred by its own
>    selection condition — and the `1 → 2` delta is a COUNT, which Stage 2 expressly bars as a
>    closing criterion. Keyed on rc alone every worked example keeps its arm: `check_doc_sync.py:153`
>    raises ⇒ CRASH; `check_convergence.py:768` and `check_structure.py:157` move rc 1 → rc 0 ⇒
>    VERDICT; `check_lint_ratchet.py:229` moves neither ⇒ SILENT.
>
>    ⚠️ Two earlier keys were wrong and both are instructive. "Pick from D6/D7 membership" is a
>    TWO-valued key for a THREE-valued choice. Its replacement — "D6 ⇒ VERDICT when the decoded
>    value feeds a gate decision, else SILENT" — reads as semantic but is vacuous: in an enforcement
>    check essentially every decoded value reaches the verdict, and it selects VERDICT for
>    `check_lint_ratchet.py:229`, the SILENT arm's own worked example (its baseline flows
>    `_read_baseline` `:264-271` → `:311` → `if current > baseline: … return 1` at `:423`). The
>    mechanical form has no such failure: it never asks what a value MEANS, only what the run DID.
>    D6/D7 remains the EXPECTATION you sanity-check the answer against, never the key. A placement
>    is proven by its observable moving, never by a red per se.
>
> 3c. ⚠️ **A site whose decoded value is consumed as an EXCLUSION set inverts assertions 2 and 3.**
>    There is exactly one in the 85 — `check_structure.py:157`, whose
>    `ls-files --others --ignored --exclude-standard` output is tested as
>    `if rel_path.as_posix() in ignored: continue` (`:217`; `:205` is the `ignored = …` assignment); an AST sweep for
>    `--ignored`/`--others`/`--exclude-standard`/`check-ignore` over the 85 returns it and
>    `validate_conventions.py:239`, and the latter is an INCLUSION use. There, a correct migration
>    can only make the check QUIETER — it can never name the artefact, so assertion 2 as stated is
>    unsatisfiable, and assertion 3 fails on a correct migration because the unrelated findings that
>    DISAPPEAR are not "the artefact's own lines". Executed: with a gitignored `dump/ba\xffd.txt`
>    (the artefact) and a gitignored `dump/stray.md` (an unrelated pre-existing finding), the site
>    reds `❌ Structure errors (1): dump/stray.md` at rc 1 pre-migration and prints
>    `✓ Project structure OK — 0 violations` at rc 0 post. **So for an exclusion site the proof is
>    that the artefact AND every other correctly-ignored path DISAPPEAR, and the acceptance is the
>    rc 1 → rc 0 lane transition** — it takes the VERDICT arm, never the SILENT one its D6
>    membership would otherwise suggest.
>
> 3b. ⚠️ **A check may decode the same artefact OUTSIDE git, and that red is a decoy.** Executed at
>    `check_changelog.py`: staging a `CHANGELOG.md` whose entry carries a raw byte reds at `:138`
>    (`content = changelog_path.read_text()`), a STRICT non-git decode that is not among the 85 and
>    that this migration never touches — so assertion 1 can never be satisfied on that fixture, and
>    step 3's red certifies a placement that is wrong. **Plant the bytes in the INDEX ONLY and leave
>    the worktree copy valid UTF-8**; the site at `:173` then reds correctly and the migrated check
>    reaches `WARNING: CHANGELOG.md contains placeholder`. Any site whose file the check also reads
>    directly takes this treatment.

Three sites need a state rather than a file and are easy to miss: `check_convergence.py:768` and
`check_lint_ratchet.py:229` read `git show HEAD:<path>` — the bytes must be COMMITTED, at a plan/
review `.md` and at `.fabrik/lint-baseline.json` respectively — and `check_doc_sync.py:153` reads
`git show :<path>`, i.e. the INDEX. Those three matter most, and ⚠️ their failure modes DIFFER even though all three sit in
silent-degrade FILES — the 12-file list is file-level and these are site-level claims. Executed:
`check_lint_ratchet.py:229` is the true green gate (identical stdout, wrong answer);
`check_doc_sync.py:153` CRASHES at rc 1 (its `except (OSError, SubprocessError)` does not catch a
`UnicodeDecodeError`); `check_convergence.py:768` reds at rc 1 and correctly turns green on
migration. One site per arm of step 3 — pick the arm from the SITE, never from its file.

This derivation carries the whole weight for the 10 of the 15 CONTENT sites that fall outside the
50-site behaviour-test union, for which this stage's acceptance is the ONLY proof they were migrated
at all.

Every stage below is read against that rule:

- **Stage 0 — land the module ALONE and sync it.** 33 of 78 gates are about to gain a hard import
  of a 79th file, and the sync copies `scripts/enforcement` per-repo via `rglob`: a mid-directory
  failure leaves a repo holding migrated consumers and no `git_output.py`, i.e. `ImportError` at
  load for all D14 of them. So it ships with ZERO consumers, is `--force` synced, and its presence
  is verified in every REACHABLE on-disk copy before any call site moves. ⚠️ **That number is 47,
  not 50, and a build that waits for 50 waits forever.** Executed:
  `ls -d /opt/*/scripts/enforcement | wc -l` = 50, but three of those directories are unreachable
  by the sync — `/opt/fabrik-lib` is in `sync_enforcement_to_projects.py`'s `exclude_folders`
  (`:2445`), and `/opt/fabrik-lib-account` and `/opt/fabrik-lib-review` are linked WORKTREES of it
  whose `.git` is a FILE, which the discovery arm rejects at `:2468` and reports at `:2473`
  (`SKIP (worktree, not a repo)`).
  A `--dry-run` reports `46 projects synced`; 46 + `/opt/fabrik` itself = 47. Acceptance:
  `ls /opt/*/scripts/enforcement/git_output.py | wc -l` = 47, with those three named as the
  known-absent remainder. (Filed to infra: the sync's own report never names a `scripts/enforcement/`
  directory it cannot reach, so an unreachable copy is invisible in the tool that would tell you.)
- **Stage 1 (the live class): the 15 CONTENT sites, silent-degrading ones FIRST, plus the 1 MULTI-USE adapter** (`check_subagent_flywheel.py:107` — it reads commit messages among its three shapes, and § The problem is built on that site; per RULING 3 its BODY moves here and none of its callers move at all). Fixture ingredients: a NUL-free
  non-UTF-8 blob planted at each surface THE DERIVATION YIELDS (the rule enumerates none, by
  design), plus a `*.bin diff`
  attributes line, plus (e)'s non-UTF-8 commit message for the adapter. The 15 sites sit in **10
  files** — `check_doc_sync.py` holds four (`:153`, `:222`, `:258`, `:488`), `check_openapi_sync.py`
  two (`:59`, `:80`) and `check_test_coverage.py` two (`:55`, `:76`), so those three contribute 8
  sites and 15 − 8 + 3 = 10 — and the rule applies to all ten. ⚠️ Three of them are also
  silent-degraders (`check_convergence`, `check_doc_sync`, `check_lint_ratchet`) — each on a
  DIFFERENT arm of the rule's step 3, see there — so assertion 2 is
  discharged three different ways among them: `check_convergence` moves a LANE (rc 1 → rc 0),
  `check_doc_sync` CRASHES pre-migration and names the artefact after, and ⚠️ `check_lint_ratchet`
  does NEITHER — executed, a correct migration there leaves rc and stdout byte-identical and is
  evidenced only at the call boundary. "Byte-identical ⇒ still swallowing" holds for the first two
  and is FALSE for the third; read as universal it rejects a correct migration. Acceptance: THE ACCEPTANCE RULE.
- **Stage 2: the 37 PATH-ONLY sites and the 6 META-path sites.** Fixture ingredient: the same repo gains a path with a raw
  non-UTF-8 byte, a tab, a backslash and a `"`. Acceptance: THE ACCEPTANCE RULE. ⚠️ *"The count it
  reports must not fall"* is assertion 3's supporting form, never the closing criterion — executed
  on the live `check_doc_links.py:117` with a `docs/ba\d.md` carrying a broken link, `git ls-files`
  still C-quotes the backslash even under `core.quotePath false`, the check never sees the file, and
  it prints `OK — 0 broken of 1 refs across 2 docs` at rc 0, byte-identical to the artefact-free
  fixture. The count does not fall and a check that decoded nothing passes. The same blindness
  covers `check_test_proposal.py:160`, whose dict keys silently miss a C-quoted path.
- **Stage 2b (the riskiest stage, and the fourth draft had no stage for it at all): the 13 MIXED
  RECORD sites.** These are the `git_records` population — the 8 `status --porcelain` calls,
  `check_changelog.py:79` (`--numstat`), `check_test_coverage.py:43` (`--name-status`),
  `check_plan_tickets.py:1063` (`%B` + `--name-only`), `check_phase_tests.py:134`
  (`--name-status -z`) and `check_corpus_weight.py:209` (`ls-tree -r -l`). § The `-z` trap and
  § Cost call these the REVIEWED class rather than mechanical edits. ⚠️ **Not because the record
  shape moves — it does not.** `git_records` forces no `-z` and leaves every caller's parser
  untouched, and all 13 keep their argv, so the decode is a swap. What earns the separate stage is
  that a MIXED record interleaves path bytes with non-path fields in ONE stream, so a decode error
  corrupts a FIELD BOUNDARY rather than one value — and that 3 of the 13 also carry the D4
  `check=True` rewrite (`check_plan_tickets.py:1063`, `check_review_coverage.py:103`,
  `check_review_hygiene.py:908`). Earlier drafts called these "parser rewrites", which contradicted
  this section's own `-z` ruling and left a builder owing a red-first test for a shape change that
  cannot occur. They cannot ride Stage 2's substitution pass because of the field-boundary risk and
  those 3 edits, not because a parser moves. Fixture ingredients: a RENAME and a COPY **STAGED in the index, and a second such pair COMMITTED
  at `HEAD`** — § Validation's three-state rule applied to this ingredient, and one state closes
  nothing: 10 of these 13 sites read the INDEX (the 8 `status --porcelain`, `check_changelog.py:79`
  `--numstat`, `check_test_coverage.py:43` `--name-status`) while `check_phase_tests.py:134`
  (`{baseline}..HEAD`) and `check_plan_tickets.py:1063` (`log --name-only`) need it COMMITTED.
  ⚠️ Executed: with the pair merely committed, `status --porcelain`, `diff --cached --numstat` and
  `diff --cached --name-status` are ALL EMPTY, so the headline ingredient reaches none of the 10 and
  the rename+copy-only regression baseline is empty pre and post — assertion 3's equality passes over
  two runs that decoded nothing, while the reach test is literally satisfied. That is the same
  cardinal false positive (b2) closes on the quoting axis, arriving on the STATE axis.
  ⚠️ **And assertion 2's rename/copy half binds only the unscoped and DIRECTORY-scoped record sites.**
  At a site whose argv narrows the pathspec to individual FILES — `check_test_coverage.py:43` (called
  per path from the `src/**/*.py` list at `:140`) and `check_stage_artifacts.py:419` (a fixed
  `FROZEN_ARTIFACTS` list) — git filters the rename's SOURCE out before detection and reports a bare
  `A`. Executed: `diff --cached --name-status` gives `C100`/`R100`, the same command with
  `src/renamed.py` appended gives `A src/renamed.py`, and `status --porcelain -uall -- src/` gives
  `C`/`R` while `-- src/renamed.py` gives `A`. There assertion 2 is discharged by the non-UTF-8 path
  record alone. Plus a non-UTF-8 path — ⚠️ **and `git config diff.renames copies`, without which the COPY
  half of this fixture is silently inert, exactly as the path half is without (b2) and the
  commit-message half without (e).** Git does not detect copies by default. Executed on a fixture
  built literally as written (`src/orig.txt` renamed to `src/renamed.txt` and copied to
  `src/copied.txt` in one commit): `status --porcelain` gives
  `R  src/orig.txt -> src/copied.txt` + `A  src/renamed.txt` and `--name-status` gives
  `R100 … copied.txt` + `A … renamed.txt` — **no `C` record at all, and the `R` git does emit names
  the WRONG destination** (the alphabetically-first copy) while the real rename arrives as an Add.
  A builder ticks "the rename is present" and closes the stage having never exercised a copy record.
  With that one config line, `status` gives `C  src/orig.txt -> src/copied.txt` and
  `R  src/orig.txt -> src/renamed.txt`, and `--name-status` the matching `C100`/`R100`
  (`status.renames` defaults to `diff.renames`, so the line covers the 8 porcelain sites too).
  ⚠️ **And the COPY must share its SOURCE with the rename.** A copy taken from an unmodified tracked
  file is still reported `A` even under that config (executed) — it would need
  `-C --find-copies-harder` in the argv, which § The `-z` trap forbids adding. The same two
  requirements bind the rename+copy-only variant that is assertion 3's regression baseline;
  without them that baseline is a rename-only baseline wearing a copy's name. Acceptance: THE ACCEPTANCE RULE, where assertion 2 reads *"the
  parsed record set CONTAINS the rename, the copy and the non-UTF-8 path as distinct records with
  their fields in the documented positions"*, and assertion 3 is run against a **rename+copy-only
  fixture variant**. ⚠️ That variant is not optional: on the hardened fixture the PRE-migration
  `status --porcelain`, `diff --cached --numstat`, `diff --cached --name-status` and `ls-tree -r -l`
  all RAISE (executed), so there is no pre-migration record set to be identical to — "identical to
  the pre-migration one field for field" is unobtainable, and earlier drafts asserted it anyway. ⚠️ No `-z` is added
  to any of them (§ The `-z` trap): `-z` INVERTS a rename's field order and these parsers read the
  human shape.
- **Stage 3: the 7 META-safe sites.** Migrated for uniformity, not safety — a reviewer must be able
  to read "no `text=True` in this directory" as an invariant rather than checking 87 call sites.
  ⚠️ **"META-safe" means the SHA-emitting subset only, and the stage does NOT opt out of the rule.**
  Four of the seven are `rev-parse --abbrev-ref` (`check_citations_resolve.py:131`,
  `check_corpus_weight.py:171`, `check_plan_tickets.py:2557`, `check_test_proposal.py:134`), which
  emit a REFNAME — and git accepts a non-UTF-8 branch name. ⚠️ **And the ingredient is a non-UTF-8 UPSTREAM, not a non-UTF-8 branch name — an earlier draft
  probed `rev-parse --abbrev-ref HEAD` and wrote the result as evidence for four sites that do not
  query `HEAD`.** All four read `@{u}`/`@{upstream}` (`check_citations_resolve.py:131` `@{u}`;
  `check_corpus_weight.py:171` `--symbolic-full-name @{upstream}`; `check_plan_tickets.py:2557` and
  `check_test_proposal.py:134` `@{upstream}`), and with only a local branch renamed they return
  **rc 128 with an empty stream** — nothing decodes, so assertion 1 passes VACUOUSLY on unmigrated
  code, the exact false green § Validation exists to prevent. The working ingredient is three steps,
  and the first is the one both earlier attempts omitted — **the ref must EXIST**:
```
git branch $'br\xff'                                   # 1. create it — without this, rc 128
git config branch.<current>.remote .                    # 2. point the branch at this repo
git config branch.<current>.merge refs/heads/$'br\xff'  # 3. name the bad ref as upstream
```
  Executed: both argv shapes then return `b'br\xff\n'` at rc 0 and raise under `text=True`. Only
  `rev-parse --verify` and `merge-base` (3 sites) are ASCII by construction, and those four sites are
  held to THE ACCEPTANCE RULE like every other. Acceptance: THE ACCEPTANCE RULE for the four refname sites, plus the cobra
  check (below) passing with exactly its DERIVED exemption set and no undeclared one — "zero exemptions" is unreachable and the fourth draft asserted it against its
  own § Cobra. The set is DERIVED by § Cobra's stated rule, never copied from a number in this
  document; every hand-written value of it so far has been wrong.

## Cobra (D-253 — required, and its own bypass written down)

The guard: an enforcement check refusing any `subprocess.run(…, text=True)` under
`scripts/enforcement/` that carries no `errors=`. **The cheapest way to satisfy it WITHOUT the
outcome is to paste `errors="replace"` onto a PATH decode** — which passes the check and
reintroduces exactly the FB2 corruption the precedent already paid for. So the check must key on
the FUNCTION, not the kwarg: any `subprocess.run` under `scripts/enforcement/` that is not
`git_text`/`git_paths`/`git_records`/`git_meta` is the finding. (The third draft named only the
first two verbs here — a guard written to that text would have flagged every `git_records` and
`git_meta` call it was built to permit.)

⚠️ **The allowlist is NOT 4 files. It has now been wrong in three consecutive drafts — 4, then
17 — so this document stops asserting the number and states the DERIVATION instead.** That is the
fix for a count whose every hand-written value has been stale: the builder RUNS it.

```
# the exemption set = every 5-verb subprocess call under scripts/enforcement/ that
# this design does NOT migrate to a decoder verb
verbs        = {run, Popen, check_output, call, check_call}
migrating    = the 85 unguarded sites MINUS the 6 NOT-GIT sites (which are OUT OF SCOPE
               per § Out of scope and therefore keep their raw call)
exemptions   = all 5-verb calls - migrating, PLUS git_output.py's own subprocess.run
```
Executed at the time of writing: 102 five-verb calls in 40 files; **79** migrate; **23 exemptions
across 14 files**, and 24 once `git_output.py` itself exists. The fourth draft's "17 / 12 files"
came from subtracting all 85 — i.e. from assuming the 6 NOT-GIT sites migrate, which § Out of scope
forbids — so it would have red the tree on day one with 6 undeclared findings
(`check_duplicates.py:20`, `check_lint_ratchet.py:52`/`:116`/`:203`, `check_mutation.py:171`,
`check_rule_grounding.py:136`): the exact failure it was written to prevent.

What the exemptions ARE, so a reviewer can sanity-check the derived list rather than trust it: the
6 NOT-GIT sites, ~10 calls that already decode correctly in BYTES mode and are exactly what this
design endorses (`check_hooks_index.py:68` and `check_undeclared_imports.py:216` do
`.stdout.decode("utf-8", "surrogateescape")`; `check_script_headers.py:206` is the precedent this
whole design generalises; three are in `check_secrets.py`, the shipped worked example this spec
declares out of scope), returncode-only calls (`git add`, `cat-file -e`, `check-ignore -q`), the
one `Popen`, and the module's own call. The allowlist is keyed on the CALL, not the file, and each
entry carries its reason on the same line. Stage 3's acceptance is re-stated to match: the cobra
check passes with exactly the derived exemption set and no undeclared member. That is
harder to satisfy dishonestly than a kwarg check — but review found the ACTUAL cheapest bypass,
and it is not allowlisting. (Two cheaper ones than the helper-relocation below, both found by
review and neither keyed on by a five-verb rule: `os.popen("git diff").read()`, which is
locale-strict and reproduces the exact defect in one line with no new file, and
`from subprocess import run as _r`, which unbinds the `subprocess.` attribute the guard matches on.
The guard must therefore key on the RESOLVED callee, building a local-name map from BOTH import
forms — `ImportFrom(module="subprocess")` for `from subprocess import run as _r`, and
`ast.Import` **with an `asname`** for `import subprocess as sp`, whose calls present as
`Attribute(value=Name("sp"))` and match no dotted `subprocess.*` matcher at all (executed: an
aliased `sp.run` reproduces the `UnicodeDecodeError` in one line). The second rule below is
resolved the same way, or `from os import popen` unbinds it exactly as the alias unbinds the first.
Neither is used in the directory today — the point is that both are one line away. ⚠️ **Two more
are cheaper still and a name-map cannot see either, so the guard needs a THIRD rule keyed on the
CALL SHAPE, not on any binding:** `__import__("subprocess").run(...)` presents as
`Attribute(value=Call(func=Name("__import__")))` and needs no import statement at all, and
`from subprocess import *` binds `run` through an `alias.name == "*"` that enters no map. Both were
executed and both reproduce the `UnicodeDecodeError` in one line.

⚠️ **STOP ENUMERATING SHAPES — the guard is an ALLOWLIST over statically resolvable callees, and
that is the whole rule.** Four drafts of this section each added the bypass the last one missed
(`Popen`, `getattr`, the alias import, the star import, `__import__`, `subprocess.__dict__["run"]`,
`importlib.import_module("subprocess").run`), and a reviewer found a cheaper one every time, because
"which names can reach `subprocess.run`" is not decidable by enumeration — Python has unboundedly
many spellings. Invert it:

> Inside `scripts/enforcement/`, a `Call` FIRES the guard when its **CALLEE** — not its subtree —
> is one of:
> 1. `<sp>.<verb>` where `<sp>` is any local name bound to the `subprocess` module (`import
>    subprocess`, `import subprocess as sp`) and `<verb>` ∈ {`run`, `Popen`, `check_output`,
>    `call`, `check_call`, `getoutput`, `getstatusoutput`};
> 2. a `Name` callee that is a verb under EITHER arm — and both arms are needed, because neither
>    covers the other:
>    - **(2a) RESOLVED.** The name is bound to a verb by a local binding map built from
>      `ImportFrom(module="subprocess")` (`from subprocess import run as _r`), `ast.Import` with an
>      `asname`, or a module- or function-level ASSIGNMENT whose value is itself a firing callee
>      (`_r = subprocess.run`). The alias is arbitrary, so only the map can see these.
>    - **(2b) LITERAL.** The name's id is one of the seven verbs, whatever bound it. This is what
>      catches `from subprocess import *`, where `alias.name == "*"` records no binding at all and
>      there is nothing for the map to resolve.
>
>    Measured cost of 2b's breadth: **zero** — the directory contains no bare-`Name` call whose id
>    is one of the seven verbs, so the fire set stays 102 and D10's arithmetic is undisturbed;
> 3. the shell-out family, resolved by BOTH arms of clause 2 — `os.popen`/`os.system` as
>    attributes, AND a bare `Name` bound by `from os import popen` (which the attribute shape
>    cannot see, and which the paragraph below names as live);
> 4. **any callee that is neither a `Name` nor `<Name>.<attr>`, and whose own resolution path
>    mentions `subprocess` (as a name or a string literal), `__import__`, or `import_module` —
>    EXCLUDING a callee built on an already-firing call.**
>
> A firing call is a FINDING unless it is on the allowlist (the four `git_output` verbs plus the
> declared exemptions, D10).

Clause 2a is the local-name map — cheap, and the only thing that can see an arbitrary alias; clause
2b is the literal-name net for the star import the map cannot record. The two are not alternatives,
and an earlier cut of this box said "no binding is resolved" while the paragraph beside it required
a map: coded literally, `_r = subprocess.run` then `_r([...], text=True)` fired NOTHING while
reproducing the `UnicodeDecodeError`. Clause 4 is what replaces enumeration: `subprocess.__dict__["run"](…)` (a `Subscript`
callee), `importlib.import_module("subprocess").run(…)` and `__import__("subprocess").run(…)` all
match it without being listed, and so does the next spelling nobody has thought of. **Its exclusion
is load-bearing** — without it, `subprocess.run([...]).stdout.splitlines()` fires, because the
CALLEE's subtree contains the run call; that is a chained accessor on a call already counted, not a
second process launch, and there are 11 of them in the directory.

**FIRE RATE, measured over all 7,740 `Call` nodes: 102 fires in 40 files — 101 `subprocess.run` +
1 `subprocess.Popen`, ZERO false positives, and clause 4 firing on nothing today.** That the total
is exactly D8 is the point: **the guard's fire set and D10's exemption arithmetic are now the same
population**, which they were not in any earlier cut. Two of those cuts are worth recording so the
next editor does not re-walk them: keying on "a callee that cannot be resolved statically" fires on
**657 calls in 66 of 78 files** — every `"".join(...)` — including `check_script_headers.py:150`'s
legitimate `getattr(p, kind)()`; and keying on the callee's SUBTREE mentioning `subprocess` fires
113, the extra 11 being those chained accessors, three of which sit on calls this design
deliberately never migrates (`check_hooks_index.py:68` and `check_undeclared_imports.py:216`, the
two `.stdout.decode("utf-8","surrogateescape")` calls this section holds up as CORRECT, plus the
NOT-GIT `check_lint_ratchet.py:203`) — so that predicate red the tree on exactly the pattern it
endorses. ⚠️ **Both new files carry an `# AFTER-EDIT:` header in the same change, or the gate reds on their
first run.** `.fabrik/doc-script-baseline.json` reads `{"headerless": 0}` — the ratchet is LOCKED at
zero, and `render_doc_script_links.py:287` fails when the count RISES, so landing `git_output.py`
plus the guard headerless is `ROSE 0 -> 2`, rc 1, while Stage 0's own acceptance (presence in D13
copies) reads green. `none` is a valid, honest header value for both.

**The check is `scripts/enforcement/check_subprocess_decode.py`, and it is WIRED in the same
change** — a hook entry in `.pre-commit-config.yaml` beside `check_duplicates.py` (`:78`) and
`check_review_coverage.py` (`:135`), and a row in `final_gate.py`'s Tier-2 roster. Naming the file
is not pedantry: 12 of the 78 enforcement scripts are referenced by no runner at all, so **an
unregistered check never runs and therefore always "passes"** — which is the CHEAPEST way to satisfy
Stage 3's acceptance without producing the outcome, and D-253 requires it be written down here. The
counter-measure is that Stage 3's acceptance names the runner, not the check: the guard must appear
in a `final_gate.py --check --json` roster line before the stage closes.

⚠️ **The second-cheapest bypass, also per
D-253: move the call OUT of `scripts/enforcement/`** — the guard is path-scoped, so a helper one
directory up satisfies it while decoding exactly as before. That bypass is named in the next
paragraph and is the one the allowlist genuinely cannot close; it is cheaper to detect socially (a
new `scripts/` helper called only from enforcement is visible in review) than to chase with a
matcher. That does NOT
close `os.popen`, which is a different module's function and is not a resolved callee of
`subprocess.*` under any resolution, so the guard carries a SECOND rule naming the shell-out
family explicitly: `os.popen`, `os.system`, `subprocess.getoutput` and
`subprocess.getstatusoutput`. ⚠️ Those last two are the live gap and the reason this rule is not
optional: they are NOT among the five call verbs, the resolved-callee rule enumerates those verbs
and so never reaches them, and `subprocess.getoutput("git show HEAD:f")` reproduces the exact
`UnicodeDecodeError` in ONE line — CPython decodes their output with the locale encoding. An
earlier draft wrote `commands.getoutput` here; `commands` is a Python-2 module that does not exist
on 3.12, so that matcher could never fire — a dead rule is wallpaper (FIX DIRECTIVE 5), and it was
guarding a name no bypass would use. A guard written to the resolved-callee rule alone still admits
the cheapest bypasses.) **The guard is PATH-SCOPED, so moving the call one directory up defeats
it:** a helper in `scripts/` rather than `scripts/enforcement/`, called from an enforcement check,
satisfies the guard, decodes exactly as before, and leaves no reviewer-visible artifact. Two more:
`subprocess.Popen(...).communicate()` is not `run` — and there is already one legitimate `Popen` in
the directory (`check_mutation.py:146`, `start_new_session=True` for group-kill) that the 5-name
allowlist does not cover — and `getattr(subprocess, "run")(...)` presents as neither a `Name` nor
an `Attribute` to an AST check. The second draft's answer — key on the IMPORT of `subprocess` — is too blunt: **40 of the 78 files
import `subprocess` today, and 13 will still need the NAME after migration** for `SubprocessError`,
`CalledProcessError`, `TimeoutExpired` and `DEVNULL`, so that guard needs a ~15-file allowlist and
becomes wallpaper (FIX DIRECTIVE 5). Key it instead on the CALLEE, per the predicate above, whose
clauses 1–3 cover what this paragraph calls the **five call verbs** — `subprocess.run`,
`Popen`, `check_output`, `call`, `check_call` — plus a separate rule for `getattr(subprocess, …)`.
That drops the allowlist from a ~15-file name-based one to the DERIVED set of § Cobra — the 6
genuinely non-git invocations, the already-correct bytes-mode calls (including the
`check_script_headers.py:206` precedent this design generalises and the three in
`check_secrets.py`), the returncode-only calls, the one `Popen` and the module's own — which is
small enough to read. And the guard
must permit all FOUR decoder functions, not the two the second draft named.

## Validation

The fleet test the reporter asked for, and this spec's acceptance criterion: **drive every check in
`scripts/enforcement/` against one fixture repo** whose artefacts exist in **ALL THREE GIT STATES —
committed at `HEAD`, STAGED in the index, and present as an UNSTAGED/UNTRACKED worktree delta.**
⚠️ This is the difference between an acceptance that proves the migration and one that passes on
UNMIGRATED code, and it is not optional: **34 of the 79 migrating sites read the INDEX**
(`--cached`/`--staged`/`show :<path>`) and 8 more are `status --porcelain`, so on a
merely-committed fixture 42 of 79 scan an EMPTY stream and report green having decoded nothing.
Executed on a repo built exactly as "tracked" describes: `git diff --cached bad.md` → rc 0, 0 bytes,
NO RAISE, while `git show HEAD:bad.md` RAISES; with a raw `bad\xff.md` path and
`core.quotePath false`, `status --porcelain -uall`, `diff --cached --name-only` and
`--numstat` all return empty at rc 0 while `ls-files`, `ls-tree` and `log --name-only` raise. No
single state covers `HEAD` (`show`, `log`, `ls-tree`, range diffs), the index (`--cached`) and the
worktree (`status -uall`, `ls-files --others`) at once — which is § Validation's own
*"a check that stops raising by scanning nothing has not been fixed"*, applied to its own fixture.
The repo therefore contains (a) a NUL-free non-UTF-8 tracked file,
(b) a `*.bin diff` attributes line over a NUL-bearing blob, (b2) ⚠️ **`git config core.quotePath false`
in the fixture repo itself — without it the whole path half of this harness is INERT**: by default
git C-quotes a non-ASCII path (`"bad\377.md"`), which is pure ASCII and decodes strictly without
raising, so Stage 2's acceptance would pass on UNMIGRATED code. Executed: `git ls-files` on a
`bad\xff.md` returns `b'"bad\\377.md"\n'` (strict decode OK) by default and `b'bad\xff.md\n'`
(strict decode RAISES) with the config. Only 2 of the 37 PATH-ONLY sites force the config
themselves, so the fixture must — (c) a path with a raw non-UTF-8 byte,
(d) a path with a tab, a backslash and a `"`, and (e) a commit whose message is not valid UTF-8 —
⚠️ **which a PLAIN `git commit -F` cannot produce — the fixture needs ONE config line, and without
it the commit-message half of this harness is inert exactly as (b2) describes for paths.** Executed:
a message file holding a raw `\xff` committed with a bare `git commit -F` stores `\303\277` under
`LC_ALL=C`, `C.UTF-8` and `en_US.UTF-8` alike, and `%B` decodes cleanly. **The working recipe is two
lines** — `git config i18n.commitEncoding ISO-8859-1`, then `git commit -F <msg>`: the raw byte is
stored AND emitted, and `git log --format=%B` raises
(`%B` hex `73 75 62 6a 20 ff 20 62 61 64`, then `'utf-8' codec can't decode byte 0xff in position 5`).
⚠️ Leave `i18n.logOutputEncoding` UNSET — it defaults to `i18n.commitEncoding`, so input and output
encodings match and git converts nothing; set it to UTF-8 and the same repo transcodes on output and
`%B` stops raising. (An earlier draft asserted the opposite — that `commitEncoding` re-encodes on
output and that raw object plumbing was the ONLY route. Both halves were wrong: the config works, and
the plumbing route it recommended is additionally incomplete, since a `git hash-object -t commit -w
--stdin` object is UNREACHABLE — `git log` still sees only the original commit — until a
`git update-ref` the draft never mentioned.) Without a working (e), Stage 1's run over the MULTI-USE
adapter and over `check_plan_tickets.py:1063`'s `%B` half passes on UNMIGRATED code, and the
adapter's C4 red-first test can never be seen red —
⚠️ **The acceptance is THREE assertions, and it is NOT an equality against the pre-migration run.**
Earlier drafts said *"each still reports what it reported on the same repo without those files"*,
which is exactly backwards and would certify a broken build: a check that silently DROPS the bad
artefact produces byte-identical output, while a correctly migrated check legitimately produces
MORE. Executed on the live `check_doc_links.py` (its `:117` is a PATH-ONLY Stage-2 site) across
three fixtures: with a `docs/ba\d.md` carrying a broken link, `git ls-files` still C-quotes the
backslash even under `core.quotePath false`, the check never sees the file, and it prints
`OK — 0 broken of 1 refs across 2 docs` at rc 0 — **byte-identical to the fixture with no artefact
at all**. With the same broken link on an un-quoted `docs/café.md` it prints
`ERROR: docs/café.md: broken ref -> nope.md` at rc≠0. Equality passes the first and fails the
second, i.e. it greens the failure and reds the fix. So:

1. **No check raises.** Necessary, never sufficient — a check that stops raising by scanning
   nothing has not been fixed.
2. **POSITIVE: every check whose surface contains the artefact NAMES it in its output.** This is
   the assertion that actually proves the migration, and it is the one no earlier draft had. The
   artefact is planted to be FOUND; a run that does not mention it decoded nothing. Per check, the
   expected mention is derived once from the class its site is in — a PATH-ONLY site must emit the
   path, a CONTENT site must act on the content, and ⚠️ **a META site is asserted at the CALL
   BOUNDARY, because most never print the value at all.** Executed: of the four
   `rev-parse --abbrev-ref` sites, `check_citations_resolve.py:131` consumes its ref at `:139` into
   an `f"{...}..HEAD"` range and `check_test_proposal.py:134` at `:157` into `ls-tree` args —
   neither is ever printed, so no stdout assertion can exist for them; only
   `check_corpus_weight.py:171` and `check_plan_tickets.py:2557` surface theirs. Without this arm
   Stage 3's criterion is unsatisfiable for half its population.
3. **NEGATIVE: findings unrelated to the artefact are unchanged** — the same (exit code, stdout)
   comparison as before, but computed with the artefact's own lines EXCLUDED, so it catches
   collateral regression without punishing the intended new finding.

Run every case with `stdin` closed AND as a live pipe.

⚠️ **Two ingredients the first draft's fixture omitted, without which it cannot catch the
regressions § The `-z` trap executed:** (f) a RENAME (the porcelain / name-status / numstat record
shape only diverges on one) and (g) a range of at least TWO commits (`check_plan_tickets`'s parser
only runs over one).

⚠️ **And the builder-must-invent gap, named so it is scheduled rather than discovered.** "Drive
every check against one fixture repo" is not a cwd exercise: **15 of the 78 scripts contain `parents[2]`, 14 of them resolving their
root from `Path(__file__).resolve().parents[2]`** — the SCRIPT's location, not the cwd — including
`check_convergence`, `check_plan_tickets`, `check_subagent_flywheel` and `check_lint_ratchet`, four
of the critical set; **31 use `Path.cwd()`**, and ⚠️ the two populations are NOT disjoint — 3 files
are in both (`check_convergence`, `check_plan_tickets`, `check_stage_artifacts`), so "a further 31"
was wrong and 15 + 31 double-counts them. There is also a THIRD convention the either/or framing
hides, and it is the one that makes the harness easy: **11 scripts take `--project-root`**, and for
`check_convergence` and `check_plan_tickets` the `parents[2]` use is only a `sys.path.insert` while
the ROOT comes from that flag (defaulting to cwd). So the harness drives `--project-root` wherever
it exists, cwd where it does not, and materialises `scripts/enforcement/` inside the fixture only
for the `parents[2]`-rooted remainder. Second, there
is **no common verdict schema** across the 78 — some print free text, some print `OK`/`WARN`, some
only set an exit code — so assertion 3's "unchanged" must be defined as *(exit code, full stdout)*
equality per script **with the artefact's own lines filtered out**, because exit code alone is blind
to a silently reduced finding count, which is the very class this exists to catch. Assertion 2 needs
no schema: it is a substring test for the planted artefact's name.

⚠️ **Stage 2b's baseline follows the same correction.** *"the parsed record set is IDENTICAL to the
pre-migration one field for field"* is unobtainable once the fixture is hardened — executed on a
three-state fixture with `core.quotePath false`, the PRE-migration `status --porcelain`,
`diff --cached --numstat`, `diff --cached --name-status` and `ls-tree -r -l` all RAISE, so there is
no pre-migration record set to compare against. Stage 2b asserts instead that the post-migration
record set (a) parses without raising, (b) CONTAINS the rename, the copy and the non-UTF-8 path as
distinct records with their fields in the documented positions, and (c) is field-for-field identical
to the pre-migration set **on a fixture variant carrying only the rename and the copy**, where the
pre-migration run does succeed. That variant is the regression baseline; the hardened fixture is the
capability test.

## Out of scope

- The 6 NOT-GIT sites (I8) — jscpd (`check_duplicates.py:20`), ruff JSON ×2
  (`check_lint_ratchet.py:52`, `:116`), `ruff --version` (`:203`), mutmut
  (`check_mutation.py:171`) and a `review_rubric.py` subprocess (`check_rule_grounding.py:136`).
  They decode third-party
  tool output, not git, and forcing git semantics on them would be a false uniformity. They get
  their own ruling when someone measures their inputs.
- `check_secrets.py` itself — shipped, reviewed and synced at `e33dcdd63`; it is the worked example.
- The ~46 project repos' own scripts outside `scripts/enforcement/`.

## Adjudicated and REFUTED (recorded so it is not re-raised)

A review seat reported the repo denominator as **43**, not 45, and scaled the tracked-file and
commit counts down with it. Re-derived two ways here — `for d in /opt/*/; do [ -e "$d.git" ]` and
`find /opt -maxdepth 2 -name .git` — both answer **45**, and summing `git ls-files` across them
gives **102,148** tracked files against the spec's 102,145 (three files' drift in a live tree over
a few hours). The seat's own 43-repo scope is what moved its file and commit totals. The spec's
populations stand; the correction is refused.

## Corrections this spec owes

`check_secrets.py`'s comment at `e33dcdd63` says a path is quoted *"On git's DEFAULT config"*,
which reads as though `core.quotePath=false` avoids it. Executed here: with that config a tab, a
backslash and a `"` are still quoted; `-z` is what disables quoting. The shipped CODE is correct
(it uses `-z`); only the explanation is incomplete. The migration touches that file anyway, so the
comment is corrected there rather than in a separate change.

## Testing — ruling on the C3/C4-vs-C5 tension

The first draft ruled "decoder = behaviour change, all 85 edits = refactor owing zero tests".
Review showed that split was too generous, on C5's own second sentence, which the first draft
quoted only half of: *"Existing integration/E2E tests must pass."* A refactor exemption is a
PRECONDITION, not a licence — and **7 of the 35 files have NO test file at all** (`check_compose_services`,
`check_configuration_md`, `check_env_updates`, `check_openapi_sync`, `check_readme_md`,
`check_routing_policy`, `check_test_coverage`; scanned across 361 files under `tests/`). "Existing
tests must pass" licenses nothing where none exist.

**The corrected three-way ruling:**

| Population | Classification | Owes |
|---|---|---|
| The decoder itself | Behaviour change | Red-first per decode class: content raise, path raise, the newline-translation collision, lossless round-trip, unavailable-git, non-zero exit preserved |
| The 13 MIXED-RECORD sites + D5 + D4 (union **50**, five sites in two of the three) | **Behaviour change, not refactor** — the record shape and the exit-code contract both move (§ The `-z` trap, § Approaches C) | One red-first test each, Bugfix-shaped per `45-testing-strategy.md:32`'s own table |
| The genuine remainder | Refactor | Zero new tests — but only where an existing test covers the file; the 7 untested files get one characterisation test first |

This is still C3's *"lean-but-complete, NOT 100%-line-coverage dogma"* — it is not 85 unit tests. It
is 50 behaviour tests plus one directory-wide fixture, which is what the evidence supports.

## Cost

⚠️ **`Profile: standard`, re-ruled — the first draft said `small` on the premise that the migration
was mechanical, and § The `-z` trap disproved that premise by execution.** Two code files
(`scripts/enforcement/git_output.py` NEW, plus the cobra check), a test file, and a migration of 85
sites across 35 files of which **13 are parser rewrites and 42 carry an exit-code contract** (D5 + D4, disjoint sets) — a UNION of **50** sites owing a behaviour test (D5 ∪ D4 ∪ the 13 MIXED, five sites in two of the three), not 55: five are counted twice (`check_plan_tickets.py:1063`, `check_review_coverage.py:103` and `check_review_hygiene.py:908` are MIXED *and* `check=True`; `check_corpus_weight.py:209` and `check_phase_tests.py:134` are MIXED *and* `.returncode`) — 50
reviewed edits, not 85 mechanical ones. The decoder, the cobra check and those 50 are all reviewed
surface. Everything here is a governance-sync path, so the build owes the full `/fabrik-review` and
one forced sync, and the staging in § Sequencing is what keeps any single review round tractable.
