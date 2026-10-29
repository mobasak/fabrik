#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/kaizen.md, tests/test_lessons_relay.py
"""LESSONS relay — the incremental reader of every repo's LESSONS_LEARNT and AFCL (W-d6ebcc04).

Nothing read those two files as a learning input: kaizen's loop consumed the command-feedback
ledger and mail, so a lesson written in any repo never reached the command or rule that would stop
its repeat (operator 2026-10-23, W-682f1189). This rides the daily kaizen cron slot beside
``feedback_relay.py`` (a rider in ``weekly_catchup.sh``'s ``kaizen_collect_v2.py`` arm) and mails
kaizen ONE digest of the entries written since the last run — a POINTER row per entry
(``- [ ] <repo>/<file>:<line> · <heading>``), never the body, because a mail is a pointer, not a
payload (``mail.py`` MAX_BODY). Kaizen answers each row with a command or rule edit, or a reject
with its reason.

Inputs: ``<root>/*/docs/LESSONS_LEARNT.md``, ``<root>/*/docs/lessons-learnt.md`` (the legacy
name) and ``<root>/*/AFCL.md`` — top-level dirs of ``--root`` (default ``/opt``), dot dirs skipped.
An entry is an ATX heading of level 1-3 outside fenced code, with its OWN section up to the next
heading of any level. It is NEW when its hash (heading text + whitespace-normalised section) is
unseen — so a scaffold-identical copy in another repo is not re-sent — AND either its key
(repo/file, level, heading text) is unseen or that heading text repeats at that level in that file
(the hub's ``## 1. Context`` x34 cannot name an entry, so its hash does). A new heading whose nearest
enclosing heading is itself sent this run folds into that row.

Only a fence opener with an info string (```bash) fences; a bare fence line is text (``_fenced``
says why: the legacy scaffold template leaves a stray bare opener in 27 of 84 live files).

The cursor is ``~/.claude/state/lessons-relay.json``. ``--seed`` records every current entry and
sends nothing (the backlog is kaizen's one-time triage, never the queue); it refuses an existing
cursor without ``--force`` and a root holding no entry. NO cursor, or one that does not parse →
exit 1, nothing sent, never a silent reseed. At most ``CAP`` rows and ``BODY_MAX`` bytes per mail,
a row's folded children always with it; the cursor advances for the rows sent, and only after
``mail.py send`` exits 0 within 120 s, so a failure or the overflow arrives on the next run. Each
row is screened with mail.py's own secret check first and a refusable heading is withheld (every
heading, when that check cannot be imported), so one heading cannot block the channel. Quiet when
nothing is new.

Stated limits: a renamed heading reads as a new entry; editing an old section under a REPEATED
heading re-sends it, while a uniquely-headed section rewritten in place — even with a wholly new
lesson under the old heading — is never re-sent; a bare-fenced code block's ``# comment`` lines
read as headings (noise kaizen rejects, never a lost lesson); a corrupt cursor, or a cursor save
that fails after a send (the next run re-sends that batch), stops with a stderr line in the cron
log only; the relay takes no lock of its own (the cron arm runs it under ``flock``).
COBRA (D-253): the cheapest way to satisfy "rows answered" is a reject without reading the file;
the row carries the path:line so a reject can cite what it read — the audit is kaizen's.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

CURSOR = Path.home() / ".claude" / "state" / "lessons-relay.json"
MAIL = Path("/opt/fabrik/scripts/mail.py")
ROOT = Path("/opt")
FILES = ("docs/LESSONS_LEARNT.md", "docs/lessons-learnt.md", "AFCL.md")
CAP = 150  # rows per mail
BODY_MAX = 60 * 1024  # body bytes per mail: mail.py refuses over 64 KiB of UTF-8 (its MAX_BODY)
HEADING_MAX = 200  # heading bytes per row, so a multi-byte heading cannot exhaust BODY_MAX
_HEADING = re.compile(r"^ {0,3}(#{1,3})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _fenced(lines: list[str]) -> set[int]:
    """Line indices inside fenced code. Only an opener with an info string (```bash,
    ````markdown) opens a block, closed by the next bare fence of the same char at least as long;
    a bare fence line is text. CommonMark lets a bare ``` open too, but a stray one — the legacy
    scaffold template leaves one in 27 of 84 live files — then paired with the first bare fence of
    a lesson appended later, hiding that lesson and reading its shell comments as headings
    (review round 1, W-d6ebcc04). Measured over the 84 live files: this rule hides 0 headings the
    strict rule shows, and shows 199 it hid, one of them a code comment (fabrik's line 7740). An
    opener with no closer before end of file fences nothing."""
    fenced: set[int] = set()
    i = 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if not m or not m.group(2).strip():
            i += 1
            continue
        fence = m.group(1)
        for j in range(i + 1, len(lines)):
            c = _FENCE.match(lines[j])
            if c and c.group(1)[0] == fence[0] and len(c.group(1)) >= len(fence):
                if not c.group(2).strip():
                    fenced.update(range(i, j + 1))
                    i = j + 1
                    break
        else:
            i += 1
    return fenced


def _entries(rel: str, text: str) -> list[dict]:
    """Every level 1-3 heading outside fences: key, hash, line, level, text, parent index."""
    # "\n" only: splitlines() also splits on \f, \x1c-\x1e, \x85 and U+2028/9, which shifted a
    # row's :line off the line an editor shows (read_text has already folded \r\n and \r).
    lines = text.split("\n")
    fenced = _fenced(lines)
    heads: list[tuple[int, int, str]] = []  # (line index, level, text)
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        h = _HEADING.match(line)
        if h:
            heads.append((i, len(h.group(1)), h.group(2).strip()))
    counts: dict[tuple[int, str], int] = {}
    for _i, level, head in heads:
        counts[(level, head)] = counts.get((level, head), 0) + 1
    out: list[dict] = []
    stack: list[int] = []  # indices into out of the open enclosing headings
    for n, (i, level, head) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        section = " ".join(" ".join(lines[i + 1 : end]).split())
        while stack and out[stack[-1]]["level"] >= level:
            stack.pop()
        out.append(
            {
                "key": f"{rel}\t{level}\t{head}",
                "hash": hashlib.sha256(f"{head}\n{section}".encode()).hexdigest(),
                "line": i + 1,
                "level": level,
                "head": head,
                "rel": rel,
                "repeated": counts[(level, head)] > 1,
                "parent": stack[-1] if stack else None,
            }
        )
        stack.append(len(out) - 1)
    return out


def collect(root: Path) -> tuple[list[dict], int]:
    """All entries under root, in file order, and the number of files read."""
    entries: list[dict] = []
    files = 0
    for repo in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        for name in FILES:
            f = repo / name
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8-sig", errors="replace")  # a BOM hid line 1
            except OSError as exc:
                print(f"lessons_relay: skipped {f}: {exc}", file=sys.stderr)
                continue
            files += 1
            base = len(entries)
            for e in _entries(f"{repo.name}/{name}", text):
                if e["parent"] is not None:
                    e["parent"] += base
                entries.append(e)
    return entries, files


def _is_new(e: dict, keys: set[str], hashes: set[str]) -> bool:
    return e["hash"] not in hashes and (e["key"] not in keys or e["repeated"])


def _rows(entries: list[dict], keys: set[str], hashes: set[str]) -> list[int]:
    """Indices of the rows to send: new entries with no new enclosing entry (those fold in)."""
    fresh = {n for n, e in enumerate(entries) if _is_new(e, keys, hashes)}
    rows = []
    for n in sorted(fresh):
        p = entries[n]["parent"]
        while p is not None and p not in fresh:
            p = entries[p]["parent"]
        if p is None:
            rows.append(n)
    return rows


def _subtree(entries: list[dict], n: int) -> list[int]:
    """n and every entry nested under it (they follow it in file order)."""
    out = [n]
    for m in range(n + 1, len(entries)):
        p = entries[m]["parent"]
        while p is not None and p != n:
            p = entries[p]["parent"]
        if p != n:
            break
        out.append(m)
    return out


def _load(path: Path) -> tuple[set[str], set[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("not a JSON object")
    keys, hashes = raw.get("keys"), raw.get("hashes")
    if not isinstance(keys, list) or not isinstance(hashes, list):
        raise ValueError("keys/hashes are not lists")
    return {str(k) for k in keys}, {str(h) for h in hashes}


def _save(path: Path, keys: set[str], hashes: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"keys": sorted(keys), "hashes": sorted(hashes)}), encoding="utf-8")
    tmp.replace(path)


def _scanner() -> Callable[[str], str | None] | None:
    """mail.py's own send-time secret refusal, so one heading cannot refuse every digest for good.
    (Its bare ack-line refusal cannot fire on a row: every row opens with `- [ ] `.)"""
    path = Path(__file__).resolve().parents[1] / "mail.py"
    try:
        spec = importlib.util.spec_from_file_location("_lessons_relay_mail", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._secret_level  # type: ignore[no-any-return]
    except Exception as exc:  # any import failure: every heading is withheld (_row)
        print(f"lessons_relay: mail.py scanners unavailable ({exc})", file=sys.stderr)
        return None


def _cut(text: str, limit: int) -> str:
    """text cut to at most limit UTF-8 bytes, an ellipsis marking a cut."""
    if len(text.encode("utf-8")) <= limit:
        return text
    raw = text.encode("utf-8")[: limit - len("…".encode())]
    return raw.decode("utf-8", errors="ignore") + "…"


def _row(entries: list[dict], e: dict, scan: Callable[[str], str | None] | None) -> str:
    where = f"- [ ] {e['rel']}:{e['line']} · "
    if scan is None:
        return where + "(heading withheld: mail.py scanners unavailable)"
    head = e["head"]
    if e["repeated"] and e["parent"] is not None:
        head = f"{entries[e['parent']]['head']} › {head}"
    row = where + _cut(head, HEADING_MAX)
    if scan(row) == "high":
        row = where + "(heading withheld: mail.py would refuse it)"
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help=f"the repos' parent dir (default {ROOT})")
    ap.add_argument("--cursor", default="", help=f"cursor file (default {CURSOR})")
    ap.add_argument("--mail", default=str(MAIL), help=f"mail.py to send with (default {MAIL})")
    ap.add_argument("--seed", action="store_true", help="record every current entry, send nothing")
    ap.add_argument(
        "--force", action="store_true", help="with --seed: replace an existing cursor (unsent lost)"
    )
    ap.add_argument("--dry-run", action="store_true", help="print the digest, send nothing")
    args = ap.parse_args(argv)
    cursor = Path(args.cursor) if args.cursor else CURSOR
    entries, files = collect(Path(args.root))

    if args.seed:
        # A re-seed records every unsent and overflow entry as seen; a seed of nothing writes a
        # valid empty cursor that the next run reads as "the whole backlog is new".
        if cursor.exists() and not args.force:
            print(
                f"lessons_relay: cursor {cursor} exists — a re-seed drops every entry not yet"
                " sent; pass --force to replace it; nothing written",
                file=sys.stderr,
            )
            return 1
        if not entries:
            print(f"lessons_relay: 0 entries under {args.root} — nothing seeded", file=sys.stderr)
            return 1
        _save(cursor, {e["key"] for e in entries}, {e["hash"] for e in entries})
        print(f"lessons_relay: seeded {len(entries)} entries from {files} file(s) — nothing sent")
        return 0
    if not cursor.exists():
        print(
            f"lessons_relay: no cursor at {cursor} — run --seed once (the seeded set is kaizen's"
            " one-time triage backlog); nothing sent",
            file=sys.stderr,
        )
        return 1
    try:
        keys, hashes = _load(cursor)
    except (OSError, ValueError) as exc:
        print(f"lessons_relay: cursor {cursor} unreadable ({exc}) — nothing sent", file=sys.stderr)
        return 1

    rows = _rows(entries, keys, hashes)
    if not rows:
        return 0
    scan = _scanner()
    day = dt.date.today().isoformat()
    texts = [_row(entries, entries[n], scan) for n in rows[:CAP]]

    def _body(k: int) -> str:
        lines = [
            f"Subject: LESSONS relay — {k} of {len(rows)} new lesson/AFCL entries "
            f"({files} files read)",
            "",
            f"WHAT: {k} of {len(rows)} new entries in a repo's docs/LESSONS_LEARNT.md,"
            " docs/lessons-learnt.md or AFCL.md since the last run, one row each (sub-headings"
            " fold into their entry).",
            f"WHERE: {files} files under the repos' parent dir; each row is <repo>/<file>:<line>.",
            f"WHEN: written before {day}.",
            "WHO: lessons_relay.py (infra, W-d6ebcc04) -> kaizen, the feedback loop's owner"
            " (D-627).",
            "WHY: a lesson that never reaches the command or rule it implicates repeats.",
            "HOW: read each entry at its path:line, answer its row with the command or rule edit"
            " it calls for, or a reject with its reason (already covered, fixed, model-obsolete,"
            " repo-local); ack this mail once every row is answered.",
            "SYSTEMIC: learning written into a lessons file reached no reader before this relay.",
            "",
            *texts[:k],
            "",
        ]
        if len(rows) > k:
            lines.append(f"{len(rows) - k} more arrive on the next run.")
        return "\n".join(lines)

    k = len(texts)
    while k > 1 and len(_body(k).encode("utf-8")) > BODY_MAX:
        k -= 1
    batch, body = rows[:k], _body(k)
    if args.dry_run:
        print(body)
        return 0

    cmd = [sys.executable, args.mail, "send", "--to", "fabrik", "--to-agent", "kaizen"]
    try:
        proc = subprocess.run(
            [*cmd, "--kind", "request", "--ack", "required"],
            input=body,
            text=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("lessons_relay: mail send timed out after 120 s — nothing recorded", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(
            f"lessons_relay: mail send failed rc={proc.returncode}: {proc.stderr.strip()[:200]}",
            file=sys.stderr,
        )
        return 1  # cursor NOT advanced — the batch retries on the next run
    held = {m for n in rows[len(batch) :] for m in _subtree(entries, n)}
    # A held entry's hash stays unseen even when a sent or known twin shares it: recorded, the
    # twin's hash would mark the held entry seen and it would never be sent (review round 1).
    held_hashes = {entries[m]["hash"] for m in held}
    for n, e in enumerate(entries):
        if n not in held:  # sent rows, their folded children, and everything already known
            keys.add(e["key"])
            if e["hash"] not in held_hashes:
                hashes.add(e["hash"])
    try:
        _save(cursor, keys, hashes)
    except OSError as exc:
        print(
            f"lessons_relay: SENT {len(batch)} row(s) but the cursor {cursor} was not saved"
            f" ({exc}) — the next run re-sends them",
            file=sys.stderr,
        )
        return 1
    print(f"lessons_relay: sent {len(batch)} of {len(rows)} new entries -> fabrik/kaizen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
