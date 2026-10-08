#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/review-loop-workflow.md | tests/test_review_loop_ledger.py | commands/_sources/fabrik-review.md
"""review_loop_ledger — a review pass's ledger, read from its workflow run into a FILE (row 5b, D-357).

`fabrik-review-loop` returns its ledger as one tool result, escaped and often truncated; the lead used to
re-derive each pass from it with an ad-hoc script, and hand-typed the next pass's claim list (once as strings
the script rendered `undefined`). Finding 30 of `docs/reference/command-loop-performance.md`: the lead reads a
file, not its scrollback. So:

    review_loop_ledger.py read RUN_DIR [--out FILE] [--box MIN]
        RUN_DIR is the run's transcript dir (the Workflow launch prints it; it holds `journal.jsonl` and one
        `agent-<id>.jsonl` per seat). Writes {seats, candidates, verdicts, ledger_status} to FILE and prints a
        compact table. Every seat carries its MINUTES, from its transcript's first and last timestamp — the
        Workflow API has no per-agent timeout, so an overrun is only ever visible here (`OVER BOX`; one refuter
        ran 59 minutes against a 12-minute box on 2026-09-23). A seat with no result row is `NO RESULT`.
    review_loop_ledger.py next FILE --ids A-S1,B-S2
        The next pass's `slices[].ledger` for exactly those confirmed ids, as objects grouped by slice (the id
        prefix). An id the pass never raised is refused by name.
    review_loop_ledger.py pin --pins-dir DIR [--from REF] [--base SHA] [--replace] FILE…
        Run from the repo root before a pass (kaizen 01M4CGJZAX): writes each FILE to DIR/<FILE> — from the
        working tree, or with --from from that commit (a committed range) — and makes every pin AND directory
        read-only (with the directory writable, `sed -i` renames over a 0444 pin). Writes DIR/MANIFEST.md5
        (md5sum format) and DIR/MANIFEST.json, and with --base extracts that whole commit read-only into
        DIR.base. Prints `DIRTY <file>` for a working-tree pin that is not HEAD's bytes, then the Workflow args
        fragment — `pins_dir`, `pin_manifest`, `digest` (the md5 of MANIFEST.md5) and `base_pin_dir` — and the
        workflow refuses a slice file the manifest lacks before any seat runs. A used DIR is refused: each pass
        gets a NEW one (`--replace` re-pins on purpose). A workflow script has no filesystem, so the pins are
        the lead's verb, never the script's.
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
    doc: dict = {
        "run": str(run),
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
        read_none = (
            label.startswith("find:")
            and bool(got)
            and not any(
                isinstance(r.get("files_read"), list)
                and any(str(e).strip() for e in r["files_read"])
                for r in got
            )
        )
        doc["seats"].append(
            {
                "label": label,
                "model": model,
                "minutes": minutes,
                "over_box": bool(box is not None and minutes is not None and minutes > box),
                "untimed": minutes is None,
                "tokens": _tokens(run / f"agent-{aid}.jsonl"),
                "returned": bool(got),
                "read_no_file": read_none,
                "duplicate_results": len(got),
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
    return doc


def _one(x: object, n: int) -> str:
    """One printed line per field: a seat's multi-line output is collapsed, then cut."""
    return " ".join(str(x).split())[:n]


def _print(doc: dict) -> None:
    for s in doc["seats"]:
        mins = "?" if s["minutes"] is None else f"{s['minutes']:.1f} min"
        flags = (
            ("  OVER BOX" if s["over_box"] else "")
            + ("  UNTIMED" if s.get("untimed") else "")
            + ("" if s["returned"] else "  NO RESULT")
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
        f"{sum(1 for s in doc['seats'] if s['over_box'])} over box · {sum(1 for s in doc['seats'] if not s['returned'])} no result · "
        f"{sum(1 for s in doc['seats'] if s.get('read_no_file'))} read 0 files"
    )


class LedgerError(Exception):
    """`next` cannot name one claim for an id: never raised, raised twice, or no `<slice>-` prefix."""


def _slice_of(c: dict, cid: str) -> str:
    """The slice that raised a candidate: its finder's label (`find:<slice>:<model>`), else the id before its last
    `-` — a section slice named `rule-grammar` raises `rule-grammar-O1` (review of chunk 6, A-S1)."""
    seat = str(c.get("seat") or "")
    if seat.startswith("find:") and seat.count(":") >= 2:
        return seat[len("find:") :].rsplit(":", 1)[0]
    return cid.rsplit("-", 1)[0]


def next_ledger(doc: dict, ids: list[str]) -> list[dict]:
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
        raise LedgerError(
            f"id(s) raised more than once (by one seat or two), so they name no single claim: {', '.join(twice)} — "
            "pass the claim by hand as {id, file, line, claim}"
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
    return [{"name": n, "ledger": rows} for n, rows in slices.items()]


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
    rels: list[str] = []
    # every file is checked before ANYTHING is written, so a refusal leaves no half-built pins dir behind
    for f in files:
        rel = os.path.normpath(f)
        cand = root / rel
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
    # the tree a seat could write into, taken BEFORE any write so the pins dir and its base are never in it
    tree = _tree(root) if top is not None else None
    _fresh(pins_dir, replace)
    base_dir = Path(f"{pins_dir}.base")
    if base:
        _fresh(base_dir, replace)
    dirty: list[str] = []
    if ref is None:
        for f in rels:
            try:
                head = _vcs(root, "show", f"HEAD:{f}")
            except subprocess.CalledProcessError:
                head = None  # untracked: not the commit's bytes either
            if head != blobs[f]:
                dirty.append(f)
    manifest = {f: hashlib.md5(b, usedforsecurity=False).hexdigest() for f, b in blobs.items()}
    try:
        for f, b in blobs.items():
            (pins_dir / f).parent.mkdir(parents=True, exist_ok=True)
            (pins_dir / f).write_bytes(b)
        (pins_dir / "MANIFEST.md5").write_text("".join(f"{m}  {f}\n" for f, m in manifest.items()))
        (pins_dir / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "root": str(root),
                    "source": ref or "working-tree",
                    "files": manifest,
                    "tree": tree,
                },
                indent=1,
            )
        )
    except OSError as exc:
        # a half-written, still-writable pins dir is never left for a seat to read (review A-S3)
        if pins_dir.exists():
            _unlock_and_remove(pins_dir)
        raise PinError(f"cannot write the pins into {pins_dir}: {exc}") from exc
    frag: dict = {
        "pins_dir": str(pins_dir),
        "pin_manifest": manifest,
        "digest": _md5(pins_dir / "MANIFEST.md5"),
    }
    _lock_tree(pins_dir)
    if base:
        base_dir.mkdir(parents=True, exist_ok=True)
        # a member the "data" filter refuses — an absolute or escaping symlink, a device: the hub itself tracks
        # `vault -> /…` — is SKIPPED and named, never fatal (dogfooding this verb on the hub died on it with a
        # traceback and a half-extracted 94 MB base)
        skipped: list[str] = []
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tar = Path(tmp) / "base.tar"
                _vcs(
                    root, "archive", "-o", str(tar), base
                )  # the COMMITTED bytes, never the working tree's
                with tarfile.open(tar) as t:
                    # every member is validated BEFORE extraction and only the safe ones are named
                    safe: list[tarfile.TarInfo] = []
                    for member in t.getmembers():
                        try:
                            tarfile.data_filter(member, str(base_dir))
                        except tarfile.FilterError:
                            skipped.append(member.name)
                        else:
                            safe.append(member)
                    t.extractall(base_dir, members=safe, filter="data")
        except (OSError, tarfile.TarError, subprocess.CalledProcessError) as exc:
            # never leave a half-extracted base, or the pins written beside it, for the lead to hand to a seat
            _unlock_and_remove(base_dir)
            _unlock_and_remove(pins_dir)
            raise PinError(f"cannot extract base {base} into {base_dir}: {exc}") from exc
        _lock_tree(base_dir)
        frag["base_pin_dir"] = str(base_dir)
        frag["base_skipped"] = skipped
    return frag, dirty


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
    n.add_argument("--ids", required=True, help="comma-separated confirmed candidate ids")
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
    a = ap.parse_args(argv)
    try:
        if a.cmd == "pin":
            pins = Path(os.path.abspath(a.pins_dir))
            frag, dirty = pin(a.files, pins, Path.cwd(), ref=a.ref, base=a.base, replace=a.replace)
            for f in dirty:
                print(
                    f"DIRTY {f} — the pin is the working tree's bytes, not HEAD's (pass --from <sha> for a commit)"
                )
            for f in frag.get("base_skipped", []):
                print(
                    f"SKIPPED {f} — the base tree leaves out a member the safe extract refuses (an absolute link)"
                )
            print(json.dumps(frag, ensure_ascii=False))
        elif a.cmd == "read":
            doc = read_run(a.run, a.box)
            if a.pins:
                doc["pins"] = check_pins(a.pins, a.run)
            if a.out:
                a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
            _print(doc)
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
        else:
            doc = json.loads(a.ledger.read_text())
            print(
                json.dumps(
                    next_ledger(doc, [i.strip() for i in a.ids.split(",") if i.strip()]),
                    ensure_ascii=False,
                )
            )
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
