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
**60 / 25 across 13 files**. The table below is a FLOOR and it errs in the direction that makes
the silent class look smaller than it is.

| Outcome | Sites | Files | What the operator sees |
|---|---|---|---|
| **CRASH** — nothing catches it | **65** of 85 | — | The check dies with a traceback; `final_gate` reports a failure. LOUD, and self-announcing |
| **SILENT DEGRADE** — a broad `except` swallows it | **20** of 85 | 11 | The helper returns `None`/`[]` and the check goes LENIENT. No traceback, no warning, a green gate |

The 11: `check_convergence`, `check_doc_sprawl`, `check_doc_sync`, `check_plan_tickets`,
`check_plans`, `check_routing_policy`, `check_rule_grounding`, `check_stage_artifacts`,
`check_structure`, `check_subagent_flywheel`, `check_ticket_breadth`.

The worked example is `check_subagent_flywheel.py:104` — `except Exception: return None` — whose
caller at `:231` reads that `None` as *"couldn't read the commits (git failure) → fail-safe, don't
block"*. A non-UTF-8 commit message therefore does not crash that gate; it makes it **stop
blocking**, exactly the shape D-308 ruled against ("I could not look" reading as "nothing to
find"). The reported incident was a CRASH, which is why it was reported at all; the 20 silent
sites are the ones nobody will ever file.

**This splits two design consequences the crash framing hides.** (a) SEQUENCING: the silent 20
outrank part of the crash 65, because a crash is self-reporting and a lenient gate is not.
(b) VALIDATION: "assert none raises" would PASS on all 20 while they are still broken — which is
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
| CONTENT / commit message | 17 | The live crash class — `git diff` without `--name-only`, `git show <rev>:<path>`, `git log --format=%B` |
| PATH-ONLY | 51 | Not safe, differently triggered (trigger 3). Two of them FORCE `core.quotePath=false`, so they do not even depend on a user setting |
| MIXED RECORD | 13 | 8 × `status --porcelain`, `check_test_coverage.py:43`, `check_changelog.py:79` (⚠️ a `--numstat` line CONTAINS a path), `check_plan_tickets.py:1063`, plus two found late — `check_phase_tests.py:134` (`--name-status -z`, an alternating status/path parser) and `check_corpus_weight.py:209` (`ls-tree -r -l`, 4th field a size) |
| METADATA — ASCII-safe | 7 | `rev-parse --verify/--abbrev-ref`, `merge-base` |
| METADATA — PATH-BEARING | 5 | 4 × `rev-parse --show-toplevel` + `ls-tree -r -l` — ⚠️ NOT ASCII-guaranteed (executed); Stage 2, not Stage 3 |
| NOT GIT | 6 | jscpd, ruff JSON ×2, **`ruff --version`**, mutmut, a `review_rubric.py` subprocess (I8). The second draft said 5 and its table summed to 84 |

Corrected partition: **17 CONTENT + 44 PATH-ONLY + 13 MIXED + 7 META-safe + 5 META-path + 6 NOT-GIT
= 85.** § Sequencing's "12 METADATA sites" is superseded by 7 + 5.

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
| `git_paths(args)` | PURE path lists — `--name-only`, `ls-files` | `surrogateescape`, split NUL | **forced** |
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

**The contract, which the first draft never stated and a builder cannot invent:** all three return
`str` and RAISE `GitUnavailableError` when git cannot be run. They do NOT raise on a non-zero exit
— review found **35 of the 85 sites read `.returncode` within 12 lines of the call**, and at least
three use a non-zero exit AS THE ANSWER (`check_corpus_weight.py:184` falls through `origin/master`
→ `origin/main` on rc 1; `check_test_proposal.py:142` returns `None` on rc 128 in a commitless repo;
`check_mutation.py:59` on a repo with no remote). A raising-on-exit decoder would delete that
branch at 35 sites. So each function takes `check: bool = False` and exposes the exit code —
`git_text(args) -> str` raises only on `GitUnavailableError`, and `git_status(args) -> tuple[int, str]`
is the form the 35 use.

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
`-z` and leaves the caller's parser untouched. And the migration of those 11 is a REVIEWED parser
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
  is verified in all 50 on-disk copies before any call site moves. Acceptance:
  `ls /opt/*/scripts/enforcement/git_output.py | wc -l` = 50.
- **Stage 1 (the live class): the 17 CONTENT sites, silent-degrading ones FIRST.** Acceptance: a
  fixture repo carrying a NUL-free non-UTF-8 tracked file AND a `*.bin diff` attributes line;
  every one of the 17 checks runs against it without raising AND — for any of them among the 11
  silent-degrade files — still returns the same verdict it returns on the same repo without those
  files. A silent site that stops raising has not been fixed; it was never raising.
- **Stage 2: the 51 PATH-ONLY sites.** Acceptance: the same fixture repo gains a path with a raw
  non-UTF-8 byte, a tab, a backslash and a `"`; every check runs without raising AND without
  silently dropping a file (the count it reports must not fall).
- **Stage 3: the 12 METADATA sites.** Migrated for uniformity, not safety — a reviewer must be able
  to read "no `text=True` in this directory" as an invariant rather than checking 87 call sites.
  Acceptance: the cobra check (below) passes with zero exemptions.

## Cobra (D-253 — required, and its own bypass written down)

The guard: an enforcement check refusing any `subprocess.run(…, text=True)` under
`scripts/enforcement/` that carries no `errors=`. **The cheapest way to satisfy it WITHOUT the
outcome is to paste `errors="replace"` onto a PATH decode** — which passes the check and
reintroduces exactly the FB2 corruption the precedent already paid for. So the check must key on
the FUNCTION, not the kwarg: any `subprocess.run` under `scripts/enforcement/` that is not
`git_text`/`git_paths` is the finding, with an explicit allowlist for the 5 NOT-GIT sites. That is
harder to satisfy dishonestly than a kwarg check — but review found the ACTUAL cheapest bypass,
and it is not allowlisting. **The guard is PATH-SCOPED, so moving the call one directory up defeats
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
That drops the allowlist to the **4 files** holding the 6 genuinely non-git invocations, which is
small enough to read. And the guard must permit all FOUR decoder functions, not the two the second
draft named.

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

- The 5 NOT-GIT sites (I8) — jscpd, ruff JSON, mutmut, `review_rubric.py`. They decode third-party
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
| The 11 MIXED-RECORD sites + the 35 that read `.returncode` | **Behaviour change, not refactor** — the record shape and the exit-code contract both move (§ The `-z` trap, § Approaches C) | One red-first test each, Bugfix-shaped per `45-testing-strategy.md:32`'s own table |
| The genuine remainder | Refactor | Zero new tests — but only where an existing test covers the file; the 7 untested files get one characterisation test first |

This is still C3's *"lean-but-complete, NOT 100%-line-coverage dogma"* — it is not 85 unit tests. It
is ~46 behaviour tests plus one directory-wide fixture, which is what the evidence supports.

## Cost

⚠️ **`Profile: standard`, re-ruled — the first draft said `small` on the premise that the migration
was mechanical, and § The `-z` trap disproved that premise by execution.** Two code files
(`scripts/enforcement/git_output.py` NEW, plus the cobra check), a test file, and a migration of 85
sites across 35 files of which **11 are parser rewrites and 35 carry an exit-code contract** — ~46
reviewed edits, not 85 mechanical ones. The decoder, the cobra check and those 46 are all reviewed
surface. Everything here is a governance-sync path, so the build owes the full `/fabrik-review` and
one forced sync, and the staging in § Sequencing is what keeps any single review round tractable.
