#!/usr/bin/env python3
# AFTER-EDIT: tests/test_command_feedback_report.py, docs/reference/command-run-protocol.md
"""Per-command optimisation report over the fleet-wide close-out ledger (D-175).

Every `command_run.py done|blocked|handoff` appends one row to
`~/.claude/state/command-feedback.jsonl` (beside the run-record dir; `COMMAND_RUN_DIR`'s parent
when set): the command, its wall-clock, its round count and findings trend, and the four usage
fields the agent wrote — confusion, waste, change, filed. This report turns those rows into the
list the corpus is optimised from: per command, how long and how many rounds a run takes, and
the concrete `change:` items agents asked for, ranked by how often they recur.

    python3 scripts/command_feedback_report.py [--since DAYS] [--command NAME] [--agent NAME]
                                               [--json] [--ledger PATH]
    python3 scripts/command_feedback_report.py --observer-rank   # who pays for a writer seat
    python3 scripts/command_feedback_report.py --queue COMMAND   # one command's change: queue

Every count states its bound: `examined` of `total_rows`. A missing ledger is an empty report.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import TypeGuard


def _default_ledger() -> Path | None:
    import os

    raw = os.environ.get("COMMAND_RUN_DIR")
    try:
        base = Path(raw).parent if raw else Path.home() / ".claude" / "state"
    except RuntimeError:  # no resolvable home
        return None
    return base / "command-feedback.jsonl"


def _rows(path: Path | None) -> list[dict]:
    """A missing OR unreadable ledger is an empty report, never a crash (review 2026-09-07)."""
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and r.get("command"):
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# The ANSWERED INDEX — which `ts` handles an applied corpus edit has already closed out.
#
# The commit trailer stays the provenance (it is immutable and human-readable), but it cannot be
# the only state: it is readable only from a hub checkout, while closes happen in ~46 repos, and
# reading it costs a `git log` that a PROSE step asked the agent to run. Measured 2026-09-15: zero
# rows had ever been marked, `/fabrik-command-improve` had never run, and the queue could only
# grow. This index is written by `--mark-answered` at the moment the edit is committed.
# ---------------------------------------------------------------------------

# The surfaces an edit that ANSWERS a verdict must actually touch. ⚠️ COBRA NOTE: the cheapest way
# to make a queue shrink without doing the work is to mark rows answered and commit nothing — so
# `--mark-answered` demands a commit SHA and refuses one that touched none of these paths. It
# cannot judge whether the edit is GOOD (that is the review's job, and a gate that tried would be
# judging prose); it can and does refuse an edit that does not exist.
# The surfaces an edit that ANSWERS a verdict must actually touch. ⚠️ COBRA NOTE: the cheapest way
# to make a queue shrink without doing the work is to mark rows answered and commit nothing — so
# `--mark-answered` demands a commit and refuses one that touched none of these paths. It cannot
# judge whether the edit is GOOD (that is the review's job, and a gate that tried would be judging
# prose); it can and does refuse an edit that does not exist.
#
# ⚠️ A DIRECTORY entry ends in `/` and matches by prefix; a FILE entry has no slash and matches
# EXACTLY. Plain `startswith` accepted `CLAUDE.md.bak` and `CLAUDE.mdx` — and
# `CLAUDE.md.backup.<date>` is the exact filename CLAUDE.md § Pointers mandates for config backups,
# so the false-accept was reachable by following another rule (review round 1).
_CORPUS_PATHS: tuple[str, ...] = (
    "commands/_sources/",
    "commands/_fragments/",
    "commands/_agents/",
    ".windsurf/rules/",
    "CLAUDE.md",
    "templates/governance/CLAUDE.md",
)


def _is_corpus_path(path: str) -> bool:
    return any(
        path.startswith(entry) if entry.endswith("/") else path == entry for entry in _CORPUS_PATHS
    )


def _git_env() -> dict[str, str]:
    """The environment with every `GIT_*` variable REMOVED.

    ⚠️ `GIT_DIR` beats `cwd`, so an exported one silently redirected the corpus check at another
    repository and turned a refusal into an acceptance (review round 1). This is not exotic: the
    private-index commit recipe in CLAUDE.md — which `/fabrik-command-improve` PHASE 5 mandates —
    exports `GIT_INDEX_FILE` and warns in its own text that git variables persist in the shell.
    """
    import os

    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _run_git(args: list[str], repo: Path, timeout: int = 30):
    import subprocess

    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotePath=false", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_git_env(),
    )


def _resolve_commit(commit: str, repo: Path) -> tuple[str | None, str]:
    """The full 40-character sha, or `(None, why)`.

    ⚠️ `--end-of-options` is the whole point, and it is CRITICAL. Without it a `--commit` value
    beginning with `-` is parsed by git as a FLAG: `--commit=--all` made `git show` walk every ref,
    print every file in the repository, match a corpus path and mark an ENTIRE queue answered at
    rc 0 with zero edits made — nine characters defeating the counter-measure this gate exists to
    be (review round 1, reproduced end-to-end).

    Resolving also fixes what a literal ref could not: `HEAD`, a branch, a tag and an abbreviated
    sha are all moving or ambiguous pointers, and an abbreviation was resolved in the WRONG repo
    (a 4-hex collision between a caller's repo and the hub, brute-forced and executed).
    """
    import subprocess

    try:
        proc = _run_git(["rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git could not be run ({exc})"
    sha = proc.stdout.strip()
    if proc.returncode != 0 or len(sha) != 40:
        return (
            None,
            f"`{commit}` does not resolve to a commit in {repo}: {proc.stderr.strip()[:200]}",
        )
    return sha, sha


def _commit_touches_corpus(commit: str, repo: Path) -> tuple[bool, str]:
    """`(touched, detail)` — does this commit change a file the corpus is made of?

    Fails CLOSED on purpose: a commit that cannot be read is not evidence of an edit, and marking
    rows answered is the one operation in this loop that DESTROYS information.
    """
    import subprocess

    sha, detail = _resolve_commit(commit, repo)
    if sha is None:
        return False, detail
    try:
        # `-m --first-parent` so a MERGE prints its diff (bare `git show` prints nothing for one,
        # which read as "touches no corpus path (0 file(s))" — a misleading refusal);
        # `--no-renames` so a renamed corpus file prints BOTH paths, not just the destination.
        proc = _run_git(
            [
                "show",
                "--name-only",
                "--format=",
                "-m",
                "--first-parent",
                "--no-renames",
                "--end-of-options",
                sha,
            ],
            repo,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"git could not be run ({exc})"
    if proc.returncode != 0:
        return False, f"git show {sha[:8]} failed: {proc.stderr.strip()[:200]}"
    files = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    hit = [f for f in files if _is_corpus_path(f)]
    if not hit:
        return False, (
            f"{sha[:8]} touches no corpus path ({len(files)} file(s): {', '.join(files[:5])})"
        )
    return True, f"{sha[:8]} touches {', '.join(hit[:5])}"


def _ts_key(value: object) -> str:
    """One ledger row's handle as a string — the DUPLICATE of `command_run.py::_ts_key`.

    ⚠️ Duplicated for the same reason `AXES` is: that file is fleet-synced to ~46 repos and this
    one is hub-only, so an import either way fails CLOSED in every project. The previous inline
    form here was `str(_num(v) or v)`, an `or`-falsiness bug: an integer `ts` of 0 keyed `'0'`
    against the close's `'0.0'`, and a string/None/NaN `ts` printed `?` — three distinct rows all
    rendering as `?`, un-markable forever, so a queue could never reach zero (review round 1).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        return str(value)
    return str(f) if math.isfinite(f) else str(value)


def _answered_path(ledger: Path | None = None) -> Path | None:
    """Beside the LEDGER IN USE — so `--ledger` scopes the answered index too.

    ⚠️ It did not, and that made polluting live state the DEFAULT: `--ledger` scoped every other
    mode while `--mark-answered` wrote to `$HOME/.claude/state` regardless, and `--queue` read its
    exclusions from there while listing rows from the file you named. The orchestrator of this very
    review wrote a real row into the live index by probing the CLI once (review round 1).
    """
    base = ledger if ledger is not None else _default_ledger()
    return None if base is None else base.parent / "command-feedback-answered.jsonl"


def _answered_ts(command: str, path: Path | None = None) -> set[str]:
    """The `ts` set already answered for one command. An absent or unreadable index means nothing
    is answered — the queue then shows every row, which is the safe direction: it over-reports work
    rather than hiding a verdict nobody acted on."""
    path = path if path is not None else _answered_path()
    if path is None:
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    out: set[str] = set()
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict) and str(row.get("command") or "") == command:
            out.add(_ts_key(row.get("ts")))
    return out


def _known_handles(command: str, ledger: Path | None = None) -> dict[str, int]:
    """Every `ts` handle the ledger carries for one command, spelled the way `--queue` PRINTS it,
    mapped to HOW MANY rows carry it — a handle shared by two rows silences both, and the ledger
    has three concurrent writers, so uniqueness is an observation about today's file and not an
    invariant anything enforces (review round 1)."""
    counts: dict[str, int] = {}
    for r in _rows(ledger if ledger is not None else _default_ledger()):
        if str(r.get("command") or "") == command:
            key = _ts_key(r.get("ts"))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _append_answered(path: Path, rows: list[dict]) -> tuple[int, str]:
    """Append rows one at a time, returning how many COMPLETED. Returns `(written, error)`.

    ⚠️ The previous form was a single buffered `open("a")` write of the whole batch. Under
    `ENOSPC` it left a TRUNCATED final line and reported `0 written / REFUSED` while 44 rows had
    in fact landed — verdicts silenced under a receipt that denied writing anything — and because
    the file no longer ended in a newline, the NEXT append glued itself onto the fragment and both
    lines became unparseable, so a later mark reported success for a row silently discarded
    (executed under `RLIMIT_FSIZE` in review round 1). One `os.write` loop per row bounds the
    damage to a single line and lets the count be honest.
    """
    import os

    written = 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    except OSError as exc:
        return 0, str(exc)
    try:
        # repair a previous partial write before adding to it
        if path.stat().st_size:
            with path.open("rb") as fh:
                fh.seek(-1, os.SEEK_END)
                if fh.read(1) != b"\n":
                    os.write(fd, b"\n")
        for row in rows:
            data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
            while data:
                n = os.write(fd, data)
                data = data[n:]
            written += 1
    except OSError as exc:
        return written, str(exc)
    finally:
        os.close(fd)
    return written, ""


def mark_answered(
    command: str,
    ts_rows: list[str],
    commit: str,
    repo: Path,
    path: Path | None = None,
    ledger: Path | None = None,
) -> tuple[int, str]:
    """Append one answered-row per `ts`. Returns `(written, message)`; 0 written is a refusal."""
    command = command.lstrip("/")
    if not command:
        return 0, "REFUSED — --mark-answered needs a command name."
    sha, _detail = _resolve_commit(commit, repo)
    ok, detail = _commit_touches_corpus(commit, repo)
    if not ok:
        return 0, f"REFUSED — nothing marked: {detail}. A verdict is answered by an EDIT."
    # ⚠️ Every handle must name a REAL row of THIS command's queue. Taking `--rows` on trust was a
    # FAIL-OPEN: a typo'd, invented or wrong-command handle was written to the index and reported
    # as `marked 2 row(s) answered` while the real rows stayed in the queue — so the agent believed
    # it had closed work it had not, and the one number this loop exists to move was wrong in the
    # flattering direction. Refuse the WHOLE batch and name the offenders: the ledger is
    # append-only, so an unknown handle is a miscopy or the wrong `<command>`, never a row that
    # aged out, and a partial write would leave the commit trailer disagreeing with the index.
    known = _known_handles(command, ledger)
    wanted = list(dict.fromkeys(ts_rows))
    if not wanted:
        return 0, "REFUSED — --rows named no handles."
    unknown = [t for t in wanted if t not in known]
    if unknown:
        if not known:
            return 0, (
                f"REFUSED — nothing marked: the ledger carries NO rows for /{command} at all "
                f"(is the command name right, and is the ledger readable?). Handles given: "
                f"{', '.join(wanted[:5])}"
            )
        return 0, (
            f"REFUSED — nothing marked: {len(unknown)} of {len(wanted)} handle(s) match no row of "
            f"/{command}'s queue: {', '.join(unknown[:5])}. Copy them from "
            f"`--queue {command}` exactly — the ledger is append-only, so an unknown handle is a "
            f"miscopy or the wrong command, never a row that expired."
        )
    shared = [t for t in wanted if known[t] > 1]
    if shared:
        return 0, (
            f"REFUSED — nothing marked: {len(shared)} handle(s) are carried by more than one row "
            f"of /{command} ({', '.join(shared[:5])}), and marking one would silence them all. "
            f"`ts` uniqueness is an observation about today's ledger, not an invariant — three "
            f"sessions share the writer. Resolve it by hand."
        )
    path = path if path is not None else _answered_path(ledger)
    if path is None:
        return 0, "REFUSED — no resolvable state dir for the answered index."
    already = _answered_ts(command, path)
    fresh = [t for t in wanted if t not in already]
    if not fresh:
        return 0, f"nothing to do — all {len(wanted)} row(s) were already marked for /{command}."
    now = time.time()
    written, err = _append_answered(
        path,
        [{"ts": t, "command": command, "commit": sha, "at": now} for t in fresh],
    )
    if err:
        return written, (
            f"PARTIAL — {written} of {len(fresh)} row(s) marked for /{command} by {sha[:8]} "
            f"before the write failed: {err}. Re-run `--queue {command}` and check what is "
            f"actually excluded before marking again."
        )
    skipped = len(wanted) - len(fresh)
    tail = f" ({skipped} already marked)" if skipped else ""
    return written, (
        f"marked {written} row(s) answered for /{command} by {sha[:8]}{tail} — {detail}"
    )


# The seven PER-RUN axes a `change:` value may be keyed with (spec § D4, the axis table rows
# :347-350 and :352-354). The one axis with NO per-run key is axis 5, continuous improvement
# (:351) — it is read ACROSS runs — which is why seven keys serve eight axes. Not "the eighth":
# the table's eighth row is `manifesto aware`, which does have a key and is in the list below.
AXES: tuple[str, ...] = ("lean", "fast", "accurate", "waste", "infra", "rules", "manifesto")

# The report's OWN copy of the phrases the close-out grammar prints, NEVER an import of
# `command_run.py::_GRAMMAR_NOUNS`: this file imports nothing from that one and must not start (it is
# owned by another plan's lock, and a cross-file import of a module-private constant is a dependency
# nobody declared). A grader pins every phrase here against the LIVE text of
# `commands/_fragments/close-feedback.md`, so a reword of the fragment fails a test rather than
# silently emptying the `placeholder` bucket.
#
# WHY the bucket exists at all: `command_run.py::_is_placeholder` was a `re.fullmatch` on `<…>`, so
# an axis key in front of a pasted grammar template DEFEATED it — `change: <the ONE concrete edit…>`
# was refused at the close and `change: lean: <the ONE concrete edit…>` was not. ⚠️ That hole is
# CLOSED (2026-09-15, eca8da1d — NOT 190e487a, which is the commit that INTRODUCED the first,
# still-holed cut): for the `change:` field the guard now strips decoration and one or more leading
# `<word>:` keys before its
# bracket test. This reader is no longer the only thing that can tell a pasted template from a
# verdict — but it stays, because the ledger still holds PRE-FIX rows that closed with a keyed
# template, and a reader is what makes those visible rather than silently bucketed as verdicts.
# LONG clauses on purpose. The short noun phrases these came from (`mail id`, `steps, turns`) are
# ordinary English that a genuine verdict ABOUT the close-out grammar uses in its own sentence —
# and the close-out grammar is exactly what this loop's verdicts are about. A paste reproduces the
# template's whole clause; a verdict borrows three words of it and then says something.
_GRAMMAR_PHRASES: tuple[str, ...] = (
    "the one concrete edit to this command or a rule",
    "what in the command text was ambiguous or misleading",
    "steps, turns or tokens spent without",
    "surfaces exercised: <what your run touched",
    "mail id(s) to infra|fleet|intel | none",
)


def _axis_of(value: str) -> str:
    """Classify one `change:` value into EXACTLY one bucket, in a fixed precedence.

    ``placeholder`` (the grammar's own noun phrase, bracketed or not, keyed or not) →
    ``bad-axis`` (a leading ``word:`` outside :data:`AXES` — an attempt that missed) →
    the named axis → ``unkeyed`` (no ``word:`` head at all).

    The order is what makes the four counts a partition: a value can satisfy two of these rules at
    once (``foo: <…>`` is both a bad key and a template) and must be counted once, not twice.
    """
    text = (value or "").strip()
    # runs of whitespace collapse before the phrase test: the fragment WRAPS its grammar across
    # lines, so `what in the\ncommand` is one phrase to a reader and two to a naive substring match
    low = " ".join(text.lower().split())
    # the KEY is the token before the first comma (so `a, lean: x` keys nothing), but the phrase
    # test below reads the WHOLE value: truncating it at the comma made one of the five clauses
    # structurally inert on the keyed path, since that clause carries a comma of its own
    head = low.split(",", 1)[0]
    key, sep, _head_rest = head.partition(":")
    rest = low.partition(":")[2] if ":" in low else ""
    key = key.strip()
    # A KEY ATTEMPT is one alphabetic word, a colon, then whitespace or nothing. The whitespace is
    # what separates a key from a URL or a Windows path (`https://x`, `c:\users`), whose colon is
    # punctuation inside a token and never an attempt to key anything.
    attempt = bool(sep) and key.isalpha() and (rest == "" or rest[:1].isspace())
    # ⚠ The placeholder test is ANCHORED at the head of the value, never a substring search over it.
    # Unanchored it ate real verdicts, because the close-out grammar IS this loop's own subject:
    # `lean: step 7 should print the mail id it filed` is a genuine verdict and matched `mail id`.
    # A paste STARTS with the grammar; a verdict merely mentions it.
    body = rest.strip() if attempt else low
    # A PASTE reproduces the template: it either opens with the angle bracket, or it repeats one of
    # the grammar's whole clauses verbatim. A VERDICT ABOUT the grammar borrows a few of its words
    # and then says something of its own. Anchoring alone was not enough: `lean: the ONE concrete edit example is three lines
    # long — cut it` is a real verdict that starts with a phrase, and four of five realistic
    # wordings about the close-out text were still eaten. Leading decoration is stripped first,
    # because the fragment prints the template inside a `> ` blockquote and that marker is the
    # likeliest copy artifact (the close's own `_is_placeholder` strips decoration the same way).
    bare = body.lstrip("> -*\"'`(")
    if bare.startswith("<") or any(bare.startswith(phrase) for phrase in _GRAMMAR_PHRASES):
        return "placeholder"
    if not attempt:
        return "unkeyed"
    if not body:
        return "unkeyed"  # `lean:` with nothing after it keys nothing
    return key if key in AXES else "bad-axis"


def _change_is_none(value: str) -> bool:
    """`_is_none` for the CHANGE field alone — the axis key is stripped before the test.

    ⚠️ The strip does NOT go inside :func:`_is_none`, which is SHARED: ``_items()`` gates `change`,
    `confusion` and `waste` on it and ``change_none`` reads it too, so teaching it about axis keys
    would silently re-classify a `confusion:` value whose first word happens to be `lean:`.
    """
    text = (value or "").strip()
    head, sep, rest = text.partition(":")
    # the SAME key-attempt shape `_axis_of` uses — one alphabetic word, a colon, then whitespace —
    # or the two helpers disagree about `lean:none` (`unkeyed` there, `none` here) and the row
    # leaves the tally while being booked as "nothing to change"
    if sep and not (rest == "" or rest[:1].isspace()):
        return _is_none(text)
    # only strip a key that actually has a verdict behind it: `lean:` with nothing after it is a
    # MALFORMED verdict, not a claim that nothing needed changing, and stripping it would report
    # the malformation as compliance — the two helpers would then disagree about the same row
    # (`_axis_of` calls it `unkeyed`, this one would call it `none`) and it would vanish from the
    # tally altogether
    if sep and head.strip().lower() in AXES and rest.strip():
        text = rest
    return _is_none(text)


def _is_none(value: str) -> bool:
    stripped = (value or "").strip()
    head = stripped.lower().split()[0].rstrip(".,;") if stripped else ""
    return not stripped or head in {"none", "nothing", "n/a", "-"}


def _finite_arg(text: str) -> float:
    """`--since` as a number that can actually filter. `float("nan")` parses, then every `>= cutoff`
    comparison is False, so the report silently empties while reporting success — and `NaN` reached
    the JSON document, which no strict parser accepts."""
    value = float(text)
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"--since needs a finite number of days, not {text!r}")
    return value


def _finite(v: object) -> object:
    """Every PUBLISHED figure, made renderable — or ``None``.

    Four review rounds guarded this file site by site and each declared the class closed: round 2
    fixed one helper and said "the only", round 3 found a second and said "six of six", round 4
    proved the sums those six return still crashed two callers — and a fifth round found the third
    caller, plus two silent `float → inf` paths no `OverflowError` guard can see, because float
    addition overflows to infinity without raising.

    A per-site guard can only ever close the sites someone enumerated. This closes the PROPERTY, at
    the one place every figure passes through on its way to a reader: a published number is finite
    and convertible to float, or it is null. Nothing downstream — `_k`, an f-string, `json.dumps` —
    can then be handed a value it cannot render, and a report is never lost to one corrupt row.
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    try:
        return v if math.isfinite(float(v)) else None
    except OverflowError:
        return None


def _median(values: list) -> float | int | None:
    """The median, or None when the values cannot be reduced to one.

    Every numeric helper here guards its COMPONENTS, but they return exact-int SUMS: four token
    fields each just under the float maximum sum past it, and `statistics.median` then cannot
    convert the result. One such row took the whole report down with rc 1 and no output — the very
    invariant this module states. A COUNT of guarded call sites was never a proof of the guarded
    property, which is how three review rounds read six-of-six as class closure.
    """
    if not values:
        return 0
    try:
        m = statistics.median(values)
        return int(m) if float(m).is_integer() else round(float(m), 1)
    except OverflowError:
        return None


def _num(v: object) -> float | None:
    """A finite number from a ledger cell, else None — one bad row in the shared, append-only
    ledger must never take the whole report down (review pass 22: the pass-21 guard covered
    cost_usd/tok_* only; a string, list, NaN, Infinity or 400-digit `wall_s`/`rounds`/`ts` still
    raised out of build()). None is NO datum: the caller drops it and discloses the row count,
    never a phantom 0 that drags a median (pass 23)."""
    try:
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
            return float(v)
    except OverflowError:  # a 400-digit JSON integer: float() itself overflows
        pass
    return None


def _cost(r: dict) -> float | None:
    v = r.get("cost_usd")
    try:
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
            return float(v)
    except OverflowError:  # a 320-digit JSON integer: float() itself overflows
        pass
    return None  # a non-finite or oversized value in an old row is counted as a run, never summed


def _nonneg_cost(r: dict) -> float | None:
    """`cost_usd` when it is a real amount. A negative dollar figure reduces a command's reported
    spend, and the writer refuses to emit one — so a negative here is a corrupt row, not a refund."""
    c = _cost(r)
    return c if c is not None and c >= 0 else None


_TOK = ("tok_in", "tok_out", "tok_cache_read", "tok_cache_create")
# the SEATS' spend (D-192/D-193): the four fields summed from each seat's own transcript —
# summed separately from the orchestrator's, never folded into `tok_total` (which stays what the
# orchestrator read), because 20M seat tokens beside 160 orchestrator tokens was invisible to every
# rollup here (review 2026-09-08)
_SEAT_TOK = ("tok_seat_in", "tok_seat_out", "tok_seat_cache_read", "tok_seat_cache_create")


def _is_count(v: object) -> TypeGuard[int | float]:
    """A finite, NON-NEGATIVE, non-bool number — the same acceptance `seats_seen` uses, so the two
    aggregations of one field cannot disagree on a `10.0` (round-6 finding).

    The sign half came later, from the whole-plan review: a count of seats is a tally, and one
    corrupt row of `-100` dragged the whole command's `seats_seen` negative. `_tok_total`,
    `_io_total` and `_seat_total` all reject a negative COMPONENT for the same reason; this is the
    fourth site of the same rule, and it carries the overflow half too.
    """
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(float(v)) and v >= 0
    except OverflowError:
        # a 400-digit JSON integer: float() itself overflows. Every other numeric helper here
        # carries this, and without it ONE such row raised out of `build` and took the whole
        # report down — rc 1, no output — against the call sites' own stated invariant
        return False


def _seat_total(r: dict) -> int | None:
    """Seat tokens on a row (sync fields + background total), or None when the row carries none."""
    total = 0
    seen = False
    for k in _SEAT_TOK:
        v = r.get(k)
        if v is None:
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return None  # a malformed seat field nulls the row's seat sum, never the count
        try:
            # the sign rule: two rows of -10000 and +10000 rendered "0 (2 · —)", which reads as
            # two rows measured at zero rather than as data nobody can trust. And the overflow
            # half — a 400-digit JSON integer overflows `float()` itself, and this was the LAST
            # of the six numeric helpers here without the catch, so one such row took the whole
            # report down with no output at all
            if not math.isfinite(float(v)) or v < 0:
                return None
        except OverflowError:
            return None
        total += int(v)
        seen = True
    return total if seen else None


def _tok_total(r: dict) -> int | None:
    vals = [r.get(k) for k in _TOK]
    try:
        if any(
            not isinstance(v, (int, float))
            or isinstance(v, bool)
            or not math.isfinite(float(v))
            or v < 0  # a NEGATIVE component, not merely a negative sum: `cache_hit` recombines
            # these same fields per-component behind this whole-row gate, so guarding only the total
            # let one bad field through to print -25% and 250% cache hits from garbage
            for v in vals
        ):
            return None  # a row without (finite, non-negative) transcript data is counted, never zeroed
        return int(sum(vals))
    except OverflowError:
        return None


def _io_total(r: dict) -> int | None:
    """Σ ``tok_in`` + ``tok_out`` on a row, or ``None`` when the row carries neither finitely.

    DELIBERATELY NOT ``_tok_total``, which sums all four token fields including the two cache ones.
    Cache tokens measure how much of a prompt was re-read, not how much work a round did, so folding
    them into a per-round figure would make a long cached conversation look like heavy work. The
    report therefore carries two conventions at once and states both (spec § Q2, § Reproduce R9).
    """
    vals = [r.get(k) for k in ("tok_in", "tok_out")]
    if any(v is None for v in vals):
        return None  # a HALF pair is not a pair (spec § Q2: it contributes to NEITHER side)
    try:
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v))
            for v in vals
        ):
            return None
        if any(v < 0 for v in vals):
            # a NEGATIVE component, not merely a negative sum: -1000000 and +1000010 net to a
            # plausible +10 and published a confident tok/round over a corrupt pair at ratio 1.0
            return None
        return int(sum(vals))
    except OverflowError:
        return None


def _whole(n: float | None) -> bool:
    """A round count that can be a divisor: a whole number above zero.

    `_num` gates finiteness but not integrality, and `int()` TRUNCATES — a `rounds` of 2.7 would
    have overstated the figure by 26% while a 0.9 silently left its tokens in the mass and out of
    the numerator, which is the asymmetry that silences a command for a reason nobody can see.
    """
    return n is not None and float(n).is_integer() and int(n) > 0


def _tok_per_round(rs: list[dict]) -> dict[str, object]:
    """Tokens per round for one command, behind the MASS RULE, with its own population counts.

    Two ordered clauses, and the order is load-bearing:
      1. total token mass ``T`` is 0  → publish nothing ("zero token mass"). Evaluated FIRST, because
         a ratio over a zero denominator is exactly the division this rule exists to prevent, and a
         0/0 would render as a confident ``0.0``.
      2. the rows carrying BOTH sides hold < ⅔ of ``T`` → publish nothing, and say the measured
         ratio. A figure over a minority of the work describes something other than the command.
    The quantity is Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying BOTH a finite token pair and
    an integer ``rounds > 0``: a row with tokens and no rounds, and a row with rounds and no tokens,
    contribute to NEITHER side, and so does a row that spent NOTHING — a zero-token row with rounds
    would dilute the divisor while leaving the ratio at a reassuring 1.0, which is the one failure
    the mass rule exists to prevent, passing it at perfect coverage. ``cost_usd`` enters nothing
    here (spec § Q2 — it derives nothing).
    """
    mass = sum(v for v in map(_io_total, rs) if v is not None)
    pairs = [
        (io, int(n))
        for r in rs
        for io in (_io_total(r),)
        for n in (_num(r.get("rounds")),)
        if io is not None and io > 0 and _whole(n)
    ]
    out: dict[str, object] = {
        "rows_with_numerator": sum(1 for r in rs if _io_total(r) is not None),
        "rows_with_denominator": sum(1 for r in rs if _whole(_num(r.get("rounds")))),
        "rows_both": len(pairs),
        "rows_total": len(rs),
        "tok_per_round": None,
        "tok_per_round_reason": None,
        "mass_ratio": None,
    }
    if mass == 0:  # clause 1, BEFORE any ratio
        # a 0 over 0 rows is "nothing looked at", not an honest zero — the file's own rule, applied
        out["tok_per_round_reason"] = (
            "zero token mass" if out["rows_with_numerator"] else "no token-carrying row"
        )
        return out
    covered = sum(io for io, _n in pairs)
    ratio = covered / mass
    out["mass_ratio"] = ratio
    if ratio < 2 / 3:  # clause 2 — `>=` two thirds publishes, so the boundary is inclusive
        out["tok_per_round_reason"] = f"mass ratio {ratio:.4f} < 2/3"
        return out
    rounds = sum(n for _io, n in pairs)
    if rounds == 0:  # unreachable while pairs require rounds > 0; never divide on a guess
        out["tok_per_round_reason"] = "no round-carrying row"
        return out
    try:
        out["tok_per_round"] = covered / rounds
    except OverflowError:  # the same sum path: one row past the float maximum
        out["tok_per_round_reason"] = "token mass too large to divide"
    return out


def _k(n: float) -> str:
    """A token count as a cell. Astronomical values go to exponent form rather than expanding.

    `_k(1.7e308)` spelled out is a 310-character table cell — one corrupt row made the whole table
    unreadable, which is the reader-facing half of the same class the `_finite` sanitiser closes on
    the value side: a figure that cannot be RENDERED is as useless as one that cannot be computed.
    """
    if abs(n) >= 1e12:
        return f"{n:.2e}"
    if round(n / 1000, 1) >= 1000:  # 999,999 rolls over to 1.0M, never "1000.0k"
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1000:.1f}k" if n >= 1000 else f"{n:.0f}"


def _axis_tally(rs: list[dict]) -> dict[str, int]:
    """Per-bucket counts over the rows carrying a NON-`none` `change:` value.

    Every bucket that occurs is present; the counts sum to ``axis_rows`` by construction, because
    :func:`_axis_of` is a total function into a single bucket. An EMPTY dict means no row carried a
    change at all — the reader says so rather than printing a confident 0 per axis, which is the
    phantom-zero class this report has already paid for once.
    """
    tally: dict[str, int] = {}
    for r in rs:
        value = str(r.get("change") or "")
        if _change_is_none(value):
            continue
        bucket = _axis_of(value)
        tally[bucket] = tally.get(bucket, 0) + 1
    return dict(sorted(tally.items()))


def build(
    rows: list[dict], since_days: float | None, command: str | None, agent: str | None = None
) -> dict:
    total = len(rows)
    cutoff = time.time() - since_days * 86400 if since_days is not None else None  # 0 = now
    kept = [
        r
        for r in rows
        if (cutoff is None or (_num(r.get("ts")) or 0) >= cutoff)
        and (command is None or r.get("command") == command)
        and (agent is None or str(r.get("agent") or "") == agent)
    ]
    per: dict[str, list[dict]] = collections.defaultdict(list)
    for r in kept:
        per[str(r["command"])].append(r)
    commands: dict[str, dict] = {}
    for cmd, rs in sorted(per.items()):
        # rows with a finite value only; the counts beside the medians are their denominators
        # a NEGATIVE wall-clock or round count is corrupt data, never a measurement: one such row
        # used to drag the whole command's median below zero, and a median wall of -45 min is a
        # number a reader cannot even interpret as wrong
        walls = [
            w / 60 for w in map(_num, (r.get("wall_s") for r in rs)) if w is not None and w >= 0
        ]
        # NOT int(): truncating a 2.7 into the median is the same defect `_whole` rejects for the
        # tok/round divisor. A 0-round run is still a real run and stays in the median's population.
        rounds = [n for n in map(_num, (r.get("rounds") for r in rs)) if n is not None and n >= 0]
        commands[cmd] = {
            "runs": len(rs),
            "done": sum(1 for r in rs if r.get("state") == "done"),
            "blocked": sum(1 for r in rs if r.get("state") == "blocked"),
            "handoff": sum(1 for r in rs if r.get("state") == "handoff"),
            "models": sorted(
                {
                    m
                    for r in rs
                    for m in (r.get("models") if isinstance(r.get("models"), list) else [])
                    if isinstance(m, str)
                }
            ),
            # no timed row ⇒ null, never a 0 that reads like a real zero-minute run (pass 24)
            "median_wall_min": round(float(statistics.median(walls)), 1) if walls else None,
            "max_wall_min": round(max(walls), 1) if walls else None,
            "median_rounds": _median(rounds) if rounds else None,
            "wall_rows": len(walls),
            "rounds_rows": len(rounds),
            "change_none": sum(1 for r in rs if _change_is_none(str(r.get("change") or ""))),
            # the tally's population is the rows carrying a real change — `none` rows are
            # `change_none`'s and are excluded here, or the bucket that means "the instrument is
            # broken" would be mostly people following the contract
            "axes": _axis_tally(rs),
            "axis_rows": sum(1 for r in rs if not _change_is_none(str(r.get("change") or ""))),
            # summed over the rows that carry a number; rows without one are counted, not zeroed
            "cost_usd": round(sum(c for c in map(_nonneg_cost, rs) if c is not None), 4),
            "cost_rows": sum(1 for r in rs if _nonneg_cost(r) is not None),
        }
        toks = [t for t in map(_tok_total, rs) if t is not None]
        ctx = sum(
            int(r["tok_in"]) + int(r["tok_cache_read"]) + int(r["tok_cache_create"])
            for r in rs
            if _tok_total(r) is not None
        )
        read = sum(int(r["tok_cache_read"]) for r in rs if _tok_total(r) is not None)
        seats = [t for t in map(_seat_total, rs) if t is not None]
        commands[cmd].update(
            {
                "tok_total": sum(toks),
                "tok_rows": len(toks),
                "seat_total": sum(seats),
                "seat_rows": len(seats),
                # ONE acceptance (`_is_count`) for the count and its denominator — two textually
                # identical predicates were free to drift (round-9 finding)
                "seats_seen": sum(
                    int(v) for r in rs for v in (r.get("seats_seen"),) if _is_count(v)
                ),  # one malformed row must never take the whole report down (round-4 finding)
                "median_tok": _median(toks) if toks else None,  # no rows ⇒ null, never "0"
                "cache_hit": round(read / ctx, 3) if ctx else None,
                # rows whose scan hit the byte cap inside the window: their sums are lower bounds
                "tok_partial_rows": sum(1 for r in rs if r.get("tok_partial") is True),
                # a seat still writing at the close; and a typed reservation that disagreed with
                # the seat files by more than one — the close's warning, made queryable (round 5)
                # the rows the seat count was read from — a 0 over 0 rows is "nothing looked at",
                # not an honest zero (round-8 Opus finding)
                "seats_seen_rows": sum(1 for r in rs if _is_count(r.get("seats_seen"))),
                "seats_partial_rows": sum(1 for r in rs if r.get("seats_partial") is True),
                # seat files dropped for size/unreadability — a count nobody could read from any
                # rollup while it lived only in the raw row (round-7 finding)
                "seats_skipped": sum(
                    int(v) for v in (r.get("seats_skipped") for r in rs) if _is_count(v)
                ),
                **_tok_per_round(rs),
                "seats_mismatch_rows": sum(
                    1
                    for r in rs
                    if _is_count(r.get("seats_declared"))
                    and _is_count(r.get("seats_seen"))
                    and abs(int(r["seats_declared"]) - int(r["seats_seen"])) > 1
                ),
            }
        )

    def _items(field: str) -> list[dict]:
        counter: collections.Counter[tuple[str, str]] = collections.Counter()
        agents: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        surfaces: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        # the CHANGE field may carry an axis key, so "nothing to change" is read through the
        # key-stripping helper — otherwise `lean: none` is counted by `change_none` AND printed as
        # an actionable backlog item, and the two halves of one report disagree about one row
        dead = _change_is_none if field == "change" else _is_none
        for r in kept:
            v = str(r.get(field) or "").strip()
            if not dead(v):
                key = (str(r["command"]), v)
                counter[key] += 1
                a = str(r.get("agent") or "")
                if a and a not in agents[key]:
                    agents[key].append(a)  # EVERY agent that raised it, first-seen order
                sf = str(r.get("surface") or "")
                if sf and sf not in surfaces[key]:
                    surfaces[key].append(sf)  # and EVERY surface — never the first row's only
        return [
            {
                "command": c,
                "item": v,
                "count": n,
                "agent": ",".join(agents[(c, v)]),
                "surface": ", ".join(surfaces[(c, v)]),
            }
            for (c, v), n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    for stats in commands.values():
        # the ONE place every published figure passes through: finite and renderable, or null
        for key, value in list(stats.items()):
            stats[key] = _finite(value)
    return {
        "conventions": {
            "tok_per_round": (
                "Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying a POSITIVE token pair and a "
                "whole rounds > 0; cache excluded; mass-weighted, not a median"
            ),
            "median_tok": (
                "cache-inclusive, over the rows carrying ALL FOUR token fields — a DIFFERENT "
                "population from tok_per_round's, neither containing the other: a row with all "
                "four fields and rounds 0 is here and not there, and a row with only the "
                "input/output pair and rounds > 0 is there and not here"
            ),
            "mass_rule": (
                "tok_per_round is silent when the command's token mass is 0 (mass_ratio is then "
                "null — there is nothing to take a ratio of), or when the rows it is computed over "
                "hold under two thirds of that mass, in which case mass_ratio is the measure"
            ),
            "row_counts": (
                "num = rows carrying a token pair; den = rows carrying a whole rounds > 0; both = "
                "the rows the figure is computed over, which additionally requires the pair to be "
                "POSITIVE — a row that measured no tokens has no work to attribute to its rounds"
            ),
        },
        "total_rows": total,
        "examined": len(kept),
        "since_days": since_days,
        "agent": agent,
        "commands": commands,
        "backlog": _items("change"),
        "confusion": _items("confusion"),
        "waste": _items("waste"),
    }


def _cell(text: str) -> str:
    """Free text made safe for a markdown table cell.

    A literal ``|`` inside a cell is an extra column boundary: one pipe in a command or model name
    used to render a 16-cell row under a 13-cell header, silently turning the table into prose for
    every downstream reader. Command names come from a controlled vocabulary; model strings do not.
    """
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _per_round_cell(c: dict) -> str:
    """`<q/T> (num/den/both)` — the figure or the reason it is silent, always with its population."""
    counts = f"({c['rows_with_numerator']}/{c['rows_with_denominator']}/{c['rows_both']})"
    if c.get("tok_per_round") is None:
        return f"— {c.get('tok_per_round_reason') or 'not derived'} {counts}"
    return f"{_k(float(c['tok_per_round']))} {counts}"


def _min(v: float | None) -> str:
    """A wall-clock cell. `None` covers both "no timed row" and a figure the sanitiser nulled."""
    return f"{v} min" if v is not None else "—"


def render(report: dict) -> str:
    lines = [
        f"command feedback — {report['examined']} of {report['total_rows']} ledger rows examined"
        + (f" (last {report['since_days']:g} days)" if report["since_days"] is not None else "")
        + (
            f" · agent {report['agent'] or '(unattributed)'}"
            if report.get("agent") is not None
            else ""
        ),
        "Population: rows are AGENT-CLOSED runs only — coroner-closed (died/expired) runs write no "
        "row; nested runs overlap their parent's window, so per-command token and cost totals are "
        "not additive across commands.",
        "Conventions: tok/round is Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying a POSITIVE "
        "token pair and a whole rounds > 0 — cache excluded, and mass-weighted rather than a "
        "median, so one heavy run moves it more than a light one. Its (num/den/both) are three "
        "SEPARATE counts: rows carrying a token pair, rows carrying a whole rounds > 0, and the "
        "rows the figure is actually computed over — the third needs BOTH of the first two AND a "
        "positive pair, so num and den usually differ from it because a row carries only one side, "
        "and it drops further only where a row measured no tokens at all. The cell reads — when "
        "the command's token mass is "
        "0, or when those rows hold under two thirds of it; it says which, and --json carries the "
        "measured ratio in the second case (in the first there is nothing to take a ratio of). "
        "median tokens is cache-inclusive and needs all four token fields — a DIFFERENT population "
        "from tok/round's, neither containing the other, so the two row counts do not compare.",
        "",
        "| command | runs | done/blocked/handoff | median wall (rows) | max wall | "
        "median rounds (rows) | change: none | pool $ (rows) | median tokens (rows) | cache hit | "
        "seat tokens (rows · seats) | tok/round (num/den/both) | models |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cmd, c in report["commands"].items():
        hit = f"{100 * c['cache_hit']:.0f}%" if c.get("cache_hit") is not None else "—"
        lines.append(
            f"| /{_cell(cmd)} | {c['runs']} | {c['done']}/{c['blocked']}/{c['handoff']} | "
            f"{_min(c['median_wall_min'])} ({c['wall_rows']}) | {_min(c['max_wall_min'])} | "
            f"{c['median_rounds'] if c['rounds_rows'] and c['median_rounds'] is not None else '—'} "
            f"({c['rounds_rows']}) | "
            f"{c['change_none']} of {c['runs']} | "
            f"{c['cost_usd'] if c['cost_rows'] and c['cost_usd'] is not None else '—'} "
            f"({c['cost_rows']}) | "
            f"{_k(c['median_tok']) if c.get('median_tok') is not None else '—'} "
            f"({c['tok_rows']}) | {hit} | "
            f"{_k(c['seat_total']) if c['seat_rows'] and c['seat_total'] is not None else '—'} "
            f"({c['seat_rows']} · "
            f"{c['seats_seen'] if c['seats_seen_rows'] and c['seats_seen'] is not None else '—'}"
            f"{' · ' + str(c['seats_skipped']) + ' skipped' if c['seats_skipped'] else ''}) | "
            f"{_per_round_cell(c)} | "
            f"{_cell(', '.join(c['models'])) or '—'} |"
        )
    # the rows whose sums UNDERSTATE — computed since round 5 and rendered only by --json until the
    # round-7 Opus seat read the text report the contract names (F119/F139 were --json-only fixes)
    cav = [
        f"/{c}: {v['seats_mismatch_rows']} declared/seen seat mismatch, "
        f"{v['seats_partial_rows']} seat(s) still running at the close, "
        f"{v['tok_partial_rows']} truncated token scan(s)"
        for c, v in report["commands"].items()
        if v["seats_mismatch_rows"] or v["seats_partial_rows"] or v["tok_partial_rows"]
    ]
    if cav:
        lines += ["", "⚠ LOWER BOUNDS — the sums above understate these rows:"] + [
            f"- {x}" for x in cav
        ]
    keyed = {c: v for c, v in report["commands"].items() if v["axis_rows"]}
    lines += ["", "## change: by axis — which property of the command text each verdict is about"]
    if not keyed:
        # never a confident 0 per axis: nothing was measured is a different statement from zero
        lines.append("- no row in this window carries a change: verdict — nothing to key")
    else:
        for c, v in sorted(keyed.items()):
            cells = " · ".join(f"{k} {n}" for k, n in v["axes"].items())
            lines.append(
                f"- /{c} ({v['axis_rows']} with a change: value of {v['runs']} run(s)): {cells}"
            )
        lines.append(
            "  (`placeholder` = the close-out grammar pasted rather than answered; `bad-axis` = a "
            "key outside the seven; `unkeyed` = no key — each is an instrument reading, not a verdict)"
        )
    for title, key in (
        ("Optimisation backlog (change:)", "backlog"),
        ("Confusion (confusion:)", "confusion"),
        ("Waste (waste:)", "waste"),
    ):
        lines += ["", f"## {title} — {len(report[key])} distinct item(s)"]
        for it in report[key][:40]:
            who = " · ".join(x for x in (it.get("agent"), it.get("surface")) if x)
            tag = f" [{who}]" if who else ""
            lines.append(f"- ×{it['count']} /{it['command']}{tag}: {it['item']}")
    return "\n".join(lines)


def queue(rows: list[dict], command: str, ledger: Path | None = None) -> str:
    """One command's `change:` queue — the whole input `/fabrik-command-improve` reads.

    TAB-separated, newest first: ``<ts>\t<bucket>\t<the value>``. A TAB and not the report's
    usual `` · `` because a stored value may legally contain a middle dot (the close keeps it
    whenever no field label follows), so a middle-dot delimiter would share an alphabet with its own
    payload and a three-field line would read as five. Any TAB or newline inside a value is escaped
    on the way out for the same reason.

    `ts` is the row handle: the ledger has no id, `sid` is per session, and `ts` is unique on every
    row of the live file — which is what lets an applied edit name the rows it answers in its commit
    trailer without a writer change to the (lock-owned) close.
    """
    command = command.lstrip("/")  # the ledger stores names slash-free; a reader types the slash
    for_it = [r for r in rows if str(r.get("command") or "") == command]
    mine = [r for r in for_it if not _change_is_none(str(r.get("change") or ""))]
    # ANSWERED rows are excluded HERE rather than by a prose step the reader was asked to perform.
    # The command text used to say "run `git log --grep=... ` and exclude them yourself"; a manual
    # exclusion is one an agent skips, and then run N+1 reads the identical queue and can pick the
    # identical group. The count is STATED, never silent — an exclusion you cannot see is a
    # denominator you cannot check.
    answered = _answered_ts(command, _answered_path(ledger))
    excluded = [r for r in mine if _ts_key(r.get("ts")) in answered]
    mine = [r for r in mine if _ts_key(r.get("ts")) not in answered]
    # the denominator is the rows FOR THIS COMMAND, never the whole ledger: "2 of 5 rows carry a
    # verdict for it" is false of a 5-row ledger where only 3 rows are about it at all, and this is
    # the figure a reader uses to decide whether the queue is worth a run
    head = (
        f"queue /{command} — {len(mine)} unanswered of "
        f"{len(mine) + len(excluded)} verdict row(s), "
        f"{len(for_it)} row(s) for it in all ({len(rows)} in the window)"
        + (f"; {len(excluded)} already answered and excluded" if excluded else "")
    )
    if not mine:
        return head + "\n(nothing to improve from — pick another command)"
    mine.sort(key=lambda r: _num(r.get("ts")) or 0, reverse=True)
    out = [head]
    for r in mine:
        value = str(r.get("change") or "").replace("\\", "\\\\").replace("\t", "\\t")
        value = value.replace("\n", "\\n").replace("\r", "\\r")
        # the HANDLE, spelled exactly as `--mark-answered` will match it — printing `_num`'s
        # `?` for a string/absent/NaN `ts` made three distinct rows indistinguishable and
        # un-markable, so such a queue could never reach zero (review round 1)
        out.append(f"{_ts_key(r.get('ts'))}\t{_axis_of(str(r.get('change') or ''))}\t{value}")
    return "\n".join(out)


OBSERVER_SEATS = 4  # how many commands are expensive enough to pay for a writer seat


def observer_rank(rows: list[dict], seats: int = OBSERVER_SEATS) -> str:
    """The commands a close should spend a writer seat on — top N by MEAN `tok_in`+`tok_out`.

    Cache tokens are EXCLUDED: :func:`_io_total` is reused rather than re-summed, because the
    cache-inclusive figure this file also publishes ran 200-320x higher on the same rows and would
    rank a long cached conversation as heavy work (spec § Q2, § Reproduce R9).

    The close-out fragment consults this at close time, so the list is DERIVED from live data and
    cannot rot the way four command names pasted into a box-wide file would. It degrades in both
    directions on purpose: fewer than N qualifying commands prints the ones that do with the
    denominator, and no qualifying row at all says so — a closing agent that reads either just
    writes its own line.
    """
    per: dict[str, list[int]] = collections.defaultdict(list)
    for r in rows:
        cmd = str(r.get("command") or "")
        io = _io_total(r)
        if cmd and io is not None:
            per[cmd].append(io)
    commands = {str(r.get("command") or "") for r in rows if r.get("command")}
    if not per:
        return (
            f"observer-rank: nothing measurable — 0 of {len(commands)} command(s) carry a token "
            "pair; write the change: line yourself"
        )
    ranked = sorted(per.items(), key=lambda kv: -(sum(kv[1]) / len(kv[1])))[:seats]
    head = (
        f"observer-rank: {len(ranked)} of {len(per)} command(s) with a token pair "
        f"(of {len(commands)} seen) — a close for one of these dispatches a writer seat"
    )
    body = [f"/{cmd}\t{round(sum(v) / len(v)):,} mean tok/close\tn={len(v)}" for cmd, v in ranked]
    return "\n".join([head, *body])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Per-command optimisation report over the feedback ledger."
    )
    ap.add_argument(
        "--since", type=_finite_arg, default=None, help="only rows from the last N days"
    )
    ap.add_argument("--command", default=None, help="one command name (without the slash)")
    ap.add_argument("--agent", default=None, help="one agent name (CLAUDE_AGENT at start)")
    ap.add_argument(
        "--observer-rank",
        action="store_true",
        help=(
            "print the commands whose closes are expensive enough to pay for a writer seat — the "
            "top four by MEAN tok_in+tok_out per close, cache excluded — and exit"
        ),
    )
    ap.add_argument(
        "--queue",
        default=None,
        metavar="COMMAND",
        help=(
            "print one command's change: queue — TAB-separated `<ts> <bucket> <value>`, newest "
            "first — and exit; the input /fabrik-command-improve reads"
        ),
    )
    ap.add_argument(
        "--mark-answered",
        default=None,
        metavar="COMMAND",
        help=(
            "record that an applied edit answered rows of this command's queue — needs --rows "
            "(comma-separated ts handles from --queue) and --commit (the SHA of the edit). The "
            "commit must touch a corpus path or nothing is marked."
        ),
    )
    ap.add_argument("--rows", default="", help="--mark-answered: comma-separated ts handles")
    ap.add_argument("--commit", default="", help="--mark-answered: the SHA of the applied edit")
    ap.add_argument(
        "--repo", type=Path, default=Path("/opt/fabrik"), help="--mark-answered: repo to verify in"
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ledger", type=Path, default=None)
    a = ap.parse_args(argv)
    # `a.ledger or _default_ledger()` was the bug: `Path("")` is `PosixPath(".")`, which is TRUTHY
    # and a directory, so a caller-computed empty path silently read the CWD and reported zero rows.
    ledger = a.ledger if a.ledger is not None else _default_ledger()
    if a.ledger is not None and not a.ledger.is_file():
        # NOT an error: a repo whose agents have never closed a command has no ledger, and an empty
        # report is the honest answer there (pinned by its own grader). But a typo and an empty
        # ledger are indistinguishable in stdout, so the difference goes to stderr where a human
        # sees it and a parsing caller does not.
        print(f"ledger: {a.ledger} is not a readable file — reporting zero rows", file=sys.stderr)
    rows = _rows(ledger)
    if (
        a.queue is not None
        and a.command is not None
        and a.queue.lstrip("/") != a.command.lstrip("/")
    ):
        ap.error("--queue and --command name different commands; pass one of them")
    if a.queue is not None and a.observer_rank:
        ap.error("--queue and --observer-rank are two different reports; pass one of them")
    if a.queue is not None or a.observer_rank:
        # the same window and filters the report uses — an all-time answer to a --since question
        # would name a command retired months ago, silently. `is not None` and not truthiness:
        # `--queue ""` is a name the caller computed, and falling through to the full report on it
        # is a different program with no diagnostic
        cutoff = time.time() - a.since * 86400 if a.since is not None else None
        rows = [
            r
            for r in rows
            if (cutoff is None or (_num(r.get("ts")) or 0) >= cutoff)
            and (a.command is None or r.get("command") == a.command)
            and (a.agent is None or str(r.get("agent") or "") == a.agent)
        ]
    if a.mark_answered is not None:
        # the same mode-exclusivity the `--queue`/`--observer-rank` pair already has: combining
        # them silently ran ONE, and this command's own PHASE 5 tells the agent to verify with
        # `--queue` in the same breath (review round 1)
        if a.queue is not None or a.observer_rank:
            print("REFUSED — --mark-answered WRITES; run it alone, then --queue to verify.")
            return 2
        ts_rows = [t.strip() for t in a.rows.split(",") if t.strip()]
        if not a.commit or not ts_rows:
            # guarded on the PARSED list: `--rows ',,,'` passed a raw-string test and then
            # reported the vacuously true "all 0 row(s) were already marked"
            print("REFUSED — --mark-answered needs --commit and at least one --rows handle.")
            return 2
        written, message = mark_answered(
            a.mark_answered,
            ts_rows,
            a.commit,
            a.repo,
            path=_answered_path(ledger),
            ledger=ledger,
        )
        print(message)
        # 0 = the index now reflects the edit (a fresh mark, or an idempotent no-op);
        # 1 = REFUSED or PARTIAL, i.e. the caller must look. A script could not tell the three
        # apart while "already marked" shared rc 1 with a refusal.
        return 0 if (written or message.startswith("nothing to do")) else 1
    if a.queue is not None:
        text = queue(rows, a.queue, ledger)
        if a.json:
            sys.stdout.write(json.dumps({"queue": text.split("\n")}, indent=1) + "\n")
        else:
            sys.stdout.write(text + "\n")
        return 0
    if a.observer_rank:
        text = observer_rank(rows)
        if a.json:
            sys.stdout.write(json.dumps({"observer_rank": text.split("\n")}, indent=1) + "\n")
        else:
            sys.stdout.write(text + "\n")
        return 0
    report = build(rows, a.since, a.command, a.agent)
    sys.stdout.write(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n" if a.json else render(report) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
