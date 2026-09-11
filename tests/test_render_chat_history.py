"""Graders for scripts/render_chat_history.py — the per-project chat-history renderer.

Each behaviour below was watched RED before the script existed (ImportError) and is
mutation-proven against the specific branch it guards.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "render_chat_history", _HERE / "scripts" / "render_chat_history.py"
)
rch = importlib.util.module_from_spec(_SPEC)
sys.modules["render_chat_history"] = rch
_SPEC.loader.exec_module(rch)


def _rec(kind: str, text: str, ts: str, **extra: object) -> dict:
    body: dict = {
        "type": kind,
        "uuid": f"{kind}-{ts}",
        "timestamp": ts,
        "cwd": "/opt/demo",
        "message": {"role": kind, "content": [{"type": "text", "text": text}]},
    }
    body.update(extra)
    return body


def _write_session(projects: Path, sid: str, records: list[dict]) -> Path:
    projects.mkdir(parents=True, exist_ok=True)
    path = projects / f"{sid}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def _demo_records() -> list[dict]:
    return [
        _rec("user", "first ask", "2026-09-01T10:00:00.000Z"),
        _rec("assistant", "first answer", "2026-09-01T10:00:05.000Z"),
        {
            "type": "user",
            "uuid": "tool-1",
            "timestamp": "2026-09-01T10:00:06.000Z",
            "toolUseResult": {"stdout": "x"},
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": "noise"},
                    {"type": "text", "text": "noise carried beside a tool result"},
                ],
            },
        },
        {
            "type": "system",
            "subtype": "compact_boundary",
            "uuid": "b-1",
            "timestamp": "2026-09-02T08:00:00.000Z",
            "compactMetadata": {"trigger": "auto", "preTokens": 900000},
        },
        _rec(
            "user",
            "This session is being continued from a previous conversation",
            "2026-09-02T08:00:01.000Z",
            isCompactSummary=True,
        ),
        _rec(
            "user",
            "<system-reminder>hidden</system-reminder>second ask",
            "2026-09-02T08:01:00.000Z",
        ),
        _rec("assistant", "second answer", "2026-09-02T08:01:05.000Z"),
    ]


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    projects = tmp_path / "projects" / "-opt-demo"
    _write_session(projects, "aaaa1111-0000-0000-0000-000000000000", _demo_records())
    out = tmp_path / "state" / "history"
    monkeypatch.setattr(rch, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(rch, "OUT_ROOT", out)
    return {"projects": projects, "out": out}


def test_compaction_becomes_a_dated_heading_and_the_last_one_is_marked(
    box: dict[str, Path],
) -> None:
    rch.main(["--project", "/opt/demo"])
    md = (box["out"] / "-opt-demo" / "aaaa1111.md").read_text()
    assert "## ⟲ Compaction #1 — 2026-09-02 08:00:00" in md
    assert "reloaded VS Code window starts HERE" in md


def test_tool_results_and_system_reminders_are_stripped_but_turns_survive(
    box: dict[str, Path],
) -> None:
    rch.main(["--project", "/opt/demo"])
    md = (box["out"] / "-opt-demo" / "aaaa1111.md").read_text()
    assert "noise" not in md
    assert "hidden" not in md
    for needle in ("first ask", "first answer", "second ask", "second answer"):
        assert needle in md


def test_session_name_mapping_names_the_file_and_persists(box: dict[str, Path]) -> None:
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=agent-2"])
    assert (box["out"] / "-opt-demo" / "agent-2.md").exists()
    # A later run WITHOUT --name keeps the name (mapping persisted beside the renders).
    rch.main(["--project", "/opt/demo"])
    assert (box["out"] / "-opt-demo" / "agent-2.md").exists()
    assert not (box["out"] / "-opt-demo" / "aaaa1111.md").exists()


def test_unchanged_transcript_is_not_rerendered(box: dict[str, Path]) -> None:
    rch.main(["--project", "/opt/demo"])
    target = box["out"] / "-opt-demo" / "aaaa1111.md"
    first = target.stat().st_mtime_ns
    target.write_text("sentinel")  # if the renderer rewrites, the sentinel disappears
    rch.main(["--project", "/opt/demo"])
    assert target.read_text() == "sentinel"
    assert target.stat().st_mtime_ns >= first


def test_project_index_lists_every_session_newest_first(box: dict[str, Path]) -> None:
    older = _demo_records()
    for r in older:
        r["timestamp"] = r["timestamp"].replace("2026-09-0", "2026-08-0")
        r["uuid"] = "old-" + r["uuid"]
    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", older)
    rch.main(["--project", "/opt/demo"])
    index = (box["out"] / "-opt-demo" / "INDEX.md").read_text()
    assert index.index("aaaa1111") < index.index("bbbb2222")
    assert index.count("| `") == 2  # one row per session, no header counted


def test_unknown_project_is_a_named_error_not_a_traceback(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    rc = rch.main(["--project", "/opt/nope"])
    assert rc == 1
    assert "no transcripts" in capsys.readouterr().err


def test_a_real_repo_path_resolves_to_its_project_key(box: dict[str, Path], tmp_path: Path) -> None:
    # An existing absolute repo path must map to Claude's key, never be taken as a key itself.
    repo = tmp_path / "opt" / "demo"
    repo.mkdir(parents=True)
    (box["projects"].parent / rch._key_for(str(repo))).mkdir()
    _write_session(
        box["projects"].parent / rch._key_for(str(repo)),
        "cccc3333-0000-0000-0000-000000000000",
        _demo_records(),
    )
    assert rch.main(["--project", str(repo)]) == 0
    assert (box["out"] / rch._key_for(str(repo)) / "cccc3333.md").exists()


def test_two_sessions_given_one_label_never_share_a_file(box: dict[str, Path]) -> None:
    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=agent-1", "--name", "bbbb2222=agent-1"])
    files = sorted(p.name for p in (box["out"] / "-opt-demo").glob("*.md") if p.name != "INDEX.md")
    assert len(files) == 2, files
    assert "agent-1.md" in files
    index = (box["out"] / "-opt-demo" / "INDEX.md").read_text()
    assert index.count("| `") == 2
    assert index.count("(agent-1.md)") == 1


def test_relabel_onto_an_existing_label_never_deletes_the_other_sessions_file(
    box: dict[str, Path],
) -> None:
    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=x", "--name", "bbbb2222=y"])
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=y"])
    out = box["out"] / "-opt-demo"
    files = sorted(p.name for p in out.glob("*.md") if p.name != "INDEX.md")
    assert len(files) == 2, files
    index = out.read_text() if out.is_file() else (out / "INDEX.md").read_text()
    for name in files:
        assert f"({name})" in index, (name, index)


@pytest.mark.parametrize("fname", ["names.json", ".render-state.json"])
def test_a_non_dict_sidecar_is_ignored_not_a_crash(box: dict[str, Path], fname: str) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / fname).write_text("[]")
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert (out / "aaaa1111.md").exists()


def test_an_unreadable_transcript_is_skipped_with_a_warning_and_the_rest_renders(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    bad = _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    bad.chmod(0)
    try:
        rc = rch.main(["--project", "/opt/demo"])
    finally:
        bad.chmod(0o600)
    assert rc == 1
    assert "WARN" in capsys.readouterr().err
    assert (box["out"] / "-opt-demo" / "aaaa1111.md").exists()


def test_a_deleted_render_is_regenerated_even_when_the_transcript_is_unchanged(
    box: dict[str, Path],
) -> None:
    rch.main(["--project", "/opt/demo"])
    target = box["out"] / "-opt-demo" / "aaaa1111.md"
    target.unlink()
    rch.main(["--project", "/opt/demo"])
    assert target.exists()


def test_a_name_prefix_shorter_than_eight_chars_is_refused(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert rch.main(["--project", "/opt/demo", "--name", "aaa=agent-1"]) == 2
    assert "at least 8" in capsys.readouterr().err


def test_a_broken_symlink_transcript_is_skipped_not_a_traceback(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    (box["projects"] / "bbbb2222-0000-0000-0000-000000000000.jsonl").symlink_to(
        "/nonexistent/x.jsonl"
    )
    assert rch.main(["--project", "/opt/demo"]) == 1
    assert "WARN" in capsys.readouterr().err
    assert (box["out"] / "-opt-demo" / "aaaa1111.md").exists()


def test_a_rename_whose_render_fails_keeps_the_old_file_and_a_true_index(
    box: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=old-label"])
    out = box["out"] / "-opt-demo"
    real = rch.render_session

    def failing(path: Path, target: Path, label: str) -> dict:  # the new name cannot be written
        if label == "new-label":
            raise OSError(28, "No space left on device")
        return real(path, target, label)

    monkeypatch.setattr(rch, "render_session", failing)
    assert rch.main(["--project", "/opt/demo", "--name", "aaaa1111=new-label"]) == 1
    assert (out / "old-label.md").exists()
    index = (out / "INDEX.md").read_text()
    assert "(old-label.md)" in index and "(new-label.md)" not in index


def test_a_relabel_never_overwrites_an_orphaned_render(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=keep"])
    out = box["out"] / "-opt-demo"
    orphan = out / "keep.md"
    (
        box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    ).unlink()  # transcript gone; render stays
    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    before = orphan.read_text()
    assert rch.main(["--project", "/opt/demo", "--name", "bbbb2222=keep"]) == 0
    assert orphan.read_text() == before
    assert (out / "keep-bbbb2222.md").exists()
    assert "WARN" in capsys.readouterr().err


def test_a_non_object_names_file_is_preserved_and_warned_before_being_replaced(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "names.json").write_text("[1, 2]")
    assert rch.main(["--project", "/opt/demo", "--name", "aaaa1111=agent-1"]) == 0
    assert "WARN" in capsys.readouterr().err
    kept = list(out.glob("names.json.bad*"))
    assert kept and kept[0].read_text() == "[1, 2]"
    assert json.loads((out / "names.json").read_text()) == {"aaaa1111": "agent-1"}


def test_after_a_skip_the_index_row_survives_only_while_its_file_does(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    rch.main(["--project", "/opt/demo"])
    out = box["out"] / "-opt-demo"
    bad = box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    bad.write_text("changed\n")  # new signature → a re-render is attempted
    bad.chmod(0)
    try:
        assert rch.main(["--project", "/opt/demo"]) == 1
        assert "(aaaa1111.md)" in (out / "INDEX.md").read_text()  # previous render still there
        (out / "aaaa1111.md").unlink()
        assert rch.main(["--project", "/opt/demo"]) == 1
        assert (
            "(aaaa1111.md)" not in (out / "INDEX.md").read_text()
        )  # never advertise a missing file
    finally:
        bad.chmod(0o600)
    capsys.readouterr()


def test_a_label_from_names_json_can_never_leave_the_project_folder(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "names.json").write_text(json.dumps({"aaaa1111": "../escaped"}))
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert not (box["out"] / "escaped.md").exists()
    assert (out / "aaaa1111.md").exists()
    assert "WARN" in capsys.readouterr().err


@pytest.mark.parametrize("label", ["INDEX", "names", ".hidden", "..", "a/b"])
def test_reserved_or_unsafe_labels_are_refused_on_the_command_line(
    box: dict[str, Path], label: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rch.main(["--project", "/opt/demo", "--name", f"aaaa1111={label}"]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_a_half_written_state_entry_reads_as_never_rendered(box: dict[str, Path]) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / ".render-state.json").write_text(
        json.dumps({"aaaa1111-0000-0000-0000-000000000000": "corrupted"})
    )
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert (out / "aaaa1111.md").exists()
