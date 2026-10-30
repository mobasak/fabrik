#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_bat.py
"""agents_bat.py [--opt DIR] [--desktop DIR] [--distro NAME] [--replace FILE]... [--tabbed] — one "<Repo> Agents.bat"
per repo, or with --tabbed ONE "All Agents (tabbed).bat". Also: agents_bat.py --list [--opt DIR].

--list (W-6e656dac T04): prints the absolute path of every registered repo under --opt (a .fabrik/session-agents.json
registry or a .claude/worktrees folder), one per line, sorted, WITHOUT the `agents_up.sh --print` probe and with no
distro to resolve; it writes nothing. A folder that cannot be read, or whose name holds a newline, is skipped with a
stderr line and the rest are still listed (exit 0). The boot sweep (claude-reboot-sweep.sh) runs `agents_up.sh --detach` on each,
which decides the builders itself — the probe is left out because at boot the user bus may not answer yet.

--tabbed (W-b9ad80ae D5): one named Windows Terminal window (`wt.exe -M -w fabrik-agents`, so a later run can append to
it) with, per repo, a tab running `agents_up.sh /opt/<repo>` (attach-or-launch) and one tab per live tmux window named
`agents-<n>` (n >= 2) of the repo's session, running `agents_up.sh --window <n> /opt/<repo>`; any other window name is
ignored and a down session, a failed or timed-out (2 s) read gives the repo its first tab only; the session is named
from the repo's physical path, as agents_up.sh does. In BOTH modes the distro defaults to the Deck's resolver
(fabrik_deck.py `_default_distro`, once per run); --distro overrides and '' is refused. The slow `agents_up.sh
--print` per repo runs OUTSIDE the lock; under flock on ~/.config/fabrik/agents-desktop.lock (30 s at most, then exit
2) only the tmux window reads and the write happen. A run with --desktop D that wrote or found current any of its
file(s) remembers D's absolute path, whatever its exit code, in ~/.config/fabrik/agents-desktop; a --tabbed run
without --desktop writes there, or, when nothing is remembered or the folder is gone, prints with a stderr note (exit
0). Every write goes through a unique temp file and a rename.

For every repo directly under --opt (default /opt) whose grid `agents_up.sh --print <repo>` accepts — it exits 0 and
lists at least one pane — it makes the desktop launcher the operator double-clicks to open that repo's agents_up.sh
tmux grid (W-bb6c9d9a, D-1042). agents_up is the ONE authority on which builders a repo has (a registry, else its
whoami bindings, each in its own worktree; W-89474fc1), so this script never restates that rule; only a repo with a
registry or a .claude/worktrees folder is asked, since a grid needs a worktree. A generated .bat whose repo no longer
qualifies is reported on stderr, never deleted. By default it only prints each target and its text; it writes only
under an explicit --desktop, the operator-named location, because the desktop is outside every repo.

Each .bat is self-contained — no hand-made Windows Terminal profile. wt.exe has no font-size option, so the .bat
writes a WT JSON fragment (%LOCALAPPDATA%\\Microsoft\\Windows Terminal\\Fragments\\Fabrik\\<repo>.json) defining a
profile "<Repo> Agents grid" (its own name: a hand-made "<Repo> Agents" may still be in settings.json) at font size 9 — written to a temp file by one redirect-first block, then moved into place, so
WT never reads half of it. settings.json is never written by us; WT itself adds a `"source": "Fabrik"` stub there for a
fragment profile. Then `start "" wt.exe -M -w new new-tab -p ... wsl.exe --distribution <distro> --exec bash -l
<agents_up.sh> /opt/<repo>` — wt.exe takes everything from wsl.exe on as the tab's command line, so each word there
is a plain token (no space, quote or `;`, which wt would split on) that wt passes through unchanged, and the command
is explicit, so the grid opens even before WT has loaded the fragment (at the default font then).

An existing target is rewritten only when this script wrote it (its marker is the second line), left alone when
identical, and otherwise refused unless named by --replace (case-blind, like the desktop); a refusal, a target that
cannot be written, or a --replace naming no target leaves files untouched while the other targets are still written
(exit 2). Repo and distro names reach cmd, JSON and bash text and a Windows file name, so both must match
[A-Za-z0-9][A-Za-z0-9._-]*, not end in a dot and not be a Windows device name (con, nul, com1, ...), and two repos
whose names differ only by case are refused, since the desktop ignores case.

COBRA (D-253): the cheapest way to pass the tests is a .bat whose TEXT is right and that never opens a grid — no
Windows runner exists here. The counter is the runbook's acceptance check on the operator's machine (the grid opens
at 9pt with no banner or dialog), named there as the live proof.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AGENTS_UP = "/opt/fabrik/scripts/sysadmin/agents_up.sh"
MARKER = "rem generated by /opt/fabrik/scripts/sysadmin/agents_bat.py"
FONT_SIZE = 9
TABBED_NAME = "All Agents (tabbed).bat"
WINDOW = (
    "fabrik-agents"  # the NAMED wt window (never `-w new`), so a later run can append tabs to it
)
LOCK = "agents-desktop.lock"
REMEMBER = "agents-desktop"
LOCK_WAIT = 30.0  # seconds a run waits for the desktop lock
_CONFIRMED: list[
    Path
] = []  # the files this run wrote or found already current (what --desktop may remember)
TMUX_TIMEOUT = 2.0  # seconds per `tmux list-windows`, which runs under the lock: N repos hold it N * this at most
_WINDOW = re.compile(r"agents-([2-9]|[1-9][0-9]+)")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# Windows maps these to devices whatever the extension, so `con.json.tmp` is never a file
_DEVICES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{n}" for n in range(10)),
    *(f"lpt{n}" for n in range(10)),
}


def _safe(name: str) -> bool:
    """A name that reaches cmd, JSON and bash text and a Windows file name: a strict charset, no trailing dot
    (Windows strips it) and no device name."""
    return (
        bool(_NAME.fullmatch(name))
        and not name.endswith(".")
        and name.split(".")[0].lower() not in _DEVICES
    )


def bat_name(repo: str) -> str:
    return f"{repo[:1].upper()}{repo[1:]} Agents.bat"


def _titles(repo: str) -> tuple[str, str]:
    """(tab title, profile name) of a repo. The profile carries its own name: a hand-made profile called `title`
    may still exist in settings.json."""
    title = f"{repo[:1].upper()}{repo[1:]} Agents"
    return title, f"{title} grid"


def _command(distro: str, repo: str, *extra: str) -> str:
    return " ".join(
        [
            "wsl.exe",
            "--distribution",
            distro,
            "--exec",
            "bash",
            "-l",
            AGENTS_UP,
            *extra,
            f"/opt/{repo}",
        ]
    )


def _fragment_block(repo: str, title: str, profile: str, command: str) -> list[str]:
    """The cmd lines that write the repo's WT fragment (temp file, then move) — shared by both .bat modes."""
    fragment = json.dumps(
        {
            "profiles": [
                {
                    "name": profile,
                    "commandline": command,
                    "tabTitle": title,
                    "suppressApplicationTitle": True,
                    "font": {"size": FONT_SIZE},
                    "hidden": False,
                }
            ]
        },
        indent=2,
    ).splitlines()
    return [
        f'> "%FRAG%\\{repo}.json.tmp" (',
        *(f"  echo {ln}" for ln in fragment),
        ")",
        f'move /y "%FRAG%\\{repo}.json.tmp" "%FRAG%\\{repo}.json" >nul',
    ]


def bat_text(repo: str, distro: str) -> str:
    title, profile = _titles(repo)
    command = _command(distro, repo)
    lines = [
        "@echo off",
        MARKER,
        f"rem agents_up.sh takes the builders from /opt/{repo}'s registry or its whoami bindings - re-run it, never hand-edit this file.",
        f"rem {title} - the builders side by side in one tmux grid in WSL, each resuming its own session in its",
        "rem own worktree. The coordinator runs in VS Code. The font comes from a Windows Terminal fragment this file",
        "rem writes; it applies once every Windows Terminal window has been closed after the first run.",
        'set "FRAG=%LOCALAPPDATA%\\Microsoft\\Windows Terminal\\Fragments\\Fabrik"',
        'if not exist "%FRAG%\\" mkdir "%FRAG%"',
        *_fragment_block(repo, title, profile, command),
        f'start "" wt.exe -M -w new new-tab -p "{profile}" --title "{title}" --suppressApplicationTitle {command}',
    ]
    return "\r\n".join(lines) + "\r\n"


def tabbed_text(repos: list[str], windows: dict[str, list[int]], distro: str) -> str:
    """The one "All Agents (tabbed).bat": every repo's fragment block, then ONE named-window wt line — per repo its
    attach-or-launch tab, then a tab per overflow window n (`agents_up.sh --window n`)."""
    lines = [
        "@echo off",
        MARKER,
        "rem agents_up.sh decides each repo's builders and its overflow windows are read from tmux - re-run this",
        "rem script, never hand-edit this file. One Windows Terminal window named fabrik-agents holds every tab, so a",
        "rem later run can append to it. The fonts come from the Windows Terminal fragments this file writes.",
        'set "FRAG=%LOCALAPPDATA%\\Microsoft\\Windows Terminal\\Fragments\\Fabrik"',
        'if not exist "%FRAG%\\" mkdir "%FRAG%"',
    ]
    tabs: list[str] = []
    for repo in repos:
        title, profile = _titles(repo)
        lines += _fragment_block(repo, title, profile, _command(distro, repo))
        flags = f'-p "{profile}" --suppressApplicationTitle'
        tabs.append(f'new-tab {flags} --title "{title}" {_command(distro, repo)}')
        for n in windows.get(repo, []):
            tabs.append(
                f'new-tab {flags} --title "{title} {n}" {_command(distro, repo, "--window", str(n))}'
            )
    lines.append('start "" wt.exe -M -w ' + WINDOW + " " + " ; ".join(tabs))
    return "\r\n".join(lines) + "\r\n"


def _session(opt: str, repo: str) -> str:
    """The tmux session name agents_up.sh derives: the basename of the repo's PHYSICAL path (`pwd -P`, so a symlinked
    /opt entry names its target's session), [A-Za-z0-9_-] only (tmux reads `.`, `:` and globs in a target)."""
    return re.sub(
        r"[^A-Za-z0-9_-]", "-", os.path.basename(os.path.realpath(os.path.join(opt, repo)))
    )


def _windows(opt: str, repo: str) -> list[int]:
    """The overflow windows `agents-<n>` (n >= 2) of the repo's live session, numerically sorted. A down session, a
    failed or timed-out read, or an empty one yields [] (the repo's first tab only); any other window name —
    including one with surrounding spaces; only the line end is removed — is ignored."""
    try:
        out = subprocess.run(
            ["tmux", "list-windows", "-t", f"={_session(opt, repo)}", "-F", "#{window_name}"],
            capture_output=True,
            text=True,
            timeout=TMUX_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    found = {
        int(m.group(1))
        for ln in out.stdout.split("\n")
        if (m := _WINDOW.fullmatch(ln.removesuffix("\r")))
    }
    return sorted(found)


_deck: object = None


def _load_deck():
    """fabrik_deck.py loaded by path (its import is constants and stdlib only): the ONE distro resolver."""
    global _deck
    if _deck is None:
        spec = importlib.util.spec_from_file_location(
            "fabrik_deck_for_agents_bat", Path(__file__).with_name("fabrik_deck.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _deck = mod
    return _deck


def _config_dir() -> Path:
    return Path(os.path.expanduser("~/.config/fabrik"))


def _atomic_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def _remember(desk: Path) -> None:
    try:
        _config_dir().mkdir(parents=True, exist_ok=True)
        _atomic_text(_config_dir() / REMEMBER, os.path.abspath(desk) + "\n")
    except OSError as exc:  # a memory that cannot be kept never fails the run
        print(f"agents_bat: could not remember the desktop ({exc})", file=sys.stderr)


def _remembered() -> tuple[Path | None, str]:
    """(the remembered desktop, '') or (None, the reason it cannot be used)."""
    try:
        raw = (_config_dir() / REMEMBER).read_text(encoding="utf-8").strip()
    except OSError:
        return None, "no desktop remembered - run once with --desktop"
    if not raw or not Path(raw).is_dir():
        return None, f"the remembered desktop {raw} is not a folder - run once with --desktop"
    return Path(raw), ""


@contextlib.contextmanager
def _desktop_lock():
    """flock on ~/.config/fabrik/agents-desktop.lock, waiting at most LOCK_WAIT seconds; TimeoutError past it."""
    _config_dir().mkdir(parents=True, exist_ok=True)
    fd = os.open(_config_dir() / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + LOCK_WAIT
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError from None
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def _tabbed(args: argparse.Namespace, repos: list[str], distro: str, desk: Path | None) -> int:
    """C3: the slow `agents_up.sh --print` per repo already ran (repos); only the millisecond tmux reads and the
    write happen under the lock."""
    rc = 0
    safe = []
    for repo in repos:
        if _safe(repo):
            safe.append(repo)
        else:
            print(f"agents_bat: repo folder {repo!r} is not a safe name; skipped", file=sys.stderr)
            rc = 2
    if not safe:
        print("agents_bat: no repo has a grid; nothing written", file=sys.stderr)
        return rc
    replace = {n.lower() for n in args.replace}
    unmatched = replace - {TABBED_NAME.lower()}
    for name in sorted(unmatched):
        print(
            f"agents_bat: --replace {name!r} names no .bat this run writes; nothing replaced",
            file=sys.stderr,
        )
        rc = 2
    if desk is None:
        text = tabbed_text(safe, {r: _windows(args.opt, r) for r in safe}, distro)
        print(f"== {TABBED_NAME}\n{text.replace(chr(13), '')}")
        return rc
    target = desk / TABBED_NAME
    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(_desktop_lock())
        except TimeoutError:
            print(
                f"agents_bat: another run holds {_config_dir() / LOCK} for over {LOCK_WAIT:g} s; nothing written",
                file=sys.stderr,
            )
            return 2
        except OSError as exc:  # the lock/config path failed, not the desktop target
            print(
                f"agents_bat: cannot take the desktop lock {_config_dir() / LOCK}: {exc.strerror or exc}; nothing written",
                file=sys.stderr,
            )
            return 2
        try:
            text = tabbed_text(safe, {r: _windows(args.opt, r) for r in safe}, distro)
            rc = max(rc, _write(target, text, TABBED_NAME.lower() in replace))
        except OSError as exc:
            print(f"agents_bat: {target}: {exc.strerror or exc}; left as it is", file=sys.stderr)
            return 2
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument(
        "--opt", default="/opt", help="the folder whose repos are scanned (default: /opt)"
    )
    ap.add_argument("--desktop", help="write the .bat files here; without it nothing is written")
    ap.add_argument(
        "--distro",
        default=None,
        help="the WSL distro the .bat starts (default: the Deck's resolver; '' is refused)",
    )
    ap.add_argument(
        "--tabbed",
        action="store_true",
        help=f'write ONE "{TABBED_NAME}" (a tab per repo and per overflow tmux window) instead of a .bat per repo',
    )
    ap.add_argument(
        "--replace",
        action="append",
        default=[],
        help="a desktop file this script may overwrite although it did not write it (case-blind, repeatable)",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="print the absolute path of every registered repo, one per line, without asking agents_up.sh; writes nothing",
    )
    args = ap.parse_args(argv)
    if args.list:
        return _list(args)
    _CONFIRMED.clear()
    rc = _run(args)
    # only a run that wrote or confirmed its file(s) moves the remembered desktop, whatever its rc (T10 F13: one skipped
    # unsafe repo or an unmatched --replace exits 2 yet wrote the rest); a run that found no repo (a mistyped --opt)
    # and a refused one confirmed nothing, so they remember nothing
    if args.desktop and _CONFIRMED:
        _remember(Path(args.desktop))
    return rc


def _registered(opt: Path) -> list[Path]:
    """The repos directly under `opt` that agents_up could give a grid: a registry or a .claude/worktrees folder. A
    folder that cannot be read is skipped with a stderr line naming it (T04 F6): one unreadable child must never
    empty the whole list."""
    found = []
    for p in sorted(opt.iterdir()):
        try:
            if p.is_dir() and (
                (p / ".fabrik" / "session-agents.json").exists()
                or (p / ".claude" / "worktrees").is_dir()
            ):
                found.append(p)
        except OSError as exc:
            print(
                f"agents_bat: cannot read {p} ({exc.strerror or exc}); skipped", file=sys.stderr
            )
    return found


def _list(args: argparse.Namespace) -> int:
    """--list (W-6e656dac T04, Interface G): the boot sweep's repo list — every registered repo's absolute path,
    WITHOUT the `agents_up.sh --print` probe (at boot the user bus may not answer yet, and a probe that fails then
    would empty the list), no distro to resolve, nothing written. agents_up --detach decides the rest per repo."""
    if args.desktop or args.tabbed or args.replace:
        print(
            "agents_bat: --list is its own mode: it takes none of --desktop, --tabbed and --replace",
            file=sys.stderr,
        )
        return 2
    opt = Path(os.path.abspath(args.opt))
    if not opt.is_dir():
        print(f"agents_bat: --opt {args.opt} is not a folder; nothing listed", file=sys.stderr)
        return 2
    for repo in _registered(opt):
        # one path per line is the sweep's contract: a name holding a newline would print as two lines and the sweep
        # would launch a truncated path (T04 F3)
        if "\n" in str(repo):
            print(f"agents_bat: {str(repo)!r} holds a newline; skipped", file=sys.stderr)
            continue
        print(repo)
    return 0


def _run(args: argparse.Namespace) -> int:
    if args.distro is None:
        args.distro = _load_deck()._default_distro()  # once per run: its stderr note prints once
    if not _safe(args.distro or ""):
        print(
            f"agents_bat: distro {args.distro!r} is not a WSL distro name ([A-Za-z0-9][A-Za-z0-9._-]*)",
            file=sys.stderr,
        )
        return 2
    if not Path(args.opt).is_dir():
        print(f"agents_bat: --opt {args.opt} is not a folder; nothing written", file=sys.stderr)
        return 2
    desk = Path(args.desktop) if args.desktop else None
    if desk is not None and not desk.is_dir():
        print(f"agents_bat: --desktop {desk} is not a folder; nothing written", file=sys.stderr)
        return 2
    if desk is None and args.tabbed:
        desk, why = _remembered()
        if desk is None:
            print(f"agents_bat: {why}; printing instead", file=sys.stderr)

    repos = [p.name for p in _registered(Path(args.opt)) if _has_grid(p)]
    by_case: dict[str, list[str]] = {}
    for repo in repos:
        by_case.setdefault(bat_name(repo).lower(), []).append(repo)
    clash = [names for names in by_case.values() if len(names) > 1]
    if clash:
        print(
            f"agents_bat: these repos share one desktop file name: {clash}; nothing written",
            file=sys.stderr,
        )
        return 2
    if args.tabbed:
        return _tabbed(args, repos, args.distro, desk)

    rc = 0
    replace = {n.lower() for n in args.replace}
    unmatched = set(replace)
    for repo in repos:
        if not _safe(repo):
            print(f"agents_bat: repo folder {repo!r} is not a safe name; skipped", file=sys.stderr)
            rc = 2
            continue
        name, text = bat_name(repo), bat_text(repo, args.distro)
        # before print mode, so a dry run of the real command reads the same
        unmatched.discard(name.lower())
        if desk is None:
            print(f"== {name}\n{text.replace(chr(13), '')}")
            continue
        target = desk / name
        try:
            rc = max(rc, _write(target, text, name.lower() in replace))
        except OSError as exc:  # a folder or a locked file at the target: say so, keep going
            print(f"agents_bat: {target}: {exc.strerror or exc}; left as it is", file=sys.stderr)
            rc = 2
    for name in sorted(unmatched):
        print(
            f"agents_bat: --replace {name!r} names no .bat this run writes; nothing replaced",
            file=sys.stderr,
        )
        rc = 2
    if desk is not None:
        wanted = {bat_name(r).lower() for r in repos}
        for old in sorted(desk.glob("* Agents.bat")):
            if old.name.lower() in wanted:
                continue
            try:
                lines = old.read_bytes().split(b"\r\n")
            except OSError:
                continue
            if len(lines) > 1 and lines[1] == MARKER.encode("ascii"):
                print(
                    f"agents_bat: {old} was generated for a repo whose grid agents_up no longer accepts; "
                    "left in place (delete it by hand if that repo is gone)",
                    file=sys.stderr,
                )
    return rc


def _has_grid(repo: Path) -> bool:
    """agents_up.sh decides: `--print` exits 0 and names at least one pane. It launches nothing."""
    try:
        out = subprocess.run(
            ["bash", os.environ.get("AGENTS_UP_BIN", AGENTS_UP), "--print", str(repo)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        # never read as "no grid" in silence: the stale-.bat report below would then blame the repo
        print(
            f"agents_bat: could not ask agents_up.sh about {repo} ({exc}); no .bat for it this run",
            file=sys.stderr,
        )
        return False
    return out.returncode == 0 and any(ln.startswith("pane ") for ln in out.stdout.splitlines())


def _write(target: Path, text: str, replace: bool) -> int:
    """Write one .bat: left alone when identical, rewritten when its second line is this script's marker or the
    operator named it with --replace, refused otherwise. The write goes through a temp file and a rename, so a cut-off
    write never leaves a half file that the marker check would then misread."""
    data = text.encode("ascii")
    if target.exists() or target.is_symlink():
        old = target.read_bytes()
        if old == data:
            _CONFIRMED.append(target)
            print(f"agents_bat: {target} is current")
            return 0
        lines = old.split(b"\r\n")
        if not (len(lines) > 1 and lines[1] == MARKER.encode("ascii")) and not replace:
            print(
                f"agents_bat: {target} exists and was not written by this script; left untouched "
                f'(--replace "{target.name}" overwrites it)',
                file=sys.stderr,
            )
            return 2
    # a unique temp name (never `<name>.tmp`): two runs cannot write one temp file, and a stale one is not ours
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix="." + target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)  # mkstemp makes it 0600; the desktop file was always world-readable
        os.replace(tmp, target)
    except OSError:
        Path(tmp).unlink(
            missing_ok=True
        )  # a locked target never leaves a stray .tmp on the desktop
        raise
    _CONFIRMED.append(target)
    print(f"agents_bat: wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
