# Fabrik Deck — every repo's VS Code in one browser window

Box-local. Design: `docs/superpowers/specs/2026-10-21-fabrik-deck-design.md` (CONVERGED, D-1106). The operator's
ask: *"i want single vs code looking window for any repos to open any agents in it opened via claude vs code
extension"*. Each repo is a code-server (VS Code web) workbench in its own Vivaldi tab, tiled side by side or kept as
tabs, reached at `http://localhost:8443/?folder=/opt/<repo>` with no password.

This page grows with the Deck plan (the board, the attention hook, the profile, the launcher). Today it covers
**code-server as a systemd user service** (W-e89a9b5b), built first because a hand-started code-server died with the
2026-10-21 WSL restart and the operator lost every repo tab, then the **attention hook** and the **board** (W-42d1ccb5).

## code-server as a service

`fabrik-deck-code.service` is a systemd user unit. Linger is on for the operator's user (`loginctl show-user ozgur`
→ `Linger=yes`), so it starts when WSL boots, before any window opens, and systemd restarts it 10 s after a crash,
with no limit on restarts. Its log is the journal: `journalctl --user -u fabrik-deck-code`.

- **Unit:** `~/.config/systemd/user/fabrik-deck-code.service`, written by `scripts/sysadmin/fabrik_deck.py install`
  (its first line is a marker; the installer never overwrites a unit file without it).
- **Start:** `ExecStart=/usr/bin/python3 <hub>/scripts/sysadmin/fabrik_deck.py code-server`, which execs
  `~/.local/bin/code-server --bind-addr 127.0.0.1:<FABRIK_DECK_CODE_PORT>` with only these variables:
  `HOME`, `USER`, `LOGNAME`, `SHELL`, `PATH`, `LANG`, `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`,
  `CLAUDE_CONFIG_DIR`, `CLAUDE_QUOTA_HOME`, `FABRIK_DECK`. That keeps a starting session's own variables
  (`CLAUDE_AGENT`, its session id, its messaging token) out of every tab. code-server's extension host then loads the
  login shell's environment for its children, so node, nvm and anything `~/.profile` exports still reach the claude
  processes in the tabs. There is no ssh agent in Deck terminals (`SSH_AUTH_SOCK` is not kept).
- **Env file:** `~/.config/fabrik-deck/env` (named by its absolute path in the unit). `install` creates it; on a later
  run it keeps every line you wrote and only appends keys that are missing, naming them on stderr. To change the
  port, edit `FABRIK_DECK_CODE_PORT` there and restart the unit. The file is read the way systemd reads it: `#` and
`;` lines are comments, `KEY="value"` loses its quotes, and a line that is not plain `KEY=value` — `export KEY=…`
included — is ignored by systemd, so `install` ignores it too and says so.

| Key | Default |
|---|---|
| `FABRIK_DECK_CODE_PORT` | `8443` |
| `CLAUDE_CONFIG_DIR`, `CLAUDE_QUOTA_HOME` | `~/.claude-fleet/active` — every tab follows the box's account rotation |
| `PATH` | `~/.local/bin:/usr/local/bin:/usr/bin:/bin` |
| `FABRIK_DECK` | `1` — marks a session as a Deck tab |
| `DISPLAY`, `WAYLAND_DISPLAY` | `:0`, `wayland-0` |

A bare `http://localhost:8443/` opens code-server's last folder; the hand start used to pass one. Open repos with
`?folder=/opt/<repo>`.

## Install

```bash
python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py install           # write env file + unit, reload, enable
python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py install --start   # also start it now
```

Every check runs before the first write, so a refusal (exit 1) changes nothing: linger off; a `--hub` path holding a
space, `%`, `$`, `\` or a quote; the hub script or `~/.local/bin/code-server` missing; a foreign unit file in the way;
`systemd-analyze --user verify` printing anything; a port in the env file that does not parse; and with `--start`,
something already listening on the port. A failing `systemctl` after the files are written exits 1 and leaves them
in place. It ends by printing `systemctl --user is-enabled`.

`--hub DIR` (default `/opt/fabrik`) is the checkout the unit runs the script from. A plain re-run only reloads and
enables; a running unit keeps its old path until it restarts, so after changing `--hub` run
`systemctl --user restart fabrik-deck-code` (costing the open tabs' claude processes, as the cutover does).

The unit restarts a crashed code-server 10 s later, without limit. A failure at start — a port that does not parse, a
missing `code-server` binary — exits 2, and `RestartPreventExitStatus=2` stops the unit there instead of retrying
forever; fix the cause and `systemctl --user restart fabrik-deck-code`.

## Cutover from a hand start

Starting the unit while a hand-started code-server holds the port fails, so the hand process must stop first, and
stopping it kills the claude processes inside every open Deck tab (a turn in progress is lost; the tabs reconnect in
seconds and the chats resume from their history). So the cutover is deliberate:

1. **Default — at the next WSL restart.** `install` enables the unit; the hand start dies with WSL and the unit takes
   over at boot. Nothing is interrupted now.
2. **Now, at a quiet moment:** stop the hand start (`pkill -f 'code-server-4.141.0-linux-amd64/out/node/entry'` and
   its parent), then `install --start`.

The untracked `~/.local/bin/fabrik-deck-server` (the step-1 hand start, logging to
`~/.local/share/code-server-deck.log`) is superseded; delete it after the cutover.

## Proof

After a WSL restart (`wsl --shutdown`, or the next one the operator runs), with nobody starting anything by hand:
`systemctl --user is-active fabrik-deck-code` reads `active`, and from Windows `curl.exe -s -o NUL -w "%{http_code}"
http://localhost:8443/` prints `302`.

## Attention hook

`scripts/sysadmin/fabrik_deck.py hook` marks every session that waits on the operator, so the Deck board can show
which repo's agent needs an answer. It is registered user-level for `Notification`, `UserPromptSubmit`, `Stop`,
`PostToolUse` and `SessionEnd` by `install_user_hooks.py` (its row in `docs/workstation/hooks-index.md` names the full
contract), and keeps one file per waiting session, `<state>/attention/<session_id>.json` = `{cwd, type, origin, at}`.
The state dir is `FABRIK_DECK_STATE`, else the value in `~/.config/fabrik-deck/env`, else
`~/.local/state/fabrik-deck`; the hook reads the env file itself, because sessions outside the Deck never load it.

Cost, measured 2026-10-22 against a scratch state dir (20 runs each, `/usr/bin/python3`): `PostToolUse` with no file —
the path every tool call of every session takes — mean 47 ms, max 116 ms; `SessionEnd` mean 47 ms, max 64 ms. With
`mcp_orphan_reaper.py` (timed as its dry run, 149 ms mean, n=5) the `SessionEnd` pair stays near 225 ms of the 1.5 s
that SessionEnd hooks share (Claude Code hooks reference, https://code.claude.com/docs/en/hooks, fetched 2026-10-22); a
real reap that finds orphans waits up to its `--grace` (5 s by default) between SIGTERM and SIGKILL, so on such an exit
the budget is the reaper's, not the hook's.

Once the script loads, the hook prints nothing on stdout and exits 0 on every path — malformed input, an unknown
argument, an unwritable state dir, a closed stderr — so it cannot block a session. A MISSING script is the one
exception: `python3` itself exits 2, which blocks, so the registrations are removed before the script ever is (see
Rollback). A `FABRIK_DECK_STATE` that is relative after `~` expansion falls back to the default, so nothing is written
into a session's working directory.

## Board

`scripts/sysadmin/fabrik_deck.py serve [--registry PATH] [--opt-root DIR]` serves the board at
`http://localhost:<FABRIK_DECK_PORT>/` (default 8445; the registry defaults to `<hub>/data/projects.yaml`, the scan
root to `/opt`). One row per repo — the git repositories directly under `/opt`, named by their directory, then the
registry's other paths, named by their key; a path that no longer exists is dropped and a registry path that is not a
repository is listed with `git: false`. A row shows a dot and the waiting agent's name while a session there waits,
and its name links to `http://localhost:<FABRIK_DECK_CODE_PORT>/?folder=<path>` in a new tab. A session whose cwd is
under no repo shows in an `other` row. *Enable notifications* asks the browser once, then notifies on each new waiting
session.

The waiting session's repo is the catalog path that is the longest whole-component prefix of its cwd, so a worktree
under `<repo>/.claude/worktrees/` maps to `<repo>` and `/opt/fabrik-lib` never maps to `/opt/fabrik`; catalog paths
are resolved, so the cwd is matched both as written and resolved, and a repo reached through a symlink still maps. The
board matches a waiting session to its row by that path, never by name, so two rows sharing a name cannot share a dot. Its label is the
agent name from that repo's `.fabrik/session-agents.json` (read bounded at 1 MiB; a damaged file reads as no
agents), else `coordinator (<repo> tab)` for a Deck tab, `session <8 chars> (tmux)` for a tmux pane, `session <8
chars>` otherwise. Attention files older than 24 h — a session that died without `SessionEnd` — are deleted as they
are read, and so is one whose time is not a finite number; a file that does not parse is skipped.

Routes: `/`, `/api/repos`, `/api/attention`, `/api/events` (server-sent events: a frame on every change and every
2 s, carrying `{repos, attention}`, so a repo that appears while the board is open gets its row without a reload). The
catalog is rebuilt at most every 10 s. It binds 127.0.0.1 only, answers GET only — every other method, TRACE and
unknown verbs included, gets 405 with `Allow: GET` — and refuses any Host other than `localhost:<port>` or
`127.0.0.1:<port>` with 421, because a page reached by DNS rebinding would otherwise read the catalog. Every response,
the server's own error pages included, carries `Content-Security-Policy: frame-ancestors 'none'` and `Cache-Control:
no-store`, and closes its connection; an idle connection is dropped after 30 s. A bad port, a bound port or
an unreadable registry at startup exits 2. Until the Deck plan's Phase C installs it as a second unit, start it by
hand: `python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py serve`.

## Rollback

`systemctl --user disable --now fabrik-deck-code`, delete `~/.config/systemd/user/fabrik-deck-code.service`,
`systemctl --user daemon-reload`; delete `~/.config/fabrik-deck/` if nothing else of the Deck uses it. For the attention
hook, in this order: remove its `DECK_HOOK` rows from `install_user_hooks.py` `ENTRIES` (else the next install or
`--sync-shared` puts them back), then its registrations from every account dir's `settings.json` (after a backup), and
only then revert or delete `fabrik_deck.py` — a registered `hook` call reaching an older or missing script would exit 2
in every session.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/fabrik_deck.py`
- `scripts/sysadmin/install_user_hooks.py`
<!-- END related-scripts -->
