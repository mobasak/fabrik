"""Tests for `docs_updater.py --adopt` (T02a, multi-agent adoption plan).

One test per Behavior Contract row (T02a-adopt-core.md). Every fixture builds a
scratch repo under `tmp_path` and monkeypatches `docs_updater.PROJECT_ROOT` /
`PLANS_DIR` / `PLANS_INDEX` — never the real /opt/fabrik tree, and `--adopt` is
never invoked against anything but a tmp_path fixture (per the ticket's hard
constraint: this flag must never run for real from inside a subagent worktree).
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import docs_updater as du  # noqa: E402
import final_gate as fg  # noqa: E402

_REAL_EPIC_ORDER = Path(__file__).parent.parent / "scripts" / "epic_order.py"


def _vendor_epic_order(root: Path) -> None:
    """`--adopt`'s epic delegation shells out to `scripts/epic_order.py` relative to
    PROJECT_ROOT (docs_updater.py:… — hub-only, never synced to projects), exactly the
    way the live hub repo carries both scripts side by side. A fixture that wants the
    subprocess to actually run copies the real script in, the same way a real repo
    would already have it there."""
    dest = root / "scripts" / "epic_order.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_REAL_EPIC_ORDER, dest)


def _fake_proc(tmp_path: Path, entries: list[tuple[str, Path]]) -> Path:
    """A scratch `/proc` tree: `<root>/<pid>/comm` + a `cwd` symlink per entry — the
    same shape a real process's /proc entry has, so `count_sessions_sharing` exercises
    its REAL scan logic against a fake root instead of a count override."""
    root = tmp_path / "fake_proc"
    root.mkdir()
    for i, (comm, cwd) in enumerate(entries, start=1):
        pid_dir = root / str(1000 + i)
        pid_dir.mkdir()
        (pid_dir / "comm").write_text(comm + "\n", encoding="utf-8")
        (pid_dir / "cwd").symlink_to(cwd, target_is_directory=True)
    return root


def _decisions_no_merge_owner(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Decisions\n\n"
        "| id | when | who | what (the decision) | why | where |\n"
        "|---|---|---|---|---|---|\n"
        "| D-001 | 2026-01-01 | operator | some unrelated decision | because | here |\n",
        encoding="utf-8",
    )


def _decisions_with_merge_owner(path: Path, name: str = "alpha") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Decisions\n\n"
        "| id | when | who | what (the decision) | why | where |\n"
        "|---|---|---|---|---|---|\n"
        f"| D-001 | 2026-01-01 | {name} | MERGE OWNER: {name} — declared by --adopt "
        "| because | docs/development/PLANS.md |\n",
        encoding="utf-8",
    )


class TestBC1FirstAdoptRun:
    """Given a scratch repo with a marker-less PLANS.md, two open plans with no Owner
    line, one EXECUTED plan, and a ledger with no MERGE OWNER row, when
    `--adopt alpha,beta --single-window` runs, PLANS.md gains the markers and a block
    whose second header line names alpha, both open plans get Owner lines round-robin,
    the EXECUTED plan is untouched, one MERGE OWNER row is appended, and the printed
    table has one row per change."""

    @staticmethod
    def _repo(tmp_path: Path, with_epics: bool = False) -> Path:
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        (plans / "2026-01-01-plan-1-open-a.md").write_text(
            "# Plan A\n\nStatus: DRAFT\n", encoding="utf-8"
        )
        (plans / "2026-01-02-plan-2-open-b.md").write_text(
            "# Plan B\n\nStatus: DRAFT\n", encoding="utf-8"
        )
        (plans / "2026-01-03-plan-3-done.md").write_text(
            "# Plan C\n\nStatus: EXECUTED\n", encoding="utf-8"
        )
        idx = root / "docs" / "development" / "PLANS.md"
        idx.write_text("# Plans\n\nSome hand table.\n", encoding="utf-8")
        _decisions_no_merge_owner(root / "docs" / "DECISIONS.md")
        if with_epics:
            epics = root / "docs" / "development" / "epics"
            epics.mkdir(parents=True)
            (epics / "2026-01-01-epic-1-one.md").write_text(
                '---\nkind: story\ntitle: "Epic 1 — One"\nstatus: 0\nepic_n: 1\nslug: one\n'
                "depends_on: []\nparallel_with: []\nowned_paths: []\n---\n# Epic 1\n",
                encoding="utf-8",
            )
            _vendor_epic_order(root)
        return root

    def test_first_run_seeds_markers_owners_and_ledger_row(self, tmp_path, monkeypatch, capsys):
        root = self._repo(tmp_path)
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

        rc = du.run_adopt(["alpha", "beta"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 0

        idx_text = (root / "docs" / "development" / "PLANS.md").read_text(encoding="utf-8")
        assert "<!-- AUTO-GENERATED:PLANS:START -->" in idx_text
        assert "Some hand table." in idx_text  # the existing hand table is kept as history
        lines = [ln for ln in idx_text.splitlines() if ln.startswith("<!-- Merge owner:")]
        assert lines == ["<!-- Merge owner: alpha | source: D-002 -->"]

        plan_a = (
            root / "docs" / "development" / "plans" / "2026-01-01-plan-1-open-a.md"
        ).read_text(encoding="utf-8")
        plan_b = (
            root / "docs" / "development" / "plans" / "2026-01-02-plan-2-open-b.md"
        ).read_text(encoding="utf-8")
        plan_c = (root / "docs" / "development" / "plans" / "2026-01-03-plan-3-done.md").read_text(
            encoding="utf-8"
        )
        assert "**Owner:** alpha" in plan_a
        assert "**Owner:** beta" in plan_b
        assert "**Owner:**" not in plan_c  # EXECUTED plan is untouched

        decisions_text = (root / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
        assert decisions_text.count("MERGE OWNER: alpha") == 1
        assert "| D-002 |" in decisions_text  # max existing id (D-001) + 1

        table_rows = [ln for ln in out.splitlines() if ln.startswith("| ") and "Item" not in ln]
        table_rows = [ln for ln in table_rows if not ln.startswith("|---")]
        assert len(table_rows) == 4  # markers + 2 owner-lines + 1 ledger-row


class TestBC2Idempotent:
    """Given the state after that run, re-running with the same names changes no byte
    and prints `(nothing to adopt)` — WITH an epics dir present too (D1): `--assign` is
    itself idempotent, so a second run must not keep reporting an `epic_order` change
    that did not happen."""

    def test_second_identical_run_is_a_byte_identical_no_op(self, tmp_path, monkeypatch, capsys):
        root = TestBC1FirstAdoptRun._repo(tmp_path, with_epics=True)
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

        du.run_adopt(["alpha", "beta"], single_window=True)
        capsys.readouterr()  # discard first run's output

        watched = [
            root / "docs" / "development" / "PLANS.md",
            root / "docs" / "development" / "plans" / "2026-01-01-plan-1-open-a.md",
            root / "docs" / "development" / "plans" / "2026-01-02-plan-2-open-b.md",
            root / "docs" / "development" / "plans" / "2026-01-03-plan-3-done.md",
            root / "docs" / "development" / "epics" / "2026-01-01-epic-1-one.md",
            root / "docs" / "DECISIONS.md",
        ]
        before = {p: p.read_bytes() for p in watched}

        rc = du.run_adopt(["alpha", "beta"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 0
        assert out.strip() == "(nothing to adopt)"
        for p in watched:
            assert p.read_bytes() == before[p], f"{p} changed on a repeat --adopt run"


class TestBC3ExistingMergeOwnerNeverRewritten:
    """Given a ledger already carrying MERGE OWNER: alpha, --adopt gamma never writes
    a new ledger row and the header comment still names alpha — a change of merge
    owner is a hand-minted superseding row, never --adopt's write."""

    def test_a_declared_merge_owner_blocks_a_second_ledger_row(self, tmp_path, monkeypatch):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        idx = root / "docs" / "development" / "PLANS.md"
        idx.write_text(
            "# Plans\n\n<!-- AUTO-GENERATED:PLANS:START -->\n<!-- AUTO-GENERATED:PLANS:END -->\n",
            encoding="utf-8",
        )
        decisions = root / "docs" / "DECISIONS.md"
        decisions.parent.mkdir(parents=True, exist_ok=True)
        decisions.write_text(
            "# Decisions\n\n"
            "| id | when | who | what (the decision) | why | where |\n"
            "|---|---|---|---|---|---|\n"
            "| D-005 | 2026-01-01 | infra (--adopt) | **MERGE OWNER: alpha** — the only "
            "writer of the base branch | because | docs/development/PLANS.md |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        before = decisions.read_text(encoding="utf-8")
        rc = du.run_adopt(["gamma"], single_window=True)
        after = decisions.read_text(encoding="utf-8")

        assert rc == 0
        assert after == before  # not one byte added
        assert after.count("MERGE OWNER:") == 1

        idx_text = idx.read_text(encoding="utf-8")
        assert "<!-- Merge owner: alpha | source: D-005 -->" in idx_text
        assert "gamma" not in idx_text.split("<!-- Merge owner:")[1].split("-->")[0]


class TestBC4SessionCountRefusal:
    """Given a fake proc tree with ONE claude process whose cwd is the repo and no
    --single-window, --adopt exits 2 with one stderr line naming the count and the
    override, and no file changes; with two such processes it proceeds."""

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
        root = tmp_path / "repo"
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        return root

    def test_one_session_refuses(self, tmp_path, monkeypatch, capsys):
        root = self._repo(tmp_path)
        proc_root = _fake_proc(tmp_path, [("claude", root)])
        idx = root / "docs" / "development" / "PLANS.md"

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        assert du.count_sessions_sharing(root, proc_root) == 1

        rc = du.run_adopt(["alpha"], single_window=False, proc_root=proc_root)
        err = capsys.readouterr().err

        assert rc == 2
        stderr_lines = [ln for ln in err.splitlines() if ln.strip()]
        assert len(stderr_lines) == 1
        assert "1" in stderr_lines[0]
        assert "--single-window" in stderr_lines[0]
        assert not idx.exists()

    def test_two_sessions_proceeds(self, tmp_path, monkeypatch):
        root = self._repo(tmp_path)
        proc_root = _fake_proc(tmp_path, [("claude", root), ("claude", root)])
        idx = root / "docs" / "development" / "PLANS.md"

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        assert du.count_sessions_sharing(root, proc_root) == 2

        rc = du.run_adopt(["alpha"], single_window=False, proc_root=proc_root)

        assert rc == 0
        assert idx.exists()  # step (a) ran — the refusal did not fire


class TestBC5ReadMergeOwner:
    """Given a ledger row whose `what` opens with `**MERGE OWNER: alpha**`,
    read_merge_owner() returns ("alpha", "D-NNN")."""

    def test_bold_merge_owner_cell_parses_name_and_id(self, tmp_path, monkeypatch):
        root = tmp_path
        decisions = root / "docs" / "DECISIONS.md"
        decisions.parent.mkdir(parents=True, exist_ok=True)
        decisions.write_text(
            "# Decisions\n\n"
            "| id | when | who | what (the decision) | why | where |\n"
            "|---|---|---|---|---|---|\n"
            "| D-041 | 2026-01-01 | infra | some other row | because | here |\n"
            "| D-042 | 2026-01-02 | infra (--adopt) | **MERGE OWNER: alpha** — the only "
            "writer | because | docs/development/PLANS.md |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(du, "PROJECT_ROOT", root)

        assert du.read_merge_owner() == ("alpha", "D-042")

    def test_no_matching_row_returns_none(self, tmp_path, monkeypatch):
        root = tmp_path
        decisions = root / "docs" / "DECISIONS.md"
        decisions.parent.mkdir(parents=True, exist_ok=True)
        decisions.write_text(
            "# Decisions\n\n"
            "| id | when | who | what (the decision) | why | where |\n"
            "|---|---|---|---|---|---|\n"
            "| D-001 | 2026-01-01 | infra | mentions MERGE OWNER: alpha mid-sentence, "
            "not as the opening | because | here |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(du, "PROJECT_ROOT", root)

        assert du.read_merge_owner() is None

    def test_missing_ledger_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(du, "PROJECT_ROOT", tmp_path)
        assert du.read_merge_owner() is None


class TestBC6EpicDelegation:
    """Given an epics dir with two frontmatter epics lacking owner:, --adopt
    alpha,beta --single-window invokes epic_order.py --assign alpha,beta once and the
    table carries an epic_order row."""

    def test_epic_order_assign_is_invoked_and_writes_owners(self, tmp_path, monkeypatch, capsys):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        epics = root / "docs" / "development" / "epics"
        plans.mkdir(parents=True)
        epics.mkdir(parents=True)
        (epics / "2026-01-01-epic-1-one.md").write_text(
            '---\nkind: story\ntitle: "Epic 1 — One"\nstatus: 0\nepic_n: 1\nslug: one\n'
            "depends_on: []\nparallel_with: []\nowned_paths: []\n---\n# Epic 1\n",
            encoding="utf-8",
        )
        (epics / "2026-01-02-epic-2-two.md").write_text(
            '---\nkind: story\ntitle: "Epic 2 — Two"\nstatus: 0\nepic_n: 2\nslug: two\n'
            "depends_on: []\nparallel_with: []\nowned_paths: []\n---\n# Epic 2\n",
            encoding="utf-8",
        )
        idx = root / "docs" / "development" / "PLANS.md"
        _decisions_no_merge_owner(root / "docs" / "DECISIONS.md")
        _vendor_epic_order(root)

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        rc = du.run_adopt(["alpha", "beta"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 0
        assert "| epics (epic_order.py --assign) | alpha | epic_order |" in out

        e1 = (epics / "2026-01-01-epic-1-one.md").read_text(encoding="utf-8")
        e2 = (epics / "2026-01-02-epic-2-two.md").read_text(encoding="utf-8")
        assert "owner: alpha" in e1
        assert "owner: beta" in e2

    def test_no_epics_dir_means_no_epic_order_row(self, tmp_path, monkeypatch, capsys):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        idx = root / "docs" / "development" / "PLANS.md"
        _decisions_no_merge_owner(root / "docs" / "DECISIONS.md")

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        du.run_adopt(["alpha"], single_window=True)
        out = capsys.readouterr().out
        assert "epic_order" not in out


class TestBC7LiveTreeHeaderAndStaleness:
    """Given the live hub tree's real PLANS.md content, generate_plans_table()'s
    second line starts with `<!-- Merge owner:`, and validate_plans_indexed() against
    the pre-change block reports the stale finding once, cleared by --sync. Grounded
    against the real repo's docs/development/PLANS.md (read-only) but exercised on a
    tmp_path copy — this ticket's Touches never include docs/development/PLANS.md."""

    def test_live_plans_md_content_is_stale_until_synced(self, tmp_path, monkeypatch):
        real_root = Path(__file__).resolve().parents[1]
        real_plans_index = real_root / "docs" / "development" / "PLANS.md"
        assert real_plans_index.is_file(), "the live hub tree must carry docs/development/PLANS.md"

        root = tmp_path
        (root / "docs" / "development" / "plans").mkdir(parents=True)
        idx = root / "docs" / "development" / "PLANS.md"
        idx.write_text(real_plans_index.read_text(encoding="utf-8"), encoding="utf-8")

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        table = du.generate_plans_table()
        second_line = table.splitlines()[1]
        assert second_line.startswith("<!-- Merge owner:")

        findings = du.validate_plans_indexed()
        assert len(findings) == 1

        changed, _msg = du.sync_plans_index()
        assert changed is True
        assert du.validate_plans_indexed() == []


class TestD2NameValidation:
    """Acceptance-review D2: `--adopt` must refuse any name that cannot round-trip
    through MERGE_OWNER_RE once written into the ledger row — a name carrying `|`
    would silently corrupt the ledger row. (A bare leading `-` is legitimately valid
    under epic_order.py's own grammar — round 2 / D3b tightens the exact character
    class; `TestD3bStrictNameGrammar` below covers that boundary precisely.)"""

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
        root = tmp_path
        (root / "docs" / "development" / "plans").mkdir(parents=True)
        return root

    @pytest.mark.parametrize("bad_name", ["al|pha"])
    def test_an_invalid_name_is_refused_before_any_file_changes(
        self, tmp_path, monkeypatch, capsys, bad_name
    ):
        root = self._repo(tmp_path)
        idx = root / "docs" / "development" / "PLANS.md"
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        rc = du.run_adopt([bad_name, "beta"], single_window=True)
        err = capsys.readouterr().err

        assert rc == 2
        assert bad_name in err
        assert not idx.exists()
        assert not (root / "docs" / "DECISIONS.md").exists()


class TestD3LastMatchWinsIsGrounded:
    """Acceptance-review D3: the T01<->T02a seam — TWO matching rows in the ledger,
    the LATER one must win. A `found = (...)` that regressed to `return (...)` inside
    the loop would keep this suite green without this fixture."""

    def test_two_merge_owner_rows_the_later_one_wins(self, tmp_path, monkeypatch):
        root = tmp_path
        decisions = root / "docs" / "DECISIONS.md"
        decisions.parent.mkdir(parents=True, exist_ok=True)
        decisions.write_text(
            "# Decisions\n\n"
            "| id | when | who | what (the decision) | why | where |\n"
            "|---|---|---|---|---|---|\n"
            "| D-010 | 2026-01-01 | infra (--adopt) | MERGE OWNER: alpha — the only "
            "writer | because | here |\n"
            "| D-011 | 2026-01-02 | infra (--adopt) | **MERGE OWNER: beta** — the only "
            "writer | because | here |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(du, "PROJECT_ROOT", root)

        assert du.read_merge_owner() == ("beta", "D-011")


class TestD4OwnerLinePlacement:
    """Acceptance-review D4: the exact LINE INDEX the Owner line lands at, not merely
    its substring presence — parametrized over the four shapes the reviewer named."""

    @pytest.mark.parametrize(
        "body,expected_lines",
        [
            pytest.param(
                "# Plan A\n\nStatus: DRAFT\n",
                ["# Plan A", "", "**Owner:** alpha", "Status: DRAFT", ""],
                id="h1-then-blank-then-status",
            ),
            pytest.param(
                "# Plan A\nStatus: DRAFT\n",
                ["# Plan A", "**Owner:** alpha", "Status: DRAFT", ""],
                id="h1-then-status-directly",
            ),
            pytest.param(
                "```text\n# not a real heading\n```\n# Plan A\n\nStatus: DRAFT\n",
                [
                    "```text",
                    "# not a real heading",
                    "```",
                    "# Plan A",
                    "",
                    "**Owner:** alpha",
                    "Status: DRAFT",
                    "",
                ],
                id="fenced-block-precedes-the-real-h1",
            ),
            pytest.param(
                '---\n# a YAML comment, not a heading\ntitle: "x"\n---\n'
                "# Plan A\n\nStatus: DRAFT\n",
                [
                    "---",
                    "# a YAML comment, not a heading",
                    'title: "x"',
                    "---",
                    "# Plan A",
                    "",
                    "**Owner:** alpha",
                    "Status: DRAFT",
                    "",
                ],
                id="leading-frontmatter-precedes-the-real-h1",
            ),
        ],
    )
    def test_owner_line_lands_immediately_after_h1_and_before_status(
        self, tmp_path, body, expected_lines
    ):
        p = tmp_path / "plan.md"
        p.write_text(body, encoding="utf-8")

        assert du._insert_owner_line(p, "alpha") is True

        lines = p.read_text(encoding="utf-8").split("\n")
        assert lines == expected_lines

        h1_idx = next(i for i, ln in enumerate(lines) if ln == "# Plan A")
        owner_idx = next(i for i, ln in enumerate(lines) if ln == "**Owner:** alpha")
        status_idx = next(i for i, ln in enumerate(lines) if ln.startswith("Status:"))
        assert owner_idx > h1_idx
        assert owner_idx < status_idx


class TestD5SeededMarkersAreByteExactSuffix:
    """Acceptance-review D5: the T02a->T06 seam literal — the seeded block is an EXACT
    suffix appended below the pre-existing hand table, byte for byte."""

    def test_the_seeded_block_is_the_exact_suffix_below_existing_content(
        self, tmp_path, monkeypatch
    ):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        idx = root / "docs" / "development" / "PLANS.md"
        existing = "# Plans\n\nSome hand table.\n| a | b |\n|---|---|\n"
        idx.write_text(existing, encoding="utf-8")
        _decisions_no_merge_owner(root / "docs" / "DECISIONS.md")

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        du.run_adopt(["alpha"], single_window=True)

        text = idx.read_text(encoding="utf-8")
        assert text.startswith(existing)
        suffix = text[len(existing) :]
        assert suffix.startswith(
            "\n## Ownership (auto-generated)\n\n<!-- AUTO-GENERATED:PLANS:START -->\n"
        )
        assert suffix.endswith("<!-- AUTO-GENERATED:PLANS:END -->\n")


class TestD6ProcScanEdgeCases:
    """Acceptance-review D6: a `claude`-prefixed-but-different comm must not count, and
    an indirect (aliased) symlink chain must still resolve via realpath."""

    def test_a_claude_prefixed_comm_is_not_counted(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        proc_root = _fake_proc(tmp_path, [("claude-foo", root)])
        assert du.count_sessions_sharing(root, proc_root) == 0

    def test_an_aliased_symlink_still_resolves_via_realpath(self, tmp_path):
        real_repo = tmp_path / "real_repo"
        real_repo.mkdir()
        alias = tmp_path / "alias_repo"
        alias.symlink_to(real_repo, target_is_directory=True)
        # the fake proc entry's cwd symlink points at the ALIAS, one hop short of the
        # real repo — only a realpath() on the readlink() target reaches it.
        proc_root = _fake_proc(tmp_path, [("claude", alias)])
        assert du.count_sessions_sharing(real_repo, proc_root) == 1


class TestD7NoTailSweepWording:
    """Acceptance-review D7: the retired 'tail sweep' wording must be gone everywhere
    it was named, and '--adopt fills it' must be the replacement text."""

    def test_phase_note_and_no_owner_comment_name_adopt_not_tail_sweep(self):
        import inspect

        source = inspect.getsource(du)
        assert "tail sweep" not in source
        assert "`--adopt` fills it" in du._PLANS_PHASE_NOTE


class TestD8EmptyAdoptStringIsRejected:
    """Acceptance-review D8: `--adopt ""` is falsy under `if args.adopt:` and silently
    fell through to the default `run_once()` branch instead of being refused."""

    def test_adopt_empty_string_exits_2_and_never_reaches_run_once(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["docs_updater.py", "--adopt", ""])

        def _boom():
            raise AssertionError("run_once() must never run for --adopt=''")

        monkeypatch.setattr(du, "run_once", _boom)

        with pytest.raises(SystemExit) as exc_info:
            du.main()

        assert exc_info.value.code == 2


class TestD9EpicOrderFailureIsReportedAndFlipsExit:
    """Acceptance-review D9: a REFUSED epic_order.py --assign (rc!=0) must not print as
    an ordinary success row, and run_adopt must return non-zero so a caller can tell."""

    def test_a_refused_assign_reports_its_rc_and_returns_3(self, tmp_path, monkeypatch, capsys):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        epics = root / "docs" / "development" / "epics"
        plans.mkdir(parents=True)
        epics.mkdir(parents=True)
        # a title that fails epic_order.py's own 'Epic N — [Name]' integrity check —
        # --assign refuses (rc=1) and writes nothing.
        (epics / "2026-01-01-epic-1-bad.md").write_text(
            '---\nkind: story\ntitle: "Not The Right Shape"\nstatus: 0\nepic_n: 1\n'
            "slug: bad\ndepends_on: []\nparallel_with: []\nowned_paths: []\n---\n# Epic 1\n",
            encoding="utf-8",
        )
        idx = root / "docs" / "development" / "PLANS.md"
        _decisions_no_merge_owner(root / "docs" / "DECISIONS.md")
        _vendor_epic_order(root)

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        rc = du.run_adopt(["alpha"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 3
        assert "epic_order (rc=1)" in out
        assert "| epics (epic_order.py --assign) | alpha | epic_order (rc=1) |" in out


class TestD3aAbsentEpicOrderIsSkippedNotFailed:
    """Round-2 acceptance review 3a: scripts/epic_order.py is fleet-synced NOWHERE
    (0 of 41 projects) while docs_updater.py itself IS fleet-synced. A repo with an
    epics dir but no vendored epic_order.py must be skipped entirely — never treated
    as a failed delegation — mirroring the guard `_epic_rows()` already applies at the
    module's ImportError branch."""

    def test_no_epic_order_script_skips_delegation_with_rc_0(self, tmp_path, monkeypatch, capsys):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        epics = root / "docs" / "development" / "epics"
        plans.mkdir(parents=True)
        epics.mkdir(parents=True)
        (epics / "2026-01-01-epic-1-one.md").write_text(
            '---\nkind: story\ntitle: "Epic 1 — One"\nstatus: 0\nepic_n: 1\nslug: one\n'
            "depends_on: []\nparallel_with: []\nowned_paths: []\n---\n# Epic 1\n",
            encoding="utf-8",
        )
        idx = root / "docs" / "development" / "PLANS.md"
        _decisions_no_merge_owner(root / "docs" / "DECISIONS.md")
        # deliberately NOT vendoring scripts/epic_order.py — the web-ecommerce-factory shape

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        rc = du.run_adopt(["alpha"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 0
        assert "epic_order" not in out
        # the epic itself is genuinely untouched — no local writer ran
        untouched = (epics / "2026-01-01-epic-1-one.md").read_text(encoding="utf-8")
        assert "owner:" not in untouched

        before = {
            idx: idx.read_bytes(),
            (root / "docs" / "DECISIONS.md"): (root / "docs" / "DECISIONS.md").read_bytes(),
        }
        rc2 = du.run_adopt(["alpha"], single_window=True)
        out2 = capsys.readouterr().out

        assert rc2 == 0
        assert out2.strip() == "(nothing to adopt)"
        for p, content in before.items():
            assert p.read_bytes() == content


class TestD3bStrictNameGrammar:
    """Round-2 acceptance review 3b: `_ADOPT_NAME_RE` must be IDENTICAL to
    epic_order.py's `_OWNER_NAME_RE` (`^[a-z0-9-]{1,32}$`) — the round-1 grammar
    (uppercase, `_`, `.`, `@`, unbounded length all accepted) let a name through that
    epic_order.py's own `--assign` would refuse, half-adopting the repo (markers +
    owner lines + an IMMUTABLE ledger row written, then rc=3 with zero epics owned)."""

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
        root = tmp_path
        (root / "docs" / "development" / "plans").mkdir(parents=True)
        return root

    @pytest.mark.parametrize(
        "bad_name",
        ["Alpha", "a.b", "x@y", "alpha_1", "a" * 40],
        ids=["uppercase", "dot", "at-sign", "underscore", "over-32-chars"],
    )
    def test_a_name_outside_epic_orders_grammar_is_refused(
        self, tmp_path, monkeypatch, capsys, bad_name
    ):
        root = self._repo(tmp_path)
        idx = root / "docs" / "development" / "PLANS.md"
        decisions = root / "docs" / "DECISIONS.md"
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        rc = du.run_adopt([bad_name], single_window=True)
        err = capsys.readouterr().err

        assert rc == 2
        assert bad_name in err
        assert not idx.exists()
        assert not decisions.exists()

    @pytest.mark.parametrize("good_name", ["n-1", "1st"])
    def test_a_name_matching_epic_orders_grammar_is_accepted(
        self, tmp_path, monkeypatch, good_name
    ):
        root = self._repo(tmp_path)
        idx = root / "docs" / "development" / "PLANS.md"
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", idx)

        rc = du.run_adopt([good_name], single_window=True)

        assert rc == 0
        assert idx.exists()  # step (a) ran — the name passed validation

    def test_the_adopt_name_regex_is_byte_identical_to_epic_orders(self):
        assert du._ADOPT_NAME_RE.pattern == "^[a-z0-9-]{1,32}$"


# ---------------------------------------------------------------------------
# T02b — `--adopt` tags the untagged STRATEGIC_BACKLOG rows in their three
# real shapes (hub `Tag`-column table, project no-`Tag` table, bullet rows).
# ---------------------------------------------------------------------------

_BACKLOG_FIXTURE = """# Strategic Backlog

## Ownership

| Tag | Agent | Beat |
| :--- | :--- | :--- |
| `[infra]` | infra | command corpus |
| `[fleet]` | fleet | VPS + deploy |

## Now

| Effort | Tag | Item | Why Priority | Ready When |
| :--- | :--- | :--- | :--- | :--- |
| **M** |  | A hub-shaped untagged item | because | now |

## Projects

| Effort | Item | Why | Ready when |
| :--- | :--- | :--- | :--- |
| **M** | A project-shaped untagged item | because | now |

## Later

- A plain bullet row
- [ ] An unchecked checkbox bullet row
- [x] A checked checkbox bullet row
"""

_BACKLOG_SKIP_FIXTURE = """| Effort | Tag | Item | Why | Ready When |
| :--- | :--- | :--- | :--- | :--- |
| **M** | `[infra]` | An already-tagged item | because | now |
| **M** |  | ~~A resolved, struck-through item~~ | because | now |

```text
- item
```
"""


def _backlog_repo(tmp_path: Path, fixture: str = _BACKLOG_FIXTURE) -> Path:
    root = tmp_path
    plans = root / "docs" / "development" / "plans"
    plans.mkdir(parents=True)
    (root / "docs" / "STRATEGIC_BACKLOG.md").write_text(fixture, encoding="utf-8")
    return root


class TestT02bBC1ThreeShapesRoundRobin:
    """Given a fixture backlog holding a hub-shaped table (`Tag` column, one empty
    tag cell), a project-shaped table (no `Tag` column, one untagged row) and three
    bullet rows (`- `, `- [ ] `, `- [x] `), when `--adopt alpha,beta --single-window`
    runs, the empty tag cell reads `` `[alpha]` ``, the project row's second cell
    starts with `[beta] `, and the bullets read `- [alpha] …`, `- [ ] [beta] …`,
    `- [x] [alpha] …` — round-robin across all five in file order.

    RED-FIRST EVIDENCE (watched against the pre-T02b script, `git show
    c2631de2:scripts/docs_updater.py` — T02a's merged state, no `_tag_backlog_rows`
    and `run_adopt` never reads STRATEGIC_BACKLOG.md at all). BC1 calls `run_adopt`
    itself, not `_tag_backlog_rows` directly, so the baseline's `run_adopt` runs to
    completion (rc == 0) without ever touching the fixture file — the failure is an
    AssertionError on the untagged content still being there, not an AttributeError:
        FAILED tests/test_docs_updater_adopt.py::TestT02bBC1ThreeShapesRoundRobin
        ::test_three_shapes_tagged_round_robin_in_file_order
        AssertionError: assert '| **M** | `[alpha]` | A hub-shaped untagged item |
        because | now |' in ['# Strategic Backlog', '', '## Ownership', '', '| Tag |
        Agent | Beat |', '| :--- | :--- | :--- |', ...]
        (raised at this test's own `assert ... in lines` line just below — a line
        number will drift; grep this test method's name instead)
    (the backlog file was byte-identical to the fixture — the untagged rows were
    never touched — before this ticket's implementation landed. BC2/BC3/BC4 below are
    vacuously green on that same baseline for the identical reason: a script that
    never reads the file can't be caught changing it, or failing to.)
    """

    def test_three_shapes_tagged_round_robin_in_file_order(self, tmp_path, monkeypatch):
        root = _backlog_repo(tmp_path)
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

        rc = du.run_adopt(["alpha", "beta"], single_window=True)
        assert rc == 0

        text = (root / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
        lines = text.splitlines()

        assert "| **M** | `[alpha]` | A hub-shaped untagged item | because | now |" in lines
        assert "| **M** | [beta] A project-shaped untagged item | because | now |" in lines
        assert "- [alpha] A plain bullet row" in lines
        assert "- [ ] [beta] An unchecked checkbox bullet row" in lines
        assert "- [x] [alpha] A checked checkbox bullet row" in lines

        # the legend table (already carrying real tags) is untouched
        assert "| `[infra]` | infra | command corpus |" in lines
        assert "| `[fleet]` | fleet | VPS + deploy |" in lines


class TestT02bBC2SkipShapes:
    """Given a row already carrying `[infra]`, the legend table, a header row, a
    fenced block containing `- item`, and a `~~struck~~` row, when `--adopt` runs,
    none of them changes.

    RED-FIRST EVIDENCE: this test is VACUOUSLY GREEN on the pre-T02b baseline
    (`git show c2631de2:scripts/docs_updater.py`) — watched directly, `rc == 0` and
    `text == _BACKLOG_SKIP_FIXTURE` both hold, for the wrong reason: `run_adopt`
    never read STRATEGIC_BACKLOG.md at all on that baseline, so "none of them
    changes" was true of every row, tagged or not. The meaningful red for this
    behavior is BC1's (the ONLY row of the five that must not have changed but is
    exercised by a run that actually touches the file at all) — see BC1's
    AssertionError above."""

    def test_already_tagged_legend_header_fence_and_struck_rows_never_change(
        self, tmp_path, monkeypatch
    ):
        root = _backlog_repo(tmp_path, fixture=_BACKLOG_SKIP_FIXTURE)
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

        rc = du.run_adopt(["alpha"], single_window=True)
        assert rc == 0

        text = (root / "docs" / "STRATEGIC_BACKLOG.md").read_text(encoding="utf-8")
        assert text == _BACKLOG_SKIP_FIXTURE


class TestT02bBC3Idempotent:
    """Given the state after one run, a second run leaves STRATEGIC_BACKLOG.md
    byte-identical and prints `(nothing to adopt)`.

    RED-FIRST EVIDENCE: vacuously green on the pre-T02b baseline for the same reason
    as BC2 — a script that never writes to the file trivially reproduces
    `(nothing to adopt)` / byte-identical on every run. BC1's AssertionError is the
    real proof that this ticket's writer exists and does something."""

    def test_second_run_is_byte_identical_and_reports_nothing(self, tmp_path, monkeypatch, capsys):
        root = _backlog_repo(tmp_path)
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

        du.run_adopt(["alpha", "beta"], single_window=True)
        capsys.readouterr()

        backlog = root / "docs" / "STRATEGIC_BACKLOG.md"
        before = backlog.read_bytes()

        rc = du.run_adopt(["alpha", "beta"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 0
        assert out.strip() == "(nothing to adopt)"
        assert backlog.read_bytes() == before


class TestT02bBC4MissingBacklogIsSilentlyNothing:
    """Given no STRATEGIC_BACKLOG.md, `--adopt` succeeds with no `backlog-row` in
    the report.

    RED-FIRST EVIDENCE: trivially true on the pre-T02b baseline too (the code never
    looked at the file at all, so a missing file changed nothing about its
    behavior) — the meaningful proof that a real, gated file-read now exists is
    BC1's AssertionError, not a rerun of this one."""

    def test_no_backlog_file_means_no_backlog_rows_and_rc_0(self, tmp_path, monkeypatch, capsys):
        root = tmp_path
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        assert not (root / "docs" / "STRATEGIC_BACKLOG.md").exists()

        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", plans)
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

        rc = du.run_adopt(["alpha"], single_window=True)
        out = capsys.readouterr().out

        assert rc == 0
        assert "backlog-row" not in out
        assert not (root / "docs" / "STRATEGIC_BACKLOG.md").exists()


class TestT02bClassifyBacklogRowDirect:
    """Direct unit coverage of `classify_backlog_row` — the five shapes it must
    recognize plus every skip case, called without going through the file-scanning
    loop at all (the T02b<->T03 Interfaces seam: T03's `--check` advisory calls this
    same function)."""

    def test_hub_shaped_empty_tag_cell_is_table_tag(self):
        header = ["Effort", "Tag", "Item", "Why Priority", "Ready When"]
        line = "| **M** |  | A hub-shaped untagged item | because | now |"
        assert du.classify_backlog_row(line, header) == "table-tag"

    def test_project_shaped_row_with_no_tag_column_is_table_item(self):
        header = ["Effort", "Item", "Why", "Ready when"]
        line = "| **M** | A project-shaped untagged item | because | now |"
        assert du.classify_backlog_row(line, header) == "table-item"

    def test_plain_bullet_is_bullet(self):
        assert du.classify_backlog_row("- A plain bullet row", None) == "bullet"

    def test_unchecked_checkbox_bullet_is_bullet(self):
        assert du.classify_backlog_row("- [ ] An unchecked bullet", None) == "bullet"

    def test_checked_checkbox_bullet_is_bullet(self):
        assert du.classify_backlog_row("- [x] A checked bullet", None) == "bullet"

    def test_already_tagged_table_row_is_skip(self):
        header = ["Effort", "Tag", "Item", "Why", "Ready When"]
        line = "| **M** | `[infra]` | An already-tagged item | because | now |"
        assert du.classify_backlog_row(line, header) == "skip"

    def test_already_tagged_bullet_is_skip(self):
        assert du.classify_backlog_row("- [infra] already tagged", None) == "skip"

    def test_legend_table_row_is_skip(self):
        header = ["Tag", "Agent", "Beat"]
        line = "| `[infra]` | infra | command corpus |"
        assert du.classify_backlog_row(line, header) == "skip"

    def test_the_header_row_itself_is_skip(self):
        header = ["Effort", "Tag", "Item", "Why", "Ready When"]
        line = "| Effort | Tag | Item | Why | Ready When |"
        assert du.classify_backlog_row(line, header) == "skip"

    def test_a_separator_row_is_skip(self):
        header = ["Effort", "Tag", "Item", "Why", "Ready When"]
        assert du.classify_backlog_row("| :--- | :--- | :--- | :--- | :--- |", header) == "skip"

    def test_struck_through_item_cell_is_skip(self):
        header = ["Effort", "Tag", "Item", "Why", "Ready When"]
        line = "| **M** |  | ~~A resolved, struck-through item~~ | because | now |"
        assert du.classify_backlog_row(line, header) == "skip"

    def test_checkbox_x_is_never_read_as_a_name_tag(self):
        # the r1 pipeline error this guards: `[x]` must never register as "already
        # tagged" (which would silently skip a row that still needs a real tag).
        assert du.classify_backlog_row("- [x] needs a real tag still", None) == "bullet"

    def test_struck_through_bullet_is_skip(self):
        # D1 (acceptance review r1): a bullet whose content is struck through must
        # be skipped exactly like a struck table row — mutating the bullet path's
        # `startswith("~~")` to `if False` left the pre-r1 suite green (only the
        # TABLE shape had a direct assertion), so 16 of 16 struck bullets fleet-wide
        # (docs/STRATEGIC_BACKLOG.md) were unguarded against a regression here.
        assert du.classify_backlog_row("- ~~a resolved bullet~~", None) == "skip"

    def test_untagged_legend_row_is_skip(self):
        # D2 (acceptance review r1): the legend guard (`names[0] == "Tag"`) was
        # never exercised because every legend fixture row already carried a real
        # tag and was caught earlier by `_BACKLOG_ALREADY_TAGGED_RE` — this row's
        # first cell is untagged, so ONLY the legend-header check can skip it.
        header = ["Tag", "Agent", "Beat"]
        line = "|  | infra | command corpus |"
        assert du.classify_backlog_row(line, header) == "skip"

    @pytest.mark.parametrize(
        "line",
        [
            "- [fleet+infra] a cross-beat bullet",
            "- [intel→fabrik-lib] a cross-repo-routed bullet",
            "- [infra/T16 decision] a decision-suffixed bullet",
            "- [infra/docs] a slash-suffixed bullet",
        ],
        ids=["plus", "arrow", "slash-space", "slash"],
    )
    def test_compound_owner_tags_are_already_tagged_skip(self, line):
        # D3 (acceptance review r1): the pre-r1 `_BACKLOG_ALREADY_TAGGED_RE`
        # (`\[(?!x\])[a-z0-9-]{1,32}\]`) only matched a bare name, so 4 of 54 hub
        # bullets already headed by a compound owner tag
        # (docs/STRATEGIC_BACKLOG.md:55/56/60/908) would get a SECOND tag inserted
        # on `--adopt`. The widened regex must still recognize all four real shapes.
        assert du.classify_backlog_row(line, None) == "skip"

    @pytest.mark.parametrize(
        "line",
        [
            "- [x] still needs a real tag",
            "- [ ] still needs a real tag",
            "- [X] still needs a real tag",
        ],
        ids=["lower-x", "empty", "upper-X"],
    )
    def test_checkbox_variants_are_never_read_as_a_tag(self, line):
        # D3: the widened already-tagged regex must still treat every checkbox
        # spelling (`[x]`, `[ ]`, `[X]`) as checkbox syntax, never a name — a
        # regression here would silently skip a row that still needs a real tag.
        assert du.classify_backlog_row(line, None) == "bullet"

    def test_hub_shaped_owner_header_is_table_tag(self):
        # D5 (acceptance review r1): the hub's REAL "Now" table header names its
        # tag cell `Owner`, never `Tag` (grep `^| Effort \| Owner \| Item` in
        # docs/STRATEGIC_BACKLOG.md — a line number will drift — for
        # `| Effort | Owner | Item | Why Priority | Ready When |`; `Tag` lives
        # only in the legend two sections above it). The pre-r1 code matched
        # literal `Tag` only, so this exact real-world header fell through to
        # `"table-item"` and would have double-prefixed the Item cell instead of
        # writing into the empty Owner cell.
        header = ["Effort", "Owner", "Item", "Why Priority", "Ready When"]
        line = "| **M** |  | A hub-shaped untagged item | because | now |"
        assert du.classify_backlog_row(line, header) == "table-tag"

    def test_hub_shaped_owner_header_already_occupied_is_skip(self):
        header = ["Effort", "Owner", "Item", "Why Priority", "Ready When"]
        line = "| **M** | `[fleet]` | An already-owned item | because | now |"
        assert du.classify_backlog_row(line, header) == "skip"


class TestT02bD6RoundRobinAcrossInterleavedShapes:
    """D6 (acceptance review r1): `_tag_backlog_rows` keeps ONE shared round-robin
    counter across all three shapes — the pre-r1 test fixtures never interleaved
    shapes (BC1's fixture runs table-tag, then table-item, then all three bullets,
    never back-and-forth), so a regression that gave each shape its OWN counter
    would have gone undetected. This fixture alternates bullet / table-item /
    bullet / table-tag and asserts the round-robin counter carries across the
    shape boundary each time."""

    _INTERLEAVED_FIXTURE = """- first bullet row

| Effort | Item | Why | Ready when |
| :--- | :--- | :--- | :--- |
| **M** | a project-shaped row | because | now |

- second bullet row

| Effort | Tag | Item | Why | Ready When |
| :--- | :--- | :--- | :--- | :--- |
| **M** |  | a hub-shaped row | because | now |
"""

    def test_alpha_beta_alpha_beta_across_shape_boundaries(self):
        new_text, report = du._tag_backlog_rows(self._INTERLEAVED_FIXTURE, ["alpha", "beta"])

        assert [name for (_excerpt, name, _kind) in report] == ["alpha", "beta", "alpha", "beta"]

        lines = new_text.splitlines()
        assert "- [alpha] first bullet row" in lines
        assert "| **M** | [beta] a project-shaped row | because | now |" in lines
        assert "- [alpha] second bullet row" in lines
        assert "| **M** | `[beta]` | a hub-shaped row | because | now |" in lines


# ---------------------------------------------------------------------------
# T02b round-2 acceptance review, DEFECT-1: "already tagged" is decided ONLY at
# the row's own tag POSITION, never by searching the whole line.
# ---------------------------------------------------------------------------

# (content_after_marker_or_cell, is_a_real_tag, id) — the fleet's real grammar
# boundary. Measured over 25 backlogs / 1618 candidate rows: the r1 whole-line
# `.search()` misread 54 of 58 "already tagged" rows fleet-wide across 15 repos
# (`[key: string]`, `[tool.ruff]`, `[0-9A-F]`, `[0.831, 0.940]`, `[the review]`,
# `[1-liner value]`, a markdown link's `[label](url)`) as an existing tag.
_BACKLOG_TAG_POSITION_SHAPES = [
    ("[fleet+infra] a cross-beat item", True, "plus"),
    ("[intel→fabrik-lib] a cross-repo-routed item", True, "arrow"),
    ("[infra/docs] a slash-suffixed item", True, "slash"),
    ("[infra/T16 decision] a decision-suffixed item", True, "slash-space"),
    ("[see the docs](x.md) explains it", False, "md-link-space-head"),
    ("[prometheus-app-metrics-setup.md](y.md) is linked", False, "md-link-dot-head"),
    ("[2026-09-06] shipped this change", False, "date"),
    ("[key: string] appears in the prose", False, "colon"),
    ("[x] needs a real tag still", False, "checkbox-lower-x"),
    ("[ ] needs a real tag still", False, "checkbox-empty"),
    ("[X] needs a real tag still", False, "checkbox-upper-x"),
    ("[WIP] needs a real tag still", False, "uppercase-wip"),
]

_NON_CHECKBOX_SHAPES = [t for t in _BACKLOG_TAG_POSITION_SHAPES if not t[2].startswith("checkbox")]


class TestT02bR2Defect1AnchoredTagPosition:
    """r2 DEFECT-1 (H): `classify_backlog_row`'s r1 "already tagged" check was
    `_BACKLOG_ALREADY_TAGGED_RE.search(line)` — searched over the WHOLE row, so
    any prose bracket anywhere read as a tag. Fixed at the mechanism: a tag is
    now recognized ONLY at the row's own tag position (right after a bullet's
    marker/checkbox/leading `**`, or a table-item row's Item-cell start) via
    `_backlog_starts_with_tag` + `_BACKLOG_TAG_AT_POS_RE`, never by scanning the
    rest of the row.

    RED-FIRST EVIDENCE (watched against the pre-DEFECT-1 script — the r1 widened
    `_BACKLOG_ALREADY_TAGGED_RE.search(line)` at the top of `classify_backlog_row`,
    committed as `3ba09e23`): the two probes named in the review —
        classify_backlog_row("- [see the docs](x.md) explains it", None)
        # pre-fix: 'skip'  (WRONG — must be 'bullet')
        classify_backlog_row(
            "| **M** | [prometheus-app-metrics-setup.md](y.md) is linked | "
            "because | now |",
            ["Effort", "Item", "Why", "Ready when"],
        )
        # pre-fix: 'skip'  (WRONG — must be 'table-item')
    Both READ the whole-line search's false positive; both are asserted below as
    part of the parametrized sweep."""

    @pytest.mark.parametrize(
        "content,is_tag,shape_id",
        _BACKLOG_TAG_POSITION_SHAPES,
        ids=[t[2] for t in _BACKLOG_TAG_POSITION_SHAPES],
    )
    def test_table_item_cell_start(self, content, is_tag, shape_id):
        header = ["Effort", "Item", "Why", "Ready when"]
        line = f"| **M** | {content} | because | now |"
        expected = "skip" if is_tag else "table-item"
        assert du.classify_backlog_row(line, header) == expected

    @pytest.mark.parametrize(
        "content,is_tag,shape_id",
        _NON_CHECKBOX_SHAPES,
        ids=[t[2] for t in _NON_CHECKBOX_SHAPES],
    )
    def test_bullet_content_start(self, content, is_tag, shape_id):
        # the three checkbox shapes are excluded here — `- [x] `, `- [ ] `,
        # `- [X] ` are absorbed by the MARKER's own optional checkbox group
        # before content is ever probed (pre-existing coverage:
        # `test_checkbox_x_is_never_read_as_a_name_tag`,
        # `test_checkbox_variants_are_never_read_as_a_tag`); this class instead
        # tests the position probe on content the marker regex does NOT consume,
        # proven separately just below for the double-bracket case.
        line = f"- {content}"
        expected = "skip" if is_tag else "bullet"
        assert du.classify_backlog_row(line, None) == expected

    @pytest.mark.parametrize(
        "token", ["[x]", "[ ]", "[X]", "[WIP]"], ids=["lower-x", "empty", "upper-X", "wip"]
    )
    def test_checkbox_or_uppercase_token_after_a_real_checkbox_is_never_a_second_tag(self, token):
        # the realistic double-bracket case: a REAL checkbox marker is consumed
        # by the bullet regex first, so the look-alike token sits AT the row's
        # own tag position in the remaining content — exactly where DEFECT-1's
        # false-positive class lived.
        line = f"- [ ] {token} still needs a real tag"
        assert du.classify_backlog_row(line, None) == "bullet"

    def test_bullet_with_key_string_prose_still_gets_tagged(self):
        # the ONE regression test the review asked for: a bullet whose PROSE
        # contains `[key: string]` after an UNTAGGED head must still be tagged —
        # the pre-fix whole-line search read `[key: string]` anywhere in the row
        # as "already tagged" and left the row untouched.
        text = "- A note about the `[key: string]` type hint\n"
        new_text, report = du._tag_backlog_rows(text, ["alpha"])

        assert new_text == "- [alpha] A note about the `[key: string]` type hint\n"
        assert len(report) == 1
        _excerpt, name, kind = report[0]
        assert (name, kind) == ("alpha", "backlog-row")


class TestT03CheckAdvisory:
    """T03 (multi-agent-per-repo spec § The delta D3): `run_check()`'s ownership
    advisory fires exactly one `ADVISORY:` line, ONLY when ≥2 live `claude` sessions
    share this checkout AND ownership is incomplete (merge owner undeclared / an
    open plan unowned / a backlog row untagged); it is collected SEPARATELY from
    `issues` so it can never change the exit code, and is suppressed unconditionally
    in the hub."""

    @staticmethod
    def _repo(
        tmp_path: Path,
        *,
        merge_owner: bool,
        plan_owned: bool,
        backlog_tagged: bool,
        hub: bool = False,
    ) -> Path:
        root = tmp_path / "repo"
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        (plans / "2026-01-01-plan-1-open.md").write_text(
            "# Plan\n\n" + ("**Owner:** alpha\n" if plan_owned else "") + "Status: DRAFT\n",
            encoding="utf-8",
        )
        decisions = root / "docs" / "DECISIONS.md"
        if merge_owner:
            _decisions_with_merge_owner(decisions)
        else:
            _decisions_no_merge_owner(decisions)
        backlog = root / "docs" / "STRATEGIC_BACKLOG.md"
        if backlog_tagged:
            backlog.write_text("- [alpha] Already tagged item\n", encoding="utf-8")
        else:
            backlog.write_text("- An untagged backlog item\n", encoding="utf-8")
        if hub:
            scripts = root / "scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            (scripts / "fabrik_synced_manifest.py").write_text("# hub\n", encoding="utf-8")
        return root

    @staticmethod
    def _patch(monkeypatch, root: Path) -> None:
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")
        monkeypatch.setattr(du, "PLANS_INDEX", root / "docs" / "development" / "PLANS.md")

    def test_two_sessions_incomplete_ownership_prints_exactly_one_advisory_line(
        self, tmp_path, monkeypatch, capsys
    ):
        """BC row 1: two `claude` processes at the fixture root, no `MERGE OWNER:`
        row — `run_check()` prints exactly one `ADVISORY:` line naming `2 sessions`
        and `--adopt`, and its return value never depends on the advisory (proven by
        re-running with the advisory monkeypatched to `[]`). D6 mutation-guard: the
        advisory line prints LAST — after the pass line / issues block, never
        interleaved above it."""
        root = self._repo(tmp_path, merge_owner=False, plan_owned=True, backlog_tagged=True)
        proc_root = _fake_proc(tmp_path, [("claude", root), ("claude", root)])
        self._patch(monkeypatch, root)

        rc = du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out
        advisory_lines = [ln for ln in out.splitlines() if ln.startswith("ADVISORY:")]

        assert len(advisory_lines) == 1, out
        assert "2 sessions" in advisory_lines[0]
        assert "--adopt" in advisory_lines[0]
        assert "merge owner undeclared" in advisory_lines[0]

        non_blank_lines = [ln for ln in out.splitlines() if ln.strip()]
        assert non_blank_lines[-1] == advisory_lines[0], out

        monkeypatch.setattr(du, "validate_ownership_advisory", lambda *a, **k: [])
        rc_without_advisory = du.run_check(proc_root=proc_root)

        assert rc == rc_without_advisory

    def test_one_session_prints_no_advisory_even_when_ownership_is_incomplete(
        self, tmp_path, monkeypatch, capsys
    ):
        """BC row 2 (first half): one process in the fake proc tree — no `ADVISORY:`
        line, however incomplete ownership is."""
        root = self._repo(tmp_path, merge_owner=False, plan_owned=False, backlog_tagged=False)
        proc_root = _fake_proc(tmp_path, [("claude", root)])
        self._patch(monkeypatch, root)

        du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out

        assert not any(ln.startswith("ADVISORY:") for ln in out.splitlines()), out

    def test_hub_identity_suppresses_the_advisory_even_at_two_sessions(
        self, tmp_path, monkeypatch, capsys
    ):
        """BC row 2 (second half): two processes, but
        `scripts/fabrik_synced_manifest.py` is present (hub identity) — no
        `ADVISORY:` line, however incomplete ownership is."""
        root = self._repo(
            tmp_path, merge_owner=False, plan_owned=False, backlog_tagged=False, hub=True
        )
        proc_root = _fake_proc(tmp_path, [("claude", root), ("claude", root)])
        self._patch(monkeypatch, root)

        du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out

        assert not any(ln.startswith("ADVISORY:") for ln in out.splitlines()), out

    @pytest.mark.parametrize("session_count", [1, 2], ids=["1-session", "2-sessions"])
    @pytest.mark.parametrize("complete", [True, False], ids=["complete", "incomplete"])
    def test_advisory_fires_only_at_two_sessions_and_incomplete_ownership(
        self, tmp_path, monkeypatch, capsys, session_count, complete
    ):
        """BC row 3: parametrized over the four combinations of
        (sessions ∈ {1,2}) × (ownership complete/incomplete) — only (2, incomplete)
        prints the advisory. "complete" = a declared merge owner, every open plan
        owned, and every backlog row already tagged."""
        root = self._repo(
            tmp_path, merge_owner=complete, plan_owned=complete, backlog_tagged=complete
        )
        proc_root = _fake_proc(tmp_path, [("claude", root)] * session_count)
        self._patch(monkeypatch, root)

        du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out
        fires = any(ln.startswith("ADVISORY:") for ln in out.splitlines())

        assert fires == (session_count == 2 and not complete), out

    def test_an_unowned_but_terminal_plan_never_fires_the_advisory(
        self, tmp_path, monkeypatch, capsys
    ):
        """D1 mutation-guard: `_count_unowned_plans` must skip TERMINAL-status plans
        (EXECUTED, COMPLETE) exactly like `run_adopt()`'s own step (b) — an unowned
        but EXECUTED plan, with a declared merge owner and a tagged backlog, must
        never fire the advisory. Deleting that skip leaves this the only test that
        catches it (every other case here uses `Status: DRAFT`)."""
        root = tmp_path / "repo"
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        (plans / "2026-01-01-plan-1-done.md").write_text(
            "# Plan\n\nStatus: EXECUTED\n", encoding="utf-8"
        )
        _decisions_with_merge_owner(root / "docs" / "DECISIONS.md")
        (root / "docs" / "STRATEGIC_BACKLOG.md").write_text(
            "- [alpha] Already tagged item\n", encoding="utf-8"
        )
        proc_root = _fake_proc(tmp_path, [("claude", root), ("claude", root)])
        self._patch(monkeypatch, root)

        du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out

        assert not any(ln.startswith("ADVISORY:") for ln in out.splitlines()), out

    _LIMB_CASES = [
        pytest.param(
            {"merge_owner": False, "plan_owned": True, "backlog_tagged": True},
            "merge owner undeclared",
            ("unowned plans", "untagged backlog rows"),
            id="merge-owner-undeclared-alone",
        ),
        pytest.param(
            {"merge_owner": True, "plan_owned": False, "backlog_tagged": True},
            "1 unowned plans",
            ("merge owner undeclared", "untagged backlog rows"),
            id="one-unowned-plan-alone",
        ),
        pytest.param(
            {"merge_owner": True, "plan_owned": True, "backlog_tagged": False},
            "1 untagged backlog rows",
            ("merge owner undeclared", "unowned plans"),
            id="one-untagged-backlog-row-alone",
        ),
    ]

    @pytest.mark.parametrize("flags,expected,forbidden", _LIMB_CASES)
    def test_each_incompleteness_limb_alone_names_only_itself(
        self, tmp_path, monkeypatch, capsys, flags, expected, forbidden
    ):
        """D2 mutation-guard: BC row 3's combined "incomplete" fixture makes all
        three limbs false together, so a mutant that neutralizes ONE counting
        function (e.g. forcing `_count_untagged_backlog_rows` to always return 0)
        still finds the advisory firing via the other two limbs and leaves the
        suite green. Each limb is now incomplete ALONE — the advisory line must
        name exactly that limb and none of the other two."""
        root = self._repo(tmp_path, **flags)
        proc_root = _fake_proc(tmp_path, [("claude", root), ("claude", root)])
        self._patch(monkeypatch, root)

        du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out
        advisory_lines = [ln for ln in out.splitlines() if ln.startswith("ADVISORY:")]

        assert len(advisory_lines) == 1, out
        assert expected in advisory_lines[0], advisory_lines[0]
        for f in forbidden:
            assert f not in advisory_lines[0], advisory_lines[0]

    def test_all_three_limbs_incomplete_join_into_one_line_in_order(
        self, tmp_path, monkeypatch, capsys
    ):
        """D2: with all three limbs incomplete, exactly ONE `ADVISORY:` line carries
        all three parts, joined by `"; "` in the merge-owner / unowned-plans /
        untagged-backlog-rows order."""
        root = self._repo(tmp_path, merge_owner=False, plan_owned=False, backlog_tagged=False)
        proc_root = _fake_proc(tmp_path, [("claude", root), ("claude", root)])
        self._patch(monkeypatch, root)

        du.run_check(proc_root=proc_root)
        out = capsys.readouterr().out
        advisory_lines = [ln for ln in out.splitlines() if ln.startswith("ADVISORY:")]

        assert len(advisory_lines) == 1, out
        assert (
            "merge owner undeclared; 1 unowned plans; 1 untagged backlog rows" in advisory_lines[0]
        ), advisory_lines[0]

    def test_at_one_session_the_ownership_files_are_never_read(self, tmp_path, monkeypatch):
        """D5 mutation-guard: the ≥2-session guard must run BEFORE any ownership
        file is read (`read_merge_owner`, the plan scan, the backlog file) — proven
        by making `read_merge_owner` raise and asserting a 1-session repo still
        returns `[]` without the exception ever propagating (i.e. without
        `read_merge_owner` ever being called). Moving the guard below the file
        reads would make this test fail with the injected exception instead of
        returning `[]`."""
        root = tmp_path / "repo"
        plans = root / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        proc_root = _fake_proc(tmp_path, [("claude", root)])
        monkeypatch.setattr(du, "PROJECT_ROOT", root)
        monkeypatch.setattr(du, "PLANS_DIR", root / "docs" / "development" / "plans")

        def _boom():
            raise AssertionError("read_merge_owner must not be called at <2 sessions")

        monkeypatch.setattr(du, "read_merge_owner", _boom)

        result = du.validate_ownership_advisory(proc_root)

        assert result == []


class TestT03GateWiring:
    """T03 (multi-agent-per-repo spec § The delta D3): the gate's `Documentation
    Drift` optional check gains `advisory=True` — proven both ways, so the wiring is
    real, not cosmetic: the call site carries the keyword (syntactic), AND
    `run_optional_check(advisory=True)` actually preserves an exit-0 check's stdout
    while `advisory=False` (the default) drops it (BEHAVIOURAL — D3: the docstring
    alone was not proof the wiring did anything; a stub script + a real call to
    `final_gate.run_optional_check` is)."""

    _FINAL_GATE = Path(__file__).parent.parent / "scripts" / "final_gate.py"

    def test_documentation_drift_call_carries_advisory_true(self):
        source = self._FINAL_GATE.read_text(encoding="utf-8")
        m = re.search(
            r'run_optional_check\(\s*"scripts/docs_updater\.py",\s*"Documentation Drift"[^)]*\)',
            source,
        )
        assert m is not None, "the Documentation Drift run_optional_check call was not found"
        assert "advisory=True" in m.group(0), m.group(0)

    def test_run_optional_check_preserves_advisory_stdout_on_a_green_exit(self, tmp_path):
        """D3: an exit-0 stub script's `ADVISORY: probe` line survives in the
        returned message with `advisory=True`, and is dropped without it — proving
        the keyword's own contract behaviourally, not by reading its docstring. The
        stub's path is passed ABSOLUTE (`PROJECT_ROOT / <absolute path>` resolves to
        the absolute path itself — the same trick `test_final_gate_advisory_display.py`
        uses), so `final_gate.PROJECT_ROOT` never needs monkeypatching."""
        script = tmp_path / "stub_check.py"
        script.write_text("print('ADVISORY: probe')\n", encoding="utf-8")

        _, passed, message = fg.run_optional_check(str(script), "Stub Check", advisory=True)
        assert passed
        assert "ADVISORY: probe" in message, message

        _, passed_plain, message_plain = fg.run_optional_check(str(script), "Stub Check Plain")
        assert passed_plain
        assert "ADVISORY: probe" not in message_plain, message_plain
