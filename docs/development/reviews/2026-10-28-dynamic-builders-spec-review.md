# Spec review — dynamic disposable builders (W-b9ad80ae)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-28-dynamic-builders-design.md`
**Reviewer:** infra-3 (orchestrator; seats via the Agent tool — shape: agent-tool, D-961: the hub never calls Workflow)
**Status:** CONVERGED

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (rule sections) + sonnet×1 (other sections) + opus×1 researcher (high-risk facts) + sonnet×1 researcher (other facts) · all axes · shape: agent-tool | found: 36, new: 36, confirmed: 33, fixed: 33, unexecuted: 0, edits: 33 | method: citation — full pass over the section partition; every candidate executed by the orchestrator (5 git/tmux probes in a throwaway repo and scratch tmux server, the Deck resolver read, commit and D-row existence checked); 1 refuted, 1 recorded, 1 duplicate | b67e58b1… → 44daeced… |
| Pass 2 | opus×1 + sonnet×1 + opus×1 researcher + sonnet×1 researcher (round-1 owners) · delta over the pass-1 fix diff + one hop · shape: agent-tool | found: 9, new: 9, confirmed: 7, fixed: 7, unexecuted: 0, edits: 7 | method: re-derivation — the round-1 seats re-derived their own slices over pins/pass-1-fix.diff; both fact slices CONFIRMED every changed quote (no defect); 7 own-fix defects (own-fix: round 1) in D1/D2/D4/D5/D7/Cost, 1 refuted, 1 recorded | 44daeced… → e94d9a33… |
| Pass 3 | opus×1 (round-1 owner of the rules slice; the other three slices held no open claim and are restated at their pass-2 values) · delta over pins/pass-2-fix.diff + one hop · shape: agent-tool | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 5 | method: re-derivation — rules slice over the pass-2 fix diff; 5 own-fix defects (own-fix: round 2); class rewrite — D2, D4, D7 (rounds 2, 3): the three paragraphs rewritten whole in one batch, the `.tmp/runs` move DELETED in favour of a refusal | e94d9a33… → f7c7fdc5… |
| Pass 4 | opus×1 (round-1 owner of the rules slice; the other three slices restated at their last values) · the scope-growth stop's fixed set only (P3-N1..N5) · shape: agent-tool | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — closing round over the stop's fixed set: all 5 fixes verified, 8 of 8 rewrite citations re-derived at the pin; the 2 new observations are own-fix residue raised after the stop fired, RECORDED — measured onto W-14219e6f; standing clean since earlier passes: intake, personas, facts, vendor, approach, constraints, completeness | f7c7fdc5… → f7c7fdc5… ✓ |
| Pass 5 | opus×1 (round-1 owner of the rules slice; the panel's changes all sit in its sections; other slices restated) · the ONE delta round over the approval panel's revision · shape: agent-tool | found: 7, new: 7, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — every panel row checked PRESENT/WRONG against its concern and counter-case, 11 of 11 new citations re-derived at the pin; 12 rows PRESENT-OK; 2 rows WRONG (PO2, PF2/PF3) and 5 record-only items are own-fix residue of the revision raised after the scope-growth stop fired, RECORDED — measured onto W-14219e6f points 7-13 (term-edit § scope-growth stop: post-stop residue does not hold the flip) | c6d3ae64… → c6d3ae64… ✓ → **CONVERGED** |

## Findings (pass 5)

| id | finding | verdict |
|---|---|---|
| P5-PO2 | the preflight headroom check runs before the cold start, so a reboot's empty slice passes it | RECORDED — measured (post-stop own-fix residue; W-14219e6f point 7) |
| P5-PF2 | a re-created first window becomes no session's current window, so tab 1 shows the overflow window | RECORDED — measured (post-stop own-fix residue; W-14219e6f point 8) |
| P5-r1..r5 | ls-remote is a network call; spawner-only not enforced; overflow numbering start; MemoryHigh `max`; no-transcript under another folder | RECORDED — measured (W-14219e6f points 9-13) |

## Findings (pass 4)

| id | seat | finding | verdict |
|---|---|---|---|
| P4-1 | opus rule | Contract deltas omits the new "no builder" exit code; tests/test_agents_up.py:1198-1204 pins rc 2 | RECORDED — measured (own-fix residue after the scope-growth stop; destination W-14219e6f point 2) |
| P4-2 | opus rule | D4's no-builder branch needs the UUID minted in D2 step 4 | RECORDED — measured (own-fix residue after the scope-growth stop; destination W-14219e6f point 1) |

## Design-approval panel (critiques of md5 f7c7fdc5…)

Opus: `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-28-dynamic-builders-design.md`
Fable: `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-28-dynamic-builders-design.md`

Every concern executed and ACCEPTED; the revision is md5 c6d3ae64…, reviewed by the pass-5 delta round.

| id | concern (quoted whole from the seat) | evidence executed | change (spec anchor) | counter-case it must still pass |
|---|---|---|---|---|
| PO1 | "a pane that dies before its first turn is resumed by the next relaunch" is false as the code stands | agents_up.sh:494 always `--resume`; a missing transcript only warns (agents_up.sh:600) | D2 step 4: `--session-id` + first prompt on `no-transcript` for a spawner-bound session | a builder WITH a transcript still relaunches with `--resume` and the wake prompt |
| PO2 | the refusals from D3, D4 and D6 come after the worktree is created | D2's old order | D2 step 1 PREFLIGHT before any write | a healthy `add` still creates its worktree |
| PO3 | the item is assigned after the pane is launched, so the builder can race it | D2's old steps 5/6 | D2 step 5 assign, step 6 launch | `add` with no `--item` still launches |
| PO4/PF6 | the tabbed `.bat` is shared by every repo, but the lock is per repo; fixed `<name>.tmp` | agents_bat.py:245-248 | D5: box-wide `flock` + per-process temp | one coordinator alone regenerates as before |
| PO5 | the 2 GB headroom check has no defined way of being measured | — (design gap) | D6: MemoryHigh − (memory.current − inactive_file); unreadable refuses | an idle box with room still spawns |
| PO-m1/PF1 | `list-panes -a` lists grouped windows once per member | rotate_session.py:471-478 dedupes by pane id | D9: `list-panes -s -t =<S>` with `#{pane_id}` | a one-window grid reads its panes once |
| PO-m2 | window naming after a gap is unstated | — | D4: lowest free name | a grid with no gap names `agents-<max+1>` |
| PO-m3 | null-pid binding leaves the name unguarded until the re-bind | whoami_agent.py:149-150 | D2: preflight refuses a live-bound name; the re-bind follows on the first turn | re-`add` of a retired name still works |
| PF2 | tmux destroys a window whose last pane is killed | tmux semantics | D4: emptied `agents` simply ceases; next `add` re-creates the lowest free name; D5 `--window` falls back to the current window | a grid whose first window keeps panes is untouched |
| PF3 | `add` opening a new window switches tab 1 to it | tmux `new-window` without `-d` | D4: background window; the grouped session gets it as current | — |
| PF4 | the stated reason for a null pid is false; the new form breaks `session_id()`'s invariant | whoami_agent.py:72-78, :146-166 | D2: holder reason stated; spawner-only subcommand, `spawned: true`, docstring amended | a builder's own `--as` bind is unchanged |
| PF5 | the push check and fail-as-refusal contradict for a never-pushed branch; base is `master` | `git rev-parse origin/HEAD` exits 128 here | D2/D7: `<base>..HEAD` first, base resolved as `merge_request.py` does | a pushed branch with commits still retires |
| PF7 | the new exit code is unnamed | agents_up.sh:104-106 (3 = undeclared) | D4 + Contract deltas: exit 3; test_agents_up.py:1199-1204 updated (also answers W-14219e6f point 2) | every other refusal still exits 2 |
| PF8 | merge owner's charter can be inherited | agents_up.sh:202-210 | D8: never when `<role>` is the merge owner | `infra-4` still gets `infra.md` |

## Ask ↔ spec comparison (recomputed against the pass-3 text)

| # | Operator's words | What the spec says | Anchor | Disposition |
|---|---|---|---|---|
| A1 | "i want you to be able to create new agents when needed" (D-1301) | `agents_up.sh add` through `agents_spawn.py`; ordered, locked, idempotent | § The delta D1, D2 | IN |
| A2 | "give them proper charters" | role charter per repo (`<role>.md`, generic `builder.md`), fallback in `agent_role.py` | D8 | CHANGED — one role charter per repo instead of a generated file per builder (a per-builder file must be committed before the worktree is cut); § Decisions taken |
| A3 | "use them, when they finish clear them" | `remove` with the never-lose-work guard; retire at the item boundary | D6, D7 | IN |
| A4 | "so dynamically adjust needed agent count" | coordinator's sizing rule (ready items vs idle builders, GREEN only), 2 GB slice floor, no fixed count | D6 | IN |
| A5 | "they must bind/wire themselves properly" | the spawner writes the binding; the first prompt re-binds, reads charter and `work.py next`, claims the item | D2 step 4, D3 | IN |
| A6 | "they should not ask me any questions, all agents must ask to their coordinators" + the auto-mode prompt | first prompt routes questions to the coordinator; `--settings` turns the auto-mode offer and tips off on every pane | D3 | IN |
| A7 | "you must use the agents as disposable working units" | spawn per need, retire at the boundary, resume from the item and seed | D6, D7 | IN |
| A8 | "their sessions are stored in b2 and sesssion recall can be used" | the existing nightly archive covers removed worktrees' transcripts | D7, § What exists today | IN (already true — verified, no new code) |
| A9 | "always uptodate in All Agents (tabbed).bat for all repos" | generated tabbed `.bat` per (repo, window), regenerated by every add/remove, live tab append | D5 | IN |
| A10 | "i want these mechanism for all repos not only fabrik" | per-repo verbs; fleet's rollout copies `builder.md` | D1, § Lifecycle | IN |
| A11 | "terminal bat can show maximum 4 columns, for the rest agents, you can create second tab" (D-1132) | named windows of four + grouped sessions, at spawn and relaunch | D4 | IN |
| A12 | "i will do what needed ones, then coordinators will take of interacting with tmux, agents etc" (1.1) | no settings edit needed; a classifier allow rule is the only possible one-time step | D3, § Open/blocking unknowns | IN |
| A13 | "as being coordinator you should handle these without me" (1.2) | the coordinator runs both verbs; a refusal is boarded as one exact allow rule | D1-D7, § Open/blocking unknowns | IN |
| A14 | coordinator suggestions 3.9-3.15 (proposed, not the operator's) | 3.9 registry kept as a cache · 3.10 role charters · 3.11 `<role>-<suffix>` names · 3.12 rule + floor, no autonomous spawner · 3.13 out (seed machinery exists) · 3.14 IN · 3.15 out → W-ed781e7a | D8, D9, D6, D3; Intake I13-I19 | IN / CHANGED / OUT as listed |
| S1 | (not asked) § What exists today | the grounded baseline | § What exists today | ADDED — this command mandates it (Profile: delta) |
| S2 | (not asked) removal guard details | ignored files, detached HEAD, failing git, bound ids | D7 | ADDED — an existing code path (`git worktree remove` deletes ignored files) would lose work |
| S3 | (not asked) suppression on relaunch, named windows, cold start | D3, D4 | D3, D4 | ADDED — existing code paths (relaunch, window targets, slice ceiling) |
| S4 | (not asked) Rejected alternatives, Lifecycle, External dependencies, verdict, docs sites, digest | the spec contract's mandated sections | §§ | ADDED — /fabrik-spec mandates them |

Rows: 14 brief rows (≥ the 33 intake items they cover: A14 groups the seven suggestions, A8-A10 cover I7-I10, fold items and mails are dispositioned in the spec's Intake I20-I31) + 4 unrequested-section rows.

## Findings (pass 3)

| id | seat | finding | verdict | fix |
|---|---|---|---|---|
| P3-N1 | opus rule | the spawner's binding row carries the coordinator's pid (whoami_agent.py:411-420), so the coordinator window resolves to the builder's name and a re-`add` hits "held by a LIVE session" | CONFIRMED (own-fix: round 2; row construction read) | D2 step 4: `pid`/`pid_start` null |
| P3-N2 | opus rule | a moved `.tmp/runs` folder is never found by its seed (absolute `scratch` path; command_run.py:1700-1710) | CONFIRMED (own-fix: round 2; a live seed holds `"scratch": "/opt/fabrik/.claude/worktrees/infra-3/.tmp/runs/…"`) | D7: move deleted; a folder a seed names refuses |
| P3-N3 | opus rule | the `--detach` cold start can run uncapped (agents_up.sh:529-533) | CONFIRMED (own-fix: round 2) | D4: `add` refuses uncapped unless `FABRIK_AGENTS_UNCAPPED=1` |
| P3-N4 | opus rule | exit 2 cannot tell "no builder" from a refused ceiling | CONFIRMED (own-fix: round 2; agents_up.sh:107, :328, :539 all exit 2) | D4: a distinct exit code |
| P3-N5 | opus rule | D2's step order contradicted D4's cold-start order | CONFIRMED (own-fix: round 2) | D2 numbered steps, cold start is step 3 |
| P3-rec | opus rule | a session's run folder can sit in two checkouts after a move between worktrees | RECORDED — one hop out (destination: the plan) | — |
| P3-self | orchestrator | the rewrite first named `scratch_sweep.py` as the judge of `.tmp/runs`; it never prunes `.tmp` (command_run.py:1527) | CONFIRMED during the rewrite's own probe, fixed before the pin | D7 cites command_run.py:1527-1531 |

## Findings (pass 2)

| id | seat | finding | verdict | fix |
|---|---|---|---|---|
| P2-O1 | opus rule | bindings-only `add` writes no record the resolver reads, so `--pane-cmd` prints no pane (agents_up.sh:199-200) | CONFIRMED (own-fix: round 1) | D2: the binding is written through whoami's writer for the minted id in every repo |
| P2-O2 | opus rule | the ignored-file refusal refuses every live builder (infra-2 holds 7 `.tmp/runs` folders) | CONFIRMED (own-fix: round 1; `ls` → 7) | D7: dependency/cache trees let go, `.tmp/runs` moved to the main checkout, other ignored files named |
| P2-O3 | opus rule | a cold `add` launches only the new builder and the relaunch then leaves the grid as it is (agents_up.sh:590) | CONFIRMED (own-fix: round 1) | D4: whole grid started detached first, before the new builder is recorded |
| P2-O4 | opus rule | `<repo>/.fabrik/agents.lock` is untracked in the coordinator's checkout | CONFIRMED (own-fix: round 1; `.gitignore` lists no such path) | D2: lock in the git common dir |
| P2-O5 | opus rule | "HEAD is on `worktree-<name>`" refuses every existing builder | CONFIRMED (own-fix: round 1) | D7: any branch, detached refuses |
| P2-O6 | opus rule | a bindings-only pane that dies before its first turn leaves no record | CONFIRMED (own-fix: round 1) | same fix as P2-O1 |
| P2-O7 | opus rule | D1 "grows only the dispatch lines" and Cost ≈ 60 contradict D4/D5; `--window` has no timeout or missing-window rule | CONFIRMED (own-fix: round 1) | D1, Cost, D5 |
| P2-S1 | sonnet | I20 SHAs unverifiable | REFUTED (`git cat-file -t` → commit ×4) | — |
| P2-S2 | sonnet | I22 destination is a future commit | RECORDED — measured (a forward destination tied to a named event; the plan carries the step — destination: /fabrik-plan-after-chat) | — |
| P2-rec | opus rule | rotate_session's registry write sits outside the new lock; launcher tests pin `run` lines | RECORDED — one hop out (destination: the plan — rotate takes the same lock; tests updated with the change) | Contract deltas names the tests |

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
