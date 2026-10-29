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


def _run(tmp: Path, *extra: str, rc: int = 0) -> subprocess.CompletedProcess:
    opt, home, mail = tmp / "opt", tmp / "home", tmp / "fake_mail.py"
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL") if k in os.environ}
    env.update(HOME=str(home), FAKE_MAIL_RC=str(rc))
    return subprocess.run(
        [sys.executable, str(RELAY), "--root", str(opt), "--mail", str(mail), *extra],
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
    assert (
        argv[:1] == ["send"]
        and "--to-agent" in argv
        and argv[argv.index("--to-agent") + 1] == "kaizen"
    )
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
        "```markdown\n# in the example\n```python\nx\n```\n\n# Lesson 4: after the example\n\n"
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
