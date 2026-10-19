# Coordinator rollout — the other /opt repos

The operator asked (D-1042) for one document covering every `/opt` repo other than `fabrik` and `fabrik-lib`, the
two that already work the coordinator way, with `web-ecommerce-factory` first. Each section below says what the
repo has today and what it still needs. The steps themselves are the runbook's: `docs/reference/repo-coordinator-rollout.md`
(five phases, 17 steps), adapted per repo. The hub may not edit another repo; each repo's own agents do the work,
and the rollout mails stay with W-cf005f94.

## How this was measured

A read-only inventory on 2026-10-19 (files read, `git worktree list`, `git status` and `git rev-list` only):

- **Population:** 44 git repos directly under `/opt`; minus `fabrik` and `fabrik-lib`, **42 documented**.
- **Already in every one of the 42:** `scripts/work.py`, `.claude/hooks/agent_role.py` registered in
  `.claude/settings.json`, `.claude/hooks/final_gate_stop.py` byte-identical to the hub's, and the coordinator
  paragraph in `CLAUDE.md`. All of these arrive through the governance sync.
- **Missing in all 42:** `scripts/decisions.py`, `scripts/agent_status.py`, charters starting `# Agent charter`,
  and `.fabrik/session-agents.json`.
- **`coordinator_mode` on:** 2 of 42 (`tryton-crm`, `web-ecommerce-factory`).
  No `.fabrik/work/config.json` at all: 1 (`fabrik-test-saas-skeleton`).
- **Repos with agents on record** (a MERGE OWNER row or a named agent worktree): 7 of 42.
  The other 35 have one line each.
- **Worktrees:** 227 under `.claude/worktrees/` across the 42 repos. A name like `agent-<hash>` is the
  harness's own and marks a stale candidate. "Changes in `git status`" counts untracked files too, so it is an upper
  bound on real uncommitted work.

## web-ecommerce-factory

- **Agents:** `wef1`, `wef2`, `wef3` (operator 2026-10-19, D-1042). `wef1` and `wef3` have worktrees; no worktree is named `wef2`, which fits a coordinator working in the main checkout. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `wef2` is the coordinator and merge owner (the operator's words, and its D-198 `MERGE OWNER: wef2`). No coordinator charter yet.
- **Worktrees:** 126 under `.claude/worktrees/`; named: `t03-contact-class`, `t05-regeneration-pilot`, `t07-imagery-worklist`, `t08-reachability`, `t09-descriptions-jsonld`, `t10-forms-gate`, `t11-legal-gate`, `wef1`, `wef1-t07`, `wef1-wp-pin`, `wef3`; 115 harness-named (`agent-<hash>`), stale candidates; 113 carry commits not on `mobasak/web-ecommerce-factory`; 126 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write `wef2-coordinator.md` (or `wef2.md`) and the `wef1`/`wef3` builder charters, each opening with `# Agent charter`; D-198 already names `wef2`, so step 7 is a confirming row only if the coordinator takes a new name; register the three session ids.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## Reference_Creator

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## ai-model-catalog

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## apidoccreator

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## brand-identiy-creator

- **Agents:** From its records: `bic1`, `bic2`, `bic3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** D-024 names `bic1` the merge owner; there is no coordinator yet. Step 7 below supersedes that row with the coordinator.
- **Worktrees:** 19 under `.claude/worktrees/`; named: `bic2`, `bic3`; 17 harness-named (`agent-<hash>`), stale candidates; 14 carry commits not on `master`; 19 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write the coordinator and builder charters; mint the MERGE OWNER row for the coordinator; register every session id.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## calendar-orchestration-engine

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## candle

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## compliance-ops

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## email-reader

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## exam-coach

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## fabrik-citation-verifier

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## fabrik-claim-validator

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## fabrik-dr-store

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## fabrik-test-saas-skeleton

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## gmail-account-creator

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## image-generation

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## iterative_image_editor

- **Agents:** From its records: `iie1`, `iie2`, `iie3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** D-054 names `iie1` the merge owner; there is no coordinator yet. Step 7 below supersedes that row with the coordinator.
- **Worktrees:** 35 under `.claude/worktrees/`; named: `iie2`, `iie3`; 33 harness-named (`agent-<hash>`), stale candidates; 25 carry commits not on `master`; 35 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write the coordinator and builder charters; mint the MERGE OWNER row for the coordinator; register every session id.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## job-agent

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## llm_batch_processor

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## longephedia-vault

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## marketing-argumant-generator

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## meb

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## obsidian-agents

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## proposal-creator

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## proxy

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## rn-kit-sandbox

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## rnfinal

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## seo

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: 28 under `.claude/worktrees/`; 28 harness-named (`agent-<hash>`), stale candidates; 22 carry commits not on `mobasak/seo`; 28 show changes in `git status`. When it gets agents, it takes every phase below.

## session-recall

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## site-provisioner

- **Agents:** From its records: `sp1`, `sp2`, `sp3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** D-041 names `sp1` the merge owner; there is no coordinator yet. Step 7 below supersedes that row with the coordinator.
- **Worktrees:** 2 under `.claude/worktrees/`; named: `sp2`, `sp3`; 0 carry commits not on `main`; 2 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write the coordinator and builder charters; mint the MERGE OWNER row for the coordinator; register every session id.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## supplement-tracker-advisor

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## test-saas-platform

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## test-saas-scaffold

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## tojlo-mail

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## trade-intelligence

- **Agents:** From its records: `agent-1`, `agent-2`, `agent-3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** D-029 names `agent-1` the merge owner; there is no coordinator yet. Step 7 below supersedes that row with the coordinator.
- **Worktrees:** 10 under `.claude/worktrees/`; named: `agent-2`, `agent-3`; 8 harness-named (`agent-<hash>`), stale candidates; 9 carry commits not on `mobasak/trading-intelligence`; 10 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write the coordinator and builder charters; mint the MERGE OWNER row for the coordinator; register every session id.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## trading-core

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## transdoc

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## triggered-content-orchestration

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## tryton-crm

- **Agents:** From its records: `agent-1`, `agent-2`, `agent-3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** D-027 names `agent-1` the merge owner; there is no coordinator yet. Step 7 below supersedes that row with the coordinator.
- **Worktrees:** 5 under `.claude/worktrees/`; named: `agent-2`, `agent-3`; 3 harness-named (`agent-<hash>`), stale candidates; 3 carry commits not on `mobasak/tryton-crm`; 5 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write the coordinator and builder charters; mint the MERGE OWNER row for the coordinator; register every session id.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## web-scraper

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.

## whatsapp-agent

- **Agents:** From its records: `wa1`, `wa2`, `wa3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** D-002 names `wa1` the merge owner; there is no coordinator yet. Step 7 below supersedes that row with the coordinator.
- **Worktrees:** 2 under `.claude/worktrees/`; named: `wa2`, `wa3`; 0 carry commits not on `mobasak/whatsapp-agent`; 2 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`.
- **Remaining steps:**
  1. Phase 1 (tooling): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles): write the coordinator and builder charters; mint the MERGE OWNER row for the coordinator; register every session id.
  3. Phase 3 (worktrees): give each named builder its `settings.local.json`; list every other worktree with its branch, merged state and uncommitted work, remove only merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5: carry D-943 in every charter, launch with `agents_up.sh`, then the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## youtube

No agents recorded: no agent worktree, no MERGE OWNER row, no session registry. Worktrees: none under `.claude/worktrees/`. When it gets agents, it takes every phase below.
