# Fabrik Deck — every repo's VS Code in one browser window

Box-local. Design: `docs/superpowers/specs/2026-10-21-fabrik-deck-design.md` (CONVERGED, D-1106). The operator's
ask: *"i want single vs code looking window for any repos to open any agents in it opened via claude vs code
extension"*. Each repo is a code-server (VS Code web) workbench in its own Vivaldi tab, tiled side by side or kept as
tabs, reached at `http://localhost:8443/?folder=/opt/<repo>` with no password.

The pieces, each below: two systemd user services — **code-server** (`fabrik-deck-code.service`, W-e89a9b5b, built
first because a hand-started code-server died with the 2026-10-21 WSL restart and the operator lost every repo tab)
and the **board** (`fabrik-deck.service`) — the **attention hook** that feeds the board, the non-coding **profile**,
and the Desktop **launcher** (W-42d1ccb5).

## The two services

`fabrik-deck-code.service` runs code-server and `fabrik-deck.service` runs the board (`fabrik_deck.py serve`, § Board).
Both are systemd user units. Linger is on for the operator's user (`loginctl show-user ozgur` → `Linger=yes`), so they
start when WSL boots, before any window opens, and systemd restarts each 10 s after a crash, with no limit on
restarts. Their logs are the journal: `journalctl --user -u fabrik-deck-code` and `-u fabrik-deck`.

- **Units:** `~/.config/systemd/user/fabrik-deck-code.service` and `fabrik-deck.service`, written by
  `scripts/sysadmin/fabrik_deck.py install` (each first line is a marker; the installer never overwrites a unit file
  without it).
- **Start:** `ExecStart=/usr/bin/python3 <hub>/scripts/sysadmin/fabrik_deck.py code-server`, which execs
  `~/.local/bin/code-server --bind-addr 127.0.0.1:<FABRIK_DECK_CODE_PORT>` with only these variables:
  `HOME`, `USER`, `LOGNAME`, `SHELL`, `PATH`, `LANG`, `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`,
  `CLAUDE_CONFIG_DIR`, `CLAUDE_QUOTA_HOME`, `FABRIK_DECK`. That keeps a starting session's own variables
  (`CLAUDE_AGENT`, its session id, its messaging token) out of every tab. code-server's extension host then loads the
  login shell's environment for its children, so node, nvm and anything `~/.profile` exports still reach the claude
  processes in the tabs. There is no ssh agent in Deck terminals (`SSH_AUTH_SOCK` is not kept).
- **Env file:** `~/.config/fabrik-deck/env` (named by its absolute path in both units). `install` creates it; on a
  later run it keeps every line you wrote and only appends keys that are missing, naming them on stderr. To change a
  port, edit it there and restart both units (the board's repo links carry code-server's port), and for the
  code-server port re-run `install` too, which keeps `config.yaml`'s `bind-addr` in step. The hook and the launcher's `up` read the same file. The file is read the way systemd reads it: `#` and
`;` lines are comments, `KEY="value"` loses its quotes, and a line that is not plain `KEY=value` — `export KEY=…`
included — is ignored by systemd, so `install` ignores it too and says so.

| Key | Default |
|---|---|
| `FABRIK_DECK_CODE_PORT` | `8443` — code-server |
| `FABRIK_DECK_PORT` | `8445` — the board |
| `FABRIK_DECK_STATE` | `<home>/.local/state/fabrik-deck` — absolute, as systemd does not expand `~`; the attention files live in `attention/` under it |
| `CLAUDE_CONFIG_DIR`, `CLAUDE_QUOTA_HOME` | `~/.claude-fleet/active` — every tab follows the box's account rotation |
| `PATH` | `~/.local/bin:/usr/local/bin:/usr/bin:/bin` |
| `FABRIK_DECK` | `1` — marks a session as a Deck tab |
| `DISPLAY`, `WAYLAND_DISPLAY` | `:0`, `wayland-0` |

A bare `http://localhost:8443/` opens code-server's last folder; the hand start used to pass one. Open repos with
`?folder=/opt/<repo>`.

## Install

```bash
DESK="/mnt/c/Users/user/OneDrive - Tojlo Solutions LLC/Desktop"
python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py install --desktop "$DESK"   # env file, config.yaml, profile, both units, the .bat; enable
python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py install --start             # also start the units now
```

`install` writes, in order: the env file (missing keys only); `~/.config/code-server/config.yaml` — when it exists
and a line would change, after a copy to `~/.local/share/code-server/User/backups/config.yaml.<timestamp>` (a `-<n>`
suffix when that name is taken) — `bind-addr: 127.0.0.1:<FABRIK_DECK_CODE_PORT>`,
`auth: none`, `cert: false`, every other line (a `password:` line included) kept, a new file mode 0600 and an existing
one's mode kept; the profile (§ Profile; a file that already holds the Deck's values is left as it is, with no new
backup); both units; then `daemon-reload` and `enable`, `start` with `--start`; with `--desktop` the launcher (§ Launcher) and
the `is-enabled` lines; and LAST, the one root-level step, the box's `/tmp` boot-wipe override (§ Troubleshooting):
`/etc/tmpfiles.d/tmp.conf` = `d /tmp 1777 root root 30d`, written with `sudo -n install -D -m 0644` only while
`systemd-tmpfiles --cat-config` still carries a line that wipes `/tmp`'s contents as a whole at boot — `D` or `R` on
`/tmp` or on `/`, `r`/`R` on a glob every direct child matches such as `/tmp/*` (read as systemd reads it — quotes, C
escapes, `%T`, `/tmp/`, `..`); the stock lines clearing one named entry under `/tmp` are not wipes — then re-read to
prove no such line is left. A refused `sudo` (no passwordless sudo, no tty — `-n` never
prompts, since a headless pane would hang on it) exits 1 with the Deck fully installed and the one line to run by
hand; a wipe line another drop-in still carries after the write exits 1 the same way, naming that file and its line
(with our file already in effect beside such a line, the refusal comes before any write instead — next paragraph).

Every check runs before the first write, so a refusal (exit 1) changes nothing — the root-level `/tmp` step above is
the one exception, last and with the Deck installed: `systemd-analyze` or
`systemd-tmpfiles` not installed; `systemd-tmpfiles --cat-config` failing, or showing a wipe line (`D`/`R` on `/tmp` or
`/`, `r`/`R` on `/tmp/*`) in effect while a file at `/etc/tmpfiles.d/tmp.conf` is in effect (anyone's, or this
script's hand-edited — the refusal names the files carrying those lines); `sudo` not installed while such a line is in
effect;
linger off; a `--hub` path (resolved first) that holds anything but letters, digits and `/ . _ -` (the units and the `.bat` carry it unquoted); the
hub script or `~/.local/bin/code-server` missing; a foreign unit file at either path; `systemd-analyze --user verify`
printing anything for either unit; a port in the env file that does not parse, or the two ports equal; an env file
that is not UTF-8; a `config.yaml` that cannot be read; a settings.json that is not a plain JSON object (an empty one
counts as no settings); a backup that cannot be written; with `--desktop`, a desktop that is not a directory, a
`Fabrik Deck.bat` this script did not write, a missing distro (no `--distro`, `$WSL_DISTRO_NAME` unset or blank, and `wslpath -w /` naming none), or a
distro or browser value `cmd` would split; and with `--start`, something listening on the port of a unit that is not
active (an active unit holds its own port, so it is not refused). A failing `systemctl` after the files are written
exits 1 and leaves them in place. It ends by printing `systemctl --user is-enabled` for each unit.

`--hub DIR` (default `/opt/fabrik`) is the checkout the units run the script from. A plain re-run only reloads and
enables; a running unit keeps its old path until it restarts, so after changing `--hub` run
`systemctl --user restart fabrik-deck-code fabrik-deck` (costing the open tabs' claude processes, as the cutover does).

A unit restarts its crashed process 10 s later, without limit. A failure at start — a port that does not parse, a
missing `code-server` binary, an unreadable registry — exits 2, and `RestartPreventExitStatus=2` stops the unit there
instead of retrying forever; fix the cause and restart it.

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
`systemctl --user is-active fabrik-deck-code fabrik-deck` reads `active` twice, and from Windows
`curl.exe -s -o NUL -w "%{http_code}" http://localhost:8443/` prints `302` and the same for `:8445/` prints `200`.

## Attention hook

`scripts/sysadmin/fabrik_deck.py hook` marks every session that waits on the operator, so the Deck board can show
which repo's agent needs an answer. It is registered user-level for `Notification`, `UserPromptSubmit`, `Stop`,
`PostToolUse` and `SessionEnd` by `install_user_hooks.py` (its row in `docs/workstation/hooks-index.md` names the full
contract), and keeps one file per waiting session, `<state>/attention/<session_id>.json` = `{cwd, type, origin, at}`.
A `Notification` of type `permission_prompt`, `idle_prompt` or `elicitation_dialog` writes it, and `Stop` writes it as
`turn_ended`; `UserPromptSubmit` and `SessionEnd` delete it, and `PostToolUse` deletes it only after a
`permission_prompt`. `origin` is `tmux` in a tmux pane, else `deck` when `FABRIK_DECK=1`, else `other`.
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
repository is listed with `git: false` (a registry path must be absolute; one that resolves to a repo already
listed is dropped). Rows are sorted by name, case-insensitively, and a *Filter repos* box narrows them by name or
path. A row shows its path, and a dot and the waiting agent's name while a session there waits, and its name links to `http://localhost:<FABRIK_DECK_CODE_PORT>/?folder=<path>` in a new tab. A session whose cwd is
under no repo shows in an `other` row (hidden by a filter that does not match `other`). *Enable notifications* asks
the browser once; after permission is granted it notifies on each session that starts waiting while the page is open.

The waiting session's repo is the catalog path that is the longest whole-component prefix of its cwd, so a worktree
under `<repo>/.claude/worktrees/` maps to `<repo>` and `/opt/fabrik-lib` never maps to `/opt/fabrik`; catalog paths
are resolved, so an absolute cwd is matched both as written and resolved, and a repo reached through a symlink still
maps; a relative cwd is never resolved (it would resolve against the server's own directory). The
board matches a waiting session to its row by that path, never by name, so two rows sharing a name cannot share a dot. Its label is the
agent name from that repo's `.fabrik/session-agents.json` (read bounded at 1 MiB; a damaged file reads as no
agents), else `coordinator (<repo> tab)` for a Deck tab, `session <8 chars> (tmux)` for a tmux pane, `session <8
chars>` otherwise. Attention files older than 24 h — a session that died without `SessionEnd` — are deleted as they
are read, and so is one whose time is not a finite number or lies more than an hour ahead; a file that does not parse
is skipped.

Routes: `/`, `/api/repos`, `/api/attention`, `/api/events` (server-sent events: a frame on every change and every
2 s, carrying `{repos, attention}`, so a repo that appears while the board is open gets its row without a reload). The
catalog is rebuilt at most every 10 s. It binds 127.0.0.1 only, answers GET only — every other method, TRACE and
unknown verbs included, gets 405 with `Allow: GET` — and refuses any Host other than `localhost:<port>` or
`127.0.0.1:<port>` with 421, because a page reached by DNS rebinding would otherwise read the catalog. Every response,
the server's own error pages included, carries `Content-Security-Policy: frame-ancestors 'none'` and `Cache-Control:
no-store`, and closes its connection; an idle connection is dropped after 30 s. A bad port, a bound port or
an unreadable registry at startup exits 2. It runs as `fabrik-deck.service`; by hand it is
`python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py serve`.

## Profile

`fabrik_deck.py profile` (and `install`) copies `~/.local/share/code-server/User/settings.json` to
`…/User/backups/settings.json.<timestamp>` (only when the file exists and a key would change) and merges these keys
into it; for these keys the Deck's value wins and every
other key stays as it is: `workbench.colorTheme: "Dark 2026"` (the desktop VS Code theme), `window.autoDetectColorScheme:
false`, `claudeCode.preferredLocation: "panel"`, `editor.minimap.enabled: false`, `breadcrumbs.enabled: false`,
`workbench.startupEditor: "none"`, `workbench.activityBar.location: "top"` (Source Control stays one click away),
`workbench.statusBar.visible: true`, `workbench.editor.showTabs: "single"`. A settings.json that is not a plain JSON
object — code-server also accepts comments and trailing commas, which a rewrite would lose — is left untouched and the
run exits 1 naming it; remove the comments, or set the keys by hand.

## Launcher

`fabrik_deck.py launcher --desktop DIR [--distro D] [--browser PATH]` (and `install --desktop`) writes
`DIR/Fabrik Deck.bat` — the operator's desktop is `/mnt/c/Users/user/OneDrive - Tojlo Solutions LLC/Desktop`
(`docs/reference/repo-coordinator-rollout.md`). `--distro` defaults to a non-blank `$WSL_DISTRO_NAME`, else the distro the script runs in (`wslpath -w /`, which needs no
environment — a code-server, tmux or unit shell has no `$WSL_DISTRO_NAME`; never the Windows default distro, which can
be another one), `--browser` to
`C:\Users\user\AppData\Local\Vivaldi\Application\vivaldi.exe` (it must be a Windows path to an `.exe`), `--hub` to
`/opt/fabrik` (letters, digits and `/ . _ -` only). A double-click:

1. runs `wsl.exe --distribution <D> --exec /usr/bin/python3 /opt/fabrik/scripts/sysadmin/fabrik_deck.py up`, which
   exports `XDG_RUNTIME_DIR` when the user bus is there (a `.bat` carries none), starts each unit that is not active
   and whose port is free — a port held by another process (a hand-started code-server) is named and that unit left
   stopped — and prints the board port. It prints none, and exits 1, when another process holds the board's own
   port; with no user bus it prints the port, starts nothing, says so and exits 1; a failed start or a missing
   `systemctl` also exits 1 with the port printed;
2. waits for `http://localhost:<port>/` to answer `200` from Windows — 30 tries, 1 s apart, each `curl.exe` try
   bounded at 2 s, so 30 s to about 90 s — else says so and pauses;
3. the first time, opens the board (in a new tab when the browser is already running) and writes
   `Fabrik Deck.first-run` beside the `.bat`; after that, when the browser is already running it stops there (a second
   launch opens no window), and otherwise starts it with no URL, so Vivaldi's session restore brings back the board
   and the repo tabs.

The file is ASCII with CRLF line ends and its second line is a marker; a `Fabrik Deck.bat` without the marker is never
overwritten (exit 2). One-time clicks in Vivaldi (Settings → Startup): start with the last session, and set the home
page to `http://localhost:8445/`, so a closed board tab is one Home click away.

## Accepted exposure: auth none

`auth: none` is the operator's ruling ("no it should not bound password", D-1106): any local process — any Windows
process through localhost forwarding, and any page open in the browser that links to it — can drive a full VS Code with
a terminal as the operator's user. Both servers bind `127.0.0.1` only; the board is read-only (GET only, a Host check,
`frame-ancestors 'none'`). Nothing in this setup listens on another address.

## Acceptance

The spec's open unknowns need the operator's hands and a reboot. Each row is a step and what to record here after it.
The operator agreed to run them (D-1128) once the branch is merged and `install` and `up` have run, and the coordinator
says when: step 0 comes first, because `wsl --shutdown` and a Windows reboot end every session.

| # | Step | Record |
|---|---|---|
| 0 | The coordinator pauses every repo's agents the `/hibernate` way (each commits, pushes and parks its run) | that every agent reported parked, before step 1 starts |
| 1 | Open 3 repo tabs from the board, tile 2 of them, close Vivaldi, reopen it | whether the board, the 3 tabs and the tiling all return |
| 2 | Tile and untile a repo tab mid-chat; leave one tab and the board in the background past Vivaldi's hibernation delay; make a session wait | whether a chat view reloads, and whether the browser notification fires |
| 3 | `wsl --shutdown`, then a Windows reboot; after each, from Windows `curl.exe -s -o NUL -w "%{http_code}" http://localhost:8443/` and `:8445/` | the codes; if forwarding fails, which fallback worked (restart WSL; reaching the NAT address would need the servers bound there, an exposure change put to the operator first) |
| 4 | Double-click the `.bat` with Vivaldi open; close the board tab and press Home | whether a new window opened (expected: none) and whether Home brings the board back |
| 5 | Open 6 repo tabs | code-server's RSS (`ps -o rss= -C node` summed) and Vivaldi's memory (Task Manager), per tab |

## Troubleshooting

**After a WSL restart: "Failed to start the systemd user session for 'ozgur'", no code-server on 8443, no docker,
`systemctl` says "Failed to connect to bus".** Measured 2026-10-31 11:01-11:10 (D-1389, W-0c208792). Ubuntu's stock
`/usr/lib/tmpfiles.d/tmp.conf` says `D /tmp 1777 root root 30d`, and `D` means "delete the contents at boot". With
~119 GB of agent scratch under `/tmp/claude-1000` (the janitor could not reach it, W-d1a4a8f5), `systemd-tmpfiles
--create --remove --boot` (a sysinit dependency) deleted at ~2.4 GB/min and held the whole boot for 9 minutes: PID 1 was
systemd, but logind, the user manager, docker and the two Deck units never started, so WSL reported no user session
and Vivaldi found no code-server. The daily 30-day age cleanup is a separate timer and was never the problem.

- **Diagnose:** `ps --ppid 1` shows `systemd-tmpfiles … --remove --boot` in state R for minutes; `df` used falls while
  it runs; `sudo systemctl list-jobs` works (the private socket) when the user bus does not.
- **Unblock now:** `sudo kill <that pid>`, then `sudo systemd-tmpfiles --create --boot --exclude-prefix=/dev`; the boot
  continues (the setup unit shows failed/signal, harmless), and `systemctl --user is-active fabrik-deck-code
  fabrik-deck` reads `active` twice within a minute.
- **Permanent:** `/etc/tmpfiles.d/tmp.conf` = `d /tmp 1777 root root 30d` shadows the stock line by file name, so
  `systemd-tmpfiles --cat-config | grep -v '^#' | grep ' /tmp '` shows ONE line, lowercase `d`: the age cleanup
  stays, only the boot-time wipe goes. Measured on this box (systemd 255, `--remove --boot` over a staged `--root`): a
  `D /tmp` line in ANY drop-in wipes, whatever other `/tmp` lines exist, so a differently named file cannot turn it
  off — only the same-named shadow, an empty or `/dev/null` file at that name, or deleting the stock line does. The
  stock lines that clear one named entry under `/tmp` at boot (`D! /tmp/.X11-unix`, `D! /tmp/snap-private-tmp`,
  `R! /tmp/systemd-private-*`) are not the wipe and stay. `fabrik_deck.py install` writes the shadow (§ Install) so a
  fresh box inherits it, and refuses while another file still carries a wipe line; the cost is that `/tmp` grows until
  the janitor or the 30-day rule takes it.
- **Also found then, unrelated to the wipe:** `C:\Users\user\.wslconfig` carried three keys WSL 2.7.10 does not know
  (`natNetwork`, `natGatewayIpAddress`, `natIpAddress`, the 2026-09-23 NAT pin that never took) and printed "Unknown
  key" for each at every start. They were removed (backup `.wslconfig.backup.20261031-111031`); networking is unchanged
  because WSL had ignored them all along.

## Rollback

`sudo rm /etc/tmpfiles.d/tmp.conf` restores the stock boot-time `/tmp` wipe (only if you want it back; the Deck's
survival of a restart depends on the wipe staying off while `/tmp/claude-1000` is large — and the next `install`
writes the shadow again; to keep the wipe off without the age rule, `sudo ln -s /dev/null /etc/tmpfiles.d/tmp.conf`
masks the stock line and `install` leaves it alone).
`systemctl --user disable --now fabrik-deck-code fabrik-deck`, delete both unit files from
`~/.config/systemd/user/`, `systemctl --user daemon-reload`; delete `Fabrik Deck.bat` and `Fabrik Deck.first-run` from
the desktop; restore `config.yaml` and `settings.json` from `~/.local/share/code-server/User/backups/` (or delete
`~/.local/share/code-server`); delete `~/.config/fabrik-deck/` and `~/.local/state/fabrik-deck/`. For the attention
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
