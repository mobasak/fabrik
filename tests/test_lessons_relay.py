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
CATCHUP = ROOT / "scripts" / "sysadmin" / "weekly_catchup.sh"

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
    f.write_text(body.replace("# Lessons Learnt\n\n", "# Lessons Learnt\n\n" + text, 1), encoding="utf-8")


def test_first_run_seeds_without_sending(tmp_path):
    _world(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert _sends(tmp_path) == []
    assert _cursor(tmp_path).is_file()
    assert "seeded" in r.stdout and "from 2 file(s)" in r.stdout, r.stdout


def test_new_entry_is_sent_once(tmp_path):
    _world(tmp_path)
    _run(tmp_path)
    _add_hub_lesson(tmp_path, "# Lesson 3: a fresh one\n\n## 1. Context\n\nnew context\n\n")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    sends = _sends(tmp_path)
    assert len(sends) == 1
    argv, body = sends[0]["argv"], sends[0]["body"]
    assert argv[:1] == ["send"] and "--to-agent" in argv and argv[argv.index("--to-agent") + 1] == "kaizen"
    rows = [line for line in body.splitlines() if line.startswith("- [ ] ")]
    assert rows == ["- [ ] hub/docs/LESSONS_LEARNT.md:3 · Lesson 3: a fresh one"], body
    assert "1 of 1 new" in body
    again = _run(tmp_path)
    assert again.returncode == 0 and again.stdout == ""
    assert len(_sends(tmp_path)) == 1


def test_send_failure_keeps_the_cursor(tmp_path):
    _world(tmp_path)
    _run(tmp_path)
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
    _run(tmp_path)
    _add_hub_lesson(
        tmp_path,
        "# Lesson 3: fenced\n\n```bash\n# not a heading\n```\n\n~~~\n## nor this\n~~~\n\n"
        "## 2. The Problem\n\nnested, folded into Lesson 3\n\n",
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
    assert rows == ["- [ ] hub/docs/LESSONS_LEARNT.md:3 · Lesson 3: fenced"], body


def test_overflow_rolls_to_the_next_run(tmp_path):
    _world(tmp_path)
    _run(tmp_path)
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


def test_catchup_runs_the_lessons_rider(tmp_path):
    root = tmp_path / "root"
    sysadmin = root / "scripts" / "sysadmin"
    sysadmin.mkdir(parents=True)
    log = tmp_path / "calls.log"
    for name in (
        "kaizen_coroner.py",
        "kaizen_collect_v2.py",
        "feedback_relay.py",
        "lessons_relay.py",
        "rules_currency_watch.py",
        "vps_script_drift.py",
    ):
        (sysadmin / name).write_text(
            f"import sys\nopen({str(log)!r}, 'a').write({name!r} + '\\n')\nsys.exit(0)\n"
        )
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ)
    env.update({"HOME": str(home), "FABRIK_ROOT": str(root), "FABRIK_PY": sys.executable})
    r = subprocess.run(
        ["bash", str(CATCHUP), "kaizen_collect_v2.py"], env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr
    calls = log.read_text().split()
    assert "lessons_relay.py" in calls
    assert calls.index("feedback_relay.py") < calls.index("lessons_relay.py")
