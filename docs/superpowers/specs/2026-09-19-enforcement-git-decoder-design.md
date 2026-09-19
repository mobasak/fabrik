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
| C2 | *"`logging.getLogger(__name__)` / `print()`"* → *"`structlog.get_logger()` imported from scaffold `logger.py`"* | `.windsurf/rules/core/10-python.md:316` (BAN table) | SCOPED OUT, stated: these are CLI gates whose stdout IS their contract — `final_gate.run_optional_check` reads it. 12-Factor XI (*"unbuffered stdout only"*) governs instead. The decoder must not introduce a logger |
| C3 | *"**Behavior Contract**: every ticket enumerates its distinct user-observable behaviors … one high-value integration/E2E test per behavior, risk-ordered … **lean-but-complete, NOT 100%-line-coverage dogma**"* | `.windsurf/rules/core/45-testing-strategy.md:19` | The migration's behaviours are the decode classes, not the 85 edits — one test per class, not per call site |
| C4 | *"**Watched-fail-first** … a non-trivial behavior's test proves something only if it has been SEEN RED"* | `.windsurf/rules/core/45-testing-strategy.md:21` | Every decoder behaviour ships red-first; the migration's per-site edits do not (C5) |
| C5 | *"**Refactor** \| Zero new tests. Existing integration/E2E tests must pass."* | `.windsurf/rules/core/45-testing-strategy.md:32` | ⚠️ The tension this spec must rule on: the 85 edits ARE a refactor (C5 says zero new tests) but the decoder underneath them is a BEHAVIOUR change (C3/C4 say red-first). Ruled in § Testing |
| C6 | *"`datetime.utcnow()`"* → *"`datetime.now(UTC)` — deprecated and naive"* | `.windsurf/rules/core/10-python.md:316` | No datetime surface here; recorded as read, `unconstrained` |

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
git returns bytes that are not valid UTF-8. That is neither `CalledProcessError` nor
`FileNotFoundError`, so the fail-open arms these scripts share do not catch it and the whole check
dies. Measured impact when it fired: the entire "Secrets (Zero Hardcoding)" leg of `final_gate`
returned a traceback in the reporting repo.

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
| METADATA | 12 | `rev-parse`, `--numstat`, version strings — ASCII-guaranteed |
| NOT GIT | 5 | jscpd, ruff JSON, mutmut, a `review_rubric.py` subprocess — excluded (I8) |

## Approaches

**A — per-call `errors=` on 85 sites.** Smallest diff per edit, no new import surface, no module to
sync. Rejected: it is 85 independent chances to pick the wrong codec, and the codec choice is
exactly what is hard — `errors="replace"` on a PATH is silently destructive (see C-row FB2 below),
and nothing would stop the next script repeating it.

**B — one `run_git()` returning bytes, decode at the call site.** Honest about what git returns and
leaves the codec to whoever knows the context. Rejected as the primary: it preserves the decision
at every call site, which is the defect, and it makes the migration 85 *judgement* edits rather
than 85 mechanical ones.

**C — two named functions that encode the decision — RECOMMENDED.** `git_text(args)` for content
(decodes `errors="replace"`) and `git_paths(args)` for path lists (forces `-z`, decodes
`errors="surrogateescape"`, splits on NUL). The call site picks a FUNCTION, not a codec, so the
wrong choice is a visibly wrong verb rather than an invisible kwarg. This is the shape
`check_script_headers.py:206` already arrived at independently after paying for the alternative.

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
3. **A named error type, raised on both non-execution and a failing exit.** `GitUnavailableError`
   already exists in the precedent; the decoder exports it so every consumer can choose LOUD over
   silently-clean, which D-308 makes mandatory for any gate whose absence of output reads as a pass.

### Where it lives — and the MIRROR

A new `scripts/enforcement/git_output.py`, synced with the directory. **MIRROR, stated because it
is the change's real cost: 35 fleet-synced scripts gain an import they did not have.** Two
consequences the build must handle, not discover: a project copy that is stale by one sync would
import a module its siblings expect (the sync writes the whole directory in one pass, so the window
is the pass itself); and `scripts/enforcement/` is on `sys.path` for these scripts by construction,
so the import is a plain `from git_output import git_text` with no package context — the same shape
`check_secrets.py` already uses for `validate_conventions`.

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

- **Stage 1 (the live class): the 17 CONTENT sites.** Acceptance: a fixture repo carrying a
  NUL-free non-UTF-8 tracked file AND a `*.bin diff` attributes line; every one of the 17 checks
  runs against it without raising.
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
harder to satisfy dishonestly, because the dishonest path is now "add yourself to a named
allowlist", which a reviewer sees.

## Validation

The fleet test the reporter asked for, and this spec's acceptance criterion: **drive every check in
`scripts/enforcement/` against one fixture repo** containing (a) a NUL-free non-UTF-8 tracked file,
(b) a `*.bin diff` attributes line over a NUL-bearing blob, (c) a path with a raw non-UTF-8 byte,
(d) a path with a tab, a backslash and a `"`, and (e) a commit whose message is not valid UTF-8 —
and assert **none raises**, and that each still reports what it reported on the same repo without
those files. The second half is the one that matters: a check that stops raising by scanning
nothing has not been fixed. Run it with `stdin` closed AND as a live pipe.

## Out of scope

- The 5 NOT-GIT sites (I8) — jscpd, ruff JSON, mutmut, `review_rubric.py`. They decode third-party
  tool output, not git, and forcing git semantics on them would be a false uniformity. They get
  their own ruling when someone measures their inputs.
- `check_secrets.py` itself — shipped, reviewed and synced at `e33dcdd63`; it is the worked example.
- The ~46 project repos' own scripts outside `scripts/enforcement/`.

## Corrections this spec owes

`check_secrets.py`'s comment at `e33dcdd63` says a path is quoted *"On git's DEFAULT config"*,
which reads as though `core.quotePath=false` avoids it. Executed here: with that config a tab, a
backslash and a `"` are still quoted; `-z` is what disables quoting. The shipped CODE is correct
(it uses `-z`); only the explanation is incomplete. The migration touches that file anyway, so the
comment is corrected there rather than in a separate change.

## Testing — ruling on the C3/C4-vs-C5 tension

C5 says a refactor owes zero new tests; C3/C4 say a behaviour change owes one red-first test per
behaviour. Both apply to different halves. Ruling: **the decoder is the behaviour change and owes
red-first tests per decode class** (content raise, path raise, path collision via newline
translation, lossless round-trip, unavailable-git, failing-git); **the 85 call-site edits are the
refactor and owe zero new tests** — they are covered by the existing suites plus the § Validation
fixture, which is one integration test over the whole directory rather than 85 unit tests. This is
C3's *"lean-but-complete, NOT 100%-line-coverage dogma"* applied honestly.

## Cost

`Profile: small`. Two code files (`scripts/enforcement/git_output.py` NEW, plus the cobra check),
one test file, and a mechanical migration of 85 sites across 35 files. The migration is the bulk by
line count and the least by risk; the decoder and the cobra check are the reviewed surface. Both
are governance-sync paths, so the build owes the full `/fabrik-review` and one forced sync.
