#!/usr/bin/env python3
"""Claude Code SessionStart + Stop hooks — enforce final_gate as the definition of done.

ONE script, two modes:
  --baseline  (SessionStart): snapshot the set of FAILING gate checks the session
              INHERITED. Never blocks. This is what stops the hook from trapping the
              agent on a project's pre-existing debt.
  (default)   (Stop): re-run the gate and BLOCK end-of-turn only when the session has
              introduced NEW failing checks (current failures − baseline) AND the
              worktree is dirty. So the agent is blocked only for problems IT caused.

Safety:
- **Fail-open**: any internal error, an un-runnable/unparseable gate, or a missing
  baseline → allow the stop (a hook must never trap the session, and inherited debt
  must never be attributed to the agent).
- **Loop cap**: after CAP consecutive blocked stops it allows the stop with a loud
  warning (Claude Code exposes no stop_hook_active flag, verified against the docs).
- **Scoped**: clean worktree / non-fabrik project → instant pass.

Contract (verified against https://code.claude.com/docs/en/hooks, 2026-06):
- stdin JSON: session_id, cwd, hook_event_name, ...
- block: print {"decision":"block","reason":...} on stdout, exit 0.
- allow: exit 0 with no decision.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CAP = 3  # consecutive blocked stops before letting it stop anyway (anti-trap)

# --- Kaizen M1 event stream (additive sensor, fail-open at the IMPORT layer) ---
# The emitter lives at ONE place per box, so both candidates are tried: this repo's own
# copy first, then the hub's. The degraded state is the module being unimportable at
# BOTH — a box that has no kaizen_events at all — and there this hook must behave
# EXACTLY as it did before the sensor existed, on stdout AND stderr. Hence the guarded
# import (never an ImportError that would degrade all five enforcement causes — the
# same reasoning the FIFTH-cause comment gives for not importing command_run.py) and a
# second guard at every emit site. Paths are APPENDED (stdlib always wins) and only when
# absent (idempotent).
kaizen_events = None
try:
    for _p in (
        str(Path(__file__).resolve().parents[2] / "scripts" / "sysadmin"),
        "/opt/fabrik/scripts/sysadmin",
    ):
        if _p not in sys.path:
            sys.path.append(_p)
    import kaizen_events  # type: ignore[no-redef]
except Exception:
    kaizen_events = None

# The Stop hook sits on the interactive hot path. A hung git probe must cost the turn
# milliseconds, not the hook's 120s budget.
_PROBE_TIMEOUT_S = 2.0

_kaizen_probe_cwd: str | None = None
_kaizen_exposure: dict | None = None
_kaizen_exposure_ready = False


@contextlib.contextmanager
def _quiet():
    """Mute stderr for the duration — hook-side, so `kaizen_events` keeps its own
    honest `_warn` channel for every OTHER caller. This hook's stderr carries the
    warn-through notices the agent is meant to read; the sensor must not add a byte."""
    try:
        devnull = open(os.devnull, "w")  # noqa: SIM115 - closed in the finally below
    except OSError:  # pragma: no cover - /dev/null is always there
        yield
        return
    try:
        with contextlib.redirect_stderr(devnull):
            yield
    finally:
        devnull.close()


def _kaizen_bind(cwd: str) -> None:
    """Pin exposure to the PAYLOAD's project. A hook subprocess has no guarantee its own
    cwd is the session's repo, and an unpinned probe stamps project A's events with
    project B's commit — silently, and unfixably after the fact."""
    global _kaizen_probe_cwd
    _kaizen_probe_cwd = cwd


def _kaizen(event: str, sid: object, **fields: object) -> None:
    """Fire-and-forget event. Module absent or ANY failure → silent no-op.

    ``sid`` is the RAW payload id, never this hook's ``"nosession"`` fallback: that
    fallback is a SHARED name every id-less session would merge into, and the event
    stream's honesty rule is that an unattributable event goes to ``unknown`` (the
    collector's unclassified bucket) rather than into a neighbour's stream.

    Exposure is resolved at most ONCE per process, lazily on the first emit — a Stop
    that never emits pays nothing, and one that emits three times still probes once.
    """
    global _kaizen_exposure, _kaizen_exposure_ready
    if not kaizen_events:
        return
    try:
        with _quiet():
            if not _kaizen_exposure_ready:
                _kaizen_exposure_ready = True
                _kaizen_exposure = kaizen_events.exposure(
                    cwd=_kaizen_probe_cwd, probe_timeout_s=_PROBE_TIMEOUT_S
                )
            kaizen_events.emit(
                event,
                kaizen_events.resolve_sid(sid),
                exposure_override=_kaizen_exposure,
                **fields,
            )
    except Exception:
        pass


#: The mandated 7-line FINAL OUTPUT block, by its line-anchored keys. ALL seven must be
#: present: the conversational two-line ``STATE:``/``NEXT:`` footer shares one of them,
#: and counting that as a task terminator would inflate the completion metric with
#: every chat turn. ``FEEDBACK:`` joined 2026-09-01 (operator directive — the run-record
#: close verdict made chat-visible; prose alone produced zero visible reports six times).
_FINAL_BLOCK_KEYS = (
    "GATE:",
    "DOCS UPDATED:",
    "CHANGELOG:",
    "LESSONS LEARNT:",
    "DONE:",
    "NEXT:",
    "FEEDBACK:",
)


#: The block is "the LAST 7 lines" — the completeness check reads only this many trailing
#: lines (seven keys + a closing fence + blank lines), so a quoted example higher up is prose.
_FINAL_BLOCK_TAIL_LINES = 10  # 7 keys + a closing fence + 2 blank lines


def _final_block_seen(text: str) -> bool:
    return all(re.search(rf"^\s*{re.escape(k)}", text, re.M) for k in _FINAL_BLOCK_KEYS)


def decide(
    git_dirty: bool,
    has_new_failures: bool,
    gate_attempts: int,
    cap: int = CAP,
    own_uncommitted: bool = False,
    commit_attempts: int = 0,
) -> tuple[str, int, int]:
    """Pure decision logic (unit-tested). Returns (action, gate_attempts', commit_attempts').

    action ∈ {"allow", "block", "block_commit", "allow_warn_gate",
    "allow_warn_commit"} — the warn actions name their CAUSE so the caller's
    warning can be truthful (an unconditional "gate still RED" message was
    factually false on commit-cap exhaustion; review finding). Priority:
    1. new gate failures (dirty tree)  → "block"        (fix before anything)
    2. session-authored files uncommitted → "block_commit" (an uncommitted task
       is an UNFINISHED task — CLAUDE.md § EXIT)
    Each reason has its OWN anti-trap counter: exhausting the gate CAP must not
    starve the commit check (or vice versa) — with a shared counter, alternating
    causes walked straight past enforcement (review finding, 2026-08-07).
    """
    if not git_dirty:
        return "allow", 0, 0  # nothing changed → nothing to gate
    # A cause's counter RESETS the moment that cause stops being true — a stale
    # count must never carry into an unrelated future streak of the same cause
    # (review finding: a resolved gate streak's persisted 3 waved a brand-new
    # regression through on its FIRST stop). A still-true cause keeps its count
    # across interleaves (the streak genuinely continues).
    if not has_new_failures:
        gate_attempts = 0
    if not own_uncommitted:
        commit_attempts = 0
    if has_new_failures:
        gate_attempts += 1
        if gate_attempts > cap:
            return "allow_warn_gate", 0, commit_attempts
        return "block", gate_attempts, commit_attempts
    if own_uncommitted:
        commit_attempts += 1
        if commit_attempts > cap:
            return "allow_warn_commit", gate_attempts, 0
        return "block_commit", gate_attempts, commit_attempts
    return "allow", 0, 0  # green + own work committed (or none authored)


def _git_dirty(root: Path) -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    return bool(out.strip())


def _run_gate(root: Path) -> tuple[bool, set[str], dict[str, str]]:
    """Run final_gate --lean --check --json. Returns (passed, failing_check_names, outputs).

    outputs maps each failing check name to its output text — used by the Stop path to
    attribute a NEW failure to this session's files vs a sibling's shared-tree dirt.
    Per-check (not concatenated) so attribution can scope to the NEW failures only:
    an inherited baseline failure that happens to cite a session file must not
    contaminate the verdict on an unrelated new one.

    Fail-open: a gate that can't run or whose output can't be parsed as a definitive
    failure returns (True, empty, {}) — we never block on an indeterminate result.
    """
    venv_py = root / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    proc = subprocess.run(
        [py, "scripts/final_gate.py", "--lean", "--check", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=110,
    )
    if proc.returncode == 0:
        return True, set(), {}
    try:
        data = json.loads(proc.stdout)
        if data.get("status") == "failure":
            fails = data.get("failures", [])
            names = {f.get("check", "?") for f in fails}
            outputs = {f.get("check", "?"): str(f.get("output") or "") for f in fails}
            return False, names, outputs
    except Exception:
        pass
    # Non-zero but not a definitive parsed failure (crash, missing deps, etc.) →
    # fail-open: don't block on a gate we couldn't actually evaluate.
    return True, set(), {}


# Path-shaped tokens in a failure output: something with a slash, or a dotted
# filename. Attribution compares these as normalized relative paths — substring
# matching is banned ('app.py' must never match inside 'data_app.py').
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_\-./]*/[A-Za-z0-9_\-./]+|[A-Za-z0-9_\-]+\.[A-Za-z0-9_]{1,8}")

# Governance files EVERY session routinely writes (Completion Contract / Doc Sync
# Matrix obligations). A failing check that cites ONLY these plus sibling files is
# sibling-caused: the sibling's code change created the CHANGELOG/INDEX obligation,
# and the session's own routine edits to these files must not claim the failure.
_ROUTINE_GOVERNANCE = frozenset(
    {
        "CHANGELOG.md",
        "INDEX.md",
        "PORTS.md",
        "docs/README.md",
        "docs/LESSONS_LEARNT.md",
        # Added 2026-09-15: CLAUDE.md names FOUR shared-append files and two of them were absent
        # here, so the "never attribute on their own" rule had a hole exactly the size of the
        # decision ledger — which every session is required to write a row in, in the same change.
        # Measured over the last 200 commits of this repo: the five names already listed cover 91,
        # these two cover 54, the union is 109. The 109 was the number quoted when this exclusion
        # shipped, so the citation was for a population the code did not implement.
        # ⚠️ MIRROR, stated rather than absorbed: this constant is shared with
        # `_failure_cites_session`, so widening it also widens the GATE-attribution cause's
        # "never attribute on their own" rule. Correct there for the same reason — every session
        # writes these — but it is a second fleet-synced behaviour change, not a free one.
        "docs/DECISIONS.md",
        "docs/STRATEGIC_BACKLOG.md",
    }
)


def _failure_cites_session(
    new_outputs: list[str], authored: dict[str, int], session_floor: float
) -> bool | None:
    """Attribute NEW gate failures to this session by cited path, or None if indeterminate.

    Returns True (session-caused → block), False (sibling-caused → downgrade), or
    None (no path-shaped evidence in any new failure's output → cannot attribute →
    caller keeps the pre-attribution behavior, i.e. block up to the cap; the known
    shared-tree false-positive checks all cite paths, so indeterminate is rare).

    - Tokens are compared as normalized relative paths, never substrings: exact
      match, cited-path suffix (`/opt/x/src/a.py` vs authored `src/a.py`), or
      basename cite (`a.py` vs authored `src/a.py`).
    - authored entries older than session_floor (the SessionStart baseline mtime)
      are a resumed transcript's ancient edits, not this session's work (same
      false-positive class the own_uncommitted timestamp guard kills).
    - _ROUTINE_GOVERNANCE names never attribute on their own — every session
      writes them, and Doc Sync failures cite the obligation doc by name even
      when a SIBLING's code change created the obligation.
    """
    text = "\n".join(new_outputs)
    tokens = {t.strip("./,:;)(\"'") for t in _PATH_TOKEN.findall(text)}
    tokens = {t for t in tokens if t and ("." in t or "/" in t)}
    if not tokens:
        return None
    candidates = {
        rel
        for rel, ts in authored.items()
        if rel not in _ROUTINE_GOVERNANCE and (not ts or not session_floor or ts >= session_floor)
    }
    for t in tokens:
        for rel in candidates:
            if t == rel or t.endswith("/" + rel) or rel.endswith("/" + t):
                return True

    # No non-governance match. If the output cites ONLY routine-governance names and
    # the session authored one of them, the session may have broken that file ITSELF
    # (malformed CHANGELOG edit) — that is not attributable either way: indeterminate,
    # keep blocking up to the cap. The sibling-obligation incident is different: its
    # output also cites the sibling's trigger file, a non-governance token.
    # ⚠️ SUFFIX-TOLERANT, exactly like the match above it. `t not in _ROUTINE_GOVERNANCE` is an
    # EXACT comparison, so `/opt/fabrik/docs/DECISIONS.md` or a bare `DECISIONS.md` fell into
    # `non_gov`, read as sibling-caused, and WAIVED a failure the session itself had caused —
    # while the relative form `docs/DECISIONS.md` correctly stayed indeterminate and blocked.
    # Three spellings of one file, two different verdicts (executed, Phase F review round 3). The
    # hole opened when this constant was widened to include the ledger files, and it is the
    # fail-OPEN direction on a gate cause: the session exits with a red gate it caused.
    def _is_governance(token: str) -> bool:
        return any(
            token == g or token.endswith("/" + g) or g.endswith("/" + token)
            for g in _ROUTINE_GOVERNANCE
        )

    non_gov = {t for t in tokens if not _is_governance(t)}
    if not non_gov and any(
        _is_governance(t)
        and any(a == t or a.endswith("/" + t) or t.endswith("/" + a) for a in authored)
        for t in tokens
    ):
        return None
    return False


# Tools whose input.file_path marks a file THIS session authored/edited. Bash
# heredoc writes are invisible here — under-detection is the fail-open direction.
_EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


def _session_files(transcript_path: str, root: Path) -> dict[str, int]:
    """Root-relative path → unix ts of this session's LAST Edit/Write to it.

    Parsed from the session transcript (JSONL). Fail-open: any parse problem →
    empty dict (the commit check then never blocks). Only paths INSIDE root count
    (memory/config edits outside the repo are not repo work). Timestamps matter:
    a long-lived resumed session's transcript spans weeks — an edit that was
    COMMITTED long ago must not re-attach to today's unrelated dirt (live
    false-positive on first ship: a July edit + the daily pipeline's timestamp
    bump today flagged the file as this session's unfinished work)."""
    import datetime as _dt

    files: dict[str, int] = {}
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"tool_use"' not in line:
                    continue  # cheap pre-filter before json cost
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                ts = 0
                raw_ts = entry.get("timestamp")
                if isinstance(raw_ts, str):
                    try:
                        ts = int(
                            _dt.datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
                        )
                    except ValueError:
                        ts = 0
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "tool_use"
                        and item.get("name") in _EDIT_TOOLS
                    ):
                        fp = (item.get("input") or {}).get("file_path")
                        if not fp:
                            continue
                        try:
                            rel = Path(fp).resolve().relative_to(root)
                        except (ValueError, OSError):
                            continue  # outside the repo → not repo work
                        key = str(rel)
                        files[key] = max(files.get(key, 0), ts)
    except Exception:
        return {}
    return files


def _last_commit_ts(root: Path, rel: str) -> int:
    """Unix ts of the last commit touching ``rel`` (0 = never committed)."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", rel],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        return int(out) if out.isdigit() else 0
    except Exception:
        return 0


def _dirty_paths(root: Path) -> set[str]:
    """Root-relative paths with uncommitted changes (staged or not), rename-aware."""
    out = subprocess.run(
        ["git", "-c", "core.quotePath=false", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    paths: set[str] = set()
    for line in out.splitlines():
        body = line[3:]
        if " -> " in body:
            body = body.split(" -> ", 1)[1]
        paths.add(body.strip().strip('"'))
    return paths


def _safe_sid(sid: str) -> str:
    """A filename-safe session id that NEVER collides with a different raw id.

    Byte-identical to ``scripts/command_run.py::_safe_sid`` (which cannot be imported
    here — see the FIFTH-cause comment); the agreement is pinned by
    ``test_hook_and_script_agree_on_every_record_filename``. Flattening ALONE collided
    (`abc.xyz` and `abc xyz` → one file), so a short digest of the RAW id is appended
    whenever flattening changed anything. uuid-shaped ids pass through unchanged, so
    no live session's tmp files are renamed by this.
    """
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)
    if not safe:
        return "nosession"
    if safe != sid:
        safe += "-" + hashlib.blake2s(sid.encode("utf-8", "replace"), digest_size=4).hexdigest()
    return safe


# These interpolate the session id into a tmp path. Unsanitized, a `/`-containing sid
# escaped the tmp dir and the resulting OSError hit main()'s outermost except —
# failing the WHOLE hook open and silently disabling all five causes.
def _baseline_path(sid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"fabrik-gate-baseline-{_safe_sid(sid)}.json"


def _counter_path(sid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{_safe_sid(sid)}.attempts"


_COUNTER_SLOTS = 6


def _read_counters(counter: Path) -> tuple[int, int, int, int, int, int]:
    """(gate, commit, stall, push, run, review) attempts — tolerates older short files.

    Each cause owns its OWN slot: exhausting one cause's cap must never starve
    another's (the alternating-cause escape, 2026-08-07).
    """
    try:
        raw = counter.read_text().strip()
        parts = raw.split(",")
        vals = [int(p) for p in parts[:_COUNTER_SLOTS]]
        while len(vals) < _COUNTER_SLOTS:
            vals.append(0)
        return vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]
    except Exception:
        return 0, 0, 0, 0, 0, 0


# --- FIFTH cause: an in-flight COMMAND RUN RECORD ----------------------------
# `scripts/command_run.py` writes ONE json per session recording which /fabrik-*
# command is running, its phase c/t, its round count and its terminal condition.
# A record that positively says state:"running" means the agent is MID-COMMAND —
# stopping there is the "agents stop without reaching a no-op pass" defect.
#
# The resolver is duplicated here (≈10 lines) rather than imported from
# scripts/command_run.py ON PURPOSE: a hook must not acquire an import that can
# fail (missing file mid-sync, a project that never received the script, a
# syntax error in it) — an ImportError here would degrade EVERY cause, not just
# this one. The two copies share only an env var name and a filename convention.
_STALE_H_DEFAULT = 12.0
# Ordinary clock wobble on a live record. Same idiom (and value) as
# claude_rotate.py's `_CLOCK_SKEW_TOLERANCE_S` — a stamp further in the FUTURE than
# this is not evidence of freshness, it is a broken clock or a corrupted write.
_CLOCK_SKEW_TOLERANCE_S = 60.0


def _stale_bound_s() -> float | None:
    """The staleness bound in seconds, or None when the operator disabled the trap.

    `COMMAND_RUN_STALE_H=0` (or negative) means "don't trap me" — it must never mean
    "block forever", which is what a naive `if stale_h > 0` guard turned it into. A
    non-finite bound (`nan`, `inf`) is no bound at all: same verdict.
    """
    raw = os.environ.get("COMMAND_RUN_STALE_H")
    if raw is None or raw.strip() == "":
        return _STALE_H_DEFAULT * 3600
    try:
        hours = float(raw)
    except ValueError:
        return _STALE_H_DEFAULT * 3600  # garbage value → the default bound still applies
    if not math.isfinite(hours) or hours <= 0:
        return None
    return hours * 3600


def _run_record(sid: str) -> dict | None:
    """This session's command-run record, or None.

    FAIL OPEN, asymmetrically. Blocking an agent's stop is a strong act, so freshness
    must be POSITIVELY PROVEN — anything else returns None:

    - missing / corrupt / unreadable / not a dict
    - `updated_ts` absent, non-numeric, boolean, or non-finite (`json.loads` accepts
      bare `NaN` / `Infinity` literals, so those really do arrive here). The old
      `isinstance(ts, (int, float))` gate SKIPPED the check for these shapes, which
      meant each one blocked FOREVER, indistinguishable from a legitimate block.
    - older than the staleness bound (an abandoned record from a dead session)
    - further in the FUTURE than the clock-skew tolerance (unprovable, not fresh)
    - the operator disabled the bound (`COMMAND_RUN_STALE_H<=0`)

    Only state == "running" on a returned record ever blocks.
    """
    try:
        raw_dir = os.environ.get("COMMAND_RUN_DIR")
        base = Path(raw_dir) if raw_dir else Path.home() / ".claude" / "state" / "command-runs"
        rec = json.loads((base / f"{_safe_sid(sid)}.json").read_text(encoding="utf-8"))
        if not isinstance(rec, dict):
            return None
        bound_s = _stale_bound_s()
        if bound_s is None:
            return None
        ts = rec.get("updated_ts")
        if isinstance(ts, bool) or not isinstance(ts, (int, float)) or not math.isfinite(ts):
            return None  # freshness unprovable → never block on it
        age = time.time() - float(ts)
        if age > bound_s or age < -_CLOCK_SKEW_TOLERANCE_S:
            return None
        return rec
    except Exception:
        return None


def _run_record_raw(sid: str) -> dict | None:
    """The record as written, freshness-blind — `_review_windows` needs a CLOSED record however
    old it is (its close time IS the fact). Unreadable/absent → None (= no coverage)."""
    try:
        raw_dir = os.environ.get("COMMAND_RUN_DIR")
        base = Path(raw_dir) if raw_dir else Path.home() / ".claude" / "state" / "command-runs"
        rec = json.loads((base / f"{_safe_sid(sid)}.json").read_text(encoding="utf-8"))
        return rec if isinstance(rec, dict) else None
    except Exception:
        return None


def _run_block_reason(rec: dict, attempt: int) -> str:
    cmd = rec.get("command") or "?"
    cur, total = rec.get("phase") or 1, rec.get("phases") or "?"
    rounds = rec.get("rounds") or []
    title = (rec.get("phase_title") or "").strip()
    where = f"phase {cur}/{total}" + (f" ({title})" if title else "")
    if rounds:
        where += f", round {len(rounds)}"
    terminal = (rec.get("terminal") or "its own no-op / completion contract").strip()
    classes = rec.get("classes") or {}
    still_open = sorted(k for k, v in classes.items() if v != "clean")
    open_note = (
        f" Class ledger still OPEN: {', '.join(still_open)} — re-sweep them with the SAME "
        "brief (re-scoping each round is what turns a review into 30 rounds)."
        if still_open
        else ""
    )
    return (
        f"COMMAND STILL RUNNING (attempt {attempt}/{CAP}). /{cmd} is in flight at {where}; "
        f"its terminal condition is: {terminal}.{open_note} An invoked command is the "
        "deliverable — run it to that terminal condition, do not hand back control "
        "mid-command. There are exactly TWO legitimate exits, and BOTH must name this "
        f"run (--command {cmd}) — a mismatched name is refused rather than closing the "
        f"wrong record: python3 scripts/command_run.py done --command {cmd} --evidence "
        '"<proof the terminal condition is met>" --feedback "<what you filed, to whom | '
        'none — the surfaces this run exercised>" when the contract IS met, or '
        f"python3 scripts/command_run.py blocked --command {cmd} --reason "
        '"<one of the three sanctioned BLOCKED cases: 3 consecutive same-test '
        'failures | missing infra | an unresolvable spec contradiction>" '
        '--feedback "<what you filed, to whom | none — the surfaces this run exercised>". '
        "BOTH exits REQUIRE --feedback; the close is refused without it."
    )


def _named_files_phrase(files: list[str], shown: int = 3) -> str:
    """The "Named: a, b, c (+N more). " clause — the ONE implementation.

    ⚠️ This exists because the TEST had a MIRROR of it. A mirror is a second implementation by
    construction, and its pin was four substrings, so changing the real `", ".join` to `"; "` left
    both the mirror and its pin green while the rendered block changed (executed, Phase F review
    round 2). The answer to "how do I stop the copy drifting" is to not have a copy: the hook
    builds the clause here and the grader calls this.
    """
    if not files:
        return ""
    more = len(files) - shown
    tail = f" (+{more} more)" if more > 0 else ""
    return "Named: " + ", ".join(files[:shown]) + tail + ". "


def _edit_age_phrase() -> str:
    """The edit-age window in words, for the one message that discloses it.

    ⚠️ NOT `int(seconds // 3600)`. That renders `0h` for any sub-hour value and `1h` for 90
    minutes — and tuning this window downward is the obvious next move, so the lossy form would
    have started lying at exactly the moment someone changed it. Executed across 86400/5400/3599/
    1800 before this replaced it.
    """
    s = _SIXTH_CAUSE_MAX_EDIT_AGE_S
    if s >= 3600:
        # ⚠️ The hours branch cuts in at ONE HOUR, not at one minute. Round 2 wrote `if s >= 60`
        # and so rendered `within the last 0.0h` for 120s and `0.1h` for 180s — the very "0h"
        # this function's docstring was written to condemn, reproduced inside the replacement
        # (executed, Phase F review round 3). A rounded hour also UNDERSTATES: 3640s read as
        # "1.0h", so the exact form is used whenever the value is not a whole number of hours.
        return (
            f"within the last {int(s // 3600)}h"
            if s % 3600 == 0
            else f"within the last {s / 3600:.2f}h"
        )
    if s >= 60:
        return (
            f"within the last {int(s // 60)}m" if s % 60 == 0 else f"within the last {s / 60:.1f}m"
        )
    return f"within the last {int(s)}s"


def _commit_is_mine(touched: set[str], distinctive: set[str], authored: set[str]) -> bool:
    """Is this commit attributable to THIS session?

    Two ways, and the second exists because the first alone caused a regression. A commit that
    touches a file only this session edited is mine — that is the strong signal, and it is what
    keeps a sibling's task-end commit (their code PLUS the shared CHANGELOG entry) from being
    ordered published under my name.

    ⚠️ BUT a commit made ENTIRELY of shared-append files has no distinctive file to offer, and the
    first cut therefore discarded it — so a docs-only task end (CHANGELOG + INDEX and nothing
    else) left the push law SILENT on the session's own unpushed work. Executed: `ahead` returned
    `None` where the pre-fix code returned 1, and **11** of the last 200 commits here have exactly
    that shape — `touched <= _ROUTINE_GOVERNANCE` over the SEVEN names this constant now holds.
    (It was first written as 3, which is the count under the FIVE names the same commit replaced:
    the number was measured against a population the code no longer had, understating this
    clause's fire rate — and therefore the sibling residue it admits — by nearly 4x. Exactly the
    defect this round was fixing one function away.) Silence there breaks the `push-at-task-end` universal marker, which is the one thing
    this cause exists to enforce, so a governance-only commit counts when its files are ones this
    session touched.

    ⚠️ THE RESIDUE, stated rather than hidden: a SIBLING's governance-only commit whose files this
    session also touched is still attributed to us. That is a narrower version of the complaint
    01M20E1QN made — it can no longer happen for a commit carrying the sibling's own code, only
    for one that is pure governance — and the alternative is silence on our own task end. Between
    being told to push someone's already-committed docs and losing our own commit off-box, the
    contract is unambiguous about which is worse.
    """
    if touched & distinctive:
        return True
    return bool(touched) and touched <= _ROUTINE_GOVERNANCE and bool(touched & authored)


def _ahead_of_upstream(root: Path, authored: set[str] | None = None) -> int | None:
    """Commits on the current branch not on its upstream that THIS SESSION authored; None =
    indeterminate (no upstream / detached HEAD / any git error — indeterminate never blocks:
    throwaway repos and mid-plan worktree branches have no upstream by design).
    Purely local (`rev-list @{upstream}..HEAD`) — never touches the network, so an offline box
    counts correctly and pushes fail visibly later.

    ⚠️ SCOPED TO THIS SESSION'S OWN COMMITS (T13.4, 01M20E1QN). The count used to be every commit
    in the range, and the block's text says "push YOUR work" — so on a tree three sessions commit
    to, it ordered a SIBLING's commit published. Publishing someone else's unpushed commit is not
    a smaller mistake than leaving your own unpushed; it is the one the push law never asked for.

    A commit is this session's when it touches a file this session edited (`authored`, from the
    transcript). That signal UNDERCOUNTS — a commit whose files were all written by a tool the
    transcript did not record drops out — and undercounting is the correct direction here: this
    cause BLOCKS an exit, so its failure mode must be letting a stop through, never trapping a
    session behind someone else's work. With `authored` empty or None the count is indeterminate
    rather than "everything", for the same reason.
    """
    # ⚠️ SHARED-APPEND NAMES NEVER ATTRIBUTE ON THEIR OWN — the same rule `_failure_cites_session`
    # already applies, for the same reason: every session writes them. The first cut of this fix
    # matched on the raw authored set, so a sibling's task-end commit (their own file PLUS the
    # shared CHANGELOG entry) was attributed to any session that had touched `CHANGELOG.md` at any
    # point in its transcript — which on a multi-day resumed session is all of them. Executed: a
    # sibling commit of `['CHANGELOG.md', 'sibling_only.py']` against `authored={'CHANGELOG.md'}`
    # returned 1, i.e. exactly the pre-fix behaviour the change claimed to remove, and it refuted
    # this phase's own Behavior Contract. MEASURED on this repo: 109 of the last 200 commits touch
    # one of these names, so the hole was the common case, not a corner.
    # ⚠️ the None guard comes FIRST: `authored` is Optional and a set comprehension over None
    # raises TypeError out of a Stop hook, which takes all six causes dark for the turn. Caught by
    # `test_no_authored_set_is_indeterminate_never_everything` the minute it was introduced.
    if not authored:
        return None
    distinctive = {f for f in authored if f not in _ROUTINE_GOVERNANCE}
    try:
        # ONE subprocess for the whole range, not one per commit. The per-commit form cost ~3 ms
        # each (measured 207 commits -> 0.67 s) with a `timeout=15` PER COMMIT, so a git stalled on
        # `index.lock` — three sessions commit to this tree — gave a worst case of 15 s x N inside
        # a Stop hook. `--no-renames` because rename detection prints only the NEW path, so a
        # session that edited `a.py` and then `git mv`-ed it attributed nothing (executed).
        #
        # ⚠️ NUL-DELIMITED, because the first cut detected commit boundaries by sniffing "a line of
        # exactly 40 hex characters" — and a FILENAME can be 40 hex characters. Executed: one
        # commit containing `a.py`, `ffff…ffff` and `z.py` was counted as TWO, and the inflated
        # number reaches the agent verbatim in the block text. The same cut passed
        # `core.quotePath=false`, which governs only NON-ASCII escaping, so a path containing a
        # quote, newline, tab or backslash was still C-quoted and never matched — executed, a file
        # named `a"b.py` gave 0. `-z` emits every path raw and `%x00%H` delimits each commit with a
        # NUL, so both classes close on the delimiter git already provides instead of on a
        # heuristic. It also makes a sha256-object repo a non-question.
        r = subprocess.run(
            [
                "git",
                "log",
                "-z",
                "--no-renames",
                "--name-only",
                "--format=%x00%H",
                "@{upstream}..HEAD",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return None
        mine = 0
        touched: set[str] = set()
        expect_sha = True
        started = False
        for field in r.stdout.split("\0"):
            if not field:
                # the NUL that opens each commit: bank the previous one
                if started and _commit_is_mine(touched, distinctive, authored):
                    mine += 1
                touched = set()
                expect_sha = True
                continue
            if expect_sha:
                expect_sha = False
                started = True
                continue  # the sha itself is not a path
            path = field.lstrip("\n")
            if path:
                touched.add(path)
        if started and _commit_is_mine(touched, distinctive, authored):
            mine += 1
        return mine
    except Exception:
        return None


# Spontaneous-work review checkpoint (operator, 2026-08-29). "Spontaneous" is mechanically
# decidable: every /fabrik-* command opens a run record (corpus predicate 5, gate-enforced), so a
# session that authored CODE files with NO record at all is record-less BY CONSTRUCTION — plain-chat
# work. Commanded work exempts itself; docs-only sessions never fire. The remedy is the light
# /fabrik-review-scoped (same convergence spine, minutes not hours); heavy surfaces escalate to the
# full /fabrik-review per its own contract.
_CODE_EXTS = frozenset(
    {
        ".py",
        ".sh",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".yaml",
        ".yml",
        ".toml",
        ".sql",
        ".go",
        ".rs",
        ".json",
    }
)


# The covered-window LEDGER was born at ff887758 (2026-09-06 19:56:08 +0300). Edits older than
# that were adjudicated by the per-session rule that ran at the time, and their commands' closes
# were never written to any ledger — the sixth cause cannot re-judge them, only re-block them
# (measured: 16 edits of one long-lived session, 09-04 21:46 → 09-06 17:16, every one before the
# first ledger window, re-blocking three attempts on every turn). Transitional by construction:
# no session started after this instant carries an older edit, so the exemption goes inert on
# its own and never widens.
_LEDGER_EPOCH = 1788713768.0

_CLOSED_STATES = frozenset(
    {"done", "blocked", "handoff"}
)  # the closes an AGENT writes — `command_run.py::AGENT_CLOSED_STATES`, bound by a parity grader.
# The coroner's `died`/`expired` are NOT closes: a reaped run covered a span no review contract
# ever ran, and granting it laundered a 37 h abandoned plan (closing review C-2, reversing P1-9);
# such a record reads as no record, and the remedy is the review the run never had.

_REVIEW_FAMILY = frozenset(
    {"fabrik-review", "fabrik-review-scoped"}
)  # the commands whose contract IS a review — `command_run.py::REVIEW_FAMILY`, bound by a parity
# grader for the same reason `_CLOSED_STATES` is: this would otherwise be the fifth hand-kept copy
# of a set the writer owns. Only these may exempt code they did not author (T5.2).


def _hold_in_force(tick_age_s: float, stale_s: float) -> bool:
    """Mirror of quota_stop.py's OFF test (`tick_age_s > stale_s`), negated: the hold is in force
    unless the tick is provably stale. The bound is finite by the time it arrives (the caller
    maps garbage/NaN/inf to 900 s, as quota_stop.py does — P3-5/P3-6); the expression shape is
    kept identical so the two sides can never disagree (review P1-6). A function, so no
    formatter folds the negation back into `<=`."""
    return not (tick_age_s > stale_s)


def _finite(v: object) -> float | None:
    """`_run_record`'s own guard, lifted verbatim: json.loads accepts bare NaN/Infinity, and a bool
    is an int — `Infinity` gave a permanent exemption, `true` read as 1970 (review A-F6)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _review_window(rec: object, sid: str | None = None) -> tuple[float, float] | None:
    """The interval of this session's code edits that a command's contract COVERED — or None.

    A command's contract owns the review discipline from its START to its CLOSE, and nothing
    outside that: code authored BEFORE `started_epoch` was never in its scope (review A-F5 — a
    /fabrik-spec run after plain-chat edits used to launder them), code authored AFTER a closed
    record's `updated_ts` is spontaneous again. A CLOSED state is one of `_CLOSED_STATES` —
    `handoff` included, which /fabrik-user-test and /fabrik-service-test MANDATE (A-F2; a
    hand-written {done, blocked} blocked every such session as "NO run record"). A RUNNING
    record covers up to "now" — but only while the FIFTH cause would still act on it: the same
    freshness rule (`_run_record`, 12h) — an abandoned `start` must not buy immunity after the
    fifth cause has failed open on it (A-F3). Timestamps are guarded for finiteness (A-F6).

    Why a window and not a per-session boolean (2026-09-06): `_run_record_exists` asked "did this
    session EVER open a record?", so one 01:45 /fabrik-review-scoped exempted ten plain-chat commits
    made across the rest of the day — measured by the hook's own author on himself.
    """
    if not isinstance(rec, dict):
        return None
    started = _finite(rec.get("started_epoch"))
    if started is None or started <= 0:
        return None  # the writer refuses to record a window unless started_epoch > 0 (E8 mirror)
    state = _tok(rec, "state")
    started = math.floor(started)  # the writer floors lo (R2): a start second is covered whole
    if state == "running":
        # stale/abandoned — the fifth cause no longer acts on it, nor does this. But the
        # operator's `COMMAND_RUN_STALE_H<=0` opt-out ("don't trap me") makes `_run_record`
        # return None for a LIVE run too — that hatch disarms the fifth cause and must not arm
        # this one (review P1-2)
        if sid is not None and _stale_bound_s() is not None and _run_record(sid) is None:
            return None
        return (started, float("inf"))
    closed = _finite(rec.get("updated_ts"))
    if state in _CLOSED_STATES and closed is not None:
        # the close stamp is FLOORED to the second by `_touch`; the true close lies anywhere in
        # [closed, closed + 1), so the close second is covered whole — symmetric with the floored
        # start (R2: a run inside one second yielded [t, t] and its own start-instant edit fell
        # outside). A ≤ 1 s fail-open at the close edge, already inherent in whole-second stamps.
        return (started, closed + 1.0)
    return None


def _tok(holder: object, key: str) -> str | None:
    """A record field used in a MEMBERSHIP or equality test, read so that it never raises.

    `_seq` closed the iteration half of this class; the membership half stayed open — `state in
    _CLOSED_STATES` and `command not in _REVIEW_FAMILY` both raise `TypeError: unhashable type` on
    a dict or list value, and a raise here costs the stop ALL SIX causes, not one. Measured in
    round 2 by a seat: 660 fuzzed calls over 11 record fields, 40 raised, every one of them a
    membership test on an unhashable value."""
    v = (holder if isinstance(holder, dict) else {}).get(key)
    return v if isinstance(v, str) else None


def _seq(holder: object, key: str) -> list:
    """A record field that MUST be iterated, read so that it never raises. `x or []` keeps a
    non-empty non-iterable — `{"stack": 7}` reached `for frame in 7` and raised TypeError, and a
    raise here costs the stop ALL SIX causes, not one (round 1 of Phase C's own review; the same
    shape was latent on `covered`). A dict is deliberately NOT iterated as its keys."""
    v = (holder if isinstance(holder, dict) else {}).get(key)
    return v if isinstance(v, list) else []


def _review_windows(rec: dict | None, sid: str | None = None) -> list[tuple[float, float]]:
    """EVERY window a command of this session covered: the record's `covered` ledger (each close
    appends `[started_epoch, close]`, and `start` carries the ledger across its overwrite —
    `command_run.py`) plus the current record's own window. One record per session is
    OVERWRITTEN by the next `start`, so a single window destroyed the coverage of every earlier
    command and made a session with two clean runs permanently unreviewable (review P1-1).

    ...plus every frame PARKED on `stack`. A nested `start` parks the running parent there and
    gives the child an EMPTY `covered` ledger deliberately (copying the parent's ledger down and
    joining it back up doubled it per nest cycle — `command_run.py`, closing review C-4/E1), so
    for the whole life of a nested run BOTH the parent's live window and every window the session
    had already closed lived only in that frame. Reading `covered` + the current record alone made
    them invisible, and code authored under the parent's own contract read as UNREVIEWED
    SPONTANEOUS WORK the moment a nested review started (T5.1; 01M288YHD, 01M25Y93RB, 01M1YB2AK).
    A frame's own running window rides the LIVE record's freshness, since it is stored in the live
    record's file: a stale record disarms the parent's immunity exactly as it disarms the child's,
    while both ledgers of CLOSED windows survive staleness — a finished contract is a historical
    fact, not a live claim (the same asymmetry the non-nested path has always had)."""
    out: list[tuple[float, float]] = []

    def _ledger(holder: object) -> None:
        for w in _seq(holder, "covered"):
            if isinstance(w, (list, tuple)) and len(w) == 2:
                lo, hi = _finite(w[0]), _finite(w[1])
                if lo is None or hi is None:
                    continue
                lo = math.floor(lo)  # floor BEFORE the validity test: a legacy `[100.7, 100]` pair
                if lo <= hi:  # written before the writer floored is a real window, not junk (F7)
                    out.append((lo, hi + 1.0))  # whole seconds at both edges (R2)

    _ledger(rec)
    # `stack` is FLAT — `start` copies the live record's frames and appends the parent, so every
    # ancestor of a doubly nested run is already a sibling entry here and no recursion is owed.
    # A frame's RUNNING window is a claim that the session is still live, and only the LIVE record
    # can make it: `kaizen_coroner.py` writes `died`/`expired` on the top-level record ALONE, so a
    # reaped session's frames keep the `running` they were parked with and would otherwise cover
    # `[started, inf)` — the 37 h abandoned plan closing review C-2 refused to launder, wearing a
    # nested hat (measured 0 unreviewed against 1 for the identical non-nested shape). Frames'
    # CLOSED ledger pairs are unconditional: those commands really did close.
    live = isinstance(rec, dict) and rec.get("state") == "running"
    for frame in _seq(rec, "stack"):
        _ledger(frame)
        parked = _review_window(frame, sid) if live else None
        if parked is not None:
            out.append(parked)
    cur = _review_window(rec, sid)
    if cur is not None:
        out.append(cur)
    return out


_SURFACE_SPLIT = re.compile(r"[^A-Za-z0-9_./\\-]+")


def _surface_reviewed(rec: object, authored: dict[str, int], sid: str | None = None) -> set[str]:
    """The authored paths a RUNNING review-family record already names as its `--surface`.

    T5.2 (01M28YN1F): the sixth cause fired on exactly those files. A review's window opens at its
    `start`, so the code it exists to review — authored before it — is outside every window until
    the record closes `done` and the reach-back applies (`command_run.py`). Between those moments
    the hook blocked a session for not reviewing what it was at that moment reviewing. The
    reach-back itself cannot move earlier: a `blocked` or `handoff` close must never certify the
    gap since the last run (reach-back reader F1). So a RUNNING review exempts by NAME instead.

    The rule is equality on a whole token, never a prefix: `scripts/` in the surface exempts
    nothing under it, because a directory is not a claim about a file. A colon is not a path
    character here, so the SPLITTER already ends a token at one and the location suffixes a surface
    actually writes fall off for free — `tests/b.py:44` yields `tests/b.py` and a bare `44`,
    `a.py::test_x` yields `a.py` and `test_x`. (Round 1 of this change's own review deleted an
    explicit strip for those suffixes: the splitter runs first, so it could never fire. A leading
    `./` IS stripped here, because `.` and `/` are both path characters and survive the split.)
    The record's parked `stack` frames are read the same way, since a nested command parks a
    running review there (T5.1).

    STATED COST (round 1, seat finding F3): the tokens come from the WHOLE free-text surface, so a
    path the surface mentions in order to EXCLUDE it ("… explicitly NOT `scripts/b.py`, a sibling
    owns it") is exempted all the same. Left as is deliberately, and bounded: the exemption lives
    only while the record RUNS, a `blocked`/`handoff` close takes it straight back, and a `done`
    close covers the whole session anyway — `command_run.py`'s reach-back is SESSION-granular by
    design ("a review that narrows its `$ARGUMENTS` scope below the session diff is narrowing its
    own contract, not this ledger's"). Parsing negation out of agent-written prose would be a
    detector that fires on legitimate text, which is how enforcement becomes wallpaper."""
    if not isinstance(rec, dict):
        return set()
    # A running record buys immunity only while the FIFTH cause would still act on it — the same
    # stale test `_review_window` applies (A-F3/P1-2). `main` feeds this `_run_record_raw`, which
    # is freshness-blind BY CONSTRUCTION (:520), so without this an abandoned
    # `/fabrik-review-scoped --surface scripts/foo.py` exempted that file for the record's whole
    # life while the window it would have granted was correctly refused (round 1, seat finding F2).
    if sid is not None and _stale_bound_s() is not None and _run_record(sid) is None:
        return set()
    # A parked frame keeps the `running` it was parked with even after the coroner reaps the
    # session (`kaizen_coroner.py` writes `died`/`expired` on the TOP record alone), so the frames
    # are readable only while the LIVE record says `running` — the same predicate `_review_windows`
    # applies. Round 1 closed that hole on the WINDOW axis and left it open on the NAME axis: a
    # fresh `died` record passed the staleness test above and still exempted its frame's surface
    # (round 2, seat finding 2 — 14 parity cells, 2 disagreed, both writer-reachable).
    live = rec.get("state") == "running"
    surfaces: list[str] = []
    for holder in [rec, *(_seq(rec, "stack") if live else [])]:
        if not isinstance(holder, dict):
            continue
        if _tok(holder, "state") != "running" or _tok(holder, "command") not in _REVIEW_FAMILY:
            continue
        s = holder.get("surface")
        if isinstance(s, str) and s:
            surfaces.append(s)
    if not surfaces:
        return set()
    tokens: set[str] = set()
    for s in surfaces:
        for raw in _SURFACE_SPLIT.split(s):
            if not raw:
                continue
            tok = raw[2:] if raw.startswith("./") else raw
            # `.` is a path character, so a surface written as a SENTENCE keeps its full stop on
            # the token and the exemption silently fails — a false BLOCK, the thing T5.2 exists to
            # end (round 1, seat finding F7). ONLY `.`: `,`, `;` and `:` are not in the splitter's
            # class, so it has already ended the token at them and stripping them here was dead
            # (round 2, seat finding 10 — the same unreachable-code class as round 1's C-R3).
            tok = tok.rstrip(".")
            if tok:
                tokens.add(tok)
    return {f for f in authored if f in tokens}


def _unreviewed_spontaneous(
    rec: object, authored: dict[str, int], session_floor: float, sid: str | None = None
) -> int:
    """The sixth cause's whole question, in one place: of THIS session's code edits, how many fall
    outside every window a command of the session covered AND are not named by a running review's
    surface? Composed here rather than at the call site because the call site sits 233 lines deep inside
    `main` — hundreds of lines, not the "~40" an earlier cut of this docstring claimed. The count
    is deliberately NOT written here: round 2 found both endpoints of the line-number cite stale by
    34 in the very commit that called them "re-derived, not recalled", because the same commit's
    other hunks moved them. A self-referential line cite in a file still being edited is
    unmaintainable by construction — the function NAME is the durable address — and
    a fix whose wiring no test reaches is a fix that can
    be deleted with a green suite (measured on this hook's sibling, D-252 round 3)."""
    return len(_unreviewed_spontaneous_files(rec, authored, session_floor, sid))


def _unreviewed_spontaneous_files(
    rec: object, authored: dict[str, int], session_floor: float, sid: str | None = None
) -> list[str]:
    """The same question as `_unreviewed_spontaneous`, answered with the FILE LIST.

    ⚠️ ONE producer, two readers, so the count and the names cannot disagree. The block used to
    print neither — no count, no file — leaving "this session authored code files outside every
    covered window" as an assertion the reader had no way to check or act on (T5.4). A block that
    cannot be verified by the person it blocks is indistinguishable from a broken one, which is
    how a real cause gets worked around instead of answered.
    """
    floor = _sixth_cause_floor(session_floor)
    windows = _review_windows(rec if isinstance(rec, dict) else None, sid)
    windows += _first_review_base_case(rec, floor)
    named = _surface_reviewed(rec, authored, sid)  # once per stop, not once per file
    scoped = {f: ts for f, ts in _this_sessions_edits(authored, floor).items() if f not in named}
    return _unreviewed_code_file_names(scoped, windows)


def _first_review_base_case(rec: object, floor: float) -> list[tuple[float, float]]:
    """The reach-back's missing base case (T5.3, 01M21JAET).

    `command_run.py` gives a review-family `done` close a window reaching BACK to the previous
    covered window's close — a review reviews the session's work SINCE THE LAST RUN. With an EMPTY
    ledger there is no previous close, so the writer falls back to the review's own
    `started_epoch`, and a session interrupted before any command closed can never cover the work
    that preceded its first review: measured permanently unclearable, round after round. 28ca7443
    closed only the PRE-LEDGER half of that mail and is transitional by construction; this half is
    not. The bound this needs — the SessionStart baseline — exists only on this side, which is why
    the base case is applied here.

    STATED COST, rewritten 2026-09-15 because T5.4 falsified both of its sentences and a stale
    cost paragraph is worse than none — the next reader reasons from it. It used to say that a
    missing baseline drops the floor to `_LEDGER_EPOCH` and that `_this_sessions_edits`'s filter is
    disarmed in that state. Neither holds: `_sixth_cause_floor` now takes the MAX of the baseline,
    `now - _SIXTH_CAUSE_MAX_EDIT_AGE_S` and the ledger's birth, so the filter is armed in every
    state and the widest window this base case can grant is one day, not the ledger's whole life.
    The fail-open direction is unchanged and still deliberate — this cause BLOCKS an exit, so its
    failure mode must be letting a stop through rather than the permanent block of 01M21JAET.

    THE PREDICATE THIS FUNCTION EVALUATES, stated as the code reads rather than as a list of the
    writer's shapes — round 2 of this change's own review found the previous paragraph describing
    neither: a durable reach on the record or any parked frame, positive, finite, not beyond the
    clock-skew tolerance, and no ledger pair starting before it. Everything else — `done` only, a
    review-family command only, an empty ledger only — is the WRITER's gate on setting the field at
    all (`command_run.py`), and is graded there. This side adds a window, never rewrites a pair, and
    reads no `command` or `state` of its own."""
    if not isinstance(rec, dict):
        return []
    # The DURABLE marker the writer leaves at a review-family `done` close that had nothing to
    # reach back to (`command_run.py`, `first_review_reach`), carried across every later `start`
    # and joined at a nested pop. Reading it — rather than re-deriving "is the live record a
    # done review" — is what makes the coverage survive the session's next command; the derived
    # form evaporated at that `start` and left the permanent block of 01M21JAET in place (round 1,
    # seat finding F5). A record written before the field existed simply has none.
    # Read the live record AND every parked frame, earliest wins. `start` gives a nested child
    # `first_review_reach: None` for the same reason it gives it an empty ledger, so reading `rec`
    # alone made the marker go DARK for the whole life of a nested run — reproducing T5.1 exactly,
    # on the field that exists to fix T5.3 (round 2, seat finding 4). `_ledger` already reads the
    # frames for `covered`; this is the same rule for the same reason.
    reaches = [
        v
        for v in (
            _finite(h.get("first_review_reach"))
            for h in [rec, *_seq(rec, "stack")]
            if isinstance(h, dict)
        )
        if v is not None and v > 0
    ]
    if not reaches:
        return []
    reach = min(reaches)
    # ...and bound it ABOVE. `_review_window` fail-CLOSES on an absurd `started_epoch` (the window
    # inverts and matches nothing) and `_run_record` refuses a future `updated_ts` past the skew
    # tolerance; this had neither, so a clock ahead at the first review's `start` minted a reach
    # that covered everything and the carry preserved it for the session's whole life (round 2,
    # seat finding 6: 1e300 covered `now`).
    if reach > time.time() + _CLOCK_SKEW_TOLERANCE_S:
        return []
    started = math.floor(reach)
    ledger = _seq(rec, "covered")
    if ledger and not all(
        isinstance(w, (list, tuple)) and len(w) == 2 and _finite(w[0]) is not None for w in ledger
    ):
        return []  # a CORRUPT pair is still evidence of an earlier run: stand down rather than
        # grant the widest window in the file on the strength of a record we cannot read (F9)
    for w in ledger:
        lo = _finite(w[0])
        if lo is not None and math.floor(lo) < started:
            return []  # the writer already reached back over an earlier run
    lo_f = _finite(floor)
    if lo_f is None or not math.isfinite(lo_f):
        return []  # no usable floor, no base case — `float(None)` used to raise here (F10)
    return [(lo_f, float(started))]


# T5.4 (01M25Y93RB): the OLDEST an edit may be and still count as THIS session's work. Not a
# fallback — it binds whether or not a SessionStart baseline exists, which is the correction the
# Phase F review forced. The first cut applied it only when the baseline was MISSING, and the
# reported shape is a RESUMED transcript, which HAS a baseline; it is merely old. Measured live:
# this session's baseline was 135.3 h old, so a 2.5-day-old transcript entry for a file that was
# committed and reviewed to `done` was reported as unreviewed work — and 87 of the 97 baselines on
# this box are older than this window, so the mis-fire was the norm rather than a corner.
# ⚠️ STATED COST, and it is a real one: work authored more than this window ago in a genuinely
# long-lived session drops out of this cause permanently. `decide_review` RE-ARMS on warn-through
# (executed: `decide_review(1, 3)` -> `('allow_warn_review', 0)`), so the status quo was not three
# blocks but three blocks per stop-cycle for the session's whole life — a block that cries wolf is
# one agents learn to warn through, which is its own hollowing-out. This is a widening of a PROXY
# (edit timestamp vs covered window), not a fix of the predicate; the predicate fix is on the
# writer side — `command_run.py` stamps `first_review_reach` only when the ledger was EMPTY, so a
# session whose first command run was not a review can never cover its pre-first-command work.
# ⚠️ THE CHEAPEST WAY TO SATISFY THIS WITHOUT THE OUTCOME (cobra-effect): wait a day, or end three
# turns and let it warn through — neither of which reviews anything. That is why the block NAMES
# the window and the files: an agent who waits it out should at least have to read what it was.
_SIXTH_CAUSE_MAX_EDIT_AGE_S = 86_400.0


def _sixth_cause_floor(session_floor: float) -> float:
    """The floor the sixth cause judges from: the LATEST of the SessionStart baseline, a bounded
    edit-age window, and the ledger's birth. Edits before the ledger existed were adjudicated by
    the per-session rule of their day and no ledger holds their closes — re-judging them can only
    re-block; edits older than the window belong to a resumed transcript's history, not to the
    work this stop is deciding about.

    ⚠️ ONE `max()`, THREE BOUNDS, and the age bound binds whether or not a baseline exists. The
    first cut branched — bounded window when the baseline was missing, the raw baseline otherwise —
    which is two implementations of one rule, and it left the REPORTED shape untouched: a resumed
    transcript has a baseline, it is merely old. Collapsed here so there is one place to read.

    The floor therefore SLIDES between stops. That is deliberate and it is why the block names the
    window and the files: a verdict that changes on its own, silently, is indistinguishable from a
    broken one."""
    return max(
        float(session_floor or 0.0),
        time.time() - _SIXTH_CAUSE_MAX_EDIT_AGE_S,
        _LEDGER_EPOCH,
    )


def _baseline_floor(sid: str) -> float:
    """The FLOORED baseline — `_sixth_cause_floor(mtime)`, never a falsy value.

    ⚠️ IT CANNOT RETURN 0.0, and an earlier line of this docstring said it could. `0.0` is the one
    value that breaks every consumer: `_this_sessions_edits` and `_failure_cites_session` both read
    a falsy floor as "no floor" and keep every entry, which is the LIFETIME set this helper exists
    to stop.

    ⚠️ THE MIRROR — the shape this bound BREAKS, stated rather than left for the next reader.
    Flooring at `now - _SIXTH_CAUSE_MAX_EDIT_AGE_S` means a session whose only edits are OLDER than
    that window has an empty `_this_sessions_edits`, so `_ahead_of_upstream` returns `None` and the
    PUSH law never fires for it: a session that committed at hour 0 and stops at hour 25 is not
    told its work is unpushed. That is the deliberate direction — this cause BLOCKS an exit, so it
    must fail toward letting a stop through rather than trapping a session behind someone else's
    work — but it IS a cost, and `_SIXTH_CAUSE_MAX_EDIT_AGE_S` states it only for the sixth cause.

    Exists so the PUSH cause reads a bounded floor rather than the raw baseline. It used to be
    handed `set(authored_map)` — the transcript's LIFETIME edit set — while
    `_failure_cites_session` and the sixth cause both floored theirs. On a resumed transcript
    (454 code files over 116 days in one sid, measured) that made any file the session ever
    touched "distinctive", so a sibling's unpushed commit on one of them counted as mine and
    the hook BLOCKED. That is the trapping direction `_ahead_of_upstream`'s own docstring
    forbids: this cause blocks an exit, so its failure mode must be letting a stop through,
    never holding a session behind someone else's work."""
    try:
        # ⚠️ `_sixth_cause_floor`, not the RAW baseline. main() keeps the ORIGINAL baseline across
        # a resume/compact BY DESIGN, so on the very transcript this helper's docstring cites
        # (454 code files over 116 days in one sid) the baseline is 116 days old and filters
        # NOTHING — the fix was inert on its own named incident. `_sixth_cause_floor` is
        # `max(baseline, now - edit-age, _LEDGER_EPOCH)`, the bound the sixth cause has always
        # used; on this box 87 of 98 baselines are older than 24h, so the two differ for ~89% of
        # live sessions and the raw one was the wrong half of that pair.
        return _sixth_cause_floor(_baseline_path(sid).stat().st_mtime)
    except OSError:
        # ⚠️ NEVER 0.0. `_this_sessions_edits` reads a FALSY floor as "no floor" and keeps every
        # entry (the `not session_floor` arm of `_this_sessions_edits`, and the same arm in
        # `_failure_cites_session`), so returning 0.0 on a missing baseline silently
        # restores the LIFETIME edit set — the precise defect this helper was added to close, in
        # the case the file elsewhere calls routine ("No baseline (SessionStart didn't run /
        # older session)"). The sibling consumer `_sixth_cause_floor` never had this hole because
        # it takes a `max()` with the edit-age window; the same window is the right fallback here,
        # and it fails toward "nothing is distinctive" (no block) rather than "everything is".
        return _sixth_cause_floor(0.0)


def _this_sessions_edits(authored: dict[str, int], session_floor: float) -> dict[str, int]:
    """Drop edits older than the SessionStart baseline — a resumed transcript's ancient work,
    not this session's (the same filter `_failure_cites_session` applies). Unfiltered, a
    months-long transcript (454 code files over 116 days in one sid, measured) made any window
    of minutes count hundreds of files as unreviewed (review P1-3). ts == 0 (unknown) stays.
    The sixth cause passes `_sixth_cause_floor(baseline)` — the LATEST of the baseline, the
    edit-age window and the ledger's birth — so pre-ledger edits are dropped here, and so are
    edits older than the window (pool DOC-001, 2026-09-07; the third bound added 2026-09-15, and
    on this box it is the one that usually binds: 87 of 97 baselines are older than it)."""
    return {
        f: ts for f, ts in authored.items() if not ts or not session_floor or ts >= session_floor
    }


def _unreviewed_code_files(
    authored: dict[str, int],
    windows: list[tuple[float, float]] | tuple[float, float] | None,
) -> int:
    """Code files this session authored OUTSIDE every covered window — the ones no command's
    contract has reviewed. An edit with no parseable timestamp (ts == 0, `_session_files`)
    COUNTS: unknown is not covered (A-F10). A single window (the pre-P1-1 shape) is accepted.

    The COUNT is `len()` of the names, never a second traversal — see
    `_unreviewed_code_file_names`, which is the one place the rule is written."""
    return len(_unreviewed_code_file_names(authored, windows))


def _unreviewed_code_file_names(
    authored: dict[str, int],
    windows: list[tuple[float, float]] | tuple[float, float] | None,
) -> list[str]:
    """The names behind the count, sorted — so the block can say WHICH files it means.

    Two readers, one traversal: a count computed separately from the list it describes is two
    implementations of one rule, and the stale one reads exactly like the current one."""
    from pathlib import PurePosixPath

    if windows is None:
        wins: list[tuple[float, float]] = []
    elif isinstance(windows, tuple):
        wins = [windows]
    else:
        wins = list(windows)
    out: list[str] = []
    for f, ts in authored.items():
        if PurePosixPath(f).suffix.lower() not in _CODE_EXTS:
            continue
        if not isinstance(ts, (int, float)) or ts == 0:
            out.append(f)
            continue
        if not any(lo <= float(ts) <= hi for lo, hi in wins):
            out.append(f)
    return sorted(out)


def decide_review(code_files: int, attempts: int, cap: int = CAP) -> tuple[str, int]:
    """Pure review-checkpoint decision. Returns (action, attempts').

    `code_files` is the count of session-authored code files OUTSIDE every covered window
    (`_unreviewed_code_files`). Warn-through RE-ARMS (attempts → 0), like every other cause: the
    old `return attempts` disarmed the cause for the rest of the session after three blocks
    (review A-F8). The former `nothing_unreviewed` flag was `code_files == 0` restated, and its
    only independent value silently disabled the cause (review P1-7).
    """
    if code_files == 0:
        return "allow", 0
    attempts += 1
    if attempts > cap:
        return "allow_warn_review", 0
    return "block_review", attempts


def decide_stall(stalled: bool, attempts: int, cap: int = CAP) -> tuple[str, int]:
    """Pure promise-guard decision. Returns (action, attempts').

    action ∈ {"allow", "block_stall", "allow_warn_stall"} — same anti-trap shape
    as the other causes: counter resets when the cause resolves, warn-through at
    the cap so a misfire can never trap the session.
    """
    if not stalled:
        return "allow", 0
    attempts += 1
    if attempts > cap:
        return "allow_warn_stall", 0
    return "block_stall", attempts


# Narrate-instead-of-act stall (live class, 2 incidents 2026-08-07): the final
# message PROMISES an action it never dispatched, or ASKS permission an active
# plan/review contract already grants. Precision over recall throughout —
# indeterminate parses fail open, human-gate wording is exempt, a kept promise
# (a dispatch in the same final turn) is exempt.
# Two-stage promise match (precision-first; review finding: bare verbs blocked
# read-only turns like "Let me run through the options"): a first-person future
# verb must be followed, within 60 chars, by an ACTION OBJECT — a slash command,
# a work artifact, or a direct object pronoun. "run through" (reviewing idiom)
# and "start by" (conversational) are excluded at the verb.
_PROMISE_VERB_RE = re.compile(
    r"\b(?:I(?:'|’)?ll|I will|let me)\s+(?:now\s+)?"
    r"(?:run(?!\s+through)|start(?!\s+by)|dispatch|launch|kick\s+off"
    r"|keep\s+(?:working|going|chaining)|work\s+through)\b"
    r"|\b(?:starting|running|dispatching)\s+(?:it|that|this|the\s+[\w\- ]{1,40}?)\s+now\b",
    re.I,
)
_ACTION_OBJECT_RE = re.compile(
    r"/[a-z][\w-]+|\bit\b|\bthem\b|\bpass(?:es)?\b|\bround\b|\bsuite\b|\bgate\b"
    r"|\breviews?\b|\btests?\b|\bpytest\b|\bplans?\b|\btickets?\b|\bphases?\b"
    r"|\bfinders?\b|\bsweep\b|\bfix(?:es|ups?)?\b|\bbatch\b|\bcommand\b|\bscript\b"
    r"|\bsubagents?\b|\bcoders?\b|\bworkflow\b|\bnow\b",
    re.I,
)
_PERMISSION_RE = re.compile(
    r"\b(?:want me to|shall I|should I(?!\s+have)|would you like me to|do you want me to)\b"
    r"[^?\n]{0,120}\?",
    re.I,
)
# PASSIVE obligation naming un-run work — the 2nd live stall shape ("Pass 7 is
# owed", trade-intelligence): the corpus's own convergence contracts teach this
# vocabulary ("you owe the next pass — dispatch it"), so no first-person future
# verb ever appears. "due to" is causal and "owed to" is credit, not obligation;
# a negated subject ("no further pass is owed") is a convergence CONCLUSION —
# both excluded. The subject noun IS the action object, so no second stage.
_OBLIGATION_RE = re.compile(
    r"\b(?:pass(?:es)?|rounds?|reviews?|sweeps?|re-?runs?|phases?|audits?"
    r"|fix(?:es)?|tickets?|gauntlets?)\b"
    r"[^.!?\n]{0,40}?\b(?:is|are|remains?|stays?)\s+(?:(?:still|now|already)\s+)?"
    # "due to" causal · "owed to" credit · "due on/by/before/after/once/when" deadline prose
    r"(?:owed(?!\s+to)|due(?!\s+(?:to|on|by|before|after|once|when)\b)|outstanding)\b"
    # "the sweep remains to be run/done/executed"
    r"|\b(?:pass(?:es)?|rounds?|reviews?|sweeps?|re-?runs?|phases?|audits?|fix(?:es)?)\b"
    r"[^.!?\n]{0,30}?\bremains?\s+to\s+be\s+(?:run|done|executed)\b"
    # passive AVAILABILITY of own work — the live 2026-08-10 miss: an orchestrator ended
    # its turn on "T03 and T05 are now both dispatchable in parallel" with the tickets
    # undispatched. Availability phrasing = the same undone-own-work signal as "is owed";
    # negated subjects ("nothing further is dispatchable") carry no matching work-noun and
    # never reach this branch. T## covers bare ticket-ID subjects.
    r"|\b(?:pass(?:es)?|rounds?|phases?|tickets?|T\d{2}[a-z]?)\b"
    r"[^.!?\n]{0,60}?\b(?:is|are)\s+(?:(?:still|now|both|all)\s+){0,2}"
    r"(?:dispatchable|launchable|ready\s+(?:to|for)\s+(?:dispatch|launch|run|start))\b"
    # first-person: only with a WORK object ("owe the next pass"), never credit
    # ("owe a debt of gratitude") or idiom ("owe it to future sessions")
    r"|\b(?:I|we)\s+(?:still\s+)?owe\s+(?:(?:the|a|an|another|one)\s+(?:next\s+)?"
    r"(?:pass|round|review|sweep|re-?run|phase|audit|fix\w*|confirming\s+\w+)\b"
    r"|it\b(?!\s+to))",
    re.I,
)
_NEGATED_BEFORE_RE = re.compile(r"\b(?:no|none|nothing|zero)\b[\s\w-]{0,32}$", re.I)
# Assertive CONTINUATION CLAIM — the 3rd live stall shape (brand-identiy-creator,
# 2026-08-11): "Continuing autonomously." then the turn ends. A present-progressive
# claim of ongoing action IS a promise — the turn's end falsifies it. Precision:
# the gerund needs an autonomy qualifier or a loop-unit object ("with round 7"),
# OR stands as its own terminal sentence; a plain conversational gerund
# ("continuing our discussion, …") matches neither branch.
_CONTINUATION_CLAIM_RE = re.compile(
    r"\b(?:continuing|proceeding|resuming)\s+(?:autonomously|now|immediately|unprompted)\b"
    r"|\b(?:continuing|proceeding|resuming)\s+with\s+(?:round|pass|phase)\b"
    r"|(?:^|[.!?]\s+)(?:continuing|proceeding|resuming)\s*[.!]\s*$",
    re.I | re.M,
)
# Structural checkpoint-stall — a NEXT: footer naming a NUMBERED own-loop unit
# ("NEXT: round 7 …"). The loop contracts forbid handing numbered rounds/passes
# to the operator, so such a line is own-session work by construction; emitting
# it undispatched is the checkpoint-stall the FINAL OUTPUT contract names.
# Same-line human-gate wording exempts via the shared _line_exempt pass.
_NEXT_ROUND_RE = re.compile(r"^\s*NEXT:[^\n]*?\b(?:round|pass)\s*#?\d+", re.I | re.M)
# Legitimate stops. Two scopes (review finding: the mandated FINAL OUTPUT
# vocabulary "NEXT: operator decision: …" appears in nearly every operator-gated
# task end — a FULL-message scan let that routine line disarm genuine promises
# anywhere in the message):
# - GLOBAL (whole message): only the BLOCKED escalation header — its detail
#   legitimately runs past the 600-char tail cut.
# - LOCAL (the line carrying the stall match): human-gate wording exempts the
#   stall it actually describes, never the whole message.
# Case-sensitive on purpose: the sanctioned escalation header is uppercase `BLOCKED:`
# everywhere in the corpus, and CASE is the only reliable discriminator — lowercase
# prose ("pre-blocked:", "blocked: on X") must not exempt, while a hyphen-glued header
# ("T1a-BLOCKED:") must; a hyphen lookbehind cannot tell those apart (review 2026-08-30).
_GATE_EXEMPT_GLOBAL_RE = re.compile(r"\bBLOCKED:")
# SELF-NAMING gates — these phrases ARE the justification (the two sanctioned human gates,
# and work whose owner is explicitly not this session). They exempt on their own.
_GATE_EXEMPT_NAMED_RE = re.compile(
    r"\bgate\s*[12]\b|\bhuman gate\b|\bplan approval\b|\bdeploy approval\b"
    r"|\byours to run\b|\boperator[- ]gated\b",
    re.I,
)
# BARE deferral vocabulary. These say "a human decides" WITHOUT saying why, and on their own
# they are the most over-used escape hatch in the corpus.
#
# ⚠️ Measured 2026-08-29 over one session's 905 NEXT: lines: 281 (31%) deferred to the operator,
# and of 185 DISTINCT deferrals only 27 (15%) named a reason that genuinely requires a human.
# The other 85% had answers already sitting in the rules, a spec, or were plain read-only work —
# one literally read "awaiting your go on measuring the 29 suites serially — that is read-only".
# The operator has objected to this three times; prose lost twice, because THIS list rewarded it:
# typing "operator decision" disarmed the checkpoint-stall guard outright, so deferring was
# cheaper than acting. A constitution that forbids the stall cannot beat a hook that blesses it.
#
# So a bare phrase no longer exempts by itself — it must sit on the same line as a CLASS naming
# why a human is structurally required. Everything else is the agent's own work to do.
_GATE_EXEMPT_BARE_RE = re.compile(
    r"\boperator decision\b|\bapproval\b|\bawait\w*\s+(?:your|the operator)\b"
    # Conditional OFFER vocabulary — a follow-up gated on the operator's word is
    # a sanctioned stop (live FP: the guard fired on its own author's offer).
    r"|\bsay the word\b|\bon your (?:yes|word|go|approval)\b|\bif you want\b|\byour call\b",
    re.I,
)
# The closed set, derived from CLAUDE.md § HARD STOPS — the cases where proceeding would be
# unsafe, irreversible, spend real money, or write outside this repo. `rule-conflict` is the
# operator's own carve-out ("if the rule is problematic, they must inform you") and is the one
# class that must cite the contradiction, so it cannot become a second bare escape hatch.
_GATE_CLASS_RE = re.compile(
    r"\bcross[- ]repo\b|\banother repo\b|\bgate\s*[12]\b|\bplan approval\b"
    r"|\bdeploy(?:ment)?\b|\bpublish\b|\bspend\b|\bcost\b|\bquota\b|\bbilling\b|\$\d"
    r"|\birreversible\b|\bdestructive\b|\bprod(?:uction)?\s+data\b|\bpolicy\b"
    r"|\brule[- ]conflict\b.*?\b[\w./-]+\.\w+:\d+",
    re.I,
)
# Tool names whose use in the final turn means a promise was KEPT (work dispatched).
_DISPATCH_TOOLS = frozenset({"Task", "Agent", "Skill", "Workflow", "SlashCommand"})


def _is_dispatch(tool: dict) -> bool:
    if tool["name"] in _DISPATCH_TOOLS:
        return True
    if tool["name"] == "Bash":
        if tool["input"].get("run_in_background"):
            return True
        # `rund -- <cmd>` is CLAUDE.md's sanctioned foreground-wrapper that
        # backgrounds internally — a kept promise (review finding).
        cmd = str(tool["input"].get("command") or "")
        if re.match(r"\s*rund\b", cmd):
            return True
    return False


# Bounded transcript read: the final TURN lives in the last slice of the file; a
# full read_text() on a multi-hundred-MB transcript cost 2.5+ GB RSS per Stop
# (measured live, review finding). 2 MB >> any single turn's tail.
_TAIL_READ_BYTES = 2 * 1024 * 1024


def _tail_lines(transcript_path: str) -> list[str] | None:
    """The transcript's last ``_TAIL_READ_BYTES``, split into whole lines, or None."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _TAIL_READ_BYTES))
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    lines = raw.splitlines()
    if size > _TAIL_READ_BYTES and lines:
        lines = lines[1:]  # first line of a mid-file slice is almost surely partial
    return lines


def _final_message_text(transcript_path: str) -> str:
    """EVERY text block of the last assistant entry, joined in order.

    The stall guard's reader (:func:`_final_turn`) joins the same way since 2026-09-07 — it
    took only the FIRST text block, and the seven-line check (2f984062) then refused a FINAL
    OUTPUT block split across two blocks as incomplete before this metric ever ran. Two
    readers of "the final message" with different join rules is how a check and its metric
    disagreed; keep them joined alike (native closing reader N5).
    """
    lines = _tail_lines(transcript_path)
    if not lines:
        return ""
    for line in reversed(lines):
        if '"type"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        text = "\n".join(
            str(b.get("text") or "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
        # Textless (tool_use/thinking-only) entries are SKIPPED, not returned as "": the
        # harness can fire Stop before the final text entry is flushed, and at that moment
        # the tail ends in the closing tool_use entry (anchor_harvest measured chars=0 at a
        # turn-final Stop, 2026-08-29). The last flushed text is the best available message.
        if text.strip():
            return text
    return ""


def _final_turn(transcript_path: str) -> tuple[str, list[dict]] | None:
    """(final assistant text, tool_use list of the final turn) or None on any gap.

    Text comes ONLY from the LAST assistant entry (an empty final message stays
    empty — never inherit an older message's promise; review finding). Tools are
    collected across the whole final turn, back to the last REAL user message.
    """
    lines = _tail_lines(transcript_path)
    if lines is None:
        return None
    text = ""
    seen_assistant_entry = False
    tools: list[dict] = []
    for line in reversed(lines):
        if '"type"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        etype = entry.get("type")
        content = (entry.get("message") or {}).get("content")
        if etype == "user":
            # tool_result blocks also arrive as type=user — only a REAL user
            # message (text content) ends the turn walk.
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "text" for b in content
            ):
                break
            continue
        if etype != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tools.append({"name": block.get("name", ""), "input": block.get("input") or {}})
            elif block.get("type") == "text" and not seen_assistant_entry:
                # EVERY text block of the last entry, joined — reading only the first split a
                # final block written as two blocks and the seven-line check (2f984062, D-173)
                # refused it as "incomplete" before the emitter ran (kaizen split-block grader
                # red at HEAD, 2026-09-07); `_final_message_text` already joins the same way
                t = str(block.get("text") or "")
                text = f"{text}\n{t}" if text else t
        seen_assistant_entry = True  # only the LAST assistant entry may supply text
    return text, tools


def _midrun_marker(root: Path, authored: set[str]) -> bool:
    """A SESSION-OWNED mid-run signal: an active plan lock this session edited, or a
    session-authored review doc with UNCHECKED rows. Session-scoped deliberately —
    an unrelated sibling session's active lock must not turn another session's
    legitimate follow-up offer into a stall."""
    for rel in authored:
        p = root / rel
        try:
            if ".fabrik/plan-locks/" in rel and p.is_file():
                # Parse, don't substring-match: compact JSON must still arm it, and
                # a history entry recording a PAST active status must not (review
                # finding). Unparseable lock → not armed (fail toward allowing).
                try:
                    if (
                        json.loads(p.read_text(encoding="utf-8", errors="replace")).get("status")
                        == "active"
                    ):
                        return True
                except Exception:
                    pass
            elif "docs/development/reviews/" in rel and p.is_file():
                # Live checklist ROW form only — a closed review's prose mention of
                # the word ("rows return to UNCHECKED") must not keep the marker on.
                if "| UNCHECKED" in p.read_text(encoding="utf-8", errors="replace"):
                    return True
        except OSError:
            pass
    return False


def _line_exempt(tail: str, match: re.Match[str]) -> bool:
    """Human-gate wording exempts only the stall it sits WITH — the line carrying the
    match (review finding: the mandated 'NEXT: operator decision: …' line was disarming
    genuine promises message-wide)."""
    ls = tail.rfind("\n", 0, match.start()) + 1
    le = tail.find("\n", match.end())
    line = tail[ls : le if le != -1 else len(tail)]
    if _GATE_EXEMPT_NAMED_RE.search(line):
        return True
    # A bare "operator decision" must say WHY a human is structurally required.
    return bool(_GATE_EXEMPT_BARE_RE.search(line) and _GATE_CLASS_RE.search(line))


def _quoted(tail: str, match: re.Match[str]) -> bool:
    """A match directly preceded by a quote char is a QUOTATION (discussing the phrase,
    not making it) — live FP: the guard's author quoting 'I'll run it' as an example.
    Conservative: only the immediately preceding non-space character is inspected."""
    before = tail[: match.start()].rstrip()
    return bool(before) and before[-1] in "\"'`“‘«"


def _in_quote(tail: str, start: int) -> bool:
    """Inside an open quote span: the nearest quote char in the preceding 80 chars has
    no closing mate before the match. Obligation matches begin at the work-noun, rarely
    at the quote's first token, so the preceding-char check alone misses mid-quote
    snippets (live FP: a report QUOTING a stall snippet was itself stall-blocked).
    Straight apostrophes are excluded (possessives)."""
    window = tail[max(0, start - 80) : start]
    for opener, closer in (('"', '"'), ("“", "”"), ("«", "»"), ("`", "`")):
        i = window.rfind(opener)
        if i != -1 and closer not in window[i + 1 :]:
            return True
    return False


def _detect_stall(
    transcript_path: str,
    root: Path,
    authored: set[str],
    waived: list[tuple[str, str]] | None = None,
) -> tuple[str, str] | None:
    """Return ("promise"|"permission", snippet) when the final message is a stall, else None.

    ``waived`` is an optional OUT-parameter recording ``(kind, marker)`` for every stall
    that MATCHED and was then exempted by a sanctioned-skip marker. From the outside a
    waived stall and a message with no stall at all both look like ``None`` — and only
    the first is an operator override. Without this ledger the override metric can only
    be approximated by matching the marker vocabulary alone, which fires on the mandated
    ``NEXT: operator decision: …`` footer of nearly every operator-gated task end.
    """
    try:
        turn = _final_turn(transcript_path)
        if not turn:
            return None
        text, tools = turn
        if not text:
            return None
        # D-059 (SEVENTH cause vocabulary, rides the stall lane so the 3-attempt
        # warn-through applies unchanged): a task-completing FINAL OUTPUT block
        # (GATE:+DONE:+NEXT: all present) missing its FEEDBACK: line is an
        # incomplete terminator. This is the ACTUAL enforcement the D-059 row
        # promised — _FINAL_BLOCK_KEYS alone only feeds a metric (review finding:
        # the first landing claimed blocking it never had).
        # Generalised 2026-09-07 (operator directive, D-173: ONE seven-line block in every repo):
        # a block that carries SOME of the seven keys but not all is incomplete whatever it
        # dropped — the FEEDBACK:-only shape above was one instance of this class (a block
        # missing DOCS UPDATED:/CHANGELOG:/LESSONS LEARNT: passed as complete). NEXT: is shared
        # with the conversational STATE:/NEXT: footer, so it never counts toward "a block is
        # being emitted": two or more of the OTHER six keys do.
        # Scoped to the message TAIL: the contract says "the LAST 7 lines", so a block quoted
        # mid-message as an example (an explainer, a how-to) is not a terminator and must not
        # trip this (round-1 finders, three readers). Ten lines leave room for a closing
        # fence and blank lines around the seven; the whole-text scan is kept for the metric.
        # A BLOCKED: escalation is one of the three sanctioned halting exits and exempts every
        # stall GLOBALLY (the flag below) — this check must not sit before that flag exists
        # (native finder r1, executed: a 3-strikes BLOCKED close was refused as "incomplete").
        escalation = _GATE_EXEMPT_GLOBAL_RE.search(text)
        tail_lines = text.rstrip().splitlines()[-_FINAL_BLOCK_TAIL_LINES:]
        tail_text = "\n".join(tail_lines)
        present = [
            k for k in _FINAL_BLOCK_KEYS if re.search(rf"^\s*{re.escape(k)}", tail_text, re.M)
        ]
        # THREE non-NEXT keys = a block is being emitted (the old anchor's strength: GATE+DONE+
        # NEXT); two let "DONE: finished the compose review." + "GATE: looked right" beside a
        # footer read as a block (native finder r1, executed).
        if sum(1 for k in present if k != "NEXT:") >= 3 and len(present) < len(_FINAL_BLOCK_KEYS):
            missing = [k for k in _FINAL_BLOCK_KEYS if k not in present]
            if escalation:
                if waived is not None:
                    waived.append(("blocked-escalation", escalation.group(0)))
            else:
                return (
                    "final-block-incomplete",
                    f"present: {' '.join(present)}; missing: {' '.join(missing)}",
                )
        tail = text[-600:]
        # The BLOCKED escalation exempts GLOBALLY: its header must not be split away
        # from its own detail by the tail cut (review finding). It is held as a flag
        # consulted by every loop rather than an early return, so a stall it waives is
        # still SEEN (and recorded) on the way past — the return value is unchanged,
        # since a truthy flag exempts every match there is.
        dispatched = any(_is_dispatch(t) for t in tools)

        def _waive(match: re.Match[str]) -> None:
            if waived is None:
                return
            if escalation:
                waived.append(("blocked-escalation", escalation.group(0)))
            else:
                waived.append(("human-gate", match.group(0)))

        # First UNQUOTED verb match with an action object in reach — a quoted
        # example must not MASK a later genuine promise (review finding).
        for m in _PROMISE_VERB_RE.finditer(tail):
            if _quoted(tail, m):
                continue
            if not _ACTION_OBJECT_RE.search(tail[m.end() : m.end() + 60]):
                continue  # conversational verb with no work object — not a promise
            if escalation or _line_exempt(tail, m):
                _waive(m)  # a real cause, waved through by a sanctioned marker
                continue
            if not dispatched:
                return "promise", m.group(0)
            break  # promise exists but was KEPT (work dispatched this turn)

        for m in _OBLIGATION_RE.finditer(tail):
            if _quoted(tail, m) or _in_quote(tail, m.start()):
                continue
            if _NEGATED_BEFORE_RE.search(tail[max(0, m.start() - 48) : m.start()]):
                continue  # "no adversarial or confirming pass is owed" — a conclusion
            if escalation or _line_exempt(tail, m):
                _waive(m)
                continue
            if not dispatched:
                return "promise", m.group(0)
            break  # obligation named AND work dispatched this turn — kept
        # Continuation claims + NEXT:-round footers share the obligation loop's
        # protections; neither needs the negation guard (no negated form exists).
        for pattern in (_CONTINUATION_CLAIM_RE, _NEXT_ROUND_RE):
            for m in pattern.finditer(tail):
                if _quoted(tail, m) or _in_quote(tail, m.start()):
                    continue
                if escalation or _line_exempt(tail, m):
                    _waive(m)
                    continue
                if not dispatched:
                    return "promise", m.group(0).strip()
                break  # claim exists but work was dispatched this turn — kept
        for m in _PERMISSION_RE.finditer(tail):
            if _quoted(tail, m):
                continue
            if escalation or _line_exempt(tail, m):
                _waive(m)
                continue
            if _midrun_marker(root, authored):
                return "permission", m.group(0)
            break
        return None
    except Exception as e:
        # Fail open — but never SILENTLY (review finding: a MemoryError-disabled
        # guard was indistinguishable from "no stall").
        sys.stderr.write(f"[promise-guard] detection error, failing open: {e}\n")
        return None


def _kaizen_pass(
    sid: object,
    transcript_path: str,
    waived: list[tuple[str, str]],
    warned: list[str],
) -> None:
    """The NON-BLOCKING exit — the only place a Stop actually ends the turn.

    Every message-shaped observation lives here, not at the top of the Stop path,
    because a blocked turn is RETRIED: the agent fixes the cause and stops again, and
    the same final message is re-read each time. Emitting from the entry point counted
    one task terminator once per retry (up to CAP+1 times), which is a multiplier on
    exactly the metric the terminator contract is measured by.

    - ``stop_pass`` — this TURN passed. Not `session_end`: the Stop hook fires once per
      turn, so session liveliness is the LAST `stop_pass` timestamp, and a session that
      never produced one is the hole.
    - ``final_block_emitted`` — the mandated 7-line FINAL OUTPUT block was written.
    - ``operator_override`` — an enforcement cause fired and a sanctioned-skip marker
      waved it through (:func:`_detect_stall`'s waiver ledger). The marker ALONE is not
      an override: it is the routine vocabulary of every operator-gated task end.

    Guard order matters: the module check comes FIRST, so a box without the emitter
    does not even pay the transcript read.
    """
    if not kaizen_events:
        return
    _kaizen(
        "stop_pass",
        sid,
        outcome="warned_through" if warned else "clean",
        warned=sorted(set(warned)),
    )
    try:
        if transcript_path and _final_block_seen(_final_message_text(transcript_path)):
            _kaizen("final_block_emitted", sid)
    except Exception:
        pass
    if waived:
        # ONE event per turn, carrying the WHOLE waiver ledger (P2): recording only
        # waived[0] under-counted turns where several stalls were waved through.
        # marker/kind keep the first entry for consumer continuity.
        kind, marker = waived[0]
        _kaizen(
            "operator_override",
            sid,
            marker=marker,
            kind=kind,
            stalls=len(waived),
            kinds=[k for k, _ in waived],
        )


def main(argv: list[str]) -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        root = Path(data.get("cwd") or os.getcwd()).resolve()
        sid = str(data.get("session_id") or "nosession")
        # The RAW id for the event stream — see _kaizen's docstring on why the
        # "nosession" fallback above must never become an event's sid.
        ev_sid = data.get("session_id")
        _kaizen_bind(str(root))

        # Thread-anchor harvest — durable memory for the NEXT: line. Agents already emit it on
        # every answer (905 in one measured session); this is the read-back half that never
        # existed: the line is persisted to ~/.claude/state/threads/<session>.json and the
        # prompt hooks re-inject the open anchors. Best-effort by construction — a harvest
        # failure must never block a turn, and a project that has not synced the script skips.
        # BEFORE the eligibility return, with a __file__ fallback: memory must not depend on
        # enforcement eligibility. A post-compact Stop arrived with a payload whose cwd/
        # transcript seam silently disabled BOTH consumers of the final message (2026-08-29:
        # register stale, final_block_emitted dark, everything else fine) — the hook's own
        # location names its repo when the payload's cannot, and the anchor_harvest event
        # below is the trace that separates "hook never ran" from "ran and found nothing".
        try:
            _ta = root / "scripts" / "thread_anchor.py"
            if not _ta.exists():
                _ta = Path(__file__).resolve().parents[2] / "scripts" / "thread_anchor.py"
            _tp = data.get("transcript_path")
            _text = _final_message_text(str(_tp)) if _tp else ""
            if _ta.exists() and _text:
                subprocess.run(
                    [sys.executable, str(_ta), "harvest", "--session", sid],
                    input=_text,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
            _kaizen("anchor_harvest", ev_sid, tp=bool(_tp), chars=len(_text))
        except Exception:
            pass

        if not (root / "scripts" / "final_gate.py").exists():
            return 0  # not a fabrik-style project → nothing to enforce

        # THE QUOTA HOLD OUTRANKS EVERY CAUSE BELOW. While `quota_stop.py`'s stamp stands the
        # session cannot run final_gate.py (not in the hold's allowed Bash set), cannot edit,
        # cannot dispatch /fabrik-review-scoped — so "gate red", "unreviewed spontaneous work"
        # and most of the rest are UNCLEARABLE, and blocking here only forces another assistant
        # turn. Turns burn quota even when every tool is denied. Measured 2026-09-06: the hold
        # fired on time at the 90% drain tier, the agent obeyed it, and still walked into "You've
        # hit your session limit" — talking its way to the wall between two hooks that did not
        # know about each other. The hold has ALREADY ordered the graceful stop; letting the turn
        # end IS the graceful stop. Same stamp path and env override as quota_stop.py; fail-OPEN
        # on any doubt (a stale stamp makes this hook lenient for one dead-cron episode, which
        # costs nothing — the opposite mistake costs the last of the quota).
        try:
            _state = Path(os.environ.get("ROTATE_STATE_DIR") or Path.home() / ".claude" / "state")
            # A-F1 (review 2026-09-06, CRITICAL): quota_stop.py fails OPEN when the tick log is
            # older than QUOTA_STOP_TICK_STALE_S — the hold is OFF and every tool is back — but this
            # yielded on the stamp's mere EXISTENCE, so a dead cron plus a leftover stamp disabled
            # all six causes indefinitely while nothing was held. Same seam, same bound, same
            # direction as quota_stop.py:489-505: yield only while the hold is genuinely in force.
            _tick = Path(
                os.environ.get("QUOTA_STOP_TICK_LOG") or Path.home() / ".claude" / "rotate-tick.log"
            )
            # the same guarded parse as quota_stop.py `_stale_after_s`: garbage or a non-finite
            # value is the 900 s default on BOTH sides (closing review P3-5/P3-6 — a NaN bound
            # read as "held forever", the opposite of the documented "a dead cron never freezes")
            try:
                _stale = float(os.environ.get("QUOTA_STOP_TICK_STALE_S", "900"))
            except (TypeError, ValueError):
                _stale = 900.0
            if not math.isfinite(_stale):
                _stale = 900.0
            if (
                (_state / "fleet-exhausted").exists()
                and _tick.exists()
                # the SAME expression shape as quota_stop.py (`age > stale` = off): under a NaN
                # bound both sides read the hold as in force — `<=` disagreed exactly there and
                # produced the held-and-blocked deadlock A-F1 exists to end (review P1-6)
                and _hold_in_force(time.time() - _tick.stat().st_mtime, _stale)
            ):
                _kaizen("stop_allowed_quota_hold", ev_sid)
                return 0
        except Exception:
            pass

        # SessionStart: record the inherited failing set, then always allow.
        # RESUME/COMPACT keep the ORIGINAL baseline: a revived session (the
        # resume mesh's claude -p --resume, or a compaction) re-baselining
        # would swallow its OWN gate breakage into "inherited" and disarm the
        # gate cause for exactly the debt the revival exists to finish
        # (review finding). Only a fresh start measures inheritance.
        if "--baseline" in argv:
            source = str(data.get("source") or "")
            if source in ("resume", "compact") and _baseline_path(sid).exists():
                return 0
            _passed, failing, _ftext = _run_gate(root)
            try:
                _baseline_path(sid).write_text(json.dumps(sorted(failing)))
            except Exception:
                pass
            return 0

        # Promise-guard input (independent of tree state): the narrate-instead-of-act
        # stall fires with a CLEAN tree just as often (a stalling agent has usually
        # committed everything and then narrates instead of dispatching).
        transcript_p = str(data.get("transcript_path") or "")
        authored_map: dict[str, int] = {}
        if transcript_p:
            try:
                authored_map = _session_files(transcript_p, root)
            except Exception:
                authored_map = {}
        # `waived` collects stalls a sanctioned marker waved through; `warned` collects
        # causes whose anti-trap cap was exhausted this turn. Both are read only at the
        # exits, so nothing is emitted before the decision is actually made.
        waived: list[tuple[str, str]] = []
        warned: list[str] = []
        stall = (
            _detect_stall(transcript_p, root, set(authored_map), waived) if transcript_p else None
        )

        def _stall_gate() -> int:
            """Final causes on an otherwise-allowed stop: the PUSH law (committed
            work must be off-box — routine-push directive), the promise-guard, then
            the in-flight COMMAND RUN RECORD. Independent counter slots, same
            reset-when-false + warn-through shape."""
            counter = _counter_path(sid)
            g, c, s_att, p_att, r_att, v_att = _read_counters(counter)
            run = _run_record(sid)
            run_active = bool(run) and (run or {}).get("state") == "running"
            # FLOORED, not the lifetime set — see `_baseline_floor`
            ahead = _ahead_of_upstream(
                root, set(_this_sessions_edits(authored_map, _baseline_floor(sid)))
            )
            p_action, p_att = decide_stall(bool(ahead), p_att)
            if p_action == "block_stall":
                counter.write_text(
                    f"{g},{c},{s_att if stall else 0},{p_att},{r_att if run_active else 0},{v_att}"
                )
                reason = (
                    f"UNPUSHED WORK (attempt {p_att}/{CAP}). {ahead} committed commit(s) on "
                    "this branch are not on origin — an unpushed task is an "
                    "OFF-BOX-UNPROTECTED task (CLAUDE.md § EXIT): push YOUR work now "
                    "(`git push`). Rejected? dirty tree → defer (wip-net protects) · clean "
                    "tree → `git pull --rebase=merges` then push · conflict → "
                    "`git rebase --abort` + report · NEVER --force."
                )
                _kaizen(
                    "stop_block",
                    ev_sid,
                    cause="unpushed",
                    outcome="blocked",
                    attempt=p_att,
                    ahead=ahead,
                )
                sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
                return 0
            if p_action == "allow_warn_stall":
                sys.stderr.write(
                    f"Work still unpushed after {CAP} blocked stops — stopping anyway; "
                    "refs/wip is the only off-box copy until someone pushes.\n"
                )
                warned.append("unpushed")
                _kaizen(
                    "stop_block", ev_sid, cause="unpushed", outcome="warned_through", attempt=CAP
                )
            s_action, s_att = decide_stall(bool(stall), s_att)
            if s_action in ("allow", "allow_warn_stall"):
                if s_action == "allow_warn_stall":
                    sys.stderr.write(
                        f"Final message still ends in a stall after {CAP} blocked stops — "
                        "stopping anyway.\n"
                    )
                    warned.append("promise-stall")
                    _kaizen(
                        "stop_block",
                        ev_sid,
                        cause="promise-stall",
                        outcome="warned_through",
                        attempt=CAP,
                    )
                # FIFTH cause, last word: a command run still in flight. It applies
                # regardless of tree state — an agent that committed, pushed and
                # narrated nothing can still be abandoning /fabrik-review at round 3.
                r_action, r_att = decide_stall(run_active, r_att)
                if r_action == "block_stall":
                    counter.write_text(f"{g},{c},0,{p_att},{r_att},{v_att}")
                    _kaizen(
                        "stop_block",
                        ev_sid,
                        cause="run-record",
                        outcome="blocked",
                        attempt=r_att,
                        command=str((run or {}).get("command") or "?"),
                    )
                    sys.stdout.write(
                        json.dumps(
                            {
                                "decision": "block",
                                "reason": _run_block_reason(run or {}, r_att),
                            }
                        )
                        + "\n"
                    )
                    return 0
                if r_action == "allow_warn_stall":
                    sys.stderr.write(
                        f"A command run is STILL marked running after {CAP} blocked stops — "
                        "stopping anyway. Close it: python3 scripts/command_run.py "
                        "done --command <name> --evidence … | blocked --command <name> --reason …\n"
                    )
                    warned.append("run-record")
                    _kaizen(
                        "stop_block",
                        ev_sid,
                        cause="run-record",
                        outcome="warned_through",
                        attempt=CAP,
                    )
                # SIXTH cause — spontaneous code changes owe a review (operator, 2026-08-29).
                # "Spontaneous" is mechanical: every command opens a run record (corpus
                # predicate 5), so code edits with NO record at all are plain-chat work by
                # construction. The remedy is the light /fabrik-review-scoped; running it
                # creates the record, which clears this cause on the next stop.
                # PER CHANGE (2026-09-06): count only this session's code authored OUTSIDE every
                # window a command of the session covered (the record's `covered` ledger + the
                # live window, edits before the SessionStart baseline excluded). The
                # 01M1NTNCFEWMP82YQFGNN6NHYP shape (reviewed, closed, idle under a hold) stays
                # allowed: idle authors nothing after the close.
                _rec = _run_record_raw(sid)
                # ONE spelling for "this session's floor" across all three consumers. This site
                # was already safe — `_unreviewed_spontaneous_files` floors internally — but a
                # raw read sitting beside two floored ones is how the 1-of-N class recurs. The
                # double application is safe but NOT strictly idempotent: `_sixth_cause_floor`
                # takes a `max()` against `now - 24h`, and `now` advances between calls, so
                # `f(f(x))` exceeds `f(x)` by the call gap — microseconds here, and always in the
                # SAFE direction (a higher floor drops more, never fewer, ancient edits).
                _floor = _baseline_floor(sid)
                _unreviewed_files = _unreviewed_spontaneous_files(_rec, authored_map, _floor, sid)
                _unreviewed = len(_unreviewed_files)
                v_action, v_att = decide_review(_unreviewed, v_att)
                if v_action == "block_review":
                    counter.write_text(f"{g},{c},0,{p_att},{r_att},{v_att}")
                    _kaizen(
                        "stop_block",
                        ev_sid,
                        cause="unreviewed-spontaneous",
                        outcome="blocked",
                        attempt=v_att,
                    )
                    sys.stdout.write(
                        json.dumps(
                            {
                                "decision": "block",
                                "reason": (
                                    f"UNREVIEWED SPONTANEOUS WORK (attempt {v_att}/{CAP}). This "
                                    f"session authored {_unreviewed} code file(s) — edited "
                                    f"{_edit_age_phrase()}, or carrying no readable timestamp, "
                                    "which counts because unknown is not covered — and OUTSIDE every "
                                    "command run's covered window (before the first started, "
                                    "between runs, or after the last closed) — plain-chat work "
                                    "that skipped every review contract. "
                                    + _named_files_phrase(_unreviewed_files)
                                    + "Run "
                                    "`/fabrik-review-scoped` (minutes: diff-scoped, same "
                                    "convergence spine, fix-in-run) — or the full "
                                    "`/fabrik-review` for gate/hook/enforcement, auth/schema/"
                                    "migration, or multi-file surfaces. Its run record is what "
                                    "clears this block."
                                ),
                            }
                        )
                        + "\n"
                    )
                    return 0
                if v_action == "allow_warn_review":
                    sys.stderr.write(
                        f"Spontaneous code edits still unreviewed after {CAP} blocked stops — "
                        "stopping anyway. The review is still owed.\n"
                    )
                    warned.append("unreviewed-spontaneous")
                    _kaizen(
                        "stop_block",
                        ev_sid,
                        cause="unreviewed-spontaneous",
                        outcome="warned_through",
                        attempt=CAP,
                    )
                if g == 0 and c == 0 and p_att == 0 and r_att == 0 and v_att == 0:
                    counter.unlink(missing_ok=True)
                else:
                    counter.write_text(f"{g},{c},0,{p_att},{r_att},{v_att}")
                # The ONE pass-through: every enforcement cause declined to block, so
                # this Stop really ends the turn.
                _kaizen_pass(ev_sid, transcript_p, waived, warned)
                return 0
            counter.write_text(f"{g},{c},{s_att},{p_att},{r_att if run_active else 0},{v_att}")
            kind, snippet = stall  # type: ignore[misc]
            if kind == "final-block-incomplete":
                _missing = snippet.split("missing:", 1)[-1].strip()
                what = (
                    f"ends with an INCOMPLETE FINAL OUTPUT block ({snippet}) — the block is the "
                    "same SEVEN lines in every repo (D-173): GATE: · DOCS UPDATED: · CHANGELOG: · "
                    f"LESSONS LEARNT: · DONE: · NEXT: · FEEDBACK: — add the missing line(s): {_missing}"
                    + (
                        " (`FEEDBACK: <what you filed about the commands/skills/rules machinery, "
                        "to whom (mail id / committed path) | none — the machinery surfaces this "
                        "run exercised>` is the 7th, D-059)"
                        if "FEEDBACK:" in _missing
                        else ""
                    )
                )
            else:
                what = (
                    f'promises an action ("{snippet}") that was never dispatched'
                    if kind == "promise"
                    else f'asks permission ("{snippet}") that the active plan/review contract already grants'
                )
            reason = (
                f"STALL DETECTED (attempt {s_att}/{CAP}). Your final message {what}. "
                "Do the work NOW — dispatch it or run it in this same turn — instead of "
                "narrating or asking (CLAUDE.md: run every owed pass unprompted; the "
                "checkpoint-stall is a named live defect). Legitimate stops must name "
                "their human gate explicitly (design approval, Gate 2, operator "
                "decision, or a formatted BLOCKED: escalation)."
            )
            _kaizen(
                "stop_block",
                ev_sid,
                cause="promise-stall",
                outcome="blocked",
                attempt=s_att,
                kind=kind,
            )
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
            return 0

        # Stop: gate/commit causes only apply when there's actual uncommitted work;
        # the promise-guard applies regardless.
        if not _git_dirty(root):
            return _stall_gate()

        baseline_file = _baseline_path(sid)
        if not baseline_file.exists():
            # No baseline (SessionStart didn't run / older session) → we can't tell
            # inherited debt from new breakage, so fail-open rather than false-block —
            # but the promise-guard needs no baseline.
            return _stall_gate()
        try:
            baseline = set(json.loads(baseline_file.read_text()))
        except Exception:
            # Corrupt baseline → gate/commit causes can't run, but the promise-guard
            # must not be disabled for the rest of the session (review finding).
            return _stall_gate()

        _passed, failing, gate_outputs = _run_gate(root)
        new_failures = failing - baseline

        # Session-authored files still uncommitted? (CLAUDE.md § EXIT: an
        # uncommitted task is an unfinished task.) Fail-open on any gap.
        own_uncommitted: set[str] = set()
        # Reuse the stall path's parse — _session_files costs ~1s on a large
        # transcript; three passes per Stop was a measured review finding.
        authored: dict[str, int] = authored_map
        transcript = str(data.get("transcript_path") or "")
        if transcript:
            dirty = _dirty_paths(root)
            for rel, edit_ts in authored.items():
                if rel not in dirty:
                    continue
                # The session's last edit already COMMITTED → today's dirt on the
                # same file belongs to someone else (pipeline/sibling), not this
                # session. Only an edit NEWER than the file's last commit counts.
                if edit_ts and _last_commit_ts(root, rel) >= edit_ts:
                    continue
                own_uncommitted.add(rel)

        # Attribute NEW gate failures by CITED PATH, not just check name: on shared
        # master a sibling's staged/dirty files flip a check red mid-session, and
        # check-name comparison alone pins it on this session — which then CANNOT fix
        # it without violating the shared-tree contract (never commit/document/revert
        # a sibling's WIP). Attribution scopes to the NEW failures' own outputs only,
        # compares normalized path tokens (never substrings), ignores the routine
        # governance files every session writes, and treats a path-less output as
        # INDETERMINATE (keep blocking up to the cap) rather than waving it through.
        # Runs only when we actually know the session's files (transcript present).
        if new_failures and authored:
            # ⚠️ `_baseline_floor`, not the raw mtime. This site carried BOTH halves of the
            # defect the helper exists to close: a `0.0` fallback, which `_failure_cites_session`
            # reads as "no floor" through the same `not session_floor` expression as
            # `_this_sessions_edits`; and a RAW baseline, which on a resumed transcript is months
            # old and filters nothing. The sixth cause's site two hundred lines up was already
            # safe because its callee floors internally (`_unreviewed_spontaneous_files` →
            # `_sixth_cause_floor`); this one had no such backstop, so a sibling's dirty file
            # could be attributed to a path this session touched three months ago and BLOCK.
            session_floor = _baseline_floor(sid)
            new_outputs = [gate_outputs.get(n, "") for n in new_failures]
            verdict = _failure_cites_session(new_outputs, authored, session_floor)
            if verdict is False:
                sys.stderr.write(
                    "final_gate has NEW failing check(s) "
                    f"({', '.join(sorted(new_failures))}) whose cited paths include no "
                    "file this session authored — shared-tree cause (a sibling's "
                    "uncommitted work); not blocking this session on it.\n"
                )
                new_failures = set()

        counter = _counter_path(sid)
        # SIX slots since the sixth cause (6f368aac) — this unpack kept FIVE and crashed
        # EVERY Stop that reached it, fail-opening the gate/commit/push causes box-wide
        # for ~12h until the full suite surfaced it (13 reds). The review slot is
        # PRESERVED on this path, never zeroed: each cause owns its own slot.
        (
            gate_attempts,
            commit_attempts,
            stall_attempts,
            push_attempts,
            run_attempts,
            review_attempts,
        ) = _read_counters(counter)

        action, gate_attempts, commit_attempts = decide(
            True,
            bool(new_failures),
            gate_attempts,
            own_uncommitted=bool(own_uncommitted),
            commit_attempts=commit_attempts,
        )

        if action in ("allow", "allow_warn_gate", "allow_warn_commit"):
            if action == "allow_warn_gate":
                sys.stderr.write(
                    f"final_gate still RED after {CAP} attempts — stopping anyway. "
                    "Run: python scripts/final_gate.py --lean --json\n"
                )
                warned.append("gate-red")
                _kaizen(
                    "stop_block", ev_sid, cause="gate-red", outcome="warned_through", attempt=CAP
                )
            elif action == "allow_warn_commit":
                sys.stderr.write(
                    f"Session-authored files STILL UNCOMMITTED after {CAP} blocked stops — "
                    "stopping anyway. Commit your own work: git commit -m <msg> -- <your files> "
                    "(pathspecs + Agent Provenance Trailers).\n"
                )
                warned.append("uncommitted")
                _kaizen(
                    "stop_block",
                    ev_sid,
                    cause="uncommitted",
                    outcome="warned_through",
                    attempt=CAP,
                )
            # gate/commit causes resolved (or capped) → reset their counters, then
            # the push law + promise-guard still have the last word on THIS stop.
            counter.write_text(
                f"0,0,{stall_attempts},{push_attempts},{run_attempts},{review_attempts}"
            )
            return _stall_gate()

        # Reset-when-cause-false applies to the stall AND push slots here too: a
        # gate/commit block must not STRAND a stale count that later shortens (or
        # mis-numbers) a brand-new streak (review finding — the same regression
        # class decide()'s own docstring documents; the p-slot edition was caught
        # by the routine-push whole-plan review).
        _run_live = (_run_record(sid) or {}).get("state") == "running"
        counter.write_text(
            f"{gate_attempts},{commit_attempts},{stall_attempts if stall else 0},"
            # the SAME scoped question as the block site — a bare call now answers None
            # (indeterminate) and would reset this streak on every unrelated gate/commit
            # block, restarting the 3-attempt ladder in the trapping direction
            f"{push_attempts if _ahead_of_upstream(root, set(_this_sessions_edits(authored_map, _baseline_floor(sid)))) else 0},"
            f"{run_attempts if _run_live else 0},{review_attempts}"
        )
        if action == "block_commit":
            listed = ", ".join(sorted(own_uncommitted)[:8])
            more = len(own_uncommitted) - 8
            gate_state = (
                "The gate is green" if _passed else "No NEW gate failures (inherited debt remains)"
            )
            reason = (
                f"DEFINITION OF DONE NOT MET (attempt {commit_attempts}/{CAP}). {gate_state} "
                "but files THIS session authored are still uncommitted — an "
                "uncommitted task is an UNFINISHED task (CLAUDE.md § EXIT): "
                f"{listed}{f' (+{more} more)' if more > 0 else ''}. Commit YOUR OWN work "
                "now with explicit pathspecs + Agent Provenance Trailers "
                "(git commit -m <msg> -- <your files>); never bundle files you didn't author. "
                "Then PUSH it — commit-and-push is the task-end law (never --force)."
            )
            _kaizen(
                "stop_block",
                ev_sid,
                cause="uncommitted",
                outcome="blocked",
                attempt=commit_attempts,
                files=len(own_uncommitted),
            )
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
            return 0
        reason = (
            f"DEFINITION OF DONE NOT MET (attempt {gate_attempts}/{CAP}). This session "
            "introduced gate failures that were not present at session start — the task "
            'is not complete until `final_gate.py --lean` shows "status":"success". '
            f"New failing checks: {', '.join(sorted(new_failures))}. "
            "Fix them, then finish. Run: python scripts/final_gate.py --lean --json"
        )
        _kaizen(
            "stop_block",
            ev_sid,
            cause="gate-red",
            outcome="blocked",
            attempt=gate_attempts,
            checks=sorted(new_failures),
        )
        # stdout is the hook's channel to Claude Code (not logging) — write directly
        # so the print/console.log ban doesn't false-positive on a required emit.
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
        return 0
    except Exception as e:  # fail-open — never trap the session on a hook bug
        sys.stderr.write(f"[final_gate_stop hook] error, allowing stop: {e}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
