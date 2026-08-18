"""Behaviour tests for the M0 shrink-audit evidence engine.

Every collector carries a BOTH-WAYS fixture pair (the duplex-fixture law, Lesson 126 /
the 1440-rounds incident): the good fixture proves it counts, the bad/empty fixture
proves it says "—" with a reason — never a fabricated 0. An empty universe and a clean
result must be distinguishable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

from kaizen_shrink_audit import (  # noqa: E402
    Sources,
    audit,
    collect_applicability,
    collect_check_activity,
    collect_invocations,
    collect_liveness,
    collect_mentions,
    enumerate_artifacts,
)


def _write_transcript(proj_dir: Path, name: str, rows: list) -> Path:
    proj_dir.mkdir(parents=True, exist_ok=True)
    f = proj_dir / name
    with f.open("wb") as fh:
        for r in rows:
            if isinstance(r, bytes):
                fh.write(r if r.endswith(b"\n") else r + b"\n")
            else:
                fh.write(json.dumps(r).encode("utf-8") + b"\n")
    return f


def test_transcript_invocations_counts_both_channels(tmp_path: Path):
    """The founding measurement: 145 Skill tool_use rows vs 4 <command-name> rows in one
    real session file — counting only the typed channel under-counts exactly the
    agent-initiated invocations. A QUOTED "skill":"x" in prose must NOT count, and one
    invalid-UTF-8 line must never make the file skip as binary."""
    proj = tmp_path / "projects" / "-opt-probe"
    _write_transcript(
        proj,
        "session1.jsonl",
        [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "<command-name>/fabrik-review</command-name> args here",
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "<command-name>/fabrik-review</command-name> again",
                        }
                    ],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "fabrik-spec"},
                        }
                    ]
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": 'prose quoting "skill":"fabrik-plan-review" must not count',
                        }
                    ]
                },
            },
            b'\xff\xfe invalid utf8 garbage line',
        ],
    )
    sig = collect_invocations(tmp_path / "projects")
    assert sig.measurable, sig.reason
    counts = sig.data
    assert counts["fabrik-review"]["typed"] == 2
    assert counts["fabrik-review"]["skill"] == 0
    assert counts["fabrik-spec"]["skill"] == 1
    assert counts["fabrik-spec"]["typed"] == 0
    assert "fabrik-plan-review" not in counts, "a quoted mention in prose is not an invocation"


def test_invocations_empty_root_is_unmeasurable_not_zero(tmp_path: Path):
    sig = collect_invocations(tmp_path / "absent")
    assert not sig.measurable
    assert sig.data is None
    assert "no transcript" in sig.reason.lower()


def test_invocations_all_files_unreadable_is_unmeasurable(tmp_path: Path):
    """Review finding (Phase A round 1): files that exist but cannot be READ must not
    present as a measurable empty universe — that is a fabricated zero."""
    proj = tmp_path / "projects" / "-opt-probe"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").mkdir()  # a directory named *.jsonl: stat() works, open() raises
    sig = collect_invocations(tmp_path / "projects")
    assert not sig.measurable
    assert "none readable" in sig.reason


# ── applicability (rule packs — never usage) ────────────────────────────────────────


def _mk_repo(tmp_path: Path, *, globs_line: str = 'globs: ["**/*.py"]') -> Path:
    import subprocess

    repo = tmp_path / "repo"
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "10-probe.md").write_text(
        f"---\ndescription: probe\n{globs_line}\n---\nbody\n"
    )
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n")
    (repo / "README.md").write_text("readme\n")
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
    ):
        subprocess.run(cmd, cwd=repo, capture_output=True, check=False)
    return repo


def test_applicability_counts_structural_and_recent_separately(tmp_path: Path):
    """Review finding baked into the plan: a time-bounded replay conflates structural
    reach with recent activity — the collector must emit BOTH columns."""
    repo = _mk_repo(tmp_path)
    sig = collect_applicability(repo, since_days=60)
    assert sig.measurable, sig.reason
    row = sig.data[".windsurf/rules/core/10-probe.md"]
    assert row["structural"] == 1, "one tracked .py file matches **/*.py"
    assert row["recent"] == 1, "the same file changed inside the git window"
    assert row["note"] == "applicability-only — activation unknown until M1"


def test_applicability_pack_without_globs_is_not_zero(tmp_path: Path):
    repo = _mk_repo(tmp_path, globs_line="description2: no globs here")
    sig = collect_applicability(repo, since_days=60)
    row = sig.data[".windsurf/rules/core/10-probe.md"]
    assert row["structural"] is None and row["recent"] is None
    assert "no globs" in row["note"]


def test_applicability_outside_a_git_repo_is_unmeasurable(tmp_path: Path):
    norepo = tmp_path / "norepo"
    (norepo / ".windsurf" / "rules").mkdir(parents=True)
    (norepo / ".windsurf" / "rules" / "p.md").write_text('---\nglobs: ["*.py"]\n---\n')
    sig = collect_applicability(norepo, since_days=60)
    assert not sig.measurable and "git" in sig.reason


# ── check activity ──────────────────────────────────────────────────────────────────


def test_check_activity_counts_and_empty_root_is_unmeasurable(tmp_path: Path):
    proj = tmp_path / "projects" / "-opt-probe"
    _write_transcript(
        proj,
        "s.jsonl",
        [{"type": "user", "message": {"content": "gate ran check_changelog twice: check_changelog"}}],
    )
    sig = collect_check_activity(tmp_path / "projects", ["check_changelog", "check_never"])
    assert sig.measurable
    assert sig.data["check_changelog"] == 2
    assert sig.data["check_never"] == 0
    bad = collect_check_activity(tmp_path / "absent", ["check_changelog"])
    assert not bad.measurable and bad.reason


def test_check_activity_name_boundaries_prevent_substring_false_positives(tmp_path: Path):
    """Review finding (Phase A round 1): `check_doc` must not count hits that belong to
    `check_doc_sync` — and `python-api` must not count inside `python-api-gpu`."""
    proj = tmp_path / "projects" / "-opt-probe"
    _write_transcript(
        proj,
        "s.jsonl",
        [{"type": "user", "message": {"content": "check_doc_sync ran; type python-api-gpu"}}],
    )
    sig = collect_check_activity(
        tmp_path / "projects", ["check_doc", "check_doc_sync", "python-api", "python-api-gpu"]
    )
    assert sig.data["check_doc_sync"] == 1
    assert sig.data["check_doc"] == 0, "substring of a longer name is not a hit"
    assert sig.data["python-api-gpu"] == 1
    assert sig.data["python-api"] == 0


# ── liveness join ───────────────────────────────────────────────────────────────────


def test_liveness_from_saved_report_and_unreadable_is_unmeasurable(tmp_path: Path):
    rep = tmp_path / "liveness.json"
    rep.write_text(
        json.dumps(
            {
                "proofs": {
                    "heartbeat": {"findings": [{"id": "cron-daemon", "verdict": "LIVE"}]},
                    "vacuity": {"findings": [{"id": "check_changelog", "verdict": "DEAD"}]},
                }
            }
        )
    )
    sig = collect_liveness(Sources(repo=tmp_path, liveness_json=rep))
    assert sig.measurable
    assert sig.data == {"cron-daemon": "LIVE", "check_changelog": "DEAD"}
    bad = collect_liveness(Sources(repo=tmp_path, liveness_json=tmp_path / "nope.json"))
    assert not bad.measurable and "unreadable" in bad.reason


# ── mentions ────────────────────────────────────────────────────────────────────────


def test_mentions_counts_ledgers_and_flags_run_records_supplementary(tmp_path: Path):
    led = tmp_path / "opt" / "proj" / "docs" / "development" / "reviews"
    led.mkdir(parents=True)
    (led / "r1.md").write_text("we ran check_changelog.py and again check_changelog.py\n")
    rr = tmp_path / "rr"
    rr.mkdir()
    (rr / "nosession.json").write_text(json.dumps({"command": "fabrik-review"}))
    sig = collect_mentions(
        Sources(repo=tmp_path, reviews_root=tmp_path / "opt", run_records=rr),
        ["check_changelog.py", "fabrik-review"],
    )
    assert sig.measurable
    assert sig.data["check_changelog.py"]["ledgers"] == 2
    assert sig.data["fabrik-review"]["run_records"] == 1
    bad = collect_mentions(
        Sources(repo=tmp_path, reviews_root=tmp_path / "empty", run_records=rr), ["x"]
    )
    assert not bad.measurable and "no review ledgers" in bad.reason


# ── census enumeration + the audit() composition ────────────────────────────────────


def _mk_sources_tree(tmp_path: Path) -> Sources:
    """A minimal full-fixture Sources tree: 1 command, 1 fragment, 1 pack (git repo),
    1 check, 1 hook, scaffold/manifest registries, 1 cron line, transcripts, ledgers."""
    repo = _mk_repo(tmp_path)
    (repo / "commands" / "_sources").mkdir(parents=True)
    (repo / "commands" / "_sources" / "fabrik-probe.md").write_text("# /fabrik-probe\n")
    (repo / "commands" / "_fragments").mkdir()
    (repo / "commands" / "_fragments" / "run-record.md").write_text("fragment\n")
    (repo / "scripts" / "enforcement").mkdir(parents=True)
    (repo / "scripts" / "enforcement" / "check_probe.py").write_text("#\n")
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / ".claude" / "hooks" / "stop_probe.py").write_text("#\n")
    (repo / "src" / "fabrik").mkdir(parents=True)
    (repo / "src" / "fabrik" / "scaffold.py").write_text(
        'SCAFFOLD_TYPES = frozenset(["python-api", "saas-skeleton"])\n'
    )
    (repo / "scripts" / "fabrik_synced_manifest.py").write_text(
        'CORE_SCRIPTS = ["scripts/final_gate.py"]\n'
    )
    proj = tmp_path / "projects" / "-opt-probe"
    _write_transcript(
        proj,
        "s.jsonl",
        [
            {"type": "user", "message": {"content": "<command-name>/fabrik-probe</command-name>"}},
            {"type": "user", "message": {"content": "output of check_probe was green"}},
        ],
    )
    led = tmp_path / "opt" / "proj" / "docs" / "development" / "reviews"
    led.mkdir(parents=True)
    (led / "r.md").write_text("mentions run-record.md and fabrik-probe\n")
    rep = tmp_path / "liveness.json"
    rep.write_text(
        json.dumps({"proofs": {"h": {"findings": [{"id": "check_probe", "verdict": "LIVE"}]}}})
    )
    return Sources(
        repo=repo,
        transcripts=tmp_path / "projects",
        reviews_root=tmp_path / "opt",
        run_records=tmp_path / "rr-absent",
        liveness_json=rep,
        crontab_text="*/5 * * * * python3 /opt/fabrik/scripts/probe_cron.py\n# comment\n",
        since_days=60,
    )


def test_enumerate_artifacts_reads_live_registries(tmp_path: Path):
    census, notes = enumerate_artifacts(_mk_sources_tree(tmp_path))
    assert census["command"] == ["fabrik-probe"]
    assert census["fragment"] == ["run-record"]
    assert census["gate-check"] == ["check_probe"]
    assert census["hook"] == ["stop_probe.py"]
    assert census["scaffold-type"] == ["python-api", "saas-skeleton"]
    assert census["core-script"] == ["scripts/final_gate.py"]
    assert census["cron"] == ["/opt/fabrik/scripts/probe_cron.py"]
    assert notes == []


def test_enumerate_missing_registry_is_a_note_never_silent(tmp_path: Path):
    src = _mk_sources_tree(tmp_path)
    (src.repo / "src" / "fabrik" / "scaffold.py").unlink()
    census, notes = enumerate_artifacts(src)
    assert "scaffold-type" not in census
    assert any("scaffold-type registry unreadable" in n for n in notes)


def test_audit_flags_shared_mention_keys(tmp_path: Path):
    """Review finding (Phase A round 1): two artifacts with the same basename in
    different classes share one textual mention count — the row must SAY so instead of
    silently double-attributing the evidence."""
    src = _mk_sources_tree(tmp_path)
    # a core-script whose basename collides with the hook's file name
    (src.repo / "scripts" / "fabrik_synced_manifest.py").write_text(
        'CORE_SCRIPTS = ["scripts/hooks/stop_probe.py"]\n'
    )
    rows, _ = audit(src)
    collided = [
        r for r in rows
        if r["cls"] in ("hook", "core-script")
        and "shared with" in (r["evidence_note"] or "")
    ]
    assert collided, "a mention-key collision must be named in evidence_note"


def test_audit_composes_rows_with_immune_and_verdict_none(tmp_path: Path):
    """Phase A gathers evidence, Phase B judges — the composition must leave
    immune/verdict None (the v1 circular-dependency review finding)."""
    rows, notes = audit(_mk_sources_tree(tmp_path))
    assert notes == []
    by_artifact = {(r["cls"], r["artifact"]): r for r in rows}
    cmd = by_artifact[("command", "fabrik-probe")]
    assert cmd["invocations"] == {"typed": 1, "skill": 0}
    assert cmd["last_seen"] is not None
    pack = by_artifact[("rule-pack", ".windsurf/rules/core/10-probe.md")]
    assert pack["applicability_structural"] == 1
    assert "applicability-only — activation unknown until M1" in pack["evidence_note"]
    chk = by_artifact[("gate-check", "check_probe")]
    assert chk["invocations"] == {"gate_output_hits": 1}
    assert chk["liveness"] == "LIVE"
    for r in rows:
        assert r["immune"] is None and r["verdict"] is None, "judgment is Phase B's"
    # census covers every class the fixture provides — nothing silently dropped
    assert {r["cls"] for r in rows} == {
        "command", "fragment", "rule-pack", "gate-check", "hook",
        "scaffold-type", "core-script", "cron",
    }
