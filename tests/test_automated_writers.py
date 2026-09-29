"""Behaviour tests for T05 (plan set 2026-09-29-plan-1-hub-worktree-cutover) — ids held until
merged, and the automated writers identifying themselves.

WHY (spec docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md § D5(b), D7, §
Validation V5, V11): `decisions.py --next-id` used to ignore live `--reserve-id` reservations
entirely, so a stale caller could be handed back an id someone else already held (H problem, spec
§49). `_live_reservations` used to prune purely by a fixed 7-day age, so an unmerged worktree
branch that simply outlived the TTL had its reservation silently dropped and a second worktree's
`--reserve-id` re-issued the exact id the first branch was still holding (D7, executed). Release
is now keyed on the id LANDING in the merge-base ledger (`_merge_base_ids`), never on age.
Separately, the daily kilo pipeline commits in the main checkout under D5, so its commits must
self-identify (`Agent-Name: kilo-pipeline`) for the commit-msg non-owner warning to tell them
apart from a session's own commits; and the boot hook stops running `sync_projects.py` in the
main checkout, since the files it regenerates are now written by the deployer's own `fabrik
apply` on the deployer's branch (D3).

⚠ Every reservation test redirects HOME to a throwaway `tmp_path` dir (`_reserve_path` is
`Path.home() / ".claude" / "state" / "decision-ids"`) — the real box-wide reservation store under
the operator's actual HOME is never touched.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("decisions", REPO / "scripts" / "decisions.py")
assert _spec and _spec.loader
dec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dec)

LEDGER_HEADER = (
    "# Decisions\n\n"
    "Append-at-top. One row per decision; rows are IMMUTABLE.\n\n"
    "| id | when | who | what (the decision) | why | where |\n"
    "|---|---|---|---|---|---|\n"
    "| D-001 | 2026-09-29 | operator | seed row | seed | seed |\n"
)


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=15, check=True
    )


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "master", cwd=root)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "DECISIONS.md").write_text(LEDGER_HEADER, encoding="utf-8")
    _git("add", "docs/DECISIONS.md", cwd=root)
    _git("commit", "-q", "-m", "seed", cwd=root)


def _worktree(root: Path, path: Path, branch: str) -> None:
    _git("worktree", "add", "-q", "-b", branch, str(path), "master", cwd=root)


def _git_env(monkeypatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")


# ── V5: --next-id skips a live reservation ──────────────────────────────────────────────────


def test_next_id_skips_a_live_reservation(tmp_path, monkeypatch, capsys):
    """Given one `--reserve-id` in a scratch repo (HOME redirected), `--next-id` must not return
    the reserved id. Before the fix `_next_id` read the ledger alone and never consulted the
    reservation file, so it handed back the SAME id `--reserve-id` had already promised."""
    _git_env(monkeypatch, tmp_path / "home")
    repo = tmp_path / "scratch"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "DECISIONS.md").write_text(LEDGER_HEADER, encoding="utf-8")

    assert dec.main(["--reserve-id", str(repo)]) == 0
    reserved = capsys.readouterr().out.strip()
    assert reserved == "D-002"

    assert dec.main(["--next-id", str(repo)]) == 0
    nxt = capsys.readouterr().out.strip()
    assert nxt != reserved, "next-id handed back the id --reserve-id already holds"
    assert nxt == "D-003"


# ── V5: a reservation outlives the fixed TTL until its row lands ───────────────────────────────


def test_reservation_outlives_the_fixed_ttl_until_its_row_lands(tmp_path, monkeypatch, capsys):
    """A reservation aged past 7 days whose id is on an unmerged branch's ledger, and not on the
    main checkout branch's, must still be held when `--reserve-id` runs from a second worktree —
    it must return a DIFFERENT id, never the one the aged (but unmerged) reservation holds. Once
    the row lands on the main checkout branch (master), the reservation is released —
    `_live_reservations` (the function both `--reserve-id` and `--next-id` now call) no longer
    counts it as live.
    """
    _git_env(monkeypatch, tmp_path / "home")
    root = tmp_path / "repo"
    _init_repo(root)
    wt1 = tmp_path / "wt1"
    _worktree(root, wt1, "agentA")
    wt2 = tmp_path / "wt2"
    _worktree(root, wt2, "agentB")

    # agentA reserves — its branch stays unmerged for the rest of this test.
    assert dec.main(["--reserve-id", str(wt1)]) == 0
    assert capsys.readouterr().out.strip() == "D-002"

    # Age the reservation entry past the OLD fixed 7-day TTL by hand — pre-fix this alone
    # released it and let a second worktree re-mint the exact same id (the D7 collision).
    key = dec._repo_key(wt1)
    reservation_file = dec._reserve_path(key)
    row = json.loads(reservation_file.read_text(encoding="utf-8").strip())
    assert row["id"] == 2
    row["at"] = time.time() - 8 * 86400
    reservation_file.write_text(json.dumps(row) + "\n", encoding="utf-8")

    # Second worktree, branch still unmerged into master: the aged-but-unmerged reservation
    # must still hold — --reserve-id must NOT re-issue D-002.
    assert dec.main(["--reserve-id", str(wt2)]) == 0
    reserved_b = capsys.readouterr().out.strip()
    assert reserved_b == "D-003", (
        "an aged-but-unmerged reservation was released by TTL alone — collision risk restored"
    )

    # Land agentA's row on the MAIN checkout branch (master) — root itself sits on master.
    ledger = root / "docs" / "DECISIONS.md"
    lines = ledger.read_text(encoding="utf-8").split("\n")
    sep = next(n for n, ln in enumerate(lines) if ln.strip().startswith("|---"))
    lines.insert(sep + 1, "| D-002 | 2026-09-29 | agentA | landed | landed | landed |")
    ledger.write_text("\n".join(lines), encoding="utf-8")
    _git("add", "docs/DECISIONS.md", cwd=root)
    _git("commit", "-q", "-m", "land D-002", cwd=root)

    # Once landed, D-002's reservation is no longer counted as live.
    wt2_ledger = dec._ledger_of(wt2)
    merged = set(dec._merge_base_ids(wt2_ledger)) | set(dec._ledger_ids(wt2_ledger))
    assert 2 in merged, "the landed row must be visible through the merge-base read"
    live_after = dec._live_reservations(reservation_file, merged)
    assert 2 not in live_after, "a landed reservation must be released, not held forever"


# ── V11 / D5: the automated writers identify themselves ────────────────────────────────────────


def test_pipeline_commit_signs_agent_name_kilo_pipeline():
    """D5(a): the daily kilo pipeline commits in the main checkout, so its commits must carry
    `Agent-Name: kilo-pipeline` — the token the commit-msg non-owner warning (D5(b)) uses to tell
    an automated writer's commit apart from a live agent session's."""
    text = (REPO / "scripts" / "kilo-benchmarks" / "autocommit_pipeline_outputs.sh").read_text(
        encoding="utf-8"
    )
    assert "Agent-Name: kilo-pipeline" in text
    # The trailer block stays ONE -m paragraph with no blank line inside it (contract §
    # Agent Provenance Trailers) — a blank line demotes everything above it to prose.
    start = text.index("Agent-Role: primary")
    end = text.index('"', start)
    block = text[start:end]
    assert "\n\n" not in block, "a blank line inside the trailer paragraph demotes it to prose"


def test_pipeline_never_commits_shared_agent_edited_files_rule_stays():
    """The ticket's DO-NOT does not touch this rule — confirm it is still there verbatim."""
    text = (REPO / "scripts" / "kilo-benchmarks" / "autocommit_pipeline_outputs.sh").read_text(
        encoding="utf-8"
    )
    assert "NEVER add shared agent-edited files here" in text


def test_boot_hook_stops_running_sync_projects_py():
    """D5(b)/V11: the boot hook no longer INVOKES sync_projects.py in the main checkout — its
    generated files (PORTS.md, docs/PROJECT_CATALOG.md, data/projects.yaml) come from the
    deployer's own `fabrik apply` on the deployer's branch (D3) instead. A COMMENT explaining the
    removal may still name the script (and does); no non-comment line may."""
    text = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    assert "SYNC_PROJECTS_SCRIPT" not in text
    code_lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    assert not any("sync_projects.py" in ln for ln in code_lines), (
        "sync_projects.py is still invoked outside a comment"
    )


# ── wave-1 review finding T02b-4: the boot hook's install_post_commit_hook.sh call swallowed
# stderr, so a foreign hook silently stopped BOTH hooks from being (re)installed ─────────────


def _extract_lines(text: str, marker: str, count: int) -> str:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if marker in ln:
            return "\n".join(lines[i : i + count])
    raise AssertionError(f"marker {marker!r} not found")


def test_boot_hook_prints_installer_stderr_only_on_failure(tmp_path):
    """A stub installer that exits 1 with a stderr message must have that message surfaced; a
    stub that exits 0 must stay silent (exactly as before). This runs the ACTUAL guarded block
    extracted from the shipped script — not a re-implementation of it — against a stub installer,
    so it exercises the real fix rather than a paraphrase of it.
    """
    script_text = (REPO / "scripts" / "wsl_startup_hook.sh").read_text(encoding="utf-8")
    block = _extract_lines(script_text, 'install_post_commit_hook.sh" ] && (', 3)

    fabrik_root = tmp_path / "fabrik_root"
    (fabrik_root / "scripts").mkdir(parents=True)
    stub = fabrik_root / "scripts" / "install_post_commit_hook.sh"

    def _run(stub_body: str) -> subprocess.CompletedProcess[str]:
        stub.write_text(f"#!/bin/bash\n{stub_body}\n", encoding="utf-8")
        stub.chmod(0o755)
        return subprocess.run(
            ["bash", "-c", f'FABRIK_ROOT="{fabrik_root}"\n{block}'],
            capture_output=True,
            text=True,
            timeout=15,
        )

    ok = _run("exit 0")
    assert ok.stderr == "", f"a successful install must stay silent, got: {ok.stderr!r}"

    failed = _run('echo "boom: foreign hook present" >&2; exit 1')
    assert "boom: foreign hook present" in failed.stderr
