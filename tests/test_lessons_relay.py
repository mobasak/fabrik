"""Graders for scripts/sysadmin/lessons_relay.py — the incremental LESSONS_LEARNT / AFCL reader that
mails kaizen one digest of new entries (W-d6ebcc04, for W-682f1189). One test per behaviour; every
run is a subprocess against a tmp `/opt`-shaped root, a tmp HOME (the cursor) and a fake mail.py
that records its argv and stdin, so no test reads the live repos or sends real mail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELAY = ROOT / "scripts" / "sysadmin" / "lessons_relay.py"

HUB_LESSONS = """# Lessons Learnt

# Lesson 2: the second one

## 1. Context

old context

# Lesson 1: the first one

## 1. Context

first context
"""


def _world(tmp: Path) -> tuple[Path, Path, Path]:
    """A two-repo root, a HOME for the cursor, and a fake mail.py writing calls to a log."""
    opt = tmp / "opt"
    (opt / "hub" / "docs").mkdir(parents=True)
    (opt / "hub" / "docs" / "LESSONS_LEARNT.md").write_text(HUB_LESSONS, encoding="utf-8")
    (opt / "proj").mkdir()
    (opt / "proj" / "AFCL.md").write_text("# AFCL\n\n## friction one\n\nbody\n", encoding="utf-8")
    home = tmp / "home"
    home.mkdir()
    log = tmp / "mail.log"
    mail = tmp / "fake_mail.py"
    mail.write_text(
        "import json, os, sys\n"
        f"open({str(log)!r}, 'a').write(json.dumps({{'argv': sys.argv[1:], 'body': sys.stdin.read()}}) + '\\n')\n"
        "sys.exit(int(os.environ.get('FAKE_MAIL_RC', '0')))\n",
        encoding="utf-8",
    )
    return opt, home, mail


def _run(tmp: Path, *extra: str, rc: int = 0, relay: Path = RELAY) -> subprocess.CompletedProcess:
    opt, home, mail = tmp / "opt", tmp / "home", tmp / "fake_mail.py"
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL") if k in os.environ}
    env.update(HOME=str(home), FAKE_MAIL_RC=str(rc))
    return subprocess.run(
        [sys.executable, str(relay), "--root", str(opt), "--mail", str(mail), *extra],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _sends(tmp: Path) -> list[dict]:
    log = tmp / "mail.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]


def _cursor(tmp: Path) -> Path:
    return tmp / "home" / ".claude" / "state" / "lessons-relay.json"


def _add_hub_lesson(tmp: Path, text: str) -> None:
    f = tmp / "opt" / "hub" / "docs" / "LESSONS_LEARNT.md"
    body = f.read_text(encoding="utf-8")
    f.write_text(
        body.replace("# Lessons Learnt\n\n", "# Lessons Learnt\n\n" + text, 1), encoding="utf-8"
    )


def test_first_run_seeds_without_sending(tmp_path):
    _world(tmp_path)
    refused = _run(tmp_path)  # no cursor and no --seed: loud, never a silent reseed
    assert refused.returncode == 1
    assert "--seed" in refused.stderr
    assert not _cursor(tmp_path).exists()
    r = _run(tmp_path, "--seed")
    assert r.returncode == 0, r.stderr
    assert _sends(tmp_path) == []
    assert _cursor(tmp_path).is_file()
    assert "seeded" in r.stdout and "from 2 file(s)" in r.stdout, r.stdout
    assert _run(tmp_path).stdout == ""  # nothing new after the seed


def test_new_entry_is_sent_once(tmp_path):
    _world(tmp_path)
    _run(tmp_path, "--seed")
    _add_hub_lesson(tmp_path, "# Lesson 3: a fresh one\n\n## 1. Context\n\nnew context\n\n")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    sends = _sends(tmp_path)
    assert len(sends) == 1
    argv, body = sends[0]["argv"], sends[0]["body"]
    assert argv == [
        "send",
        "--to",
        "fabrik",
        "--to-agent",
        "kaizen",
        "--kind",
        "request",
        "--ack",
        "required",
    ], argv
    assert body.startswith("Subject: LESSONS relay — "), body
    rows = [line for line in body.splitlines() if line.startswith("- [ ] ")]
    assert rows == ["- [ ] hub/docs/LESSONS_LEARNT.md:3 · Lesson 3: a fresh one"], body
    assert "1 of 1 new" in body
    again = _run(tmp_path)
    assert again.returncode == 0 and again.stdout == ""
    assert len(_sends(tmp_path)) == 1


def test_send_failure_keeps_the_cursor(tmp_path):
    _world(tmp_path)
    _run(tmp_path, "--seed")
    before = _cursor(tmp_path).read_bytes()
    _add_hub_lesson(tmp_path, "# Lesson 3: a fresh one\n\nx\n\n")
    failed = _run(tmp_path, rc=1)
    assert failed.returncode == 1
    assert _cursor(tmp_path).read_bytes() == before
    ok = _run(tmp_path)
    assert ok.returncode == 0
    assert "Lesson 3: a fresh one" in _sends(tmp_path)[-1]["body"]


def test_fences_nesting_and_copies_are_not_rows(tmp_path):
    _world(tmp_path)
    _run(tmp_path, "--seed")
    _add_hub_lesson(
        tmp_path,
        "# Lesson 3: fenced\n\n```bash\n# not a heading\n```\n\n~~~\n## nor this\n~~~\n\n"
        "## 2. The Problem\n\nnested, folded into Lesson 3\n\n"
        # an info-string fence line never CLOSES (CommonMark): the bare ``` after `x` does, so
        # Lesson 4 is outside any fence; the trailing ``` is a stray opener, read as text
        "```markdown\n# in the example\n```python\n# a python comment\n```\n\n# Lesson 4: after the example\n\n"
        "```\n\n",
    )
    # a second repo gains a byte-identical copy of the proj AFCL entry: not a new lesson
    (tmp_path / "opt" / "copy").mkdir()
    (tmp_path / "opt" / "copy" / "AFCL.md").write_text(
        "# AFCL\n\n## friction one\n\nbody\n", encoding="utf-8"
    )
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    body = _sends(tmp_path)[0]["body"]
    rows = [line for line in body.splitlines() if line.startswith("- [ ] ")]
    assert rows == [
        "- [ ] hub/docs/LESSONS_LEARNT.md:3 · Lesson 3: fenced",
        "- [ ] hub/docs/LESSONS_LEARNT.md:23 · Lesson 4: after the example",
    ], body
    # the folded `## 2. The Problem` advanced with its row: no orphan row on the next run
    again = _run(tmp_path)
    assert again.returncode == 0 and again.stdout == "", again.stdout
    assert len(_sends(tmp_path)) == 1


def test_unclosed_fence_and_poison_heading(tmp_path):
    """The legacy scaffold ends in an opener with no closer (27 of 84 live files): a lesson
    appended after it is a row. A heading mail.py's secret scanner would refuse goes out
    withheld instead of refusing the whole digest."""
    _world(tmp_path)
    afcl = tmp_path / "opt" / "proj" / "AFCL.md"
    afcl.write_text(
        afcl.read_text(encoding="utf-8") + "\n```markdown\nexample\n```python\nx\n```\n\n```\n",
        encoding="utf-8",
    )
    _run(tmp_path, "--seed")
    afcl.write_text(
        afcl.read_text(encoding="utf-8")
        + "\n## after the stray fence\n\nreal\n\n## GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789\n\nx\n",
        encoding="utf-8",
    )
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    body = _sends(tmp_path)[0]["body"]
    rows = [line for line in body.splitlines() if line.startswith("- [ ] ")]
    assert len(rows) == 2, body
    assert rows[0].endswith("· after the stray fence"), rows
    assert "ghp_" not in body and "withheld" in rows[1], rows


def test_overflow_rolls_to_the_next_run(tmp_path):
    _world(tmp_path)
    _run(tmp_path, "--seed")
    _add_hub_lesson(tmp_path, "".join(f"# Lesson {100 + i}: bulk\n\nb{i}\n\n" for i in range(160)))
    first = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    body = _sends(tmp_path)[0]["body"]
    assert sum(line.startswith("- [ ] ") for line in body.splitlines()) == 150
    assert "150 of 160 new" in body
    second = _run(tmp_path)
    assert second.returncode == 0
    body2 = _sends(tmp_path)[1]["body"]
    assert sum(line.startswith("- [ ] ") for line in body2.splitlines()) == 10
    assert "10 of 10 new" in body2


def test_corrupt_cursor_refuses(tmp_path):
    _world(tmp_path)
    cur = _cursor(tmp_path)
    cur.parent.mkdir(parents=True)
    cur.write_text("{not json", encoding="utf-8")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "cursor" in r.stderr
    assert cur.read_text(encoding="utf-8") == "{not json"
    assert _sends(tmp_path) == []


def _rows(body: str) -> list[str]:
    return [line for line in body.splitlines() if line.startswith("- [ ] ")]


def test_a_stray_bare_fence_never_hides_a_later_lesson(tmp_path):
    """Review round 1 (A): a bare ``` left open by the legacy template paired with the first bare
    fence of a lesson appended later, hiding that lesson and turning a shell comment into a row.
    Only an opener with an info string fences; a bare fence line is text."""
    _world(tmp_path)
    afcl = tmp_path / "opt" / "proj" / "AFCL.md"
    afcl.write_text(afcl.read_text(encoding="utf-8") + "\n```\n", encoding="utf-8")  # the stray
    _run(tmp_path, "--seed")
    afcl.write_text(
        afcl.read_text(encoding="utf-8")
        + "\n## Lesson with a tagged block\n\n```bash\n# not a heading\nmake x\n```\n"
        + "\n## Lesson with a bare block\n\nrun:\n```\nmake y\n```\n",
        encoding="utf-8",
    )
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    rows = _rows(_sends(tmp_path)[0]["body"])
    assert [row.split(" · ", 1)[1] for row in rows] == [
        "Lesson with a tagged block",
        "Lesson with a bare block",
    ], rows


def test_the_batch_fits_mail_py_byte_cap(tmp_path):
    """(B) mail.py refuses a body over 64 KiB of UTF-8; 150 rows of multi-byte headings went over
    and jammed the channel for good. Headings are cut by bytes and the batch by body bytes."""
    _world(tmp_path)
    _run(tmp_path, "--seed")
    _add_hub_lesson(tmp_path, "".join(f"# L{i:03d} {'—' * 190}\n\nb{i}\n\n" for i in range(150)))
    first = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    body = _sends(tmp_path)[0]["body"]
    rows = _rows(body)
    assert len(rows) == 150 and len(body.encode("utf-8")) <= 60 * 1024
    assert all(len(r.split(" · ", 1)[1].encode("utf-8")) <= 200 for r in rows), rows[0]
    # a long repo path makes 150 byte-cut rows still too big: the batch itself is cut by bytes
    repo = tmp_path / "opt" / ("r" * 200)
    repo.mkdir()
    (repo / "AFCL.md").write_text(
        "".join(f"# L{i:03d} {'—' * 190}\n\nc{i}\n\n" for i in range(150)), encoding="utf-8"
    )  # bodies differ from the hub's, so the cross-repo copy dedupe does not skip them
    second = _run(tmp_path)
    assert second.returncode == 0, second.stderr
    body2 = _sends(tmp_path)[1]["body"]
    sent = len(_rows(body2))
    assert len(body2.encode("utf-8")) <= 60 * 1024 and 0 < sent < 150, sent
    assert f"{150 - sent} more arrive on the next run." in body2
    _run(tmp_path)
    assert sent + len(_rows(_sends(tmp_path)[2]["body"])) == 150


def test_an_overflow_row_sharing_a_sent_rows_hash_is_not_lost(tmp_path):
    """(C) recording the hash of every unheld entry also recorded an overflow entry's hash when a
    sent twin shared it, so the overflow entry was never sent."""
    _world(tmp_path)
    _run(tmp_path, "--seed")
    (tmp_path / "opt" / "aaa").mkdir()
    (tmp_path / "opt" / "aaa" / "AFCL.md").write_text("## dup\n\nsame body\n", encoding="utf-8")
    (tmp_path / "opt" / "zzz").mkdir()
    (tmp_path / "opt" / "zzz" / "AFCL.md").write_text(
        "".join(f"## L{i:03d}\n\nb{i}\n\n" for i in range(149)) + "## dup\n\nsame body\n",
        encoding="utf-8",
    )
    _run(tmp_path)
    assert len(_rows(_sends(tmp_path)[0]["body"])) == 150
    _run(tmp_path)
    assert _rows(_sends(tmp_path)[1]["body"]) == ["- [ ] zzz/AFCL.md:597 · dup"]


def test_seed_refuses_a_live_cursor_and_an_empty_root(tmp_path):
    """(D) a second --seed recorded unsent and overflow entries as seen; a seed of zero entries
    wrote a valid empty cursor that the next run read as 'everything is new'."""
    _world(tmp_path)
    _run(tmp_path, "--seed")
    _add_hub_lesson(tmp_path, "# Lesson 3: unsent\n\nx\n\n")
    again = _run(tmp_path, "--seed")
    assert again.returncode == 1 and "--force" in again.stderr
    assert _run(tmp_path).returncode == 0
    assert "Lesson 3: unsent" in _sends(tmp_path)[0]["body"]
    empty = tmp_path / "empty"
    empty.mkdir()
    cur = tmp_path / "other-cursor.json"
    r = subprocess.run(
        [sys.executable, str(RELAY), "--root", str(empty), "--cursor", str(cur), "--seed"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 1 and not cur.exists(), r.stdout + r.stderr


def test_a_cursor_save_failure_after_a_send_is_loud(tmp_path):
    """(E) the send succeeded, the cursor write raised, and the run died on a traceback."""
    _world(tmp_path)
    _run(tmp_path, "--seed")
    _add_hub_lesson(tmp_path, "# Lesson 3: fresh\n\nx\n\n")
    _cursor(tmp_path).with_suffix(".json.tmp").mkdir()
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "SENT" in r.stderr and "Traceback" not in r.stderr, r.stderr
    assert len(_sends(tmp_path)) == 1


def test_bom_and_form_feed_keep_the_true_line(tmp_path):
    """(F, G) a UTF-8 BOM hid the first heading; splitlines() split on a form feed, so the row's
    :line pointed at the wrong line."""
    _world(tmp_path)
    _run(tmp_path, "--seed")
    (tmp_path / "opt" / "new").mkdir()
    (tmp_path / "opt" / "new" / "AFCL.md").write_text(
        "﻿# First\n\na\x0cb\n\n# Second\n", encoding="utf-8"
    )
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert _rows(_sends(tmp_path)[0]["body"]) == [
        "- [ ] new/AFCL.md:1 · First",
        "- [ ] new/AFCL.md:5 · Second",
    ]


def test_without_mail_py_scanners_every_heading_is_withheld(tmp_path):
    """(I) with mail.py's scanners unavailable a refusable heading would block every digest, so
    each row keeps its path:line and withholds its heading."""
    _world(tmp_path)
    alone = tmp_path / "alone" / "sysadmin"
    alone.mkdir(parents=True)
    copy = alone / "lessons_relay.py"
    copy.write_text(RELAY.read_text(encoding="utf-8"), encoding="utf-8")
    _run(tmp_path, "--seed", relay=copy)
    _add_hub_lesson(tmp_path, "# Lesson 3: fresh\n\nx\n\n")
    r = _run(tmp_path, relay=copy)
    assert r.returncode == 0, r.stderr
    assert _rows(_sends(tmp_path)[0]["body"]) == [
        "- [ ] hub/docs/LESSONS_LEARNT.md:3 · (heading withheld: mail.py scanners unavailable)"
    ]
