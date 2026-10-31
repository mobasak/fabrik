"""W-1ee3f07d: the credential shapes scripts/enforcement/check_secrets.py flags — today's AWS key ids, every GitHub token
prefix, fine-grained PATs and OpenAI project keys — while it stays a superset of every shape it flagged before.

Ported from fabrik-lib's scripts/tests/test_check_secrets.py (its D-517/D-519, 7ecb7b3c; mail 01M5EC2S14). Every case drives
the real entry point, `check_file`, on a `.txt` file under tmp_path (`SKIP_PATTERNS` skips `test_*.py`). Tokens are built
from parts so this file's source holds no token-shaped literal (CPython folds the constants in its .pyc, which the gate
never scans).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
import check_secrets as cs  # noqa: E402

_BODY36 = ("Ab1Cd2Ef3Gh4" * 3)[:36]
_PAT = "github" + "_pat_" + "A1b2C3d4E5f6G7h8I9j0K1" + "_" + ("Lm2No3Pq4Rs5Tu6Vw7Xy8Za9" * 3)[:59]
_OPENAI_BODY = ("SevzWEV_NmNnMndQ5gn6PjFcX-" * 3)[:58]
_MARKER = "T3Bl" + "bkFJ"


def _openai_key(prefix: str) -> str:
    return "sk-" + prefix + "-" + _OPENAI_BODY + _MARKER + _OPENAI_BODY


def _scan(tmp_path: Path, text: str) -> list[str]:
    target = tmp_path / "sample.txt"
    target.write_text(text + "\n", encoding="utf-8")
    return [r.message for r in cs.check_file(target)]


@pytest.mark.parametrize(
    ("token", "desc"),
    [
        ("AS" + "IA" + "ABCDEFGHIJKLMNOP", "AWS Access Key ID"),
        ("AB" + "IA" + "QRSTUVWXYZ234567", "AWS Access Key ID"),
        ("AC" + "CA" + "MNOPQRSTUV234567", "AWS Access Key ID"),
        ("gh" + "u_" + _BODY36, "GitHub token"),
        ("gh" + "s_" + _BODY36, "GitHub token"),
        ("gh" + "r_" + _BODY36, "GitHub token"),
        (_PAT, "GitHub fine-grained PAT"),
        (_openai_key("proj"), "OpenAI project / service-account / admin key"),
        (_openai_key("svcacct"), "OpenAI project / service-account / admin key"),
        (_openai_key("admin"), "OpenAI project / service-account / admin key"),
    ],
    ids=[
        "asia",
        "abia",
        "acca",
        "ghu",
        "ghs",
        "ghr",
        "github-pat",
        "sk-proj",
        "sk-svcacct",
        "sk-admin",
    ],
)
def test_gate_flags_the_new_credential_shapes(tmp_path: Path, token: str, desc: str) -> None:
    messages = _scan(tmp_path, f"value {token} end")
    assert len(messages) == 1 and desc in messages[0], messages


def test_gate_ignores_prefix_prose_and_lowercase_ids(tmp_path: Path) -> None:
    text = "\n".join(
        (
            "the github" + "_pat_ prefix",
            "AK" + "IA is the access key prefix",
            "id acca" + "0123456789abcdef",
            "id acca"
            + "abcdef234567abcd",  # lowercase base32 letters: only the scoped (?-i: keeps it unflagged
            "digest AC"
            + "CA"
            + "1F2E3D4C5B6A7980"
            + "ABCDEF",  # uppercase hex holding 0/1/8/9: not base32
            "the sk-" + "proj- prefix",
            "sk-" + "proj-xxxx",
            "an sk-" + "admin-key placeholder",
            "value " + "sk-" + "proj-" + "A1b2C3d4E5f6G7h8I9j" + " end",  # a 19-character body
        )
    )
    assert _scan(tmp_path, text) == []


@pytest.mark.parametrize(
    ("token", "desc"),
    [
        ("AK" + "IA" + "IOSFODNN7EXAMPLE", "AWS Access Key ID"),
        (
            "AK" + "IA" + "0123456789ABCDEF",
            "AWS Access Key ID",
        ),  # 0/1/8/9 are no base32, the old row took them
        ("ak" + "ia" + "iosfodnn7example", "AWS Access Key ID"),  # the old row ran under re.I
        ("gh" + "p_" + _BODY36, "GitHub token"),
        ("gh" + "o_" + _BODY36, "GitHub token"),
        ("GH" + "P_" + _BODY36, "GitHub token"),
        ("sk-" + "A1b2C3d4E5f6G7h8I9j0" + _MARKER + "K1l2M3n4O5p6Q7r8S9t0", "OpenAI API Key"),
    ],
    ids=["akia", "akia-digits", "akia-lower", "ghp", "gho", "ghp-upper", "legacy-sk"],
)
def test_gate_is_a_superset_of_its_old_rows(tmp_path: Path, token: str, desc: str) -> None:
    """A HARD gate keeps everything its old AKIA / ghp_ / gho_ / sk- rows flagged (under re.I)."""
    messages = _scan(tmp_path, f"value {token} end")
    assert len(messages) == 1 and desc in messages[0], messages


def test_gate_openai_project_row_body_minimum_is_20(tmp_path: Path) -> None:
    """The row's `{20,}` bound: a 19-character body is a placeholder-length run, 20 is a (truncated) key."""
    assert _scan(tmp_path, "value " + "sk-" + "proj-" + "A1b2C3d4E5f6G7h8I9j" + " end") == []
    assert len(_scan(tmp_path, "value " + "sk-" + "proj-" + "A1b2C3d4E5f6G7h8I9j0" + " end")) == 1


@pytest.mark.parametrize(
    "body",
    [
        ("A1b2C3d4E5f6G7h8I9j0K1L2M3N4O5" + "_" + ("p6Q7r8S9t0" * 6)[:51]),  # a 30 + `_` + 51 split
        (
            "A1b2C3d4E5f6G7h8I9j0K_" + "_" + ("p6Q7r8S9t0" * 6)[:59]
        ),  # an `_` inside the first 22 characters
    ],
    ids=["split-30-51", "underscore-in-first-segment"],
)
def test_gate_flags_a_fine_grained_pat_split_any_way(tmp_path: Path, body: str) -> None:
    """The flat 82-character body: a token the 22 + `_` + 59 split would miss is still flagged."""
    assert len(body) == 82, len(body)
    messages = _scan(tmp_path, "value " + "github" + "_pat_" + body + " end")
    assert len(messages) == 1 and "GitHub fine-grained PAT" in messages[0], messages


@pytest.mark.parametrize(
    "text",
    [
        "a"
        + "\\"
        + "n"
        + "AK"
        + "IA"
        + "IOSFODNN7EXAMPLE",  # a literal backslash-n glued to the key
        "x=%3D" + "AK" + "IA" + "IOSFODNN7EXAMPLE",  # a percent-encoded `=` glued to it
        "SECRET_" + "gh" + "p_" + _BODY36,  # an `_`-glued token
        "SECRET_" + _openai_key("proj"),
    ],
    ids=["backslash-n", "pct3d", "underscore-gh", "underscore-sk-proj"],
)
def test_gate_takes_no_word_boundary(tmp_path: Path, text: str) -> None:
    """A boundary that suits a redactor loses recall in a HARD gate (fabrik-lib D-517)."""
    assert len(_scan(tmp_path, text)) == 1
