"""clip_output — the --json truncation must preserve the TAIL and state its omission.

WHY. A bare `[:500]` dropped exactly the line every tool puts its totals on (mypy/ruff/
pytest all end with "Found N errors ..."), so the JSON showed "3 errors" indistinguishably
from "the first 3 of 83" — a consumer built a false cascade model and argued for reverting
correct fixes (job-agent 01M10DYMRG; the 1-of-4-findings gate line in transdoc 01M12A2D90
is the same class).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import final_gate as fg  # noqa: E402 — the path insert must precede the import


def test_short_output_passes_through_with_stable_schema():
    d = fg.clip_output("Found 2 errors in 1 file")
    assert d == {
        "output": "Found 2 errors in 1 file",
        "truncated": False,
        "omitted_lines": 0,
        "rerun": None,
    }


def test_long_output_keeps_the_tail_and_states_the_omission():
    body = "\n".join(f"file{i}.py:1: error: boom" for i in range(200))
    totals = "Found 200 errors in 200 files (checked 15 source files)"
    d = fg.clip_output(body + "\n" + totals)
    assert d["truncated"] is True
    assert d["omitted_lines"] > 0
    out = str(d["output"])
    assert totals in out, "the totals line — always LAST — must survive the clip"
    assert "[truncated:" in out, "the omission must be stated in-band, never silent"
    assert out.startswith("file0.py"), "the head survives too"


def test_truncated_row_names_the_command_that_prints_the_full_set():
    """Stating THAT output was omitted is not telling the reader how to see it.

    tryton-crm paid for the distinction on 2026-07-30 (LESSONS_LEARNT:907-927): a
    truncated row listed 3 docs, the check's own script listed 7, and scoping the fix
    to the preview would have left the gate RED. The rule lived only in that project's
    file, so the cost recurred hub-side 2026-08-31.
    """
    fg._CHECK_SCRIPTS["Doc Link Integrity"] = "scripts/enforcement/check_doc_links.py"
    body = "\n".join(f"docs/f{i}.md: broken ref" for i in range(200))
    d = fg.clip_output(body, check_name="Doc Link Integrity")
    assert d["truncated"] is True
    assert d["rerun"] == "python scripts/enforcement/check_doc_links.py"
    out = str(d["output"])
    assert "python scripts/enforcement/check_doc_links.py" in out, (
        "the rerun command must be IN-BAND — a consumer reading only `output` must see it"
    )
    assert "NEVER scope a fix to this preview" in out


def test_unknown_check_still_tells_you_to_re_run_the_script():
    """Degrade to the generic instruction rather than silently omitting it."""
    # must exceed head+tail (1400+600) or clip_output correctly returns untruncated
    body = "\n".join(f"docs/some/longer/path/file{i}.md: a broken reference" for i in range(200))
    d = fg.clip_output(body, check_name="a check registered by some other path")
    assert d["truncated"] is True
    assert d["rerun"] is None
    assert "re-run this check's own script" in str(d["output"])
