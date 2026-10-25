---
description: "Pause every agent on the box for a hibernate: the hub coordinator finds each repo's live coordinator, sends one URGENT pause, collects a PAUSED line per agent, and says \"safe to hibernate\" only when every worktree is clean and pushed and no run is running. TRIGGER — EN: \"pause all agents, we need to hibernate\", \"/hibernate\"; TR: \"tüm ajanları durdur, hazırda bekletmemiz gerekiyor\". SKIP: pausing one agent. Stage: utility."
argument-hint: "[the operator's words, quoted — they ride into every pause]"
---
The operator runs `/hibernate` in the hub coordinator's window; `H=/opt/fabrik/scripts/sysadmin/hibernate.py` (`docs/reference/hibernate.md`) is the machinery. The run record, Orient and Phases are the hub coordinator's alone: a repo coordinator or an agent receiving the pause text opens no record and runs no Orient.

{{include:run-record}}
{{include:orient}}

## Phase 1 — the hub coordinator marks the pause and finds every agent

1. **Mark the pause**: `python3 $H mark --words "<the operator's words>"`, with no other run of yours running: it would stay `running` across the sleep.
2. **Find every agent, live**: `python3 $H targets`. A repo added tomorrow appears the moment its agents run — never edit a list. `claude -p` pool and review-seat sessions sit on the `pool:` line and are NEVER messaged.

## Phase 2 — the hub coordinator sends the pause and pauses itself

3. **Send the pause**, after `ListAgents` (use a `targets` peer name only if `ListAgents` shows it): ONE `SendMessage` per repo coordinator with `python3 $H brief --role coordinator --words "<the words>"`, verbatim; `brief --role agent` to each session of a repo whose row says to message each session, and each `outside /opt` session. Then pause yourself: commit and push, and close your OTHER runs; this run stays open until phase 4.

## Phase 3 — the hub coordinator collects and proves

4. **Collect** one `PAUSED — …` line per agent.
5. **Prove it**: `python3 $H status`; `BLOCKS` names why a row is not safe. Re-run it every 2 minutes for at most 15 minutes, nudging each agent a `BLOCKS` row names; untracked files never block.

## Phase 4 — the hub coordinator closes and tells the operator

6. **Close this run FIRST, so no record of yours is `running` when the box sleeps, then tell the operator.** The terminal is `status` printing `SAFE TO HIBERNATE` (close `done`, that output as evidence) or the 15-minute bound passing (close `blocked`, the blocking rows as reason). Then give one table — repo · agent · item · pushed sha · seed — and the last `status` output. Say **"safe to hibernate"** ONLY when `status` printed `SAFE TO HIBERNATE`; otherwise name each blocking row. `status` exiting 2 is never safe.

## If you are a repo's coordinator — the relay

Send the coordinator text's AGENT part verbatim to each live agent, pause yourself, and send their PAUSED lines to the hub in one reply, naming any agent silent for 15 minutes.

## If you are an agent — the pause

Do exactly the agent text's five steps: let your subagents finish before closing anything; close each live run in the first form your `command_run.py` accepts (`blocked --paused` · `handoff --resume` · `blocked` with the reason); write everything your next self needs to disk.

## After the wake

On any wake line run `python3 $H woke`: exit 0 (the box slept, or the hub lifted the pause) means resume the SAME item from its seed without being told again; exit 1 says why to stay put. The hub coordinator, once awake, ALWAYS runs `python3 $H lift`, then `targets`, and sends "RESUME — the hibernate is over" to every session.

{{include:close-chain}}
