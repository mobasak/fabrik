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
import os
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
        proof="heartbeat",
        id="x",
        kind="cron",
        instrument=la.Instrument.broken("ss", "ss is not on PATH"),
        verdict=la.Verdict.LIVE,
        detail="port looked open",
    )
    assert f.verdict is la.Verdict.UNKNOWN


def test_a_proven_instrument_passes_the_verdict_through() -> None:
    f = la.finding(
        proof="heartbeat",
        id="x",
        kind="cron",
        instrument=la.Instrument.proven("crontab -l"),
        verdict=la.Verdict.DEAD,
        detail="no line matches",
        reason_class="unscheduled",
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

    def __init__(
        self, tmp_path: Path, cron: list[str] | None = None, hooks: list[str] | None = None
    ):
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
        {
            "id": "fresh",
            "kind": "cron",
            "cron_match": "job_a",
            "evidence": {"type": "log", "path": str(fresh)},
            "max_age_hours": 24,
        },
        {
            "id": "stale",
            "kind": "cron",
            "cron_match": "job_b",
            "evidence": {"type": "log", "path": str(stale)},
            "max_age_hours": 24,
        },
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
    surfaces = [
        {
            "id": "dr",
            "kind": "cron",
            "cron_match": "dr_backup.sh",
            "evidence": {"type": "log", "path": str(log)},
            "max_age_hours": 24,
        }
    ]
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/something_else.sh"])
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    assert out["findings"][0]["verdict"] == "DEAD"
    assert out["findings"][0]["reason_class"] == "unscheduled"


def test_an_unreadable_crontab_makes_every_cron_surface_unknown(tmp_path: Path) -> None:
    surfaces = [
        {
            "id": "dr",
            "kind": "cron",
            "cron_match": "dr_backup.sh",
            "evidence": {"type": "log", "path": str(tmp_path / "x.log")},
            "max_age_hours": 24,
        }
    ]
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
    surfaces = [
        {"id": "known", "kind": "cron", "cron_match": "known_job.sh", "evidence": {"type": "none"}}
    ]
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
            "log",
            "log_marker",
            "port",
            "unit",
            "hook",
            "none",
        }


# ── review fix-wave: adjudicated findings, red-first (H5) ────────────────────────


def test_kaizen_surfaces_use_success_stamps_and_the_coroner_is_registered() -> None:
    """H5: the kaizen heartbeats' evidence is each job's SUCCESS STAMP (touched only
    on job success) — ~/.claude/kaizen.log is also written by the retirement nudge,
    so the log satisfied the heartbeat without the job ever succeeding. The coroner
    joins as its own daily surface: nothing on the box ran it."""
    registry, fault = la.load_registry(REPO_ROOT / la.DEFAULT_REGISTRY)
    assert fault == "", fault
    by_id = {s["id"]: s for s in registry["surfaces"]}

    meas = by_id["kaizen-measurement"]
    assert meas["evidence"]["path"] == "~/.claude/state/daily-kaizen_collect_v2.py.stamp"
    assert "crontab" in meas["why"], "the why must name the pending crontab install"

    sweep = by_id["kaizen-sweep"]
    assert sweep["evidence"]["path"] == "~/.claude/state/daily-kaizen_outcomes.py.stamp"
    assert "crontab" in sweep["why"], "the why must name the pending crontab install"

    coroner = by_id.get("kaizen-coroner")
    assert coroner is not None, "the coroner must be a registered surface (H5)"
    assert coroner["kind"] == "cron"
    assert coroner["cron_match"] == "kaizen_coroner.py"
    assert coroner["evidence"]["type"] == "log"
    assert coroner["evidence"]["path"] == "~/.claude/state/daily-kaizen_coroner.py.stamp"
    assert coroner["max_age_hours"] == 54


def test_weekly_catchup_runs_the_coroner_daily(tmp_path: Path) -> None:
    """H5: kaizen_coroner.py is a daily job key in weekly_catchup.sh — sweep runs,
    stamp touched on success, fresh stamp is a quiet no-op."""
    for sub in ("locks", "events", "runs"):
        (tmp_path / sub).mkdir()
    env = dict(
        os.environ,
        HOME=str(tmp_path),
        FABRIK_ROOT=str(REPO_ROOT),
        FABRIK_PY="/opt/fabrik/.venv/bin/python",
        CLAUDE_SOUND_LOCKDIR=str(tmp_path / "locks"),
        KAIZEN_EVENTS_DIR=str(tmp_path / "events"),
        COMMAND_RUN_DIR=str(tmp_path / "runs"),
    )
    script = REPO_ROOT / "scripts" / "sysadmin" / "weekly_catchup.sh"
    argv = ["bash", str(script), "kaizen_coroner.py"]
    first = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
    assert first.returncode == 0, first.stdout + first.stderr
    stamp = tmp_path / ".claude" / "state" / "daily-kaizen_coroner.py.stamp"
    assert stamp.is_file(), "the success stamp must be touched on a green run"
    second = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)
    assert second.returncode == 0
    assert second.stdout.strip() == "", "a fresh stamp is a QUIET no-op (heartbeat law)"


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
    inst, went_red, reported = la.run_canary("check_vacuous", canary, tmp_path)
    assert inst.ok, inst.fault
    assert went_red is False, "a check that exits 0 on its canary must not read as healthy"
    assert reported is False, (
        "this check prints the SAME line on both trees — it detected nothing, and a "
        "`reported` of True here would let a silent advisory read as LIVE"
    )


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
    canary = {
        "form": "root",
        "files": {"compose.yaml": "platform: linux/arm64\n"},
        "expect": "arm64",
    }
    inst, went_red, reported = la.run_canary("check_real", canary, tmp_path)
    assert inst.ok and went_red is True
    assert reported is True, "it printed FAIL on the bad tree and PASS on the clean one"


def test_a_check_that_cannot_be_invoked_is_unknown_not_inert(tmp_path: Path) -> None:
    """We must never call a check inert when we have measured our own harness."""
    enforcement = tmp_path / "scripts" / "enforcement"
    enforcement.mkdir(parents=True)
    (enforcement / "check_crashy.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    inst, went_red, reported = la.run_canary(
        "check_crashy", {"form": "root", "files": {}, "expect": "x"}, tmp_path
    )
    assert not inst.ok and "crashed on a clean tree" in inst.fault
    assert went_red is False and reported is False


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


def _gate_with(tmp_path: Path, extra: str) -> Path:
    """A final_gate.py fixture with enough registrations to clear the parse-guard floor."""
    gate_dir = tmp_path / "scripts"
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate = gate_dir / "final_gate.py"
    filler = "\n".join(
        f'run_optional_check("scripts/enforcement/check_filler{i}.py", "F{i}")' for i in range(6)
    )
    gate.write_text(f"{filler}\n{extra}\n", encoding="utf-8")
    return gate


def _speaker(tmp_path: Path, name: str) -> None:
    """A check that REPORTS a violation and always exits 0 — the warn-only shape."""
    enforcement = tmp_path / "scripts" / "enforcement"
    enforcement.mkdir(parents=True, exist_ok=True)
    (enforcement / f"{name}.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "bad = [p for p in Path.cwd().rglob('*.yaml') if 'arm64' in p.read_text()]\n"
        "print(f'WARNING: {len(bad)} violation(s)' if bad else 'OK')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )


_SPEAKER_CANARY = {
    "form": "cwd",
    "warn_only": "always exits 0",
    "files": {"compose.yaml": "platform: linux/arm64\n"},
    "expect": "an arm64 platform pin",
}


def test_warn_only_registrations_are_read_off_the_gate(tmp_path: Path) -> None:
    gate = _gate_with(
        tmp_path,
        'run_optional_check("scripts/enforcement/check_quiet.py", "Q", warn_only=True)\n'
        'run_optional_check("scripts/enforcement/check_loud.py", "L", advisory=True)\n'
        'run_optional_check("scripts/enforcement/check_off.py", "O", warn_only=False)',
    )
    declared = la.discover_warn_only_checks(gate)
    assert declared == {"check_quiet"}, (
        "advisory= only preserves stdout — several checks carrying it DO fail the gate — "
        "so it must never be read as a non-blocking declaration"
    )


def test_an_unparseable_gate_declares_no_row_advisory(tmp_path: Path) -> None:
    """Fail in the STRICT direction: unknown means blocking, never excused."""
    gate = tmp_path / "final_gate.py"
    gate.write_text("run_optional_check( this is not python\n", encoding="utf-8")
    assert la.discover_warn_only_checks(gate) == set()


def test_a_declared_advisory_row_that_speaks_is_live_not_inert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit must not punish the fix.

    Once a warn-only check is honestly registered `warn_only=True`, the gate labels its
    row [ADVISORY] and the operator can see it can never red. Reporting it INERT anyway
    would make the truthful registration indistinguishable from the defect it replaced.
    """
    _speaker(tmp_path, "check_quiet")
    _gate_with(
        tmp_path,
        'run_optional_check("scripts/enforcement/check_quiet.py", "Q", warn_only=True)',
    )
    monkeypatch.setattr(la, "CANARIES", {"check_quiet": _SPEAKER_CANARY})
    monkeypatch.setattr(la, "UNREACHABLE", {})
    found = next(f for f in la.proof_vacuity(tmp_path)["findings"] if f["id"] == "check_quiet")
    assert found["verdict"] == "LIVE", found
    assert found["kind"] == "check(advisory)"
    assert "REPORTED" in found["detail"]


def test_the_same_check_registered_as_a_blocking_row_is_still_inert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The teeth, kept: identical check, no declaration — the vacuous-green defect."""
    _speaker(tmp_path, "check_quiet")
    _gate_with(tmp_path, 'run_optional_check("scripts/enforcement/check_quiet.py", "Q")')
    monkeypatch.setattr(la, "CANARIES", {"check_quiet": _SPEAKER_CANARY})
    monkeypatch.setattr(la, "UNREACHABLE", {})
    found = next(f for f in la.proof_vacuity(tmp_path)["findings"] if f["id"] == "check_quiet")
    assert found["verdict"] == "DEAD" and found["reason_class"] == "inert", found
    assert "can never go red" in found["detail"]


def test_a_declared_advisory_row_that_says_nothing_is_dead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advisory is not a free pass: the output IS the product, so silence is death."""
    enforcement = tmp_path / "scripts" / "enforcement"
    enforcement.mkdir(parents=True, exist_ok=True)
    (enforcement / "check_mute.py").write_text("print('OK')\n", encoding="utf-8")
    _gate_with(
        tmp_path,
        'run_optional_check("scripts/enforcement/check_mute.py", "M", warn_only=True)',
    )
    monkeypatch.setattr(la, "CANARIES", {"check_mute": dict(_SPEAKER_CANARY)})
    monkeypatch.setattr(la, "UNREACHABLE", {})
    found = next(f for f in la.proof_vacuity(tmp_path)["findings"] if f["id"] == "check_mute")
    assert found["verdict"] == "DEAD", found
    assert "said nothing" in found["detail"]


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
        "```cron\n0 6 * * 1 /opt/fabrik/real.sh\n0 2 * * 0 /opt/fabrik/imaginary.sh\n```\n",
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
        FakeBox(tmp_path),
        claim,
        la.Instrument.proven("crontab -l"),
        ["0 6 * * 1 /opt/fabrik/job.sh"],
    )
    assert f.verdict is la.Verdict.DEAD and "schedule drift" in f.detail


def test_a_prose_word_is_not_mistaken_for_a_scheduled_job(tmp_path: Path) -> None:
    """ "the weekly cron line (Sun 02:00, ...)" once produced a job named "line"."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "- the weekly cron line (Sun 02:00, plaintext KEY) was removed\n"
        "- calendar-orchestration (Sun 02:00) still runs\n",
        encoding="utf-8",
    )
    tokens = {c.payload for c in la.extract_claims(doc, "d.md") if c.ctype == "scheduled_name"}
    assert tokens == {"calendar-orchestration"}


def test_a_doc_that_names_several_states_is_true_if_the_box_reports_any_of_them(
    tmp_path: Path,
) -> None:
    """A unit documented as `enabled` but ending `failed` on purpose is NOT a stale doc."""
    doc = tmp_path / "d.md"
    doc.write_text(
        "`x.service` is also `enabled` and ends `failed` on the port race\n", encoding="utf-8"
    )
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
    doc.write_text(
        "Serves <http://localhost:5051/> and the VPS runs on port 8443\n", encoding="utf-8"
    )
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
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "sysadmin" / "liveness_audit.py"),
            "--proof",
            proof,
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert json.loads(result.stdout)["summary"]["LIVE"] >= 1


def test_strict_is_opt_in_and_fails_only_on_dead(tmp_path: Path) -> None:
    surfaces = [
        {"id": "dead-one", "kind": "cron", "cron_match": "gone.sh", "evidence": {"type": "none"}}
    ]
    registry = _registry(tmp_path, surfaces)
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/other.sh"])
    report = la.audit(tmp_path, registry, {"heartbeat"}, box=box)
    assert report.failures() == 1

    unknown_only = la.audit(
        tmp_path,
        _registry(
            tmp_path,
            [
                {
                    "id": "opaque",
                    "kind": "cron",
                    "cron_match": "other.sh",
                    "evidence": {"type": "none"},
                }
            ],
        ),
        {"heartbeat"},
        box=box,
    )
    assert unknown_only.failures() == 0, "UNKNOWN must never fail --strict; only DEAD does"


def test_mail_escalate_is_registered_with_the_precedent_fields():
    """The escalation cron must stay registered (an unregistered cron is unmonitored) with
    the precedent's shape: a log-evidence path, a slack-justified budget, and a `why` that
    names the crontab install state so DEAD/unscheduled reads as expected pre-install."""
    import json
    from pathlib import Path

    reg = json.loads(
        (Path(__file__).resolve().parent.parent / ".fabrik" / "liveness-registry.json").read_text()
    )
    surfaces = reg["surfaces"] if isinstance(reg, dict) and "surfaces" in reg else reg
    row = next(s for s in surfaces if s.get("id") == "mail-escalate")
    assert row["cron_match"] == "mail_escalate.py"
    assert row["evidence"]["path"] == "/var/log/fabrik-mail-escalate.log"
    assert row["max_age_hours"] == 54 and "max_age_note" in row
    assert "crontab" in row["why"].lower()


def test_the_audit_stamps_its_own_heartbeat_line(tmp_path, capsys):
    """The auditor audits itself (registry surface `liveness-audit`, a log_marker on the cron's
    log): on completion it prints ONE LOG_STAMP-shaped stderr line carrying SELF_MARKER, which is
    exactly what `_stamp_age` can age — the installed weekly line has no `cd /opt/fabrik`, so its
    only scheduled attempt failed with nothing watching the watcher (DA1)."""
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"surfaces": []}), encoding="utf-8")
    argv = ["--registry", str(reg), "--repo-root", str(tmp_path), "--proof", "heartbeat", "--json"]
    assert la.main(argv) == 0
    captured = capsys.readouterr()
    lines = [ln for ln in captured.err.splitlines() if la.SELF_MARKER in ln]
    assert len(lines) == 1, captured.err
    age = la._stamp_age(lines[0])
    assert age is not None and 0 <= age < 0.01, lines[0]
    json.loads(captured.out)  # stdout stayed pure JSON — the stamp went to stderr


def test_the_self_heartbeat_line_survives_the_crons_merged_streams(tmp_path):
    """The installed line appends `>> log 2>&1`: a report larger than the stdout buffer was written
    through with its trailing newline still BUFFERED, so the stderr stamp landed glued to the last
    brace (`}2026-09-03 05:03:51 liveness-audit: …`) — never LOG_STAMP-shaped, the self-surface
    UNKNOWN forever. Proven through ONE merged file the way cron sees it, with a report big enough
    to overflow the buffer (DC1)."""
    surfaces = [
        {
            "id": f"s{i}",
            "kind": "cron",
            "cron_match": f"never-matches-{i}",
            "doc": "x.md",
            "evidence": {"type": "none"},
            "max_age_hours": 24,
            "why": "x" * 120,
        }
        for i in range(80)
    ]
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"surfaces": surfaces}), encoding="utf-8")
    merged = tmp_path / "merged.log"
    with merged.open("w", encoding="utf-8") as fh:
        subprocess.run(
            [
                sys.executable,
                la.__file__,
                "--registry",
                str(reg),
                "--repo-root",
                str(tmp_path),
                "--proof",
                "heartbeat",
                "--json",
            ],
            stdout=fh,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=300,
        )
    text = merged.read_text(encoding="utf-8")
    assert len(text) > 16384, len(text)  # the report must overflow the stdout buffer to prove it
    lines = [ln for ln in text.splitlines() if la.SELF_MARKER in ln]
    assert len(lines) == 1 and la._stamp_age(lines[0]) is not None, lines


def _big_registry(tmp_path, n: int):
    surfaces = [
        {
            "id": f"s{i}",
            "kind": "cron",
            "cron_match": f"never-matches-{i}",
            "doc": "x.md",
            "evidence": {"type": "none"},
            "max_age_hours": 24,
            "why": "x" * 120,
        }
        for i in range(n)
    ]
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"surfaces": surfaces}), encoding="utf-8")
    return reg


def _run_audit(tmp_path, reg, **popen):
    argv = [
        sys.executable,
        la.__file__,
        "--registry",
        str(reg),
        "--repo-root",
        str(tmp_path),
        "--proof",
        "heartbeat",
        "--json",
    ]
    return subprocess.Popen(argv, **popen)


def test_a_closed_stdout_never_raises_and_the_stamp_still_lands(tmp_path):
    """`--json | head`: with the report flushed inside `main` (DC1) a closed reader raised
    BrokenPipeError out of `main` — a traceback, exit 1, and NO stamp — while the doc promises the
    audit "exits 0 by default and never raises" (DE2). The reader leaves after 16 bytes; the report
    is large enough that its write is not one syscall, so the EPIPE lands mid-write (DG1)."""
    reg = _big_registry(tmp_path, 300)
    proc = _run_audit(tmp_path, reg, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None and proc.stderr is not None
    proc.stdout.read(16)
    proc.stdout.close()  # the reader leaves — every later write is EPIPE
    with proc.stderr:
        err = proc.stderr.read().decode("utf-8", "replace")
    assert proc.wait(timeout=300) == 0, err
    assert "Traceback" not in err and "BrokenPipeError" not in err, err
    lines = [ln for ln in err.splitlines() if la.SELF_MARKER in ln]
    assert len(lines) == 1 and la._stamp_age(lines[0]) is not None, err


def test_a_dead_merged_pipe_and_a_full_disk_never_raise_either(tmp_path):
    """DE2 guarded only the stdout leg against BrokenPipeError: `--json 2>&1 | head` (stderr is the
    same dead pipe) still exited 120 with the stamp lost, and `> /dev/full` (ENOSPC — the cron's
    own `>> log` shape on a full disk) raised out of `main` with a traceback and no stamp (DG1).
    A reader that leaves is its choice (exit 0); a box that cannot STORE the report exits 1 — the one
    non-zero exit outside `--strict` — never a raise, the stamp still landing wherever stderr works
    (DI1); with stdout and stderr on the same full disk nothing can be written, exit 1 (DI1)."""
    reg = _big_registry(tmp_path, 300)
    proc = _run_audit(tmp_path, reg, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.stdout is not None
    proc.stdout.read(16)
    proc.stdout.close()
    assert proc.wait(timeout=300) == 0  # the merged dead pipe: the reader's choice
    if not (os.path.exists("/dev/full") and os.access("/dev/full", os.W_OK)):
        pytest.skip("no writable /dev/full on this box")
    with open("/dev/full", "w") as full:
        proc = _run_audit(tmp_path, reg, stdout=full, stderr=subprocess.PIPE)
        assert proc.stderr is not None
        with proc.stderr:
            err = proc.stderr.read().decode("utf-8", "replace")
        assert proc.wait(timeout=300) == 1, err  # the report could not be stored
        assert "Traceback" not in err, err
        # an undeliverable report stamps a DIFFERENT marker: the registry's `liveness-audit`
        # surface must age to DEAD, not read LIVE for 180 h on a report that went nowhere (DM2)
        lines = [ln for ln in err.splitlines() if la.SELF_MARKER_UNDELIVERED in ln]
        assert len(lines) == 1 and la._stamp_age(lines[0]) is not None, err
        assert not [ln for ln in err.splitlines() if ln.rstrip().endswith(la.SELF_MARKER)], err
        # the cron's own shape on a full disk: `>> log 2>&1` — both streams dead, exit 1, no raise
        proc = _run_audit(tmp_path, reg, stdout=full, stderr=subprocess.STDOUT)
        assert proc.wait(timeout=300) == 1


def test_a_closed_stdout_is_an_undeliverable_report(tmp_path):
    """`1>&-`: `print()` silently no-ops on a None stdout, so the report went nowhere while the run
    exited 0 and STAMPED "report generated" — vacuous evidence, the mirror of DI2 (DK2). Exit 1,
    the stamp still lands."""
    reg = _big_registry(tmp_path, 40)
    argv = [
        sys.executable,
        la.__file__,
        "--registry",
        str(reg),
        "--repo-root",
        str(tmp_path),
        "--proof",
        "heartbeat",
        "--json",
    ]
    proc = subprocess.run(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=300,
        preexec_fn=lambda: os.close(1),
    )
    err = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 1, err
    assert "Traceback" not in err, err
    lines = [ln for ln in err.splitlines() if la.SELF_MARKER_UNDELIVERED in ln]
    assert len(lines) == 1 and la._stamp_age(lines[0]) is not None, err
    assert not [ln for ln in err.splitlines() if ln.rstrip().endswith(la.SELF_MARKER)], err


def test_a_closed_stderr_never_corrupts_the_report(tmp_path):
    """`2>&-` leaves `sys.stderr` None: `print(file=None)` falls back to STDOUT, so the stamp was
    appended to the JSON report (unparseable), and the dead-stderr guard itself raised
    `AttributeError` on `None.fileno()` (DI2). The stamp is skipped, the report stays pure JSON,
    exit 0."""
    reg = _big_registry(tmp_path, 40)
    argv = [
        sys.executable,
        la.__file__,
        "--registry",
        str(reg),
        "--repo-root",
        str(tmp_path),
        "--proof",
        "heartbeat",
        "--json",
    ]
    out = tmp_path / "out.json"
    with out.open("w", encoding="utf-8") as fh:
        rc = subprocess.run(
            argv,
            stdout=fh,
            stderr=subprocess.DEVNULL,
            timeout=300,
            close_fds=True,
            pass_fds=(),
            preexec_fn=lambda: os.close(2),
        ).returncode
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert la.SELF_MARKER not in text
    json.loads(text)


def test_a_marker_echoed_by_the_report_itself_is_not_evidence(tmp_path):
    """The audit's own JSON report names the marker in its `detail` text and the cron appends that
    report to the marker's log: substring hits inflated the count, and a run that died before its
    stamp left only untimestamped hits — UNKNOWN, which `--strict` never fails (DE2). Only a
    LOG_STAMP-shaped line counts."""
    home = tmp_path / "home"
    home.mkdir()
    log = home / "liveness.log"
    log.write_text(
        "2026-09-01 06:40:00 liveness-audit: report generated\n"
        '          "detail": "~/liveness.log carries no line with \'liveness-audit: report generated\'",\n'
        "2026-09-02 06:40:00 liveness-audit: report generated\n"
        '          "detail": "carries no line with \'liveness-audit: report generated\'",\n',
        encoding="utf-8",
    )
    box = la.Box(home=home) if "home" in la.Box.__init__.__code__.co_varnames else None
    if box is None:
        pytest.skip("Box has no injectable home")
    inst, age, hits = box.marker_age("~/liveness.log", "liveness-audit: report generated")
    assert inst.ok and hits == 2 and age is not None, (inst, age, hits)
    # the age is the NEWEST stamped line's (2026-09-02), never the oldest — `stamped[-1]` (DG2)
    newest = la._stamp_age("2026-09-02 06:40:00 x")
    assert newest is not None and abs(age - newest) < 0.01, (age, newest)
    log.write_text(
        '          "detail": "carries no line with \'liveness-audit: report generated\'",\n',
        encoding="utf-8",
    )
    inst, age, hits = box.marker_age("~/liveness.log", "liveness-audit: report generated")
    assert not inst.ok and age is None, (inst, age, hits)  # untimestamped hits only: still UNKNOWN
    log.write_text("2026-09-02 06:40:00 liveness-audit: report UNDELIVERED\n", encoding="utf-8")
    inst, age, hits = box.marker_age("~/liveness.log", la.SELF_MARKER)
    assert inst.ok and hits == 0 and age is None, (
        inst,
        age,
        hits,
    )  # an undelivered run is no evidence (DM2)


def test_a_future_dated_stamp_is_unknown_never_live(tmp_path: Path) -> None:
    """A stamp two days in the FUTURE (a clock jump after resume, a restored backup, a stray
    `touch`) satisfied `age <= limit` and read LIVE however long the real run stayed absent —
    the audit's own canary already refused a future mtime; the evidence readers did not (EQ3)."""
    import os
    import time

    future = tmp_path / "future.log"
    future.write_text("ran\n")
    os.utime(future, (time.time() + 48 * 3600, time.time() + 48 * 3600))
    surfaces = [
        {
            "id": "future",
            "kind": "cron",
            "cron_match": "job_f",
            "evidence": {"type": "log", "path": str(future)},
            "max_age_hours": 24,
        }
    ]
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/job_f"])
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    f = {x["id"]: x for x in out["findings"]}["future"]
    assert f["verdict"] == "UNKNOWN", f
    assert "NEGATIVE age" in f["detail"], f


def test_the_negative_age_threshold_is_a_minute_not_a_day(tmp_path: Path) -> None:
    """A stamp two HOURS in the future is UNKNOWN too — the tolerance is one minute of clock
    jitter (the canary's own), never a day of slack that a widened constant would smuggle in
    (ES3)."""
    import os
    import time

    soon = tmp_path / "soon.log"
    soon.write_text("ran\n")
    os.utime(soon, (time.time() + 2 * 3600, time.time() + 2 * 3600))
    jitter = tmp_path / "jitter.log"
    jitter.write_text("ran\n")
    os.utime(jitter, (time.time() + 20, time.time() + 20))  # twenty seconds ahead: jitter, LIVE
    surfaces = [
        {
            "id": "soon",
            "kind": "cron",
            "cron_match": "job_s",
            "evidence": {"type": "log", "path": str(soon)},
            "max_age_hours": 24,
        },
        {
            "id": "jitter",
            "kind": "cron",
            "cron_match": "job_j",
            "evidence": {"type": "log", "path": str(jitter)},
            "max_age_hours": 24,
        },
    ]
    box = FakeBox(tmp_path, cron=["0 * * * * /opt/fabrik/job_s", "0 * * * * /opt/fabrik/job_j"])
    reg, _ = la.load_registry(_registry(tmp_path, surfaces))
    out = la.proof_heartbeat(box, reg, "")
    by_id = {x["id"]: x for x in out["findings"]}
    assert by_id["soon"]["verdict"] == "UNKNOWN", by_id["soon"]
    assert by_id["jitter"]["verdict"] == "LIVE", by_id["jitter"]
