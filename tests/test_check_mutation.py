"""Behavior contract for scripts/enforcement/check_mutation.py (advisory mutation runner).

The runner's user-observable behaviors: it reports surviving mutants; it is opt-in in the per-commit
gate (skips with a pointer unless FABRIK_MUTMUT is set); it skips when mutmut is absent; it never
blocks (always exit 0); and it scopes to committed, non-test, non-vendored Python.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "enforcement" / "check_mutation.py"
sys.path.insert(0, str(ROOT))
import scripts.enforcement.check_mutation as cm  # noqa: E402


def test_parse_survivors_reports_a_surviving_mutant():
    # Given mutmut results with a survivor, When parsed, Then it is reported.
    assert cm.parse_survivors("2/5 mutants: 2 survived, 3 killed") == 2


def test_parse_survivors_clean_when_none_survive():
    # Given results with no survivors, Then zero is reported.
    assert cm.parse_survivors("5/5 killed - 0 survived") == 0
    assert cm.parse_survivors("all mutants killed") == 0


def test_parse_survivors_no_false_positive_on_negation():
    # "survived" in a NEGATION must NOT read as a survivor (a false advisory alarm).
    assert cm.parse_survivors("no mutants survived") == 0
    assert cm.parse_survivors("Done. All killed. No survivors.") == 0


def test_parse_survivors_handles_survived_colon_n():
    # tolerate the `survived: N` ordering some mutmut summaries use.
    assert cm.parse_survivors("Survived: 3") == 3


def test_parse_survivors_real_mutmut36_per_mutant_lines():
    # Review finding (installed-source grounded): mutmut 3.6's `results` prints ONE
    # `    <mutant-id>: survived` line per survivor and NO aggregate — the per-line arm
    # must count exactly the survived lines, never other statuses.
    real = (
        "    src.fabrik.app.compute__mutmut_1: survived\n"
        "    src.fabrik.app.compute__mutmut_2: survived\n"
        "    src.fabrik.app.compute__mutmut_3: no tests\n"
    )
    assert cm.parse_survivors(real) == 2
    assert cm.parse_survivors("    src.fabrik.app.f__mutmut_9: timeout\n") == 0


def test_mutmut_bin_prefers_interpreter_sibling(tmp_path, monkeypatch):
    # Review finding (live-reproduced under cron's PATH): resolution must try the running
    # interpreter's bin dir FIRST — cron pins .venv/bin/python but has no .venv on PATH.
    fake_bin = tmp_path / "venvbin"
    fake_bin.mkdir()
    monkeypatch.setattr(cm.sys, "executable", str(fake_bin / "python"))
    monkeypatch.setattr(cm.shutil, "which", lambda _: "/usr/bin/mutmut")
    assert cm.mutmut_bin() == "/usr/bin/mutmut"  # no sibling yet → PATH fallback
    sib = fake_bin / "mutmut"
    sib.write_text("#!/bin/sh\n")
    sib.chmod(0o755)
    assert cm.mutmut_bin() == str(sib)  # sibling exists → wins over PATH
    monkeypatch.setattr(cm.shutil, "which", lambda _: None)
    sib.unlink()
    assert cm.mutmut_bin() is None  # neither → honest absence


def test_flag_unset_skips_advisory_in_gate(tmp_path):
    # Given FABRIK_MUTMUT unset (the per-commit gate), Then the runner skips with a pointer, exit 0.
    # Hermetic (review finding: under a system interpreter with no venv mutmut, this test
    # silently exercised the WRONG branch — mutmut-absent — and failed): a fake executable
    # mutmut is prepended to PATH so binary resolution succeeds under ANY interpreter.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake = fake_bin / "mutmut"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "FABRIK_MUTMUT"}
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    r = subprocess.run(
        [sys.executable, str(CHECK)], capture_output=True, text=True, env=env, cwd=str(ROOT)
    )
    assert r.returncode == 0, r.stderr
    assert "skipped in the per-commit gate" in r.stdout


def test_mutmut_absent_skips(monkeypatch, capsys, tmp_path):
    # Given mutmut is not installed, Then the runner skips (exit 0) rather than erroring.
    # (sys.executable is pointed at an empty dir so the interpreter-sibling arm is absent too.)
    monkeypatch.setattr(cm.sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(cm.shutil, "which", lambda _: None)
    assert cm.main() == 0
    assert "not installed" in capsys.readouterr().out


def test_changed_python_excludes_tests_and_vendored():
    # Then the diff scope is applied code only — never tests/ or the canonical-owned libs/ (smoke: the
    # live call returns a list and never a tests/libs/ or non-.py entry).
    files = cm.changed_python()
    assert isinstance(files, list)
    assert all(f.endswith(".py") and not f.startswith(("tests/", "libs/")) for f in files)


def test_changed_python_filters_tests_libs_and_nonpy(monkeypatch):
    # Robust (non-vacuous): a controlled diff with tests/, libs/, a doc, and two src .py files →
    # only the applied src .py survive. Path.exists forced True so the FILTER, not existence, is tested.
    import types

    fake = "src/fabrik/a.py\ntests/test_a.py\nlibs/subagents/b.py\ndocs/c.md\nsrc/fabrik/d.py\n"
    monkeypatch.setattr(cm.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=fake))
    monkeypatch.setattr(cm.Path, "exists", lambda self: True)
    assert cm.changed_python(base="somebase") == ["src/fabrik/a.py", "src/fabrik/d.py"]


def test_wall_cap_timeout_kills_group_and_stays_advisory(monkeypatch, capsys):
    # Given FABRIK_MUTMUT set and mutmut exceeding the wall cap, When main() runs, Then the whole
    # process GROUP is reaped (not just the direct child), the cap is reported, and exit stays 0.
    import subprocess as sp
    import types

    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setenv("FABRIK_MUTMUT_WALL_CAP_S", "1")
    monkeypatch.setattr(cm.shutil, "which", lambda _: "/usr/bin/mutmut")
    monkeypatch.setattr(cm, "changed_python", lambda base=None: ["src/fabrik/x.py"])
    killed: dict = {}

    class FakeProc:
        pid = 4242
        calls = 0

        def wait(self, timeout=None):
            FakeProc.calls += 1
            if FakeProc.calls == 1:
                raise sp.TimeoutExpired(["mutmut", "run"], timeout)
            return 0

        def kill(self):
            killed["direct"] = True

    monkeypatch.setattr(cm.subprocess, "Popen", lambda cmd, **kw: FakeProc())
    monkeypatch.setattr(cm.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(stdout="0 survived", returncode=0))
    monkeypatch.setattr(cm.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(cm.os, "killpg", lambda pgid, sig: killed.setdefault("group", (pgid, sig)))
    assert cm.main() == 0
    out = capsys.readouterr().out
    assert "wall cap" in out and "exit 0" in out
    assert killed.get("group") == (4242, cm.signal.SIGKILL)


def test_malformed_wall_cap_falls_back_to_default(monkeypatch, capsys):
    # Given a malformed FABRIK_MUTMUT_WALL_CAP_S, When main() runs, Then it falls back to 1200 and
    # never raises — an ALWAYS-exit-0 advisory must not fail the gate on a typo'd env var.
    import types

    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setenv("FABRIK_MUTMUT_WALL_CAP_S", "20m")
    monkeypatch.setattr(cm.shutil, "which", lambda _: "/usr/bin/mutmut")
    monkeypatch.setattr(cm, "changed_python", lambda base=None: ["src/fabrik/x.py"])

    class FakeProc:
        pid = 1

        def wait(self, timeout=None):
            assert timeout == 1200  # the fallback default, not a crash
            return 0

    monkeypatch.setattr(cm.subprocess, "Popen", lambda cmd, **kw: FakeProc())
    monkeypatch.setattr(cm.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(stdout="0 survived", returncode=0))
    assert cm.main() == 0
    assert "malformed FABRIK_MUTMUT_WALL_CAP_S" in capsys.readouterr().out


def test_negative_wall_cap_caps_immediately_and_stays_advisory(monkeypatch, capsys):
    # Given a NEGATIVE cap, When main() runs, Then wait(timeout=-5) times out immediately,
    # the group is reaped, and exit stays 0 — the advisory contract holds at the low boundary.
    import subprocess as sp
    import types

    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setenv("FABRIK_MUTMUT_WALL_CAP_S", "-5")
    monkeypatch.setattr(cm, "mutmut_bin", lambda: "/usr/bin/mutmut")
    monkeypatch.setattr(cm, "changed_python", lambda base=None: ["src/fabrik/x.py"])
    killed: dict = {}

    class FakeProc:
        pid = 77
        calls = 0

        def wait(self, timeout=None):
            FakeProc.calls += 1
            if FakeProc.calls == 1:
                assert timeout == -5  # the parsed negative cap reaches wait un-mangled
                raise sp.TimeoutExpired(["mutmut", "run"], timeout)
            return 0

    monkeypatch.setattr(cm.subprocess, "Popen", lambda cmd, **kw: FakeProc())
    monkeypatch.setattr(cm.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(stdout="", returncode=0))
    monkeypatch.setattr(cm.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(cm.os, "killpg", lambda pgid, sig: killed.setdefault("group", (pgid, sig)))
    assert cm.main() == 0
    assert killed.get("group") == (77, cm.signal.SIGKILL)
    assert "wall cap" in capsys.readouterr().out


def test_hanging_results_call_stays_bounded_and_advisory(monkeypatch, capsys):
    # Review finding: `mutmut results` was the one unguarded subprocess — a hang there
    # would stall the ALWAYS-exit-0 advisory forever. It must be time-bounded and
    # degrade to "no survivors parsed", still exit 0.
    import subprocess as sp

    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setattr(cm, "mutmut_bin", lambda: "/usr/bin/mutmut")
    monkeypatch.setattr(cm, "changed_python", lambda base=None: ["src/fabrik/x.py"])

    class FakeProc:
        pid = 9

        def wait(self, timeout=None):
            return 0

    def hanging_run(cmd, **kw):
        assert kw.get("timeout"), "results call must carry a timeout"
        raise sp.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(cm.subprocess, "Popen", lambda cmd, **kw: FakeProc())
    monkeypatch.setattr(cm.subprocess, "run", hanging_run)
    assert cm.main() == 0
    assert "no surviving mutants" in capsys.readouterr().out


def test_unforeseen_exception_fails_soft(monkeypatch, capsys):
    # Review finding: run_optional_check marks a non-zero exit FAILED regardless of
    # advisory=True — an uncaught raise would flip the whole gate red. main() must catch
    # everything and exit 0.
    def boom():
        raise OSError("TOCTOU: resolved binary vanished")

    monkeypatch.setattr(cm, "mutmut_bin", boom)
    assert cm.main() == 0
    assert "fail-soft" in capsys.readouterr().err


def test_since_window_scopes_by_committed_history(monkeypatch):
    # Given FABRIK_MUTMUT_SINCE, When changed_python runs, Then the git log --since window (deduped,
    # filtered) is the scope — not the merge-base diff.
    import types

    monkeypatch.setenv("FABRIK_MUTMUT_SINCE", "7 days ago")
    fake = "src/a.py\nsrc/a.py\ntests/test_a.py\nlibs/x.py\ndocs/d.md\nsrc/b.py\n\n"
    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return types.SimpleNamespace(stdout=fake)

    monkeypatch.setattr(cm.subprocess, "run", fake_run)
    monkeypatch.setattr(cm.Path, "exists", lambda self: True)
    assert cm.changed_python() == ["src/a.py", "src/b.py"]
    assert "--since=7 days ago" in " ".join(captured["cmd"])
