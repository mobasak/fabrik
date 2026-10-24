"""Behavior Contract — Phase C.2/C.3 of the session-history retention plan (D-736),
`docs/development/plans/2026-09-06-plan-1-session-history-retention.md` § C.2.3.

Every grader guards one way the pruner could delete a transcript the invariant says to keep, or
fail to leave the trail a restore needs. rclone never runs for real: `at._run_rclone` is replaced
by a listing built from the LOCAL archive (so a test edits the dict to make the bucket disagree);
session-recall's index is the `pt._fetch_index_rows` seam; `/proc` is a fake tree under
`pt._PROC_ROOT`. zstd runs for real, so `.zst` objects exist and decompress.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "prune_transcripts.py"
UNITS = REPO / "scripts" / "sysadmin" / "systemd"

spec = importlib.util.spec_from_file_location("prune_transcripts", SCRIPT)
pt = importlib.util.module_from_spec(spec)
sys.modules["prune_transcripts"] = pt  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(pt)
at = pt.at

pytestmark = pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")

DAY = 86400
LIVE_PID, LIVE_START = 4242, 777_000
DEAD_PID = 999_999
NOW = time.time()


def _age(path: Path, days: float) -> None:
    ts = NOW - days * DAY
    os.utime(path, (ts, ts))


def _sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes(), usedforsecurity=False).hexdigest()  # noqa: S324


def _write_proc(proc: Path, pid: int, start: int) -> None:
    d = proc / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    fields = ["0"] * 52
    fields[0], fields[1] = str(pid), "(claude)"
    fields[21] = str(start)  # field 22, 1-based
    (d / "stat").write_text(" ".join(fields) + "\n")


class World:
    """The tree, the archive, the registry, the identity file, the fake proc and the fake bucket."""

    def __init__(self, tmp: Path, monkeypatch):
        self.tmp, self.mp = tmp, monkeypatch
        self.projects = tmp / "projects"
        self.archive = tmp / "archive"
        self.sessions = tmp / "sessions"
        self.identity = tmp / "agent-identity.jsonl"
        self.tasks = tmp / "tasks"
        self.snapshots = tmp / "shell-snapshots"
        self.proc = tmp / "proc"
        for d in (self.projects, self.sessions, self.tasks, self.snapshots, self.proc):
            d.mkdir(parents=True, exist_ok=True)
        _write_proc(self.proc, LIVE_PID, LIVE_START)
        monkeypatch.setattr(pt, "_PROC_ROOT", self.proc)
        for k in [k for k in os.environ if k.startswith(("RCLONE_", "SESSION_ARCHIVE_", "PRUNE_"))]:
            monkeypatch.delenv(k)
        monkeypatch.setenv("CLAUDE_PROJECTS_DIR", str(self.projects))
        monkeypatch.setenv("ARCHIVE_ROOT", str(self.archive))
        monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(self.sessions))
        monkeypatch.setenv("AGENT_IDENTITY_FILE", str(self.identity))
        monkeypatch.setenv("CLAUDE_TASKS_DIR", str(self.tasks))
        monkeypatch.setenv("CLAUDE_SHELL_SNAPSHOTS_DIR", str(self.snapshots))
        monkeypatch.setenv("ARCHIVE_AFTER_DAYS", "0")
        monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp / "no-such.env"))
        monkeypatch.setenv("SESSION_ARCHIVE_B2_KEY_ID", "kid-test")
        monkeypatch.setenv("SESSION_ARCHIVE_B2_APPLICATION_KEY", "SECRET-test-value")
        monkeypatch.setenv("SESSION_RECALL_RO_DSN", "postgresql://recall_ro:x@db.test/recall")
        monkeypatch.setenv("PRUNE_AFTER_DAYS", "3")
        monkeypatch.delenv("PRUNE_MAX_PER_RUN", raising=False)
        monkeypatch.delenv("ROTATE_ADVISE_MB", raising=False)
        # the fake bucket: slug → {name: (size, sha1)}; None = the listing fails
        self.bucket: dict[str, dict[str, tuple[int, str]] | None] = {}
        self.rclone_calls: list[list[str]] = []
        self.bucket_ledger: str | None = None  # the bucket's pruned.jsonl copy; None = absent
        monkeypatch.setattr(at, "_run_rclone", self._rclone)
        # session-recall's index: (inode, size) rows; None = the connection fails
        self.index: list[tuple[int, int]] | None = []
        monkeypatch.setattr(pt, "_fetch_index_rows", self._fetch_index)

    # ── building ────────────────────────────────────────────────────────────────────────────
    def transcript(
        self,
        slug: str,
        sid: str,
        *,
        days: float,
        body: bytes | None = None,
        twin: str | None = None,
    ) -> Path:
        p = self.projects / slug / f"{sid}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body or (json.dumps({"sid": sid, "slug": slug}).encode() + b"\n") * 50)
        _age(p, days)
        if twin:
            q = self.projects / twin / f"{sid}.jsonl"
            q.parent.mkdir(parents=True, exist_ok=True)
            os.link(p, q)
        return p

    def registry(self, sid: str, pid: int | None, start: int | None | str = LIVE_START) -> None:
        e: dict = {"sessionId": sid, "pidDomain": "boot-1"}
        if pid is not None:
            e["pid"] = pid
        if start is not None:
            e["procStart"] = str(start) if isinstance(start, int) else start
        (self.sessions / f"{pid or 'x'}-{sid}.json").write_text(json.dumps(e))

    def bind(self, sid: str, name: str, pid: int, start: int | None, at_ts: int = 1) -> None:
        row = {
            "session_id": sid,
            "name": name,
            "pid": pid,
            "pid_start": start,
            "toplevel": True,
            "at": at_ts,
        }
        with self.identity.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    def archive_all(self) -> None:
        """Run the real archiver locally, then index every file at its current inode and size."""
        assert at.run(["--no-ship"]) == 0
        self.index_everything()

    def index_everything(self) -> None:
        self.index = []
        for p in self.projects.glob("*/*.jsonl"):
            st = p.stat()
            self.index.append((st.st_ino, st.st_size))

    def bucket_from_archive(self) -> None:
        """slug → {path under the slug: (size, sha1)} — what `lsf -R` prints (a MAIN key is a bare name)."""
        self.bucket = {}
        for zst in self.archive.glob("*/**/*.jsonl.zst"):
            slug, key = zst.relative_to(self.archive).as_posix().split("/", 1)
            self.bucket.setdefault(slug, {})[key] = (zst.stat().st_size, _sha1(zst))

    def ready(self) -> None:
        self.archive_all()
        self.bucket_from_archive()

    # ── the seams ───────────────────────────────────────────────────────────────────────────
    def _rclone(self, argv, env):
        self.rclone_calls.append(list(argv))
        verb = argv[1]
        if verb == "lsf":
            slug = argv[-1].rstrip("/").rsplit("/", 1)[-1]
            objects = self.bucket.get(slug)
            if objects is None:
                return subprocess.CompletedProcess(argv, 1, "", "listing failed")
            # like rclone: without -R a listing shows the top-level objects only
            recursive = "-R" in argv
            out = "".join(
                f"{n};{s};{h}\n" for n, (s, h) in sorted(objects.items()) if recursive or "/" not in n
            )
            return subprocess.CompletedProcess(argv, 0, out, "")
        if verb == "copyto":  # --fetch: hand back the LOCAL archive's copy of that object
            src, dst = argv[-2], argv[-1]
            rel = src.split(f"{at._remote_base()}/", 1)[-1]
            local = self.archive / rel
            if rel == pt.LEDGER_NAME:
                # the bucket's copy of the restore list: served from `self.bucket_ledger` when set
                if self.bucket_ledger is not None:
                    Path(dst).write_text(self.bucket_ledger)
            elif local.is_file() and "/" in rel:
                slug, key = rel.split("/", 1)
                if (self.bucket.get(slug) or {}).get(key) is not None:
                    shutil.copyfile(local, dst)
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def _fetch_index(self, dsn):
        assert dsn and "recall" in dsn
        if self.index is None:
            raise ConnectionRefusedError("db down")
        return list(self.index)

    # ── reading back ────────────────────────────────────────────────────────────────────────
    def ledger(self) -> list[dict]:
        return at._json_rows(self.archive / pt.LEDGER_NAME)

    def log(self) -> list[dict]:
        return at._json_rows(self.archive / pt.LOG_NAME)

    def evaluate(self) -> dict[str, str | None]:
        cands, _refusals, _over = pt.evaluate_main(pt._world(None))
        return {c.session_id: c.reason for c in cands}


@pytest.fixture
def world(tmp_path, monkeypatch) -> World:
    w = World(tmp_path, monkeypatch)
    # alpha: two old sessions and a young one (the young one is also the slug's newest)
    w.transcript("-opt-alpha", "a-old-10", days=10)
    w.transcript("-opt-alpha", "a-old-06", days=6)
    w.transcript("-opt-alpha", "a-young", days=1)
    # beta: only old sessions — the newest of them must be kept
    w.transcript("-opt-beta", "b-old-10", days=10)
    w.transcript("-opt-beta", "b-old-05", days=5)
    return w


def _apply(expect: int, *extra: str) -> int:
    return pt.run(["--apply", "--expect", str(expect), *extra])


# ── r1–r3: the cheap rules ─────────────────────────────────────────────────────────────────


def test_r1_a_file_inside_the_window_is_never_offered(world):
    world.ready()
    verdict = world.evaluate()
    assert verdict["a-young"] == "in-window"
    assert verdict["a-old-10"] is None


def test_r2_a_registry_entry_with_a_live_pid_and_matching_procstart_is_open(world):
    world.registry("a-old-10", LIVE_PID, LIVE_START)
    world.ready()
    assert world.evaluate()["a-old-10"] == "open"


def test_r2_a_live_pid_with_another_procstart_is_a_recycled_pid_not_open(world):
    world.registry("a-old-10", LIVE_PID, LIVE_START + 5)
    world.ready()
    assert world.evaluate()["a-old-10"] is None


def test_r2_a_missing_or_non_numeric_procstart_beside_a_live_pid_counts_as_open(world):
    world.registry("a-old-10", LIVE_PID, None)
    world.registry("a-old-06", LIVE_PID, "not-a-number")
    world.ready()
    v = world.evaluate()
    assert v["a-old-10"] == "open" and v["a-old-06"] == "open"


def test_r2_a_dead_pid_is_not_open_and_a_registry_entry_without_a_pid_is(world):
    world.registry("a-old-10", DEAD_PID, LIVE_START)
    world.registry("a-old-06", None, None)
    world.ready()
    v = world.evaluate()
    assert v["a-old-10"] is None
    assert v["a-old-06"] == "open", "an entry we cannot test is fail-closed"


def test_r2_an_identity_row_alone_with_pid_and_pid_start_alive_is_open(world):
    world.bind("a-old-10", "fleet", LIVE_PID, LIVE_START)
    world.bind("a-old-06", "intel", LIVE_PID, LIVE_START + 1)  # recycled pid: not alive
    with world.identity.open("a") as fh:  # a row without a pid: untestable, so OPEN (pruner-S1)
        fh.write(json.dumps({"session_id": "b-old-10", "name": "kaizen", "at": 1}) + "\n")
    world.ready()
    v = world.evaluate()
    assert v["a-old-10"] == "open"
    assert v["a-old-06"] != "open"
    assert v["b-old-10"] == "open", "the identity leg is fail-closed like the registry leg"


def test_r3_the_newest_session_of_a_slug_is_kept_even_when_old(world):
    world.ready()
    v = world.evaluate()
    assert v["b-old-05"] == "newest-of-slug"
    assert v["b-old-10"] is None


def test_r3_each_agents_newest_is_kept_even_when_another_agents_session_is_newer(world):
    world.transcript("-opt-fabrik", "hub-infra-20", days=20)
    world.transcript("-opt-fabrik", "hub-infra-12", days=12)
    world.transcript("-opt-fabrik", "hub-fleet-07", days=7)
    world.transcript("-opt-fabrik", "hub-none-04", days=4)  # the slug's newest, untagged
    for sid, name in (
        ("hub-infra-20", "infra"),
        ("hub-infra-12", "infra"),
        ("hub-fleet-07", "fleet"),
    ):
        world.bind(sid, name, DEAD_PID, 1)
    world.ready()
    v = world.evaluate()
    assert v["hub-infra-12"] == "newest-of-agent"
    assert v["hub-fleet-07"] == "newest-of-agent"
    assert v["hub-infra-20"] is None, "an agent's OLDER session is deletable"
    assert v["hub-none-04"] == "newest-of-slug"


# ── r8: session-recall must hold it ───────────────────────────────────────────────────────


def test_r8_no_index_row_a_size_mismatch_no_dsn_or_a_dead_db_all_refuse_as_not_indexed(
    world, monkeypatch
):
    world.ready()
    ino = (world.projects / "-opt-alpha" / "a-old-10.jsonl").stat().st_ino
    world.index = [(i, s) for i, s in world.index if i != ino]
    assert world.evaluate()["a-old-10"] == "not-indexed"
    world.index_everything()
    world.index = [(i, s + 1 if i == ino else s) for i, s in world.index]
    assert world.evaluate()["a-old-10"] == "not-indexed"
    world.index_everything()
    assert world.evaluate()["a-old-10"] is None
    world.index = None
    assert world.evaluate()["a-old-10"] == "not-indexed"
    world.index_everything()
    monkeypatch.setenv("SESSION_RECALL_RO_DSN", "")
    assert world.evaluate()["a-old-10"] == "not-indexed"


def test_r8_a_row_for_the_inode_under_the_worktree_name_passes_the_hub_name(world):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)  # the newest of both slugs' twin-less rows
    world.transcript("-opt-fabrik--claude-worktrees-fleet", "wt-2", days=4)
    world.ready()
    # ONE row per inode, keyed by inode: that is what session-recall keeps (the worktree name's)
    ino = (world.projects / "-opt-fabrik--claude-worktrees-fleet" / "hub-1.jsonl").stat().st_ino
    size = (world.projects / "-opt-fabrik" / "hub-1.jsonl").stat().st_size
    world.index = [(ino, size)]
    assert world.evaluate()["hub-1"] is None


# ── r4–r7: the archive and the bucket ─────────────────────────────────────────────────────


def test_r4_no_manifest_row_is_not_archived_and_a_changed_file_is_a_sha_mismatch(world):
    world.ready()
    late = world.transcript("-opt-alpha", "a-late", days=9)  # after the archive run: no row
    world.index_everything()
    assert world.evaluate()["a-late"] == "not-archived"
    with (world.projects / "-opt-alpha" / "a-old-10.jsonl").open("ab") as fh:
        fh.write(b'{"resumed":1}\n')
    _age(world.projects / "-opt-alpha" / "a-old-10.jsonl", 10)
    world.index_everything()
    assert world.evaluate()["a-old-10"] == "sha-mismatch"
    assert late.exists()


def test_r5_a_missing_corrupt_or_foreign_zst_refuses(world):
    world.ready()
    zst = world.archive / "-opt-alpha" / "a-old-10.jsonl.zst"
    keep = zst.read_bytes()
    zst.unlink()
    assert world.evaluate()["a-old-10"] == "zst-missing"
    zst.write_bytes(b"not a zstd frame")
    assert world.evaluate()["a-old-10"] == "zst-corrupt"
    other = world.archive / "-opt-beta" / "b-old-10.jsonl.zst"
    shutil.copyfile(other, zst)  # a valid frame holding ANOTHER session's bytes
    assert world.evaluate()["a-old-10"] == "zst-bytes-differ"
    zst.write_bytes(keep)
    world.bucket_from_archive()
    assert world.evaluate()["a-old-10"] is None


def test_r6_the_bucket_must_list_the_object_with_the_same_size_and_sha1(world):
    world.ready()
    name = "a-old-10.jsonl.zst"
    size, sha1 = world.bucket["-opt-alpha"][name]
    del world.bucket["-opt-alpha"][name]
    assert world.evaluate()["a-old-10"] == "remote-missing"
    world.bucket["-opt-alpha"][name] = (size + 1, sha1)
    assert world.evaluate()["a-old-10"] == "remote-differs"
    world.bucket["-opt-alpha"][name] = (size, "0" * 40)
    assert world.evaluate()["a-old-10"] == "remote-differs"
    world.bucket["-opt-alpha"][name] = (size, sha1)
    assert world.evaluate()["a-old-10"] is None
    world.bucket["-opt-alpha"][name] = (size, sha1.upper())  # some backends list upper-case hex
    assert world.evaluate()["a-old-10"] is None, "the listing's case is normalised (graders-S1)"


def test_r6_a_failed_listing_refuses_every_object_of_that_slug_and_no_other(world):
    world.ready()
    world.bucket["-opt-alpha"] = None
    v = world.evaluate()
    assert v["a-old-10"] == "listing-failed" and v["a-old-06"] == "listing-failed"
    assert v["b-old-10"] is None
    assert (
        sum(1 for c in world.rclone_calls if c[1] == "lsf" and c[-1].endswith("/-opt-alpha/")) == 1
    ), "one listing per slug"


def test_r6_the_listing_needs_credentials_and_without_them_nothing_in_the_slug_is_deleted(
    world, monkeypatch
):
    world.ready()
    monkeypatch.delenv("SESSION_ARCHIVE_B2_KEY_ID")
    v = world.evaluate()
    assert v["a-old-10"] == "listing-failed"


def test_r7_one_inode_two_names_where_one_name_fails_a_rule_or_has_no_row_keeps_both(world):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)
    world.transcript("-opt-fabrik--claude-worktrees-fleet", "wt-2", days=4)
    world.ready()
    assert world.evaluate()["hub-1"] is None
    # the twin's slug has no row for it: a link created after the archive run. The aliasing the
    # pop below removes lives in archive_transcripts._latest_rows (`also_slugs` → a row per
    # alias slug), which the pruner calls as `at._latest_rows` — not in prune_transcripts.py.
    manifest = world.archive / at.MANIFEST_NAME
    rows = [json.loads(x) for x in manifest.read_text().splitlines()]
    for r in rows:
        if r["session_id"] == "hub-1":
            r.pop("also_slugs", None)
    manifest.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert world.evaluate()["hub-1"] == "not-archived"
    hub, wt = (
        world.projects / "-opt-fabrik" / "hub-1.jsonl",
        world.projects / "-opt-fabrik--claude-worktrees-fleet" / "hub-1.jsonl",
    )
    assert _apply(3) == 0, "the three alpha/beta inodes; the hub inode is not in the set"
    assert hub.exists() and wt.exists()


def test_r7_two_names_of_one_inode_with_different_session_ids_are_refused(world):
    """A hand-made hard link under another name: no per-name lookup can be keyed right (pruner-S2)."""
    world.transcript("-opt-alpha", "a-old-10", days=10)  # re-create: the fixture's file, re-aged
    other = world.projects / "-opt-beta" / "b-alias.jsonl"
    os.link(world.projects / "-opt-alpha" / "a-old-10.jsonl", other)
    world.ready()
    v = world.evaluate()
    assert v["a-old-10"] == "names-differ"
    assert _apply(2) == 0  # a-old-06 and b-old-10 only
    assert (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists() and other.exists()


def test_r7_a_twin_that_is_the_newest_of_its_slug_keeps_the_hub_name_too(world):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)
    world.ready()  # hub-1 is the worktree slug's ONLY (so newest) session
    assert world.evaluate()["hub-1"] == "newest-of-slug"


# ── the apply path: --expect, the cap, the ledger, the last look ──────────────────────────


def test_dry_run_is_the_default_deletes_nothing_and_writes_a_summary_row(world, capsys):
    world.ready()
    before = sorted(str(p) for p in world.projects.glob("*/*.jsonl"))
    assert pt.run([]) == 0
    assert sorted(str(p) for p in world.projects.glob("*/*.jsonl")) == before
    out = capsys.readouterr().out
    assert "dry-run" in out and "would delete" in out and "deletable 3" in out
    row = world.log()[-1]
    assert row["mode"] == "dry-run" and row["deleted"] == 0 and row["deletable"] == 3
    assert row["refusals"]["in-window"] == 1 and row["refusals"]["newest-of-slug"] == 1, (
        "the FIRST failing rule names the refusal: alpha's newest is in-window, beta's newest-of-slug"
    )


def test_apply_without_expect_or_with_the_wrong_count_deletes_nothing(world, capsys):
    world.ready()
    with pytest.raises(SystemExit) as exc:
        pt.run(["--apply"])
    assert exc.value.code == 2
    assert _apply(2) == 3
    err = capsys.readouterr().err
    assert "--expect 2" in err and "count is 3" in err
    assert len(list(world.projects.glob("*/*.jsonl"))) == 5
    assert world.ledger() == []


def test_apply_with_the_right_count_deletes_exactly_this_runs_set_oldest_first(world):
    world.ready()
    assert _apply(3) == 0
    left = {p.name for p in world.projects.glob("*/*.jsonl")}
    assert left == {"a-young.jsonl", "b-old-05.jsonl"}
    rows = world.ledger()
    assert [r["session_id"] for r in rows] == ["a-old-10", "b-old-10", "a-old-06"], (
        "oldest mtime first"
    )
    for r in rows:
        assert (
            r["sha256"]
            and r["object"].endswith(f"{r['session_id']}.jsonl.zst")
            and r["object_sha1"]
        )
    assert world.log()[-1]["deleted"] == 3


def test_the_cap_takes_the_oldest_cap_many_and_defers_the_rest_on_both_paths(
    world, monkeypatch, capsys
):
    world.ready()
    monkeypatch.setenv("PRUNE_MAX_PER_RUN", "2")
    assert pt.run([]) == 0
    assert "this run 2 (cap 2) · deferred 1" in capsys.readouterr().out
    assert _apply(3) == 3, "the count must be the capped figure"
    assert _apply(2) == 0
    assert {r["session_id"] for r in world.ledger()} == {"a-old-10", "b-old-10"}
    assert world.log()[-1]["deferred"] == 1
    # the nightly path: no --expect, the same cap
    world.ledger_before = len(world.ledger())
    assert pt.run(["--apply", "--nightly", "--tier", "main"]) == 0
    assert [r["session_id"] for r in world.ledger()][-1] == "a-old-06"


def test_max_widens_or_narrows_a_hand_run_and_expect_must_match_it(world):
    world.ready()
    assert _apply(1, "--max", "1") == 0
    assert [r["session_id"] for r in world.ledger()] == ["a-old-10"]
    assert _apply(1, "--max", "5") == 3, "2 remain deletable; --expect 1 is stale"
    assert _apply(2, "--max", "5") == 0


def test_the_ledger_row_is_written_and_fsynced_before_the_unlink_and_names_every_path(
    world, monkeypatch
):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)
    world.transcript("-opt-fabrik--claude-worktrees-fleet", "wt-2", days=4)
    world.ready()
    seen: list[tuple[int, int]] = []
    real_unlink = Path.unlink

    def spy_unlink(self, *a, **kw):
        seen.append((len(world.ledger()), 1))
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", spy_unlink)
    assert _apply(4) == 0
    assert len(seen) == 5, "a-old-10, b-old-10, a-old-06 and hub-1's two names: five unlinks"
    assert all(n >= 1 for n, _ in seen), "an unlink ran before any ledger row existed"
    hub_row = next(r for r in world.ledger() if r["session_id"] == "hub-1")
    assert len(hub_row["paths"]) == 2 and not any(Path(p).exists() for p in hub_row["paths"])


def test_the_last_look_skips_a_file_that_changed_between_the_hash_and_the_unlink(
    world, monkeypatch
):
    world.ready()
    target = world.projects / "-opt-alpha" / "a-old-10.jsonl"
    real = pt.open_sessions
    calls = {"n": 0}

    def grow_then_answer(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:  # the r2-again call right before the unlinks (evaluate_main made one)
            with target.open("ab") as fh:
                fh.write(b'{"late turn":1}\n')
        return real(*a, **kw)

    monkeypatch.setattr(pt, "open_sessions", grow_then_answer)
    assert _apply(3) == 0
    assert target.exists()
    assert "a-old-10" not in {r["session_id"] for r in world.ledger()}
    row = world.log()[-1]
    assert row["refusals"]["changed-under-hash"] == 1 and row["deleted"] == 2


def test_the_last_look_catches_a_same_size_rewrite_by_mtime(world, monkeypatch):
    """A rewrite that keeps the size (one byte changed) is caught by the mtime half of the stat."""
    world.ready()
    target = world.projects / "-opt-alpha" / "a-old-10.jsonl"
    real = pt.open_sessions
    calls = {"n": 0}

    def rewrite_then_answer(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            body = bytearray(target.read_bytes())
            body[0] = ord("X")
            target.write_bytes(bytes(body))  # same size, new bytes, new mtime
        return real(*a, **kw)

    monkeypatch.setattr(pt, "open_sessions", rewrite_then_answer)
    assert _apply(3) == 0
    assert target.exists()
    assert world.log()[-1]["refusals"]["changed-under-hash"] == 1


def test_the_last_look_re_checks_open_right_before_the_unlink(world, monkeypatch):
    world.ready()
    real = pt.open_sessions
    calls = {"n": 0}

    def opens_late(*a, **kw):
        calls["n"] += 1
        out = real(*a, **kw)
        return out | {"a-old-10"} if calls["n"] == 2 else out

    monkeypatch.setattr(pt, "open_sessions", opens_late)
    assert _apply(3) == 0
    assert (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists()


def test_the_open_re_check_runs_before_each_unlink_not_once_before_the_loop(world, monkeypatch):
    """Run order is a-old-10, b-old-10, a-old-06 (oldest first). a-old-06's session opens only at
    the re-check made for ITS unlink (call 4: one in evaluate_main, then one per inode) — a single
    pre-loop snapshot would have deleted it (pruner-S3)."""
    world.ready()
    real = pt.open_sessions
    calls = {"n": 0}

    def opens_for_the_third(*a, **kw):
        calls["n"] += 1
        out = real(*a, **kw)
        return out | {"a-old-06"} if calls["n"] >= 4 else out

    monkeypatch.setattr(pt, "open_sessions", opens_for_the_third)
    assert _apply(3) == 0
    assert (world.projects / "-opt-alpha" / "a-old-06.jsonl").exists()
    assert not (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists()
    assert not (world.projects / "-opt-beta" / "b-old-10.jsonl").exists()
    assert calls["n"] == 4, "one call in evaluate_main, then one per inode in the run set"


def test_the_archiver_lock_held_refuses_with_exit_3_and_deletes_nothing(world):
    world.ready()
    import fcntl

    world.archive.mkdir(exist_ok=True)
    with (world.archive / at.LOCK_NAME).open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert _apply(3) == 3
        assert pt.run([]) == 3
    assert len(list(world.projects.glob("*/*.jsonl"))) == 5
    assert world.log()[-1].get("refused", "").startswith("the archive lock is held")


def test_no_manifest_refuses_before_scanning(world, capsys):
    assert pt.run([]) == 3
    assert "no manifest" in capsys.readouterr().err


def test_an_exception_mid_run_writes_the_summary_row_with_error_exits_1_and_leaves_no_unlogged_unlink(
    world, monkeypatch
):
    world.ready()
    real = pt._append_fsync
    state = {"rows": 0}

    def boom_after_first(path, row):
        real(path, row)
        if path.name == pt.LEDGER_NAME:
            state["rows"] += 1
            if state["rows"] == 2:
                raise RuntimeError("disk vanished")

    monkeypatch.setattr(pt, "_append_fsync", boom_after_first)
    assert _apply(3) == 1
    ledger, present = world.ledger(), {p.name for p in world.projects.glob("*/*.jsonl")}
    assert len(ledger) == 2
    unlinked = [r for r in ledger if not Path(r["paths"][0]).exists()]
    assert len(unlinked) == 1, "exactly the file whose row landed before the crash is gone"
    assert "b-old-10.jsonl" in present, (
        "the second row landed, its unlink never ran — the file is still there"
    )
    log = world.log()[-1]
    assert "RuntimeError" in log["error"] and log["mode"] == "apply"


def test_over_threshold_lists_every_main_transcript_larger_than_rotate_advise_mb(
    world, monkeypatch
):
    world.transcript("-opt-alpha", "a-fat", days=1, body=b"x" * (2 * 1024 * 1024 + 1))
    world.ready()
    monkeypatch.setenv("ROTATE_ADVISE_MB", "2")
    assert pt.run([]) == 0
    assert world.log()[-1]["over_threshold"] == [str(world.projects / "-opt-alpha" / "a-fat.jsonl")]


def test_status_prints_the_last_row_and_the_last_apply_row(world, capsys):
    world.ready()
    assert _apply(3) == 0
    assert pt.run([]) == 0  # a later dry-run
    capsys.readouterr()
    assert pt.run(["--status"]) == 0
    out = capsys.readouterr().out
    last, last_apply = out.splitlines()[0], out.splitlines()[1]
    assert (
        '"mode": "dry-run"' in last
        and '"mode": "apply"' in last_apply
        and '"deleted": 3' in last_apply
    )
    assert len(world.log()) == 2, "--status writes no row"


def test_settings_come_from_the_env_file_when_the_process_env_lacks_them(
    world, tmp_path, monkeypatch
):
    env = tmp_path / "hub.env"
    env.write_text(
        'PRUNE_AFTER_DAYS="7" # a week\nexport PRUNE_MAX_PER_RUN=1\nSESSION_RECALL_RO_DSN=postgresql://x\nPRUNE_AFTER_DAYS=8\n'
    )
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env))
    monkeypatch.delenv("PRUNE_AFTER_DAYS")
    monkeypatch.delenv("SESSION_RECALL_RO_DSN")
    w = pt._world(None)
    assert (w.after_days, w.cap, w.dsn) == (8.0, 1, "postgresql://x"), (
        "the last line wins; quotes and export are read"
    )


# ── --restore ─────────────────────────────────────────────────────────────────────────────


def test_restore_fetches_the_object_recreates_every_path_as_one_inode_and_touches_mtime(world):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)
    world.transcript("-opt-fabrik--claude-worktrees-fleet", "wt-2", days=4)
    world.ready()
    assert _apply(4) == 0
    row = next(r for r in world.ledger() if r["session_id"] == "hub-1")
    assert not any(Path(p).exists() for p in row["paths"])
    assert pt.run(["--restore", "hub-1"]) == 0
    paths = [Path(p) for p in row["paths"]]
    assert all(p.exists() for p in paths)
    assert len({p.stat().st_ino for p in paths}) == 1
    assert at._sha256(paths[0]) == row["sha256"]
    assert time.time() - paths[0].stat().st_mtime < 60, "a restored file carries a fresh mtime"
    assert world.evaluate()["hub-1"] == "in-window"


def test_restore_hard_links_to_a_surviving_identical_twin_without_fetching(world):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)
    world.transcript("-opt-fabrik--claude-worktrees-fleet", "wt-2", days=4)
    world.ready()
    assert _apply(4) == 0
    row = next(r for r in world.ledger() if r["session_id"] == "hub-1")
    survivor, gone = Path(row["paths"][0]), Path(row["paths"][1])
    # the half-unlinked state: one twin back from the object, the other still missing
    zst = world.archive / "-opt-fabrik" / "hub-1.jsonl.zst"
    subprocess.run(["zstd", "-dc", "-q", str(zst), "-o", str(survivor)], check=True)
    _age(survivor, 10)  # the survivor carries its OLD mtime: a hard link would inherit it
    world.rclone_calls.clear()
    assert pt.run(["--restore", "hub-1"]) == 0
    assert gone.exists() and gone.stat().st_ino == survivor.stat().st_ino
    assert not any(c[1] == "copyto" for c in world.rclone_calls), "a surviving twin means no fetch"
    assert time.time() - survivor.stat().st_mtime < 60, (
        "the inode's mtime is now, or r1 offers it again"
    )
    assert world.evaluate()["hub-1"] == "in-window"


def test_restore_refuses_a_survivor_with_another_sha256_and_writes_nothing(world, capsys):
    world.transcript("-opt-fabrik", "hub-1", days=10, twin="-opt-fabrik--claude-worktrees-fleet")
    world.transcript("-opt-fabrik", "hub-2", days=4)
    world.transcript("-opt-fabrik--claude-worktrees-fleet", "wt-2", days=4)
    world.ready()
    assert _apply(4) == 0
    row = next(r for r in world.ledger() if r["session_id"] == "hub-1")
    survivor, gone = Path(row["paths"][0]), Path(row["paths"][1])
    survivor.write_bytes(b'{"resumed after the prune":1}\n')
    assert pt.run(["--restore", "hub-1"]) == 3
    assert not gone.exists()
    assert "live history" in capsys.readouterr().err


def test_restore_whose_fetch_fails_exits_3_naming_the_three_causes_with_fetch_stderr(world, capsys):
    world.ready()
    assert _apply(3) == 0
    world.bucket["-opt-alpha"] = {}  # the object is gone from the bucket: copyto writes nothing
    assert pt.run(["--restore", "a-old-10"]) == 3
    err = capsys.readouterr().err
    assert (
        "absent from the bucket" in err and "download host" in err and "rclone itself failed" in err
    )
    assert "was not downloaded" in err, "--fetch's own line is passed through"
    assert not (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists()


def test_restore_falls_back_to_the_buckets_ledger_copy_when_the_local_one_is_gone(world):
    """The restore list is off-box too (the archiver ships pruned.jsonl); with no local ledger the
    row is read from the bucket's copy — and with none there either, a refusal (graders-H1)."""
    world.ready()
    assert _apply(3) == 0
    ledger = world.archive / pt.LEDGER_NAME
    world.bucket_ledger = ledger.read_text()
    ledger.unlink()
    assert pt.run(["--restore", "a-old-10"]) == 0
    assert (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists()
    fetched = [c for c in world.rclone_calls if c[1] == "copyto"]
    assert fetched and fetched[0][-2].endswith("/" + pt.LEDGER_NAME), "the ledger was fetched first"
    world.bucket_ledger = None
    assert pt.run(["--restore", "b-old-10"]) == 3


def test_restore_computes_the_object_key_when_an_old_row_lacks_it(world):
    """A ledger row from before the `object` key: the key is `<slug>/<sid>.jsonl.zst` (graders-S3)."""
    world.ready()
    assert _apply(3) == 0
    ledger = world.archive / pt.LEDGER_NAME
    rows = [json.loads(x) for x in ledger.read_text().splitlines()]
    for r in rows:
        r.pop("object", None)
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert pt.run(["--restore", "a-old-10"]) == 0
    fetched = [c for c in world.rclone_calls if c[1] == "copyto"]
    assert fetched[-1][-2].endswith("/-opt-alpha/a-old-10.jsonl.zst")
    assert at._sha256(world.projects / "-opt-alpha" / "a-old-10.jsonl") == rows[0]["sha256"]


def test_restore_without_zstd_refuses_before_any_fetch(world, monkeypatch, capsys):
    """A restore cannot finish without zstd: exit 3 naming it, nothing fetched (pruner-H3)."""
    world.ready()
    assert _apply(3) == 0
    real_which = shutil.which
    monkeypatch.setattr(at.shutil, "which", lambda n: None if n == "zstd" else real_which(n))
    world.rclone_calls.clear()
    assert pt.run(["--restore", "a-old-10"]) == 3
    assert "zstd" in capsys.readouterr().err
    assert not any(c[1] == "copyto" for c in world.rclone_calls)
    assert not (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists()


def test_restore_never_overwrites_and_refuses_an_unknown_session(world, capsys):
    world.ready()
    assert pt.run(["--restore", "no-such-session"]) == 3
    assert "no pruned.jsonl row" in capsys.readouterr().err


# ── --verify-ledger ───────────────────────────────────────────────────────────────────────


def test_verify_ledger_prints_ok_per_row_missing_for_an_absent_object_and_exits_3(world, capsys):
    world.ready()
    assert _apply(3) == 0
    assert pt.run(["--verify-ledger"]) == 0
    out = capsys.readouterr().out
    assert out.count("OK     ") == 3 and "MISSING" not in out.replace("0 MISSING", "")
    del world.bucket["-opt-alpha"]["a-old-10.jsonl.zst"]
    assert pt.run(["--verify-ledger"]) == 3
    out = capsys.readouterr().out
    assert out.count("MISSING -opt-alpha/a-old-10") == 1 and out.count("OK     ") == 2
    assert not any(c[1] == "copyto" for c in world.rclone_calls), "verify-ledger needs no download"


def test_the_read_only_verbs_take_no_other_flag(world):
    for argv in (
        ["--status", "--apply"],
        ["--verify-ledger", "--status"],
        ["--restore", "x", "--max", "3"],
    ):
        with pytest.raises(SystemExit) as exc:
            pt.run(argv)
        assert exc.value.code == 2


# ── C.3: the subagent tier ────────────────────────────────────────────────────────────────


def _sidechain(world: World, slug: str, sid: str, name: str, *, days: float, running: bool) -> Path:
    d = world.projects / slug / sid / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.jsonl"
    stop = "tool_use" if running else "end_turn"
    p.write_text(json.dumps({"message": {"role": "assistant", "stop_reason": stop}}) + "\n")
    _age(p, days)
    return p


def test_c3_an_old_sidechain_of_a_closed_parent_is_deleted_with_a_row_and_a_young_one_stays(world):
    old = _sidechain(world, "-opt-alpha", "a-old-10", "agent-old", days=10, running=False)
    young = _sidechain(world, "-opt-alpha", "a-young", "agent-young", days=1, running=False)
    world.ready()
    assert pt.run(["--apply", "--tier", "subagents", "--expect", "1"]) == 0
    assert not old.exists() and young.exists()
    row = world.ledger()[-1]
    assert row["tier"] == "subagents" and row["kind"] == "subagent" and row["paths"] == [str(old)]
    assert len(list(world.projects.glob("*/*.jsonl"))) == 5, "the MAIN tier was not touched"


def test_c3_a_live_parent_keeps_every_sidechain_and_an_in_flight_one_stays(world, monkeypatch):
    kept = _sidechain(world, "-opt-alpha", "a-old-10", "agent-kept", days=10, running=False)
    world.registry("a-old-10", LIVE_PID, LIVE_START)
    monkeypatch.setenv("PRUNE_AFTER_DAYS", "0")
    flight = _sidechain(
        world, "-opt-alpha", "a-old-06", "agent-flight", days=10 / 1440, running=True
    )  # 10 min
    done = _sidechain(world, "-opt-alpha", "a-old-06", "agent-done", days=10 / 1440, running=False)
    world.ready()
    assert pt.run(["--tier", "subagents"]) == 0
    s_ref = world.log()[-1]["subagents_refusals"]
    assert s_ref["parent-open"] == 1 and s_ref["in-flight"] == 1
    assert pt.run(["--apply", "--tier", "subagents", "--expect", "1"]) == 0
    assert kept.exists() and flight.exists() and not done.exists()


def test_c3_tasks_and_shell_snapshots_older_than_the_window_go_with_a_row_each(world):
    old_task = world.tasks / "sess-old"
    old_task.mkdir()
    (old_task / "t.json").write_text("{}")
    _age(old_task / "t.json", 5)
    _age(old_task, 5)
    new_task = world.tasks / "sess-new"
    new_task.mkdir()
    (new_task / "t.json").write_text("{}")
    old_snap = world.snapshots / "snapshot-old.sh"
    old_snap.write_text("echo")
    _age(old_snap, 4)
    new_snap = world.snapshots / "snapshot-new.sh"
    new_snap.write_text("echo")
    world.ready()
    assert pt.run(["--apply", "--tier", "subagents", "--expect", "2"]) == 0
    assert (
        not old_task.exists() and new_task.exists() and not old_snap.exists() and new_snap.exists()
    )
    kinds = sorted(r["kind"] for r in world.ledger())
    assert kinds == ["shell-snapshot", "task"]


def test_nightly_runs_both_tiers_under_the_cap_without_expect(world, monkeypatch):
    old = _sidechain(world, "-opt-alpha", "a-old-10", "agent-old", days=10, running=False)
    world.ready()
    monkeypatch.setenv("PRUNE_MAX_PER_RUN", "1")
    assert pt.run(["--apply", "--nightly"]) == 0
    rows = world.ledger()
    assert [r["tier"] for r in rows] == ["main", "subagents"]
    assert rows[0]["session_id"] == "a-old-10" and not old.exists()
    assert world.log()[-1]["tiers"] == ["main", "subagents"] and world.log()[-1]["deferred"] == 2


# ── D-1182: the subagent tier is archived, so its pruning is vouched ──────────────────────


def test_c3_a_sidechain_is_deleted_only_when_the_archive_vouches_for_it(world):
    side = {
        n: _sidechain(world, "-opt-alpha", "a-old-10", n, days=10, running=False)
        for n in ("agent-changed", "agent-nozst", "agent-nobucket", "agent-good")
    }
    world.ready()
    norow = _sidechain(world, "-opt-alpha", "a-old-10", "agent-norow", days=10, running=False)
    with side["agent-changed"].open("ab") as fh:
        fh.write(b'{"late":1}\n')
    _age(side["agent-changed"], 10)
    zdir = world.archive / "-opt-alpha" / "a-old-10" / "subagents"
    (zdir / "agent-nozst.jsonl.zst").unlink()
    del world.bucket["-opt-alpha"]["a-old-10/subagents/agent-nobucket.jsonl.zst"]
    good_sha = at._sha256(side["agent-good"])
    assert pt.run(["--tier", "subagents"]) == 0
    s_ref = world.log()[-1]["subagents_refusals"]
    assert {k: s_ref.get(k) for k in ("not-archived", "sha-mismatch", "zst-missing", "remote-missing")} == {
        "not-archived": 1,
        "sha-mismatch": 1,
        "zst-missing": 1,
        "remote-missing": 1,
    }, s_ref
    assert pt.run(["--apply", "--tier", "subagents", "--expect", "1"]) == 0
    assert not side["agent-good"].exists()
    assert norow.exists() and all(side[n].exists() for n in side if n != "agent-good")
    row = world.ledger()[-1]
    key = "a-old-10/subagents/agent-good.jsonl.zst"
    assert row["kind"] == "subagent" and row["sha256"] == good_sha
    assert row["object"] == f"-opt-alpha/{key}"
    assert (row["object_bytes"], row["object_sha1"]) == world.bucket["-opt-alpha"][key]
    lsf = [c for c in world.rclone_calls if c[1] == "lsf"]
    assert lsf and all("-R" in c and "--fast-list" in c for c in lsf), "one recursive B2 list per slug"


def test_the_summary_line_counts_each_tier_when_a_main_inode_is_skipped(world, monkeypatch, capsys):
    """The closing line once split `deleted` by `len(run_main)`: a MAIN inode skipped by its last look
    was reported as a subagent-tier deletion (review W-62d2ce7d pass 1, B-haiku-2/B-sonnet-4)."""
    _sidechain(world, "-opt-alpha", "a-old-06", "agent-one", days=10, running=False)
    world.ready()
    real = pt.open_sessions
    calls = {"n": 0}

    def opens_late(*a, **kw):
        calls["n"] += 1  # 1 evaluate_main, 2 evaluate_subagents, 3+ the per-unlink re-reads
        out = real(*a, **kw)
        return out | {"a-old-10"} if calls["n"] >= 3 else out

    monkeypatch.setattr(pt, "open_sessions", opens_late)
    assert pt.run(["--apply", "--nightly"]) == 0
    assert "deleted 3 (MAIN 2 inode(s), subagent-tier 1)" in capsys.readouterr().out


def test_a_zst_that_vanishes_before_its_sha1_refuses_the_file_not_the_night(world, monkeypatch):
    world.ready()

    def gone(_path):
        raise FileNotFoundError("removed under the pruner")

    monkeypatch.setattr(pt, "_sha1", gone)
    reasons = world.evaluate()
    assert reasons["a-old-10"] == "zst-missing" and reasons["b-old-10"] == "zst-missing"


def test_c3_the_last_look_skips_a_sidechain_that_changed(world, monkeypatch):
    target = _sidechain(world, "-opt-alpha", "a-old-10", "agent-late", days=10, running=False)
    world.ready()
    real = pt.open_sessions
    calls = {"n": 0}

    def grow_then_answer(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:  # evaluate_subagents made the first; this is the one right before the unlink
            with target.open("ab") as fh:
                fh.write(b'{"late turn":1}\n')
        return real(*a, **kw)

    monkeypatch.setattr(pt, "open_sessions", grow_then_answer)
    assert pt.run(["--apply", "--tier", "subagents", "--expect", "1"]) == 0
    assert target.exists()
    assert not any(r.get("kind") == "subagent" for r in world.ledger()), "no row for a skipped file"
    assert world.log()[-1]["subagents_refusals"]["changed-under-hash"] == 1


def test_restore_puts_a_pruned_sidechain_back_and_keeps_the_main_selection(world, capsys):
    side = _sidechain(world, "-opt-alpha", "a-old-10", "agent-back", days=10, running=False)
    body = side.read_bytes()
    world.ready()
    assert _apply(3) == 0  # MAIN first: a-old-10's own transcript is pruned
    assert pt.run(["--apply", "--tier", "subagents", "--expect", "1"]) == 0  # then its sidechain
    assert not side.exists()
    # a MAIN restore still picks the MAIN row although a later subagent row carries the same session id
    assert pt.run(["--restore", "a-old-10"]) == 0
    assert (world.projects / "-opt-alpha" / "a-old-10.jsonl").exists() and not side.exists()
    assert pt.run(["--restore", "agent-back"]) == 0
    assert side.read_bytes() == body
    assert time.time() - side.stat().st_mtime < 60
    capsys.readouterr()
    assert pt.run(["--verify-ledger"]) == 0
    assert "OK      -opt-alpha/a-old-10/subagents/agent-back.jsonl.zst" in capsys.readouterr().out
    # a pre-D-1182 row (no sha256) refuses by name; two distinct paths for one id refuse and list both
    with (world.archive / pt.LEDGER_NAME).open("a") as fh:
        for sid in ("x-1", "x-2"):
            p = world.projects / "-opt-alpha" / sid / "subagents" / "agent-twice.jsonl"
            fh.write(json.dumps({"tier": "subagents", "kind": "subagent", "project_slug": "-opt-alpha",
                                 "session_id": sid, "paths": [str(p)], "sha256": "ab" * 32,
                                 "object": f"-opt-alpha/{sid}/subagents/agent-twice.jsonl.zst",
                                 "pruned_at": "2026-10-24T00:00:00Z"}) + "\n")
        old = world.projects / "-opt-alpha" / "x-3" / "subagents" / "agent-old.jsonl"
        fh.write(json.dumps({"tier": "subagents", "kind": "subagent", "project_slug": "-opt-alpha",
                             "session_id": "x-3", "paths": [str(old)], "pruned_at": "2026-10-20T00:00:00Z"}) + "\n")
    capsys.readouterr()
    assert pt.run(["--restore", "agent-twice"]) == 3
    err = capsys.readouterr().err
    assert "x-1/subagents/agent-twice.jsonl" in err and "x-2/subagents/agent-twice.jsonl" in err
    assert pt.run(["--restore", "agent-old"]) == 3
    assert "no sha256" in capsys.readouterr().err


# ── the unit file (C.2 unit ordering) ─────────────────────────────────────────────────────


def test_unit_file_runs_the_pruner_after_the_archiver_with_the_dash_prefix():
    lines = [
        ln.strip()
        for ln in (UNITS / "session-archive.service").read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith(("#", ";"))
    ]
    assert "Type=oneshot" in lines
    starts = [ln for ln in lines if ln.startswith("ExecStart=")]
    assert len(starts) == 3, "archiver, pruner, rotation mail (W-f975fee0 slice 3)"
    assert (
        starts[0]
        == "ExecStart=/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/archive_transcripts.py"
    )
    assert starts[1] == (
        "ExecStart=-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/prune_transcripts.py"
        " --apply --nightly"
    ), "Gate C passed 2026-10-12 (D-746): the unit applies"
    assert starts[2].startswith("ExecStart=-") and "rotate_session.py due" in starts[2]


# ── set-asides (W-a2cae11b): `<sid>.jsonl.superseded-<ms>`, Claude Code's name for a moved-aside transcript ──


def _set_aside(world: World, live: Path | None, slug: str, sid: str, ms: int, *, days: float = 10) -> Path:
    """A set-aside: a hard link of `live` (Claude Code's measured shape), or an inode of its own."""
    p = world.projects / slug / f"{sid}.jsonl.superseded-{ms}"
    p.parent.mkdir(parents=True, exist_ok=True)
    if live is not None:
        os.link(live, p)
    else:
        p.write_bytes(json.dumps({"sid": sid, "aside": ms}).encode() * 40 + b"\n")
        _age(p, days)
    return p


def test_pruning_a_live_name_also_unlinks_its_set_aside_links(world):
    """r7 over EVERY MAIN name of the inode: a set-aside link (one in a slug with no live name of the
    inode) is vouched through the live rows, unlinked in the same pass and named in the ledger row —
    so the blocks are freed, and `--restore` puts every name back."""
    live = world.projects / "-opt-alpha" / "a-old-10.jsonl"
    near = _set_aside(world, live, "-opt-alpha", "a-old-10", 1792094167189)
    far = _set_aside(world, live, "-opt-gamma", "a-old-10", 1792288372659)
    world.ready()
    verdict = world.evaluate()
    assert verdict["a-old-10"] is None, verdict  # not names-differ, not not-archived
    assert not any(k.startswith("a-old-10.superseded") for k in verdict), "one inode, one candidate"
    n = sum(1 for v in verdict.values() if v is None)
    assert _apply(n) == 0
    assert not live.exists() and not near.exists() and not far.exists(), "a set-aside pinned the inode"
    row = next(r for r in world.ledger() if r.get("session_id") == "a-old-10")
    assert set(row["paths"]) == {str(live), str(near), str(far)}
    assert pt.run(["--restore", "a-old-10"]) == 0
    assert live.exists() and near.exists() and far.exists()
    assert live.stat().st_ino == near.stat().st_ino == far.stat().st_ino


def test_a_set_aside_only_inode_is_archived_but_never_pruned(world):
    """No live name: session-recall indexes `*/*.jsonl` only, so an index row for this inode can only be
    a stale one — the inode is archived under its own key and refused, even with that row."""
    aside = _set_aside(world, None, "-opt-alpha", "a-gone", 1792029283292)
    world.ready()
    st = aside.stat()
    world.index.append((st.st_ino, st.st_size))  # a stale pre-rename row
    key = "a-gone.superseded-1792029283292"
    assert (world.archive / "-opt-alpha" / f"{key}.jsonl.zst").is_file()
    assert world.evaluate()[key] == "set-aside-only"
    assert _apply(sum(1 for v in world.evaluate().values() if v is None)) == 0
    assert aside.exists()


def test_a_fresh_set_aside_never_displaces_the_newest_live_session(world):
    """Claude Code refreshes a set-aside's mtime, so a set-aside-only inode is often the slug's newest
    file; counted by r3 it would unprotect the slug's real newest live session."""
    _set_aside(world, None, "-opt-beta", "b-older", 1792255742699, days=4)  # newer than b-old-05
    world.ready()
    v = world.evaluate()
    assert v["b-older.superseded-1792255742699"] == "set-aside-only"
    assert v["b-old-05"] == "newest-of-slug", v


def test_a_set_aside_in_a_slug_that_sorts_first_never_keys_its_live_inode(world, capsys):
    """Path order puts `-opt-alpha/<sid>.jsonl.superseded-*` before `-opt-alpha--wt/<sid>.jsonl`; the
    candidate must still key by the live name, or the inode is refused and pinned (review r1, O3).
    An off-grammar name the set-aside glob matches is skipped, never a crash (review r1, O4), and the
    over-threshold report counts the inode's live names, never its set-asides (review r1, O8)."""
    live = world.transcript("-opt-alpha--wt", "w-1", days=10)
    world.transcript("-opt-alpha--wt", "w-new", days=1)  # the slug's newest, so w-1 is not
    _set_aside(world, live, "-opt-alpha", "w-1", 1792029283292)
    (world.projects / "-opt-alpha" / "x-1.jsonl.superseded-abc").write_bytes(b"{}\n")
    world.ready()
    verdict = world.evaluate()
    assert verdict["w-1"] is None, verdict
    assert not any(k.startswith("w-1.superseded") for k in verdict)
    w = pt._world(None)
    w.advise_mb = 0  # every file is over the threshold
    _cands, _refusals, over = pt.evaluate_main(w)
    assert not any(".superseded-" in p for p in over), over
    assert str(live) in over


def test_restore_refuses_a_session_id_pruned_as_two_inodes_under_two_slugs(world, capsys):
    """A set-aside makes "two inodes, one session id" ordinary: restoring only the latest row would
    leave the other silently missing (review r1, O2) — refuse and list both, as `agent-` does."""
    for slug, body in (("-opt-eta", b'{"b":1}\n' * 30), ("-opt-eta--wt", b'{"a":1}\n' * 40)):
        world.transcript(slug, "e-1", days=10, body=body)
        world.transcript(slug, "e-newest", days=1)
    world.ready()
    cands, _refusals, _over = pt.evaluate_main(pt._world(None))  # two inodes share one id: count both
    assert _apply(sum(1 for c in cands if c.reason is None)) == 0
    gone = [world.projects / s / "e-1.jsonl" for s in ("-opt-eta", "-opt-eta--wt")]
    assert not any(p.exists() for p in gone)
    assert pt.run(["--restore", "e-1"]) == pt.EXIT_REFUSED
    err = capsys.readouterr().err
    assert "-opt-eta--wt" in err and "--slug=" in err, err
    assert not any(p.exists() for p in gone), "a refusal writes nothing"
    assert pt.run(["--restore", "e-1", "--slug=-opt-eta--wt"]) == 0  # the spelling the refusal names
    assert gone[1].exists() and not gone[0].exists()
