# Operator requirements — coordinators and agents (every repo)

The operator's requirements for how coordinators and builder agents work, collected 2026-10-28. **Scope:
every repo on the box, not only the hub** (operator, 2026-10-28: "i want these mechanism for all repos not
only fabrik."). Source: the hub coordinator's session `3f001c89-2b6a-4287-ad10-33eef762a282` (searchable
through session-recall), including the operator's messages typed mid-turn; a rule relayed from an earlier
day is marked with its record.

The **Operator's words** column is verbatim, typos included; a line break inside a message is shown as one space. Where it holds anything else, the cell says
so: *coordinator's text the operator approved*, *relayed* (from a decision row), or *coordinator's
reading*. Rows marked *proposed* are the coordinator's suggestions, not the operator's.

## 1. Who does what

| # | Requirement | Operator's words | Record |
|---|---|---|---|
| 1.1 | The operator does the one-time steps only the operator can do; after that the coordinators handle all interaction with tmux, agents and sessions. *Coordinator's reading of "what needed ones": settings allow rules and Claude Code's auto-mode environment setup.* | "i will do what needed ones, then coordinators will take of interacting with tmux, agents etc ok?" | — |
| 1.2 | Coordinators handle without the operator the steps Claude Code's safety check refuses (settings-file edits, launches flagged "Unauthorized Persistence"); settled by 1.1 (*coordinator's reading*: the operator's one-time setup removes those refusals) | "as being coordinator you should handle these without me, can you do that?" | — |
| 1.3 | No agent asks the operator anything; every question, including Claude Code's own UI prompts, goes to its coordinator | "they should not ask me any questions, all agents must ask to their coordinators. example \"Teach auto mode about your environment? Auto mode works better when it knows your environment. Takes about a minute.\"" | D-1301 |

## 2. Coordinator continuity (no hand-pasting)

The operator's order is "ok make this happen for all repos NOW", given about the coordinator's text quoted in
rows 2.1–2.4, which the operator pasted back with that order. The coordinator's text is: "stop hand-pasting.
When a coordinator rotates, it writes the handoff text to one file, and the session-start hook prints that
file into the new session. Launching the window with CLAUDE_AGENT=coordinator also removes the bind step.
Then a /clear or crash needs nothing from you."

| # | Requirement | Operator's words | Record |
|---|---|---|---|
| 2.1 | Before rotating, a coordinator writes its handoff to one file | *coordinator's text the operator approved:* "When a coordinator rotates, it writes the handoff text to one file" | W-835894a6 |
| 2.2 | The session-start hook prints that file into the new session | *coordinator's text the operator approved:* "the session-start hook prints that file into the new session" | W-835894a6 |
| 2.3 | The coordinator window launches with `CLAUDE_AGENT=coordinator`, so no bind step is typed | *coordinator's text the operator approved:* "Launching the window with CLAUDE_AGENT=coordinator also removes the bind step." | W-835894a6 |
| 2.4 | A `/clear` or a crash needs nothing from the operator | *coordinator's text the operator approved:* "Then a /clear or crash needs nothing from you." | W-835894a6 |
| 2.5 | Done at once, in every repo | "ok make this happen for all repos NOW" | W-835894a6 |
| 2.6 | The hub coordinator is not rotated until 2.1–2.4 are implemented | "before it is implemented, i will not rotate you." | — |

## 3. Dynamic, disposable builder agents

| # | Requirement | Operator's words | Record |
|---|---|---|---|
| 3.1 | Every coordinator creates new agents when needed | "as being coordinator, you and any coordinator. i want you to be able to create new agents when needed" | D-1301, D-1128, W-b9ad80ae |
| 3.2 | Each new agent gets a proper charter | "give them proper charters" | D-1301, D-1128 |
| 3.3 | The coordinator uses them, and clears them when they finish | "use them, when they finish clear them" | D-1301 |
| 3.4 | The agent count adjusts dynamically to the work | "so dynamically adjust needed agent count" | D-1301; *relayed* from D-1092: no fixed count, quota and memory are the ceiling |
| 3.5 | Agents bind and wire themselves properly at launch | "they must bind/wire themselves properly" | D-1301 |
| 3.6 | Agents are disposable working units | "you must use the agents as disposable working units" | D-1301 |
| 3.7 | A cleared agent's session stays stored in B2 and searchable through session-recall | "but their sessions are stored in b2 and sesssion recall can be used to search their chat history" | D-1301, D-736, D-1182 |
| 3.8 | "All Agents (tabbed).bat" always shows the live agent set, for all repos | "also i want to see them always uptodate in All Agents (tabbed).bat for all repos" | D-1301, D-1128 |

### Coordinator suggestions (*proposed*; the operator asked "what other suggestions you can add to these?")

| # | Suggestion |
|---|---|
| 3.9 | One agent registry per repo as the single source for the tmux grid, the `.bat` and the charters |
| 3.10 | Charters generated from role templates (builder, reviewer, researcher), with the item and beat filled in at spawn |
| 3.11 | Agent names that carry their work (for example `b-W1234`), so the grid, `ListAgents` and session-recall show what each did |
| 3.12 | Automatic sizing: spawn when ready top-priority items outnumber free builders and the quota band is GREEN; retire idle builders; cap by box memory (1.3–3.6 GB per Claude session, from infra's 2026-10-27 kill-wave report to the coordinator, in this doc's source session) |
| 3.13 | A disposable agent writes its resume point into the item's seed, not its personal memory, so any fresh agent can resume the item |
| 3.14 | Claude Code settings pre-set so tips and onboarding prompts never appear; any prompt that still appears is answered by the coordinator in the pane |
| 3.15 | A status line per tab showing each pane's item, context % and quota band |

## 4. Working rules for coordinators

| # | Requirement | Operator's words | Record |
|---|---|---|---|
| 4.1 | No coordinator, in any repo, now or later, blocks a turn on a long wait; merges, queues and API runs run in the background and their notification wakes the coordinator | *relayed (2026-10-27):* "while you and any coordinator waiting a background run, i cant reach you." / "not only you, all coordinators should not block for long waits" / "existing and future" | D-1296 |
| 4.2 | Finish the lean rewrite of the command files, fastest way | "ok finish them asap in a fastest way."; "2 finish the command edits asap in a fastest way." | W-96f36043 |
| 4.3 | The lean rewrite runs on API and cloud credits first, then Max quota, and keeps every rule | *relayed (2026-10-27)* | D-1293; W-8d2815a8 answered A |
| 4.4 | Report plainly whether the lean edits are finished; when they finish, pause all agents | *relayed (2026-10-27):* "tell me lean edits are finished or not; when they finish PAUSE ALL AGENTS" | the hub coordinator's resume note, 2026-10-27 13:45 section |
| 4.5 | Remove the hold on merges and complete all merges | "1. remove the block, complete all merges" | — |
| 4.6 | Fix master's lint ratchet red | "secondly finish  master lint ratchet red until kaizen's fix (01M5YYJ577) merges too" | W-4059f92e; merged as a0546ad5a |
| 4.7 | After finishing, list the urgent tasks still open | "then tell me what urgent tasks/work remained in fabrik list them" | — |
| 4.8 | bhdtrade.com is not deployed (not ready) | *relayed (2026-10-27)* | D-1292 |
| 4.9 | Who gets scarce quota first is the coordinator's call, never the operator's | *relayed (2026-10-23):* "you are the coordinator you must manage who gets it first." | D-1174 |

## 5. The box-wide kill waves

| # | Requirement | Operator's words | Record |
|---|---|---|---|
| 5.1 | Find what caused code-server's "cannot reconnect" error and the loss of every agent from "All Agents (tabbed).bat" | "which idiot caused cannot reconnect error here ?"; "i keep getting cannot reconnect please reload window error and also in All Agents (tabbed).bat i lost all active agents what is going on ?" | W-d87cebbb |
| 5.2 | Finding and fixing the root cause of the SIGTERM waves (2026-10-27 16:43:20 and 17:02:09, +03:00) is top priority | "have you found the root cause? and fixed it now? this is top priority item now." | W-d87cebbb |
| 5.3 | Before a deliberate repro, every coordinator pauses its agents, knowing a WSL shutdown may happen, and each records where it left off | "first ask all coordinators to pause their agents by knowing a wsl shutdown might happen and they need to remember where they have left, then we can trigger" | W-5d59cf35 (the operator's answer) |
| 5.4 | No agent runs until the operator lifts the hold. Lifted on 2026-10-28 for: merges, the lean rewrite and the lint fix (4.2, 4.5, 4.6); the continuity mechanism (§2, "ok make this happen for all repos NOW"); and, *coordinator's reading*, the disposable-agents mechanism (§3), which the operator asked for after the hold | "do not run any agent yet" | — |

## Related

- Coordinator role: `docs/reference/agents/coordinator.md` and the coordinator paragraph in `CLAUDE.md` § Orient.
- Rolling the coordinator model out to a repo: `docs/reference/repo-coordinator-rollout.md`.
- Launcher and grid: `scripts/sysadmin/agents_up.sh`, `scripts/sysadmin/agents_bat.py`.
