"""Behavior-contract tests for T03 (plan 2026-09-25-plan-1-work-store-single-tracker):
``mail.py``'s ``claim``/``ack``/``requeue`` CLI verbs create and close the linked
``kind: mail`` work item (spec § D2).

Every test runs against a throwaway git repo under ``tmp_path``, its own
``FABRIK_MAIL_ROOT``, and an explicit ``CLAUDE_CODE_SESSION_ID`` — never the hub's own
mailbox (``/opt/fabrik-mail``) or work store (``.fabrik/work/``). ``scripts/work.py`` is
never edited or monkeypatched at the function level — only ``mail.py``'s own module
cache (``_WORK``/``_WORK_ERR``) is touched, and only through ``monkeypatch`` (auto-restored).

mail.py and work.py are loaded by path (they live in scripts/, not an installed package).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_MAIL_PY = _SCRIPTS / "mail.py"
_WORK_PY = _SCRIPTS / "work.py"


def _load_mail():
    spec = importlib.util.spec_from_file_location("fabrik_mail_items_under_test", _MAIL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mail = _load_mail()


# --- repo + mailbox scaffolding ------------------------------------------------------


def _git_env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        }
    )
    return env


def _git(cwd: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    )


def _init_repo(base: Path, name: str, env: dict[str, str], *, with_store: bool = True) -> Path:
    """A throwaway git repo at ``base/<name>`` — its basename IS the mailbox name
    (``mail.py``'s ``_current_repo`` reads the main-checkout basename), one seed commit,
    and (unless ``with_store`` is False) a work store, given via the REAL CLI
    (``python3 scripts/work.py --repo <repo> init``) — never a hand-built store dir."""
    repo = base / name
    _git(base, env, "init", "-q", "-b", "main", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    if with_store:
        r = subprocess.run(
            [sys.executable, str(_WORK_PY), "--repo", str(repo), "init", "--distributor", "infra"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0, (r.stdout, r.stderr)
    return repo


def _plant(mail_root: Path, mailbox: str, mid: str, body: str, ack: str = "required") -> None:
    """Plant a message file directly in ``<mailbox>``'s inbox (frontmatter-level fixture,
    same shape as ``tests/test_mail.py``'s ``_mint``)."""
    inbox = mail_root / mailbox / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"id: {mid}",
        "from: alpha-sender",
        f"to: {mailbox}",
        "ts: 2026-09-25T10:00:00+00:00",
        "re: ",
        "kind: request",
        f"ack: {ack}",
        "hops: 0",
        "---",
        body,
    ]
    (inbox / f"{mid}.md").write_text("\n".join(lines), encoding="utf-8")


def _items(repo: Path) -> dict[str, dict]:
    d = repo / ".fabrik" / "work"
    if not d.is_dir():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("W-*.json"))}


def _mail_items(repo: Path) -> list[dict]:
    return [it for it in _items(repo).values() if it.get("kind") == "mail"]


def _claim_of(repo: Path, item_id: str) -> dict | None:
    """The item's live-claim record, read straight off disk (``<git common
    dir>/fabrik-work/claims/<id>.json``) — a throwaway repo's common dir is its own
    ``.git``, never the hub's."""
    common = Path(
        subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    )
    p = common / "fabrik-work" / "claims" / f"{item_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


@pytest.fixture
def alpha(tmp_path, monkeypatch):
    """A repo named ``alpha`` (its own mailbox) with a work store, chdir'd into, its own
    ``FABRIK_MAIL_ROOT``, and a live session — the CLI's-eye view of a real claim."""
    env = _git_env(tmp_path)
    repo = _init_repo(tmp_path, "alpha", env)
    mail_root = tmp_path / "mail"
    mail_root.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "S1")
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    return repo, mail_root


# --- row 1: claim opens one linked item, titled from the body, claimed by the session ------


def test_cli_claim_creates_one_open_mail_item_titled_from_the_body_and_claims_it(alpha):
    repo, mail_root = alpha
    mid = mail._ulid()
    _plant(mail_root, "alpha", mid, "Subject: fix the leaking pipe\nmore detail below\n")

    rc = mail.main(["claim", mid, "--repo", "alpha"])

    assert rc == 0
    items = _mail_items(repo)
    assert len(items) == 1, items
    item = items[0]
    assert item["links"]["mail"] == mid
    assert item["title"] == "fix the leaking pipe"
    assert item["status"] == "open"
    claim = _claim_of(repo, item["id"])
    assert claim is not None and claim["session"] == "S1", claim


# --- row 2: ack closes the item done with the disposition note; requeue closes dropped -----


def test_cli_ack_closes_done_with_the_disposition_and_requeue_closes_dropped(alpha):
    repo, mail_root = alpha
    mid1 = mail._ulid()
    _plant(mail_root, "alpha", mid1, "first message\n")
    assert mail.main(["claim", mid1, "--repo", "alpha"]) == 0
    assert mail.main(["ack", mid1, "--repo", "alpha", "--disposition", "done"]) == 0

    items = _mail_items(repo)
    assert len(items) == 1, items
    closed = items[0]
    assert closed["links"]["mail"] == mid1
    assert closed["status"] == "done"
    assert closed["note"] == "mail ack: done"

    # a fresh claim on a second message, then requeue it
    mid2 = mail._ulid()
    _plant(mail_root, "alpha", mid2, "second message\n")
    assert mail.main(["claim", mid2, "--repo", "alpha"]) == 0
    assert mail.main(["requeue", mid2, "--repo", "alpha"]) == 0

    items_by_mail = {it["links"]["mail"]: it for it in _mail_items(repo)}
    assert len(items_by_mail) == 2, items_by_mail
    dropped = items_by_mail[mid2]
    assert dropped["status"] == "dropped"
    assert dropped["note"] == "requeued"


# --- row 3: an ack with no prior CLI claim creates no item, and acks as before -------------


def test_cli_ack_without_a_prior_claim_creates_no_item_and_acks_normally(alpha):
    repo, mail_root = alpha
    mid = mail._ulid()
    _plant(mail_root, "alpha", mid, "never explicitly claimed\n")

    rc = mail.main(["ack", mid, "--repo", "alpha", "--disposition", "done"])

    assert rc == 0
    assert _mail_items(repo) == []
    archived = mail_root / "alpha" / "archive" / f"{mid}.md"
    assert archived.is_file()
    assert "disposition: done" in archived.read_text(encoding="utf-8")


# --- row 4: --repo naming ANOTHER repo's mailbox creates nothing in either store -----------


def test_cli_claim_with_repo_naming_another_mailbox_creates_no_item_anywhere(tmp_path, alpha):
    repo, mail_root = alpha  # cwd is "alpha"; _current_repo() == "alpha"
    env = _git_env(tmp_path)
    beta = _init_repo(tmp_path, "beta", env)  # a second repo, its OWN store
    mid = mail._ulid()
    _plant(mail_root, "beta", mid, "lives in beta's mailbox\n")

    rc = mail.main(["claim", mid, "--repo", "beta"])

    assert rc == 0  # the claim (mail-side) itself still succeeds
    claimed = mail_root / "beta" / "archive" / f"{mid}.md"
    assert claimed.is_file()
    assert _mail_items(repo) == [], "nothing in the calling session's own (alpha) store"
    assert _mail_items(beta) == [], "nothing in the named --repo's (beta) store either"


# --- row 5: no store, or work.py unavailable -> prints/exits as today, nothing created -----


def test_claim_ack_requeue_create_nothing_when_store_absent_or_work_unavailable(
    tmp_path, monkeypatch
):
    env = _git_env(tmp_path)

    # (a) a repo with NO store at all — has_store is False, work.py imports for real.
    bare = _init_repo(tmp_path, "gamma", env, with_store=False)
    mail_root = tmp_path / "mail"
    mail_root.mkdir()
    monkeypatch.chdir(bare)
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "S1")
    mid_a = mail._ulid()
    _plant(mail_root, "gamma", mid_a, "no store here\n")
    rc = mail.main(["claim", mid_a, "--repo", "gamma"])
    assert rc == 0
    claimed = mail_root / "gamma" / "archive" / f"{mid_a}.md"
    assert claimed.is_file()
    assert not (bare / ".fabrik" / "work").exists(), "no store is ever created implicitly"

    # (b) a repo WITH a store, but work.py fails to import — the CACHED-failure state
    # `_work()` leaves behind on a real import error (module-level cache, restored by
    # monkeypatch): claim/ack/requeue must still print/exit exactly as before and write
    # nothing, with one stderr line per call.
    stored = _init_repo(tmp_path, "delta", env, with_store=True)
    monkeypatch.chdir(stored)
    monkeypatch.setattr(mail, "_WORK", None)
    monkeypatch.setattr(mail, "_WORK_ERR", "simulated import failure for T03 row 5")
    mid_b = mail._ulid()
    _plant(mail_root, "delta", mid_b, "store exists, work.py does not import\n")

    rc = mail.main(["claim", mid_b, "--repo", "delta"])
    assert rc == 0
    assert (mail_root / "delta" / "archive" / f"{mid_b}.md").is_file()
    assert _mail_items(stored) == []

    rc = mail.main(["ack", mid_b, "--repo", "delta", "--disposition", "done"])
    assert rc == 0
    assert "disposition: done" in (mail_root / "delta" / "archive" / f"{mid_b}.md").read_text(
        encoding="utf-8"
    )
    assert _mail_items(stored) == []

    mid_c = mail._ulid()
    _plant(mail_root, "delta", mid_c, "a third message, for requeue\n")
    assert mail.main(["claim", mid_c, "--repo", "delta"]) == 0
    assert _mail_items(stored) == [], "claim() itself never creates a fallback item"
    rc = mail.main(["requeue", mid_c, "--repo", "delta"])
    assert rc == 0
    assert (mail_root / "delta" / "inbox" / f"{mid_c}.md").is_file()
    assert _mail_items(stored) == []
