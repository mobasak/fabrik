"""Behavior-Contract tests for the SessionStart agent-role hook (.claude/hooks/agent_role.py).

The hook distributes fleet-wide (governance-sync trigger surface), so its fleet-safety
behaviors (b)-(d) are load-bearing: a project with no charters must see a silent no-op.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "agent_role.py"
AGENTS_DIR = REPO / "docs" / "reference" / "agents"
REAL_AGENT_FILES = sorted(AGENTS_DIR.glob("*.md")) if AGENTS_DIR.is_dir() else []


def _assert_matches_charter_marker_contract(path: Path) -> None:
    """The contract docs/reference/agents/ enforces today (T02a round-2/3 review): every
    kaizen-log-* file must NOT carry the marker (it stays a silent no-op), and every OTHER
    file in the directory is expected to BE a charter — it must carry the '# Agent charter'
    marker on its first line (the whole line, or the marker followed by whitespace). A file
    that is neither a kaizen log nor a marked charter fails this check; that states the
    directory's current contract, it is not a claim about any one file's intent (a
    legitimate non-charter reference doc, e.g. a README or INDEX, would also fail here and
    would need the directory's contract revisited, not this message reworded again)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    first_line = lines[0] if lines else ""  # empty file -> fail the assertion below, never IndexError
    if path.name.startswith("kaizen-log-"):
        assert not first_line.startswith("# Agent charter"), (
            f"{path.name}: a kaizen log must NOT carry the charter marker"
        )
    else:
        assert first_line.startswith("# Agent charter") and (
            len(first_line) == len("# Agent charter") or first_line[len("# Agent charter")].isspace()
        ), (
            f"{path.name}: docs/reference/agents/ contract violation — every file here that is "
            "not kaizen-log-* must carry the '# Agent charter' marker on its first line (the "
            "whole line, or followed by whitespace); this file has neither shape"
        )


def _run(env_val: str | None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_AGENT"}
    if env_val is not None:
        env["CLAUDE_AGENT"] = env_val
    env["CLAUDE_PROJECT_DIR"] = str(cwd or REPO)
    return subprocess.run(
        [sys.executable, str(HOOK)], capture_output=True, text=True, timeout=30, env=env
    )


def test_named_role_injects_charter() -> None:
    r = _run("infra")
    assert r.returncode == 0
    assert "AGENT ROLE: infra" in r.stdout
    assert "Mandate" in r.stdout  # charter body actually included


def test_unset_is_silent_noop() -> None:
    r = _run(None)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_unregistered_name_without_charter_is_silent_noop() -> None:
    """A syntactically-valid, project-local name with no charter file is the fleet-safe
    default (T02a relaxed the fixed role enum — this name is now ACCEPTED, but silent
    because docs/reference/agents/xyz-not-a-role.md does not exist)."""
    r = _run("xyz-not-a-role")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_missing_charter_file_is_silent_noop(tmp_path: Path) -> None:
    # a project tree with the hook but no charters (the fleet case)
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


# --- Phase A review findings (native closer) — each pins a fleet-safety contract ---------------


def test_traversal_name_is_silent_noop() -> None:
    """CLAUDE_AGENT='../../CONFIGURATION' must never inject a file outside agents/."""
    r = _run("../../CONFIGURATION")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_charter_body_is_delimited() -> None:
    """Plan interface: the charter body is fenced by explicit delimiters, so the overlay's
    end is unambiguous next to CLAUDE.md's own sections."""
    r = _run("infra")
    assert "--- charter begin ---" in r.stdout
    assert "--- charter end ---" in r.stdout
    body = r.stdout.split("--- charter begin ---", 1)[1]
    assert "Mandate" in body.split("--- charter end ---", 1)[0]


def test_oversized_charter_truncates_loudly(tmp_path: Path) -> None:
    """A cut charter must SAY it was cut — the safety clauses live at the tail."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "infra.md").write_text("# Agent charter — infra\n" + "x" * 40_000 + "\nTAIL-MARKER\n")
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert "TRUNCATED" in r.stdout
    assert len(r.stdout.encode()) < 40_000  # byte cap actually binds


def test_symlinked_charter_outside_repo_is_silent(tmp_path: Path) -> None:
    """'Never reads outside the repo' is enforced by construction (realpath containment)."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET-OUTSIDE\n")
    (d / "infra.md").symlink_to(outside)
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert "SECRET-OUTSIDE" not in r.stdout


def test_empty_charter_is_silent(tmp_path: Path) -> None:
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "infra.md").write_text("   \n")
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_cwd_fallback_without_project_dir() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_AGENT", "CLAUDE_PROJECT_DIR")}
    env["CLAUDE_AGENT"] = "infra"
    r = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True,
                       timeout=30, env=env, cwd=REPO)
    assert r.returncode == 0
    assert "AGENT ROLE: infra" in r.stdout


# --- round-2 closer findings ------------------------------------------------------------------


def test_symlinked_agents_directory_is_contained(tmp_path: Path) -> None:
    """A symlinked agents/ DIRECTORY resolving outside the repo root is never read."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "infra.md").write_text("SECRET-DIR-BODY\n")
    repo = tmp_path / "repo"
    (repo / "docs" / "reference").mkdir(parents=True)
    (repo / "docs" / "reference" / "agents").symlink_to(outside, target_is_directory=True)
    r = _run("infra", cwd=repo)
    assert r.returncode == 0
    assert "SECRET-DIR-BODY" not in r.stdout


def test_truncation_binds_in_bytes_for_multibyte(tmp_path: Path) -> None:
    """A CJK charter must be capped in BYTES (the old char-read emitted 3x the cap)."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "infra.md").write_text("# Agent charter — infra\n" + "世" * 40_000, encoding="utf-8")  # 3 bytes/char
    r = _run("infra", cwd=tmp_path)
    assert r.returncode == 0
    assert "TRUNCATED" in r.stdout
    assert len(r.stdout.encode()) < 33_500  # cap + banner/fence margin only


# --- T02a: any [a-z0-9-]{1,32} project-local name, charter optional -----------------------------
# Fixtures below live entirely under tmp_path — never docs/reference/agents/ (the real hub dir).


def test_arbitrary_name_with_charter_injects(tmp_path: Path) -> None:
    """Behavior Contract row 1: a non-hub name (e.g. 'alpha') with a matching charter injects
    it exactly like the hub's pinned roles used to — the relaxation is not infra/fleet/intel-only."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "alpha.md").write_text("# Agent charter — alpha\n\nMandate: ship the thing.\n")
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert "AGENT ROLE: alpha" in r.stdout
    assert "Mandate" in r.stdout


def test_arbitrary_name_without_charter_is_silent_noop(tmp_path: Path) -> None:
    """Behavior Contract row 2: an accepted name with no charter file is a silent no-op —
    today's non-hub / no-charter fleet path, now reachable by any project-local name."""
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_invalid_name_shape_is_silent_noop(tmp_path: Path) -> None:
    """Behavior Contract row 3 (part 1): 'Alpha_1' has an uppercase letter and an underscore,
    outside [a-z0-9-]{1,32} — rejected before any charter lookup. A REAL marked charter is
    planted for this exact name so the no-op can only come from the name gate, never from a
    missing file or a missing marker (T02a round-4 fixup — a widened regex must still fail this)."""
    name = "Alpha_1"
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / f"{name}.md").write_text("# Agent charter\n\nMandate: unreachable — name gate must reject first.\n")
    r = _run(name, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_33_char_name_is_silent_noop(tmp_path: Path) -> None:
    """Behavior Contract row 3 (part 2): 33 chars exceeds the {1,32} bound — silent no-op even
    though a matching, PROPERLY MARKED charter file exists, so the no-op can only come from the
    name-length gate, never from a missing marker or a missing file (T02a round-4 fixup — the
    original fixture had no marker at all, so it no-opped for the wrong reason)."""
    name = "a" * 33
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / f"{name}.md").write_text("# Agent charter\n\nMandate: unreachable — name gate must reject first.\n")
    r = _run(name, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_32_char_name_is_accepted(tmp_path: Path) -> None:
    """Behavior Contract row 3 (part 3): exactly 32 chars is the accepted boundary."""
    name = "a" * 32
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / f"{name}.md").write_text(f"# Agent charter — {name}\nMandate: reachable at 32 chars.\n")
    r = _run(name, cwd=tmp_path)
    assert r.returncode == 0
    assert f"AGENT ROLE: {name}" in r.stdout
    assert "Mandate" in r.stdout


def test_symlinked_charter_escaping_agents_dir_is_silent_for_any_name(tmp_path: Path) -> None:
    """Behavior Contract row 4: a symlinked charter escaping docs/reference/agents/ is refused
    exactly as today (realpath containment, unchanged), now exercised through a non-hub name."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET-OUTSIDE-ALPHA\n")
    (d / "alpha.md").symlink_to(outside)
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert "SECRET-OUTSIDE-ALPHA" not in r.stdout


# --- T02a acceptance review — finding 1: charter marker required --------------------------------
# docs/reference/agents/ holds non-charter documents too (kaizen logs); a file whose NAME happens
# to match an accepted agent name must not be injected unless its first line marks it as a charter.


def test_marked_file_injects(tmp_path: Path) -> None:
    """A tmp file whose first line carries the charter marker injects normally."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "alpha.md").write_text("# Agent charter — alpha\n\nMandate: do the work.\n")
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert "AGENT ROLE: alpha" in r.stdout
    assert "Mandate" in r.stdout


def test_unmarked_kaizen_log_is_not_injected(tmp_path: Path) -> None:
    """A file whose first line is a kaizen-log header (not '# Agent charter') must be a silent
    no-op — exactly the live escape this finding closes: CLAUDE_AGENT=kaizen-log-infra against
    the real repo would otherwise inject docs/reference/agents/kaizen-log-infra.md as a charter."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "kaizen-log-infra.md").write_text(
        "# Kaizen log — infra (weekly, Monday after the cron batch; ≤90 min timebox)\n\n"
        "Mandate: this is a log entry, never a charter.\n"
    )
    r = _run("kaizen-log-infra", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


# --- T02a acceptance review — finding 2: fullmatch, not match+$ ---------------------------------


def test_embedded_newline_in_name_is_silent_noop() -> None:
    """A name is never allowed to smuggle extra content past the shape check via an embedded
    newline — fullmatch() makes this explicit regardless of what precedes it in main()."""
    r = _run("alpha\nDANGEROUS")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


# --- T02a round-2 review — finding: the real docs/reference/agents/ roster is untested -----------
# The marker is now load-bearing on the three REAL hub charters; nothing previously asserted that
# fleet.md/intel.md (only infra.md had a live-file test) still carry it, or that the two kaizen
# logs still don't. This section READS the real files but never mutates them (outside Touches).


def test_real_agents_dir_is_not_empty() -> None:
    """Denominator guard: the parametrized test below is vacuous if the glob ever finds nothing
    (a moved/renamed directory would silently drop all coverage — CLAUDE.md denominator-honesty)."""
    assert REAL_AGENT_FILES, f"no files found under {AGENTS_DIR}"


@pytest.mark.parametrize("charter_path", REAL_AGENT_FILES, ids=lambda p: p.name)
def test_real_agents_dir_file_matches_charter_marker_contract(charter_path: Path) -> None:
    """Runs over the LIVE directory, so an added/renamed/reworded file is covered automatically:
    every real charter (infra.md, fleet.md, intel.md today) must open with the marker the hook
    requires to inject it, and every kaizen-log-* file must NOT — documenting and enforcing the
    directory's contract in one test, per file, by name."""
    _assert_matches_charter_marker_contract(charter_path)


def test_charter_marker_contract_catches_a_reworded_h1(tmp_path: Path) -> None:
    """RED proof for the parametrized test above: copy the REAL fleet.md into tmp_path and
    reword its H1 the way a future editor might (never touching the real file, outside this
    ticket's Touches); the same assertion the parametrized test runs must then FAIL loudly
    instead of silently no-opping the charter."""
    real_fleet = AGENTS_DIR / "fleet.md"
    mutated = tmp_path / "fleet.md"
    mutated.write_text(
        real_fleet.read_text(encoding="utf-8").replace(
            "# Agent charter — fleet", "## Fleet role (renamed by a future editor)", 1
        ),
        encoding="utf-8",
    )
    assert not mutated.read_text(encoding="utf-8").splitlines()[0].startswith("# Agent charter")
    with pytest.raises(AssertionError):
        _assert_matches_charter_marker_contract(mutated)


def test_contract_helper_fails_cleanly_on_empty_file(tmp_path: Path) -> None:
    """T02a round-3 finding: an EMPTY file used to IndexError inside the helper
    (`splitlines()[0]` on an empty string) instead of failing the assertion with a
    message — the helper must FAIL, never crash, on a stray empty file."""
    empty = tmp_path / "stray.md"
    empty.write_text("")
    with pytest.raises(AssertionError, match="contract violation"):
        _assert_matches_charter_marker_contract(empty)


# --- T02a round-2 review — finding: the marker needs a delimiter, not a bare prefix --------------
# `startswith(b"# Agent charter")` alone also matched "# Agent charter-obsolete" and
# "# Agent chartering". The hook now requires end-of-line or whitespace right after the marker.


def test_marker_lookalike_suffix_is_not_injected(tmp_path: Path) -> None:
    """'# Agent charter-obsolete' shares the prefix but is not the marker — must be a silent
    no-op exactly like a missing/unmarked file, never injected as a binding overlay."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "alpha.md").write_text(
        "# Agent charter-obsolete — do not use\n\nMandate: this must never inject.\n"
    )
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_marker_with_em_dash_suffix_still_injects(tmp_path: Path) -> None:
    """The real charters' shape — '# Agent charter — <name>' — must keep injecting: the
    delimiter fix must not regress the marker's actual, whitespace-separated production form."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "alpha.md").write_text("# Agent charter — alpha\n\nMandate: still injects.\n")
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert "AGENT ROLE: alpha" in r.stdout
    assert "Mandate" in r.stdout


def test_bare_marker_with_no_suffix_still_injects(tmp_path: Path) -> None:
    """The marker as the WHOLE first line (no trailing name) is also a valid charter — the
    end-of-line branch of the delimiter check."""
    d = tmp_path / "docs" / "reference" / "agents"
    d.mkdir(parents=True)
    (d / "alpha.md").write_text("# Agent charter\n\nMandate: bare marker still injects.\n")
    r = _run("alpha", cwd=tmp_path)
    assert r.returncode == 0
    assert "AGENT ROLE: alpha" in r.stdout
    assert "Mandate" in r.stdout
