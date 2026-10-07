# Plan — make check_doc_sprawl non-vacuous (the independent half)

Status: EXECUTED 2026-08-14 (8/8 tests, fleet 2272→22, gate green)
Prior: CONVERGED (2026-08-14 — 2-pass review: pass 1 corrected the non-activation mechanism
(`advisory=True` only preserves stdout, `final_gate.py:170` — it cannot downgrade a non-zero
exit; replaced with a `--warn`/`--strict` exit policy in the script) and dropped final_gate from
File Scope; closing pass edit-free, md5 verified)
Date: 2026-08-14
Owner: infra (spec-fed: docs/superpowers/specs/2026-08-14-doc-sprawl-activation-design.md, CONVERGED 43e76553)
Shape: monolith, single phase (~1 file + tests; the orphan disposition is NOT in scope)

## What we already agreed (spec-inherited)

- The check is inert in BOTH paths: no `__main__` (so `final_gate.py:1064`'s
  `run_optional_check` always exits 0) and `check_file()` dies on
  `file_path.relative_to(repo_root)` when handed a RELATIVE path (`:256-259` returns `[]`).
- It has no vendor guard: `rnfinal`'s 2230 hits are `node_modules/**/*.md`.
- **NOT in scope (blocking decision, mailed to intel 01M00W8WWX):** the disposition of the
  orphaned bulk copies (`ai_agent_prompt_directives.md`, `AI_TAXONOMY.md`). This plan does NOT
  activate the check fleet-wide; it makes the mechanism real and correct so activation is a
  one-line follow-up once that decision lands.
- fabrik-lib's corollary, adopted: a check wired BLOCKING must have a non-zero exit path.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `scripts/enforcement/check_doc_sprawl.py` | the whole surface: allowlists `:31-64`, patterns `:66-110`, `get_repo_root` `:114`, `is_tracked` `:128`, `path_is_existing` `:144-198` (HEAD + staged-rename semantics, archive-prefix smuggle guard), `check_file` `:245-267`, KNOWN-INERT comment `:56-64` | read in full this session |
| `scripts/final_gate.py:1062-1066` | invokes it via `run_optional_check(script_path, "Documentation Sprawl")` → `python <script>`; a missing `__main__` therefore reads GREEN | read this session |
| `scripts/enforcement/validate_conventions.py:117-119` | imports `check_file` and calls it per file — the caller passes a path whose relativity decides whether the ValueError fires | read this session |
| existing tests | `tests/` has no doc-sprawl suite (grep: none) — this plan adds the first | ls this session |
| `.windsurf/rules` core/10-python | stdlib-only, fail-soft outside a repo (the check already does this in `path_is_existing`'s except) | ACTIVE set |
| SYNC-CONSCIOUSNESS | `scripts/enforcement/**` is a governance-sync TRIGGER surface — this commit distributes to ~46 projects. Behavior must be correct for ALL of them: the change makes the check WORK, so it must not newly RED anyone → **activation stays gated** (see § Non-activation guard) | `.pre-commit-config.yaml` governance-sync filter |

## Design (settled)

1. **`__main__` (repo-scan mode)** — walk the repo's untracked+unignored `.md` files
   (`git ls-files --others --exclude-standard '*.md'`), apply the existing allowlist logic, print
   one line per violation with its `get_suggestion()` hint, exit 1 if any. Exit 0 with a count
   line otherwise. Outside a git repo: print a skip line, exit 0 (fail-soft, per pack).
2. **`relative_to` fix** — `check_file` accepts BOTH absolute and repo-relative paths: resolve
   against `repo_root` first (`(repo_root / file_path).resolve()` when not absolute), then
   relativize. The current `except ValueError: return []` stays as the last-resort guard for a
   path genuinely outside the repo.
3. **Vendor guard** — a shared `_is_vendor(path_str)` skipping `node_modules/`, `vendor/`,
   `.venv/`, `venv/`, `site-packages/`, `dist/`, `build/`, `.tox/`, `.next/` at ANY depth,
   applied in BOTH `check_file` and the new `__main__` scan. A default-deny doc policy must never
   adjudicate third-party files.
4. **Non-activation guard (deliberate).** ⚠️ Grounded correction at review time:
   `run_optional_check`'s `advisory=True` only PRESERVES stdout on success (`final_gate.py:170`);
   it does NOT downgrade a non-zero exit — a failing check still fails the gate. So the guard
   cannot be a kwarg. Instead the new `__main__` takes the exit policy itself:
   **`--warn` (default in the final_gate call site) prints violations and exits 0**;
   **`--strict` exits 1**. Activation = flipping the call site to `--strict`, a one-line,
   separately-reviewed change once the orphan disposition lands. The mechanism is real either
   way — `--strict` is exercised by the tests, so the exit path is proven non-vacuous today.

## Behavior Contract

- **Given** a repo with an untracked `.md` outside the allowlist, **When** the script runs with
  `--strict`, **Then** it exits 1 and names the file. (T1)
- **Given** only allowlisted new docs (dated plan, `docs/archive/`, root allowlist), **When** the
  script runs with `--strict`, **Then** it exits 0. (T2)
- **Given** a violating doc addressed by a repo-RELATIVE path, **When** `check_file()` is called,
  **Then** it returns the same finding as for the absolute path. (T3)
- **Given** a doc committed in HEAD that the allowlist would deny, **When** either entry point
  runs, **Then** it stays green (grandfathering preserved). (T4)
- **Given** a `.md` inside `node_modules/`, **When** either entry point runs, **Then** it is
  ignored, while the same filename outside a vendor tree is blocked. (T5)
- **Given** a directory that is not a git repo, **When** the script runs, **Then** it reports a
  skip and exits 0 without adjudicating anything. (T6)
- **Given** an identical violating repo state, **When** the script runs with `--strict` versus
  the default, **Then** it exits 1 versus 0 and reports the violation either way. (T7)
- **Given** the shipped `final_gate.py`, **When** its `check_doc_sprawl` call site is inspected,
  **Then** it carries no `--strict` (activation cannot slip in silently). (T7b)

## Phase A — implement + prove (single phase)

1. **Red-first tests** (`tests/test_check_doc_sprawl.py`, first suite for this check; each
   watched RED):
   - T1 `__main__` exits 1 and names the file when an untracked non-allowlisted `.md` exists
     (tmp git repo fixture).
   - T2 `__main__` exits 0 when the only untracked `.md` files are allowlisted
     (`docs/development/plans/2026-08-14-plan-x.md`, `docs/archive/foo.md`).
   - T3 `check_file` returns a finding for a REPO-RELATIVE path (the ValueError class) and the
     same for the absolute path — both must agree.
   - T4 tracked/HEAD-present docs stay green through both entry points (grandfathering).
   - T5 vendor guard: `node_modules/pkg/README.md` ignored by both paths; the identical filename
     outside `node_modules/` is blocked.
   - T6 outside a git repo: `__main__` exits 0 with a skip line (fail-soft).
   - T7 `--strict` exits 1 on a violation while the default `--warn` exits 0 on the SAME repo
     state (the exit-policy split), and `final_gate`'s call site passes no `--strict` (asserted
     on the source, so the non-activation guard cannot be silently lost).
2. **Implement** the four design items.
3. **Fleet re-measure** with the working check: run the repo scan across all `/opt` repos and
   record the post-fix number in Evidence (expect the two orphan classes to remain, everything
   else to clear — proving the vendor guard's effect).
4. **Docs**: `docs/workstation/` needs no new doc (the check is documented in-place); update the
   KNOWN-INERT comment to describe the NEW state (working, advisory pending disposition);
   CHANGELOG entry.
5. **/fabrik-review** to a quiet close; FULL gate; commit (explicit pathspecs + trailers); push.

Gates: `pytest tests/test_check_doc_sprawl.py` green · `python scripts/final_gate.py --json`
success · the fleet re-measure recorded · the final_gate call site carries no `--strict`.

## Risks

- **Fleet-wide surface**: making an inert check work is behavior change for ~46 projects — hence
  the `--warn` default. Without it this plan would red 14 repos on files nobody has adjudicated.
- **`path_is_existing` semantics are subtle** (HEAD + staged-rename + archive-prefix smuggle
  guard, added by an earlier docs-truth plan). The tests must not weaken them: T4 pins
  grandfathering, and no existing logic is edited — only path normalization ahead of it.
- **`get_repo_root()` fallback to `Path.cwd()`** means a non-repo run relativizes against cwd;
  T6 pins the fail-soft exit rather than letting it adjudicate junk.

## File Scope

`docs/development/plans/2026-08-14-plan-1-doc-sprawl-non-vacuous.md` ·
`docs/development/reviews/2026-08-14-plan-1-doc-sprawl-non-vacuous-review.md` ·
`scripts/enforcement/check_doc_sprawl.py` (`scripts/final_gate.py` NOT touched — the
default `--warn` needs no call-site change) ·
`tests/test_check_doc_sprawl.py`.

## Evidence

Fleet re-measure with the working check (`--strict` across all /opt git repos, this run):

```
$ for d in /opt/*/; do (cd "$d" && python3 scripts/enforcement/check_doc_sprawl.py --strict | grep -c BLOCKED:); done | paste -sd+ | bc
22          # was 2272 before the fix — rnfinal alone 2230 -> 1 (vendor guard)
```

Remaining 22 = the two orphaned bulk copies awaiting intel's disposition (mail 01M00W8WWX) plus
~3 genuine unfiled docs in rn-kit-sandbox. `pytest tests/test_check_doc_sprawl.py` → 8 passed,
every behavior watched RED first. `final_gate.py --check --json` → status success, 0 failed.

## Self-audit

- The blocking decision (orphan disposition) is explicitly OUT of scope and cannot stall this
  run; the `--warn` default is what makes that separation safe rather than theoretical.
- No existing allowlist/pattern/`path_is_existing` semantics change — this plan only makes the
  existing rule reachable and stops it adjudicating vendor trees.
