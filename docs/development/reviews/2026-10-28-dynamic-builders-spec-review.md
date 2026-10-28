# Spec review — dynamic disposable builders (W-b9ad80ae)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-28-dynamic-builders-design.md`
**Reviewer:** infra-3 (orchestrator; seats via the Agent tool — shape: agent-tool, D-961: the hub never calls Workflow)
**Status:** IN-PROGRESS

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (rule sections) + sonnet×1 (other sections) + opus×1 researcher (high-risk facts) + sonnet×1 researcher (other facts) · all axes · shape: agent-tool | found: 36, new: 36, confirmed: 33, fixed: 33, unexecuted: 0, edits: 33 | method: citation — full pass over the section partition; every candidate executed by the orchestrator (5 git/tmux probes in a throwaway repo and scratch tmux server, the Deck resolver read, commit and D-row existence checked); 1 refuted, 1 recorded, 1 duplicate | b67e58b1… → 44daeced… |

## Findings (pass 1)

| id | seat | finding | verdict | fix |
|---|---|---|---|---|
| P1-O1 | opus rule | `add` creating `session-agents.json` in a bindings-only repo drops every bound builder (agents_up.sh:199-200; 10 of 13 worktree repos have no registry) | CONFIRMED (code read at the pin) | D2: no file created where none exists; D9 |
| P1-O2 | opus rule | overflow windows named `agents` make every `=$S:agents` target ambiguous | CONFIRMED (scratch tmux: `can't find window: agents`, rc 1) | D4: windows `agents`, `agents-<n>` |
| P1-O3 | opus rule | concurrent `add` loses a registry row / doubles a name | CONFIRMED (no lock in the design) | D2: `flock` on `.fabrik/agents.lock` |
| P1-O4 | opus rule | no tmux server: `add` behaviour undefined; root not recorded | CONFIRMED (design gap) | D4: cold start builds the session |
| P1-O5 | opus rule | slice ceiling set only on a new grid, so the 2 GB floor reads an unset MemoryHigh | CONFIRMED (agents_up.sh:591-592 call slice_ceiling only before a new grid) | D4: cold start re-asserts the ceiling |
| P1-O6 | opus rule | tabs 2..n race tab 1 after a reboot; a down grid gets no tab | CONFIRMED (design text) | D5: `--window <n>` waits and creates the grouped session; every accepted repo gets tab 1 |
| P1-O7 | opus rule | `git worktree remove` deletes ignored `.tmp/runs` files `--porcelain` never shows | CONFIRMED (throwaway repo: file gone, rc 0) | D7: ignored files outside caches refuse |
| P1-O8 | opus rule | detached HEAD / failing `rev-list` read as pushed | CONFIRMED (`rev-list @{u}..HEAD` rc 128 detached) | D7: detached refuses; a failing git call refuses |
| P1-O9 | opus rule | run-record check under the registry id misses the bound id after /clear | CONFIRMED (design text vs rotate re-bind) | D7: every id the name owns |
| P1-O10 | opus rule | leftover `worktree-<name>` branch breaks re-`add` | CONFIRMED (`fatal: a branch named 'worktree-x' already exists`, rc 255) | D2: re-create only when merged, else refuse naming it |
| P1-O11 | opus rule | role fallback hands a coordinator a builder charter | CONFIRMED (`fabrik-lib-coordinator` strips to `fabrik-lib`) | D8: never for coordinator names |
| P1-O12 | opus rule | suppression spawn-only; relaunched builders meet the dialog | CONFIRMED (D3 said relaunch unchanged) | D3: suppression in `cmd_of` for every pane; Contract deltas restated |
| P1-O13 | opus rule | "can never differ" contradicts `--new`; resolver blocks `add` | CONFIRMED (text) | D1 reworded |
| P1-O14 | opus rule | "never `$WSL_DISTRO_NAME`" false vs the Deck resolver | CONFIRMED (fabrik_deck.py:892-901 reads it first) | D5: the Deck's order, one function |
| P1-O15 | opus rule | hand-written tabbed .bat refused without `--replace` | CONFIRMED (agents_bat.py:227-244) | D5: first run with `--replace` |
| P1-O16 | opus rule | refusal events have no sink; a logfile would break the digest row | CONFIRMED (text) | D6: `~/.claude/state/agents-spawn.jsonl`; Lifecycle |
| P1-O17 | opus rule | LANE not covered by the GREEN rule | CONFIRMED (CLAUDE.md quota bands) | D6: no spawn at LANE |
| P1-O18 | opus rule | a live pane with no row cannot be adopted | CONFIRMED (text) | D2: adopt by `@agent` + argv session flag |
| P1-S1 | sonnet | requirements 1.1/1.2 have no intake row | CONFIRMED (requirements :17-18) | I32, I33 |
| P1-S2 | sonnet | I19 destination hollow | CONFIRMED (no item) | W-ed781e7a filed |
| P1-S3 | sonnet | I22-I25 items still open | CONFIRMED (status open); SHA doubt REFUTED (all commits exist — `git cat-file -t`) | W-456aa02a, W-84ad2ff1, W-1783a9fe closed; W-1961cc42 closes with the build commit (its fix commit does not name it) |
| P1-S4 | sonnet | W-89474fc1 slice 1 undispositioned | CONFIRMED | I20 rewritten |
| P1-S5 | sonnet | tiebreak closed with no record | CONFIRMED | I27: the approval D-row records it |
| P1-S6 | sonnet | intake split does not reconcile | CONFIRMED (script count: 33 = 22 IN, 10 OUT, 1 split) | split line rewritten |
| P1-S7 | sonnet | persona quote elides sentences | REFUTED (the elision is marked `...`; characters match docs/DECISIONS.md row D-1301) | — |
| P1-S8 | sonnet | persona step 2 relies on an unproven `wt` append | CONFIRMED | Open unknown added; step text names the fallback |
| P1-S9 | sonnet | attach range cited two ways | CONFIRMED | I21 → agents_up.sh:548-590 |
| P1-S10 | sonnet | archive cite misses MAIN_GLOBS | CONFIRMED (archive_transcripts.py:101) | table row |
| P1-S11 | sonnet | session_orient.py and "generated charter" unaddressed | CONFIRMED | Decisions taken |
| P1-S12 | sonnet | refusal events sink | DUPLICATE of P1-O16 | — |
| P1-S13 | sonnet | empty `## Constraints` heading | CONFIRMED | heading removed |
| P1-R1 | opus researcher | "create-only" rests on a user's hedged comment | CONFIRMED (raw: "I believe `--session-id` is only for creating…") | D3, External dependencies |
| P1-R2 | opus researcher | `feedbackSurveyRate: 0` meaning off unverified | CONFIRMED (no doc says 0 = off) | key dropped; env var kept |
| P1-R3 | opus researcher | `skillOverrides` via `--settings` is an inference | RECORDED — by design (already § Open/blocking unknowns, live probe) | D3 says so |
| P1-R4 | sonnet researcher | claude-squad force-removal cited to its README, which never says it | CONFIRMED (raw worktree_ops.go) | citation to worktree_ops.go; `Cleanup()` named |
| P1-R5 | sonnet researcher | mu quote fuses its heading into the sentence | CONFIRMED | quote re-rendered |
| P1-R6 | sonnet researcher | settings-reference missing from the settings row | CONFIRMED | URL added |
