# Coordinator rollout — the other /opt repos

The operator asked (D-1042) for one document covering every `/opt` repo other than `fabrik` and `fabrik-lib`, the
two that already work the coordinator way, with `web-ecommerce-factory` first. Each section says what the repo has
today and what it still needs. The steps are the runbook's, `docs/reference/repo-coordinator-rollout.md` (five phases, steps 1–17), adapted per repo;
"step N" below always means that runbook's step. The hub may not edit another repo: each repo's own agents do the
work, and the rollout mails stay with W-cf005f94.

## How this was measured

This page is a snapshot: before acting on a repo, run the runbook's pre-flight against it live (§ Before the first
phase), which takes minutes and supersedes anything below that has since changed. youtube and the tryton-crm
walkthrough were refreshed on 2026-10-20; the rest is the read-only inventory of 2026-10-19 (files read; `git worktree list`, `git status` and `git rev-list` only):

- **Population:** 44 git repos directly under `/opt`; minus `fabrik` and `fabrik-lib`, **42 documented**,
  `web-ecommerce-factory` first and the rest in case-insensitive alphabetical order.
- **Already in every one of the 42:** `scripts/work.py`; `.claude/hooks/agent_role.py`, registered in
  `.claude/settings.json`; `.claude/hooks/final_gate_stop.py`, byte-identical to the hub's; and the coordinator
  paragraph in `CLAUDE.md`. All arrive through the governance sync.
- **Missing in 41 of 42** (all 42 on 2026-10-19; youtube has added them since): `scripts/decisions.py`, charters
  starting `# Agent charter`, the step-8 rulings (D-943, D-1034, D-558, D-961; present only in youtube's charters),
  and a `.fabrik/session-agents.json` registry (optional: the launcher reads the builders' whoami bindings). `scripts/agent_status.py` is in none of the 42, and the runbook says not to vendor it yet.
- **`coordinator_mode` on:** 3 of 42 (`tryton-crm`, `web-ecommerce-factory`, and `youtube` since 2026-10-20).
  No `.fabrik/work/config.json` at all: 1 of 42 (`fabrik-test-saas-skeleton`).
- **Repos with agents on record** (a MERGE OWNER row or a named agent worktree): 7 of 42 on 2026-10-19, each
  with a full section, and youtube since (rolled out 2026-10-20), making 8 of 42. The other 34 get a short entry.
- **Worktrees:** 227 registered under `.claude/worktrees/` across the 42 repos, plus 27 registered
  elsewhere in 8 repos (9 still on disk). A name like `agent-<hash>` is the harness's own and marks a
  stale candidate. "Carry commits" counts each worktree's own `HEAD` against the repo's branch. "Changes in
  `git status`" counts untracked files too, so it is an upper bound on real uncommitted work.

## web-ecommerce-factory

- **Agents:** `wef1`, `wef2`, `wef3` (operator 2026-10-19, D-1042). `wef1` and `wef3` have worktrees; no worktree is named `wef2`, which fits a coordinator working in the main checkout. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `wef2` is the coordinator and merge owner (the operator's words, and its D-198 `MERGE OWNER: wef2`); `coordinator_mode` is on. No coordinator charter yet.
- **Worktrees:** 126 registered under `.claude/worktrees/`; named: `t03-contact-class`, `t05-regeneration-pilot`, `t07-imagery-worklist`, `t08-reachability`, `t09-descriptions-jsonld`, `t10-forms-gate`, `t11-legal-gate`, `wef1`, `wef1-t07`, `wef1-wp-pin`, `wef3`; 115 harness-named (`agent-<hash>`), stale candidates; 113 of 126 carry commits not on `mobasak/web-ecommerce-factory`; 126 of 126 show changes in `git status`. Builder worktrees not on their `worktree-<name>` branch (runbook step 10): `wef1` is on `wef1-audit-artifact-download`. Directories in `.claude/worktrees/` that are not worktrees: `wef1-w1-scratch`. 4 registered outside `.claude/worktrees/`; on disk: `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/fabrik-review-2026-10-14T15-32-00-0300/pin`, `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/fabrik-review-2026-10-15T04-48-13-0300/pin`, `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/fabrik-task-2026-10-14T15-01-42-0300/probe`, `/opt/web-ecommerce-factory/.tmp/runs/b612103c-fb2b-4bc3-8325-e4763823e5ba/t13d-probe`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): the coordinator stays `wef2`, the merge owner its ledger names (D-198): the launcher takes the coordinator from the ledger, so no rename is needed. Write `wef2.md` plus the `wef1` and `wef3` builder charters, each opening with `# Agent charter` and carrying the step-8 items listed as missing above; D-198 already makes `wef2` the merge owner, so no new row is needed; bind `wef1` and `wef3` in their worktrees per runbook step 9.
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
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): decide the coordinator from the ledger (the runbook's pre-flight, check 1) and write its charter and one charter per builder, each carrying the step-8 items listed as missing above; keep the merge owner the ledger names as the coordinator, with no new row (mint a superseding row only if the operator names a different coordinator); bind each builder in its worktree per runbook step 9.
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
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): decide the coordinator from the ledger (the runbook's pre-flight, check 1) and write its charter and one charter per builder, each carrying the step-8 items listed as missing above; keep the merge owner the ledger names as the coordinator, with no new row (mint a superseding row only if the operator names a different coordinator); bind each builder in its worktree per runbook step 9.
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
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): decide the coordinator from the ledger (the runbook's pre-flight, check 1) and write its charter and one charter per builder, each carrying the step-8 items listed as missing above; keep the merge owner the ledger names as the coordinator, with no new row (mint a superseding row only if the operator names a different coordinator); bind each builder in its worktree per runbook step 9.
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
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): decide the coordinator from the ledger (the runbook's pre-flight, check 1) and write its charter and one charter per builder, each carrying the step-8 items listed as missing above; keep the merge owner the ledger names as the coordinator, with no new row (mint a superseding row only if the operator names a different coordinator); bind each builder in its worktree per runbook step 9.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## trading-core

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. 1 registered outside `.claude/worktrees/`; on disk: `/home/ozgur/.traycer/worktrees/mobasak__trading-core/traycer-stellar-dolphin`. Phase 3's cleanup (runbook steps 10–12) applies to those now; when the repo gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## transdoc

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## triggered-content-orchestration

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## tryton-crm

- **Dry-run walkthrough, 2026-10-20 (read-only, the runbook's checks run as written; the proof for W-e413b79b):**
  - Pre-flight: `decisions.py --merge-owner` → `agent-1` (D-027), so the coordinator is `agent-1`; trunk
    `mobasak/tryton-crm` (config `base_branch` = the main checkout's branch; not `main`); `CLAUDE.md` synced (`cmp` 0),
    so step 8 goes into charters; `.gitignore` shows ` M` (uncommitted sync block: commit it first); builders `agent-2`,
    `agent-3`, each on its `worktree-agent-N` branch.
  - Phase 1: `scripts/work.py`, `agent_role.py` (registered once) and a stop hook identical to the hub's are present;
    `config.json` has `coordinator_mode`, `queue_floor`, `base_branch` and `distributor: agent-1`, and lacks
    `autonomy` and `feedback_owner`; `scripts/decisions.py` absent; `agent_status.py` absent and stays so; the
    `.gitignore` has no `/.fabrik/session-agents.json` line.
  - Phase 2: no `docs/reference/agents/`; D-027 already names `agent-1`, so step 7 mints nothing.
  - Phase 3: both builder worktrees have `.claude/settings.local.json` but without `claudeMdExcludes` (step 11 owed);
    three harness-named worktrees to list for the operator.
  - Launch: `agents_up.sh --print /opt/tryton-crm` on master (after infra's 53325487c) exits 0: `agent-1` is skipped
    as the merge owner, `agent-2` and `agent-3` get capped panes (`3G 1024`) in their worktrees, status `ok`, from
    their whoami bindings with no registry.
  - No step needed a question to the hub.
- **Agents:** From its records: `agent-1`, `agent-2`, `agent-3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `agent-1` is the merge owner (D-027) and, with `coordinator_mode` on, the coordinator. No coordinator charter yet.
- **Worktrees:** 5 registered under `.claude/worktrees/`; named: `agent-2`, `agent-3`; 3 harness-named (`agent-<hash>`), stale candidates; 3 of 5 carry commits not on `mobasak/tryton-crm`; 5 of 5 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): decide the coordinator from the ledger (the runbook's pre-flight, check 1) and write its charter and one charter per builder, each carrying the step-8 items listed as missing above; keep the merge owner the ledger names as the coordinator, with no new row (mint a superseding row only if the operator names a different coordinator); bind each builder in its worktree per runbook step 9.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## web-scraper

No agents recorded: no named agent worktree, no MERGE OWNER row, no session registry. Worktrees: none registered under `.claude/worktrees/`. When it gets agents it takes every phase of `docs/reference/repo-coordinator-rollout.md`.

## whatsapp-agent

- **Agents:** From its records: `wa1`, `wa2`, `wa3`. Session ids: none recorded (no `.fabrik/session-agents.json`).
- **Coordinator and merge owner:** `wa1` is the merge owner (D-002); `coordinator_mode` is off, so there is no coordinator yet.
- **Worktrees:** 2 registered under `.claude/worktrees/`; named: `wa2`, `wa3`; 0 of 2 carry commits not on `mobasak/whatsapp-agent`; 2 of 2 show changes in `git status`.
- **Missing against the runbook:** `.fabrik/work/config.json` keys `coordinator_mode`, `queue_floor`, `autonomy`, `feedback_owner`; `scripts/decisions.py`; charters in `docs/reference/agents/`, carrying (runbook step 8: a synced repo cannot edit its `CLAUDE.md`) the rulings D-943, D-1034, D-558 and D-961 and the coordinator named as holder of the bare mail arm; each builder bound in its worktree per runbook step 9.
- **Remaining steps:**
  1. Phase 1 (tooling, runbook steps 1–5): vendor and set what is missing above, through the repo's own gate.
  2. Phase 2 (roles, steps 6–9): decide the coordinator from the ledger (the runbook's pre-flight, check 1) and write its charter and one charter per builder, each carrying the step-8 items listed as missing above; keep the merge owner the ledger names as the coordinator, with no new row (mint a superseding row only if the operator names a different coordinator); bind each builder in its worktree per runbook step 9.
  3. Phase 3 (worktrees, steps 10–12): every builder on `worktree-<name>` with its `settings.local.json`; list every other worktree and directory named above with its branch, merged state and uncommitted work, remove only the merged and clean ones, and send the rest to the operator as one list through the coordinator.
  4. Phases 4–5 (steps 13–17): D-943 in every charter, sessions launched with `CLAUDE_CONFIG_DIR` and allow entries for any prompt, no Workflow tool, then `agents_up.sh` and the coordinator's first run (whoami, self-watch, score the backlog once, `work.py triage --apply`).

## youtube

- **Rolled out 2026-10-20, phases 1–3** (its report: hub mail `01M5CGP8FN`; operator: "youtube project, i want to make it coordinator managed, it has 3 agent windows").
- **Agents:** coordinator `youtube-coordinator` (D-063 `MERGE OWNER: youtube-coordinator`, superseding nothing);
  builders `yt1`, `yt2`, `yt3`, each bound in `.claude/worktrees/ytN` on `worktree-ytN`, all three in
  `.fabrik/session-agents.json`. Trunk `spec/video-classification-pipeline` (`base_branch`; `origin/main` lacks most of it).
- **Adaptations** (now in the runbook): rulings carried in all four charters (synced `CLAUDE.md`); `agent_status.py`
  not vendored; D-063 minted by hand; worktree `settings.local.json` without main's allow-list; the sync's `.gitignore`
  block committed on its own.
- **Remaining:** the operator opens `youtube-coordinator` in VS Code and renames the windows; `.kilo/worktrees/frost-nightshade`
  (merged, but its tree shows uncommitted deletions) goes to the operator through the coordinator.
