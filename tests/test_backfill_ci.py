"""W-76d3448d: backfill_ci.py keys "already has CI" on the file it writes and grades the SQL the
replica will lint before it writes anything.

The generator stopped emitting `.github/workflows/ci.yml` on 2026-08-29, so the old guard rewrote
every newer repo on each `--apply`; and since 921e40b0a the written `scripts/ci_local.sh` runs
sqlfluff over every tracked `*.sql`, which a backfill never checked. Every repo here is a tmp git
repo under a tmp OPT; the sqlfluff probe runs a fake interpreter, never the hub venv.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "backfill_ci.py"


def _module():
    spec = importlib.util.spec_from_file_location("backfill_ci_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# A fake interpreter for `<python> -m sqlfluff …`: its behaviour comes from FAKE_SQLFLUFF in the
# environment, so one script plays every state of the verdict grammar.
FAKE = r"""#!/usr/bin/env bash
[ "$1 $2" = "-m sqlfluff" ] || exit 9
shift 2
mode="${FAKE_SQLFLUFF:-clean}"
if [ "$1" = "--version" ]; then
  case "$mode" in
    absent) echo "No module named sqlfluff" >&2; exit 1 ;;
    wrongversion) echo "sqlfluff, version 3.0.0"; exit 0 ;;
    *) echo "sqlfluff, version PINNED"; exit 0 ;;
  esac
fi
echo "$PWD $*" >> "${FAKE_SQLFLUFF_LOG:-/dev/null}"
case "$mode" in
  clean) echo '[{"filepath": "a.sql", "violations": []}]'; exit 0 ;;
  red) echo '[{"filepath": "a.sql", "violations": [{"code": "L1"}, {"code": "L2"}]}, {"filepath": "b.sql", "violations": [{"code": "L3"}]}]'; exit 1 ;;
  badjson) echo 'not json'; exit 1 ;;
  warned) echo '[{"filepath": "a.sql", "violations": [{"code": "LT01", "warning": true}, {"code": "CP01", "warning": false}]}]'; exit 1 ;;
  nonutf8) printf '\377\376' >&2; echo '[]'; exit 0 ;;
  usage) echo 'usage error' >&2; exit 2 ;;
  slow) sleep 5; exit 0 ;;
esac
"""


@pytest.fixture
def bf(tmp_path, monkeypatch):
    mod = _module()
    opt = tmp_path / "opt"
    opt.mkdir()
    fake = tmp_path / "fake-python"
    fake.write_text(FAKE.replace("PINNED", mod.SQLFLUFF_VERSION), encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr(mod, "OPT", opt)
    monkeypatch.setattr(mod, "HUB_SPECS", tmp_path / "no-specs")
    monkeypatch.setattr(mod, "SQLFLUFF_PYTHON", str(fake))
    monkeypatch.setattr(mod, "_ruff_count", lambda proj: 0)
    monkeypatch.setattr(mod, "_assert_ruff_matches_pin", lambda: None)
    monkeypatch.setenv("FAKE_SQLFLUFF_LOG", str(tmp_path / "lint.log"))
    mod.TMP = tmp_path
    return mod


def _repo(bf, name: str, files: dict[str, str]) -> Path:
    proj = bf.OPT / name
    proj.mkdir()
    for rel, body in files.items():
        p = proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    return proj


def _managed_ci_local(bf, *, with_sqlfluff: bool = True) -> str:
    body = "#!/usr/bin/env bash\n# fabrik-managed — regenerate via fabrik scaffold\nset -e\n"
    return body + (bf.SQLFLUFF_STEP + "\n" if with_sqlfluff else "")


def _main(bf, monkeypatch, capsys, *argv: str, rc: int = 0) -> str:
    monkeypatch.setattr(sys, "argv", ["backfill_ci.py", *argv])
    assert bf.main() == rc
    return capsys.readouterr().out


def _row(out: str, name: str) -> str:
    (line,) = [ln for ln in out.splitlines() if ln.startswith(name + " ")]
    return line


def _cells(row: str) -> dict[str, str]:
    """The row's RUFF, SQL and SQLFLUFF cells, read by the column widths main() prints."""
    tail = row[30 + 14 + 3 + 4 + 4 :]
    # A verdict wider than its column must still end before the CI? cell: two spaces separate them.
    verdict = tail[13:].split("  ")[0].strip()
    return {"ruff": tail[:6].strip(), "sql": tail[6:11].strip(), "sqlfluff": verdict}


# ── 1. the skip guard keys on scripts/ci_local.sh ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("files", "action"),
    [
        (
            {"scripts/ci_local.sh": "MANAGED", ".fabrik/run-pytest": "x\n"},
            "already has CI",
        ),
        ({"scripts/ci_local.sh": "MANAGED"}, "already has CI (stale: no .fabrik/run-pytest)"),
        (
            {"scripts/ci_local.sh": "MANAGED-OLD", ".fabrik/run-pytest": "x\n"},
            "already has CI (stale: no sqlfluff step)",
        ),
        (
            {"scripts/ci_local.sh": "MANAGED-OLD"},
            "already has CI (stale: no sqlfluff step, no .fabrik/run-pytest)",
        ),
        ({"scripts/ci_local.sh": "#!/bin/sh\necho mine\n"}, "already has CI (not fabrik-managed)"),
        (  # the header must be line 2, as the generator writes it — not anywhere in the file
            {"scripts/ci_local.sh": "#!/bin/sh\necho mine\n# fabrik-managed — copied\n"},
            "already has CI (not fabrik-managed)",
        ),
        ({"scripts/ci_local.sh": "# fabrik-managed\n"}, "already has CI (not fabrik-managed)"),
    ],
)
def test_ci_local_sh_marks_the_repo_backfilled(bf, monkeypatch, capsys, files, action):
    managed = {
        "MANAGED": _managed_ci_local(bf),
        "MANAGED-OLD": _managed_ci_local(bf, with_sqlfluff=False),
    }
    files = {k: managed.get(v, v) for k, v in files.items()}
    files["db/schema.sql"] = "select 1;\n"
    proj = _repo(bf, "p", files)
    before = (proj / "scripts/ci_local.sh").read_bytes()
    monkeypatch.setenv("FAKE_SQLFLUFF", "clean")
    out = _main(bf, monkeypatch, capsys, "p", "--apply", "--force")
    assert _row(out, "p").endswith(action)
    assert (proj / "scripts/ci_local.sh").read_bytes() == before  # never rewritten
    assert not (bf.TMP / "lint.log").exists()  # a skipped repo is never linted


# ── 2. ci.yml alone no longer counts ───────────────────────────────────────────────────────


def test_ci_yml_alone_is_a_target(bf, monkeypatch, capsys):
    proj = _repo(bf, "p", {".github/workflows/ci.yml": "name: ci\n"})
    out = _main(bf, monkeypatch, capsys, "p", "--apply")
    assert "WROTE" in _row(out, "p")
    assert (proj / "scripts/ci_local.sh").exists()


# ── 3. the dry-run row ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "sql", "verdict", "refuses"),
    [
        ("clean", 2, "clean", False),
        ("red", 2, "red 3", True),
        ("absent", 2, "unknown (no sqlfluff)", True),
        ("clean", 0, "-", False),
    ],
)
def test_dry_run_row_shows_sql_and_verdict(bf, monkeypatch, capsys, mode, sql, verdict, refuses):
    files = {f"db/{i}.sql": "select 1;\n" for i in range(sql)} or {"README.md": "x\n"}
    _repo(bf, "p", files)
    monkeypatch.setenv("FAKE_SQLFLUFF", mode)
    row = _row(_main(bf, monkeypatch, capsys, "p"), "p")
    assert _cells(row) == {"ruff": "0", "sql": str(sql), "sqlfluff": verdict}
    if refuses:
        assert row.endswith(f"would REFUSE (sqlfluff {verdict}; --force overrides)")
    else:
        assert row.endswith("would seed baseline@0")


def test_a_forced_dry_run_says_what_it_would_force_past(bf, monkeypatch, capsys):
    _repo(bf, "p", {"db/schema.sql": "select 1;\n"})
    monkeypatch.setenv("FAKE_SQLFLUFF", "red")
    row = _row(_main(bf, monkeypatch, capsys, "p", "--force"), "p")
    assert row.endswith("would seed baseline@0 (forced past sqlfluff red 3)")


# ── 4. --apply refuses red and unknown ─────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["red", "absent", "wrongversion", "usage"])
def test_apply_refuses_a_red_or_unknown_verdict(bf, monkeypatch, capsys, mode):
    proj = _repo(bf, "p", {"db/schema.sql": "select 1;\n"})
    monkeypatch.setenv("FAKE_SQLFLUFF", mode)
    out = _main(bf, monkeypatch, capsys, "p", "--apply", rc=1)
    verdict = _cells(_row(out, "p"))["sqlfluff"]
    assert _row(out, "p").endswith(f"REFUSED (sqlfluff {verdict}; --force overrides)")
    assert not (proj / "scripts").exists() and not (proj / ".fabrik").exists()
    cmd = f"git ls-files -z -- '*.sql' | xargs -0 uvx sqlfluff=={bf.SQLFLUFF_VERSION} lint"
    assert cmd in out and "--dialect postgres" in out


# ── 5. --force writes and records what it forced past ──────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "verdict"), [("red", "red 3"), ("absent", "unknown (no sqlfluff)")]
)
def test_force_writes_and_records_the_verdict(bf, monkeypatch, capsys, mode, verdict):
    proj = _repo(bf, "p", {"db/schema.sql": "select 1;\n"})
    monkeypatch.setenv("FAKE_SQLFLUFF", mode)
    row = _row(_main(bf, monkeypatch, capsys, "p", "--apply", "--force"), "p")
    assert row.endswith(f"WROTE +baseline@0 (forced past sqlfluff {verdict})")
    assert (proj / "scripts/ci_local.sh").exists()
    assert json.loads((proj / ".fabrik/lint-baseline.json").read_text()) == {"ruff_errors": 0}


# ── 6. the verdict grammar ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "verdict"),
    [
        ("clean", "clean"),
        ("red", "red 3"),
        ("absent", "unknown (no sqlfluff)"),
        ("wrongversion", "unknown (sqlfluff 3.0.0 != PIN)"),
        ("badjson", "unknown (unreadable lint output)"),
        ("usage", "unknown (lint failed, rc 2)"),
        ("slow", "unknown (timeout)"),
        ("warned", "red 1"),  # a rule the project configures as a warning does not red the run
        ("nonutf8", "clean"),  # undecodable output never crashes the run
    ],
)
def test_the_sqlfluff_verdict_grammar(bf, monkeypatch, mode, verdict):
    proj = _repo(bf, "p", {"db/a.sql": "select 1;\n", "db/sub/b.sql": "select 2;\n"})
    monkeypatch.setenv("FAKE_SQLFLUFF", mode)
    monkeypatch.setattr(bf, "SQLFLUFF_TIMEOUT_S", 1)
    got = bf._sqlfluff_verdict(proj, bf._tracked_sql(proj))
    assert got == verdict.replace("PIN", bf.SQLFLUFF_VERSION)
    if mode in ("clean", "red"):  # the replica's population: relative paths, run from the project
        (logged,) = (bf.TMP / "lint.log").read_text(encoding="utf-8").splitlines()
        assert logged.startswith(f"{proj} lint --dialect postgres --format json ")
        assert logged.split()[-2:] == ["db/a.sql", "db/sub/b.sql"]


def test_no_tracked_sql_is_never_probed(bf, monkeypatch):
    proj = _repo(bf, "p", {"README.md": "x\n"})
    monkeypatch.setattr(bf, "SQLFLUFF_PYTHON", "/nonexistent/python")
    assert bf._sqlfluff_verdict(proj, bf._tracked_sql(proj)) == "-"


def test_a_directory_that_is_not_a_git_repo_is_unknown(bf):
    proj = bf.OPT / "plain"
    proj.mkdir()
    (proj / "a.sql").write_text("select 1;\n", encoding="utf-8")
    assert bf._tracked_sql(proj) is None
    assert bf._sqlfluff_verdict(proj, None) == "unknown (no git)"


# ── 7. an existing marker is kept ──────────────────────────────────────────────────────────


def test_apply_keeps_an_existing_run_pytest_marker(bf, monkeypatch, capsys):
    reason = "# hand-written: this repo's suite must run in the gate (finding 01M15CJTSK)\n"
    proj = _repo(bf, "p", {".fabrik/run-pytest": reason})
    _main(bf, monkeypatch, capsys, "p", "--apply")
    assert (proj / ".fabrik/run-pytest").read_text(encoding="utf-8") == reason
    assert (proj / "scripts/ci_local.sh").exists()


def test_apply_keeps_an_existing_lint_baseline(bf, monkeypatch, capsys, tmp_path):
    hand = '{"ruff_errors": 0, "ruff_version": "0.15.12"}\n'
    proj = _repo(bf, "p", {".fabrik/lint-baseline.json": hand})
    monkeypatch.setattr(bf, "_ruff_count", lambda p: 57)
    dry = _row(_main(bf, monkeypatch, capsys, "p"), "p")
    assert dry.endswith("would keep its baseline")
    row = _row(_main(bf, monkeypatch, capsys, "p", "--apply"), "p")
    assert row.endswith("WROTE (kept its baseline)")
    assert (proj / ".fabrik/lint-baseline.json").read_text(encoding="utf-8") == hand


# ── write safety: nothing is written through a symlink, and a failed write is retried ──────


def test_a_symlink_or_directory_at_ci_local_sh_is_skipped(bf, monkeypatch, capsys, tmp_path):
    outside = tmp_path / "outside-ci.sh"
    proj = _repo(bf, "p", {"README.md": "x\n"})
    (proj / "scripts").mkdir()
    (proj / "scripts/ci_local.sh").symlink_to(outside)  # dangling
    q = _repo(bf, "q", {"README.md": "x\n"})
    (q / "scripts/ci_local.sh").mkdir(parents=True)
    out = _main(bf, monkeypatch, capsys, "p", "q", "--apply")
    assert _row(out, "p").endswith("already has CI (not fabrik-managed)")
    assert _row(out, "q").endswith("already has CI (not fabrik-managed)")
    assert not outside.exists()


def test_a_symlinked_marker_fails_the_project_before_any_write(bf, monkeypatch, capsys, tmp_path):
    """Following it writes outside; skipping it leaves a marker the gate's `.exists()` reads as
    absent — so the project fails, loudly, with nothing written."""
    outside = tmp_path / "outside-marker"
    proj = _repo(bf, "p", {"README.md": "x\n"})
    (proj / ".fabrik").mkdir()
    (proj / ".fabrik/run-pytest").symlink_to(outside)  # dangling
    out = _main(bf, monkeypatch, capsys, "p", "--apply", rc=1)
    assert _row(out, "p").endswith("FAILED (OSError: symlink at .fabrik/run-pytest)")
    assert not outside.exists()
    assert not (proj / "scripts").exists()


@pytest.mark.parametrize("linked", ["scripts", ".fabrik"])
def test_a_symlinked_parent_directory_fails_the_project(bf, monkeypatch, capsys, tmp_path, linked):
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    proj = _repo(bf, "p", {"README.md": "x\n"})
    (proj / linked).symlink_to(outside)
    out = _main(bf, monkeypatch, capsys, "p", "--apply", rc=1)
    assert _row(out, "p").endswith(f"FAILED (OSError: symlink at {linked})")
    assert list(outside.iterdir()) == []


def test_a_dry_run_names_the_symlink_the_apply_will_fail_on(bf, monkeypatch, capsys, tmp_path):
    proj = _repo(bf, "p", {"README.md": "x\n"})
    (proj / ".fabrik").mkdir()
    (proj / ".fabrik/run-pytest").symlink_to(tmp_path / "gone")  # dangling
    row = _row(_main(bf, monkeypatch, capsys, "p"), "p")
    assert row.endswith("would FAIL (symlink at .fabrik/run-pytest)")


def test_a_live_symlinked_baseline_inside_the_project_is_kept(bf, monkeypatch, capsys):
    proj = _repo(bf, "p", {"shared/baseline.json": '{"ruff_errors": 4}\n'})
    (proj / ".fabrik").mkdir()
    (proj / ".fabrik/lint-baseline.json").symlink_to(proj / "shared/baseline.json")
    assert _row(_main(bf, monkeypatch, capsys, "p"), "p").endswith("would keep its baseline")
    row = _row(_main(bf, monkeypatch, capsys, "p", "--apply"), "p")
    assert row.endswith("WROTE (kept its baseline)")
    assert (proj / ".fabrik/lint-baseline.json").is_symlink()
    assert (proj / "shared/baseline.json").read_text(encoding="utf-8") == '{"ruff_errors": 4}\n'


def test_a_leftover_temp_symlink_is_never_followed(bf, monkeypatch, capsys, tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep\n", encoding="utf-8")
    proj = _repo(bf, "p", {"README.md": "x\n"})
    (proj / "scripts").mkdir()
    (proj / "scripts/.ci_local.sh.backfill-tmp").symlink_to(victim)
    _main(bf, monkeypatch, capsys, "p", "--apply")
    assert victim.read_text(encoding="utf-8") == "keep\n"
    ci_local = proj / "scripts/ci_local.sh"
    assert ci_local.is_file() and not ci_local.is_symlink()


def test_a_failed_chmod_leaves_no_ci_local_sh(bf, monkeypatch, capsys):
    proj = _repo(bf, "p", {"README.md": "x\n"})
    real_chmod = Path.chmod

    def chmod(self, mode, *a, **k):
        if self.name.endswith(".backfill-tmp"):
            raise PermissionError(1, "Operation not permitted")
        return real_chmod(self, mode, *a, **k)

    monkeypatch.setattr(Path, "chmod", chmod)
    out = _main(bf, monkeypatch, capsys, "p", "--apply", rc=1)
    assert "FAILED (PermissionError" in _row(out, "p")
    assert not (proj / "scripts/ci_local.sh").exists()
    assert sorted(p.name for p in (proj / "scripts").iterdir()) == []  # no temp file left


def test_a_project_that_is_not_found_fails_an_apply(bf, monkeypatch, capsys):
    out = _main(bf, monkeypatch, capsys, "nosuch", "--apply", rc=1)
    assert _row(out, "nosuch").endswith("not found")
    _main(bf, monkeypatch, capsys, "nosuch")  # a dry run still exits 0


def test_a_dry_run_with_no_ruff_count_says_so(bf, monkeypatch, capsys):
    _repo(bf, "p", {"README.md": "x\n"})
    monkeypatch.setattr(bf, "_ruff_count", lambda p: None)
    assert _row(_main(bf, monkeypatch, capsys, "p"), "p").endswith("would write (no ruff)")


def test_a_sqlfluff_interpreter_that_cannot_start_reads_no_sqlfluff(bf, monkeypatch):
    proj = _repo(bf, "p", {"db/a.sql": "select 1;\n"})
    monkeypatch.setattr(bf, "SQLFLUFF_PYTHON", str(bf.TMP / "no-such-python"))
    assert bf._sqlfluff_verdict(proj, bf._tracked_sql(proj)) == "unknown (no sqlfluff)"


def test_a_failed_write_leaves_no_ci_local_sh_and_the_batch_goes_on(bf, monkeypatch, capsys):
    bad = _repo(bf, "bad", {".fabrik": "a file where a directory must go\n"})
    good = _repo(bf, "good", {"README.md": "x\n"})
    out = _main(bf, monkeypatch, capsys, "bad", "good", "--apply", rc=1)
    assert _row(out, "bad").startswith("bad") and "FAILED" in _row(out, "bad")
    assert not (bad / "scripts/ci_local.sh").exists()  # written last, so the next run retries
    assert "WROTE" in _row(out, "good") and (good / "scripts/ci_local.sh").exists()


def test_an_argv_the_os_refuses_reads_unknown_not_missing_sqlfluff(bf, monkeypatch):
    proj = _repo(bf, "p", {"db/a.sql": "select 1;\n"})
    real_run = subprocess.run

    def run(cmd, *a, **k):
        if "lint" in cmd:
            raise OSError(7, "Argument list too long")
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(bf.subprocess, "run", run)
    got = bf._sqlfluff_verdict(proj, bf._tracked_sql(proj))
    assert got == "unknown (lint not run: Argument list too long)"


def test_a_version_probe_that_hangs_reads_timeout(bf, monkeypatch):
    proj = _repo(bf, "p", {"db/a.sql": "select 1;\n"})

    def run(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr(bf.subprocess, "run", run)
    assert bf._sqlfluff_verdict(proj, ["db/a.sql"]) == "unknown (timeout)"


def test_the_lint_summary_is_valid_json_for_the_fake(bf):
    """Guard on the fixture itself: the red fake's JSON holds three violations."""
    red = FAKE.split("red) echo '")[1].split("'; exit 1")[0]
    assert sum(len(f["violations"]) for f in json.loads(red)) == 3
