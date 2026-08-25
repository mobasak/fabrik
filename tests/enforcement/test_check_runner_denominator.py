"""`_check_runner`'s verdict must state how much it walked.

`PASS: <check> — 0 error(s), 0 warning(s)` cannot distinguish "walked the tree and found nothing"
from "walked nothing", and the second is how a check that has quietly stopped working passes for one
that is healthy. Measured 2026-08-25 across all 59 enforcement checks in a subject-free repo: 17
emitted an affirmative success claim and exactly ONE stated its denominator
(docs/reference/enforcement-battery-audit.md).

This runner backs SEVEN checks (docker · health · ports · watchdog · vps_docs · env_contract ·
deps_sync), so the count lands in all of them from one place. The unit is deliberately WALKED rather
than "examined": the runner hands every repo file to `check_file` and each check's own dispatch
decides what applies, so walk size is what this layer can honestly attest to.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "enforcement"))

import _check_runner as runner  # noqa: E402


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def test_verdict_reports_the_walk_size(tmp_path, capsys, monkeypatch) -> None:
    _tree(tmp_path, {"a.py": "x\n", "b.py": "y\n", "docs/c.md": "z\n"})
    monkeypatch.chdir(tmp_path)
    rc = runner.run_as_main(
        lambda _p: [], check_name="probe", description="probe", argv=[]
    )
    out = capsys.readouterr().out
    assert rc == 0
    m = re.search(r"across (\d+) file\(s\) walked", out)
    assert m is not None, f"verdict carries no denominator: {out!r}"
    assert int(m.group(1)) > 0, f"walked nothing but still claimed a clean verdict: {out!r}"


def test_a_zero_subject_walk_is_visibly_zero(tmp_path, capsys, monkeypatch) -> None:
    """THE case the audit exists for — a run with nothing to look at must SAY so.

    An empty tree yields a small, visibly-tiny walk count. A reader (or an agent) can then tell
    that `0 error(s)` covers nothing, instead of reading it as a clean bill of health.
    """
    monkeypatch.chdir(tmp_path)
    runner.run_as_main(lambda _p: [], check_name="probe", description="probe", argv=[])
    out = capsys.readouterr().out
    m = re.search(r"across (\d+) file\(s\) walked", out)
    assert m is not None, f"verdict carries no denominator: {out!r}"
    assert int(m.group(1)) < 5, (
        "an empty tree must report a visibly tiny walk — if this grows, the runner is walking "
        f"something other than the repo under test: {out!r}"
    )
