"""Behaviour tests for the T04 sensor emitters — the gate and the rules selectors.

Two contracts are under test, and the second one is the load-bearing one:

1. **The sensors observe honestly.** ``final_gate.py`` emits ONE ``gate_run`` per
   invocation whose ``checks`` rows are 1:1 with the report it just printed — no check
   silently absent, advisory rows labelled as such. ``select_rules.py`` and
   ``review_rubric.py`` emit ``rule_activation`` naming the packs that actually fired,
   labelled *invocation-time* (the honest label: per-EDIT activation needs a PostToolUse
   surface, which lands in M2).

2. **NEVER-ROUTE: the sensor cannot touch the gate.** ``final_gate.py`` is the fleet's
   completion gate; an observation that changed a check, an exit code, an output line or
   an ordering would be a defect with a ~46-repo blast radius. So every emitter is proven
   inert by BYTE-COMPARING stdout + exit code against the same run with the emitter
   removed (``sys.modules['kaizen_events'] = None`` — exactly what a project that has not
   received the module sees) and against a run whose event store is unwritable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "final_gate.py"
SELECT_RULES = REPO / "scripts" / "select_rules.py"
REVIEW_RUBRIC = REPO / "scripts" / "review_rubric.py"

# Runs a script with `kaizen_events` made unimportable — the exact state of a project
# that has not received the box-local module. `python -c <harness> <script> <args…>`.
_ABSENT_HARNESS = (
    "import sys, runpy;"
    "sys.modules['kaizen_events'] = None;"
    "sys.argv = sys.argv[1:];"
    "runpy.run_path(sys.argv[0], run_name='__main__')"
)


def _env(events_dir: Path | str, sid: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["KAIZEN_EVENTS_DIR"] = str(events_dir)
    env["CLAUDE_SESSION_ID"] = sid
    env.update(extra or {})
    return env


def _run(
    script: Path,
    *args: str,
    events_dir: Path | str,
    sid: str,
    cwd: Path = REPO,
    absent: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    cmd = (
        [sys.executable, "-c", _ABSENT_HARNESS, str(script), *args]
        if absent
        else [sys.executable, str(script), *args]
    )
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_env(events_dir, sid, extra_env),
        capture_output=True,
        text=True,
        timeout=900,
    )


def _unwritable(tmp_path: Path) -> Path:
    """An events dir that cannot exist: its parent is a regular file."""
    wall = tmp_path / "wall"
    wall.write_text("not a directory\n", encoding="utf-8")
    return wall / "events"


def _events(events_dir: Path, sid: str, event: str) -> list[dict]:
    path = events_dir / f"{sid}.jsonl"
    if not path.is_file():
        return []
    return [
        row
        for row in (json.loads(ln) for ln in path.read_text().splitlines() if ln.strip())
        if row.get("event") == event
    ]


def _pack(root: Path, rel: str, globs: str) -> Path:
    path = root / ".windsurf" / "rules" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"description: Fixture pack {rel} for the T04 sensor emitters\n"
        f"globs: [{globs}]\n"
        "---\n\n"
        "# Rules\n\n"
        "- MUST never emit an event that changes what it observes\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal project tree: one pack whose glob a real file fires, plus a real FLOOR.

    The floor packs carry a glob nothing here matches, so they stay AVAILABLE for
    select_rules while review_rubric still injects them unconditionally — which is the
    whole point of the mandatory-core floor.
    """
    root = tmp_path / "proj"
    _pack(root, "core/10-fixture.md", '"**/*.fixture.py"')
    for rel in ("core/35-security-auth.md", "core/25-data-postgres.md", "core/30-ops.md"):
        _pack(root, rel, '"**/*.nomatch"')
    src = root / "app"
    src.mkdir()
    (src / "thing.fixture.py").write_text("x = 1\n", encoding="utf-8")
    return root


# ── final_gate.py: gate_run ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def _gate_lean(tmp_path_factory) -> tuple[subprocess.CompletedProcess, Path, str]:
    """One real `--lean --json --check` gate run (read-only), shared by the gate tests."""
    events = tmp_path_factory.mktemp("gate-events")
    sid = "t04-gate"
    proc = _run(GATE, "--lean", "--json", "--check", events_dir=events, sid=sid)
    return proc, events, sid


def test_gate_run_rows_are_1to1_with_the_report(_gate_lean):
    proc, events, sid = _gate_lean
    assert proc.returncode in (0, 1), proc.stderr[-2000:]
    report = json.loads(proc.stdout)

    rows = _events(events, sid, "gate_run")
    assert len(rows) == 1, f"exactly ONE gate_run per invocation, got {len(rows)}"
    ev = rows[0]

    checks = ev["checks"]
    assert len(checks) == report["passed"] + report["failed"], (
        "every EXECUTED check owes a row — no check silently absent"
    )
    assert {c["name"] for c in checks if c["outcome"] == "fail"} == {
        f["check"] for f in report["failures"]
    }
    assert {c["name"] for c in checks if c["outcome"] == "advisory"} == {
        a["check"] for a in report["advisory"]
    }
    assert ev["status"] == report["status"]
    assert ev["tier"] == report["tier"] == 1
    assert ev["mode"]["check"] is True and ev["mode"]["lean"] is True
    assert ev["mode"]["systemic"] is False and ev["mode"]["json"] is True


def test_gate_stdout_and_exit_code_are_byte_identical_without_the_emitter(_gate_lean, tmp_path):
    """NEVER-ROUTE: the module absent must be indistinguishable from the module present."""
    proc, _, _ = _gate_lean
    absent = _run(
        GATE,
        "--lean",
        "--json",
        "--check",
        events_dir=tmp_path / "unused",
        sid="t04-gate-absent",
        absent=True,
    )
    assert absent.stdout == proc.stdout
    assert absent.returncode == proc.returncode
    assert not (tmp_path / "unused").exists(), "an absent emitter must not create a store"


def test_gate_is_unharmed_when_the_event_store_is_unwritable(_gate_lean, tmp_path):
    """A broken store fails open on EVERY channel: stdout, stderr and exit code.

    stderr is the one the first round missed — ``emit()``'s internal failure path calls
    ``_warn()``, and none of these three scripts wrote a byte to stderr before T04. A
    sensor that narrates its own failure into the gate's stderr has changed the gate.
    """
    blocked = _unwritable(tmp_path)
    proc, _, _ = _gate_lean
    broken = _run(GATE, "--lean", "--json", "--check", events_dir=blocked, sid="t04-gate-broken")
    assert broken.stdout == proc.stdout
    assert broken.stderr == proc.stderr
    assert broken.returncode == proc.returncode
    assert blocked.parent.read_text(encoding="utf-8") == "not a directory\n"


# ── select_rules.py: rule_activation ─────────────────────────────────────────────────


def test_select_rules_emits_active_packs_with_the_globs_that_fired(project, tmp_path):
    events = tmp_path / "events"
    proc = _run(SELECT_RULES, "--project-root", str(project), events_dir=events, sid="t04-rules")
    assert proc.returncode == 0, proc.stderr[-2000:]

    rows = _events(events, "t04-rules", "rule_activation")
    assert len(rows) == 1, f"exactly ONE rule_activation per invocation, got {len(rows)}"
    ev = rows[0]
    assert ev["kind"] == "select_rules"
    # residual #1, baked in: this is activation at INVOCATION time, not per edit
    assert ev["label"] == "invocation-time"
    assert ev["packs"] == [{"pack": "core/10-fixture.md", "globs_fired": ["**/*.fixture.py"]}]


def test_select_rules_stdout_is_byte_identical_without_the_emitter(project, tmp_path):
    args = (SELECT_RULES, "--project-root", str(project))
    live = _run(*args, events_dir=tmp_path / "live", sid="t04-rules-live")
    absent = _run(*args, events_dir=tmp_path / "gone", sid="t04-rules-gone", absent=True)
    assert absent.stdout == live.stdout
    assert absent.returncode == live.returncode == 0


def test_select_rules_is_unharmed_when_the_event_store_is_unwritable(project, tmp_path):
    args = (SELECT_RULES, "--project-root", str(project))
    live = _run(*args, events_dir=tmp_path / "live", sid="t04-rules-ok")
    broken = _run(*args, events_dir=_unwritable(tmp_path), sid="t04-rules-broken")
    assert broken.stdout == live.stdout
    assert broken.stderr == live.stderr
    assert broken.returncode == live.returncode == 0


def test_select_rules_json_mode_still_emits_and_stays_parseable(project, tmp_path):
    events = tmp_path / "events"
    proc = _run(
        SELECT_RULES,
        "--project-root",
        str(project),
        "--json",
        events_dir=events,
        sid="t04-rules-json",
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    data = json.loads(proc.stdout)
    assert [e["pack"] for e in data["active"]] == ["core/10-fixture.md"]
    assert len(_events(events, "t04-rules-json", "rule_activation")) == 1


# ── review_rubric.py: rule_activation / rubric_injection ─────────────────────────────


def test_review_rubric_emits_the_packs_it_injected(project, tmp_path):
    events = tmp_path / "events"
    proc = _run(
        REVIEW_RUBRIC,
        "--changed",
        "app/thing.fixture.py",
        "--project-root",
        str(project),
        events_dir=events,
        sid="t04-rubric",
    )
    assert proc.returncode == 0, proc.stderr[-2000:]

    rows = _events(events, "t04-rubric", "rule_activation")
    assert len(rows) == 1, f"exactly ONE rule_activation per invocation, got {len(rows)}"
    ev = rows[0]
    assert ev["kind"] == "rubric_injection"
    assert ev["label"] == "invocation-time"
    packs = [p["pack"] for p in ev["packs"]]
    # the mandatory-core FLOOR is always injected, and the glob-matched pack rides with it
    assert "core/35-security-auth.md" in packs
    assert "core/10-fixture.md" in packs
    assert all(p.endswith(".md") for p in packs), "the 12-FACTOR axis block is not a pack"


def test_review_rubric_stdout_is_byte_identical_without_the_emitter(project, tmp_path):
    args = (REVIEW_RUBRIC, "--changed", "app/thing.fixture.py", "--project-root", str(project))
    live = _run(*args, events_dir=tmp_path / "live", sid="t04-rubric-live")
    absent = _run(*args, events_dir=tmp_path / "gone", sid="t04-rubric-gone", absent=True)
    assert absent.stdout == live.stdout
    assert absent.returncode == live.returncode == 0


def test_review_rubric_is_unharmed_when_the_event_store_is_unwritable(project, tmp_path):
    args = (REVIEW_RUBRIC, "--changed", "app/thing.fixture.py", "--project-root", str(project))
    live = _run(*args, events_dir=tmp_path / "live", sid="t04-rubric-ok")
    broken = _run(*args, events_dir=_unwritable(tmp_path), sid="t04-rubric-broken")
    assert broken.stdout == live.stdout
    assert broken.stderr == live.stderr
    assert broken.returncode == live.returncode == 0


def test_review_rubric_does_not_claim_a_missing_floor_pack_was_injected(project, tmp_path):
    """A FLOOR pack absent on disk still gets a `### heading` + a placeholder line — but
    NOTHING of it reached the reviewer, so the event must not report it as injected."""
    (project / ".windsurf" / "rules" / "core" / "30-ops.md").rename(
        project / ".windsurf" / "rules" / "core" / "30-ops-renamed.md"
    )
    events = tmp_path / "events"
    proc = _run(
        REVIEW_RUBRIC,
        "--changed",
        "app/thing.fixture.py",
        "--project-root",
        str(project),
        events_dir=events,
        sid="t04-rubric-missing",
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "(pack missing at" in proc.stdout, "the rubric still prints the placeholder heading"

    ev = _events(events, "t04-rubric-missing", "rule_activation")[0]
    packs = [p["pack"] for p in ev["packs"]]
    assert "core/30-ops.md" not in packs, "an absent pack was never injected"
    assert "core/35-security-auth.md" in packs, "the present floor packs still are"
    assert ev["packs_missing"] == ["core/30-ops.md"], "and the gap is reported, not swallowed"


def test_review_rubric_emits_even_when_the_consumer_closes_the_pipe(project, tmp_path):
    """`review_rubric.py | head` is a REAL, successful invocation — its rubric was built
    and delivered as far as the consumer wanted it. The sensor must not lose that run.

    The pack is padded past stdout's 8 KiB block buffer on purpose: a small rubric never
    reaches a `write()` inside `print()`, so it would fail at interpreter-exit flush
    INSTEAD — long after `main()` returned, which makes the test pass without ever
    entering the handler under test.
    """
    pack = project / ".windsurf" / "rules" / "core" / "10-fixture.md"
    pad = "".join(f"- MUST bound the probe, rule {i}\n" for i in range(2000))
    pack.write_text(pack.read_text(encoding="utf-8") + pad, encoding="utf-8")
    events = tmp_path / "events"
    read_fd, write_fd = os.pipe()
    os.close(read_fd)  # no reader: the child's first write to stdout gets EPIPE
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(REVIEW_RUBRIC),
                "--changed",
                "app/thing.fixture.py",
                "--project-root",
                str(project),
            ],
            cwd=str(REPO),
            env=_env(events, "t04-rubric-pipe"),
            stdout=write_fd,
            stderr=subprocess.PIPE,
        )
    finally:
        os.close(write_fd)
    proc.communicate(timeout=120)

    rows = _events(events, "t04-rubric-pipe", "rule_activation")
    assert len(rows) == 1, "a pipe closed early must still record the invocation"
    assert [p["pack"] for p in rows[0]["packs"]]


# ── the hot path: bounded probes ─────────────────────────────────────────────────────


@pytest.fixture
def stub_emitter(tmp_path: Path) -> tuple[Path, Path]:
    """A recording stand-in for `kaizen_events`, shadowing the real one via PYTHONPATH.

    The sensors append `scripts/sysadmin` to `sys.path`, so a PYTHONPATH entry wins —
    which lets us assert the KWARGS each script passes, not just the line it produced.
    """
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    log = tmp_path / "emits.jsonl"
    (stub_dir / "kaizen_events.py").write_text(
        "import json, os\n"
        "def emit(event, sid=None, **kw):\n"
        "    with open(os.environ['T04_STUB_LOG'], 'a') as fh:\n"
        "        row = {'event': event, 'probe_timeout_s': kw.get('probe_timeout_s')}\n"
        "        fh.write(json.dumps(row) + '\\n')\n"
        "    return True\n",
        encoding="utf-8",
    )
    return stub_dir, log


def test_every_sensor_bounds_the_exposure_probe(project, tmp_path, stub_emitter):
    """The git probes behind `exposure()` default to a 10 s timeout each. These sensors
    fire AFTER the verdict is settled, ahead of the script's own output — an `unknown`
    field beats making the fleet's gate wait on a hung git."""
    stub_dir, log = stub_emitter
    env = {"PYTHONPATH": str(stub_dir), "T04_STUB_LOG": str(log)}
    runs = (
        (GATE, ("--lean", "--json", "--check")),
        (SELECT_RULES, ("--project-root", str(project))),
        (REVIEW_RUBRIC, ("--changed", "app/thing.fixture.py", "--project-root", str(project))),
    )
    for script, args in runs:
        _run(script, *args, events_dir=tmp_path / "unused", sid="t04-timeout", extra_env=env)

    rows = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
    assert [r["event"] for r in rows] == ["gate_run", "rule_activation", "rule_activation"]
    assert [r["probe_timeout_s"] for r in rows] == [2.0, 2.0, 2.0]
