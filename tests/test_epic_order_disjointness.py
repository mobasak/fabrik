# AFTER-EDIT: scripts/epic_order.py
"""Tests for scripts/epic_order.py's disjointness check (T03b).

`--check` used to intersect `owned_paths` as SETS OF GLOB STRINGS, and only for
pairs that each named the other in `parallel_with`. These tests pin the real
check: epics are compared by the PHASE `phased_order()` puts them in (that is
what determines concurrency), and overlap is the UNION of two predicates — the
intersection of the REALISED file sets (each glob expanded against `git
ls-files` with a `/`-aware matcher) and a pattern-level SUBSUMPTION test
(`**`-aware, glob-vs-glob) that fires before any file exists.

Every fixture lives under tmp_path — never docs/development/epics/.
"""

import json
import subprocess
import time
from pathlib import Path

import pytest
from scripts.epic_order import (
    _glob_matches,
    _glob_subsumes,
    _owns_migrations,
    check_integrity,
    load_epics,
    main,
)


def _write_epic(
    path: Path,
    number: int,
    owned_paths: str,
    deps: str = "[]",
    parallel: str = "[]",
) -> None:
    path.write_text(
        f"---\n"
        f"title: Epic {number} — epic-{number}\n"
        f"epic_n: {number}\n"
        f"slug: epic-{number}\n"
        f"depends_on: {deps}\n"
        f"parallel_with: {parallel}\n"
        f"owned_paths: {owned_paths}\n"
        f"---\n\n## Epic {number} — epic-{number}\n",
        encoding="utf-8",
    )


def _git_repo_with(root: Path, files: list[str]) -> None:
    """A throwaway repo whose INDEX holds `files` — `git ls-files` reads the
    index, so `git add` is enough (no commit, no author config needed)."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "--", *files], check=True)


def _overlap_findings(findings: list[str]) -> list[str]:
    return [f for f in findings if "share owned_paths" in f]


def _check_no_tree(epics_dir: Path) -> list[str]:
    """check_integrity with an EMPTY realised tree pinned — the pattern-level
    predicate alone. (Without `tree=`, check_integrity would `git ls-files`
    the cwd, coupling these rows to whatever the hub happens to track.)"""
    return check_integrity(load_epics(str(epics_dir)), expected_count=None, tree=[])


# --- Row 1: same phase, overlapping paths -------------------------------------


def test_same_phase_different_globs_subsumed_is_a_finding_before_any_file_exists(tmp_path):
    # src/app/** vs src/app/models/**, both root epics (phase 1), declared
    # parallel. Today: glob STRINGS differ -> no finding. No tree at all here
    # (tmp_path is not a repo): the pattern-level predicate must carry it.
    _write_epic(tmp_path / "e1.md", 1, '["src/app/**"]', parallel="[2]")
    _write_epic(tmp_path / "e2.md", 2, '["src/app/models/**"]', parallel="[1]")

    findings = _check_no_tree(tmp_path)

    hits = _overlap_findings(findings)
    assert len(hits) == 1, findings
    assert "phase 1" in hits[0] and "1 & 2" in hits[0], hits
    assert "src/app/**" in hits[0] and "src/app/models/**" in hits[0], hits


def test_same_phase_identical_globs_with_empty_parallel_with_is_a_finding(tmp_path):
    # Byte-identical globs, parallel_with EMPTY on both -> today never
    # compared at all, while phased_order() places both in phase 1.
    _write_epic(tmp_path / "e1.md", 1, '["src/app/**"]')
    _write_epic(tmp_path / "e2.md", 2, '["src/app/**"]')

    findings = _check_no_tree(tmp_path)

    assert len(_overlap_findings(findings)) == 1, findings


def test_same_phase_realised_file_overlap_names_the_shared_file(tmp_path):
    # A real tree: the realised sets intersect on src/app/models/m.py and the
    # finding names it (the realised predicate, not only the pattern one).
    _git_repo_with(tmp_path, ["src/app/models/m.py", "src/app/main.py"])
    epics = tmp_path / "epics"
    epics.mkdir()
    _write_epic(epics / "e1.md", 1, '["src/app/**"]')
    _write_epic(epics / "e2.md", 2, '["src/app/models/*.py"]')

    findings = check_integrity(load_epics(str(epics)), expected_count=None,
                               epics_dir=str(epics))

    hits = _overlap_findings(findings)
    assert len(hits) == 1, findings
    assert "src/app/models/m.py" in hits[0], hits


def test_check_cli_exits_1_and_prints_the_overlap(tmp_path, capsys):
    _write_epic(tmp_path / "e1.md", 1, '["src/app/**"]')
    _write_epic(tmp_path / "e2.md", 2, '["src/app/**"]')

    rc = main(["--epics-dir", str(tmp_path), "--check"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "INTEGRITY: FAIL" in out and "share owned_paths" in out, out


# --- Row 2: same phase, both under libs/, realised sets disjoint --------------


def test_same_phase_libs_globs_with_shared_literal_prefix_is_not_a_finding(tmp_path):
    _git_repo_with(tmp_path, [
        "libs/a/product_entitlements_bridge/bridge.py",
        "libs/b/other/thing.py",
    ])
    epics = tmp_path / "epics"
    epics.mkdir()
    _write_epic(epics / "e1.md", 1, '["libs/**/product_entitlements_bridge/**"]')
    _write_epic(epics / "e2.md", 2, '["libs/**/other/**"]')

    findings = check_integrity(load_epics(str(epics)), expected_count=None,
                               epics_dir=str(epics))

    assert findings == [], findings


def test_single_star_never_crosses_a_separator(tmp_path):
    # The bare-fnmatch trap: fnmatch('src/a/b/deep.py', 'src/a/*') is True.
    # `src/a/*` owns only the files DIRECTLY under src/a, so it is disjoint
    # from `src/a/b/**` — realised (deep.py lives under b/) AND at pattern level.
    _git_repo_with(tmp_path, ["src/a/x.py", "src/a/b/deep.py"])
    epics = tmp_path / "epics"
    epics.mkdir()
    _write_epic(epics / "e1.md", 1, '["src/a/*"]')
    _write_epic(epics / "e2.md", 2, '["src/a/b/**"]')

    findings = check_integrity(load_epics(str(epics)), expected_count=None,
                               epics_dir=str(epics))

    assert findings == [], findings


# --- a wildcard-free entry owns its SUBTREE (round-1 item 1) ------------------


@pytest.mark.parametrize("bare", ["src/app", "src/app/"])
def test_bare_directory_entry_overlaps_the_glob_of_its_subtree(tmp_path, bare):
    # `src/app` (trailing slash insignificant) is a directory entry, not the
    # name of one file: it realises its subtree and subsumes `src/app/**`.
    _git_repo_with(tmp_path, ["src/app/models/m.py"])
    epics = tmp_path / "epics"
    epics.mkdir()
    _write_epic(epics / "e1.md", 1, f'["{bare}"]')
    _write_epic(epics / "e2.md", 2, '["src/app/**"]')

    findings = check_integrity(load_epics(str(epics)), expected_count=None,
                               epics_dir=str(epics))

    hits = _overlap_findings(findings)
    assert len(hits) == 1, findings
    assert "src/app/models/m.py" in hits[0], hits


def test_bare_directory_entry_subsumes_before_any_file_exists(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["src/app"]')
    _write_epic(tmp_path / "e2.md", 2, '["src/app/models/**"]')

    assert len(_overlap_findings(_check_no_tree(tmp_path))) == 1


@pytest.mark.parametrize("entry", ["alembic/versions", "alembic/versions/", "db", "alembic",
                                   "db/*", "alembic/versions/0001_x.py"])
def test_bare_migration_directory_owns_migrations(entry):
    # `db/*` is the mirror of the strict subsumption predicate: it covers the
    # bare `db/schema.sql` but not `db/schema.sql/**`, so migration ownership
    # keeps its own LOOSE reading (any form of the entry reaches the glob).
    assert _owns_migrations([entry]) is True


@pytest.mark.parametrize(("outer", "bare", "files"), [
    ("docs/*", "docs/reference", ["docs/README.md", "docs/reference/agents.md"]),
    ("src/*", "src/app", ["src/main.py", "src/app/x.py"]),
])
def test_glob_covering_only_the_bare_form_of_a_directory_is_not_an_overlap(
    tmp_path, outer, bare, files,
):
    # Round-2 item 1: `docs/*` "subsumed" `docs/reference` because the
    # predicate OR'd over both sides' forms — accepting an outer that covers
    # only the BARE form. Their realised sets are non-empty and permanently
    # disjoint (a directory is never a file `docs/*` can own).
    _git_repo_with(tmp_path, files)
    epics = tmp_path / "epics"
    epics.mkdir()
    _write_epic(epics / "e1.md", 1, f'["{outer}"]')
    _write_epic(epics / "e2.md", 2, f'["{bare}"]')

    findings = check_integrity(load_epics(str(epics)), expected_count=None,
                               epics_dir=str(epics))

    assert findings == [], findings


def test_two_literal_files_in_one_phase_are_silent(tmp_path):
    # The hub's own epic-1 shape vs a sibling doc — two distinct literal
    # paths never overlap, subtree reading or not.
    _write_epic(tmp_path / "e1.md", 1, '["specs/services/zitadel.yaml", "docs/reference/zitadel.md"]')
    _write_epic(tmp_path / "e2.md", 2, '["docs/reference/umbrella-sso-integration.md"]')

    assert _check_no_tree(tmp_path) == []


# --- Row 3: different phases, overlapping paths -------------------------------


def test_different_phases_with_identical_globs_is_not_a_finding(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["src/app/**"]')
    _write_epic(tmp_path / "e2.md", 2, '["src/app/**"]', deps="[1]")

    findings = _check_no_tree(tmp_path)

    assert findings == [], findings


# --- Row 4: single-migration-owner, keyed on the phase -----------------------


def test_same_phase_two_migration_owners_fires_without_parallel_with(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["alembic/versions/**", "src/a/**"]')
    _write_epic(tmp_path / "e2.md", 2, '["db/schema.sql", "src/b/**"]')

    findings = _check_no_tree(tmp_path)

    mig = [f for f in findings if "both own migrations" in f]
    assert len(mig) == 1, findings
    assert "phase 1" in mig[0], mig
    assert _overlap_findings(findings) == [], findings


def test_different_phases_two_migration_owners_is_not_a_finding(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["alembic/versions/**"]')
    _write_epic(tmp_path / "e2.md", 2, '["db/schema.sql"]', deps="[1]")

    findings = _check_no_tree(tmp_path)

    assert findings == [], findings


# --- Row 5: a depends_on cycle is a named finding, never a traceback ---------


def _cycle(tmp_path: Path) -> None:
    _write_epic(tmp_path / "e1.md", 1, '["src/a/**"]', deps="[2]")
    _write_epic(tmp_path / "e2.md", 2, '["src/b/**"]', deps="[1]")


def test_cycle_is_an_integrity_finding(tmp_path):
    _cycle(tmp_path)

    findings = check_integrity(load_epics(str(tmp_path)), expected_count=None)

    assert any("dependency cycle" in f for f in findings), findings


@pytest.mark.parametrize("flags", [["--check"], ["--check", "--json"], ["--json"], []])
def test_cycle_exits_1_cleanly_in_every_mode(tmp_path, capsys, flags):
    _cycle(tmp_path)

    rc = main(["--epics-dir", str(tmp_path), *flags])  # a traceback would escape here

    out = capsys.readouterr().out
    assert rc == 1
    assert "dependency cycle" in out, out
    if "--json" in flags:
        payload = json.loads(out)
        assert payload["ok"] is False
        assert any("dependency cycle" in f for f in payload["findings"])


def test_dangling_depends_on_is_named_as_such_not_as_a_cycle(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["src/a/**"]', deps="[7]")

    findings = check_integrity(load_epics(str(tmp_path)), expected_count=None)

    assert any("depends_on" in f and "7" in f for f in findings), findings
    assert not any("cycle" in f for f in findings), findings


# --- Row 6: empty/absent owned_paths is NOT a shared [''] --------------------


@pytest.mark.parametrize("shape", ["", '""', "[]"])
def test_empty_owned_paths_is_not_reported_as_shared(tmp_path, shape):
    _write_epic(tmp_path / "e1.md", 1, shape)
    _write_epic(tmp_path / "e2.md", 2, shape)

    epics = load_epics(str(tmp_path))
    assert epics[0]["owned_paths"] == [] and epics[1]["owned_paths"] == [], epics

    findings = check_integrity(epics, expected_count=None)

    assert findings == [], findings


@pytest.mark.parametrize("entry", ['"   "', '" "'])
def test_whitespace_only_entry_owns_nothing(tmp_path, entry):
    # Round-2 item 3: a no-segment entry made `_forms` return [[], ['**']] —
    # the whole repo, silently. Dropped at the parse filter.
    _write_epic(tmp_path / "e1.md", 1, f"[{entry}]")
    _write_epic(tmp_path / "e2.md", 2, '["src/app/**"]')

    epics = load_epics(str(tmp_path))
    assert epics[0]["owned_paths"] == [], epics[0]["owned_paths"]
    assert _check_no_tree(tmp_path) == []


@pytest.mark.parametrize("root", [".", "./", "/"])
def test_root_entry_owns_the_whole_repo_and_overlaps_everything(tmp_path, root):
    # Round-3 item: a bare `.` survived `_pattern_segs` as a literal segment
    # (matching only a file literally named `.`) while `./` and `/` read as
    # the whole repo — the bad direction, a missed overlap.
    _write_epic(tmp_path / "e1.md", 1, f'["{root}"]')
    _write_epic(tmp_path / "e2.md", 2, '["src/app/**"]')

    assert len(_overlap_findings(_check_no_tree(tmp_path))) == 1


def test_interior_dot_segment_is_still_a_literal():
    assert _glob_matches("a/./b", "a/./b") is True
    assert _glob_matches("a/./b", "a/b") is False


def test_absent_owned_paths_key_is_no_paths(tmp_path):
    for n in (1, 2):
        (tmp_path / f"e{n}.md").write_text(
            f"---\ntitle: Epic {n} — epic-{n}\nepic_n: {n}\nslug: epic-{n}\n"
            f"depends_on: []\nparallel_with: []\n---\n",
            encoding="utf-8",
        )

    findings = check_integrity(load_epics(str(tmp_path)), expected_count=None)

    assert findings == [], findings


# --- parallel_with contradicting phased_order() ------------------------------


def test_parallel_with_across_phases_is_a_finding(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["src/a/**"]', parallel="[2]")
    _write_epic(tmp_path / "e2.md", 2, '["src/b/**"]', deps="[1]")

    findings = check_integrity(load_epics(str(tmp_path)), expected_count=None)

    hits = [f for f in findings if "parallel_with" in f and "phased_order" in f]
    assert len(hits) == 1, findings


def test_parallel_with_naming_an_unknown_epic_is_a_finding(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["src/a/**"]', parallel="[9]")

    findings = check_integrity(load_epics(str(tmp_path)), expected_count=None)

    assert any("parallel_with" in f and "9" in f for f in findings), findings


def test_parallel_with_naming_itself_is_a_finding(tmp_path):
    # Round-1 item 3: `phase_of[n] != phase_of[n]` is never true, so a
    # self-reference used to pass where every other malformed value fails.
    _write_epic(tmp_path / "e1.md", 1, '["src/a/**"]', parallel="[1]")

    findings = _check_no_tree(tmp_path)

    assert any("parallel_with" in f and "itself" in f for f in findings), findings


def test_parallel_with_agreeing_with_phased_order_is_silent(tmp_path):
    _write_epic(tmp_path / "e1.md", 1, '["src/a/**"]', parallel="[2]")
    _write_epic(tmp_path / "e2.md", 2, '["src/b/**"]', parallel="[1]")

    findings = _check_no_tree(tmp_path)

    assert findings == [], findings


# --- the matchers themselves ---------------------------------------------------


@pytest.mark.parametrize(("pattern", "path", "expected"), [
    ("src/app/**", "src/app/models/m.py", True),
    ("src/app/**", "src/app", False),  # trailing ** needs at least one segment
    ("src/a/*", "src/a/x.py", True),
    ("src/a/*", "src/a/b/deep.py", False),  # never crosses a separator
    ("libs/**/peb/**", "libs/peb/x.py", True),  # mid ** spans zero segments
    ("libs/**/peb/**", "libs/a/b/peb/x.py", True),
    ("libs/**/peb/**", "libs/a/other/x.py", False),
    ("db/schema.sql", "db/schema.sql", True),
    ("db/schema.sql", "db/schema.sql.bak", False),
    ("app/(admin)/**", "app/(admin)/page.tsx", True),  # parens are literals
    ("src/?.py", "src/a.py", True),
    ("src/?.py", "src/ab.py", False),
    ("src/app", "src/app/models/m.py", True),  # bare directory realises its subtree
    ("src/app/", "src/app/models/m.py", True),
    ("src/app", "src/apple/x.py", False),
])
def test_glob_matches_is_separator_aware(pattern, path, expected):
    assert _glob_matches(pattern, path) is expected


@pytest.mark.parametrize(("outer", "inner", "expected"), [
    ("src/app/**", "src/app/models/**", True),
    ("src/app/models/**", "src/app/**", False),
    ("src/app/**", "src/app/**", True),
    ("libs/**/peb/**", "libs/**/other/**", False),
    ("libs/**/other/**", "libs/**/peb/**", False),
    ("src/a/*", "src/a/b/**", False),
    ("src/a/b/**", "src/a/*", False),
    ("src/*/x", "src/**/x", False),  # * spans one segment, ** many
    ("src/**/x", "src/*/x", True),
    ("src/a/f*", "src/a/f?", True),
    ("src/a/f?", "src/a/f*", False),
    ("docs/**", "docs/reference/zitadel.md", True),
    ("src/app", "src/app/**", True),  # a bare directory entry IS its subtree
    ("src/app/**", "src/app", False),  # ...but the glob does not contain the bare PATH
    ("docs/*", "docs/reference", False),  # covers the bare form only, never the subtree
    ("src/*", "src/app", False),
    ("src/app/", "src/app/models/**", True),
    ("db", "db/schema.sql", True),
    ("db/schema.sql", "db/*", False),  # a literal FILE covers nothing else
    ("db/*", "db/schema.sql/**", False),
    ("specs/services/zitadel.yaml", "docs/reference/zitadel.md", False),
])
def test_glob_subsumes_is_star_star_aware(outer, inner, expected):
    assert _glob_subsumes(outer, inner) is expected


def test_matcher_has_no_catastrophic_case():
    pattern = "src/" + "a*" * 12 + "b/**"
    path = "src/" + "a" * 41 + "/deep.py"
    t0 = time.monotonic()
    assert _glob_matches(pattern, path) is False
    assert time.monotonic() - t0 < 1.0
