# Fabrik Deck — a non-coding VS Code for many repos, in one browser window

Status: DRAFT
Work item: W-42d1ccb5 (owner fleet) · related: W-ea993618 (the tab router, agent picking inside a pane — separate,
queued) · W-a02d1c86 (every existing and new repo Deck-ready: scaffolder + rollout — separate, after this spec) ·
rulings: D-1092 (coordinator in the Claude extension GUI, builders in tmux, no fixed count), D-1072 (WSL NAT: Windows
reaches WSL only at its address — superseded for this service by the measured localhost forwarding below).

## Personas

| Persona | Who | Duties held in this design |
|---|---|---|
| **Primary — the operator** | The box's one human. In their words: *"it will be like non coding version of vs code, vibe coding ide using vs code's claude extension for multiple repos."* and *"i want single vs code looking window for any repos to open any agents in it opened via claude vs code extension"* | Opens the Deck, opens repos, tiles them, answers agents |
| Each repo's **coordinator** (an AI agent, D-874) | The agent the operator talks to per repo, in the Claude extension's chat (D-1092) | Runs in its repo's code-server workbench; its hook events feed the board |
| **Builders** (AI agents in tmux, D-1092) | Per-repo worker sessions | Not opened as Deck tabs; their waiting state still shows on the board, labelled by agent name, so the operator knows to go to tmux |
| **fleet** (this agent) | Box-local tooling owner | Builds and maintains the Deck server, board, hook, profile, launcher, doc |
| **infra** | Owner of `.claude/hooks/`, `install_user_hooks.py` and `hooks-index.md` (beat: hooks) | Reviews the `ENTRIES` rows and the hooks-index row the attention hook needs |
| The **Claude Code hook runtime** (automated) | Fires `Notification` / `UserPromptSubmit` / `Stop` in every session on the box, extension and tmux alike | Runs the hook that writes and clears the per-session attention files the board reads |
| The **launcher** (automated, a Windows `.bat`) | Runs on the operator's double-click | Starts the two servers if they are not answering, then opens the browser |

**The primary's loop, counted — the STEP BUDGET (5):** (1) double-click *Fabrik Deck* on the Windows desktop →
(2) Vivaldi opens with the board tab and the repo tabs from last time → (3) click a repo on the board (a dot marks a
repo whose agent waits; the link opens that repo in a new tab) → (4) type to that repo's coordinator in its Claude
panel → (5) select two or more tabs and Tile them (drag a tab into the page, or right-click → Tile) to watch repos
side by side.

Every feature below traces to this persona's quoted asks (I-rows in the Intake Inventory).

## Goal

One browser window that looks and behaves like VS Code — each repo a full code-server (VS Code web) workspace with the
real Claude Code extension, tiled side by side or kept as tabs — dark, with no password, at an address that never
changes, and a board that says which repo's agent is waiting on the operator.

## Why this exists

The official Claude extension scopes a window's chat tabs and history to that window's first folder (measured under
W-ea993618), so today the operator needs one VS Code window per repo, and the coordinators the operator talks to
(D-1092) are spread across windows. The Deck puts every repo's coordinator in one browser window. The step-1 proof
(2026-10-21, operator: *"yes i can see youtube agents in it"*) showed the core works: code-server + the Claude
extension, reached from the Windows browser at `http://localhost:8443`. What is missing is the window arrangement, the
attention signal, the repo list, the profile, the launcher and the doc.

**Where the agents run (executed 2026-10-21):** the extension's `claude` process is a child of code-server's
extension host in WSL (`ps`: `…/anthropic.claude-code-2.1.306-linux-x64/resources/native-binary/claude` under a
`bootstrap-fork` child of the code-server process), not in the browser. A hidden or background tab therefore never
pauses an agent; the browser only renders. That is the property behind "hidden tabs keep running" (I3).

## Intake Inventory

| I# | Item (anchored, operator's words unless marked) | Disposition | Where |
|---|---|---|---|
| I1 | "non coding version of vs code, vibe coding ide using vs code's claude extension for multiple repos" | IN | Goal, Chosen approach |
| I2 | "single vs code looking window for any repos to open any agents in it" | IN | Chosen approach (one Vivaldi window, repo tabs) |
| I3 | "i can have multiple tabs, also i can see some side by side or some as tabbed (not seen)" | IN | Vivaldi tab tiling; agents run server-side (Why this exists) |
| I4 | "no it should not bound password" | IN | code-server auth none (live); accepted risk under Constraints |
| I5 | "our ip is dynamic not static" | IN | localhost forwarding (measured) — no address in any config |
| I6 | "i want same theme as like i use in vs code here, not white" | IN | Profile: pins "Dark 2026", the desktop VS Code default (live in settings.json) |
| I7 | coordinator: attention badge when a pane's agent waits | IN | Attention hook + board |
| I8 | coordinator: layout remembered across reloads | IN | Vivaldi session restore (Open unknowns row 2 verifies) |
| I9 | coordinator: repo/agent list from the registries | IN | Repo catalog (`data/projects.yaml` + `/opt` + `session-agents.json`) |
| I10 | coordinator: non-coding profile (minimal chrome, Claude panel primary, git view kept, dark) | IN | Profile |
| I11 | coordinator: Desktop .bat launcher (starts the servers if needed, opens the Deck) | IN | Launcher |
| I12 | coordinator: box doc under docs/workstation/ with rollback | IN | Documentation landing sites |
| I13 | coordinator: the router (agent picking inside a pane) | OUT-OF-SCOPE | W-ea993618 (queued item) |
| I14 | operator earlier: "i want exact look and feel with vs code" | IN | It IS VS Code (code-server) inside each tab |
| I15 | coordinator: keep the router usable inside a code-server pane | OUT-OF-SCOPE | W-ea993618 sets `claudeCode.claudeProcessWrapper` when it ships; this spec sets nothing for it |
| I16 | coordinator (relayed): "Vivaldi tiles any number of tabs natively … weigh it, do not assume" | IN | Chosen approach (weighed against the dockview shell; Rejected alternatives) |
| I17 | operator (relayed): "now all existing and new repos will support this setup ? if not they should." | IN (registry read) · OUT-OF-SCOPE (rollout) | Repo catalog reads every repo with a plain-session fallback; the scaffolder + rollout runbook is W-a02d1c86 |

Intake: 17 items — 14 IN, 2 OUT-OF-SCOPE, 1 split (IN for the registry read, OUT-OF-SCOPE for the rollout), 0 ASK.

## Constraints Digest

| Quote | Source |
|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` |
| Testing Trophy model: integration and E2E tests are the primary source of truth. | `.windsurf/rules/core/45-testing-strategy.md:19` |
| No cosmetic assertions: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Source, config, or Docker file changed | `.windsurf/rules/core/40-documentation.md:67` |

(12-Factor axes applied as design constraints: III — every port and path the Deck reads comes from env or a flag with
a default; XI — both servers write to stdout, held by a tmux pane, never a logfile; VIII — no daemonizing, no PID
files: the servers run in the foreground of a tmux window.)

## Chosen approach — browser tiling + a Deck board

Four pieces, all box-local, in WSL as the operator's user unless marked:

1. **code-server** (installed, live since step 1): `~/.local/lib/code-server-4.141.0-linux-amd64`, config
   `~/.config/code-server/config.yaml` = `bind-addr: 127.0.0.1:8443`, `auth: none`, `cert: false`. Started with a
   CLEAN environment (`env -i` keeping only `HOME`, `USER`, `LOGNAME`, `SHELL`, `PATH`, `LANG`, `DISPLAY`,
   `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `CLAUDE_CONFIG_DIR` and `CLAUDE_QUOTA_HOME`) — measured 2026-10-21: a start from inside a Claude session leaked `CLAUDE_AGENT`, the session id and the
   messaging token into every workbench's claude process. The start moves into the repo as
   `scripts/sysadmin/fabrik_deck.py code-server` (tracked); the untracked `~/.local/bin/fabrik-deck-server`, which
   appends to `~/.local/share/code-server-deck.log`, is retired by the build. Its port comes from
   `FABRIK_DECK_CODE_PORT` (default 8443), passed as `--bind-addr 127.0.0.1:<port>`, which overrides the config file's
   `bind-addr` — one source for the port.
2. **The Deck server** — `scripts/sysadmin/fabrik_deck.py serve`, stdlib `http.server.ThreadingHTTPServer`
   (one thread per request, so an open event stream never blocks another request), bound to `127.0.0.1` on
   `FABRIK_DECK_PORT` (default 8445). It refuses a request whose `Host` header is not `localhost:<port>` or
   `127.0.0.1:<port>` (DNS rebinding) and accepts GET only; the one state it changes is deleting attention files
   older than 24 h, so no web page can change anything through it. It serves
   the **board** (`GET /`) and two JSON reads:
   - `GET /api/repos` — the **repo catalog**, never a hand list: every entry of `data/projects.yaml` (52 at this
     spec's base commit) plus every other git repo directly under `/opt` (a `.git` present), each `{name, path,
     agents}` where `agents` are the names in that repo's `.fabrik/session-agents.json` (a map of session id → agent
     name; 3 repos carry one today: fabrik, fabrik-lib, youtube). A repo with no file opens as a plain session — the
     fallback I17 asks for; W-a02d1c86 gives the rest their files.
   - `GET /api/attention` — the waiting sessions, read from the attention files (below), each mapped to its repo by
     `cwd` (a path under `<repo>/.claude/worktrees/` maps to `<repo>`), named by its agent where that repo's
     `session-agents.json` knows the session id, otherwise as `session <first 8 characters of the id>`.

   The board is one page: the repo list (a search box, one row per repo, a dot and the agent name when a session there
   waits, a link that opens `http://localhost:<code port>/?folder=<path>` in a new tab). It follows `/api/attention`
   over Server-Sent Events, so a background board stays current. An *Enable notifications* button on the board asks the browser's
   permission on the operator's click (browsers refuse a request not made from a user gesture); once granted, the board
   raises a browser notification on each NEW waiting session (`http://localhost` is a secure context, MDN cited below).
3. **Vivaldi** (installed: `C:\Users\user\AppData\Local\Vivaldi\Application\vivaldi.exe`, 8.2.4133.89, executed `ls`)
   does the window: each repo is a top-level tab; tiling (no limit on the number of tiled tabs; vertical, horizontal or
   grid; untile per tab or all — Vivaldi help, cited below) gives side by side; untiled tabs stay as tabs. No iframe
   exists, so nothing is re-parented and no cross-origin frame is throttled; whether tiling, untiling or Vivaldi's tab
   hibernation reloads a workbench tab is an open unknown the build's acceptance settles (a reload costs the view, never
   the agent, which runs server-side).
4. **Attention hook** — `scripts/sysadmin/fabrik_deck.py hook`, registered with no matcher for `Notification`,
   `UserPromptSubmit` and `Stop` as one `ENTRIES` row per event in `scripts/sysadmin/install_user_hooks.py` (its rows
   are command lists with no matcher field, `install_user_hooks.py:29-68`, so the hook filters `notification_type`
   itself). States, per `session_id`:
   - `Notification` with `notification_type` ∈ {`permission_prompt`, `idle_prompt`, `elicitation_dialog`} → write
     `<state dir>/attention/<session_id>.json` (state dir: `FABRIK_DECK_STATE`, default `~/.local/state/fabrik-deck`,
     read by the hook and the server alike) = `{cwd, type, at}` (atomic replace). Every other type is
     ignored.
   - `UserPromptSubmit` or `Stop` → delete that file. A permission prompt answered by a click keeps its dot until the
     turn ends (`Stop`); an agent that then sits waiting for input is re-marked by `idle_prompt`.
   - The server deletes files older than 24 h on each read.

   The hook fires in every session on the box (user-level hooks reach every account dir), so builders' waits show on
   the board under their agent name — the operator's cue to go to tmux.

**Profile** — `fabrik_deck.py profile` merges these keys into `~/.local/share/code-server/User/settings.json`
(live today: `workbench.colorTheme: "Dark 2026"`, `window.autoDetectColorScheme: false`,
`claudeCode.preferredLocation: "panel"`), after copying the file to `…/User/backups/settings.json.<timestamp>`:
`workbench.colorTheme: "Dark 2026"` (the operator's desktop VS Code 1.130 default theme, background `#121314`;
code-server 4.141.0 bundles it as `extensions/theme-defaults/themes/2026-dark.json`, executed `ls`),
`window.autoDetectColorScheme: false`, `claudeCode.preferredLocation: "panel"`, `editor.minimap.enabled: false`, `breadcrumbs.enabled: false`, `workbench.startupEditor: "none"`,
`workbench.activityBar.location: "top"` (kept, so Source Control stays one click away), `workbench.statusBar.visible:
true`, `workbench.editor.showTabs: "single"`. For these listed keys the Deck's value wins; every other key is left as
it is. The values are grounded in code-server 4.141.0's own settings schema (External dependencies).
`fabrik_deck.py install` copies `~/.config/code-server/config.yaml` to the same backups folder before writing it.

**Launcher** — `Fabrik Deck.bat` on the Windows desktop, written by `fabrik_deck.py launcher --desktop <dir>` (the
`scripts/sysadmin/agents_bat.py` pattern: a marker line, never overwriting a file it did not write). It runs
`wsl.exe` to (a) start tmux session `deck` with one window per server, each running `fabrik_deck.py code-server` or
`fabrik_deck.py serve` in a restart loop, when either port is not answering — stdout stays in the tmux pane (`tmux
attach -t deck` shows it) and the servers outlive the `.bat` window; (b) wait until `http://localhost:<deck port>/`
answers from Windows (measured: a newly bound port took up to ~15 s to forward; it waits up to 30 s, then shows an
error); (c) open the browser — on the board URL the first time (a marker file beside the `.bat`, written only after the board answered and the browser started, records it), and with
no URL afterwards, so Vivaldi's session restore brings back the board and the repo tabs without a duplicate board. The
install step in the doc sets Vivaldi's startup to the last session (Settings → Startup), a one-time operator click. The
browser path is a launcher flag (`--browser`), default the Vivaldi
path above.

**How it resolves the motivating failure:** every repo's coordinator is a tab in one window (I1, I2); tabs tile or stay
tabbed and hidden ones keep running server-side (I3); no password (I4) and no address (I5); dark (I6); the board says
which repo waits (I7); the browser restores its tabs (I8); the list comes from the registries (I9, I17).

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| **A dockview-core page framing code-server iframes** (the earlier draft: own-port page, judges 2 of 3; or the same page through code-server's path proxy, judge 1 of 3) | Builds a layout engine the browser already has (vendored 540 KB `dockview-core` 8.4.1, layout persistence, popout suppression, `renderer: 'always'` to stop iframe reloads). The Edge throttling doc says throttling "applies to all cross-origin iframes, regardless of whether they're same-process or cross-process", so the own-port variant's hidden panes are throttled; the same-origin variant couples the page to code-server's proxy. Its one gain — a dot on each tab itself — the board's dot plus a browser notification covers. |
| A `file://` page with no server | No attention data, cannot fetch the repo list; all three judges ranked it last. |
| One Brave tab per repo with no board | Today's interim: no tiling in Brave, no attention signal. |
| One VS Code window with a multi-root workspace | The Claude extension scopes chat tabs and history to the first folder (measured under W-ea993618). |
| A VS Code-side attention signal (title / badge) | None exists for the extension's webview (Claude Code VS Code docs); hooks are the documented channel. |
| `--cert` + the WSL address | Operator: no password, dynamic IP; localhost forwarding is a secure context with no cert. |
| systemd user units for the servers | No user bus in this WSL (`systemctl --user is-system-running` → "Failed to connect to bus", executed); tmux is the box's existing home for long-lived sessions (D-1092). |

## Lifecycle

- **First run:** `fabrik_deck.py install` backs up and writes config.yaml and the profile, and writes the `.bat`;
  infra registers the hook rows. The board opens with no repo tabs; the operator opens the ones they want, and Vivaldi
  remembers them.
- **Daily:** one double-click; Vivaldi restores the tabs; the board shows waiting agents.
- **Growth:** each open repo tab is a VS Code workbench in the browser plus an extension host process in code-server.
  The build's acceptance opens 6 repo tabs and records code-server's and Vivaldi's memory in the doc, and the doc's
  guidance is drawn from that measurement. No hard cap — closing a tab is the operator's lever.
- **Degradation:** code-server down → workbench tabs show VS Code web's reconnect banner and recover when the restart
  loop brings it back; the Deck server down → the board shows the browser's error until the loop restarts it;
  Windows localhost forwarding stuck (measured transient: one `000` on 2026-10-21) → the launcher's wait says so.
- **Retirement:** `tmux kill-session -t deck`; delete the `.bat` and its marker file; remove the `ENTRIES` rows, then delete the
  registration from each account dir's `settings.json` by hand after a backup (`install_user_hooks.py` adds and
  repairs but has no remove — its only flags are `--check` and `--warn`, `install_user_hooks.py:133-141`); restore
  config.yaml and settings.json from their backups, or delete `~/.local/share/code-server` and
  `~/.local/state/fabrik-deck`. Nothing in any project repo depends on it.

## External dependencies

| Dependency | Grounded facts (fetched 2026-10-21) | Source |
|---|---|---|
| code-server 4.141.0 (Code 1.141.0) | Installed and running; no X-Frame-Options (executed header read); the extension's `claude` process runs under code-server's extension host (executed `ps`); settings schema in `lib/vscode/out/vs/code/browser/workbench/workbench.js`: `workbench.startupEditor` enum includes `"none"`, `workbench.editor.showTabs` enum `["multiple","single","none"]`, `workbench.activityBar.location` enum `["default","top","bottom","hidden"]`; `breadcrumbs.enabled`, `workbench.statusBar.visible`, `editor.minimap.enabled` defined (executed grep) | executed 2026-10-21 |
| Vivaldi 8.2 tab tiling | "There’s no limit to how many tabs you can tile at once"; tile by dragging a tab into the page ("Drop to tile"), right-click → Tile, or Quick Commands "Tile Vertically/Horizontally/to Grid"; untile per tab or all | https://help.vivaldi.com/desktop/tabs/tab-tiling/ |
| Chromium cross-origin iframe throttling (why the iframe shell was rejected) | "This feature standardizes throttling, so it applies to all cross-origin iframes, regardless of whether they're same-process or cross-process." | https://learn.microsoft.com/en-us/deployedge/edge-learnmore-iframe-throttling-display |
| Claude Code hooks | "Claude Code fires the same hook events wherever it runs: sessions in the terminal, IDE extensions, …"; `Notification` input carries `notification_type` (`permission_prompt`, `idle_prompt`, `elicitation_dialog` among others) and `cwd`; `UserPromptSubmit` and `Stop` carry `session_id` | https://code.claude.com/docs/en/hooks |
| Claude Code VS Code extension | `preferredLocation` (`sidebar` · `panel`), `claudeProcessWrapper`, `environmentVariables`; no documented attention badge | https://code.claude.com/docs/en/vs-code |
| WSL2 localhost forwarding | Windows `curl.exe http://localhost:8443/` → 302 (3/3); a newly bound 8445 answered 200 (3/3) after ~15 s and failed in its first seconds (executed) | executed 2026-10-21 |
| Browser secure context on localhost (the board's notifications) | "Top-level documents provide a secure context when their URL is a potentially trustworthy URL", with `http://localhost` listed as "Secure (localhost URL)"; the Notification API is available only in secure contexts, and browsers are moving to refuse a permission request not made from a user gesture | https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts · https://developer.mozilla.org/en-US/docs/Web/API/Notification |

## fabrik-lib verdict

| Capability | Verdict | Module / why |
|---|---|---|
| Window tiling and tabs | CONSUME (the browser) | Vivaldi's built-in tab tiling; nothing built |
| Small loopback HTTP server + JSON + SSE | BUILD | stdlib `http.server`; fabrik-lib's module table has no static or loopback server (grep of `/opt/fabrik-lib/README.md`) |
| Hook → attention state | BUILD | Box-local hook; no module |

No `🆕 fabrik-lib candidate`: none is used by ≥2 project types.

## Shape / infra implications

Box-local tooling in the hub, not a scaffolded project or a deployed service: no `specs/services/*.yaml`, no `shape:`
flags, no VPS. Runs in WSL as the operator's user; the browser runs on Windows.

## Documentation landing sites

- `docs/workstation/fabrik-deck.md` (NEW, the box doc): what it is, install, the launcher, the env variables
  (`FABRIK_DECK_PORT`, `FABRIK_DECK_CODE_PORT`, `FABRIK_DECK_STATE`), the profile keys, the attention hook, the measured memory per tab,
  rollback (the Retirement steps), and the accepted auth-none exposure.
- `docs/CONFIGURATION.md` + `.env.example` — the three env variables (a new environment variable, `.windsurf/rules/core/40-documentation.md:68`).
- `INDEX.md` — the doc's and the script's rows; `docs/workstation/hooks-index.md` — the hook's row (infra's doc,
  edited with the `ENTRIES` rows); `CHANGELOG.md` — one entry per build commit.
- `docs/DECISIONS.md` — the approach and the auth-none exposure acceptance, minted at approval.

## Constraints

- **Auth none is an exposure the operator accepted:** with `auth: none` on 127.0.0.1:8443, ANY local process — any
  Windows process through localhost forwarding, and any web page open in the browser that frames or links it — can
  drive a full VS Code with a terminal as the operator's user. The operator ruled it ("no it should not bound
  password"); the spec records it as an accepted risk, binds both servers to `127.0.0.1` only, keeps the Deck
  server GET-only with a Host check, and the doc says so.
- Box-local: nothing deploys; no project repo changes (the hub gains the script, the `ENTRIES` rows and docs).
- No third-party JavaScript: the board is plain HTML and JS served by the stdlib server.

## Open / blocking unknowns

| Unknown | Status | Resolution step |
|---|---|---|
| The approach (browser tiling + board, vs the dockview iframe shell the judges ranked before the coordinator's Vivaldi input) | OPEN | The Opus + Fable approval panel at `/fabrik-spec-review` rules; a split goes to the coordinator |
| Vivaldi restores the board, the code-server tabs and their tiling after a restart (its "last session" startup) | OPEN | The build's acceptance closes and reopens Vivaldi with 3 repo tabs, 2 of them tiled, and confirms all return |
| Tiling, untiling or tab hibernation reloads a workbench tab | OPEN | The build's acceptance tiles and untiles a repo tab mid-chat and leaves one in the background past Vivaldi's hibernation delay, and records whether the chat view reloads; if hibernation reloads it, the doc tells the operator to exclude `localhost` from hibernation |
| Memory per open repo tab (code-server extension host + workbench) | OPEN | The build's acceptance opens 6 tabs and records RSS in the doc |
| The `ENTRIES` rows and their hooks-index row (infra's surface) | OPEN | The plan names infra as reviewer of those rows |
