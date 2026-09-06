"""Tests for `docs_updater.py --adopt` (T02a, multi-agent adoption plan).

One test per Behavior Contract row (T02a-adopt-core.md). Every fixture builds a
scratch repo under `tmp_path` and monkeypatches `docs_updater.PROJECT_ROOT` /
`PLANS_DIR` / `PLANS_INDEX` — never the real /opt/fabrik tree, and `--adopt` is
never invoked against anything but a tmp_path fixture (per the ticket's hard
constraint: this flag must never run for real from inside a subagent worktree).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import docs_updater as du  # noqa: E402

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


class TestBC1FirstAdoptRun:
    """Given a scratch repo with a marker-less PLANS.md, two open plans with no Owner
    line, one EXECUTED plan, and a ledger with no MERGE OWNER row, when
    `--adopt alpha,beta --single-window` runs, PLANS.md gains the markers and a block
    whose second header line names alpha, both open plans get Owner lines round-robin,
    the EXECUTED plan is untouched, one MERGE OWNER row is appended, and the printed
    table has one row per change."""

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
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
    and prints `(nothing to adopt)`."""

    def test_second_identical_run_is_a_byte_identical_no_op(self, tmp_path, monkeypatch, capsys):
        root = TestBC1FirstAdoptRun._repo(tmp_path)
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
        assert "epic_order" in out
        assert "rc=0" in out

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
