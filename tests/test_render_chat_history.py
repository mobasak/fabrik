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


def test_meta_records_are_never_rendered(box: dict[str, Path]) -> None:
    recs = _demo_records()
    recs.append(_rec("user", "meta-hidden text", "2026-09-02T09:00:00.000Z", isMeta=True))
    _write_session(box["projects"], "aaaa1111-0000-0000-0000-000000000000", recs)
    rch.main(["--project", "/opt/demo"])
    md = (box["out"] / "-opt-demo" / "aaaa1111.md").read_text()
    assert "meta-hidden" not in md
    assert "second ask" in md


def test_a_failed_write_never_truncates_the_previous_render_or_leaves_a_temp_file(
    box: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    rch.main(["--project", "/opt/demo"])
    out = box["out"] / "-opt-demo"
    target = out / "aaaa1111.md"
    before = target.read_text()
    bad = box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    bad.write_text(bad.read_text() + "\n")  # new signature → a re-render is attempted
    real_write = Path.write_text

    def partial_write(self: Path, data: str, *a: object, **k: object) -> int:
        if self.name.startswith("aaaa1111.md"):  # the render's own write dies mid-way (ENOSPC)
            real_write(self, data[:10], *a, **k)
            raise OSError(28, "No space left on device")
        return real_write(self, data, *a, **k)

    monkeypatch.setattr(Path, "write_text", partial_write)
    assert rch.main(["--project", "/opt/demo"]) == 1
    assert target.read_text() == before
    assert not list(out.glob("*.tmp"))


def test_a_stale_old_name_that_another_session_just_took_is_not_unlinked(
    box: dict[str, Path],
) -> None:
    # A rendered as x.md, then its render was deleted; in the same later run A is renamed to z
    # and B takes x — B (sorted after A? no: bbbb sorts after aaaa, so render order is A then B)
    # so make the RENAMED session sort AFTER the one taking its old name.
    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    rch.main(["--project", "/opt/demo", "--name", "bbbb2222=x"])
    out = box["out"] / "-opt-demo"
    (out / "x.md").unlink()  # B's render is gone; its state entry still says file x.md
    rch.main(["--project", "/opt/demo", "--name", "aaaa1111=x", "--name", "bbbb2222=z"])
    assert (out / "x.md").exists() and "aaaa1111" in (out / "x.md").read_text()
    assert (out / "z.md").exists()
    index = (out / "INDEX.md").read_text()
    assert "(x.md)" in index and "(z.md)" in index


# ---- pass-1 seat A residue (heavy review): every guard must hold for every shape, not one type ----


@pytest.mark.parametrize("line", ["null", "{not json", "[1, 2]"])
def test_a_record_that_is_not_an_object_is_dropped_and_warned(
    box: dict[str, Path], line: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    path.write_text(path.read_text() + line + "\n")
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert "1 unparseable record" in capsys.readouterr().err
    md = (box["out"] / "-opt-demo" / "aaaa1111.md").read_text()
    assert "second answer" in md and "unparseable records: 1" in md


@pytest.mark.parametrize(
    "line",
    [
        '{"type":"system","subtype":"compact_boundary","uuid":"b9","timestamp":"2026-09-02T08:00:00.000Z","compactMetadata":"manual"}',
        '{"type":"user","uuid":"u9","timestamp":"2026-09-02T08:00:00.000Z","message":"oops"}',
        '{"type":"user","uuid":"u8","timestamp":1757577600,"message":{"content":"numeric stamp"}}',
        '{"type":"user","uuid":"u7","timestamp":"2026-09-02T08:00:00.000Z","message":{"content":["not a block", {"type":"text","text":"listed text"}]}}',
    ],
)
def test_a_record_with_an_unexpected_nested_shape_is_tolerated_not_a_crash(
    box: dict[str, Path], line: str
) -> None:
    path = box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    path.write_text(path.read_text() + line + "\n")
    assert rch.main(["--project", "/opt/demo"]) == 0
    md = (box["out"] / "-opt-demo" / "aaaa1111.md").read_text()
    assert "second answer" in md
    assert "1757577600" not in md  # a non-string timestamp never becomes a span
    assert "not a block" not in md


def test_an_unparseable_record_is_counted_in_the_index(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    path = box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    path.write_bytes(path.read_bytes() + b'{"type":"user","message":{"content":"bad \xff byte"}}\n')
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert "unparseable record" in capsys.readouterr().err
    index = (box["out"] / "-opt-demo" / "INDEX.md").read_text()
    assert "| dropped |" in index.splitlines()[3] or "dropped" in index
    row = next(ln for ln in index.splitlines() if "`aaaa1111`" in ln)
    assert row.rstrip().endswith("| 1 |")


def test_a_lone_surrogate_in_a_message_renders_and_leaves_no_temp_file(
    box: dict[str, Path],
) -> None:
    path = box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl"
    path.write_text(
        path.read_text()
        + '{"type":"user","uuid":"s1","timestamp":"2026-09-02T08:02:00.000Z","message":{"content":"bad \\ud800 char"}}\n'
    )
    assert rch.main(["--project", "/opt/demo"]) == 0
    out = box["out"] / "-opt-demo"
    assert (out / "aaaa1111.md").exists() and not list(out.glob("*.tmp"))


@pytest.mark.parametrize("value", ['"x\\u0000y"', "7", '"' + "a" * 300 + '"', '"a b"', '"a|b"'])
def test_an_unusable_label_in_names_json_falls_back_to_the_id(
    box: dict[str, Path], value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "names.json").write_text('{"aaaa1111": ' + value + "}")
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert (out / "aaaa1111.md").exists()
    assert "WARN" in capsys.readouterr().err


def test_a_names_file_with_invalid_utf8_is_moved_aside(box: dict[str, Path]) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "names.json").write_bytes(b'{"aaaa1111": "ag\xffent"}')
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert list(out.glob("names.json.bad*"))


@pytest.mark.parametrize(
    "row", ['{"file": "aaaa1111.md"}', '{"file": null, "last": ""}', '{"file": 5}']
)
def test_a_state_row_missing_its_shape_reads_as_never_rendered_twice_in_a_row(
    box: dict[str, Path], row: str
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    st = (box["projects"] / "aaaa1111-0000-0000-0000-000000000000.jsonl").stat()
    sig = f"{st.st_size}:{st.st_mtime_ns}:aaaa1111"  # a MATCHING signature: only _is_entry decides
    (out / "aaaa1111.md").write_text(
        "# aaaa1111 — aaaa1111\n\nstale\n"
    )  # this session's own render
    (out / ".render-state.json").write_text(
        json.dumps({"aaaa1111-0000-0000-0000-000000000000": {"sig": sig, "row": json.loads(row)}})
    )
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert rch.main(["--project", "/opt/demo"]) == 0  # never sticky
    assert "second answer" in (out / "aaaa1111.md").read_text()  # re-rendered, not trusted


def test_a_suffixed_label_is_itself_checked_against_orphans_and_live_sessions(
    box: dict[str, Path],
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "foo-bbbb2222.md").write_text("# ORPHAN — the last copy\n")
    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    _write_session(box["projects"], "0000cccc-0000-0000-0000-000000000000", _demo_records())
    (out / "names.json").write_text(
        json.dumps({"aaaa1111": "foo", "bbbb2222": "foo", "0000cccc": "foo-bbbb2222"})
    )
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert (out / "foo-bbbb2222.md").read_text().startswith("# ORPHAN")
    files = {p.name for p in out.glob("*.md")} - {"INDEX.md"}
    assert len(files) == 4, files  # orphan + three live sessions, no shared file
    index = (out / "INDEX.md").read_text()
    for name in files - {"foo-bbbb2222.md"}:
        assert f"({name})" in index


def test_all_survives_one_broken_project_and_scopes_names_to_matching_projects(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    other = box["projects"].parent / "-opt-other"
    _write_session(other, "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    (box["out"] / "-opt-demo").parent.mkdir(parents=True, exist_ok=True)
    (box["out"] / "-opt-demo").write_text("a file where the project folder should be")
    assert rch.main(["--all", "--name", "bbbb2222=agent-9"]) == 1
    assert (box["out"] / "-opt-other" / "agent-9.md").exists()
    assert "WARN" in capsys.readouterr().err
    # the mapping is persisted only where its session lives
    other_names = json.loads((box["out"] / "-opt-other" / "names.json").read_text())
    assert other_names == {"bbbb2222": "agent-9"}


def test_a_second_concurrent_render_of_the_same_project_backs_off(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    import fcntl

    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    with (out / ".render.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert rch.main(["--project", "/opt/demo"]) == 1
    assert "another render" in capsys.readouterr().err
    assert not (out / "aaaa1111.md").exists()


@pytest.mark.parametrize("key", ["../evil", "", "a/b", "."])
def test_a_project_argument_can_never_write_outside_the_history_root(
    box: dict[str, Path], key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # every case names a directory that EXISTS relative to the projects dir and holds a transcript,
    # so only the key guard — not the "no transcripts" fallback — can refuse it
    projects = box["projects"].parent
    _write_session(
        projects.parent / "evil", "eeee1111-0000-0000-0000-000000000000", _demo_records()
    )
    _write_session(projects / "a" / "b", "eeee2222-0000-0000-0000-000000000000", _demo_records())
    _write_session(projects, "eeee3333-0000-0000-0000-000000000000", _demo_records())
    assert rch.main(["--project", key]) == 2
    assert "is not a project path or key" in capsys.readouterr().err
    assert not (box["out"].parent / "evil").exists()
    assert not (box["out"] / "INDEX.md").exists()  # never the history root itself
    assert not (box["out"] / "a").exists()


def test_a_render_with_no_state_entry_is_recognised_as_its_own_by_its_header(
    box: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    rch.main(["--project", "/opt/demo"])
    out = box["out"] / "-opt-demo"
    (out / ".render-state.json").unlink()  # a schema change or a lost sidecar
    assert rch.main(["--project", "/opt/demo"]) == 0
    files = sorted(p.name for p in out.glob("*.md") if p.name != "INDEX.md")
    assert files == ["aaaa1111.md"], files  # never suffixed, never duplicated
    assert "already used" not in capsys.readouterr().err


def test_under_all_a_name_is_persisted_only_where_its_session_lives(box: dict[str, Path]) -> None:
    other = box["projects"].parent / "-opt-other"
    _write_session(other, "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    assert rch.main(["--all", "--name", "bbbb2222=agent-9"]) == 0
    assert json.loads((box["out"] / "-opt-other" / "names.json").read_text()) == {
        "bbbb2222": "agent-9"
    }
    assert not (box["out"] / "-opt-demo" / "names.json").exists()


def test_a_state_row_whose_file_name_is_unusable_reads_as_never_rendered(
    box: dict[str, Path],
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    row = {
        "label": "x",
        "id": "aaaa1111-0000-0000-0000-000000000000",
        "file": "x\u0000y.md",
        "first": "",
        "last": "",
        "compactions": 0,
        "user": 0,
        "assistant": 0,
        "dropped": 0,
    }
    (out / ".render-state.json").write_text(
        json.dumps({"aaaa1111-0000-0000-0000-000000000000": {"sig": "x", "row": row}})
    )
    assert rch.main(["--project", "/opt/demo"]) == 0
    assert (out / "aaaa1111.md").exists()


def test_an_existing_render_with_a_corrupt_header_never_crashes_the_owner_check(
    box: dict[str, Path],
) -> None:
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "aaaa1111.md").write_bytes(b"# \xff\xfe broken header\n")
    assert rch.main(["--project", "/opt/demo"]) == 0
    rendered = [
        p for p in out.glob("aaaa1111*.md") if "second answer" in p.read_text(errors="replace")
    ]
    assert rendered


def test_the_suffix_search_is_bounded_when_the_filesystem_rejects_every_name(
    box: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import signal

    _write_session(box["projects"], "bbbb2222-0000-0000-0000-000000000000", _demo_records())
    out = box["out"] / "-opt-demo"
    out.mkdir(parents=True)
    (out / "names.json").write_text(json.dumps({"aaaa1111": "samelabel", "bbbb2222": "samelabel"}))
    real = Path.exists

    def name_too_long(self: Path) -> bool:
        if len(self.name) > 20:
            raise OSError(36, "File name too long")
        return real(self)

    monkeypatch.setattr(Path, "exists", name_too_long)

    class SpunError(
        Exception
    ):  # not an OSError: the guard under test must not be able to swallow it
        pass

    def spun(*_: object) -> None:
        raise SpunError("suffix search spun")

    signal.signal(signal.SIGALRM, spun)
    signal.alarm(10)
    try:
        rc = rch.main(["--project", "/opt/demo"])
    finally:
        signal.alarm(0)
    assert rc == 1
    err = capsys.readouterr().err
    assert "SpunError" not in err  # the search must END, not be rescued by the per-project guard
    assert "no free file name" in err
