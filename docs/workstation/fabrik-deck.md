# Fabrik Deck — every repo's VS Code in one browser window

Box-local. Design: `docs/superpowers/specs/2026-10-21-fabrik-deck-design.md` (CONVERGED, D-1106). The operator's
ask: *"i want single vs code looking window for any repos to open any agents in it opened via claude vs code
extension"*. Each repo is a code-server (VS Code web) workbench in its own Vivaldi tab, tiled side by side or kept as
tabs, reached at `http://localhost:8443/?folder=/opt/<repo>` with no password.

This page grows with the Deck plan (the board, the attention hook, the profile, the launcher). Today it covers the
part built first: **code-server as a systemd user service** (W-e89a9b5b), because a hand-started code-server died with
the 2026-10-21 WSL restart and the operator lost every repo tab.

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
`mcp_orphan_reaper.py` (timed as its dry run, 149 ms mean, n=5) the `SessionEnd` pair stays near 225 ms of its shared
1.5 s budget; a real reap that finds orphans waits up to its `--grace` (5 s by default) between SIGTERM and SIGKILL, so
on such an exit the budget is the reaper's, not the hook's.

The hook prints nothing on stdout and exits 0 on every path — malformed input, an unknown argument, an unwritable state
dir — so it can never block a session.

## Rollback

`systemctl --user disable --now fabrik-deck-code`, delete `~/.config/systemd/user/fabrik-deck-code.service`,
`systemctl --user daemon-reload`; delete `~/.config/fabrik-deck/` if nothing else of the Deck uses it. Remove the
attention hook's registrations from every account dir's `settings.json` (after a backup) BEFORE reverting
`fabrik_deck.py`, or every session's registered `hook` call would reach an older script.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/fabrik_deck.py`
<!-- END related-scripts -->
