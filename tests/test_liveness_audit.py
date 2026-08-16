"""Contract tests for the liveness layer.

THE HEADLINE is `test_a_probe_whose_instrument_fails_reports_unknown_never_dead`. Everything
else in this file is subordinate to it. On 2026-08-16 three orchestrator probes reported
ABSENCE OF EVIDENCE as EVIDENCE OF ABSENCE — a binary-classified log, a single directory
generalised to "does not exist", and an empty stdout from a permission-denied docker call —
and all three reached the operator as fact. The three-state rule is the fix, and a test that
does not fail when the rule is removed is not testing it.

Watched-fail-first: the headline test was proven RED by neutering `finding()` to a plain
constructor (see docs/workstation/liveness.md § Watched fail).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "sysadmin"))

import liveness_audit as la  # noqa: E402, I001 - path insert must precede the import


# ── THE THREE-STATE CONTRACT ─────────────────────────────────────────────────────


def test_a_probe_whose_instrument_fails_reports_unknown_never_dead() -> None:
    """A probe that cannot prove its instrument may not report DEAD. THE headline.

    `grep -c arg=sweep` printed nothing because GNU grep called the file binary; the
    conclusion drawn was "the reboot sweep has NEVER run". The instrument had failed, so
    the only honest verdict was UNKNOWN with the fault named.
    """
    broken = la.Instrument.broken("grep", "the file was classified as binary")
    f = la.finding(
        proof="heartbeat",
        id="reboot-sweep",
        kind="cron",
        instrument=broken,
        verdict=la.Verdict.DEAD,
        detail="no evidence found",
        reason_class="absent",
    )
    assert f.verdict is la.Verdict.UNKNOWN, (
        "a DEAD verdict survived a failed instrument — this is exactly the rumour-mill bug"
    )
    assert f.instrument_fault == "the file was classified as binary"
    assert f.reason_class == "", "an UNKNOWN must not carry a DEAD reason class"


def test_a_failed_instrument_also_cannot_prove_liveness() -> None:
    """The rule is symmetric: a broken instrument proves nothing in either direction."""
    f = la.finding(
        proof="heartbeat", id="x", kind="cron",
        instrument=la.Instrument.broken("ss", "ss is not on PATH"),
        verdict=la.Verdict.LIVE, detail="port looked open",
    )
    assert f.verdict is la.Verdict.UNKNOWN


def test_a_proven_instrument_passes_the_verdict_through() -> None:
    f = la.finding(
        proof="heartbeat", id="x", kind="cron", instrument=la.Instrument.proven("crontab -l"),
        verdict=la.Verdict.DEAD, detail="no line matches", reason_class="unscheduled",
    )
    assert f.verdict is la.Verdict.DEAD
    assert f.reason_class == "unscheduled"
    assert f.instrument_fault == ""


def test_the_verdict_space_has_exactly_three_states() -> None:
    assert {v.value for v in la.Verdict} == {"LIVE", "DEAD", "UNKNOWN"}


# ── Instrument controls ──────────────────────────────────────────────────────────


def test_binary_evidence_is_read_where_a_strict_decoder_would_fail(tmp_path: Path) -> None:
    """The 2026-08-16 failure class: one invalid UTF-8 byte hides every later match.

    A strict reader RAISES on this fixture — the portable, deterministic stand-in for GNU
    grep's binary suppression on the real 1.9 MB log. The audit must still find and DATE
    the marker that sits AFTER the bad byte.
    """
    log = tmp_path / "sound-debug.log"
    log.write_bytes(
        b"2026-07-30 23:42:00  note=a round-3 verdict \xe2\x80\n"
        b"2026-08-16 07:32:34  arg=sweep  event=boot\n"
    )
    with pytest.raises(UnicodeDecodeError):
        log.read_text(encoding="utf-8")

    box = la.Box(home=tmp_path)
    inst, age, hits = box.marker_age(str(log), "arg=sweep")
    assert inst.ok, inst.fault
    assert hits == 1
    assert age is not None and age >= 0


def test_the_audit_agrees_with_grep_a_on_the_real_sound_log() -> None:
    """The live incident, pinned against ground truth (`grep -a`, the binary-safe form).

    On 2026-08-16 plain `grep -c arg=sweep` on this file printed NOTHING and exited 1, and
    that silence was reported as "the reboot sweep has NEVER run"; `grep -a` showed 21.
    Measured again minutes later, after the Stop hook appended more lines, plain grep
    answered 21 — the suppression is INTERMITTENT, which is worse than a stable bug and is
    precisely why the audit does not shell out to grep at all. So this test pins the audit
    to the binary-safe count, which is right in both regimes. Skipped where the log is
    absent (CI).
    """
    log = Path.home() / ".claude" / "sound-debug.log"
    if not log.is_file():
        pytest.skip("no Stop-hook sound log on this machine")
    truth = subprocess.run(
        ["grep", "-a", "-c", "arg=sweep", str(log)], capture_output=True, text=True
    )
    inst, age, hits = la.Box().marker_age(str(log), "arg=sweep")
    assert inst.ok, inst.fault
    assert hits == int(truth.stdout.strip() or 0), (
        f"the audit found {hits} sweep events; grep -a found {truth.stdout.strip()}"
    )
    assert age is not None


def test_the_log_instrument_control_is_itself_a_binary_round_trip() -> None:
    """The positive control must prove the reader survives an invalid byte, not just stat."""
    assert b"\xff" in la._CONTROL_BYTES
    assert la._CONTROL_BYTES.index(b"\xff") < la._CONTROL_BYTES.index(b"marker=positive-control")
    assert la.Box().log_instrument().ok


def test_missing_evidence_under_an_unreadable_parent_is_unknown(tmp_path: Path) -> None:
    """We only get to call a file absent when we can prove we looked somewhere real."""
    box = la.Box(home=tmp_path)
    inst, age = box.evidence_age(str(tmp_path / "nope" / "job.log"), volatile=False)
    assert not inst.ok and "does not exist" in inst.fault
    assert age is None


def test_missing_evidence_in_a_volatile_directory_is_unknown_not_dead(tmp_path: Path) -> None:
    """/tmp is cleared on boot; silence there proves nothing about whether the job ran."""
    box = la.Box(home=tmp_path)
    inst, _ = box.evidence_age(str(tmp_path / "gone.log"), volatile=True)
    assert not inst.ok and "volatile" in inst.fault


def test_missing_evidence_in_a_readable_directory_is_a_provable_absence(tmp_path: Path) -> None:
    box = la.Box(home=tmp_path)
    inst, age = box.evidence_age(str(tmp_path / "never-written.log"), volatile=False)
    assert inst.ok, inst.fault
    assert age is None  # provable absence, and the caller may call it DEAD


def test_an_empty_crontab_read_is_an_instrument_fault_not_an_empty_box(monkeypatch) -> None:
    """Calling every cron DEAD off a blank page is failure 2 in another costume."""
    monkeypatch.setattr(la.shutil, "which", lambda _: "/usr/bin/crontab")
    monkeypatch.setattr(
        la, "_run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "# just a comment\n", "")
    )
    inst, lines = la.Box().crontab()
    assert not inst.ok and "no parseable cron entries" in inst.fault
    assert lines == []


# ── PROOF 1: heartbeat ───────────────────────────────────────────────────────────


def _registry(tmp_path: Path, surfaces: list[dict], owned: list[str] | None = None) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "ownership": {"cron_owned_substrings": owned or ["/opt/fabrik"]},
                "surfaces": surfaces,
            }
        ),
        encoding="utf-8",
    )
    return path


class FakeBox(la.Box):
    """A Box whose box-level reads are supplied, so probes are testable off-machine."""

    def __init__(self, tmp_path: Path, cron: list[str] | None = None, hooks: list[str] | None = None):
        super().__init__(home=tmp_path)
        self._cron = cron
        self._hooks = hooks if hooks is not None else ["/x/claude-sound.sh done"]

    def crontab(self):  # type: ignore[override]
        if self._cron is None:
            return la.Instrument.broken("crontab -l", "crontab is unreadable"), []
        return la.Instrument.proven("crontab -l"), self._cron

    def hooks(self):  # type: ignore[override]
        return la.Instrument.proven("claude settings hooks"), self._hooks


def test_a_stale_log_is_overdue_and_a_fresh_one_is_live(tmp_path: Path) -> None:
    import os
    import time

    fresh, stale = tmp_path / "fresh.log", tmp_path / "stale.log"
    fresh.write_text("ran\n")
    stale.write_text("ran once\n")
    os.utime(stale, (time.time() - 40 * 3600, time.time() - 40 * 3600))

    surfaces = [
        {"id": "fresh", "kind": "cron", "cron_match": "job_a",
         "evidence": {"type": "log", "path": str(fresh)}, "max_age_hours": 24},
        {"id": "stale", "kind": "cron", "cron_match": "job_b",
         "evidence": {"type": "log", "path": str(stale)}, "max_age_hours": 24},
    ]
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/job_a", "0 * * * * /opt/fabrik/job_b"])
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    by_id = {f["id"]: f for f in out["findings"]}
    assert by_id["fresh"]["verdict"] == "LIVE"
    assert by_id["stale"]["verdict"] == "DEAD"
    assert by_id["stale"]["reason_class"] == "overdue"


def test_a_surface_with_no_crontab_line_is_dead_even_with_a_fresh_log(tmp_path: Path) -> None:
    """The DR-backup class: the schedule is gone, so the fresh log is a hand-run."""
    log = tmp_path / "hand-run.log"
    log.write_text("ran by hand\n")
    surfaces = [{"id": "dr", "kind": "cron", "cron_match": "dr_backup.sh",
                 "evidence": {"type": "log", "path": str(log)}, "max_age_hours": 24}]
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/something_else.sh"])
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    assert out["findings"][0]["verdict"] == "DEAD"
    assert out["findings"][0]["reason_class"] == "unscheduled"


def test_an_unreadable_crontab_makes_every_cron_surface_unknown(tmp_path: Path) -> None:
    surfaces = [{"id": "dr", "kind": "cron", "cron_match": "dr_backup.sh",
                 "evidence": {"type": "log", "path": str(tmp_path / "x.log")}, "max_age_hours": 24}]
    box = FakeBox(tmp_path, cron=None)
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    assert out["findings"][0]["verdict"] == "UNKNOWN"
    assert "unreadable" in out["findings"][0]["instrument_fault"]


def test_a_surface_with_no_evidence_channel_is_unknown_not_live(tmp_path: Path) -> None:
    """Scheduled but unobservable is unfalsifiable — which is not the same as healthy."""
    surfaces = [{"id": "opaque", "kind": "cron", "cron_match": "job", "evidence": {"type": "none"}}]
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/job"])
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    assert out["findings"][0]["verdict"] == "UNKNOWN"


def test_the_box_to_registry_diff_reports_unregistered_surfaces(tmp_path: Path) -> None:
    """Unregistered = unmonitored. A registry that misses surfaces is its own blind spot."""
    surfaces = [{"id": "known", "kind": "cron", "cron_match": "known_job.sh",
                 "evidence": {"type": "none"}}]
    box = FakeBox(
        tmp_path,
        cron=[
            "0 * * * * /opt/fabrik/known_job.sh",
            "0 2 * * * /opt/fabrik/nobody_watches_this.sh",
            "0 3 * * * /opt/other-repo/foreign.sh",
        ],
        hooks=["/x/claude-sound.sh done", "/x/undeclared_hook.py"],
    )
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    cron = la.proof_heartbeat(box, reg, "")["unregistered"]["cron"]
    assert cron["foreign_count"] == 1
    assert any("nobody_watches_this.sh" in line for line in cron["owned"])
    assert not any("known_job.sh" in line for line in cron["owned"])


def test_an_empty_registry_is_itself_a_finding(tmp_path: Path) -> None:
    out = la.proof_heartbeat(FakeBox(tmp_path), {}, "no registry at /nowhere")
    assert out["findings"][0]["verdict"] == "UNKNOWN"
    assert "no registry" in out["findings"][0]["instrument_fault"]


def test_the_shipped_registry_parses_and_declares_surfaces() -> None:
    registry, fault = la.load_registry(REPO_ROOT / la.DEFAULT_REGISTRY)
    assert fault == "", fault
    ids = [s["id"] for s in registry["surfaces"]]
    assert len(ids) == len(set(ids)), "duplicate surface id in the registry"
    for surface in registry["surfaces"]:
        assert surface.get("kind") in {"cron", "hook", "service", "port"}
        assert (surface.get("evidence") or {}).get("type") in {
            "log", "log_marker", "port", "unit", "hook", "none",
        }


# ── PROOF 2: vacuity ─────────────────────────────────────────────────────────────


def test_a_vacuous_check_is_caught_by_its_canary(tmp_path: Path) -> None:
    """The 2026-08-16 bug in miniature: exit 0 on a known-bad fixture = asserts nothing."""
    enforcement = tmp_path / "scripts" / "enforcement"
    enforcement.mkdir(parents=True)
    (enforcement / "check_vacuous.py").write_text(
        "import sys\n"
        "def check_file(p):\n    return []\n"
        "print('PASS: check_vacuous')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    canary = {"form": "root", "files": {"compose.yaml": "bad\n"}, "expect": "anything at all"}
    inst, went_red = la.run_canary("check_vacuous", canary, tmp_path)
    assert inst.ok, inst.fault
    assert went_red is False, "a check that exits 0 on its canary must not read as healthy"


def test_a_real_check_goes_red_on_its_canary(tmp_path: Path) -> None:
    enforcement = tmp_path / "scripts" / "enforcement"
    enforcement.mkdir(parents=True)
    (enforcement / "check_real.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "root = Path(sys.argv[sys.argv.index('--root') + 1])\n"
        "bad = [p for p in root.rglob('*.yaml') if 'arm64' in p.read_text()]\n"
        "print('FAIL' if bad else 'PASS')\n"
        "sys.exit(1 if bad else 0)\n",
        encoding="utf-8",
    )
    canary = {"form": "root", "files": {"compose.yaml": "platform: linux/arm64\n"}, "expect": "arm64"}
    inst, went_red = la.run_canary("check_real", canary, tmp_path)
    assert inst.ok and went_red is True


def test_a_check_that_cannot_be_invoked_is_unknown_not_inert(tmp_path: Path) -> None:
    """We must never call a check inert when we have measured our own harness."""
    enforcement = tmp_path / "scripts" / "enforcement"
    enforcement.mkdir(parents=True)
    (enforcement / "check_crashy.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    inst, went_red = la.run_canary(
        "check_crashy", {"form": "root", "files": {}, "expect": "x"}, tmp_path
    )
    assert not inst.ok and "crashed on a clean tree" in inst.fault
    assert went_red is False


def test_a_check_without_a_canary_is_unproven_not_green(tmp_path: Path) -> None:
    gate = tmp_path / "scripts"
    gate.mkdir(parents=True)
    (gate / "final_gate.py").write_text(
        "\n".join(
            f'run_optional_check("scripts/enforcement/check_x{i}.py", "X{i}")' for i in range(8)
        ),
        encoding="utf-8",
    )
    out = la.proof_vacuity(tmp_path)
    assert out["registered"] == 8
    assert all(f["verdict"] == "UNKNOWN" for f in out["findings"]), (
        "no check may read as green here: 8 have no canary, and the shipped canaries have "
        "no scripts to run against in this fixture tree"
    )
    uncanaried = [f for f in out["findings"] if f["id"].startswith("check_x")]
    assert len(uncanaried) == 8
    assert all("no canary authored" in f["instrument_fault"] for f in uncanaried)


def test_a_broken_gate_parse_never_declares_anything_inert(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "final_gate.py").write_text("# nothing registered here\n")
    inst, names = la.discover_registered_checks(tmp_path / "scripts" / "final_gate.py")
    assert not inst.ok and "registered check" in inst.fault
    assert names == []


def test_every_shipped_canary_names_a_real_check_script() -> None:
    for name in la.CANARIES:
        assert (REPO_ROOT / "scripts" / "enforcement" / f"{name}.py").is_file(), name


# ── PROOF 3: doc claims ──────────────────────────────────────────────────────────


def test_a_stale_cron_claim_is_detected_and_a_true_one_passes(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text(
        "```cron\n"
        "0 6 * * 1 /opt/fabrik/real.sh\n"
        "0 2 * * 0 /opt/fabrik/imaginary.sh\n"
        "```\n",
        encoding="utf-8",
    )
    claims = la.extract_claims(doc, "d.md")
    assert len(claims) == 2
    box = FakeBox(tmp_path)
    inst, lines = la.Instrument.proven("crontab -l"), ["0 6 * * 1 /opt/fabrik/real.sh"]
    verdicts = [la.verify_claim(box, c, inst, lines).verdict for c in claims]
    assert verdicts == [la.Verdict.LIVE, la.Verdict.DEAD]


def test_a_proposed_cron_block_is_not_a_claim_about_the_live_box(tmp_path: Path) -> None:
    """Docs show lines to INSTALL. Reporting those as stale trains the reader to ignore this
    proof — and liveness.md itself prints exactly such a block."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "### Proposed cron (NOT installed)\n\n"
        "```cron\n40 6 * * 1 /opt/fabrik/not-yet.sh\n```\n\n"
        "## Cron — the installed lines\n\n"
        "```cron\n0 6 * * 1 /opt/fabrik/real.sh\n```\n",
        encoding="utf-8",
    )
    payloads = [c.payload for c in la.extract_claims(doc, "d.md") if c.ctype == "cron_line"]
    assert payloads == ["0 6 * * 1 /opt/fabrik/real.sh"]


def test_schedule_drift_is_reported_distinctly_from_a_missing_line(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text("```cron\n0 2 * * 0 /opt/fabrik/job.sh\n```\n", encoding="utf-8")
    claim = la.extract_claims(doc, "d.md")[0]
    f = la.verify_claim(
        FakeBox(tmp_path), claim, la.Instrument.proven("crontab -l"), ["0 6 * * 1 /opt/fabrik/job.sh"]
    )
    assert f.verdict is la.Verdict.DEAD and "schedule drift" in f.detail


def test_a_prose_word_is_not_mistaken_for_a_scheduled_job(tmp_path: Path) -> None:
    """"the weekly cron line (Sun 02:00, ...)" once produced a job named "line"."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "- the weekly cron line (Sun 02:00, plaintext KEY) was removed\n"
        "- calendar-orchestration (Sun 02:00) still runs\n",
        encoding="utf-8",
    )
    tokens = {c.payload for c in la.extract_claims(doc, "d.md") if c.ctype == "scheduled_name"}
    assert tokens == {"calendar-orchestration"}


def test_a_doc_that_names_several_states_is_true_if_the_box_reports_any_of_them(tmp_path: Path) -> None:
    """A unit documented as `enabled` but ending `failed` on purpose is NOT a stale doc."""
    doc = tmp_path / "d.md"
    doc.write_text("`x.service` is also `enabled` and ends `failed` on the port race\n", encoding="utf-8")
    claim = next(c for c in la.extract_claims(doc, "d.md") if c.ctype == "unit")
    assert "enabled" in claim.extra and "failed" in claim.extra

    class UnitBox(FakeBox):
        def unit_state(self, unit):  # type: ignore[override]
            return la.Instrument.proven("systemctl"), ("enabled", "failed")

    f = la.verify_claim(UnitBox(tmp_path), claim, la.Instrument.proven("crontab -l"), [])
    assert f.verdict is la.Verdict.LIVE


def test_a_unit_the_box_cannot_resolve_is_unknown(tmp_path: Path) -> None:
    doc = tmp_path / "d.md"
    doc.write_text("`ghost.service` runs at boot\n", encoding="utf-8")
    claim = next(c for c in la.extract_claims(doc, "d.md") if c.ctype == "unit")

    class NoSystemd(FakeBox):
        def unit_state(self, unit):  # type: ignore[override]
            return la.Instrument.broken("systemctl", "the user bus is unreachable"), None

    f = la.verify_claim(NoSystemd(tmp_path), claim, la.Instrument.proven("crontab -l"), [])
    assert f.verdict is la.Verdict.UNKNOWN


def test_only_loopback_ports_become_claims(tmp_path: Path) -> None:
    """A VPS port in prose is not a claim about THIS box; only localhost:NNNN is."""
    doc = tmp_path / "d.md"
    doc.write_text("Serves <http://localhost:5051/> and the VPS runs on port 8443\n", encoding="utf-8")
    ports = {c.payload for c in la.extract_claims(doc, "d.md") if c.ctype == "port"}
    assert ports == {"5051"}


def test_every_workstation_doc_is_enumerated() -> None:
    """A truncated listing already produced a false n=12 where the real count is 19."""
    docs_dir = REPO_ROOT / "docs" / "workstation"
    out = la.proof_doc_claims(la.Box(), docs_dir)
    assert out["docs"] == len(list(docs_dir.glob("*.md")))
    assert set(out["doc_names"]) == {p.name for p in docs_dir.glob("*.md")}


# ── The audit as a whole ─────────────────────────────────────────────────────────


def test_the_audit_never_raises_when_a_proof_explodes(tmp_path: Path, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("the proof itself died")

    monkeypatch.setattr(la, "proof_vacuity", boom)
    report = la.audit(tmp_path, tmp_path / "missing.json", {"vacuity"})
    crashed = report.proofs["vacuity"]["findings"][0]
    # A proof that died proved nothing, so by the three-state rule it may not say DEAD...
    assert crashed["verdict"] == "UNKNOWN"
    assert "RuntimeError" in crashed["instrument_fault"]
    # ...but --strict must still bite, or a silently skipped proof reads as all-clear.
    assert report.crashed() == 1


def test_the_report_is_json_serialisable_and_carries_the_proposed_cron(tmp_path: Path) -> None:
    report = la.audit(tmp_path, tmp_path / "missing.json", {"heartbeat"})
    blob = json.loads(json.dumps(report.as_dict()))
    assert blob["proposed_cron"].startswith("40 6 * * 1")
    assert set(blob["summary"]) == {"LIVE", "DEAD", "UNKNOWN"}
    assert la.render(report)


@pytest.mark.parametrize("proof", ["heartbeat", "doc_claim"])
def test_the_cli_exits_zero_by_default_on_the_real_box(proof: str) -> None:
    """A monitoring layer that blocks work gets disabled, and then it monitors nothing."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sysadmin" / "liveness_audit.py"),
         "--proof", proof, "--json"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=600,
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert json.loads(result.stdout)["summary"]["LIVE"] >= 1


def test_strict_is_opt_in_and_fails_only_on_dead(tmp_path: Path) -> None:
    surfaces = [{"id": "dead-one", "kind": "cron", "cron_match": "gone.sh",
                 "evidence": {"type": "none"}}]
    registry = _registry(tmp_path, surfaces)
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/other.sh"])
    report = la.audit(tmp_path, registry, {"heartbeat"}, box=box)
    assert report.failures() == 1

    unknown_only = la.audit(tmp_path, _registry(tmp_path, [
        {"id": "opaque", "kind": "cron", "cron_match": "other.sh", "evidence": {"type": "none"}}
    ]), {"heartbeat"}, box=box)
    assert unknown_only.failures() == 0, "UNKNOWN must never fail --strict; only DEAD does"
