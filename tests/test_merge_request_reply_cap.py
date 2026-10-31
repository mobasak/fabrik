"""scripts/merge_request.py — refusal replies and after-merge red titles stay under mail.py's cap
(W-f4ce5c6b): one parametrize id ~100 KB long made MR 01M690NBSH's refusal reply 102 KB, mail.py
refused it, and every resume retried the same body."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "merge_request.py"
LONG = "tests/test_x.py::test_p[" + "[" * 100_000 + "]"


def _load():
    spec = importlib.util.spec_from_file_location("merge_request_reply_cap", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mr = _load()


def test_a_long_red_title_is_cut_where_a_refusal_quotes_it(monkeypatch):
    title = f"after-merge red: merge {'a' * 12} by kaizen (request x, branch b) turned {LONG} red"
    monkeypatch.setattr(mr, "_open_after_reds", lambda main: [{"id": "W-0000beef", "title": title}])

    class Ctx:
        main = Path("/nonexistent")

    with pytest.raises(mr.RefusedError) as err:
        mr._after_merge_block(Ctx(), {"requester": "kaizen", "item": "none"})
    msg = str(err.value)
    assert len(msg) < 2000, len(msg)
    assert "W-0000beef" in msg and "the item holds it whole" in msg


def test_a_long_red_id_is_cut_in_the_filed_title(monkeypatch, tmp_path):
    seen: dict = {}

    def run(argv, timeout, cwd=None, env=None, stdin_text=None):
        seen["title"] = argv[argv.index("--title") + 1]
        return subprocess.CompletedProcess(argv, 0, "W-0000cafe\n", "")

    monkeypatch.setattr(mr, "_run", run)
    cause = {"merge_sha": "a" * 40, "requester": "kaizen", "id": "01M", "branch": "b"}
    mr._file_after_red(tmp_path, cause, [LONG, "tests/test_y.py::test_ok"], "b" * 40, "c" * 40)
    title = seen["title"]
    assert len(title) < 2000, len(title)
    assert "tests/test_y.py::test_ok" in title  # short ids are kept whole
    assert (
        "chars)" in title and "status.json" in title
    )  # the cut is said, and where the full ids are
