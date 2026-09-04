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
    _registry_surface_map,
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
            b"\xff\xfe invalid utf8 garbage line",
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
        [
            {
                "type": "user",
                "message": {"content": "gate ran check_changelog twice: check_changelog"},
            }
        ],
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
        r
        for r in rows
        if r["cls"] in ("hook", "core-script") and "shared with" in (r["evidence_note"] or "")
    ]
    assert collided, "a mention-key collision must be named in evidence_note"


# ── Phase B: immune registry + verdict assignment + report ──────────────────────────


def _row(**kw) -> dict:
    base = {
        "artifact": "x",
        "cls": "command",
        "invocations": None,
        "last_seen": None,
        "applicability_structural": None,
        "applicability_recent": None,
        "liveness": None,
        "mentions": None,
        "evidence_note": "",
        "immune": None,
        "verdict": None,
    }
    base.update(kw)
    return base


def test_immune_entries_all_carry_justifications():
    from kaizen_immune_list import IMMUNE, JUSTIFICATIONS

    assert frozenset(JUSTIFICATIONS) == IMMUNE
    assert all(isinstance(j, str) and j.strip() for j in JUSTIFICATIONS.values())
    # plan-named members: rare-by-design commands, the Stop hook, the never-route script
    for member in ("fabrik-decommission", "fabrik-upstream", "final_gate_stop.py", "final_gate.py"):
        assert member in IMMUNE, member
    # the never-route prefix immunizes the whole gate-check class, self-maintaining
    assert "check_changelog" in IMMUNE


def test_zero_usage_immune_artifact_is_never_candidate():
    """Spec § M0 (final-panel amendment): rarely-fired safety machinery presents as
    'unused' precisely because it works — zero usage must NOT make it a candidate."""
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(
                artifact="fabrik-decommission",
                cls="command",
                invocations={"typed": 0, "skill": 0},
                mentions={"ledgers": 0, "run_records": 0},
            ),
        ]
    )
    r = rows[0]
    assert r["verdict"] == "keep"
    assert r["immune"] is True
    assert "keep — immune:" in r["evidence_note"]


def test_rule_pack_zero_usage_is_unknown_never_candidate():
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(
                artifact=".windsurf/rules/core/10-x.md",
                cls="rule-pack",
                applicability_structural=0,
                applicability_recent=0,
                evidence_note="applicability-only — activation unknown until M1",
            ),
        ]
    )
    assert rows[0]["verdict"] == "unknown"
    assert "applicability-only — activation unknown until M1" in rows[0]["evidence_note"]


def test_zero_on_every_measurable_signal_and_not_immune_is_candidate():
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(
                artifact="fabrik-nonesuch",
                cls="command",
                invocations={"typed": 0, "skill": 0},
                mentions={"ledgers": 0, "run_records": 0},
            ),
            _row(
                artifact="fabrik-busy",
                cls="command",
                invocations={"typed": 3, "skill": 1},
                mentions={"ledgers": 0, "run_records": 0},
            ),
        ]
    )
    assert rows[0]["verdict"] == "candidate"
    assert rows[1]["verdict"] == "keep"


def test_all_class_signals_unmeasurable_routes_unknown_never_candidate():
    """The honesty rule generalized (review amendment): a class whose named signals are
    ALL unmeasurable routes to unknown — absence of measurement is not absence of use."""
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(artifact="fabrik-dark", cls="command", invocations=None, mentions=None),
        ]
    )
    assert rows[0]["verdict"] == "unknown"
    assert "unmeasurable" in rows[0]["evidence_note"]


def test_verdict_tokens_are_the_exact_enum():
    """Review finding on the v1 spec: decorated tokens ('keep — immune: …') read as
    extra verdict forms — the TOKEN is exactly one of three; decoration lives in
    evidence_note."""
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(artifact="final_gate.py", cls="core-script"),
            _row(artifact="x.md", cls="rule-pack"),
            _row(
                artifact="fabrik-nonesuch",
                cls="command",
                invocations={"typed": 0, "skill": 0},
                mentions={"ledgers": 0, "run_records": 0},
            ),
        ]
    )
    for r in rows:
        assert r["verdict"] in ("candidate", "keep", "unknown"), r["verdict"]


def test_liveness_live_is_usage_evidence_dead_is_measured_zero():
    from kaizen_shrink_audit import assign_verdicts

    live, dead, unk = assign_verdicts(
        [
            _row(
                artifact="a.py",
                cls="hook",
                liveness="LIVE",
                mentions={"ledgers": 0, "run_records": 0},
            ),
            _row(
                artifact="b.py",
                cls="hook",
                liveness="DEAD",
                mentions={"ledgers": 0, "run_records": 0},
            ),
            _row(artifact="c.py", cls="hook", liveness=None, mentions=None),
        ]
    )
    assert live["verdict"] == "keep"
    assert dead["verdict"] == "candidate"
    assert unk["verdict"] == "unknown"


def test_fragment_usage_is_include_references_not_ledger_mentions(tmp_path: Path):
    """Live-census false positive (Phase B round 0, self-review): 6 of 13 fragments listed
    as candidates while being {{include:}}-ed by many command sources. A fragment's usage
    channel IS inclusion at render time; ledger mentions are secondary."""
    from kaizen_shrink_audit import assign_verdicts, audit

    src = _mk_sources_tree(tmp_path)
    (src.repo / "commands" / "_sources" / "fabrik-probe.md").write_text(
        "# /fabrik-probe\n{{include:run-record}}\n"
    )
    (src.repo / "commands" / "_fragments" / "orphan.md").write_text("included nowhere\n")
    rows = assign_verdicts(audit(src)[0])
    by = {(r["cls"], r["artifact"]): r for r in rows}
    used = by[("fragment", "run-record")]
    assert used["invocations"] == {"includes": 1}
    assert used["verdict"] == "keep", "an included fragment is USED"
    orphan = by[("fragment", "orphan")]
    assert orphan["verdict"] == "candidate", "a never-included, unmentioned fragment is a candidate"


def test_cron_liveness_joins_via_registry_cron_match(tmp_path: Path):
    """Live-census false positive (Phase B round 0): provably-live crons fell to candidate
    because liveness findings key on registry surface ids (via cron_match), never script
    paths — the join must go through the registry declarations."""
    from kaizen_shrink_audit import assign_verdicts, audit

    src = _mk_sources_tree(tmp_path)
    fabrik_dir = src.repo / ".fabrik"
    fabrik_dir.mkdir(exist_ok=True)
    (fabrik_dir / "liveness-registry.json").write_text(
        json.dumps({"surfaces": [{"id": "probe-cron", "cron_match": "probe_cron.py"}]})
    )
    src.liveness_json.write_text(
        json.dumps({"proofs": {"h": {"findings": [{"id": "probe-cron", "verdict": "LIVE"}]}}})
    )
    rows = assign_verdicts(audit(src)[0])
    cron = next(r for r in rows if r["cls"] == "cron")
    assert cron["liveness"] == "LIVE", "the registry cron_match must join the verdict"
    assert cron["verdict"] == "keep"


def test_immune_lookup_matches_relative_cron_forms():
    """Live-census false positive (Phase B round 0): liveness_audit.py listed as a
    candidate — its immune entry is the absolute path, the census key was relative."""
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(
                artifact="scripts/sysadmin/liveness_audit.py",
                cls="cron",
                mentions={"ledgers": 0, "run_records": 0},
            ),
        ]
    )
    assert rows[0]["immune"] is True
    assert rows[0]["verdict"] == "keep"


def test_report_refuses_a_row_with_a_decorated_or_missing_verdict(tmp_path: Path):
    """Phase B review finding: the token enum had no runtime guard — a future bug
    assigning 'keep — immune: …' as the TOKEN would render silently."""
    import pytest
    from kaizen_shrink_audit import render_report

    bad = _row(artifact="x", cls="command", verdict="keep — immune: nope")
    with pytest.raises(ValueError, match="verdict token"):
        render_report([bad], [], tmp_path / "r.md")
    unassigned = _row(artifact="y", cls="command")  # verdict None: assign_verdicts never ran
    with pytest.raises(ValueError, match="verdict token"):
        render_report([unassigned], [], tmp_path / "r2.md")


def test_report_covers_every_census_row_and_carries_the_ruling_section(tmp_path: Path):
    from kaizen_shrink_audit import assign_verdicts, audit, render_report

    src = _mk_sources_tree(tmp_path)
    rows, notes = audit(src)
    rows = assign_verdicts(rows)
    out = tmp_path / "report.md"
    text = render_report(rows, notes, out)
    assert out.exists()
    # count ARTIFACT rows only — legend + table headers also start with "| ", and a
    # header-inclusive count passed even with zero artifact rows (closing-review finding)
    artifact_rows = [ln for ln in text.splitlines() if ln.startswith("| `")]
    assert len(artifact_rows) == len(rows), "every census row must render, none twice"
    assert "## Operator ruling" in text
    assert "applicability-only — activation unknown until M1" in text
    assert "no gate JSON history exists" in text, "the evidence-substitution erratum"
    assert "final for METER SIZING" in text, "the census-scope statement"


# ── Phase C closing-review findings (native non-author reviewer) ────────────────────


def test_cron_census_prefers_the_script_over_env_assignments(tmp_path: Path):
    """H: `PYTHONPATH=/opt/fabrik/src …/audit_x.py` keyed on `/opt/fabrik/src` — a
    phantom directory artifact that swallowed two LIVE crons."""
    src = _mk_sources_tree(tmp_path)
    src.crontab_text = (
        "0 * * * * PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python "
        "/opt/fabrik/scripts/audit_authelia_gates.py\n"
        "5 * * * * PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python "
        "/opt/fabrik/scripts/audit_all_registrars.py\n"
    )
    census, _ = enumerate_artifacts(src)
    assert census["cron"] == [
        "/opt/fabrik/scripts/audit_authelia_gates.py",
        "/opt/fabrik/scripts/audit_all_registrars.py",
    ], census["cron"]


def test_immune_lookup_reaches_the_stem_of_a_pathed_check(tmp_path: Path):
    """H: the same file rendered `immune: keep` as a gate-check and `[ ] candidate` as
    a cron — the lookup must reach the stem (`check_mutation`) from the path form."""
    from kaizen_shrink_audit import assign_verdicts

    rows = assign_verdicts(
        [
            _row(
                artifact="scripts/enforcement/check_mutation.py",
                cls="cron",
                mentions={"ledgers": 0, "run_records": 0},
            ),
        ]
    )
    assert rows[0]["immune"] is True
    assert rows[0]["verdict"] == "keep"


def test_hook_liveness_joins_via_registry_command_contains(tmp_path: Path):
    """H: hook surfaces key on `evidence.command_contains`; without that join every
    hook row falsely read 'declares no liveness surface' — the exact defect class the
    cron join fixed, left unfixed for hooks."""
    from kaizen_shrink_audit import assign_verdicts, audit

    src = _mk_sources_tree(tmp_path)
    fabrik_dir = src.repo / ".fabrik"
    fabrik_dir.mkdir(exist_ok=True)
    (fabrik_dir / "liveness-registry.json").write_text(
        json.dumps(
            {
                "surfaces": [
                    {
                        "id": "probe-hook",
                        "kind": "hook",
                        "evidence": {"type": "hook", "command_contains": "stop_probe.py"},
                    },
                ]
            }
        )
    )
    src.liveness_json.write_text(
        json.dumps({"proofs": {"h": {"findings": [{"id": "probe-hook", "verdict": "LIVE"}]}}})
    )
    rows = assign_verdicts(audit(src)[0])
    hook = next(r for r in rows if r["cls"] == "hook")
    assert hook["liveness"] == "LIVE"
    assert hook["verdict"] == "keep"


def test_transcript_walk_includes_subagent_session_files(tmp_path: Path):
    """M: 5,848 of 11,270 transcript files live at <proj>/<session>/subagents/*.jsonl —
    a non-recursive glob scanned 46% of the corpus while presenting as the whole."""
    proj = tmp_path / "projects" / "-opt-probe"
    sub = proj / "session-uuid" / "subagents"
    _write_transcript(
        sub,
        "agent-x.jsonl",
        [{"type": "user", "message": {"content": "<command-name>/fabrik-probe</command-name>"}}],
    )
    sig = collect_invocations(tmp_path / "projects")
    assert sig.measurable and sig.data.get("fabrik-probe", {}).get("typed") == 1


def test_mentions_are_boundary_aware(tmp_path: Path):
    """M: `fabrik-deploy` credited 16 ledger mentions of which 9 belonged to
    fabrik-deploy-plan/-plan-review/-verify — a keep verdict resting on other
    commands' names."""
    led = tmp_path / "opt" / "proj" / "docs" / "development" / "reviews"
    led.mkdir(parents=True)
    (led / "r.md").write_text(
        "ran fabrik-deploy-plan then fabrik-deploy-plan-review then fabrik-deploy once\n"
    )
    sig = collect_mentions(
        Sources(repo=tmp_path, reviews_root=tmp_path / "opt", run_records=tmp_path / "rr"),
        ["fabrik-deploy", "fabrik-deploy-plan", "fabrik-deploy-plan-review"],
    )
    assert sig.data["fabrik-deploy"]["ledgers"] == 1
    assert sig.data["fabrik-deploy-plan"]["ledgers"] == 1
    assert sig.data["fabrik-deploy-plan-review"]["ledgers"] == 1


def test_enumerate_notes_every_unenumerable_class(tmp_path: Path):
    """M: 5 of 8 classes dropped SILENTLY when their registry was absent — the
    docstring promised a note per unreadable registry and kept it for only 3."""
    src = Sources(
        repo=tmp_path / "bare",
        transcripts=tmp_path / "t",
        reviews_root=tmp_path / "opt",
        run_records=tmp_path / "rr",
        crontab_text="",
    )
    (tmp_path / "bare").mkdir()
    census, notes = enumerate_artifacts(src)
    assert census == {}
    for cls in (
        "command",
        "fragment",
        "rule-pack",
        "gate-check",
        "hook",
        "scaffold-type",
        "core-script",
    ):
        assert any(cls in n for n in notes), f"missing-class note owed for {cls}: {notes}"


def test_assign_verdicts_is_idempotent():
    """L: a second verdict pass duplicated every immune justification into the note.
    Round-3 hardening: the FIRST guard used split('; ') and was defeated by every
    justification that itself contains '; ' — 58 of 68 immune rows (the never-route
    class and the Stop hook); this test now uses a semicolon-bearing member."""
    from kaizen_shrink_audit import assign_verdicts

    rows = [
        _row(artifact="fabrik-decommission", cls="command"),  # semicolon-free
        _row(artifact="check_changelog", cls="gate-check"),  # never-route: has '; '
        _row(artifact="final_gate_stop.py", cls="hook"),  # Stop hook: has '; '
    ]
    for _ in range(3):
        assign_verdicts(rows)
    for r in rows:
        assert r["evidence_note"].count("keep — immune:") == 1, r["evidence_note"]


def test_includes_count_only_whole_line_markers(tmp_path: Path):
    """L: the assembler substitutes only whole-line {{include:x}} markers — a
    mid-sentence mention must not credit the fragment with a render-time inclusion."""
    from kaizen_shrink_audit import collect_includes

    repo = tmp_path / "repo"
    (repo / "commands" / "_sources").mkdir(parents=True)
    (repo / "commands" / "_sources" / "fabrik-x.md").write_text(
        "{{include:run-record}}\nsee the {{include:grounding-code}} marker in prose\n"
    )
    sig = collect_includes(repo)
    assert sig.data.get("run-record") == 1
    assert "grounding-code" not in sig.data


def test_typed_channel_ignores_tool_result_echoes(tmp_path: Path):
    """L (observer effect): a session that merely DISCUSSES the candidate list writes
    literal <command-name> strings into its transcript via tool results — those must
    not count as invocations, or every audited candidate flips to keep next run."""
    proj = tmp_path / "projects" / "-opt-probe"
    _write_transcript(
        proj,
        "s.jsonl",
        [
            {"type": "user", "message": {"content": "<command-name>/fabrik-real</command-name>"}},
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "t1",
                            "content": "grep hit: <command-name>/fabrik-echoed</command-name>",
                        },
                    ]
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "the report lists <command-name>/fabrik-echoed</command-name>",
                        },
                    ]
                },
            },
        ],
    )
    sig = collect_invocations(tmp_path / "projects")
    assert sig.data.get("fabrik-real", {}).get("typed") == 1
    assert "fabrik-echoed" not in sig.data, "tool-result/assistant echoes are not invocations"


def test_applicability_recent_counts_only_still_tracked_files(tmp_path: Path):
    """L: a pack whose only 'recent' matches are DELETED files read as recently
    applicable (75-workers-jobs rendered 0/15 on 15 deleted paths)."""
    import subprocess

    repo = _mk_repo(tmp_path)
    doomed = repo / "src" / "doomed.py"
    doomed.write_text("x = 2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=False)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "add"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    doomed.unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=False)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "rm"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    sig = collect_applicability(repo, since_days=60)
    row = sig.data[".windsurf/rules/core/10-probe.md"]
    assert row["structural"] == 1
    assert row["recent"] == 1, "the deleted file must not count as recent applicability"


def test_core_script_liveness_joins_via_registry(tmp_path: Path):
    """Verification round: the registry join covered cron+hook but not core-script —
    the legend advertises 'core-script: liveness + mentions' while mail.py's DEAD
    surface never reached the operator (the same false '—' the hook fix removed)."""
    from kaizen_shrink_audit import assign_verdicts, audit

    src = _mk_sources_tree(tmp_path)
    (src.repo / "scripts" / "fabrik_synced_manifest.py").write_text('CORE_SCRIPTS = ["mail.py"]\n')
    fabrik_dir = src.repo / ".fabrik"
    fabrik_dir.mkdir(exist_ok=True)
    (fabrik_dir / "liveness-registry.json").write_text(
        json.dumps({"surfaces": [{"id": "fabrik-mail-digest", "cron_match": "mail.py digest"}]})
    )
    src.liveness_json.write_text(
        json.dumps(
            {"proofs": {"h": {"findings": [{"id": "fabrik-mail-digest", "verdict": "DEAD"}]}}}
        )
    )
    rows = assign_verdicts(audit(src)[0])
    cs = next(r for r in rows if r["cls"] == "core-script")
    assert cs["liveness"] == "DEAD", "the declared surface's verdict must reach the row"


def test_sidechain_user_rows_are_not_typed_invocations(tmp_path: Path):
    """Verification round: a dispatched subagent's BRIEF is a type:user row with string
    content — quoting a literal marker in a brief must not count as an operator
    keystroke (the observer-effect door re-opened by the rglob fix)."""
    proj = tmp_path / "projects" / "-opt-probe"
    sub = proj / "session" / "subagents"
    _write_transcript(
        sub,
        "agent-x.jsonl",
        [
            {
                "type": "user",
                "isSidechain": True,
                "message": {
                    "content": "review the row <command-name>/fabrik-briefed</command-name>"
                },
            }
        ],
    )
    _write_transcript(
        proj,
        "main.jsonl",
        [{"type": "user", "message": {"content": "<command-name>/fabrik-genuine</command-name>"}}],
    )
    sig = collect_invocations(tmp_path / "projects")
    assert sig.data.get("fabrik-genuine", {}).get("typed") == 1
    assert "fabrik-briefed" not in sig.data, "a subagent brief is not an operator keystroke"


def test_unreadable_crontab_earns_exactly_one_note(tmp_path: Path):
    """Verification round: an unreadable crontab produced TWO contradictory census
    notes — the precise cause diluted by a generic second line."""
    import kaizen_shrink_audit as ksa

    src = _mk_sources_tree(tmp_path)
    src.crontab_text = None  # force the crontab -l path
    orig = ksa.subprocess.run

    def _fail(cmd, **kw):
        if cmd[:1] == ["crontab"]:
            raise OSError("no crontab binary")
        return orig(cmd, **kw)

    ksa.subprocess.run, run_backup = _fail, ksa.subprocess.run
    try:
        _, notes = enumerate_artifacts(src)
    finally:
        ksa.subprocess.run = run_backup
    assert len([n for n in notes if "cron" in n.split(" ")[0] or "crontab" in n]) == 1, notes


def test_append_note_dedupes_whole_segments_not_substrings():
    """Verification round: the idempotency guard was a substring test — a distinct
    shorter note swallowed by a longer existing one loses operator evidence. Round-3:
    a note CONTAINING '; ' must also dedupe (split-on-separator cannot tell)."""
    from kaizen_shrink_audit import _append_note

    row = {"evidence_note": "all class signals unmeasurable — routed to unknown, never candidate"}
    _append_note(row, "all class signals unmeasurable")
    assert row["evidence_note"].endswith("; all class signals unmeasurable"), row["evidence_note"]
    semi = {"evidence_note": ""}
    _append_note(semi, "keep — immune: gate machinery; usage-evidence cannot prove it useless")
    _append_note(semi, "keep — immune: gate machinery; usage-evidence cannot prove it useless")
    assert semi["evidence_note"].count("keep — immune:") == 1, semi["evidence_note"]


def test_missing_class_note_survives_a_path_containing_a_class_name(tmp_path: Path):
    """Round-3: the missing-class guard was a substring test over notes embedding repo
    PATHS — a repo at .../my-hooks-repo/ suppressed the hook class's note, silently
    dropping the class again."""
    repo = tmp_path / "my-hooks-repo" / "commands-lab"
    (repo / "src" / "fabrik").mkdir(parents=True)
    (repo / "src" / "fabrik" / "scaffold.py").write_text("SCAFFOLD_TYPES = 3\n")  # unreadable shape
    src = Sources(
        repo=repo,
        transcripts=tmp_path / "t",
        reviews_root=tmp_path / "opt",
        run_records=tmp_path / "rr",
        crontab_text="",
    )
    _, notes = enumerate_artifacts(src)
    assert any(n.startswith("hook registry") for n in notes), notes
    assert any(n.startswith("command registry") for n in notes), notes


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
        "command",
        "fragment",
        "rule-pack",
        "gate-check",
        "hook",
        "scaffold-type",
        "core-script",
        "cron",
    }


def test_a_blank_needle_never_kills_the_surface_census(tmp_path: Path):
    """`match.split()[0]` on `" "` raised IndexError out of the unguarded census — the FE3 needle rule
    lived in liveness_audit only; this is the OTHER reader (G66-C4, FF1)."""
    (tmp_path / ".fabrik").mkdir()
    (tmp_path / ".fabrik" / "liveness-registry.json").write_text(
        json.dumps(
            {
                "surfaces": [
                    {"id": "blank", "cron_match": " "},
                    {
                        "id": "null-then-hook",
                        "cron_match": None,
                        "evidence": {"command_contains": "  hook.sh  "},
                    },
                    {"id": "str-ev", "cron_match": "", "evidence": "not-a-mapping"},
                    {"id": "good", "cron_match": "/opt/fabrik/x/good.py --flag"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _registry_surface_map(tmp_path) == {"hook.sh": ["null-then-hook"], "good.py": ["good"]}


def test_a_malformed_registry_container_never_kills_the_census(tmp_path: Path):
    """The needle guard left the CONTAINER unguarded: a list top level, a string element, a dict
    `surfaces` raised AttributeError out of audit() (R67-5, FG1)."""
    reg = tmp_path / ".fabrik" / "liveness-registry.json"
    reg.parent.mkdir()
    for shape in (
        '["not", "a", "mapping"]',
        '"text"',
        '{"surfaces": "text"}',
        '{"surfaces": {"a": 1}}',
    ):
        reg.write_text(shape, encoding="utf-8")
        assert _registry_surface_map(tmp_path) == {}, shape
    reg.write_text(
        json.dumps({"surfaces": ["str", None, {"id": "ok", "cron_match": "x.sh"}]}),
        encoding="utf-8",
    )
    assert _registry_surface_map(tmp_path) == {"x.sh": ["ok"]}
