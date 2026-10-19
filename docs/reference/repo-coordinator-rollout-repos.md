# Coordinator rollout — the other /opt repos

The operator asked (D-1042) for one document covering every `/opt` repo other than `fabrik` and `fabrik-lib`, the
two that already work the coordinator way, with `web-ecommerce-factory` first. Each section says what the repo has
today and what it still needs. The steps are the runbook's, `docs/reference/repo-coordinator-rollout.md` (five phases, steps 1–17), adapted per repo;
"step N" below always means that runbook's step. The hub may not edit another repo: each repo's own agents do the
work, and the rollout mails stay with W-cf005f94.

## How this was measured

A read-only inventory on 2026-10-19 (files read; `git worktree list`, `git status` and `git rev-list` only):

- **Population:** 44 git repos directly under `/opt`; minus `fabrik` and `fabrik-lib`, **42 documented**,
  `web-ecommerce-factory` first and the rest in case-insensitive alphabetical order.
- **Already in every one of the 42:** `scripts/work.py`; `.claude/hooks/agent_role.py`, registered in
  `.claude/settings.json`; `.claude/hooks/final_gate_stop.py`, byte-identical to the hub's; and the coordinator
  paragraph in `CLAUDE.md`. All arrive through the governance sync.
- **Missing in all 42:** `scripts/decisions.py`, `scripts/agent_status.py`, charters starting `# Agent charter`,
  `.fabrik/session-agents.json`. The `CLAUDE.md` rulings of step 8 (D-943, D-558, D-961): present in 0 of 42.
- **`coordinator_mode` on:** 2 of 42 (`tryton-crm`, `web-ecommerce-factory`).
  No `.fabrik/work/config.json` at all: 1 of 42 (`fabrik-test-saas-skeleton`).
- **Repos with agents on record** (a MERGE OWNER row or a named agent worktree): 7 of 42, each
  with a full section. The other 35 get a short entry.
- **Worktrees:** 227 registered under `.claude/worktrees/` across the 42 repos, plus 27 registered
  elsewhere in 8 repos (9 still on disk). A name like `agent-<hash>` is the harness's own and marks a
  stale candidate. "Carry commits" counts each worktree's own `HEAD` against the repo's branch. "Changes in
  `git status`" counts untracked files too, so it is an upper bound on real uncommitted work.

## web-ecommerce-factory

- **Agents:** `wef1`, `wef2`, `wef3` (operator 2026-10-19, D-1042). `wef1` and `wef3` have worktrees; no worktree is named `wef2`, which fits a coordinator working in the main checkout. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `wef2` is the coordinator and merge owner (the operator's words, and its D-198 `MERGE OWNER: wef2`); `coordinator_mode` is on. No coordinator charter yet.
- **Worktrees:** 126 registered under `.claude/worktrees/`; named: `t03-contact-class`, `t05-regeneration-pilot`, `t07-imagery-worklist`, `t08-reachability`, `t09-descriptions-jsonld`, `t10-forms-gate`, `t11-legal-gate`, `wef1`, `wef1-t07`, `wef1-wp-pin`, `wef3`; 115 harness-named (`agent-<hash>`), stale candidates; 113 of 126 carry commits not on `mobasak/web-ecommerce-factory`; 126 of 126 show changes in `git status`. Builder worktrees not on their `worktree-<name>` branch (runbook step 10): `wef1` is on `wef1-audit-artifact-download`. Directories in `.claude/worktrees/` that are not worktrees: `wef1-w1-scratch`. 4 registered outside `.claude/worktrees/`; on disk: `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/fabrik-review-2026-10-14T15-32-00-0300/pin`, `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/fabrik-review-2026-10-15T04-48-13-0300/pin`, `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/fabrik-task-2026-10-14T15-01-42-0300/probe`, `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/t13d-probe`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): name the coordinator `wef2-coordinator` — `agents_up.sh` gives no pane only to a name ending in `-coordinator`, and `agent_role.py` loads `docs/reference/agents/<name>.md` — and write that charter plus the `wef1` and `wef3` builder charters, each opening with `# Agent charter`; mint the row `supersedes D-198: MERGE OWNER: wef2-coordinator`; adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register the three session ids.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## ai-model-catalog

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. 1 registered outside `.claude/worktrees/`; 1 whose directory is gone (prunable). Phase 3's cleanup (runbook steps 10–12) applies to those now; when the repo gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## apidoccreator

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## brand-identiy-creator

- **Agents:** From its records: `bic1`, `bic2`, `bic3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `bic1` is the merge owner (D-024); `coordinator_mode` is off, so there is no coordinator yet.
- **Worktrees:** 19 registered under `.claude/worktrees/`; named: `bic2`, `bic3`; 17 harness-named (`agent-<hash>`), stale candidates; 14 of 19 carry commits not on `master`; 19 of 19 show changes in `git status`. 17 registered outside `.claude/worktrees/`; 17 whose directory is gone (prunable).
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): write the `<repo>-coordinator` charter and one charter per builder; mint the row that supersedes the current MERGE OWNER row (or the first one); adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register every session id.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## calendar-orchestration-engine

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## candle

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## compliance-ops

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## email-reader

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## exam-coach

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## fabrik-citation-verifier

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. 1 registered outside `.claude/worktrees/`; on disk: `/home/ozgur/.traycer/worktrees/local__fabrik-citation-verifier__a1cd4a60ef/traycer-fabrik-citation-verifier-chipper-leopard`. Phase 3's cleanup (runbook steps 10–12) applies to those now; when the repo gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## fabrik-claim-validator

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## fabrik-dr-store

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## fabrik-test-saas-skeleton

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## gmail-account-creator

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## image-generation

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## iterative_image_editor

- **Agents:** From its records: `iie1`, `iie2`, `iie3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `iie1` is the merge owner (D-054); `coordinator_mode` is off, so there is no coordinator yet.
- **Worktrees:** 35 registered under `.claude/worktrees/`; named: `iie2`, `iie3`; 33 harness-named (`agent-<hash>`), stale candidates; 29 of 35 carry commits not on `master`; 35 of 35 show changes in `git status`. 1 registered outside `.claude/worktrees/`; on disk: `/home/ozgur/.traycer/worktrees/mobasak__iterative_image_editor/traycer-tidy-hawk`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): write the `<repo>-coordinator` charter and one charter per builder; mint the row that supersedes the current MERGE OWNER row (or the first one); adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register every session id.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## job-agent

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## llm_batch_processor

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## longephedia-vault

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## marketing-argumant-generator

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## meb

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## obsidian-agents

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## proposal-creator

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## proxy

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## Reference_Creator

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## rn-kit-sandbox

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## rnfinal

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## seo

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: 28 registered under `.claude/worktrees/`; 28 harness-named (`agent-<hash>`), stale candidates; 22 of 28 carry commits not on `mobasak/seo`; 28 of 28 show changes in `git status`. Phase 3's cleanup (runbook steps 10–12) applies to those now; when the repo gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## session-recall

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## site-provisioner

- **Agents:** From its records: `sp1`, `sp2`, `sp3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `sp1` is the merge owner (D-041); `coordinator_mode` is off, so there is no coordinator yet.
- **Worktrees:** 2 registered under `.claude/worktrees/`; named: `sp2`, `sp3`; 0 of 2 carry commits not on `main`; 2 of 2 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): write the `<repo>-coordinator` charter and one charter per builder; mint the row that supersedes the current MERGE OWNER row (or the first one); adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register every session id.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## supplement-tracker-advisor

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## test-saas-platform

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## test-saas-scaffold

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## tojlo-mail

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## trade-intelligence

- **Agents:** From its records: `agent-1`, `agent-2`, `agent-3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `agent-1` is the merge owner (D-029); `coordinator_mode` is off, so there is no coordinator yet.
- **Worktrees:** 10 registered under `.claude/worktrees/`; named: `agent-2`, `agent-3`; 8 harness-named (`agent-<hash>`), stale candidates; 9 of 10 carry commits not on `mobasak/trading-intelligence`; 10 of 10 show changes in `git status`. 1 registered outside `.claude/worktrees/`; on disk: `/opt/trade-intelligence/.kilo/worktrees/berry-oatmeal`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): write the `<repo>-coordinator` charter and one charter per builder; mint the row that supersedes the current MERGE OWNER row (or the first one); adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register every session id.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## trading-core

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. 1 registered outside `.claude/worktrees/`; on disk: `/home/ozgur/.traycer/worktrees/mobasak__trading-core/traycer-stellar-dolphin`. Phase 3's cleanup (runbook steps 10–12) applies to those now; when the repo gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## transdoc

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## triggered-content-orchestration

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## tryton-crm

- **Agents:** From its records: `agent-1`, `agent-2`, `agent-3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `agent-1` is the merge owner (D-027) and, with `coordinator_mode` on, the coordinator. No coordinator charter yet.
- **Worktrees:** 5 registered under `.claude/worktrees/`; named: `agent-2`, `agent-3`; 3 harness-named (`agent-<hash>`), stale candidates; 3 of 5 carry commits not on `mobasak/tryton-crm`; 5 of 5 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): write the `<repo>-coordinator` charter and one charter per builder; mint the row that supersedes the current MERGE OWNER row (or the first one); adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register every session id.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## web-scraper

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## whatsapp-agent

- **Agents:** From its records: `wa1`, `wa2`, `wa3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `wa1` is the merge owner (D-002); `coordinator_mode` is off, so there is no coordinator yet.
- **Worktrees:** 2 registered under `.claude/worktrees/`; named: `wa2`, `wa3`; 0 of 2 carry commits not on `mobasak/whatsapp-agent`; 2 of 2 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; `scripts/agent_status.py`; charters in `docs/reference/agents/`; `.fabrik/session-agents.json`; the `CLAUDE.md` adoption of D-943, D-558, D-961 (runbook step 8).
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): write the `<repo>-coordinator` charter and one charter per builder; mint the row that supersedes the current MERGE OWNER row (or the first one); adopt the step-8 rulings (D-943, D-558, D-961, and the coordinator as holder of the bare mail arm) in `CLAUDE.md`; register every session id.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## youtube

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. 1 registered outside `.claude/worktrees/`; on disk: `/opt/youtube/.kilo/worktrees/frost-nightshade`. Phase 3's cleanup (runbook steps 10–12) applies to those now; when the repo gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.
