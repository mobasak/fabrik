# Review — ticket-handling code after the VPS chat

Surface: 3dfd3e702643f3312a9565c8e42a8806214a5096 + diff-md5 66f886f66d660a70fbf738ef45103c61

**Scope (two committed changes):**
- **3dfd3e70** — `scripts/enforcement/check_subagent_flywheel.py::_warn_unrecorded`: `has_dsn` now spans all
  three `load_env` layers (process env → repo `.env` → fleet-wide `~/.config/fabrik/subagents.env`, resolved
  by an inlined mirror of `_dotenv._shared_env_path`); `tests/test_check_subagent_flywheel.py` new
  `test_shared_fallback_dsn_suppresses_unrecordable` + hermeticity guard on the absent-DSN test.
- **b151bd7d** — `src/fabrik/scaffold.py::create_project`: `specs_dir` made base-relative (real `/opt` → hub
  `FABRIK_ROOT/specs/services`; any other base → `<base>/specs/services`); `tests/test_scaffold_logging.py`
  regression test.

**HUB review — governance-synced blast radius:** `check_subagent_flywheel.py` distributes to every project;
correctness for ALL ~46 projects is the bar.

Reviewers: pool `fanout("review", mode=read_only")` (flywheel-scored) + native `fabrik-reviewer` Opus
(authoritative) + orchestrator Opus (refute/merge/decide).

## Coverage Checklist
| # | Class | Verdict |
|---|---|---|
| 1 | fail-open vs fail-closed on the advisory guard (unreadable file → True) | REFUTED(1) — intentional fail-soft PRESERVED from the pre-fix code ("unreadable proves nothing"); the check is ADVISORY (never blocks), so not claiming false UNRECORDABLE on an unreadable file is correct. Grounded: pre-fix line had `except OSError: has_dsn = True`. |
| 2 | boundary/sentinel/prefix (`startswith`, BOM lstrip, empty value after split) | REFUTED(1) — `SUBAGENT_RUNS_DSN=` / `= ` → `.split("=",1)[1].strip()` empty → correctly NOT a DSN (matches runtime `_apply_env_file`: empty value is falsy → not set). BOM lstrip preserved. `SUBAGENT_RUNS_DSN_OTHER=` fails startswith (correct). |
| 3 | inlined resolver fidelity vs `_dotenv._shared_env_path` | REFUTED(2) — grounded: empty `SUBAGENTS_ENV_FILE` → `if override:` False → falls through (matches runtime `if override:`); empty `XDG_CONFIG_HOME` → `... or ...` falsy → `~/.config` (matches runtime `if not xdg:`); HOME-unset KeyError/RuntimeError caught in both. Byte-equivalent resolution. |
| 4 | precedence/layer parity vs `load_env` (process → repo .env → shared) | REFUTED(1) — OR-chain order matches load_env precedence. The `.env`-walk-up (load_env's `_find_dotenv` walks parents) is NOT mirrored, but that is PRE-EXISTING (pre-fix used `PROJECT_ROOT/.env` too) and irrelevant: `PROJECT_ROOT=parents[2]` IS the repo root where `.env` lives. |
| 5 | behavior-without-a-test | CLEAN — new `test_shared_fallback_dsn_suppresses_unrecordable` proven red-on-revert (neuter shared layer → UNRECORDABLE fires → fail); absent-DSN test made hermetic vs the real `~/.config` via `SUBAGENTS_ENV_FILE` → nonexistent. 26/26 pass. |
| 6 | cost/quota/limit edges | CLEAN — no cost/limit accounting in either diff. |
| 7 | scaffold base-keying + never write outside tree + `relative_to` guard | REFUTED(4) — grounded: `Path("/opt/")==Path("/opt")` is True (pathlib normalizes → trailing-slash non-bug); all real callers (cli.py:1791, infrastructure.py:798) use the default `base=Path("/opt")`, tests use absolute tmp → subdir/symlink/relative-`.` bases are non-scenarios. `relative_to` ValueError guard returns the absolute path for a non-hub base (log-only, correct). |
| 8 | governance-sync fleet-correctness | CLEAN — the fix REMOVES a false-positive (advisory fired at every fallback-provisioned project); no project loses a true advisory (a genuinely DSN-less repo — no process env, no `.env`, no shared file — still gets it). Strictly less crying-wolf, fleet-wide. |
| 9 | 12-Factor III (config/env layering) | CLEAN — reads env layers, injects nothing; no secret/grouped-config introduced. |
| 10 | cross-file contract break (inlined resolver drifts from `_dotenv`) | REFUTED — inlined with a comment naming the source; the resolution is byte-equivalent (class 3). Drift risk is a doc-linked comment, not a runtime break. |

*(All Pass-1 verdicts are the pool layer + orchestrator grounding; the native Opus authoritative finder is folded in at Pass 2 before exit.)*

## Pass Ledger
| Pass | finders | found | new | fixed |
|-----:|---|---:|---:|---:|
| 1 | pool `fanout("review")` ×3 (deepseek-v3.2, gemini-3-flash, qwen3-max) + orchestrator-Opus grounding | 5 | 5 | 0 |
