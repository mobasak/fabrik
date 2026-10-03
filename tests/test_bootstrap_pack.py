"""Pins `core/90-bootstrap-scripts.md` to the scripts it describes and to the rules its 2026-10-04 currency pass set.

The pack is glob-activated on the hub's own bootstrap scripts, templates and rebuild runbooks. What it states can go
false with no other gate red:

1. Its `currency_pass:` stamp, and globs that cover every file its CONSUMER line names.
2. The line references it cites into the scripts — the `EFFECTIVE_REMOTE` comment at `bootstrap-vps.sh` 139-142,
   the spoke-name regex at line 104, `liveness_audit.py` 10-11 — still say what the pack says they say.
3. The repo facts: every script disables root login with `PermitRootLogin no`; no script writes a fail2ban jail, so
   the pack's defaults are the package's; `--skip-dns` exists only in `bootstrap-vps.sh`; the spoke pre-creates its
   `/var/log` files.
4. The external facts: fail2ban's 5 failures in 10 minutes for 10 minutes; sshd's first-match drop-ins and
   `sshd -T`; Claude Code's native installer and the `sudo npm` warning; PEP 668; `command -v`; the console route.
5. No version number in any shape in the prose.

Guards read emphasis-stripped, whitespace-collapsed text and pin the clause that carries the force, so a reversed
verb fails. The cheapest way past (2) is to keep a line number that still lands on similar text; the guard reads the
cited line and asserts the specific token, so a shifted script fails it.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "core" / "90-bootstrap-scripts.md"
BOOT = ROOT / "scripts" / "bootstrap"
VPS, HUB, RESTORE = (BOOT / f"bootstrap-{n}.sh" for n in ("vps", "hub", "spoke-restore"))


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _rule(n: int) -> str:
    body = _pack().split(f"\n## Rule {n} ", 1)[1]
    return _plain(re.split(r"\n## ", body, maxsplit=1)[0])


def _has(text: str, *phrases: str) -> None:
    for phrase in phrases:
        assert phrase in text, f"lost: {phrase!r}"


def _line(path: Path, n: int) -> str:
    return path.read_text(encoding="utf-8").splitlines()[n - 1]


def test_stamp_and_globs() -> None:
    head = _pack().split("---", 2)[1]
    assert re.search(r"^currency_pass: \d{4}-\d{2}-\d{2}$", head, re.M), (
        "the pack lost its currency_pass stamp"
    )
    globs = re.search(r"^globs: \[(.*)\]$", head, re.M).group(1)
    consumer = _pack().split("<!-- CONSUMER:", 1)[1].split("GOAL:", 1)[0]
    named = re.findall(r"scripts/[\w./-]+\.(?:sh|template)", consumer)
    assert len(named) >= 5, f"the CONSUMER line names only {named}"
    patterns = [g.strip().strip('"') for g in globs.split(",")]
    for rel in named:
        assert (ROOT / rel).is_file(), f"the pack names {rel}, which does not exist"
        assert any(
            Path(rel).match(p)
            or re.fullmatch(p.replace("**/", "(.*/)?").replace("*", "[^/]*"), rel)
            for p in patterns
        ), f"no glob activates the pack for {rel}"


def test_cited_lines_still_say_it() -> None:
    _has(_rule(1), "the comment at lines 139–142")
    comment = " ".join(_line(VPS, n) for n in range(139, 143))
    assert "EFFECTIVE_REMOTE" in comment and "Step 00" in comment, "bootstrap-vps.sh 139-142 moved"
    _has(_rule(5), "Validation at bootstrap-vps.sh line 104")
    assert "^vps[0-9]+$" in _line(VPS, 104), (
        "bootstrap-vps.sh line 104 no longer holds the spoke-name regex"
    )
    _has(_rule(7), "scripts/sysadmin/liveness_audit.py:10-11")
    audit = ROOT / "scripts" / "sysadmin" / "liveness_audit.py"
    assert "/var/log" in _line(audit, 10) and "aborted before the script" in _line(audit, 11)


def test_repo_facts() -> None:
    for script in (VPS, HUB, RESTORE):
        assert "PermitRootLogin no" in script.read_text(encoding="utf-8"), (
            f"{script.name} no longer sets it"
        )
    for script in BOOT.rglob("*"):
        if script.is_file():
            text = script.read_text(encoding="utf-8", errors="ignore")
            assert not re.search(r"^\s*(maxretry|findtime|bantime)\s*=", text, re.M), (
                f"{script.name} now writes a fail2ban jail: the pack's package-default figures may be wrong"
            )
    assert "--skip-dns)" in VPS.read_text(encoding="utf-8")
    for script in (HUB, RESTORE):
        assert "--skip-dns" not in script.read_text(encoding="utf-8"), (
            f"{script.name} gained --skip-dns"
        )
    _has(
        _rule(4),
        "bootstrap-hub.sh and bootstrap-spoke-restore.sh accept --skip-mesh and --verify but have no --skip-dns",
    )
    assert re.search(
        r"touch[^\n]*/var/log/sysadmin-proactive\.log", VPS.read_text(encoding="utf-8")
    ), "bootstrap-vps.sh no longer pre-creates the sysadmin log the pack cites"


def test_fail2ban_and_lockout() -> None:
    _has(
        _rule(1),
        "ban after 5 failures within 10 minutes, for 10 minutes",
        "No bootstrap script writes a jail config",
    )
    _has(
        _rule(6),
        "Stop after the second failure",
        "sudo fail2ban-client set sshd unbanip",
        "need a password login",
        "Recovery Console",
    )
    assert "3 failures" not in _plain(_pack()), (
        "the pack states the old three-failure threshold again"
    )


def test_effective_sshd_config() -> None:
    s = _rule(1)
    _has(
        s,
        "sshd uses the first value it reads",
        "50-cloud-init.conf",
        "low-numbered drop-in",
        "sshd -T | grep -Ei",
        "sshd -t checks syntax only",
    )


def test_idempotency_and_installs() -> None:
    s = _rule(3)
    _has(
        s,
        "Probe with command -v",
        "not which",
        "curl -fsSL https://claude.ai/install.sh | bash",
        "must not be installed with sudo npm install -g",
        "about 512 MB of free memory",
        "externally managed (PEP 668)",
        "prefer an apt python3-… package, a venv, or pipx",
    )
    assert "==" not in s, "Rule 3 pins a package version again"


def test_cron_redirect() -> None:
    _has(
        _rule(7),
        "The shell opens the redirect before exec'ing the script",
        "journalctl -t CRON",
        "prove the redirect target",
    )


def test_no_version_literals() -> None:
    vre = importlib.util.spec_from_file_location("vision55", ROOT / "tests" / "test_vision_pack.py")
    mod = importlib.util.module_from_spec(vre)
    vre.loader.exec_module(mod)
    prose = re.sub(r"```.*?```", "", _pack().split("\n---\n", 1)[1], flags=re.S)
    found = mod.VERSION_RE.findall(re.sub(r"\b(?:Rule|PEP) \d+\b", "", _plain(prose)))
    assert not found, f"version literals in the pack: {found}"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/infrastructure/vps-spoke-rebuild.md",
        "docs/infrastructure/vps-hub-rebuild.md",
        "docs/infrastructure/vps-bootstrap-plan.md",
    ],
)
def test_runbooks_exist(rel: str) -> None:
    assert rel in _pack() and (ROOT / rel).is_file(), f"cross-reference {rel} is gone"
