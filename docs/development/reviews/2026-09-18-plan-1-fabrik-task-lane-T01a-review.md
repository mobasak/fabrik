# T01a — SIZE at `start`, and `step --design`: per-ticket review ledger

## Round 1 (2026-09-18)

Finders: native opus×1 + native sonnet×1 — round 1
Surface: worktree commit ce00d042 (master..worktree-agent-a984d4a77e8e72e98): `scripts/command_run.py` +312/−0, `tests/test_command_run_fabrik_task.py` +578 (new). Partitioned by file — opus on the script, sonnet on the graders.

Coder self-verified: 9 graders all watched red first, one red-on-revert after a self-review finding (its `files:` block terminator keyed only on `- id:`, so a governance-sync block that lost its `files:` key would adopt a LATER hook's regex — hardened and proven red). Orchestrator re-ran independently: 9 passed on the rebased tree; `tests/test_command_run.py` 252 passed; six other `command_run`-touching suites 229 passed — run against the WORKTREE's copies, because three of the repo's `command_run`-touching test files carry a sibling's WIP and the main-checkout versions would have tested their half-finished edits.

| # | Finding | Source | Disposition |
|---|---|---|---|
| C1 | A block or folded `files:` scalar BECOMES the regex: `files: >-` compiles to `'>-'` and matches nothing (a declared `scripts/enforcement/` path starts rc 0 recording a PASS); `files: \|` compiles to `'\|'` and matches everything (every start refused). Neither prints the fail-open warning, because the indicator is itself a valid regex — the "empty regex is truthy" hazard the docstring claims to have closed, in a spelling it did not consider | opus CONFIRMED, orchestrator re-executed | **FIXED** — indicator characters route to the documented fail-open |
| C2 | Seam break: `sync_test` writes `"pass"`; the spine's `## Interfaces` declares `"ok"\|"unavailable"`. The shipped assertion tested `!= "unavailable"`, which passes against either string and cannot catch it | opus CONFIRMED + orchestrator seam audit | **FIXED** — `"ok"`, and the grader now asserts equality |
| C3 | `.resolve()` follows symlinks, so a declared symlink is rewritten to its TARGET before the dirty check. A symlink git reports as modified is ACCEPTED — the exact silent success the check exists to prevent. Population: 5,731 tracked symlinks across 4 of the 45 `/opt` repos, the hub's own `scripts/verify_prod_parity.py` among them | opus CONFIRMED, orchestrator re-executed | **FIXED** — normalise without following links; containment on a resolved fallback; the directory test excludes symlinks |
| C4 | The five `--declare` answers are never validated. `heavy`/`mechanism`/`oneway`/`tradeoffs` are tested `== "yes"`, so `yse`/`nope`/`1` read as *no* and route to the cheapest lane; `decision` is tested `!= "yes"` and fails the other way | opus CONFIRMED | **FIXED** — values constrained to `yes\|no`, correction printed beside the missing-keys one |
| C5 | An EMPTY design file leaves the write-once slot re-writable: the guard is truthiness, so `design=""` is falsy and the next `--design` overwrites with no NOTE | opus CONFIRMED | **FIXED** — presence, not truth |
| C6 | Glob metacharacters in a declared path are git PATHSPEC magic: `src/rep[1].py` clean but its sibling `src/rep1.py` dirty → refused, naming the wrong file. Fail-CLOSED | opus CONFIRMED | **FIXED** — `--literal-pathspecs` |
| C7 | A bare `-` YAML sequence item defeats the block terminator, so the scan runs on and adopts a LATER hook's regex — the same trap the coder hardened, in the spelling it missed | opus CONFIRMED | **FIXED** |
| C8 | The block anchor demands `- id: governance-sync` as the item's FIRST line; a `name:`-first reorder disables the lane test (fail-open, loud) | opus CONFIRMED | **FIXED** — `id:` found anywhere in the item |
| C9 | The 3-file cap counts OCCURRENCES, not distinct paths: four copies of one path refuse a one-file task into the spec chain; two copies persist into `declared.files`, which T01b re-measures against | opus CONFIRMED | **FIXED** — order-preserving de-dup |
| C10 | `step --design` on a non-`fabrik-task` record is silently ignored — no mirror of the `start` guard. rc 0, pinned line printed, nothing recorded | opus CONFIRMED + sonnet mutation N5 | **FIXED** — refused, mirroring `start` |
| C11 | A `--declare` member with no `=` surfaces as `(ValueError)`. Row 1's contract is met, but the message names neither the flag nor the member, and it is the likeliest `--declare` mistake | opus CONFIRMED, advisory | **FIXED** — named refusal |
| C12 | `sha: "unavailable"` conflates "no commits yet" with "not a git repo at all", and the second skips the dirty check entirely | opus CONFIRMED, low | **FIXED** — `no-repo` distinguished |
| S1 | The lane's HEADLINE rule has no grader: `files > 3 → /fabrik-spec`. Max 3 `--file` flags in any call; raising the cap to 4 left 9/9 green | sonnet mutation N2, orchestrator re-verified | **FIXED** — grader added |
| S2 | Four of seven declared-answer lanes unguarded — `heavy=yes`, `oneway=yes`, `tradeoffs=yes`, `decision=no` have ZERO occurrences in the file; deleting those branches left 9/9 green | sonnet mutations N3/N4, orchestrator re-verified | **FIXED** — one grader per lane plus a precedence grader |
| S3 | The `--design` cap is untested AT the boundary: only 2001 is sent, never exactly 2000 (which must succeed). `>` → `>=` left 9/9 green | sonnet mutation N1 | **FIXED** — boundary grader added |
| C13 | Nothing proved Python `re` and `grep -qE` AGREE on what the scalar MATCHES — only that both extract the same string. Latent, no live instance (172/172 over 3,009 tracked files, sets identical) | opus PLAUSIBLE | **FIXED (strengthened)** — the grader now compares match SETS across `git ls-files` |
| C14 | The size gate's git subprocesses run while the per-session record flock is held; a hung git could stall concurrent same-session calls for up to ~70s | opus PLAUSIBLE, unexecuted | **RECORDED — measured.** Moving the gate outside the lock is a structural change to `main()`'s flow and was not worth risking the byte-identity property that had just been verified. Routed to the ticket's Evidence |
| S4 | The PyYAML-equality grader reads the LIVE `/opt/fabrik/.pre-commit-config.yaml` rather than a fixture, and skips where absent | sonnet PLAUSIBLE | **RECORDED — by design.** The spec mandates live agreement; a fixture would prove agreement with the fixture. Its skip in the ~46 project repos is correct |
| S5 | Row 5's directory/outside-repo checks reuse the succeeded call's session id and pass only because the size gate refuses ahead of the nested-start logic | sonnet PLAUSIBLE | **FIXED** — own session ids |

Refuted / swept clean (executed, no finding): byte-identity for every non-`fabrik-task` command — stdout, stderr and record keys diffed live-vs-built across three verbs, identical, the headline risk for ~46 repos; the guard ORDER ships as specified with each stage short-circuiting; `_cmd` bound once and tested by every guard, so `--command /fabrik-task` enters the lane; the bare `except Exception` proven to convert a real `FileNotFoundError` and a real `ValueError` into rc 1 + template + no record; all four git calls `check=False` reading `.returncode`, including the separate untracked probe (`git diff --quiet` returns 0 for an untracked path — executed); the `--design` write strictly before the event queue, so a refusal emits no `phase` event; no key collision for `rec["design"]`/`rec["declared"]`; 19 of 19 "should catch" mutations red with a control proving the harness grades the mutant.

Two orchestrator adjudications against the ticket, not the code: the ticket's step 5 said to persist `declared` "in the record literal", and the coder set it conditionally AFTER the literal because a literal member writes `declared: None` into every other command's record in ~46 repos — the coder was right and **the ticket was corrected**. The coder also declined the suggestion to refuse a zero-length `--design`, arguing that refusing empties makes the presence-check guard unfalsifiable (with empties refused the field is always truthy, so no mutation could catch a regression to truthiness) — accepted, and recorded as considered-and-declined.

| Pass | Finders | found | confirmed | fixed | unexecuted |
|---|---|---:|---:|---:|---:|
| Round 1 | opus×1 + sonnet×1 | 19 | 15 | 15 | 0 |

## Round 2 — fixup verification (2026-09-18)

Finders: native sonnet×1 (fresh, non-authoring) — round 2
Surface: the fixup commit 6cb58bb1 (+125/−20 script, +462/−6 graders) over the merged tree.

Coder's own evidence: 23 graders green, 19 of 19 mutations caught red each with a pre-written backup, the mutation asserted landed and an md5-verified restore; 817 existing tests green across 13 suites. It also caught a regression in its OWN fix — gating the `rev-parse` probe on `_repo_root()` being non-empty would have made a MISSING GIT BINARY read as "not a repo" and skip the dirty check, the same fail-open class C3 closes.

Orchestrator re-verified independently: 23 passed; `sync_test` now `"ok"`; both block/folded shapes return `None` and fail open; two mutations spot-checked (raising the file cap; restoring `.resolve()`) each turned the RIGHT test red, with a byte-identical restore.

A fresh non-authoring sonnet seat swept all seven open classes against the merged tree, driving every one through its own throwaway repo:

| class | verdict |
|---|---|
| yaml-scalar-shapes | **CLOSED** — folded, block, double-quoted and absent-id fixtures all print the SKIP line and record `unavailable`; a genuine single-quoted match still refuses correctly |
| symlink-resolution | **CLOSED** — a clean tracked symlink records its own spelling; retargeted so only the link shows ` M`, the start refuses; a symlink-to-directory is not mis-rejected as a directory |
| pathspec-magic | **CLOSED** — `src/rep[1].py` clean with its glob sibling dirty now starts cleanly |
| truthiness-vs-presence | **CLOSED, and the grader is falsifiable** — reverting `"design" in rec` to `rec.get("design")` on a mutant copy makes the second `--design` silently overwrite, and the shipped grader goes red |
| duplicate-paths | **CLOSED** — four spellings of one path de-duplicate to one; the cap still trips on four distinct files |
| re-vs-ere-agreement | **CLOSED, not vacuous** — the grader asserts a >100-file population AND a non-empty match set, so an empty-regex degenerate case cannot pass; re-run live, 172/172 identical |
| flock-held-across-subprocess | **STILL OPEN, as declared** — confirmed genuinely unfixed and NOT worsened: the only loop edit was `exists()` → `os.path.lexists()` (same call count) and every new check is in-process string work |

All six other fixes confirmed by direct probe, including the one that mattered most: the `rev-parse` probe runs **unconditionally**, so with `PATH` pointing at a directory holding no `git` binary the `FileNotFoundError` propagates into the refusal arm (`start could not complete (FileNotFoundError)`, no record opened). The coder's self-described regression is not in the shipped code.

**On the zero-length `--design` question the coder declined:** the seat judged the argument SOUND and proved it rather than asserting it. `_design` is only ever the file's text, so the only falsy stored value is an empty design; refusing empties at write time would make every stored value truthy, and `"design" in rec` versus `rec.get("design")` behaviourally identical for every input the code can produce — no mutation could distinguish them. It confirmed the distinguishing input is reachable today by reverting the guard and watching the grader go red.

| Pass | Finders | found | confirmed | fixed | unexecuted |
|---|---|---:|---:|---:|---:|
| Round 2 | sonnet×1 (fresh) | 0 | 0 | 0 | 0 |

**Round 2 CLOSED — `confirmed: 0`.** Six classes closed by execution; one (`flock-held-across-subprocess`) stays RECORDED with its rationale above.

⚠️ **Machinery note on my own pin:** the fixup diff I handed the seat was taken as `91fba505b..<branch>`, and because the branch had been rebased that range also swept in a sibling's unrelated Fable-band-clamp change set (`claude_rotate.py`, `quota_posture_hook.py` and their tests). The seat correctly fenced its scope and routed it back rather than reviewing it. A per-ticket pin should be the ticket's own two files, not a commit range across a rebased branch.

⚠️ **Process note, recorded rather than hidden:** — the convergence seat's verdict on the seven open classes (`yaml-scalar-shapes`, `symlink-resolution`, `pathspec-magic`, `truthiness-vs-presence`, `duplicate-paths`, `re-vs-ere-agreement`, `flock-held-across-subprocess`) is pending and will be appended here.

⚠️ **Process note, recorded rather than hidden:** T01a was MERGED at `2fc8beef` after round 1 and its fixups, before this round-2 confirmation closed. D4 requires the coverage-adjudicated exit BEFORE merge. The convergence round is being run against the merged tree instead, and any finding it raises will be fixed on `master` before T01b lands on the same file.
