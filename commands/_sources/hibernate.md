---
description: "Pause every agent on the box for a hibernate — the hub coordinator finds each repo's live coordinator (its ledger's merge owner, never a hand list), sends one URGENT pause, collects a PAUSED line per agent, and says \"safe to hibernate\" only when every agent's worktree is clean and pushed and no run is running; after the wake every agent resumes its own item. TRIGGER — EN: \"pause all agents, we need to hibernate\", \"/hibernate\"; TR: \"tüm ajanları durdur, hazırda bekletmemiz gerekiyor\". SKIP: pausing one agent (send it the agent text directly). Stage: utility."
argument-hint: "[the operator's words, quoted — they ride into every pause]"
---
**The operator runs `/hibernate` in the hub coordinator's window.** The machinery is `scripts/sysadmin/hibernate.py`
(`docs/reference/hibernate.md`); this command sequences it. `H=/opt/fabrik/scripts/sysadmin/hibernate.py` below.
The run record below and the Phase sections are the hub coordinator's alone: a repo coordinator or an agent
receiving the pause text opens none for it.

## Phase 1 — the hub coordinator marks the pause and finds every agent

1. **Mark the pause**: `python3 $H mark --words "<the operator's words>"`. It starts a fresh pause, so a wake from an
   earlier one never counts.
2. **Find every agent, live**: `python3 $H targets`. One block per repo: its coordinator (the ledger's merge owner)
   and peer name, and every other live agent session. A repo added tomorrow appears the moment its agents run — never
   edit a list. `claude -p` pool and review-seat sessions are counted on the `pool:` line and are NEVER messaged.

## Phase 2 — the hub coordinator sends the pause and pauses itself

3. **Send the pause** (`ListAgents` first — peer names change when a session restarts; use the name `targets` printed
   only if `ListAgents` shows it):
   - each repo whose row names a coordinator: ONE `SendMessage` to that peer with the output of
     `python3 $H brief --role coordinator --words "<the words>"`, verbatim;
   - each repo whose row says to message each session (no live coordinator, two sessions holding the name, or your own
     repo) and each `outside /opt` session: the output of `brief --role agent`, to each session;
   - then pause yourself: finish your step, commit and push what you hold, and close your OTHER runs — this
     `/hibernate` run stays open until phase 4.

## Phase 3 — the hub coordinator collects and proves

4. **Collect** one `PAUSED — …` line per agent (a coordinator relays its agents' lines).
5. **Prove it**: `python3 $H status` — one row per live agent, yours included (marked `(you)`; your own run is the one
   not counted); `BLOCKS` names why (a run still `running`, an unreadable run record, uncommitted changes, unpushed
   commits, a branch on no remote, no usable cwd). Re-run it every 2 minutes for at most 15 minutes, nudging the agent
   each `BLOCKS` row names; untracked files are counted in the row but never block.

## Phase 4 — the hub coordinator closes and tells the operator

6. **Close this run, then tell the operator**: the terminal is `status` printing `SAFE TO HIBERNATE` (close `done`,
   its evidence that output) or the 15-minute bound passing (close `blocked`, its reason the blocking rows) — close
   FIRST, so no record of yours is `running` when the box sleeps. Then one table — repo · agent · item · pushed sha ·
   seed — from the PAUSED lines, and the last `status` output. Say **"safe to hibernate"** ONLY when `status` printed
   `SAFE TO HIBERNATE`; otherwise name each blocking row. `status` exiting 2 (no live session found, no session id, or
   you are not among them) is never safe.

## If you are a repo's coordinator — the relay

You received the coordinator text. Send its AGENT part verbatim to each of your live agents, pause yourself the same
way, collect their PAUSED lines, and send them to the hub in one reply (name any agent that did not answer in 15
minutes).

## If you are an agent — the pause

You received the agent text: do exactly its five steps. The important ones: let your own subagents and seats finish
before you close anything; close each live run in the first form your `command_run.py` accepts (`blocked --paused` ·
`handoff --resume` · `blocked` with the reason); and write everything your next self needs to disk — the wake drops
your cached prompt, so the seed, the RESUME note and memory are all you will have.

## After the wake

Any wake line (the self-watch may still word a sleep as "the fleet-quota hold LIFTED") → run `python3 $H woke`.
Exit 0 means the box slept (or the hub lifted the pause): resume the SAME item from its seed without being told again.
Exit 1 says why to stay put (no wake yet, or you already resumed). The hub coordinator, once awake, ALWAYS runs
`python3 $H lift` (a sleep during a fleet-quota hold writes no resume-wake row, and a pause with no sleep writes none
either), then `targets`, and sends "RESUME — the hibernate is over" to every session: a relaunched session sits idle
until prompted.

{{include:run-record}}

{{include:close-chain}}
