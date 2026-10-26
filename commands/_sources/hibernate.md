---
description: "Pause every agent on the box for a hibernate: finds each repo's live coordinator (never a hand list), sends one URGENT pause, collects a PAUSED line per agent, and says \"safe to hibernate\" only when every worktree is clean and pushed and no run is running. TRIGGER — EN: \"pause all agents, we need to hibernate\", \"/hibernate\"; TR: \"tüm ajanları durdur, hazırda bekletmemiz gerekiyor\". SKIP: pausing one agent (send it the agent text directly). Stage: utility."
argument-hint: "[the operator's words, quoted — they ride into every pause]"
---
The operator runs `/hibernate` in the hub coordinator's window; `scripts/sysadmin/hibernate.py` (`docs/reference/hibernate.md`) is the machinery, `H=/opt/fabrik/scripts/sysadmin/hibernate.py` below. The run record below, its Orient step and the Phase sections are the hub coordinator's alone: a repo coordinator or an agent receiving the pause text opens no record and runs no Orient for it.

{{include:run-record}}
{{include:orient}}

## Phase 1 — the hub coordinator marks the pause and finds every agent

1. **Mark the pause**: `python3 $H mark --words "<the operator's words>"`. It starts a fresh pause, so a wake from an earlier one never counts. Open `/hibernate` with no other run of yours running: a run under this one would stay `running` across the sleep, and `status` blocks on it.
2. **Find every agent, live**: `python3 $H targets`. One block per repo: its coordinator (the ledger's merge owner) and peer name, and every other live agent session. A repo added tomorrow appears the moment its agents run — never edit a list. `claude -p` pool and review-seat sessions sit on the `pool:` line and are NEVER messaged.

## Phase 2 — the hub coordinator sends the pause and pauses itself

3. **Send the pause**, `ListAgents` first (peer names change when a session restarts; use the name `targets` printed only if `ListAgents` shows it): for each repo whose row names a coordinator, ONE `SendMessage` to that peer with the output of `python3 $H brief --role coordinator --words "<the words>"`, verbatim; the output of `brief --role agent` to each session of a repo whose row says to message each session (no live coordinator, two sessions holding the name, or your own repo) and each `outside /opt` session. Then pause yourself: finish your step, commit and push what you hold, and close your OTHER runs; this `/hibernate` run stays open until phase 4.

## Phase 3 — the hub coordinator collects and proves

4. **Collect** one `PAUSED — …` line per agent (a coordinator relays its agents' lines).
5. **Prove it**: `python3 $H status` — one row per live agent, yours included (marked `(you)`; this `/hibernate` run is the one run not counted); `BLOCKS` names why (a run still `running`, an unreadable run record, uncommitted changes, unpushed commits, a branch on no remote, no usable cwd). Re-run it every 2 minutes for at most 15 minutes, nudging each agent a `BLOCKS` row names; untracked files are counted in the row but never block.

## Phase 4 — the hub coordinator closes and tells the operator

6. **Close this run, then tell the operator:** the terminal is `status` printing `SAFE TO HIBERNATE` (close `done`, its evidence that output) or the 15-minute bound passing (close `blocked`, its reason the blocking rows) — close FIRST, so no record of yours is `running` when the box sleeps. Then one table — repo · agent · item · pushed sha · seed — from the PAUSED lines, and the last `status` output. Say **"safe to hibernate"** ONLY when `status` printed `SAFE TO HIBERNATE`; otherwise name each blocking row. `status` exiting 2 (no live session found, no session id, or you are not among them) is never safe.

## If you are a repo's coordinator — the relay

Send the coordinator text's AGENT part verbatim to each live agent, pause yourself the same way, collect their PAUSED lines, and send them to the hub in one reply, naming any agent silent for 15 minutes.

## If you are an agent — the pause

Do exactly the agent text's five steps. The important ones: let your own subagents and seats finish before you close anything; close each live run in the first form your `command_run.py` accepts (`blocked --paused` · `handoff --resume` · `blocked` with the reason); and write everything your next self needs to disk — the wake drops your cached prompt, so the seed, the RESUME note and memory are all you will have.

## After the wake

On any wake line (the self-watch may still word a sleep as "the fleet-quota hold LIFTED") run `python3 $H woke`: exit 0 (the box slept, or the hub lifted the pause) means resume the SAME item from its seed without being told again; exit 1 says why to stay put (no wake yet, or you already resumed). The hub coordinator, once awake, ALWAYS runs `python3 $H lift`, then `targets`, and sends "RESUME — the hibernate is over" to every session: a relaunched session sits idle until prompted.

{{include:close-chain}}
