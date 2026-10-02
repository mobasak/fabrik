"""Graders for the admission half of ``scripts/task_lane.py`` (plan T02; spec D1, D2, D4, D7, D9, D12).

One test per Behavior Contract row of the ticket, plus the path helpers the close (T03a) reuses.
``lane_version`` runs against scratch git repos under ``tmp_path`` — never a live ``/opt`` repo.
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


def _module():
    name = "task_lane"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "task_lane.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


def _declared(**over: str) -> dict[str, str]:
    base = {
        "decision": "yes",
        "heavy": "no",
        "mechanism": "no",
        "oneway": "no",
        "tradeoffs": "no",
        "consumers": "internal",
    }
    base.update(over)
    return base


def _admit(files, *, version=2, sync_hits=frozenset(), appetite=None, why=None, **declare):
    return _module().admit(
        _declared(**declare),
        list(files),
        sync_hits=set(sync_hits),
        appetite=appetite,
        why=why,
        version=version,
    )


# ── V1 / D2: the file count no longer refuses; more than 5 files selects the full review ──


def test_six_existing_files_and_two_new_sources_are_admitted_with_the_full_review():
    files = [f"src/mod{i}.py" for i in range(6)] + ["src/new_a.py", "src/new_b.py"]
    v = _admit(files)
    assert (v.route, v.review) == ("lane", "full"), v


def test_four_files_are_admitted_with_the_scoped_review():
    v = _admit(["src/a.py", "src/b.py", "src/c.py", "tests/test_a.py"])
    assert (v.route, v.review) == ("lane", "scoped"), v


# ── D1: the contract path test and the consumers declaration ─────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "specs/services/x.yaml",
        "api/openapi.yaml",
        "api/openapi-v2.json",
        "web/x.schema.json",
        "api/OpenAPI.yaml",
        "web/X.Schema.JSON",
        "myvendor/openapi.yaml",
        "node_modules_old/x.schema.json",
        "api/openapi.yml",
        "apps/x/specs/services/y.yaml",
    ],
)
def test_a_contract_path_routes_to_the_chain(path):
    tl = _module()
    assert tl.contract_hit(path)
    v = _admit(["src/a.py", path])
    assert v.route == "chain: contract", v
    assert path in v.reason


@pytest.mark.parametrize(
    "path",
    [
        "node_modules/pkg/openapi.yaml",
        "web/node_modules/x.schema.json",
        ".venv/lib/specs/services/x.yaml",
        "vendor/openapi.json",
        "a/vendor/b/openapi-v1.yaml",
        "x.schema.json.bak",
        "myvendor/readme.txt",
        "node_modules_old/index.js",
    ],
)
def test_a_non_contract_path_is_not_a_hit(path):
    tl = _module()
    assert not tl.contract_hit(path)
    assert _admit(["src/a.py", path]).route == "lane"


def test_consumers_external_routes_to_the_chain_and_internal_never_removes_a_path_hit():
    assert _admit(["src/a.py"], consumers="external").route == "chain: contract"
    assert _admit(["specs/services/x.yaml"], consumers="internal").route == "chain: contract"


# ── D9: --why and the refusal ledger ─────────────────────────────────────────────────────


@pytest.mark.parametrize("key", ["oneway", "tradeoffs"])
def test_oneway_or_tradeoffs_without_why_is_refused_naming_the_reason(key):
    for why in (None, "", "   "):
        v = _admit(["src/a.py"], why=why, **{key: "yes"})
        assert v.route == "refused", v
        assert "--why" in v.reason and f"{key}=yes" in v.reason


@pytest.mark.parametrize("key", ["oneway", "tradeoffs"])
def test_with_why_the_route_is_chain_and_the_refusal_is_ledgered(tmp_path, key):
    tl = _module()
    v = _admit(["src/a.py", "src/b.py"], why="A vs B", **{key: "yes"})
    assert v.route == f"chain: {key}", v
    ledger = tmp_path / "state" / "lane-refusals.jsonl"
    row = {
        "repo": "/opt/x/.git",
        "session": "s-1",
        "declared": _declared(**{key: "yes"}),
        "why": "A vs B",
        "files": ["src/a.py", "src/b.py"],
        "refusal": f"REFUSED — fabrik-task: {v.reason}",
    }
    rid = tl.record_refusal(ledger, row)
    lines = ledger.read_text().splitlines()
    assert len(lines) == 1
    got = json.loads(lines[0])
    assert got["id"] == rid and rid
    assert got["repo"] == "/opt/x/.git"
    assert got["declared"][key] == "yes"
    assert got["why"] == "A vs B"
    assert got["files"] == ["src/a.py", "src/b.py"]
    assert isinstance(got["ts"], float)
    second = tl.record_refusal(ledger, row)
    assert second != rid and len(ledger.read_text().splitlines()) == 2


# ── D1/D4: the appetite ──────────────────────────────────────────────────────────────────


def test_appetite_default_and_240_are_admitted_and_241_routes_to_the_chain():
    assert _admit(["src/a.py"], appetite=None).route == "lane"
    assert _admit(["src/a.py"], appetite=240).route == "lane"
    assert _module().APPETITE_DEFAULT == 240
    v = _admit(["src/a.py"], appetite=241)
    assert v.route == "chain: appetite", v


@pytest.mark.parametrize("bad", [0, -5, "60", 1.5, True, "soon"])
def test_a_non_positive_or_non_integer_appetite_is_refused_naming_the_flag(bad):
    v = _admit(["src/a.py"], appetite=bad)
    assert v.route == "refused", v
    assert "--appetite" in v.reason


# ── D2 / D7: heavy surfaces keep the lane with the full review; v1 keeps today's routes ──


@pytest.mark.parametrize(
    "case",
    [
        {"sync_hits": {"scripts/command_run.py"}, "files": ["scripts/command_run.py"]},
        {"heavy": "yes", "files": ["src/auth.py"]},
        {"files": ["web/db/migrations/0001_init.sql"]},
        {"files": ["apps/web/prisma/migrations/x/migration.sql"]},
        {"files": ["alembic/versions/abc_add.py"]},
        {"files": ["src/app/alembic/versions/abc_add.py"]},
    ],
)
def test_version_2_sends_sync_heavy_and_migration_work_to_the_lane_with_the_full_review(case):
    case = dict(case)
    files = case.pop("files")
    v = _admit(files, **case)
    assert (v.route, v.review) == ("lane", "full"), v


def test_a_dependency_or_lookalike_migration_path_is_not_a_migration():
    tl = _module()
    assert not tl.is_migration("node_modules/pkg/migrations/0001.js")
    assert not tl.is_migration("src/mymigrations/x.py")
    assert not tl.is_migration("alembic/env.py")
    assert tl.is_migration("migrations/0001.py")


def test_version_1_keeps_todays_dispositions():
    v = _admit(["scripts/command_run.py"], version=1, sync_hits={"scripts/command_run.py"})
    assert (v.route, v.review) == ("right-now + /fabrik-review", "full"), v
    v = _admit(["src/auth.py"], version=1, heavy="yes")
    assert (v.route, v.review) == ("right-now + /fabrik-review", "full"), v
    v = _admit(["src/a.py", "src/b.py", "src/c.py", "src/d.py"], version=1)
    assert v.route == "chain: files" and v.reason == "files > 3", v
    # version 1 has no contract test, no appetite and no --why: today's gate verbatim
    assert _admit(["specs/services/x.yaml"], version=1).route == "lane"
    assert _admit(["src/a.py"], version=1, appetite=999).route == "lane"
    assert _admit(["src/a.py"], version=1, tradeoffs="yes").route == "chain: tradeoffs"


@pytest.mark.parametrize("version", [1, 2])
def test_decision_no_keeps_the_right_now_scoped_route_at_both_versions(version):
    v = _admit(["src/a.py"], version=version, decision="no")
    assert (v.route, v.review) == ("right-now + /fabrik-review-scoped", "scoped"), v


def test_the_chain_takes_precedence_over_a_heavy_surface():
    v = _admit(["specs/services/x.yaml"], heavy="yes", sync_hits={"specs/services/x.yaml"})
    assert v.route == "chain: contract", v
    v = _admit(["src/a.py"], heavy="yes", tradeoffs="yes", why="A vs B")
    assert v.route == "chain: tradeoffs", v


# ── the path helper the close reuses ─────────────────────────────────────────────────────


def test_is_new_source_counts_added_or_copied_non_test_non_doc_files_only():
    tl = _module()
    assert tl.is_new_source("A", "src/new.py")
    assert tl.is_new_source("C", "src/copy.py")
    assert not tl.is_new_source("M", "src/old.py")
    assert not tl.is_new_source("R", "src/moved.py")
    assert not tl.is_new_source("A", "tests/test_new.py")
    assert not tl.is_new_source("A", "pkg/test_util.py")
    assert not tl.is_new_source("A", "docs/guide.md")
    assert not tl.is_new_source("A", ".fabrik/work/W-1.json")


# ── D12: the repo-owned switch ───────────────────────────────────────────────────────────


def _git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("x\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _switch(repo: Path, text: str) -> None:
    (repo / ".fabrik").mkdir(exist_ok=True)
    (repo / ".fabrik" / "lane.json").write_text(text)


def test_no_switch_file_returns_the_default(tmp_path):
    tl = _module()
    assert tl._LANE_DEFAULT == 1
    assert tl.lane_version(_repo(tmp_path)) == (1, None, None)


def test_a_committed_version_2_returns_2_and_the_commit_that_set_it(tmp_path):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": 2}\n')
    _git(repo, "add", ".fabrik/lane.json")
    _git(repo, "commit", "-q", "-m", "lane v2")
    set_by = _git(repo, "rev-parse", "HEAD")
    (repo / "other.txt").write_text("later\n")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-q", "-m", "later")
    assert tl.lane_version(repo) == (2, set_by, None)
    # edited after the commit: the working version is no longer the committed one
    _switch(repo, '{"version": 1}\n')
    assert tl.lane_version(repo) == (1, None, None)


@pytest.mark.parametrize(
    "text", ["{not json", '{"version": 3}', '{"version": "2"}', "[2]", '{"version": true}']
)
def test_an_invalid_switch_returns_1_with_a_warning_naming_the_file(tmp_path, text):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, text)
    version, commit, warning = tl.lane_version(repo)
    assert (version, commit) == (1, None)
    assert warning and ".fabrik/lane.json" in warning


def test_an_uncommitted_switch_returns_its_version_with_no_commit(tmp_path):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": 2}\n')
    assert tl.lane_version(repo) == (2, None, None)


# ── Round-1 review fixes (T02-O1 … O19, H1, H2, S1, S4) ──────────────────────────────────

_SYNC = r"(^templates/governance/|^scripts/command_run\.py$)"


def _classify(rows, kind="project", regex=_SYNC):
    return _module().classify_commit(rows, repo_kind=kind, sync_regex=regex)


def _capture():
    name = "lane_replay_capture"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


@pytest.mark.parametrize("sep", [" ", " ", "\u0085"])
def test_a_unicode_line_separator_in_why_keeps_one_parseable_ledger_line(tmp_path, sep):
    ledger = tmp_path / "lane-refusals.jsonl"
    _module().record_refusal(ledger, {"why": f"A B vs C{sep}D"})
    pieces = ledger.read_text(encoding="utf-8").splitlines()
    assert len(pieces) == 1
    assert json.loads(pieces[0])["why"] == f"A B vs C{sep}D"


def test_a_lone_surrogate_in_why_is_still_ledgered(tmp_path):
    ledger = tmp_path / "lane-refusals.jsonl"
    why = b"bad\xff".decode("utf-8", "surrogateescape")
    rid = _module().record_refusal(ledger, {"why": why})
    (line,) = ledger.read_text(encoding="utf-8").splitlines()
    got = json.loads(line)
    assert got["id"] == rid and got["why"] == why


def test_record_refusal_ignores_a_caller_supplied_id_and_ts(tmp_path):
    ledger = tmp_path / "lane-refusals.jsonl"
    tl = _module()
    a = tl.record_refusal(ledger, {"id": "X", "ts": None})
    b = tl.record_refusal(ledger, {"id": "X", "ts": 1.0})
    rows = [json.loads(x) for x in ledger.read_text().splitlines()]
    assert a != "X" and b != "X" and a != b
    assert [r["id"] for r in rows] == [a, b]
    assert all(isinstance(r["ts"], float) and r["ts"] > 1.0 for r in rows)


def test_new_source_excludes_only_fabrik_work_like_the_measurement_rule():
    tl = _module()
    assert tl.is_new_source("A", ".fabrik/plan-locks/a.json")
    assert not tl.is_new_source("A", ".fabrik/work/W-1.json")
    rows = [("M", "src/a.py", None)] + [("A", f".fabrik/plan-locks/{c}.json", None) for c in "abc"]
    assert _classify(rows) == "chain: new-source"
    assert _capture().expected_verdict(rows, kind="project", sync_regex=_SYNC) == _classify(rows)


@pytest.mark.parametrize(
    "path",
    [
        "tests/x.py",
        "web/tests/c.py",
        "pkg/test/helper.py",
        "web/src/__tests__/a.ts",
        "pkg/test_util.py",
        "web/src/a.test.ts",
        "go/pkg/a_test.go",
        "web/src/b.spec.ts",
    ],
)
def test_a_test_path_at_any_depth_is_not_new_source(path):
    tl = _module()
    assert tl.is_test(path)
    assert not tl.is_new_source("A", path)


@pytest.mark.parametrize(
    "path", ["src/contest.py", "src/attest/x.py", "src/testing.py", "spec/x.rb"]
)
def test_a_lookalike_is_not_a_test(path):
    assert not _module().is_test(path)


def test_nested_test_files_do_not_route_a_commit_to_new_source():
    rows = [
        ("A", "web/src/a.test.ts", None),
        ("A", "web/src/b.test.ts", None),
        ("A", "web/tests/c.py", None),
        ("M", "web/other.py", None),
    ]
    assert _classify(rows) == "lane"


def test_the_capture_has_no_rule_helpers_of_its_own():
    cap = _capture()
    for name in ("_is_test", "_is_contract", "_is_migration", "_is_excluded", "_in_dependency_dir"):
        assert not hasattr(cap, name), name


@pytest.mark.parametrize(("n", "review"), [(5, "scoped"), (6, "full")])
def test_more_than_five_files_is_the_full_review_boundary(n, review):
    v = _admit([f"src/m{i}.py" for i in range(n)])
    assert (v.route, v.review) == ("lane", review), v


def test_measurement_excluded_paths_do_not_count_towards_the_full_review():
    files = [
        "CHANGELOG.md",
        "docs/DECISIONS.md",
        "INDEX.md",
        ".fabrik/work/W.json",
        "src/a.py",
        "src/b.py",
    ]
    v = _admit(files)
    assert (v.route, v.review) == ("lane", "scoped"), v
    rows = [("M", p, None) for p in files[:4]] + [("A", p, None) for p in files[4:]]
    assert _classify(rows) == "lane"


def test_duplicate_files_count_once():
    v = _admit(["src/a.py"] * 6)
    assert (v.route, v.review) == ("lane", "scoped"), v
    assert _admit(["src/a.py"] * 4, version=1).route == "lane"


def test_version_1_oneway_routes_to_the_chain():
    assert _admit(["src/a.py"], version=1, oneway="yes").route == "chain: oneway"


@pytest.mark.parametrize(
    "case",
    [
        {"sync_hits": {"scripts/command_run.py"}, "files": ["scripts/command_run.py"]},
        {"heavy": "yes", "files": ["src/auth.py"]},
    ],
)
def test_version_1_sync_and_heavy_take_precedence_over_decision_no(case):
    case = dict(case)
    v = _admit(case.pop("files"), version=1, decision="no", **case)
    assert (v.route, v.review) == ("right-now + /fabrik-review", "full"), v


@pytest.mark.parametrize(
    "case",
    [
        {"sync_hits": {"scripts/command_run.py"}, "files": ["scripts/command_run.py"]},
        {"heavy": "yes", "files": ["src/auth.py"]},
        {"files": ["web/db/migrations/0001.sql"]},
    ],
)
def test_version_2_decision_no_on_a_heavy_surface_is_right_now_with_the_full_review(case):
    case = dict(case)
    v = _admit(case.pop("files"), decision="no", **case)
    assert (v.route, v.review) == ("right-now + /fabrik-review", "full"), v


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("consumers", "externl"),
        ("consumers", "External"),
        ("oneway", "Yes"),
        ("tradeoffs", "true"),
        ("heavy", "1"),
        ("decision", "nope"),
        ("mechanism", ""),
    ],
)
def test_version_2_refuses_an_invalid_declared_value_naming_the_key(key, value):
    v = _admit(["src/a.py"], **{key: value})
    assert v.route == "refused", v
    assert f"{key}={value}" in v.reason


@pytest.mark.parametrize(
    "key", ["consumers", "decision", "heavy", "mechanism", "oneway", "tradeoffs"]
)
def test_version_2_refuses_a_missing_declared_key_naming_it(key):
    declared = _declared()
    del declared[key]
    v = _module().admit(declared, ["src/a.py"], sync_hits=set(), appetite=None, why=None, version=2)
    assert v.route == "refused", v
    assert key in v.reason


def test_the_route_is_decided_before_the_why_check():
    assert _admit(["specs/services/x.yaml"], tradeoffs="yes").route == "chain: contract"
    assert _admit(["src/a.py"], consumers="external", oneway="yes").route == "chain: contract"
    assert _admit(["src/a.py"], appetite=300, tradeoffs="yes").route == "chain: appetite"
    v = _admit(["src/a.py"], heavy="yes", tradeoffs="yes")
    assert v.route == "refused" and "--why" in v.reason, v


@pytest.mark.parametrize(
    ("rows", "kind", "want"),
    [
        ([("R", "api/old_spec.yaml", "api/openapi.yaml")], "project", "chain: contract"),
        ([("C", "src/x.json", "specs/services/x.yaml")], "project", "chain: contract"),
        ([("R", "scripts/old_run.py", "scripts/command_run.py")], "hub", "lane: full-review"),
        ([("R", "db/0001.sql", "db/migrations/0001.sql")], "project", "lane: full-review"),
        ([("R", "docs/old.md", "templates/governance/x.md")], "hub", "lane: full-review"),
    ],
)
def test_rename_and_copy_rows_test_the_old_path_too(rows, kind, want):
    assert _classify(rows, kind) == want


def test_an_empty_sync_regex_matches_nothing():
    assert _classify([("M", "docs/CAPABILITIES.md", None)], "hub", "") == "lane"
    assert _classify([("M", "src/a.py", None)], "hub", "") == "lane"


@pytest.mark.parametrize(
    "path", ["Vendor/openapi.yaml", "NODE_MODULES/x.schema.json", "a/.VENV/openapi.json"]
)
def test_dependency_segments_match_case_insensitively(path):
    assert not _module().contract_hit(path)


@pytest.mark.parametrize("path", ["db/Migrations/1.sql", "Alembic/Versions/a.py"])
def test_migration_segments_match_case_insensitively(path):
    assert _module().is_migration(path)


def test_lane_version_ignores_the_git_env_of_a_hook(tmp_path, monkeypatch):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": 2}\n')
    _git(repo, "add", ".fabrik/lane.json")
    _git(repo, "commit", "-q", "-m", "lane v2")
    set_by = _git(repo, "rev-parse", "HEAD")
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    (other / "f").write_text("x\n")
    _git(other, "add", "f")
    _git(other, "commit", "-q", "-m", "o")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))
    assert tl.lane_version(repo) == (2, set_by, None)


def test_an_assume_unchanged_edit_is_not_attributed_to_the_setting_commit(tmp_path):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": 2}\n')
    _git(repo, "add", ".fabrik/lane.json")
    _git(repo, "commit", "-q", "-m", "lane v2")
    _git(repo, "update-index", "--assume-unchanged", ".fabrik/lane.json")
    _switch(repo, '{"version": 1}\n')
    assert _git(repo, "status", "--porcelain") == ""
    assert tl.lane_version(repo) == (1, None, None)


def test_lane_version_never_writes_the_index(tmp_path):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": 2}\n')
    _git(repo, "add", ".fabrik/lane.json")
    _git(repo, "commit", "-q", "-m", "lane v2")
    lane = repo / ".fabrik" / "lane.json"
    st = lane.stat()
    lane.write_text('{"version": 2}\n')  # identical bytes, stale stat cache
    os.utime(lane, (st.st_atime + 5, st.st_mtime + 5))
    index = repo / ".git" / "index"
    before = index.read_bytes()
    assert tl.lane_version(repo)[0] == 2
    assert index.read_bytes() == before


# ── Round-2 (T02-O20): the capture's expected_verdict and classify_commit are ONE rule ───


@pytest.mark.parametrize(
    ("rows", "kind", "regex"),
    [
        ([("R", "api/old_spec.yaml", "api/openapi.yaml")], "project", _SYNC),
        ([("M", "Vendor/openapi.yaml", None)], "project", _SYNC),
        ([("M", "db/Migrations/1.sql", None)], "project", _SYNC),
        ([("R", "db/0001.sql", "db/migrations/0001.sql")], "project", _SYNC),
        ([("R", "scripts/old_run.py", "scripts/command_run.py")], "hub", _SYNC),
        ([("M", "docs/CAPABILITIES.md", None)], "hub", ""),
        ([("M", "src/a.py", None)], "hub", ""),
    ],
)
def test_the_capture_rule_and_classify_commit_agree(rows, kind, regex):
    got = _capture().expected_verdict(rows, kind=kind, sync_regex=regex)
    assert got == _classify(rows, kind, regex)


def test_the_capture_rule_text_names_the_old_path_and_case_insensitive_segments():
    rule = _capture().RULE
    assert "reads the row's NEW path" not in rule
    assert "OLD" in rule and "case-insensitively" in rule and "empty" in rule


def test_check_refuses_a_fixture_whose_rule_text_is_stale(tmp_path, capsys):
    cap = _capture()
    stored = json.loads((ROOT / "tests" / "fixtures" / "lane_replay.json").read_text())
    stored["header"]["rule"] = "every path test reads the row's NEW path"
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps(stored))
    called = []
    cap_capture = cap.capture
    try:
        # the rows are not what this asserts: re-derive from the stale file itself, no git
        cap.capture = lambda plan: called.append(plan) or cap.load(stale)
        assert cap.check(stale) == 1
    finally:
        cap.capture = cap_capture
    assert called
    assert "rule" in capsys.readouterr().out


# ── T08-D7: the whole-plan review's admission findings ───────────────────────────────────


@pytest.mark.parametrize(
    "path", ["node_modules/pkg/index.js", "web/.venv/lib/x.py", "a/Vendor/b/c.go"]
)
def test_b_s1_a_new_file_under_a_dependency_directory_is_not_new_source(path):
    assert not _module().is_new_source("A", path)


@pytest.mark.parametrize("path", ["docs/GUIDE.MD", "notes/Plan.Md", "README.mD"])
def test_b_s2_the_md_exclusion_is_case_insensitive(path):
    assert not _module().is_new_source("A", path)


def test_b_h1_oneway_and_tradeoffs_together_name_both_reasons():
    v = _admit(["src/a.py"], why="A vs B", oneway="yes", tradeoffs="yes")
    assert v.route == "chain: oneway", v
    assert v.reason == "oneway, tradeoffs", v


def test_b_o1_a_permission_denied_switch_directory_falls_back_with_a_warning(tmp_path):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": 2}\n')
    fabrik = repo / ".fabrik"
    fabrik.chmod(0)
    try:
        version, commit, warning = tl.lane_version(repo)
    finally:
        fabrik.chmod(0o755)
    assert (version, commit) == (tl._LANE_DEFAULT, None)
    assert warning and ".fabrik/lane.json" in warning


def test_b_o1_a_deeply_nested_switch_falls_back_with_a_warning(tmp_path):
    tl = _module()
    repo = _repo(tmp_path)
    _switch(repo, '{"version": ' + "[" * 200_000 + "]" * 200_000 + "}")
    version, commit, warning = tl.lane_version(repo)
    assert (version, commit) == (tl._LANE_DEFAULT, None)
    assert warning and ".fabrik/lane.json" in warning


@pytest.mark.parametrize(
    "path",
    [
        "api/openapi.yml",
        "api/OpenAPI-v2.YML",
        "apps/x/specs/services/y.yaml",
        "a/b/specs/services/c/d.yaml",
    ],
)
def test_d_o6_yml_and_nested_specs_services_are_contract_hits(path):
    assert _module().contract_hit(path)


@pytest.mark.parametrize(
    "path",
    [
        "node_modules/x/openapi.yml",
        "apps/vendor/specs/services/y.yaml",
        "myspecs/services/y.yaml",
        "specs/servicesx/y.yaml",
        "apps/specs/services",
    ],
)
def test_d_o6_dependency_and_lookalike_specs_services_are_not_hits(path):
    assert not _module().contract_hit(path)
