"""Graders for scripts/lane_replay_capture.py and the replay fixture it writes (plan T01).

The capture is exercised on scratch git repos built under ``tmp_path`` — never on the live
``/opt`` repos. The last block reads the COMMITTED fixture file only (no git), so it pins the
shape T02's replay test consumes: the commit counts per repo, the closed verdict set, the wef1
commit and the task rows' historical handoffs.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lane_replay_capture.py"
FIXTURE = ROOT / "tests" / "fixtures" / "lane_replay.json"
TASKS = ROOT / "tests" / "fixtures" / "lane_replay_tasks.json"

VERDICTS = {"lane", "lane: full-review", "chain: contract", "chain: new-source"}
SYNC_REGEX = r"(^templates/governance/|^scripts/enforcement/)"


def _load():
    spec = importlib.util.spec_from_file_location("lane_replay_capture", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.com",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.com",
    )
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=_git_env()
    ).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _commit(repo: Path, msg: str, *paths: str) -> str:
    if paths:
        _git(repo, "add", "--", *paths)
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


BIG = "".join(f"line {i} of a long enough body to detect copies and renames\n" for i in range(40))


@pytest.fixture()
def scratch(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "master", str(repo)], check=True, env=_git_env())
    _write(
        repo,
        ".pre-commit-config.yaml",
        (
            "repos:\n  - repo: local\n    hooks:\n      - id: other\n        files: '^nope$'\n"
            "      - id: governance-sync\n        name: Sync\n"
            f"        files: '{SYNC_REGEX}'\n        pass_filenames: false\n"
        ),
    )
    _write(repo, "src/a.py", BIG)
    _commit(repo, "c1 root", ".pre-commit-config.yaml", "src/a.py")
    _write(repo, "src/b.py", "b\n")
    _write(repo, "src/c.py", "c\n")
    _write(repo, "src/d.py", "d\n")
    _commit(repo, "c2 three new sources", "src/b.py", "src/c.py", "src/d.py")
    _git(repo, "mv", "src/b.py", "src/b2.py")
    _commit(repo, "c3 rename")  # `git mv` already staged both halves
    _write(repo, "src/a.py", BIG + "tail\n")
    _write(repo, "src/a_copy.py", BIG)
    _commit(repo, "c4 copy", "src/a.py", "src/a_copy.py")
    _git(repo, "checkout", "-q", "-b", "side")
    _write(repo, "docs/x.md", "x\n")
    _commit(repo, "c5 side docs", "docs/x.md")
    _git(repo, "checkout", "-q", "master")
    _write(repo, "specs/services/svc.yaml", "id: svc\n")
    _commit(repo, "c6 contract", "specs/services/svc.yaml")
    _git(repo, "merge", "-q", "--no-ff", "-m", "m1 merge", "side")
    _write(repo, "templates/governance/CLAUDE.md", "g\n")
    _commit(repo, "c7 sync", "templates/governance/CLAUDE.md")
    return repo


def _plan(repo: Path, n: int, kind: str = "hub") -> dict:
    end = _git(repo, "rev-parse", "HEAD")
    return {
        "sync": {"repo": str(repo), "rev": end},
        "sources": [{"name": "scratch", "path": str(repo), "kind": kind, "end": end, "n": n}],
        "extras": [],
    }


# ── Behavior row 1: the capture holds exactly N non-merge commits with -M -C letters ────


def test_capture_takes_exactly_n_non_merge_commits_newest_first(scratch: Path) -> None:
    mod = _load()
    fx = mod.capture(_plan(scratch, 3))
    shas = [c["sha"] for c in fx["commits"]]
    assert len(shas) == 3
    subjects = [_git(scratch, "log", "-1", "--format=%s", s) for s in shas]
    assert subjects == ["c7 sync", "c6 contract", "c5 side docs"]  # merge m1 skipped


def test_capture_takes_the_whole_history_when_shorter_than_n(scratch: Path) -> None:
    mod = _load()
    fx = mod.capture(_plan(scratch, 200))
    assert len(fx["commits"]) == 7  # 8 commits, one merge


def test_capture_records_rename_and_copy_letters_with_old_paths(scratch: Path) -> None:
    mod = _load()
    fx = mod.capture(_plan(scratch, 200))
    by_subject = {
        _git(scratch, "log", "-1", "--format=%s", c["sha"]): c["rows"] for c in fx["commits"]
    }
    assert ["R", "src/b2.py", "src/b.py"] in by_subject["c3 rename"]
    assert ["C", "src/a_copy.py", "src/a.py"] in by_subject["c4 copy"]
    assert sorted(by_subject["c2 three new sources"]) == [
        ["A", "src/b.py", None],
        ["A", "src/c.py", None],
        ["A", "src/d.py", None],
    ]
    # the root commit is diffed against the empty tree
    assert ["A", "src/a.py", None] in by_subject["c1 root"]


def test_capture_pins_expected_verdicts_from_the_rows(scratch: Path) -> None:
    mod = _load()
    fx = mod.capture(_plan(scratch, 200))
    got = {
        _git(scratch, "log", "-1", "--format=%s", c["sha"]): c["expected"] for c in fx["commits"]
    }
    assert got["c2 three new sources"] == "chain: new-source"
    assert got["c6 contract"] == "chain: contract"
    # a hub commit whose only path is a sync-regex .md: the sync check precedes docs-only (T01-S2)
    assert got["c7 sync"] == "lane: full-review"
    assert got["c5 side docs"] == "lane"  # docs-only, no sync path
    assert got["c3 rename"] == "lane"
    assert got["c4 copy"] == "lane"
    assert set(got.values()) <= VERDICTS


def test_header_records_the_sync_regex_and_the_commit_it_was_read_at(scratch: Path) -> None:
    mod = _load()
    plan = _plan(scratch, 2)
    fx = mod.capture(plan)
    assert fx["header"]["sync_regex"] == SYNC_REGEX
    assert fx["header"]["sync_regex_commit"] == plan["sync"]["rev"]
    assert fx["header"]["sync_regex_source"].startswith(".pre-commit-config.yaml:")
    assert "chain: contract" in fx["header"]["rule"]


def test_a_merge_commit_extra_is_refused_naming_its_sha(scratch: Path, tmp_path: Path) -> None:
    # T01-S1: git log emits no diff rows for a merge, which would pin `rows: []` -> "lane"
    mod = _load()
    merge = _git(scratch, "rev-parse", "HEAD~1")
    assert _git(scratch, "log", "-1", "--format=%s", merge) == "m1 merge"
    plan = _plan(scratch, 2)
    plan["extras"] = [
        {"label": "m", "name": "scratch", "path": str(scratch), "kind": "project", "sha": merge}
    ]
    with pytest.raises(SystemExit) as exc:
        mod.capture(plan)
    assert merge in str(exc.value)
    plan_path = tmp_path / "merge-plan.json"
    plan_path.write_text(json.dumps(plan))
    r = _cli("--plan", str(plan_path), "--out", str(tmp_path / "never.json"))
    assert r.returncode != 0
    assert merge in r.stdout + r.stderr
    assert not (tmp_path / "never.json").exists()


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=_git_env()
    )


def test_check_rederives_the_same_rows_and_fails_on_any_difference(
    scratch: Path, tmp_path: Path
) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan(scratch, 5)))
    out = tmp_path / "fx.json"
    r = _cli("--plan", str(plan_path), "--out", str(out))
    assert r.returncode == 0, r.stderr
    ok = _cli("--check", str(out))
    assert ok.returncode == 0, ok.stdout + ok.stderr

    # a later commit past the recorded end changes nothing
    _write(scratch, "src/z.py", "z\n")
    _commit(scratch, "c8 later", "src/z.py")
    assert _cli("--check", str(out)).returncode == 0

    fx = json.loads(out.read_text())
    fx["commits"][0]["rows"][0][0] = "M" if fx["commits"][0]["rows"][0][0] != "M" else "A"
    bad = tmp_path / "bad_rows.json"
    bad.write_text(json.dumps(fx))
    r_bad = _cli("--check", str(bad))
    assert r_bad.returncode != 0
    assert "differ" in (r_bad.stdout + r_bad.stderr)

    fx = json.loads(out.read_text())
    assert fx["commits"][1]["expected"] == "chain: contract"  # c6
    fx["commits"][1]["expected"] = "lane"
    bad2 = tmp_path / "bad_verdict.json"
    bad2.write_text(json.dumps(fx))
    assert _cli("--check", str(bad2)).returncode != 0

    fx = json.loads(out.read_text())
    fx["commits"].pop()
    bad3 = tmp_path / "bad_count.json"
    bad3.write_text(json.dumps(fx))
    assert _cli("--check", str(bad3)).returncode != 0


# ── Behavior row 2: the verdict rule (closed set; T02's contract rule) ─────────────────


@pytest.mark.parametrize(
    ("rows", "kind", "want"),
    [
        ([("M", "specs/services/x.yaml", None)], "project", "chain: contract"),
        ([("M", "api/openapi.yaml", None)], "project", "chain: contract"),
        ([("M", "api/openapi-v2.json", None)], "project", "chain: contract"),
        ([("M", "web/x.schema.json", None)], "project", "chain: contract"),
        ([("M", "api/OpenAPI.yaml", None)], "project", "chain: contract"),
        ([("M", "web/X.Schema.JSON", None)], "project", "chain: contract"),
        ([("M", "api/openapi.yml", None)], "project", "chain: contract"),
        ([("M", "x.schema.json.bak", None)], "project", "lane"),
        ([("M", "apps/x/specs/services/y.yaml", None)], "project", "chain: contract"),
        ([("M", "node_modules/p/openapi.json", None)], "project", "lane"),
        ([("M", "a/.venv/b/x.schema.json", None)], "project", "lane"),
        ([("M", "vendor/openapi.yaml", None)], "project", "lane"),
        ([("M", "myvendor/openapi.yaml", None)], "project", "chain: contract"),
        ([("M", "node_modules_old/openapi.yaml", None)], "project", "chain: contract"),
        (
            [("A", "src/a.py", None), ("A", "src/b.py", None), ("C", "src/c.py", "src/a.py")],
            "project",
            "chain: new-source",
        ),
        (
            [
                ("A", "src/a.py", None),
                ("A", "src/b.py", None),
                ("A", "tests/test_c.py", None),
                ("A", "docs/c.md", None),
                ("A", "pkg/test_d.py", None),
            ],
            "project",
            "lane",
        ),
        ([("R", "src/b2.py", "src/b.py"), ("M", "src/c.py", None)], "project", "lane"),
        ([("M", "templates/governance/x.py", None)], "hub", "lane: full-review"),
        ([("M", "templates/governance/x.py", None)], "project", "lane"),
        ([("A", "web/db/migrations/0001.sql", None)], "project", "lane: full-review"),
        ([("M", "alembic/versions/abc.py", None)], "project", "lane: full-review"),
        ([("M", f"src/m{i}.py", None) for i in range(6)], "project", "lane: full-review"),
        ([("M", f"src/m{i}.py", None) for i in range(5)], "project", "lane"),
        (
            [("M", f"src/m{i}.py", None) for i in range(5)]
            + [("M", "CHANGELOG.md", None), ("M", "docs/reference/x.md", None)],
            "project",
            "lane",
        ),
        ([("M", f"docs/d{i}.md", None) for i in range(8)], "project", "lane"),
        ([("M", "README.md", None), ("A", ".fabrik/work/W-1.json", None)], "hub", "lane"),
        ([("M", "templates/governance/CLAUDE.md", None)], "hub", "lane: full-review"),
        ([("M", "templates/governance/CLAUDE.md", None)], "project", "lane"),
        (
            [("A", "specs/services/x.yaml", None)] + [("A", f"s/{i}.py", None) for i in range(3)],
            "project",
            "chain: contract",
        ),
    ],
)
def test_expected_verdict_rule(rows: list, kind: str, want: str) -> None:
    mod = _load()
    assert mod.expected_verdict(rows, kind=kind, sync_regex=SYNC_REGEX) == want


# ── The committed fixture (file read only, no git) ─────────────────────────────────────


def _fixture() -> dict:
    return _load().load(FIXTURE)


def test_fixture_fits_the_large_file_limit() -> None:
    # .pre-commit-config.yaml's check-added-large-files refuses an added file over 500 KB
    assert FIXTURE.stat().st_size <= 500 * 1024


def test_fixture_holds_300_hub_and_200_per_project_commits() -> None:
    fx = _fixture()
    counts: dict[str, int] = {}
    for c in fx["commits"]:
        counts[c["repo"]] = counts.get(c["repo"], 0) + 1
    assert counts == {
        "fabrik": 300,
        "web-ecommerce-factory": 200,
        "trade-intelligence": 200,
        "tojlo-mail": 137,
        "seo": 200,
    }
    hub = next(s for s in fx["header"]["sources"] if s["name"] == "fabrik")
    assert hub["end"] == "c84f0b0b79e62e230e71c6e99eadd6e7c8d1f8f6"
    assert hub["kind"] == "hub"
    assert fx["commits"][0]["sha"] == hub["end"]
    for s in fx["header"]["sources"]:
        assert len(s["end"]) == 40
        if s["name"] != "fabrik":
            assert s["kind"] == "project"


def test_fixture_verdicts_are_the_closed_set_and_wef1_is_lane() -> None:
    fx = _fixture()
    for c in fx["commits"] + fx["extras"]:
        assert c["expected"] in VERDICTS, c["sha"]
        assert c["kind"] in {"hub", "project"}
        for st, path, old in c["rows"]:
            assert st in {"A", "C", "D", "M", "R", "T"}
            assert (old is not None) == (st in {"R", "C"}), (c["sha"], path)
    wef1 = [e for e in fx["extras"] if e["label"] == "wef1"]
    assert len(wef1) == 1
    assert wef1[0]["sha"] == "0e89dcb67641ca0131e7b9d0b8177ee44671154c"
    assert wef1[0]["expected"] == "lane"
    assert "sync_regex" in fx["header"] and fx["header"]["sync_regex_commit"]


def test_task_rows_keep_the_historical_handoff_verdicts() -> None:
    tasks = json.loads(TASKS.read_text())
    rows = tasks["rows"]
    assert len(rows) == 21
    non_file_handoffs = [r for r in rows if r["state"] == "handoff" and r["upgrade"] != "files"]
    assert [(r["upgrade"], r["expected"]) for r in non_file_handoffs] == [
        ("tradeoffs", "chain: tradeoffs"),
        (None, "not-a-lane-verdict"),
    ]
    wef1 = [r for r in rows if r["repo"] == "wef1"]
    assert [r["expected"] for r in wef1] == ["lane"]


# ── T08-D7 C-O7: a missing or unreadable fixture is the documented failure, never a traceback ──


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_c_o7_check_reports_an_unreadable_fixture_and_exits_1(tmp_path, capsys, kind) -> None:
    mod = _load()
    path = tmp_path / "fx.json"
    if kind == "directory":
        path.mkdir()
    assert mod.check(path) == 1
    out = capsys.readouterr().out
    assert "fixture and re-derivation differ — unreadable" in out, out
