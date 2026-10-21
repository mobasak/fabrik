# Spec review — the Fabrik Deck, a non-coding VS Code for many repos in one browser window (W-42d1ccb5)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-21-fabrik-deck-design.md`
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** DRAFT

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice R, rules: digest, code-grounded claims, fabrik-lib verdict, shape, constraints, 12-Factor) + sonnet×1 (slice P, the rest: personas → intake, approach logic, lifecycle, docs, unknowns) + sonnet×1 fabrik-researcher (slice F, the cited facts) · all axes | found: 31, new: 31, confirmed: 18, fixed: 18, unexecuted: 0, edits: 1 | method: citation — full pass; every candidate re-executed by the lead: `install_user_hooks.py:29-68` (ENTRIES has no matcher field) and `:133-141` (only `--check`/`--warn`), `10-python.md:22`, the Edge throttling doc raw-fetched ("applies to all cross-origin iframes, regardless of whether they're same-process or cross-process" — the judges' same-site argument was wrong), code-server 4.141.0's settings schema in `workbench.js` (enums executed), `ps` (the extension's `claude` runs under code-server's extension host, not in the browser), the Vivaldi tiling page raw-fetched, Vivaldi 8.2.4133.89 installed. With the coordinator's relayed input ("Vivaldi tiles any number of tabs natively … weigh it, do not assume") the approach was rewritten in one edit to Vivaldi tiling + a read-only Deck board; the dockview iframe shell moved to Rejected alternatives | 5eadfb4db3528066dc949e617f88f002 → c65a64da0e2c84505868634d1ff53663 |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over the rewrite | found: 17, new: 17, confirmed: 10, fixed: 10, unexecuted: 0, edits: 12 | method: re-derivation — R1-R9, P1-P15, F1-F7 dispositioned (FIXED/MOOT); new by the lead: MDN Secure Contexts raw-fetched ("Top-level documents provide a secure context when their URL is a potentially trustworthy URL", `http://localhost` "Secure (localhost URL)"), MDN Notification (user gesture), `http.server.ThreadingHTTPServer`, one port source (`--bind-addr`), `FABRIK_DECK_STATE`, the reload claim moved to an open unknown, the theme pinned to "Dark 2026" (`2026-dark.json` in code-server's bundle, executed `ls`; coordinator relay) | c65a64da0e2c84505868634d1ff53663 → cf52a690db851cdcc7a0f358b107e8f4 |
| Pass 3 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over the pass-2 hunks | found: 5, new: 5, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — counts re-derived from the table (Intake 17), `data/projects.yaml` 52, 3 `session-agents.json` files, the 11 kept env names against the start script; confirmed: "two env variables" (three exist), the launcher marker's timing and its retirement | cf52a690db851cdcc7a0f358b107e8f4 → 3d46a2101b5a0fbee1aecd3e955d49f5 |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners of slices R and P; F standing clean, no fact changed) · the pass-3 fixed set + the I18 systemd hunks | found: 6, new: 6, confirmed: 2, fixed: 2, unexecuted: 0, edits: 1 | method: re-derivation — Intake re-counted (18: 15 IN, 2 OUT, 1 split), every tmux mention read (4, all builders), `systemctl --user is-system-running` → running, `loginctl show-user ozgur` → Linger=yes (lead and slice R; slice P's call printed nothing), `~/.config/systemd/user/code-tunnel.service` read: confirmed `RestartSec=10` + `StartLimitIntervalSec=0` missing, and no `EnvironmentFile=` for the three variables | 3d46a2101b5a0fbee1aecd3e955d49f5 → ca7eba7fb00f6e3a3f2f6d0ecd1ed947 |

The scope-growth stop fired at Pass 3 (own-fix 10 of 10 at Pass 2, 2 of 2 at Pass 3). The run was paused for the operator's
/hibernate after Pass 3 and resumed 2026-10-21 19:51. On resume the coordinator relayed one more operator input (I18:
code-server must survive a WSL restart as a systemd user service, W-e89a9b5b); it is folded into Pass 4's hunks.

## Recorded, not confirmed

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| F1 | 2 | Rejected alternatives, the dockview row | RECORDED — measured (the Edge doc covers `display: none` and off-viewport frames; dockview hides with `visibility: hidden`, which it does not address — the inference only rejects an alternative, no design rests on it) |
| P-N1 | 2 | Chosen approach 4, the stale dot after a permission click | RECORDED — by design (P, round 2) (stated in the spec; cleared at `Stop`, `idle_prompt` re-marks) |
| P-N5 | 2 | Lifecycle, Growth | RECORDED — by design (P, round 2) (no hard cap; the build measures 6 tabs and the doc carries the number) |
| P-C3 | 3 | Profile, the Deck owns its listed keys | RECORDED — by design (P, round 3) (a later `profile` run restores the theme; the backup is taken first) |
| R-cosmetic | 2 | Constraints Digest, `40-documentation.md:67` quotes the trigger column only | RECORDED — measured (wording; changes no behaviour) |

## Ask ↔ spec

| # | Operator's / coordinator's words | What the spec says | Anchor | Verdict |
|---|---|---|---|---|
| 1 | "non coding version of vs code, vibe coding ide using vs code's claude extension for multiple repos" | each repo a full code-server workbench with the real Claude extension | Goal; Chosen approach 1 | IN |
| 2 | "single vs code looking window for any repos to open any agents in it" | one Vivaldi window, a tab per repo, opened from the board | Chosen approach 2-3 | IN |
| 3 | "i can have multiple tabs, also i can see some side by side or some as tabbed (not seen)" | Vivaldi tiling; hidden tabs keep their agent running server-side (`ps`) | Why this exists; Chosen approach 3 | IN |
| 4 | "no it should not bound password" | `auth: none`, accepted risk stated | Chosen approach 1; Constraints | IN |
| 5 | "our ip is dynamic not static" | localhost forwarding, no address in any config | External dependencies (WSL2 row) | IN |
| 6 | "i want same theme as like i use in vs code here, not white" | "Dark 2026", the desktop VS Code 1.130 default | Profile | CHANGED (Dark Modern → Dark 2026, coordinator relay) |
| 7 | "i want exact look and feel with vs code" | it IS VS Code inside each tab | I14 | IN |
| 8 | attention badge when a pane's agent waits (coordinator) | the board's dot + a browser notification, not a dot on each tab | Chosen approach 2, 4 | CHANGED (on the board, since browser tabs carry no badge) |
| 9 | layout remembered across reloads (coordinator) | Vivaldi session restore; verified at the build | I8; Open unknowns | IN |
| 10 | repo/agent list from the registries (coordinator) | `data/projects.yaml` + `/opt` + `session-agents.json` | Chosen approach 2 | IN |
| 11 | non-coding profile (coordinator) | the listed profile keys | Profile | IN |
| 12 | Desktop .bat launcher (coordinator) | `Fabrik Deck.bat` | Launcher | IN |
| 13 | box doc with rollback (coordinator) | `docs/workstation/fabrik-deck.md` | Documentation landing sites | IN |
| 14 | the router (coordinator) | out of scope | I13, I15 | DROPPED (W-ea993618) |
| 15 | "Vivaldi tiles any number of tabs natively … weigh it, do not assume" (coordinator) | chosen, weighed against the dockview shell | Chosen approach; Rejected alternatives | IN |
| 16 | "now all existing and new repos will support this setup ? if not they should." | the registry read with a plain-session fallback; rollout is W-a02d1c86 | I17 | IN (read) · DROPPED (rollout → W-a02d1c86) |
| 17 | "via vivaldi i cant reach the repos why?" — code-server as a systemd user service (coordinator) | two systemd user services, linger on | Lifecycle, Supervision; I18 | IN |
| — | (not asked) the attention hook | needed for item 8 | Chosen approach 4 | ADDED (the only documented signal) |
| — | (not asked) the Deck server's Host check and GET-only | needed by the auth-none exposure | Chosen approach 2; Constraints | ADDED (safety) |
