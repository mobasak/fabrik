"""Behavior Contract — Phase A of the session-history retention plan, revision 2026-10-05
(`docs/development/plans/2026-09-06-plan-1-session-history-retention.md`, D-565).

Every test guards a way the off-site archive could silently fail to be what a restore needs.
rclone never runs for real here: `_rclone` hands its argv and env to `_run_rclone`, which the
`rec` fixture replaces with a recorder. zstd runs for real, so `.zst` files exist and decompress.
"""

from __future__ import annotations

import ast
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "archive_transcripts.py"
UNITS = REPO / "scripts" / "sysadmin" / "systemd"

spec = importlib.util.spec_from_file_location("archive_transcripts", SCRIPT)
at = importlib.util.module_from_spec(spec)
spec.loader.exec_module(at)

pytestmark = pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    (projects / "-opt-alpha").mkdir(parents=True)
    (projects / "-opt-beta").mkdir(parents=True)
    # SAME session id under TWO project slugs — the collision a 2-part key could not see
    (projects / "-opt-alpha" / "shared-id.jsonl").write_bytes(b'{"a":1}\n' * 100)
    (projects / "-opt-beta" / "shared-id.jsonl").write_bytes(b'{"b":2}\n' * 200)
    subs = projects / "-opt-alpha" / "shared-id" / "subagents"
    subs.mkdir(parents=True)
    (subs / "agent-x.jsonl").write_bytes(b"S" * 50_000)
    archive = tmp_path / "archive"
    for k in [k for k in os.environ if k.startswith(("RCLONE_", "SESSION_ARCHIVE_"))]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(projects))
    monkeypatch.setenv("ARCHIVE_ROOT", str(archive))
    # pinned to 0 (also the default since 2026-10-08) so a test never depends on the default
    monkeypatch.setenv("ARCHIVE_AFTER_DAYS", "0")
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp_path / "no-such.env"))
    monkeypatch.setenv("SESSION_ARCHIVE_B2_KEY_ID", "kid-test")
    monkeypatch.setenv("SESSION_ARCHIVE_B2_APPLICATION_KEY", "SECRET-test-value")
    monkeypatch.delenv("ARCHIVE_MAX_FILE_MB", raising=False)
    return projects, archive


@pytest.fixture
def rec(monkeypatch):
    """Replace the one rclone seam; `rec.results[verb]` sets the return code per verb."""

    class Recorder:
        def __init__(self):
            self.calls: list[tuple[list[str], dict[str, str], int]] = []
            self.results: dict[str, int] = {}

        def __call__(self, argv, env):
            rows = 0
            local = [a for a in argv[2:] if a.endswith(at.MANIFEST_NAME) and ":" not in a]
            if argv[1] == "copyto" and local:
                p = Path(local[0])
                rows = len(p.read_text().splitlines()) if p.exists() else 0
            self.calls.append((list(argv), dict(env), rows))
            return subprocess.CompletedProcess(argv, self.results.get(argv[1], 0), "", "boom")

        def verbs(self):
            return [c[0][1] for c in self.calls]

    r = Recorder()
    monkeypatch.setattr(at, "_run_rclone", r)
    return r


def _rows(archive: Path, name: str | None = None) -> list[dict]:
    m = archive / (name or at.MANIFEST_NAME)
    return [json.loads(x) for x in m.read_text().splitlines()] if m.exists() else []


def _sub_rows(archive: Path) -> list[dict]:
    return _rows(archive, at.SUBAGENT_MANIFEST_NAME)


# ── revision-1 behaviours, kept ─────────────────────────────────────────────────────────────


def test_manifest_sha_matches_the_source_bytes(tree, rec):
    projects, archive = tree
    assert at.run([]) == 0
    rows = _rows(archive)
    assert rows, "no manifest rows written"
    for r in rows:
        src = projects / r["project_slug"] / f"{r['session_id']}.jsonl"
        assert r["sha256"] == at._sha256(src), "manifest vouches for bytes it did not hash"
        assert r["bytes"] == src.stat().st_size


def test_manifest_key_disambiguates_the_same_session_id_across_projects(tree, rec):
    _projects, archive = tree
    at.run([])
    rows = [r for r in _rows(archive) if r["session_id"] == "shared-id"]
    assert len(rows) == 2, "both projects' same-named sessions must be archived"
    assert {r["project_slug"] for r in rows} == {"-opt-alpha", "-opt-beta"}
    assert rows[0]["sha256"] != rows[1]["sha256"]
    for r in rows:
        assert (archive / r["project_slug"] / f"{r['session_id']}.jsonl.zst").is_file()


def test_subagent_transcripts_are_archived_under_their_path(tree, rec):
    """D-1182: the */subagents/** tier is archived like MAIN — object at <slug>/<rel>.zst, row in its OWN
    manifest (manifest.jsonl stays MAIN-only, so no MAIN reader can mis-key a sidechain row)."""
    projects, archive = tree
    subs = projects / "-opt-alpha" / "shared-id" / "subagents"
    wf = subs / "workflows" / "wf_1"
    wf.mkdir(parents=True)
    (wf / "agent-y.jsonl").write_bytes(b"W" * 3000)
    (wf / "journal.jsonl").write_bytes(b'{"j":1}\n' * 10)
    (subs / "agent-x.meta.json").write_text("{}")
    sup = projects / "-opt-beta" / "old-id.superseded-17" / "subagents"
    sup.mkdir(parents=True)
    (sup / "agent-z.jsonl").write_bytes(b"Z" * 700)
    assert at.run([]) == 0
    sub = {(r["project_slug"], r["rel"]): r for r in _sub_rows(archive)}
    assert set(sub) == {
        ("-opt-alpha", "shared-id/subagents/agent-x.jsonl"),
        ("-opt-alpha", "shared-id/subagents/workflows/wf_1/agent-y.jsonl"),
        ("-opt-alpha", "shared-id/subagents/workflows/wf_1/journal.jsonl"),
        ("-opt-beta", "old-id.superseded-17/subagents/agent-z.jsonl"),
    }
    for (slug, rel), r in sub.items():
        assert r["session_id"] == rel.split("/", 1)[0], "the session dir, never the leaf's parent"
        src = projects / slug / rel
        assert r["sha256"] == at._sha256(src) and r["bytes"] == src.stat().st_size
        zst = archive / slug / f"{rel}.zst"
        plain = subprocess.run(["zstd", "-dc", "-q", str(zst)], check=True, capture_output=True)
        assert hashlib.sha256(plain.stdout).hexdigest() == r["sha256"], "the object holds the bytes"
    assert not list(archive.rglob("*.meta.json*")), "a sidecar is not a transcript"
    assert {(r["project_slug"], r["session_id"]) for r in _rows(archive)} == {
        ("-opt-alpha", "shared-id"),
        ("-opt-beta", "shared-id"),
    }, "manifest.jsonl carries MAIN rows only"


def test_an_unchanged_subagent_transcript_is_skipped_and_a_grown_one_rearchived(tree, rec):
    projects, archive = tree
    assert at.run([]) == 0
    zst = archive / "-opt-alpha" / "shared-id" / "subagents" / "agent-x.jsonl.zst"
    before, n = zst.stat().st_mtime_ns, len(_sub_rows(archive))
    assert n == 1
    assert at.run([]) == 0
    assert zst.stat().st_mtime_ns == before, "an unchanged sidechain was re-compressed"
    assert len(_sub_rows(archive)) == n, "an unchanged sidechain was re-rowed"
    src = projects / "-opt-alpha" / "shared-id" / "subagents" / "agent-x.jsonl"
    with src.open("ab") as fh:
        fh.write(b"more")
    assert at.run([]) == 0
    rows = _sub_rows(archive)
    assert len(rows) == n + 1 and rows[-1]["sha256"] == at._sha256(src)


def test_a_failing_subagent_transcript_does_not_stop_the_night(tree, rec, monkeypatch, capsys):
    """A sidechain that cannot be archived is reported and kept (the pruner refuses it as not-archived);
    the MAIN rows and the transport still happen."""
    _projects, archive = tree
    real = shutil.copyfile

    def denied_for_sidechains(src, dst):
        if "/subagents/" in str(src):
            raise PermissionError(13, "Permission denied")
        return real(src, dst)

    monkeypatch.setattr(at.shutil, "copyfile", denied_for_sidechains)
    assert at.run([]) == 0
    out = capsys.readouterr().out
    assert "FAILED" in out and "agent-x.jsonl" in out and "the pruner keeps it" in out
    assert "1 subagent failure(s)" in out
    assert _sub_rows(archive) == [] and len(_rows(archive)) == 2
    assert rec.verbs()[0] == "copy"


def test_a_failed_test_of_a_new_object_keeps_the_last_good_object(tree, rec, monkeypatch, capsys):
    """A compress or `zstd -t` that fails never leaves bytes at the object path for `ship()` to upload
    over the key's last good version: the new object is built beside the snapshot and renamed in only
    once tested (review W-62d2ce7d pass 1, A-haiku-1)."""
    projects, archive = tree
    assert at.run([]) == 0
    zst = archive / "-opt-alpha" / "shared-id" / "subagents" / "agent-x.jsonl.zst"
    good = zst.read_bytes()
    with (projects / "-opt-alpha" / "shared-id" / "subagents" / "agent-x.jsonl").open("ab") as fh:
        fh.write(b"grown")
    real = subprocess.run

    def verify_fails(argv, *a, **kw):
        if argv[:2] == ["zstd", "-t"]:
            raise subprocess.CalledProcessError(1, argv)
        return real(argv, *a, **kw)

    monkeypatch.setattr(at.subprocess, "run", verify_fails)
    assert at.run([]) == 0
    assert "FAILED" in capsys.readouterr().out
    assert zst.read_bytes() == good, "the last good object was replaced by an untested one"
    assert len(_sub_rows(archive)) == 1


def test_a_zstd_failure_on_a_subagent_transcript_does_not_stop_the_night(
    tree, rec, monkeypatch, capsys
):
    """The zstd branch of the same rule (review W-62d2ce7d pass 1, A-sonnet-2): a compressor that fails on
    a sidechain is a reported skip, while MAIN still archives and ships."""
    _projects, archive = tree
    real = subprocess.run

    def zstd_fails_for_sidechains(argv, *a, **kw):
        if argv and argv[0] == "zstd" and any("/subagents/" in str(x) or "agent-" in str(x) for x in argv):
            raise subprocess.CalledProcessError(1, argv)
        return real(argv, *a, **kw)

    monkeypatch.setattr(at.subprocess, "run", zstd_fails_for_sidechains)
    assert at.run([]) == 0
    out = capsys.readouterr().out
    assert "FAILED" in out and "1 subagent failure(s)" in out
    assert _sub_rows(archive) == [] and len(_rows(archive)) == 2


def test_file_over_the_ceiling_is_reported_not_archived(tree, rec, monkeypatch, capsys):
    _projects, archive = tree
    monkeypatch.setenv(
        "ARCHIVE_MAX_FILE_MB", "0.001"
    )  # 1048 bytes: between alpha (800) and beta (1600)
    assert at.run([]) == 0
    assert "OVER-CEILING" in capsys.readouterr().out
    assert {r["project_slug"] for r in _rows(archive)} == {"-opt-alpha"}
    assert not (archive / "-opt-beta" / "shared-id.jsonl.zst").exists()


# ── A-B1 … A-B13 ────────────────────────────────────────────────────────────────────────────


def test_ab1_unchanged_transcript_is_neither_hashed_nor_recompressed(tree, rec, monkeypatch):
    _projects, archive = tree
    assert at.run([]) == 0
    n_rows = len(_rows(archive))
    zstd_calls, hashes = [], []
    real_run, real_sha = subprocess.run, at._sha256
    monkeypatch.setattr(
        at.subprocess, "run", lambda a, *k, **kw: (zstd_calls.append(a), real_run(a, *k, **kw))[1]
    )
    monkeypatch.setattr(at, "_sha256", lambda p: (hashes.append(p), real_sha(p))[1])
    assert at.run([]) == 0
    assert [c for c in zstd_calls if c and c[0] == "zstd"] == [], (
        "an unchanged file was recompressed"
    )
    assert hashes == [], "an unchanged file was re-hashed"
    assert len(_rows(archive)) == n_rows


def test_ab2_changed_transcript_gets_a_new_row_and_new_bytes(tree, rec, tmp_path):
    projects, archive = tree
    assert at.run([]) == 0
    src = projects / "-opt-alpha" / "shared-id.jsonl"
    with src.open("ab") as fh:
        fh.write(b'{"later":1}\n')
    assert at.run([]) == 0
    alpha = [r for r in _rows(archive) if r["project_slug"] == "-opt-alpha"]
    assert len(alpha) == 2 and alpha[-1]["sha256"] == at._sha256(src)
    out = tmp_path / "back.jsonl"
    subprocess.run(
        [
            "zstd",
            "-d",
            "-q",
            "-f",
            str(archive / "-opt-alpha" / "shared-id.jsonl.zst"),
            "-o",
            str(out),
        ],
        check=True,
    )
    assert out.read_bytes() == src.read_bytes()


def test_ab3_hard_linked_twins_are_archived_once(tree, rec):
    projects, archive = tree
    (projects / "-opt-alpha--wt").mkdir()
    os.link(
        projects / "-opt-alpha" / "shared-id.jsonl", projects / "-opt-alpha--wt" / "shared-id.jsonl"
    )
    assert at.run([]) == 0
    alpha_like = [r for r in _rows(archive) if r["project_slug"].startswith("-opt-alpha")]
    assert len(alpha_like) == 1, alpha_like
    assert alpha_like[0]["project_slug"] == "-opt-alpha"
    assert alpha_like[0]["also_slugs"] == ["-opt-alpha--wt"]
    assert not (archive / "-opt-alpha--wt").exists()


def test_ab3_three_links_list_every_other_slug_sorted(tree, rec):
    projects, archive = tree
    for extra in ("-opt-alpha--zz", "-opt-alpha--bb"):
        (projects / extra).mkdir()
        os.link(projects / "-opt-alpha" / "shared-id.jsonl", projects / extra / "shared-id.jsonl")
    assert at.run([]) == 0
    row = next(r for r in _rows(archive) if r["project_slug"] == "-opt-alpha")
    assert row["also_slugs"] == ["-opt-alpha--bb", "-opt-alpha--zz"]


def test_ab3_surviving_link_is_not_archived_again_when_its_primary_vanishes(tree, rec):
    projects, archive = tree
    (projects / "-opt-alpha--wt").mkdir()
    os.link(
        projects / "-opt-alpha" / "shared-id.jsonl", projects / "-opt-alpha--wt" / "shared-id.jsonl"
    )
    assert at.run([]) == 0
    n_rows = len(_rows(archive))
    shutil.rmtree(projects / "-opt-alpha")
    assert at.run([]) == 0
    assert len(_rows(archive)) == n_rows, "the surviving hard link was archived a second time"
    assert not (archive / "-opt-alpha--wt").exists()


def test_ab1_a_missing_zst_is_archived_again(tree, rec):
    _projects, archive = tree
    assert at.run([]) == 0
    zst = archive / "-opt-alpha" / "shared-id.jsonl.zst"
    zst.unlink()
    assert at.run([]) == 0
    assert zst.is_file(), "a manifest row without its .zst must not count as archived"


def test_ab4_ship_order_copy_then_rows_then_manifest(tree, rec):
    _projects, archive = tree
    assert at.run([]) == 0
    assert rec.verbs() == ["copy", "copyto", "copyto"]
    copy_argv = rec.calls[0][0]
    assert f"/{at.MANIFEST_NAME}" in copy_argv[copy_argv.index("--exclude") + 1 :]
    assert f"/{at.SUBAGENT_MANIFEST_NAME}" in copy_argv[copy_argv.index("--exclude") + 1 :]
    assert rec.calls[1][2] == len(_rows(archive)) > 0, (
        "the manifest shipped before its rows existed"
    )
    assert rec.calls[2][0][-1].endswith(f"/{at.SUBAGENT_MANIFEST_NAME}"), "the tier's manifest ships too"
    assert (tree[0] / "README").is_file(), "A.6: the data-not-cache marker"


@pytest.mark.parametrize("how", ["absent", "missing-file", "unreadable-file"])
def test_ab5_missing_key_exits_before_any_rclone_call(
    tree, rec, monkeypatch, tmp_path, capsys, how
):
    _projects, archive = tree
    monkeypatch.delenv("SESSION_ARCHIVE_B2_KEY_ID")
    monkeypatch.delenv("SESSION_ARCHIVE_B2_APPLICATION_KEY")
    env_file = tmp_path / "keys.env"
    if how == "unreadable-file":
        env_file.mkdir()  # read_text raises IsADirectoryError for every user, root included
    elif how == "absent":
        env_file.write_text("OTHER=1\n")
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env_file))
    assert at.run([]) == 1
    err = capsys.readouterr().err
    assert "SESSION_ARCHIVE_B2_KEY_ID" in err and "SESSION_ARCHIVE_B2_APPLICATION_KEY" in err
    assert str(env_file) in err and "sek" not in err
    assert rec.calls == [] and _rows(archive) == []


def test_ab6_key_travels_only_in_the_child_env(tree, rec, monkeypatch, tmp_path):
    monkeypatch.delenv("SESSION_ARCHIVE_B2_KEY_ID")
    monkeypatch.delenv("SESSION_ARCHIVE_B2_APPLICATION_KEY")
    env_file = tmp_path / "keys.env"
    env_file.write_bytes(
        b'export SESSION_ARCHIVE_B2_KEY_ID="kid-from-file"\r\n'
        b"SESSION_ARCHIVE_B2_APPLICATION_KEY='sek-from-file'\r\n"
        b"OTHER_SECRET=do-not-load\n"
    )
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env_file))
    monkeypatch.setenv("RCLONE_B2_HARD_DELETE", "true")
    assert at._read_env_file(env_file) == {
        "SESSION_ARCHIVE_B2_KEY_ID": "kid-from-file",
        "SESSION_ARCHIVE_B2_APPLICATION_KEY": "sek-from-file",
    }, "the env file must contribute only SESSION_ARCHIVE_* lines"
    assert at.run([]) == 0
    for argv, env, _ in rec.calls:
        assert not any("sek-from-file" in a or "kid-from-file" in a for a in argv)
        assert env["RCLONE_CONFIG_SESSIONB2_KEY"] == "sek-from-file"
        assert env["RCLONE_CONFIG_SESSIONB2_ACCOUNT"] == "kid-from-file"
        assert env["RCLONE_CONFIG_SESSIONB2_TYPE"] == "b2"
        assert "OTHER_SECRET" not in env and "RCLONE_B2_HARD_DELETE" not in env


def test_bucket_and_prefix_are_read_from_the_env_file(tree, rec, monkeypatch, tmp_path):
    env_file = tmp_path / "s.env"
    env_file.write_text(
        "SESSION_ARCHIVE_B2_BUCKET=bkt-from-file  # the bucket\n"
        'SESSION_ARCHIVE_B2_PREFIX="pfx" # where under it\n'
    )
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env_file))
    assert at.run([]) == 0
    assert rec.calls[0][0][3] == "sessionb2:bkt-from-file/pfx/", rec.calls[0][0]


@pytest.mark.parametrize(
    ("line", "value"),
    [
        ("SESSION_ARCHIVE_B2_KEY_ID=abc123  # the key id", "abc123"),
        ('SESSION_ARCHIVE_B2_KEY_ID="abc#123" # quoted, hash kept', "abc#123"),
        ("SESSION_ARCHIVE_B2_KEY_ID='abc' # single-quoted", "abc"),
        ("export SESSION_ARCHIVE_B2_KEY_ID=abc", "abc"),
        ("SESSION_ARCHIVE_B2_KEY_ID=ab#c", "ab#c"),
        ("SESSION_ARCHIVE_B2_KEY_ID= # nothing but a note", ""),
    ],
)
def test_env_values_drop_inline_comments_and_quotes(tmp_path, line, value):
    f = tmp_path / "e.env"
    f.write_text(line + "\n")
    assert at._read_env_file(f) == {"SESSION_ARCHIVE_B2_KEY_ID": value}


def test_rclone_failure_text_never_carries_the_key(monkeypatch):
    env = at._child_env("KID-VALUE", "SECRET-VALUE")
    monkeypatch.setattr(
        at,
        "_run_rclone",
        lambda argv, env_: subprocess.CompletedProcess(
            argv, 1, "", "auth failed for KID-VALUE with SECRET-VALUE"
        ),
    )
    with pytest.raises(at.ArchiveError) as exc:
        at._rclone("lsf", "sessionb2:x/", env=env)
    assert "KID-VALUE" not in str(exc.value) and "SECRET-VALUE" not in str(exc.value)
    assert "<redacted>" in str(exc.value)


def test_a_zstd_timeout_is_a_clean_exit_1(tree, rec, monkeypatch, capsys):
    real = subprocess.run

    def slow(argv, *a, **kw):
        if argv and argv[0] == "zstd":
            raise subprocess.TimeoutExpired(argv, 1)
        return real(argv, *a, **kw)

    monkeypatch.setattr(at.subprocess, "run", slow)
    assert at.run([]) == 1
    assert "zstd failed" in capsys.readouterr().err


def test_a_non_numeric_ceiling_is_a_clean_exit_1(tree, rec, monkeypatch, capsys):
    monkeypatch.setenv("ARCHIVE_MAX_FILE_MB", "lots")
    assert at.run([]) == 1
    assert "must be numbers" in capsys.readouterr().err


@pytest.mark.parametrize(
    "verb",
    [
        "sync",
        "move",
        "moveto",
        "delete",
        "deletefile",
        "purge",
        "cleanup",
        "rmdir",
        "rmdirs",
        "backend",
    ],
)
def test_ab7_rclone_refuses_every_verb_off_the_allow_list(verb, rec):
    with pytest.raises(ValueError):
        at._rclone(verb, "sessionb2:x/", env={})
    assert rec.calls == []


@pytest.mark.parametrize("flag", ["--delete-after", "--b2-hard-delete", "--b2-hard-delete=true"])
def test_ab7_rclone_refuses_deleting_options(flag, rec):
    with pytest.raises(ValueError):
        at._rclone("copy", "a/", "sessionb2:x/", flag, env={})
    assert rec.calls == []


def test_ab7_only_the_door_names_rclone():
    """`"rclone"` heads an argv list ONLY inside `_rclone` — no second door around the allow-list."""
    tree_ = ast.parse(SCRIPT.read_text())
    owners = []
    for fn in ast.walk(tree_):
        if isinstance(fn, ast.FunctionDef):
            for node in ast.walk(fn):
                if isinstance(node, ast.List) and node.elts:
                    head = node.elts[0]
                    if isinstance(head, ast.Constant) and head.value == "rclone":
                        owners.append(fn.name)
    assert owners == ["_rclone"], owners


def test_ab8_failed_copy_writes_no_rows(tree, rec, capsys):
    _projects, archive = tree
    rec.results["copy"] = 1
    assert at.run([]) == 1
    assert rec.verbs() == ["copy"], "the transport must actually have been attempted"
    assert _rows(archive) == []
    assert "TRANSPORT FAILED" in capsys.readouterr().err


def test_ab9_failed_manifest_upload_keeps_rows_and_reships(tree, rec, capsys):
    projects, archive = tree
    rec.results["copyto"] = 1
    assert at.run([]) == 1
    assert _rows(archive), "the bytes landed, so the rows must be kept"
    assert "manifest upload failed" in capsys.readouterr().err
    rec.results["copyto"] = 0
    rec.calls.clear()
    assert at.run([]) == 0
    assert "copyto" in rec.verbs(), "the next run must re-ship the manifest"


def test_ab10_held_lock_makes_a_second_run_a_no_op(tree, rec, capsys):
    _projects, archive = tree
    archive.mkdir(parents=True)
    with (archive / at.LOCK_NAME).open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert at.run([]) == 0
    assert "holds the archive lock" in capsys.readouterr().out
    assert rec.calls == [] and _rows(archive) == []


def test_ab11_window_defaults_to_zero_days(tree, rec, monkeypatch, capsys):
    """Default 0 (D-row of 2026-10-08): every MAIN transcript, idle or still open, is eligible."""
    projects, _archive = tree
    monkeypatch.delenv("ARCHIVE_AFTER_DAYS")
    old = projects / "-opt-beta" / "shared-id.jsonl"
    two_days = time.time() - 2 * 86400
    os.utime(old, (two_days, two_days))
    assert at.run(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "2 MAIN transcript(s) eligible (idle > 0.0d)" in out, out
    assert f"would archive {old}" in out


@pytest.mark.parametrize("missing", ["zstd", "rclone"])
def test_ab12_missing_binary_exits_naming_it(tree, rec, monkeypatch, capsys, missing):
    real = shutil.which
    monkeypatch.setattr(
        at.shutil, "which", lambda n: None if n == missing else real(n) or f"/x/{n}"
    )
    assert at.run([]) == 1
    assert missing in capsys.readouterr().err
    assert rec.calls == []


def test_ab13_units_load_no_env_file_run_main_checkout_and_catch_up():
    def directives(name):
        lines = (UNITS / name).read_text().splitlines()
        return "\n".join(
            ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith(("#", ";"))
        )

    service, timer = directives("session-archive.service"), directives("session-archive.timer")
    assert not any(ln.startswith("EnvironmentFile") for ln in service.splitlines())
    assert (
        "ExecStart=/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/archive_transcripts.py"
        in service
    )
    assert "ExecStartPre=-/opt/fabrik/scripts/sysadmin/sample_transcript_growth.sh" in service
    assert "Persistent=true" in timer and "Unit=session-archive.service" in timer
    assert "Restart=on-failure" in service, "a boot-time run without network must be retried"
    # C.2 unit ordering: Type=oneshot, the archiver's ExecStart first, the pruner's `ExecStart=-` second,
    # the rotation mail's `ExecStart=-` third (W-f975fee0 slice 3, D-1119)
    assert "Type=oneshot" in service.splitlines()
    starts = [ln for ln in service.splitlines() if ln.startswith("ExecStart=")]
    assert len(starts) == 3 and "archive_transcripts.py" in starts[0]
    assert starts[1].startswith("ExecStart=-") and "prune_transcripts.py" in starts[1]
    assert starts[2].startswith("ExecStart=-") and "rotate_session.py due" in starts[2]


def test_a_path_that_vanishes_between_the_scan_and_group_by_inode_is_skipped(
    tree, rec, monkeypatch, capsys
):
    """C.2: `_group_by_inode` stats each scanned path; one removed in between is skipped, not a crash,
    and the skip is SAID like the other vanished site's (review 2026-10-11, wiring-S3)."""
    projects, archive = tree
    real_group = at._group_by_inode

    def gone_before_grouping(paths):
        (
            projects / "-opt-beta" / "shared-id.jsonl"
        ).unlink()  # removed after main_transcripts() saw it
        return real_group(paths)

    monkeypatch.setattr(at, "_group_by_inode", gone_before_grouping)
    assert at.run([]) == 0
    assert {r["project_slug"] for r in _rows(archive)} == {"-opt-alpha"}
    assert "vanished" in capsys.readouterr().out


def test_a_stale_marker_readme_is_rewritten_and_names_the_pruner(tree, rec):
    """The README that stops a human freeing disk must not say 'nothing prunes' once the pruner
    exists: an older text is refreshed on the next run (review 2026-10-11, wiring-S2)."""
    projects, _archive = tree
    readme = projects / "README"
    readme.write_text(
        "THIS DIRECTORY IS DATA, NOT CACHE.\n\nNothing on this box prunes these files.\n"
    )
    assert at.run([]) == 0
    text = readme.read_text()
    assert "Nothing on this box prunes" not in text
    assert "prune_transcripts.py" in text and "--restore" in text
    assert "subagents/ transcripts" in text and "--restore agent-<id>" in text, "D-1182: the tier is archived"
    assert text == at.MARKER


def test_group_by_inode_skips_a_vanished_path_directly(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "gone.jsonl"
    a.write_text("x")
    assert at._group_by_inode([a, b]) == [(a, [])]


# ── rclone copyto exits 0 when the SOURCE object is absent and writes nothing ───────────────
# (measured live 2026-10-08: `--remote-count` against the empty `wsl-ozgur` bucket passed the rc
# check, then crashed opening a manifest that never arrived). The recorder models that: rc 0, no file.


def test_remote_count_on_an_empty_bucket_reports_the_manifest_absent(tree, rec, capsys):
    """`--remote-count` before the first upload answers `absent`, never a traceback."""
    assert at.run(["--remote-count"]) == 0
    out = capsys.readouterr().out
    assert "remote_objects 0" in out
    assert "remote_manifest_sha256 absent" in out


def test_fetch_of_an_object_the_bucket_does_not_hold_fails_loudly(tree, rec, tmp_path, capsys):
    """A restore must never print `fetched` for bytes that never arrived (Phase B relies on it)."""
    dest = tmp_path / "out.zst"
    assert at.run(["--fetch", "/-opt-alpha/missing.jsonl.zst", str(dest)]) == 1
    assert "was not downloaded" in capsys.readouterr().err
    assert not dest.exists()


# ── the named windows: a session open for days is still backed up, as a daily snapshot ──────
# (operator 2026-10-08: "will we keep all chat histories of all active windows … infra, kaizen,
# intel, fleet"; those windows never go idle for a day, so a 1-day idle window never took them)


def test_an_active_transcript_is_archived_by_default(tree, rec, monkeypatch, capsys):
    """A transcript written seconds ago is eligible with no ARCHIVE_AFTER_DAYS set."""
    projects, _archive = tree
    monkeypatch.delenv("ARCHIVE_AFTER_DAYS")
    live = projects / "-opt-alpha" / "shared-id.jsonl"  # mtime: now
    assert at.run(["--dry-run"]) == 0
    assert f"would archive {live}" in capsys.readouterr().out


def test_a_transcript_growing_during_the_archive_gets_a_row_matching_its_object(
    tree, rec, monkeypatch
):
    """The row's sha256 and bytes describe the uploaded object even while the session appends."""
    projects, archive = tree
    live = projects / "-opt-beta" / "shared-id.jsonl"
    real = at._sha256

    def hash_then_the_session_appends(path):
        digest = real(path)
        with live.open("ab") as fh:  # the open window writes its next turn mid-archive
            fh.write(b'{"turn":"next"}\n')
        return digest

    monkeypatch.setattr(at, "_sha256", hash_then_the_session_appends)
    assert at.run([]) == 0
    row = next(r for r in _rows(archive) if r["project_slug"] == "-opt-beta")
    got = subprocess.run(
        ["zstd", "-d", "-c", str(archive / "-opt-beta" / "shared-id.jsonl.zst")],
        capture_output=True,
        check=True,
    ).stdout
    assert row["sha256"] == hashlib.sha256(got).hexdigest(), "the row vouches for other bytes"
    assert row["bytes"] == len(got)


# ── review round 1 (fabrik-review-scoped of the 2026-10-08 change) ──────────────────────────


def test_an_orphaned_snapshot_from_a_killed_run_is_reaped(tree, rec):
    """A SIGKILL skips the with-block's cleanup; the next run, holding the lock, removes it."""
    _projects, archive = tree
    orphan = archive / f"{at.SNAPSHOT_PREFIX}killed" / "big.jsonl"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"x" * 1000)
    assert at.run([]) == 0
    assert not orphan.parent.exists()
    assert not list(archive.glob(f"{at.SNAPSHOT_PREFIX}*"))


def test_the_ship_copy_never_uploads_a_snapshot(tree, rec):
    assert at.run([]) == 0
    copy = next(c[0] for c in rec.calls if c[0][1] == "copy")
    assert ("--exclude", f"/{at.SNAPSHOT_PREFIX}*/**") in list(zip(copy, copy[1:], strict=False))


def test_the_manifest_upload_skips_the_destination_check(tree, rec):
    """B2's download host is the one copyto HEADs first; an upload must not depend on it
    (2026-10-08: the HEAD hung 42 min behind an SNI filter while every upload worked)."""
    assert at.run([]) == 0
    manifest_calls = [c[0] for c in rec.calls if c[0][1] == "copyto"]
    assert len(manifest_calls) == 2, "the MAIN manifest and the subagent tier's (D-1182)"
    assert all("--no-check-dest" in call for call in manifest_calls)


def test_fetch_refuses_a_local_path_that_already_exists(tree, rec, tmp_path, capsys):
    """An old file at the target would read as a successful restore of a missing object."""
    dest = tmp_path / "out.zst"
    dest.write_bytes(b"stale")
    assert at.run(["--fetch", "/-opt-alpha/missing.jsonl.zst", str(dest)]) == 1
    assert "already exists" in capsys.readouterr().err
    assert dest.read_bytes() == b"stale"
    assert rec.calls == []


def test_fetch_of_a_prefix_is_not_a_restore(tree, monkeypatch, tmp_path, capsys):
    """copyto copies a PREFIX as a directory tree; only a regular file is a restored object."""

    def copies_a_tree(argv, env):
        (Path(argv[-1]) / "sid.jsonl.zst").parent.mkdir(parents=True)
        (Path(argv[-1]) / "sid.jsonl.zst").write_bytes(b"z")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(at, "_run_rclone", copies_a_tree)
    assert at.run(["--fetch", "/-opt-alpha", str(tmp_path / "out")]) == 1
    assert "not a single object" in capsys.readouterr().err


def test_a_transcript_that_vanishes_mid_run_is_skipped(tree, rec, monkeypatch, capsys):
    _projects, archive = tree
    real = shutil.copyfile

    def gone_for_beta(src, dst):
        if "-opt-beta" in str(src):
            Path(src).unlink()  # the session's file really is gone by the time the copy opens it
        return real(src, dst)

    monkeypatch.setattr(at.shutil, "copyfile", gone_for_beta)
    assert at.run([]) == 0
    assert {r["project_slug"] for r in _rows(archive)} == {"-opt-alpha"}
    assert "vanished" in capsys.readouterr().out


def test_a_full_disk_is_a_clean_exit_1(tree, rec, monkeypatch, capsys):
    def no_space(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(at.shutil, "copyfile", no_space)
    assert at.run([]) == 1
    err = capsys.readouterr().err
    assert "No space left on device" in err
    assert "Traceback" not in err


def test_a_transcript_that_grew_during_the_copy_settles_on_the_next_run(tree, rec, monkeypatch):
    """The skip state must describe the snapshot's bytes, or a stable file re-hashes forever."""
    projects, _archive = tree
    live = projects / "-opt-beta" / "shared-id.jsonl"
    real = shutil.copyfile

    def window_writes_then_copy(src, dst):
        if Path(src) == live:
            with live.open("ab") as fh:  # the turn lands after the stat, before the copy reads
                fh.write(b'{"turn":"mid-copy"}\n')
        return real(src, dst)

    monkeypatch.setattr(at.shutil, "copyfile", window_writes_then_copy)
    assert at.run([]) == 0
    monkeypatch.setattr(at.shutil, "copyfile", real)
    assert at.run([]) == 0  # the file is now stable
    hashed = []
    real_sha = at._sha256
    monkeypatch.setattr(at, "_sha256", lambda p: (hashed.append(p), real_sha(p))[1])
    assert at.run([]) == 0
    assert hashed == [], "a stable, already-archived transcript was re-hashed"


# ── review round 2 ──────────────────────────────────────────────────────────────────────────


def test_a_missing_zstd_mid_run_is_loud_not_a_vanished_skip(tree, rec, monkeypatch, capsys):
    """FileNotFoundError from a removed zstd binary is NOT a vanished transcript."""
    real_run = subprocess.run

    def zstd_gone(argv, *a, **kw):
        if argv and argv[0] == "zstd":
            raise FileNotFoundError(2, "No such file or directory", "zstd")
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(at.subprocess, "run", zstd_gone)
    assert at.run([]) == 1
    captured = capsys.readouterr()
    assert "vanished" not in captured.out
    assert "zstd" in captured.err


def test_an_oserror_outside_the_archive_loop_is_a_clean_exit_1(tree, rec, monkeypatch, capsys):
    """A full disk on the marker or the manifest append exits 1 with a message, no traceback."""

    def no_space(_projects):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(at, "_ensure_marker", no_space)
    assert at.run([]) == 1
    err = capsys.readouterr().err
    assert "No space left on device" in err
    assert "Traceback" not in err


def test_a_snapshot_named_symlink_is_left_alone_and_does_not_crash(tree, rec, tmp_path):
    _projects, archive = tree
    archive.mkdir(parents=True)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "keep.txt").write_text("not ours")
    link = archive / f"{at.SNAPSHOT_PREFIX}link"
    link.symlink_to(target, target_is_directory=True)
    assert at.run([]) == 0
    assert link.is_symlink()
    assert (target / "keep.txt").exists()


# ── Phase C.1 (D-736 / D-737): the `agent` tag and the `--agent` verb ───────────────────────────


def _identity(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "state" / "agent-identity.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    d = tmp_path / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    for e in entries:
        (d / f"{e['pid']}.json").write_text(json.dumps(e))
    return d


def test_c11_a_bound_session_row_carries_agent_and_an_unbound_one_carries_no_key(
    tree, rec, tmp_path, monkeypatch
):
    projects, archive = tree
    (projects / "-opt-alpha" / "bound.jsonl").write_bytes(b'{"x":1}\n' * 10)
    identity = _identity(
        tmp_path, [{"session_id": "bound", "name": "fleet", "pid": 1, "pid_start": 2, "at": 10}]
    )
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(tmp_path / "no-sessions"))
    assert at.run(["--no-ship"]) == 0
    rows = [json.loads(line) for line in (archive / "manifest.jsonl").read_text().splitlines()]
    by_sid = {r["session_id"]: r for r in rows}
    assert by_sid["bound"]["agent"] == "fleet"
    assert "agent" not in by_sid["shared-id"]


def test_c11_the_latest_binding_by_at_wins(tree, rec, tmp_path, monkeypatch):
    projects, archive = tree
    (projects / "-opt-alpha" / "rebound.jsonl").write_bytes(b'{"x":1}\n' * 10)
    identity = _identity(
        tmp_path,
        [
            {"session_id": "rebound", "name": "intel", "pid": 1, "pid_start": 2, "at": 50},
            {"session_id": "rebound", "name": "fleet", "pid": 1, "pid_start": 2, "at": 20},
        ],
    )
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(tmp_path / "no-sessions"))
    assert at.run(["--no-ship"]) == 0
    rows = [json.loads(line) for line in (archive / "manifest.jsonl").read_text().splitlines()]
    assert {r["session_id"]: r.get("agent") for r in rows}["rebound"] == "intel"


def test_c11_registry_join_tags_a_cleared_window_by_pid_and_procstart_as_integers(
    tree, rec, tmp_path, monkeypatch
):
    """After /clear the new session id has no identity row; the registry entry for the SAME
    claude pid carries the new id, and its procStart (a JSON string) equals the identity row's
    pid_start (an int)."""
    projects, archive = tree
    (projects / "-opt-alpha" / "new-sid.jsonl").write_bytes(b'{"x":1}\n' * 10)
    (projects / "-opt-alpha" / "other-sid.jsonl").write_bytes(b'{"x":1}\n' * 10)
    identity = _identity(
        tmp_path,
        [{"session_id": "old-sid", "name": "kaizen", "pid": 777, "pid_start": 123456, "at": 5}],
    )
    sessions = _registry(
        tmp_path,
        [
            {"pid": 777, "sessionId": "new-sid", "procStart": "123456"},
            {"pid": 778, "sessionId": "other-sid", "procStart": "123456"},  # another pid: no join
        ],
    )
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(sessions))
    assert at.run(["--no-ship"]) == 0
    rows = {
        r["session_id"]: r
        for r in (json.loads(x) for x in (archive / "manifest.jsonl").read_text().splitlines())
    }
    assert rows["new-sid"]["agent"] == "kaizen"
    assert "agent" not in rows["other-sid"]


def test_c12_agent_verb_lists_that_agents_rows_newest_first_with_the_local_flag(
    tree, rec, tmp_path, monkeypatch, capsys
):
    projects, archive = tree
    archive.mkdir(parents=True, exist_ok=True)

    def row(slug, sid, when, agent=None, n=1):
        r = {
            "project_slug": slug,
            "session_id": sid,
            "sha256": str(n) * 64,
            "bytes": 10 * n,
            "mtime_ns": 1,
            "also_slugs": [],
            "archived_at": when,
        }
        if agent:
            r["agent"] = agent
        return r

    rows = [
        row("-opt-alpha", "a1", "2026-10-01T00:00:00Z", "fleet", 1),
        row("-opt-alpha", "a2", "2026-10-03T00:00:00Z", "fleet", 2),
        row("-opt-beta", "b1", "2026-10-02T00:00:00Z", "intel", 3),
        row("-opt-beta", "shared-id", "2026-10-04T00:00:00Z", None, 4),
    ]
    (archive / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (projects / "-opt-alpha" / "a2.jsonl").write_bytes(b"x")  # a2 is still local, a1 is not
    assert at.run(["--agent", "fleet"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert [line.split()[0] for line in out] == ["a2", "a1"], out
    assert "local=yes" in out[0] and "local=no" in out[1]
    assert all("intel" not in line and "shared-id" not in line for line in out)


# ── review round 1 (2026-10-11) regression guards for the agent tag ─────────────────────────────


def test_c11_an_ambiguous_registry_join_tags_nothing_and_an_agreeing_one_tags(
    tree, rec, tmp_path, monkeypatch
):
    """archiver-S1: two `<pid>.json` entries for one session id joining to different identity
    rows — the lexically-first file must not decide the tag."""
    projects, archive = tree
    (projects / "-opt-alpha" / "amb.jsonl").write_bytes(b'{"x":1}\n' * 10)
    (projects / "-opt-alpha" / "agree.jsonl").write_bytes(b'{"x":1}\n' * 10)
    identity = _identity(
        tmp_path,
        [
            {"session_id": "old-a", "name": "alpha", "pid": 100, "pid_start": 1, "at": 1},
            {"session_id": "old-b", "name": "beta", "pid": 200, "pid_start": 2, "at": 2},
        ],
    )
    sessions = _registry(
        tmp_path,
        [
            {"pid": 100, "sessionId": "amb", "procStart": "1"},
            {"pid": 200, "sessionId": "amb", "procStart": "2"},
            {"pid": 300, "sessionId": "agree", "procStart": "1"},
        ],
    )
    # a third entry for `agree` joining to the SAME name as a 100/1 twin is not ambiguous
    (sessions / "301.json").write_text(
        json.dumps({"pid": 100, "sessionId": "agree", "procStart": "1"})
    )
    (sessions / "300.json").write_text(
        json.dumps({"pid": 100, "sessionId": "agree", "procStart": "1"})
    )
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(sessions))
    assert at.run(["--no-ship"]) == 0
    rows = {
        r["session_id"]: r
        for r in (json.loads(x) for x in (archive / "manifest.jsonl").read_text().splitlines())
    }
    assert "agent" not in rows["amb"]
    assert rows["agree"]["agent"] == "alpha"


def test_c11_a_pretty_printed_registry_entry_joins_and_a_missing_at_ranks_below_zero(
    tree, rec, tmp_path, monkeypatch
):
    """archiver-S2: `<pid>.json` is one document, indented or not. archiver-S5: a row without `at`
    must not beat a row with an explicit `at: 0` by file order."""
    projects, archive = tree
    (projects / "-opt-alpha" / "pp.jsonl").write_bytes(b'{"x":1}\n' * 10)
    (projects / "-opt-alpha" / "tie.jsonl").write_bytes(b'{"x":1}\n' * 10)
    identity = _identity(
        tmp_path,
        [
            {"session_id": "old", "name": "kaizen", "pid": 777, "pid_start": 5, "at": 3},
            {"session_id": "tie", "name": "intel", "pid": 1, "pid_start": 1, "at": 0},
            {"session_id": "tie", "name": "fleet", "pid": 1, "pid_start": 1},  # no `at`
        ],
    )
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "777.json").write_text(
        json.dumps({"pid": 777, "sessionId": "pp", "procStart": "5"}, indent=2)
    )
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(sessions))
    assert at.run(["--no-ship"]) == 0
    rows = {
        r["session_id"]: r
        for r in (json.loads(x) for x in (archive / "manifest.jsonl").read_text().splitlines())
    }
    assert rows["pp"]["agent"] == "kaizen"
    assert rows["tie"]["agent"] == "intel"


def test_c12_agent_verb_local_flag_sees_a_surviving_hard_linked_twin(
    tree, rec, tmp_path, monkeypatch, capsys
):
    """archiver-S3: the primary name is gone, the worktree twin (`also_slugs`) survives — the
    history is still local."""
    projects, archive = tree
    archive.mkdir(parents=True, exist_ok=True)
    row = {
        "project_slug": "-opt-alpha",
        "session_id": "twin",
        "sha256": "9" * 64,
        "bytes": 1,
        "mtime_ns": 1,
        "also_slugs": ["-opt-alpha--claude-worktrees-x"],
        "archived_at": "2026-10-05T00:00:00Z",
        "agent": "fleet",
    }
    (archive / "manifest.jsonl").write_text(json.dumps(row) + "\n")
    (projects / "-opt-alpha--claude-worktrees-x").mkdir()
    (projects / "-opt-alpha--claude-worktrees-x" / "twin.jsonl").write_bytes(b"x")
    assert at.run(["--agent", "fleet"]) == 0
    assert "local=yes" in capsys.readouterr().out
    # a row whose also_slugs is a bare STRING (not the list the archiver writes) is one slug, never
    # a sequence of one-character directory names (review round 2, archiver-S6)
    row["also_slugs"] = "-opt-alpha--claude-worktrees-x"
    (archive / "manifest.jsonl").write_text(json.dumps(row) + "\n")
    assert at.run(["--agent", "fleet"]) == 0
    assert "local=yes" in capsys.readouterr().out
    # a scalar the archiver never writes (an int, a bool, a null) means NO aliases — the listing
    # reports the primary's state and never raises (review round 3, archiver-S8)
    for scalar in (7, True, None, 2.5, {"k": "v"}):
        row["also_slugs"] = scalar
        (archive / "manifest.jsonl").write_text(json.dumps(row) + "\n")
        assert at.run(["--agent", "fleet"]) == 0, scalar
        assert "local=no" in capsys.readouterr().out, scalar


def test_c12_agent_verb_refuses_to_double_as_another_verb(tree, rec, tmp_path, capsys):
    """archiver-S4: `--agent fleet --fetch a b` silently listed and never fetched."""
    _projects, archive = tree
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "manifest.jsonl").write_text("")
    with pytest.raises(SystemExit) as exc:
        at.run(["--agent", "fleet", "--fetch", "/-opt-x/s.jsonl.zst", str(tmp_path / "out")])
    assert exc.value.code == 2
    assert "--agent takes no other verb" in capsys.readouterr().err
    for extra in (
        ["--no-ship"],
        ["--dry-run"],
        ["--remote-count"],
        ["--version-at", "2026-01-01T00:00:00Z"],
    ):
        with pytest.raises(SystemExit) as more:
            at.run(["--agent", "fleet", *extra])
        assert more.value.code == 2, extra  # the usage exit, never a traceback or a listing
