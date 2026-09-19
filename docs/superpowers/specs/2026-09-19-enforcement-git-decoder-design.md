# Design — a shared git-output decoder for `scripts/enforcement/`

**Status:** DRAFT
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
| I3 | *"17 of them reading file content or commit messages (the same crash class)"* | IN SCOPE, and it is the staging boundary | § Sequencing |
| I4 | *"a measured trigger population of 63 non-UTF-8-but-git-says-text files in 2 of 45 repos"* | CONFIRMED, and the grounding found the population is **larger than the file count suggests** — two further triggers below | § Triggers |
| I5 | *"generalises `check_script_headers.py`'s existing bytes-then-decode `_git` helper"* | ADOPTED as the base, with three corrections the brief did not carry | § Chosen approach |
| I6 | *"ships a lint rule as its cobra guard"* | ADOPTED, with its own cobra written down | § Cobra |
| I7 | *"it is rule-1 work on a sync path"* | CONFIRMED against the live filter | § Lane |
| I8 | The 5 NEEDS-A-PROBE sites are not git at all (jscpd, ruff JSON, mutmut, a `review_rubric.py` subprocess) | EXCLUDED from the git decoder; they get their own ruling | § Out of scope |
| I9 | `check_lint_ratchet.py:229` feeds `git show` output to `json.loads` | IN SCOPE as a named exception | § The one parsing consumer |
| I10 | Three duplicated `_git` helpers (`check_doc_sync.py:70`, `check_subagent_flywheel.py:104`, `check_script_headers.py:206`) | IN SCOPE — collapsing them is most of the value | § Chosen approach |
| I11 | A comment shipped in `check_secrets.py` at `e33dcdd63` attributes path quoting to *"git's DEFAULT config"* | CORRECTION OWED — executed below; the code is right, the explanation is incomplete | § Corrections this spec owes |
| I12 | `check_script_headers.py:206` passes no `stdin=` | IN SCOPE — the hang class applies there too | § Chosen approach |

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
**60 / 25 across 14 files**. The table below is a FLOOR and it errs in the direction that makes
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

The worked example is `check_subagent_flywheel.py:104` — `except Exception: return None` — whose
caller at `:231` reads that `None` as *"couldn't read the commits (git failure) → fail-safe, don't
block"*. A non-UTF-8 commit message therefore does not crash that gate; it makes it **stop
blocking**, exactly the shape D-308 ruled against ("I could not look" reading as "nothing to
find"). The reported incident was a CRASH, which is why it was reported at all; the 20 silent
sites are the ones nobody will ever file.

**This splits two design consequences the crash framing hides.** (a) SEQUENCING: the silent 22
outrank part of the crash 63, because a crash is self-reporting and a lenient gate is not.
(b) VALIDATION: "assert none raises" would PASS on all 22 while they are still broken — which is
why § Validation's second half (each check still reports what it reported) is load-bearing rather
than belt-and-braces, and why it is stated as an equality, not an absence.

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
§ Sequencing's "12 METADATA sites" is superseded by 7 + 6.

⚠️ **The third draft's partition summed to 92, and its own table summed to 99** — it carried
`44 PATH-ONLY` in the sum line against `51` in the table, and neither reached 85. Three satellite
counts disagreed with the table too (`5 NOT-GIT` at § Cobra vs `6` here; `11 MIXED-RECORD` at
§ Testing vs `13` here). Two causes, both mechanical and both worth naming because the next
re-derivation will hit them: (a) `ast.literal_eval` fails on a STARRED UNPACK, so the six sites
built as `["git", *args]` and the four built as `subprocess.run(cmd, …)` over a list of literal
command lists read as "non-git" and were counted in the wrong row — `check_phase_tests.py:134` is
`git diff --name-status … -z`, not a non-git call; (b) a `--name-only` diff and a bare
`git diff -- <path>` share the verb and differ entirely in what they emit.

### The one helper — the only place the four-verb API does not close

`check_subagent_flywheel.py:107` is a `_git(args)` wrapper whose argv arrives from 5 callers
spanning THREE shapes — `:119` (`merge-base`) and `:154` (`show -s --format=%at`) are metadata,
`:130` and `:136` (both `--name-only`) are paths, and `:230` (`log --format=%B`) is content — so
no single verb is correct for the SITE. It is migrated by DELETING the local wrapper and moving each caller to the
verb its own argv names. That is the only structural edit in the migration; everything else is a
call-site substitution.

⚠️ **Its callers therefore split across STAGES, and one of them is the document's own headline
example.** `:230` is `["log", "--format=%B", f"{base}..HEAD"]` — a commit-message CONTENT read, and
the site § The problem argues hardest about (*a non-UTF-8 commit message does not crash that gate;
it makes it stop blocking*). It migrates in **Stage 1** under Stage 1's acceptance, not in Stage 2:
Stage 2's fixture is path-shaped and can never exercise a non-UTF-8 commit message, so migrating
that caller there would move the one site the design cares most about under a criterion blind to
its failure mode. `:119` (`merge-base`) and `:154` (`show -s --format=%at`) go to Stage 3 as
META-safe; `:130` and `:136` (both `--name-only`) to Stage 2. The wrapper is deleted in Stage 1
with `:230`, and the remaining callers use the decoder verbs directly from that point.

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

## RESUME

**State:** DRAFT at `36aa50e2c`. Four review rounds; 39 confirmed defects fixed, the 10 in
§ OPEN DEFECTS still confirmed and unfixed. `/fabrik-spec-review` handed off rather than flipping,
because the D-278 scope-growth stop fired at 2 of the last 3 rounds (confirmed/own-fix
`13/4 → 12/12 → 10/9`).

**The next pass, and its one binding condition:** fix the 10 in § OPEN DEFECTS in a single pass in
which the FINDER and the FIXER are DIFFERENT agents. That separation is the entire reason these
stand open — rounds 3 and 4 each confirmed ~12 defects and each time nearly every one lay inside
the fix prose the previous round had just written. A reviewer correcting its own findings
regenerates the surface it is correcting.

**Two of the ten need a RULING, not an edit** — settle them before touching prose:
- Defect 1: either the MULTI-USE wrapper is deleted in Stage 1 and ALL five callers migrate there
  (then Stages 2 and 3 carry none of this file and say so), or the wrapper survives to Stage 3.
  Both are coherent; the document currently asserts both.
- Defect 4: `GitUnavailableError` is raised on NON-EXECUTION ONLY (§ the contract) or a TIMEOUT is
  folded into it (§ the mirror, and the precedent at `check_script_headers.py:219` folds it). Rule
  once, in one place, and re-derive the affected handler set from the ruling rather than editing
  the existing numbers.

**Do NOT re-derive — verified correct by a fresh seat in round 4:** the partition
`15 CONTENT + 37 PATH-ONLY + 13 MIXED + 7 META-safe + 6 META-path + 6 NOT-GIT + 1 MULTI-USE = 85`,
with no site in two rows or none; the census 87 sites / 2 guarded / 85 unguarded / 35 files; 102
five-verb calls in 40 files and the 23-exemption cobra derivation; the `-z`-before-`--` rule, swept
over every real PATH-ONLY argv shape including `-c`-prefixed globals, trailing pathspecs, trailing
revisions and doubled `-z`; the sync citations `:2445`/`:2468`/`:2473` and the 47 reachable copies;
every print-path citation and the 2,942-line span; the 50-site union and its five double-counts;
`safe()`'s round-trip; `rev-parse -z` echoing `-z` at rc 0 and `merge-base -z` at rc 129; and the
crash/silent table at 63 / 22 across 12 files.

**And the method lesson this artifact paid four rounds for:** a count confirmed wrong in two
consecutive rounds is replaced by its DERIVATION, not corrected a third time. The cobra allowlist
was stated as 4 files, then as 17 calls in 12 files — both wrong; replaced with the derivation it
was the only round-3 fix to survive round 4 intact, while every count restated as a number came
back stale in the very next round.


## ⚠️ OPEN DEFECTS — confirmed 2026-09-20, UNFIXED, and why they are unfixed

This spec is **DRAFT** and stays DRAFT. A fourth review round confirmed the ten defects below and
they are recorded here rather than patched, because `command_run.py`'s scope-growth stop (D-278)
fired at 2 of the last 3 rounds: `confirmed/own-fix 13/4 → 12/12 → 10/9`. Rounds 3 and 4 were
almost entirely defects inside text the review itself had just added — correcting prose was
regenerating the surface being corrected. The loop's own exit says to stop and route, and the
standing rule is that a site yielding confirmed defects in two consecutive rounds is REWRITTEN,
not patched a third time. **Every item below is EXECUTED evidence from a fresh non-authoring seat,
not a candidate.** Fix them in one pass, with a different agent finding than fixing.

**UNBUILDABLE**

1. **The MULTI-USE wrapper deletion contradicts its own caller staging.** § The one helper says the
   `check_subagent_flywheel.py:104` wrapper *"is deleted in Stage 1 with `:230`"* while assigning
   `:119`/`:154` to Stage 3 and `:130`/`:136` to Stage 2. Delete it in Stage 1 and those four
   callers raise `NameError` in a fleet-synced gate across all 47 copies until Stage 3; rewrite
   them in Stage 1 instead and Stages 2 and 3 are empty for this file, so their stage-specific
   acceptance never covers the code that changed. Pick one and say it once.
2. **`check_script_headers.py:206` is declared "single-shape" and is polymorphic across three.**
   § A polymorphic `_git` helper is SPLIT says it *"collapses"*; its callers are `ls-files -s -z`
   at `:243` (a MIXED RECORD — `<mode> <sha> <stage>\t<path>`), `rev-parse --show-toplevel` at
   `:295` (META) and two `--name-only` at `:300`/`:314` (PATH). Two further consequences: its call
   at `:213` is BYTES-mode and therefore not among the 85, so § Cobra's derivation keeps it as an
   EXEMPTION while I10 puts it in scope; and it passes `env={**os.environ, "LANGUAGE": "C"}`, which
   the mandated `git_*(args, *, cwd=None, timeout=None)` signature has nowhere to carry — the same
   defect class this spec already caught for `cwd=` and `timeout=`.
3. **The second cobra rule names a Python-2 module and misses the live bypass.** `commands` does
   not exist on 3.12 (`No module named 'commands'`), so that matcher can never fire — wallpaper by
   FIX DIRECTIVE 5. Meanwhile `subprocess.getoutput("git show HEAD:f")` is not one of the five
   verbs and reproduces the exact `UnicodeDecodeError` in one line (executed), cheaper than
   `os.popen`. Replace `commands.getoutput` with `subprocess.getoutput`/`getstatusoutput`.
4. **The `GitUnavailableError(OSError)` MIRROR names the wrong site set, in the wrong direction.**
   The ruling itself is sound and `check_lint_ratchet.py:229` is safe under it. But the mirror
   paragraph claims *"4 sites catch `SubprocessError` but not `OSError`"* and that a timeout is
   swallowed there: executed, it is **5 git sites** (6 with the out-of-scope mutmut one) and NONE
   of them catches `TimeoutExpired` — they catch `CalledProcessError`/`FileNotFoundError`. The
   timeout mirror shows at the 22 sites that DO catch `OSError`. And `31 / 27` only reproduces if
   `ValueError` and `TimeoutExpired` join the narrow set; the four names as stated give 28 / 26.
   Unresolved beside it: the contract says `GitUnavailableError` is raised on NON-EXECUTION ONLY
   while the mirror says a timeout is folded into it — the precedent folds it at
   `check_script_headers.py:219`. Rule once, in one place.
5. **Stage 3's bullet was not updated with Stage 2's.** It still reads *"the 7 META-safe sites"* and
   omits `check_subagent_flywheel.py:119`/`:154`, which § The one helper assigns to it.

**COSMETIC — stale satellites of numbers corrected elsewhere in the same pass**

6. § It is TWO failure classes: *"nearer 60 / 25 across 14 files"* — the file count was corrected,
   the site pair was not. On the corrected 63 / 22 base its own premise (*"5 further sites across 2
   more files"*) gives **58 / 27**.
7. § It is TWO failure classes: *"the 20 silent sites are the ones nobody will ever file"* — 22.
8. § Cost: *"a UNION of 50 sites … those 46 are all reviewed surface"* — the 46 is the superseded
   `~46` and names no set in this document.
9. § Approaches C: *"11 of the 85 sites carry paths AND a non-path field in ONE stream"* —
   § Classification, § The `-z` trap and Stage 2b all say **13**; this enumeration omits
   `check_phase_tests.py:134` and `check_corpus_weight.py:209`.
10. Two citations point at a `def` rather than the call: `check_subagent_flywheel.py:104` for an
    `except Exception:` that is at `:109`, and `check_script_headers.py:206` inside a paragraph
    that says the allowlist is *"keyed on the CALL, not the file"* — the call is `:213`.

**What the same round verified as CORRECT, so the next pass does not re-derive it:** the partition
(15/37/13/7/6/6/1 = 85, no site in two rows or none); the census 87/2/85/35; 102 five-verb calls in
40 files and the 23-exemption derivation; the `-z`-before-`--` rule, swept over every real
PATH-ONLY argv shape including `-c`-prefixed globals, trailing pathspecs, trailing revisions and
doubled `-z`; the three sync citations `:2445`/`:2468`/`:2473` and the 47 reachable copies; every
print-path citation (`:103`/`:130`/`:133`/`:2984`/`:3072`/`:3074`/`:3078`, the 2,942-line span);
the 50-site union and its five double-counts; `safe()`'s round-trip; `rev-parse -z` echoing `-z` at
rc 0 and `merge-base -z` at rc 129; and the crash/silent table at 63 / 22 across 12 files.


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
execution: **11 of the 85 sites carry paths AND a non-path field in ONE stream**, so neither verb
fits — eight `git status --porcelain`, `check_test_coverage.py:43` (`--name-status`),
`check_changelog.py:79` (`--numstat`), and the worst case `check_plan_tickets.py:1063`
(`git log --name-only --format=%x01%H%x02%B%x02`), which reads a commit BODY and PATHS in the same
call. The shapes are therefore:

⚠️ **FOUR shapes, not three**, and one shared signature — 38 of the 85 sites pass `cwd=` and 20
pass `timeout=`, which a one-argument signature silently drops:

```python
def git_text|git_paths|git_records|git_meta(
    args: list[str], *, cwd: Path | None = None, timeout: float | None = None,
) -> tuple[int, str] | tuple[int, list[str]]: ...
```

| Function | For | Decode | `-z` |
|---|---|---|---|
| `git_text(args)` | content — `show <rev>:<path>`, `diff` without a name filter, `log --format=%B` | `errors="replace"` | never |
| `git_paths(args)` | PURE path lists — `--name-only`, `ls-files` | `surrogateescape`, split NUL | **forced — APPENDED** |

⚠️ **"Forced" needs an insertion POINT, and only one of the two readings works.** `git_paths`
APPENDS `-z` to the end of `args`; it never prepends. Two PATH-ONLY sites open their argv with
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
| `git_meta(args)` | `rev-parse`, `merge-base`, `ls-tree`, version strings | `surrogateescape` | never |

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
other three `tuple[int, str]`), and they RAISE `GitUnavailableError` when git cannot be RUN.

⚠️ **RULING — `GitUnavailableError` SUBCLASSES `OSError`, unlike the precedent.**
`check_script_headers.py:77` declares `class GitUnavailableError(Exception)`, and generalising that
verbatim is a fleet-wide fail-open→crash regression. Executed by AST: **31 of the 85 sites sit
under ONLY narrow handlers** — `OSError`, `SubprocessError`, `CalledProcessError`,
`FileNotFoundError` — and 27 of those are git sites; e.g. `check_review_hygiene.py:915` is
`except (subprocess.CalledProcessError, FileNotFoundError, OSError): return []` and
`check_doc_sync.py` catches `(OSError, SubprocessError)`. A plain-`Exception` type is invisible to
every one of them, so on a box with no git those 27 currently-fail-open gates become tracebacks.
Subclassing `OSError` is also semantically right rather than a dodge: the condition being wrapped
IS an `OSError` today (`FileNotFoundError` from the exec). **MIRROR — name the shape this breaks:**
a site catching only `OSError` now also swallows a git TIMEOUT, which is `subprocess.TimeoutExpired`
(a `SubprocessError`, NOT an `OSError`) before the migration and is folded into
`GitUnavailableError` after it. That site gets LESS loud, not more. The 4 sites that catch
`SubprocessError` but not `OSError` are where that shows, and each is named in the Stage that moves
it. This also keeps § The one parsing consumer true: `check_lint_ratchet.py:229`'s
`except (OSError, ValueError)` still sees an unavailable git. They
do NOT raise on a non-zero exit — re-derived by AST on 2026-09-20, **34 of the 85 sites read
`.returncode` within 12 lines of the call**, and at least
three use a non-zero exit AS THE ANSWER (`check_corpus_weight.py:184` falls through `origin/master`
→ `origin/main` on rc 1; `check_test_proposal.py:142` returns `None` on rc 128 in a commitless repo;
and `check_mutation.py:59`, which is the near-miss: it never reads `.returncode` at all — `.stdout.strip() or "HEAD~1"` makes EMPTY OUTPUT the signal, so it migrates cleanly either way). A raising-on-exit decoder would delete that
branch at 34 sites. The exit code is therefore in the RETURN, not in a `check=` kwarg and not in
an exception: the signature is exactly `git_*(args, *, cwd=None, timeout=None)` as § The API
states, with no fifth parameter and no fifth `git_*` VERB. The module also exports `safe()` and the
`GitUnavailableError` type, which are not verbs and are both REQUIRED. (The third draft ended this paragraph with
"all three return `str`" and a `git_status(args) -> tuple[int, str]`, both residue of the
superseded three-function draft; `git_status` is not part of this design.)

⚠️ **The 8 sites that pass `check=True` are a THIRD exit-code shape and they are dispositioned
here, because "no `check=` parameter" alone would leave a builder guessing.** Executed by AST over
the 85: `check_env_vars.py:203`, `check_plan_tickets.py:1063`, `check_review_coverage.py:103`,
`check_review_hygiene.py:908`, `check_structure.py:157`, `validate_conventions.py:227`, `:233`,
`:239` — and NONE of them is among the 34 that read `.returncode`, so 42 of the 85 are
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
3. **A named error type, raised on NON-EXECUTION ONLY — a failing exit is RETURNED, never raised.**
   (The second draft said "and a failing exit" here while § Approaches C said the opposite; resolved
   in favour of returning, because 34 of the 85 sites read `.returncode` and three use a non-zero
   exit AS the answer.) `GitUnavailableError`
   already exists in the precedent; the decoder exports it so every consumer can choose LOUD over
   silently-clean, which D-308 makes mandatory for any gate whose absence of output reads as a pass.

### ⚠️ A polymorphic `_git` helper is SPLIT, never collapsed

I10 calls collapsing the three duplicated `_git` helpers *"most of the value"*. For two it is. For
`check_subagent_flywheel.py:107` it is a trap: that ONE `subprocess.run` serves five argv shapes
from five call sites — `merge-base` (meta), two `--name-only` (paths), `show -s --format=%at`
(meta) and `log --format=%B` (content). No single verb is correct, and `git_paths` would make
`merge-base -z` exit 129, which the helper turns into `None`, which its caller at `:231` reads as
*"fail-safe, don't block"* — the exact silent degradation this spec exists to close. **Rule: a
helper whose argv varies by caller is split at the CALL SITES first.** The other two
(`check_doc_sync.py:70`, `check_script_headers.py:206`) are single-shape and do collapse.

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

**MIRROR, stated because it is the change's real cost: 35 fleet-synced scripts gain an import they
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
how they can be proven:

- **Stage 0 — land the module ALONE and sync it.** 35 of 78 gates are about to gain a hard import
  of a 79th file, and the sync copies `scripts/enforcement` per-repo via `rglob`: a mid-directory
  failure leaves a repo holding migrated consumers and no `git_output.py`, i.e. `ImportError` at
  load for 35 gates there. So it ships with ZERO consumers, is `--force` synced, and its presence
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
- **Stage 1 (the live class): the 15 CONTENT sites, silent-degrading ones FIRST, plus `check_subagent_flywheel.py:230` (the `%B` caller of the MULTI-USE helper — CONTENT by shape, and the site § The problem is built on).** Acceptance: a
  fixture repo carrying a NUL-free non-UTF-8 tracked file AND a `*.bin diff` attributes line;
  every one of the 15 checks runs against it without raising AND — for any of them among the 12
  silent-degrade files — still returns the same verdict it returns on the same repo without those
  files. A silent site that stops raising has not been fixed; it was never raising.
- **Stage 2: the 37 PATH-ONLY sites, the 6 META-path sites and the 2 path-shaped callers of the MULTI-USE helper** (§ The one helper splits its 5 callers by shape; the helper itself is deleted in Stage 1). Acceptance: the same fixture repo gains a path with a raw
  non-UTF-8 byte, a tab, a backslash and a `"`; every check runs without raising AND without
  silently dropping a file (the count it reports must not fall).
- **Stage 2b (the riskiest stage, and the fourth draft had no stage for it at all): the 13 MIXED
  RECORD sites.** These are the `git_records` population — the 8 `status --porcelain` calls,
  `check_changelog.py:79` (`--numstat`), `check_test_coverage.py:43` (`--name-status`),
  `check_plan_tickets.py:1063` (`%B` + `--name-only`), `check_phase_tests.py:134`
  (`--name-status -z`) and `check_corpus_weight.py:209` (`ls-tree -r -l`). § The `-z` trap and
  § Cost both call these PARSER REWRITES rather than mechanical edits — the record SHAPE moves —
  so they cannot ride Stage 2's substitution pass. Acceptance is its own: a fixture repo carrying
  a RENAME and a COPY in one commit plus a non-UTF-8 path, driven through each of the 13, asserting
  the parsed record set is IDENTICAL to the pre-migration one field for field. ⚠️ No `-z` is added
  to any of them (§ The `-z` trap): `-z` INVERTS a rename's field order and these parsers read the
  human shape.
- **Stage 3: the 7 META-safe sites.** Migrated for uniformity, not safety — a reviewer must be able
  to read "no `text=True` in this directory" as an invariant rather than checking 87 call sites.
  Acceptance: the cobra check (below) passes with exactly its DERIVED exemption set and no
  undeclared one — "zero exemptions" is unreachable and the fourth draft asserted it against its
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
The guard must therefore key on the RESOLVED callee — an `ImportFrom(module="subprocess")` builds
a local-name map, which closes the alias — rather than on the dotted source text. That does NOT
close `os.popen`, which is a different module's function and is not a resolved callee of
`subprocess.*` under any resolution, so the guard carries a SECOND rule naming the shell-out
family explicitly: `os.popen`, `os.system`, `commands.getoutput`. A guard written to the
resolved-callee rule alone still admits the cheaper of the two bypasses.) **The guard is PATH-SCOPED, so moving the call one directory up defeats
it:** a helper in `scripts/` rather than `scripts/enforcement/`, called from an enforcement check,
satisfies the guard, decodes exactly as before, and leaves no reviewer-visible artifact. Two more:
`subprocess.Popen(...).communicate()` is not `run` — and there is already one legitimate `Popen` in
the directory (`check_mutation.py:146`, `start_new_session=True` for group-kill) that the 5-name
allowlist does not cover — and `getattr(subprocess, "run")(...)` presents as neither a `Name` nor
an `Attribute` to an AST check. The second draft's answer — key on the IMPORT of `subprocess` — is too blunt: **40 of the 78 files
import `subprocess` today, and 13 will still need the NAME after migration** for `SubprocessError`,
`CalledProcessError`, `TimeoutExpired` and `DEVNULL`, so that guard needs a ~15-file allowlist and
becomes wallpaper (FIX DIRECTIVE 5). Key it instead on the **five call verbs** — `subprocess.run`,
`Popen`, `check_output`, `call`, `check_call` — plus a separate rule for `getattr(subprocess, …)`.
That drops the allowlist from a ~15-file name-based one to the DERIVED set of § Cobra — the 6
genuinely non-git invocations, the already-correct bytes-mode calls (including the
`check_script_headers.py:206` precedent this design generalises and the three in
`check_secrets.py`), the returncode-only calls, the one `Popen` and the module's own — which is
small enough to read. And the guard
must permit all FOUR decoder functions, not the two the second draft named.

## Validation

The fleet test the reporter asked for, and this spec's acceptance criterion: **drive every check in
`scripts/enforcement/` against one fixture repo** containing (a) a NUL-free non-UTF-8 tracked file,
(b) a `*.bin diff` attributes line over a NUL-bearing blob, (c) a path with a raw non-UTF-8 byte,
(d) a path with a tab, a backslash and a `"`, and (e) a commit whose message is not valid UTF-8 —
and assert **none raises**, and that each still reports what it reported on the same repo without
those files. The second half is the one that matters: a check that stops raising by scanning
nothing has not been fixed. Run it with `stdin` closed AND as a live pipe.

⚠️ **Two ingredients the first draft's fixture omitted, without which it cannot catch the
regressions § The `-z` trap executed:** (f) a RENAME (the porcelain / name-status / numstat record
shape only diverges on one) and (g) a range of at least TWO commits (`check_plan_tickets`'s parser
only runs over one).

⚠️ **And the builder-must-invent gap, named so it is scheduled rather than discovered.** "Drive
every check against one fixture repo" is not a cwd exercise: **14 of the 78 scripts resolve their
root from `Path(__file__).resolve().parents[2]`** — the SCRIPT's location, not the cwd — including
`check_convergence`, `check_plan_tickets`, `check_subagent_flywheel` and `check_lint_ratchet`, four
of the critical set; a further 31 use `Path.cwd()`. So the harness either materialises
`scripts/enforcement/` inside the fixture repo or drives two invocation conventions. Second, there
is **no common verdict schema** across the 78 — some print free text, some print `OK`/`WARN`, some
only set an exit code — so "reports what it reported" must be defined as *(exit code, full stdout)*
equality per script, because exit code alone is blind to a silently reduced finding count, which is
the very class this exists to catch.

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
| The 13 MIXED-RECORD sites + the 34 that read `.returncode` + the 8 that pass `check=True` (union **50**, five sites in two of the three) | **Behaviour change, not refactor** — the record shape and the exit-code contract both move (§ The `-z` trap, § Approaches C) | One red-first test each, Bugfix-shaped per `45-testing-strategy.md:32`'s own table |
| The genuine remainder | Refactor | Zero new tests — but only where an existing test covers the file; the 7 untested files get one characterisation test first |

This is still C3's *"lean-but-complete, NOT 100%-line-coverage dogma"* — it is not 85 unit tests. It
is 50 behaviour tests plus one directory-wide fixture, which is what the evidence supports.

## Cost

⚠️ **`Profile: standard`, re-ruled — the first draft said `small` on the premise that the migration
was mechanical, and § The `-z` trap disproved that premise by execution.** Two code files
(`scripts/enforcement/git_output.py` NEW, plus the cobra check), a test file, and a migration of 85
sites across 35 files of which **13 are parser rewrites and 42 carry an exit-code contract** (34 reading `.returncode` + the 8 passing `check=True`, disjoint sets) — a UNION of **50** sites owing a behaviour test, not 55: five are counted twice (`check_plan_tickets.py:1063`, `check_review_coverage.py:103` and `check_review_hygiene.py:908` are MIXED *and* `check=True`; `check_corpus_weight.py:209` and `check_phase_tests.py:134` are MIXED *and* `.returncode`) — 50
reviewed edits, not 85 mechanical ones. The decoder, the cobra check and those 46 are all reviewed
surface. Everything here is a governance-sync path, so the build owes the full `/fabrik-review` and
one forced sync, and the staging in § Sequencing is what keeps any single review round tractable.
