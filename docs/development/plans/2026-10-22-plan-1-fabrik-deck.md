# Fabrik Deck — attention hook, board server, profile, launcher

Status: DRAFT
**Owner:** fleet
Spec: `docs/superpowers/specs/2026-10-21-fabrik-deck-design.md` (CONVERGED, approved D-1106) · Work item: W-42d1ccb5 ·
already built: the code-server unit (W-e89a9b5b, D-1107, merged 73eec28ca).

## What we already agreed

- Goal and the four pieces: spec § Goal, spec § Chosen approach — browser tiling + a Deck board (items 1-4, Profile,
  Launcher). Piece 1 (code-server under `fabrik-deck-code.service`) is built (D-1107).
- Rejected: the dockview iframe shell and four others — spec § Rejected alternatives.
- Supervision (two user units, one env file): spec § Lifecycle, Supervision.
- The hook reads `~/.config/fabrik-deck/env` itself for `FABRIK_DECK_STATE` (R-P10, recorded at the spec's approval,
  D-1106), because sessions outside the Deck never load that file.
- The repo catalog reads every repo with a plain-session fallback (spec I17); the scaffolder and rollout half is
  W-a02d1c86, held behind this plan by the coordinator (2026-10-22).
- Auth none is an accepted exposure: spec § Constraints.
- Tests: spec § Tests, behaviours 1-10.

Branch: RICH — a CONVERGED, approved spec; nothing re-brainstormed. Approval row D-1106 present (grepped).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec intake I1-I18 ("non coding version of vs code … for multiple repos" and the rest) | IN as dispositioned there | spec § Intake Inventory; phases A-C |
| I2 | coordinator, 2026-10-22: W-a02d1c86 "held behind" the Deck; "the audit file stays as the spec's seed" | OUT-OF-SCOPE | W-a02d1c86 (its own /fabrik-spec later) |
| I3 | `$ARGUMENTS`: "Carry R-P10 (the hook reads ~/.config/fabrik-deck/env itself for FABRIK_DECK_STATE)" | IN | Phase A step 2 |
| I4 | `$ARGUMENTS`: "The repo catalog's plain-session fallback (spec I17) is in scope" | IN | Phase B step 2 |
| I5 | grounding G1: the hooks-index row must reach master BEFORE `install_user_hooks.py` runs (blocking gate row) | IN | Phase A step 5; Post-merge order |
| I6 | grounding G1: `tests/test_install_user_hooks.py:74` breaks when a Notification row is added | IN | Phase A step 4 |

Intake: 6 items — 5 IN, 1 OUT-OF-SCOPE (W-a02d1c86), 0 ASK.

## Global Constraints

- Box-local tooling in the hub: no `specs/services/*.yaml`, no `shape:`, no VPS, no compose (spec § Shape / infra implications).
- Stdlib only in `scripts/sysadmin/fabrik_deck.py` except PyYAML for the catalog (system `/usr/bin/python3` has PyYAML 6.0.1 — Evidence E1).
- 12-Factor: III — every port and path from env or a flag with a default; XI — logs to stdout only, never a logfile
  (journald holds it); VIII — no daemonizing, no PID file; each server runs in the foreground of its unit. No
  migrations, no backing services, no sticky sessions apply here.
- Both servers bind `127.0.0.1` only; the Deck server is GET-only with a Host check (spec § Constraints).
- The hook prints nothing on stdout, always exits 0, finishes far inside the 10 s registration timeout; SessionEnd
  hooks share a 1.5 s budget (Claude Code hooks doc, fetched 2026-10-22 by grounder G1).
- Never register a hook before review: `install_user_hooks.py` is run only after merge, from the main checkout, and
  only after the hooks-index row is on master (the "Hooks Index Fresh" gate row is blocking and reads the LIVE
  `~/.claude/settings.json`, `final_gate.py:2314-2316`).
- Tests run through `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest …`; never `uv sync` from a worktree.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | uv only; no logfile; granular env | `.windsurf/rules/core/10-python.md:22`, `:302` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env with defaults; frame-ancestors header | `.windsurf/rules/core/35-security-auth.md:267`, `:219` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour; watched-fail-first; no cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:20-22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | fenced code; no skipped heading levels | `.windsurf/rules/core/40-documentation.md:242`, `:244` |
| fabrik-lib | no loopback server or hook module (spec § fabrik-lib verdict: BUILD) | `/opt/fabrik-lib/README.md` module table (spec) |
| `agents-fabrik.md` | Development Environment: WSL dev, `.venv` | `agents-fabrik.md:130` |
| hub precedent — HTTP guard | `_allowed_hosts`/`_guard`/cross-site 403 | `scripts/sysadmin/quota_dashboard.py:2806-2850` |
| hub precedent — hook stdin | defensive payload read, sid guard | `scripts/sysadmin/worktree_transcript_link.py:100`, `:113-122` |
| hub precedent — registry read | bounded, regular file, dict of str | `scripts/agent_status.py:189`, `:209-242` |
| hub precedent — .bat writer | marker line 2, CRLF, ASCII, refuse foreign | `scripts/sysadmin/agents_bat.py:44`, `:92-107`, `:227-253` |

## Constraints Digest

| Quote | Source |
|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` |
| **BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. | `.windsurf/rules/core/10-python.md:302` |
| => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. | `.windsurf/rules/core/35-security-auth.md:267` |
| - `Content-Security-Policy: frame-ancestors 'none'` — the MODERN clickjacking control (CSP Level 2; browsers ignore XFO when it is present) | `.windsurf/rules/core/35-security-auth.md:219` |
| - **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only. | `.windsurf/rules/core/45-testing-strategy.md:21` |
| - **No skipped heading levels** — `##` to `###`, never `##` to `####` | `.windsurf/rules/core/40-documentation.md:242` |
| - **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:244` |

Selections: the board sends `Content-Security-Policy: frame-ancestors 'none'` (digest row 4); every new knob is an env
var with a default or a flag (row 3); tests assert files, HTTP status and JSON (row 5).

## Phase A — the attention hook and its registration

Appetite: 90

Implements spec § Chosen approach item 4 and Tests 1-2.

**Interfaces.** Consumes: `_read_env` (`scripts/sysadmin/fabrik_deck.py:113-136`). Produces:
`_env_path(home: Path) -> Path` (`<home>/.config/fabrik-deck/env`); `_state_dir(home: Path, environ) -> Path` (env
`FABRIK_DECK_STATE`, else the env file's value, else `<home>/.local/state/fabrik-deck`); the attention file
`<state>/attention/<session_id>.json` = `{"cwd": str, "type": str, "origin": "tmux"|"deck"|"other", "at": <epoch float>}`,
written temp-then-rename; subcommand `fabrik_deck.py hook` (stdin JSON).

**Behavior Contract.**
- Given a Notification with `notification_type` permission_prompt, idle_prompt or elicitation_dialog, When the hook runs, Then `<state>/attention/<sid>.json` holds that type (spec § Tests 1)
- Given any other Notification type, When the hook runs, Then no file is written (spec § Tests 1)
- Given Stop, When the hook runs, Then the file holds `turn_ended`; Given UserPromptSubmit or SessionEnd, Then the file is gone (spec § Tests 1)
- Given PostToolUse, When the file's type is permission_prompt, Then it is deleted, and any other type is kept (spec § Tests 1)
- Given `TMUX` or `FABRIK_DECK=1` in the environment, When the hook writes, Then `origin` is `tmux` or `deck`, else `other` (spec § Tests 2)
- Given malformed JSON, a non-dict payload, a session id holding `/`, or an unwritable state dir, When the hook runs, Then it exits 0 with empty stdout (spec § Tests 2)
- Given no `FABRIK_DECK_STATE` in the environment but one in the env file, When the hook runs, Then it writes under the file's directory (R-P10)
- Given the five ENTRIES rows, When `install_user_hooks.py` installs into a temp home holding a foreign Notification entry, Then each event carries exactly one `fabrik_deck.py hook` command and the foreign entry survives

**Steps.**
1. Probe: `/usr/bin/python3 --version` and `.venv/bin/python -m pytest --version` — expect both print a version.
2. TDD, risky path first: in `tests/test_fabrik_deck.py` give `box.run` an `input=` argument (`:94-103` has none) and
   write the eight tests above; run `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fabrik_deck.py -k hook`
   — expect them to FAIL (no `hook` subcommand).
3. In `scripts/sysadmin/fabrik_deck.py`: factor `_env_path` out of `install` (`:211`); add `_state_dir` (reads the
   file with `_read_env(text, warn=False)` — no stderr in every session); add `hook()`: read stdin only when not a
   TTY, `json.loads` in a `try`, require a dict and a `session_id` str without `/` (`worktree_transcript_link.py:100`),
   branch on `hook_event_name` (`scripts/thread_anchor.py:1122` reads the same key) per the contract, write by
   `_atomic_write` (`:139-151`) under `<state>/attention/`, catch `Exception` → one stderr line, `sys.exit(0)`.
   Restructure `main()` (`:262-284`): a branch per subcommand, the `systemd-analyze` check only for `install`.
   Add `docs/workstation/hooks-index.md` and `scripts/sysadmin/install_user_hooks.py` to the `# AFTER-EDIT:` header (`:2`).
   Gate: the step-2 command — expect all `hook` tests green.
4. In `scripts/sysadmin/install_user_hooks.py` `ENTRIES` (`:29-68`): append
   `f"python3 {HUB}/scripts/sysadmin/fabrik_deck.py hook"` as the LAST command of UserPromptSubmit, Stop and SessionEnd,
   and add `Notification` and `PostToolUse` keys holding only it (one per event — the duplicate rule `:127-128`; no
   matcher — `:121` requires one only for PreToolUse). In `tests/test_install_user_hooks.py` re-expect `:26`/`:74`:
   seed a foreign Notification entry (`claude-sound.sh attention`, matcher `permission_prompt`) and assert it
   survives beside the new row; add the five-events test. Gate:
   `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_install_user_hooks.py` — expect all pass.
5. `docs/workstation/hooks-index.md`: one user-level row beside `:95-96` naming `Notification`, `UserPromptSubmit`,
   `Stop`, `PostToolUse`, `SessionEnd`, the command, its contract and its tests, and stating that an answered
   permission DENIAL fires PostToolUseFailure, so that dot clears at Stop or the next prompt. Gate:
   `command grep -c "fabrik_deck.py hook" docs/workstation/hooks-index.md` — expect ≥1; `command grep -c PostToolUse docs/workstation/hooks-index.md` — expect ≥1.
6. Measure the hook's cost on PostToolUse with no file: 20 runs of `/usr/bin/time -f %e /usr/bin/python3 scripts/sysadmin/fabrik_deck.py hook < <payload file>`; record the mean in `docs/workstation/fabrik-deck.md` (the spec accepted 22-35 ms for a bare start).
7. Closing sequence: (1) the phase gates above, green; (2) `python3 scripts/enforcement/check_doc_sync.py` and the
   doc steps 5-6; (3) **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated
   exit**; infra reviews the `ENTRIES` rows and the hooks-index row (their beat — mail with the commit); (4) commit
   the phase by explicit paths with provenance trailers.

## Phase B — the Deck server, catalog and board

Appetite: 150

Implements spec § Chosen approach item 2 and Tests 3-7.

**Interfaces.** Consumes: `_state_dir`, `_env_path`, the attention file shape (Phase A). Produces: subcommand
`fabrik_deck.py serve [--registry PATH] [--opt-root DIR]` (defaults: `<hub>/data/projects.yaml`, `/opt`), port from
`FABRIK_DECK_PORT` (default 8445, `_parse_port`); `catalog(registry, opt_root) -> list[{"name","path","git": bool,"agents": list[str]}]`;
`attention(state, catalog, now) -> list[{"repo"|"other","label","type","at"}]`; routes `GET /`, `GET /api/repos`,
`GET /api/attention`, `GET /api/events` (SSE, `text/event-stream`).

**Behavior Contract.**
- Given a cwd under `<repo>/.claude/worktrees/<x>/sub`, When attention is read, Then it maps to `<repo>`; a cwd under no catalog repo lands in `other`; `/opt/fabrik-lib` never matches `/opt/fabrik` (spec § Tests 3)
- Given a session id in that repo's `.fabrik/session-agents.json`, Then its label is the agent name; else `coordinator (<repo> tab)` for origin deck, `session <8 chars> (tmux)` for tmux, `session <8 chars>` otherwise (spec § Tests 4)
- Given attention files older and younger than 24 h, When `/api/attention` is read, Then the older are deleted and the younger kept (spec § Tests 5)
- Given a request with a foreign Host header or a method other than GET, Then the server refuses it (421 / 405) (spec § Tests 6)
- Given a registry with a duplicate of an `/opt` repo, a missing path and a non-repository directory, When `/api/repos` is read, Then each repo appears once, the missing path is dropped and the non-repository is listed with `git: false` (spec § Tests 7)
- Given a damaged `session-agents.json` (not JSON, not a dict, over 1 MiB, not a regular file), Then the repo is listed with no agents and the server keeps serving

**Steps.**
1. TDD: add a `deck_server` fixture to `tests/test_fabrik_deck.py` — `subprocess.Popen` of `serve --registry <tmp
   yaml> --opt-root <tmp>` with `FABRIK_DECK_PORT=<_free_port()>` (`:116-119`) and `FABRIK_DECK_STATE=<tmp>`, poll the
   port with `socket.create_connection`, terminate in the finalizer; write the six tests; run
   `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fabrik_deck.py -k "serve or catalog or attention"` — expect FAIL.
2. Implement `catalog`: read the registry with `yaml.safe_load` (`path` is the only universal key — Evidence E2), scan
   `opt_root` with `os.scandir` in a `try` (an unreadable entry such as `/opt/containerd` is skipped), a repo = a
   directory holding `.git` (`exists()`, a worktree's `.git` is a file), dedupe by resolved path, drop missing paths;
   read each repo's `.fabrik/session-agents.json` from the repo root bounded at 1 MiB, regular file, dict of str
   (`scripts/agent_status.py:189`, `:209-242`).
3. Implement `attention`: map cwd by path components, longest catalog match first; label per the contract; delete
   files older than 24 h on each read.
4. Implement the server: `ThreadingHTTPServer` with `daemon_threads = True` on `127.0.0.1:<port>`; the Host guard
   (`localhost:<port>`, `127.0.0.1:<port>`, port from `server_address` — `scripts/sysadmin/quota_dashboard.py:2806-2850`),
   421 on a foreign Host, 405 for every method but GET, `Content-Security-Policy: frame-ancestors 'none'` and
   `Cache-Control: no-store` on every response; `/api/events` sends `data: <attention JSON>\n\n` every 2 s and on
   change, flushes each frame, and returns on `BrokenPipeError`/`ConnectionResetError`.
5. The board (`GET /`): one HTML page with inline JS, no third-party code; a search box; one row per repo with the
   dot and agent name when waiting, the link `http://localhost:<code port>/?folder=<path>` opening a new tab; an
   `other` row; an *Enable notifications* button that calls `Notification.requestPermission()` on the click and then
   notifies on each NEW waiting session. `FABRIK_DECK_CODE_PORT` supplies the code port.
6. Gate: the step-1 command — expect all green; plus a live smoke against a temp state dir:
   `curl -s -o /dev/null -w "%{http_code}" -H "Host: localhost:<port>" http://127.0.0.1:<port>/api/repos` — expect `200`.
7. Closing sequence: (1) gates green; (2) `python3 scripts/enforcement/check_doc_sync.py`; (3) **`/fabrik-review` on
   this phase's changed surface — BLOCKING, to its coverage-adjudicated exit**; (4) commit by explicit paths with trailers.

## Phase C — install (second unit), profile, launcher, docs

Appetite: 150

Implements spec § Chosen approach (Profile, Launcher), § Lifecycle (Supervision) and Tests 8-10.

**Interfaces.** Consumes: Phases A-B. Produces: `install` writes `fabrik-deck.service` (`ExecStart=/usr/bin/python3
<hub>/scripts/sysadmin/fabrik_deck.py serve`) beside `fabrik-deck-code.service`, both marker-led and verified before
any write; env defaults gain `FABRIK_DECK_PORT=8445` and `FABRIK_DECK_STATE=<home>/.local/state/fabrik-deck`
(absolute — systemd does not expand `~`); `install` backs up `~/.config/code-server/config.yaml` to
`~/.local/share/code-server/User/backups/` and writes `bind-addr`, `auth: none`, `cert: false` (mode kept 0600);
`profile`; `launcher --desktop DIR [--distro D] [--browser PATH]`; `up` (the .bat's WSL leg: export
`XDG_RUNTIME_DIR=/run/user/<uid>` when its bus socket exists — `scripts/sysadmin/agents_up.sh:289-293` — start any
inactive unit, print the Deck port).

**Behavior Contract.**
- Given a settings.json with other keys, When `profile` runs, Then a backup exists first, the listed keys hold the Deck's values and every other key is unchanged; a file that does not parse as JSON is left untouched and the run exits 1 (spec § Tests 8)
- Given an existing `Fabrik Deck.bat` without the marker, When `launcher` runs, Then it refuses (rc 2) and leaves the file; with the marker or no file, Then it writes CRLF ASCII text with the marker on line 2 (spec § Tests 9)
- Given a temp home, When `install` runs, Then both unit files carry `EnvironmentFile=%h/.config/fabrik-deck/env` and each passes `systemd-analyze --user verify` printing nothing (spec § Tests 10)
- Given a foreign file at either unit path, When `install` runs, Then it refuses before writing anything

**Steps.**
1. TDD: write the four tests; re-expect the single-unit tests — `tests/test_fabrik_deck.py:111` (UNIT), `:188`,
   `:219` (the appended tail), `:245`, `:265`, `:275`, `:329`, `:339`, `:369` (key list and stderr text `:380-391`),
   `:395` — each named in the step that changes it; run `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fabrik_deck.py` — expect the new ones to FAIL.
2. Generalise `_render_unit(hub, env_file, subcommand, description)`; loop the foreign check, the verify and the
   writes over both units, every check before the first write (the comment at `:228` binds); `--start` checks both ports.
3. `profile`: `json.loads`; on failure exit 1 naming the file; `mkdir` the backups folder; copy the file there with a
   timestamp; merge the spec's nine keys; `_atomic_write`.
4. `launcher`: the .bat text — `@echo off`, the marker line, then `for /f %%p in ('wsl.exe --distribution <d> --exec
   /usr/bin/python3 <hub>/scripts/sysadmin/fabrik_deck.py up') do set PORT=%%p`; a 30-try loop of
   `curl.exe -s -o NUL -w "%%{http_code}" http://localhost:%PORT%/` with `findstr 200` and `timeout /t 1`;
   `tasklist /FI "IMAGENAME eq vivaldi.exe" /NH | find /I "vivaldi.exe"` → when running, exit; else start Vivaldi with
   the board URL the first time (a marker file beside the .bat, written after the board answered) and with no URL
   afterwards. ASCII only, CRLF, refuse a non-marker file (`scripts/sysadmin/agents_bat.py:227-253`).
5. Docs: `docs/workstation/fabrik-deck.md` — the board, the hook and its measured cost, `profile`, the launcher (with
   the OneDrive desktop path, `docs/reference/repo-coordinator-rollout.md:287`), the three env variables, rollback
   (spec § Lifecycle, Retirement), the accepted auth-none exposure, and § Acceptance (below); `docs/CONFIGURATION.md` +
   `.env.example` — `FABRIK_DECK_PORT`, `FABRIK_DECK_CODE_PORT`, `FABRIK_DECK_STATE`; `INDEX.md` rows if a file is added.
6. Gate: `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fabrik_deck.py tests/test_install_user_hooks.py tests/test_hub_write_root.py` — expect all pass.
7. Closing sequence: (1) gates green; (2) `python3 scripts/enforcement/check_doc_sync.py`; (3) **`/fabrik-review` on
   this phase's changed surface — BLOCKING, to its coverage-adjudicated exit**; (4) commit by explicit paths with
   trailers; then `/fabrik-docs-review` over the plan's docs; then `python scripts/final_gate.py --check --json`
   (expect `"status": "success"` — necessary, not sufficient) and `python3 scripts/enforcement/check_convergence.py`.

## Post-merge order and acceptance (operator gate)

After the coordinator merges: (1) the hooks-index row is on master; (2) from the main checkout,
`python3 scripts/sysadmin/install_user_hooks.py` (new sessions pick the hook up at start); (3)
`python3 scripts/sysadmin/fabrik_deck.py install --start`, `profile`, `launcher --desktop "<desktop>"`. The spec's
OPEN unknowns (spec § Open / blocking unknowns rows 2-6: Vivaldi session restore, tiling reload, `localhost`
forwarding across `wsl --shutdown` and a Windows reboot, a second launch, memory per tab) need the operator's hands
and a reboot: the plan's last step hands § Acceptance to the coordinator as a gate (DECISION NEEDED, ground: gate —
destructive, the reboot ends every session), and its results land in the doc.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every phase, before its commit, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit; no phase moves on a first-pass green.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181): per slice one Sonnet and one
  Haiku finder, Opus or Fable orchestrating and executing every refutation.
- **Parallelism + merge** — the three phases are sequential (all edit `scripts/sysadmin/fabrik_deck.py` and
  `tests/test_fabrik_deck.py`); inside a phase the review's slices run in parallel and merge at the orchestrator's
  adjudication.

## File Scope (owned paths)

- scripts/sysadmin/fabrik_deck.py
- tests/test_fabrik_deck.py
- scripts/sysadmin/install_user_hooks.py
- tests/test_install_user_hooks.py
- docs/workstation/hooks-index.md
- docs/workstation/fabrik-deck.md
- docs/CONFIGURATION.md
- .env.example
- docs/development/reviews/2026-10-22-plan-1-fabrik-deck-review.md

## Evidence

Phase A — `scripts/sysadmin/install_user_hooks.py:29-68` (ENTRIES), `:103`, `:127-128`; `tests/test_install_user_hooks.py:74`;
`scripts/sysadmin/fabrik_deck.py:113-136`, `:262-284`. hooks-index.md mentions of the hook today:

```text
0
```

Phase B — `scripts/sysadmin/quota_dashboard.py:2806-2850`; `scripts/agent_status.py:209-242`; registry census (E2):

```text
52 entries; 50 paths exist
```

System python for the catalog (E1):

```text
yaml 6.0.1
```

Phase C — `scripts/sysadmin/fabrik_deck.py:154-172`, `:187-259`; `scripts/sysadmin/agents_bat.py:227-253`;
`scripts/sysadmin/agents_up.sh:289-293`. READ-set sizes (`wc -c`):

```text
 12428 scripts/sysadmin/fabrik_deck.py
 15541 tests/test_fabrik_deck.py
 10278 scripts/sysadmin/install_user_hooks.py
 15193 tests/test_install_user_hooks.py
  6294 docs/workstation/fabrik-deck.md
 87127 docs/workstation/hooks-index.md
151096 scripts/sysadmin/quota_dashboard.py
297957 total
```

External: Claude Code hooks — https://code.claude.com/docs/en/hooks (spec, 2026-10-21; re-fetched by grounder G1 via exa
2026-10-22: SessionEnd 1.5 s budget, PostToolUseFailure, two more Notification types). Vivaldi tiling —
https://help.vivaldi.com/desktop/tabs/tab-tiling/ (spec).

## Coverage Checklist

| Class | Verdict |
|---|---|
| Rubric classes (pasted below) | UNCHECKED |
| Recurrence: fail-open/fail-closed | UNCHECKED |
| Recurrence: boundary/sentinel/prefix | UNCHECKED |
| Recurrence: behavior-without-a-test | UNCHECKED |
| Recurrence: denominator on every count | UNCHECKED |

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- `POST /auth/passwordless/request` is ALREADY capped per email and per IP in Redis by the library (`AUTH_PASSWORDLESS_REQUEST_CAP`, `AUTH_PASSWORDLESS_IP_REQUEST_CAP`): tune those, add no second limiter, and never answer it with 429 — it returns 202 either way, so throttling never reveals an account. `POST /auth/passwordless/verify` has a per-code attempt cap (`AUTH_PASSWORDLESS_ATTEMPT_CAP`) but no per-IP bound; the project adds that bucket.
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/sysadmin/fabrik_deck.py, scripts/sysadmin/install_user_hooks.py, tests/test_fabrik_deck.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/workstation/fabrik-deck.md, docs/workstation/hooks-index.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_fabrik_deck.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.
# promote-to-check_* tail elided (review_rubric.py prints it here)
```

## Self-audit

- Grounding: three seats (G1 Opus researcher — hook and registration; G2 Sonnet — server and catalog; G3 Sonnet —
  profile, launcher, install), full notes in the run's SCRATCH folder (`grounding.md`). Found and folded: the
  Notification test at `tests/test_install_user_hooks.py:74`, the blocking hooks-index ordering, the `main()`
  fall-through, the missing stdin in `box.run`, no SSE precedent, the component-boundary repo match, JSONC risk in
  settings.json, `%` doubling in the .bat, and a red write-root test on master (fixed before this plan, 41db66900).
- (a) Coverage: spec Tests 1-2 → Phase A; 3-7 → Phase B; 8-10 → Phase C; R-P10 → Phase A; the docs → Phase C.
- (b) Signatures: `_state_dir`/`_env_path` produced in A and consumed in B-C under the same names; the attention
  file shape is the one B reads.
- Shape: a monolith of three phases, all on two shared files, so tickets would serialize; the plan runs past ~300
  lines only with the pasted rubric.

## Residual unknowns

- Resolved: PyYAML in system python (E1); hook registration mechanics (G1); the registry shape (E2).
- Open — the spec's acceptance rows 2-6 (Vivaldi restore, tiling reload, forwarding after `wsl --shutdown` and a
  Windows reboot, second launch, memory per tab): resolved by § Post-merge order and acceptance, an operator gate.
- Open — the two Notification types the spec does not list (`elicitation_url_dialog`, `agent_needs_input`): the plan
  keeps the spec's three; adding them is a spec amendment, raised to the coordinator if the acceptance shows a missed wait.
