#!/usr/bin/env python3
# AFTER-EDIT: tests/test_session_orient_hook.py, docs/workstation/hooks-index.md
"""SessionStart orientation (Fabrik-synced, stdlib-only, fail-open).

Every session starts with an explicit orientation block so the agent is AWARE
of what is connected to it before any work: the governing CLAUDE.md (hub
contract in /opt/fabrik, synced template copy in projects — the text branches
on repo identity), the persistent MEMORY.md index, the session-recall MCP
tools, and the enforcement mesh (Stop hook, prompt router, final_gate).
CLAUDE.md and MEMORY.md are harness-auto-loaded — this hook does not re-read
them; it BINDS the agent to act on them and surfaces their state. Fail-open:
any error exits 0 (a broken orientation must never block a session).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Read at most this much of MEMORY.md when counting entries (bound reads by
# bytes — a pathological index must not spike every SessionStart).
_MEMORY_READ_BYTES = 256 * 1024

# --- Kaizen M1 event stream (additive sensor, fail-open at the IMPORT layer) ---
# The emitter lives at ONE place per box, so both candidates are tried: this repo's own
# copy first, then the hub's. The degraded state is the module being unimportable at
# BOTH — a box that has no kaizen_events at all — and there the hook must behave
# EXACTLY as it did before the sensor existed. Hence the guarded import (never an
# ImportError reaching a session) and a second guard at every emit site. Paths are
# APPENDED (stdlib always wins) and only when absent (idempotent under re-import).
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

# SessionStart's whole budget is 10s (.claude/settings.json). A hung git probe must
# cost this hook milliseconds, not the orientation itself.
_PROBE_TIMEOUT_S = 2.0

_MANIFEST_REL = "scripts/fabrik_synced_manifest.py"


def _git_layout(cwd: str) -> tuple[str, str, str]:
    """(toplevel, git dir, common dir) of the repo holding `cwd`, each realpath'd — or three
    empty strings on ANY failure (not a repo, git absent, the probe timeout, a NUL in `cwd`).
    ONE `git rev-parse` per SessionStart, shared by every reader below; a main checkout is the
    tree whose git dir IS its common dir, a linked worktree the one whose git dir is not."""
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                cwd,
                "rev-parse",
                "--path-format=absolute",
                "--show-toplevel",
                "--git-dir",
                "--git-common-dir",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
            check=False,
        )
        lines = out.stdout.splitlines()
        if out.returncode != 0 or len(lines) != 3 or not all(lines):
            return "", "", ""
        top, gdir, common = (os.path.realpath(x) for x in lines)
        return top, gdir, common
    except Exception:
        return "", "", ""


def _is_hub(cwd: str, layout: tuple[str, str, str] | None = None) -> bool:
    """Hub identity (spec 2026-09-29 hub-worktree cut-over, D4): the manifest is in the tree AND
    the git common dir's parent is the hub path, so a hub WORKTREE is the hub. The same rule as
    `scripts/final_gate.py::_is_hub` and `scripts/enforcement/check_vendored_drift.py::_is_hub`,
    re-implemented because this hook is standalone and fleet-synced and imports neither. The
    mirror stays a project: a project repo carries no manifest, and one that did would still have
    its OWN common dir. ⚠️ Unlike both sources the manifest is checked BEFORE the hub-path
    short-circuit, so no value of the seam can make a manifest-less repo the hub.
    `FABRIK_ORIENT_HUB_ROOT` is this hook's own test seam for the hub path (default
    `/opt/fabrik`) — NOT `FABRIK_HUB_ROOT`, which `command_run.py` reads for another purpose."""
    try:
        if not (Path(cwd) / _MANIFEST_REL).is_file():
            return False
        hub = os.path.realpath(os.environ.get("FABRIK_ORIENT_HUB_ROOT") or "/opt/fabrik")
        if os.path.realpath(cwd) == hub:
            return True
        common = (layout or _git_layout(cwd))[2]  # probed only when the manifest is there
        return bool(common) and os.path.dirname(common) == hub
    except Exception:
        return False


@contextlib.contextmanager
def _quiet():
    """Mute stderr for the duration — hook-side, so `kaizen_events` keeps its own
    honest `_warn` channel for every OTHER caller. A hook's stderr is part of its
    observable output, and the sensor must not add a byte to it."""
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


def _kaizen(event: str, sid: object, probe_cwd: str | None = None, **fields: object) -> None:
    """Fire-and-forget event. Module absent or ANY failure → silent no-op.

    ``emit`` already swallows everything, but the outermost guard lives HERE so a
    future emitter that does raise still cannot cost a session its orientation.
    ``probe_cwd`` pins exposure to the PAYLOAD's project rather than this process's
    cwd — a hook subprocess has no guarantee the two agree.
    """
    if not kaizen_events:
        return
    try:
        with _quiet():
            exp = kaizen_events.exposure(cwd=probe_cwd, probe_timeout_s=_PROBE_TIMEOUT_S)
            kaizen_events.emit(
                event, kaizen_events.resolve_sid(sid), exposure_override=exp, **fields
            )
    except Exception:
        pass


def _instrumented(cwd: str) -> bool:
    """Does a Stop hook run here? The sensors must instrument ONE universe.

    `final_gate_stop.py` returns early when `scripts/final_gate.py` is absent, so a
    `session_start` emitted outside that universe is a session the collector can never
    see closed — a fabricated hole in exactly the metric this stream exists to measure.
    """
    try:
        return (Path(cwd) / "scripts" / "final_gate.py").exists()
    except OSError:
        return False


def _memory_line(cwd: str) -> str:
    # Harness project-key convention: '/' AND '.' become '-'
    # (ground truth: ~/.claude/projects/-opt-…--rec-…-jpg style keys).
    proj_key = cwd.replace("/", "-").replace(".", "-")
    idx = (
        Path(os.environ.get("HOME", str(Path.home())))
        / ".claude/projects"
        / proj_key
        / "memory/MEMORY.md"
    )
    try:
        if idx.is_file():
            with open(idx, encoding="utf-8", errors="replace") as f:
                head = f.read(_MEMORY_READ_BYTES)
            entries = sum(1 for line in head.splitlines() if line.lstrip().startswith("- "))
            more = "+" if len(head) == _MEMORY_READ_BYTES else ""
            return (
                f"- **Memory:** your MEMORY.md index is loaded ({entries}{more} entries). Recalled"
                " facts in system-reminders are background truth-at-write-time — verify named"
                " files/flags still exist. Save new durable facts per the memory contract; update,"
                " don't duplicate."
            )
    except OSError:
        pass
    return (
        "- **Memory:** no memory index yet for this project — when you learn a durable fact"
        " (operator preference, project constraint, feedback), write it per the memory contract."
    )


# ⚠️ KEY ON THE LEDGER ROW AND ON LIVE SESSIONS — never on `docs/development/PLANS.md`.
# Two defects drove this, both executed. (1) The PLANS.md `<!-- Merge owner: … -->` line is
# RENDERED from the ledger row (`docs_updater.py::_merge_owner_header_line`), so keying on it is
# a free, silent bypass: delete that HTML comment and `read_merge_owner()` still returns the
# owner while this advisory goes quiet for good. The ledger row is IMMUTABLE by contract, so
# silencing THIS means an edit the contract forbids — loud by construction. (2) Keying on
# ADOPTION at all misses the repos that need it most: `/opt/iterative_image_editor` runs three
# lanes with 14 plan-locks and commits daily, and carries neither a marker nor a ledger row
# (executed 2026-09-16), so no adoption key can ever reach it. A repo is multi-agent when
# several agents are IN it — which the /proc scan already answers for `_sessions_line`.
# ⚠️ COBRA (D-253): the cheapest way to satisfy this without naming anyone is to close a window
# so the live count drops below 2 — but that also ends the concurrency the warning is about, so
# the cheap path IS the outcome. The other cheap path is naming every session the same string;
# `check_commit_trailers.py::_warn_agent_name_mismatch` compares the SIGNED name against the
# resolved one, so two sessions sharing one name still mis-sign and still warn.
# The grammar is single-sourced at `docs_updater.py::MERGE_OWNER_RE` and `decisions.py::MERGE_OWNER_RE` (cited by SYMBOL: a line number in a file this change itself grows is drift by construction — :940 was already wrong for :938 when it was written); this hook is
# standalone and fleet-synced so it cannot import either — `tests/test_session_orient_hook.py`
# pins the copy against both, the precedent `command_run.py` already set for its axis list.
# C3: `(?!UNDECLARED)` is NOT decoration — `--adopt` cannot mint that name (`_ADOPT_NAME_RE`)
# but a HUMAN writes `MERGE OWNER: UNDECLARED — we un-adopted` as an ordinary un-adoption
# row, and without the lookahead this hook then announces `UNDECLARED` as the owner.
# Case-insensitive because the phrase match is, so `undeclared` cannot sneak past it.
# TOKEN-exact: `undeclared-team` is a real owner name, and `decisions.py` captures the whole token.
# A trailing full stop is punctuation (`UNDECLARED.` is un-adoption prose); a dot before a name
# character is not (`UNDECLARED.team` is an owner).
# ⚠️ The CAPTURE is byte-identical to both single sources — no length quantifier of
# our own. `docs_updater.py` states the permissiveness is deliberate ("stays permissive so
# it can still READ a name minted before this tightening"), so a narrower copy here would be
# a silent third dialect; the length cap belongs at RENDER time and lives in `_identity_line`.
# W-076ff4a9: a changed owner is a NEW row whose what-cell OPENS a supersedes clause (the ledger's
# own law, in any of its real spellings), so that prefix is optional before the phrase — shared
# byte for byte with both sources.
# The prefix ends at the cell's FIRST `:` or `.` (the qualifier may hold neither), and the phrase
# must follow it at once — so it cannot reach a `MERGE OWNER:` written later in the prose.
# After a supersedes clause the phrase must be the exact UPPERCASE `MERGE OWNER:` (the lookahead's
# `(?-i:...)`): a prose sentence such as `Supersedes D-001.** Merge owner: rotated weekly` is not a
# declaration. A bare row with no prefix keeps the case-insensitive phrase it always had.
_SUPERSEDES_PREFIX = r"(?:supersedes\s+D-\d+[^:.]{0,160}[:.][\s*]*(?=(?-i:MERGE OWNER:)))?"
_MERGE_OWNER_RE = re.compile(
    r"^\**\s*"
    + _SUPERSEDES_PREFIX
    + r"MERGE OWNER:\s*(?!UNDECLARED(?![A-Za-z0-9_@-]|\.[A-Za-z0-9_@-]))([A-Za-z0-9][A-Za-z0-9_.@-]*)",
    re.I,
)
_LEDGER_ROW_RE = re.compile(r"^\|\s*D-\d+\s*\|", re.I)
# Cell decoding ported from `decisions.py::_rows` / `_code_span_ranges` / `_ESCAPABLE` (this hook
# cannot import it); `tests/test_session_orient_hook.py` compares the result to the real
# `decisions.py --merge-owner` over escaped-pipe, code-span and escaped-name ledgers.
_ESCAPABLE = frozenset("""!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~""")  # GFM: punctuation only
_UNDECLARED_RE = re.compile(
    r"^\**\s*"
    + _SUPERSEDES_PREFIX
    + r"MERGE OWNER:\s*UNDECLARED(?![A-Za-z0-9_@-]|\.[A-Za-z0-9_@-])",
    re.I,
)


def _code_span_ranges(s: str) -> list[tuple[int, int]]:
    """Half-open ranges of the CommonMark code spans in `s`: a run of N backticks is closed only
    by a run of exactly N; an unclosed run is literal and opens nothing."""
    spans: list[tuple[int, int]] = []
    i, n = 0, len(s)
    while i < n:
        if s[i] != "`":
            i += 1
            continue
        j = i
        while j < n and s[j] == "`":
            j += 1
        k = j
        while k < n:
            if s[k] != "`":
                k += 1
                continue
            m = k
            while m < n and s[m] == "`":
                m += 1
            if m - k == j - i:
                spans.append((i, m))
                i = m
                break
            k = m
        else:
            i = j
    return spans


def _cells(row: str) -> list[str]:
    """A table row's cells, GFM-decoded: `\\|` is CONTENT (inside a code span too), and `\\\\|`
    is a literal backslash then a REAL separator — so the scan consumes each escape rather than
    looking behind. `\\X` for other punctuation decodes to X outside a code span; a backslash
    before anything else stays literal."""
    s = row.strip().strip("|")
    if "\\" not in s:  # no escape at all: the scan below reduces to exactly this split
        return [c.strip() for c in s.split("|")]
    spans = _code_span_ranges(s)
    cells: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if c == "\\" and nxt == "|":
            buf.append("|")
            i += 2
        elif c == "\\" and nxt and nxt in _ESCAPABLE and not any(a <= i < b for a, b in spans):
            buf.append(nxt)
            i += 2
        elif c == "\\" and nxt:
            buf.append(c + nxt)
            i += 2
        elif c == "|":
            cells.append("".join(buf).strip())
            buf = []
            i += 1
        else:
            buf.append(c)
            i += 1
    cells.append("".join(buf).strip())
    return cells


def _owner_in(text: str) -> str:
    """The HIGHEST-id `MERGE OWNER:` row's name in `text` (column 4 of a `| D-NNN |` row, an
    optional `supersedes D-NNN:` prefix allowed), or "". Position never decides: the ledger's
    header says row order is a convention nothing reads (W-076ff4a9). An un-adoption row
    (`MERGE OWNER: UNDECLARED`) is a row too: when its id is highest, nobody owns the repo —
    `decisions.py --merge-owner` answers `UNDECLARED` at exit 3 for it."""
    best = -1
    found = ""
    for line in text.splitlines():
        s = line.strip()
        if not _LEDGER_ROW_RE.match(s):
            continue
        cells = _cells(s)
        if len(cells) < 4:
            continue
        if _UNDECLARED_RE.match(cells[3]):
            name = ""
        else:
            m = _MERGE_OWNER_RE.match(cells[3])
            if not m:
                continue
            name = m.group(1)
        num = _row_id(cells[0])
        if num >= best:  # an (illegal) duplicate id resolves to the later row, as before
            best, found = num, name
    return found


def _row_id(cell: str) -> int:
    """The numeric part of a `D-NNN` id cell; -1 when the decoded cell carries none."""
    m = re.match(r"D-(\d+)", cell, re.I)
    return int(m.group(1)) if m else -1


# The ONE ledger read both owner consumers use — the identity line and the move line (W-076ff4a9).
# It reads the WHOLE ledger, as `decisions.py --merge-owner` (the named source) does: the owner is
# the highest-id row WHEREVER it sits, so any window can hide the winner. An earlier head+tail 64 KB
# window here returned a stale lower-id owner for a row in the middle of a >128 KB ledger (the hub's
# measured 759 KB at 9c82f26af; 4 of 49 fleet ledgers exceeded one window on 2026-09-16). It is re-implemented here,
# not shelled out: that subprocess measured 165 ms on the hub against a ~55 ms hook, and
# `tests/test_session_orient_hook.py` pins this reader's answer to decisions.py's. The phrase
# prefilter hands `_owner_in` only the lines that mention it at all, so the hub's ledger costs one
# byte scan rather than a decode and split of every row (measured 6 ms -> under 1 ms).
# The cap (16 MB, ~20x the largest ledger) only bounds a pathological file; past it the line the
# cut lands in is dropped, so a cut inside an owner name can never render the TRUNCATED name.
_LEDGER_MAX_BYTES = 16 * 1024 * 1024


def _ledger_merge_owner(top: str) -> str:
    """The merge owner the ledger at `<top>/docs/DECISIONS.md` declares (highest id wins), or "".
    Fails OPEN: a missing, unreadable or undecodable ledger answers "" like an unadopted repo."""
    try:
        path = Path(top) / "docs" / "DECISIONS.md"
        if not path.is_file():
            return ""
        with open(path, "rb") as fh:
            raw = fh.read(_LEDGER_MAX_BYTES + 1)
        if len(raw) > _LEDGER_MAX_BYTES:  # over the cap: drop the line the cut lands in
            raw = raw[: raw.rfind(b"\n", 0, _LEDGER_MAX_BYTES) + 1]
        low = raw.lower()  # ASCII-only lowering: every offset below indexes `raw` unchanged
        lines = []
        hit = low.find(b"merge owner")
        while hit != -1:
            start = raw.rfind(b"\n", 0, hit) + 1
            end = raw.find(b"\n", hit)
            end = end if end != -1 else len(raw)
            lines.append(raw[start:end].decode("utf-8", errors="replace"))
            hit = low.find(b"merge owner", end)
        return _owner_in("\n".join(lines))
    except Exception:
        return ""


_AGENT_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent.py::_NAME_RE, used with fullmatch
# The store is trimmed to 30 days by its writer, so the WHOLE store is read up to this cap; past
# it the TAIL is read (the newest rows) and the line the cut lands in is dropped.
_IDENTITY_READ_BYTES = 4 * 1024 * 1024


def _identity_rows() -> list[dict]:
    """The `whoami_agent.py` binding store's rows (its layout: one JSON object per line at
    `$AGENT_IDENTITY_FILE`, else `$HOME/.claude/state/agent-identity.jsonl`), oldest first. A row
    needs a non-empty STRING `session_id`; anything else is skipped. Regular files only: a FIFO
    would block this hook forever."""
    try:
        raw_env = os.environ.get("AGENT_IDENTITY_FILE")
        path = (
            Path(raw_env)
            if raw_env
            else Path(os.environ.get("HOME", str(Path.home())))
            / ".claude/state/agent-identity.jsonl"
        )
        if not path.is_file():
            return []
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > _IDENTITY_READ_BYTES:
                # one byte before the cut, so a cut landing exactly on a line start keeps it
                fh.seek(size - _IDENTITY_READ_BYTES - 1)
                data = fh.read(_IDENTITY_READ_BYTES + 1)
                data = data[data.find(b"\n") + 1 :]  # drop through the partial line
            else:
                data = fh.read()
        lines = data.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("session_id"), str) and row["session_id"]:
            rows.append(row)
    return rows


def _resolved_name(sid: str, rows: list[dict]) -> str:
    """`whoami_agent.py::resolve_agent_name`'s order: a well-formed `CLAUDE_AGENT`, else this
    session's LAST binding row, else "". `sid` is the payload's raw session id, falling back to
    `CLAUDE_CODE_SESSION_ID` (the variable the writer keys on). The ONE validity test every
    advisory here uses: `CLAUDE_AGENT=ALPHA` is unnamed to all of them."""
    env = (os.environ.get("CLAUDE_AGENT") or "").strip()
    if _AGENT_NAME_RE.fullmatch(env):
        return env
    sid = sid or (os.environ.get("CLAUDE_CODE_SESSION_ID") or "").strip()
    name = ""
    for row in rows:
        if sid and row.get("session_id") == sid:
            cand = str(row.get("name") or "")
            if _AGENT_NAME_RE.fullmatch(cand):
                name = cand
    return name


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _binding_live(row: dict) -> bool:
    """`whoami_agent.py::_pid_alive_same_start`: the pid is alive AND started when the row says.
    The pid must be a real int (`True` is 1 — pid 1 is always alive); a row with no start time is
    pid-only, as the writer treats it."""
    try:
        pid = row.get("pid")
        if not _is_int(pid) or pid <= 0 or not Path(f"/proc/{pid}").is_dir():
            return False
        was = row.get("pid_start")
        if was is None:
            return True
        if not _is_int(was):
            return False
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        return int(raw[raw.rindex(")") + 1 :].split()[19]) == was
    except Exception:
        return False


def _model_line(
    layout: tuple[str, str, str], live: int, hub: bool, name: str, rows: list[dict]
) -> tuple[str, bool]:
    """The multi-agent model at SessionStart (spec 2026-09-29, D1 and D5 (a)), in every repo AND
    the hub: (1) the main checkout of an UNADOPTED repo is prompted to `--adopt` at ANY session
    count; (2) in an adopted main checkout, a session whose resolved `name` is not the merge owner
    is told to move into its worktree (an unnamed one to bind first); (3) the repo's live
    `whoami_agent.py` bindings are listed. Returns (text, instructed): `instructed` is True when
    (2) printed, and then `_identity_line` and `_sessions_line` yield to it — ONE instruction.
    ⚠️ COBRA (D-253): the cheapest way to silence (2) is to bind yourself AS the merge owner;
    (3) is the counter — the owner's name held by two sessions is then visible to both. Stated
    limit: a session named at launch by `CLAUDE_AGENT` writes no binding and is not listed.
    Any failure prints nothing new."""
    try:
        top, gdir, common = layout
        if not top:
            return "", False
        out = ""
        instructed = False
        if gdir == common:  # the main checkout
            owner = _ledger_merge_owner(top)[:32]  # render cap, as in `_identity_line`
            if not owner:
                # outside the hub, >=2 live sessions already get `--adopt` from `_sessions_line`
                if (Path(top) / "scripts" / "docs_updater.py").is_file() and (hub or live < 2):
                    flag = " --single-window" if live < 2 else ""
                    out += (
                        "- ⚠️ **This repo has not adopted the multi-agent model** (no `MERGE"
                        " OWNER:` row in `docs/DECISIONS.md`). Every repo runs it — agent-1 here in"
                        " the main checkout, agents 2..N in `.claude/worktrees/<name>` — so adopt"
                        " it now: `python scripts/docs_updater.py"
                        f" --adopt <names>{flag}` (the first name becomes the merge owner).\n"
                    )
            elif not name:
                instructed = True
                out += (
                    f"- ⚠️ **This session is UNNAMED in the main checkout, and the merge owner"
                    f" is `{owner}`.** Only the merge owner works here. If you are not"
                    f" `{owner}`, bind first — `python3 /opt/fabrik/scripts/whoami_agent.py"
                    " --as <name>` — then move with `EnterWorktree` into"
                    " `.claude/worktrees/<name>`; the conversation follows you. Then check the"
                    " gitignored paths `.worktreeinclude` lists (`.env`, …) arrived, and copy"
                    " any missing one in from the main checkout.\n"
                )
            elif name != owner.lower():  # names are lowercase; a hand-written owner may not be
                instructed = True
                out += (
                    f"- ⚠️ **You are `{name}` in the main checkout, and the merge owner is"
                    f" `{owner}`.** Only the merge owner works here: move now with"
                    f" `EnterWorktree` into `.claude/worktrees/{name}` — the conversation"
                    " follows you, and a target under `.claude/worktrees/` asks no approval. Then"
                    " check the gitignored paths `.worktreeinclude` lists (`.env`, …) arrived, and"
                    " copy any missing one in from the main checkout.\n"
                )
        latest: dict[str, dict] = {}
        for row in rows:  # LAST row per session wins, as in the writer
            latest[row["session_id"]] = row
        held = []
        for row in latest.values():
            bound = str(row.get("name") or "")
            scope = str(row.get("toplevel") or "")
            if not _AGENT_NAME_RE.fullmatch(bound) or not scope:
                continue
            if os.path.realpath(scope) != common or not _binding_live(row):
                continue
            held.append(f"`{bound}` (pid {row['pid']})")
        if held:
            shown = sorted(held)[:12]
            more = f" · (+{len(held) - 12} more)" if len(held) > 12 else ""
            out += (
                "- **Live `whoami` bindings in this repo:** "
                + " · ".join(shown)
                + more
                + ". Sessions named at launch by `CLAUDE_AGENT` write no binding, so they are"
                " not listed.\n"
            )
        return out, instructed
    except Exception:
        return "", False


def _charter_line(cwd: str, name: str, hub: bool, env_set: bool) -> str:
    """The whoami-only session's bullet: named for attribution, but the charter (and, in the hub,
    beat routing) needs the env var. `name` is `_AGENT_NAME_RE`-valid, so it renders safely."""
    what = "the role charter (`agent_role.py`)" + (" and, in the hub, beat routing" if hub else "")
    if "/.claude/worktrees/" in cwd:
        relaunch = f"`CLAUDE_AGENT={name} claude --worktree {name} -n {name}-<repo>`"
    else:
        relaunch = f"`CLAUDE_AGENT={name} claude`"
    state = "is not a valid name" if env_set else "is unset"
    return (
        f"- ⚠️ **Named `{name}` by whoami, but `CLAUDE_AGENT` {state}:** {what} reads the env var"
        f" only — a named relaunch {relaunch} gives {'both' if hub else 'it'}.\n"
    )


def _identity_line(
    cwd: str,
    live: int | None = None,
    hub: bool | None = None,
    name: str | None = None,
    yield_to_model: bool = False,
) -> str:
    """Advisory (D-034, re-keyed 2026-09-16): an UNNAMED session is a mistake wherever several
    agents share one tree — the hub always, and any project repo that either DECLARES a merge
    owner in its ledger or currently has >=2 live `claude` sessions in this exact checkout.
    A session named by a valid `CLAUDE_AGENT` (the one validity test, `_AGENT_NAME_RE`), and a
    single-session unadopted repo, get nothing HERE — that repo's `--adopt` prompt is
    `_model_line`'s (spec 2026-09-29 D1). `yield_to_model`: `_model_line` already printed this
    session's bind-or-move instruction, and one instruction is the whole point.
    ⚠️ A session named ONLY by its whoami binding (`name`) is attributable but still has no role
    charter (`agent_role.py` reads the env var only) and, in the hub, no beat routing — so it
    gets the short `_charter_line` instead of silence, with no "bind" remedy: it is bound."""
    try:
        env = os.environ.get("CLAUDE_AGENT", "").strip()
        if _AGENT_NAME_RE.fullmatch(env) or yield_to_model:
            return ""
        if name is None:  # a direct caller; main() passes the name it resolved once
            name = _resolved_name("", _identity_rows())
        bad = (
            " (`CLAUDE_AGENT` is set, but not to a valid `[a-z0-9-]{1,32}` name, so every"
            " consumer drops it.)"
            if env
            else ""
        )
        if hub is None:  # a direct caller; main() passes the one probe it shares
            hub = _is_hub(cwd)
        if hub:
            if name:
                return _charter_line(cwd, name, hub=True, env_set=bool(env))
            return (
                f"- ⚠️ **CLAUDE_AGENT is UNSET — this hub session is UNNAMED.**{bad} Several sessions"
                " share this repo; the role charter, beat routing and Agent-Name trailers all"
                " key on the env var (a window rename never reaches hooks — the mis-signed-day"
                " class). Ask the operator which role this window is, or work without beat"
                " claims until named.\n"
            )
        if live is None:
            live = _count_sessions_sharing(os.path.realpath(cwd))
        owner = _ledger_merge_owner(cwd)[:32]  # the grammar is permissive by design; the
        # cap belongs HERE, at render time, so the regex stays byte-identical to both sources
        if not owner and live < 2:
            return ""
        # ⚠️ C5: do NOT print a second bullet about the same measured fact. When `_sessions_line`
        # will fire — non-hub, non-worktree, live >= 2 — it already names the count AND gives the
        # worktree relaunch, which is the correct remedy for a shared MAIN checkout. Two bullets
        # stating one fact with two different commands is what this branch shipped at b5c01855,
        # live in 5 of 45 repos. The identity bullet survives for the cases `_sessions_line` does
        # not cover: a DECLARED owner (any session count) and a worktree session.
        if not owner and "/.claude/worktrees/" not in cwd:
            return ""
        if name:
            return _charter_line(cwd, name, hub=False, env_set=bool(env))
        why = (
            f"this repo DECLARES merge owner `{owner}`"
            if owner
            else f"{live} live sessions share this checkout"
        )
        # ⚠️ ONE remedy per block. When the shared-checkout bullet also fires it already gives
        # the worktree relaunch, and a second, DIFFERENT command here is the contradiction
        # b5c01855 shipped. Point at it instead of restating it differently.
        if "/.claude/worktrees/" in cwd:
            remedy = "a relaunch as `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>`"
        elif live >= 2:
            remedy = "the relaunch named in the shared-checkout bullet below"
        else:
            remedy = "a relaunch as `CLAUDE_AGENT=<name> claude`"
        return (
            f"- ⚠️ **CLAUDE_AGENT is UNSET and {why}.**{bad} Without a name the role charter is not"
            " injected (`agent_role.py`) and the `Agent-Name` trailer you sign is a CLAIM nothing"
            " checks (project repos install no trailer check; the hub's `check_commit_trailers.py`"
            " compares it only against a resolvable name). ✅ **You can fix this"
            " right now, without a relaunch:** `python3 /opt/fabrik/scripts/whoami_agent.py --as"
            " <name>` binds THIS session, and every `command_run.py`"
            " run you START from here on is attributable (the hub's trailer check reads that binding too). ⚠️ A run record ALREADY OPEN keeps the empty agent it"
            " resolved at its own `start` — close and re-`start` it, or accept that one empty cell."
            " The role CHARTER needs a named relaunch either way (`agent_role.py` reads the env var"
            f" only). A named relaunch — {remedy} — still works and still wins. Ask the"
            " operator which name is yours before you bind or sign one.\n"
        )
    except Exception:
        pass
    return ""


def _count_sessions_sharing(real_cwd: str) -> int:
    """Live `claude` processes whose cwd IS this checkout. 0 on any scan failure — every caller
    reads 0 as "cannot tell", never as "nobody else is here". Extracted so `_identity_line` and
    `_sessions_line` cannot drift on the definition of "several agents are in this repo"."""
    proc_root_env = os.environ.get("FABRIK_PROC_ROOT", "")
    proc_root = (
        Path(proc_root_env) if proc_root_env and Path(proc_root_env).is_dir() else Path("/proc")
    )
    try:
        pids = [e.name for e in os.scandir(proc_root) if e.name.isdigit()]
    except OSError:
        return 0
    count = 0
    for pid in pids:
        entry = proc_root / pid
        try:
            comm = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
            if comm != "claude":
                continue
            entry_cwd = os.path.realpath(os.readlink(entry / "cwd"))
        except OSError:
            continue  # vanished or unreadable mid-scan — never fatal
        if entry_cwd == real_cwd:
            count += 1
    return count


def _sessions_line(
    cwd: str, live: int | None = None, hub: bool | None = None, instructed: bool = False
) -> str:
    """D5 (multi-agent-adoption spec): ≥2 live `claude` processes sharing this
    exact main checkout is the shared-index way that has lost work before
    (D-099) — undetected until now. A self-contained `/proc` scan: no
    `git worktree list` (subagent residue makes that trigger wrong, I10), no
    `/proc/<pid>/environ` read (payload sanitization boundary). Fail-open per
    entry: a vanished/unreadable pid is skipped, never raised — and the whole
    scan degrades to "" on any top-level OSError. Suppressed for a worktree
    session (cwd under `/.claude/worktrees/`) and for the hub (same `is_hub`
    test as `_identity_line`). `instructed`: `_model_line` already told this session where to go
    (`EnterWorktree`), so the count stands alone — no second, relaunch-shaped remedy."""
    if "/.claude/worktrees/" in cwd:
        return ""
    try:
        if hub is None:
            hub = _is_hub(cwd)
        if hub:
            return ""
        if live is None:  # a direct caller may still invoke this with one argument
            live = _count_sessions_sharing(os.path.realpath(cwd))
    # ValueError: a cwd carrying an embedded NUL raises out of realpath, and `print()` evaluates
    # every argument before emitting — so one raise here costs the ENTIRE ORIENT block at rc 0,
    # zero bytes, no stderr (executed; present in this file before the identity work touched it).
    except (OSError, ValueError):
        return ""

    count = live
    if count < 2:
        return ""
    if instructed:
        return (
            f"- ⚠️ **{count} sessions share this main checkout.** Only the merge owner works"
            " here; the move line below says where this session goes.\n"
        )
    return (
        f"- ⚠️ **{count} sessions share this main checkout.** The multi-agent model puts agents"
        " 2..N in worktrees — `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` —"
        " and one merge owner in the main checkout; adopt once with `python scripts/docs_updater.py"
        " --adopt <names>` (docs: /opt/fabrik/docs/reference/multi-agent-operating-model.md).\n"
    )


def _mcp_line(cwd: str) -> str:
    """The session's ASSIGNED MCP set + catalog pointer + fix-first duty (operator
    directive 2026-08-30, D-032). Reads the repo's emitted .mcp.json at runtime;
    fail-safe: any problem degrades to the universal-set line, never crashes."""
    assigned = "the universal set (no repo .mcp.json here)"
    try:
        import json as _json

        raw = (Path(cwd) / ".mcp.json").read_text()
        try:
            servers = _json.loads(raw).get("mcpServers", {})
            names = sorted(servers) if isinstance(servers, dict) else []
        except Exception:
            # a BROKEN file is not an ABSENT file — fix-first applies to the config too
            names = []
            assigned = "⚠️ .mcp.json EXISTS but is malformed/unreadable — fix it first (re-run the emitter)"
        if names:
            shown = names[:40]
            assigned = " · ".join(shown) + (f" · (+{len(names) - 40} more)" if len(names) > 40 else "")
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return (
        f"- **Your ASSIGNED MCPs (this repo):** {assigned} — plus the user-level universal set."
        " The FULL catalog + every ruling: `/opt/fabrik/docs/workstation/mcp-roster.md` (box-local,"
        " absolute path works from every repo); need a server this repo lacks? cite the roster row"
        " and ask the operator — never hand-edit `.mcp.json` (hub-emitted; the ruling changes first)."
        " **An MCP that fails to connect is FIXED FIRST, before the task** — known classes: corrupted"
        " `~/.npm/_npx/<hash>` entry → clear that ONE entry, never the whole `_npx`; cold-spawn herd"
        " timeout → reload the window; postgres-pro needs a CONNECTING `DATABASE_URL` in the repo"
        " `.env` (then re-run `python3 /opt/fabrik/scripts/sysadmin/emit_mcp_project_config.py"
        " --repo <this repo>`).\n"
    )


def _governance_line(cwd: str, hub: bool | None = None) -> str:
    # Repo identity is `_is_hub`'s rule (spec 2026-09-29 D4): the synced manifest in the tree AND
    # the git common dir under the hub path — so a hub worktree is the hub.
    if hub is None:
        hub = _is_hub(cwd)
    if hub:
        return (
            "- **Governance (HUB):** this is the platform repo — CLAUDE.md HERE is the hub"
            " agents' own contract: canonical and yours to edit (a synced-surface commit"
            " distributes fleet-wide; the project-facing template lives at"
            " templates/governance/CLAUDE.md). Obey it fully; every task-completing output owes"
            " the RULES ACTIVE line and ends with the 7-line FINAL OUTPUT block (incl."
            " DONE:/NEXT:)."
        )
    return (
        "- **Governance:** this project's CLAUDE.md is already loaded into your context. It is"
        " Fabrik-SYNCED (distributed from the hub's templates/governance/CLAUDE.md) — obey it"
        " fully; NEVER edit the local copy (the next sync overwrites it; changes go upstream via"
        " /fabrik-upstream). Every task-completing output owes the RULES ACTIVE line and ends"
        " with the 7-line FINAL OUTPUT block (incl. DONE:/NEXT:)."
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")  # C-locale must degrade, not swallow
        # stdin too: a non-ASCII cwd/transcript path under LC_ALL=C would otherwise raise
        # UnicodeDecodeError and silently drop the WHOLE payload (review finding).
        sys.stdin.reconfigure(errors="replace")
    except Exception:
        pass
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}  # [] / "x" / 42 payloads must not swallow the whole block
    cwd = str(data.get("cwd") or os.getcwd())
    # sid lands inside a command the agent is told to RUN — allowlist it to the
    # same class every mesh script sanitizes to ([A-Za-z0-9_-], first 64).
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id") or ""))[:64]

    # Pane auto-continue (operator directive: always on in interactive sessions):
    # the self-watch is the ONLY pane-safe revival mechanism (the headless
    # reviver against a pane forks a second writer — spec-disqualified), and a
    # background task can only be armed BY the agent — so the ORIENT block orders it
    # with the concrete session id. Skipped when: headless (the reviver exports
    # CLAUDE_MESH_HEADLESS=1, the declared spawners FABRIK_HEADLESS=1 — no pane to wake) or source=compact (same process,
    # the already-armed task SURVIVES compaction; selfwatch_check.py re-orders an arm whose lock is free — proven live 2026-08-09;
    # re-ordering there breeds duplicate watchers).
    arm_line = ""
    if sid and os.environ.get("CLAUDE_MESH_HEADLESS") != "1" \
            and os.environ.get("FABRIK_HEADLESS") != "1" \
            and data.get("source") != "compact" \
            and Path(os.environ.get("HOME", str(Path.home()))) \
            .joinpath(".claude/bin/claude-selfwatch.sh").is_file():
        arm_line = (
            "- **ARM YOUR SELF-WATCH NOW (first tool action, operator-mandated):** call "
            "Bash(run_in_background: true, command: "
            f"\"bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh {sid}\") — it wakes THIS pane"
            " automatically when a turn dies on a healed API error or a lost waker, or when the"
            " fleet-quota hold lifts. Zero cost while silent; skip ONLY if this session already armed"
            " it. ONE wake per arm (D-356): the task ENDS on its wake, and the wake line carries the"
            " re-arm order. Never a Monitor arm — a Monitor ends within 30 minutes — and never a"
            " `nohup ... &` arm: its wake line lands in /dev/null and the watch still consumes the"
            " death marker (a wef session revived 13 times became unrevivable the day it re-armed"
            " that way, 2026-08-30). A duplicate arm for this session exits at once.\n"
        )

    # Reboot sweep (plan 2026-08-10-plan-1, Phase D): a launcher that exports
    # CLAUDE_MESH_AUTONOMOUS=1 marks its session as machine-driven work worth resuming
    # after a reboot. INDEPENDENT of the pane arm-gate above — the sweep's whole
    # population is headless runs, so gating the marker on the arm would unmark exactly
    # the sessions it serves. Panes never set the env, so they are structurally excluded.
    if sid and os.environ.get("CLAUDE_MESH_AUTONOMOUS") == "1":
        try:
            # PERSISTENT state dir, never the /tmp lock dir (plan 2026-08-13-plan-1): a VM
            # termination (standby cut, host kill) wipes /tmp and with it every sweep
            # eligibility — the marker must outlive the VM for the @reboot sweep to revive
            # the session. The sweep reads this dir first, legacy lock dir second.
            locks = Path(os.environ.get("MESH_STATE_DIR")
                         or Path(os.environ.get("HOME", str(Path.home())))
                         / ".claude" / "state" / "autonomous")
            locks.mkdir(mode=0o700, parents=True, exist_ok=True)
            # 0600 at CREATE time: the marker carries cwd + transcript path (project
            # names, task slugs) and the default umask would make it world-readable.
            payload = json.dumps({
                "sid": sid,
                "cwd": cwd,
                "transcript_path": str(data.get("transcript_path") or ""),
                "marked_at": int(time.time()),
            })
            fd = os.open(locks / f"{sid}.autonomous",
                         os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(payload)
        except OSError:
            pass  # fail-open: an unmarkable session is un-swept, never a broken start

    # ONE /proc scan per SessionStart, shared by both advisories. Two scans cost 2x (11 ->
    # 22 ms on this box, 643 pids) and, worse, can DISAGREE inside one emitted block: a
    # sibling that exits between them made the identity bullet name a count the sessions
    # bullet then denied, and the reverse — both executed against a mutated fake /proc.
    try:
        live = _count_sessions_sharing(os.path.realpath(cwd))
    except (OSError, ValueError):
        live = 0  # the same "cannot tell" the helper itself returns
    # ONE git probe too, shared by hub identity and the model line (both fail open).
    layout = _git_layout(cwd)
    hub = _is_hub(cwd, layout)
    # ONE identity resolution and ONE model decision, shared so the three bullets that can name a
    # remedy (identity, shared checkout, move) give exactly one instruction between them.
    rows = _identity_rows()
    name = _resolved_name(str(data.get("session_id") or ""), rows)
    model, instructed = _model_line(layout, live, hub, name, rows)
    print(
        "## ORIENT (binding — read before acting)\n"
        + arm_line
        + _governance_line(cwd, hub)
        + "\n"
        + _memory_line(cwd)
        + "\n"
        + _identity_line(cwd, live, hub, name, instructed)
        + _sessions_line(cwd, live, hub, instructed)
        + model
        + _mcp_line(cwd)
        + "- **Decision-shaped question? LEDGER FIRST:** grep `docs/DECISIONS.md` (fleet-wide:"
        " `python3 /opt/fabrik/scripts/decisions.py <term>`) BEFORE any wider hunt — a prior ruling,"
        " retirement, or rejected option is a structured row there, and structured beats lexical."
        " A decision made or received this run gets its row in the same change.\n"
        "- **session-recall is CONNECTED:** `search_chats` (keyword) · `recent_chats` (recency) ·"
        " `get_chat` (read one). MANDATORY before answering when resuming work, when the user"
        " references a prior decision not in this conversation (AFTER the ledger), or after"
        " compaction — never claim no previous conversation exists without searching first.\n"
        "- **Enforcement mesh wired to this session:** the Stop hook blocks unfinished exits — SIX"
        " causes: gate red on YOUR files · your work uncommitted · committed-but-UNPUSHED (the"
        " task-end law: push your own work; never --force) · promise/permission stalls · a command"
        " run record still `running` · spontaneous CODE edits with no run record at all (plain-chat"
        " work owes /fabrik-review-scoped — running it creates the record that clears the block); the prompt router suggests the owning /fabrik-* skill;"
        " `python scripts/final_gate.py --json` is the completion gate. Work WITH them — they are"
        " the definition of done, not obstacles.\n"
        "- **Before ANY claim about hooks, the mesh, death/revival or sounds, READ"
        " `/opt/fabrik/docs/workstation/hooks-index.md`** — it is the authority and it is box-local"
        " (absolute path works from every repo). An infra agent stated four false things about this"
        " subsystem in one answer on 2026-08-16 by checking `~/.claude/state/` and the project hook"
        " config and reporting absence as fact; the mesh writes to"
        " `/tmp/claude-sound-locks-$(id -u)/`. Searching one plausible location is not evidence."
    )

    # Kaizen M1 — LAST, deliberately. This hook IS the session's birth certificate, but
    # the ORIENT block above is its actual product: emitting first put the whole block
    # behind a sensor that can be slow or throw. Two guards, both about not lying to the
    # collector: only where a Stop hook also runs (symmetric universe), and only on a
    # real session BIRTH — a resume/compact is the same session continuing, which is why
    # the --baseline path special-cases them too. An ABSENT source is treated as a
    # startup: a harness that stops sending the field must degrade to over-counting, not
    # to a silently dead metric. The RAW payload id is passed, never the flattened `sid`
    # above — flattening is many-to-one, and the emitter's own sanitizer is injective.
    if _instrumented(cwd) and str(data.get("source") or "startup") == "startup":
        _kaizen(
            "session_start",
            data.get("session_id"),
            probe_cwd=cwd,
            cwd=cwd,
            source=str(data.get("source") or ""),
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
