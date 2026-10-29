#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/review-loop-workflow.md | tests/test_review_loop_ledger.py | commands/_sources/fabrik-review.md
"""review_loop_ledger — a review pass's ledger, read from its workflow run into a FILE (row 5b, D-357).

`fabrik-review-loop` returns its ledger as one tool result, escaped and often truncated; the lead used to
re-derive each pass from it with an ad-hoc script, and hand-typed the next pass's claim list (once as strings
the script rendered `undefined`). Finding 30 of `docs/reference/command-loop-performance.md`: the lead reads a
file, not its scrollback. So:

    review_loop_ledger.py read RUN_DIR [--out FILE] [--box MIN]
        RUN_DIR is the run's transcript dir (the Workflow launch prints it; it holds `journal.jsonl` and one
        `agent-<id>.jsonl` per seat). Writes {seats, candidates, verdicts, ledger_status, ledger_flags} to FILE
        and prints a compact table; `ledger_flags` prints as ledger CONTRADICTION / DISAGREE (advisory,
        `ledger_flags`). Every seat carries its MINUTES, from its transcript's first and last timestamp — the
        Workflow API has no per-agent timeout, so an overrun is only ever visible here (`OVER BOX`; one refuter
        ran 59 minutes against a 12-minute box on 2026-09-23). A seat with no result row is `NO RESULT` — or
        `RUNNING` while the workflow's run file is absent (`workflow_state`: the read then exits 5), and an ended
        run's own failures print as SLICE DROPPED / REFUTER FAILED / SEAT FAILED, and an ended run with no result
        prints the first line of the run file's `error` (a review loop whose every finder came back null throws,
        W-b36e2a4a). Each seat also keeps its
        `notes` (every result's non-blank string note: its coverage statement and MACHINERY block) and its
        `files_read` (every result's non-blank string entries, trimmed and deduplicated), so a lead resuming from
        FILE still has what the close-out feedback is built from.
    review_loop_ledger.py next FILE --ids A-S1,B-S2 [--args RUN_OR_ARGS] [--drop ID,ID]
        The next pass's `slices[].ledger` for those confirmed ids (and, with --args, the open claims carried below), as objects grouped by slice (the id
        prefix). An id the pass never raised is refused by name; an id two raw claims share is refused with
        every claim listed. With --args (mail 01M4PHYNXJ) — the run's `workflows/<runId>.json`, or a bare args
        object — each slice is emitted whole (files, models, scope, priority, agent copied from the launch, its
        ledger replaced), so stdout is the next launch's `slices`; a run file resolves each id against its
        `result` union candidates, the ids the verdicts carry (`A-S1#2`), never a numbering of its own. stderr
        names the launch slices not carried and the `DISPATCH:` stamp (finders + one refuter per slice).
        Every OPEN claim the --ids leave out is CARRIED too (W-b1f67743, /fabrik-spec-review row 1790195711): with
        a run file, a union candidate whose verdict (the workflow's own, normalised) is confirmed or unverified, and
        with --args a DEFECT_PRESENT/NEW ledger_status id no candidate carries, from the launch ledger
        (`open_claims`). stderr says `CARRIED <id>`; `OPEN NOT CARRIED <id>` when nothing resolves it; `NOT CHECKED
        <n> candidate(s)` when no run file was given, since verdicts are read from it alone; `--drop ID[,ID]`
        closes an open claim the lead settled outside the pass file (`DROPPED <id>`), and a --drop id that is not
        open, or is in --ids, is refused.
    review_loop_ledger.py pin --pins-dir DIR [--from REF] [--base SHA] [--replace] FILE…
        Run from the repo root before a pass (kaizen 01M4CGJZAX): writes each FILE to DIR/<FILE> — from the
        working tree, or with --from from that commit (a committed range) — and makes every pin AND directory
        read-only (with the directory writable, `sed -i` renames over a 0444 pin). Writes DIR/MANIFEST.md5
        (md5sum format, repo-relative: the live-file check from the repo root), DIR/MANIFEST.pins.md5 (the
        copies by absolute path: checks the pins from any cwd) and DIR/MANIFEST.json, and with --base extracts that whole commit read-only into
        DIR.base. Writes DIR/change.diff from a basis to the pins (`_change_diff`). On STDERR it prints `UNCHANGED
        <file>` for a pin equal to that basis, `DIRTY <file>` for a working-tree pin that is not HEAD's bytes and
        `SKIPPED <member>` for a base member it leaves out; STDOUT is the Workflow args fragment alone, one JSON
        document — `pins_dir`, `pin_manifest`, `digest` (the md5 of MANIFEST.md5), `pins_digest` (of MANIFEST.pins.md5),
        `change_diff`, `change_diff_md5`, `basis`, `unchanged`, `dirty` and, with --base, `base_pin_dir` and
        `base_skipped` (the advisory lines' lists are in the JSON too, for a caller that reads stdout alone) — and the
        workflow refuses a slice file the manifest lacks before any seat runs. A used DIR is refused: each pass
        gets a NEW one (`--replace` re-pins on purpose). A workflow script has no filesystem, so the pins are
        the lead's verb, never the script's.
        With --base MANIFEST.json also records `base_copy` (the commit DIR.base holds) and `base_skipped` (the members
        its safe extract left out); a --replace re-pin without
        --base removes a previous pin's DIR.base, which no manifest would vouch for.
    review_loop_ledger.py stage --pins-dir DIR --out SCRATCH/arch
        A seat's test tree in one command (W-b976638f, kaizen 01M5PN3806): DIR.base copied when MANIFEST.json's
        `base_copy` equals its `base_sha`, else that commit archived whole (the tar under SCRATCH/tmp), made writable,
        every pin laid over it by the recipe's link rules and md5-checked; SCRATCH/home and SCRATCH/tmp made; ONE
        JSON line printed (`arch`, `source`, `base_sha`, `overlaid`, `skipped`, `pytest` — PYTEST_PINS's launcher,
        filled in). Any refusal exits 2 and removes the half-built tree; it never deletes anything else.
    review_loop_ledger.py read RUN_DIR --pins DIR …
        After the pass, BEFORE any fix, re-hashes every manifest entry into the pass file's `pins`: a pin whose
        bytes changed is `PIN MOVED` — the pass is void for the slices that read it, the read exits 3, and it
        names every seat whose transcript span, widened by two minutes, covers the pin's mtime (attribution
        without an agent step per seat); a working-tree pin whose live file no longer matches is `LIVE MOVED`, informational — the lead's
        own fix or a sibling's commit moves it, so its candidates are re-verified against the current tree. A
        DIR with no manifest reads `UNPINNED`, and a read without --pins says `pins: NOT CHECKED`. It also
        diffs the live TREE against the snapshot `pin` took at the toplevel before writing (infra 01M4CV040F — a
        seat's cwd is the live checkout, so a relative `git archive -o arch.tar` lands there): NEW UNTRACKED,
        NEW IGNORED (collapsed dirs), NEW MODIFIED (a tracked file outside the manifest) and CHANGED AGAIN, each
        with its size and the seats live then — informational, a sibling's file shows too — and SEAT ARCHIVE, a
        tar whose pax comment names a commit of this repo, which exits 4 (PIN MOVED's 3 wins). A snapshot that
        cannot run reads `tree: NOT CHECKED` and never fails the read.

COBRA (D-253): the cheapest way to a clean-looking file is a pass whose seats returned nothing — a seat with
no result is printed `NO RESULT` and kept in `seats` with `returned: false`, never dropped. For the pins, the
workflow refuses a launch without `pin_manifest`, but it cannot hash, so a hand-typed map of the right shape
gets through — said HERE, on the path the lead does read: `UNPINNED` for a pins dir with no MANIFEST.json,
`pins: NOT CHECKED` without the flag. The cheapest way past `read --pins` is to drop the flag: that is the
NOT CHECKED line, which the receipt's Pass row must then carry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path


def _minutes(transcript: Path) -> float | None:
    stamps = []
    try:
        for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                t = json.loads(line).get("timestamp")
            except (ValueError, AttributeError):
                continue
            if t:
                stamps.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
    except OSError:
        return None
    # the span, not last-minus-first: an out-of-order line made a negative duration read as within box (A-H1)
    return round((max(stamps) - min(stamps)).total_seconds() / 60, 1) if len(stamps) > 1 else None


_USAGE = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_read", "cache_read_input_tokens"),
    ("cache_create", "cache_creation_input_tokens"),
)


def _tokens(transcript: Path) -> dict | None:
    """A seat's tokens from its own transcript (D-358): every assistant message's `usage`, counted ONCE per
    message id (the per-field maximum over its lines) — a streamed message is logged more than once. No OpenTelemetry collector is needed for this:
    Claude Code's token metrics label a user-defined agent `custom`, while the transcript is the seat's own."""
    # per message id, the per-field MAXIMUM over its lines — command_run.py's rule, because an id can carry a
    # trailing all-zero line beside the real one (review of D-358, A-S3); a message with no id is its own message,
    # never dropped (B-S2)
    per: dict[str, dict] = {}
    try:
        for n, line in enumerate(
            transcript.read_text(encoding="utf-8", errors="replace").splitlines()
        ):
            try:
                m = json.loads(line).get("message")
            except (ValueError, AttributeError):
                continue
            if not (isinstance(m, dict) and isinstance(m.get("usage"), dict)):
                continue
            key = m.get("id") or f"#line{n}"
            prev = per.setdefault(key, {})
            for _, src in _USAGE:
                v = m["usage"].get(src)
                if isinstance(v, int) and not isinstance(v, bool) and v > prev.get(src, 0):
                    prev[src] = v
    except OSError:
        return None
    tot = {k: sum(u.get(src, 0) for u in per.values()) for k, src in _USAGE}
    return {**tot, "messages": len(per)}


_ENDED = frozenset({"completed", "killed", "failed"})


def run_file_of(run: Path) -> Path | None:
    """The harness writes `<session>/workflows/<runId>.json` only when the workflow ENDS — completed, killed or
    failed (2412 of 2412 runs on this box had one, 2026-10-13) — and keeps the seats' transcripts at
    `<session>/subagents/workflows/<runId>`. Judged on the resolved path, so `read .` from inside the run dir and a
    symlinked fleet root both count; a run dir outside that layout (a copy, a test fixture) has none."""
    run = run.resolve()
    if run.parent.name == "workflows" and run.parent.parent.name == "subagents":
        return run.parent.parent.parent / "workflows" / f"{run.name}.json"
    return None


def _idle_minutes(run: Path) -> float | None:
    try:
        newest = max(p.stat().st_mtime for p in run.iterdir())
    except (OSError, ValueError):
        return None
    return max(0.0, (datetime.now().timestamp() - newest) / 60)


def workflow_state(run: Path) -> dict | None:
    """What the workflow itself said, from its run file — None outside the harness layout. `wait` is True while
    there is nothing final to read: no run file yet (running), a file that does not parse (it may be mid-write),
    or a status other than completed, killed or failed. Ended, it carries the failures the workflow recorded:
    failed refuters, failed seats and dropped slices (a slice whose stage threw is absent from `result.slices`).

    COBRA (D-253): the cheapest clean table is one read before the seats finish; a read with `wait` now exits 5,
    so a scripted read cannot adjudicate half a pass, and a resultless seat prints RUNNING, never NO RESULT. A
    session that died mid-run leaves no run file and reads RUNNING forever — it fails closed, and the line shows
    how long the run dir has been idle so the lead can tell."""
    f = run_file_of(run)
    if f is None:
        return None
    if not f.exists():
        return {
            "status": "running",
            "wait": True,
            "no_file": True,
            "run_file": str(f),
            "idle_min": _idle_minutes(run),
        }
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        status = str(doc.get("status") or "unknown")
    except (OSError, ValueError, AttributeError) as exc:
        return {
            "status": "unreadable",
            "wait": True,
            "run_file": str(f),
            "reason": f"{type(exc).__name__}: {exc}",
        }
    if status not in _ENDED:
        return {"status": status, "wait": True, "run_file": str(f), "idle_min": _idle_minutes(run)}
    res = doc.get("result")
    if not isinstance(res, dict):
        # W-b36e2a4a: a run that THREW (the review loop does when no finder returned anything) keeps its message
        # in `error`; its first NON-BLANK line is the cause and the check the lead reads before relaunching
        # (review pass 1, B-S2: a message opening with a newline printed nothing)
        lines = (ln.strip() for ln in str(doc.get("error") or "").splitlines())
        error = next((ln for ln in lines if ln), "")[:300]
        return {
            "status": status,
            "wait": False,
            "run_file": str(f),
            "result": False,
            "error": error,
        }
    slices = []
    for s in res.get("slices") or []:
        if not isinstance(s, dict):
            continue
        ref = s.get("refuter") if isinstance(s.get("refuter"), dict) else {}
        slices.append(
            {
                "name": s.get("name"),
                "failed_seats": [
                    x.get("model")
                    for x in s.get("seats") or []
                    if isinstance(x, dict) and x.get("failed")
                ],
                "refuter_failed": bool(ref.get("failed")),
                "refuter_reason": ref.get("reason") or "",
                "open": [str(o) for o in s["open"]]
                if isinstance(s.get("open"), list)
                else ([str(s["open"])] if s.get("open") else []),
            }
        )
    args = doc.get("args") if isinstance(doc.get("args"), dict) else {}
    launched = [
        s["name"]
        for s in args.get("slices") or []
        if isinstance(s, dict) and isinstance(s.get("name"), str) and s["name"]
    ]
    returned = {s["name"] for s in slices}
    return {
        "status": status,
        "wait": False,
        "run_file": str(f),
        "result": True,
        "closable": res.get("closable"),
        "failed_refuters": res.get("failed_refuters"),
        "dropped_seats": res.get("dropped_seats"),
        "dropped_slices": res.get("dropped_slices"),
        "dropped_names": [n for n in launched if n not in returned],
        "slices": slices,
    }


def read_run(run: Path, box: float | None) -> dict:
    journal = run / "journal.jsonl"
    if not journal.is_file():
        raise FileNotFoundError(
            f"{journal} is missing — pass the run's transcript dir (the Workflow launch prints it)"
        )
    # Nothing the journal carries is dropped (review of D-357, pass 1): a result row with no started row is a
    # seat of its own (A-S1), every result row of an agent is kept and counted (A-S7), and a row that cannot be
    # read is counted and printed, never raised as another subcommand's error (A-S3).
    labels: dict[str, str] = {}
    results: dict[str, list] = {}
    unreadable = 0
    for line in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        aid = row.get("agentId") if isinstance(row, dict) else None
        if not aid:
            unreadable += row.get("type") in ("started", "result") if isinstance(row, dict) else 1
            continue
        if row.get("type") == "started":
            labels[aid] = row.get("label", aid)
        elif row.get("type") == "result":
            results.setdefault(aid, []).append(row.get("result"))
    wf = workflow_state(run)
    waiting = bool(wf and wf["wait"])
    doc: dict = {
        "run": str(run),
        "workflow": wf,
        "unreadable_rows": unreadable,
        "seats": [],
        "candidates": [],
        "verdicts": [],
        "ledger_status": [],
    }
    for aid in list(labels) + [a for a in results if a not in labels]:
        # an orphan is labelled as one, so it can never read as a real seat's label (A-NEW2)
        label = labels.get(aid, f"orphan:{aid}")
        meta = run / f"agent-{aid}.meta.json"
        try:
            model = json.loads(meta.read_text()).get("model")
        except (OSError, ValueError):
            model = None
        minutes = _minutes(run / f"agent-{aid}.jsonl")
        got = [r for r in results.get(aid, []) if isinstance(r, dict)]
        # a finder that returned but listed no file reviewed nothing (01M4C00TSS); the workflow fails it when no
        # SLICE file is credited, which needs the slice list this reader does not have — so only the zero case here
        # what the seat read: every result's non-blank string entries, trimmed, deduplicated, first-seen order —
        # one rule for the pass file's `files_read` and for this flag, so a `[null]` reads as no file in both
        files_read = list(
            dict.fromkeys(
                e.strip()
                for r in got
                if isinstance(r.get("files_read"), list)
                for e in r["files_read"]
                if isinstance(e, str) and e.strip()
            )
        )
        read_none = label.startswith("find:") and bool(got) and not files_read
        doc["seats"].append(
            {
                "label": label,
                "model": model,
                "minutes": minutes,
                "over_box": bool(box is not None and minutes is not None and minutes > box),
                "untimed": minutes is None,
                "tokens": _tokens(run / f"agent-{aid}.jsonl"),
                "returned": bool(got),
                "running": waiting and not got,
                "read_no_file": read_none,
                "duplicate_results": len(got),
                # the seat's own report — its coverage statement and MACHINERY block — and what it read, kept so
                # a lead resuming from the pass file can still write the close-out (kaizen 01M55F55HE); a seat can
                # return more than once, so `notes` keeps each result's non-blank string note
                "notes": [
                    r["notes"]
                    for r in got
                    if isinstance(r.get("notes"), str) and r["notes"].strip()
                ],
                "files_read": files_read,
            }
        )
        for result in got:
            for c in result.get("candidates") or []:
                doc["candidates"].append({**c, "seat": label})
            for st in result.get("ledger_status") or []:
                doc["ledger_status"].append(
                    {**st, "seat": label, **({"read_no_file": True} if read_none else {})}
                )
            for v in result.get("verdicts") or []:
                doc["verdicts"].append({**v, "seat": label})
    doc["ledger_flags"] = ledger_flags(doc)
    return doc


# A legacy label reads as its successor, so a run that mixes the two vocabularies compares like with like
# (W-729416b3: STILL_TRUE / NOW_FALSE named the claim's truth, and a Haiku seat read a re-verified claim as true)
_LEGACY_STATUS = {"STILL_TRUE": "DEFECT_PRESENT", "NOW_FALSE": "DEFECT_ABSENT"}


def _fold(x: object) -> str:
    """The workflow's `foldId` (.claude/workflows/fabrik-review-loop.js): trim, then lower-case."""
    return str(x if x is not None else "").strip().lower()


def open_claims(
    doc: dict, result: dict | None, launch: dict | None
) -> tuple[list[tuple[str, str, dict, str]], list[str], list[str]]:
    """The claims a pass leaves OPEN: `(id, slice, ledger row, why)` each; the ids reported open that nothing can
    carry (no row resolves it, or the run file repeats it); and one folded id per candidate left unjudged (no run file, or a slice with no verdicts list).

    Verdicts are read only from a run file's `result` (`--args <workflows/<runId>.json>`), never re-derived: there
    the workflow has already normalised each verdict (`verdictFor` — a refutation without counter-evidence, a
    conflict or no answer is `unverified`), made every id unique (`A-S1#2`), folded seat echoes, moved claims on a
    `recorded: true` ledger entry to its `recorded` list and named each slice as it launched. A candidate is open
    when its verdict is confirmed or unverified; one with no verdict at its index (a short or missing list) is
    `unverified` — it is re-verified, never dropped; a slice with no `verdicts` list at all was never judged, and
    its candidates count as unchecked. A DEFECT_PRESENT/NEW ledger_status id that no candidate
    carries (compared through `_fold`) is carried from the launch ledger, unless that entry is `recorded: true`.
    Without a run file no candidate is judged: their folded ids are returned so the lead is told how many lie
    outside its ids, instead of a second copy of the workflow's rule drifting from it (review round 1).

    COBRA (D-253): the cheapest way to keep a pass small is to `--drop` every carried id; each drop is printed by
    id beside the carried ones, so what the lead closed by hand stays visible in the transcript."""
    opened: list[tuple[str, str, dict, str]] = []
    claimed: set[str] = set()  # folded ids some candidate (or recorded candidate) carries

    def row(c: dict, cid: str) -> dict:
        return {"id": cid, "file": c.get("file"), "line": c.get("line"), "claim": c.get("claim")}

    union = result.get("slices") if isinstance(result, dict) else None
    unchecked: list[str] = []
    union_ids: dict[str, str] = {}  # folded id -> the first spelling the run carried
    repeated: set[str] = set()  # folded ids carried more than once
    if isinstance(union, list):
        for s in union:
            if not isinstance(s, dict) or not isinstance(s.get("name"), str):
                continue
            cands = s.get("candidates") if isinstance(s.get("candidates"), list) else []
            verds = s.get("verdicts")
            for c in s.get("recorded") if isinstance(s.get("recorded"), list) else []:
                if isinstance(c, dict):
                    claimed.add(_fold(c.get("id")))
            for n, c in enumerate(cands):
                if not isinstance(c, dict) or not isinstance(c.get("id"), str):
                    continue
                if _fold(c["id"]) in union_ids:
                    # the workflow makes union ids unique (`A-S1#2`), as `_from_union` relies on: a repeat names no single
                    # claim, so it is never carried — named instead (review round 2, A-H2); compared folded, as every
                    # other id here is, so `alpha-S1` and `alpha-s1 ` are one repeat (W-9f436e18)
                    repeated.add(_fold(c["id"]))
                union_ids.setdefault(_fold(c["id"]), c["id"])
                claimed.add(_fold(c["id"]))
                # a slice nobody judged (no refuter, an older run file): said, not guessed
                if not isinstance(verds, list):
                    unchecked.append(_fold(c["id"]))
                    continue
                v = verds[n] if n < len(verds) and isinstance(verds[n], dict) else {}
                verdict = str(v.get("verdict") or "unverified")
                if verdict in ("confirmed", "unverified"):
                    opened.append((c["id"], s["name"], row(c, c["id"]), verdict))
    else:
        for c in doc.get("candidates") or []:
            if isinstance(c, dict) and c.get("id") is not None:
                claimed.add(_fold(c.get("id")))
                unchecked.append(_fold(c.get("id")))
    ledger: dict[str, tuple[str, dict]] = {}
    for s in (launch or {}).get("slices") or []:
        if isinstance(s, dict) and isinstance(s.get("ledger"), list):
            for e in s["ledger"]:
                if isinstance(e, dict) and isinstance(e.get("id"), str):
                    ledger.setdefault(_fold(e["id"]), (str(s.get("name")), e))
    stuck: list[str] = []
    seen: set[str] = set()
    for r in doc.get("ledger_status") if isinstance(doc.get("ledger_status"), list) else []:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str):
            continue
        status = _LEGACY_STATUS.get(str(r.get("status")), str(r.get("status")))
        sid, key = r["id"], _fold(r["id"])
        if status not in ("DEFECT_PRESENT", "NEW") or key in claimed or key in seen:
            continue
        seen.add(key)
        hit = ledger.get(key)
        if hit is None:
            stuck.append(sid)
        elif not hit[1].get("recorded"):
            e = hit[1]
            opened.append(
                (e["id"], hit[0], {k: e.get(k) for k in ("id", "file", "line", "claim")}, status)
            )
    # a repeated union id is open but names no single claim: it is reported, never carried
    # one line per repeated claim, under the first spelling the run carried; every spelling is kept out of the carry
    stuck_f = {_fold(i) for i in stuck}
    stuck += sorted(union_ids[f] for f in repeated if f not in stuck_f)
    opened = [o for o in opened if _fold(o[0]) not in repeated]
    return opened, stuck, unchecked


def ledger_flags(doc: dict) -> list[dict]:
    """ADVISORY flags over a later pass's ledger rows — printed for the lead, never a gate.

    `contradiction`: a seat reported a defect PRESENT (or NEW) and raised no candidate at all — the shape of the label
    inversion in mail 01M48MQ2HS (161 of 587 such seats on the box, 104 of them Haiku). A REPORT ONLY (recorded)
    claim legitimately raises none, which is why this is a flag. `disagree`: two seats gave one id different
    statuses. Cobra: a seat avoids the flag by raising any candidate; the refuter executes every candidate, so a
    fake one costs the seat a refuted verdict the lead sees."""
    by_seat: dict[str, list[dict]] = {}
    for s in doc["ledger_status"]:
        by_seat.setdefault(str(s.get("seat")), []).append(s)
    raised = {str(c.get("seat")) for c in doc["candidates"]}
    flags: list[dict] = []
    seen: dict[str, dict[str, str]] = {}
    for seat, rows in by_seat.items():
        for s in rows:
            status = _LEGACY_STATUS.get(str(s.get("status")), str(s.get("status")))
            sid = str(s.get("id"))
            seen.setdefault(sid, {})[seat] = status
            # both labels a candidate must back (review B3 r1 A-S1: NEW alone was never flagged)
            if status in ("DEFECT_PRESENT", "NEW") and seat not in raised:
                flags.append({"kind": "contradiction", "seat": seat, "id": sid})
    for sid, statuses in seen.items():
        if len(set(statuses.values())) > 1:
            flags.append({"kind": "disagree", "id": sid, "statuses": statuses})
    return flags


def _one(x: object, n: int) -> str:
    """One printed line per field: a seat's multi-line output is collapsed, then cut."""
    return " ".join(str(x).split())[:n]


def _print(doc: dict) -> None:
    for s in doc["seats"]:
        mins = "?" if s["minutes"] is None else f"{s['minutes']:.1f} min"
        flags = (
            ("  OVER BOX" if s["over_box"] else "")
            + ("  UNTIMED" if s.get("untimed") else "")
            + ("" if s["returned"] else "  RUNNING" if s.get("running") else "  NO RESULT")
            + ("  READ 0 FILES" if s.get("read_no_file") else "")
            + (
                f"  DUPLICATE RESULT x{s['duplicate_results']}"
                if s.get("duplicate_results", 0) > 1
                else ""
            )
        )
        t = s.get("tokens") or {}
        toks = (
            f"  {t['output']:,} out · {t['cache_read']:,} cache read · {t['input'] + t['cache_create']:,} new in"
            if t.get("messages")
            else ""
        )
        print(f"seat {s['label']:<18} {mins:>9}{toks}{flags}")
    for c in doc["candidates"]:
        print(
            f"candidate {c.get('id')} {c.get('file')}:{c.get('line')} [{c.get('failure_class')}] {_one(c.get('claim'), 240)}"
        )
    for v in doc["verdicts"]:
        print(f"verdict {v.get('id')} {v.get('verdict')} — {_one(v.get('mechanism'), 240)}")
    for s in doc["ledger_status"]:
        print(
            f"ledger {s.get('id')} {s.get('status')} ({s.get('seat')}{', READ 0 FILES' if s.get('read_no_file') else ''}) — {_one(s.get('output'), 160)}"
        )
    for f in doc.get("ledger_flags") or []:
        if f["kind"] == "contradiction":
            print(
                f"ledger CONTRADICTION {f['id']} ({f['seat']}) — a defect reported PRESENT and no candidate raised: "
                "re-execute it yourself (a REPORT ONLY claim raises none by design)"
            )
        else:
            said = " · ".join(f"{k}: {v}" for k, v in sorted(f["statuses"].items()))
            print(f"ledger DISAGREE {f['id']} — {said}: re-execute it yourself")
    tot = [s["tokens"] for s in doc["seats"] if s.get("tokens")]
    if tot:
        print(
            f"pass tokens: {sum(t['output'] for t in tot):,} out · {sum(t['cache_read'] for t in tot):,} cache read · "
            f"{sum(t['input'] + t['cache_create'] for t in tot):,} new in, over {sum(t['messages'] for t in tot)} messages"
        )
    if doc.get("unreadable_rows"):
        print(
            f"{doc['unreadable_rows']} unreadable journal row(s) — a seat may be missing from this table"
        )
    print(
        f"{len(doc['seats'])} seats · {len(doc['candidates'])} candidates · {len(doc['verdicts'])} verdicts · "
        f"{sum(1 for s in doc['seats'] if s['over_box'])} over box · "
        f"{sum(1 for s in doc['seats'] if not s['returned'] and not s.get('running'))} no result · "
        f"{sum(1 for s in doc['seats'] if s.get('running'))} running · "
        f"{sum(1 for s in doc['seats'] if s.get('read_no_file'))} read 0 files"
    )


def _print_workflow(wf: dict | None, run: Path) -> None:
    if wf is None:
        print(f"workflow: NOT CHECKED — {run} is not under <session>/subagents/workflows/")
        return
    st = wf["status"]
    idle = wf.get("idle_min")
    idle_s = (
        ""
        if idle is None
        else f" (run dir idle {idle:.0f} min — long idle may mean the session died)"
    )
    if st == "unreadable":
        print(
            f"workflow: UNREADABLE ({wf['reason']}) — it may be mid-write; read again: {wf['run_file']}"
        )
    elif wf["wait"]:
        state = "RUNNING — no run file yet" if wf.get("no_file") else f"{st} — not ended"
        print(
            f"workflow: {state}; adjudicate nothing, wait for the workflow's notification and read again{idle_s}"
        )
    elif not wf.get("result"):
        err = f" — {wf['error']}" if wf.get("error") else ""
        print(f"workflow: {st} — no result: every seat without one is NO RESULT{err}")
    else:
        print(
            f"workflow: {st} · {'closable' if wf.get('closable') else 'NOT closable'} · "
            f"{wf.get('failed_refuters') or 0} failed refuter(s) · {wf.get('dropped_seats') or 0} dropped seat(s) · "
            f"{wf.get('dropped_slices') or 0} dropped slice(s)"
        )
        for n in wf.get("dropped_names") or []:
            print(f"SLICE DROPPED {n} — a stage threw; the slice is unverified")
        for s in wf["slices"]:
            if s["refuter_failed"]:
                print(f"REFUTER FAILED {s['name']} — {s['refuter_reason'] or 'no reason recorded'}")
            for m in s["failed_seats"]:
                print(f"SEAT FAILED {s['name']}:{m}")


class LedgerError(Exception):
    """`next` cannot name one claim for an id: never raised, raised twice, or no `<slice>-` prefix."""


def _slice_of(c: dict, cid: str) -> str:
    """The slice that raised a candidate: its finder's label (`find:<slice>:<model>`, or `…:retry` for the seat's one
    retry — W-6399d1a3), else the id before its last `-` — a section slice named `rule-grammar` raises
    `rule-grammar-O1` (review of chunk 6, A-S1)."""
    seat = str(c.get("seat") or "").removesuffix(":retry")
    if seat.startswith("find:") and seat.count(":") >= 2:
        return seat[len("find:") :].rsplit(":", 1)[0]
    return cid.rsplit("-", 1)[0]


_SLICE_FIELDS = ("files", "models", "scope", "priority", "agent")
_DEFAULT_FINDERS = 2  # the workflow's DEFAULT_MODELS: one Sonnet and one Haiku finder per slice


def load_args(path: Path) -> tuple[dict, dict | None]:
    """The launch args and, from a Workflow run file, its result. A run file is an object whose `args` key is an
    object; anything else is read as the args themselves. Either way `slices` must be a list."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise LedgerError(f"--args {path} is not JSON ({exc})") from None
    run = isinstance(raw, dict) and isinstance(raw.get("args"), dict)
    args = raw["args"] if run else raw
    if not isinstance(args, dict) or not isinstance(args.get("slices"), list):
        raise LedgerError(
            f"--args {path} holds no `slices` list — pass the run's workflows/<runId>.json or the launch args"
        )
    result = raw.get("result") if run else None
    return args, result if isinstance(result, dict) else None


def _from_union(result: dict, ids: list[str]) -> dict[str, list]:
    """Each id resolved against the run's union candidates — the ids the verdicts carry, suffix and all. The
    workflow makes them unique per run (slice-prefixed, `#n`-suffixed), so an id two rows carry is a malformed
    file and is refused with both claims listed, never resolved to the first (review round 1, A-S2/B-S2)."""
    found: dict[
        str, list[tuple[str, dict]]
    ] = {}  # keyed by the FOLDED id, as `open_claims` compares (W-9f436e18)
    want = {_fold(i) for i in ids}
    for n, s in enumerate(result["slices"]):
        if not isinstance(s, dict) or not isinstance(s.get("name"), str) or not s["name"]:
            raise LedgerError(
                f"the run file's result slice {n + 1} has no name, so no slice owns its ids"
            )
        cands = s.get("candidates", [])
        if not isinstance(cands, list):
            raise LedgerError(
                f"the run file's result slice {s['name']} has candidates that are not a list"
            )
        for c in cands:
            if isinstance(c, dict) and isinstance(c.get("id"), str) and _fold(c["id"]) in want:
                found.setdefault(_fold(c["id"]), []).append((s["name"], c))
    missing = [i for i in ids if _fold(i) not in found]
    if missing:
        raise LedgerError(f"id(s) the run's union candidates never carried: {', '.join(missing)}")
    twice = [i for i in ids if len(found[_fold(i)]) > 1]
    if twice:
        menu = "; ".join(
            f"{i}: "
            + " · ".join(
                f"[slice {n}] {c.get('file')}:{c.get('line')} {str(c.get('claim'))[:80]!r}"
                for n, c in found[_fold(i)]
            )
            for i in twice
        )
        raise LedgerError(
            f"id(s) the run file carries more than once, so they name no single claim — {menu}"
        )
    slices: dict[str, list] = {}
    for i in ids:
        name, c = found[_fold(i)][0]
        slices.setdefault(name, []).append(
            {"id": c["id"], "file": c.get("file"), "line": c.get("line"), "claim": c.get("claim")}
        )
    return slices


def _from_pass(doc: dict, ids: list[str]) -> dict[str, list]:
    # a byte-identical repeat (a result row delivered twice) is ONE claim; only distinct claims sharing an id
    # are ambiguous (A-NEW1)
    by_id: dict[str, list] = {}
    for c in doc["candidates"]:
        rows = by_id.setdefault(c.get("id"), [])
        key = (c.get("file"), c.get("line"), c.get("claim"))
        if all((r.get("file"), r.get("line"), r.get("claim")) != key for r in rows):
            rows.append(c)
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise LedgerError(f"id(s) this pass never raised: {', '.join(missing)}")
    twice = [i for i in ids if len(by_id[i]) > 1]
    if twice:
        # The raw ids are not the verdicts' ids: the workflow absorbs a cross-seat twin and suffixes the rest
        # (`A-S1#2`), so a number assigned here could name a different claim than the verdict did, and keeping
        # the first could carry a refuted claim while the confirmed one is dropped (mail 01M4PHYNXJ, both
        # design critiques). So the refusal stays — as the menu, with the exact path out.
        menu = "; ".join(
            f"{i}: "
            + " · ".join(
                f"[{c.get('seat')}] {c.get('file')}:{c.get('line')} {str(c.get('claim'))[:80]!r}"
                for c in by_id[i]
            )
            for i in twice
        )
        raise LedgerError(
            f"id(s) raised more than once (by one seat or two), so they name no single claim — {menu} — pass "
            "--args <the run's workflows/<runId>.json> to resolve the verdicts' own ids, or the claim by hand "
            "as {id, file, line, claim}"
        )
    bare = [i for i in ids if "-" not in i or not i.split("-", 1)[0]]
    if bare:
        raise LedgerError(
            f"id(s) with no `<slice>-` prefix, so no slice owns them: {', '.join(bare)}"
        )
    slices: dict[str, list] = {}
    for i in ids:
        c = by_id[i][0]
        slices.setdefault(_slice_of(c, i), []).append(
            {"id": i, "file": c.get("file"), "line": c.get("line"), "claim": c.get("claim")}
        )
    return slices


def next_ledger(
    doc: dict,
    ids: list[str],
    args: dict | None = None,
    result: dict | None = None,
    carry: list[tuple[str, dict]] | None = None,
) -> list[dict]:
    """The next launch's slices. With `args` every slice carries its launch fields and a REPLACED ledger; with a
    run `result` the ids resolve against the union candidates.

    COBRA (D-253): the cheapest way past the ambiguity refusal is to hand-pick a listed claim without reading the
    verdict; the menu names `--args`, the cheaper exact path. The cheapest way past `not carried` (`carry_notes`)
    is to ignore stderr and drop an unverified slice; the closing round's `round --slices` re-statement is the
    counter."""
    # a repeated --ids entry is one claim (review round 1, A-S3) — compared folded, as `_from_union` resolves it, so
    # `alpha-S1,ALPHA-s1` is one row, never two (W-9f436e18); the first spelling is kept
    seen: set[str] = set()
    ids = [i for i in ids if not (_fold(i) in seen or seen.add(_fold(i)))]
    slices = (
        _from_union(result, ids)
        if result and isinstance(result.get("slices"), list)
        else _from_pass(doc, ids)
    )
    for name, row in carry or []:  # the open claims the --ids left out (`open_claims`)
        slices.setdefault(name, []).append(row)
    if args is None:
        return [{"name": n, "ledger": rows} for n, rows in slices.items()]
    named = [s.get("name") for s in args["slices"] if isinstance(s, dict)]
    dup = sorted({str(n) for n in named if named.count(n) > 1})
    if dup:
        raise LedgerError(
            f"slice {', '.join(dup)} is named by more than one launch slice of --args"
        )
    launch = {s.get("name"): s for s in args["slices"] if isinstance(s, dict)}
    absent = [n for n in slices if n not in launch]
    if absent:
        raise LedgerError(
            f"slice {', '.join(absent)} is in no launch slice of --args, so its files and models are unknown"
        )
    for n in slices:
        # the emitted slice is the next launch verbatim, so what the workflow would refuse is refused here
        files, models = launch[n].get("files"), launch[n].get("models", [])
        if (
            not isinstance(files, list)
            or not files
            or not all(isinstance(f, str) and f for f in files)
        ):
            raise LedgerError(
                f"launch slice {n} in --args has no `files` list, so the next launch cannot read it"
            )
        if not isinstance(models, list):
            raise LedgerError(
                f"launch slice {n} in --args has `models` that are not a list: {models!r}"
            )
    return [
        {"name": n, **{k: launch[n][k] for k in _SLICE_FIELDS if k in launch[n]}, "ledger": rows}
        for n, rows in slices.items()
    ]


def carry_notes(args: dict, out: list[dict]) -> list[str]:
    """stderr for an --args emit: the launch slices not carried, and the stamp the next launch owes."""
    carried = {s["name"] for s in out}
    left = [
        str(s.get("name"))
        for s in args["slices"]
        if isinstance(s, dict) and s.get("name") not in carried
    ]
    finders = sum(len(s["models"]) if "models" in s else _DEFAULT_FINDERS for s in out)
    notes = [f"not carried: {', '.join(left)} — no id named this pass"] if left else []
    return notes + [
        f"DISPATCH: {finders} finder(s) + {len(out)} refuter(s) = stamp {finders + len(out)}"
    ]


_MANIFEST_NAMES = frozenset({"MANIFEST.md5", "MANIFEST.json", "MANIFEST.pins.md5", "change.diff"})


class PinError(Exception):
    """`pin` cannot pin a named file — absent, a directory, a symlink, outside the repo root — or its pins dir
    is already in use (each pass gets a NEW dir; `--replace` re-pins one on purpose)."""


def _md5(p: Path) -> str:
    return hashlib.md5(
        p.read_bytes(), usedforsecurity=False
    ).hexdigest()  # an identity, not a secret


def _lock_tree(top: Path) -> None:
    """Every file AND directory under `top` (itself included) read-only: with the directory writable, `sed -i`
    (write a new file, rename it over the pin) mutates a 0444 pin at rc 0 — both design critiques executed it."""
    for d, _, names in os.walk(top, topdown=False):
        for n in names:
            p = Path(d) / n
            if not p.is_symlink():
                p.chmod(stat.S_IMODE(p.stat().st_mode) & ~0o222)
        Path(d).chmod(stat.S_IMODE(Path(d).stat().st_mode) & ~0o222)


def _unlock_and_remove(top: Path) -> None:
    for d, _, names in os.walk(top):
        Path(d).chmod(stat.S_IMODE(Path(d).stat().st_mode) | stat.S_IWUSR)
        for n in names:
            p = Path(d) / n
            if not p.is_symlink():
                p.chmod(stat.S_IMODE(p.stat().st_mode) | stat.S_IWUSR)
    shutil.rmtree(top)


def _vcs(root: Path, *argv: str) -> bytes:
    # read-only repository verbs only (show, archive into a temp path): the live repo is never written
    return subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True).stdout


def _fresh(top: Path, replace: bool) -> None:
    if top.exists() and not top.is_dir():
        raise PinError(f"{top} exists and is not a directory — name a NEW pins dir")  # review A-S1
    if top.exists() and any(top.iterdir()):
        if not replace:
            raise PinError(
                f"{top} is already in use — each pass gets a NEW pins dir (a straggling seat may still be "
                "reading the old one); pass --replace to re-pin it on purpose"
            )
        _unlock_and_remove(top)


# the snapshot of the live tree a seat could write into (infra 01M4CV040F), in TWO listings: tracked changes and
# untracked files ONE BY ONE (a collapsed untracked `dir/` hid every file a seat later wrote into it — review A-S1),
# and ignored entries COLLAPSED to their directory (listing every ignored file is 4263 entries of __pycache__ churn
# on this hub, 56 collapsed). A new file inside an ALREADY-ignored dir (data/x) therefore stays unseen; that is
# PIN_IMPORT's FABRIK_ROOT warning, not this check's reach.
_TREE_STATUS = ("--no-optional-locks", "status", "--porcelain=v1", "-z", "--untracked-files=all")
_TREE_IGNORED = ("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
_HASH_CAP = 32 * 1024 * 1024


def _fingerprint(p: Path) -> str:
    try:
        st = p.lstat()
    except OSError:
        return "gone"
    if stat.S_ISDIR(st.st_mode):
        return "dir"
    if st.st_size > _HASH_CAP or not stat.S_ISREG(st.st_mode):
        return f"size:{st.st_size}:{st.st_mtime_ns}"  # full precision: a same-second rewrite still differs (A-S2)
    try:
        return _md5(p)
    except OSError:
        return "gone"


def _tree(root: Path) -> dict | None:
    """`?? untracked` (one by one) · ignored (collapsed) · every other code `modified`, each untracked or modified path with
    its fingerprint. None when the snapshot cannot run there — a caller records "not checked", never fails."""
    try:
        out = _vcs(root, *_TREE_STATUS)
        ignored = _vcs(root, *_TREE_IGNORED)
    except (subprocess.CalledProcessError, OSError):
        return None
    snap: dict = {"untracked": {}, "ignored": [], "modified": {}}
    entries = out.split(b"\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        code, path = e[:2].decode(), e[3:].decode("utf-8", errors="replace")
        if code[0] in "RC":
            i += 1  # a rename or copy carries its source path as the next entry
        if code == "??":
            snap["untracked"][path] = _fingerprint(root / path)
        else:
            snap["modified"][path] = _fingerprint(root / path)
    snap["ignored"] = sorted(e.decode("utf-8", errors="replace") for e in ignored.split(b"\0") if e)
    return snap


def _toplevel(root: Path) -> Path | None:
    try:
        return Path(_vcs(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    except (subprocess.CalledProcessError, OSError):
        return None


def _seat_archive(root: Path, p: Path) -> bool:
    """A tar whose pax `comment` names a commit of THIS repo is a seat's `git archive` (git writes the commit sha
    there); a sibling's legitimate file cannot carry it, so this is the one leak shape precise enough to stop on."""
    try:
        if not (p.is_file() and tarfile.is_tarfile(p)):
            return False
        with tarfile.open(p) as t:
            sha = (t.pax_headers or {}).get("comment", "")
        # a FULL object name only (40 hex, or 64 under SHA-256): a short hex string could resolve as an
        # abbreviation of some commit and misread an unrelated tar as a seat's (review A-S3)
        if len(sha) not in (40, 64) or not all(c in "0123456789abcdef" for c in sha.lower()):
            return False
        _vcs(root, "cat-file", "-e", f"{sha}^{{commit}}")
        return True
    except (OSError, tarfile.TarError, subprocess.CalledProcessError, UnicodeError):
        return False


def _tree_changes(root: Path, before: dict, after: dict, skip) -> list[dict]:
    changes: list[dict] = []
    for kind_new, kind_old, b, a in (
        ("NEW UNTRACKED", "CHANGED AGAIN", before["untracked"], after["untracked"]),
        ("NEW MODIFIED", "CHANGED AGAIN", before["modified"], after["modified"]),
    ):
        for path, fp in a.items():
            if skip(path):
                continue
            if path not in b:
                changes.append({"path": path, "kind": kind_new})
            elif fp != b[path] and fp != "dir":
                changes.append({"path": path, "kind": kind_old})
    for path in after["ignored"]:
        if path not in before["ignored"] and not skip(path):
            changes.append({"path": path, "kind": "NEW IGNORED"})
    for c in changes:
        full = root / c["path"].rstrip("/")
        try:
            st = full.lstat()
            c["size"] = None if stat.S_ISDIR(st.st_mode) else st.st_size
            c["mtime"] = st.st_mtime
            c["dir"] = stat.S_ISDIR(st.st_mode)
        except OSError:
            c.update({"size": None, "mtime": None, "dir": False, "gone": True})
        if c["kind"] in ("NEW UNTRACKED", "NEW IGNORED") and _seat_archive(root, full):
            c["kind"] = "SEAT ARCHIVE"
    return changes


def _change_diff(
    root: Path, basis: str, blobs: dict[str, bytes], explicit: bool
) -> tuple[bytes, list[str]]:
    """One diff per pinned file, from `basis` to the pinned bytes (01M4PNBVJ1 row 1791099162), and the files whose
    pin equals the basis (UNCHANGED, row 1791481582 — compared to the SAME basis, so a committed change read with
    --base is never called unmade). `git diff --no-index` over two scratch copies, never difflib, so a missing
    final newline, a non-UTF-8 or binary file all come out as git prints them; a file absent at the basis — an
    untracked file, or every file when an IMPLIED basis does not resolve (HEAD in a repo with no commit yet, `<ref>^`
    of a root commit) — diffs from /dev/null. An EXPLICIT basis (`--base`) that does not resolve is refused, whatever
    its spelling (review round 1, A-H1 and A-S3/B-S3: keying the fallback on a trailing `^` refused a fresh repo's
    working-tree pin and admitted `--base <typo>^`). `<ref>^` is ONE commit: a multi-commit range needs `--base`."""
    try:
        _vcs(root, "rev-parse", "--verify", "-q", f"{basis}^{{commit}}")
        resolved = True
    except subprocess.CalledProcessError:
        resolved = False
    if not resolved and explicit:
        # a --base typo would otherwise diff every file from /dev/null and call none UNCHANGED (A1 critique, Fable 3)
        raise PinError(f"cannot diff against {basis}: not a commit here")
    out = [f"# change.diff — basis {basis}, {len(blobs)} pinned file(s)\n".encode()]
    unchanged: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for f, new in blobs.items():
            old = None
            if resolved:  # an unresolved implied basis has no tree: every file diffs from /dev/null
                try:
                    old = _vcs(root, "show", f"{basis}:{f}")
                except subprocess.CalledProcessError:
                    old = None  # the path is absent at the basis: a new file
            if old == new:
                unchanged.append(f)
                continue
            for side, data in (("a", old), ("b", new)):
                if data is not None:
                    (Path(tmp) / side / f).parent.mkdir(parents=True, exist_ok=True)
                    (Path(tmp) / side / f).write_bytes(data)
            r = subprocess.run(
                [
                    "git",
                    "diff",
                    "--no-index",
                    "--no-color",
                    "--no-ext-diff",
                    "--no-prefix",
                    "--",
                    "/dev/null" if old is None else f"a/{f}",
                    f"b/{f}",
                ],
                cwd=tmp,
                capture_output=True,
                check=False,
            )
            if r.returncode not in (0, 1):
                raise PinError(
                    f"cannot diff {f} against {basis}: {r.stderr.decode(errors='replace').strip()}"
                )
            out.append(r.stdout)
    return b"".join(out), unchanged


def _extract_commit(root: Path, sha: str, dest: Path, tmp_dir: Path | None = None) -> list[str]:
    """`git archive` of `sha` extracted into `dest`; returns the members it SKIPPED. A member the "data" filter
    refuses — an absolute or escaping symlink, a device: the hub once tracked `vault -> /…`, untracked since
    W-36c2607c — is SKIPPED and named, never fatal (dogfooding `pin --base` on the hub died on it with a traceback and
    a half-extracted 94 MB base). `stage` passes `tmp_dir` so a seat's tar stays under its own scratch."""
    skipped: list[str] = []
    with tempfile.TemporaryDirectory(dir=tmp_dir) as tmp:
        tar = Path(tmp) / "base.tar"
        _vcs(root, "archive", "-o", str(tar), sha)  # the COMMITTED bytes, never the working tree's
        with tarfile.open(tar) as t:
            # every member is validated BEFORE extraction and only the safe ones are named
            safe: list[tarfile.TarInfo] = []
            for member in t.getmembers():
                try:
                    tarfile.data_filter(member, str(dest))
                except tarfile.FilterError:
                    skipped.append(member.name)
                else:
                    safe.append(member)
            t.extractall(dest, members=safe, filter="data")
    return skipped


def pin(
    files: list[str],
    pins_dir: Path,
    root: Path,
    ref: str | None = None,
    base: str | None = None,
    replace: bool = False,
) -> tuple[dict, list[str]]:
    """Write the pass's pins; return the Workflow args fragment and the DIRTY paths (working-tree mode)."""
    root = root.resolve()
    top = _toplevel(root)
    if top is not None and top != root:
        # from a subdirectory the tree snapshot lists only that subtree and misses a root-level tarball
        raise PinError(f"run pin from the repo toplevel {top}, not {root}")
    if "\n" in str(pins_dir):
        # every MANIFEST.pins.md5 line carries this string, so a newline splits it (W-1008046c review A-S1)
        raise PinError(
            f"cannot pin into {str(pins_dir)!r}: a newline in the pins dir breaks MANIFEST.pins.md5"
        )
    rels: list[str] = []
    # every file is checked before ANYTHING is written, so a refusal leaves no half-built pins dir behind
    for f in files:
        rel = os.path.normpath(f)
        cand = root / rel
        # W-1008046c: a newline splits md5sum's line into a false FAILED, and a root file named like a
        # manifest would be overwritten by it — both refused before anything is written
        if "\n" in rel:
            raise PinError(f"cannot pin {f!r}: a newline in the path breaks the md5 manifests")
        if rel in _MANIFEST_NAMES:
            raise PinError(f"cannot pin {f}: the name is reserved for the pins dir's own files")
        # with --from the bytes come from the commit, so the WORKING-TREE shape of the path (a local
        # symlink, a deletion) is irrelevant: escape is judged lexically and a symlink AT the ref by its
        # tree mode below (pin-refusal wording review A-S1)
        if ref is None and cand.is_symlink():
            raise PinError(f"cannot pin {f}: a symlink (its bytes may live outside the repo)")
        outside = rel.startswith("..") or os.path.isabs(rel)
        if outside or (ref is None and not cand.resolve().is_relative_to(root)):
            raise PinError(f"cannot pin {f}: it resolves outside the repo root {root}")
        if ref is None and not cand.is_file():
            raise PinError(
                f"cannot pin {f}: {'not a regular file' if cand.exists() else 'no such file'}"
            )
        rels.append(Path(rel).as_posix())
    blobs: dict[str, bytes] = {}
    for f in rels:
        if ref is not None:
            # a regular file at REF only: `show REF:<dir>` prints a TREE LISTING at rc 0 and a symlink's blob is its
            # target text — either would be pinned as the file's bytes (review pass 1, L-1)
            try:
                entry = _vcs(root, "ls-tree", ref, "--", f).decode(errors="replace").split()
            except subprocess.CalledProcessError as exc:
                raise PinError(
                    f"cannot pin {f} from {ref}: {exc.stderr.decode(errors='replace').strip()}"
                ) from exc
            if not entry:
                raise PinError(f"cannot pin {f} from {ref}: no such path at {ref}")
            if entry[0] not in ("100644", "100755"):
                raise PinError(
                    f"cannot pin {f} from {ref}: not a regular file there (mode {entry[0]})"
                )
            blobs[f] = _vcs(root, "cat-file", "blob", entry[2])
        else:
            blobs[f] = (root / f).read_bytes()
    # computed before anything is written, so a refused basis leaves no pins dir behind
    basis = base or ("HEAD" if ref is None else f"{ref}^")
    change, unchanged = _change_diff(root, basis, blobs, explicit=base is not None)
    # the full commit a seat archives and overlays the pins on (D-1051's "that pin's own base_sha"), recorded so a
    # delta brief can read the previous pass's back from its pin (W-0b09fae6): the `--base` commit when given (the
    # same commit `base_pin_dir` holds, which seats copy in place of archiving base_sha), else the `--from` ref,
    # else HEAD. Only a working-tree pin in a repo with no commit yet records null (A-H1); an anchor given as
    # `--from` or `--base` that names no commit (ls-tree accepts a tree) is refused, since no seat could archive
    # it — a tree `--from` beside a commit `--base` pins, the `--base` commit being the anchor.
    anchor = base or ref or "HEAD"
    try:
        base_sha: str | None = (
            _vcs(root, "rev-parse", "--verify", f"{anchor}^{{commit}}").decode().strip()
        )
    except subprocess.CalledProcessError as exc:
        if base or ref:
            raise PinError(
                f"cannot pin from {anchor}: it names no commit to archive "
                f"({exc.stderr.decode(errors='replace').strip()})"
            ) from exc
        base_sha = None
    # the tree a seat could write into, taken BEFORE any write so the pins dir and its base are never in it
    tree = _tree(root) if top is not None else None
    _fresh(pins_dir, replace)
    base_dir = Path(f"{pins_dir}.base")
    if base:
        _fresh(base_dir, replace)
    elif replace and os.path.lexists(base_dir):
        # the previous pin's copy, of another commit: left beside this manifest it read as this pin's base
        # (W-b976638f, both design critiques replayed it); `stage` also trusts only a copy `base_copy` records
        if base_dir.is_dir() and not base_dir.is_symlink():
            _unlock_and_remove(base_dir)
        else:
            base_dir.unlink()
    dirty: list[str] = []
    if ref is None:
        for f in rels:
            try:
                head = _vcs(root, "show", f"HEAD:{f}")
            except subprocess.CalledProcessError:
                head = None  # untracked: not the commit's bytes either
            if head != blobs[f]:
                dirty.append(f)
    # the base is extracted BEFORE the manifest is written, so the manifest can record what the copy left out
    # (`stage` reports it on the base-copy route, where it reads no tar of its own — review pass 1, A-S5)
    skipped: list[str] = []
    if base:
        base_dir.mkdir(parents=True, exist_ok=True)
        try:
            skipped = _extract_commit(root, base, base_dir)
        except (OSError, tarfile.TarError, subprocess.CalledProcessError) as exc:
            # never leave a half-extracted base for the lead to hand to a seat
            _unlock_and_remove(base_dir)
            raise PinError(f"cannot extract base {base} into {base_dir}: {exc}") from exc
    manifest = {f: hashlib.md5(b, usedforsecurity=False).hexdigest() for f, b in blobs.items()}
    try:
        for f, b in blobs.items():
            (pins_dir / f).parent.mkdir(parents=True, exist_ok=True)
            (pins_dir / f).write_bytes(b)
        (pins_dir / "MANIFEST.md5").write_text("".join(f"{m}  {f}\n" for f, m in manifest.items()))
        # W-1008046c: MANIFEST.md5 is repo-relative, so from the repo root it checks the LIVE files;
        # a seat cannot cd, so the COPIES get their own manifest of absolute paths — the same
        # pins_dir string the fragment prints, never resolved, so a quoted path still matches it
        (pins_dir / "MANIFEST.pins.md5").write_text(
            "".join(f"{m}  {pins_dir}/{f}\n" for f, m in manifest.items())
        )
        (pins_dir / "change.diff").write_bytes(change)
        (pins_dir / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "root": str(root),
                    "source": ref or "working-tree",
                    "base_sha": base_sha,
                    # the commit `<pins_dir>.base` holds, present only when THIS pin wrote it (`stage` copies
                    # a base only when it equals base_sha — an unrecorded copy may be another pin's)
                    **({"base_copy": base_sha, "base_skipped": skipped} if base else {}),
                    "files": manifest,
                    "change_diff": hashlib.md5(change, usedforsecurity=False).hexdigest(),
                    "tree": tree,
                },
                indent=1,
            )
        )
    except OSError as exc:
        # a half-written, still-writable pins dir is never left for a seat to read (review A-S3), nor its base
        if pins_dir.exists():
            _unlock_and_remove(pins_dir)
        if base and base_dir.exists():
            _unlock_and_remove(base_dir)
        raise PinError(f"cannot write the pins into {pins_dir}: {exc}") from exc
    frag: dict = {
        "pins_dir": str(pins_dir),
        "pin_manifest": manifest,
        "digest": _md5(pins_dir / "MANIFEST.md5"),
        "pins_digest": _md5(pins_dir / "MANIFEST.pins.md5"),
        "change_diff": str(pins_dir / "change.diff"),
        "change_diff_md5": _md5(pins_dir / "change.diff"),
        "basis": basis,
        "base_sha": base_sha,
        "unchanged": unchanged,
    }
    _lock_tree(pins_dir)
    if base:
        _lock_tree(base_dir)
        frag["base_pin_dir"] = str(base_dir)
        frag["base_skipped"] = skipped
    return frag, dirty


# PYTEST_PINS's in-process launcher (.claude/workflows/fabrik-review-loop.js) with SCRATCH filled in: the workflow test
# renders the recipe and asserts the two programs are equal, so the copies cannot drift.
_LAUNCHER = (
    'import os,site,sys; os.chdir("{arch}"); os.environ["PYTHONUSERBASE"]=site.getuserbase(); '
    'os.environ["HOME"]="{home}"; os.environ["TMPDIR"]="{tmp}"; os.environ["FABRIK_ROOT"]=os.getcwd(); '
    'i=next((n for n,p in enumerate(sys.path) if p.endswith(("site-packages","dist-packages"))),len(sys.path)); '
    'sys.path[i:i]=[os.path.abspath("src"),os.path.abspath(".")]; import pytest; '
    "raise SystemExit(pytest.main(sys.argv[1:]))"
)


def _writable(top: Path) -> None:
    for d, _, names in os.walk(top):
        Path(d).chmod(stat.S_IMODE(Path(d).stat().st_mode) | stat.S_IWUSR)
        for n in names:
            p = Path(d) / n
            if not p.is_symlink():
                p.chmod(stat.S_IMODE(p.stat().st_mode) | stat.S_IWUSR)


def _check_out(out: Path, pins_dir: Path) -> Path:
    """Every --out refusal, before anything is written (W-b976638f critiques): a seat's shell starts in the LIVE
    checkout, so a relative or in-repo tree lands there (an 87 MB archive once did), and the launcher embeds the path
    in a single-quoted shell program and a double-quoted Python string. Returns the path every check judged — `..`
    and symlinked parents resolved, so no spelling reaches the pins dir or a work tree around them (review pass 1)."""
    if not out.is_absolute():
        raise PinError(f"--out {out} is relative: name an absolute path under your scratch dir")
    if os.path.lexists(
        out
    ):  # before any resolving: a link AT --out (even dangling) is never followed
        raise PinError(f"{out} already exists — stage builds a NEW tree")
    out = Path(os.path.realpath(out.parent)) / out.name
    if out.name != "arch":
        raise PinError(f"--out {out} must end in /arch: the recipe's later steps name SCRATCH/arch")
    if any(c in str(out) for c in "'\"\\") or any(c.isspace() for c in str(out)):
        raise PinError(
            f"--out {out!r} holds a quote, a backslash or whitespace, which break the printed launcher"
        )
    if os.path.lexists(out):
        raise PinError(f"{out} already exists — stage builds a NEW tree")
    scratch = out.parent
    if not scratch.is_dir():
        raise PinError(f"{scratch} is not a directory — --out goes in your existing scratch dir")
    for d in (pins_dir, Path(f"{pins_dir}.base")):
        if out.is_relative_to(Path(os.path.realpath(d))):
            raise PinError(f"--out {out} is inside {d}")
    home = Path(os.path.realpath(Path.home()))
    if out.is_relative_to(home):
        raise PinError(f"--out {out} is under the home directory {home}")
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=scratch,
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode == 0:
        ign = subprocess.run(
            ["git", "check-ignore", "-q", str(out)],
            cwd=top.stdout.strip(),
            capture_output=True,
            check=False,
        )
        if ign.returncode != 0:
            raise PinError(
                f"--out {out} is inside the work tree {top.stdout.strip()} and not ignored"
            )
    for side in ("home", "tmp"):
        if os.path.lexists(scratch / side) and not (scratch / side).is_dir():
            raise PinError(f"{scratch / side} exists and is not a directory")
    return out


def _read_pins(pins_dir: Path) -> tuple[dict, dict[str, bytes]]:
    """The manifest, its md5 list cross-checked, and every pin's bytes re-hashed against it."""
    mf = pins_dir / "MANIFEST.json"
    if not mf.is_file():
        raise PinError(f"{pins_dir} holds no MANIFEST.json — UNPINNED: it was not written by `pin`")
    try:
        doc = json.loads(mf.read_text())
    except ValueError as exc:
        raise PinError(f"{mf} is not JSON ({exc})") from None
    files = doc.get("files") if isinstance(doc, dict) else None
    if not isinstance(files, dict) or not files:
        raise PinError(f"{mf} names no pinned files")
    blobs: dict[str, bytes] = {}
    for f, m in files.items():
        if (
            not isinstance(f, str)
            or not isinstance(m, str)
            or os.path.normpath(f) != f
            or f.startswith("..")
            or os.path.isabs(f)
            or "\n" in f
            or "\0" in f
            or f in _MANIFEST_NAMES
        ):
            raise PinError(f"{mf} names an unsafe path {f!r}")
        p = pins_dir / f
        if p.is_symlink() or not p.is_file():
            raise PinError(f"PIN MOVED {f} — the pin is missing")
        b = p.read_bytes()
        if hashlib.md5(b, usedforsecurity=False).hexdigest() != m:
            raise PinError(f"PIN MOVED {f} — its bytes no longer match the manifest")
        blobs[f] = b
    try:
        listed = (pins_dir / "MANIFEST.md5").read_text()
    except OSError:
        listed = ""
    if sorted(listed.splitlines()) != sorted(f"{m}  {f}" for f, m in files.items()):
        raise PinError(f"{pins_dir}/MANIFEST.md5 does not list the files MANIFEST.json names")
    return doc, blobs


def _overlay(arch: Path, rel: str, data: bytes) -> None:
    """Lay one pin over the staged tree by the recipe's rules: a link AT the path is replaced, never written
    through; a parent link resolving inside the tree is written through (makedirs+copyfile does, keeping the link's
    other files); a parent link outside the tree, or dangling, refuses; a file where a directory belongs, or a
    directory where the pin's file belongs, is removed first (the change turned one into the other)."""
    real = arch.resolve()
    cur = arch
    for part in Path(rel).parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            target = cur.resolve()
            if not target.is_relative_to(real) or not target.is_dir():
                raise PinError(
                    f"cannot overlay {rel}: {cur} is a link leaving the staged tree, or dangling"
                )
        elif cur.exists() and not cur.is_dir():
            cur.unlink()
        cur.mkdir(exist_ok=True)
    dest = cur / Path(rel).name
    if dest.is_symlink():
        dest.unlink()
    elif dest.is_dir():
        _unlock_and_remove(dest)
    if not dest.resolve().is_relative_to(real):
        raise PinError(f"cannot overlay {rel}: it resolves outside the staged tree")
    dest.write_bytes(data)


def stage(pins_dir: Path, out: Path) -> dict:
    """Build a seat's test tree at `out` in one command: the pin's recorded base copy (else an archive of its
    base_sha), user-writable, every pin laid over it and md5-checked. Writes `out` and its siblings `home` and
    `tmp`; on any refusal it removes its own half-built `out` and nothing else."""
    out = _check_out(out, pins_dir)
    doc, blobs = _read_pins(pins_dir)
    base_sha, root = doc.get("base_sha"), Path(str(doc.get("root")))
    base_dir = Path(f"{pins_dir}.base")
    recorded = isinstance(base_sha, str) and doc.get("base_copy") == base_sha and base_dir.is_dir()
    if not recorded and not isinstance(base_sha, str):
        raise PinError(
            f"{pins_dir}/MANIFEST.json records no base_sha and no base copy: nothing to stage from"
        )
    scratch = out.parent
    for side in ("home", "tmp"):
        (scratch / side).mkdir(exist_ok=True)
    skipped: list[str] = []
    made = False  # only a tree THIS call created is removed on a refusal (review pass 1, A-S1: a racing stager's)
    try:
        if recorded:
            # mkdir FIRST: it fails on a tree that appeared since the checks (never ours), and once it succeeds
            # a copy that dies part-way still leaves a tree this call made (review pass 2, A-S10)
            out.mkdir()
            made = True
            shutil.copytree(base_dir, out, symlinks=True, dirs_exist_ok=True)
            listed = doc.get("base_skipped")
            skipped = [s for s in listed if isinstance(s, str)] if isinstance(listed, list) else []
        else:
            out.mkdir()
            made = True
            skipped = _extract_commit(root, str(base_sha), out, tmp_dir=scratch / "tmp")
        _writable(out)
        for f, b in blobs.items():
            _overlay(out, f, b)
        bad = [
            f
            for f, b in blobs.items()
            if _md5(out / f) != hashlib.md5(b, usedforsecurity=False).hexdigest()
        ]
        if bad:
            raise PinError(f"md5 mismatch after the overlay: {', '.join(bad)}")
    except (PinError, OSError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        if made and os.path.lexists(out):
            _unlock_and_remove(out)
        if isinstance(exc, PinError):
            raise
        detail = (
            exc.stderr.decode(errors="replace").strip()
            if isinstance(exc, subprocess.CalledProcessError)
            else exc
        )
        raise PinError(f"cannot stage {out}: {detail}") from exc
    venv = root / ".venv" / "bin" / "python"
    python = str(venv) if venv.is_file() else sys.executable
    prog = _LAUNCHER.format(arch=out, home=scratch / "home", tmp=scratch / "tmp")
    return {
        "arch": str(out),
        "source": "base-copy" if recorded else "archive",
        "base_sha": base_sha,
        "overlaid": len(blobs),
        "skipped": skipped,
        "pytest": f"{shlex.quote(python)} -P -B -c '{prog}' <pytest args>",
    }


# a transcript's timestamps are when a seat LOGGED, not every moment it ran, and a one-line transcript is a
# zero-width span (review A-S2): attribution widens each span by this many seconds on both sides
_SLACK = 120.0


def _span(transcript: Path) -> tuple[float, float] | None:
    stamps = []
    try:
        for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                t = json.loads(line).get("timestamp")
            except (ValueError, AttributeError):
                continue
            if t:
                stamps.append(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())
    except OSError:
        return None
    return (min(stamps), max(stamps)) if stamps else None


def _size(n: int | None) -> str:
    if n is None:
        return "(?)"
    return f"({n} B)" if n < 1024 * 1024 else f"({n / 1048576:.1f} MB)"


def check_pins(pins_dir: Path, run: Path) -> dict:
    """Re-hash every manifest entry after the pass (the post-pass half of `pin`). A moved PIN voids the pass for
    the slices that read it and names every seat whose transcript span covers the pin's mtime — attribution
    without an agent step per seat; a moved LIVE file (working-tree pins only) is informational."""
    if not (pins_dir / "MANIFEST.json").is_file():
        return {
            "status": "unpinned",
            "checked": 0,
            "pin_moved": [],
            "live_moved": [],
            "live_at_move": {},
        }
    doc = json.loads((pins_dir / "MANIFEST.json").read_text())
    root, files = Path(doc["root"]), doc["files"]
    pin_moved = [
        f for f, m in files.items() if not (pins_dir / f).is_file() or _md5(pins_dir / f) != m
    ]
    # change.diff is every seat's view of the change, so a mutated one moves the pass like a pin (review round 1,
    # A-S1); a manifest written before it existed carries no `change_diff` and checks nothing here
    cd = doc.get("change_diff")
    if isinstance(cd, str) and (
        not (pins_dir / "change.diff").is_file() or _md5(pins_dir / "change.diff") != cd
    ):
        pin_moved.append("change.diff")
    live_moved = (
        [f for f, m in files.items() if not (root / f).is_file() or _md5(root / f) != m]
        if doc.get("source") == "working-tree"
        else []
    )
    spans: dict[str, tuple[float, float]] = {}
    for line in (run / "journal.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("type") == "started" and row.get("agentId"):
            span = _span(run / f"agent-{row['agentId']}.jsonl")
            if span:
                spans[str(row.get("label") or row["agentId"])] = span
    at_move: dict[str, list[str]] = {}
    for f in pin_moved:
        when = (pins_dir / f).stat().st_mtime if (pins_dir / f).exists() else None
        at_move[f] = sorted(
            s
            for s, (a, b) in spans.items()
            if when is not None and a - _SLACK <= when <= b + _SLACK
        )
    # the live tree outside the manifest (infra 01M4CV040F): a seat's cwd is the live checkout, so a relative
    # write lands there whatever its brief says
    tree_changes: list[dict] | None = None
    tree_reason = ""
    before = doc.get("tree")
    if not isinstance(before, dict):
        tree_reason = (
            "no snapshot (a pins dir written before the tree check, or pinned outside a repo)"
        )
    else:
        after = _tree(root)
        if after is None:
            tree_reason = f"the snapshot could not run in {root}"
        else:
            rel_pins = [
                os.path.relpath(d, root)
                for d in (pins_dir.resolve(), Path(f"{pins_dir.resolve()}.base"))
                if d.is_relative_to(root)
            ]

            def skip(path: str) -> bool:
                q = path.rstrip("/")
                return q in files or any(q == r or q.startswith(r + "/") for r in rel_pins)

            tree_changes = _tree_changes(root, before, after, skip)
            for c in tree_changes:
                when = c.get("mtime")
                c["seats"] = sorted(
                    s
                    for s, (a, b) in spans.items()
                    if when is not None and a - _SLACK <= when <= b + _SLACK
                )
    return {
        "status": "checked",
        "source": doc.get("source"),
        "checked": len(files),
        "pin_moved": pin_moved,
        "live_moved": live_moved,
        "live_at_move": at_move,
        "tree_changes": tree_changes,
        "tree_reason": tree_reason,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("run", type=Path)
    r.add_argument("--out", type=Path)
    r.add_argument(
        "--box",
        type=float,
        help="the seats' time box in minutes; a longer seat is flagged OVER BOX",
    )
    r.add_argument(
        "--pins",
        type=Path,
        help="the pins dir `pin` wrote: re-hash its manifest against the pins and the live files",
    )
    n = sub.add_parser("next")
    n.add_argument("ledger", type=Path)
    n.add_argument(
        "--ids",
        required=True,
        help="comma-separated confirmed candidate ids; with --args the other open claims are carried as well — "
        "a run file's confirmed or unverified candidates left out of --ids, and DEFECT_PRESENT/NEW ledger rows "
        "from the launch ledger",
    )
    n.add_argument(
        "--drop",
        default="",
        help="comma-separated OPEN ids the lead closed outside the pass file — never carried",
    )
    n.add_argument(
        "--args",
        dest="launch",
        type=Path,
        help="the run's workflows/<runId>.json, or the launch args: emit whole slices",
    )
    p = sub.add_parser("pin")
    p.add_argument("--pins-dir", type=Path, required=True)
    p.add_argument(
        "--from", dest="ref", help="pin each file's bytes from this commit, not the working tree"
    )
    p.add_argument(
        "--base", help="also extract this commit, whole and read-only, into <pins-dir>.base"
    )
    p.add_argument(
        "--replace", action="store_true", help="re-pin a pins dir that is already in use"
    )
    p.add_argument("files", nargs="+", help="repo-relative slice files, from the repo root")
    s = sub.add_parser("stage")
    s.add_argument("--pins-dir", type=Path, required=True, help="the pins dir `pin` wrote")
    s.add_argument(
        "--out",
        type=Path,
        required=True,
        help="SCRATCH/arch: an absolute path, not yet created, in your existing scratch dir",
    )
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage":
            print(json.dumps(stage(Path(os.path.abspath(a.pins_dir)), a.out), ensure_ascii=False))
        elif a.cmd == "pin":
            pins = Path(os.path.abspath(a.pins_dir))
            frag, dirty = pin(a.files, pins, Path.cwd(), ref=a.ref, base=a.base, replace=a.replace)
            frag["dirty"] = dirty  # in the JSON too, so a caller reading stdout alone still sees it
            for f in dirty:
                print(
                    f"DIRTY {f} — the pin is the working tree's bytes, not HEAD's (pass --from <sha> for a commit)",
                    file=sys.stderr,
                )
            for f in frag.get("unchanged", []):
                print(
                    f"UNCHANGED {f} — the pin equals {frag['basis']} (a context file, or a change not made yet)",
                    file=sys.stderr,
                )
            for f in frag.get("base_skipped", []):
                print(
                    f"SKIPPED {f} — the base tree leaves out a member the safe extract refuses (an absolute or escaping link, or a device)",
                    file=sys.stderr,
                )
            # stdout is the fragment ALONE, so a caller can hand it to a launch whole; every advisory above went to
            # stderr, as `next`'s carry notes do (kaizen 01M4V6VQ8V, row 1791913338)
            print(json.dumps(frag, ensure_ascii=False))
        elif a.cmd == "read":
            doc = read_run(a.run, a.box)
            if a.pins:
                doc["pins"] = check_pins(a.pins, a.run)
            if a.out:
                a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
            _print(doc)
            _print_workflow(doc["workflow"], a.run)
            wait = 5 if doc["workflow"] and doc["workflow"]["wait"] else 0
            chk = doc.get("pins")
            if chk is None:
                print("pins: NOT CHECKED — pass --pins <pins_dir> to re-hash the pins `pin` wrote")
            elif chk["status"] == "unpinned":
                print(
                    f"pins: UNPINNED — {a.pins} holds no MANIFEST.json, so these pins were not written by `pin`"
                )
            else:
                for f in chk["pin_moved"]:
                    who = (
                        ", ".join(chk["live_at_move"].get(f) or [])
                        or "no seat's span covers its mtime"
                    )
                    print(
                        f"PIN MOVED {f} — its bytes no longer match the manifest; seats live then: {who}"
                    )
                for f in chk["live_moved"]:
                    print(
                        f"LIVE MOVED {f} — the live file no longer matches its pin: "
                        "re-verify its candidates against the current tree"
                    )
                print(
                    f"pins: {chk['checked']} checked · {len(chk['pin_moved'])} pin moved · "
                    f"{len(chk['live_moved'])} live moved"
                )
                if chk["tree_changes"] is None:
                    print(f"tree: NOT CHECKED — {chk['tree_reason']}")
                else:
                    for c in chk["tree_changes"]:
                        size = (
                            "(gone)"
                            if c.get("gone")
                            else "(dir)"
                            if c.get("dir")
                            else _size(c["size"])
                        )
                        who = ", ".join(c["seats"]) or "no seat's span covers its mtime"
                        tail = (
                            " — delete it before any commit" if c["kind"] == "SEAT ARCHIVE" else ""
                        )
                        print(f"{c['kind']} {c['path']} {size} — seats live then: {who}{tail}")
                    print(
                        f"tree: {len(chk['tree_changes'])} new or changed path(s) outside the manifest"
                    )
                if chk["pin_moved"]:
                    # the pass is void for the slices that read a moved pin: re-pin into a NEW dir and re-launch
                    return 3
                if any(c["kind"] == "SEAT ARCHIVE" for c in chk["tree_changes"] or []):
                    return 4  # the pass stands; a seat's archive sits in the live tree, one `git add` from a commit
            if wait:
                return wait  # the workflow has not ended: a seat still out is an open question
        else:
            try:
                doc = json.loads(a.ledger.read_text())
            except (
                ValueError
            ) as exc:  # review round 1 A-S1: a torn pass file is a refusal, never a traceback
                raise LedgerError(f"{a.ledger} is not JSON ({exc})") from None
            wf = doc.get("workflow") if isinstance(doc, dict) else None
            if isinstance(wf, dict) and wf.get("wait"):
                # `read --out` writes the pass file before it exits 5: a pass 2 built from it rests on half a pass
                raise LedgerError(
                    f"{a.ledger} was read while the workflow was {wf.get('status')} — read the run again once it has "
                    "ended, then build the next pass"
                )
            launch, result = load_args(a.launch) if a.launch else (None, None)
            ids = [i.strip() for i in a.ids.split(",") if i.strip()]
            drop = list(dict.fromkeys(i.strip() for i in a.drop.split(",") if i.strip()))
            opened, stuck, unchecked = open_claims(doc, result, launch)
            named = {_fold(i) for i in ids}
            open_ids = {_fold(o[0]) for o in opened} | {_fold(s) for s in stuck}
            bad = [d for d in drop if _fold(d) not in open_ids or _fold(d) in named]
            if bad:
                raise LedgerError(
                    f"--drop {', '.join(bad)}: not an open claim this pass leaves out of --ids — nothing to drop"
                )
            gone = {_fold(d) for d in drop}
            carry = [o for o in opened if _fold(o[0]) not in named and _fold(o[0]) not in gone]
            out = next_ledger(doc, ids, launch, result, [(o[1], o[2]) for o in carry])
            for cid, _name, _row, why in carry:
                print(f"CARRIED {cid} — {why}, not in --ids", file=sys.stderr)
            for sid in stuck:  # a stuck id is never a candidate, so never in --ids
                if _fold(sid) not in gone:
                    how = (
                        "carry it by hand as {id, file, line, claim}, or --drop it"
                        if launch is not None
                        else "re-run next with --args <the run file>, or --drop it"
                    )
                    print(
                        f"OPEN NOT CARRIED {sid} — reported open, but no single candidate this pass and no launch "
                        f"ledger row carries it: {how}",
                        file=sys.stderr,
                    )
            left = sum(1 for k in unchecked if k not in named)
            if left:
                if isinstance(result, dict) and isinstance(result.get("slices"), list):
                    why = "their slice carries no verdicts (no refuter answered): re-verify them by hand"
                elif launch is not None:  # --args given, but no usable `result` (W-9f436e18)
                    why = (
                        "the --args file holds no usable `result` (bare launch args, a run that never returned, "
                        "or a result with no `slices` list): pass the ended run's workflows/<runId>.json, or "
                        "re-verify them by hand"
                    )
                else:
                    why = (
                        "next reads verdicts only from a run file: pass --args <workflows/<runId>.json> to carry "
                        "the open ones"
                    )
                print(f"NOT CHECKED {left} candidate(s) outside --ids — {why}", file=sys.stderr)
            for d in drop:
                print(f"DROPPED {d}", file=sys.stderr)
            for note in carry_notes(launch, out) if launch else []:
                print(note, file=sys.stderr)
            print(json.dumps(out, ensure_ascii=False))
    except (
        OSError
    ) as exc:  # FileNotFoundError, and any filesystem error a verb did not turn into its own
        print(f"review_loop_ledger: {exc}", file=sys.stderr)
        return 2
    except (LedgerError, PinError) as exc:
        print(f"review_loop_ledger: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(
            f"review_loop_ledger: {exc} — {exc.stderr.decode(errors='replace').strip()}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
