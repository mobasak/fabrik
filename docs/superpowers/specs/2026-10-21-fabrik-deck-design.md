# Fabrik Deck — a non-coding VS Code for many repos, in one browser tab

Status: DRAFT
Work item: W-42d1ccb5 (owner fleet) · related: W-ea993618 (the tab router, agent picking inside a pane — separate,
queued) · rulings: D-1092 (coordinator in the Claude extension GUI, builders in tmux, no fixed count), D-1072 (WSL NAT:
Windows reaches WSL only at its address — superseded for this service by the measured localhost forwarding below).

## Personas

| Persona | Who | Duties held in this design |
|---|---|---|
| **Primary — the operator** | The box's one human. In their words: *"it will be like non coding version of vs code, vibe coding ide using vs code's claude extension for multiple repos."* and *"i want single vs code looking window for any repos to open any agents in it opened via claude vs code extension"* | Opens the Deck, picks tabs, drags splits, answers agents |
| Each repo's **coordinator** (an AI agent, D-874) | The agent the operator talks to per repo, in the Claude extension's chat (D-1092) | Runs in its pane's Claude panel; its hook events feed the attention badge |
| **Builders** (AI agents in tmux, D-1092) | Per-repo worker sessions | Not panes by default (D-1092 keeps them in tmux); reachable later through the router W-ea993618 |
| **fleet** (this agent) | Box-local tooling owner | Builds and maintains the Deck server, page, launcher, doc |
| **infra** | Owner of `.claude/hooks/` and `install_user_hooks.py` (beat: hooks) | Reviews the one user-level hook entry the attention badge needs |
| The **Claude Code hook runtime** (automated) | Fires `Notification` / `UserPromptSubmit` / `Stop` in every session, extension included | Writes the per-session attention state the Deck reads |

**The primary's loop, counted — the STEP BUDGET (5):** (1) double-click *Fabrik Deck* on the Windows desktop →
(2) Brave opens one tab with the last layout (every remembered repo pane loads) → (3) click a repo's tab (or a badged
one) → (4) type to that repo's coordinator in its Claude panel → (5) drag a tab to the side to watch two repos at once.
Adding a repo: + button → pick a repo from the list → it opens as a tab (counted within step 3).

Every feature below traces to this persona's quoted asks (I-rows in the Intake Inventory).

## Goal

One Brave tab that looks and behaves like VS Code's editor area — a tab strip with drag-to-split columns and rows —
where every tab is a full code-server (VS Code web) workspace on one repo, with the real Claude Code extension, dark
theme, no password, at an address that never changes, and a badge on any tab whose agent is waiting on the operator.

## Why this exists

The official Claude extension scopes a window's chat tabs and history to that window's first folder (measured under
W-ea993618), so today the operator needs one VS Code window per repo, and the coordinators the operator talks to
(D-1092) are spread across windows. The Deck puts every repo's coordinator in one window. The step-1 proof (2026-10-21,
operator: *"yes i can see youtube agents in it"*) showed the core works: code-server + the Claude extension, reached
from Brave at `http://localhost:8443`. What is missing is the one-window shell, the profile, the launcher and the doc.

## Intake Inventory

| I# | Item (anchored, operator's words unless marked) | Disposition | Where |
|---|---|---|---|
| I1 | "non coding version of vs code, vibe coding ide using vs code's claude extension for multiple repos" | IN | Goal, Chosen approach |
| I2 | "single vs code looking window for any repos to open any agents in it" | IN | Chosen approach (one tab, dockview grid) |
| I3 | "i can have multiple tabs, also i can see some side by side or some as tabbed (not seen)" | IN | Shell: tabs + splits; hidden tabs stay live |
| I4 | "no it should not bound password" | IN | code-server auth none (measured, live) |
| I5 | "our ip is dynamic not static" | IN | localhost forwarding (measured) — no address in any config |
| I6 | "i want same theme as like i use in vs code here, not white" | IN | Profile: Dark Modern (live in settings.json) |
| I7 | coordinator: attention badge when a pane's agent waits | IN | Attention via Claude Code hooks |
| I8 | coordinator: layout remembered across reloads | IN | Layout persistence |
| I9 | coordinator: repo/agent list from the registries | IN | Repo catalog |
| I10 | coordinator: non-coding profile (minimal chrome, Claude panel primary, git view kept) | IN | Profile |
| I11 | coordinator: Desktop .bat launcher (starts the server if needed, opens the Deck in Brave) | IN | Launcher |
| I12 | coordinator: box doc under docs/workstation/ with rollback | IN | Documentation landing sites |
| I13 | coordinator: the router (agent picking inside a pane) | OUT-OF-SCOPE | W-ea993618 (queued item, parked at review pass 1) |
| I14 | operator earlier: "i want exact look and feel with vs code" | IN | It IS VS Code (code-server) inside each pane |
| I15 | coordinator: keep the router's design usable inside a code-server pane | IN | Profile sets claudeCode.claudeProcessWrapper only when the router ships |

Intake: 15 items — 14 IN, 1 OUT-OF-SCOPE (named above), 0 ASK.

## Constraints Digest

| Quote | Source |
|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:16` |
| Testing Trophy model: integration and E2E tests are the primary source of truth. | `.windsurf/rules/core/45-testing-strategy.md:19` |
| No cosmetic assertions: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Source, config, or Docker file changed | `.windsurf/rules/core/40-documentation.md:67` |

(12-Factor axes applied as the design constraints: III config in env — the server's port and paths are env-overridable;
XI logs — the server logs to stdout, never a logfile; VIII — never daemonize or write PID files: the launcher starts
the server attached to a `wsl.exe` process, not as a daemon.)

## Chosen approach — the own-port shell (judge panel 2 of 3; the split is carried to the approval gate)

Three pieces, all box-local, all in WSL as the operator's user:

1. **code-server** (installed, live since step 1): `~/.local/lib/code-server-4.141.0-linux-amd64`, config
   `~/.config/code-server/config.yaml` = `bind-addr: 127.0.0.1:8443`, `auth: none`, `cert: false` (operator: no
   password; no address). Started by `~/.local/bin/fabrik-deck-server` with a CLEAN environment (`env -i` plus HOME,
   PATH, DISPLAY and the `CLAUDE_CONFIG_DIR`/`CLAUDE_QUOTA_HOME` pair the VS Code server also passes) — measured
   2026-10-21: a start from inside a Claude session leaked `CLAUDE_AGENT`, the session id and the messaging token into
   every pane's claude process.
2. **The Deck server** — one stdlib Python process (`scripts/sysadmin/fabrik_deck.py serve`), bound to `127.0.0.1` on
   `FABRIK_DECK_PORT` (default 8445; config from env, 12-Factor III), logging to stdout (XI), never a PID file or a
   daemon (VIII). It serves:
   - `GET /` — the page; `GET /static/*` — the vendored files (`dockview-core` 8.4.1 UMD, pinned by sha256, no CDN at
     runtime);
   - `GET /api/repos` — the repo catalog: every repo under `/opt` that has a coordinator (the ledger's merge owner,
     `decisions.py --merge-owner`) or a `.fabrik/session-agents.json`, plus the rest of `data/projects.yaml` for the
     "add a tab" picker — each `{name, path, coordinator}`;
   - `GET /api/attention` — the waiting state per repo, read from the hook's state files (below);
   - `GET/PUT /api/layout` — the layout JSON in `~/.local/state/fabrik-deck/layout.json` (atomic write), so the
     layout survives a browser-profile reset; the page also keeps a localStorage copy.
3. **The page** — a static HTML/JS page using `dockview-core` with `defaultRenderer: 'always'` (an iframe never leaves
   the DOM, so hiding, showing, or dragging a tab into another split never reloads it — dockview docs and the 8.4.1
   bundle, both cited below). Each panel is an `<iframe src="http://localhost:8443/?folder=<repo path>">` with the
   `allow` list the workbench needs (clipboard). Tabs show the repo name; a tab whose repo has a waiting agent gets a
   dot (a custom tab renderer, dockview's documented path); popout windows are disabled (a popout would reload the
   iframe). Layout changes (`onDidLayoutChange`) save to `/api/layout`, debounced. Default layout on first run: one
   tab per repo that has a coordinator.

**Attention** — one small user-level Claude Code hook, `scripts/sysadmin/fabrik_deck.py hook`, registered for
`Notification` (matchers `permission_prompt`, `idle_prompt`, `elicitation_dialog`), `UserPromptSubmit` and `Stop`:
on `Notification` it writes `~/.local/state/fabrik-deck/attention/<session_id>.json` = `{cwd, type, at}`; on
`UserPromptSubmit` it deletes that file (the operator answered); `Stop` records `{type: "done"}` (a finished turn).
The server maps each file's `cwd` to the repo it lies under (a builder's worktree under `<repo>/.claude/worktrees/`
maps to its repo) and drops files older than 24 h. Hooks fire inside the VS Code extension (docs, cited). The hook is
registered through `scripts/sysadmin/install_user_hooks.py`'s `ENTRIES` — infra's surface, so infra reviews that one
entry (named in the plan).

**Profile** — code-server's `~/.local/share/code-server/User/settings.json` (live today: `workbench.colorTheme: "Dark
Modern"`, `window.autoDetectColorScheme: false`, `claudeCode.preferredLocation: "panel"`) gains the non-coding keys,
each grounded below: `editor.minimap.enabled: false`, `breadcrumbs.enabled: false`, `workbench.startupEditor: "none"`,
`workbench.activityBar.location: "top"` (kept, so Source Control stays one click away — `hidden` would remove the
switcher), `workbench.statusBar.visible: true`, `workbench.editor.showTabs: "single"`. Written by
`fabrik_deck.py profile` as a key-by-key merge that never drops a key the operator set.
`claudeCode.claudeProcessWrapper` is NOT set here until the router W-ea993618 ships (I15).

**Launcher** — `Fabrik Deck.bat` on the Windows desktop, written by `fabrik_deck.py launcher --desktop <dir>` (the
`agents_bat.py` pattern: a marker line, never overwriting a file it did not write). It runs `wsl.exe` to start
`fabrik-deck-server` and `fabrik_deck.py serve` if either port is not answering, waits until
`http://localhost:<deck port>/` answers from Windows (measured: a newly bound port took several seconds to forward;
up to 30 s, then a visible error), then opens
`"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe" --app=http://localhost:<deck port>/`
(an app window with no browser chrome — the "VS Code looking window").

**How it resolves the motivating failure:** every repo's coordinator becomes a tab in one window (I1, I2); tabs split
and hidden tabs keep running (I3); no password (I4) and no address (I5, measured localhost forwarding); dark (I6);
the badge says which repo waits (I7); the layout survives reloads (I8).

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| **C — Proxied shell** (the same server, opened through code-server's path proxy `http://localhost:8443/proxy/<port>/`, one origin) | Judge 3 ranked it first (one forwarded port, same-origin frames). Judges 1 and 2: it couples the Deck to code-server's proxy (prefix stripping, a code-server restart takes the shell down) for a same-origin guarantee nothing needs — the page and the panes are already same-SITE (localhost, ports ignored), and auth is none. Executed: the second port forwards from Windows (3/3 after ~15 s). **Carried to the approval gate as the open split.** |
| **A — File shell** (a `file://` page, no server) | No attention badge (no server to read hook state), a `file://` page cannot fetch the repo list, `file://` localStorage is fragile; all three judges ranked it last. |
| One Brave tab per repo (`?folder=` each) | Not one window (I2); no splits; today's interim only. |
| One VS Code window with a multi-root workspace | The Claude extension scopes chat tabs and history to the first folder (measured under W-ea993618). |
| Golden Layout 2 (Virtual binding) | Keeps iframes alive, but its last release is 2022, the repo is dormant and the npm package needs a build step. |
| FlexLayout | React only. |
| dock-spawn-ts | Every 4.x release is under 14 days old; no documented iframe guarantee. |
| dockview-core 8.6.1 (latest) | Published 2026-10-19 — under the 14-day age rule; 8.4.1 has the same `always` renderer (executed grep of the bundle). |
| A VS Code-side attention signal (title / badge) | None exists for the extension's webview (Claude Code VS Code docs); hooks are the documented channel. |
| `--cert` + the WSL address | Operator: no password, dynamic IP; localhost forwarding is a secure context with no cert. |

## Lifecycle

- **First run:** the launcher writes the profile, starts both servers, opens the default layout (one tab per repo with
  a coordinator). Each pane's first load takes a few seconds (VS Code web boots per tab).
- **Daily:** one double-click; the remembered layout loads; badges show waiting repos.
- **Growth:** each pane is a full VS Code workbench in the browser plus its extension host process in code-server.
  Trigger to measure: at 6 open panes, read code-server's RSS and Brave's tab memory; if a pane costs over 500 MB, the
  doc tells the operator to close idle tabs (closing a tab ends nothing in the agent — the session resumes from its
  history). No hard cap.
- **Degradation:** code-server down → panes show the connection error and reconnect when it is back (VS Code web's own
  behaviour); the Deck server down → the page cannot load, the launcher restarts it; Windows localhost forwarding
  stuck (measured transient: one `000` on 2026-10-21) → the launcher's wait loop retries, then says so.
- **Retirement:** stop both servers, delete the `.bat`, remove the hook entry with `install_user_hooks.py`, delete
  `~/.local/share/code-server` and `~/.local/state/fabrik-deck`; nothing in any repo depends on it.

## External dependencies

| Dependency | Grounded facts (fetched 2026-10-21) | Source |
|---|---|---|
| code-server 4.141.0 (Code 1.141.0) | Installed and running; no X-Frame-Options and no frame-ancestors (executed header read); path proxy serves loopback ports on its origin (executed); session cookie SameSite=lax; maintainer: "we'd recommend making sure all parent and iframe have the same origin" | https://github.com/coder/code-server/issues/1401 · https://coder.com/docs/code-server/guide |
| dockview-core 8.4.1 (MIT, 2026-10-05) | UMD `dist/dockview-core.min.js`, 540,640 bytes (downloaded); "re-parenting an iframe within the DOM reloads its contents … render its panel with `renderer: 'always'`"; the 8.4.1 bundle carries `defaultRenderer` and three `always` branches (executed grep); `toJSON`/`fromJSON`, `onDidLayoutChange`, `setTitle` | https://dockview.dev/docs/core/panels/rendering · https://dockview.dev/docs/core/state/save · https://registry.npmjs.org/dockview-core |
| Chromium iframe move semantics | Re-insertion "resets all sorts of state"; `moveBefore()` (Chrome 133) is the state-preserving move — not needed with `always` | https://developer.chrome.com/blog/movebefore-api |
| Chromium hidden-iframe throttling | Cross-origin non-visible frames are throttled only when rendered cross-process; the Deck's panes are same-site with the page | https://learn.microsoft.com/en-us/deployedge/edge-learnmore-iframe-throttling-display |
| Claude Code hooks | "Claude Code fires the same hook events wherever it runs … IDE extensions"; `Notification` carries `notification_type` (`permission_prompt`, `idle_prompt`, `elicitation_dialog`) and `cwd` | https://code.claude.com/docs/en/hooks |
| Claude Code VS Code extension | `preferredLocation` (`sidebar` · `panel`), `claudeProcessWrapper`, `environmentVariables`; no documented attention badge | https://code.claude.com/docs/en/vs-code |
| VS Code settings | `workbench.activityBar.location` (`default`·`top`·`bottom`·`hidden`), `workbench.editor.showTabs` (`multiple`·`single`·`none`), `workbench.startupEditor`, `editor.minimap.enabled`, `breadcrumbs.enabled`, `workbench.statusBar.visible` | https://code.visualstudio.com/docs/configure/custom-layout · https://code.visualstudio.com/docs/getstarted/settings |
| WSL2 localhost forwarding | Windows `curl.exe http://localhost:8443/` → 302 (3/3); a newly bound 8445 answered 200 (3/3) after ~15 s, failed in its first seconds (executed) | executed 2026-10-21 |
| Brave | `C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe` (155.1.97.59 present, executed `ls`) | executed 2026-10-21 |

## fabrik-lib verdict

| Capability | Verdict | Module / why |
|---|---|---|
| Tabs + splits layout in a browser | BUILD (vendor a third-party file) | No fabrik-lib module covers browser layout; dockview-core vendored as one pinned file |
| Small loopback HTTP server + JSON API | BUILD | stdlib `http.server`; no fabrik-lib module for a box-local static server |
| Hook → attention state | BUILD | Box-local hook; no module |

No `🆕 fabrik-lib candidate`: none is used by ≥2 project types.

## Shape / infra implications

Box-local tooling, not a scaffolded project or a deployed service: no `specs/services/*.yaml`, no `shape:` flags, no
VPS. Runs in WSL as the operator's user.

## Documentation landing sites

- `docs/workstation/fabrik-deck.md` (NEW, the box doc): what it is, install, the launcher, the profile keys, the
  attention hook, rollback (stop both servers; restore `config.yaml` and `settings.json` from their backups; delete the
  `.bat`; remove the hook entry), and the measured caveats (forwarding delay, auth-none exposure).
- `INDEX.md` — the doc's tree row; `docs/workstation/hooks-index.md` — the new hook row (infra's doc, edited with the
  hook entry); `CHANGELOG.md` — one entry per build slice.
- `docs/DECISIONS.md` — the approach and the auth-none exposure acceptance (below), minted at approval.

## Constraints

- **Auth none is an exposure the operator accepted:** with `auth: none` on 127.0.0.1:8443, ANY local process — and
  any Windows process, through localhost forwarding — can drive a full VS Code with a terminal as the operator's user.
  The operator ruled it ("no it should not bound password"); the spec records it as an accepted risk, binds both
  servers to `127.0.0.1` only, and the doc says so.
- Box-local: nothing deploys; nothing in a project repo changes; no `specs/services/` file.
- No network at runtime: dockview is vendored and pinned by sha256.

## Open / blocking unknowns

| Unknown | Status | Resolution step |
|---|---|---|
| The approach split (B own-port, panel 2/3, vs C proxied, 1/3) | OPEN | The approval panel at `/fabrik-spec-review` decides; a split goes to the operator |
| Several live code-server panes in one page (memory, websocket count) | OPEN | Build slice 1's acceptance opens 3 panes and measures RSS |
| dockview `always` panels during a drag between splits (no reload) | OPEN — documented, not yet executed | Slice 1's acceptance drags a live pane mid-chat and confirms no reload |
| `window.zoomLevel` in code-server web | Not used | The profile does not depend on it |
| The hook entry in `install_user_hooks.py` (infra's surface) | OPEN | The plan names infra as reviewer of that entry |
