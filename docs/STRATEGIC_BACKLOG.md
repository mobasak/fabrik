# Strategic Backlog

**Last Updated:** 2026-08-25 — every item now carries an owner tag (see § Ownership).
Current split of the 16 open items: **infra 3 · fleet 11 · intel 1 · operator 1** (5 infra rows closed 2026-08-25).

> **Purpose:** Track work that's been deliberately deferred from active development — not because it's unimportant, but because it's not yet ready for a focus window, blocked on operator action, or correctly waiting for a triggering incident.

Generated from the end-of-day plan-state on 2026-06-07 after the trio Phase 5.1.a ship. Each item below is something we explicitly DIDN'T do this session and explicitly DIDN'T commit to today — and why.

---

- ~~**[operator] WSL2's NAT range collides with the `1+Open 12` Wi-Fi, and the only supported fix is a `.wslconfig` mode change (2026-09-20)**~~ ✅ **RESOLVED 2026-09-23 (D-360)** — `networkingMode=mirrored` plus pinned Docker pools (`bip` `10.211.0.1/24`, `default-address-pools` `10.212.0.0/16`); the colliding NAT range no longer exists. The baseline below is still worth one run ON that Wi-Fi, since the failure was never reproduced here. The original entry follows — Windows allocates WSL's NAT range at `172.22.16.0/20`; that Wi-Fi hands out `172.22.29.0/24`, inside it. While it is the active uplink, every outbound IPv4 connection from WSL dies at the host while Windows itself stays fine, surfacing in Claude Code as `API Error: Connection refused — a firewall or proxy may be blocking it (ConnectionRefused)`. **Not fixable from inside WSL:** `natNetwork` and `natIpAddress` are not `.wslconfig` keys (verified against the live Microsoft reference, 2026-09-20), so the range cannot be moved; and the obvious candidate — re-addressing `eth0` out of the colliding `/24` — is REFUTED, because the VM held `172.22.22.127`, outside that `/24`, across a 4-day uptime spanning the outage. The supported fixes are both `networkingMode` values under `[wsl2]` plus one `wsl --shutdown`: `mirrored` (documented: IPv6, `127.0.0.1` reaching Windows servers, VPN compatibility, multicast, and WSL reachable from the LAN) or `consomme` (userspace, also NAT-free, and WSL's own fallback when NAT fails since 2.3.25 — but it gets one line in the config reference and no coverage in the networking doc, so its behaviour here is unverified). Box is WSL 2.7.10 / Windows 11 build 26200, so both version floors are met. **Two costs measured on this box, both specific.** (1) Mirrored makes WSL LAN-reachable by design, and this box runs 11 containers and ~11 services bound to `0.0.0.0` (5173, 8016, 8029, 8031, 8032, 18013, 11235, 18000, 54322, 631) while the network in question is an OPEN Wi-Fi; `firewall=true` (default) still filters, but the blast radius is real. (2) Docker's next auto-allocated bridge is `172.22.0.0/16` — `172.17`–`172.21` and `172.23`–`172.25` are taken — and that range CONTAINS the Wi-Fi's `/24`. NAT mode masks this today because `eth0`'s permanent `172.22.16.0/20` route makes Docker skip it; mirrored deletes that route, so a network created while off the Wi-Fi can claim `172.22.0.0/16` and collide on rejoin, which would read as "the fix failed". Prevention is pinning `default-address-pools` in `/etc/docker/daemon.json` — WSL-side, docker restart only, no WSL restart, and worth doing independently of any mode change. **Deferred by the operator 2026-09-20** (*"no wait for it for now"*), and certainty was the blocker: the recommending session never reproduced the failure — every measurement it took was of a healthy box on a different uplink — so "mirrored fixes it" is inference from a mechanism, not a cure observed here. What bounds the risk is the rollback: delete one line, one more shutdown, nothing migrated and no container state touched. **Baseline to diff against, run ON that Wi-Fi:** `ssh mac 'echo ok'` · `curl -4 -so/dev/null -w '%{http_code}\n' https://api.anthropic.com/v1/messages` · `docker ps -q | wc -l` (expect 11) · `curl -4 -so/dev/null -w '%{http_code}\n' http://localhost:5173`. Two related facts for whoever picks this up: `ssh mac` is unreachable from the phone tether (`172.16.100.33` times out), so staying off that Wi-Fi is not a workaround — the Mac goes with it; and the `2026-09-09` note in `/etc/resolv.conf` blaming public DNS on UDP/53 looks like this same overlap misdiagnosed, since all three nameservers resolve correctly today. Medium.
- **[infra] The two-tier research ladder (D-337/D-338) leaves two escape variants standing by design, recorded here so nobody re-derives them (2026-09-22)** — the scoped review's authoritative reader tested 11 ways to defeat the rule while leaving its text verbatim; the rewrite forecloses 8, converts 1, and 2 survive: **V1, the weak hit** — tier 1 returns a plausible-but-wrong answer, and "fail or do not find it" has no quality predicate, so tier 2 never fires; the base contract has no trigger that recognises a claim as CONTESTED, which is what `docs/reference/rules-currency-pass.md` row 2 ("≥2 DIFFERENT tools on any contested or currency-critical claim") supplies for a pass turn and nothing supplies for an ordinary one. **V7, the stale repo doc** — step 1 (`Grep docs/` + `AFCL.md`) has no freshness predicate, so a stale local fact short-circuits both tiers; partly blunted by the widened trigger's "a claim you are re-verifying", which makes the repo copy the subject rather than the answer. Both judged acceptable for a base contract: a good first answer SHOULD end a metered ladder, and a date check on every local fact is wallpaper (FIX directive 5). Destination if either bites: fold the currency bar's "contested" trigger into § External Knowledge as the one case that skips tier 1's stop, and no more. Low.
- **[RESOLVED 2026-09-20 — D-311] [infra] 10 confirmed defects in the enforcement git-decoder spec, left unfixed by the D-278 stop (2026-09-20)** — all ten were fixed in the resumed run, which then continued to a fresh-seat `confirmed 0` over all 47 classes after 25 rounds. The operator refused the D-278 exit for this artifact (*"you should not stop without reaching a no ops pass"*), and the stop's own premise — that the artifact's surface was quiet — proved false: later rounds found genuine pre-existing defects the earlier ones had walked past while busy with fix residue.
- **[infra] `--queue fabrik-task`'s `unmeasurable` and `upgrade` shares are diluted by rows that cannot contribute (2026-09-18)** — both read `total = len(for_it)`, which counts every `fabrik-task` row including any written by a `command_run.py` predating the close-time re-measure: such a row carries neither `oversized_mini` nor `upgrade`, sits in the denominator, and can never enter either numerator. `unmeasurable 0/2` then reads "no close failed to measure" when the truth is "no close was ever measured". The `oversized_mini` rate already gets an honest denominator of its own (`over_n`, with the `—/0` guard); these two do not. Deliberately NOT fixed with T02's other findings: the reachability turns on whether pre-lane `fabrik-task` rows exist at all, which needs a ledger probe rather than a guess, and the fix is a disclosure decision (derive over rows carrying the key, or append `(of N rows, M pre-lane)`) that belongs with whoever makes it. Low-medium.
- **[infra] `_task_series_nested` is O(|review-scoped| x |others|) over the fleet-wide append-only ledger (2026-09-18)** — measured on synthetic ledgers: 500 rows 0.04 s, 5,000 rows 0.25 s, 20,000 rows 3.89 s, i.e. 4x the rows for 15.6x the time. Harmless at today's size and `--queue` applies no default `--since`, but the ledger spans ~46 repos and only grows. A dict keyed on `sid` makes it linear. Recorded by T02's review as "not urgent"; the trigger to act is the first `--queue` run that feels slow, or the row count passing ~10k. Low.
- **[infra] The `/fabrik-task` close holds the record flock across up to five 10s git subprocesses (2026-09-18)** — `scripts/command_run.py`'s phase-5 re-measure runs `cat-file`, two `log`s, `rev-parse` and the `diff` via `_task_git` (`timeout=10` each), and `_task_close_fields` is called from `_close` inside `_mutate`, which the function's own docstring says "Runs with the record's flock HELD". Worst case ≈ 50 s of lock hold on a hung or NFS-backed git, on a close path that previously did no I/O at all — and the close is the one verb the Stop hook waits on. Raised by T01b's acceptance review as PLAUSIBLE (read, not reproduced: it needs a deliberately stalled git binary to measure). The fix, if the measurement justifies it, is to compute the re-measure BEFORE taking the lock, or to drop the per-call timeout for this leg. Low.
- **[infra] `oversized_mini`'s `paths=` sample is comma-joined with no escaping (2026-09-18)** — `scripts/command_run.py:3036` renders `",".join(paths[:3])`, so a path containing a comma is ambiguous to any reader splitting the field on one. The JSONL row itself is valid (`json.dumps` escapes it; 21 of 21 probe lines parsed), so this is a human-read and future-parser hazard rather than data loss — which is why T01b routed it rather than fixing it. Note the neighbouring PLAUSIBLE half, unreproduced: `_task_git` passes `text=True`, so universal-newline translation rewrites a bare `\r` in a path to `\n` before it is ever compared to `declared`. Low.
- **[infra] The `/fabrik-task` close event and its ledger row can disagree about the two lane fields (2026-09-18)** — `scripts/command_run.py:4409-4412` comments that the fields are "mirrored from the row so the event stream carries what the ledger carries — a close the two disagree about is a disagreement nothing downstream can ever repair". But the EVENT spread is unconditional while the ROW is gated on `_usage_is_required(rec)`: for a record whose `started_at` predates `_USAGE_REQUIRED_FROM`, the event carries `oversized_mini`/`upgrade` and no row exists at all. T01b's acceptance review could not REACH this (the feedback gate refuses first) and filed it as PLAUSIBLE — so the first task is to establish whether it is reachable at all before changing anything. Low.
- **[infra] The mandatory `--commit` on a `/fabrik-task` `done` has no rollout cutover (2026-09-18)** — every other close gate in `scripts/command_run.py` that could wedge an in-flight record carries one; `_AXIS_REQUIRED_FROM` (`:1288-1291`) was minted for exactly this class, with a comment saying a gate landing mid-run "would wedge every in-flight session in ~46 repos at once". `_task_close_fields` reads no such cutoff, so a `fabrik-task` record opened before T01b and closed after it cannot be `done`-closed. T01b routed it rather than fixing it because the window is provably closed — the lane is unreachable until T03 ships `commands/_sources/fabrik-task.md`, so no such record can exist, and a dated constant added now would be born dead. Revisit ONLY if a future change to this lane can strand a live record. Low.
- **[infra] `test_the_matrix_parser_reads_every_row_of_the_live_contract` asserts 22 rows / 25 tokens against the LIVE `CLAUDE.md` (2026-09-18)** — `tests/test_command_run_fabrik_task.py` reads the repo's own contract rather than a fixture, so any legitimate Doc Sync Matrix edit by any of the three concurrent hub sessions turns it red with no code change. Verified NON-vacuous by mutation, so it is genuinely testing the parser — the exposure is brittleness, not vacuity, and it is hub-only (test files are not in `CORE_SCRIPTS`, and the hub's completion gate does not run pytest). Not fixed in T01b because the ticket's own Behavior Contract row 8 MANDATES those exact numbers; changing the assertion's SHAPE — assert the invariant (tokens = concrete paths + the two `<name>` prefixes, every table row read) and keep the literals as a canary with a message naming the cause — is a ticket-scope decision. Low.
- **[infra] `command_run.py`'s SHARED close path still makes two bare git calls with no scrubbed environment (2026-09-18)** — T01b closed the class inside the `/fabrik-task` lane (`_repo_root` and `_task_git` both take `_scrubbed_git_env()`), but `git status --porcelain` and `git log -m` on the general close path — the one EVERY command takes — remain bare `subprocess.run(["git", …])`. An inherited `GIT_DIR`/`GIT_WORK_TREE` points their advisory at a repository the close never named. NOT fixed in T01b on purpose: those calls are pre-existing and shared, and T01b's whole acceptance rests on byte-identity for every other command, so changing a shared-path subprocess is exactly what that invariant forbids doing casually. The fix is one argument each plus a byte-identity re-verification, and it belongs to whoever next owns that path. Medium — the same class as the T01b defect, at lower severity (an advisory, not a measurement).
- **[infra] The ambient-`GIT_DIR` grader covers only the REFUSAL direction of the launder (2026-09-18)** — `tests/test_command_run_fabrik_task.py::test_an_ambient_git_dir_cannot_relocate_the_measurement` reds when the scrub is deleted, so it is a real grader, but it reds on `returncode == 0`: its decoy repo does not contain the measured sha, so unscrubbed the close takes the REFUSAL path. The commit subject names the other direction — a decoy that DOES resolve the sha, closing `oversized_mini: 0` on a real multi-file commit — and no grader observes it. Needs a decoy cloned after the commit (or an alternates entry) asserting the honest count rather than the decoy's zero. Low — the scrub is proven; it is the grader's coverage that is partial.
- **[infra] An EMPTY `declared.files` passes the element guard and publishes a confident count (2026-09-18)** — `all(...)` of an empty iterable is `True`, so `files: []` clears both halves of `scripts/command_run.py`'s guard and `declared` becomes the empty set: every path in the commit is then a non-member and is counted. The guard's own stated principle two lines above is "a record this malformed is not measurable; say so rather than publish a count". `start` cannot emit such a record (`--file` is required) but the guard exists precisely for records `start` can no longer produce. Deliberately NOT fixed in T01b: the fix widens `unmeasurable=no-git` again, which is the same grammar-pressure that made `bad-record` a frozen-ticket violation, so it belongs with that row and not in a review fix. Low.
- **[infra] The element-guard's `TypeError` message names neither the member nor its type (2026-09-18)** — `f"declared.files is not a list of str: {type(_raw_files).__name__}"` prints `… is not a list of str: list` for `["mas.txt", 7]`, which reads as a contradiction. The string never reaches an operator (the close prints only `type(e).__name__`), so it is the sole record of the cause and it identifies nothing actionable. One-line fix: interpolate the member types. Low.
- **[infra] `check_rule_grounding._digest_rows` grades NOTHING on a Pack-first Constraints Digest, and says so in a way that reads like the opposite (2026-09-18)** — it takes `cells[0]` as the QUOTE and `cells[1]` as the cited path. A digest written `| Pack | Rule | file:line |` makes it resolve each quote's FIRST WORD (`uv`, `Behavior`, `Fenced`) as a filename and emit `QUOTE-NOT-FOUND: digest cites uv which does not exist` — 8 findings while verifying ZERO quotes. Found by running the gate on a flipped scratch copy during `/fabrik-plan-review`; the fix in the reviewed artifact was to reorder its columns, but the GATE should detect a table whose cell 1 holds no path-shaped token and say "this digest's columns are in an order I cannot read" rather than emit per-row not-found noise. Low-medium.
- **[infra] `.windsurf/rules/core/40-documentation.md:241` names blank lines around headings, lists and code blocks — but not TABLES (2026-09-18)** — a paragraph flush against a table's last row is absorbed as a `<tr>` (executed with `markdown_it`, commonmark + tables). `check_rule_grounding` is structurally blind to it (`if not line.startswith("|"): continue`), so the rule pack and the only gate over that table both miss a live rendering defect. Add tables to the pack's list. Low.
- **[infra] `check_plan_tickets.py::MAX_BEHAVIORS = 8` has no exit for a ticket that legitimately GAINS a graded behaviour after its breadth adjudication (2026-09-18)** — measured here: two tickets sat at the cap while a review round added five user-observable behaviours to their STEPS, and both sanctioned exits (split the ticket, the `Integration: true` hatch) were closed by a recorded keep-it adjudication. The cheapest way to satisfy the cap is to leave the behaviour out of the contract, which is the Cobra path and is written down nowhere in the checker. Either allow a documented over-cap with a cited adjudication, or say in the finding that folding into an existing row is the intended move. Medium.
- **[infra] The Bash tool persists large output to a `$HOME`-rooted `.claude*` path and instructs the agent to read it — which every subagent brief on this box forbids (2026-09-18)** — hit by two review seats in one run (a 50.6 KB and a 36.3 KB command output). The prohibition exists because such a read stalls a seat indefinitely; the seats correctly declined and re-sliced with `sed`, at a real cost in turns. There is no way to tell the tool the destination is out of bounds. Worth raising with the harness, or documenting the `sed`-offset workaround in the subagent brief fragment. Medium.
- **[infra] The governance-sync `files:` regex differs from the hub's in 38 of 38 non-hub `/opt/*` repos (2026-09-18)** — measured by parsing the `- id: governance-sync` block in each of the 39 `/opt/*/.pre-commit-config.yaml` files; 0 of 38 equal the hub's 678-char scalar. `CLAUDE.md` § Sync-consciousness calls that regex canonical and single-sourced, so any project-side tool reading its OWN copy gets a different filter than the hub's. Not a defect in any one repo — a fleet-consistency question worth a look. Low.

- **[infra] The CONVERGED `/fabrik-task` spec miscounts the hub's `files:` scalars (2026-09-18)** — `docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` § Chosen approach, Phase 0 says `.pre-commit-config.yaml` "carries five, lengths 84 / 30 / 74 / 33 / 678"; re-derived at 06920e213 it carries **six** (84 / 20 / 30 / 74 / 33 / 678) — `decisions-ledger-check` at `:103` was missed. The MECHANISM the spec mandates is unaffected (the scalar is located by the `- id: governance-sync` id, never by position, and the governance-sync one is still last), and `/fabrik-plan-review` corrected the census in the build's plan set, so nothing is blocked. Found by executing the claim the plan inherited. Fix in the next spec-review round on that file, or let the build supersede it. Low.
- **[infra] The `/fabrik-task` spec's `oversized_mini` field order loses the commit sha under truncation (2026-09-18)** — `docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` § Chosen approach, Phase 5 (vi) fixes the grammar as `<n> · paths=<first three> · commit=<sha>`. `_cap_field` (`scripts/command_run.py:1605-1606`) truncates the TAIL at 2,000 chars, so three deep paths (executed: 2,441 chars) destroy `commit=<sha>` entirely and the row loses its provenance. `/fabrik-plan-review` DIVERGED the plan set to `<n> · commit=<sha> · paths=<first three>` on that executed evidence (minted in D-294) rather than ship a grammar its own cap breaks. Amend the spec on its next non-delta pass so basis and build agree. Low.

- **[intel] `/fabrik-rivals` guard debt left after the 2026-09-14 key-autoload review** — four low-severity grader gaps a 25-mutant battery found and the run deliberately did not close, each one line: the unreadable-`.env` fail-open path (`chmod 000`) is claimed by a docstring and pinned by no test; the `expanduser()` on `$SUBAGENTS_ENV_FILE` is documented as a deliberate divergence from `libs/alerting/_dotenv.py` and nothing pins it, so the next re-port reverts it; `main()`'s `load_env(str(REPO))` argument is ungraded, and swapping it for `os.getcwd()` — the historical wrong-repo bug — passes every test; and the `note:` the docs make a contract is not asserted. Plus one behaviour item: running the HUB's copy of the driver from another repo binds `REPO` to the hub, so it reads the hub's `.env` and writes its checkpoint under `/opt/fabrik/.tmp` while preflight calls it repo-local (reproduced; the doc now states the precondition, but no check enforces it). None is a live defect in the shipped path — the closing reader's verdict was SAFE for 48 repos.

### ~~[fleet] The Fable clamp makes a sentence in all three CLAUDE.md copies FALSE~~ — LANDED 2026-09-18, and the emitted `QUOTA:` line no longer matches its pinned shape

Raised by the closing delta seat of `/fabrik-review` over D-295 (2026-09-18), receipt
`docs/development/reviews/2026-09-18-fable-band-clamp-review.md` § RESUME item 3. RECORDED, not
fixed: it is a fleet-synced three-file edit plus a grader, and the round that found it was already
100% own-fix under a quota wall.

**The false sentence.** `/opt/fabrik/CLAUDE.md`, `/opt/fabrik/templates/governance/CLAUDE.md` and
`/opt/fabrik-lib/CLAUDE.md` all assert *"Because the band is the fleet's, a RED means every account
that could serve the hot window is RED too — the hold is the fleet's wall approaching, never one
account's."* The Fable clamp (D-295) makes that false for a Fable session BY DESIGN: `band_fable` is
raised to the ACTIVE account's own Fable reading precisely because no flip can relieve it.
`command grep -c "Fable window binds\|band_fable_clamped\|no relief leg" /opt/fabrik/CLAUDE.md` → 0.

**The shape drift.** The contract pins the line as
`band <GREEN|AMBER|RED|WALL>[ on <window>] (fleet-wide: …)[ — this account alone reads <band>; …]`.
On the clamped path the emitted line carries a PHRASE where `<window>` belongs
(`on this account's own Fable window (no relief leg)`) and a trailing clause the contract does not
list. `test_prompt_line_matches_the_contract_format_byte_for_byte` passes only because it has no
clamped case — so the byte-for-byte grader the contract points at is blind to exactly this.

**LANDED the same day, on the operator's push-back** (*"why did you add it into docs/STRATEGIC_BACKLOG.md but not fixed/implemented?"*): all three contracts corrected byte-identically, the clause pinned as its own three-way-graded shared span, and the byte-for-byte line grader given the clamped case it lacked. The deferral reason below was real when written — `can` at weekly 95% with the wall ~40 minutes out — and expired when the fleet relief-flipped to `sarp`. Kept for the record:

**Why it was not a quick edit.** The three copies are graded identical on that text; the hub copy is a
governance-sync trigger distributing to ~46 repos; and fabrik-lib's is sync-excluded and CROSS-REPO,
so it needs the operator's explicit approval in the turn it is made. The grader must gain a clamped
case in the same change, or the next drift is invisible again.

### D-201's ledger-retention figure is ~5x off, and the fleet tick's weekly leg is still unbuilt (2026-09-16)

- **D-201 states the 1 MB `_ledger_rotate` cap holds "roughly three weeks of history"**, derived from
  ~288 ticks/day at ~150 B. Measured over this ledger's real 33.8-day span on 2026-09-16: **68.7
  ticks/day at 115.9 B = 8,929 B/day**, so the cap actually holds ~16 weeks (~14 after the
  `weekly_pct` field). The row is immutable, so this needs a NEW decision row correcting it —
  D-201's tuning argument leans on that window being scarce when it is not. Owner: infra.
- **One ledger row carries `ts=0` (1970-01-01)**, which poisons any `min()`/`max()` span computed
  over `rotate-ledger.jsonl` — it produced a 20,712-day span before I range-filtered. Nothing reads
  the span today, so this is latent, not live. Owner: infra.
- **The weekly urgent-drain leg itself is NOT built.** `_urgent_drain_pct` remains session-gated, so
  an account that is weekly-hot and session-cold is RED by the bands contract with no mail. The
  instrument now records `weekly_pct` per tick; the threshold stays unset until that band has been
  measured over real data, exactly as D-201 restored the session row before moving the flip line.
  Owner: infra, after ~2 weeks of `weekly_pct` rows accumulate.


### The rotate-ledger's retention window, and the weekly urgent-drain leg that is still unbuilt (2026-09-16)

- **D-201 states the 1 MB `_ledger_rotate` cap holds "roughly three weeks of history"**, derived
  from ~288 ticks/day at ~150 B. Neither input matches this ledger, so the figure needs a NEW
  decision row (rows are immutable) — but ⚠️ do NOT re-derive it from the ledger's whole span: the
  fleet tick wrote ZERO tick rows on every date before 2026-09-08 (D-201 is what turned the series
  on), so a whole-span average is a bounded population wearing a denominator's clothes. Use a
  recent window, and state which. Owner: infra.
- **`_ledger_rotate` keeps only the NEWEST HALF on crossing the cap**, so retained history
  sawtooths between half and full — the GUARANTEED floor is half the apparent window, and a rotate
  can land mid-sample. Any plan that schedules work against "N weeks of accumulated rows" must use
  the floor, not the ceiling. Owner: infra.
- **One ledger row carries `ts=1.0` (1970-01-01)**, which poisons any `min()`/`max()` span over
  `rotate-ledger.jsonl` — it produced a 20,712-day span before range-filtering. Latent: nothing
  reads the span today. Owner: infra.
- **The weekly urgent-drain leg itself is NOT built.** `_urgent_drain_pct` remains session-gated,
  so an account that is weekly-hot and session-cold is RED by the bands contract with no mail. The
  tick now records `weekly_pct`; the threshold stays unset until that band has been observed —
  subject to the sampling bound above, which means the high band accumulates slowly by design.
  Owner: infra.


### Residue from the 2026-09-16 quota-bands contract pass (D-265)
- **Routed residue of the D-278 stop on the D-287 review (the box-shared peer registry, 2026-09-17; owner: fleet).** Four rounds over `30781421d` (own-fix 2/0 → 4/4 → 2/2 → 2/2) hardened the scaffolder and the detector; recorded, not cut: (1) the doc's collision check skips `~/.claude/sessions` when the DESTINATION is itself a symlink (a real dir on this box) — add `-L`-aware handling for the last element; (2) `_shared_link_warnings()` calls `Path.exists()`, which propagates `EACCES` — a permission wall on a link's target would kill `--status` and the tick (pre-existing on the parent's comprehension, unchanged); (3) the heal grader never asserts the DANGLING note absent after a heal; (4) `~/.claude/sessions` holds 911 pid-keyed records the CLI reaps only on ESRCH, so five whose pid another process reused are never removed — harmless (their socket is gone), but the merge concentrated them; (5) `tests/test_claude_fleet.py` loads the module from the LIVE path, so a SHA-pinned seat cannot run the shipped graders against its pin without a worktree — a `CLAUDE_ROTATE_SRC` override would let it; (6) the confirming seat's recorded fixture-mode question: a legacy `_cmd_status` (no fleet) never reaches the detector by construction, so no call there is owed.
- **Routed residue of the D-278 scope-growth stop on the GATE-row scoped review (2026-09-17; D-284; owner: infra for the gate, fleet for the sentence).** Three rounds (8/0 → 3/3 → 6/6 own-fix) converged the GATE sentence in both contracts to the gate's actual behaviour (`b206f0655`); the printed verdict stopped the loop. Recorded, not cut: (1) `scripts/final_gate.py:1276-1278` — the `pytest (NOT RUN) — pytest is not installed` branch is unreachable through `main()` because the `REQUIRED_TOOLS` probe (`:2877-2893`) aborts first; dead code that a future reader will document as a live row. (2) `:2883` builds the setup-error message as "cannot import 'ruff'" while ruff is probed as a resolved binary (`:80`, `:110`) — misleading text for the ruff arm. (3) `skip_advisory`'s ⚠ prefix says "this green" even on a RED run (it is called unconditionally at `:1308`). (4) The skip/deselect counts exist only in that ⚠ text; no structured `--json` key carries them, so no consumer can machine-assert "this green skipped n" (infra's ask in 01M2PT1G6K2EXFDBDM6TMBHVYQ, item three). (5) The template's GATE row still ends "a suite that genuinely cannot fit waits on the hub's diff-scoped leg" — a hub concept in a fleet-synced sentence a project cannot act on (pre-existing).
- **Routed residue of the D-278 scope-growth stop on the routed-up `/fabrik-review` over the `_pick_flip_target` fix (2026-09-17; receipt `docs/development/reviews/2026-09-17-review-scoped-pick-flip-target-review.md`; owner: fleet).** Rounds 2 and 3 each confirmed only residue of the previous fix (11/11, then 5/5 own-fix), so the loop stopped after one bounded remainder round. Recorded, not cut: (1) `_usable_ts` validates TYPE and FINITENESS, never RANGE — a finite `1e300` utilization renders 321 characters into `--status`, the `QUOTA:` line and the drain mail while the band still reads RED (fail-closed); a range validator (`_usable_pct`) is a new mechanism, measure first. (2) The `--status --json` board emits `session_resets_at`/`weekly_resets_at` as raw `_usable_ts` floats, so a machine consumer receives an undateable `1e300` the relief writer now refuses (`_dateable_ts`); and `_promised_resume` converts the stamp's content with a bare `float()` — both two hops from the reviewed diff. (3) A capless account whose weekly figure is UNREADABLE serves nothing (`_SERVING_STATES` excludes the new `weekly-unreadable` state) even when its session reading is fine — the fail direction is toward scarcity by the documented rule, but the 5h window of such a row is lost to the fleet band; decide whether `weekly-unreadable` should serve the 5h window the way `session-exhausted` serves the weekly one. (4) Two `get("utilization")` reads without an `isinstance` guard remain at the advisory's `row["five_hour"].get(...)` and the ledger write's `_active_row["five_hour"].get(...)` — both pre-narrowed by an `isinstance` on the row one line above, listed for the next sweep of the class, not defects today. (5) The round-zero commit message (`639caf855`) says thirteen sites and the round-2 title (`e96386725`) says seven graders; the diffs say fifteen and six — immutable history, corrected in the CHANGELOG entries.
- **Remainder rounds 4–5 of the same review (`1d9f5c2fc`, `bc40dc40e`), recorded under D-281, not cut (owner: fleet).** The ACTIVE account at a readable weekly over the picker's threshold but under its cap carries no `returns_at` on the board while its non-active twin does — pre-existing at `5b8452da0`, the `over-threshold` arm never keys on the active row. `quota_dashboard.py` keeps its own `_returns_at`/`_eligible` mirror of the verdict and never reads `_fleet_picture`, so a NaN utilization passes its `seven is None` guard and it renders a row the tick treats differently — route its `_util` through a finite check. A READABLE weekly at 100 under a cap prints `weekly-exhausted` in the queue and `cap-walled` in the warning — two labels for one row, pre-existing.
- **The confirming seat over `bc40dc40e` (recorded, D-281; owner: fleet).** On the same unreadable cache cell the NON-active row's `returns_at` follows its state (`cap-walled`/`weekly-unreadable` → the weekly reset, a day out) while the ACTIVE row's arm now reads only a validated figure (`fddbfa5cf`'s parent) — two rationales in one section; round 4's rule (`returns_at` follows the state) stands, so the honest close is either a comment stating one rule or gating the sibling arm on readability too. Decide when the dashboard mirror is reconciled (the item above), not before.
- **Routed residue of the D-278 scope-growth stop on the quota-posture Finish review (2026-09-17; owner:
  fleet).** The review took the stop at recorded round 14 (108 of 123 confirmed defects own-fix), re-verified
  the last fixed set, and routes what that round RECORDED here rather than opening a hunting round on it.
  (1) `_fleet_picture` (`scripts/sysadmin/claude_rotate.py`) still calls `float(cap)` bare on a row's
  `weekly_cap` — a caps.json field, not the usage cache — so a giant JSON int there raises OverflowError into
  the picture's guarded call sites (`--status` prints the safe picture, the tick prints `quota-posture not
  written`); route it through `_usable_ts` with a red-first grader that builds the value. (2) A FRACTIONAL
  `resume_epoch` in the open interval `(ts, ts + 1)` still reads two ways — the ledger latch sees a promise
  already due and speaks, the re-armed stamp truncates it to `ts` and `_promised_resume` reads no promise (a
  week's hold); unreachable from the one writer, which adds two ints, so it waits for a writer that emits
  fractions. (3) `tests/test_external_services_chain.py::test_gen_dashboard_help_writes_no_file` lists
  `tmp_path` and expects it empty while the autouse pins create six dirs there — fails on HEAD's own conftest;
  mailed to infra as 01M2QG0YAP88HJQD5RDGB24WRD. (4) `_isolated_sound_lock_dir` never had a docstring, so
  the docstring grader cannot cover it — one line and one tuple entry.
- **Three adjacent shapes the quota-posture closing rounds recorded rather than cut (Delta 18 · 20 · 21 seat A, 2026-09-17).**
  (1) `_refresh_expiry_epoch` (`scripts/sysadmin/claude_rotate.py`) — the guard `_usable_ts` cites for the
  giant-int class — has no bool exclusion: `{"refreshTokenExpiresAt": true}` reads as an expiry of 0.001
  (1970), so the chain reads long-dead and the account is excluded from flip candidacy. Fail-safe direction,
  outside the plan's diff; the one-line `isinstance(exp, bool)` refusal wants its own red-first grader beside
  the existing OverflowError one. Owner: fleet. (2) `os.utime` silently CLAMPS the stored mtime to the filesystem's ceiling
  (`0x3_7FFF_FFFF` = `15032385535.0`) for every ts between there and `time_t` (~9.2e18) — measured with
  `1e17`, first recorded here as a wrap (Delta 19 seat A, F3); no writer can emit such a ts (`time.time()`),
  so it is unreachable, but the re-arm has no upper bound on a returned row's ts below `time_t`. A clamped
  mtime is FUTURE-dated, so the advisory latch reads the stamp as invalid, re-fires once, and the primary
  write resets it (fail-open, measured 1 → 2 telegrams) — while the ledger ROW carrying that ts stays open
  by the future-dated rule (Delta 20 seats A F6 / C #3; the first cut of this row said the opposite).
  Owner: fleet.
  (3) Both tick invokers — the crontab line and the quota board — wrap the run in `flock -n` on the rotate
  lock, so two ticks never overlap; `ROTATE_LOCK` (credential writers only) is not what serialises them.
  The re-arm's documented intra-tick race therefore needs an UNLOCKED direct `--tick` call, where a relief
  clearing the stamp between the re-arm's ledger read and its `os.replace` re-raises a hold just lifted,
  with nothing said (Delta 20 seat A, P2; the first cut of this sentence said the tick does not serialise
  itself — Delta 21 seat C, #1). Owner: fleet.
- **Three review-harness gaps the quota-posture closing rounds paid for, each measured by a seat
  (2026-09-17).** (1) `tests/conftest.py` pins ten box-state seams autouse but NOT the clock: every
  multi-tick probe hand-rolls a 4-line `cr._now` monkeypatch — one seat wrote it sixteen times. A
  `_fleet_clock` fixture beside `_fleet_tick_spies` is one edit. (2) `/opt/fabrik/mutants/` holds a
  full second copy of `tests/`, so a repo-root grep for a rotate symbol inflates 8.6× (223 vs 26
  once `.claude/worktrees/` and `mutants/` are excluded); the contract names the worktrees trap and
  nothing names this one. (3) Driving `_cmd_tick()` many times in one pytest file is a ~300× wall-clock
  trap with no code cause: 32 ticks took 99 s under capture while one tick profiles at 3 ms — the
  cost is pytest capturing the per-dir "fleet dir:" lines. A note beside `_fleet_tick_spies`, or
  `-s`/`--capture=no` guidance for tick-driving probes, saves the two 280 s timeouts a seat lost.
  Owner: infra (test harness). Also worth carrying: the reviewer brief fragment should PIN every
  write-channel env for seats and MANDATE a per-seat scratch subdir — two seats collided on a shared
  path and one landed a nested run record under the dispatcher's session id (both measured this run).
  Two more from Delta 9: hand-built fleet rows cost a seat a round each to a silent mismatch
  (`_active_account_walled` matches on `slugs`, a list, so a row carrying `slug` reads as a clean
  negative; `_cmd_status` takes `as_json` positionally) — a `_fleet_row(...)` helper beside
  `_fleet_two_accounts` removes both; and the mirror recipe every brief carries must name
  `tests/test_claude_fleet.py` itself (its fixtures) and `quota_posture_hook.py` + its suite, or
  the mirror collects 293 of 324.
- **The RED predicate cannot tell a QUOTED shell operator from shell SYNTAX, and no fix is free.**
  `quota_posture_hook.py::_is_new_run_start` reads `--command`'s value through `_cut`, which
  truncates at the first `[;&|<>()]`. `shlex` has already discarded the quoting by then, so
  `--command 'fabrik-review;x'` (bash passes it WHOLE — the recorder files `fabrik-review;x`, which
  is off-`REVIEW_FAMILY`) is indistinguishable from `--command fabrik-review;x` (bash cuts at the
  `;`). Measured end-to-end against a real `command_run.py start` in an isolated `COMMAND_RUN_DIR`:
  the quoted form is ALLOWED at RED and then counts as no review at Stop. ⚠️ The guess is currently
  the RIGHT way round and must not be flipped casually: removing `_cut` from the value fixes this
  and DENIES the far likelier subshell spelling `(… --command fabrik-review-scoped)`, where the `)`
  is bash syntax — executed, it reds that corpus case. Punctuation-aware tokenisation
  (`shlex.shlex(..., punctuation_chars=True)`) resolves both in principle and was EXECUTED here: it
  breaks the `$(echo scripts/command_run.py)` bypass the corpus already guards. So the real fix is a
  FOURTH rewrite of this predicate, and each of its three rewrites introduced a fresh defect while
  fixing something else. Owner: infra (the hook is box-local but the class is the predicate's
  shape). First step: decide whether the string predicate survives at all — the sibling row above
  already asks that question, and this is a second measured argument for answering it.
  ⚠️ **AND IT FAILS IN THE WORSE DIRECTION TOO — this half is the more serious one.** `_cut` also
  does `.strip("`$'\"")`, so a SUBSTITUTED value is mangled instead of truncated: `--command
  "$CMD"` reads as the literal name `CMD`, `--command "$(echo /fabrik-review)"` reads as nothing,
  and an UNQUOTED backtick form reads as `echo` — while the QUOTED `` "`echo /fabrik-review`" ``,
  which is the form parallelling the two examples above, reads as `echo /fabrik-review`; a guard
  written against the wrong one of those two tests nothing. All FOUR are DENIED at RED — so a
  session whose command name comes from a variable is refused the one start RED exists to permit,
  the mandated review of the
  change it is checkpointing, and the deny text names a command that does not exist so the reader
  cannot tell what was refused. Measured end-to-end: the recorder files `fabrik-review` (in-family)
  for exactly the line the hook denies. This inverts the trade `_is_new_run_start`'s own docstring
  states out loud ("Between leaking a record and blocking a checkpoint, leak"), and the docstring's
  gap list says substitution is CAUGHT — true of the script path token, false of the `--command`
  VALUE, and it does not distinguish them. Whoever takes this row fixes both directions together or
  neither: they are one `_cut` call.

- **`docs/workstation/claude-account-rotation.md` carries no band wording at all**, while the two
  CLAUDE.md twins now make the bands a behaviour contract and name that doc as the Authority. Doc
  Sync Matrix floor rule. Same doc has an illustrative `{"ob@ocoron.com": 90}` using a REAL account
  with a number that matches neither the old cap (99) nor the new (95). Owner: fleet.
- **`scripts/sysadmin/test_bot_rotation_wire.py` — 4 pre-existing failures** in the
  `claude-keepalive-rotate.sh` shim tests (e.g. `test_shim_fail_on_401` expects
  `KEEPALIVE_FAIL:401_auth`, gets `KEEPALIVE_OK`). Both the script and the test are unmodified at
  HEAD, so this predates today's work — but it is red and nothing watches it, because the hub's
  pytest leg is off by design. Owner: fleet.
- **Both resume channels can be silent at once**: the urgent-drain mail does not fire when an
  eligible successor exists, and `_next_session_relief` returns None when no sibling is blocked by
  a readable future reset. The contract now says "read `--status`", which is right, but `--status`
  itself can name no relief. Owner: fleet.
- **`_fleet_active_wall_advisory`'s candidate test is looser than the relief leg's** — the advisory
  suppresses on any `_validated_pick` candidate, while the relief flip additionally requires the
  successor under 85 on BOTH windows. So the fleet can be told nothing while no flip is possible.
  Worth a decision on which predicate is canonical. Owner: fleet.
- **Residue risk of `/fabrik-plan-review`'s own round-4 fix batch on `2026-09-16-plan-1-quota-posture.md`** (owner: **fleet**; destination: `/fabrik-execute-plan`'s Phase B and Phase C `/fabrik-review-scoped` passes, which read the same paragraphs against the CODE) — rounds 2-4 of that review confirmed only defects inside the review's own fix prose (11/11 · 10/10 · 6/6) and the loop closed on the operator's stop + D-252; the last batch (the cap-is-bounded-by-the-stamp paragraph, B12's no-successor fixture, the null-burn rendering arm, the successor skip-and-continue rule, the derived ring length) was fixed by the orchestrator and NOT re-read by a fresh seat. The executor treats those five paragraphs as unreviewed prose: verify each against `claude_rotate.py` (`cap_trip` `:4271`, the trip-leg return `:4357-4362`, `_active_account_walled` `:4391`) before building from them.
- **Phase A of 2026-09-16-plan-1-quota-posture closed under the D-252 scope-growth stop (review rounds 2 and 3 confirmed only its own fix prose, 5/5 → 1/1).** The round-3 fix — the identity grader `test_the_quota_line_sentence_set_is_identical_across_the_three_contracts` (A1b) plus the plan and CHANGELOG lines that describe it — was NOT re-read by a fresh seat. Destination: the plan's Finish `/fabrik-review` reads the cumulative Phase A–C diff, and this row is retired in that receipt's per-phase verdict for Phase A.
- **~25 `monkeypatch.setattr(cr, "OPT_DIR", …)` calls in `tests/test_claude_fleet.py` are now DEAD.** `_opt_dir()` prefers `FABRIK_OPT_DIR`, which the autouse conftest pin sets for every test, so the patched module constant is never consulted. They fail SAFE today — the env pin is stricter than what they were doing — but a future test that patches the constant and expects its fixture repos to appear gets a silent empty list. Found by the Phase B closing delta seat (finding 5). NOT fixed in that run on purpose: a 25-site mechanical replace is the exact shape that rewrote five unrelated sentences earlier in the same run, and it was the end of a long session. Destination: convert each to `monkeypatch.setenv("FABRIK_OPT_DIR", …)` or delete it as redundant, in its own change with the diff read line by line.
- **`quota_posture_hook._is_new_run_start` was rewritten THREE times in one review, and each rewrite shipped a docstring claiming the spellings were handled that the next seat disproved.** v1 (regex substring): a quoted script path made the hold vanish, a quoted `--command 'fabrik-review'` denied the review family, the first `--command` beat the last, and a commit message naming the script was denied. v2 (shlex + pre-split): the pre-split severed quotes, denying that commit AGAIN, and `\n` in the split class denied the review-family start. v3 (one parse, operator-cut tokens, start-bound names): fixes six more, including the verb comparison failing on `start;echo done` and a `bash -c` payload never reaching the comparison. ⚠️ v3's own fixes are UNREVIEWED by a fresh seat, and the base rate for that in this review is three for three. The review closed under the D-252 scope-growth stop with round 3 at 6 confirmed / 6 own-fix. Destination: the Finish `/fabrik-review` over the cumulative diff, whose seats should be briefed to attack this ONE function first. The deeper question for that review is whether a string predicate over arbitrary shell is the right shape at all — the `Agent` half of the hold is a single exact tool-name comparison and has never been wrong, while this half has been wrong in every version. Dropping it and keeping only the `Agent` hold is a live option; it would need the sentence set in all three CLAUDE.md files re-cut, which is why it was not taken mid-phase. Mitigation already in place: the failure direction is now uniformly fail-OPEN, so a residual bug leaks a run record rather than blocking the commit RED mandates.
- **⚠️ TWO UNPINNED WRITES INTO THE OPERATOR'S LIVE `~/.claude` REMAIN, found by the heavy review's closing seat and deliberately NOT fixed in that run.** `claude_rotate.ROTATE_LOCK` (`~/.claude/.claude-rotate.lock`) and `claude_rotate.ALERT_STATE` (`~/.claude/.last-401-alert`) are module constants bound at import from `Path.home()` with NO env seam, so no conftest fixture can reach them. A test driving `_file_refreshed_credentials(provenance=True)` takes a `flock(LOCK_EX)` on the REAL rotation lock every real credential writer contends on; a test driving the 401 branch stamps the real debounce file and SILENCES the operator's 401 alert for 12 hours. Containment today is per-test `monkeypatch.setattr` in 3 of 17 relevant test files, and the one `ROTATE_LOCK` pin is a raw module assignment that is never restored — so the suite's safety is an artifact of collection order and vanishes when a file runs alone. This is the SAME class as the three sinks this plan already closed (`/opt`, the notifier, the fleet root): a `Path.home()` constant bound at import. ⚠️ Destination: give the family a call-time `_claude_dir()` seam reading `CLAUDE_HOME_DIR` and pin it autouse beside the others. The MIRROR is why it is not done here — roughly 60 existing `monkeypatch.setattr(cr, "ACTIVE_CREDS", …)` / `ACCOUNTS_DIR` sites across three test files bind the CONSTANTS and would silently become no-ops, un-pinning what is currently pinned. A ~60-site mechanical migration is exactly the shape that rewrote five unrelated sentences earlier in this same session, and it is not a thing to do at the end of a long run. It needs its own change, its own review, and the diff read line by line.
- **⚠️ THE OPUS WEEKLY LIMIT IS INVISIBLE TO THE POSTURE, measured by walking into it minutes after the system went live (2026-09-16).** A review seat died mid-pass on `You've hit your weekly limit · resets Sep 19` for `claude-opus-5` while the injected line read `band GREEN` — correctly, because it bands on 5h, weekly and Fable only. The probe's `model_windows` carries exactly ONE entry on this box (`Fable`), verified against the live posture file: the usage API reports Fable's ceiling as a `weekly_scoped` limit and reports no such limit for Opus, so there is nothing for the tick to read. This is the SAME gap D-269 was built to close for Fable — one model's ceiling tracked, another's not — and it bites hardest on a plan-execution run, which is exactly when a seat dying mid-round costs a whole round. ⚠️ The writer already has the shape: `windows.models` is a generic per-model dict and would carry an Opus entry the moment the probe reported one, so ONLY the banding would need extending (`band_fable` generalised to `band_model` over whichever model the session is on). Destination: first establish whether the Opus ceiling is reportable at all — read a fresh `/api/oauth/usage` payload for an account that has hit it and look for a second `weekly_scoped` limit — because if the API does not expose it, no amount of code closes this and the honest fix is a sentence in the contract saying the line cannot see it.

## [infra] A plan authored and committed in one motion is a convergence subject at NO moment a gate runs

`check_convergence.py:550` skips `??` paths — deliberately, so a sibling's mid-write scratch never
reds this session's gate — and since 2026-09-12 it says so with a NOTE ("checked at staging"). But
fabrik-lib-dev1's original finding (`01M1RFN3BT` defect 1) was never that the skip was SILENT; it is
that the skip has no downstream: the plan is `??` when the completion gate fires, and once committed
it is gone from `git status` entirely. Verified 2026-09-15: `check_convergence` appears in no
`.pre-commit-config.yaml` hook, so **nothing forces a gate run between staging and commit** — the
staged state is never re-gated and the subject is checked at no moment at all. The NOTE improved the
visibility and left the hole.

⚠️ **fabrik-lib-dev1's stated preference is (c) — re-run the gate once after auto-staging** — for a
shared-tree reason worth recording: (a) gating the staged set makes the check read a SHARED index
that carries siblings' staged paths, and (b) a pre-commit hook fires per-commit on a tree three
sessions commit into. (c) keeps the subject the session's own post-stage state. Their preference,
not mine, and they found the hole.

Not fixed as a drive-by on purpose: narrowing the `??` skip changes the FAIL DIRECTION of a
fleet-synced check across ~46 repos, and the skip exists because the alternative reds every session
on a sibling's in-flight draft. The shapes worth weighing: gate the staged set explicitly (`git
diff --cached --name-only`) rather than the working tree; or register `check_convergence` as a
pre-commit hook so the staged state is the subject; or have the gate re-run itself once after
auto-staging. Each is a contract change with its own mirror.

## [infra] `libs/competitor_intel` has drifted from fabrik-lib canonical, and the VENDORED set has no drift signal at all

Measured 2026-09-15 on fabrik-lib's report (`01M2J82N9TF7`), verified at HEAD against
`/opt/fabrik-lib/competitor-intel/competitor_intel/`: the degraded-taxonomy fix is absent from our
copy (`us_unmapped` canonical 5 / ours 0, `trust_us` 7/0, `_UNSTRIPPABLE` 9/0), so the us-column bug
is LIVE for `/fabrik-rivals` here. ⚠️ A re-vendor is NOT a copy: ours is a different shape, not just
older — synth 590 lines vs canonical 1401, and **196 lines exist only on our side** across
synth/orchestrator/dossier/stages (43/52/87/14); `protocols.py` is byte-identical. A blind `cp`
closes their bug and reverts 196 lines with no git trace, which is the trap this repo paid for three
times on 2026-09-05 in `libs/subagents`. The work is: adjudicate those 196 lines, then re-vendor.

SYSTEMIC, and the larger half: the hub enforces `check_synced_unmodified.py` over the SYNCED set and
has NOTHING equivalent for the VENDORED set (`libs/*`). This drift was invisible until a peer
measured it by hand. A periodic md5 sweep of `libs/*` against fabrik-lib canonical, reported the way
the sync check reports, would surface it the day it happens.

## [infra] The fleet-quota hold refuses read-only `git -C`, a piped `mail.py send`, and a `cd`-prefixed close — and the obvious fix opens a force-push bypass

Reported by fabrik-32 (`01M2CX7RGK44`) and reproduced: `_ALLOWED_BASH` is START-anchored, so
`git -C /opt/fabrik log -1` is refused while `git log -1` passes, and `printf … | mail.py send` is
refused although `mail.py`'s body IS stdin — so the hold's own mail exemption cannot be exercised at
all. ⚠️ EXECUTED: the naive relaxation is WORSE than the bug. `_git_flags_forbidden` reads
`verb = argv[1]`, so admitting `-C` past the regex makes
`_git_flags_forbidden("git -C /opt/fabrik push --force origin master")` return **False** — the
force-push veto bypassed, across ~46 repos. A correct fix threads a verb RESOLVER (strip `cd <dir>;`
and `-C <dir>`) through `_ALLOWED_BASH`, `_git_flags_forbidden` AND `_positional_forbidden` together,
with a red-first grader per shape. Spec work, deliberately not an inline patch.

## [infra] `check_plan_tickets` cannot tell a session's OWN plan lock from a sibling's, so a clean tree silently demotes its own findings

`own_dirs` is built from working-tree/staged plan-file edits alone, so committing plan work empties
it and the session's own plan is demoted to `[sibling plan]` advisory WARNs — measured at
web-ecommerce-factory (`01M2HH0NVMMD`): 0 errors / 32 warns on the gate path vs 4 errors / 28 warns
with `--plan-dir` on the same plan. A dispatcher-mode run commits plan files constantly, so the set
is unenforced exactly when you are about to report done. The SILENCE is fixed (the demotion now
names its count, its real selection reason and a working remedy, and reaches `--json`); ATTRIBUTION
is not, because no plan lock records a session identity. Needs a decision on what identifies "my
plan" — the active run record's `surface`, a lock owner field, or the working-tree/upstream split.

## [infra] Harness worktrees carry STALE synced copies, so every subagent's completion gate runs a different `final_gate.py` than master

Reported by wef3 (`01M2H05T88XM`): a harness worktree holds untracked copies of every
gitignored-but-synced path, snapshotted at creation and never refreshed. Measured there:
`check_synced_unmodified` says "all 208 match" in the main checkout and names TEN stale files inside
a worktree; four coder seats in one dispatcher run each separately diagnosed it and each concluded
"pre-existing, not mine". The check's own remedy text ("Revert it") tells a seat to edit a synced
file, which is a HARD STOP. Directions: refresh the synced set at worktree creation; make the check
worktree-aware via `git rev-parse --git-common-dir` with a distinct non-blocking staleness verdict.
⚠️ ALSO sweep `scripts/enforcement/` for the sibling shape — any check matching an exclusion pattern
against an ABSOLUTE path self-excludes inside `.claude/worktrees/`.

## [operator] `claude-stop-decider.py`'s lock prune aborts on one vanishing entry

`acquire_lock`'s prune puts `f.stat()` inside the try that wraps the WHOLE loop, so one entry
disappearing between `iterdir()` and `stat()` aborts the prune and every stale lock behind it
survives. CONFIRMED by reading the code at HEAD (`01M2CH5CWPWV`, from fabrik-32). NOT fixable by an
agent: `~/.claude/bin/claude-stop-decider.py` is box-local, tracked by no repo, and the mesh scripts
are read-only by contract — this one is the operator's.

## [infra] The private-index recipe's post-commit assertion wants a TESTED SCRIPT, not a bullet ~46 repos copy by hand

Three consecutive review rounds tried to write step 5a's assertion as copy-paste shell inside
`CLAUDE.md` § Behavior, and each cut was refuted by execution. The third attempt — a fenced
`|| exit 1` block — carried NINE executed defects in the block itself: an empty `$new` makes
`"$new":<file>` resolve to `:<file>`, which is git's shorthand for the INDEX, so the guard passes on
a commit that does not exist; `grep -vx` is a BRE, so the `.` in every one of the four shared-append
files this recipe names is a wildcard and a stowaway `CHANGELOGxmd` is hidden; `core.quotePath`
(default on) makes the stowaway guard fire on every non-ASCII path; `|| true` swallows an rc-128 and
passes on a non-existent SHA; `|| echo MISSING` never fires because `git rev-parse` echoes its
unresolved argument to stdout; `<branch>` is nowhere derivable and on a detached HEAD
`--abbrev-ref HEAD` returns the literal `HEAD`; the guard fires on a legitimate `git mv` two-path
commit that the SAME bullet mandates; a lost exec bit passes all three; and the column-0 fence SPLIT
the ordered list so steps 5b, 6 and 7 stopped being steps in every renderer.

Step 5a is now PROSE stating the invariant (`git ls-tree "$new" -- <file>` against the built
mode+blob, root-relative path, the ref equal to `$new`, an empty `$new` meaning a split run and NOT
a lost hunk). That is true and short. The EXECUTABLE form belongs in `scripts/` with its own
red-first graders per shape — the shapes are enumerated above and every one of them is already a
written-down failing case, so the test table exists before the script does. Until it ships, the
recipe asks a human to hold nine edge cases in their head, which is exactly what the executed
evidence says does not work.

## [infra] `docs/DECISIONS.md` is the one mandated markdown table with NO cell-count check, and 9 of 260 rows are off-width

A literal `||` inside a D-row's `what` cell splits the row into 8 fields against a 6-column header:
the rendered table and `scripts/decisions.py` BOTH silently drop the `why` and `where` columns — on
a superseding row, that is its entire provenance. Found on `D-259` at mint time (repaired by
rewording; `decisions.py:83` does a bare `line.strip("|").split("|")` and honours no `\|` escape, so
the markdown escape fixes renderers and not the tool — the two consumers disagree about the same
file). A sweep of the pinned file found **9 of 260** `| D-` rows with a pipe count ≠ 7; 8 predate
this run. `check_governance_tables.py` exists and reports "across 2 contract(s)" — the two
`CLAUDE.md` files — and is structurally blind to the ledger, which § Behavior mandates a row in on
every decision. A cell-count check over `docs/DECISIONS.md` would have caught this at commit time.

## [infra] Eleven code spans in the rule packs carry `\|`, which is a LITERAL pipe in every language they illustrate

Swept after a Phase D fix escaped two pipes inside a Python regex in `core/45-testing-strategy.md`
and shipped a destructive-test guard that rejected every legitimate name to 46 of 49 repos (fixed at
`08c0d005` by rephrasing to `dbname.endswith((...))`, which carries no pipe at all).

**Denominator:** 116 governance files scanned (both contracts, every `.windsurf/rules/**`, every
`commands/_sources` and `_fragments`); **11** code spans contain a backslash-pipe. None is a
copy-and-run predicate — they are type and schema NOTATION in don't/do tables — which is why this is
a backlog row and not a fix-now: `core/10-python.md:310` (`str \| None`), `core/12-node.md:295`
(`process.env.X \|\| 'default'`), and nine schema illustrations in `core/app-audit-log.md`.
Severity is still real for the first two: both packs' headers say "Follow verbatim", and a RAW
reader — which is how a pack reaches an agent — gets invalid Python and invalid JS.

**Do:** rephrase each so the span carries no literal pipe (`Optional[str]` prose, a named constant,
a fenced block instead of a span), as `check_governance_tables.py`'s own finding message prescribes.
**And extend that check:** its `_TARGETS` are the two CLAUDE.md files only, so the surface where this
shipped — `.windsurf/rules/` — has no detector at all. A row-width sweep of all 58 governance files
found **0 of 1,659** rows off their header width today, so the table half is clean and only the
code-span half needs the new rule.

## [infra] The rules packs cite hub-only docs 169 relative / 4 absolute, with no stated rule

Phase D made two `ai/20-vision.md` cites absolute because the doc they name is hub-only and is NOT
in `fabrik_synced_manifest.py` — sampled 3 project repos, 3 of 3 carry the pack and 0 of 3 have the
doc, so the relative form was a dead link in every one. That fix is right and it leaves the
convention incoherent: `command grep -roh '\`docs/[a-zA-Z0-9_./-]*\.md\`' .windsurf/rules/` → **169**
relative, `command grep -roh '/opt/fabrik/docs/...'` → **4** absolute, two of them created by that
change. And both directions are wrong elsewhere: `docs/reference/gui-toolchain.md` and
`docs/reference/research/chrome-ext-gui-research.md` are hub-only and cited relative (dead in every
project), while `/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` IS synced and cited
absolute, which defeats the sync.

**Do:** state the rule once — synced ⇒ relative, hub-only ⇒ `/opt/fabrik/…` — and sweep the three
inconsistent sites. **Do not** bulk-rewrite the 169: most are correct.

## [infra] `fabrik-lib/alerting/`'s `_last_sent` is unbounded and its only reset is a test reaching into the module

Surfaced reviewing Phase D's correction of `core/58-resilience.md`. Beyond the four properties the
pack now names, two more the rule does not carry: `_last_sent` has no eviction, so a title carrying a
varying token (an id, a timestamp) both defeats dedup entirely AND grows the dict for the process's
lifetime; and the module exposes no reset — its own tests clear it by touching
`alerting._last_sent.clear()` directly (`test_alerting.py:73`), which is the tell that the public
surface is missing one. Cross-repo, so it is fabrik-lib's to fix.

**Do:** mail fabrik-lib — a bounded store (or a documented `reset()`), and a note in the pack that a
title must be a STABLE key, not a formatted string.

## [infra] THREE `tests/enforcement` tests pass in isolation and FAIL in the full-suite run — pre-existing pollution, attributed by execution

⚠️ **Narrowed from four to three, 2026-09-15 (plan-2 Finish).** The fourth,
`test_plan_tickets_epic_scope.py::test_frontmatter_parser_matches_epic_order_verbatim`, was NOT an
ordering defect and is now FIXED: it is a twin-parser drift guard, and `_find_fences` had genuinely
diverged between `scripts/enforcement/check_plan_tickets.py`'s ported block and its source
`scripts/epic_order.py`. The port sits inside a `# fmt: off` block (`:1153`) whose own comment says
it "keeps the SOURCE MODULE's formatting", so `ruff format` reformatted the SOURCE and left the
frozen copy behind — both files are individually ruff-stable, which is why no formatting gate saw
it and only the verbatim-comparison test did. Re-synced the ported block; that file now reads
84 passed. The drift was already present at this plan's base commit `36da6bb4`, so it was never
this plan's — but the plan touched `check_plan_tickets.py` eight times and a defect in committed
code is the repo's.

`python3 -m pytest tests/enforcement -q` remains RED at HEAD for the other three, and was before
Phase E. All three pass cleanly when their file runs alone (`test_pack_reachability.py` →
16 passed, re-verified 2026-09-15), which makes this a test-ORDERING defect, not a defect in the
checks.

**Attribution, executed rather than assumed** (2026-09-14, three independent probes):

1. Reverting all six enforcement scripts Phase E touched to `84f88595` — the three still fail.
2. Reverting ONLY `_doc_registry.py` (removing `office-extension`, the likeliest suspect since the
   failures are about scaffold types) — the three still fail.
3. Running `tests/enforcement` with all FOUR test files Phase E modified excluded via `--ignore` —
   the three still fail.

So none of it is Phase E's. ⚠️ A fourth probe that does NOT work and is recorded so nobody repeats
it: `git archive <sha> | tar -x` into a scratch tree fails **103** tests, because the archive omits
gitignored files the suite needs. A clone-shaped baseline cannot attribute anything here.

**The mechanism, diagnosed but not fixed:** the three failures are the "scaffolder unavailable" and
"masked scaffolder failure" simulations — they assert the check does NOT condemn a pack it could not
evaluate. In a full run the scaffolder IS importable, so the simulation never takes effect and the
check evaluates the pack and condemns it. Something earlier in the run leaves `fabrik.scaffold` in
`sys.modules` (or `src/` on `sys.path`), and monkeypatching the import path does not defeat an
already-imported module. `test_pack_layout_audit.py` imports the same module and is the first place
to look.

The fourth failure is separate and also pre-existing:
`test_plan_tickets_epic_scope.py::test_frontmatter_parser_matches_epic_order_verbatim` reports
`['_find_fences']` — the two frontmatter parsers it holds to verbatim parity have drifted by one
helper.

**Do:** make the unavailability simulation defeat an already-imported module (pop it from
`sys.modules` in the fixture, or assert the precondition and skip loudly rather than silently
evaluating), and re-derive the `_find_fences` parity. Both are small; neither belongs inside a phase
whose scope is 23 mail-triage rows.

## [infra] `# AFTER-EDIT:` needs a SYMMETRIC coupling it can opt into — blanket symmetry was measured and rejected

wef2 reported (01M1V2P02) that the coupling is directional and points the wrong way for how the
files actually change: a checker script is stable, the DATA it measures churns, so editing
`packages/sections/registry.json` without the section-registry reference doc beside it (both
paths are wef2's repo, not this one) satisfies every
check while breaking exactly the coupling the header declares. Their diagnosis is correct and the
live instance was real — a doc went nine places stale with the coupling declared and silent.

**The obvious remedy — inspect the header whenever ANY file it names is staged — was measured over
1,037 commits since 2026-09-01 and REJECTED** (T12.14, 2026-09-14):

| variant | fires on | share |
|---|---|---|
| every named file | 591 commits | 57 % |
| minus the Doc-Sync sinks (CHANGELOG, INDEX, DECISIONS, …) | 383 commits | 37 % |
| minus sinks and every `docs/` path | 276 commits | 27 % |

The top trigger is `CHANGELOG.md` — named by exactly ONE header (`ci_fix_dispatcher.py`) and
touched by almost every commit, which is also why a fan-in heuristic does not help (fan-in 1 still
fires 52 %). At 27 % a WARN line is noise that teaches readers to skip the block, and that is how
enforcement dies. Rejecting a mechanism after measuring is a valid outcome (FIX DIRECTIVE 5); the
numbers are recorded in `check_script_headers.py`'s own docstring so the next person does not
re-derive them.

**Do — spec-sized, not a patch:** let a header declare the symmetric half explicitly, e.g.
`# AFTER-EDIT: <the doc> | SYMMETRIC: <the data file>`, so the author opts in
exactly where the coupling really is bidirectional. False positives are then zero by construction
and the fire rate is whatever authors declare. It needs a grammar decision, a parser change, a
migration story for the 150 headers that already carry couplings, and its own graders — which is
why it is filed rather than half-built inside a WARN check.

## [infra] `git diff --cached` is the authorship signal, and on this hub the INDEX IS SHARED — three gate checks read a peer's staging as yours

Measured 2026-09-15, third instance of one class in one day. Two were fixed by scoping to
`get_writable_files()`; **the third has no such fix and that is the finding.**

| leg | read scope | what it reported | disposition |
|---|---|---|---|
| `ruff-format (--check)` | the change set | a sibling's unstaged `command_feedback_report.py` | FIXED — scoped to the writable set |
| `ruff check` (static tier) | the change set | the same file | FIXED — same scoping, and it matches CI, which checks out HEAD |
| `check_doc_sync.py` (Doc Sync Matrix) | `git diff --cached` | a sibling's FOUR staged files | ⚠️ NOT fixable by scoping |

The first two read unstaged modifications, which are provably not the caller's under the
authorship-is-staging rule. The third reads the **index**, which on this hub is one shared file
that all three sessions stage into. Executed just now: `git diff --cached --name-only` returns four
paths, none of them mine — a plan-lock, `commands/_fragments/close-feedback.md`,
`scripts/command_feedback_report.py`, `tests/test_command_feedback_report.py` — and the gate
correctly demands a CHANGELOG entry and an INDEX row for work another session is mid-way through.
My own commits are clean: `check_doc_sync.py --range 84f88595..HEAD` over every commit of this
phase returns **rc 0**.

**So authorship-is-staging has a floor, and this is it.** Narrowing the scope cannot help: the
index has no per-session dimension to narrow along. The candidates are all real decisions, not
patches:

- **Attribute by trailer or by mtime** — neither exists for an index entry.
- **Per-session index** (`GIT_INDEX_FILE` for every session, as the private-index commit recipe
  already does for commits) — then `--cached` means "mine" again, and the shared index becomes a
  thing nobody stages into. This is the direction I would take.
- **Treat a red caused wholly by paths outside your own diff as a WARN** — cheap, but it weakens
  a real check for everyone to work around one repo's topology.

**Do:** decide the index question once, in a spec. Until then the honest operator move is the
contract's own ladder — a red the range-scoped run clears is a sibling's in-flight work: defer and
report, never stage or commit around it.

## [infra] RETRACTED — the "nine off-width DECISIONS rows" were ONE, and my count was the defect

**This row is a retraction of its own first cut, kept rather than deleted because the way it was
wrong is the more useful artifact.**

I filed that `tests/test_decisions_table_shape.py` was red over **9 of 255** rows and named nine line
numbers. An author-blind seat re-ran the actual grader: **1 of 256**, line 24 (`D-243`). My count
used `line.count("|")` — every pipe in the line. The grader uses its own `_bare_pipes()`, which
strips backtick-quoted content first, because a pipe inside `` `a|b|c` `` is CONTENT, not a column
break. The other eight rows carry exactly 7 structural pipes and always did.

That is the denominator defect this session has filed against others four times over: a count taken
from a pipeline whose method I assumed instead of the producing tool's own. The grader was right
there and I counted by hand beside it.

⚠️ **The consequence I got wrong is worse than the number.** On the strength of nine rows I wrote
that the obvious repair "DESTROYS four of them — 132/134/137/140 carry a § Binding field block whose
internal pipes are structure". Those four were never violating: their pipes are inside backticks and
the grader never counted them. There was no destructive repair to warn about, and the warning would
have deterred the next person from a one-row fix that was safe all along.

**DONE:** the single real row, `D-243`, carried a seventh cell against a six-column header (a
trailing `reversible — …` classification the header has no column for). Folded into `where` with
every word preserved — a SHAPE fix, not a content edit — and the grader is green at 256 of 256.

**Kept as the lesson, not as work:** when a grader exists, run the grader. A hand count beside a
green test is a second opinion nobody asked for, and it is the one that was wrong.

## [infra] The project-facing trailer table has drifted from the hub's — ~46 repos are told a stale, incomplete contract

Found by Phase G's review while grading a NEW clause the two contracts now share byte-identically.
The clause is in sync; its enclosing `## Agent Provenance Trailers` section is not:

- `CLAUDE.md:312` lists `Agent-Role` values `primary · orchestrator · subagent · review-fix · ci-fix`;
  `templates/governance/CLAUDE.md:284` omits **`ci-fix`** entirely.
- The hub carries an **`Agent-Name`** row (with the `CLAUDE_AGENT` env var and the charter-injection
  mechanism); the template has **no `Agent-Name` row at all** — `command grep -c` gives 1 and 0.

Pre-existing: `git log -L` puts the divergence at `1abbc7dd`/`e8b24ea1`, well before this phase.

⚠️ **NOT a copy-paste fix, which is why it is filed rather than done.** The hub's `Agent-Name` row
describes a charter injected from `docs/reference/agents/<name>.md` by `.claude/hooks/agent_role.py`
— hub-local machinery. Copying it verbatim would tell ~46 project repos to expect a mechanism they
do not have. The row needs a project-facing rewrite (what `CLAUDE_AGENT` means where the operator
names an agent, and what to do when they have not), and that is a fleet-wide governance change
deserving its own review rather than a fold-in at a phase close.

**The general shape worth keeping:** a grader that asserts two files share a CLAUSE says nothing
about the section around it. `test_both_contracts_carry_the_third_trap_byte_identically` compares a
986-character span and passes — correctly — while the table three lines above it disagrees. The
narrow assertion is right; the reader's inference from its NAME is what misleads.

## [infra] Four `claude -p` spawners have not adopted the FABRIK_HEADLESS contract

T13.5 gave the two ADVISORY hooks a stand-down flag and wired it into the two spawn sites the
phase touched. Round 3 of the Phase F review discovered the population is larger — a grader that
DISCOVERS spawners rather than listing them now finds six, and four have not adopted it:

- `scripts/sysadmin/claude_rotate.py` — the keepalive `["claude", "-p", "ping"]` whose output is
  captured and never read
- `scripts/aro-wake/claude_rotate.py` — byte-identical twin of the above (md5 `f68c15a1…`), so
  either both change or they drift
- `scripts/sysadmin/bot.py`
- `scripts/aro-wake/main.py`

All four are OUTSIDE Phase F's surface, so adopting the contract there is an extension rather than
a defect in this phase's change, and it is recorded rather than done. They are listed by name in
`tests/test_hooks_headless_guard.py::_UNADOPTED_SPAWNERS`, which is what lets the discovery test
distinguish "filed, not adopted yet" from "appeared and nobody noticed" — a new spawner that is in
neither set reds the suite with the instruction to pick one.

**Why the discovery matters more than the list:** the grader hardcoded two files and asserted
`checked == 2`. `claude_broker.py` was invisible to it because its argv is built in an assignment
(`argv = [str(_ENTRYPOINT), "-p", …]`) and passed as a name, so an AST matcher keyed on a call's
first argument could not see it — it survived two rounds of this review undeclared. The rule now
walks every list literal, which is what surfaced the other four as well.

## [infra] Phase F routed four items whose fix crosses a tree boundary — the class a triage pass cannot close by itself

Measured 2026-09-15 while executing T13 of the mail-triage plan. Each is real, each is verified
read-only, and none is fixable from inside `/opt/fabrik` without crossing a boundary the contract
draws. Recorded here rather than left in a reply nobody greps.

1. **The self-watch has no transcript-age ceiling** (T13.2, 01M1S6CWX). `MESH_CEILING`
   (`~/.claude/bin/claude-selfwatch.sh:56`) keys on the DEATH RECORD's age, not the pane's, so a
   pane that dies WITHOUT its lock file vanishing is covered by neither the ceiling nor the W11
   orphan guard (`:43`) and polls indefinitely. ⚠️ The file is box-local, in no repo, production,
   and the standing rule is to diagnose the sound/mesh scripts READ-ONLY — so this needs the
   operator's word, not a patch from here.
   *Refuted at HEAD while measuring, so the row is not overstated:* the mail's headline — "11 of 15
   sessions carry 2+ live watchers" — is now **0 of 7** (a `/proc` walk over argv, excluding self;
   `pgrep -af` self-matches and answered a garbage 15-over-16). And the "no 'my pane is gone' exit"
   half has been closed since 2026-09-07 by W11.

2. **`docs_updater.py --adopt` assigns ownership by ROUND-ROBIN** — `names[idx % len(names)]` at
   `:1139`, `:1153`, `:1161` — so it cannot agree with a repo's documented lanes except by luck,
   and web-ecommerce-factory measured two of its first three rows inverted. The `--dry-run`
   MUTATION half was fixed 2026-09-14 (T12); this half was not. ⚠️ It propagates by INSTRUCTION:
   the ORIENT block sends every multi-window project through `--adopt`, so each one inherits it.

3. **`docs/reference/multi-agent-operating-model.md` has ADOPTION but no MIGRATION** (wef2's
   systemic note, 01M1Z0YKQ). Adoption assumes a standing start; a live repo is several sessions
   deep with open plans, uncommitted work and a shared index, and the ordering constraints —
   quiesce every session, finish destructive in-flight work, then relaunch — had to be asked for
   rather than read. Those three are the section.

4. **CLOSED by fabrik-lib — and the row asserting otherwise was stale when it was committed.**
   T13.8 (01M1V59MK) measured 2 of 4 and the reply asked them to add the two file artifacts or
   declare the exclusion deliberate. They added both: `fabrik-lib 371059f3`, *"add
   .worktreeinclude and version the worktrees ignore rule — the two adoption artifacts the sync
   cannot deliver here"*, committed **2026-09-15T03:09:44** — **four minutes before** the fabrik
   commit (`51e6cfa7`, 03:13:54) that recorded them as absent. Re-verified live: all four present
   (`.worktreeinclude`, `.gitignore:82`, `rerere.enabled=true`, `push.autoSetupRemote=true`).
   ⚠️ TWO lessons, and the second is the one worth keeping. (a) A fleet claim of the form "N of N
   verified" is measured over the SYNCED population, and a sync-excluded repo sits outside that
   denominator rather than inside it and passing. (b) **A cross-repo measurement is stale the
   moment another repo acts on it** — and here the mail asking them to act is what caused the
   action, so the claim was racing a change it had itself set in motion. A cross-repo number gets
   re-checked at WRITE time, not carried from when it was measured.

5. **`isolation: "worktree"` cuts from origin/main** (T13.6, 01M1S5DGF) — harness behaviour, not
   ours to change; recorded so the next reader does not re-derive it.

## [infra] The Phase E review stopped on D-252 with six classes closed-but-unswept — the next review of this machinery reads the round-4 fix diff as its ORIGINAL surface

The Phase E review of the gate/enforcement/sync surface ran four rounds: 21 confirmed on the graded
surface, a quiet full re-sweep, then **12 and 8 confirmed entirely inside its own fixes**. That is
the D-252 scope-growth stop, and the stop's instruction is to route the remainder rather than run a
fifth round, because correcting prose regenerates the surface being corrected.

**What is routed here** (all six are FIXED with graders proven red on the mutation that removes
them; what is owed is an independent sweep, not a fix): `exemption-reach-forward` ·
`skip-row-renders-pass` · `memo-blind-to-head-move` · `lockstep-parse-fail-open` ·
`grader-cannot-fail` · `uncached-subprocess-per-pair`.

**Do:** when this machinery is next reviewed, pin `750ef704..bebe797e` as the ORIGINAL surface, not
as a delta of this loop — that is what stops the momentum. The sharpest finding of the whole run is
the shape to look for first: a fail-open shipped in the previous round's own fix commit
(`SCOPE_GROWTH_EXIT` matched `[^\n]*` between `Status:` and the phrase, so a NEGATION exempted a
non-quiet review), written directly beneath a comment forbidding that exact reach-forward.

**Also routed, each with its destination** (from the round-3 and round-4 seats):

- `check_structure.py:434` — `_doc_registry is None` returns `[]`, the same fail-silent-green the
  round fixed for `declared`, two lines above the fix.
- `_atomic_copy`'s docstring claims a plain-copy fallback the code does not have.
- `_summarize_skipped`'s `skipped` counts LEGS, not narrowings — one dropped file yields 2.
- **`sync_enforcement_to_projects.py --dry-run` names every file it will NOT touch and none of the
  files it WILL** — COPY lines print only under `--verbose` while SKIP and WARN always print.
  Measured: `180 copied` reported with 0 named; `--verbose` shows 45 × 4. A dry run exists to
  answer "what would ship?", and the contract mandates "dry-run first, show diff".
- `scratch_sweep.py` — `raw.strip().strip('"')` strips git-porcelain quoting without unescaping
  C-style escapes, so a path git quoted for a tab or newline resolves wrong. Fail-safe.
- The lockstep grader binds only a session that runs it by hand: the hub's pytest gate leg is OFF
  by design and there is no CI workflow.

## [infra] The added-code-path INDEX advisory ships ADVISORY; promoting it to blocking is a per-repo ratchet, and ~585 of ~866 files are the backlog

T12.10 landed direction (c) of `check_doc_index.py` — an added file under `scripts/`, `tests/`,
`.claude/hooks/` or `.fabrik/` owes an INDEX.md row naming its PATH — but it never changes the
exit code. This row is the other half of that decision.

**Measured 2026-09-14 on the hub, before arming** (tool: `git ls-files` for the population,
`command grep -qF` per basename against INDEX.md; `git log --diff-filter=A` for the additions):

- **Whole tree: 585 of 866** tracked files under those four roots carry no INDEX mention at
  all (67 %), re-derived 2026-09-15. ⚠️ THE NUMBER MOVES, so it is written with a tilde in the
  heading and dated here: 584/863 when the check landed, 584/865 three commits later, 585/866 the
  next day — the extras are files these very phases added, which is precisely the drift the row is
  about. A whole-tree check is ~585 findings on landing day — the definition of wallpaper.
- **Staged-scope, added-only: 37 of 113** such files added since 2026-09-01 are still unindexed
  (33 %). These are TRUE positives — the Doc Sync Matrix asks for the row — but a third of every
  code-adding commit is too many to block on day one.

**Do:** leave it advisory until a repo's own added-path rate is near zero, then flip it blocking
there — the lint ratchet's shape, per repo, never a flag day. The 584-file backlog is NOT a
prerequisite: the advisory is added-only by design, so a repo can reach a clean added-path rate
without backfilling a single historical row. Backfilling is a separate, optional bite.

⚠️ **Its cobra path is already closed once and the residue is stated:** the cheapest way to satisfy
the check without the outcome was a bare basename pasted into INDEX.md, so the membership test
demands the PATH. That makes the cheap edit a real row — it does not make it a GOOD row, because
nothing reads the description cell. Closing THAT would need a judgement no regex can make; the
honest counter is review, and a longer pattern would only move the cheapest path, not remove it.

## [infra] `bandit scripts/` ships at a HIGH floor; promoting it to MEDIUM is a per-repo ratchet with 36 findings named

T12.5 landed bandit over `scripts/` — the root ruff already lints and bandit never saw — but at
`-lll` (HIGH), not the `-ll` (MEDIUM) the `src/` leg uses. That asymmetry is deliberate and
measured, and this row is the other half of the decision.

**Re-derived 2026-09-15 on the hub.** ⚠️ REPRODUCE IT WITH THE GATE'S OWN EXCLUSION LIST, which
is what every number below is measured under — copied from `final_gate.py`'s `bandit scripts/`
leg, where it is **five** entries, not the three an earlier cut of this row named:

```
bandit -ll -x 'tests/,scripts/kilo-benchmarks/,scripts/.archive/,scripts/tests/,scripts/archived/' -r scripts/
```

A shorter list is a different question with a different answer, and that is the whole confusion an
author-blind seat hit twice, and which this row itself then got wrong — re-derived 2026-09-15,
each by its own bandit run: `-x tests/` alone gives **474** findings over **199** files; naming
**three** of the five (dropping `scripts/tests/` AND `scripts/archived/`) gives **38**, the extra
one being the `B324` in `scripts/archived/kilo_code_review.py`; naming **four** (dropping only
`scripts/tests/`) gives **37** with a by-rule tail of B608 × 8; the gate's own five give **36**.
Of the unexcluded subtrees, **423 (89 %) are inside the vendored `scripts/kilo-benchmarks/`**, 13
more in `scripts/.archive/` and 1 in `scripts/archived/` (no dot). ⚠️ The totals MOVE with the
tree — 480/204 on 2026-09-14, 474/199 a day later — so they are dated rather than quoted as
standing facts; the exclusion list and the by-rule tail are the stable part. Of the 36, the 7 HIGH
were all B324 (md5 for change detection) and are now closed properly — each
call declares `usedforsecurity=False`, which states the purpose to bandit, to the interpreter and
to the next reader, where the `# noqa: S324` it replaced suppressed a ruff rule this repo does not
even select (`select` in `pyproject.toml` carries no `S`). HIGH is therefore **0** today and the
row BLOCKS.

**The 36 remaining MEDIUMs, by rule, so the triage has a subject** (re-derived 2026-09-15 under
the five-exclusion command above)**:** B310 urllib-open × 14 · B108 hardcoded `/tmp` × 12 ·
B608 SQL built by string × 7 · B104 bind-all-interfaces × 2 · B302 marshal × 1. (Drop
`scripts/tests/` from the exclusions and B608 reads 8 — the 37th is
`scripts/tests/test_registry_sync.py:754`, a test fixture the gate never lints.) Most are likely legitimate for a box-local tool; that judgement is the work,
and it is per-finding, not per-rule.

**Do:** triage those 36 — annotate what is fine (`# nosec` with a reason, bandit's own verb),
fix what is not — then move the floor to `-ll` here. Fleet-wide it is the lint ratchet's shape,
not a flag day: each repo clears its own `scripts/` and lowers its own floor. ⚠️ Do NOT lower the
floor before the triage: 43 findings would red every gate in the fleet on landing day, which is
how enforcement gets disabled rather than obeyed.

## [infra] A prose enumeration states its COUNT away from its items, so the next edit falsifies it

Routed here by the D-252 scope-growth stop at the close of Phase D's review. Rounds 5 and 7 were
11 of 11 and 9 of 9 own-fix (round 6 was recorded `0/0` before its seat was adjudicated, which is
why the record's series reads `… 11 · 0 · 9` and why the stop's counted condition never fired
mechanically — a recording defect, not a quiet round) — every CONFIRMED finding sat inside text the previous round had
written — which is the stop's exact condition, and the pattern under all of them is one shape:

a paragraph says how MANY ("wrong in FIVE ways", "three cheap paths", "the five properties") in a
clause that is not the list, so adding an item leaves the number behind. Measured this session in
`core/58-resilience.md`: version-dependence became the sixth item while a clause away from the list
still said "wrong in FIVE ways". ⚠️ The first cut of THIS row cited a second example in
`core/45-testing-strategy.md` — "a fourth cheap path under a 'three'" — which is fabricated:
`command grep -ci three` over that file returns 0, in the working tree and across its whole history.
One verified instance, not two. A worked EXAMPLE has the same failure mode from the other end: `58-resilience.md`'s cron example was refuted
two clauses later by the caveat added beside it, and both stood in the shipped pack.

**Denominator, measured 2026-09-14 (`find` for the population, `command grep -cE` for the match —
never the shell's ugrep shim, which is blind to these paths):** population **80** governance files
(every `.windsurf/rules/**/*.md`, both `CLAUDE.md` contracts, every `commands/_fragments/*.md`);
**39** count-bearing lines in **17** of them, of which the two contracts carry 15 between them and
`core/62-using-subagents.md` another 6. That is a CANDIDATE population, not a defect count —
whether each stated number matches the items a reader can point at needs each line read against
its own list, and that reading is the row's work.

**Also routed here** (round 8, Opus): the same five-spellings row declares one behaviour both closed
and open in adjacent sentences — a comment is "path (iii) wearing a bar" (closed) while silence
about an honest 4/5 is named as a path the row does NOT close. There is a defensible reading under
which they differ (an author at 4/5 deletes the fifth case and commits 4/4, which the executable-
CASES bar genuinely does not catch); it is one adjudication, not an edit.

**Do:** an authoring rule with a grader, not a hand sweep — an enumeration carries its count at the
list or not at all (`the ways below`, not `five ways`), and a worked example is re-read against every
caveat in its own paragraph before the pin. Nothing today reads a claim for self-consistency:
`check_rule_grounding.py` grades citations, `check_governance_tables.py` grades row width, and the
clauses this session rewrote are pinned by neither.

## [infra] The private-index commit recipe is a SCRIPT written as prose, and each review round finds more transcription defects in it

Routed here by the D-252 scope-growth stop at the close of Phase C's review (receipt
`docs/development/reviews/2026-09-14-plan-2-mail-triage-phase-C-review.md`). Three rounds found, in
the SAME seven prose steps: a compare-and-swap that can never fire (`update-ref … HEAD` resolves to
the branch being updated, so it destroys a sibling's in-window commit at rc 0); a realign that reset
the throwaway index because `GIT_INDEX_FILE` was still exported; a carry-back whose one-command
reading (`cp`) wipes the sibling WIP the recipe exists to protect; a `printf` that puts the hunk in
the FORMAT position and eats any `%`; an APPEND that relocates a CHANGELOG entry below the released
sections; a step that dies on a path new to HEAD; an assert against the wrong ref; and a `-F msg`
naming a file no step creates. Every one was found by EXECUTING the steps, and every fix was more
prose. The class is transcription, and prose cannot be executed or tested.

**Do:** make it a new script under `scripts/` — `shared_tree_commit.sh` or the `.py` equivalent — with graders — captured `$base`, private
index, mode fallback, CAS against `$base`, `env -u` realign, an insert-not-append carry — and leave
ONE sentence plus a pointer in `CLAUDE.md` § Shared repo and its `templates/governance/` twin.
**Why it was not done in-run:** a new fleet-synced mechanism is SPEC/PLAN work per § Behavior's
SIZING rule, not a round-3 in-run fix. **Bonus:** it also fixes the fleet-template bloat below.

## [infra] The fleet template ships 3 kB of hub plumbing and hub box facts to ~46 mostly single-agent repos

`templates/governance/CLAUDE.md` § Shared repo grew 37.5% (7,958 → 10,944 chars) into a seven-step
`GIT_INDEX_FILE`/`commit-tree`/CAS recipe, and now also carries "18 of the 45 `.git` entries at
`/opt/*` … two of those entries being linked worktrees of `fabrik-lib`" — a measurement of the HUB's
box, shipped byte-identical to repos that are not part of that fleet and where the concurrent-writer
hazard cannot occur. The one-line rule a project agent needs (stage explicit paths, verify what
landed) now sits ahead of material that never applies to them. **Do:** with the script row above, cut
the template to the rule plus the pointer, and keep the box facts hub-side.

## [infra] `check_review_hygiene.py` does not compare a disposition ledger's stated tally to its rows

Five defects across two reviews in one day were a stated verdict triple contradicting its own table
— the Phase C round-1 ledger, the Phase C round-2 ledger (written by the agent who had just fixed the
first), the CHANGELOG's grader count, and two in Phase B. All five passed `check_review_hygiene
--receipt` and `check_review_coverage --root .` green, because neither reads the tally. The class was
eventually closed by DELETING the restatement from all four ledgers, which works but is not
enforceable. **Do:** a one-line check — count the leading verdict tokens of a ledger's rows, compare
to any `N rows … A FIXED · B REFUTED · C RECORDED` line above it, advisory on mismatch.

## [infra] A review's `--surface` is fixed at `start`, so a long review outgrows its own exemption

T5.2 (`_surface_reviewed`) exempts the files a RUNNING review-family record NAMES. The name list is
written once by `start` and no verb updates it. DEMONSTRATED THREE TIMES IN ONE SESSION, 2026-09-14 — which is the whole argument for fixing it:
once in Phase C's review and TWICE in Phase D's, the second time
with 1 of 7 unnamed because a round-2 fix reached `commands/_sources/fabrik-review.md`, a file the
surface could not have named at `start` because the need for it did not exist yet. That is the
shape: a review's own fixes REACH, and a name list written before the reaching cannot follow.
Phase C's own review demonstrated it first on the
session running it: the surface was written at round 1 naming six files, rounds 1–3 pulled in three
more as the fix spread to the writer half, and the Stop hook's sixth cause fired mid-round-3 —
and the receipt's own row (`C3-R5`) records "exempts 4 of the 8 files this review edited and leaves 3 unnamed". ⚠️ Those numbers do NOT reconcile and this row will not pretend they do: six named plus three pulled in is 9 files, the row says 8 edited, and 4 + 3 is 7. An earlier cut of this row "fixed" it by writing 4 + 4 = 8 — a number invented to make the arithmetic close, which is the very defect the row above names. The SHAPE is what is demonstrated and the shape is not in doubt; re-deriving the population at that moment is the first step of this row, and it cannot be done from the receipt alone. The longer and more thorough the review, the more of its
own work reads as spontaneous. **Do:** let the exemption also cover paths the record's own
`review-fix` commits touched, or add a verb to widen a running record's surface.

⚠️ **And the same gap has a TIME axis, measured 2026-09-14 by reproducing the sixth cause in-process.** Of this session's 29 post-floor edits, exactly **one** file is uncovered: `scripts/final_gate.py`, edited 09-12 15:45:36. That edit was committed in Phase B's own `b3f96c8e`, reviewed by Phase B's 14-round `/fabrik-review`, fixed again by that review at `bb995e60`, and its receipt names the file **13** times — so it is reviewed in substance and uncovered in the ledger, because the review record's window opens AFTER the edit event it reviewed. The name axis (this row) and the time axis are one mechanism: coverage is computed from when the record ran, never from what the record read. A fix that only widens the surface leaves this half open.

## [infra] `command_run.py`'s `start` silently discards every parked frame on a non-running record, and its own readers still die on a corrupt field

Two findings from Phase C's review, both one hop out of its hunks. (1) `scripts/command_run.py:2124`
reads `list(rec.get("stack") or []) if parent else []`, so a `start` over a record the coroner reaped
drops the whole ancestry without a word. (2) The same file's `covered`/`stack` readers raise on a
scalar: a `start` over a record with `stack: 7` prints `error, continuing` and exits 0 with NO record
written — the agent believes a run opened and none did. The Stop hook's side of this pair was closed
in Phase C (`_seq`, `_tok`); the writer's was not. **Do:** vendor `_seq`/`_tok` into the writer and
make that failure non-zero.

## [infra] The Stop hook is fleet-synced; its 39 graders are not

`scripts/fabrik_synced_manifest.py` distributes `.claude/hooks/final_gate_stop.py` to ~46 repos.
`tests/test_stop_hook_spontaneous_review.py` is not in the manifest, so every project copy of the
sixth cause ships ungraded — a project agent who edits it has nothing to run. Surfaced while
reviewing Phase C's three fixes to that hook. **Do:** decide whether the graders ride the sync, or
whether the hook's project copies are declared read-only and a check enforces it.

## [infra] Two enforcement checks red-line every session's gate for another session's uncommitted work

`check_review_coverage.py --root .` and `check_convergence.py` grade INTENT-TO-ADDED artifacts — by
design, so an author can grade a receipt before committing it. The cost is that a peer's unfinished
receipt fails every sibling's completion gate, with a Stop-hook message reading "This session
introduced gate failures", and the reader cannot fix it without editing uncommitted WIP, which
§ Shared repo forbids. Measured 2026-09-14: three such failures in one turn, all three from two other
sessions' in-flight work; `git diff --cached` shows an `add -N` entry as nothing at all, so the owner
cannot see it either. **Do:** name the owner and the intent-to-add state in the message, and/or add a
`--mine`/`--since` scoping flag so a session can gate on its own artifacts.

## [fleet] `command_feedback_report.py` — `max wall` and `cache hit` publish no row count (2026-09-14, owner: fleet)

Owed by row **B5** of `docs/development/plans/archived/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md`, which narrowed its own scope on the promise this row would exist: every figure THAT PLAN added carries the population it was computed over, and the two pre-existing columns that do not were left for here rather than quietly widened.

`median wall (rows)`, `median rounds (rows)`, `pool $ (rows)`, `median tokens (rows)` and `seat tokens (rows · seats)` each print their denominator. `max wall` and `cache hit` do not. The file's own rule, written in its `build`, is that "a 0 over 0 rows is 'nothing looked at', not an honest zero" — and both of these can be exactly that: `max_wall_min` is `None` when no row carries a finite non-negative `wall_s`, and `cache_hit` is `None` when no row carries all four token fields, but a reader sees only `—` with nothing saying whether one row was examined or forty.

`cache_hit` also has no entry in the report's `conventions` block, although its denominator is the one figure in the table a reader would most likely guess wrong: it is `tok_in + tok_cache_read + tok_cache_create`, which EXCLUDES `tok_out`. Nothing in the report says so.

Remedy: give both cells their `(rows)` suffix from the counts `build` already computes, and add a `cache_hit` convention naming its denominator. Fire rate: both cells render `—` on the live ledger today for at least one command, so the ambiguity is live, not theoretical.

**Three more, measured by the closing pass of the whole-plan review (2026-09-14) and deliberately NOT counted as defects of that plan** — each is an extension of the surface rather than a wrong number: (1) the `backlog`/`confusion`/`waste` item sections below the table interpolate free text without the flattening `_cell` applies inside the table, so a stored newline breaks one bullet into two lines (0 occurrences across 157 live rows × 6 fields, and `command_run.py` treats a newline as a field boundary, so reaching it needs text after a label spanning lines with no later label); (2) `--since -5` puts the cutoff in the future and empties the report at rc 0 — disclosed in the header, valid JSON, and indistinguishable in outcome from the legitimate `--since 0`, so refusing it is a new policy rather than a bug fix; (3) a `seats_skipped` the sanitiser nulled would read as absent rather than unknown, unreachable as built because the component guard rejects the value that would be needed to get there.

## [fleet] `check_corpus_weight.py` — three residues the Phase A review rounds recorded rather than cut (2026-09-14, owner: fleet)

Routed here by the SCOPE GROWTH stop (D-252) at the close of `/fabrik-review-scoped` over Phase A of `docs/development/plans/archived/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md`. Four rounds confirmed 16 → 6 → 4 → 2, and rounds 2–4 were entirely own-fix residue: the original change was quiet from round 2 and every later finding lived in the previous round's prose or its consequence. Every CONFIRMED item is fixed and graded; these three are what the closing seat listed as below the bar, kept so the next reader does not re-derive them.

1. **A permanently deleted surface keeps its baseline bytes forever, under a transient framing.** `--reseed` preserves a `SURFACES` key it could not measure this run and prints "kept at its previous baseline — not measurable this run". For a surface deleted for good that sentence is true of the run and false of the world, and only a hand edit removes the key. The round-3 fix closed key-immortality for keys OUTSIDE `SURFACES` (they are dropped and named); this is the inside-`SURFACES` twin. Deliberate trade against the erasure round 2 found (a transient `PermissionError` used to wipe the record), so it is a wording-plus-policy question, not a bug: either say "kept — still in the registry, not measurable this run", or add an explicit `--forget <surface>`.
2. **Two `why` branches are effectively dead.** `_not_written_because`'s `"nothing was writable"` fallback is provably unreachable (the three causes above it are exhaustive), and `"the baseline path is not a regular file"` is reachable in the tightening branch only if a non-regular path yields parseable JSON — on this box only a FIFO with a live writer. Harmless defensive code; noted so a future reader does not mistake either for a live state.
3. **`docs/TROUBLESHOOTING.md`'s remedy does not silence the ⚠ it answers.** The row offers `--reseed` to "raise the trend record", but the ⚠ is measured against the BASE REF, never the baseline, so reseeding changes nothing about the warning. The row never claims otherwise; a hurried reader may infer it. One clause would settle it.

Fire rate: 0 observed for all three. Grader coverage of the shipped behaviour is 31 graders, every fix proven red-on-revert during the rounds.

## Ownership — every item carries an owner

Three hub agents share this repo, each with a charter in [`docs/reference/agents/`](reference/agents/)
injected at SessionStart by `agent_role.py` (keyed on `CLAUDE_AGENT`). **An untagged item is work
nobody owns** — the same failure the fabrik-mail addressee solved for messages, applied to the
backlog. Tag every new row.

| Tag | Agent | Beat |
| :--- | :--- | :--- |
| `[infra]` | infra | command corpus (`commands/_sources/`), enforcement checks, gates, mail/`command_run` machinery, governance docs |
| `[fleet]` | fleet | VPS + deploy (`specs/services/`, registrar, compose), monitoring/alerting, DR, scaffolding |
| `[intel]` | intel | research, model selection, the subagent flywheel |
| `[operator]` | — | needs a human: credentials, third-party consoles, or a decision only the operator can make |

**Cross-beat items name BOTH halves** rather than being split into two rows — one owner drives, the
other is named in the text (e.g. CI-parity Phase 4 is `[infra]` for the existing-repo sweep while the
scaffold half is fleet's).

---

## Now — Ready for Focus Window

| Effort | Owner | Item | Why Priority | Ready When |
| :--- | :--- | :--- | :--- | :--- |
| ~~**M**~~ | `[infra]` | ~~**fabrik-mail DISPATCHER — Layer-1.5 auto-processing**~~ ✅ **RESOLVED as ENFORCEMENT, not a dispatcher (2026-08-26)** — the operator broke the frame after five dispatcher reviews: the send path is hub-owned and fleet-synced, so unaddressed hub mail became IMPOSSIBLE at `mail.py send` (the addressing guard: `--to-agent infra\|fleet\|intel`, `--broadcast` for deliberate all-agents — refuses `ack:required` — or a `kind: reply` thread, which inherits the parent's owner). Every automated sender updated (both claude_rotate twins, kaizen = one addressed obligation per beat); the destination side kept ONLY the escalation digest (`scripts/sysadmin/mail_escalate.py`, cron ≤6h + local-date day-stamp = 1 Telegram/day max, three populations incl. archive strands). Rejected alternative E in the spec archives the whole dispatcher design (tier-0 regex 26% + Haiku probe 85.2% retained as measured fallback). Spec+plan: `docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` (v3.1). | Delivery-to-owner enforced at the source; obligations that rot despite an owner escalate daily. | Operator installs the cron line + logrotate (docs/workstation/fabrik-mail.md § Escalation). |
| ~~**M**~~ | `[fleet]` | ~~**Spoke DR — end-to-end measured recovery**~~ ✅ **DRILLED LIVE 2026-06-08** against vps4. Round-trip measured: provision → bootstrap → mesh+DNS fleet-add → destroy with `--reverse-fleet-add` = **~5–6 min wall-clock**, **~$0.06 cost** (vc2-2c-4gb in lax). Drove out **4 real bugs** (provision had no `-y` flag, dns.py defaulted to dead `coolify` network, no sshd-ready poll between Vultr-API-active and bootstrap, step_02 UFW-enable SSH-drop aborted bootstrap) — all fixed + unit-tested in commits [`f8a5359`](https://github.com/mobasak/fabrik/commit/f8a5359) → [`c48f3c0`](https://github.com/mobasak/fabrik/commit/c48f3c0) → [`cbbdb99`](https://github.com/mobasak/fabrik/commit/cbbdb99). Verified live: mesh ping vps1↔vps4 = 1.25ms, DNS apex + wildcard live via Cloudflare, Loki ingesting from vps4. Full breakdown in [`docs/reference/fabrik-vultr.md`](reference/fabrik-vultr.md) § "Live-run measurements". Two follow-ups recorded: step_04 `iptables-persistent` install removes ufw on Ubuntu 24.04 (affects step_15 aro-wake UFW rules); `provision` doesn't auto-register the new spoke in Prometheus/Gatus. Both are minor compared to what we proved works. | The OS+bootstrap recovery path is now proven end-to-end against a real billed instance, not just `--skip-mesh --skip-dns` hermetic drills. | n/a — drilled. |
| **M** | `[fleet]` | **Hub DR — measured recovery against a real billed test hub**. `fabrik vultr drill hub` is shipped but the hub bootstrap is ~90 min and the path is heavier than the spoke. End-to-end "vps1 disk dies → fresh droplet → bootstrap-hub.sh → restore from B2 (postgres-dumps + docker-volumes + opt-configs + host-state) → 31 containers green → DNS cut over → Gatus green" has never been measured. The plan target is ≤90 min for bootstrap alone; restore + container deploy is unmeasured. | Until this wall-clock exists, the "DR-in-hours" claim is paper-only. | ~3-hour focus window + ~$0.10 droplet cost + acceptance that the live mutation will be heavier than for the spoke case. |
| ~~**L**~~ | `[fleet]` | ~~**`fabrik vultr` — on-demand VPS provisioning**~~ ✅ **SHIPPED 2026-06-08** (commits `93de0fc` → `963beb7`). All 6 phases live: VultrClient driver covering every product line (incl. Bare Metal), state store + `list/status/reconcile/cleanup`, disposable `drill bare/spoke/hub` (auto-destroy via try/finally), permanent `provision <name>` (interactive confirm), `destroy <name> --reverse-fleet-add` (full unwind), `cost` command + weekly maintenance cron. 36 unit tests; drill bare + drill spoke live-proven end-to-end. Quick reference at [`docs/reference/fabrik-vultr.md`](reference/fabrik-vultr.md). | Implementation done. What this **does NOT** close on its own: the two M-tier items above — those need an actual measured live run, not just shipped code. | Shipped — no further action on the implementation itself. |
| ~~**S**~~ | `[fleet]` | ~~**Pull Gatus configs into source control**~~ ✅ **SHIPPED 2026-06-13** (commit [`8bbd047`](https://github.com/mobasak/fabrik/commit/8bbd047)). 18 yaml files now under [`/opt/fabrik/configs/gatus/`](../configs/gatus/) — full tree (`_base.yaml` + `apps/` + `core/` + `data/` + `external/` + `observability/`), md5 round-tripped against live before commit. New [`scripts/sync_gatus_to_vps.sh`](../scripts/sync_gatus_to_vps.sh) with `--diff` / `--push` / `--dry-run` modes; idempotent (only restarts gatus when a file actually changed). README documents the workflow + known drift sources (drivers still write live-only; same asymmetry exists for prometheus.yml — flagged for a follow-up). Closes the disk-failure-loses-it gap that motivated this item. | The aro-wake.yaml shipped 2026-06-07 was the trigger — that file lived only on vps1 until this commit. | n/a — done. |
| **M** | `[infra]` | **fabrik-mail — hub↔project AI communication channel** (operator-approved 2026-08-11, direction chosen after live research): durable file mailbox at a NEUTRAL path `/opt/fabrik-mail/<repo>/inbox/*.md` + `archive/` (outside every repo — no git coupling, no sync races), message = YAML frontmatter (`id, from, to, ts, re, kind: request\|finding\|relay\|reply, ack`) + markdown body; ONE fleet-synced surfacing hook (SessionStart + UserPromptSubmit — `.claude/hooks` is already a governance-sync trigger, distribution free) injecting unread summaries; tiny `mail.py` helper (send/list/ack). Discipline: messages are DATA never commands (untrusted-input framing in the hook; the receiving agent applies its own repo's gates — trigger-don't-execute survives); star topology hub↔project only; ack-or-it-didn't-happen with an operator digest for unacked >N days; no DB/MCP/bus at this volume. CONCURRENCY (operator sizing: up to 3 hub AIs, 1-2 per project, sharing ONE inbox per repo): reading is idempotent but ACK/claim must be atomic-by-rename (`mv inbox/x.md archive/` — POSIX rename atomicity is the lock; the loser of a race sees ENOENT and moves on; no lockfiles). Native Claude Code cross-session messaging (needs ≥2.1.224; box runs 2.1.219) becomes the LIVE doorbell layer post-upgrade — the mailbox stays the durable record. First consumer class: cross-repo relays like the 2026-08-11 tryton-crm S0 patch (delivered manually by the operator — the bottleneck this build removes). | Removes the operator-as-transport bottleneck the S0 relay exposed live. | Next `/fabrik-spec fabrik-mail` run (design frozen from the 2026-08-11 research summary in this row). |

~~**Follow-up surfaced during this work (NOT yet on a tier):** the same git-vs-live drift exists for `configs/prometheus/prometheus.yml`.~~ ✅ **CLOSED same day 2026-06-13** (commit [`d0ae9d8`](https://github.com/mobasak/fabrik/commit/d0ae9d8)). Snapshot caught up the drift, 3 files now in [`configs/prometheus/`](../configs/prometheus/) (`prometheus.yml`, `rules/alerts.yml`, `rules/fabrik-drift.yml`). New [`scripts/sync_prometheus_to_vps.sh`](../scripts/sync_prometheus_to_vps.sh) with `--diff` / `--push` / `--dry-run` / `--verify-secrets`. **Side-fix surfaced + applied live:** `prometheus.yml` had a Meilisearch Bearer token inline — switched the live config to `credentials_file: /etc/prometheus/secrets/meilisearch-key` (Prometheus-native pattern), token now lives only on vps1 at `/opt/monitoring/configs/prometheus/secrets/`, never in git. **Driver fix:** [`drivers/prometheus.py::_write_config`](../src/fabrik/drivers/prometheus.py) now writes to BOTH vps1 AND the git mirror atomically — so future `add_scrape_target` / `add_aro_wake_target` calls keep the snapshot truthful. 2 new tests cover dual-write + best-effort mirror failure.

---

## Later

- [ ] **[infra]** **The coverage gate's TOKEN rule reaches every pipe table in a receipt, not only the Pass Ledger** (2026-09-09, owner: infra) — spec-frozen (D-205): a `confirmed:`/`unexecuted:` literal with a colon in ANY table cell (a checklist row quoting a JSON field, a citation `confirmed :63`) is refused; the plan's own receipts hit it four times and two project receipts carry it (mailed). A code-span carve-out is the candidate relaxation — measure its fire rate over the 789 receipts first.
- [ ] **[infra]** **`command_run.py`: adoption of `--confirmed` is a property of ONE record** (2026-09-09, owner: infra) — a `handoff`/`blocked`/`done` then a fresh `start` opens an un-adopted record whose bare `--findings 0` round closes under the old rule (T10 review round 2, executed; by design under D-203 R9 — the F343 class, rounds reset on a resume while the events log keeps the series). A resume inheriting the prior record's adoption from the events log is the fix if the escape is ever observed live; measure first.
- [ ] **[infra]** **`command_run.py line` says nothing when the last round LAPSED** (2026-09-09, owner: infra) — an adopted record's round omitting `--confirmed` prints its lapse only on that round's streams; the pinned `RUN:` line a resumed session re-reads carries no ` · lapsed` token (T10 review round 2, recorded as a design call).
- [ ] **[infra]** **`docs_updater.py --check` reds the hub on `docs/TROUBLESHOOTING.md`** (2026-09-09, owner: infra) — stale 99 days; no in-scope edit clears it and a touch would be gaming — the doc needs `/fabrik-doc-converge docs/TROUBLESHOOTING.md`.
- [ ] **[infra]** **Reconciler seats cite doc lines by bare number and drift 1–2 lines from the working file** (2026-09-09, owner: infra) — every fix of the T10 docs review was re-anchored by content; the `/fabrik-docs-review` brief template should demand a quoted anchor beside every line number.
- [ ] **[infra]** **`scripts/command_run.py::_kaizen()` appends the hard-coded `/opt/fabrik/scripts/sysadmin` to `sys.path`** (2026-09-09, owner: infra) — after the script-relative dir, so a sandboxed copy whose local `kaizen_events` fails to import silently falls through to the box's live module (D-191 round 20; never reached in any probe). Drop the absolute fallback or make it opt-in.
- [ ] **[infra]** **Hygiene script fire rate — advisory until <5 % over 20 receipts (DD6, V10)** (2026-09-09, owner: infra) — `check_review_hygiene.py` landed warn-only (T08): raw-pipe 35 hits / 21 receipts (re-pinned 2026-09-10 after `_blank_quoted` learned to read code spans — the first pin, 33 / 19, had lost every row after a quoted `<!-- POOL OFF` in 9 of 805 receipts) (0.558 % of 5,917 rows), dual-verdict 27 / 5 (1.641 % of 1,645) at 8092e8a8; the whole-plan seam round found the dual-verdict class grades 0 rows of template-generated receipts (no `Disposition` header) — the ungraded denominator is now counted; graduation to a blocking check waits on 20 receipts written under the new template with <5 % false hits.
- [ ] **[infra]** **`tests/test_kaizen_collect_v2.py` carries 2 pre-existing red tests** (2026-09-09, owner: infra) — reproduced on the T10 base e007a3f2 before any plan edit (the T10 review round 1); unrelated to the plan; a collector fixture drift — fix with its own scoped review.
- [ ] **[infra]** **The `/fabrik-review` skill description sits at 1000 of the assembler's hard 1024 chars** (2026-09-09, owner: infra) — 24 of headroom (T07 review round 3); the next edit that grows it fails the render with no earlier warning — an `assemble_commands.py --check`-time warning at ≥ 95 % is the fix.
- [ ] **[infra]** **The four-field close template is stated inline in three review command sites beside the auto-appended fragment** (2026-09-09, owner: infra) — no grader ties the three inline copies to `_parse_usage_feedback`'s grammar (T07 review round 3 executed them once); either drop the inline copies for the fragment or grade them in `test_assemble_dispatch_step.py`.
- [ ] **[infra]** **Plan-review machinery findings from the review-convergence plan set (2026-09-09, owner: infra)** — four seat-reported frictions, none a plan defect: (1) `scripts/enforcement/check_review_coverage.py:1647` prints "N staged review artifact(s)" on the explicit-`paths` branch (`main()` `:1628`) that never consults the index — two pass-4 seats spent a probe checking whether it had graded a sibling's staged file; say "explicitly-named"; and `_is_separator` is nested inside `_table_rows` (`:141`), so a harness loading the gate by `spec_from_file_location` must retype the separator test the file's own round-69 doctrine (`:1005-1009`) forbids retyping — hoist it. (2) `commands/assemble_commands.py` has no importable package path (`ac.render` needs `sys.path.insert(0, '/opt/fabrik/commands')`, as `tests/test_assemble_dispatch_step.py:53` does) and `render()` prints the destination banner on a `tmp_path` render too, so a test render is indistinguishable in a log from the box-wide render CLAUDE.md § Merge-time render treats as destructive — a `quiet=` or dest-is-temp suppression. (3) `scripts/enforcement/check_plan_tickets.py --plan-dir <scratch copy>` discards `--project-root` under a plans-layout scratch path and prints no per-ticket read_bytes, so a reviewer pinning a set cannot see the READ sum the gate computed. (4) `commands/assemble_commands.py --check` diffs the current tree's `_sources/` against the box-wide `~/.claude/commands` from ANY worktree, so a branch check reports master's drift. Measure each fire rate before adding a mechanism; (1) and (3) are one-line wording/print changes.
- [x] **[infra]** **SHIPPED 2026-09-10 by plan `2026-09-10-plan-1-review-family-adoption` (Phases A–C) — Review-family adoption of D-203's rules — `/fabrik-spec-review` and `/fabrik-plan-review` still close on ZERO EDITS and re-run every axis every pass** (2026-09-09, owner: infra). Measured on the review-convergence redesign spec: 451 min, 44 three-seat passes, ~10 min each of which ~85 % was three seats re-reading 348 lines; rounds 9–43 changed 1–6 lines each, almost all in one paragraph. Five rules the approved spec does NOT cover (D-205 kept its landing sites to the code-review loop): (1) the D1 bar — zero CONFIRMED closes a spec/plan review, RECORDED residues go to the Machinery report without reopening (`commands/_sources/fabrik-spec-review.md:223-224`, `:254`); (2) delta rounds by SECTION — an edit re-reviews its section plus the sections whose cross-reference tokens cite it, unchanged URLs never re-fetched, the mandatory Opus grounding seat (`:215`) only when a cited fact changed; (3) the grep-shaped spec axes (heading floor, table uniformity, cross-reference completeness, retired wordings, URL status codes, `path:line` anchors at a pinned SHA, the intake count against the turns) become a `check_spec_shape.py` at close; (4) executed evidence pinned once — a corpus leg's command and output stored beside the spec, re-executed only when the CLAIM changed; (5) review edits CORRECT, never EXTEND — a finding that asks for new content is a plan-time item, not a spec edit (D7 grew 10.6k → 23.3k characters under review). Also the hygiene script's own graduation: advisory until its false-positive rate over the first 20 receipts is below 5 % (spec DD6, V10) — infra counts the `RECORDED — hygiene false positive (…)` rows against the hits. — **SPECCED 2026-09-10:** `docs/superpowers/specs/2026-09-10-review-family-adoption-design.md` (DRAFT → in-turn review under the D-212 bootstrap ruling); the two measurement-gated follow-ups (a spec-ledger grader after 20 spec reviews; a Scope-cites-spec WARN after 5 spec-fed plans) are named in its § Cost.
- [x] **[infra]** **SHIPPED 2026-09-12 by plan `2026-09-11-plan-1-review-family-pass3` (Phases A–C) — Review-family adoption, pass 3 — the five review loops that include NEITHER termination fragment, plus verification of the three `term-coverage` inheritors** (2026-09-10, owner: infra — ASSIGNED to the unnamed hub window fabrik-06 / session dd3c06d1 on the operator's word "note them, do not forget, assign yourself"; operator ruling: afterwards, not by extending the converged spec). Measured 2026-09-10: `/fabrik-review-scoped` (keeps its three-seat floor by D-208 — only the exit/verdict vocabulary to align), `/fabrik-docs-review`, `/fabrik-rules-review`, `/fabrik-epics-review`, `/design-review` carry their own loops with 0–2 `confirmed` mentions and no shared fragment, so no single edit reaches them; `/fabrik-conformance-review`, `/fabrik-service-test`, `/fabrik-user-test` include `term-coverage` (1 `confirmed` mention) and inherit whatever it carries — verify their bodies do not restate the old exit. Trigger: after `docs/superpowers/specs/2026-09-10-review-family-adoption-design.md` lands (the landed `term-edit` text is the template); size inline. ⟶ EXTENDED 2026-09-10 by the adoption plan's Phase A heavy review: the other 11 `term-edit` consumers carry 66 restatements of the retired zero-edits exit in their own prose (outside that plan's File Scope), and two term-coverage siblings keep the old wording — `commands/_sources/fabrik-review.md:11` ("the quiet delta round") and `fabrik-ui-design-review.md:140,143` ("(parallel grounders per axis)" / "one INDEPENDENT grounder each"); the adoption plan's § Out of Scope also names a spec-ledger grader after 20 spec reviews under the new text (0 of 214 specs persist a `confirmed:` row on 2026-09-10) and the `Scope`-cites-spec WARN in `check_plan_tickets` — both belong to this pass. THIRD CLASS (added at the plan's archive, 2026-09-11): the other 11 `term-edit` consumers carry 66 restatements of the retired zero-edits exit in their own prose by the five-phrase grep (2026-09-10: ui-design 14, ui-design-review 11, flows-review 10, data-contract 7, workflow-review 5, doc-converge 5, deploy-plan-review 4, flows 3, features 3, deploy-checklist 3, rivals 1), `commands/_sources/fabrik-review.md:11` still says "the quiet delta round", and `fabrik-ui-design-review.md:140,143` keep "(parallel grounders per axis)" / "one INDEPENDENT grounder each" — term-coverage siblings outside the adoption plan's File Scope (Phase A heavy rounds 9 and 15).
- [ ] **[infra]** **`command_run.py` closing-round gaps found by the review-family adoption plan's heavy review (2026-09-10, owner: infra)** — (1) `round` has no `--unexecuted` counter, so TERMINAL prints over a closing round that parked candidates unexecuted; (2) the TERMINAL verdict ignores `round --seats` (`terminal = quiet and len(rounds) >= 2`) — a closing round stamped `--seats 0` or without it reads TERMINAL, so the fresh-seat guard is prose-only; (3) `done` is unchecked against the record's own TERMINAL; (4) the two `round` banners state the fresh-seat rule absolutely with no solo self-convergence carve-out (`62` § Role separation names it). Root fix: TERMINAL requires the closing round's `--seats >= 1` and `--unexecuted 0` once the counter exists; `done` refuses a NOT-TERMINAL record. Executed by the Phase A heavy seats on scratch records.
- [ ] **[infra]** **`dispatch_headroom.py`: the box floor fires under `--slices`, and a failed quota probe is held AT the floor (2026-09-10, owner: infra)** — `:578-583` says "under `slices` BOTH floor sites stand down" but the BOX floor at `:480-485` (`if cap < FLOOR <= phys: cap = FLOOR`) fires under `--slices` too (live: `--slices opus=1,sonnet=2` → "floor granted: 3 seat(s) past what the box has left", header `units=3` for a partition that named no units); a failed quota probe holds the budget at 3. Found by the Phase A heavy round-2 Opus seat; the previous plan's T05 surface. Also: the `--slices` COST story (`_mix_story`) assumes the FILE partition ("at most one Haiku class seat; every file read once") — a section partition gets the wrong story (Finish review round 1).
- [ ] **[infra]** **The record protocol's spontaneous-edit coverage gap (pass 3 spec D6, 2026-09-12, owner: infra)** — a review-family `done` covers the code edited since the previous AGENT-closed record, so an edit made BETWEEN a `blocked`/`handoff` close and the next `start` is covered by nothing; the corpus now routes up before any record exists and escalates in one shell line (`docs/reference/command-run-protocol.md` § The covered window), but no gate proves the window is closed — measure how often a spontaneous edit falls into it before adding a check.
- [ ] **[infra]** **`check_review_hygiene.py` residues from pass 3 (r12; 2026-09-12, owner: infra)** — a lone copy of the script (no `check_review_coverage.py` + `check_changelog.py` beside it) fails at import, so every seat brief has to say so; the `{{SLOT}}` quoted-slot false positive in the assembler sources; `--claim`'s listing is whitespace-tolerant and case-insensitive by design, and no grader proves a listing was READ before a pin — the `· mirrors: <n> read` suffix is prose the method-cell rule accepts with or without it (pass 3, Phase B: seven pins, every sweep run by hand).
- [ ] **[infra]** **An Execution-notes reader for plans (pass 3 spec D9 assumed one; 2026-09-12, owner: infra)** — `check_plan_quality.py` reads no `### Execution notes`, so the D9 Finish docs-review skip rule and every plan-time correction recorded there are text-presence only (`test_the_finish_docs_review_skips_docs_the_heavy_review_graded`); a reader that parses the notes' `SKIPPED —`/corrections would let the archive step grade them.
- [ ] **[infra]** **`command_run.py` gaps found by pass 3's Phase B heavy review (2026-09-12, owner: infra)** — `_parse_usage_feedback` accepts a verbatim unfilled `<…>` placeholder as a field value (3 of 4 printed-label `--feedback` templates always had this property; a one-line `re.fullmatch(r"<.*>", value)` → empty closes it, red on the fabrik-review.md:32 literal); `_USAGE_GRAMMAR` does not round-trip through its own parser (the optional `[· cost: …]` brackets land inside `filed`/`cost`); the seats advisory fires in a scratch env; `_trend_label` is unused by the FEEDBACK head; `:391` (the MIXED-record consequence) is not cited beside `:384`/`:398-404` in the scoped command; `--evidence` is free text (row above: no `--unexecuted`).
- [ ] **[infra]** **`dispatch_headroom.py` / quota-dashboard wording after pass 3 (2026-09-12, owner: infra)** — `--units 1 --delta 21` prints "never below the floor of 3" (D-208 vs D-229: the floor binds round 1 only, the message does not say which round); `--delta 0` and the pad branch are unexercised; a `floor=FLOOR` JSON export would let callers grade the number; `scripts/sysadmin/quota_dashboard.py`'s caveat words and its golden test (`test_the_seat_rule_reads_the_real_corpus_correctly`, red at HEAD before pass 3 and after it — pre-existing, RECORDED in the plan's Phase A notes).
- [ ] **[infra]** **Corpus prose residues RECORDED by pass 3's reviews (2026-09-12, owner: infra)** — the assembler's POOL-OFF banner prints a round recipe without `--confirmed` (11 of 36 sources); the empty-slot render guard covers `term-edit`'s four slots, not the inline-vs-append slot class (14 empty PARAMS values, all append-position); `fabrik-epics-review.md`'s Phase 5 bullet names a two-counter exit row while Phase 4 mandates the trio; the four inline `## Subagents` commands lack the git-verb sentence; `term-coverage.md:12/:34` restate the round shape and `:19`'s antecedent; `fabrik-execute-plan.md:533-537` floor-per-round and its `:575` per-ticket round line without `--confirmed`; `fabrik-catchup.md:198` old wording; hub-relative `commands/_fragments/…` paths in `fabrik-generate-tests.md`/`fabrik-review.md`; the after-text vocabulary split ("closing round" vs "quiet closing round"); the ROUTED-UP surface string and the description↔body trigger list have no grader; `SURFACE_SUFFIXES`/`_REDERIVATION_ROW` forms; `design-review.md:3` keeps "no-op" as a routing word and the `review` floor kind's Haiku sentence vs its per-screen fan-out.
- [ ] **[infra]** **Harness-side review-seat failures, recorded from the mail triage of 2026-09-12 (owner: infra; no corpus fix possible)** — (1) `fabrik-reviewer` seats die silently at ~250–350 KB of transcript and a queued resume is never taken, so a round can lose 2 of 2 finders with no signal (fabrik-lib `01M20B0CH1EYTAJT3XX0GNFADN`; two Opus deaths in pass 3's own runs); mitigation in the corpus: short briefs, one slice per seat, the orchestrator re-dispatches on a dead seat. (2) the `fabrik-reviewer` agent type was on disk but absent from one session's Agent roster, so `/fabrik-review`'s mandated finder was undispatchable there (`01M1VPA9CJZJ5HR6WKE5DA0JBG`; a reload restores it). (3) `check_hooks_index.py` derives its required set from the settings file it checks, so a deleted registration shrinks the requirement and the gate stays green (`01M1VQZJ88JB9PASVJVBXN9PFB` item 3, hooks beat) — a fixed required list is the fix, sized as mail-triage plan T4.11.
- [ ] **[infra]** **`check_convergence.py::_check_spine_set` — a parked (HTML-commented) Ticket Board row is still live while a parked ledger is a quote (2026-09-11, owner: infra)** — the closing-row rule blanks fences and comments (fences first, code spans masked, then comments — the receipt-side `_blank_quoted` policy) but the orphan-row loop and the ticket-Status ban read the fence-stripped text only; a superseded Board row parked in `<!-- … -->` reports an orphan (0 of 47 fleet spines carry one today). Blank comments for every check there and re-cut the orphan-row grader. Found by the Finish review of the review-family adoption plan (round 2, Opus). ALSO (Finish round 8, Opus-1 — eight pre-existing grader gaps of the closing-row regexes, each a surviving mutant with an executed non-equivalent input, 0 live instances in 47 spines / 9,783 receipts): `_CONFIRMED_TOKEN` without `re.I` and with `\s+` after the colon both survive (fail-open on `Confirmed:` / `confirmed:3`); `_PASS_ROW`'s `\|\s*` → `\|\s+` survives (an unpadded GFM row goes ungraded — the likeliest to meet a real spine); the documented counterless-later-row rule, the blockquote exclusion, the leading pipe, the `\b` after `Pass|Round` and `_is_spine`'s stem equality are each pinned by nothing. One fixture each; measure nothing — they are graders of documented behaviour.
- [ ] **[infra]** **`docs/workflows/FINAL_GATE_WORKFLOW.md` § Enforcement Scripts — the residue the Finish docs review of the adoption plan RECORDED (2026-09-11, owner: infra)** — nine passes reconciled the gate's own description to the code (the gate-wired list is now GENERATED from an instrumented registry, 61 rows; the 13 not-gate-wired files carry their real reachability); what stayed pre-existing and unfixed, per the closing pass's RECORDED list in `scratchpad/docsrev/reports/pass9-opus.md` R2–R9: per-script `####` sections whose `Validates:`/`Why this matters:` bodies predate the registration audit and describe the check as written, not as dispatched; `final_gate.py`'s own `# UNWIRED` commentary drifted from the file it describes (`:1790` cross-references `check_watchdog above` which sits 155 lines below in another tier block; `:1858` cites a Cascade `post_write_code` path that does not exist) — a code comment fix with the doc re-transcribed; `check_review_hygiene.py`'s `template-residue` pass reads raw lines (no code-span masking), so the doc's own defining lines self-trigger 4 hits against the class's <5 % promotion bar; `tests/test_final_gate_advisory_display.py`'s skip-shape ratchet omits the two directly-appended `(check not present, skipping)` rows (Kilo, Fabrik Convention Validator), which reach neither `skipped_checks` nor `--json` warnings. The `check_env_example.py` section's own arithmetic (2,223 undeclared vars vs its 1,720 + 535 + 88 + 1 = 2,344 decomposition, three sites) is off by 121 — pre-existing, re-measure and restate. Also the process lesson: a docs review whose delta hop is not bounded re-derives one neighbouring section per pass — the BAR (a discrepancy is a wrong or stale claim inside the previous pass's hunks) belongs in `commands/_sources/fabrik-docs-review.md`.
- [ ] **[infra]** **`scripts/enforcement/check_deps_sync.py` (fleet-synced) — live defects the Finish docs review of the adoption plan measured (2026-09-11, owner: infra)** — (a) `--hash=sha256:…` continuation lines are parsed as package names: on the REAL `/opt/job-agent/requirements.txt` 518 of 550 parsed names are non-package-shaped and `check_file` returns 538 WARN results; `deps_sync` is not in `validate_conventions.py`'s `_strict_exempt`, so `final_gate.py`'s Tier-3 `--strict --git-diff` row REDS that repo on any `requirements.txt` edit (exposure 1 of 17 `/opt` pairs); (b) a PEP-508 marker with no version specifier mangles the name (`flask; python_version >= "3.9"` → `flask; python-version`), one false positive each way; (c) a URL/`@` entry is dropped, so a package named in `requirements.txt` is reported as absent from it; (d) only `[project] dependencies` is read — `[project.optional-dependencies]`, PEP-735 `[dependency-groups]`, `[tool.poetry.dependencies]` and setuptools `dynamic` are invisible (11 of 17 pairs declare one, the hub among them), so a dev dependency listed in both files is reported missing; (e) the module docstring claims a version-conflict check the code never implements. Fix the parser with a fixture per shape and a red-first test, then re-transcribe the doc's `#### check_deps_sync.py` section (its `# AFTER-EDIT:` names `FINAL_GATE_WORKFLOW.md`).
- [ ] **[infra]** **`check_review_coverage.py:19-20` docstring documents the retired command-name sniff (2026-09-10, owner: infra)** — it says a changed reviews/*.md naming `/fabrik-review` with NO Coverage Checklist fails; the sniff was retired at round 27 (`:487-494`) and `check_file()` returns `[]` for such a file (executed by the Phase A round-10 Opus seat). Fleet-synced; one docstring edit.
- [ ] **[infra]** **`commands/assemble_commands.py` — the gates that never see it, and the read-only gate's completeness (2026-09-10, owner: infra)** — (a) `scripts/final_gate.py:700-717` `detect_src_package()` returns `src/fabrik`, so the Tier-2 mypy leg never type-checks `commands/` (a real arg-type error reached 98a13b24 under a green gate; the importlib preambles of `tests/test_assemble_dispatch_step.py` and `tests/test_check_convergence.py` carry 3 mypy errors each that nothing grades), and `_RUFF_ROOTS = ("scripts/", "src/")` at `:2299` excludes it from every ruff leg — extend both or add a pre-commit hook; (b) `# noqa-file: template-generator` on `:2` makes ruff warn "Invalid # noqa directive" on every lint — rename the marker; (c) three commands sit within 12 chars of the 1024-char composed skill-description cap (`fabrik-flows-review` 5, `fabrik-decommission` 8, `fabrik-rivals` 12; 36 of 36 sources measured through `_compose_skill`) — the next trigger phrase trips a now fail-closed render; (d) `# AFTER-EDIT:` headers on `tests/**` files are graded by neither `check_script_headers.py` (`:224` skips `test_*`, `:275` `scripts/` only) nor `render_doc_script_links.py` (`:136`); (e) `check()` has no ORPHAN rule for the agents tree (a retired agent source leaves a dispatchable stale definition and the gate prints check OK — `render()`'s prune removes it, the commands/skills orphan loops exit 1), its three `MISSING` branches and the `dispatch_step_gaps` wiring are graded by nothing (mutants M6/M7/M8/M30/M25 survive 39 tests) — extend the `_installed` grader table; (f) `agent_drift()` (typed `-> list[str]`) raises SystemExit on a defective agent SOURCE instead of reporting (one test caller). Found by the Phase A heavy rounds 11–15. (g) the two orphan-prune loops raise on a DIRECTORY named `*.md` after a complete write; (h) leaf writes follow a symlink where a FILE belongs (a dangling link writes outside the tree — hygiene under the single-operator threat model); (i) `--extract` rewrites 16 of 36 sources from the July backup — guard or retire the flag; (j) no grader on any `AXES` PARAMS cell. Found by the Finish review of the adoption plan (2026-09-10). (k) `check()` has no ORPHAN rule for the agents tree (a retired agent source leaves a dispatchable stale definition under `check OK`; the commands/skills loops exit 1), a broken orphan link in the agents or skills tree is reported by no gate loop, and the three MISSING branches of `check()`/`agent_drift` plus the `dispatch_step_gaps` wiring are graded by nothing (mutants M6/M7/M8/M25/M30 survived); `agent_drift()` raises SystemExit on a defective agent SOURCE instead of reporting; (l) after the Finish's ONE symlink policy (c75ead3b): a TREE that is a broken symlink has no abort case (`_tree`'s dangling arm predates the delta), and a HARD link at a current generated path is written through (`st_nlink == 2`) while the docstring's "never writes through a link" means a symbolic link — H17's class (Finish rounds 6–7, Opus seats); (n) `_HTML_COMMENT_RE`'s non-greedy strip vs a Mermaid `-->` arrow inside a comment (latent: 0 comments terminated early over 36 of 36 rendered commands, Finish round 4); (m) an unreadable (mode 000) bannered orphan or a read-only tree crashes the prune with `PermissionError` over a half-written tree, and two interlinked orphan skill dirs leave a DANGLING link no later render or gate sees through a dangling dir link (Finish round 8, Opus-2; the walks are sorted since 06f50d37 and graded under a forced glob order since e91ea6f5, so a link that sorts before its target goes first and nothing dangles for that shape; the reverse-sorting pair still leaves the link). TESTS HYGIENE (Finish round 9, Opus-1): FIFO-planting tests across several suites leave named pipes under `/tmp/pytest-of-<user>` (36 across 27 retained dirs on 2026-09-11; the assembler's own test now unlinks its two) — no sweeper covers that directory; either every FIFO test cleans up or `scratch_sweep.py` learns the path. DOC-SCRIPT COUPLING (Finish round 9, Opus-2): `check_script_headers.py` WARNs on a comment-only edit to a headered script whose coupled files are unstaged — no 'no executable line changed' escape; measure how often a comment-only commit trips it before adding one.
- [ ] **[infra]** **`check_review_hygiene.py` follow-ons from the adoption plan's Phase B review (2026-09-10, owner: infra)** — pre-existing, one hop from the Phase B diff: (a) the cursor walk in `_table_parity_hits` recovers a row's line by TEXT EQUALITY — a data row whose text equals an earlier skipped line is never reached (fixture-proven; 0 of 30,111 live rows mis-attributed); (b) `_blank_quoted` blanking a fence INSIDE a table orphans every later row from its header (now COUNTED as ungraded, never graded) and leaves a same-line `<!-- … -->` comment raw; (c) `TEMPLATE_RESIDUE` vs the assembler's own leftover grammar (`{{run-record}}`, `{{artifact}}`, `{{Extra}}`, `{{include:}}` invisible to the check; 0 of 43 live tokens in the gap); (d) `test_the_gate_registers_it_warn_only` raises FileNotFoundError outside a repo instead of skipping; (e) the one-cell caption idiom (`| **Heading** |` inside a 3-column table) is 34 of 77 `table-parity` fires over the hub's 1,186 docs — the first exemption candidate if the class ever graduates; (f) `Sweep.ungraded` sums two populations on a mixed `--surface … --receipt …` run — one summary number, unattributable; (g) `_expand`'s resolve-dedupe is a second silent vanish route — emit `N named paths resolved to M files` when M < N; (h) the two per-file sorts are deliberate (a global sort would break the file grouping) — one docstring sentence; (i) `_resolved`'s guard drops ValueError (embedded NUL) while `_display` catches it — unreachable through `scan()`, align the sets; (j) which spelling the dedupe keeps is unpinned (first-seen). Finish-review additions (rounds 2–6): (h) `Sweep.ungraded` sums two populations on a mixed `--surface … --receipt …` run — one unattributable number; (i) `_expand`'s resolve-dedupe is a silent vanish route — emit `N named paths resolved to M files` when M < N, and pin which spelling survives (first-seen, invisible under cwd via `_display`); (j) the two per-file sorts are deliberate — one docstring sentence in `_surface_hits`; (k) `_resolved` drops ValueError (embedded NUL) while `_display` catches it — align the guard sets; (l) `_fence_hits` reads raw lines and is comment-blind — a fence opener parked in an HTML comment earns a false fence-parity hit (0 of 3,611 live files), and `_fence_step`'s CommonMark 4.5 backtick-in-info-string guard is ungraded; (n) the summary arithmetic does not close — `5992 table data rows · 1663 disposition-bearing · 4296 ungraded` leaves 33 rows in neither bucket (the `raw-pipe`-hit rows `_table_parity_hits` reports and then `continue`s past without counting), so a reader summing the two published numbers gets a denominator 33 short (docs review of the adoption plan, 2026-09-11); (m) `check_convergence._mask_spans` and `check_review_hygiene._mask_code_spans` implement one rule with different line policies — inert today, a docstring note; a `\r`-only document is graded by neither `_PASS_ROW` nor the receipt classes (no action).
- [ ] **[infra]** **Spec-ledger grader — after 20 spec reviews close under the adopted text (2026-09-11, owner: infra)** — the adoption plan's § Out of Scope names it: a `check_spec_convergence.py` rule that a CONVERGED spec's last Pass row reads `confirmed: 0` (the plan-set twin landed in `check_convergence.py::_check_spine_set`, Phase C). Measured 2026-09-10: 0 of 214 specs persist a `confirmed:` row, so the rule has no population to grade yet — arm it once 20 specs carry a ledger under `/fabrik-spec-review`'s D-203 text; measure its fire rate over those 20 first.
- [ ] **[infra]** **`check_plan_tickets.py`: a WARN when a ticket's `Scope` re-narrates a spec section instead of citing it (2026-09-11, owner: infra)** — the adoption plan's § Out of Scope (D8, the `/fabrik-plan-after-chat` emit rule: tickets CITE spec sections, never re-narrate). No fire rate yet: measure over the next 5 spec-fed plans before arming; the rule is a WARN by construction (a cite-only Scope with the spec section's own words is legitimate).
- [ ] **[infra]** **`check_citations_resolve.py`: a `--pin <dir>` root and bare-basename resolution** (2026-09-10, owner: infra). Found by the review-family adoption spec's own review: the corpus cites bare basenames (`fabrik-spec-review.md:214`, 38 of 79 anchors in that spec) which the checker cannot land, and a review pins its artifact to a scratch dir the checker cannot be pointed at. Extend it (resolve a bare basename against `git ls-files`; ambiguous ⇒ a note, never a hit; `--pin` for the pinned copy), never a second grader (spec § Rejected alternatives 12). Also a fail-open with a success tick: `--root <scratch>` where the cited repo paths do not exist prints `✓ citations resolve — 0 path:line citation(s) … all land` — a run that examined 0 anchors must say so, never tick green (executed 2026-09-10 by the spec review's Opus seat).
- [ ] **[infra]** **`scripts/decisions.py --check`: a `supersedes D-NNN` that names ANOTHER repo's row reads as DANGLING** (2026-09-10, owner: infra). Measured while minting D-212: trade-intelligence's D-007 (2026-09-08) supersedes the hub's D-048 from their ledger — a legitimate cross-repo pointer the checker reports as `DANGLING: trade-intelligence D-007 supersedes D-048 which has no row in /opt/trade-intelligence/docs/DECISIONS.md`. Fix: resolve a pointer against the hub ledger when the row's text names the hub (or accept a `fabrik D-NNN` form); measure the fire rate over every /opt ledger first.
- [ ] **[infra]** **`command_run.py` TERMINAL banner says "swept every known class (a, b) clean" when the closing round swept only one and the rest stood clean from an earlier round** (2026-09-10, owner: infra). Found by the review-family adoption spec's pass-4 seat by probe (`:407-409`): under D-207's one-seat delta close the banner hands the closer a sentence asserting a sweep that did not happen, and a receipt that copies it carries a false coverage claim. Fix: print swept-this-round and standing-clean separately; red-first test on a two-class record.
- [ ] **[infra]** **The /fabrik-review convergence bar reopens the loop on ANY receipt row — the D-191 review ran 12 rounds over 5.4 h of run-record wall-clock (10:38 → 16:00, still open at that reading) on a 91-file surface because RECORDED and REFUTED rows count as findings** (operator ask 2026-09-08: "all my day is passing while waiting reviews"). Proposed ruling for the operator: the closing round is one with zero CONFIRMED code/doc defects (RECORDED/REFUTED rows do not reopen it); every finder seat carries a hard time box (15 min — the Opus seat overran twice by 20–30 min); a review surface is capped near 25 files (a change that grows across nine fix commits is re-cut per range). Seat COUNT is not the lever — a round's wall-clock is the slowest seat + the adjudicate/fix/commit cycle, ~40 min whatever the count (D-194). Owner: infra; needs a D-row.
- [ ] **[infra]** **Hub diff-scoped pytest leg** — the hub's gate pytest leg is OFF (5,913 tests), so a commit that reds a COMMITTED test still gates green: 741eebbf swept half of fleet's D-201 change and HEAD was red at `tests/test_quota_dashboard.py:709` for ~15 minutes with `status: success` in the commit body. Run only the test files the commit touches (<10 s here); measure the fire rate on the last 50 hub commits before it blocks. Round-13 Opus MACHINERY note, 2026-09-08.
- [ ] **[infra]** **hub/template CLAUDE.md divergences outside the D-191 surface** — the doc-script-coupling bullet (hub current, template an older shorter wording) and the "The flow:" intro (template carries a rivals-resolution clause the hub lacks); found by the round-14 governance seat 2026-09-08 (F334). Decide per divergence: deliberate hub-vs-project difference (say so in the template) or drift (mirror it).
- [ ] **[infra]** **`pyproject.toml` excludes `^scripts/` from mypy, so the Tier-2 gate's mypy leg asserts nothing about any `scripts/` file** — four real errors in `command_run.py` shipped green until a review seat ran mypy by hand (D-191 review F178/F202, 2026-09-08); `quota_dashboard.py` carries 9 and `command_feedback_report.py` 2 pre-existing errors at HEAD (F192). Measure the fire rate of lifting the exclusion before deciding. Owner: infra.
- [ ] **[infra]** **A DECISIONS row minted with a DRAFT plan cites artifacts that do not exist yet, and `check_doc_links.py` reds every session's gate on it** (third distinct ledger-reds-the-gate shape in ~24 h — D-099's bare pipe, the D-180/D-181 pathspec absorptions, D-184 → the scratch-sweep script's planned path at a01de4a6; named by intel 2026-09-08 — and a FOURTH: this very row, as first written at bd301620, named that planned path in link position and reddened every session's gate for the hour it stood). Evidence that the convention, not the authors, is the defect: two careful sessions hit it within an hour, one while writing the fix — so prefer the check-side option (skip a path a same-commit DRAFT plan declares) over a convention. Close the class, not the instance: let the link check skip a path a same-commit DRAFT plan declares it will create, or put planned paths out of link position by convention (a fenced `planned:` form) — and say which in the decision-ledger contract.
- [ ] **[infra]** **`tests/test_select_rules.py::test_desktop_active_on_electron_dir_not_generic_main` is RED on master** (found 2026-09-07 while running the enforcement slice for the D-181 corpus flip; reproduced on a clean HEAD worktree, so it predates that change): `sr.collect(tmp)["active"]` returns no `desktop-app/72.md` for a fixture with `electron/main.js` although the pack's glob is `**/electron/**` — last touched by the inert-rule-packs plan (T04 shared path→pack matcher, `fec39417`/`b589a1b8`). Own it: fix the matcher or the test, red-first, in its own scoped run.
- [ ] **[infra]** **`check_plan_quality.py` is a vacuous check** — it reads `PLAN_DIR = Path.cwd()/docs/development/plans` (`:44`), takes no `--plan-dir`, and printed nothing on a deliberately broken fixture ticket missing `Complexity:`/`Gate:`/`Docs:` (plan 2026-09-06-plan-2 review, 2026-09-06). Measure what it actually grades, then either wire field presence into `check_plan_tickets --plan-dir` or make this one print its denominator and findings.
- [ ] **[infra]** **`final_gate.py --check --json` cannot surface a PASSING advisory row's stdout** — `run_optional_check(..., advisory=True)` preserves the text, but the JSON's `advisory` key is `WARN_ONLY_CHECKS` only and `warnings` only rows starting `⚠` (`final_gate.py:2570-2597`), and the `Documentation Drift` call sits under `if tier == 3` (`:1783`), so the T03 ownership `ADVISORY:` line is visible on a direct `docs_updater.py --check` and in tier-3 text only (plan 2026-09-06-plan-2 T03 review r1, native finder, 2026-09-06). Emit passing advisory rows into the JSON (a small `final_gate.py` change, never-route).

- **[infra] `/fabrik-rivals` hub fallback shadows a partial local vendor** (native closing reader, 2026-09-05, pre-existing): `_resolve_engine` inserts `/opt/fabrik/libs` at `sys.path[0]` when `libs/competitor_intel` is absent, so a project that vendored `libs/deep_research` but NOT `libs/competitor_intel` silently runs the HUB's deep_research. Fix shape: resolve each of the three packages independently (local-first per package) or refuse the mixed layout at preflight. Measured 2026-09-05: 2 of 48 `/opt/*/libs` dirs — iterative_image_editor (carrying the hub's FORKED `libs.` self-imports; informed) and web-ecommerce-factory (canonical form); neither has run a rivals dossier yet.

- [x] **[infra]** **Traycer-chain command evaluation — run the orchestrator commands natively, retire the Traycer layer** (DONE 2026-09-06 — plan set 2026-09-03-plan-1-multi-agent-per-repo: T06a–c/T07a/T07b the corpus commands, T09 the layer retired, T10–T12b the chains tombstoned) (operator ruling 2026-08-30, ledger D-012: "we rarely use traycer instead, i want to use their commands here"). The chain already executes in Claude Code (Traycer is a layer; the _traycer-skills are thin wrappers over docs/orchestrator/ canonical docs), so the evaluation scopes: which of the ettw/mega commands become first-class rendered /commands, what the cockpit/card layer loses, and what dies with the Traycer dependency (server-side My Workflow already retired wiring). SEQUENCED by the operator: starts only after (1) the MCP evaluation (the per-type roster split decision + implementation) and (2) the rules evaluation are finished. Blocked by: those two, in order.
- [ ] **[infra]** **The fleet sync's SAFETY FLOOR summary line names `.env` whatever pattern failed** — the per-project line was fixed under 01M1H1V2; the `SAFETY FLOOR FAILED in N project(s)` summary still hardcodes `.env` (seen live 2026-09-06 on proxy, where `.venv/` was the committed path). Fix: carry the failing pattern(s) per project into the summary + a grader. (plan 2026-09-03-plan-1-multi-agent-per-repo close, T16)
- [ ] **[infra]** **`generate_capability_index.py` classifies a script from its first 4000 chars and takes the `# AFTER-EDIT:` comment as its summary** — a script whose `if __name__` sits past the window silently becomes "manual" and drops out of docs/CAPABILITIES.md (check_traycer_chain.py crossed it at 4219 chars, T09 r1); every headered script's catalog summary is its AFTER-EDIT line (`_first_docline`, :114). Fix: classify on the whole file; skip the header comment in the summary; graders. (T16)
- [ ] **[infra]** **`final_gate.py`'s ruff roots exclude `tests/`** (`_RUFF_ROOTS = ("scripts/", "src/")`, :2202) — T13's test file went red (UP017 ×2, F841) across eight review rounds unseen. Measure the fire rate over `tests/` box-wide before widening (FIX DIRECTIVE 5). (T16)
- [ ] **[infra/T16 decision]** **Nothing runs `scripts/enforcement/check_traycer_chain.py`** — 0 of ~40 `run_optional_check` registrations in final_gate.py, not in pre-commit; fleet-synced to ~46 repos where nothing invokes it, cwd-relative and fail-open from a wrong cwd (T09 r1). Decide: register it hub-side as an optional check (a project prints `PASS - 0 files`) or record the hand-run decision as a D-row. (T16)
- [ ] **[infra/docs]** **README.md still carries 21 `traycer` + 48 `kilo` prose mentions and five fenced refs to absent Kilo scripts** (`:248,:254,:556,:583,:745`) outside T14d's `.traycer` gate — a Kilo/Windsurf-retirement sweep of README, no ticket owned it. (T14d, T16)
- [ ] **[infra]** **A linked worktree whose `.claude/hooks/*.py` are missing blocks EVERY prompt** ("UserPromptSubmit operation blocked by hook: can't open file …") — in a project the hooks are gitignored synced copies that only the `.worktreeinclude` carry puts into a worktree (proven the hard way by two invalid T16 probes: a clone without the copies, the hub main checkout without an include file). Worth a guard: a missing hook script should WARN, not block, or the carry should be verified at worktree creation. (T16)
- [ ] **[intel]** **`libs/subagents` `fanout` docstring still advertises a default price cap** the pool no longer applies — routed to intel (D-135/D-137: the module is fabrik-lib's vendored copy; the hub does not edit it). (T16, mailed)
- [ ] **[infra]** **The never-built orchestrator cockpit docs** (`docs/orchestrator/orchestrator-cockpit-{decisions,feature-set,requirements}.md`, spine I13) still describe the retired chains in live tense — excluded from the plan's sweep as a separate retirement decision; retire or rewrite. (T16)
- [x] **[fleet+infra]** **Universal governance docs publish to PUBLIC docusaurus sites — audit the class** (fleet's observation in `01M19JJNWKAKNEZBA65TVDT5A1`, 2026-08-30, raised while wiring the DECISIONS scaffold seed) — **RESOLVED at the generator 2026-08-30 (commit `62858b50`).** Measured (the "measure first" step): **0 live docusaurus projects fleet-wide** (39 `project.yaml` + `data/projects.yaml` registry), so there is no live site leaking today and no retro-fix. Fix chosen: a docusaurus content-docs `exclude` in the scaffold generator (`_DOCUSAURUS_UNPUBLISHED_DOCS` in `src/fabrik/scaffold.py`) covering the seeded governance docs (DECISIONS/LESSONS_LEARNT/STRATEGIC_BACKLOG) AND the pipeline-generated contracts a UI-bearing docusaurus project writes into the same `docs/` (flows/ui-design/design-system) — present-but-unpublished, rendered `**/<name>`. Reviewed via /fabrik-review (pool + native Opus; report `docs/development/reviews/2026-08-30-docusaurus-governance-doc-exclude-review.md`). Infra's build-time-exclude + enforcement-guard alternative is now moot for new scaffolds; the only residual is an OPTIONAL enforcement guard to catch a hand-authored docusaurus that removes the exclude — low value at 0 live sites (infra's call).

- [ ] **[infra]** **Plan-lock release check — a finished plan must not hold its lock** (specced 2026-08-25, operator-requested follow-on). **Nothing writes a plan lock but the agent.** `grep` across `scripts/` and `.claude/hooks/` returns zero writers: `check_plan_tickets.py:561`, `check_phase_tests.py:36` and `final_gate_stop.py:785` all only READ. The lock is created by prose (`/fabrik-execute-plan` Before-You-Start step 7) and released by prose (Finish step 5), so the whole protocol is honour-system — with the honour supplied by an LLM following a paragraph it read hours earlier at the far end of a long run. **Two live instances, both measured this session.** (1) `2026-08-19-plan-1-kaizen-m1-event-stream.json` sat `status:"active"` with `completed_at:"2026-08-21"` and `final_commit:null` — one field of a three-field write landed — while its plan was `Status: EXECUTED` in `plans/archived/` with 9/9 tickets `merged`. It BLOCKED the inert-rule-packs plan on three high-traffic hub paths (`final_gate.py`, `select_rules.py`, `review_rubric.py`) until the operator ruled, because D1/step-7 forbids agent auto-reclaim unconditionally and correctly. (2) `2026-07-26-plan-1-ai-model-catalog-extraction.json` is STILL `active` today holding 10 owned paths (`scripts/kilo-benchmarks/`, `tests/kilo_benchmarks/`, …) with its plan archived and `completed_at`/`final_commit` both null — it will block the next plan touching those paths. **Two mechanically-decidable facts, no judgement needed:** a lock whose plan is `Status: EXECUTED` or lives under `plans/archived/` must not be `status:"active"`; and a lock with `completed_at` set must have `final_commit` set (a half-applied Finish is the exact signature of instance 1). Advisory WARN on landing, per this repo's own doctrine that a check firing fleet-wide on day one gets ignored. **Why it matters beyond tidiness:** the paths involved are the ones every plan touches, so one unreleased lock silently blocks the next several plans, and the failure surfaces as a hard BLOCKED halt at another agent's step 7 — far from its cause, days later. | The protocol has readers and no writer, and its two failure modes are decidable from the lock file plus the plan's own status line. | A short focus window; both instances are already measured, so this is implementation, not investigation.
- [ ] **[infra]** **Plan-stage pack-routing gaps** (transdoc `01M0WN9RXJJY9SDQTF8183GTYW` items 4a–4c, filed 2026-08-25 with the inert-glob findings; the glob class itself is fixed — 15/75 by the D7 plan, 86 this sitting — these three are the COMMAND-CORPUS half): (4a) plan-time pack routing is by ticket TOPIC, not the ticket's FILES — `review_rubric.py --changed` already maps paths→packs but runs only at review time; teach `select_rules.py` a `--changed`, or have `/fabrik-plan-after-chat` route packs per ticket via `review_rubric.py --changed` on the ticket's declared files, and `/fabrik-plan-review` diff glob-matched packs against each ticket's Context Files (non-empty difference = finding). (4b) a Constraints Digest may cite a pack and drop its HARD STOPs in summarisation — transdoc's spine cited 15-api-contracts and kept only the RFC 9457 clause, dropping the codegen ban that would have prevented 19 phantom frontend calls; require a cited pack's Banned Patterns verbatim in the Digest. (4c) `/fabrik-execute-plan` D7 is satisfiable by green suites alone — no step requires one live request against a running service; transdoc's whole finding list came from a one-minute read of `app.openapi()["paths"]` that no gate ever forced. Blocked by: next command-corpus focus window.
- [ ] **[fleet]** **Fleet container-name/alias reconciliation check** (deploy-triad root-cause #1, 2026-08-11): nothing mechanically reconciles a project compose's `container_name`/service keys against LIVE fleet container names + fabrik-net aliases — the tryton-crm `gotenberg` collision (a standalone container squatting the name for 4 weeks, the compose's own "no such service exists anywhere on the fleet" comment false when written) reached a deploy plan before anything caught it. Candidate shapes: a `/fabrik-deploy-plan` Phase-2 mandatory probe (it now does this for tryton-crm ad hoc), a `fabrik validate` extension, or an enforcement check. Blocked by: next deploy plan for a multi-service stack, or a spare S-window.
- [ ] **[fleet]** **Scaffold/validate warning for dependency-asserting compose healthchecks** (deploy-triad root-cause #1): a compose healthcheck pointing at a READINESS route (one that 503s on an unreachable dependency — tryton-crm's `/health` pings trytond as a login that doesn't exist pre-init) deadlocks `docker compose up --wait` on first deploy AND invites healer restart-storms on dependency blips. Docker healthchecks should be liveness. Candidate: a compose-lint in `fabrik validate`/`deployer_ssh._validate_compose` flagging healthcheck URLs that match the app's readiness route when a `/healthz` liveness route exists. Blocked by: a focus window; the class is now documented in the tryton plan + Lesson 110's neighborhood.
- [ ] **[fleet]** **Scaffold a captured-event GlitchTip secret-leak test (+ vacuity guard)** (tryton-crm `01M145D3N`, passed back 2026-08-28 after fixing the emitter leak `f273064c`). The emitter now sets `include_local_variables=False` + `max_request_body_size="never"` (Python) / `includeLocalVariables:false` (Node), and the hub test asserts the emitted INIT carries them — but no scaffolded project verifies its own RUNTIME behavior on the captured event. tryton-crm built exactly this (`tests/test_glitchtip_no_secret_leak.py`, verified d2ca9d9) and flagged two things the scaffold should emit for every DB/auth project: **(1) a kept VACUITY GUARD** — a second test that re-runs the same capture with `include_local_variables=True` and asserts the secret DOES appear, so a green leak-test can't certify nothing when the SDK's capture path changes (~10 lines); **(2) a Transport SUBCLASS, not a callable** — sentry-sdk 2.64 deprecated function transports, and a security test that silently stops capturing on an SDK bump is the worst failure mode. Candidate: emit `tests/test_glitchtip_no_secret_leak.py` from the fastapi-backend scaffolder (mirror the `_TEST_DB_GUARD_CONFTEST` emission pattern) + a hub test asserting the emission. Blocked by: a focus window; the emitter leak itself is already fixed fleet-forward, this is per-project self-verification.
- [ ] **[fleet]** **Deploy ordering breaks init-at-boot images (registrar injects `DATABASE_URL` AFTER first `up`)** (found live in the Zitadel deploy-plan review, 2026-08-28, plan finding D1). `deploy()` runs `deployer.deploy` (`docker compose up -d --wait`) at `orchestrator/__init__.py:163`, then the postgres registrar injects `DATABASE_URL` at `:173` — so the container's FIRST boot has no DSN. Services whose entrypoint connects lazily (evolution-api etc.) tolerate this; an image that runs migrations synchronously at boot and **exits with no retry** (Zitadel `start-from-init` — grounded via zitadel issues #5810/#11942 + troubleshooting docs) crashes, `up --wait` raises, and the deploy rolls back at `:207` **before** the registrar ever runs → the DB is never created → a repeated `fabrik apply` re-crashes identically. Such a service **cannot be stood up by a plain `fabrik apply`**. Candidate fixes: (a) a `shape`/spec flag that provisions the DB + injects `DATABASE_URL` BEFORE the app's first `up` for init-at-boot images; (b) a DB-reachability wait-wrapper the emitter injects; (c) a documented bootstrap runbook (pre-create DB+role, pre-seed the DSN into the remote `.env`, then `up`). Blocked by: a focus window; the class is measured + documented in the Zitadel plan's D1, and it currently blocks that deploy at Gate 2.
- [ ] **[fleet]** **`generate` secrets lack a remote-`.env` preservation read — re-apply re-mints a stable-forever key** (found live authoring the Zitadel deploy plan, 2026-08-28, `docs/development/plans/archived/2026-08-28-plan-deploy-zitadel.md` finding F1). `orchestrator/__init__.py:301-303` resolves `secrets.generate` via `secrets_manager.load_all(generate)` — process-env + a **hub-local** dotenv only (`secrets.py:60,77-101`). Only `from_env` gets the remote-`.env` preservation read (`__init__.py:306-320`), and even that targets a hub-local `/opt/<id>/.env` that never exists for a remote-only third-party service. Consequence: a secret minted on FIRST `fabrik apply` into the **remote** `/opt/<id>/.env` is **re-minted** on any SECOND apply (the hub resolver never sees the remote value) and `inject_env`'s `merged.update()` (`deployer_ssh.py:235`) overlays the new value. For an ordinary generated password this is a silent auth break; for a **stable-forever encryption key** (Zitadel's `ZITADEL_MASTERKEY`, which decrypts stored data) it is **catastrophic data loss**. Candidate fix: give `generate` the same remote-`.env` preservation read `from_env` has — read the target VPS's `/opt/<id>/.env` over SSH before resolving, and never regenerate a key already present there (mint-once). The Zitadel deploy works around it with an apply-once + updates-via-`redeploy` runbook invariant, but every future generate-secret service inherits the trap. Blocked by: a focus window; the class is now measured + documented in the Zitadel plan's F1.
- [ ] **[infra]** **Spec-comment truth discipline** (deploy-triad root-cause #4, Lesson-105 class): three tryton spec comments were code-false (shared-token "accepts TI's token too" — dev-only in production; `expose.internal_only` — a DEAD field no orchestrator code reads; RPC_PASSWORD "creates the login WITH it" — the script generates its own). Candidate: extend the review commands' checklists (done for deploy plans — class 8 doc-truth) and/or a periodic spec-comment audit against the code. Blocked by: recurrence. **RECURRENCE CHECKED 2026-08-25 — it has NOT recurred, so this stays deferred on evidence rather than assumption.** The three original tryton comments were corrected in place with the finding recorded beside them (`tryton-crm.yaml:96` now reads "create_rpc_service_user.py IGNORES it and GENERATES its own"; `:85` records the A4 removal). Across the 75 specs on disk, 38 comment lines are assertion-shaped; three live ones were verified against code and all three are TRUE: `seo.yaml:55` (auto-generate) vs `orchestrator/secrets.py:77,100 generate_if_missing`; `spoke-canary.yaml:3` (docker source) vs `deployer_ssh.py:150 SourceType.DOCKER`; `site-provisioner.yaml:44` (registrar overwrite + restart) vs `inject_env`'s contract. **Do not build the periodic auditor until a real second instance appears** — enforcement for a non-recurring class is the churn this backlog exists to avoid. The deploy-plan review's class-8 doc-truth check already covers the path where it bit.
- [x] **[infra]** **`/fabrik-deploy-plan` Output contract omits the gate-required `## Behavior Contract` section** (found live on the first run — the plans gate demands it on every new plan; the command's four gate-required sections don't name it, the executing agent discovers it at gate time). One-line corpus fix in `commands/_sources/fabrik-deploy-plan.md` + render. Blocked by: nothing; fold into the next corpus touch. ✅ **CLOSED 2026-08-25** — the Output contract now names FIVE gate-required sections incl. `## Behavior Contract`, with the shape to author and the reason it is easy to miss (the demanding gate is `check_test_proposal`, NOT `check_plan_quality`, whose Behavior-Contract pillar is spine-only). Proven: a deploy-shaped monolith went False→True against `evaluate_plan`.
- [ ] **[infra]** **Store-terminal adjudication** (deploy-triad recorded residual): the plan-frozen release NEXT routes STORE surfaces post-submit to `/fabrik-deploy-verify`, whose contract is spec-driven VPS-only — a store agent dead-ends cleanly at target resolution. Options: a store analogue inside deploy-verify, or reword the store terminal across all FOUR encoding surfaces (NEXT dict + release body line + § Pipeline parenthetical + 6-release stage row, the latter two in BOTH CLAUDE.md copies). Blocked by: first real store-surface release (mobile-app etc.). **PARTIALLY CLOSED 2026-08-25 — the live dead-end is fixed; the analogue stays blocked.** `/fabrik-deploy-verify` Phase 0 now opens with a SURFACE GUARD: a store-surface target stops with a clean hand-back naming what a store release actually needs verified (build provenance from a pushed SHA, vendor-console review/rollout state, first-ring crash/ANR) instead of failing at step 1 on a `specs/services/<id>.yaml` that store types never have — which read as a missing file rather than an inapplicable command. Same rule as the enforcement-battery audit: a command that cannot ask its question must SAY so. **Still open and still correctly blocked:** the store ANALOGUE itself, plus the four-surface reword — grounding what it should probe needs the first real store release, and the guard now makes the aspirational routing honest at the point of use meanwhile.
- [x] **[infra]** **North-star "deploy = manual `fabrik apply`" lines** (`docs/orchestrator/00-autonomous-factory-north-star.md:143`, also :44/:200): predate the deploy triad; `/fabrik-deploy`'s Gate-2 tiebreak absorbs them (the operator's dispatch IS that manual act for plan-governed deploys). Cosmetic doc alignment when the north-star is next edited. ✅ **CLOSED 2026-08-25** — all three lines aligned to the deploy triad: Gate 2 is the operator's explicit go, after which `/fabrik-deploy-plan` → `/fabrik-deploy-plan-review` → `/fabrik-deploy` executes and calls `fabrik apply` underneath. Nobody types it by hand, so the old phrasing described a workflow that no longer exists. Verified: zero remaining "manual `fabrik apply`" occurrences in the file.
- [x] **[infra]** **Three pre-existing adjacents from the triad's gate B** (recorded, non-behavioral): `skill_router.py:128` comment still says wordpress "deploy-only" (the retired phrasing); `scaffold.py:5768-5772` wordpress `NotImplementedError` still points at the archived `wpf` CLI; `templates/governance/CLAUDE.md:24`'s "All projects … deploy via `fabrik apply`" overstates for store surfaces. Fold into the next touch of each file. ✅ **CLOSED 2026-08-25** — all three corrected: `skill_router.py` no longer calls wordpress "deploy-only" (it is out of fabrik; `/opt/wpf` archived 2026-08-07), `scaffold.py`'s NotImplementedError no longer points callers at the deleted `wpf` CLI, and the governance line no longer claims ALL projects deploy via `fabrik apply` (store surfaces do not).
- [x] **[infra]** **Whole-tree docs_updater debt** (pre-existing, reported 2026-08-11 during the triad's docs sweep — NOT the triad's): docs/CAPABILITIES.md link rot (auto-generated — fix the generator's link targets), stale docs/QUICKSTART.md (111d) + docs/CONFIGURATION.md (107d), broken links in old plans/specs. Blocked by: a docs focus window or the next `/fabrik-docs-review` full run. **UPDATED 2026-08-25:** the CAPABILITIES.md half is CLOSED — its generator wrote repo-root doc_links (`AGENTS.md`) into a file that lives in `docs/`, so every one resolved to a non-existent copy one directory too deep. **273 of the repo's 386 broken links were that single bug (71%)**; fixed at the generator + regression-tested, total now **113**. What REMAINS is not the same class: 111 of the 113 are citations inside `docs/development/plans/**` and `docs/superpowers/specs/**` — historical artifacts that `check_doc_links` deliberately EXEMPTS as sources (plans cite files as they were; specs forward-reference). `docs_updater` scans them anyway, so the two link checkers disagree by design — reconcile the scopes before treating those 111 as debt. Genuinely open: stale `docs/QUICKSTART.md` (125d) + `docs/CONFIGURATION.md` (121d), which need a content pass, not a link fix. ✅ **CLOSED 2026-08-25 (second half).** Both stale docs verified against code, corrected, and their currency headers refreshed — stale count 2 → 0. QUICKSTART's executable surface was already accurate: all 10 documented `fabrik` subcommands exist and every documented flag (`--from-preplan`, `--github-create`, `--dry-run`, `--filter`, `--yes`, `--spec`, `-n`) resolves. CONFIGURATION carried the REAL rot — two live pointers to `/opt/wpf` ("the real driver is /opt/wpf/src/wpf/drivers/wordpress.py", and the WP credentials line), a path ARCHIVED on 2026-08-07 and gone from disk. Both rewritten as tombstones so nobody re-adds the variables thinking they were an oversight. Newest env vars (FABRIK_MAIL_*, FABRIK_OPT_ROOT) confirmed present in BOTH `.env.example` and this doc, per the Doc Sync Matrix. **Note on the metric:** staleness is measured from the `**Last Updated:**` header, not git mtime — CONFIGURATION had been edited 2 days before it was flagged. Bumping the header alone would have been a lie; content first, then the date.
- [x] **[infra]** **`fabrik-deploy-verify.md` cite range off-by-one-sentence** (Phase-D whole-pack review nit, pre-existing): its `:16,148` cite of `fabrik-catchup.md:68-75` anchors the right item but the bridge-namespace sentence itself sits at catchup `:76-78`. Fold into the next corpus touch of that file. ✅ **ALREADY CLOSED** (0883b987, 2026-08-16) — both cites were de-numbered to a section anchor (`§ the local-`fabrik`-bridge probe`), which cannot drift; the anchor resolves at `fabrik-catchup.md:77`. No action was needed; this row was stale.
- [x] **[intel]** **Flywheel `refuses-ungrounded` axis** — BUILT 2026-08-29 (plan `2026-08-28-plan-1-canary-grounding`, Phases A+B; the `select.py` multiplier rides the fabrik-lib filing). Original row (job-agent `01M13TM8FN`, 2026-08-28): "does this model fabricate when its grounding input is absent" is invisible in normal scoring — on a well-formed prompt both models look fine. Measured differential on an identical missing-input grounder: `gemini-3-flash-preview` refused to invent in its first sentence; `deepseek-v3.2-exp` produced a line-numbered analysis of a file it never saw, wrong in the direction that plans the wrong fix. Candidate shape: a per-model boolean/score column fed by deliberate missing-input probes (a tiny periodic canary batch), consumed by `pick_models` as a penalty for grounding-class task types. Needs a small spec (ledger schema + probe design + ranking integration) — deferred per the no-spec boundary of the sitting that filed this row. The 62-pack warning (same commit) covers the caller-side trap meanwhile.
- [ ] **[intel]** **Reconcile the 2026-08-28 transdoc score contamination in `subagent_runs`** (transdoc 01M154PZQ, self-reported): ~226 historical review runs (2026-08-21→28, other sessions' agent_ids) received `status='scored'` deltas at 2026-08-28T21:3x from project=transdoc with per-model constants (v3.2-exp 4.0, qwen3-max 4.0, gemini-3-flash 3.0, v4-flash 3.0) — under latest-wins those now shadow real adjudications. MEASURE FIRST (the fix directive): count affected agent_ids whose prior latest score differed, split had-prior-score (re-assert prior latest via fresh deltas — INSERT-only-compatible) vs never-scored (needs an aggregation-side exclusion or acceptance — decide on measured counts). Module-side guards (refuse re-score without override + ownership warning) filed to fabrik-lib the same day.
- [ ] **[intel]** **Wire `MISTRAL_MONTHLY_CAP_USD` to a real enforcer** (2026-08-29, found by the key-wiring self-review): the $10/month hard cap across ALL Mistral keys is provisioned in `.env` + documented in CONFIGURATION.md, but NO consumer reads it — an advisory cap on a paid API is the stored-and-never-read class. Mitigated today: all four Mistral keys 401 (monthly free credit EXHAUSTED — operator-confirmed; usable again at the credit reset, which makes the enforcer MORE urgent, not less: an unbudgeted consumer burns the whole month's credit in a day). Resolution: when the Mistral account activates and a first consumer appears (crowdlex haiku-replacement is the candidate), route its spend through the cost-budget seam reading this var — monthly + total across keys, never per-call (sysadmin-loop rule).
- [ ] **[intel]** **Kilo golden-parity standing red — routes/IMAGE_GEN/ai-pack marker drift** (2026-08-29, surfaced during the canary Phase B review): 10 `test_golden_parity` failures list ONLY foreign artifacts — `scripts/kilo_openrouter_routes_final.json` structure change + OPENROUTER_ROUTES marker rows collapsed to 0 across the ai/ packs + `IMAGE_GEN_SELECTION.md` 3→1 rows — the routes half of the daily pipeline has gone husk; `capture_golden --verify` (a `severity='critical'` daily gate) is red on it. Deliberately NOT frozen over during the canary work (freezing empties makes them "never red again"). Fix the routes pipeline, then re-snapshot.
- [ ] **[intel]** **Flywheel back-scoring debt — ~1093 unrecorded pool runs** (box-wide advisory printed on every `fanout`; predates this session): `audit_unrecorded('/opt/fabrik/.tmp/subagents/ledger.jsonl')` lists them; `pick_models` cannot learn from unrecorded runs. Blocked by: a focus window; decide score-vs-write-off per batch (Lesson-97 discipline: errored runs are non-results, never 0-scored).
- [ ] **[fleet]** **CI-parity Phase 2 — spec-driven `shape.db_extensions: [pgvector]`**: deferred from [`archived/2026-07-01-plan-fabrik-ci-parity.md`](development/plans/archived/2026-07-01-plan-fabrik-ci-parity.md). The one-source CI generator (`src/fabrik/ci_scaffold.py`) already accepts `db_extensions=("pgvector",)` → `pgvector/pgvector:pg16`, but scaffolding runs *before* a spec exists, so there's no spec→CI regen path to drive it — new scaffolds default to plain `postgres:16` (correct for most). Blocked by: a project that actually needs pgvector in CI AND a decision on the regen trigger (a `fabrik ci-refresh <spec>` step vs an apply-time registrar). Not urgent — the default is right for the common case.
- [x] ~~**[infra]** **CI-parity Phase 4 — backfill existing projects with `ci_local.sh`**~~ ✅ **MOOT 2026-08-29** — the operator retired CI checks in every existing and future repo, so there is no workflow left to mirror. Every repo's check workflows are `disabled_manually` (verified fleet-wide: zero active), the scaffold no longer emits `ci.yml`, and enforcement moved to `final_gate` plus the hub's pre-push gate. I flagged this as likely-moot in the 2026-08-25 thread; it is now decided. Original text follows for the record. ~~: deferred from the same plan. New python scaffolds now auto-emit `ci.yml` + `ci_local.sh`. **Scope re-measured 2026-08-25 — the earlier "~39 projects" estimate was wrong by an order of magnitude, and counting only `ci.yml` undercounts it (repos also carry `test.yml`, `type-check.yml`).** Counting ANY `.github/workflows/*.yml`: **15 repos have workflows, 7 lack a local replica** — `fabrik` (the hub itself, 2 workflows), `proxy`, `trade-intelligence`, `youtube`, plus `rnfinal` / `rn-kit-sandbox` / `supplement-tracker-advisor` (13 workflows each — RN-template output, likely out of scope; confirm before touching). The remaining ~33 repos have no workflow at all, so there is nothing to mirror. Deliberately NOT a blind overwrite: a project's hand-rolled workflow must not be clobbered, and a faithful `ci_local.sh` must mirror *that* project's actual workflow (the generator renders from `CiConfig`, not by parsing an existing one). Blocked by: a small "generate `ci_local.sh` from an existing workflow" tool, or a per-project decision to adopt the generated `ci.yml`. Real remaining scope is **4 repos**, not 39 — small enough to do by hand if the tool is not worth building.
- [ ] **[fleet]** **PostgreSQL 16 → 18 upgrade** (WSL dev + VPS hub): plan at [`archived/2026-05-25-postgresql-18-upgrade.md`](development/plans/archived/2026-05-25-postgresql-18-upgrade.md). Created 2026-05-25, never started. 14 dbs on `postgres-main` would need pg_dumpall → PG18 cluster bootstrap → restore + verify, plus matching upgrade on the WSL dev DB to keep "same code in 3 envs" valid. PG16 reaches EOL November 2028 so there's no urgency; the existing setup is healthy. Blocked by: (a) a focus window of 2–3 hours, OR (b) a real PG18-only feature need (none today). When ready, unarchive the plan and run.
- [ ] **[fleet]** **propose/ack peer-protocol verbs** (trio plan Phase 5, deferred): Today the cross-host destructive bridge is operator Telegram `reply "go"`. Build the `propose`/`ack` HTTP verbs in aro-wake only when a real incident proves the bridge is insufficient — don't speculate. The "real cross-host destructive action" use case hasn't shown up yet. Blocked by: first real incident where consult-only + operator-bridge is provably too slow.
- [ ] **[fleet]** **Apprise pre-route through aro-wake** (trio plan Phase 5, deferred): Gatus / GlitchTip / Backrest webhooks currently go straight to Telegram. AI never sees them. Wire Apprise to aro-wake first with `continue: true` semantics like Alertmanager Phase 4. Blocked by: first real incident proving Alertmanager-only triage missed something.
- [ ] **[infra]** **Telegram legacy-Markdown parity at the alerting boundary** (external-services review pass 33, CW4): `libs/alerting/telegram.py` sends `*{title}*\n{body}` with `parse_mode: Markdown` and escapes nothing, so any caller whose body carries an odd number of `_` (or a stray `*`/`` ` ``/`[`) gets HTTP 400 and — when the ssh-apprise leg, tried first and Markdown-free, has also failed — the alert is lost with only a warning logged — measured on the chain: 1 of 346 triage names (`bridge_internal`) can reach the classify INFO alert's provider list; the chain's step alert is parity-safe by construction on the production log path (graded); on the `/tmp/fabrik_daily_refresh_YYYYMMDD.log` FALLBACK path (3 `_`) every chain alert MESSAGE (`*title*\n{body}` — the title carries `$label` too, so 5/5/7/5/5 and 3) goes odd (pass 36, DC5 — 0 of 1, the cache log is writable). The class fix is escaping at the boundary (all 7 direct `send_alert` call sites plus `mail_escalate.py`'s indirect one are exposed — and that digest is the likeliest odd-`_` body); mirror: a caller passing intentional Markdown loses its formatting. Blocked by: measuring which callers pass Markdown on purpose.
- [ ] **[infra]** **A confidence gate between one model answer and the curated catalog** (external-services review pass 39, DI3): the classifier writes a paid pool model's single answer straight into `scripts/service_catalog.json` as `status: active` — the first production run filed `argusmedia` (a commodities price-reporting agency) under `media-stock` on the word "media", and `--only` cannot re-dispatch a curated name, so a misfile is permanent without a hand edit (1 of 4 identifications that run; all 10 units were code-only hosts — 6 came back `unidentified` and were tombstoned once, never re-billed, 4 became permanent entries; the queue composition is by design, and until pass 40 the units ran with NO web tools — provider names where tool names go — so every answer was model recall). Options measured before building: a second-model vote on `category` only, or a `status: proposed` state the dashboard shows and a human flips. Blocked by: measuring the misfile rate over the next ~30 runs (338 queued at 10/run).
- [ ] **[infra]** **13 registered gate checks have no canary** (12 found at external-services review pass 41; `check_citations_resolve` joined 2026-09-03 with a sibling's gate row — re-measured at pass 56: `tests/test_gate_check_canaries.py::test_every_registered_gate_check_is_accounted_for` names 13; the older 2026-08-30 row below listing 10 is superseded by this one): `tests/test_gate_check_canaries.py` fails at HEAD — `test_every_registered_gate_check_is_accounted_for` lists 13 checks with neither a `CANARIES` pair nor an `UNREACHABLE` reason (`check_certification_coverage`, `check_citations_resolve`, `check_command_corpus`, `check_decisions_unique`, `check_feedback_duty`, `check_frozen_chain`, `check_pack_reachability`, `check_plan_lock_release`, `check_rivals_dossier`, `check_rule_grounding`, `check_spec_convergence`, `check_trigger_routing`, `check_vendored_drift`), and its sibling lists 10 `warn_only` rows with no recorded WHY. Pre-existing (not the chain's surface; `check_command_corpus` carries its own self-test). Blocked by: authoring the 13 pairs — one sitting, the enforcement-inert class.
- [ ] **[fleet]** **Loki ruler with starting rule set** (trio plan Phase 5, deferred): Log-pattern alerts not generated at all today. Sidecars catch their own container's logs; cross-container log signals on vps1 aren't observed. Blocked by: first incident that log-pattern-rule would have caught earlier than container-state probe.
- [ ] **[fleet]** **Grafana `aro-wake` dashboard**: 8 SLI metrics + 2 alert rules live on full fleet since 2026-06-06. PromQL + Telegram alerts cover real operator needs today. Build a dashboard only when ad-hoc PromQL queries become tedious. Blocked by: operator running the same PromQL recipe 3+ times in a week.
- [ ] **[fleet]** **"Repeated-flag-no-action" pattern detector** (complement to `detect_reversals.py`): The 2026-06-07 netdata flood was 24 benign "anomaly detected" wakes with no AI action taken — `detect_reversals.py` correctly doesn't fire (no AI action to reverse), but a different correlator could flag "AI flagged X N times in a row, operator never acted → AI is wrong OR alert is misconfigured". Same `lessons-pending.jsonl` output stream, different correlator. Blocked by: second occurrence of a similar pattern that's not the netdata case (which is now fixed).
- [ ] **[fleet]** **Bake the new operator-reversal cron line into the live cron-template DEPLOY path for existing hosts**: Today I appended to `/etc/cron.d/vps-sysadmin` on all 3 hosts manually and also updated [`sysadmin-cron.template`](../scripts/bootstrap/templates/sysadmin-cron.template) for future spokes. There's no `fabrik`-level redeploy step that re-renders the cron template on existing hosts after a template change. Blocked by: another cron template change that needs to propagate.
- [ ] **[fleet]** **Reset `/opt/fabrik/` ownership on vps2 + vps3 from `root:root` to `ozgur:ozgur`** (cosmetic): Today's bootstrap-vps.sh change covers fresh installs going forward, but the live state on vps2/vps3 still has `/opt/fabrik` as `root:root`. Nothing is breaking — the venv was already created earlier — but the asymmetry would be discovered during the first real maintenance touch. Blocked by: nothing; one-liner SSH per spoke, but not worth interrupting steady state for.
- [ ] **[operator]** **Bot token rotation** for `SysAdminVPS2` (`8838110344:...`) + `SysAdminVPS3` (`8674270904:...`): Operator declared this private chat 2026-06-07 and declined rotation. Re-evaluate if the chat scope ever changes. Blocked by: operator decision.

- [ ] **[infra]** **Un-extracted duplication across command sources** (measured 2026-08-29 while fixing the `/fabrik-review` ↔ `/fabrik-generate-tests` copy). That fix single-sourced ONE pipeline into `commands/_fragments/test-generation-loop.md`; a sweep for the same class across all 31 sources found **4 more source pairs sharing 95 six-line windows**, dominated by ~~`fabrik-service-test.md` + `fabrik-user-test.md` at 65 windows~~ ✅ **EXTRACTED 2026-08-29 (cmd 15/31 audit):** the gauntlet pair now renders four shared fragments (`cert-board-contract` · `cert-execution` · `cert-handoff-grammar` · `cert-visual-deliverable`), rendered-parity md5-proven, residual shared windows **0** — and the extraction erased two REAL drifts the cmd-14 fixes had just created (the recorder naming and the grader-honesty split existed only in user-test). Remaining pairs: `fabrik-spec.md` + `fabrik-spec-review.md` (11), `fabrik-flows-review.md` + `fabrik-ui-design-review.md` (10), and `fabrik-data-contract.md` + `fabrik-flows.md` + `fabrik-ui-design.md` (9). Each is a contract maintained in two files where an editor of one cannot see the other. ⚠️ **The measure has a known blind spot and it is the important one:** it normalises whitespace and emphasis but not WORDING, so it scored the review/generate-tests pair at **0** — the copy that motivated all of this had been lightly reworded. A duplication gate built on this measure would therefore miss the exact defect class it is named for; the honest framing is that it finds *un-factored twins*, not *drifted copies*. Fix direction: extract per pair into `_fragments/`, largest first, and re-measure. Blocked by: the audits of the remaining pairs' commands (spec/spec-review at cmd 16+; the audit is at command 15 of 31 done).

- [ ] **[infra]** **`final_gate` has NO TypeScript/JS checks — and CI was the only thing running them** (surfaced 2026-08-29 when CI checks were retired fleet-wide). `grep -n "tsc\|eslint\|vitest\|npm test\|type-check" scripts/final_gate.py` returns **nothing**. trade-intelligence's CI ran a whole job the gate cannot replace — `npm run type-check`, `npm run test:unit`, `npm run test:components` — and it was FAILING on all five of its last runs. Disabling CI moved the python half to a stricter place (the gate blocks the commit instead of emailing after the push) but moved the web half to **nowhere**: a green `final_gate` in a repo with a web surface now asserts nothing about its TypeScript. Affected: any repo with `package.json` + a web surface (trade-intelligence confirmed; the three RN repos carry `lint-ts`/`type-check`/`test` workflows but two of them have no git remote so those never ran anyway). Fix direction: a diff-scoped web tier in `final_gate` — run `type-check`/`lint`/`unit` **only when the diff touches web paths and the scripts exist in `package.json`**, `warn_only` on landing per this repo's own doctrine that a check firing fleet-wide on day one gets ignored. ⚠️ Measure the fire rate first: an unknown number of these suites are already red, which is exactly how CI ended up ignored. Blocked by: a focus window; nothing is waiting on a decision.

- [ ] **[infra]** **/fabrik-rivals driver: `--seed-rival` flag** (fabrik-lib `01M15DM2G`, module SHIPPED bebc57b→6cf6a74, 515 tests green): `competitor_intel.run` now accepts seeds; the driver half is `scripts/rivals_run.py` — expose the flag per the module contract in the mail. Closes trade-intelligence's pinned-vendor upstream ask. Small; next rivals window.
- [ ] **[infra]** **Plan lint: Scope-mentioned paths ⊆ Touches** (brand-identiy `01M15PMZ3` #1, proven live: a T07 Scope bound two files its Touches omitted; cards wiped at review-mount): candidate `check_plan_tickets.py` extension — flag a ticket whose Scope sentences name paths absent from Touches/Context Files. MEASURE fire rate on the plan archive first per doctrine.
- [ ] **[infra]** **Gate behavior question: a STAGED plan with no HEAD commit reds every session's diff-scoped gate un-attributably** (fleet `01M16Q0KQ`, two live occurrences): should `check_test_proposal`/the gate skip index-only plans, or warn-attributing to the stager? Needs a decided semantics, not a patch — the red is real work-in-flight, the tax is cross-session.
- [ ] **[infra]** **check_doc_links blind spots** (youtube `01M15AYX5` #2): cannot see cross-refs inside `docs/development/` or `docs/superpowers/`, and omits `CHANGELOG.md` from root sources — a Doc-Sync-mandated link class is never checked. Extend + measure the new fire rate before landing (archived plans link freely; a naive widening floods).
- [ ] **[infra]** **Playwright-MCP roots vs scratchpad directive contradiction** (brand-identiy `01M15PMZ3` #3): the MCP refuses the system-prompt scratchpad (`outside allowed roots`); agents work around via gitignored `.playwright-mcp/`. Either add the session scratchpad to MCP roots (settings) or sanction `.playwright-mcp/` in the fabrik-gui agent def — one of the two, documented.

---

## Context

- ⚠️ **Stale Prometheus scrape targets cause Telegram floods via the Phase 4 wire**. The netdata flood on 2026-06-06→07 ran for ~12 hours (24 messages every 30 min) because a `netdata:19999` scrape target was left in `prometheus.yml` after the container was retired 2026-05-30. Pattern: removing a service from compose MUST also remove its scrape job from `prometheus.yml`. Captured in commit `f5c6e48`. Should make this a registrar invariant check long-term.
- 💡 **Cross-mesh container→host scrape pattern works** via docker MASQUERADE rewriting the source IP to vps1's wg0 IP (`10.99.0.1`), which the spokes' existing `from 10.99.0.0/24 to any port <port>` UFW rules permit. Documented in [`prometheus-app-metrics-setup.md`](infrastructure/prometheus-app-metrics-setup.md) § aro-wake SLI metrics. Reusable for any future host-service that needs Prometheus scrape coverage from spokes (no firewall changes needed beyond the existing mesh allow).
- 💡 **Loop-guard counters are in-memory by design** — restart = reset = safe default. `rate()` / `increase()` in PromQL handle this via the `_created` timestamps that prometheus_client emits. Don't migrate to persistent counters; the reset semantics are correct.
- 💡 **Operator-reversal detector deduplicates by `(ai_source, ai_ts, operator_ts)` tuple** in [`detect_reversals.py`](../scripts/sysadmin/detect_reversals.py). Re-running 2× after a match produces 0 new entries. If we ever extend the schema, preserve this idempotency property.
- ⚠️ **sqlite3 `-csv` mode quotes timestamp fields with embedded space**, breaking `strptime` unless you strip quotes. The default `-list` (pipe-separator) mode works cleanly for our 3 simple columns. Documented in `detect_reversals.py` `collect_sidecar_actions()`.
- 💡 **Trio loop guards (4 layers) are sufficient for `consult`-only protocol AND future `propose`/`ack` Phase 5 work**. Same handler, same guards. No protocol version bump needed when Phase 5 ships propose/ack. Documented in [`scripts/sysadmin/peer-protocol.md`](../scripts/sysadmin/peer-protocol.md) §3.2.1.
- 💡 **Watchdog sidecar action log (`state.db`) is the canonical source for "AI took an action"** today — `sysadmin-actions.jsonl` is mostly diagnose-only wakes for now. When host-AI gains explicit action verbs (e.g., autonomous container restart from proactive-check), add the `action_name` + `target` fields to the jsonl entry so `detect_reversals.py::collect_host_sysadmin_actions()` starts firing.
- ⚠️ **Gatus configs live ONLY on vps1** (not in this repo) — see "Now" row above. If you edit an existing endpoint and want it source-controlled, you need to also pull the file into the repo manually OR do the gatus-source-control work first.

---

## [intel] 119 uncommitted ruff-format files sit under every session's diffs — land them AFTER the review-convergence plan closes (2026-09-09, owner: intel)

> Re-pointed 2026-09-09 by infra at the plan's Finish: the sweep is nobody's authored work — every bare `final_gate.py` run re-runs `ruff format` over the dirty set and re-stamps it (fabrik-32's infra mail 01M22XDJ7DQ5G8M2FES3DT2S44); the plan closed without staging any of it.

At 2026-09-09 09:53 local, 134 files in `/opt/fabrik` were modified in one minute — **120 `.py` under `scripts/` and `tests/`**, all sharing that single mtime. Proven, not eyeballed: for each file I ran `ruff format` on its own HEAD blob and compared bytes — **119 of 120 are byte-identical to `ruff format(HEAD)`**, i.e. they contain no human authorship whatsoever beyond what is already committed. The 120th, `scripts/enforcement/check_command_corpus.py`, carries an additional **8-line comment-only** edit citing "T08a round 1". **It is ORPHANED, not live WIP** — traced 2026-09-09: the only `T08a` on the box that owns this file is `docs/development/plans/2026-09-03-plan-1-multi-agent-per-repo/T08a-check-command-corpus-drop-the-orchestra.md`, whose Scope line names this exact path, and whose plan is **`Status: EXECUTED (2026-09-06 — all 33 tickets merged on converged reviews)`**. So a CLOSED plan left an uncommitted edit in a FLEET-SYNCED enforcement script and it has sat unowned for three days. Ruled out: `fabrik-44`'s in-flight plan (T01–T10, no T08a, and this path is outside its File Scope — it only reads `_fence_step` via `git show`), and the 2026-08-31 manifesto-command-pass plan (T01–T34, no T08a) which is where the "63 audited files" command-corpus vocabulary comes from — that plan is the likely source of the comment's CONTENT, but the ticket id belongs to multi-agent-per-repo. Routed to **infra** (`scripts/enforcement/` is their beat) rather than committed or dropped: judging whether an abandoned comment edit to an enforcement script is correct is the owner's call, not a cleanup decision. NOT part of the 119.

SOURCE UNIDENTIFIED, and the negative has a denominator: no Claude session ran a format at that minute — 6,020 transcripts across all 331 project dirs, 39,650 ruff-bearing lines scanned, 5 invocations inside the 06:50–06:59 UTC window (local 09:50–09:59) and **all five are investigation greps**, four of them mine. Ruled out by reading rather than recall: there is no `ruff-format` hook in `.pre-commit-config.yaml`; `scripts/wsl_startup_hook.sh` invokes no ruff/format/`final_gate` path; and `final_gate.py` scopes its fixers to the diff by design (its own comment at `:596` contrasts that with "a whole-tree `ruff format scripts/`"). The 09:53 mtime coincides exactly with commit `03bb9702` (the `wsl_startup_hook` auto-commit) but I could not convert that co-occurrence into a mechanism — so it stands as a coincidence, not a finding. Remaining candidates are outside the sessions: the operator's own shell, an editor/IDE action, or non-Claude automation.

WHY IT IS DEFERRED RATHER THAN LANDED — a timing interaction, not caution. `fabrik-44` is mid-flight on `2026-09-09-plan-1-review-convergence-redesign` (9 tickets, lock from `0c1f2d50`). Its ticket coders run in harness worktrees **branched from the unformatted HEAD**, and its merges are **index-only from those branch blobs**. So a formatting commit landed on those paths NOW would be silently reverted, path by path, as each ticket merges — a revert-without-conflict, which is the exact class this tree has hit five times in two days. The correct sequence is: their plan closes, then the 119 land as one formatting-only commit.

WHEN PICKED UP: re-run the proof before committing (the working tree may have moved) — for each candidate file, `git show HEAD:<f> | ruff format -` compared byte-wise against the working copy; commit **only** files where those are identical; exclude `check_command_corpus.py` and anything else that has since grown non-format content. Cite the comparison in the commit body. If the source is still unidentified at that point, expect it to re-fire and fix the generator rather than re-committing the output — a sweep that returns is a leak, and landing its output repeatedly is the wallpaper outcome.

## [infra] `claude_rotate.py --status --json` can exceed `quota_dashboard.py`'s 60s subprocess cap under partial network degradation (2026-09-05, owner: infra)

Found by the closing pass of the 2026-09-05 mail-queue review (native finder, re-derived from the call graph, not executed against a degraded network). `_oauth_get`'s worst case is ~32.6s per call with the defaults (2 hosts × (8s + 0.3s backoff + 8s)); on this box `--status --json` takes the FLEET path (`_cmd_status` → `_cmd_fleet_status` whenever `_fleet_dirs()` is non-empty), where `_fleet_account_rows` makes an unconditional `usage` call plus an hourly `profile` call per FRESH account — the `_FLEET_TOKEN_FRESH_S` gate only skips STALE tokens, so it does not bound latency in the normal steady state; the INVARIANT is that the aggregate has no wall-clock bound: per-call worst case × (2 calls × N fresh accounts), N=4 on this box, no budget across the loop. So any sustained slowness breaches `quota_dashboard.py:51` `PROBE_TIMEOUT_S=60`. THE ONLY COPY of the derived figures (the docstring and the rotation doc point here): per-host exhaustion = timeout + backoff + timeout = 8 + 0.3 + 8 = 16.3s. One dead host (host 1 exhausts, host 2 answers) ≈ 16.3s/call → ~32.6s per account (2 calls) → ~130s across this box's four accounts; a link-wide stall (both hosts exhaust — the 2026-08-22 VPN-drop shape) ≈ 32.6s/call → ~65s per account → ~260s across four. Derived from `OAUTH_GET_TIMEOUT_S=8`, `OAUTH_GET_ATTEMPTS=2`, `backoff_s=0.3`, `len(_OAUTH_HOSTS)=2`, N=4 — re-derive when any of those moves. The legacy `_account_status`/`_collect_statuses` path has the same unbounded shape. A regression test for the fix asserts the AGGREGATE against the cap (derived from the same constants and the account count), under both fault shapes — not a per-call figure. The 2026-08-22 incident entry in CHANGELOG describes exactly this path. A first draft of this row put the risk on the legacy path and called the fleet path gated — corrected by the review's pass-4 finder. That reproduces the 2026-08-22 "Live probe failed — TimeoutExpired after 60s" incident this retry was written to end, now needing only ONE flaky account among three rather than a dead link. Candidate fixes, sized as a change to a synced rotation surface (plan work, not inline): (a) a per-account wall-clock budget or short-circuit on `_fleet_account_rows` (the live path) and `_account_status` alike — a freshness gate is NOT the fix, since fresh accounts are the steady state; (b) a shared wall-clock budget across the `_collect_statuses` loop; (c) raise `QUOTA_DASH_PROBE_TIMEOUT_S` — the weakest, since it moves the cliff rather than removing it. Guard to ship with it: a test asserting the aggregate `--status` worst case against the dashboard's cap, derived from the same constants, so the next host/attempt bump cannot re-open the gap silently. The `_oauth_get` docstring no longer claims the per-call bound is inside the cap.

## [infra] Mailbox second pass 2026-09-03 — the findings that need infra's design or ruling, parked here so they are not re-hunted (owner: infra)

Each row is a filed mail still in the box (`mail.py read <id>`), read in full by the fleet session, judged to need a design decision or a grader-semantics ruling rather than a one-hunk fix. None is refuted; none is dropped.

- **check_convergence semantics cluster** — a plan whose ledger says RE-CONVERGED while its Status says DRAFT exits 0 (01M1H7DY: two-way consistency); an honest RED gate cannot be embedded (01M1HKZA: accept `failure` when every failing check is named); the coverage population is a diff RANGE, so a committed non-converged review flips verdicts as the base moves (01M1GZB5); the embedded gate must be no older than the last ledger row (01M1J02D item 2). One design pass over `check_convergence.py` + `check_review_coverage.py`.
- **`/fabrik-execute-plan` D2 pool precondition** — passes on `permissions.allow` while the POOL coder has no shell (01M1GRPM: $0.142, two discarded worktrees); plus the plan-7 dispatcher findings (01M1GXDV: absolute-path gate false-green in worktrees, shared-index priming, unvalidated lock base, `ack:no` blocking asks). A dispatcher spec, not a hunk.
- **`check_schema_sync.py` for TypeScript/YAML entity surfaces** (01M1JHZ2) — declare entity surfaces per project; the data-contract coupling is prose-only on every Astro/Zod project.
- **`check_plan_tickets.py` grammar** — Gate-vs-Touches containment, Depends-vs-Interfaces coverage, `path::symbol` citations (01M1GNGS items 3–5).
- **`check_doc_links.py`** — extension widening to mjs/ts/tsx/js (01M1H0YY, 01M1G8CR option C — WILL red gates fleet-wide, land advisory first), dead-anchor resolution against heading slugs (01M1KDTV finding 1), `path:NN` validation inside docs (01M1JF7Y — partly covered by `check_citations_resolve.py --changed` on reference docs). The link-base marker (option A) landed; these are the rest.
- **`final_gate.py` running vendored test dirs** (01M1HRWT) — `_uninvoked_test_dirs()` already names them; running them can red every project that vendors a red suite. Blast radius needs a ruling.
- **`check_index_md.py` unwired and failing** (01M1KDTV finding 3) — wire advisory-first or retire.
- **Route detector redesign** (01M1H61P — fleet's own filing): `check_doc_sync._has_route_change` is content-based; a path-based or literal-aware detector is a design choice.
- **Python runtime pin drift** (01M1KCXY): packs pin 3.13, the scaffold image is 3.12, upstream stable is 3.14 — a fleet runtime decision (rules-pass owner), not a one-line edit.
- **`fanout()` drops completed units** (01M1HVS3) and the pool `research` empty units (01M1GVW3 item 2) — `libs/subagents`, a sibling's live WIP today; intel's beat.
- **Governance-sync floor policy** (01M1H1V2 c): whether the floor may WRITE into a repo whose own rules ignore `.env` but not `.venv/` — the worktree adoption and the message are fixed; the policy is yours.
- **Stop-hook `waiting-on` state** (01M1GNKP item 2) and a MACHINERY-note duty when a brief names a tool the agent lacks (01M1J1WV systemic) — measure before building.
- **`exa` web_fetch strips angle-bracket URIs from plain-text payloads** (01M1GV6T machinery note) — MCP roster item.

## [infra] `commands/_fragments/grounding-research.md` is included by NO command (2026-09-03, owner: infra)

Found while draining infra's box: `grep -rl 'grounding-research' commands/` → only the fragment itself; no `{{include:grounding-research}}` in any of the 32 sources and no reference in `assemble_commands.py`. A fragment nothing renders is text that cannot bind anything — either wire it into the research commands (`fabrik-rivals`/`fabrik-spec` include `grounding-rules`/`subagents-core`, not this) or retire it. The 'a single-shot pool grounder MUST be told to fetch' rule from 01M1GSR9 went into `subagents-core.md` instead, which those commands DO include. Parked by the fleet session 2026-09-03.

## [infra] Stop-hook cause 6 re-arms on a CLOSED review's edits after resume (2026-09-02, owner: infra)

Intel's corroboration 01M1G8R520ZCDDX2P3KZGQYPDV (second live instance, session 4e90716e): `final_gate_stop.py:582-584` allows on `has_any_record`, but a closed-and-aged review-family record stops counting while the session's `authored_map` still remembers the pre-review `.py` edits across a resume — a guaranteed block on every long-lived session that ever edited code, cleared only by a `/fabrik-review-scoped` over a provably empty surface. Candidate fix (theirs, to measure): clear `authored_map` entries covered by a CLOSED review-family record at close time, so only edits AFTER the close re-arm cause 6. Parked here by the fleet session draining infra's box 2026-09-03; the mail is acked, this row is the durable pointer.

## [fleet] `tests/test_scaffold*.py` cannot run to completion (2026-09-01, owner: fleet = me)

From fleet's own reply 01M1G2Z9FS6SEZEF2B8GPYKZBN: the scaffold suite exceeded a 900s timeout with 10–11 live child processes (npm/uv installs inside the chrome-ext wxt scaffold) and produced zero output, so a generator change was verified end-to-end for `python-api` only, not `file-worker` or `chrome-extension`, which share `_logger_py_content`. A generator with no runnable suite is a surface where the next regression ships silently. Fix shape: an offline/no-install mode for the scaffold tests (skip `npm i`/`uv sync` under a `FABRIK_SCAFFOLD_OFFLINE=1` guard, assert the emitted files instead) — then the suite runs in minutes and the three logger-sharing types get exercised. Parked 2026-09-03 while draining infra's box.

## [infra] The git-isolation scrub has no end-to-end regression test (2026-09-01, owner: infra = me)

`tests/conftest.py`'s `pytest_configure` strips 14 `GIT_*` vars session-wide after incident
`f7627885` (a red-on-revert experiment's `git add -A` committed a sibling's WIP to master).
`tests/enforcement/test_git_env_isolation.py` asserts the scrub and the resulting behaviour — but
**both of its tests are green with the scrub reverted** under normal invocation, because nothing in
a normal environment sets `GIT_DIR`; they only red when the harness itself is started with it, and
no gate does that.

**The attempt and why it failed:** spawn a victim repo, run a NESTED pytest with a hostile
`GIT_DIR`, assert the victim's modified file is still UNSTAGED (` M`, not `M `). It red-failed
against correct code — the nested test file was written under `tmp_path`, which is outside the
`tests/` tree, so `tests/conftest.py` never loaded for it. It measured an unprotected process and
blamed the scrub. Writing the nested file inside `tests/` would work but is a tree mutation this
suite should not make mid-run.

**Current proof status:** the scrub is verified by a MEASUREMENT recorded in `d36239cc` (decoy repo,
pytest under a hostile GIT_DIR, victim HEAD and index confirmed unchanged) — not by a regression
test. So a future edit that deletes the scrub ships green.

**Shape of the fix:** a session-scoped fixture that writes the nested test into a temp dir *inside*
`tests/` and removes it afterwards, or a `pytest_configure` unit test that asserts the hook is
registered and pops the right keys from a synthetic environ. The second is weaker but has no tree
mutation.

**Trigger:** next time anything touches `tests/conftest.py`, or the next git-isolation incident.

---

## [infra] warn_only checks that print on a ZERO-finding run — 7 of 18, fleet-wide (2026-09-01, owner: infra = me)

**Measured**, not estimated: 18 of 19 `warn_only=True` registration sites in `scripts/final_gate.py`
run as scripts (the other 3 `warn_only` hits are runner/printer code). Each was executed bare in a
CLEAN fleet repo (`/opt/youtube`); **7 print on a zero-finding run**, so every green gate in the 48
synced repos carries that many content-free rows — in the human listing AND in the `--json`
`advisory` array, which applies no ⚠ filter (`scripts/final_gate.py`, `advisory_rows` is gated only
on `WARN_ONLY_CHECKS` membership).

| check | bytes on a clean run | what it prints |
|---|---:|---|
| `check_mutation` | 238 | `MUTATION (advisory): skipped in the per-commit gate …` — unconditional; can never carry a finding in gate mode |
| `check_pack_reachability` | 385 | dumps `reachable:` inventory with zero findings |
| `check_feedback_duty` | 272 | clean case not exercised (both probe repos had a real finding) — UNPROVEN |
| `check_plan_lock_release` | 225 | `0 stale | 0 likely-stale | 0 half-applied | …` |
| `check_spec_convergence` | 105 | `4 CONVERGED spec(s) examined, 0 with findings` |
| `check_vps_docs` | 90 | `PASS: check_vps_docs — 0 error(s), 0 warning(s)` (tier 3 only) |
| `check_phase_tests` | 85 | `PHASE-TESTS (advisory): OK — no active plan window …` |
| `check_rivals_dossier` | 76 | `rivals dossiers: 1 examined, 0 with findings` |

Clean-silent and correct: `check_vendored_drift`, `check_rule_grounding`, `check_trigger_routing`,
`check_frozen_chain`, `check_decisions_unique`, `check_doc_stubs`, `check_env_example`,
`check_ticket_breadth` (0 bytes each). `check_retired_terms` prints 6870 bytes of GENUINE warn rows —
not an offender.

**Why it is here and not fixed:** `22a1a062` gave `check_script_headers` a `--quiet` flag that the
gate passes, closing exactly ONE instance. Fixing 7 more scripts is outside that diff's surface and
is its own change. Recording it rather than letting the class die in a session's context.

⚠️ **Attribution corrected** — the finder reported these as "same defect, same author, same commit
range" as `d2e0d4f2`. They are not: `git log -S` puts the `N examined, 0 with findings` strings at
`9342ae9f` and `15bcec7a`, and the finder confused `test_plan_lock_release` (which that commit
touched) with `check_plan_lock_release` (which it did not). Pre-existing, repo-owned.

**Two fix shapes, both viable:** (a) add `--quiet` to each of the 7 scripts and pass it at each
registration site — explicit, skew-safe, precedented, 7 small diffs; (b) suppress zero-finding stdout
inside `run_optional_check` — one diff, but it changes a synced contract for every advisory row and
would need a sentinel convention. ⚠️ Do NOT "just pass `--quiet` to every warn_only check" from the
runner: scripts using `argparse` would exit 2 on an unknown flag, which `run_optional_check` treats
as a broken warn_only contract and FAILS the gate.

**Trigger:** the next time a warn_only check is added or edited, or the next gate-noise complaint.

---

## [infra] Review-machinery findings — ROUTED from the 2026-09-01 triage deep review (owner: infra = me)

Raised by author-blind finders during `/fabrik-review` of the LOCAL-vs-ARCHITECTURAL triage. Both are
OUT of that review's surface (pre-existing, different files) and are recorded here with owner + trigger
rather than smuggled into a command-corpus commit. Disposition: ROUTED, not deferred-to-nobody.

- **`command_run.py --reason` is unvalidated free text.** `:891` advertises "one of the three sanctioned
  BLOCKED cases" and `:1435-1438` stores whatever it is given — so an unauthorized fourth cause closes a
  run record cleanly. This is not theoretical: the escalation bullet deleted in `e82e7a0a` would have
  done exactly that. The three-case restriction is prose-only at the one moment it could be mechanical.
  **Trigger to build:** measure first, per FIX-directive verb 5 — count closed `blocked` records and how
  many cite a non-sanctioned cause (`~/.claude/state/command-runs/`); if >0, add a WARN-tier validator
  (rollout law: warn before block).
- **Two disposition vocabularies that no command cross-references.** `check_review_coverage.py:293-304`
  accepts a `## BLOCKED` section ONLY with 3-attempts evidence, while `:49-50` already carries
  `ROUTED(n)` for the "adjudicated, not open, not fixed" case — and no command source teaches `ROUTED`.
  That gap is precisely why my escalation bullet pointed at the path the grader rejects instead of the
  one it accepts. **Fix shape:** teach `ROUTED(n)` in the review commands' disposition vocabulary, and
  cross-reference the two in the grader's docstring so the next author cannot repeat the mistake.
- **`assemble_commands.py:829` mislabels source drift.** It prints `HAND-EDITED (N diff lines)` naming
  the INSTALLED file when the real cause is an uncommitted edit to the SOURCE — the message points at
  the wrong file. Same at `:690` (agents) and `:837` (skills). Cost me a re-check this session.
- **`CLAUDE.md` line-wrapping defeats phrase greps** (a bounded-search negative on that file is
  unreliable without `tr -d '\n'`) — the denominator-honesty class, hit live by a finder this run.
- **Corrected framing, fleet-wide:** the command corpus is NOT per-repo synced (`commands/` appears in
  neither the governance-sync files-filter nor `fabrik_synced_manifest.py`). Its blast radius is
  BOX-WIDE via `~/.claude/commands/` — one install, every repo on the box. My own commit messages said
  "ships to ~46 repos"; that is the wrong mechanism, and anyone sizing risk from it mis-models the
  change. Measured by a finder: 43 git repos under /opt; 223 paths in a project's synced.lock, none
  under `commands/`.

## [infra] Rules currency pass (operator-dispatched 2026-09-01, file-by-file) — cross-pack class findings

**FILE 27 — `core/app-audit-log.md` (2026-09-23): the audit log is mandatory in every project; the pack says what "properly" means and where the platform cannot yet deliver it (D-368).**
- **Fleet adoption (owed now, per the operator):** 37 of 41 project repos call `record_event` nowhere (census in D-368); no scaffold type emits the module or the table. Scaffold emission and a non-owning app role in the registrar are with fleet (01M37RTQ0NX8MJQAAXAHHMG723, 01M37SPA86MGV4Z7DDJFY4E4DJ).
- **fabrik-lib (10 changes, 01M37RT50PAADKY3Y5NR8GRCZK + 01M37SPA67NFMQ380B527P91QM):** IdP audit hook fails silently, writes `auth.login` and no failure/refusal rows, no `details`/`target_type`; no async writer; retention keeps billing/consent/gdpr forever and breaks chain verification; README and `data_retention.sql` claim the watchdog runs retention; the watchdog writes no `watchdog.*` rows; `reference_adapter.py` takes no lock and never commits; no Node port. Each interim workaround is in the pack — remove it as each lands.
- **Enforcement (measure first):** a gate check that a project carries the `audit_log` table and a scheduled `verify_chain` would fire in 37 of 41 repos today — decide its tier after scaffold emission lands, or it is wallpaper.
- **Projects:** transdoc's `account.*` strings and youtube's `admin.api_key_create/revoke` break the closed vocabulary (mailed).

**FILE 26 — `saas/60-saas-ui.md` (2026-09-23): the SaaS UI pack now describes the frontend the scaffold emits and stops imposing the house identity (D-366).**
- **Cross-pack drift, for their own turns:** 45 rule packs still carry the retired `TRAYCER USAGE` header comment (D-102; counted with `command grep -rl` over `.windsurf/rules`); `core/ocoron-design-system.md` § Save Behavior keys drafts per entity+user but not per tenant and says nothing about purging on logout; `docs/reference/gui-toolchain.md` names Tailwind v4 while the scaffold emits v3. `core/35-security-auth.md:186` says a leftover `middleware.ts` is silently ignored at build, while the Next.js Proxy doc (ledger op-01) says only "deprecated and renamed" — re-verify on core/35's turn (this pack now defers to it rather than restating it).
- **Scaffold (fleet, mailed 01M37NN5ZSM3EEG8CR7V30JB8R + 01M37P3K1Z59TG9XD9J5BK0Y7Y):** the i18n validator's Levels 2/3 still shell out to the retired Kilo CLI; `templates/scaffold/i18n-kit/` is a stale second copy of the kit `scaffold.py` seeds from `templates/i18n-kit/`; Tailwind v3 with `darkMode: ["class"]` and no pre-hydration theme script; `app/layout.tsx` mounts no `I18nProvider`; `AppShell` has no rail or hamburger; no Playwright/axe/LHCI devDeps; the backend env should set `AUTH_WEB_LOGIN_REDIRECT`; `main.py` does not install the IdP's `CsrfOriginMiddleware`, which passwordless web mode requires; the single `/app/settings` placeholder carries an in-app "Upgrade to Pro" card instead of the portal hand-off.

**FILE 25 — `ai/00-ai-model-selection.md` (2026-09-23): the AI index now puts the Claude subscription first and selects the latest models by alias (D-364).**
- **Cross-pack drift, for their own turns:** the other AI packs still carry the retired Kilo gateway (8 of the 10 per-category packs plus `core/62-using-subagents.md`) and versioned Claude names (`ai/30-language.md`, `ai/40-multimodal.md`, `ai/90-long-context.md`); each should select Claude by alias and cite the index's § Claude subscription first.
- **Sibling contradictions (their owners' turns):** `core/57-external-data-sourcing.md:221` says "LLM data = OpenRouter ONLY", which forbids `claude -p` for an external-data LLM step; `core/cost-budget.md` pins `claude-haiku-4-5` and a one-generation-old Sonnet id (:132, :152) and its ladder has no opus rung, and its line 28 makes per-call caps mandatory for every watchdog project while the index keeps USD per-call caps off the diagnose loop; `ai/30-language.md:21` still routes translation to DeepL, while the index now puts it on `claude -p` first. The index now says its § Claude subscription first wins until they are corrected.
- **Machinery (infra):** `rules_render_versions.py`'s `_LOOSE` sweep does not match Claude model-version prose (`Opus 4.8` passes), so the version-literal ban is unenforced for exactly this class — measure the fire rate of `(?:Opus|Sonnet|Haiku|Fable)\s+\d+(?:\.\d+)?` over the corpus before adding it.
- **fabrik-lib (llm-dispatch, mailed — see D-364's evidence):** the README's pin example is the superseded `claude-fable-5`; the default model is `opus` while the fleet ladder starts at `haiku`; `modelUsage` is dropped from `usage`/`budget_record`; the HTTP leg is taken on ANY CLI failure and reads the fleet's live keys; `LLM_DEFAULT_MODEL` defaults to a pinned placeholder id; `KILO_API_KEY`/`KILO_API_URL` still take precedence over `OPENROUTER_API_KEY` for a retired gateway; and `complete(model=…)` never reaches the `claude -p` leg, so a caller cannot escalate a rung through it; and `complete()` raises `ValueError` on a malformed numeric env var (`LLMConfig.from_env()` runs `int(...)` outside its try) despite its never-raises contract.
- **Benchmark engine (intel, mailed):** the ai-model-catalog engine crashes right after `update_gateway_counts` (psycopg placeholder error), so the hub's `ai/*.md` gateway-counts blocks have not been delivered since 2026-09-07; and `daily_refresh.sh` still regenerates Kilo-era artifacts (`kilo_agents.db`, the counts block, the `K` badge) for a retired gateway; and `claude_p_cost.json` carries a stale `amortized_per_mtok_by_family` (`amortized_per_mtok_by_family_carried: true`) that ranks haiku above opus and sonnet, the opposite of its own `per_model_spend.tiers`.

**FILE 24 — `core/self-healing.md` (2026-09-23): the ladder prescribed watchdog steps that cannot run; now it says which can (D-362).**
- **fabrik-lib (mails 01M37F6Z3F5GK9BHRFKE6H8JYG, 01M37FWQR19CQZ6CKMQCZFE39X, 01M37GQN02ETTD7AP4Y9SAW35F):** the sidecar passes `{}` as params at all three dispatch sites (`agent.py:791`, `coordinator.py:250`, `:319`), so every parameter-bearing action refuses; `scale_concurrency` targets `/opt/<id>` from a sidecar that mounts `/project:ro`; the README names the code-fix lane Tier C; its `code_fix_window_sec` Gotcha ignores the hub driver that renders the spec value into the env; the deadman cannot be acknowledged and bypasses the forbidden-target check; `http_5xx_spike` is blind to JSON access logs; `pause-state` does not classify httpx timeouts. Hub side (fleet): `drivers/watchdog.py` reads `wcfg.get("project_prefix")`, a field the spec rejects.
- **Approval-window conflict (fleet mail 01M37F6Z1PC7Y5R92EA5CN3EPH):** the hub spec defaults `code_fix_window_sec` to 1800 and the driver passes it through, against fabrik-lib's operator ruling of 300 (fabrik-lib D-236); `calendar-orchestration-engine` runs Tier D at 1800 today. The hub-side decision is owed.
- **Cross-pack drift, for 60-watchdog's re-visit:** its Tier A/C tables describe the parameter-bearing actions as working, its Tier-D window default is 1800 (the conflict above), and its § Worked example — OOM diagnosis narrates the kernel oom-killer line reaching `docker logs`, which it does not (the restart-count pass fires).
- **Research notes:** WebFetch truncates RFC 9110 and firecrawl's query mode failed on it; the Retry-After grammar came from the httpwg ABNF source.

**FILE 23 — `core/86-email-templates.md` (2026-09-23): the pack described none of the three vendored modules and carried refuted vendor facts; now it points at the modules and the facts are re-grounded (D-354).**
- **Cross-pack drift, for the owners' turns:** `core/35-security-auth.md:340` tells agents to call the Resend API directly from FastAPI — it should point at the vendored `email-transport` module (and its never-raises return). `core/35-security-auth.md:396`'s gate admits only Resend, while this pack now sanctions the SES transport. `mobile-app/00-domain-mobile-app.md:107` defaults push to "FCM via Expo Push or OneSignal", while `mobile-app/80-mobile.md:304-306` and this pack name only the Expo push service.
- **fabrik-lib (mails 01M36A3GQ0MRMPAN528CBJ0KBS, 01M36AKQW6NX3JCGH560030HYX, 01M36BHCQR0MDHNJWG6AJKPS50):** `email-templates/README.md` counts nine templates while listing ten and gives six and seven core renderers; `email-transport/README.md:10,:119` claims a one-domain Resend limit (the free plan has three) and `:105` calls a two-transport module Resend-specific; the module's documented vendor path cannot be imported, `tr.json` is a placeholder, `lang` carries the requested locale, there is no RTL path, and `render_welcome` defaults to Free / 0 credits; `build.py` compiles only a hardcoded template list, the transports' `.env` autoload is inert when vendored as a package, and `send_email`'s error carries no status to classify.
- **Routed own-fix residue (scoped review round 4, RECORDED — measured; destination: the next edit of `core/86-email-templates.md`):** the transport-error classifier names `SMTPRecipientsRefused`, `SMTPSenderRefused` and `SMTPAuthenticationError` as terminal whatever their reply code, so a temporary 4xx SES refusal (a 454 throttle at MAIL FROM, a 451 recipient deferral, a 454 temporary auth failure) would be dead-lettered instead of retried. Reword to "…and any other SES error — when its SMTP reply code is 5xx; an SES error with a 4xx code is transient whatever its class". Which SMTP step SES throttles at is unverified.
- **Unresolved:** AWS's SES FAQ still promises 3,000 free messages a month for 12 months, while the live pricing page describes Free Tier credits; the pack states neither until one source settles it.
- **Research notes:** WebFetch times out on docs.aws.amazon.com, fails TLS on mevzuat.gov.tr, renders only the title of iys.org.tr and Microsoft Tech Community pages, and misreads caniemail's colour-coded grid as support — firecrawl (with its og:description) and exa carried those. The 110 facts are in `docs/reference/research/2026-09-23-email-templates-currency-ledger.md`.

**FILE 22 — `core/85-payments-billing.md` (2026-09-23): three rulings behind the module it governs; now it describes the module.**
- **fabrik-lib (mailed 01M35MWWGG038XJVG2MAV3V2F2):** `payments/README.md:902` cites `85-payments-billing.md:130` (now § Resilience); psycopg 3 vs 25's asyncpg (25's turn); iyzico V3 header needs account enablement — possibly missing from the module's Gotchas.
- **Cross-pack / corpus (row 9 — owners' turns):** `commands/_sources/fabrik-spec.md:148` still says "PayTR (primary) with iyzico as its fallback"; `commands/_sources/fabrik-vision.md:506-508` says "TR domestic SaaS → iyzico … PayTR is WooCommerce-only, not SaaS"; `saas/88-saas-launch-checklist.md:117` says "PayTR, or iyzico as its fallback" and `:59` names only Paddle and iyzico — all predate fabrik-lib D-084's billing-model split. `commands/_sources/fabrik-spec-review.md:165` lists "iyzico / Paddle / RevenueCat" (no PayTR).
- **Blocker (fabrik-lib 01M35P4TBZVB665H5DVD25SD29 + correction 01M35P9VK6JCHWAPZSGGPNWP35; fleet 01M35P4TDRECDC4J6D0B2P4EHY + correction 01M35P9VMZAVB9HHZPQV9635XT):** `purchases` has only a `FOR SELECT` tenant policy, so no hub-sanctioned role can record a PayTR one-off; the write path is a scoped fulfilment-worker role with `INSERT`+`SELECT` grants and both an `INSERT` and a `SELECT` policy (a grant or an `INSERT` policy alone is refused — measured), not the ingest role; `docs/CONFIGURATION.md:216`'s `verify_service_role(…, allow_policy_based=True)` checks nothing — both need fixing before PayTR goes live.
- **Open (operator's):** TRY recurring billing has no Non3D-free rail (iyzico subscription = NON3D; no iyzico account, fabrik-lib D-235) — any product that needs it is a planning decision.
- **Research method notes:** iyzico's TR page carries the NON3D fact the EN page omits, while PayTR's EN page carries the retry interval the TR page omits — read both languages and diff; WebFetch invented an `exp` claim in Paddle's example portal JWT (decode it); `stripe.com/global` loses its country list under exa-raw; `mevzuat.gov.tr` breaks WebFetch's TLS chain but reads via exa's iframe URL.

**FILE 21 — `core/67-file-api.md` (2026-09-23): the pack described a service and a sandbox that do not exist; now it describes the scaffold that ships.**
- **Scaffold (fleet beat, mailed 01M35GSMKNRNT3WDAWWVSP60Z9 + 01M35JNA6534F8AVR124NJ2W2T):** healthchecks on the dependency-checking endpoint with no `/healthz`; presign with a default client signs an empty-body CRC32; first-tenant `authMiddleware`; uncapped download expiry and open CORS; presigned PUT leaves `content-type` unsigned; `DELETE` drops the row after a failed object delete; Supabase Pattern B auth; deprecated `@aws-sdk/util-retry` with an inaccurate "adaptive" comment; Express pinned to the legacy major; `confirm` skips the scan; `saas-skeleton` + Traycer `spec-pipeline` copied into every scaffold type; Dockerfile on `bookworm` vs `versions.yaml` `trixie`. The scaffold's comments quote pack text ("67-file-api mandate: …") and went stale with this turn — the mail asks for the grep.
- **Research doc (infra, hub-local):** `docs/reference/research/Node API File Storage Rules.md` carries the misattributions this turn removed (its NIST citation [30] is an arXiv paper on LLM agents; its undici figure misquotes the README) — the pack now says "superseded where this pack corrects it"; the doc itself is left as a dated research artifact.
- **Cross-pack (row 9):** `12-node.md` makes Fastify the greenfield default while the file-api family stays Express CJS — consistent (12's "existing CJS stays CJS"), recorded only. `35-security-auth.md` § API-based systems says a service "validates" Pattern A JWTs but not that HS256 makes the validator a minting-capable secret holder, nor that the `jti` denylist is invisible to it — 35's turn. `app-audit-log.md` is the chain authority; 67 reuses it.
- **fabrik-lib `app-audit-log` (recorded, not mailed — a doc-comment drift):** `schema.sql:11` says the payload uses "sorted keys" while `_canonical_payload` uses a FIXED order, and `schema.sql` ships `ts DEFAULT now()` which the module's own clamp note warns against; the hub's `app-audit-log.md` has no lock/clamp text at all — that pack's turn.
- **Tenant registry posture (95's turn):** 67's retention job iterates "the tenants table" as `app_role`; neither 67 nor `95-multi-tenant-saas.md` gives that table's DDL or RLS posture — if it is itself tenant-scoped, a job with no GUC cannot list it.
- **Not mandated anywhere (the pack now says so):** KVKK's deletion regulation requires the 3-year record, not a hash chain — the chain is house policy.
- **Research method notes:** registry-level WebFetch truncates (`time` objects missing, a stale busboy range) — use `/<pkg>/latest`; GitHub release pages gave 2024 for 2026 releases; Cloudflare's `*.preview.developers.cloudflare.com` hosts still carry the old `WHEN_REQUIRED` advice the live page dropped; a follow-up SendMessage to a researcher that has already handed back is lost (it cannot reply) — dispatch a new seat instead.

**FILE 20 — `core/66-rag-chunking.md` (2026-09-22): the pack described a chunker nobody has; now it says which half is the module's.**
- **fabrik-lib `rag/` (mailed 01M34V4146R9SNMNF8QZKJBFC3):** no Markdown-aware path (`chunker.py:5` plaintext-only; both fleet consumers pass a hand-written `heading_path` (two elements for youtube, one for trade-intelligence)) — a `chunk_markdown()` pre-pass requested; `Chunk.chunk_header` computed but never embedded (`ingest.py:295`) — a `prepend_header` flag requested, grounded on Contextual Retrieval; the two fleet copies (`trade-intelligence/src/rag/chunker.py:32`, `youtube/rag/chunker.py:33`) declare `TOKEN_API_CEILING = 6800` but neither enforces it (corrected in 01M34VNWQD453PB8D3MXWM9WES) — re-vendor is fabrik-lib's to route; and in the module itself (01M34WBKN4JCRXAWZNP11GRHER) the ceiling backstop runs only when the ceiling is under the hard max, the one-chunk early return can emit a sub-hard-min piece unlogged, and the ceiling env is read at import.
- **Not implemented anywhere (the pack now says so):** the § 9 fence/table/anchor quality checks — a project's Markdown pre-pass writes them or its plan says it did not; a hub-side grader is not warranted until a project ships a Markdown corpus (none does today: trade-intelligence ingests customs-tariff plaintext, youtube ingests transcripts).
- **Cross-pack (row 9):** `65-rag-search.md:87` re-cut in this commit (the keyword band it cited no longer exists); 65 § Done When's 512–800 line already agreed. `ai/30-language.md:10` still says "Opus 4.8 default" and "pgvector on Postgres/Supabase" — that pack's turn.
- **Research method notes:** the pack's "beyond 1,200 tokens precision drops / below 120 context is lost" had no source and none was found — replaced by the measured picture, which points SMALLER than the pack's target; the LangChain docs moved (python.langchain.com → docs.langchain.com / reference.langchain.com, 308s) — exa found the new pages after two WebFetch redirects; OpenAI's tokens help page returns 403 to WebFetch — Azure's page carries the same ~4-chars-per-token statement.

**FILE 19 — `core/65-rag-search.md` (2026-09-22): the fleet fact the pack promised for four months, the module as reference, the paused runtimes out.**
- **Fleet (fleet beat, open since the 25-data turn — backlog rows at ~983 and ~1974, mail 01M1EHNXT4/01M1Q6K71P/01M1M5VS0H):** `postgres-main` = `postgres:16-alpine` (PostgreSQL 16.11, musl), `pg_available_extensions` = `pg_trgm 1.6` only (installed in `glitchtip`), NO `vector`; `specs/services/youtube.yaml:49-52` tells a reader to `sudo apt install postgresql-16-pgvector` — impossible on an alpine image, and no `youtube_pipeline` database exists on `postgres-main` (the youtube project's DB is elsewhere). The route the pack now names: the fleet swaps the image family to one that ships pgvector for the fleet major, then a superuser `CREATE EXTENSION` per database. Re-probe command in claims row `fleet-postgres-main-no-pgvector`.
- **fabrik-lib `rag/` (mailed 01M34G3PPNQ2AE1SAZYM6N1E54):** paused runtimes still wired (`adapters/lanes.py` soft-imports the retired `subagents.lane_chain`; `_dotenv.py` autoloads `~/.config/fabrik/subagents.env` + Kilo/NVIDIA lane keys); README Prerequisites assume pgvector on the fleet DB; `psycopg2` throughout vs 25's by-name `psycopg2-binary` ban — an OPEN CONFLICT (the pack says so; 25's turn records the exception or the module changes driver — mailed to fabrik-lib in the same message); `search()` fails open to a bare `[]` with no degraded signal and is retry-free by design (mailed 01M34J9VGVEQJ5ZJF9CEQW0KH1 with the free-first-hop rerank tier); docstring prices stale (`qwen/qwen3-8b` is $0.117/$0.455 per M today, not $0.02); `dimensions` honouring per provider undocumented → the pack asks for a length assert.
- **Cross-pack (row 9):** `kilo` still named in `tojlo-design-system.md` (2), `ocoron-design-system.md` (3) and `62` (4, all "paused" context) — a corpus-wide "Kilo retired/paused" sweep, not solo flips; `tojlo-design-system.md:2108` `PG16` is that pack's row-6 debt; `25-data-postgres.md:23` still says "NOT currently installed (probed 2026-09-01)" — true, and it now has a sibling probe here; its re-audit should cite one claims row for both.
- **Research method notes:** the Meilisearch six-rule list was a documented-then-changed default (seven from v1.36.0, and the fleet's `getmeili/meilisearch:v1.13` still runs six — a rule about a version-dependent default names both, or names neither; `meilisearch_major` joined `versions.yaml` for it) — a "verified 2026-05" claim rots silently when the vendor splits a rule; the semantic-chunking "3–5%" and the MRL "1–3%" figures had no primary source at all (both now stated as unmeasured); `WebFetch` on GitHub's Releases tab reads an empty shell (JS-rendered) — read `CHANGELOG.md` instead.
- **Residue recorded, not fixed (the scoped review's closing round):** `66-rag-chunking.md`'s own chunk table (300–800) vs 65's 512–800 default band (landed at file 20, 2026-09-22 — 66 now keys to the module's 512–800); `src/fabrik/spec_loader.py:320` docstring says "full-text/vector search" for `has_search_feature` — Meili is keyword-only; `src/fabrik/drivers/meilisearch.py:38` calls `delete_index` "the rollback path" — its only caller is `destroyer.py`'s `--drop-data` branch; `apps/postgres-main/compose.yaml` names `postgres-main` with NO memory limit and `postgres:16-bookworm` while the live compose is `infra/vps1/postgres/compose.yaml` (`16-alpine`, 2G) — two tracked composes for one container (mailed to fleet); `specs/services/youtube.yaml:52`'s `apt install postgresql-16-pgvector` cannot run on alpine (same mail); 65 § Done When names 76's managed-API routes (`76-gpu-workers.md:28,31,67`) as NOT its self-hosted carve-out — 76's next pass re-reads `65:235` (a sibling-pack tripwire, no claims row); `25-data-postgres.md:119,303,313,329` still name `75-workers-jobs.md`'s parent monitor as the psycopg2 exception while `75:109` calls psycopg2 "legacy-only" — 25's turn (row 9 there).

**FILE 18 — `core/62-using-subagents.md` (2026-09-22): the paused pool moved out, D-335 applied, the Claude Code limits stated from the docs.**
- **Second opinion (Fable, row 4): 22 findings → 9 confirmed (8 fixed here, 1 routed to the CLAUDE.md twins' owner), 13 recorded (10 fixed), 6 refuted.** Fixed here: the companion's regex-born empty blocks (an opener-line parser now), six pool-era one-liners that fell out of the move, D-321 → D-330 for "no round cap", the declared-budget/hand-off half of D-335's terminal, `experimental` struck from the frontmatter key list (a plugin-manifest key, not an agent key — read from the 2.1.276 binary), the two leaf-briefed types named (`fabrik-gui`, `general-purpose`), the ban bound to modules and verbs (`libs.subagents`, `ai-consult`, `kilo run`, a raw OpenRouter call, `claude -p` from a seat), the fragment's "restore by uncommenting" sentence and `check_plan_tickets.py`'s `62-using-subagents.md:118-120` line cite. Routed: hub `CLAUDE.md:599` / template `:613` "re-enabling is an uncomment" — fabrik-38's chunk 3. Recorded, not fixed: `commands/_agents/fabrik-reviewer.md:3` says "the dispatching Opus session" (Fable orchestrates, Opus when Fable refuses) and `check_subagent_flywheel.py:9,:346` hint text names the retired "§ Dispatch policy's pool-default" heading — both infra beat, next corpus touch.
- **Scoped review, own-fix residue (recorded per the scope-growth stop, all fixed in-run):** rounds 22/18 → 9/9 → 1/1 → 0 — round 2 was contradictions my fixes introduced (a CLAIMS row left saying `FORCE=1` after the pack said "any value"; the resume rule's fallback named a status string the pack then dropped; a corrected containment sentence that no longer supported its own inference), round 3 one registry row trailing the pack sentence it mirrors. Two lessons the seats named: pin CLAIMS.yaml beside every pack under review (registry drift is invisible otherwise), and a "the only X" claim about a minified bundle needs `grep -c` for its population first — the seat retracted its own round-2 count.
- **The D-191 tripwire, measured (row 3):** `/fabrik-review` runs closed since 2026-09-08 with a round ledger = 4 of the 20 rows the tripwire waits for (31 · 3 · 6 · 4 rounds; median 5, mean 11 with the one 31-round run). Above the 4 the rule names, on a quarter of the sample — not yet a verdict; re-measure at 20 rows (`~/.claude/state/command-runs/*.json`, `command == fabrik-review`).
- **Cross-doc (infra beat, sibling in flight):** `CLAUDE.md` and `templates/governance/CLAUDE.md` § Pointers "Subagent fan-out" still cite `dispatch_headroom.py --delta <n>` and D-229's "one fresh seat + hygiene script ≤ 20 lines" (3 refs at HEAD) — retired by D-335; both files carry fabrik-38's D-335 chunk-2 WIP, messaged to them, not edited here. `.windsurf/rules/ai/00-ai-model-selection.md` keeps one `<!-- POOL OFF -->` block — its own turn moves it to the frozen doc (row 9).
- **Row 3 grounding of a pack about the harness itself:** the claude binary (`grep -aoE` on `$(readlink -f "$(which claude)")` — 2.1.276) carries the refusal string and the env-var names; `dispatch_headroom.py --help` has no `--delta`; the four agent type files show which omit `tools` (`fabrik-gui` inherits `Agent`); `env`/settings show `CLAUDE_CODE_SUBAGENT_MODEL` unset. A research seat mis-stated the model resolution order (env var first) from a third-party blog; the docs page (firecrawl, verbatim) says per-invocation → frontmatter → env var → parent since v2.1.251 — the same aggregator-vs-vendor class as file 17's Thunder Compute price.
- **Frozen doc refutations owed to the pool's owner (fabrik-lib / intel) before any re-enable:** mcp SDK v2 is the stable line (the pool's MCP client imports v1's `ClientSession`); OpenRouter `/credits` needs a management key. Recorded in the doc header, no mail — the pool is paused and nobody is building on it.

**FILE 17 — `core/76-gpu-workers.md` (2026-09-22): three stale-state claims about the hub's OWN surface, and the deferrals.**
- **The class: a rule pack narrating hub build state.** The pack said `fabrik gpu` was "future / not yet implemented" beside an "as of 2026-06-16 it shipped" paragraph, told services to write `shape.needs_gpu: true` (a field `Shape` lacks — the spec FAILS TO LOAD, `scaffold.py:5736-5740`), and called fabrik-lib's chain-rebuild helper "requested, not yet shipped" (it is `health_probe.live_chain()`, mail `01M14E3MWN` acked done 2026-08-28). Every "not yet" in a pack is a claim with an expiry and no watcher; the fix here was grounding by EMITTING (`create_project(..., project_type="python-api-gpu")` into scratch — the standard's row 3 now says so) and by reading `gpu_rent.py`. Detector: wallpaper for 3 instances; re-audit item for every pack with a "future"/"not yet" heading (`command grep -rln 'Not yet implemented\|(future)' .windsurf/rules --include='*.md'`).
- **Scaffold-side (fleet beat — mailed this turn):** the emitted `src/<pkg>/gpu_handler.py` docstring says the kind "is read from the spec's `shape.gpu_kind` field" — no such field, the constant `DEFAULT_KIND` is the only source (`scaffold.py:5757`); `templates/python-api-gpu/defaults.yaml:3` says `app/gpu_handler.py` (the path is `src/<pkg>/`); `gpu_rent.HOURLY_USD_BY_PROVIDER` is stamped "verified 2026-06-16, re-verify quarterly" and is 6 days past due (RunPod Secure H100 SXM now $3.49, PCIe $2.89; serverless flex $4.79 vs the `0.50` idle budget; Modal $3.95 holds) — `fabrik gpu compare` prices on it.
- **Line-number cites INTO a rule pack (class, 2 instances, both fixed this turn):** `docs/operations/gpu-rent.md` ("rule line 342") and `gpu_checkpoint.py` ("lines 305–319", "line 310") pointed at line numbers a rewrite moves; both now cite the section heading. Any future pack turn: `command grep -rn "rule line\|lines [0-9]\+–[0-9]\+" docs src --include='*.md' --include='*.py'` before committing.
- **Research seat vs primary page:** the GPU-cloud seat reported Thunder Compute H100 at $2.19 from a third-party index; the vendor's own pricing page (tier 2, exa) says $3.20. A price from an aggregator is a claim about the aggregator — the pack carries the vendor number and the claims row cites the vendor page.
- **Second opinion (Fable, row 4): 17 findings → 16 fixed, 1 recorded.** (a) `58-resilience.md:595` said the chain-rebuild helper was "requested, not shipped" — it is `health_probe.live_chain()`, vendored to projects as `libs/health_probe/` by the governance sync; the clause is FIXED in this same change (the "pack narrating build state" class above, second instance in a sibling pack). Recorded: (b) `check_pack_reachability.py` examines only packs declaring `applies_to` (2 of 13 types) — 76 has globs and no `applies_to`, so its green asserts nothing about this pack; a re-audit turn that cites it as evidence for a globs-only pack is citing wallpaper.
- **Scaffold-side, second mail:** the emitted `requirements.txt` has no `fabrik` while `gpu_handler.py` imports `fabrik.orchestrator.gpu_rent`; `rent()` is hub-local by construction (`/opt/fabrik/.env.sysadmin`, `$FABRIK_ROOT/data`, `~/.fabrik/ai_usage.db`). The pack now states the hub-side precondition; the scaffold either drops the helper into a hub-run job template or documents the same.
- **My own instrument error, caught by the seat:** I ran the renderer from `scripts/` (one directory too high) piped into a grep — the script lives at `scripts/sysadmin/`, python printed "No such file" to stderr, grep matched nothing, and I read `rc=0` (grep's) as a clean sweep. The real run (`scripts/sysadmin/rules_render_versions.py --check`) reports the same three literals as file 16 and none in 76. A pipeline hides the producer's exit code; the producer's own rc, not the filter's, is the number.
- **Round-1 scoped review (3 seats, 22 confirmed) — code defects in the surface the pack describes, mailed to fleet as one finding:** serverless endpoints are never tagged (`_create_serverless_endpoint` passes no `env=`, so a lost state record makes them FOREIGN to the reaper); `rented()` lacks `rent()`'s recorded-id destroy fallback and catches only `RunPodError` on destroy; `_compute_actual_cost` prices every provider at RunPod rates (Modal under-counted ~27% against the daily cap) and returns $0 for serverless; `rented()`'s per-call estimate ignores `provider`; the reaper's `lifetime_exceeded`/`destroy_pending` lists are not provider-scoped under `reap_all_providers`; Modal + `keep_warm_after_use` leaves a permanent `active` ghost in state; `gpu_checkpoint`'s docstring claims a completeness check the LIST fallback does not do; two stale `fabrik gpu` CLI help strings (`--image` default, `--needs-serverless`). The pack now states each as the code IS. (b) `./mutants/` is a tracked mutation-testing tree that shadows every `src/` path under a bare `command grep -r .` — no rule names it beside `.claude/worktrees/` and `.tmp/` as a denominator exclusion (infra). (c) The seat-brief phrase "never read under /home or ~" collides with the harness persisting an over-long tool result to a home path; briefs should exempt the harness's own persisted-output path.
- **Scoped-review own-fix residue (recorded per the scope-growth stop, all fixed in-run):** rounds 22/0 → 11/11 → 3/3 → 1/1 — every post-round-1 finding was a contradiction my previous fix introduced (a false "Traefik drops it" clause, a table cell forbidding what Done When permits, a caps figure that ignored the int lifetime). The pattern: a fix that adds a JUSTIFICATION adds a claim; a fix that restates a rule in a second place adds a contradiction surface. Next pack turn: fix the rule in ONE place and cross-reference, never restate.
- **Cross-pack question for 55-observability's owner (row 9 — not flipped here):** 55 `:491/:553/:574` says `/health` verifies consumed APIs before returning 200; 76 follows it (zero reachable providers → non-200) but a survivable consumed-API loss behind a failover chain with a graceful fallback arguably deserves 200 + `"status": "degraded"`. Either way the scaffold emits no Traefik load-balancer healthcheck label, so a non-200 never drains the container — it alerts. 55's turn decides the semantics; 76 will follow.
- **Header comment still names Traycer** (as do 25 of 28 core packs) — cross-pack class, D-102 retired the orchestrator; owed to a corpus-wide sweep, not a solo flip (bar row 9).

**FILE 16 — `core/75-workers-jobs.md` (2026-09-22): deferrals, one debt closed, and one of my own claims retracted.**
- **Scaffold-side (fleet beat — `01M342MM0WQCQ72WQ0354MT25D`, corrected by `01M343KNE86FPSEM0Z9DF9T85N`):** the first mail attributed the asyncio pool at `scaffold.py:2596` to the file-worker scaffold; it is `_SAAS_WORKER_PY`, emitted only by `_scaffold_saas_backend` (`:3276`). `_scaffold_file_worker` (`:3855`) copies `templates/file-worker/worker/main.py` verbatim, and that file is a Supabase-RPC, fixed-concurrency, `time.sleep` poller (`command grep -c`: supabase 6 · time.sleep 1 · ThreadPoolExecutor 2 · SKIP LOCKED 0 · LISTEN 0 · WORKER_MIN 0 · max_retries 0 · structlog 0) — three of the pack's own banned patterns on a retired backend. Also theirs: `Dockerfile.j2:2` `python:3.12-slim-bookworm` (a literal AND the codename D-064 retired, in the one surface that builds images; `rules_render_versions.py` sweeps `.windsurf/rules` only); no reaping PID 1 (no `tini`, no `init:`); `compose.yaml.j2` has no `stop_grace_period` (only the saas worker service does, `scaffold.py:3191`); the SAAS worker's retry is `POWER(2, attempts)` with no jitter and literal 5/5s. The pack was re-keyed at this turn to state the pool's properties and to tell the agent to verify the emitted worker rather than assume it — and to stop demanding Traefik labels of the HTTP-less file-worker compose (`with_traefik=False, healthcheck_kind="process"`, `scaffold.py:3966-3977`).
- **`25-data-postgres.md` (file 5, DONE) now cites an exception that no longer exists:** `:303`, `:313`, `:329` grant `75-workers-jobs.md` a `psycopg2` carve-out for parent monitor loops; 75 carries 0 `psycopg2` after this turn (asyncpg throughout). A re-audit item for 25 — the class is "a pack's rule keyed to another pack's text that moved".
- **Version literals owed to their OWN turns** (`rules_render_versions.py --check`, 2026-09-22): `65-rag-search.md` `pgvector:pg16` (landed at file 19, 2026-09-22) · `tojlo-design-system.md` `PG16` · `mobile-app/00-domain-mobile-app.md` `PostgreSQL 16` — the remaining two unevaluated; row 6 at each.
- **D-064 codename debt — CLOSED.** The "7 live hits" line above is stale: `75-workers-jobs.md` lost its `bookworm` at `214d9e49a` (2026-09-05) and carries the `debian_codename` span at its Dockerfile sample; `76-gpu-workers.md` has 0 hits (`command grep -c bookworm`, 2026-09-22). Nothing remains to flip.
- **Row 7 — `Lesson N` cites, re-measured after the second opinion refuted my first count.** My instrument (`LESSONS_LEARNT.md…Lesson N`) demanded the file path and so missed cites without one. Correct instrument `command grep -rnoE "[Ll]essons? ?#?[0-9]+" .windsurf/rules --include='*.md'` over 56 packs: **2 lines, both in `58-resilience.md`** (`:214` "Lessons 72 & 74", `:575` "Lesson 73"), and both resolve BY NUMBER to unrelated hub lessons (72 ISP SYN-ACK, 73 docker.sock `group_add`, 74 `claude -p` flags) — dangling by meaning. This turn removed the two in 75. Owed to 58's re-audit. A detector for a 2-instance class is still wallpaper (FIX directive 5); the class is "a fleet-synced pack citing a PROJECT repo's lesson number".
- **A row-3 method the standard should name:** reachability is a glob hit on a directory name; the only executable ground truth for a pack's claims about "what the scaffold emits" is `create_project(..., base=<scratch>, generate_spec=False)` into a scratch base and grepping the result. The second opinion did exactly that and it is what caught the mis-attribution above. DONE 2026-09-22 (file 17 turn): row 3 now names the method.

**DETECTOR GAP — `_LOOSE` misses several literal shapes (re-measured 2026-09-02; the first version
of this entry was WRONG and is corrected below).**

`rules_render_versions.py::_LOOSE` catches `Node 24` / `Debian 13` but not everything. Denominator:
**56 rule files** (`find .windsurf/rules -name '*.md' | wc -l`). Spanned lines excluded.

| shape | hits | pattern (the instrument) | verdict |
|---|---:|---|---|
| tool-name outside the alternation | 6 | `\b(React\|Electron\|Vite\|Next\.js\|…)\s+\d+\b` | **REAL** — `Electron 30`×4, `Next.js 14`, `React 19`. The exact class `_LOOSE` was built for; only the name list is short |
| bare package pin `x.y.z` | 10 | `(?<![\w.:/-])\d+\.\d+\.\d+(?![\w.])` | **MOSTLY REAL** — `sentry-sdk[fastapi]>=2.18.0`, `1.4.11`; 2 are dates (`23.05.2026`) |
| bare Debian **codename** | 7 | `\b(trixie\|bookworm\|bullseye)\b` | **REAL, and the worst** — see below |
| `>=N` | 20 | `>=\s?\d+` | **NOISE** — `CHECK (balance >= 0)`, `>= 99.5%` crash-free, `>= 500` status codes. ~1 of 20 is a version |
| `^N` / `~N` | 0 / 1 | `\^\d+` / `~\d+\.\d+` | **EMPTY** post-fix; the one `~1.05x` is a throughput ratio |
| `vN` | see note | `\bv\d` → 111 occurrences / 25 files | **MIXED** — `Recraft v4.1` real; `v1 = one workflow`, `/v1/` paths not |

⚠️ **The first version of this entry claimed `>=N`/`^N`/`~N` were "high signal — dependency ranges"
and proposed widening for them. That is backwards**: after file 14's fix the corpus holds ~zero true
positives in those shapes, and widening would red ~10 packs entirely on thresholds and ratios — the
wallpaper FIX-directive verb 5 forbids. It also quoted a `vN` count of 59 with no pattern recorded;
`\bv\d` yields 111. A count without its instrument, in the ledger whose governance anchor is
denominator honesty.

⚠️ **The codename shape is the one with NO detector at all, and it silently defeats the span test.**
`nginx:mainline-trixie` contains no digit, so `_LOOSE` cannot see it: unwrap a `debian_codename`
span and nothing fires. That is why the pinned span COUNT matters (file 14 was pinned at 4 against 9
actual — five spans removable with zero signal until corrected). The 7 live hits are `bookworm` in
`75-workers-jobs` (×3) and `76-gpu-workers` — the D-064 debt already deferred to those packs' turns.

**Deliberate fix, when taken:** extend the name alternation (cheap, high signal), add a codename
watch keyed off `versions.yaml::debian_codename`, and leave `>=`/`^`/`~`/`vN` alone. Not done here:
it touches a fleet-synced detector and belongs in one measured change, not mid-pass.

## [infra] Rules currency pass (operator-dispatched 2026-09-01, file-by-file) — cross-pack class findings

**PACK-SIZE PRESSURE — RESOLVED by retiring the cap (D-071, 2026-09-02); one sub-item survives it.**
File 13 was trimmed from 61 KB back under the then-blocking 50 KB auto-load cap. **That cap has since
been removed** — it was a Windsurf-era context budget and Windsurf is retired — so byte pressure is no
longer a reason to shed rule content anywhere in the corpus. The trimming itself stands: every byte cut
was a duplicated implementation (a hand-rolled `CircuitBreaker` that fabrik-lib ships as
`CircuitBreakerRegistry`, a `TRANSIENT_PATTERNS` table the scaffold emits, a second TS client
re-implementing `fetchWithRetry` — the defective one).

**Still open, and NOT about bytes:** `58-resilience`'s globs are overbroad — `**/client*`,
`**/health*`, `**/dispatch*` activate it on nearly any service touch (a `clients/` dir, a Redux
`dispatcher.ts`). That is real context cost the byte cap only ever proxied for, and it is unaffected by
the cap's removal. Related option, now optional rather than forced: splitting the worker-only
§ Autonomous Pause-State Pipeline into its own pack (the section already declares "applies ONLY to
`file-worker`/`file-api`", and every `python-api`/`saas-skeleton`/`mobile-app` project currently loads
worker rules it can never use).

**FILE 12 RE-AUDIT (2026-09-02) — three classes deferred to their OWNING surfaces (bar row 9), all
found by the author-blind opinion and verified:**
- **`15-api-contracts` has ZERO webhook text** (`grep -in "webhook|hmac|compare_digest"` → 0 hits)
  while 57 says an inbound receiver "is a served route: `15-api-contracts` applies". 57 now carries
  the receiver's auth posture + delivery semantics itself; at 15's turn decide whether the inbound
  receiver contract (signature, timestamp tolerance, event-id dedup, ack-fast) is 15's to own or 57's
  to keep — one home, then a pointer from the other.
- **The command corpus never asks for the profile** — 0 of 32 `commands/_sources/*.md` mention
  "Capability Profile" or `57-external`. The pack's "teeth at plan time" is currently 57 alone. A
  single bullet in `/fabrik-plan-review`'s checklist ("every external dependency in the plan has a
  profile, or an `UNKNOWN — <tried>` per field") is the measured first step — command corpus,
  merge-time render only.
- **fabrik-lib `async-http-client` surfaces neither `Deprecation`/`Sunset` headers nor a
  distinct expired-credential outcome** (`grep -in "sunset|deprecat|401|expir"` over the module → only
  the breaker's own "OPEN + expired"). Profile fields 9/10 are therefore project-local to implement
  today. A one-hook request to fabrik-lib (log-once + counter on first `Deprecation` seen; a typed
  `CredentialRejected` outcome) is the lean fix — cross-repo, so filed by mail, not edited from here.

**SEEDED FOR FILE 13 — `core/58-resilience.md` says "Never retry 4xx" and never mentions 429.**
Measured 2026-09-01: `grep -c 429 .windsurf/rules/core/58-resilience.md` → **0**;
`grep -ci retry-after` → **0**; the rule at `:86` reads "Retry transient errors: timeout,
connection, and 5xx … Never retry 4xx." 429 IS a 4xx and is the canonical retryable one — an agent
following 58 literally will never retry a rate limit, which is backwards, and will ignore
`Retry-After` because 58 never names it. Surfaced by file 12's new Capability Profile field 2
("429 + `Retry-After`?"), which an agent can now answer correctly and then be told by 58 not to act
on. Fix in 58's own turn: carve 429 (and 408) out of the never-retry-4xx rule and require honouring
`Retry-After` when present.



**THE GOAL (D-062, operator verbatim):** always-uptodate · correct · lean · efficient ·
low-maintenance · free · resilient · traceable · logged · fastest · agile · best-practice.
**Standing ruling:** version literals are banned from packs — tripwires are triage (D-061);
the solve is a machine-updated version source + render-time injection (pipeline proposal owed
during the pass). Scope: core/ then ALL folders, to completion.

- ✅ **bookworm→trixie FLIPPED (D-064, 2026-09-01, 30-ops's turn).** Grounds: Debian 12 regular
  security ended 2026-07-12 — the fleet had built on an EOL-full-support layer for 7 weeks; trixie
  stable since 2025-08, images live. One yaml line + one render because the spans were laid
  file-by-file (the D-062 machinery's first class-flip in anger). 40-documentation had already
  dropped its literal; 50-code-review reworded version-free. Scaffold emission now TWO axes stale
  (bookworm + 3.12) — see the interpreter-gap alignment row.
- Evaluated so far: 10-python (2026-09-01 — 3.13→3.14 current-stable fixed; Alpine rationale
  updated to the PEP-656 reality; distro literal deferred to the class commit) · 12-node
  (2026-09-01 — full bar; record below).
- **Tripwire ARMED** (`rules_currency_watch.py`, weekly-cron rider): pinned python/node vs
  endoflife.date, mails infra per new upstream release (watermarked, silent on blips). First
  scheduled firing: node 26 LTS on 2026-10-28 (packs pin 24). This is the "what happens in one
  year" answer — the drift now pages instead of waiting for a re-read.
- **File-1 SECOND OPINION adjudicated** (mandatory subagent bar, backfilled 2026-09-01): 14
  verdicts → 9 ACCEPTED+applied (fail-open secret exemplar; temp-rule rationale rewritten
  honest incl. ephemeral/persistent split; global-handler-default + `from exc`; /healthz–/health
  split defined pack-side; single-process-uvicorn made an explicit rule; async-discipline block
  [task refs · shared AsyncClient · now(UTC)]; ruff `ASYNC`/`B`/`S` baseline; pinning policy;
  router-tutorial shrunk + testing section pointed at 45) · 2 REGISTERED as aging claims
  (glitchtip-5xx-capture → 55's turn; musl-allocator) · 2 CLASS-DEFERRED (30-ops HEALTHCHECK
  target + the duplicated CMD block — 30-ops's turn) · 1 REFUTED (in-file prose↔table dedup:
  the banned table is an INDEX of the prose, one truth + one index, not two truths).
- **Scaffold alignment owed** (rule leads, scaffold follows): emit /healthz in python-api
  template; emit ruff ASYNC/B/S selection in scaffolded pyproject. Trigger: next scaffolder window.
- **DEEPENED same day (operator: "very shallow") → CLAIMS REGISTER (D-061):** `.windsurf/rules/
  CLAIMS.yaml` — every external assertion as a dated, verify-hinted row; the watcher mails infra
  when a claim outlives its window; the pass grows the register file-by-file (10-python's 7 claims
  + 2 class rows seeded). Version regex = layer 1; claim windows = layer 2.
- **File-2 (12-node) COMPLETE under the full bar (2026-09-01).** Own research legs: Node 22 is
  Maintenance-only (pack said "both active LTS" — false); type stripping stable+default (the
  `--experimental-strip-types` prescription was a self-contradicting relic); Express current
  major is npm `latest` since 2025 (pack said "post-2026 maybe"); helmet/pino/vitest headings
  de-literalized; CVE trio re-grounded to the 2026-03-24 advisory. All 18 `_LOOSE` hits +
  regex-blind shapes (Fastify 5, Express 4/5, pino v9+, Helmet 7+, chalk v5+, Paddle v2) triaged;
  spans: `node_lts`, new `node_engines_floor`, `debian_codename`. **SECOND OPINION (Fable 5,
  author-blind, D-063 dispatch pin): 33 verdicts → 18 KEEP · 14 FIX + 1 ADD adjudicated as: 8
  already covered by my own pass, 9 newly applied** (Express-major pin warning; Mastra
  `easy-day-js` RESTORED — it verified the incident my search missed and I had wrongly deleted;
  ALS ~7%-overhead causality inversion fixed → negligible-under-AsyncContextFrame; 20s-backstop
  false rationale → scaffold `stop_grace_period: 45s` grounded at scaffold.py:3126; ungrounded
  "Traefik strips __proto__" safety claim deleted → patched-runtime floor rule ADDED;
  `@fastify/helmet` clause; CVE-21713 recast as bug-class-not-userland-mitigation; nonexistent
  `@stripe/stripe-node` → real `stripe` package, both occurrences), **literal-bearing correction
  shapes REJECTED** (its "helmet 8+"/"pino v10" suggestions re-literalize; staleness findings
  accepted, shape overruled per D-062 — the subagent is deliberately blind to the ban). 9 new
  claims rows + node-lts-line widened. Pinned tests now parametrized over CLEANED_PACKS.
- **Scaffold alignment owed (12-node additions):** compose template already emits
  `stop_grace_period: 45s` (verified); Node scaffolds still declare `engines.node ">=22.0.0"` —
  when the previous LTS EOLs (Apr 2027) raise the floor AND flip `node_engines_floor` in
  versions.yaml in the same change.
- **Scaffold alignment owed (15-api-contracts):** the pack now mandates the un-prefixed
  `Idempotency-Key` header (industry-consensus name — the IETF httpapi draft EXPIRED at -07;
  RFC 6648 deprecates `X-`); the scaffold's widget example still reads `X-Idempotency-Key`
  (`scaffold.py:2990` — its docstring also cites the pack by line number, which shifted). Rule
  leads, scaffold follows: flip the emission to accept `Idempotency-Key` (keep `X-` as legacy
  fallback) at the next scaffolder window. Note the scaffold example is a POST — still
  key-required under the narrowed POST/non-idempotent-PATCH scope.
- **TWO OPERATOR LENSES ADDED TO THE BAR (2026-09-01, post-file-6):** (a) `docs/infrastructure/`
  fleet docs are mandated grounding for deploy/VPS-surface packs — read AND live-verified (they
  rot both ways: the inventory had the true redis tag while agents-fabrik:183 had aspirational
  pgvector); (b) **D-065**: OPERATIONS.md + DEPLOYMENT.md are fleet-AI interfaces — fully
  current, machine-consumable (what/how to deploy; which VPS services: workers, systemd, cron).
  Enforcement lands at 40-documentation + 75-workers-jobs + deploy-surface turns: check the
  rules ENFORCE currency + consumability, not merely name the files.
- **File-11 (55-observability) COMPLETE under the full bar (2026-09-01) — the largest pack (501 lines) and the most FICTION.**
  Triggered by the operator's live symptom ("agents are not creating a proper logging system"),
  measured to root cause rather than guessed. **Answer: the machinery works, the SCAFFOLD leaks** —
  site-provisioner emits textbook structlog JSON *and* raw uvicorn access lines on the same stdout
  (34.6% of its 24h lines carry no `{`), because scaffold.py:799 uses `PrintLoggerFactory()` which
  bypasses stdlib entirely and the emitted CMD runs uvicorn with default access logging. Rules side
  fixed here; scaffold side filed (01M1EP16E2HBFYA2G4XKJV9X1C). **THE FILE-1 CLAIM DISCHARGED:
  glitchtip-5xx-capture VERIFIED TRUE IN SOURCE** (`_DEFAULT_FAILED_REQUEST_STATUS_CODES =
  frozenset(range(500,600))`) with three precisions the row had hidden — 5xx ONLY (4xx captured by
  nothing), duck-typed on `.status_code`, recorded `handled: True`; row rewritten, window 180→365.
  **SECOND OPINION (Opus 5, 39 verdicts — the deepest of the pass): accepted wholesale.** Its
  findings, each re-verified by me at the source before acting: the Loki section named THREE LABELS
  THAT DO NOT EXIST (`service`/`environment`/`level`; the live set is container_name/filename/host/
  job/service_name/stream — my own probe) so its worked LogQL example returned zero rows; the
  pipeline diagram described docker.sock auto-discovery when the config uses a filesystem glob;
  the metrics code block called ACTIVE_JOBS/PROCESSING_COUNT Gauges when they are a **Histogram**
  and a **Counter** (`.set()` would raise) and taught `Counter("request_count")` when the client
  auto-appends `_total`; `src/metrics.js` HAS NEVER EXISTED; the matrix claimed `file-worker` serves
  /health + /metrics when it scaffolds no HTTP server at all (deps: boto3/structlog/supabase/pypdf);
  TWO of five alert rows describe alerts that exist nowhere in configs/, and "never page on CPU/RAM"
  is contradicted by five shipped paging rules; and the pack claimed enforcement from
  `check_health.py`/`check_watchdog.py` — both WARN-only AND documented UNWIRED in final_gate.py.
  It also corrected MY OWN uvicorn prescription from this same turn (it silenced rather than routed
  and omitted `log_config=None`, without which uvicorn re-applies its dictConfig over yours) — now
  a 3-step form. **OTel: measured REJECTION recorded** (logs are the weakest OTel signal; adoption
  costs a Collector + re-instrumenting 46 projects for tracing nobody needs) with the nuance that
  the forced Promtail→Alloy migration adopts it at the COLLECTION layer anyway. Fleet findings
  filed: 01M1EQ3NCA98EF178ZY366V47T (**Promtail EOL 2026-03-02, still running**; node-api template
  default sets exposes_metrics with no metrics module → permanently broken scrape target).
  Net +33 lines on a 501-line pack: mostly deletions of fiction plus ~8 corrective sentences.
- **File-10 (50-code-review) COMPLETE under the full bar (2026-09-01) — the worst-contradiction pack.**
  Own legs: TWO drift-anchor INVERSIONS shipping to ~46 repos — "the user commits and pushes,
  coding agents only implement and fix" (vs commit-at-task-end + push-at-task-end, both § UNIVERSAL
  anchors) and "Max 5 review iterations then STOP" (a fourth halt condition vs converge-to-fixed-
  point + the three BLOCKED cases); § D prescribed TWO NONEXISTENT scripts (kilo_code_review.py /
  kilo_docs_enforcer.py — in the sync's RETIRED_CORE_SCRIPTS, i.e. actively deleted from projects:
  a guaranteed-fail instruction, not merely stale) → replaced with the real /fabrik-review family;
  stale "one of 14 trigger-based doc updates" (matrix carries 25) → SSOT pointer, no count.
  **SECOND OPINION ran on OPUS 5 — first exercise of the D-063 quota fallback (Fable 5 limit hit
  mid-turn).** Its verdict: all four legs CONFIRMED real (and #1 worse than I stated — the sync
  guarantees the script's absence), and then it caught that FOUR of its top five were MY OWN FIX
  RESIDUE: I fixed instances and never swept the file for the class (FIX-directive verb 2). All
  accepted and swept this turn — `:97` Key Reminder contradicted my new `:36` 61 lines apart;
  "full gate at milestone, not every task" survived in THREE places (header, § C heading, Key
  Reminders) against the per-task completion-gate law; Output Format shipped a COMPETING
  GATE:/NEXT: grammar with PASS/FAIL where the gate emits "status": "success"; "stop and ask"
  against the question bar / operator-decision bar; orphaned Systemic Gate H3 under § D; dead
  "iteration limits" vocabulary; bare `--lean` in the child-project note. ADDED per its verdicts:
  FIX-DIRECTIVE + 62-using-subagents pointers. **External-practice research (13 sources) REJECTED
  a new mechanism** — 2026 consensus keeps a ceiling but as a BUDGET exit with a different report,
  never as the quality gate; our convergence law + 3-round escalation already matches the shape,
  and the false-consensus risk it names is already mitigated by "refuted with the disproving line".
  Rejection recorded per FIX-directive verb 5. CROSS-REPO ROUTED: /opt/fabrik-lib is sync-EXCLUDED
  and still carries the entire pre-fix pack — mail 01M1ENAVE3MD0KV5HMWC74QEXJ (with the systemic
  ask: excluded repos need a periodic pack-diff, or their rules contradict the anchors their own
  drift check enforces).
- **File-9 (45-testing-strategy) COMPLETE under the full bar (2026-09-01).** Own legs: the pack's
  biggest policy line MOVED with the world — the blanket Vitest/RTL ban for Next.js narrowed to the
  ASYNC-RSC boundary (official Next.js docs now recommend Vitest for the unit lane; async Server
  Components remain Playwright-only BY DESIGN) + two consensus E2E-discipline lines (never stub a
  server action from Playwright; test the production build); @playwright/test >=1.59 floor →
  version-free wording + claims-row boundary. **SECOND OPINION (Fable 5, 15 verdicts): the two
  lenses DISAGREED on both my edits and the adjudication is recorded — (a) Playwright floor: their
  keep-it-load-bearing point (fix only 5 months old, old pins live) is sound, but the version-free
  wording carries the same protection and D-062 wins on shape; (b) Vitest ban: they'd keep it as
  Trophy-coherent; I hold the narrowing (a rule contradicting the official docs erodes pack trust;
  Trophy bias kept explicit). Their FOUR new catches all accepted: the fixture example silently
  depended on asyncio_mode="auto" (breaks under pytest-asyncio 1.4 strict default — exactly in the
  no-pyproject fabrik-lib carve-out; disclosure line added); example default `testdb` was REFUSED
  by the pack's own require_throwaway guard (→ myproject_test); ASGITransport-never-runs-lifespan
  caveat added (scaffolded apps are lifespan-based); and the CROSS-PACK CLASS: `src.main:app`
  matches NO scaffolded layout (scaffold emits src/<package>/main.py, scaffold.py:1487/:4834) —
  swept in the same change across 45 (regen one-liner), 30-ops (CMD ×2), 10-python (×3); the 2
  residual mentions are deliberate never-do-this references.** 3 claims rows. Zero literals.
- **File-8 (40-documentation) COMPLETE under the full bar (2026-09-01) — the D-065 owner turn.**
  A registry-derivation pack whose hand-forked enumerations had all drifted from their own SSOTs.
  Own legs: D-065 fleet-AI interface bar landed (deployed-types callout + deploy-config/scheduled-
  jobs matrix rows); DECISIONS.md added everywhere it was absent (universal list + matrix row +
  allowlist — a fleet-synced doc pack with no decision ledger, post-D-000); retired-docs self-
  contradiction closed (matrix + allowlist still mandated API_REFERENCE/DATABASE_SCHEMA/DOCS_INDEX
  that line 41 retires — registry sides with retirement); trailers table caught up (ci-fix,
  Agent-Name, post-commit verify line); dead my-workflow/06-* citations repointed (§ Step 8
  verified at :124). **SECOND OPINION (Fable 5, 23 verdicts): accepted — STRATEGIC_BACKLOG
  mis-bucketed as SaaS (registry :272-281 made it UNIVERSAL, operator rule 2026-08-27);
  docs/flows.md missing entirely (registry :254-260); matrix canonicality claim false (PROJECT_DOCS
  is SSOT, table now says it renders it); 7 more project-side matrix rows (flows/ui/design-system/
  data-contract/troubleshooting/docs-index/backlog); docs/traycer/** allowlist line dropped (gate
  flags it); plan-SET shape added; AGENTS.md open-standard line (Linux Foundation, 60k+ repos).
  PUSHED BACK on one: "Traycer machinery is gone" is overbroad — the PATH is dead but Traycer is
  the operator's live planning tool (open thread this week); citations fixed, Traycer kept.
  Gate-vs-gate fix in-beat: VALID_DOCS_SUBDIRS lacked user-guide while check_user_guide REQUIRES
  it — one-line fix in check_structure.py.** 2 claims rows. Zero literals (internal-facts pack).
  SEPARATE finding filed: 19 enforcement tests RED at committed HEAD (D-053 coverage-gate family,
  sibling mid-flight surface) — mail 01M1EKG4BFS4HCNK516ZQ5HBK3.
- **File-7 (35-security-auth) COMPLETE under the full bar (2026-09-01) — the high-risk pack.**
  HEADLINE: the committed file was AMPUTATED — commit 6e404160 (the 12-factor pass) wrote it back
  from a truncated read, ending with a literal '…[truncated]' line; 7 Done When rows + the entire
  security-critical Spec Contract — Auth Registrars section (bearer-bypass warning) were absent
  from HEAD for weeks and survived that pass's reviews. Restored from 6e404160~1, all citations
  re-verified live (check_api_bypass verifier.py:465); corpus swept (1 amputation total); guard
  test added (rules + commands/_sources + templates), Lesson 147. Own legs: JWT alg-pinning rule
  (allow-list verifier, none rejected); HS256 scoped to issuer==verifier w/ EdDSA/ES256 escape;
  frame-ancestors added (XFO formally obsolete); CVE-2025-29927 recast (patched; rule outlives).
  **SECOND OPINION (Fable 5, 25 verdicts, zero FALSE claims, every in-repo cite verified exact):
  all FIX/ADD accepted — middleware.ts→proxy.ts staleness (current Next.js SILENTLY IGNORES a
  leftover middleware.ts: nonce/redirects stop, no error — highest blast radius), CSP directive
  gains frame-ancestors+form-action (was contradicting the pack's own checklist), Factor III ✅
  example shipped a hub-BANNED localhost silent fallback (now fail-loud os.environ), denylist
  two-sources-of-truth fixed (lib SHIPS it), Argon2→Argon2id (OWASP; lib defaults exceed minimums),
  passkeys honest-limit line (OTP not phishing-resistant; fabrik-lib request first), sticky-session
  ❌ example was invalid Python with mislabeled mechanism (fixed), settings.py path nit.** 6 claims
  rows. Convergences with my legs: frame-ancestors + RS256→ES256/EdDSA found independently by both.
- **File-6 (30-ops) COMPLETE under the full bar (2026-09-01) — the class-owner turn.** D-064
  bookworm→trixie EXECUTED (own grounds: debian.org + endoflife + Docker Hub tag probes; the
  opinion independently endorsed with digest-level proof). File-1 deferrals closed: HEALTHCHECK
  → dep-free /healthz (migration clause for pre-split services; compose-override mirror named);
  base-image table span-carried. Parity section rewritten to PROBED truth (VPS runs
  postgres:16-alpine + redis:7-alpine; U+2011 hyphens killed; Alpine ban scoped to images WE
  build). **SECOND OPINION (Fable 5, 17 verdicts + flip endorsement): 4 FIX + 1 ADD accepted:
  apt exact-pin example was BROKEN on the pack's own new base (ffmpeg=7:6.1.1-3 absent from
  trixie — the only Follow-verbatim block that failed verbatim; pins dropped, base-is-the-
  boundary rule); unpinned pip-install-uv → Astral's COPY --from with span-owned uv_version pin;
  file-1's debian-slim-variant claims row was over-broad (bare -slim = trixie TRUE for python,
  FALSE for node, digest-proven) → superseded (3rd supersede of the day); redis-fleet-major
  horizon row added (7.x security ends 2029-12, current 8.x); builder/runtime same-base ABI
  sentence added. Its empirical re-proof that deploy.resources.limits works under plain compose
  v2 (live docker inspect) retired that lore-caveat question.** 30-ops: 10 spans, zero residual.
  pgvector probed NOT INSTALLED in postgres-main → 25-data corrected + claims row; fleet mail
  owed (agents-fabrik.md:183 claims it "fully self-hosted" — aspirational-as-fact).
- **File-5 (25-data-postgres) COMPLETE under the full bar (2026-09-01).** Own legs (brave + exa +
  WebFetch endoflife/SQLAlchemy/pgbouncer.org + live psql probe): stdlib `uuid.uuid7()` (Python
  3.14) replaces the uuid_utils idiom for current-python services; PgBouncer guidance rewritten
  two-layer; pg16 literals → new `postgres_major` span (fleet state, agents-fabrik.md:165, flip
  tripwire in claims); PG18-uuidv7 boundary → capability-probe phrasing. **THE SWEEP ITSELF had a
  blind spot: `_LOOSE` spelled 'PostgresQL' so real 'PostgreSQL 16' never fired, nor PG18/pgvector:pg16
  shapes — widened red→green; 7 literals surfaced in this pack that the sweep had passed** (16
  advisory WARNs now corpus-wide — other packs' hits belong to their turns). **SECOND OPINION
  (Fable 5): 20 verdicts → 15 KEEP · 4 FIX + 1 ADD; convergent with my legs on the two big ones
  (stdlib uuid7, PgBouncer staleness — it graded the old mandate 'the pack's one materially stale
  rule', inherited from asyncpg's own unrevised FAQ). Two of its catches corrected MY fresh work:
  (1) 'the scaffold default' phrasing was FALSE — scaffold.py:4809 still emits python:3.12 +
  uuid-utils (verified myself), pack now says so; (2) my pgbouncer claims row said 'default 0/off'
  — pgbouncer.org primary says DEFAULT 200 (ON) in current releases → row refuted + superseded
  (second supersede today).** saas/ prefix fixed. 3+1 claims rows, 1 superseded.
- **Scaffold alignment owed (25-data + file-1 follow-through — the INTERPRETER GAP, now TWO axes):**
  scaffold emits `python:3.12-slim-bookworm` (scaffold.py:4809, ×4) while the corpus spans
  python_stable=3.14 AND debian_codename=trixie (D-064) — interpreter and distro both drifted. At
  the scaffold window: bump the emission to the span values, drop `uuid-utils` from scaffolded
  requirements (scaffold.py:2042) in favor of stdlib uuid.uuid7, emit /healthz alongside /health
  (the health split), flip the idempotency header emission, and source the Dockerfile pin from
  versions.yaml so it cannot re-drift. (This row now aggregates ALL scaffold-alignment debt from
  files 1-6.)
- **File-4 (20-typescript) COMPLETE under the full bar (2026-09-01).** Own legs (brave + exa +
  earlier WebSearch/WebFetch): TypeScript's native-compiler major is GA (ships as `tsc`, API
  port next minor) — pack got a version-free currency line; zod 4 stable, pack idiom unchanged.
  **SECOND OPINION (Fable 5): 17 verdicts → 11 KEEP · 4 FIX + 2 ADD, all accepted** with
  literal-bearing phrasings converted to spans/version-free per D-062: `erasableSyntaxOnly`
  ADDED to the strict block (turns 12-node's erasable-syntax prose ban into a compiler error —
  the unwired checkable gate); the numeric-only enum ban was a CROSS-PACK CONFLICT with 12-node
  (native stripping refuses ALL enums) — banned-table row widened; `forceConsistentCasingInFileNames`
  DELETED (TS 5.0 default = dead weight); both `FROM node:24-bookworm-slim` literals wrapped in
  spans (the known debt item — this pack now auto-flips with node_lts on 2026-10-28); `paths`
  without `baseUrl` (hard error in the current major); dev-side type-stripping cross-ref;
  12-node added to Related Packs (asymmetric backlink); saas/ prefix on 60-saas-ui (×2).
  4 claims rows. CLEANED_PACKS += 20-typescript (4 spans).
- **RETIRED-CONSUMERS class, split disposition (2026-09-01):** mechanical header mentions of
  Windsurf Cascade / Kilo CLI swept from 10-python, 20-typescript, 50-code-review, 67-file-api,
  72-desktop (12-node done at its turn). SUBSTANTIVE Kilo-as-gateway content remains in
  **65-rag-search (gateway tables + a Done When line mandating OpenRouter/Kilo), ai/00-ai-model-selection
  (peer-gateway policy + dual-route counts), ai/60-code, ocoron-design-system (i18n levels 2-3),
  saas/60-saas-ui:325** — real guidance contradicting the retirement ruling (LLM access = Claude
  Max OAuth + OpenRouter only); owned by each pack's own evaluation turn, NOT a sed sweep.
- **File-3 (15-api-contracts) COMPLETE under the full bar (2026-09-01).** Own legs (multi-engine:
  brave + exa + WebFetch/PyPI + WebSearch): header flip, hey-api pin-exact, oasdiff v1.26
  currency, idemptx existence. **SECOND OPINION (Fable 5): 17 clusters → 12 KEEP · 4 FIX + 1 ADD,
  all accepted**: idempotency scope narrowed to POST/non-idempotent PATCH (PUT/DELETE idempotent
  per RFC 9110); idemptx name dropped (decorator-not-middleware, semi-stale redis<6 pin,
  off-culture named dep); OFFSET ban got the bounded-admin recorded exception; Deprecation header
  re-grounded on RFC 9745 (date-valued) + Sunset RFC 8594; store-key scoping rule ADDED
  (endpoint+principal); saas/ prefix on the 95-multi-tenant pointer; oasdiff CI-absence grep
  re-verified 2026-09-01. **One reversal of MY leg: the IETF idempotency draft is EXPIRED, not
  standards-track — my same-day claims row refuted and superseded (the register's supersede
  discipline exercised for real).** One defect neither lens caught alone, fixed while editing:
  flow step 4 said "Key absent" where it meant "key not yet in Redis". Zero literals (0 spans —
  claims-rot pack, not literal-rot).

## [intel] `flush_outbox` reports `all-rows-malformed` on an EMPTY outbox — a data-loss verdict for a benign state (2026-09-03, owner: intel = me)

Found on the FIRST unattended run of the newly-wired flush step (2026-09-03 06:01, `cache/update.log`),
on the hub's own row — the line an operator is most likely to read:

```
fabrik   fabrik/.tmp/subagents   pending 0 · flushed 0 · left 0 · rounds 1 · reasons ['all-rows-malformed']
```

**No data was lost.** `libs/subagents/pg_ledger.py:1102-1104` returns `all-rows-malformed` whenever
`good` is empty after parsing the `.flushing` file — which is also true when the file is EMPTY or
whitespace-only, the common residual case. The real discriminator is already in hand and thrown away:
`bad` is non-empty only when rows were genuinely parsed and rejected. Verified: `find /opt -name
pg_outbox.corrupt.jsonl` returns **nothing**, so the `bad` bucket was empty on every walked dir — the
hub simply had a leftover empty `.flushing`, which the same code path then unlinked.

- `good` empty **and** `bad` empty ⇒ the outbox was empty. Benign. Should read `outbox-empty`.
- `good` empty **and** `bad` non-empty ⇒ real quarantined data loss. `all-rows-malformed` is correct.

**Why deferred rather than fixed in-run:** the fix is a one-line discriminator, but it lives in
canonical `/opt/fabrik-lib/subagents` and carries the vendored blast radius (48 sync-reachable copies,
50 live — see D-093). A fleet-wide re-vendor is disproportionate for a log string on its own. **It
should ride the next `libs/subagents` change**, not trigger a sync of its own. Needs the operator's
explicit cross-repo word at that point, as every vendored edit does.

**Cost of leaving it:** advisory noise only — but it is exactly the noise that makes a REAL
`all-rows-malformed` unreadable when one eventually fires. Wallpaper is how enforcement dies.

---

## Activation

Items move to active development when:

1. **Focus window opens**: A block of 3+ hours of uninterrupted time is identified — applies to "Now" tier specifically (DR drill needs 3-4 hours, Gatus migration needs 1-2 hours).
2. **Triggering incident**: A "deferred until real case" item gets a real case (propose/ack, Apprise pre-route, Loki ruler, repeated-flag detector).
3. **Repeated friction**: The same operational pain hits 3+ times in a week — e.g., the same PromQL query becomes "type this AGAIN" → Grafana dashboard tier.
4. **Resource availability**: External tools / budgets / operator availability — DR drill needs a throwaway VPS purchase.

The hardest discipline here is the second one — resisting the urge to build "propose/ack" speculatively because it sounds important. The Phase 5 plan explicitly says: each new incident teaches; capability expands from incidents, not architecture.

## [fleet] Zitadel /debug/metrics not enabled — Prometheus target DOWN (2026-08-29)

Zitadel v4.17.1 deployed at auth.ocoron.com does NOT serve `/debug/metrics` by default (404) — the
`specs/services/zitadel.yaml` spec declares `exposes_metrics: true` + `monitoring.metrics_path: /debug/metrics`
but never sets the env that ENABLES Zitadel metrics, so the Prometheus scrape target is registered but
`health=down` (404). `docs/reference/zitadel.md:52` wrongly claims metrics is "enabled by default via
`ZITADEL_METRICS_TYPE: otel`". FIX: ground the correct Zitadel v4 metrics-enable env, add it to the spec,
re-apply (`fabrik apply` re-syncs env), confirm `/debug/metrics`=200 + the Prometheus target flips to `up`;
correct the reference doc's default claim. The IdP itself is fully live + functional — this is monitoring polish.

## [infra] Measure the hub's own test suite — the self-exclusion has let it rot (revisited 2026-08-29)

**Revisit requested by the operator** (3 stale-test findings traced to it). Grounded this session:
`final_gate.py:842 _ci_runs_pytest()` runs a repo's suite only on a `.fabrik/run-pytest` marker OR a
CI-workflow pytest mention. **fabrik has neither + 225 test files**, so its suite never runs at the gate —
"unmeasured." The exclusion was "measured and REJECTED for now" (`final_gate.py:855`) to avoid reding the
gate with stale suites on landing day.

**Empirical result of running it (2026-08-29): 25 failed, 4964 passed, 5 skipped in 1h20m01s.** Two
independent reasons a naive `.fabrik/run-pytest` marker is WRONG: (1) it would red every session's gate
with the 25 failures; (2) an 80-min suite cannot run on every gate touching src/tests/scripts even all-green.

**The 25 are overwhelmingly STALE TESTS (code evolved, tests didn't) — the exact rot the exclusion hid:**
`test_shape_phase_4k` (Shape gained `has_bearer_api`/`needs_payments_ingest`/`uses_claude_cli`/`claude_cli_home`);
`test_state::test_save_writes_all_8_fields` (state now writes a 9th field `target_vps`); plus contract-drift in
gate-canaries, session-orient-hook (×4), kaizen (×3), final-gate-symlinks (×5), scaffold, mail-addressing,
file-worker-logger, select-rules (this one reads sibling-dirty `.windsurf/rules` + `libs/subagents/select.py` —
verify vs a clean worktree before attributing). Scoped run: 23 failed / 113 passed in 20s.

**Fleet-side measurement of the same class (wef 01M1R81T, 2026-09-05):** web-ecommerce-factory's `pytest tests/` runs 791s against `TIMEOUTS["pytest"]` = 900s (their D-104), so their sentinel stayed UN-armed under their D-102 — then their wef1 lane re-measured 431s while a sibling suite ran and ARMED it (their D-111, 2026-09-05, supersedes D-102): the class is real (a suite near the budget) but its only measured instance now fits. Their wef1 lane filed the remedy as `/opt/web-ecommerce-factory/docs/reference/upstream-proposals/2026-09-04-diff-scoped-pytest-leg.md` (their repo, absolute on purpose — not a hub path): a DIFF-SCOPED pytest leg that fits a fixed budget where a whole suite cannot. Disposition (infra, 2026-09-05): PLAN work — a new mechanism on a synced gate — designed together with (b) below; raising the timeout fleet-wide is REJECTED (the margin returns as suites grow). Until it lands, the CLAUDE.md clause says: arm where the suite fits the budget, otherwise a ledger decision per repo.

**Path to measurement (the revisit's recommendation):** (a) triage + clear the ~25 on a CLEAN worktree
(distinguish stale-test → update the contract, real-bug → fix, sibling-WIP → ignore); (b) add a marker that
runs a FAST curated subset at the gate (seconds, network/integration tests excluded), NOT the 80-min full
suite; (c) OR a scheduled nightly full run that alerts on new failures (the ci-health-probe pattern) without
gating interactive work. Same reasoning for `iterative_image_editor` (separate repo — its owner adds its marker).
Do NOT flip the marker until (a) is done. Blocked by: a quiet-tree window for the triage + the subset design.

## [infra] Gate pytest leg — project-declared environment/command (transdoc 01M171R8, 2026-08-29)

The gate now runs the suite under the RIGHT interpreter (the ruff-coupling fix, cmd-29 audit turn) and
names an exit-4 refusal distinctly (`pytest (SUITE REFUSED — usage error)`), but a project whose suite
NEEDS environment (`TEST_DATABASE_URL`) still cannot pass the leg — transdoc's conftest deliberately
refuses rather than skip-to-green. Their ranked ask: honour a project-declared env/command (e.g.
`.fabrik/pytest-env` or `[tool.fabrik.gate]`) so such repos supply what their suite needs instead of
carrying a permanent named red. **Measured need: 1 repo** (transdoc; every other marker-armed repo
passes env-free) — below the build threshold; revisit when a second repo hits it or transdoc asks
again. Blocked by: nothing — deliberately deferred at n=1.

## [infra] governance-sync as pre-commit is the widest concurrent-writer window (2026-08-29)

Two sessions hit "files were modified by this hook" aborts in one day (infra cmd-26 retries; intel
01M178GME0 twice + a justified SKIP on daf984f5). Measured: the sync writes NOTHING inside
/opt/fabrik (hub excluded from discovery, write-site audit clean) — the abort is pre-commit's
tree-delta detection catching a CONCURRENT writer during the slowest hook's ~30s×47-repo window
(evidence: .windsurf/rules/ai mtimes regenerating from a live session mid-window). Root
contributors: (1) the `.windsurf/rules/ai/**` renders lost their committer at the Phase-D cutover
(autocommit_pipeline_outputs.sh removed them deliberately — the ai-model-catalog ENGINE owns
publishing now, and its commit half is intel's to wire); (2) structurally, distribution does not
need to GATE the commit — a post-commit sync would eliminate the window class entirely. DECIDED +
SHIPPED same day (operator sign-off 2026-08-29): governance-sync is now a POST-COMMIT hook —
`scripts/governance_sync_postcommit.sh`, always_run + re-applying the config's own `files:` regex
against HEAD (measured first: post-commit passes NO file list, so a naive stage move silently
disables the sync). It can no longer abort a commit and has no stash window; a sync failure prints
loudly with the manual re-run command. Residual: the `.windsurf/rules/ai/**` renders' missing
committer stays intel's engine-side item.

## [infra] kaizen coroner books headless claude -p workers as died-silent sessions (2026-08-30)

The digest's first compose flagged hole_count 10→105→116→336; re-derivation by project matched 336
exactly and named the driver: 315 of 336 are HEADLESS `claude -p` sessions from the rivals driver's
neutral-cwd invocations (youtube 149, fabrik-lib 117, -tmp 49) — by-design one-shots that never
emit stop_pass, booked by kaizen_coroner.holes() as silent deaths. Fix direction: the coroner
classifies known-headless session shapes (neutral-cwd project names, -p transcripts) as their own
class instead of holes — the metric then measures what it names. Also noted: stop_block_causes
unpushed=970 dwarfs all others; partly the push law working, partly tonight's transient
github DNS/SSH resets forcing retry loops — watch, don't build.

## [infra] Audit the check set for staged-only scoping (transdoc 01M17VA9's meta-question, 2026-08-30)

check_doc_index's tracked-only enumeration gave the run that CREATES a doc a false green (fixed:
untracked docs under the INDEX-governed tree now count as live). transdoc explicitly flagged the
class question — how many OTHER gate checks enumerate via `git ls-files`/staged-only scope and
therefore cannot fire on the run that owes the obligation — as a hub measurement. Sweep
scripts/enforcement/ for `ls-files`/`diff --cached`-scoped denominators and judge each: some are
deliberate (sibling-WIP protection, the review-coverage '??' carve-out), some are this defect.
Next window; measure before changing any.

## [infra] Canary-completeness debt: 10 registered checks lack CANARIES pairs (2026-08-30)

test_gate_check_canaries' two completeness tests are red (part of the accepted-queued suite reds):
10 registered checks (check_certification_coverage, check_command_corpus, check_feedback_duty,
check_frozen_chain, check_pack_reachability, check_plan_lock_release, check_rivals_dossier,
check_spec_convergence, check_trigger_routing, check_vendored_drift) have neither a canary pair
in liveness_audit.CANARIES nor a recorded UNREACHABLE/warn_only reason. Accumulated across
sessions as checks landed without their canaries; none added today. Each needs a deliberately-bad
fixture proven to trip its check — real authoring work per check, not a fixture tweak. Author in
batches at the next enforcement window; the two tests are the ledger of what remains.

## [infra] check_changelog verifies existence, not correspondence (found by /fabrik-review 2026-08-30)

`scripts/enforcement/check_changelog.py` only requires that *some* `###` entry exist under
`## [Unreleased]` when `CHANGELOG.md` is staged — it never checks the entry's content against the
staged file list, so two real code fixes (the Stop-hook regex, the decisions.py duplicate check)
initially landed with zero CHANGELOG mention while the gate read green (piggybacking on unrelated
doc entries in the same commit; caught by a review finder, fixed by hand). A correspondence check
(staged code paths ↔ entry text) is buildable but is a new mechanism — per the rollout law, measure
the miss rate first: if reviews keep catching this class, promote; if this was a one-off, don't
build wallpaper. Trigger: the next occurrence of a code change landing entry-less.

## [fleet] .fabrik/state/<id>.json has no durable record of registrar FAILURES (review finding 2026-09-01)

The 01M1CKEK fix makes `fabrik apply`/`redeploy --refresh-infra` exit 2 and print each failed
registrar — but that truth lives only in the one terminal's stdout+exit code. The persisted
state file's 8-field G-F3 schema records `registrars_applied` by omission only; `fabrik
audit-registrars` and the state file both answer "did our last apply finish clean?" with
silence. Fix direction: a `registrar_failures: [...]` field (schema addition — G-F3 consumers:
`state.py` docstring names them) written by `_persist_state`. Deliberately NOT folded into the
01M1CKEK change: a schema change deserves its own consumer sweep. Trigger: the next state-file
or audit-registrars window.

## [infra] tests/orchestrator/test_infrastructure.py's dispatch tests SSH to PROD (measured 2026-08-31)

`TestProvisionDispatch` calls `provision()` with only the per-registrar drivers patched —
`_provision_shared_analytics` and `_provision_watchdog` run REAL: observed live as pytest child
processes `ssh vps sudo docker build -t fabrik/watchdog:my-project` and `ssh vps mkdir -p
/tmp/fabrik-watchdog-build` during a plain local test run, and the box carries a
`fabrik/watchdog:my-project` image built 5 HOURS EARLIER by a previous unnoticed run (leftover;
junk image, removable). A unit suite that mutates the shared VPS on every run is both a prod
hazard and why the suite takes minutes. Fix direction: an autouse fixture (or conftest guard)
that patches `fabrik.drivers.ssh.ssh`/`scp_to_vps` to raise in tests unless a marker opts in —
which also converts the two unpatched provisioning paths into loud failures instead of silent
prod writes. My new `test_registrar_failures_not_green.py` patches both explicitly.
Trigger: next test-infra window; the guard is one conftest fixture.

## [infra] Concurrent pre-commit stash windows DELETED 15 dirty files from the shared tree (live 2026-08-31, recovered)

The daily pipeline's auto-commit (a216a4c2, VPS-docs updater, 19:30 UTC) triggered THREE pre-commit
stash processes within 2 seconds (`~/.cache/pre-commit/patch1788204608-32641`, `patch1788204610-32730`,
`patch1788204610-32863` — preserved in the session scratchpad). The earliest patch records the true
WIP (15 files `M`); the two later ones record the same files as `deleted file mode` — the deletion
happened INSIDE the first hook window, and the last stash-restore faithfully restored the broken
state. Result: 15 tracked dirty files (two sessions' WIP incl. `docs/DECISIONS.md` and
`scripts/final_gate.py`) vanished from the working tree with no process left to restore them.
Recovered same-hour by hand: `git checkout -- <15 paths>` + `git apply` of the earliest patch
(excluding the one survivor file) + the later patch's DECISIONS.md hunk; verified against the
session-start status snapshot, tests green. CLASS: concurrent `pre-commit` runs share one working
tree and one stash namespace; their checkout/apply interleaving is destructive — the same class as
the documented pre-commit-stash near-misses, now with a measured data-loss occurrence. Fix
direction (measure first): serialize hook runs with a repo-scoped lock (flock in a pre-commit
local hook or wrapping the pipeline's commit path), and/or make the pipeline's auto-commit refuse
to run while the tree carries foreign dirty files. Trigger for promotion: this row IS the second
occurrence class-wide — a third means build it without further debate.

## [infra] assemble_commands.render() silently defaults agents_dest to the LIVE ~/.claude/agents (found by a review finder 2026-08-31)

`render(dest)` with `agents_dest=None` resolves to the live installed agents dir
(assemble_commands.py:31,~706) — only the CLI `--check` path passes a temp dir. A read-only review
finder doing `import assemble_commands; render(tmpdir)` for inspection silently OVERWROTE the 4 live
agent files (benign that day — sources unchanged, post-hoc byte-match to a fresh render — but there
was no pre-call snapshot to prove it). Fix direction: `render()` requires an explicit `agents_dest`,
or the agents writer (`_compose_agents` + `_write_agents` since 2026-09-10 — `_emit_agents` was split; composing before any write already refuses a defective source) refuses/warns when overwriting a file its own `agent_drift` check would call
HAND-EDITED. Out of plan-1's File Scope (the renderer is not a source/fragment); parked per the
rollout law — the trigger for promotion is a second live mutation.
**PROMOTED + FIXED 2026-08-31:** the second live mutation was measured the same day (T02's verifier's
`--dest` probe); `render()` now derives `agents_dest` from dest (live AGENTS only when dest == OUT,
else `dest/_agents`), red-first proven with 2 regression tests (tests/test_assemble_agents_dest.py).

## [infra] command_run.py `done` never reads round content — the found:0/new:0 conventions are honour-bound at close (found by T02's verifier, 2026-08-31)

`_close()` checks name/state/artifact-existence (6 named commands)/feedback substance — never the last
round's `findings`. A `/design-review` (or any round-convention command) can close `done` after a
`findings: 5` round. Enforcement candidate under the rollout law — but NOT a naive `findings != 0`
refusal: the sanctioned `new: 0` exit legitimately closes with `found > 0` standing rows (the exact
fabrik-review-vs-check_convergence tension T22 of the manifesto pass adjudicates). Design the check
AFTER T22 settles which exit vocabulary is canonical; promotion trigger = T22's ruling + one measured
false close. **T22 RULED 2026-08-31 (D-048): the quiet `found: 0 · fixed: 0` exit is canonical —
re-raises of adjudicated standing rows are cited, never counted — so a naive `findings != 0` refusal
is now designable; remaining trigger = one measured false close.**

## [infra] release_cut.py stages only CHANGELOG.md — a same-commit DECISIONS.md cut-row is impossible; the versioning-adoption carve-out itself has no ledger row (found by T20's verifier, 2026-08-31)

`release_cut.py:149,162` hardcodes `git add -- CHANGELOG.md` / `git commit -- CHANGELOG.md`, so the
manifesto-pass mint law ("built X at vY" → its `docs/DECISIONS.md` row) cannot ride the cut commit —
`/fabrik-release` now instructs an ADJACENT commit in the same push and says why (the honest recipe,
not the preferred one). Fix direction when promoted: `release_cut.py` stages `docs/DECISIONS.md` when
modified (or gains `--extra-path`), restoring same-COMMIT atomicity. Related provenance gap the same
verifier measured: the "versioning adoption" carve-out the command description cites ("the one
sanctioned publish-shaped act") has ZERO hits in `docs/DECISIONS.md` — the standing policy lives only
in prose; mint its provenance row when the operator confirms. Out of plan-1's File Scope (scripts/).
Promotion trigger: the first cut that actually mints a row (proves the two-commit shape in anger).

## [infra] No fixture test asserts the corpus's own quoted exit strings parse under the graders (found by the fresh corpus review's native finder, 2026-08-31)

The finding-2 class (a completion sentence naming a ledger shape `check_convergence.py`/
`check_review_coverage.py` reject) was only findable by hand-running the graders on a constructed
fixture — prose and grader can drift with zero mechanical signal. Candidate: a ~10-line test that
extracts the exit-row examples quoted in `commands/_sources`/`_fragments` and asserts they parse
under `_pass_counters` + QUIET_PASS. Measure-first per the fix directive: one confirmed occurrence
so far (the `found: 0 · new: 0` two-token QUIET sentence, fixed 2026-08-31); promote if the class
recurs. Trigger: the next prose-vs-grader mismatch found by any review.

## [infra] Two dead fragments: grounding-research + grounding-rules-cite (0 consumers, 0 renderer refs — found by the fresh corpus review round 5, 2026-08-31)

`grep -l "{{include:<name>}}" commands/_sources/*.md` returns 0 for both, and `assemble_commands.py`
names neither (unlike `close-feedback`/`agent-feedback`, which are auto-appended). Either dead files
to delete in a maintenance pass, or a second injection path nobody documented — decide, then either
delete or document. Pre-existing (not touched by the manifesto-pass diff).

## [infra] check_command_corpus.py never grounds scaffold-type enumerations against SCAFFOLD_TYPES (found by the fresh corpus review round 12, 2026-08-31)

`office-extension` (registry since D-039) was absent from all 57 corpus files while the checker
printed green — it validates chain targets/scripts/trailers but not type enumerations. Measured
fire rate at promotion time: 7 files enumerated ≥3 registry types with ≥1 omitted (all fixed
in-round; the checker would have been red on real drift, green after). Fix direction: import
SCAFFOLD_TYPES, fail when a corpus file enumerates ≥3 registry types yet omits one. Promote on the
next registry-drift recurrence.

## [infra] Mailbox-clear 2026-08-31 — accepted-direction majors (each cites its finding mail)

- **final_gate --json honesty cluster** (01M19R99M, 01M1CAE2F4): `degraded:[...]` key for
  NOT-INSTALLED tools; `passed` as a list of check names; a status-level warning when the diff adds
  N test files and the gate ran none; tolerate DECLARED opt-in skips in the skip-advisory.
- **WATCH: wef arms `.fabrik/run-pytest` when two lanes go green** (01M1CW5P): their intake lane
  committed to arming the sentinel same-day once the section-registry 29 + content-lane 7 test
  failures are fixed by their owners. Conditional offer, tracked nowhere until this line — if a
  future wef status shows both groups green and no sentinel, this is the thread to pull.
- **Fleet-check design law: import-and-call, never source-grep** (01M1CWKE, wef's glitchtip-PII fix):
  a source grep passes on a commented-out flag, a dead branch, or a shadowed kwarg — their test
  captures the ACTUAL kwargs reaching sentry_sdk.init. Binding on any future fleet-wide config
  sweep check (PII flags, security kwargs); recorded here so the advice outlives the ack.
- **Stop-hook resumed-session false positive** (01M19970HP): `final_gate_stop.py:573-580,1228-1229`
  re-fires "UNREVIEWED SPONTANEOUS WORK" after a record closed — scope the authored set to
  uncommitted∩dirty, or let a closed review-family record satisfy has_any_record.
- **transdoc post-mortem corpus candidates** (01M19YFM2F): walking-skeleton mandate, seam-test
  floor (generated OpenAPI client only), core-journey certification at phase boundaries, MVP tier
  in FEATURES EARLY — four dispositions, each a design change; take as one corpus pass.
- **READ-budget waiver for narrow edits to a pre-existing monolith** (01M1A6SSEY — youtube is
  mechanically BLOCKED on this): line-range Touches syntax or a gate-recognized waiver line.
  PRIORITY: a live plan cannot flip.
- **check_review_coverage formatting-fix ratchet** (01M1CA0WJ3): a parser-visible formatting repair
  to a COMMITTED review escalates advisory→hard gate; exempt edits whose parsed counter rows are
  value-identical before/after.
- ~~**Synced per-repo DECISIONS duplicate-id gate check**~~ ✅ **LANDED 2026-09-01** (01M1CBJWQS →
  D-057 sequencing → wef repair 5a58c11 + reply 01M1CW4S = the trigger → `check_decisions_unique.py`,
  WARN-tier, keyed on the row ID CELL per wef's repair-experience request, 0/49 fleet ledgers firing
  at landing — verify: `for f in /opt/*/docs/DECISIONS.md; do grep -oE "^\| D-[0-9]+ \|" "$f" | sort | uniq -c | awk '$1>1'; done`). Remaining half deliberately unbuilt: the origin/HEAD stale-max WARN needs a fetch —
  revisit only if collisions recur despite detection + pull-before-mint. wef's generalization
  learning recorded in the check docstring: BOTH-CITED is the common case; first-committed carries
  the tiebreak.
- **mcp-config-changed hook precision** (01M1BXBRKM): name WHICH servers changed / suppress when
  the repo-assigned set is unaffected (false-fired on wef3 AND on this session today). ALSO
  (operator, 2026-09-01: "i restarted all windows why does you and all agents keep saying"): the
  warning re-fires on EVERY prompt of a resumed conversation — a window restart cannot clear it
  (resumed conversations keep the old tool universe by design; only a NEW conversation gets the
  new roster). Add told-once suppression per session, and say "start a NEW chat" not "reload".
- **tech-stack guide engine-neutral ecommerce row** (01M19G0HM0 + correction 01M19G66X8): replace
  the Vendure default with the choice criterion (copyleft tolerance, payment-provider availability);
  point iyzico-reaching projects at fabrik-lib payments/ first.
- **release HANDOFF closed-by overlay** (01M1A00DS1): an appendable `closed-by <commit/test>` line
  in the grammar so closure doesn't require editing a ratcheted report.
- **waitForHydration adoption** (01M1B0BHZN): replace the hand-rolled networkidle+waitFor pattern
  in the certification fragment with fabrik-lib's `@fabrik/ui-verify` primitive.
- **deploy triad remainder from the consolidated v3** (01M1C95A2S): infra-wiring FLOOR (name the 10
  registrars), supersede step-diff, rollback-on-failure semantics, cumulative window expiry, S0
  credential write-time verification, citation-precision check. (F11 quoting + F12 redaction +
  F14 amend-trailer + cold-start + capability-check are DONE.)
- **[fleet] subagents fleet re-vendor sweep** (01M1B35GKQ): NVIDIA_API_KEY dotenv fix + lane_chain
  landed upstream; every vendored copy behind.
- **[intel→fabrik-lib] fanout resilience** (01M1CGKVWC): pre-flight credits check, 402/404 unit
  re-route to next ranked model, dead-unit count surfaced in the return. OPERATOR: OpenRouter
  credits tail is SPENT — top-up needed.
- **I1 watch item** (01M1CCNMGT): auto-mode permission-classifier outages (31× in one project) are
  indistinguishable from agent stalls — harness-level; watch for recurrence post-CLI-updates —
  and it fired AGAIN on this very session while this row was being written.
- **[infra] fabrik-researcher brief + grounding fragment drift** (2026-09-02, 10 dispatches, 10/10
  reported it): the agent has NO shell, so a brief that says "run `awk …`" is unexecutable (each agent
  substituted Grep+Read; the dispatch template should give a Read/Grep recipe); the fragment's claim that
  non-HTML (JSON) content is unreachable via exa was refuted twice in one day (api.bls.gov and
  api.cerebras.ai JSON fetched raw); WebFetch does not follow cross-host redirects (api.slack.com →
  docs.slack.dev, cloud.google.com → docs.cloud.google.com cost a full extra round each) and truncates
  long pages silently then asserts a NEGATIVE ("no Outlook section") — WebFetch output must be treated as
  bounded-search evidence, never as a negative. Fix in `commands/_sources/_fragments/` at next touch.
- **[infra] check_subagent_flywheel: on shared master the cycle boundary is HEAD** (2026-09-02, /fabrik-review):
  the check counts local-ledger pool rows newer than `merge-base HEAD <ref>`, which on a shared master
  with no branch is HEAD itself — so a SIBLING's commit at 13:34 made this session's four pool review
  rows from 13:19 "not this cycle" and the gate BLOCKED a run that had used the pool minutes earlier.
  Measured once; the fix candidates (key the window on the staged files' oldest mtime, or on the last
  commit AUTHORED by this session) need a fire-rate measurement before shipping (FIX verb 5). Until
  then a later-pass pool dispatch re-satisfies it.

## [infra] fabrik-review finder brief: pin the ledger high-water mark AND finder imports to a sha (found by the external-services review pass 9, 2026-09-02)

The pass-9 Opus finder, briefed on commit `fae20651` with reads pinned to `git show <sha>:<path>`,
still `sys.path.insert(0, "/opt/fabrik/scripts")`-imported the LIVE modules for its measurement
scripts — and the live tree carried a sibling's uncommitted `is_credential` edit for ~20 min of the
run, so three measurements reported on the wrong code (caught by `inspect.getsource()` vs the diff).
The same brief named the standing-row scope as letters ("P…AF, AG1") while the worktree ledger
already held AH1/AH2, so a pass was spent re-deriving a fixed row. Two edits to the finder brief in
`commands/_sources/fabrik-review.md` (+ the finder fragment): (1) "measure by extracting the pinned
sha to a sandbox and asserting the loaded module's provenance — never import from the live tree on a
shared master"; (2) "state the ledger's high-water mark as the review file's sha/timestamp at
dispatch". Not applied mid-run: a corpus edit renders box-wide and needs its own scoped review.
Related: [[feedback_test_real_invariant_not_proxy]] (this session's own flip-set measurement was
vacuous for the same reason — a temp-loaded module found no catalog — until the paths were pinned).

---

## [infra] Hub `docs/FEATURES.md` documents 9 of the 33 rendered commands as features (2026-09-02, owner: infra)

Measured by the `/fabrik-features` REFRESH after plan 2026-09-01-plan-1: `grep -c "/<command>\b" docs/FEATURES.md`
over the 33 rendered `~/.claude/commands/*.md` → 7 covered before that run, 9 after it (the new Deployment Verification
section names `/fabrik-deploy-checklist` and `/fabrik-features`); 24 commands appear in no feature section (the
`/fabrik-spec → … → /fabrik-service-test` pipeline, `/fabrik-execute-plan`, `/fabrik-rivals`, `/fabrik-docs-review`, …);
the covered set is the deploy family, `/fabrik-review`, `/fabrik-release`, `/fabrik-upstream` plus those two.
The file is shaped as narrative feature sections (Status/Audience/Since + Headline + What/How/Technical), not a
per-command registry, and its "9-Step Workflow" section still describes the retired Traycer-era flow. Deferred, not
absent: a "Command pipeline" feature section grounded per command (the corpus is infra's beat; `capabilities.json`
already enumerates the surface — `docs/CAPABILITIES.md` is the machine index, `FEATURES.md` the customer-facing claim).
Trigger: the next hub `/fabrik-features` REFRESH that is not scoped to a single plan.

## [infra] No executable check grades the parity contract's `FROZEN` header (2026-09-02, owner: infra)

Plan `2026-09-01-plan-1-deployment-verification` (D-082) shipped `scripts/verify_prod_parity.py` with a
machine-readable `# Status: DRAFT | FROZEN · Version · Date · Mode` header. Two commands bind on it:
`/fabrik-release`'s VPS path BLOCKS on `DRAFT` and `/fabrik-deploy-verify` caps its verdict at `UNVERIFIED`
without `FROZEN`. **Both bind on honour** — `check_stage_artifacts.py` grades only the data-contract,
ui-design and flows `FROZEN` flips (three graded artifacts at `check_stage_artifacts.py:319-332`). The header grammar is settled (`parse_header()` in the seeded script is the parser),
so the extension is mechanical: a `stage_artifacts` row that reads the project's `scripts/verify_prod_parity.py
--header` and fails a release-shaped change (a `specs/services/*.yaml`, compose or migration edit) whose
contract is still `DRAFT` or whose `Version` predates the edit. Trigger to build it: the first project that
freezes a contract (`/fabrik-deploy-checklist` Mode B on tryton-crm is the planned first run). Deliberately
deferred, not forgotten — recorded in the plan's Phase B step 6 and in `docs/reference/deployment-verification.md`.

## [infra] fabrik-mail relay has no liveness guarantee and no sender-visible failure signal (peer report from the seo session, 2026-09-02)

Reported session-to-session on purpose (a mailed finding would join the queue): the shared hub
`fabrik` inbox stood at 81 unread (oldest 2026-09-01 00:40) and grew 73→81 in an hour while three hub
sessions ran long reviews; an ack-required finding (`01M1GZ3MFPEXZCJE4BYRQMBJ35`, web-ecommerce-factory
→ seo via the hub) was dropped in BOTH directions for ~6 h and the seo side only learned its own mail
was unread by stat-ing the hub's inbox directory. Two halves: (1) drain — the handle-now duty applies,
and the review-bound sessions did not claim the box for a day; (2) design — a sender cannot tell
"queued" from "dropped": the relay needs a liveness surface (inbox age/depth in `liveness_audit.py`)
and a sender-visible signal (an `unread-for` line on `mail.py list`, or an auto-nack after N hours on
`ack: required`). Beat: infra (fabrik-mail).

## [infra] fabrik-review finder brief: helpers go in the finder's OWN sandbox dir, never the shared scratchpad root (2026-09-02)

The pass-11 Opus finder wrote a measurement helper named `h11.py` into this session's scratchpad
root; the pool helper lives there too, so its own directory — first on `sys.path` — shadowed the real
`h11` and two full pool dispatches errored in every unit (`module 'h11' has no attribute 'Request'`)
and recorded nothing. Add to the finder fragment: "write every helper under your sandbox extract
directory; never the dispatcher's scratchpad root; never a name that collides with a package".
Also keep the brief's `rm -f $D/scripts/verify_prod_parity.py`: `git archive` extracts the symlink
DANGLING (verified `tar -tv` + `test -L`, pass 13) — a pass-12 finder's claim that it is not extracted
was wrong and briefly propagated here.

## [infra] `libs/alerting` Telegram fallback sends legacy Markdown without escaping (2026-09-02, owner: infra)

`libs/alerting/telegram.py` sends `*{title}*\n{body}` with `parse_mode: "Markdown"` and its own error map names
bad Markdown as a 400. An alert whose title or body carries an unbalanced `*` or `_` (a step label such as
`gather_envs_reconsolidate`, a log path, a glob) is REJECTED on exactly the fallback leg that fires when the
primary SSH→apprise leg is down — the operator gets nothing. The external-services chain's own body was made
parity-safe in review pass 25 (CC5), but the label and the log path still carry underscores and every other
caller is exposed. Fix at the root: escape the four legacy-Markdown metacharacters in `telegram.py` (or drop
`parse_mode`), with a grader that sends a title containing `a_b*c` through the formatter. Measured 2026-09-02:
the chain body had 1 `*` and 11 `_` before CC5; the alerting docstring's `body: up to ~500 chars` was exceeded (896).
## [fleet] ✅ RESOLVED 2026-09-03 (D-108) — `fabrik apply` and `fabrik plan`/`destroy` disagreed on the watchdog default

Mail 01M1G851DWCX35T5NSQXADQW0H, validated at `path:line` this run. `resolve_applicability` reads RAW
yaml on the apply path and falls back to `True` (`infrastructure.py`, the `watchdog_cfg.get("enabled", True)` gate in `resolve_applicability` — line numbers in that file shifted when the corrective comment landed, so it is cited by SYMBOL), while `WatchdogConfig.enabled`
defaults to `False` (`spec_loader.py:428`) and `fabrik plan` (`cli.py:360`), `audit.py:87`, `dev_tools.py:121`
and the DESTROYER (`destroyer.py:532`) all arrive through `model_dump()`. So a spec that omits the block gets
a sidecar provisioned and reported "not applicable" — and the teardown replay is on the not-applicable side,
so apply can create a sidecar destroy will not remove. **Measured: 34 of 72 `specs/services/*.yaml` omit the
block**, and a test pins the model default (`test_spec_loader.py:454`). A third intent exists and is
unimplemented: `spec_loader.py:414/:417` cite a `_register_watchdog` dispatcher computing True for
service|worker|wordpress and False for static — no such dispatcher exists.

The false comment that hid this (the watchdog gate's own comment, "WatchdogConfig.enabled defaults to True") is
FIXED this run, along with the module docstring; it had already propagated into
`docs/infrastructure/vps-ai-sysadmin.md`, which infra has since corrected.

RESOLUTION: the operator chose (a) — the MODEL default is now True (`spec_loader.py`), matching the apply
path. No provisioning changed, because apply already behaved this way; `fabrik plan`, `audit` and the
destroyer now report what was actually created, so the teardown gap is closed. Both pinned tests flipped
with the reason inline, and the P2 sub-plan's original `False` is explicitly superseded (nine of its ten
watchdog defaults still hold). Rejected at the same time: (b) apply → False, which would have taken the
sidecar away from 34 projects on their next apply and orphaned the existing containers; (c) the documented
default-by-kind dispatcher, which was never built — still open as a follow-up if the kind matrix is ever
worth encoding, and it is the only remaining reason to touch this field again.

## [fleet] Fleet capability claims in `agents-fabrik.md` were written from intent, never probed — pgvector was false for months (2026-09-03, owner: operator decision + fleet)

Mail 01M1EHNXT4829615ZARZF9WJP7 (infra, rules pass), each item re-probed by fleet this run rather than
taken on report:

- **pgvector — FIXED in the map this run.** `postgres-main` is `postgres:16-alpine` and
  `pg_available_extensions` AND `pg_extension` both have **0** rows for `vector` — neither installed nor installable on this image, re-probed by fleet 2026-09-03. The map claimed `pgvector/pgvector:pg16`,
  "✅ fully self-hosted". `fabrik-lib/rag` is real; the fleet DB cannot run it. **Operator decision owed:**
  move postgres-main to the pgvector image (restarts the shared DB, so it wants a window) or record that
  vector search is not a fleet capability today.
- **redis-main is `redis:7-alpine`** (probed). Redis 7.x is security-only; 8.x is current. No urgency
  claimed — a scheduled major upgrade of the shared cache, or a deliberate "stay on 7 until X" row.
- **Scaffold Dockerfile literals** (`scaffold.py`, `python:3.12-slim-bookworm` ×4): bookworm regular
  security ended 2026-07-12 and D-064 flipped the fleet to trixie. The rule packs are marker-spanned
  against `versions.yaml`; the scaffold's literals are hardcoded and drift silently. Same class as the
  docusaurus scaffold row below — both want the scaffold reading `versions.yaml`, not literals.

SYSTEMIC (infra's framing, adopted): capability claims in infra docs rot exactly like version literals in
rule packs. The rules corpus has `CLAIMS.yaml` (dated assertions, re-verified on a window); the RUNNING
FLEET has no equivalent. A probe-backed claims register for fleet state is the class fix.

## [fleet] The docusaurus scaffold emits the runtime its own rule pack bans (2026-09-03, owner: fleet)

Mail 01M1G4PYGTQQGMXKK91VDKZGQJ. `templates/docusaurus/Dockerfile.j2` ends in `node:22-bookworm-slim`
running `npm run serve`; `core/42-docusaurus.md` bans a Node runtime in production and prescribes a
two-stage build ending in `nginx:mainline-<codename>` serving `build/`. Three divergences: the Node
runtime (RAM on a shared VPS to serve static files), NO Pagefind anywhere (`grep -rn pagefind
templates/docusaurus/ src/fabrik/scaffold.py` → nothing, so the pack's § Search is unreachable in every
scaffolded site), and hardcoded `node:22` + `bookworm` against `versions.yaml`'s node_lts 24 / trixie
(D-064). Sized as a scaffold change with a rendered-output grader, not a right-now edit: it rewrites the
emitted image, adds a build step, and every existing docusaurus project's next redeploy inherits it.

## [fleet] Scaffolded `pause_state.py` fails OPEN with no counter and no log line (2026-09-03, owner: fleet)

Mail 01M1GGBFSHSNBRDH961QYZ1XQK. `templates/scaffold/python/pause_state.py:50-60` returns None on any
Redis exception and every caller swallows it (`:84`, `:105`, `:117`), so when redis-main is unreachable
every pause flag reads "not paused", the workers un-pause, and nothing records that it happened. Fail-open
is the right POSTURE for a guard that optimises — the finding's own point is that the posture must be
DECLARED and COUNTED, not silent (`58-resilience` now requires exactly that). Fix shape: one counter +
one WARN log at the degrade point, and the docstring naming the posture. Emitted into every python-api and
file-worker project, so it ships through the scaffolder with a regression test.

## [fleet] `is_admin_dashboard` gates the whole DOMAIN, so a saas-skeleton cannot have both an admin surface and customers (2026-09-03, owner: fleet)

Mail 01M1HJ0S4FMJ1A9RT8N9E4Z7PT (youtube). `shape.is_admin_dashboard: true` attaches
`authelia-forward@docker` to the Traefik ROUTER, gating every path on the domain, not `/admin`. The
project hit it because `project.yaml::type` was corrected (D-001) while `specs/services/<id>.yaml::shape`
kept the old template's value — two independent statements of the same fact with no consistency check.
Three fixes, ranked by the sender: (1) emit a PATH-SCOPED second router for the admin prefix; (2) refuse
the combination at `fabrik apply` for types that serve public routes; (3) cheapest and worth doing
regardless — a check that `shape` agrees with `project.yaml::type` after a type change. (3) is a gate
addition on my beat and the natural first step; (1) changes the Authelia registrar's emitted labels for
every affected project and wants a plan.

## [fleet] Promtail is END-OF-LIFE (2026-03-02) and the fleet still ships logs with it (2026-09-03, owner: fleet + operator window)

Mail 01M1EQ3NCA98EF178ZY366V47T. Grafana declared Promtail EOL on 2026-03-02 — no updates, no security
fixes — and `configs/monitoring-compose.yaml:30` runs `grafana/promtail:3.4.2`. The successor is Grafana
Alloy, and `alloy convert` takes the existing config, so the migration is mechanical; it is a live
monitoring-stack change on vps1, so it wants a window and a rollback (keep the promtail service defined
and stopped until Alloy is proven shipping). Second item in the same mail, smaller and independent:
`templates/node-api/defaults.yaml:14` sets `exposes_metrics: true` while no Node metrics module is
scaffolded anywhere (`grep -rn "prom-client\|metrics.js" src/fabrik/ templates/` → nothing), so every
scaffolded node-api registers a Prometheus target that can never be scraped — flip the default to false
or scaffold a metrics module; the flag is spec-canonical, so whichever is chosen must match the code.

SYSTEMIC (sender's, adopted): nothing on the box watches upstream component lifecycles. The rules corpus
has `CLAIMS.yaml`; the running fleet needs the same shape — see the capability-claims row above.

## [fleet] Every hub edit to a VPS-EXECUTED script has been inert since 2026-08-30 — the sync is manual and nobody is obliged to run it (2026-09-05, owner: fleet)

Found by asking, during a combined review, whether a check I had just shipped actually RUNS where it must
run. It did not. `proactive-check.sh` executes on vps1 from `/opt/fabrik/scripts/sysadmin/` via
`/etc/cron.d/vps-sysadmin` (`*/15`), and **that tree is not a git repo** — files arrive only through
`scripts/sync-vps-sysadmin.sh`, run by hand. Measured 2026-09-05: the deployed `proactive-check.sh` was
dated **2026-08-30** and contained none of the day's changes; across `scripts/sysadmin/` the newest mtime
was the same date, with several files back to July. So anything ANY agent changed in a VPS-executed script
in the last six days has not been running — silently, because the hub copy looks correct and the gate is
green against the hub copy.

**Two live consequences already measured, both filed with this row rather than assumed:** a recurrence
check shipped that night executed nowhere at all until deployed by hand, and `detect_reversals.py` failed
every five minutes for ~5.5 days (1,597 logged failures in the current rotation) — that second one is
FIXED, its root being a non-executable file mode in the HUB copy that `rsync -a` faithfully reproduced.

**Why the obvious fix was NOT taken:** running `sync-vps-sysadmin.sh` pushes `scripts/sysadmin/`,
`scripts/audit/`, `docs/infrastructure/` and `specs/services/` wholesale, so invoking it while sibling
sessions have in-flight hub state would deploy their unfinished work to production. A blanket sync is the
wrong instrument on a shared tree with concurrent writers, which is exactly why it keeps not being run.

**Candidates, none built:** (a) make the deploy per-file and idempotent so it is safe to run at any moment;
(b) a staleness CHECK rather than a push — compare hub vs VPS md5 for the cron-invoked set and warn, which
is cheap, read-only, safe under concurrency, and would have caught this on day one; (c) put `/opt/fabrik`
on the VPS under git and pull a tag. (b) is the smallest honest step and does not require deciding (a) or
(c) first. Measure nothing before building (b) — a divergence check over 8 cron targets cannot be
wallpaper. Blocked by: an operator call on whether the box should pull instead of being pushed to.

## [fleet] `fabrik-zitadel`'s Prometheus target has been DOWN (404) — a registered scrape job that has never worked (2026-09-05, owner: fleet)

Found while validating a different finding: `fabrik-zitadel` scrapes
`https://auth.ocoron.com:443/debug/metrics` and reports `health=down`, `lastError: server returned HTTP
status 404 Not Found`. It is one of only two `fabrik-*` jobs; the other (`fabrik-tryton-crm`, an INTERNAL
`http://tryton-crm:8000/metrics` target) is up.

**Why it matters beyond one dashboard:** `proactive-check.sh` alerts on `max_over_time(up[10m])==0`, so a
permanently-down target is either firing `target_down` continuously or has already been tuned out — either
way the signal is worthless, and a monitoring job that has never once succeeded is indistinguishable from
one that just broke. This is the concrete instance of "a wrong scrape target is worse than no scrape
target", which is why the site-provisioner spec fixed the same day was given an internal target instead of
the default public one.

Likely cause, NOT yet confirmed (stated as a hypothesis, not a finding): the path. Zitadel's metrics path
is configurable and `/debug/metrics` may be wrong for the deployed version, or the endpoint may require
auth that the public edge refuses. Next step is to probe the container directly on the fabrik network the
way site-provisioner's was probed, then either correct `monitoring.metrics_path` or move it to an internal
target. Blocked by: nothing — this is a small, self-contained fix, it simply was not mine to make inside
another finding's scope.

## [fleet] A VENDORED file has no staleness detector — the glitchtip scrubber moved 9 times in one day and every gap was silent (2026-09-05, owner: fleet)

`templates/scaffold/python/glitchtip_init.py` is vendored from site-provisioner under the fabrik-lib
law (copy, never import). It was vendored three times TODAY — `4f5c158` → `13d3243` → `7f96834` — and
each re-vendor was triggered by a MAIL from the origin repo, never by anything on this side noticing.
Between the first two pins sat a redaction that "missed 68.8% of the shape it was built for" and a
logging channel `_scrub_event` cannot reach; between the second and third sat one that "leaked 100% of
the time". The hub shipped each of those to every new Python scaffold until a human wrote to us.

**The gap is structural, not attentional.** Nothing compares the vendored copy to its origin. The
docstring records the revision it claims to be, and the guard proves the file is internally consistent
and functionally correct — but a copy that is faithful to a SUPERSEDED revision passes every test we
have. Staleness is invisible by construction.

**Candidate, deliberately not built inside the ticket that found it:** an advisory check that reads the
`revision:` line from a vendored file's docstring, asks the origin repo how many commits that path has
moved since, and reports the count. Cheap (`git -C <origin> rev-list --count <rev>..HEAD -- <path>`),
read-only, and it cannot be wallpaper — it fires only when a vendored file is genuinely behind. Open
questions worth settling before building: where the origin/path pair is declared (the docstring already
carries both — parse it, or add a manifest?), whether it warns or fails, and whether it belongs in
`final_gate` (runs everywhere, needs the origin repo present) or in the daily pipeline (runs once,
where the origin repos definitely are). The daily pipeline looks right for exactly that reason.

**Scope note:** this is the general vendoring class, not one file. `libs/health_probe/` and every future
`VENDORED_DIRS` entry has the same hole. Blocked by: an operator call on warn-vs-fail and where it runs.

## [fleet] An ABSENT `shape:` flag is byte-identical to a deliberate `false`, so "code exposes X, spec never mentions X" is silent by construction (2026-09-05, owner: fleet)

Raised by site-provisioner (`01M1Q7RJ5ZWAP7BGFQE1EWJC6Z`) and validated here: their `/metrics` endpoint
is live and deliberately auth- and rate-limit-exempt, but the spec had no `exposes_metrics` line, so
`fabrik apply` skipped the Prometheus registrar and nothing scraped it. Confirmed live before fixing —
Prometheus carried 18 active jobs, none of them site-provisioner. The one spec is FIXED (2026-09-05);
this row is the CLASS, which that fix does not close.

**Why it is invisible:** every registrar gate reads `shape.get("<flag>", False)`
(`orchestrator/infrastructure.py:325` for prometheus, same shape for the others), so an omitted flag and
a considered `false` are the same bytes. Code and spec each look correct in isolation; only a
cross-reading finds the contradiction, and nothing does that cross-reading today.

**Measured, and stated as a population rather than a defect count:** of the **72** specs in
`specs/services/`, **28** carry no `exposes_metrics` line at all. That is how many COULD be wrong, not
how many ARE — each needs its code checked for a live `/metrics` route before it counts. The same
question applies independently to `needs_cache`, `has_search_feature`, `needs_database` and
`is_admin_dashboard`, so the real population is larger than 28.

**Candidate fix, deliberately NOT built yet:** a hub-side check that greps each project's routes for
flag-bearing surfaces (`/metrics`, a Redis client, a Meilisearch index) and WARNS when the corresponding
flag is absent. Before building it, measure the fire rate across those 28 — a detector that fires on
legitimate patterns is wallpaper, and wallpaper is how enforcement dies (FIX DIRECTIVE 5). Note the
cheaper half first: the checker only has to distinguish *absent* from *false*, which is a one-line
change to how specs are loaded, and might be better solved by making the flag REQUIRED in new specs than
by detecting its absence in old ones. Blocked by: the fire-rate measurement.

## [fleet] The VPS copy of `/opt/traefik/compose.yaml` is AHEAD of its hub repo-of-record — a hub-driven redeploy would drop the Cloudflare DNS-01 resolver (2026-09-05, owner: fleet)

Found while executing Part B of the memory-ceilings spec (D-124), by diffing each stack's hub copy against
the live VPS file rather than assuming they matched — `redis` and `monitoring` were byte-identical, traefik
was not. The VPS file carries three lines the hub copy lacks: an `env_file: ./cf.env` (the scoped
`CF_DNS_API_TOKEN`) and a `./acme-cloudflare.json:/acme-cloudflare.json` bind — the tenant-wildcard DNS-01
certresolver work. Part B deliberately did NOT reconcile it in either direction: the ceiling was inserted
into each copy independently so the drift survives untouched, because reconciling means choosing a
direction and one direction pulls a secrets-file reference into the hub. **The risk is concrete:** anyone
redeploying traefik from `infra/vps1/traefik/compose.yaml` drops the Cloudflare resolver, and `*.tojlo.com`
tenant certificates stop renewing. Decide the direction (hub adopts the VPS lines, with `cf.env` gitignored
and documented; or the VPS lines move into a documented override), then re-verify with a diff. Blocked by:
an operator ruling on where the Cloudflare credential reference should live.

**The GENERAL gap behind this instance, stated so it is not mistaken for a one-off:** nothing guards
`infra/vps1/**` against the live box. The Part-B grader reads the HUB copies only, and no enforcement check
references `infra/vps` for drift (`scripts/enforcement/` grep: only `check_env_contract.py`, for a different
purpose) — so the hub can be right and the box wrong, or drift again tomorrow, with a fully green suite.
Measured today: 1 of 3 stacks had drifted. That is a real rate, but a hub↔VPS compose differ is a NEW
mechanism and this row is not the place to build one on a sample of three — measure the rate across all
`infra/**` stacks first (there are ~14 on vps1 alone), then decide. Recorded rather than built.

## [fleet] `monitoring_grafana-data` carries no compose labels — it is the one monitoring volume Docker Compose did not create (2026-09-05, owner: fleet)

Surfaced by `docker compose up -d --dry-run` during Part B: *"volume monitoring_grafana-data already exists
but was not created by Docker Compose."* Confirmed by inspection — its four siblings
(`alertmanager-data`, `loki-data`, `prometheus-data`, `promtail-positions`) each carry
`com.docker.compose.project`/`.volume` labels; `grafana-data` has `map[]`. It holds 31 MB: the dashboards,
users and Grafana's SQLite DB. **No action was taken and none is urgent** — Compose reuses a same-named
volume and never deletes one on `up -d` (only `down -v` does, which is a standing HARD STOP), so the
recreate Part B enables is safe. It is filed because an unlabelled volume is invisible to any
ownership-based tooling we might later write, and because "dangling ≠ disposable" makes mislabelled data
worth knowing about BEFORE someone runs a cleanup. Candidate: declare it `external: true`, or recreate the
label — neither without an operator decision, since both touch a live data volume.

## [fleet] RESOLVED for memory (2026-09-05) — the unbounded containers on vps1; the redis-main EVICTION-POLICY half stays open (2026-09-03, owner: fleet + operator)

**RESOLVED 2026-09-05 (fleet), for the memory half only — D-122.** All ten remaining unbounded
containers now carry ceilings, applied in place on the operator's authorisation: **0 of 32 unbounded**,
every kernel cgroup verified carrying its value, `oom_kill 0`, and a 32-row before/after snapshot of
(name, id, StartedAt, status) diffed IDENTICAL — nothing recreated, nothing restarted. The count moved
15/37 → 10/32 when the operator removed the `ocoron-com` stack (D-121), not because five were fixed.
The recurrence check that makes this stick is `container_no_memory_limit` in `proactive-check.sh`
(every 15 min, `docker ps -aq` so a stopped-but-defined container still counts) plus
`scripts/vps_apply_limits.sh --check`. **Two things this row's own history teaches, worth keeping:**
the applier ALREADY EXISTED and named all ten containers — it had simply not been run since
2026-05-30, and re-running it unmodified would have lowered prometheus 1.5 GiB to 1g and mutated a
network renamed the day after it was last touched. A stale enforcer reads as coverage and is worse
than none. **Still open here:** the redis-main eviction policy (`allkeys-lru` can evict pause keys
that carry no TTL — the 640M ceiling is coupled to this, per the spec's open unknown 3), and
~~**Part B**~~ — **DONE 2026-09-05 (D-124)**: the ceilings are declared in all three stacks' compose (`infra/vps1/{traefik,redis,monitoring}/compose.yaml` + the VPS copies), verified with `docker compose config`, and a test now binds compose ↔ applier ↔ spec. No container was recreated; the recreate the declarations imply belongs to each stack's next deploy and cannot move a ceiling, since every declared value equals the live one.

**CORRECTED 2026-09-04 (fleet), and SUPERSEDED by a spec:** this row said "redis-main and traefik".
A live sweep of every container measured **15 of 37** with `HostConfig.Memory == 0` — also loki,
grafana, alertmanager, promtail, cadvisor, the three exporters, and all five `ocoron-com-*`. A 7x-low
count in a backlog row is a number that gets quoted. Also corrected: this row assumes setting the
limit "restarts both containers, so it is an operator window, and traefik restarting drops every
route briefly" — **that is wrong.** `docker update --memory` mutates the live cgroup in place, proven
by execution (same container id, same StartedAt, Running=true, `/sys/fs/cgroup/memory.max` updated).
No restart, no window, no dropped routes for the in-place path. Design:
`docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md`. The eviction-policy half
of this row (protecting pause keys) is NOT covered by that spec and remains open here.


Mail 01M1GQEJ14Z8TSH7KC4RVYDH0H, probed by infra 2026-09-02: `docker inspect --format {{.HostConfig.Memory}}`
returns 0 for redis-main and traefik; postgres-main 2048 MiB, meilisearch 512 MiB, zitadel 1024 MiB. Both
live in shared-infra compose stacks that `fabrik apply` never touches, so `deployer_ssh._validate_compose()`
— the invariant's only enforcement point — never sees them. Two parts: (a) set `deploy.resources.limits.memory`
on both, plus `maxmemory` and an eviction policy for redis-main that PROTECTS pause keys (a `volatile-*`
policy evicts only keys with a TTL; the pause flags must outlive pressure) — this restarts both containers,
so it is an operator window, and traefik restarting drops every route briefly; (b) the class fix: a periodic
`docker inspect` sweep over ALL containers so "every service has a limit" becomes checkable rather than
assumed.

## [fleet] 23 of 32 vps1 containers have NO CPU limit, and two bounded containers sit near their ceiling (2026-09-04, owner: fleet)

Measured live 2026-09-04 while specifying the memory-limit fix. `core/30-ops.md:186` mandates
`deploy.resources.limits.memory` **and `cpus`** together; the checklist treats them as one row. The
memory half is being closed by
`docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md`; the CPU half is not.
`docker inspect -f '{{.HostConfig.NanoCpus}}'` returns 0 for **23 of 32** containers (re-derived live 2026-09-05; was 28 of 37 before the `ocoron-com` removal, D-121). Deliberately
scoped OUT of that spec: an unbounded CPU degrades neighbours, while an unbounded memory ceiling
lets one container trigger a host-level OOM kill that takes an arbitrary subset of all 37 down —
different severity, different urgency. Whoever picks this up should reuse that spec's Part C check,
which already enumerates every defined container and would only need a second predicate.

**Watch item from the same sweep (bounded, but close):** `trytond-worker` at 315.5 MiB of its 512 MiB
limit (61.6%) and `glitchtip-web` at 242.7 MiB of 512 MiB (47.4%). The netdata guidance treats
sustained usage above 80% of the limit as the warning threshold, so neither is urgent — but these are
the two containers whose ceilings are most likely to be genuinely too LOW, which is the opposite
failure from the one the memory spec addresses and would show up as an OOM kill, not a host stall.

## [fleet] `fabrik apply` provisions a second flywheel database nothing reads (2026-09-03, owner: fleet)

Mail 01M1H2XGV09Y78W9TGVG3G92TH (intel), which also CORRECTS the open finding 01M1EWW9G8SSFZX08KFPRQEAM2:
the reported `missing-driver-psycopg` reason is not what stops the recording (psycopg 3.3.4 is installed).
`infrastructure.py:748-755` unconditionally injects `SUBAGENT_RUNS_DSN` at `postgres-main:5432/fabrik_analytics`
plus a per-project writer role, while the hub flywheel reads elsewhere — so a project can record faithfully
for weeks into a sink no consumer reads. The resolution step needs the fleet path to postgres-main
(`SELECT count(*), min(ts), max(ts), count(DISTINCT project) FROM subagent_runs`) and then a decision: one
analytics DB with the hub reading it, or drop the injection. Note for whoever takes it: `libs/subagents/`
carried a sibling session's uncommitted WIP through 2026-09-03 — check `git status` before editing that surface.
## [fleet] Existing fleet projects have no `.dockerignore` — the scaffold fix only covers NEW ones (2026-09-03, owner: fleet)

The scaffolder now emits `.dockerignore` at the build context root for every Dockerfile-bearing project
(`_ensure_dockerignore`, one place, graded). That fixes new scaffolds only. Every project scaffolded before
today as `node-api`, `file-api`, `file-worker`, `desktop-app`, `docusaurus`, `python-api-gpu` or
`office-extension` still has none, and their Dockerfiles do `COPY . .` while the VPS deploys by `git pull`
into a long-lived working tree — so a gitignored `.env`, `node_modules/` or `dist/` surviving a pull is
baked into the image. Backfill wants: an enumeration of affected repos (Dockerfile present, `.dockerignore`
absent), the file added per repo, and a decision on the delivery path — the governance sync does not carry
project-local build files today, so it is either a one-off scripted pass or a new synced-manifest entry.
Mail 01M1M9CYEHA55DQP03081X09HS (infra, pass 61).

## [fleet] The fleet GlitchTip default (D-126, `event_level=ERROR`) ships an EAGERLY-built log message verbatim (2026-09-05, owner: fleet + operator)

The vendored scrubber `templates/scaffold/python/glitchtip_init.py` diverges from its origin on one line:
upstream uses `LoggingIntegration(event_level=None)` — a log record NEVER becomes an event — while the fleet
default keeps `logging.ERROR` so errors are visible in GlitchTip. The comment beside that line claimed the
resulting channel was "closed" by `_ALLOWED_LOGENTRY_KEYS == {"message"}`. It is NARROWED, not closed, and
the comment has been corrected in place (2b656cfd + follow-up).

The residual, measured rather than reasoned — `_scrub_event({"logentry": {"message": "auth failed for
token=BEARER_TOKEN_ABC123"}})` returns that string UNCHANGED:

    logger.error("token=%s", tok)   -> logentry.message "token=%s"    SAFE (params dropped)
    logger.error(f"token={tok}")    -> logentry.message "token=abc"   SHIPS

`.format()` and `+` concatenation behave like the f-string. The template is still passed through
`_redact_userinfo_in_text`, so a URL-shaped credential IS caught (`postgres://u:pw@h` -> `postgres://[redacted]@h`);
a BARE token has no shape to key on. Upstream has no such residual because the event is never created.

This is not a defect in the vendor — it is the price of D-126, and it was previously undocumented, which is
the part that mattered: the next reader was told the channel was closed. Open questions for the operator,
none of them mine to decide unilaterally since D-126 is a ledger decision: (a) does the fleet accept the
residual and rely on the convention that scaffolded services log with %-style placeholders, (b) should the
scaffold ship a lint rule that flags an f-string/`.format()` argument to `logger.error`/`.exception` (measure
the fire rate first — FIX DIRECTIVE 5), or (c) should D-126 be revisited toward upstream's `event_level=None`
with errors surfaced through the Starlette/FastAPI integrations instead, which still report unhandled
exceptions. Note that exception VALUES carry bare secrets on BOTH sides of this choice
(`{"exception": {"values": [{"value": "bad key sk-live-DEADBEEF"}]}}` survives scrubbing), so (c) narrows
this channel without closing the class for an UNCAUGHT exception — but it DOES close it for a caught one,
which is the sharper half: `logger.error(..., exc_info=True)` on a caught exception creates an event ONLY
under `event_level=ERROR`, and `exception.values[].value` is allowlisted and never text-redacted. Two pool
readers found that half independently of me; a third finding of theirs — that `transaction_style="endpoint"`
could expose path parameters — is REFUTED at `sentry_sdk/integrations/starlette.py:853-856`, where `endpoint`
resolves to `transaction_from_function(endpoint)`, the handler's qualified name, carrying no request data.

## Upstream the subagents routing denies to fabrik-lib (intel, opened 2026-09-05)

**Status:** hub side is DONE and correct; this item is the upstream half only.

The hub's operator denies now live in `scripts/kilo-benchmarks/rank_task_subagents.py::OPERATOR_DENY`,
which generates the ranking doc `pick_models` prefers over its vendored table. That is the right
surface: it is hub-owned, and `libs/subagents` is fabrik-lib's module which the hub must not edit
(D-137 — an earlier attempt forked it, force-synced the fork to 46 copies, and was correctly reverted
three times by the re-vendor).

**The residual, stated rather than hidden:** the deny suppresses models from the ranking DOC. A
consumer with no synced doc falls back to `select.py::_TABLE`, which still lists them. Every fleet
repo receives the doc via the sync, so this is the no-doc case only — closing it fully needs the
upstream change.

**What was asked of fabrik-lib** (mail `01M1S7QACGEP66JM891E9B4CCQ`): four root causes in their module
— `FanoutBatch.__len__` returning 2 unconditionally (generating false "fanout dropped units" reports),
the default price ceiling removed on a premise production has falsified, the review roster's two
dearest models also being its two worst on 12,764 live runs, and `deepseek/deepseek-v4-pro` ranked
first for `docs` while failing 81% of 83 dispatches.

**Bar for closing:** fabrik-lib adopts the denies (or a value-preferring default) in canonical, at
which point `OPERATOR_DENY` becomes redundant and is deleted.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/rules_currency_watch.py`
<!-- END related-scripts -->

## [fleet] Quota board: a render-failure banner, not a fresh-looking page over a stale render (2026-09-07, owner: fleet = me)

The board froze for 16 regeneration cycles on a `TypeError` in `_pool_credits` (introduced 610c01b8, fixed a9e5fd4a by a peer, mails 01M1W7FEAJVNDVK8F4CP55R1VA / 01M1W9DPSPYPDS6RH6KYH2CD8Q): the traceback WAS logged, to `~/.claude/quota-dashboard.log`, which nobody reads — while the page's own header kept advertising a 20-second refresh over a render 67 s old and climbing. The defect class is not "unlogged"; it is that the artifact cannot tell the reader it is stale. Owed: a banner carrying the last successful render time + the error class of the last failed one (the external-services page's mtime-age embed is the pattern to copy). Small, a design call; the crash itself is fixed and graded.

## [operator] Claude Code deletes its own transcripts at 30 days, and session-recall is the only copy (2026-09-11, owner: operator + infra)

`cleanupPeriodDays` is UNSET in both `~/.claude/settings.json` and `~/.claude.json`, so Claude Code's
default transcript retention applies. Verified as a real setting in the running binary (2.1.263 —
"Transcript retention cleanup"); corroborated on disk, where the oldest surviving
`~/.claude/projects/*/*.jsonl` was dated exactly 30 days back. `scripts/dr_claude_backup.sh`
deliberately does NOT mirror `projects/` ("regenerable or huge"), and there is no pg_dump of the
session-recall database — so once a transcript ages out, the recall row is the last remaining record
of that conversation.

That became concrete on 2026-09-11: a `python -m ingest.reindex --full` in `/opt/session-recall`,
run to apply the new worktree project labels, also ran `_reclaim_orphans` — which by design removes
rows whose file is gone from disk — and reclaimed **5,791** files / 5,781 sessions, taking the DB
from 11,107 to 5,326 sessions. Not a bug: `--full` is the only path that sweeps orphans, and the
docstring says so. The loss skewed SHORT (26,941 turns over 5,781 sessions, ~4.7 each, against ~46
for the survivors — mostly pings, one-shot subagent runs and headless calls), and it is not
recoverable.

TWO decisions, both the operator's because both edit files outside any project tree — **(1) is now DONE, D-233: `cleanupPeriodDays: 3650` is set, DR-mirrored and verified. (2) remains OPEN.**
(1) raise `cleanupPeriodDays` so transcripts stop aging out at all — the root cause, one settings
key; (2) whether `--full` should refuse to reclaim without an explicit `--reclaim-orphans` opt-in,
or take a dump first. Until (1) lands, treat `--full` as a destructive operation and prefer the
plain incremental reindex (what the SessionStart hook and the MCP self-heal already run).

## [infra] check_doc_index's basename matching is a measured fail-open — 140 of 213 hub docs pass on a bare filename, 4 live false negatives (2026-09-11, owner: infra)

Found by an author-blind Opus seat closing the `/fabrik-review` on D-227, RECORDED rather than fixed
because it is pre-existing, untouched by that change, and far larger than the one-file exemption the
review was about — folding it in would have been the scope creep that stops a loop converging.

`scripts/enforcement/check_doc_index.py` direction (b) passes a doc when EITHER its full path OR its
bare basename appears anywhere in INDEX.md. Measured on the hub tree with the check's own exclusion
logic: **213 docs examined, 73 matched by full path, 140 matched only by basename.** Five files are
named `README.md`; exactly one of them is indexed by path, and the other four
(`docs/infrastructure/audit-prompts/`, `docs/infrastructure/probe-reports/`, `docs/preplans/`,
`docs/traycer/`) are in INDEX.md by neither path nor row — they ride the single string `README.md`
and are green today while being genuinely unindexed.

Minimum honest fix named by the seat: require the full path for any doc deeper than
`docs/<name>.md`, or accept a basename only when it is unique among examined docs. Either changes
fleet behaviour materially, which is why it wants its own measured change rather than a ride-along.

Two smaller members of the same file, same disposition:
* a non-UTF-8 doc path crashes the check — `_ls` uses `text=True` with strict decoding while the
  INDEX read two functions away uses `errors="replace"`. The complete fix is `surrogateescape` PLUS
  a surrogate-safe print (the seat verified that fixing only the decode moves the crash to the
  plain-text branch). Pre-existing; this file already carries a documented non-ASCII-path incident.
* `/opt/scratch_bhd` flips green -> red as an accepted consequence of the `_ls` fail-closed fix
  landed under D-227: it holds 21 markdown files under `docs/` and an INDEX.md but is NOT a git
  repo, so the check can no longer report OK over zero examined docs. Correct, and the only
  directory of the 48 carrying the check that changes verdict.

## [infra] check_doc_index decodes `%20` on ONE side of its membership test — 52 docs fleet-wide are reachable (2026-09-11, owner: infra)

Found by an author-blind Opus seat on the consolidation round of the D-227 review, RECORDED rather
than fixed for the same reason as the basename fail-open above: it is pre-existing, untouched by
that change, and fixing it inside a converging review is the scope creep that stops loops closing.

`scripts/enforcement/check_doc_index.py` unescapes `%20` on the direction-(a) side (the INDEX link
target) and compares raw paths on the direction-(b) side. So a doc whose name contains a SPACE, linked the
correct markdown way with the space percent-escaped, passes (a) and FAILS (b) — the check reports
`live doc not in INDEX.md: <the space form>` naming a doc that IS in INDEX.md. Reproduced in a fixture.

Denominator: **52 non-archive `docs/**/*.md` paths containing a space, across the 45 git repos
under /opt (5,051 docs total)**; 11 of the 52 are in the hub's own `docs/reference/research/`.
`/opt/job-agent/INDEX.md:295` already ships a `%20` link and is green only by accident — its link
TEXT repeats the raw basename, which satisfies the basename branch. A human-written title there
turns it red.

Fix named by the seat (2 lines at the membership test): compare the index text against `p`, `base`
and their `%20` forms. ⚠️ Its MIRROR must be decided at the same time, not after: a doc named with
a LITERAL the percent-escaped form currently produces `INDEX.md names missing path: docs/a b.md` — a path
that neither exists nor appears in INDEX.md, with NO link spelling that can satisfy it, because
there is no escape for a literal `%`. Same shape for a literal `#` (the anchor strip). Both are
the no-reachable-remedy class this review already hit twice. Honest denominator for the mirror:
**0 of 5,051** docs carry a literal `%20` or `#` today, so it is latent, not firing.

## [fleet] Kaizen observer tiers 2–3 are DEFERRED behind tier 1 and one kappa experiment (2026-09-11, owner: fleet)

The operator ruled the feedback→kaizen→command-improvement loop approved (**D-224**) and scoped the
build **tier 1 first** on 2026-09-11. Spec: `docs/superpowers/specs/2026-09-10-kaizen-feedback-loop-design.md`
§ D4 (content converged at review round 12, committed `3639ba6e`; the review itself closed **BLOCKED** on
the stall breaker — see below).

**Deferred, in order, with the trigger that releases each:**

- **Tier 3's judge** — released by ONE experiment, not by a decision: hand-label **20 closes on the
  `rules aware` axis** (the axis with the most ledger signal, 29 mentions at 107 rows) and measure the
  judge's **chance-corrected kappa** against them. Clears ⇒ build with 2–3 binary criteria per axis,
  each in its own call. Doesn't ⇒ an afternoon spent instead of a fortnight. Until it clears, every
  tier-3 verdict is a *candidate*, never evidence. ⚠️ Raw agreement overstates discriminative power by
  **33–41 pp** (Norman et al.), so the kappa is the whole test.
- **The tier-3 percentile cut-off** — waits on the M1→M2 variance sign-off (operator-triggered), the
  same owner as Q2's minimum-n and Q5's ⅔ threshold. **The sign-off is now the named owner of three
  distinct quantities and must be handed all three explicitly.** Until then the static attach-list runs
  (`fabrik-execute-plan`, `fabrik-review`, `fabrik-spec-review`, `fabrik-plan-after-chat` = 48 of 109
  closes = 44.0%) and the percentile is reported beside it, unused.
- **The manifesto axis (the operator's 8th)** — buildable, but **reuse `docs/reference/command-evaluation-checklist.md`
  item 63b's six intersections; do not write new criteria.** The three measured zeros are real and the
  neglect inference drawn from them was refuted: the 2026-08-31 manifesto command pass is `Status: EXECUTED`
  with *"do not inject manifesto vocabulary where an intersection is genuinely N/A"* as a global
  constraint. Residual gaps that ARE real: 4 of today's 36 command sources post-date that pass and were
  never walked, and the **56 rule packs were never walked at all** — no fact in the spec disposes of that
  third zero.
- **The spec's wording residue** — a parenthetical's ordering claim, an enumeration saying "four" where
  the text supports two, and a provenance phrase naming one artifact where two are needed. None changes a
  build decision. Released only by a DIFFERENT author: rounds 10–15 each confirmed defects the previous
  round's fixes introduced, fresh finder each round, same fixer every round, so another round by the
  spec's author is the mechanism that generates the next one.

**Do not re-propose:** `cost_usd` as a tier-1 field (13.9% non-null at 108 rows; dropped twice already
and re-imported once anyway) · tier-1 derivations as kaizen series (`counter_metric` is reciprocal and
therefore exclusive; three axes cannot pair, and inventing counters that guard nothing is a second
primary metric by Q2's own rule) · an observer on every run (7.3% of all tokens; production norm is
1–10% sampling) · eight judged axes (the exact configuration measured to collapse: >0.93 factor
correlations, >90% unexplained variance).

## [infra] Nine confirmed candidates in the kaizen spec's amendment — filed, NOT fixed, deliberately (2026-09-11, owner: infra)

`docs/superpowers/specs/2026-09-10-kaizen-feedback-loop-design.md` at HEAD `e7d5f7f6` (committed
`3639ba6e`). An amendment-only review of its last 97 lines confirmed **9 candidates, 3 blocking**, all
in text the spec's own author wrote. Filed to infra as `01M28VKD807M6QZB31NJ5D9W1T` with each item's
executed disproof.

**They are unfixed on purpose, and the reason is the finding.** That spec's review ran fifteen rounds
and closed BLOCKED on the stall circuit-breaker: rounds 10–15 each confirmed defects the PREVIOUS
round's fixes introduced — a fresh finder every round, the **same fixer** every round. The sharpest of
the nine is that pattern in its purest form: a residue list naming three remaining items, **two of which
the same diff had already fixed**. A sixteenth pass by the same author is the mechanism, not the remedy.
The reviewing seat reached that disposition independently.

**The three blocking ones, so nobody has to re-derive them:** the defect series prints 14 values and
calls itself fourteen rounds when fifteen ran (round 15's `confirmed = 7` is in the event stream and the
document cites it ten lines later) · the residue list is stale and incomplete · the universal negative
*"not one was a defect in the DESIGN … not a citation, not a ledger figure"* is false twice, once for a
struck claim about what `validate_registry` forbids and once for a corrected ledger figure.

⚠️ **One refutation worth keeping, because it kills a recommendation I had already made to the
operator:** the spec claimed handing residue to `/fabrik-plan-after-chat` *"breaks the finder-is-fixer
identity by construction"*. It does not — that command changes no author, and session `1970a0ff` ran it
and committed the resulting plan (`8bf4787d`) six minutes before the amendment was pinned. **Only a
different SESSION supplies the break.** Any future "hand it to the next pipeline stage" reasoning must
clear that bar.

**The systemic gap this exposes, and the real backlog item:** when a review's foundation error IS the
fixer's identity, the loop has no verb for it. `command_run.py` offers `done`, `blocked` and `handoff`;
the breaker text says name the foundation error as one operator question; neither expresses *"same
findings, different author"*. That is why this is a mail and a backlog row rather than a round 16. Worth
either a `handoff --resume` shape that carries a findings brief, or a line in
`commands/_fragments/term-edit.md`.

**Nothing downstream is blocked:** the spec is `Status: DRAFT — BLOCKED`, and the tier-1 plan
(`docs/development/plans/archived/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md` — superseding the 2026-09-11 plan-2 at 450e5c43, D-240; `8bf4787d`) depends on none of the
contested lines.

## [fleet] `_file_refreshed_credentials` is a credential writer with no production caller — keep with a reason or delete with its tests (2026-09-13, owner: fleet)

Found by the rotation refresh-chain review (round 2, Opus seat, receipt row P6 in `docs/development/reviews/2026-09-13-rotation-refresh-chain-review.md`): retiring `--touch` (D-247) removed the last production caller of `_file_refreshed_credentials` (`scripts/sysadmin/claude_rotate.py` — ROTATE_LOCK + `.prev` backup + `os.replace`; 42 lines from its `def` to the next top-level statement, blanks included — re-derived, the first cut of this row said 52); it is now exercised only by `tests/test_claude_rotate_v2.py` (4 call sites — lines 223, 233, 257, 270; two more mentions are docstring prose) and inventoried by name in `tests/test_claude_fleet.py`. One hop outside the review's fix hunks (D-230), so RECORDED here, not fixed there. Two shapes: keep it as the ONE sanctioned credential writer (then name the caller that will use it), or delete it with its tests. A second one-hop note from the same round: every `mesh-notify` message from the tick is rendered by `claude-sound.sh` as a session-death sentence ("Session quota-ro in /opt/fabrik died on <the message> …") — pre-existing for all 8 call sites of `_tick_telegram` (9 mentions minus the def), cosmetic, worth one line in the notifier's mesh-notify case when infra next touches it (the sound system is production: diagnose read-only, the edit is theirs).

## [fleet] `_tick_telegram`'s torn-above and symlinked-artifact verdicts are asserted by wording only — an executed grader is owed (2026-09-13, owner: fleet)

Recorded by the rotation refresh-chain review (round 13, test seat, receipt row **YY3** in `docs/development/reviews/2026-09-13-rotation-refresh-chain-review.md`). Round 12 established two facts about `_tick_telegram` in `scripts/sysadmin/claude_rotate.py` by ad-hoc execution against a stub notifier: with no prior artifact (`before == 0`) a torn non-empty write ADVANCES and confirms the push, and a SYMLINKED `.notified` reads as nothing forever (`_stamp_epoch` refuses symlinks; the notifier's `printf >` writes through the link). Both are pinned only as wording — the invariance grader `test_notify_failure_reason_names_every_cause_it_cannot_tell_apart` substring-asserts the returned line — while the one executed grader of `_tick_telegram` (`test_tick_telegram_reports_delivery_from_the_notifier_artifact`) covers absent / exit-0-without-artifact / advanced / stale only. One hop outside the round-12 fix hunks (D-230: the fix changed wording, not `_tick_telegram`), so RECORDED here. Remedy: two legs on the existing executed grader — a stub notifier writing `'175'` with no prior artifact → True, and a symlinked marker whose target advances → False. Fire rate: 0 observed; the class is a regression in `_stamp_epoch`'s policy going unnoticed. A second one-hop note from the same round (receipt row **XX7**, Opus seat): the notifier's window parse (`claude-sound.sh:263-265`) accepts any all-digits `last`, so a planted far-future `.notified` suppresses every send for that key indefinitely while `_stamp_epoch` clamps the same value to 0 — the sound system is production and infra's to edit; read-only here.

## [fleet] The tick's other stamps do not follow the symlink-refusing standard the chain push set (2026-09-13, owner: fleet)

Recorded by the rotation refresh-chain review (round 3, Opus seat, receipt row **U6** in `docs/development/reviews/2026-09-13-rotation-refresh-chain-review.md`; this row is the CORRECTED form of a round-1 row that was withdrawn because its claim — that the drain-stamp reader decodes stamp bytes — was false: it reads `stat().st_mtime`). Rounds 2–6 established the standard for stamp IO in `scripts/sysadmin/claude_rotate.py`: `_stamp_holds` refuses symlinks, `_write_stamp` opens `O_NOFOLLOW|O_NONBLOCK` 0600, refuses a non-regular sink (`S_ISREG`) and enforces the mode. The sibling stamps in the same file predate it and follow symlinks — cited by FUNCTION, not by line: the drain stamp in `_tick_inner` (the legacy single-account tick — `stamp.touch()` + `os.utime` on `_drain_stamp_path()`; fleet mode runs `_fleet_tick_inner`, which is rewritten and carries no drain stamp), the fleet advisory stamp (`stamp.write_text(...)` + `os.utime` in `_fleet_active_wall_advisory`), and the identity-probe stamp (`_identity_probe_result`'s `read_text().strip()` — wrapped in `_STATE_DIR_ERRORS`, but without the symlink refusal) — all with temp-dir fallbacks into shared space. One hop outside the review's fix hunks (D-230), so RECORDED here. Remedy: route them through `_write_stamp`/`_stamp_holds`-shaped helpers; grader per stamp: a planted symlink is neither read nor written through. Fire rate: 0 observed; the class is a planted link in a shared dir on a single-operator box.

## [fleet] An undelivered chain push retries every tick with no backoff — a dead notifier costs a spawn per account per tick (2026-09-13, owner: fleet)

Recorded by the rotation refresh-chain review (round 4, Opus seat, receipt row X7): when the notifier is permanently broken (bad Telegram keys), `_chain_expiry_push` re-attempts every 5-minute tick for every chain inside 3 d of expiry — one `bash claude-sound.sh mesh-notify` spawn per account per tick (each may block on `curl -m 15`), plus one "NOT delivered — send FAILED" line per account per tick in `rotate-tick.log`. Correct (the operator must be told, and the notifier's window bounds delivered sends) but unbounded in spawns. Lean close: skip the attempt while the account's last attempt is younger than the notifier's 30-minute window (an attempt epoch beside the stamp), or suppress the repeated line after N identical reasons. Fire rate: 0 observed (the notifier has keys); the class is a dead notifier for days.

## [infra] The scope-growth stop can never fire for `/fabrik-repo-review` — one command set is serving two different questions (2026-09-14, D-252 review round 2)

`scope_growth_warning` stands down for `PER_UNIT_ROUND_COMMANDS = {"fabrik-execute-plan", "fabrik-repo-review"}`, borrowing the set the OSCILLATION advisory uses. The borrowing is right for `fabrik-execute-plan` (dispatcher mode: round 4 is T11's review, round 5 is T08's — different surfaces, and the stop's exit sentence "close on the ORIGINAL delta's state" has no referent). It is questionable for `/fabrik-repo-review`, which under D-203 is a partitioned re-swept loop over ONE repo and can outgrow its artifact exactly as `/fabrik-review` can. Consequence, measured: the stop can never fire there, and the uncounted-round NOTE never prompts for the counter either, because that NOTE keys on `REVIEW_FAMILY` which excludes it.

**Shape of the fix:** split the set — `PER_UNIT_FOR_OSCILLATION` vs `PER_UNIT_FOR_SCOPE_GROWTH` — or mint a D-row stating that one set answers both questions deliberately. Either way the two advisories should stop sharing a constant sized for the first of them. `scripts/command_run.py` (`PER_UNIT_ROUND_COMMANDS`, `scope_growth_warning`, the round handler's NOTE).

## [infra] `--command` is normalised for its leading slash but not its case, so `--command Fabrik-Review` silences the review-family branches (2026-09-14, D-252 review round 2)

`start` stores `(args.command or "").lstrip("/")` — no `.strip().lower()`. The stand-down predicates in `convergence_warning` and `scope_growth_warning` both apply `.strip().lower()` before their membership test, but the `in REVIEW_FAMILY` tests in the round handler and on the close path are case-SENSITIVE against the stored value. So a record started as `--command Fabrik-Review` silences the uncounted-round NOTE and takes the wrong close branch, while the two advisories still stand down correctly — the same record read two ways.

**Shape of the fix:** normalise once at the start handler (`.strip().lower()` beside the existing `lstrip("/")`), rather than at each reader. Pre-existing on the close path; the new NOTE inherits it. `scripts/command_run.py`.

## [infra] `_trend_series` still filters non-dict rounds out of its series — the sibling half of a defect the scope-growth stop fixed (2026-09-14, D-252 review round 3)

`scope_growth_warning` no longer filters: a row it cannot read BREAKS the run, because closing the window across a malformed round made rounds 1 and 5 read as adjacent. `_trend_series` (`scripts/command_run.py`) still carries `if isinstance(r, dict)`, so the same malformed row is silently dropped from the oscillation and FEEDBACK series and the two rounds either side read as consecutive there. Executed: `_trend_series([{f:1}, "MALFORMED", {f:5}])` → `[1, 5]` while `scope_growth_warning` on the same shape returns `""`.

Also: the comment beside the removed filter claims "`_trend_series` applies the same rule over the unfiltered list" — it does not, so the claim is false as written.

**Shape of the fix:** decide which reader is right (dropping vs breaking), make both do it, and correct the comment either way. Not done here because the choice changes the oscillation advisory's behaviour on live records and deserves its own judgement, not a hurried one inside a review that had already tripped its own scope-growth stop.

## [infra] The `int()`-over-a-record-field class is closed for `findings` only — eight sibling call sites remain (2026-09-14, D-252 review round 3)

`_int0` was introduced after a bare `int()` on `findings` raised inside `_round_report`, whose single return sits on the Stop hook's path, so the outer guard blanked the entire round report — TERMINAL verdict included — while the record kept accepting rounds. The sweep converted the three `findings` readers. The same bare-`int()`-over-a-record-value shape remains at `event_seq` (×2), `seats_skipped`, `seats` (×3) and `phase` (×2) in `scripts/command_run.py`. Executed: a hand-written round carrying `{"phase": "x"}` raises `ValueError` inside that same one-return path and blanks the same report.

**Shape of the fix:** route the remaining eight through `_int0` (or a keyed sibling), or state per site why a raise there is acceptable. Measured, not vibed: only the `findings` path had a reproduced incident, which is why the first sweep stopped there.

## [infra] A test leg attributes its silence to the wrong mechanism (2026-09-14, D-252 review round 3)

`tests/test_command_run.py::test_a_review_round_that_confirms_without_counting_its_own_residue_is_noted` ends with a `fabrik-repo-review` leg commented "a per-unit loop is not prompted". The NOTE it checks is gated on `REVIEW_FAMILY`, which simply does not contain `fabrik-repo-review` — the assertion holds for ANY non-review command and would pass with `PER_UNIT_ROUND_COMMANDS` emptied. Proven: dropping `fabrik-repo-review` from that set reds two other tests and leaves this leg green.

**Shape of the fix:** assert the mechanism the comment names (`assert "fabrik-repo-review" not in REVIEW_FAMILY`), or re-word the comment to say what is actually being graded.

## [infra] A plan that indexes phases by LETTER cannot satisfy `step`'s review gate, whose matcher is ORDINAL — the only exit is a waiver that has to explain itself

`command_run.py::step` refuses a phase advance unless a file under `docs/development/reviews/`
matches `(?:^|[^0-9a-z])p(?:hase)?[-_ ]?<N>(?:[^0-9]|$)` for the NUMERIC phase it is leaving, or
the DISPATCHER ticket form. Every `/fabrik-*` plan in this repo names its phases with LETTERS —
`## Phase A`, `## Phase B`, … — because that is what the plan template writes and what the
receipts are then named after (`…-phase-C-review.md`). The two conventions never meet: a receipt
named exactly as the plan's own heading dictates is invisible to the gate, and `--review-waived`
is the only way forward.

**Measured 2026-09-14, on this plan:** `step --phase 3` refused with "phase 1 has no review
artifact", while `docs/development/reviews/2026-09-14-plan-2-mail-triage-phase-C-review.md` was
committed at `c17750aa` — three rounds, a full Coverage Checklist, closed on the D-252 stop. The
waiver had to carry a paragraph saying it was not a skip, which is the shape of an escape hatch
being used as a workaround. **Denominator, not yet measured:** how many of the 132 `*phase*-review.md`
files under `/opt/*/docs/development/reviews` carry a LETTER rather than a digit — that count
decides whether this is one plan's habit or the fleet's convention.

**Do:** accept a letter in the matcher and bind it to the plan's own phase headings (read the
plan at the record's stem, map its Nth `## Phase <X>` heading to ordinal N, accept either key), or
change the plan template to number its phases. Do NOT just widen the regex to `[0-9a-z]` — that
makes a phase-A receipt satisfy phase 1 of a plan whose first phase is Phase 0, which is the
prefix bug the existing comment at `:608` already paid for once.

## [infra] A review that closes on the SCOPE-GROWTH STOP can flip its RECEIPT but still cannot flip its PLAN — the exit was taught to one checker of two

⚠️ **Re-opened 2026-09-15 (plan-2 Finish).** I marked this RESOLVED when Phase E shipped
`check_review_coverage.py::_scope_growth_exit` — and that closed only half of it. The plan's
`Status: EXECUTED` flip is graded by a DIFFERENT script, `check_convergence.py`, which has zero
occurrences of `scope.growth` (`command grep -c` → 0) and refuses the flip unless the last Pass
row reads `confirmed: 0` (`CLOSING_ROW_REFUSAL`, `:215`). So a review that legitimately closes on
the stop writes a receipt that `check_review_coverage` accepts and a plan that `check_convergence`
rejects — the two gates disagree about the same artifact.

Found by RUNNING `check_convergence.py --project-root .` while preparing this plan's own archive,
not by reading: the flip had not been attempted yet, so nothing had surfaced it.

**This is the same class as round 2's headline defect** — a fix landing on 1 of N copies of the
same rule. `_plan_stem` was 1 of 3; this exit is 1 of 2.

**Shape of the fix:** give `check_convergence.py` the same fourth sanctioned exit, reading the
receipt's header-zone declaration and its ledger tail exactly as `_scope_growth_exit` does —
ideally by IMPORTING that predicate rather than copying it, since copying is what produced both
of this round's instances. Deliberately not built inside plan-2's Finish: adding a gate mechanism
during a Finish is the scope growth the stop itself exists to refuse.

⚠️ **SCOPE, corrected by execution 2026-09-15.** My first cut of this row said plan-2 "cannot
flip" and would be driven to a quiet round. That over-stated it, and I found the error the same way
I should have the first time — by running the predicate instead of generalising from a neighbouring
one. `_closing_row_fail` is reached only from `_check_spine_set`, whose population is
`_is_spine()` — a same-stem `.md` inside a dated plan DIRECTORY. Measured:

| plan | `_is_spine` | closing-row |
|---|---|---|
| `2026-09-12-plan-2-mail-triage-command-machinery.md` (monolith) | **False** | not graded |
| `2026-09-14-plan-1-kaizen-observe-and-act.md` (monolith, archived) | False | not graded |
| `2026-09-09-plan-1-review-convergence-redesign/…md` (SET) | **True** | graded |

So the seam bites **plan SETS only**, and a monolith `.md` plan is outside the rule entirely. The
disagreement between the two gates is still real for sets — and the archived kaizen plan reads
`Status: EXECUTED` over a ledger ending `confirmed: 3`, which `_closing_row_fail` refuses and which
survives only because the caller carves out the lowercase `archived` directory. That carve-out is
doing more work than its comment claims. (2026-09-14, D-252
review round 3, found by the stop's own close) (2026-09-14, D-252 review round 3, found by the stop's own close)

D-252 added a counted scope-growth stop whose sanctioned exit is "STOP the loop — route the remaining own-fix work to a backlog row and close on the ORIGINAL delta's state". A review that obeys it ends on a round with `confirmed > 0`, because the whole point is that the loop is still finding things and they are no longer worth another round. `check_review_coverage.py` then refuses the flip: *"the exit round must be quiet, or the stuck finding must be BLOCKED-escalated (named + 3 failed attempts), or the report must declare `Status: IN-PROGRESS`"*. None of the three fits — the round is not quiet, there is no stuck finding with three failed attempts, and IN-PROGRESS understates a review that reached a designed terminal state.

Measured on the stop's own review: rounds confirmed 5 · 4 · 5 with own-fix 0 · 4 · 5; the stop fired at round 3 (`4/4 → 5/5`); the receipt was written, every finding fixed or routed, and it still cannot say CONVERGED.

**Shape of the fix:** a fourth sanctioned exit in the receipt grammar and in `check_review_coverage.py` — a closing row whose method cell declares the scope-growth stop and whose RECORDED rows all carry backlog destinations, accepted as terminal. It belongs with the `_confirmed_quiet` / `QUIET_PASS` readers that already encode the other exits. Deliberately NOT built inside the review that found it: that review had already tripped its own stop, and building the fix there is the exact scope growth the rule forbids.

## [infra] A grader anchored to a live shared-tree governance clause by an emoji heading raises IndexError, not an assertion failure (2026-09-15, plan-2 Phase G review round 2, RECORDED one hop out)

`tests/test_mail_structure.py` reads the trailer-trap clause with
`Path("CLAUDE.md").read_text().split("⚠️ **And a THIRD trap")[1][:986]`. Three concurrent sessions
share that file. The moment any of them rewords that heading the grader raises `IndexError` — not a
readable assertion failure naming the drifted clause — and the fixed `[:986]` window silently
shortens if the clause is edited without moving the heading, so the test can weaken without failing.

Pre-existing: the round-2 diff changed only the `verify` loop above it. **Shape of the fix:** anchor
on a stable sentinel comment in `CLAUDE.md` rather than on prose, and assert the split succeeded
with a message naming the expected anchor before indexing `[1]`.

## [infra] `final_gate.py --json` per-check dicts carry no `status` key — a consumer cannot tell green from red per check (2026-09-15, plan-2 Phase G review round 2, MACHINERY note)

Executed: `json.load(...)['checks']` over `final_gate.py --check --json` gives
`Counter({None: 63})` for `d.get('status')` across every check dict. Pass/fail/skip counts exist only
as the top-level `passed`/`failed`/`skipped`/`skipped_checks` keys. Any consumer following the
obvious per-check shape reads N statusless entries and silently learns nothing — the same
fail-silent-green class the enforcement corpus already tracks.

**Shape of the fix:** emit a per-check `status` field, or document at the schema that the top-level
counters are the only verdict. Ungraded either way today.

## [infra] The phase-boundary review gate matches receipts by record ORDINAL while plans name them by LETTER, so a reviewed phase reads as unreviewed (2026-09-15, plan-2 Phase H step, found by a refused `command_run.py step`)

`/fabrik-execute-plan`'s D4 gate refuses a step when "phase N has no review artifact", looking for a
filename containing `phase-<N>`. Plans A/B/C name their receipts by LETTER
(`…-phase-C-review.md`), which is the convention those phases actually shipped with. Phase C of
plan-2 HAS a committed receipt and still read as unreviewed, because it is record-phase 1 and its
filename says `phase-C`.

The escape hatch works and was used honestly (`--review-waived` with the reason recorded), but a
gate whose normal outcome on a correctly-reviewed phase is a waiver trains agents to waive. Phases
E/F/G of the same plan carry BOTH (`phase-3-E`, `phase-4-F`, `phase-5-G`) and are read correctly,
which is the accidental workaround rather than a documented convention.

**Shape of the fix:** accept either spelling — match `phase-<ordinal>` OR `phase-<letter>` where the
letter is the plan's Nth `## Phase <X>` heading — or state the dual-token naming
(`phase-<ordinal>-<letter>`) in the receipt convention so it stops being folklore. Do NOT just widen
to a bare `phase-.` glob: that makes any phase's receipt satisfy every phase.

## [infra] `commands/_sources/fabrik-review.md:23`'s ROUTED-UP citations resolve to unrelated lines, and there is no route-up logic in `command_run.py` at all (2026-09-15, plan-2 Finish review, RECORDED — pre-existing)

The sentence cites `command_run.py:1863` → `:2702` as "the ledger's only positive witness that
`/fabrik-review-scoped`'s route-up fired", and `:2585` for the reach-back. Executed:
`command grep -n "ROUTED-UP\|route-up\|route_up" scripts/command_run.py` → **0 matches**; the three
cited lines are `common.add_argument(`, `started_epoch = rec.get(...)` and a `_scratch_advisory`
docstring line. ROUTED-UP exists only as prose inside the command markdown — the run record witnesses
it because the surface STRING is written by the caller, not because any code detects it.

Unchanged by plan-2 (present at `36da6bb4`), so RECORDED rather than fixed in that run. **Shape of the
fix:** cite the real closing-state check (`AGENT_CLOSED_STATES` at `:774`) or drop the false precision —
three exact line numbers that resolve to unrelated code read as verified and are not.

## [infra] `check_plan_lock_release.py` cannot see a cross-plan overlap — it judges staleness only from the plan's own `Status:` string (2026-09-15, plan-2 Finish review)

`.fabrik/plan-locks/2026-09-09-plan-1-review-convergence-redesign.json` is `status: active` with 34
`owned_paths` that cover essentially plan-2's entire File Scope (`commands/_sources/fabrik-review.md`,
`fabrik-review-scoped.md`, `scripts/command_run.py`, `scripts/final_gate.py`,
`docs/workflows/FINAL_GATE_WORKFLOW.md`, `CLAUDE.md`, `templates/governance/CLAUDE.md`, …). Plan-2 ran
75 commits across those paths over three days and never referenced that lock
(`command grep -c "review-convergence-redesign"` over the plan file → **0**), and no plan-lock JSON
exists for plan-2 at all. No work was lost — both are this operator's own sequential sessions — but the
one check that exists to catch this is structurally blind to it.

**Shape of the fix:** flag an `active` lock whose `owned_paths` have been edited by commits carrying a
DIFFERENT plan's provenance (`Agent-Phase`/`Agent-Context`) since the lock's own creation. Staleness
read from the plan's self-reported `Status:` cannot detect a lock the editing plan never knew about.

## [infra] Findings RECORDED by the plan-2 Finish review (2026-09-15) — one hop out, or measured rather than defective

Each was EXECUTED by the seat that raised it and re-checked before filing; none is inside plan-2's
own hunks, so under the D-230 bar they are RECORDED with destinations rather than counted.

1. **`final_gate_stop.py` — the widened `_ROUTINE_GOVERNANCE` also widened the GATE cause's
   exclusion.** `candidates` excludes the two new ledger names, so a `docs/DECISIONS.md` failure the
   session itself caused is WAIVED whenever any sibling token is present. Disclosed in the
   constant's own MIRROR comment, but the comment does not say the fail direction is OPEN on a gate
   cause. **Fix:** keep ledger files out of `candidates` only when they are the SOLE token.
2. **`final_gate_stop.py::_surface_reviewed` matches only whole root-relative paths**, so a review
   whose `--surface` names a file by BASENAME exempts nothing and the sixth cause false-BLOCKs.
   Bounded by the 3-attempt warn-through. **Fix:** match basenames too, or say so in the docstring.
3. **`mail_notify.py` / `mcp_watch.py` — the headless guard sits OUTSIDE the catch-all** both
   modules document as wrapping "the WHOLE body". `os.environ.get` cannot raise, so there is no
   live defect; the INVARIANT as written is simply no longer true, and the next edit to that region
   is unprotected. **Fix:** move the guard inside the `try`, or amend the docstring's claim.
4. **`command_run.py:303` — the delta stand-down accepts a bool.** `isinstance(d, (int, float))` is
   True for `True` and `0 <= True <= 20`, so `delta: true` silences the oscillation advisory; and
   `_trend_series` filters non-dict rows while `deltas` does not, so `len(deltas) == len(series)`
   fails silently on a malformed row. Both advisory-only. **Fix:** mirror `_count`'s bool guard.
5. **`sync_enforcement_to_projects.py::_head_source` has no symlink/gitlink guard.**
   `stat.S_IMODE(0o120000)` is `0o000` and `git show HEAD:<link>` returns the LINK TEXT, so a
   symlinked synced source would distribute as a 0-permission regular file containing a path. Not
   live: exactly one symlink exists under the synced roots (`scripts/verify_prod_parity.py`) and it
   is in neither `CORE_SCRIPTS` nor `scripts/enforcement/`. **Fix:** `if mode not in (0o100644,
   0o100755): return None`.
6. **`check_review_hygiene.py` — `--stop-at-heading ""` is a silent no-op**, the only selector in a
   file where every other bad argument prints a `REFUSED —` envelope. **Fix:** route it through
   `_refuse`.
7. **`check_plan_tickets.py::_GATE_FILE_RE` roots are Python/hub-shaped** —
   `(?:tests?|src|scripts|server|app|lib)/` covers no `packages/`, `apps/`, `web/`, `api/`, `ios/`,
   `android/`, `functions/`, which is what the `node-api`, `mobile-app`, `chrome-extension` and
   `office-extension` scaffolds actually use. Direction is a MISS, never a false red — degraded
   coverage, not a break. **Fix:** widen the root alternation per scaffold type.
8. **The bandit `scripts/` leg's "0 today" denominator is the HUB's.** Measured across all 47
   `.fabrik/synced.lock` repos with each repo's own interpreter: bandit is installed in 6, and
   `/opt/tryton-crm` already carries the leg and now reds on pre-existing code no change touched
   (its own `certification_inventory.py:105`, B324 — that file is tryton-crm's, not the hub's). The other 41 get a green
   `NOT INSTALLED — skipped`, so a check "measured at 0" is unarmed in 87% of the fleet.
   **Fix:** state the denominator in the comment and seed a per-repo allowance (the lint-ratchet
   shape the comment itself invokes) instead of a flag-day HIGH floor.
9. **`check_doc_index.py` and `check_doc_sync.py` disagree about `.fabrik/plan-locks/`** — one
   demands an INDEX row for a tracked plan lock, the sibling hunk declares the path transient.
   Re-derived on this repo: of 128 files added under the four `_CODE_ROOTS` since 2026-09-01, 52
   are unindexed and 13 of those (25%) are `.fabrik/` paths, 12 of them plan locks — a quarter of
   the advisory's real output is the class the sibling just declared out of scope. Advisory-only,
   but it fires on every `/fabrik-execute-plan` start fleet-wide. **Fix:** exclude
   `.fabrik/plan-locks/` and `.fabrik/cert-locks/` from `_CODE_ROOTS`, or reuse
   `check_doc_sync.SKIP_PATTERNS`.
10. **`tests/test_sync_head_source.py` — the red-on-revert harness graded the LIVE tree.**
    ⚠️ **TWO causes, and I filed one while a reviewer filed the other — each of us called the
    other's wrong.** Both were real and neither alone was sufficient, which is why the first two
    attempts at a proof both lied, in opposite directions.
    (a) `REPO = Path("/opt/fabrik")`, hardcoded absolute, so `SCRIPT = REPO / "scripts" / …`
    loaded the LIVE script whichever tree pytest ran in — the reverted copy sat beside the test
    and was never read, and both arms went green.
    (b) the revert tree carried only the one file, so once (a) was fixed the module hit
    `ModuleNotFoundError` on its `fabrik_synced_manifest` import and both arms went RED — a
    failure that looks like a passing red-on-revert and is not.
    FIXED 2026-09-15: `REPO = Path(__file__).resolve().parents[1]`, the other spellings aligned to `SCRIPT` — the CWD-relative
    one and a long-hand re-derivation of the same path, FOUR in one file before this — and the
    revert recipe copies the import surface. With
    all three, GREEN with the fix and RED on the reverted blob, md5-asserted. The assertion was
    sound throughout; only the harness was blind.
    **Lesson worth more than the fix:** each of us diagnosed from a plausible mechanism rather
    than executing both arms to completion, and a partial diagnosis reads exactly like a whole
    one — the same defect this review confirmed nineteen times in other people's code. Three
    files is the minimum revert tree here, and a revert harness that goes green on BOTH arms —
    or red on both — is reporting on itself, not on the code.

## [infra] 15 of this plan's 66 phase-named commits carry no `Agent-Phase` trailer, so phase attribution under-reports its own work (2026-09-15, plan-2 Finish, found while assembling the archive Status line)

Measured over `git log 36da6bb4..HEAD`, kaizen commits excluded, by reading
`%(trailers:key=Agent-Phase,valueonly)` per commit: **66 commits name a phase in their SUBJECT and
15 of them (23%) carry no trailer** — Phase B ×1, Phase C ×9, Phase D ×5. Phases C and D were
therefore committed almost entirely without it, and
`git log --format='%h %(trailers:key=Agent-Phase)'` — the query the trailer table exists to serve —
shows those phases as empty. Assembling this plan's own archive Status line is what surfaced it:
the per-phase closer had to be recovered by subject grep instead.

⚠️ **Why no check caught it, and why the obvious fix would not have:** every one of those commits
was made with the private-index recipe (`commit-tree` + `update-ref`), and that path runs **no
commit hook at all** — not pre-commit, not commit-msg. A `commit-msg` guard would have fired on
exactly the commits that do not use it. The contract already says the trailers are "yours to run by
hand" there; the gap is that nothing then checks the hand-written result.

**Shape of the fix:** a repo-health check (Tier-3, advisory) that reads back the last N commits and
reports any whose subject names a phase, a ticket or a review round while the corresponding trailer
is absent — a POST-hoc audit, since the pre-commit seam is structurally unavailable on the one path
this repo mandates for shared-append files. Note the cobra before arming it: the cheapest way to
satisfy such a check is to stop naming the phase in the subject, which is worse than the gap — so it
must key on the plan-lock or the run record, not on subject text alone.

## [infra] CLAUDE.md's denominator rule names `.claude/worktrees/` but not `mutants/`, and a repo-root recursive count descends both (2026-09-15, plan-2 Finish round 3, raised by a reviewer seat's MACHINERY note)

The § HARD STOPS denominator rule teaches `command grep` / `rg --no-ignore --hidden` for negatives
over synced paths, and warns that worktrees are 36% of an unscoped `*.py` count. It does not name
`/opt/fabrik/mutants/` — a gitignored, untracked full copy of the tree left by mutation runs — so
an agent following the rule exactly still gets an inflated number. Measured with `find` (the
producing tool, not a grep pipeline), this hour:

| question | answer |
|---|---|
| `find tests -type f -name '*.py'` | **354** |
| `find . -type f -name 'test_*.py'` | **9,798** |
| same, excluding `mutants/`, `.claude/worktrees/`, `.tmp/` | **3,354** |

A 2.9× inflation between the second and third rows, and neither equals the first — rooting the
search at the directory you mean is what makes the count immune, which the rule's own advice about
search ROOTS already implies but never states beside the exclusion list.

**Shape of the fix:** add `mutants/` to the rule's named exclusions and state the general form —
the exclusion list is unbounded because it is generated by tooling, so the durable advice is to
ROOT the search at the directory whose population you are claiming, and to name that root beside
the number. A reviewer seat hit this independently on one pattern (919 hits from `mutants/` alone),
which is the evidence that the current wording is not sufficient.

## [infra] The lint ratchet's version relief lets a SIBLING's uncommitted re-seed set the floor, inside the mismatch window (2026-09-15, plan-2 Finish round 6, narrowed not closed)

`_baseline_payload` reads `git show HEAD:<rel>` precisely so "a sibling's uncommitted re-seed on a
shared tree" cannot "move a fleet-wide bar" — its own docstring. The version relief added this run
re-opens that for the COUNT, in one bounded window: session A leaves debt uncommitted and runs
`--reseed`; session B's plain gate then takes A's floor and passes. Executed on a shared-tree
simulation: rc 0 at the relief, rc 1 at its parent.

**Bounded three ways** — the stored and live ruff versions must genuinely differ, a working-tree
baseline must exist carrying the LIVE version, and its count must not exceed what the tree measures
now (`_local_count <= current`, the falsifiable stand-in for "this is a re-seed").

**Why it is not simply closed:** the alternative is the wedge — a gate nobody can clear before a
commit, which is how gates get switched off. Three cuts of this relief were each fail-open in a
different way before the count became a precondition, so the honest disposition is a narrowed,
stated residual rather than a fourth attempt inside a Finish.

**Shape of the fix:** require the working-tree baseline to be STAGED by this session (or carry a
session marker) before its count is honoured, so a sibling's unstaged file cannot serve. Needs a
notion of "mine" the check does not currently have — spec-shaped, not a one-liner.

### Kaizen loop — the residue of the D-252 stop (2026-09-15)

- **`docs_updater.py` reimplements the ledger row parser and will DIVERGE from it** (owner:
  **infra**) — routed out of the ledger-write-integrity spec by its own D-252 stop. `docs_updater.py`
  deliberately does not import `decisions.py` (`:936`, *"no import — see the Interfaces seam"*): it
  carries its own `MERGE_OWNER_RE` / `_DECISION_ROW_ID_RE` (`:938-939`) and a plain
  `stripped.strip("|").split("|")` at `:1190`. Once `_rows` becomes code-span-aware the two disagree
  on cell boundaries for any row carrying an escaped pipe. Second half of the same seam:
  `read_merge_owner` takes the LAST match in FILE order while `--append` writes atop the table, so a
  merge-owner row written by the sanctioned writer would lose to an older one below it (the hub
  ledger's last merge-owner match is D-155 at line 244 today). Shape of the fix: one shared helper, or
  the same rule taught to both with a drift pin across the seam.

- **`check_governance_tables.py` does not see the two files carrying addressable rows** (owner:
  **infra**) — it scopes itself to governance contracts (`:19-23`, `OK — … across 1 contract(s)`), so
  `docs/DECISIONS.md` and `INDEX.md` have no cell-width check at all, and the same sweep found a `-`
  bullet inside an `INDEX.md` table dropping 13 rows out of the render with no gate able to see it.
  Its docstring names the wallpaper trade-off deliberately, so this is a judgement call, not an
  oversight. Reported by iterative_image_editor inside 01M2JQYM9PGQK6Q53GJ3SGP3TV; kept OUT of the
  ledger-write-integrity spec because that spec's gate covers `DECISIONS.md` only.

- **`decisions.py` reconstruction residue** (owner: **infra**) — routed by the scope-growth stop
  rather than patched a fourth time: (a) the both-ends read anchors on the last two cells, which is
  wrong when the shatter happens INSIDE the `why` — fabrik-lib D-177 gets a prose fragment as its
  `where` where HEAD had an honest blank (1 of 947 rows); a `where` plausibility test would close
  it; (b) the short-branch marker is ungraded for columns 0-3, so a 3-cell row could regain a
  silent blank in `what` (0 live rows today); (c) `tests/test_decisions_table_shape.py` strips code
  spans before counting pipes, so 10 of 947 rows pass its shape check while the parser splits them
  long — the guard is lenient exactly where the parser is strict; (d) `.strip("|")` still eats a
  trailing escaped pipe (0 live rows, unchanged from HEAD).
- **`--next-id` collides when two agents mint correctly** (owner: **infra**; SPEC work) —
  `decisions.py --next-id` reads max+1 without reserving, and in a linked worktree the window is
  until MERGE, not seconds. Two incidents in iterative_image_editor alone (2026-09-03 three agents
  minted D-006 twice; 2026-09-15 lanes A and C both minted D-037/D-038). Rows are immutable, so the
  repair renumbers rows and BREAKS citations written before the merge. Reported with a proposal at
  01M2KA20BJ02GF1GG3TQ8YA6VB; needs a mechanism (reservation, or worktree-scoped ids), not a patch.

- **The quota-band contract's routed residue** (owner: **infra**; D-264) — four items the
  scope-growth stop routed rather than patched a fourth time: (a) the bands overlap at exactly 90
  and the RED band's mail keys on the SESSION window while the band keys on the HOTTEST, an 8-point
  gap where an agent is RED with no mail coming — both are in the operator's own directive text and
  are raised on its ack, not rewritten by its implementer; (b)
  `docs/workstation/claude-account-rotation.md:30` says the carrier binding is "a no-op" without
  both env vars while `claude_rotate.py:1386` says it fails OPEN onto the wrong chain — the doc
  overstates; (c) the legacy tick writer records `pct` as `max(five_hour, seven_day)` while the
  fleet writer records `five_hour` alone, so one file holds two incompatible series under one key;
  (d) stale comments in `claude_rotate.py` — `:4257` names caps "sarp 90, ob 80" against a live
  `caps.json` of 95/99, and `:4908` says the threshold defaults to 95 when it returns 98.
- **`check_corpus_weight.py` exits rc 0 while printing its growth warning** (owner: **infra**) — a
  caller gating on the exit code alone sees green, and the warning names a D-row obligation the
  script never verifies. Both halves surfaced by review seats on 2026-09-16.

- **`mail.py ack()` cannot distinguish "handled and answered" from "handled and silent"**
  (owner: **infra**; SPEC work, not a patch) — `ack()` takes a `disposition` from a fixed set and
  appends an `acked-by:` line; it has no notion of whether a reply was ever sent, so a message can
  leave the inbox with the sender never hearing anything and nothing downstream can see it.
  Measured on the HUB's own archive (1,254 messages, reply-threading resolved across the whole
  `/opt/fabrik-mail` store): **342 of 669 findings, 62 of 171 requests and 15 of 27 relays carry no
  reply anywhere** — worse than the fabrik-lib number that prompted the question (187 of 350).
  Reported by fabrik-lib-dev1 (01M2K5ZAAS41EHGQ52HDW6QFDM), who asked BEFORE building because
  `scripts/mail.py` is hub-vendored. It is: the fix changes the mail contract's grammar on a file
  distributed to ~46 repos, so it opens at /fabrik-spec — a `reply-sent` fact the ack can read, or
  a disposition that names silence honestly, plus whatever the digest should do with it.

- **The denominator rule never warns that a SEARCH ROOT can contain whole duplicate trees**
  (owner: **infra**) — it names `.claude/worktrees` only inside its `*.py` population example, so a
  compliant census rooted at a repo root over-counts: fabrik-lib measured `LlmMeter(` at 43 hits of
  which 35 were stale worktree copies, an AST pass returned 10. Two independent reports (fabrik-lib
  01M2JWEMFRFN3H item 3; a hub review seat the same day).
- **The mutation rule and a read-only finder brief contradict each other** (owner: **infra**) —
  CLAUDE.md mandates `repo_lock.py acquire` before a mutation sweep; a finder brief forbids mutating
  the shared tree at all. They reconcile only if "mutate a COPY under your own scratchpad" is named
  as the sanctioned finder path, which neither document says. A seat took the right route and
  reported worrying it was non-compliant (fabrik-lib 01M2JWEMFRFN3H item 4).
- **Nothing catches a malformed `docs/DECISIONS.md` row** (owner: **infra**) — `decisions.py:97` pads
  a short row with `[""] * (6 - len(cells))` and `check_decisions_unique.py` exits rc 0, so a
  column-shifted row answers the ledger query the contract says to run FIRST with a blank `where`.
  Two rows shipped that way this session (D-262, D-263) and were repaired by hand; a one-line
  cell-count assertion closes the class for all 264 rows. Separately, 8 rows carry MORE cells than
  the header from a literal `|` in prose (D-178, D-099, D-092, D-090, D-087, D-084, D-075, D-055).

- **The Pass-row FINDERS cell: checker, command text, error string and generator all disagree** (owner:
  **infra**; D-262) — `check_review_coverage.py:753` reads `cells[1]`; `commands/_fragments/term-coverage.md`
  documents "METHOD FIRST … finders after"; the checker's sibling error string and `review_receipt.py:180`
  both emit finders SECOND. A row written as documented is REFUSED. Three patches were tried and withdrawn
  (fail-open twice, then 9 retro-red receipts across 3 repos). Size: /fabrik-spec — it is a fleet-synced
  grammar with 847 receipts constraining it. Reported by site-provisioner 01M2K19AEKKAXG5NB211C2WFCM.
- **`check_citations_resolve` cannot grade a bare-filename citation, by design** (owner: **infra**; D-262) —
  `check_text:72-77` skips every path without a `/` because a bare name is ambiguous across repos (measured:
  11 of 30 hits at review of 66aa32a5). So `.env.example:N`, `Makefile:N` and CLAUDE.md's own `.gitignore:199`
  are ungraded and a wrong line number there is invisible. A fix must engage that measurement — root-anchored
  dotfiles are safe (measured: 43 repos, 156 resolve, 0 red) while `Makefile`/`Dockerfile` are not (5 false
  reds in the hub alone). Reported by trade-intelligence 01M2JT7N2RKZ7DABFMRDXE6KJ1.

- **`commands/assemble_commands.py::PARAMS` holds per-command TEXT that `--mark-answered` refuses**
  (owner: **infra**) — `_is_corpus_path('commands/assemble_commands.py')` is False, so a verdict about a
  per-command slot can be edited but never marked answered; the run dies mid-PHASE-5 and the queue never
  falls. Executed in a throwaway repo: `REFUSED — nothing marked: … touches no corpus path`.
- **The lock-status filter is narrower than the writer's own partition** (owner: **infra**) —
  `/fabrik-command-improve` and its readers filter `status == "active"`, while
  `scripts/enforcement/check_plan_lock_release.py:59` defines `NON_TERMINAL = {active, paused, blocked}`.
  No paused/blocked lock exists today (0 of 70), so this is a latent fail-open, not a live one.
- **A foreign `{{include:}}` on its own line renders GREEN and silently inlines** (owner: **infra**) —
  `assemble_commands.py:1170` substitutes `[\w-]+` while the leftover guard at `:1171` matches only
  `[A-Za-z_-]+`, so a digit-bearing directive passes both. A round-3 seat rendered a copied corpus with a
  foreign fragment inserted: rc 0, `rendered 37 commands`, the file 3.5 KB larger. Only the mid-line shape
  errors — the corpus warning about this is therefore true only for that shape.
- **`COMMAND_RUN_DIR` does not scope kaizen events** (owner: **infra**) — a review seat's scratch-scoped
  `command_run.py` probe still wrote a fabricated session into the shared fleet stream
  (`~/.claude/state/events/probe-seat-r3.jsonl`, removed). `kaizen_events.py` keys only on
  `KAIZEN_EVENTS_DIR`; every probe brief that scopes `COMMAND_RUN_DIR` must set both, or the scoping lies.

- **`^def test_` reaches 75% of Python graders** (owner: **infra**) — round 3 measured 310,030 of
  413,590 declaration lines across 79,354 files (`rg --no-ignore --hidden`): the pattern misses every
  class-method and `async def test_` grader. Rule (4) now hedges with "whichever pattern the suite's
  language uses" rather than prescribing; the pattern engineering is deferred, not done. Routed here by
  the D-252 scope-growth stop on `/fabrik-command-improve` 2026-09-15 (rounds 2 and 3 both confirmed
  only defects inside round 1's own fix).
- **No check greps the command corpus for BRE-invalid regex literals** (owner: **infra**) — rule (4)
  shipped `^\s*(test|it)\(`, which exits 2 under default BRE and reads as a clean `0` through a pipe:
  the exact trap CLAUDE.md § denominator-honesty names in prose. The corpus now warns in-line; nothing
  enforces it. Found by the round-3 seat's MACHINERY note.
- **`_MAIL_TRIAGE_FRAGMENT_SENTENCES` is named for a plan that no longer owns it** (owner: **infra**) —
  it is now the general fragment-phrase registry (adjudicated COSMETIC by the round-2 seat: the rows
  carry their own provenance comments, and a second dict would re-create the third-parallel-reader
  defect this run removed). Rename when something else touches the file.

`/fabrik-review` over `9802bd43..11b75eac` closed on the D-252 scope-growth stop after three
rounds (confirmed 28 / 21 / 9; own-fix 1 / 21 / 9). Every confirmed defect of rounds 2 and 3 lay
inside a fix the review itself had written, which is the stop's own definition. These four were
RECORDED rather than fixed, each with its destination.

| Residue | Why it was not fixed in-run | Destination |
|---|---|---|
| `tests/test_command_feedback_report.py::test_a_partial_write_is_not_reported_as_success` is a pure tautology — it re-implements `main()`'s rc branch inside the test body and never drives the CLI (mutating `main()` to `return 0` leaves it green) | One hop out: it landed at `84b62eb7`, the left endpoint of round 3's range, so the D-230 bar makes it RECORDED. The CLASS is covered — `test_cli_return_codes_separate_refusal_from_an_idempotent_no_op` reds under the same mutation — so the guard is a decoy, not a hole | **infra** — drive `main()` via `_cli(...)` with a forced PARTIAL and assert `returncode == 1` |
| `test_every_live_ledger_row_that_reads_as_a_none_still_closes` has three narrownesses: it `pytest.skip`s when the ledger is absent (CI, a fresh clone) so it asserts nothing there; its filter strips an ASCII hyphen that `_is_none_head` does not, so a row whose first token is `none-` would be selected and falsely reported; and it hard-codes `("none","nothing","n/a")` instead of reading `cr._NONE_WORDS` | Not vacuous — it selects 5 of 186 live rows and 4 of those 5 catch the regression it guards — so the value is real and the narrowing is a hardening, not a fix | **infra** — same file |
| `test_the_writer_never_blocks_on_a_non_regular_index` catches its regression by HANGING (rc 124), not failing | A genuine catch, but in a repo with the pytest leg armed it would wedge the completion gate with no diagnostic instead of printing a failure | **infra** — wrap in `signal.alarm` / `faulthandler.dump_traceback_later` |
| `command_feedback_report.py::_axis_of` buckets `<legal axis>: <anything bracketed>` as `placeholder`, so `change: lean: <cut the rubric block>` never counts toward its axis | Pre-dates this diff (`eca8da1d`), and 0 of 186 live rows are affected. Either `_axis_of` mirrors `_is_placeholder`'s keyed rule, or the sweep's `unkeyable` definition excludes a keyed bracket — today they contradict | **infra** — `_axis_of`, or the grader's definition |

**Not blocking.** Every fix from all three rounds is committed, pushed and fleet-synced; the gate is
green; the loop is proven end to end at `<scratchpad>/kzrev/probes/loop-closes-end-to-end.md`.
Receipt: `docs/development/reviews/2026-09-15-kaizen-loop-gap-closure-review.md`.

### Multi-agent identity — trade-intelligence's proposal, the part not yet built (2026-09-16, D-267/D-268)

- **Multi-agent identity has ONE channel and it is write-only at process launch — SPEC work**
  (owner: **infra**; reported by trade-intelligence `01M2N1MJK1FVS543HS7MHW0D7K`, ruled in D-267).
  Direction 3 shipped; these three did not, because together they are a new mechanism spanning
  fleet-synced hooks and `mail.py`:
  (1) **ROOT FIX — a second identity source a LIVE session can write.** `--adopt` also emits
  `.fabrik/agents.json`; resolution becomes `CLAUDE_AGENT` → `Agent-Name:` trailer → file →
  unresolved. ⚠️ A roster alone does not say WHICH session you are — but hooks receive `session_id`
  on stdin (executed: `session_orient.py`'s SessionStart payload parse already reads it — cited by symbol, not line, because this very change moved that line twice), so a session→name map is the shape
  worth speccing. `agent_role.py` is SessionStart-only, so a mid-flight self-naming binds the
  charter on the NEXT start; say so in the spec rather than implying otherwise.
  (2) **`acked-by: <repo>/<agent>` via an optional `mail.py --as`.** The reporter proved all five
  consumers route through one `_ACK_LINE` regex and that the suffixed form matches; the open half is
  the READ path across ~46 repos' archives, which is why it is not a one-liner.
  (3) **`owner:` on the plan-lock schema** (`commands/_sources/fabrik-execute-plan.md` step 7);
  `check_plan_lock_release.py` is local and unsynced, so projects adopt at their own pace.
  Measured by the reporter in their repo, denominators stated: `Agent-Role` parses in 299 of 300
  commits, `Agent-Name` appears in 0 of 300, 174 of 300 commits touch a shared-append file, and 0 of
  28 plan-locks carry an owner. A path gate would therefore sit on the MAJORITY path and must fail
  OPEN on an unresolvable owner — the false-positive rate of such a gate is still unmeasured, which
  the reporter stated rather than letting their numbers read as an argument for blocking.

- **The three ledger readers disagree, and the identity advisory now depends on one of them**
  (owner: **infra**) — routed by the D-252 stop that closed the identity-advisory review rather
  than patched a third time. All executed, all with ZERO live instances today, which is why they
  are backlog and not a fix: (a) a `| D-NNN |` row inside a fenced code block is parsed as a real
  row by `session_orient.py`, `decisions.py::_rows` AND `docs_updater.py` alike, so a
  documentation EXAMPLE of a merge-owner row declares its owner (`ghost`, executed) — the advisory
  moved the key from a machine-rendered HTML comment onto a prose document, which is where this
  starts to matter; (b) an escaped pipe in a cell BEFORE the `what` column shifts the split and
  silences a real declaration — `session_orient.py` matches `docs_updater.py:1190`'s naive
  `strip("|").split("|")` while `decisions.py::_rows` consumes the escape correctly, and
  `read_merge_owner`'s docstring falsely claims it uses *"decisions.py's own cell scan"*; 0 of 956
  rows across 49 ledgers place one before cell 3 today; (c) a FIFO at `docs/DECISIONS.md` hangs the
  hook past the 10 s SessionStart budget (pre-existing in kind — the old hook hung the same way on
  `PLANS.md`); the fix is `O_NONBLOCK` plus an `S_ISREG` check. Shape of the fix: make
  `docs_updater.py` actually call the escape-aware scan its docstring already claims, teach all
  three fence-awareness, then re-copy into the hook and widen the drift pin to cover it.

- **`_count_sessions_sharing` is called outside the widened guard** (owner: **infra**) — the same
  review widened `_sessions_line`'s guard to `except (OSError, ValueError)` for the NUL class, but
  the helper is invoked from `main()` and its own loop still catches `OSError` alone. No reachable
  trigger was found (`Path.is_dir()` swallows `ValueError`, symlink targets cannot carry NUL), so
  it is latent — but it is the exact asymmetry the commit just paid to close.

- **`docs/workstation/hooks-index.md` still says the mesh has FIVE Stop causes; it has six**
  (owner: **infra**) — pre-existing, and the identity work rewrote that very table cell twice
  without fixing it. One-line correction on the next hooks-index pass.

- **The identity advisory's truncated-owner class is NOT closed, and the review said it was**
  (owner: **infra**) — routed by the D-252 stop after the closing round confirmed it. Two halves,
  both executed by an author-blind seat. (a) The partial-line drop branches on a `stat()` size taken
  BEFORE the read, so a ledger crossing 64 KiB between the stat and the read gets a full-window
  truncated head with the drop skipped — **1,703 of 87,919 reads (1.9%) rendered `alphab` for
  `alphabravocharliedelta`**, reproduced on a second run at 1,518/46,244. Fix: branch on the bytes
  actually read (`len(head) == _LEDGER_WINDOW_BYTES`), which drops the rate to 0.84%. (b) The
  residue is a plain non-atomic append: `docs_updater.py:2063` writes the ledger with
  `write_text`, no temp+rename, so a **185-byte** ledger renders a truncated owner at 2.8% — the
  same before and after this review's window work (28,224/992,946 vs 21,859/783,167). The delta did
  not move it and the CHANGELOG's claim that the class was closed was wrong. Real fix: accept a row
  only when its source line ended on a newline, and make the ledger write atomic.
- **Five behaviours of the identity advisory are ungraded** (owner: **infra**) — every one proven by
  a surviving mutant against all 44 graders: the TAIL-side partial-line drop; dropping the worktree
  conjunct from the duplicate-bullet suppression (which SILENCES the worktree case the code claims
  to preserve); un-threading the shared `live` count; setting `live = 2` on the exception path
  (fabricating "2 sessions share this main checkout" on a NUL cwd); and swapping the two bullets so
  the "bullet below" pointer points up. Also: `len(cells) < 4` -> `< 3` survives, and the render cap
  `[:32]` -> `[:64]` survives because the grader asserts `"a"*32 in out`, which a 64-cap satisfies.
  The positive grader for the headline fix is itself under-sized — its fixture is 1.51 windows, so a
  mutant reading the SECOND block instead of the end passes; the hub's own ledger is 6.3 windows.
- **The hook and `docs_updater.read_merge_owner` disagree on any ledger wider than two windows**
  (owner: **infra**) — the hook reads head+tail, the updater reads the whole file; executed, hook
  `''` vs updater `('deepowner','D-901')` on a 4.56-window ledger. On the hub's 415.8 KB ledger the
  blind middle is ~287 KB. Belongs with the three-readers row above.
- **`main()` now scans `/proc` unconditionally** (owner: **infra**) — b5c01855 returned before
  scanning for hub, named and worktree sessions. Measured at 653 pids, median of 9: hub named
  36.9 -> 46.5 ms, hub unnamed 34.8 -> 44.7 ms; the intended saving is real elsewhere (unnamed
  project 59.5 -> 47.5 ms) but the code comment names only the saving. Make `live` lazy or memoised.
- **8 of 44 graders in `tests/test_session_orient_hook.py` pass against a dead hook** (owner:
  **infra**) — six pre-existing, two added by this work; they assert absence with no positive
  control. The file's own convention is `assert "ORIENT" in out`. Add it to all eight.
- **The drift-pin grader reads its two sources from the LIVE tree** (owner: **infra**) — three
  sessions edit this repo concurrently, so the pin scores a moving target; it should read them at a
  pinned SHA. Reported by the closing seat as machinery, not a defect in the code under review.

### Self-naming identity — the residue of the D-271 build (2026-09-16)

- **Two sessions can still hold one agent name, and nothing downstream catches it** (owner:
  **infra**) — `whoami_agent.py --force` deliberately overrides a live holder, which is the
  sanctioned escape, but `check_commit_trailers.py::_warn_agent_name_mismatch` reads
  `CLAUDE_AGENT` directly and never consults the binding, so a session named with `--as` gets NO
  mismatch check at all — not merely a missing cross-session one. Executed: two sessions bound to
  one name both sign consistently and the check stays silent. Shape of the fix: teach that check
  the resolver, then compare the SIGNED name against the store's live holders rather than against
  this session's own resolved name. ⚠️ The `agent-identity.md` doc claimed this was already routed
  here before this row existed; that claim was false and this row is the repair.
- **`force` is write-only** (owner: **infra**) — the flag is recorded on the row and read by
  nothing. Either surface it (the SessionStart advisory is the natural reader) or drop the field;
  an audit trail nobody reads is not an audit trail.
- **The two SessionStart hooks and `check_commit_trailers.py` are untaught** (owner: **infra**) —
  D-271 shipped the writer, the resolver and `command_run.py` only. Until the hooks are taught, a
  session that names itself mid-flight gets attribution immediately but its role charter waits for
  the next start.

- **`whoami_agent.py` residue routed by the D-252 stop** (owner: **infra**) — the review closed on
  the scope-growth stop after two consecutive rounds confirmed only defects inside its own fixes
  (4 of 4, then 10 of 10). All 34 confirmed defects are fixed; these are the RECORDED items the
  seats raised one hop out, none of them reachable in normal use, none patched a third time:
  (a) a **SIGKILL** mid-`_write_rows` still leaks `<store>.tmp<pid>` — a `finally` cannot run on
  SIGKILL and `scratch_sweep.py:59` prunes nothing in that directory; cheap fix is to unlink stale
  `*.tmp*` at the top of the locked section. (b) Rows written by the pre-`pid_start` build keep the
  **recycled-pid false refusal** by documented backward compatibility — the store is per-box and the
  old build was live for hours, so the exposure is small but real. (c) **`--force` with no `--as`**
  is still a silent no-op at rc 0 — the argparse mutex covers `--as`/`--who` but not this. (d)
  Re-binding the **same** name appends a duplicate row every time; only the 30-day trim reclaims
  them. (e) `os.replace` silently converts a **symlinked store** into a regular file while
  `_append_row` writes *through* the link — two write paths, two behaviours for one store.

## [infra] Round zero legislates for consumers that may never reach it, and rule (5) speaks only to checkers and gates

`commands/_fragments/term-coverage.md:16` frames the round-zero probe as "the orchestrator's OWN
pre-pin probe … before any finder sees a delta", and line 14 says a certification gauntlet "runs a
DELTA round only where its own text names one as such" — so a gauntlet may never reach round zero
at all, while line 14 also states that every obligation below "binds all five consumers alike".
Two of the five consumers (`/fabrik-user-test`, `/fabrik-service-test`) are gauntlets.

Rule (5)'s governing subject is "a fix to a checker or a gate". A gauntlet is neither, so the rule
is silent for them by construction. That is a defensible reading, but it is nowhere stated, and a
first draft of rule (5) tried to legislate a gauntlet's evidence mode and was wrong twice in two
rounds: it named a rendered screen, which `/fabrik-service-test` ("a system with no screen",
`commands/_sources/fabrik-service-test.md:9`) never produces; then it named screen-or-payload, which
a `file-worker` certification also never produces — its evidence is a job record
(`fabrik-service-test.md:167`), and a rasterized PDF deliverable is a third shape again
(`commands/_fragments/cert-visual-deliverable.md`).

RESOLUTION, when someone takes this: decide whether round zero binds gauntlets at all, and say so
in line 14's parenthetical — which currently enumerates "(the exit row, the ledger grammar, the
finder-return rule, the gates)" and never names round zero. Do NOT re-enumerate gauntlet evidence
modes inside rule (5); delegate to each gauntlet's own evidence rule or leave them out of scope
explicitly. Pre-existing — this was true before the rule (5) edit and is not a defect that edit
introduced. Owner: infra.

Also still open and deliberately unmarked in the `/fabrik-review` change queue: row `1788875064`,
which asks that the CLOSING round build evidence outside the module's own suite, including that a
grader whose outcome depends on an environment privilege ASSERT that privilege first. Rule (5) does
not carry it — wrong round, wrong subject — and the row's near-synonymous wording ("outside the
module's own suite" vs rule (5)'s "never only from the test file that ships beside the module")
makes it easy to mark answered by accident. It is not answered.

## [infra] The restatement rule enforces a pointer's FORMAT but never its FIDELITY

`commands/_fragments/term-coverage.md` rule (3) now says that when review residue is a sentence which
restates, counts or partitions what another artifact owns, the rewrite is a DELETION — "the sentence
goes, replaced by at most a pointer to where the fact is re-derivable, never by a re-cut of the
claim". A closing review seat CONFIRMED the gap that wording leaves: nothing requires the pointer to
actually RESOLVE to the fact at the moment of the edit.

The cheapest bypass it opens: delete the restating sentence, drop in a plausible pointer
(a bare `see <path>:<line>` at whatever looks plausible) aimed at a target that is stale, wrong, or itself another
restatement one hop away. The letter is satisfied — the sentence is gone, no citation was appended to
a surviving sentence — and the fact is still not re-derivable where the pointer says it is. Contrast
rule (2), which for its own case mandates RUNNING `check_review_hygiene.py --surface <pin> --claim
<term>` and reading each mirror before the pin; rule (3)'s pointer has no equivalent.

RESOLUTION when someone takes this: the seat's own four-word candidate is "…re-derivable AS OF THE
PIN", which at least dates the claim; a stronger form would require the pointer be opened and the
fact seen there before the pin, the way rule (2) requires the sweep be run. Do NOT simply re-cut the
existing sentence a third time — this residue has already survived two consecutive delta rounds, and
rule (3) itself says the next edit is a rewrite in one batch, not a third patch.

NOT a defect this edit introduced in the sense of regressing anything: the clause is a net
improvement and the gap is narrower than what it closed. Routed under the D-252 scope-growth stop
(rounds 2 and 3 both confirmed only own-fix defects: 2/2 then 1/1), which is why this is a backlog row
rather than a fourth round. Owner: infra.

## [infra] Three CONFIRMED mailed defects on unlocked paths, deferred at the quota band — not blocked, just unstarted

Triaged 2026-09-17 during a full mailbox pass (77 → 12). Each is confirmed, each target is FREE of any
active plan-lock, and each needs a code change plus its own review pass — which is why they stopped at
the AMBER band rather than being half-landed. Four OTHER mailed defects from the same pass DID ship
(`5f39fd5f4`, `d429cd6bd`).

1. **`docs_updater.py --adopt` tags every backlog row as live work** (trade-intelligence,
   `01M2MY0D99TZ6K`). `_classify_backlog_row` skips only the legend table and header/separator rows, so
   it has no notion of a WORK ITEM; its only "done" signal is strikethrough, which no project's backlog
   actually uses. Measured there: 232 rows written, 224 of them backlog-row tags. Destination:
   `scripts/docs_updater.py`, and the real question first — what IS the done signal, given strikethrough
   is unused fleet-wide. Do not add a second tagging pass before answering that.

2. **`docs_updater.py`'s staleness gate watches 7 of 26 project docs** (site-provisioner,
   `01M2NJGZGV20WP`). Every defect in the other 19 is invisible to a two-command sweep. Destination:
   the same file; widening the watch list is the easy half, and the fire rate over the other 19 across
   ~46 repos is the half that decides whether it is armed (FIX DIRECTIVE 5).

3. **`.windsurf/rules/core/40-documentation.md` retires the only complete API reference** in favour of
   a `/docs` endpoint that does not carry the same content (site-provisioner, `01M2NXHVCS9WYJ`). ⚠️ The
   reporter filed THREE self-corrections to their own denominator on this thread (`19 of 45` → `19 of
   46` → `19 of 65`, the last noting the two sets are DISJOINT and the finding gets STRONGER). Whoever
   takes it re-derives the ratio themselves rather than inheriting any of the four numbers. The rule
   file is free of the review-convergence lock, which owns only `core/62-using-subagents.md`.

ALSO WORTH A READER, from the same pass — the kaizen daily collection reports
**`premature_stop_rate: 61% (379/620)`**, stop verdicts whose cause is a run-record or promise stall,
and **`terminator_spam: 1.19`** (>1.00 is spam). Those are fleet-wide measurements of agents stopping
before the work is finished and emitting terminator blocks more than once per run. The operator raised
the same complaint about this window directly on 2026-09-17. The number is already being collected and
nothing reads it; that is the gap, not the number.

## [infra] The READ-budget exemption for MERGED tickets is EARNED by measurement — and the right key is git-derived, not the ✅ row

web-ecommerce-factory asked for the exemption, I asked for the fire rate, and they measured it
(`01M2P2Z7B7M1PC` and its same-hour erratum `01M2P30TXGWCRP`, which corrected its own population from
one live set to six before I could). **18 tickets over `READ_BUDGET_BYTES` across 6 live sets / 59
tickets; 16 carry a ✅ merged Board row, 2 do not.** So the exemption removes the check on 16 tickets
no cold coder will ever read again and leaves both unmerged ones — which is exactly the shape that
justifies removing a check.

WHY IT IS NOT A ONE-TOKEN EDIT, measured here 2026-09-17:
`_sizing_severity` already returns WARN in the GATE path for DRAFT / IN-PROGRESS / EXECUTED /
BLOCKED, and ERROR only for CONVERGED. Their 18 ERRORs were all at **cli** severity. So:
· a GATE-path-only exemption bites only on CONVERGED spines — **3 of 19 live plan-set spines
  fleet-wide** — and does essentially nothing for the problem they measured;
· a cli/flip exemption is the loosening of the author's own path, and they explicitly did NOT ask
  for it ("keep the cli/flip context strict if you would rather").

THE KEY IS THE DECIDING QUESTION, and their second proposal answers my Cobra objection outright. The
✅ row is SELF-REPORTED, so keying an exemption on it lets a ticket exempt itself from a dispatch-time
guard by editing its own row. They noted it is not free to forge (the emit-time gate errors on a merge
commit whose Board row is still ⬜, and D5 makes the Board flip ride the squash commit carrying the
ticket's `Agent-Task` trailer, so a ✅ without a landed commit shows in `git log`) — and then offered
the better key: **derive "merged" from git** — a commit carrying `Agent-Task: T##` touching the
ticket's `Touches` paths within the lock's `baseline_commit..HEAD` window. That is not self-reported,
so the bypass closes and the exemption becomes defensible in cli/flip too.

DESTINATION: this is a NEW MECHANISM (git-derived merge detection inside `check_plan_tickets.py`), not
a list edit, so it is spec/plan work rather than a patch — `/fabrik-spec` on the key, then the change.
Whoever takes it has the fire rate already: 18/59 over budget, 16 merged, 2 not, across six live sets
in one repo, plus the fleet figure that only 3 of 19 live spines are CONVERGED. Do NOT ship the
✅-keyed version as a shortcut; it is the half that fails the Cobra check. Owner: infra.

## [infra] The private-index recipe has a SECOND cause of the empty-commit trap, and it is the same root as the `set -e` heredoc finding

Two repos found the two halves of one defect on the same day, independently, and neither can fix it:
`CLAUDE.md` and `templates/governance/CLAUDE.md` are both owned by the active plan-lock
`2026-09-09-plan-1-review-convergence-redesign`.

**HALF ONE (web-ecommerce-factory, `01M2JK0SDZ9HBF`):** inside the Claude Code Bash tool, `set -e`
does NOT abort the script when a `python3 - <<'PY' … PY` heredoc exits non-zero — the following lines
run.

**HALF TWO (fabrik-lib, `01M2P2XHFHM1P2`):** the consequence, executed in the recipe itself. Their
build script's assertion failed, so the scratch file was never written; `hash-object` returned an
EMPTY blob; `update-index` errored; **and the shell kept going.** `commit-tree` then produced a commit
carrying the PARENT's tree, `update-ref` returned rc 0, and HEAD moved to a commit whose full message
claimed two fixes it did not contain. Unpushed, and caught only by step 5a's `ls-tree` returning the
PREVIOUS blob.

⚠️ WHY THE RECIPE DOES NOT COVER THIS: it documents the empty-`$new` trap and attributes it to
SPLITTING the run across two shells, because `GIT_INDEX_FILE` does not survive a new process. That is
a real cause and it was NOT theirs — they ran it in one shell exactly as instructed. This is a SECOND
cause with an IDENTICAL symptom. Every guard the recipe lists watches the INDEX or the REF; none of
them stops execution when the CONTENT step fails, and `commit-tree` is perfectly happy to commit an
unchanged tree.

THE FIX, their words and it is one line: **assert the blob is non-empty and ABORT before
`commit-tree`.** That is upstream of every existing guard and costs nothing.

THE RECOVERY SHAPE, worth recording because the reflex is wrong: they recovered with a
compare-and-swap — `update-ref refs/heads/<branch> <parent> <the empty commit>` — NOT a reset. The CAS
would have REFUSED had a sibling committed in the window, and the working tree carrying that sibling's
live hunk was never touched. `git reset --hard` is the reflex here and would have destroyed it.

ALSO THEIRS, at their own expense and worth keeping: the assertion that failed was WRONG, not the
edit — their new text contained the old sentence as a prefix, so `assert old not in out` could never
hold. A bad guard cost more than the bug it guarded. Same shape as the `find_spec` probe in this same
mailbox pass that passed for the wrong reason.

DESTINATION: `CLAUDE.md` § Behavior, the private-index recipe, when the lock clears — add the
non-empty-blob abort at step 2 and name the second cause beside the split-shell one. Both mail ids
above carry the executed evidence. Owner: infra.

## [infra] /fabrik-execute-plan's phase-gate verdicts: three rows, three rejected cuts, and the referent that killed them

`/fabrik-command-improve` ran over `/fabrik-execute-plan`'s queue on 2026-09-17 and closed with **NO
EDIT**. Three review rounds (9, 3 and 5 CONFIRMED) killed three successive cuts, the D-252 scope-growth
stop fired at 3/3 → 5/5 own-fix, and the working-tree edit was reverted. This row exists so the next
attempt starts from the evidence rather than from a fourth draft. Rows still UNANSWERED:
1788820659.8885953, 1789477812.4539094, 1788815558.909572 (and 1788799311.0929735, below).

**WHAT THE THREE ROWS ACTUALLY DESCRIBE** — one failure: an agent acted on a gate's `status` without
establishing what the gate executed. A suite under an interpreter missing a dep; a `-x` stop naming one
failure of an unknown-sized list; a green mechanism check read as evidence about DATA.

**THE ROOT CAUSE OF ALL THREE REJECTED CUTS — read this before writing any replacement.** The line the
edit kept landing on is `run phase validation gate (bash checks from the plan)`. Its subject is a
**plan-authored command**, NOT `final_gate.py`. `commands/_sources/fabrik-plan-after-chat.md:498-505`
defines a per-step gate as "the exact command + the expected result" and reserves `final_gate.py` for the
plan's FINAL step; a live hub plan confirms it — `docs/development/plans/archived/2026-09-16-plan-1-quota-posture.md:130`
is `uv run pytest tests/test_governance_template_split.py -x --tb=short` and `:249` is the same without
`-x`. So every `final_gate.py` fact is FALSE of that line's actual subject: a `uv run pytest` gate emits
no `warnings`/`skipped_checks`/`status` JSON, runs under uv's project env rather than
`final_gate.py:69-79`'s resolution, may or may not pass `-x`, and prints no re-run remedy.
**A replacement must either be machinery-free, or name its referent in each sentence.**

**EXECUTED EVIDENCE, so it is not re-derived** (all verified by the orchestrator, not taken from a seat):
- An UNGUARDED missing import is a collection ERROR (`Interrupted: 1 error during collection`, rc 2) that
  ABORTS the run — never a silent green. Only a GUARDED import (`pytest.importorskip`, a conftest
  `except -> skip`) yields `1 passed, 1 skipped` at rc 0. Cut 1 asserted the opposite.
- `final_gate.py:69` `PROJECT_ROOT = Path.cwd()`; `:70` `VENV_PYTHON = PROJECT_ROOT/".venv"/"bin"/"python"`;
  `:79` `PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable`. So "never the interpreter
  you typed" (cut 2) is FALSE in the else branch, and it is the CWD's venv, not the repo's. 22 of the 45
  git repos under /opt have no `.venv/bin/python` (git-aware count; a `[ -d .git ]` sweep answers 20 of 43
  because it misses two linked worktrees whose `.git` is a FILE).
- `final_gate.py --json` keys are exactly: advisory, blocking, checks, failed, failures, passed, skipped,
  skipped_checks, status, tier, warnings. There is no "tail" key (cut 2 pointed at one). `skip_advisory`'s
  text reaches `warnings` only while the leg stayed GREEN (`:3058` filters on `ok and …startswith("⚠")`);
  a RED leg's untested remainder lands in `failures`.
- `--lean` returns at `:1105` BEFORE the pytest leg at `:1260`, so a lean envelope has no pytest row at
  all — `skipped_checks: []` is not evidence the suite ran. Tier 2 does carry it: 39 of 45 /opt repos have
  no `.fabrik/run-pytest` sentinel.
- `final_gate.py:1273` hardcodes `-x`; `:1317-1319` records "`-x` STAYS — it is a deliberate cost
  decision". `:1320-1327` already prints the no-`-x` re-run remedy, and `skip_advisory` (`:196-236`)
  already prints "this green SKIPPED n test(s) … asserts NOTHING about them", counting deselected too.
  **Both remedies the three rows ask for already ship as gate runtime output** — which is why a
  restatement in a command's own words is the wrong form; a pointer that names its referent is the right
  one. Mail 01M2PT1G6K2EXFDBDM6TMBHVYQ carries the doc half of this to infra.

**OTHER RESIDUE FROM THE SAME RUN:**
- **The phase-gate lines are invisible in DISPATCHER mode.** That Execution Loop is headed `PHASE MODE
  ONLY — in dispatcher mode this entire loop is REPLACED`, so a spine+ticket run reads none of it. D4's
  per-ticket gate and D7 have no equivalent. Fix ONCE for both modes; mirroring is two sources of truth.
- **Verdict 1788815558.909572 asked for its rule "in the review contract"**, and the command has two
  plausible homes (§ Reviewer & fix-dispatch discipline, Finish step 1) with neither canonical. Pick one.
- **Pin line 413 (`run FULL final gate: python scripts/final_gate.py --json`) is the ONE place where every
  envelope claim above is unconditionally true, and it carries none of the advice** — the cheapest correct
  home for a referent-bound version.
- **Four of the six `final_gate.py` references in that command source invoke a bare `python`** (counted
  with `command grep`), ambiguous on any box with a `.venv`. Not respelled: `tests/test_kaizen_hook_emitters.py`
  embeds the string as a fixture and one occurrence is the completion-block template.
- **`scripts/final_gate.py` defects found in passing** (the file is owned by the ACTIVE
  `.fabrik/plan-locks/2026-09-09-plan-1-review-convergence-redesign.json`, so filed not fixed): `:1326`
  prints its own remedy as a bare `python -m pytest` while `:79` deliberately resolves an interpreter;
  `:1322-1324` asserts "the first one, not the only one" whenever `stopping after` appears, which pytest
  emits even when the failing test is the LAST collected; `:1277-1279`'s green `pytest (NOT RUN)` branch
  for `"No module named pytest"` looks unreachable behind `_toolchain_missing` at `:2877`, which exits
  with a third envelope shape carrying no `warnings`/`skipped_checks` at all.
- **Queue row 1788799311.0929735 stays UNANSWERED**: a mandatory live-box census at Finish for any
  mechanism acting on box state. Same family, different phase of the run.

The rejected text and all three review reports are in this run's scratchpad; the commit body of this row
is the durable copy.

## [infra] VERDICT: the gate-verdict rule does NOT belong in /fabrik-execute-plan — fleet-synced governance already owns it

Second attempt, 2026-09-17, after f99153c84 closed the first with NO EDIT. Also closes NO EDIT. Four
cuts have now been written and all four were CONFIRMED wrong by review (rounds of 9, 3, 5 and 7). This
row records the SURFACE verdict so a fifth is not attempted: **the three verdict rows cannot be
answered in this command source, because the content is owned by `templates/governance/CLAUDE.md:211`
— fleet-synced and auto-loaded in every project session — and any version written here is a second
source of truth by construction.** Rows still UNANSWERED: 1788820659.8885953, 1789477812.4539094,
1788815558.909572.

**WHAT ATTEMPT 2 TRIED AND WHY IT FAILED.** Attempt 1 died on a REFERENT error (final_gate.py facts
attached to `run phase validation gate (bash checks from the plan)`, whose subject is a plan-authored
command). Attempt 2 SPLIT the claims — referent-free judgement at the phase gate, machinery at the
FULL-gate line whose subject IS final_gate.py. The authoritative seat refuted the split itself:
- The phase-gate line still named four pytest-only referents (`importorskip`, `conftest`, COLLECTION,
  "tests") on a line whose population is not pytest. Measured over `docs/development/plans/**.md`:
  **58 of 63 GATE blocks contain no `pytest` at all** — they are `curl -sI`, `ls -la`, `grep -c`,
  `npx jscpd`, `fabrik apply`, `final_gate.py --check`. The paragraph was unexecutable for ~92% of
  the lines it governed.
- The machinery line was a DRIFTED restatement of `templates/governance/CLAUDE.md:211`, deleting that
  row's `(or CI names pytest)` disjunct.
- It also named the wrong JSON key (below).

**THE TWO EXECUTED CORRECTIONS, now mailed as 01M2Q5PJ2DK33V0N2EFCWRAPW3 (threaded to
01M2PT1G6K2EXFDBDM6TMBHVYQ), both against files this lock owns:**
- `pytest (NOT RUN)` is in `WARN_ONLY_CHECKS` (`final_gate.py:327-340`), so `--json` routes it to
  **`advisory`** (`:3023-3027`); `warnings` collects only ⚠-prefixed output (`:3058-3062`) and is
  EMPTY for this case; `_summarize_skipped` (`:378`) strips the marker so `skipped_checks` carries the
  bare name `pytest`, never the REASON. Both CLAUDE.md copies send the reader to `skipped_checks`
  alone, so nobody reads the gate's own "THIS GREEN ASSERTS NOTHING ABOUT THE TEST SUITE"
  (`:1340-1350`). Executed by importing the module.
- The arming clause is short two disjuncts: `final_gate.py:1261-1271` requires `tests/` AND
  `_ci_runs_pytest()` AND (sentinel OR no diff OR a `src/`/`tests/`/`scripts/` diff). "Absent both …"
  is wrong — 8 /opt repos run the leg with NO sentinel (6 armed, 10 with CI naming pytest).

**IF SOMEONE LATER WANTS THE COMMAND-SIDE HALF ANYWAY**, two narrow pieces survived review and are the
only ones worth writing, both referent-free and neither yet attempted:
- ts 1788820659 wants a RECORDING surface, not a private act. The existing phase report line
  (`report ONE line: ✓ Phase X — …`) is the natural home: `✓ Phase X — gate <cmd> under <interpreter>,
  <n> ran / <n> skipped`. "Establish the interpreter" with nowhere to write it is why the phase report
  can still be silent about it.
- ts 1788815558 asked for its clause "in the review contract". It exists nowhere in
  `commands/_sources/` or `commands/_fragments/` — `command grep` for `MECHANISM|plumbing ran|asserts
  nothing` returns only the rejected cut. `commands/_fragments/term-coverage.md` round-zero rule (5) is
  the natural home, since that rule already governs how a grader observes its subject.
- A third, smaller: the phase gate is invoked again at two MERGE-PROTOCOL sites in the same file
  (`Run the phase validation gate`, `Run the validation gate for EACH phase after merge`) which carry
  none of this guidance — and `check_review_hygiene.py --claim` cannot find those mirrors, because it
  sweeps only the surface file despite both fragments describing it as the cross-file mirror sweep.

The rejected text of both attempts and all seven review reports are in the runs' scratchpads; this row
and the two mails are the durable copies.

## [infra] check_doc_links.py's bare-ref matcher is narrower than its subject — widening MEASURED, landing needs a ratchet

Reported by web-ecommerce-factory as `01M2Q61CBECCQFB7YWQW1Z6EE7` (validated at source, replied
`01M2QBVYCCNBK3G9RYJKJENMA1`). `scripts/enforcement/check_doc_links.py:95-97`'s `_BARE_RE` matches the
prefixes `docs|scripts|src|specs|configs|templates|.windsurf` and the extensions
`md|py|sh|yaml|yml|json|txt` — so NO doc citation of a test path, and no `.ts/.tsx/.mjs/.cjs/.astro`
reference, is ever scanned. A `<!-- link-base: … -->` marker cannot rescue a ref that is never matched.
The file is owned by NO active plan-lock; edit rights are not the obstacle.

**FIRE RATE, measured 2026-09-17 by DRIVING THE REAL CHECK** (imported the module, repointed its
module-global `REPO` per repo, ran `main()`; harness first validated against the live CLI on the hub —
`OK — 0 broken of 2653 refs across 228 docs`, identical both ways). Widening = add `tests` to the
prefix alternation and `ts|tsx|mjs|cjs|astro` to the extensions:
- population 45 git repos under /opt (git-aware enumeration)
- **220 NEW broken refs surface across 39 of the 45 repos**
- **0 false positives in the sampled set** — every sample is a genuine stale or wrong-path cite. The
  hub's `INDEX.md` cites `tests/capture_golden.py` and `tests/test_flywheel_safety.py`, which live at
  `scripts/kilo-benchmarks/tests/`; `tests/test_derive_cost.py` and `tests/test_lcb_smoke.py` exist
  nowhere.
- **the hub itself gains 14**, in `INDEX.md`, `docs/CAPABILITIES.md`, `docs/FEATURES.md`,
  `docs/STRATEGIC_BACKLOG.md`, `docs/orchestrator/orchestrator-cockpit-decisions.md`,
  `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md`, `docs/workstation/wsl-startup-inventory.md`.

**WHY IT IS NOT A REGEX COMMIT.** `check_doc_links.py` is BLOCKING — `final_gate.py:1965-1970`,
"links + index are blocking (the tree was converged to zero drift and must stay there)" — and it is on
the governance-sync trigger surface, so one hub commit distributes it fleet-wide on the post-commit
sync. Landing the widening as-is reds the COMPLETION GATE in 39 repos at once for 220 pre-existing doc
defects, in repos the hub must not edit (cross-repo HARD STOP). Same shape as the deferred pytest-leg
promotion ("would flip every repo with a red-but-unrun suite red on landing day").

**DESTINATION: `/fabrik-spec`, with this measurement as its input** (do not re-derive it). Two shapes,
both already precedented in this repo: a per-repo baseline ratchet that may only go DOWN — the pattern
of `.fabrik/doc-script-baseline.json`, `.fabrik/decision-shape-baseline.json` and the lint ratchet,
where the first run seeds today's count, blocks nothing, and the number can only fall — or a
WARN-then-BLOCK window. The ratchet lands green everywhere on day one while making every NEW bad cite
blocking, and puts no repo on a deadline. Its cobra (D-253) is written down here in advance: the
cheapest way to satisfy a doc-link ratchet without producing the outcome is to DELETE the citation
rather than fix it, which passes a count-based ratchet — so the ratchet keys on the SET of unresolved
refs, not the count, exactly as `.fabrik/decision-shape-baseline.json` does.

**CARRIED FORWARD, reported and not addressed:** `_resolves()` tries the repo root BEFORE a declared
`link-base`, so a mistyped repo-root ref can be masked when a same-relative file exists under the site
root. Their words, my agreement, nobody's fix yet.

**SEPARATE AND SMALLER, owner infra:** the hub's own 14 cites above are real debt TODAY — they are
simply invisible because the matcher never looks. They do not need the spec; they need one docs pass.

## [infra] /fabrik-review-scoped's missing scope-growth exit — the BRANCH does not belong in the command; three rounds, 25 confirmed, count rising

`/fabrik-command-improve` ran over this command's queue 2026-09-17 and shipped only ONE line: step 4's
`round` template now carries `--own-fix`. The intervention the queue asked for — naming the scope-growth
stop beside step 5's route-up (ts 1789580959.8031142) — was written, reviewed three times and REVERTED.
That row stays UNANSWERED. So does 1789439248.852039, which targets `command_run.py`'s advisory.

**THE DEFECT IS REAL AND STILL OPEN.** Step 5 escalates to the heavy `/fabrik-review` after "the SECOND
consecutive round that confirms defects" — which is also the exact signature of a loop reviewing its own
fix. So the fleet's most-run review command, the pass the Stop hook mandates for every spontaneous
code-editing session, routes self-reviewing loops to the most expensive exit it has. Measured before the
attempt: `own-fix` appeared 0 times in the rendered command against 1 in each of fabrik-review,
fabrik-repo-review, fabrik-conformance-review and fabrik-rules-review.

**WHY THE FIX WAS REVERTED — the shape, not the wording.** Confirmed counts across the three rounds ran
7 → 5 → 13, rounds 2 and 3 both 100% own-fix, and `command_run.py` printed the D-278 scope-growth
advisory on its own. The count RISING is the signal: each fix generated more surface than it closed.
The cause is structural — this command encodes its exit in SIX places (the `description` frontmatter,
step 4's round template, step 5's trigger, step 6's close gate, the `Profile: small` carve-out, and the
fleet-synced `.windsurf/rules/core/50-code-review.md`), so any new BRANCH must be mirrored consistently
into all six, and each mirror is a fresh contradiction surface. Three rounds never reached a fixed point.

**WHAT THE ATTEMPT PROVED, so the next one does not re-derive it:**
- Rendering `term-coverage.md` into this command is REFUSED on a measurement: 25,697 B against the
  command's 16,399 B (+157%) on the command whose identity is being the LIGHT pass.
- A CWD-relative `commands/_fragments/...` pointer is DEAD off-hub: that directory is absent in 5 of 5
  project repos checked, and this command renders box-wide. Use the absolute `/opt/fabrik/...` path with
  step 4's own caveat, as step 4 already does.
- `check_review_coverage.py::_scope_growth_exit` is INERT for this command (it emits no receipt, by its
  own step 4) and is keyed on the superseded D-252 shape.
- A single-evaluation branch cannot express the fragment's SLIDING two-of-three window: round 1 is the
  full pass at `--own-fix 0` and permanently occupies a slot that can never qualify, so a one-shot
  evaluation at the trigger degenerates to a consecutive bar — the very shape the fragment's COBRA note
  measured as dodgeable.
- Any branch needs an arm for a deferral round that CONFIRMS ZERO, or a converged loop escalates.
- The `--own-fix` integer is UNFALSIFIABLE here: the fragment requires it EVIDENCED per finding
  (`own-fix: round k`, checkable against that round's md5 pair), and this command persists no report to
  carry the citation. That is a real deviation and must be stated openly, not left silent.

**DESTINATION: `/fabrik-spec`,** because this is a control-flow change across six mirror sites plus a
fleet-synced pack, not a wording edit. Two constraints for it: the synced pack must carry the stop's FIX
and re-verify duty (a project agent cannot read the hub fragment, so shipping the halt without its duty
licenses stopping a loop whose rounds still confirm), and the pack defines neither "own-fix" nor the
bar's arithmetic today.

**SEPARATE AND SMALLER, now unblocked:** `command_run.py` still computes the superseded equality and its
`--own-fix` help still reads "omitted = not stated, which asserts nothing"; `check_review_coverage.py::_scope_growth_exit`
is a third site on the superseded bar; and the fragment, D-278 and `command_run.py` give THREE different
answers for an omitted round (never-qualifies / read-as-own-fix / breaks-the-window). All were lock-owned
this morning and are free now. Mail 01M2QCJBYV9F8ZKPR9KMNVV6FC.

## [infra] Two seat-harness costs a partitioned review pays 3× per round — one sends a seat at a forbidden path, the other makes a compliant seat look stalled

Filed by fleet from two native `fabrik-reviewer` seats in the quota-posture Finish review
(`01M2QGRXNCHY68HHD8PG4WXXDC`, 2026-09-17). Both are MACHINERY, not repo defects, and both are
silent-cost shapes.

**(1) The Bash tool's overflow target follows the SESSION, not the scratchpad the brief pins.** A seat
`cat`-ed a 53 KB pin; the result overflowed to
`/home/ozgur/.claude-fleet/active/projects/<repo-key>/<session>/tool-results/<id>.txt` — under
`$HOME/.claude*`, the zone every seat brief forbids because a seat that reads it stalls (the
subagent-home-dir-hang class). **Confirmed first-hand, not taken on report:** this very session's
overflows land at exactly that path while its scratchpad is `/tmp/claude-1000/…`. So a seat that obeys
the brief's scratch pin can still be handed a path the same brief forbids, with no warning.

**(2) A Bash safety-classifier outage has no documented fallback for a read-only finder.** During one
delta the classifier (`claude-sonnet-5[1m]`) reported "temporarily unavailable (connection failed)" then
"(timed out)" twice mid-pass, refusing `git worktree`/`pytest` invocations it had allowed minutes
earlier. Each cost a retry and a split of a compound command; nothing tells a seat whether to retry,
route around, or report.

**Destination — ONE file, both notes:** `commands/_fragments/subagents-core.md:5`, the line that already
carries the git-verb prohibition every brief renders. The leanest cuts, from the reporter: (a) read a
pin with `sed -n`/`head`, never `cat` a file over ~20 KB, because the overflow target is not yours to
choose; (b) a classifier refusal on a command allowed moments earlier is an OUTAGE — retry once after
30 s, then report it as MACHINERY, so the seat neither loops nor silently drops the step.

**Why it is not a one-line edit anyone can take blind:** `subagents-core.md` renders into the whole
review family, so the sentence must be true for every consumer (the fragment-consumer enumeration rule),
and a size threshold stated as a number in rendered text is a moving number unless it is a rule of
thumb — write it as "never `cat` a pin, range-read it", not as a byte budget nobody can check.
**Blast radius:** every partitioned review dispatches 3+ seats per round, so each cost lands 3× per
round. Take it in the next `/fabrik-command-improve` run over the review fragments.

**ADDENDUM 2026-09-17, same day — reproduced by MY OWN grounding seat, with a number the original
report did not have.** An Opus `fabrik-researcher` seat on this hub session lost **three** fetch results
to the same sink: `mcp__exa__web_fetch_exa` auto-persists a result over roughly 50 KB to
`/home/ozgur/.claude-fleet/active/projects/<repo-key>/<session>/tool-results/<id>.json`, which its own
brief forbade it to read. The lost calls were `maxCharacters` 78,000 (77.9 KB), 63,000 (63.1 KB) and one
`web_search_exa` at `numResults 8` (54.8 KB). **So the effective reachable window is ~48 KB, not
`maxCharacters`** — a reference page longer than that has a tail no in-session arm can reach, and it
reads as ABSENCE rather than as truncation. The seat hit exactly that on ISO/IEC Directives Part 2, a
single ~200 KB XHTML (WebFetch returns 403 on iso.org), and had to downgrade one load-bearing quote to
a search-extract and SAY so. **Two concrete additions to the fix already named above:** a grounding
brief that bans `.claude` paths must ALSO cap `maxCharacters` at ~45,000 and say why, and the
fetch-routing block in the grounding-subagent definition should state the effective ~48 KB ceiling
rather than implying `maxCharacters` is the only bound.

**A SECOND, unrelated finding from the same seat — for `docs/workstation/mcp-roster.md`, not for the
brief fragments.** The `fabrik-researcher` definition's fetch-routing block says firecrawl "is not
connected on this box … Verified gone 2026-08-30", while this session's MCP server-instructions preamble
advertises a firecrawl server with `firecrawl_scrape` / `firecrawl_search` / `firecrawl_map` /
`firecrawl_agent`. The seat probed it: `ToolSearch "+firecrawl scrape search"` returned "No matching
deferred tools found". **The definition is correct in effect; the PREAMBLE is the stale surface** — an
MCP server whose instructions load while it exposes zero callable tools. Cost: one probe, plus a live
contradiction between two instruction sources a seat is told to trust. Worth one line in the roster's
§ the servers naming firecrawl as instructions-present / tools-absent, so the next seat does not
re-probe it.

## [infra] Successors routed out of the CONVERGED /fabrik-review-scoped scope-growth spec (D-281)

The spec at `docs/superpowers/specs/2026-09-17-review-scoped-scope-growth-exit-design.md` CONVERGED on
2026-09-17, closing on **D-278's own scope-growth stop** — rounds confirmed 29 · 15 · 6 · 3 · 0 at
own-fix 0% · 86% · 66% · 66%, so three of the last three qualified. Under that stop's exit the items
below were RECORDED rather than fixed, which is what let the remainder terminate.

**1. The `--own-fix` counter is a bare self-report, and the evidence field is CHEAP.** The spec's COBRA
section concedes the command has only the SOX-404(a) half — a self-report — with its stated attestation
(D-206's fresh non-authoring reader) unenforced for this command: `check_review_coverage.py`'s V11
grades a review report `/fabrik-review-scoped` never writes, and the command is absent from
`command_run.py`'s done-time report floor. The draft claimed a per-finding citation had "nowhere to
live"; that was a preference, not a structural fact — `own_fix` is stored as a bare integer on the
round row in the file D1 already edits, so an evidence field costs what the required-flag change costs.
**Destination: the build, as a stated successor, or a follow-on spec if it grows.**

**2. `check_citations_resolve.py` should reach `commands/_sources/`.** Sweeping the CLASS rather than
the two instances a seat found, **all FIVE code line-citations in `commands/_sources/fabrik-review-scoped.md`
are stale** (`command_run.py:338`, `:384`, `:398-404`, `:2288`, `:2585`) — every underlying claim true,
every pointer rotted as the script grew. The checker's `SOURCE_GLOBS` cover `docs/` roots only, so
nothing watches the corpus that ships to ~46 repos. The build fixes those five; widening the checker is
the class fix.

**3. Three wording residues, recorded under the stop and deliberately not fixed** (fixing them would
have un-quieted the closing round): § Goal's "nine sites touching" lost its object; the
`term-coverage` rejection row repeats "a 16,559 B source" after a parenthetical insertion; and Ruling
1's "a fourth was withdrawn" reads positionally where it is meant cardinally. All three are prose-only;
none changes a claim.

**4. The false-alarm side of D-278's bar is UNMEASURED on our own series.** The spec's grounding found
that adding window rules to a detector raises its false-signal rate and that the documented human
response is to keep the rule and take it "less seriously" — but the control-chart figures behind that
do NOT transfer (they assume a stationary, independent series; a convergence loop is neither). So there
is no borrowed number, and the question is open on our data: after one month, re-measure whether
qualifying rounds are followed by reviews that still find ORIGINAL-surface defects. If they are, the
stop is firing on healthy reviews and this spec moved the wallpaper rather than removing it.

## [infra] The refuted-never-reopens protection is INACTIVE on half of all scoped review runs

Operator question, 2026-09-17: *"does refuted review findings cause a new review loop in our review
commands or not? they should not."* **They should not, and by design they do not** — the exit counter
is `confirmed`, not raw findings (`scripts/command_run.py:515-520`; `check_review_coverage.py:717`
grades `_confirmed_quiet` on the receipt's last row), REFUTED and RECORDED are named non-counting
buckets, and a delta seat's brief carries the previous seat's REFUTED list verbatim so a fresh reader
cannot re-raise one. One deliberate carve-out stands: a re-raise carrying evidence the refutation does
not cover COUNTS.

**The gap is adoption, and it is measurable.** Adoption of the `confirmed` counter is STICKY — the
legacy `--findings 0` rule survives for any record whose rounds NEVER state `--confirmed`. Measured
over `~/.claude/state/command-feedback.jsonl`, window 2026-09-07..2026-09-17: of 60
`/fabrik-review-scoped` closes carrying a round series, **29 (48%) carry an explicit `confirmed`
series and 31 (51%) do not**. On those 31 the loop closes on RAW findings — where a refuted candidate
does keep it open, and where "quiet" can be reached by relabelling rather than by converging.

So the rule is right, is enforced where the counter is stated, and is silently inert on about half the
runs. **Two candidate closures, neither taken here:** make `--confirmed` required on a review-family
round the same way D-281's D1 makes `--own-fix` required (same selector, same NOTE-then-refuse
ratchet, same file — so it is nearly free if done in that build); or have the close REFUSE a terminal
verdict computed on the raw-findings fallback for a command whose contract names `confirmed` as its
exit counter. The first is cheaper and is where it belongs. **Destination: D-281's build, as a
successor item — not folded into it without the operator's word, because it widens a refusal on a
file fleet-synced to 49 dirs.**

## [infra] Three findings routed out of the D-281 build's heavy review (2026-09-17)

The build shipped D1–D5 and its heavy review CONVERGED on the D-278 scope-growth stop
(`docs/development/reviews/2026-09-17-scope-growth-exit-build-review.md`, four passes
19 → 9 → 7 → 0 confirmed). These three were RECORDED rather than fixed, each for a stated reason.

**1. `quota_dashboard.py::_FLOOR_RE` is stale against the corpus it reads — PRE-EXISTING, two
graders already red.** `scripts/sysadmin/quota_dashboard.py:1726` matches
`Floor — every \w+ dispatches ≥1 native`, written 2026-09-08 in `7178fa278`. Measured 2026-09-17:
that string appears in **ZERO** command sources at HEAD, so `_command_seat_rule(...)[0]` is False
for every command and the dashboard's seat column reports no Opus floor anywhere.
`tests/test_quota_dashboard.py::test_the_seat_rule_reads_the_real_corpus_correctly` and
`::test_the_matrix_reads_the_rendered_corpus_not_the_sources` are red on it. **Verified NOT caused by
this build** — grepped every `commands/**.md` at HEAD before any of its edits. The fix is a re-key,
and whoever takes it should anchor on a phrase the fragments OWN rather than one a reword can move,
which is the lesson D5 shipped in the same build.

**2. The fragment and the pack hedge the converging claim differently.**
`commands/_fragments/scope-growth-exit.md` says "nothing prints when the loop is **simply**
converging"; `.windsurf/rules/core/50-code-review.md` was corrected to "a loop that is **MERELY**
converging **with no own-fix residue** — a FALLING count that is mostly own-fix still prints SCOPE
GROWTH". The pack's form is the precise one. The fragment's is not wrong, but it is weaker than its
own downstream copy, which inverts the maintained-source relationship D3 exists to establish. Left
alone deliberately: the remainder round was bounded to the fixed set, and widening it to chase a
wording asymmetry is exactly what the stop had just forbidden.

**3. ⚠️ A CONTRACT CONTRADICTION that costs every read-only finder a valid probe method.**
`CLAUDE.md` § Behavior (the shared-tree bullet) mandates
`git worktree add <scratch>/probe HEAD` for any mutate-restore probe, and states that a single
copied FILE "fails in the worst direction" because graders resolve their subject by
`Path(__file__).resolve().parents[1]`. But every finder brief forbids writing git verbs — and
`git worktree add` writes (it registers under `.git/worktrees/`). **The two rules together leave a
read-only finder no sanctioned probe method.** A seat this run obeyed the brief, built a multi-file
`git show` mirror instead, and got **18 false FAILs at baseline** because cross-file agreement tests
resolved `parents[1]` into a mirror root with no command corpus — the exact false-verdict class the
worktree rule exists to prevent, reached by obeying the brief. Two candidate fixes: carve out
`git worktree add <scratch>` as a sanctioned exception in the finder briefs (it writes only under
the scratchpad and the repo's worktree registry, never the working tree), or have the DISPATCHER
create the probe worktree and hand its path to the seat. The second is cleaner and costs the seat
nothing. Destination: the review-command fragments, next `/fabrik-command-improve` run over them.

### [infra] A lesson RETIRED at its root keeps rendering from the corpus, and nothing links the two

`scripts/sysadmin/dispatch_headroom.py:156-169` fixed the root cause of the `SEATS: 0` incident —
the budget no longer caps on commit headroom unless `overcommit_memory == 2` means the kernel would
actually enforce it, and a zero-sum partition now prints its reason (`:749-753`). The feedback
verdict born of that incident (ts 1789483273.93) nevertheless asks `/fabrik-review` to carry the
lesson as prose, and `/fabrik-command-improve` duly landed it 2026-09-17. The general predicate is
sound and was kept deliberately — a tool's zero or refusal is a CLAIM to attribute before it is a
reason to stop, and that is true of every tool. But nothing in the loop notices when the SPECIFIC
incident behind a corpus sentence has been fixed at its root, so a restated incident outlives its
cause with no one watching it go stale.

Scope, measured 2026-09-17: this particular clause sits in `commands/_sources/fabrik-review.md` and
so renders to **1 of 37** commands. The exposure is larger for the fragments — **21 of 37** commands
render `subagents-core`, so the same shape landing in `commands/_fragments/` would carry a retired
lesson into 21 rendered commands at once.

Shape of a fix, unbuilt: `check_corpus_weight.py` already walks the six governance surfaces; a
sibling check could compare a corpus sentence's cited `path:line` against the CURRENT text at that
path and flag a citation whose surrounding code no longer says what the sentence claims. That is a
different check from `check_citations_resolve.py`, which only asks whether the line EXISTS.

Found by the round-1 Opus seat of `/fabrik-command-improve fabrik-review`, filed as its MACHINERY
note (F9, RECORDED — deliberately not confirmed against the edit, whose general form is correct).

### [infra] The finder-brief lesson list covers a truncated FILE and not a truncated LINE

`commands/_sources/fabrik-review.md:196` tells every finder brief *"the Read tool truncates a long
file on a token cap with NO marker — read in offset pages and confirm the last line"*. It says
nothing about the other shape: a single very long LINE. Measured 2026-09-17, `:165` of that same file
is one line of **3,161 bytes**, and both review seats dispatched over it had to be told per-dispatch
to use `sed -n '165p' | fold` or python slicing; one of them reported that the warning was the only
reason it saw the end of the paragraph. A seat that reads that line with the Read tool and concludes
from the visible half is making exactly the bounded-search error the same lesson list forbids, with
no marker telling it the read was partial. One clause on the existing lesson would close it — the
list already owns the file case, so this is an edit INSIDE it, not a new home.

### [infra] The mutation COPY and the pin dir are never linked, so a brief's room obligation is covered only by inference

`commands/_sources/fabrik-review.md:165` now requires a brief to state, for a **pin dir**, its
CONTENTS and the commit they were built from — the obligation feedback verdict ts 1789501504.70
asked for. But the artifact that verdict was actually about is the MUTATION room, and the file names
that with two other phrases which are never tied to the pin dir: `:200` *"a MUTATION-TESTING seat
works on a COPY of the surface, never the tree"* and `:299` *"a probe on a pinned copy"*. A seat must
deduce that its COPY is made FROM the pin dir for the provenance obligation to reach the room where
the verdict's failures actually happened ("every mutation-verification failure this run came from an
incomplete or stale room"). Pre-dates the 2026-09-17 edit and was RECORDED, not confirmed, against
it. Destination: one clause in the `:196` lesson list — *"…and a mutation seat's COPY is made FROM
the pin dir"*. Found by the round-3 seat of `/fabrik-command-improve fabrik-review`.

### [infra] `premature_stop_rate` counts a turn that ends with its own seats in flight — SPEC candidate

`scripts/sysadmin/kaizen_collect_v2.py:118` (`PREMATURE_CAUSES`), `:399` (the aggregation),
`:1024-1033` (the series), `:1539` (the numerator). Raised by fleet as `01M2R0KJYX4NXKFGF5YYKG1V9Y`,
validated and re-measured by infra 2026-09-17.

**The defect.** The series counts every `stop_block` with cause `run-record` as a premature stop. Under
the convergence commands, a turn that ends while the agent's own dispatched seats are running is the
SANCTIONED shape — a seat's report arrives as a task-notification, which requires the turn to end. So
the number tracks how many seats a run dispatches, not how often an agent stops early, and a kaizen
change queue acting on it would tighten the Stop hook against behaviour the review commands mandate
(the Cobra reading, D-253).

**Measured 2026-09-17** over all 38,457 files under `~/.claude/state/events` (100,275 lines, 0
unparseable), events stamped that day: 520 `stop_block`, 188 `stop_pass`, rate 73.4%. Two facts the
originating finding did not carry: **100% of the day's blocks are cause `run-record` — `promise-stall`
contributes zero**, so half the cause set is inert; and three sessions produce all 520 (59.4% / 30.8%
/ 9.8%), so the series is dominated by whichever session is running a multi-seat review.

**Both collector-only remedies are REFUTED, with their measurements.** (a) Collapsing "warn-through
attempts" to `attempt == 1` rests on a false premise: `attempt` RESETS PER RUN RECORD and INCREMENTS
PER BLOCKED TURN, sticking at 3 after the warn-through. The blocks are distinct turns, each with a
different dispatch's seats live — not retries of one wait. It would read 41.2% instead of 73.4% by
discarding real turn-ends. (b) "A block preceded by a `dispatch` with no intervening `run_close`"
excludes 132 of 132 episodes — it discriminates nothing.

**Therefore the fix is the fleet-synced one and it is SPEC work.** `.claude/hooks/final_gate_stop.py`
must carry `background_tasks_live: <n>` in its stop event; the collector then keeps only no-live-task
turns in `premature_stop_rate` and takes the rest into a `waiting_turn_rate`. The hook is a
governance-sync trigger (~46 repos); `kaizen_collect_v2.py` is NOT fleet-synced (absent from
`fabrik_synced_manifest.py`), so the collector half stays hub-local. A definition change also owes a
version bump — the series is v3 and the file's own law is that one `def_hash` must never span
differently-populated points.

**Interim, and deliberately NOT shipped as a standalone:** a magnitude-only fix would cut 73% to 41%
without changing what is counted, removing the pressure for the real fix. The originating finding's own
SYSTEMIC note is the right interim shape — COUNT THE INSTRUMENT GAP, never bucket it: until the hook
can tell, the collector should expose that its numerator is undifferentiated rather than call it
premature.

### [infra] `runtime.md` is MANDATED by /fabrik-user-test and REJECTED at three enforcement sites — SPEC candidate

Raised by web-ecommerce-factory as `01M2R6FHVDKA8S0QMDJR1S5Y0Z` (finding 1, measured on
`docs/development/certifications/2026-09-17-cert-bhdtrade/`), validated and ESCALATED by infra
2026-09-17: they found one rejecting site, there are three.

- **Mandates it:** `commands/_sources/fabrik-user-test.md:55` — *"RECORD how you started it —
  `<board>/runtime.md` — before any round runs."*
- **Rejects it (a):** `scripts/enforcement/check_certification_coverage.py:331` exempts only the
  spine and `ledger.md`, so `runtime.md` reports `BAD TICKET: runtime.md is not TC##[a-z]?-<slug>.md`.
- **Rejects it (b):** `scripts/enforcement/check_doc_sprawl.py:44-47` — `CERT_BOARD_RE` permits
  `<spine>.md|ledger.md|TC\d{2}[a-z]?-<slug>.md` and nothing else.
- **Forbids it (c):** `CLAUDE.md` § HARD STOPS, the new-`.md` allowlist row: cert boards are
  "same-stem spine + `ledger.md` + `TC##[a-z]?-<slug>.md` tickets ONLY" — and its byte-identical twin
  in `templates/governance/CLAUDE.md`, auto-loaded in ~46 repos.

So a project agent that follows the command exactly creates a file its own governance forbids and two
of its own gates reject. Advisory today, which is the only reason nothing blocked.

**Why this is SPEC work and not a one-line exemption:** the fix has to land at four sites at once
(two enforcement scripts, both fleet-synced governance-sync triggers, plus BOTH CLAUDE.md copies),
and it has to RULE first — either `runtime.md` joins the cert-board namespace everywhere, or the
command names a different home. Patching only `check_certification_coverage.py`, which is the
obvious reading of the incoming finding, leaves `check_doc_sprawl.py` and the contract still
rejecting it, i.e. three of four sites wrong and the symptom hidden.

### [infra] A harness worktree's synced copies are STALE, so every seat's `final_gate --check` reds at random

Raised as finding 3 of the same mail: 7 of 7 fix seats in one web-ecommerce-factory run hit
`Fabrik-Synced Files Unmodified` or `Doc Link Integrity` red, none naming a file they touched, and one
seat saw a DIFFERENT red eight minutes later. Reproduced hub-side 2026-09-17: of 18 registered
worktrees, the sampled `/opt/fabrik/.claude/worktrees/agent-a1465c43f1a445a7f` carries a
`scripts/command_run.py` that DIFFERS from the main checkout.

⚠️ The mechanism is NOT the same in the two places and a fix must handle both: in a PROJECT the synced
set is gitignored, so a worktree receives nothing; in the HUB those paths are TRACKED
(`git check-ignore --no-index` reports no rule), so a worktree receives them at whatever commit it was
created from and drifts as master moves. Same red, two causes.

This collides with a rule the hub actively mandates: CLAUDE.md § Behavior routes every mutate-restore
cycle to a throwaway `git worktree add`, and the seat brief template sanctions it. So the contract
sends seats into an environment whose gate is unreliable. Disposition to rule on: re-sync the ignored
set on worktree creation, or have the gate say "worktree: synced-set drift is expected" instead of
`failure`. Related: the already-filed contradiction that read-only finder briefs forbid every writing
git verb while the shared-tree rule mandates a worktree (cost one seat 18 false FAILs).

### [infra] A background Bash task inside a subagent is killed at ~1h with no signal to the caller

Finding 2 of the same mail, measured: a wave driver died silently at 47 of 99 pages at exactly 60
minutes and was recovered with `setsid nohup … & disown`. NOT independently reproduced by infra (it
would cost an hour to observe). Destination: one line in `.windsurf/rules/core/62-using-subagents.md`
telling a long driver to launch detached from the start — a fleet-synced pack, so it rides whatever
change next touches that file rather than a commit of its own.

### [infra] The pin contract binds only the SEAT — extending it to the orchestrator is SPEC work, not a command edit

`commands/_sources/fabrik-review-scoped.md` step 5. Six ledger verdicts ask for this and every one is a
measured incident, not a preference: *"three seats in this run read a moving target"* (ts 1789584522.96),
*"I moved the tree under reviewers 3 times"* (1788863357.22), *"2 of the authoritative seat's 8 candidates
were already fixed live before it could report them"* (1789037346.84), *"a finder reading the live tree
scores a moving target"* (1788822963.36), *"the single edit that would have saved the most time here"*
(1788971389.36), *"pin the base sha … so a mid-run sibling commit never empties the diff"* (1788733157.33),
plus *"the brief tells SEATS not to mutate the tree and says nothing to the ORCHESTRATOR"* (1789494438.58).
The hub's own LESSONS_LEARNT (2026-09-16) carries the executed case: a seat watched the file under review
change and change back mid-pass and said that, had it re-read the live path instead of its pin, it would
have filed a CONFIRMED defect as REFUTED.

**Attempted as a command edit 2026-09-17 and REVERTED.** `/fabrik-command-improve fabrik-review-scoped`
wrote the paragraph three times; three review rounds (5 native seats, 35 findings, 22 confirmed) each
found NEW defects in the previous round's fix — confirmed/own-fix **10/0 → 6/6 → 6/6**, which fired the
D-278 scope-growth stop, and the third cut had introduced a live regression (it deleted the head of the
following sentence, orphaning the two-causes trigger and unbalancing a `**` span, in the rendered corpus).
Reverted to HEAD; the corpus is whole. It is filed rather than re-patched because the obligations turn out
to depend on `command_run.py` internals, which makes it a MECHANISM — this command's own PHASE 2 routes a
verdict wanting a new mechanism to `/fabrik-spec`, not to a wording edit.

**What the three rounds ESTABLISHED, so the spec need not re-derive it:**

1. **The pin has two plausible bases and BOTH fail empty if named naively.** `git diff HEAD -- <surface>`
   returns empty once a sibling commits the surface mid-round — the md5 then matches nothing, the seat is
   told the pin holds, and a CONFIRMED-zero round closes the loop on a surface nobody read. The committed
   branch fails the same way in different clothes: measured on this repo, `git show <sha> -- <path>` →
   **0 bytes** where `git show <sha>:<path>` → **18,524 bytes**. A base is a REV; a content pin is
   `<sha>:<path>`; a diff pin is `<sha>^`. The text must name which.
2. **The md5 must be of the LIVE file compared against the pinned copy, re-computed at adjudication.**
   An md5 "of the surface at the base" is immutable by construction, so a "changed md5 kills the round"
   rule written that way can never fire.
3. **"Kill the round" is not expressible today.** `command_run.py` registers 9 subcommands
   (`start·step·dispatch·round·done·blocked·handoff·line·status`) and none abandons a round or releases a
   stamp. Worse, `cmd_dispatch` ACCUMULATES within a round (`command_run.py:2807`, `carried =
   prev_disp["seats"] if prev_disp["round"] == len(rec["rounds"])`), so kill + re-dispatch stamps **6**
   seats on one 25-minute reservation that siblings subtract from their headroom; only the run's close
   releases it (`:3494`). Either the tool grows a verb or the text must name the accounting.
4. **An orchestrator-applied fix counts in `--confirmed`, NOT `--own-fix`** — adjudicated and REFUTED as an
   edit: `--own-fix` means "of those confirmed, how many lay in THIS review's own earlier fixes", so
   counting an artifact defect there would inflate `own_fix * 3 >= confirmed * 2`, trip the stop early AND
   buy a backlog exit for a real defect. That is the cobra `command_run.py:397` names in its own docstring.
5. **Step 3's "no third bucket, no 'noted'" needs a signpost**, because step 3 and the seats-are-out
   interval are the same interval on every round-1 pass (the floor is 3 readers at round 1), and a reader
   at step 3 has no reason to read step 5 mid-pass.
6. **The pin directory must be per-DISPATCH, not per-round** (`<scratch>/<round>-<dispatch>/`), because two
   Task messages in one round are two stamps (`command_run.py:2804-2806`) and a shared dir lets the second
   dispatch's copy overwrite a still-running seat's pin — the moving-target failure, re-created by the fix.

**Cost note for whoever sizes it:** the LIGHT pass is the constraint. Three cuts measured +700 / +959 /
+738 B on an 18,524 B command whose identity is being cheaper than `/fabrik-review`; a seat judged the
obligations earned but the wording not at its Pareto frontier every time. A spec should decide how much of
this belongs in the command text at all versus in `command_run.py` behaviour.

### [infra] `term-edit.md` reads as LICENSING the working-tree edit that `/fabrik-review-scoped` now forbids — 17 consumers vs 1

Found by the confirming pass of `/fabrik-review-scoped` over 02df9b74f (D-288), which added to that one
command: *"While seats are out you do not edit the pinned files either — queue what you find and fix it
when you adjudicate the union."* The MIRROR of that change, named per CLAUDE.md § Behavior:

`commands/_fragments/term-edit.md:20`, pin obligation (2): *"…and never touch the pin while its seats run
(the seats read the pin; you edit the working tree)."*

The subordinate *"while its seats run"* scopes the parenthetical, so it reads as a WHEN claim licensing
working-tree edits during the seat window — the exact behaviour the nine ledger verdicts behind D-288
describe as harmful. A charitable reading exists and may be the author's intent: the contrast is WHERE
(the seats read the pin copy, you work in the tree), not WHEN. Either reading is defensible from the words,
which is itself the defect — a rule 17 commands render should not depend on which one a reader takes.

**Measured 2026-09-17:** `{{include:term-edit}}` appears in **17 of 37** `commands/_sources/*.md`; the new
sentence appears in **1 of 37**. So the ambiguous posture out-reaches the explicit one seventeen-fold, and
`fabrik-review-scoped.md:63` cites `term-edit.md` BY PATH as canonical for its own delta rounds — the file
now points at a fragment a reader may take as saying the opposite.

**Why this is filed, not fixed.** The repair is four words, but it lands in a fragment rendering into 17
commands whose orchestrators never asked for the rule, and a fragment edit must be verified coherent for
every consumer (the `spec-review`/`plan-review` family included). This session already spent three reverted
attempts learning that a small-looking edit on a shared surface is not small. Size it, then make it.

**Not a regression introduced by D-288:** before it, 17 commands carried the ambiguous sentence and none
carried an explicit rule. D-288 did not change those 17; it made a pre-existing ambiguity visible by stating
the opposite clearly in one place. Leaving it costs nothing that was not already being paid.

### [infra] The `$HOME`-rooted `.claude*` read ban is keyed on the PATH; the hang is keyed on the TOOL

Every seat brief this session carried "NEVER read any `$HOME`-rooted `.claude*` path — it stalls the seat
indefinitely" (memory `feedback_subagent_home_dir_reads_hang`), and two briefs in the `/fabrik-spec-review`
of the `/fabrik-task` spec REQUIRED a read of `~/.claude/state/command-feedback.jsonl` for a measurement.
Measured by three seats 2026-09-17: `python3 open()` on that path returned in under 2 seconds every time;
the stall the memory records came from the Read/Grep tools on `~/.claude-fleet/…` transcript-sized files.
So a seat that obeys the memory refuses a read the brief requires, and a brief that carves out the ledger
contradicts the memory it also quotes. Fix: re-key the rule to the TOOL — Read/Grep never; `python3`
`open()`/`sed -n` on a NAMED small file with a size check first — in both the memory and the standing
brief preamble. Found as MACHINERY by the pass-2 Opus B seat.

### [infra] `commands/_agents/fabrik-researcher.md:22` says firecrawl "is not connected on this box" — it is

The parenthetical reads *"(firecrawl was named here once; it is not connected on this box — a routing arm
that does not exist is not redundancy. Verified gone 2026-08-30, wef 01M17XXF.)"* — while
`docs/workstation/mcp-roster.md:65` rules it **ON everywhere** (D-013; the crash was a corrupted npx cache
entry) and `scripts/sysadmin/mcp_health.py` reported `firecrawl: CONNECTED` in this session three times. A
researcher seat reading its own agent definition is told a live arm is dead. One-line fix in the agent
source, rendered to `~/.claude/agents/` (not a governance-sync trigger); its own scoped review. Found as
MACHINERY by a `fabrik-researcher` seat verifying the spec's citations.

### [infra] The /fabrik-task lane spec closed run 2 on the D-278 exit at DRAFT — the last apply has been read by no fresh seat

`docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` after `/fabrik-spec-review` run 2 (2026-09-18):
three rounds confirmed 53 / 47 / 25 defects with 37 / 45 / 25 inside text the review itself had just written;
`command_run.py` printed `⚠️ SCOPE GROWTH` at round 3. Per the exit the last named set (25, incl. the
`--no-merges` non-sequitur, the `1` branch's missing sync arm, the nested-heavy-review contradiction, the
`handoff` line missing `--command`/`--feedback`, "six of eight" route-up classes) was FIXED and no further seat
re-armed — so the 19-line r6 diff is unverified by a non-authoring reader. Destination: a THIRD run is the
operator's call; if taken, it starts with ONE fresh Opus seat over `git diff a929b33f8..HEAD -- <the spec>`
restricted to § Chosen approach + § The decision rule, and the round-zero rule that every mechanism claim the
apply introduces is executed BEFORE the seats go out — the lesson of this run is that two applies of 34 and
20 block edits each carried ~20 executable claims nobody ran. Also unresolved, for the operator at D-291: the
U19 pointer's MIRROR (>5 → >3 files fleet-wide; synced and vendored surfaces change lane).

### [infra] The /fabrik-task lane spec after run 3: seven rounds, the residual is phase 5's re-measure, and the approval is the operator's

`docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` (2026-09-18): run 3 ran seven fresh-seat delta
rounds (23 → 25 → 19 → 20 → 19 → 12 → 15 confirmed, all own-fix; SCOPE GROWTH printed from round 3). Since round
3 every finding outside phase 5 has been word-level; phase 5's own-commit re-measure kept sprouting git edge cases
(root commits, merges, rebases, quoting, the capture path, the exclusion set) that a paragraph cannot close and a
grader can. Recommendation: the operator flips the spec CONVERGED by ruling with phase 5's six invariants as the
build's Phase A acceptance criteria (each with a red-first grader), and the build's full `/fabrik-review` on
`command_run.py` is where the re-measure is settled. Not recommended: an eighth prose round.

## check_governance_tables.py is blind to two GFM-invisible table shapes (routed from T04a, D-297)

Found by T04a's review (2026-09-18) and verified by reading the code plus rendering through
markdown-it-py. `scripts/enforcement/check_governance_tables.py` is the fleet-facing guard that a
governance rule living in a markdown table still RENDERS, and it misses two shapes that render
nothing at all:

- `:121` `indent = len(raw) - len(raw.lstrip(" "))` is space-only. A TAB-indented row scores
  indent 0 and is checked as a normal row, but GFM expands a tab to the next 4-column stop, making
  the whole table an indented code block — invisible to every rendered reader.
- `:128` gates the header-vs-delimiter width comparison on `_DELIM.match(nxt)`. Delete the
  delimiter row and the only check that would notice self-disables; GFM then renders a paragraph.

A third, narrower gap: the width comparison only runs when a delimiter row is present AND both
outer pipes are there, so a delimiter one cell short is caught but a pipe-less one is not examined
at all (the same convention T04a's grader now names in its failure message).

Fix shape: `e = raw.expandtabs(4); indent = len(e) - len(e.lstrip(" "))` at both sites, and track
whether a delimiter row was seen per table rather than gating on finding one. T04a solved the same
class in its own grader by delegating validity to markdown-it-py instead of approximating GFM —
three rounds of approximation there produced defects in BOTH directions — so the leanest fix here
may be the same delegation rather than a fourth hand-rolled rule.

⚠️ This is `scripts/enforcement/` — a governance-sync path distributing to ~46 repos — so by the
lane table T04a adds, it is rule 1: right-now + a full `/fabrik-review`, never a rider on another
ticket. That is why it was routed rather than fixed in T04a (D-297).

## Two test suites reach back into the live tree from a scratch probe (routed from T04a, D-297)

`tests/test_command_run_fabrik_task.py:25` hard-pins `_HUB_CONFIG = Path("/opt/fabrik/.pre-commit-config.yaml")`
while resolving everything else via `Path(__file__).resolve().parents[1]`, and
`tests/test_governance_template_split.py:230` hard-pins `THIRD_CONTRACT = Path("/opt/fabrik-lib/CLAUDE.md")`.
Both make those suites ungradeable from an isolated worktree — the mixed resolution grades the live
repo while the probe believes it is isolated, which is the "a grader copied into a worktree still
grades the live repo" class the review constraints exist to prevent. Found by two independent T04a
review seats, each of which had to work around it.

**Amended 2026-09-19 (the first `/fabrik-task` run, D-300):** the `_HUB_CONFIG` half is NOT a defect — `scripts/command_run.py:2694-2697` rules the hub path absolute because the equality test must grade the scalar `governance_sync_postcommit.sh:30` opens, and 18 of 23 registered worktrees carry a different governance-sync scalar; a repo-relative pin would grade the wrong file exactly where the split matters. What remains of this row is the PROBE-side discipline (a grader copied into a worktree still reads the live hub, so a mutation probe must baseline first) and `THIRD_CONTRACT` in `tests/test_governance_template_split.py`, which points at a different repo by design. Two siblings surfaced by the same review, not yet dispositioned: `tests/test_sync_trigger_coverage.py` pins `Path("/opt/fabrik")` in 15 places and 48 such pins sit across 32 test files (`command grep -rn --include='*.py' 'Path("/opt/fabrik' tests/`, executed 2026-09-19; one of them is the `_HUB_CONFIG` pin this row rules on) — each is either the same ruling (grades the live hub on purpose) or a real portability defect, and nobody has classified them; and `scripts/governance_sync_postcommit.sh:26` exits silently from any worktree, so a synced-path commit made in a worktree distributes to zero projects with no warning — § Sync-consciousness does not name it.

## Three claims about the close-time exclusion that the code refutes, in artifacts a fix may not edit (routed from the /fabrik-task docs review, 2026-09-19)

Found by the docs review's closing seat and re-derived here, each by execution against
`scripts/command_run.py` at `318778aea`.

1. **`scripts/command_run.py:3028` says EXCL "collapses from 26 paths to 6"; the number is 25 and
   always was.** Measured: the live Doc Sync Matrix yields 24 destination tokens, five of which are
   the ledger files, and `_task_excl` adds only `docs/CAPABILITIES.md` — `len(_task_excl(root))` is
   **25**, at `318778aea` and at `01a216fea~1`, the commit before the sentence was written. The
   collapsed value 6 is right. `tests/test_command_run_fabrik_task.py:1806` pins the literal string,
   so a presence grader certifies the wrong number; fixing the docstring alone reds it. The same 26
   appears in the CONVERGED spec (`:112`, `:269`) and in `T01b-command-run-close-remeasure.md:29`.
   Fix shape: correct the docstring and the grader literal together, in a change that also decides
   whether the pin should compute `len(_task_excl(root))` instead of matching a sentence — a number
   pinned by string presence is a number nothing checks.
2. **The `sync_test` correction reached 1 of 4 artifacts.** The close keys
   `unmeasurable=sync_test-unavailable` on the CLOSE-time reading alone
   (`command_run.py:3346-3353`); the refuted AND-condition ("`unavailable` at start AND the close's
   re-run still fails") survives in the spec at `:112` (vi) and `:172`, and in
   `T01b-command-run-close-remeasure.md:29` (vi). The protocol doc was fixed at `318778aea`. This
   code↔spec divergence is unminted — unlike the field-order one, which has D-294. Fix shape:
   a D-row naming the divergence, per D-294's precedent; the spec is frozen and is not edited.
3. **The spec's rule 5 still reads "*(executable — the `--file` count)*"**, the occurrence-count
   reading both contracts dropped on 2026-09-19 after execution showed four `--file` occurrences of
   two distinct paths start at rc 0. Same disposition as (2): the divergence is recorded, the
   converged artifact is not edited.

All three are the same shape as everything else this review found — a document asserting something
its own code refutes — and all three sit in artifacts (a frozen spec, a merged ticket) that a fix
may not rewrite, which is why they are rows rather than edits.

## The step-6 validation-first clause: three residuals the scope-growth stop left (routed 2026-09-19)

`/fabrik-command-improve fabrik-execute-plan` closed on the D-278 stop (confirmed/own-fix 8/0 →
7/5 → 10/9): after round 1 the command's own surface was quiet and every later finding sat inside
the review's own prose. The correctness defect was fixed and shipped — an owned-paths test on the
SPEC routed every refuting verdict to `BLOCKED`, because a plan is downstream of its spec and never
owns it — and twelve mutants are now killed. What the stop left, with destinations:

1. **`commands/_sources/fabrik-execute-plan.md:30` vs `:215`/`:239` spell the third BLOCKED cause
   two ways** — `unresolvable spec contradiction` at the enumeration, `unresolvable spec/scope
   contradiction` at both sites that use it. Fixed at `:30` in this change so the reason string the
   new clause mandates is consistent; `scripts/command_run.py` takes `--reason` as free text with no
   allowlist, so nothing detects which spelling an agent emits. **Destination:** an allowlist on
   `blocked --reason`'s three causes is a MECHANISM — spec/plan work, not a command edit.
2. **The phrase-substring pin style this grader family uses is polarity-blind by construction.**
   `assert "OWNED paths is authorised work you" in block` matched both polarities; a one-word
   inside↔outside swap inverted the ruling with all four tests green. The precedent
   (`tests/test_execute_plan_d7.py`) solves it with an explicit INVERSION control, and that pattern
   is not carried into new graders of the family. **Destination:** a shared helper (assert the
   ordered PAIR plus a hedge-word denylist) for the command-pin graders — infra.
3. **`check_corpus_weight.py` names an unsatisfiable remedy on a pure addition.** Its advisory says
   *"the review that accepts it cites the D-row naming what the growth retires"* on ANY growth,
   including an addition that retires nothing; a reader cannot satisfy it and learns to ignore the
   line. **Destination:** infra — reword to "names what the growth buys, or what it retires".

## The seat-brief clause: five residuals the scope-growth stop left (routed 2026-09-19)

`/fabrik-command-improve fabrik-review-scoped` closed on the D-278 stop (confirmed/own-fix 10/0 →
6/6 → 10/10): after round 1 the command's own surface was quiet and all sixteen later findings sat
in this review's own prose. The correctness defects shipped — including the sharpest, that the
edit's two spans CONTRADICTED each other (one forbade putting the expected answer in a brief while
the other required the author to supply the escape variants by name), demonstrated live by the
brief that dispatched the round which found it. What the stop left, with destinations:

1. **Three escape variants of the new clause survive.** A brief can name STRAWMAN variants (nothing
   requires the reader to test them); "ships a GUARD, or states a RULE" is self-assessed and
   undefined, so "it records a fact, it does not state a rule" costs nothing; and the ask is owed
   only at the CLOSING pass, so a variant found earlier by an unasked reader can be relabelled
   own-fix later. **Destination:** infra — close EV3 by naming the test (any modal sentence: must /
   never / owes), which is a one-clause edit the next run of this command can make.
2. **The clause ships without its fire rate and its cobra counter**, both mandated (FIX DIRECTIVE 5,
   the `cobra-effect` universal anchor). Measured for it during review, last 200 hub commits:
   `guard=75 · rule=27 · either=84 of 200`, so the disjunction fires on 42% and is NOT the
   unconditional error the previous cut was. The cheapest satisfaction is EV1 above. **Destination:**
   infra — the cobra line belongs beside the clause, in the same command.
3. **`commands/_sources/fabrik-review-scoped.md:65` is now the file's longest line at ~1.7 KB**
   against a ~98-column median, so every reviewer of this clause needs the `fold -w 170` workaround
   and every future edit to it is a whole-line diff. Three >800-char lines pre-exist. **Destination:**
   infra — a re-wrap pass over the four long lines, mechanical and reviewable.
4. **`assemble_commands.py --check` cannot be run by a seat under the standing brief rules.** It
   diffs a temp render against the INSTALLED corpus under `$HOME/.claude`, and every finder brief
   forbids reading any `$HOME`-rooted `.claude*` path. Three consecutive rounds worked around it
   per-brief. **Destination:** infra — either a `--check --sources-only` mode or an explicit carve-out
   in the brief boilerplate; a mandated check no seat may run is a check nobody runs.
5. **`:106` says "D-066 named only the heavy command"; D-066's own row reads "`/fabrik-review`
   Phase 3 + the scoped twin"** and lists both command sources. Pre-existing base text that now sits
   inside an edited hunk. **Destination:** infra — a scoped fix, not this diff (D-230: one hop out).

## The residue-rewrite trigger is round-shaped where the defect is site-shaped (routed 2026-09-19, with the two drafts that failed)

`/fabrik-command-improve fabrik-review` produced no corpus edit: two drafts of one clause were
written and BOTH withdrawn, which is the disposition `term-coverage.md` rule (3) itself prescribes
for a site that yields in two consecutive rounds. The subject is real and measured; what follows is
everything the two review rounds established, so the next attempt starts from it rather than from
the verdict rows.

**THE GAP.** Rule (3) forces a rewrite "when two consecutive DELTA rounds confirm ONLY defects
inside the previous round's hunks". Two quantifiers make it narrow: `only` disarms the whole round
if one defect sits on the original surface, and `delta` excludes round 1 (line 12: "Round 1 is the
ONLY full pass (D-207)"). A single SITE can therefore yield in consecutive rounds and never trigger
it. Measured on `37d849ffa`: rounds 2-3 read 7/5 then 10/9 — two and one defects respectively on
the original surface, so `only` fails for both while one clause kept yielding. (⚠️ The first draft
cited rounds 1-2 for this and was WRONG: round 1 is not a delta round, so the trigger was
inapplicable there, not silenced. Use the 2-3 pair.)

**WHY BOTH DRAFTS FAILED — what the next attempt must not repeat.** Draft one (934 B, a standalone
span on line 36) restated rule (3) five lines above it, landed in the fragment that does NOT govern
the loop whose evidence it cited, and asserted a premise ("a round can sit under the ratio while a
site keeps yielding") exhibited by none of the four delta rounds it named — all four were at or
above the bar. Draft two (709 B, inside rule (3)) was correctly placed but: dropped `delta` and so
armed rule (3)'s rewrite mandate, for the first time, in the three consumers that run no delta
rounds (`fabrik-user-test`, `fabrik-service-test`, `fabrik-conformance-review`), where "rewrite the
affected paragraph or function" has no referent and the mandated `own-fix` sibling counter is never
stated; left the third yield with no exit, because rule (3)'s `## BLOCKED` escalation is gated on
the ABSENCE of a rewrite and a compliant author rewrites every time; and keyed on CONFIRMED, which
line 36 turns off after the scope-growth stop (`RECORDED — measured`), so it was dead in the phase
it exists to govern.

**REFUTED, do not carry it forward.** A reviewer reported that citing `site: <id> — round k` or
`own-fix: round k` in a Pass row's COUNTER cell nulls the counter run and flips a row reading
`unexecuted: 3` to quiet. Re-executed here against a copy of `check_review_coverage.py`
(md5 `f131cee66019fcf1cff251a61c917312`) across five row shapes including the reporter's own
control: every one read `ext=(0, 0, 0, 3)` with `quiet=False`. The fail-open does not reproduce.

**FIX SHAPE for the next attempt.** Keep `delta` (parity with the trigger it extends). Key on
confirmed OR recorded, or say the rule stands down at the scope-growth stop. Give the third yield
an exit that does not depend on a rewrite being absent. Put the citation in the METHOD cell, as
rule (3)'s two sibling appendages already do. And note the mechanism is hand-maintained in THREE
fragments — `term-coverage.md` (5 consumers), `term-edit.md` (17), `scope-growth-exit.md` (1, the
copy `/fabrik-review-scoped` renders) — so a correct change touches all three; `scope-growth-exit.md`
claims "Maintained once … every copy is a render of it", which is false of the other two, and
`tests/enforcement/test_review_exit_contract.py` grades their parity against a HARDCODED phrase
tuple, so a rule added to one fragment is invisible to the check that exists to catch exactly that.
**Destination:** infra, as one change with its own D-row.

## A Pass row loses its counters to a cell PIPE, and the guidance for it sits in 1 of 5 commands (routed 2026-09-19)

`/fabrik-command-improve fabrik-review` shipped one true clause and answered none of the rows it
was grouped from — a PHASE 2 error worth recording: the three counter-grammar rows ask for the
grader's CELL ORDER, the finders cell's position, and example rows per verdict kind; the clause
that survived review states a VALUE-FORM rule, which came from this session's own experience
rather than from those rows. They stay unanswered and unmarked.

**What was measured while getting there** (all against `check_review_coverage.py`
`f131cee66019fcf1cff251a61c917312`, driven on a copy):

1. **The live cause of a lost counter is a cell `|`, not a bad value.** Census over 324 `.md` files
   and 873 Pass-headed rows under `docs/development/reviews/`: 6 rows state a numeric
   `confirmed:`/`unexecuted:` and lose it to a run break, and in 6 of 6 the run-ending character is
   `|` — 0 of 6 were caused by a value. `docs/development/reviews/2026-09-10-mail-handling-governance-review.md:39-44`
   are those rows: they are refused by the current checker and grade `_confirmed_quiet → None`.
   **Destination:** infra — those six rows want repair, and the refusal text
   (`check_review_coverage.py:1790`) tells a separate-cell author to "write `confirmed:` between
   `new:` and `fixed:`", which they already did; the real edit is dropping the pipes.
2. **The value-form rule reaches 1 of 5 consumers.** `{{include:term-coverage}}` renders into
   `fabrik-review`, `fabrik-repo-review`, `fabrik-conformance-review`, `fabrik-user-test` and
   `fabrik-service-test`; all five render the canonical row, and only `fabrik-review` now carries the
   value-form warning. **Destination:** infra — move it into `term-coverage.md`'s canonical-row
   paragraph, beside the sentence that already says the checker "refuses a displaced `new:` or
   `confirmed:` by name". That is a different change with a wider blast radius and its own review.
3. **A displaced `new:` with a wrapped value escapes the order check.** `| … found: 5, confirmed: 0,
   new: '2', fixed: 3 |` returns `(5, 0, 3, None)` with ZERO refusals, while the same row with
   `new: 2` is refused by name: `_RUN_ITEM` never matches the quoted item, so `new` never enters
   `names` and the rank test cannot see it. **Destination:** infra, `check_review_coverage.py:1288`.
4. **The same trap sits in `confirmed:`**, the D-206 exit counter: `confirmed: 0 (all refuted)` —
   the shape an author writes on a refute-everything quiet exit, which `term-coverage.md` explicitly
   blesses — parses `confirmed: 0` and silently drops `unexecuted:`. **Destination:** infra, with (2).

**REFUTED, do not carry forward.** A reviewer reported that a prose `unexecuted:` makes a row grade
QUIET with work standing. Re-executed across three row shapes including the reporter's own control:
all returned `quiet=False`. It does not reproduce.

## § Completion Contract 1a's `>5 files` and the lane table's `>3` are two numbers in one contract (routed from T04a)

§ 1a's `>5` is REVIEW sizing (how heavy a pass does work already in flight owe?); the lane table's
`>3` is LANE sizing (which lane should this change take at all?). They are different axes and both
are correct, but they sit ~170 lines apart with nothing saying so, and T04a's step 3 permits exactly
one change on that line. Worth one disambiguating clause in § 1a, or an explicit note that 1a keeps
its own number.

## `_TASK_LEDGER_EXCL` misses the lowercase lessons file in 12 of 43 repos (routed from T04b)

`scripts/command_run.py:2996` lists `docs/LESSONS_LEARNT.md` in `_TASK_LEDGER_EXCL`, and
`_task_excluded` matches a non-directory token EXACTLY. But the Doc Sync Matrix row it mirrors says
`docs/LESSONS_LEARNT.md` (canonical name; lowercase `lessons-learnt.md` is legacy-tolerated), and a
sweep of `/opt` finds **24 repos with the uppercase name only, 12 with the LOWERCASE only, 3 with
both, 4 with neither**. So in those 12 repos a `/fabrik-task` run that writes its mandated lessons
entry either burns a `--file` slot on a file the contract calls free, or has the close score it
undeclared — the COBRA counter-measure firing on an agent who followed the instruction.

Fix shape: add `"docs/lessons-learnt.md"` to `_TASK_LEDGER_EXCL` with a grader asserting BOTH
spellings are excluded. One line, but `scripts/command_run.py` is fleet-synced to 47 dirs and the
Stop hook reads its records, so by the lane table's own rule 1 it is right-now + a full
`/fabrik-review`, as its own work. Found by T04b's authoritative review seat, verified here.

## The lane table's hub-only references, as seen from a project repo (routed from T04b)

Three were fixed in the template (the sync regex path, the vendored-surface example, and
`docs/CAPABILITIES.md`). Two references remain hub-shaped in the template and are worth a pass:
`templates/governance/CLAUDE.md:162` tells a project agent to run
`scripts/sync_enforcement_to_projects.py --force` "yourself" on a governance-sync trigger surface —
pre-existing, not T04b's, but it is the hub's fleet-wide distribution script and a project agent
either no-ops or, from a box carrying `/opt/fabrik`, pushes the hub's tree to 46 repos. And the
grounding pointer at `:66` now names an absolute hub path, which is correct but means a project
reader cannot follow it without the hub checked out.

## `declared.sha` is written at `start` and never read — nothing binds `--commit` to the run's own work (whole-plan review, `command_run.py`)

`_task_size_gate` records HEAD-at-start as `declared.sha` (`scripts/command_run.py:2943`); `_task_measure` diffs `<commit>~1..<commit>` (`:3253`) and never reads it. Executed: a run declares one file, the real work lands as a 5-undeclared-file commit `W`, a later ledger-only commit `D` is passed as `--commit` → `oversized_mini: 0`, rc 0, while `git diff --name-status <declared.sha> <D>` shows the honest five. On a three-session tree `D` need not even be yours. This cobra is cheaper than the `docs/reference/` parking the gate's docstring names, and is named nowhere.

The data to close it is on the record already. Two fixes, and choosing between them is a DESIGN ruling, which is exactly what the re-cut test 4 sends to a reviewer rather than an executor:
- **(a) range diff** — base on `declared.sha` when it is an ancestor of `<commit>`, so a multi-commit run is measured whole. MIRROR: a sibling's commit landing between your start and your `--commit` is counted as YOUR undeclared files. On this tree that is the common case, so (a) needs a `rev-list --count > 1` NOTE naming the intervening commits or it manufactures false oversized scores.
- **(b) refuse** — keep `<commit>~1` and REFUSE the close when `rev-list --count <declared.sha>..<commit> > 1`, telling the agent to pass the commit that is the next after their start. MIRROR: refuses honest runs whenever a sibling committed first, which on this tree is most runs.
Neither is clean; (a) with the NOTE is the more honest measurement, (b) the safer gate. Its own `/fabrik-task`-sized run on `scripts/command_run.py` — a governance-sync path, so right-now + a full review — not a rider on this plan. Evidence: whole-plan review seat, 2026-09-18, `probe/r4`.

## The lane table's "a governance-sync path" reads as inapplicable in every repo that is a sync SOURCE (fabrik-lib 01M2TT9K70EH8MJ4G5Q2BYTJVA)

fabrik-lib took § 1a's trigger (their D-274, `56785a81`) and, reading our manifest rather than
reasoning about it, found the case the phrase misses: `scripts/fabrik_synced_manifest.py:197`
`VENDORED_DIRS` names `libs/health_probe`, distributed fleet-wide FROM a sync-excluded tree by
machinery under the heading "Vendored fabrik-lib modules (synced fleet-wide)". That tree receives
nothing and is still a source with a ~46-repo blast radius; "a governance-sync path" names the
hub's regex and, to a source repo, names nothing. Their fix — each recipient states its own
qualifying paths beside the clause — is the right shape and is what
`templates/governance/CLAUDE.md` row 1 should also say for projects: name `libs/` vendored FROM
fabrik-lib and `.windsurf/rules/` as this repo's own sync-shaped paths next to the hub-regex
pointer. One clause in the template (a sync trigger, so its own full review), not a rider.

## § 1a's heavy-surface list should be an ANCHORED span so the next divergence is a gate warning, not a mail (fabrik-lib 01M2TT9K70EH8MJ4G5Q2BYTJVA)

`check_governance_drift.py` keys on the UNIVERSAL markers' anchor phrases; the heavy-surface list
is not one, which is why fabrik-lib's copy could drift silently and needed a mail. They recorded
the anchor as considered-and-not-done because the UNIVERSAL list is the hub's to own. One anchor
(lowercase, mid-sentence, case-exact per the markers' own rule) makes every sync-excluded copy's
drift visible at its own gate. Hub `CLAUDE.md` § UNIVERSAL + § 1a; small, its own change.

## `_MODEL_TOK` is a substring search, so a seat token nobody dispatched closes the round (routed 2026-09-19)

Two residuals from the `/fabrik-command-improve fabrik-review` run that wrote and then reverted a
closing-row sentence (D-304). Both belong to the grammar D-262's row above already sizes as
`/fabrik-spec` work; recorded here so that change inherits them rather than re-deriving them.

1. **The COBRA path on the finders-cell gate is unwritten.** `check_review_coverage.py:2049`'s
   `_MODEL_TOK` is a case-insensitive substring search over the closing row's finders cell. Executed
   on a pinned copy (`f131cee66019fcf1cff251a61c917312`): a cell reading `the orchestrator (opus×1)
   re-read its own fix diff — no seat dispatched` is SILENT, and so is `same seats as pass 1:
   opus×1 + sonnet×2, re-prompted`. Both are exactly the states the rule exists to forbid. Typing a
   token is cheaper than dispatching a seat, and the only artifact that could falsify it is the
   `command_run.py dispatch --seats` stamp, which the checker deliberately does not read (`:2044-2046`
   — "this gate has no run-record reader and adding one would be a new mechanism"). D-253 asks for
   the cheapest bypass to be written down in the mechanism's own docstring; it is not. Writing it
   down is the minimum; a counter-measure is the design question for D-262's change.

2. **The rule's one wording covers only the TABLE grammar.** `:763-776` has two arms: a table row is
   graded on `cells[1]`, a prose row on the text BEFORE its counters, and `:755-761` records that the
   prose ledger is a legal grammar which once made this check unsatisfiable. `review_receipt.py:171`
   and the checker's refusal text both say "Finders cell", which names only the table arm. Measured
   across 324 receipts under `docs/development/reviews/`: 114 carry a parsed closing row, 95
   table-shaped and 19 prose-shaped, and of the 42 closing rows the gate actually grades (those
   stating `confirmed:`) 42 are table and 0 prose. So the gap is PROSPECTIVE, with zero live
   instances — which is why it is a precision note on D-262's change and not its own work.

**Destination:** infra, inside the D-262 change.

## The parity contract: a scaffold template and two command sources written apart and never executed together (wef3 01M2SJT2ZVYP1SM573GDEJYG5Z / 01M2SJVGJQQ65YYBMFW0Q0CSCV / 01M2ST86PY4RZW89TG7NFC0D10, routed 2026-09-19)

web-ecommerce-factory filed four defects from its `/fabrik-deploy-checklist` round 2, all in
Fabrik-owned files they may not edit. Item 3 was fixed in the same run as this row
(`_parse` raising IndexError on a bare value flag). The other three are routed here with the
verdict each earned when I re-derived it; **item 2 is REFUTED as stated** and whoever picks this
up should not build the fix it asks for.

1. **The template's repo root breaks under the runner's own host-leg recipe.** CONFIRMED in
   substance, with a correction: there is no `_repo_root` in the hub's template. The root is
   computed inline in `_health_probe` —
   `templates/scaffold/scripts/verify_prod_parity.py:102`, `root = str(Path(__file__).resolve().parent.parent)`
   — and `sys.path`-inserted so `libs.health_probe` imports. `/fabrik-deploy-verify`'s host-leg
   recipe scps the script to `/tmp` and runs it there, so the root resolves to `/`, the vendored
   import fails, `_health_probe` returns None and every host row reads UNVERIFIABLE. Their fix
   (env `PARITY_REPO_ROOT`, else the script's clone when it holds `compose.yaml`, else the cwd)
   is one reversible decision about precedence — `/fabrik-task` sized, not a right-now fix,
   because the precedence order is the whole content of the change.

2. **REFUTED as filed: `CONTAINER_LEG_SERVICE = ""` does NOT carry two meanings.** The report says
   the template's comment means "no container leg" while the runner means "the project's own app
   service". Both hub copies say the same thing: the template comment at
   `templates/scaffold/scripts/verify_prod_parity.py:62-63` reads "Empty = this project's own app
   service (the compose service named after the project)", and
   `commands/_sources/fabrik-deploy-verify.md:245-246` reads "empty means the project's own app
   service". `tests/test_scaffold_deploy_contract.py:510` pins the seeded value with the same
   gloss. **The real residual is their HOW(2), which is an enhancement, not a defect:** `--header`
   emits `{status, version, date, parsed, container_leg_service}` and NO per-site row counts
   (executed), so a project with zero `container` rows cannot be distinguished from one whose leg
   failed, and the runner execs into an app image to run nothing. Adding `sites: {hub, host,
   container}` counts to `--header` and a "skip a leg with 0 rows" rule to the runner is a
   contract change across the template and the command source — it needs the MIRROR stated for
   every project already emitting a v0 header.

3. **A contract that obeys `/fabrik-deploy-checklist` can never satisfy `/fabrik-deploy-verify`.**
   CONFIRMED by reading both sources. `commands/_sources/fabrik-deploy-checklist.md:139-140`:
   "`UNVERIFIABLE (<why>)` rows are emitted, never dropped — they count in the denominator so
   shrinkage is visible." `commands/_sources/fabrik-deploy-verify.md:310`: CONFIRMED is claimable
   only when every verdict-bearing row reads PASS, "informational registrar rows AND `n/a (not
   obligated)` rows are exempt" — UNVERIFIABLE is NOT exempt. The checklist's own tryton-crm note
   at `:100` records 15 of 27 rows permanently UNVERIFIABLE, so this is not hypothetical. This is
   the one that must NOT be patched in either file alone: what a declared gap means for the
   top-line verdict is a design ruling, so it opens at `/fabrik-spec`, with wef3's two candidate
   shapes (treat a `UNVERIFIABLE (` detail as a declared gap counted beside the verdict; or a
   `mode: declared-gap` marker in the template's unreachable path) as its inputs.

4. **Phase 2 of `/fabrik-deploy-checklist` should name the leg-file threat model** (their `change:`
   verdict, relayed 01M2T4AEWH4XM8CP2H28THQ6NQ). A merged `--rows-from` input can reach CONFIRMED
   by four axes — which row ids appear, how many times each appears, which comparison keys each
   row carries, and what `match` value holds — and the seeded stub guards none of them. They spent
   four of eight rounds on fake-green axes in that layer. The list is identical for every
   project's contract, so naming the four turns four review rounds into one authoring step.

**Destination:** infra, as ONE piece of work — items 1, 2-residual, 3 and 4 share a root cause the
sender named exactly: a synced recipe and a scaffold template that are never executed together.
The fleet test they propose (run the runner against the template stub) is what would have caught
every one of them, and belongs in the same change.

## `/fabrik-review-scoped`'s own source puts its classify-first rule two lines above a heading that overrides it (found reviewing 01M2SSVATCF4WBV2HMT8XQ110G, routed 2026-09-19)

The wrapper fix shipped with that mail is a compensating control: it tells the reader of every
generated wrapper to read the command before opening the record. A review seat located the ROOT,
and it is one file. `commands/_sources/fabrik-review-scoped.md:15` reads "**Before the record —
classify the surface FIRST**"; `:17` is `{{include:run-record}}`, which renders immediately beneath
it as "## Run record — open it as this command's FIRST act". A heading beats the paragraph above
it, and that is exactly what the reporting session did.

The compensating control is still right — the wrapper is all the Skill tool loads, so a source-only
fix reaches nobody who has not already opened the file — but the source ordering should be fixed
too, and it is not this change's to make: `run-record.md` has 35 `{{include:}}` consumers, so any
reordering has to be correct for all of them. Measured while reviewing: 38 of 38 commands carry a
record heading saying FIRST, and 2 of 38 route away without opening one (`fabrik-review-scoped`
and `fabrik-task`). **Destination:** infra, with the fragment's consumer list enumerated first.

## Two residuals from the wrapper/parity fix, left deliberately at the D-278 scope-growth exit (routed 2026-09-19)

The review of that change ran three rounds at 7/7, 11/11 and 10/9 confirmed/own-fix and
`command_run.py` printed the D-278 stop. The named set was fixed; these two were not, and this row
is the reason they are safe to leave.

1. **`test_a_value_flag_with_no_value_prints_usage_instead_of_crashing` executes a real contract
   row in-process, and that row mutates `sys.path` for the rest of the session.**
   `_rows_for(...)` runs `l0_health_probe_vendored`, whose `_health_probe()`
   (`templates/scaffold/scripts/verify_prod_parity.py:102-104`) inserts `templates/scaffold` at
   `sys.path[0]` to import the vendored `libs.health_probe`. Under a randomised test order that
   directory then sits ahead of `/opt/fabrik/scripts` as a namespace-package candidate, and
   `tests/test_claude_fleet.py` imports `scripts.sysadmin.claude_rotate` at nine sites. Measured:
   no breakage today — 45 passed in 83s under random order, 120 passed for the corpus file. The
   row execution exists only to keep `assert rows` non-vacuous; a fixture that restores `sys.path`
   would remove the hazard without weakening the grader. **Destination:** infra, low.

2. **"that command file" has two antecedents in the wrapper paragraph.** The sentence follows
   "…is in `~/.claude/commands/<name>.md` (rendered from `commands/_sources/<name>.md`; edit the
   source, never this wrapper)", so both named paths are command files and the parenthetical's last
   instruction points at the source. Measured: 37 of 38 sources carry `{{include:}}`, so a reader
   binding to the source reads an unexpanded file. Not a live break for the one command whose
   ordering the sentence exists to protect (`fabrik-review-scoped`'s source carries its
   "open NO record here" rule literally), which is why it was not fixed at the exit — the word
   "rendered" closes it whenever that paragraph is next touched. **Destination:** infra, low.

## Two residuals from the wrapper/parity fix, left deliberately at the D-278 scope-growth exit (routed 2026-09-19)

The review of that change ran three rounds at 7/7, 11/11 and 10/9 confirmed/own-fix and
`command_run.py` printed the D-278 stop. The named set was fixed; these two were not, and this row
is the reason they are safe to leave.

1. **`test_a_value_flag_with_no_value_prints_usage_instead_of_crashing` executes a real contract
   row in-process, and that row mutates `sys.path` for the rest of the session.**
   `_rows_for(...)` runs `l0_health_probe_vendored`, whose `_health_probe()`
   (`templates/scaffold/scripts/verify_prod_parity.py:102-104`) inserts `templates/scaffold` at
   `sys.path[0]` to import the vendored `libs.health_probe`. Under a randomised test order that
   directory then sits ahead of `/opt/fabrik/scripts` as a namespace-package candidate, and
   `tests/test_claude_fleet.py` imports `scripts.sysadmin.claude_rotate` at nine sites. Measured:
   no breakage today — 45 passed in 83s under random order, 120 passed for the corpus file. The
   row execution exists only to keep `assert rows` non-vacuous; a fixture that restores `sys.path`
   would remove the hazard without weakening the grader. **Destination:** infra, low.

2. **"that command file" has two antecedents in the wrapper paragraph.** The sentence follows
   "…is in `~/.claude/commands/<name>.md` (rendered from `commands/_sources/<name>.md`; edit the
   source, never this wrapper)", so both named paths are command files and the parenthetical's last
   instruction points at the source. Measured: 37 of 38 sources carry `{{include:}}`, so a reader
   binding to the source reads an unexpanded file. Not a live break for the one command whose
   ordering the sentence exists to protect (`fabrik-review-scoped`'s source carries its
   "open NO record here" rule literally), which is why it was not fixed at the exit — the word
   "rendered" closes it whenever that paragraph is next touched. **Destination:** infra, low.

## serena auto-creates a single-language project, and `.serena/` is missing from the fleet-synced gitignore block (wef3 01M2WR8Y0XBT6C0TASWHKYT8F9, routed 2026-09-19)

web-ecommerce-factory lost a `/fabrik-review` Phase-0 caller hop to this and fell back to grep.
Three items, validated here, in lane order.

1. **`.serena/` is not in the fleet-synced `.gitignore` block — rule 1, heavy.** The hub's own
   `.gitignore:201` carries `.serena/`, hand-added, which is why no hub window has seen the
   `?? .serena/` that every project agent does. `scripts/fabrik_synced_manifest.py` — which
   generates the projects' "Fabrik-synced" block — contains ZERO serena references (`command grep
   -n 'serena'`, rc 1). That file matches the `governance-sync` files-filter (verified against
   `.pre-commit-config.yaml`), so the one-line addition is right-now + the FULL `/fabrik-review`
   plus a forced `sync_enforcement_to_projects.py --force`. **Destination:** infra.

2. **Nothing seeds `.serena/project.yml::language_servers`, so first activation mints one
   language — spec chain.** `scripts/sysadmin/emit_mcp_project_config.py` mentions serena once and
   seeds no serena project file; it is NOT a sync trigger (verified). Detecting a repo's languages
   and seeding the list is a new mechanism (lane table test 2), so it opens at `/fabrik-spec`. The
   spec must cover the repair case as well as the seeding case: every repo that has already
   activated carries a minted single-language file, and seeding helps none of them. Reported
   symptom: a `.ts` symbol request in a 770-tracked-`.py` monorepo errors as "path is ignored"
   rather than "unsupported language", and a re-activation does not start the added server — the
   running MCP process reads its language set at startup, so only a new window restores it.
   **Destination:** infra.

3. **The roster should name the diagnostic class — one doc edit.** `docs/workstation/mcp-roster.md`
   gains a serena row saying: an auto-created project carries one language; a TS lookup reporting
   "path is ignored" is the language set, not gitignore; fix the yml and open a NEW window. This
   is the cheapest of the three and carries most of the value, because the reporter's time went to
   diagnosis, not to the missing server. **Destination:** infra.

**Why this matters beyond the three fixes:** the review corpus's one named use of serena (the
Phase-0 caller hop) degrades silently to grep on exactly the multi-language repos where symbol
navigation pays most. D-021 adopted serena and named "still unused after wiring" as the retirement
signal — a tool that degrades silently will read as unused for a reason unrelated to its value.
That argument belongs in item 1's D-row. The reporter states plainly that they did not read
serena's source, so the ignored-path-vs-unsupported-language mechanism is their inference; items 2
and 3 would change shape if it is wrong, item 1 would not.

## The gitignore block bypasses the T12.17 "never ship the working tree" guard — 46 repos patched from uncommitted bytes (found reviewing the serena ignore, routed 2026-09-19)

`scripts/sync_enforcement_to_projects.py` built `_head_source`/`_shipped_hash` after T12.17, whose
own warning text records the incident: *"this script … copied the WORKING TREE: an uncommitted
edit — mine, or a sibling's — shipped to every project. Measured … 48 copies carried one."* That
protection covers files the sync COPIES, because they are read out of HEAD.

The `.gitignore` block is not copied — it is COMPUTED. `:153` calls `gitignore_block_text()`, an
in-process call into the currently-imported `scripts/fabrik_synced_manifest.py`, i.e. its
WORKING-TREE bytes; `src/fabrik/scaffold.py:550` does the same dynamic import for new projects.
Neither goes through `_head_source`, and `fabrik_synced_manifest.py` is never itself a synced file,
so no HEAD-vs-tree check ever runs on it. Executed against the live tree with that file uncommitted:
the `--dry-run` drift list named `PORTS.md, docs/PROJECT_CATALOG.md,
templates/governance/.worktreeinclude` and did NOT name `fabrik_synced_manifest.py` — 0 occurrences
in the whole dry-run output — while every one of the 46 `Would patch <project>'s .gitignore` lines
was computed from it.

Failure scenario, on a tree three sessions share: a sibling has a half-finished or wrong edit to
`fabrik_synced_manifest.py` sitting uncommitted, anyone runs the sync for real, and all 46 repos'
`.gitignore` are patched with that content, silently, with no drift line. This is the exact
incident T12.17 was built to prevent, reopened through a second code path in the same tool.
`.worktreeinclude` is correctly protected (it IS a tracked file read via `_head_source`), which is
what makes the asymmetry confirmed rather than assumed. **Destination:** infra — the fix is to
compute the block from HEAD's manifest (or to refuse to patch while the manifest differs from
HEAD), and it lands on a governance-sync trigger, so it takes its own full `/fabrik-review`.

## The synced block's header is false for a third of its groups, and it CANNOT be corrected in one edit (routed 2026-09-19)

`gitignore_block_text()` heads the block *"Fabrik-synced files — DO NOT EDIT (centrally managed)"*,
but 3 of its 9 groups are explicitly NOT synced: the retired vendored group, the MCP-config group,
and the new per-machine serena group. The obvious one-word repair ("Fabrik-MANAGED files") is a
TRAP, and this row exists to stop the next agent making it: `sync_enforcement_to_projects.py`'s
`_GITIGNORE_BLOCK_RE` keys on the literal `# Fabrik-synced files`. Executed against a pinned copy
of a real project `.gitignore`: with the header renamed the regex stops matching (`False`), so the
NEXT sync appends a SECOND block and the file ends with two `# End Fabrik-synced block` markers —
in 46 repos, with the stale block never reaped.

The correct order is a migration: widen the regex to accept BOTH headers, sync, then change the
header, sync again, then narrow the regex. Three sync passes, or a one-off repair script.
**Destination:** infra, with its own review; the block is a public contract for ~46 repos.

## `check_synced_unmodified.py` swallows a missing manifest symbol and degrades 46 gates silently (routed 2026-09-19)

`scripts/enforcement/check_synced_unmodified.py:45-53` and `:72-80` do
`from fabrik_synced_manifest import SEEDED_NOT_ENFORCED` (and `RETIRED_VENDORED_DIRS`) inside a
`try/except ImportError` that returns an empty set. `from X import Y` raises ImportError when Y is
MISSING, not just when X is — so a future rename of either symbol makes the check quietly report
"no seeded exemptions / no retired dirs" with no message. `fabrik_synced_manifest.py` is not in
`CORE_SCRIPTS` (verified), so project repos hold no copy and import the HUB's live module through a
`sys.path` insert: one hub rename degrades the gate in every project at once.

This was found while verifying that THIS change's rename (`RETIRED_GITIGNORE_GROUPS` →
`IGNORE_ONLY_GITIGNORE_GROUPS`) was safe. It was — two independent whole-`/opt` sweeps found zero
references outside the hub — but it was safe by luck of which symbol was renamed, not by design.
**Destination:** infra — catch the symbol explicitly, or import the module and `getattr` with a
loud failure.

## Pre-existing red at HEAD: `test_docs_updater.py::TestMultiAgentOperatingModelDoc` (noted 2026-09-19)

`test_doc_exists_and_names_the_planned_surfaces` fails at HEAD `623c00cfb`, verified in a throwaway
worktree before any of this change was applied. Not touched here: it is a different subsystem, and
fixing an unrelated doc test inside a governance-sync review would bundle unreviewed work into a
46-repo distribution. Recorded so the next reader knows it is not this change's. **Destination:**
whoever owns the multi-agent operating-model doc.

## The ignore-only set is an opt-OUT, so a new gitignore group still defaults to "distribute it" (routed 2026-09-19)

`IGNORE_ONLY_GITIGNORE_GROUPS` keeps a group out of `.worktreeinclude`, and the serena change added
a guard that refuses a state where a declared ignore-only group does not exist. That closes the
ORPHAN direction. It does not close the other one, and a review seat executed the gap: add a new
group to `gitignore_dest_paths()`, leave it out of the set, then regenerate the tracked template
with the exact command the test's own failure message prints — the suite goes 28/28 green and the
new paths are shipped into `.worktreeinclude` for ~46 repos. The documented workflow IS the escape.

The mechanism's own comment already admits the default was never inverted ("it moved the EDIT SITE,
it did NOT invert the default"), and admitting it is not the same as closing it in a mechanism whose
purpose is to stop silent distribution. The smallest shape that closes it is an explicit
classification: a second constant naming the groups that ARE distributed, and a guard requiring
every group key to appear in exactly one of the two sets — so a new group is a loud refusal until a
human picks a side. That is a change to a governance-sync path and takes its own full review; it was
deliberately not bundled into the serena change at its third round. **Destination:** infra.

## Two latent residuals in the ignore-only guard (routed 2026-09-19)

1. **The guard can be narrowed back to one hardcoded key with the suite green.** A seat mutated the
   orphan loop to iterate `{SERENA_GITIGNORE_GROUP}` instead of the set and all tests passed — the
   same `==`-shaped defect D-199 fixed one level down, reinstated one level up. The grader could
   kill it the way its sibling does: monkeypatch a SECOND ignore-only group into both the set and
   the dict, orphan that one, and assert the guard names it.
2. **Nothing records why the guard is a `raise` and not a bare `assert`.** Executed both forms: as
   shipped it raises under `python` and `python -O`; rewritten as `assert not orphans, …` it is
   silently disabled under `-O` and the paths leak. The shipped form is correct; the risk is that a
   later "simplification" to `assert` looks equivalent and is not.

**Destination:** infra, low — both are grader/comment work on a file that already carries a full
review's worth of guards.

## Nothing in `scripts/enforcement/` binds the distributed `.worktreeinclude` to its generator (routed 2026-09-19)

`templates/governance/.worktreeinclude` is a GENERATED artifact that ships to ~46 repos by file copy
(`sync_enforcement_to_projects.py:2028`) and into every new project (`scaffold.py:1288-1290`).
Neither consumer calls `worktreeinclude_text()`, so no runtime guard in that function can protect
them. The only thing tying the tracked file to its generator is
`tests/test_synced_manifest.py::test_worktreeinclude_template_matches_generated_text`, and the hub's
pytest leg is not armed (`/opt/fabrik/.fabrik/run-pytest` does not exist), so the completion gate
never runs it. Measured: `command grep -rn 'worktreeinclude' scripts/enforcement/` → rc 1, zero hits
across the whole enforcement directory.

This is why the template sat drifted for three days after `0a8d5fc7f` added `whoami_agent.py` to
`CORE_SCRIPTS` without regenerating it — every new linked worktree in ~46 repos lacked that script
and nothing said so. A one-check fix (compare the tracked template to the render, fail the gate on
drift) closes the class for every future generated-artifact drift, not just this one.
**Destination:** infra — `scripts/enforcement/` is a governance-sync path, so it takes its own
full review.

## Fire-rate note on the widened `# AFTER-EDIT:` header (measured 2026-09-19, kept deliberately)

FIX DIRECTIVE 5 asks for a measured fire rate before a check is armed, and this one was widened
rather than armed, so the measurement is recorded here instead of being skipped. `# AFTER-EDIT:` on
`scripts/fabrik_synced_manifest.py` now names `templates/governance/.worktreeinclude` as well as
`scripts/sync_enforcement_to_projects.py`. Measured over the file's full history — 53 commits, not a
sample — only 3 also touched the template, so 12 of 53 past commits would gain an advisory WARN they
do not produce today. The coupling is real only when the RENDERED SET changes, which is a strict
subset of manifest edits.

Kept anyway, and the reason is the row above: the untied template drifted for three days across ~46
repos precisely because nothing warned. A 23% advisory false-fire is the cheaper error while no
enforcement check exists. **If** that check ships, revisit this header — the WARN becomes redundant
wallpaper at that point, which is exactly the shape FIX DIRECTIVE 5 says kills enforcement.
**Destination:** infra, revisit with the row above.

## [infra + fleet] Eight findings routed out of the D-306 stamp-tier review (2026-09-19)

The `/fabrik-review` over `623c00cfb..e9abe0b35` fixed 18 defects in-run. These eight are RECORDED
rather than fixed, each for a stated reason — a forbidden file, a missing mechanism, or an
operator authorisation. None is "reported, not mine": each names where it goes.

- **⚠️ `.claude/hooks/final_gate_stop.py:1888`'s D-158 quota yield is TIER-BLIND (owner: infra).**
  It reads a bare `(_state / "fleet-exhausted").exists()`, so since D-306 it stands ALL SIX Stop
  causes down at the `urgent-90` tier — where `quota_stop.py` denies nothing and there is no
  deadlock to yield against. The yield's own justification ("the hold denies the very tools that
  clear these causes") is false at that tier, so a session can end with uncommitted, unpushed,
  unreviewed work while nothing is holding it. Fix: `and _stamp_tier(stamp) == "walled"`, with the
  reader copied as the other three are. **NOT fixed in the review run because this session is
  contractually forbidden to edit that file.** Found by the contracts seat.
- **An unreadable or malformed `caps.json` now drops the fleet's hard stop (owner: fleet).**
  `walled` is blind to a cap it could not read (the loader fails soft to `{}` and prints "rotating
  UNCAPPED"). Before D-306 that was inert — stamp present meant WALL either way. Now the mis-read
  is written into the tier: executed on the real ob@ shape (5h 91, weekly 93, operator cap 90),
  a readable caps.json gives `walled` and an unreadable one gives `urgent-90` for the same
  account past the same reserve. A correct fix needs a "caps unknown" signal distinct from
  "this account has no cap", which is a new mechanism, not a review fix.
- **The advisory's stamp write is non-atomic while the re-arm's is atomic (owner: fleet).**
  `stamp.write_text(...)` truncates before writing, so a concurrent reader — or ENOSPC — sees a
  zero-byte stamp; `_rearm_wall_stamp` writes tmp + `os.replace` for exactly this reason. The
  asymmetry is what makes `_promised_resume`'s `IndexError` arm reachable.
- **A broken symlink at the stamp path allows silently (owner: fleet).** `Path.exists()` follows
  symlinks, so `quota_stop.py` never reaches the tier reader and emits no warning, while
  `_stamp_tier` on the same path would say `walled`. Pre-existing; unchanged by D-306.
- **⚠️ Two graders in `tests/test_governance_template_split.py` have never run on this box
  (owner: infra).** `test_the_lane_table_renders_as_a_table_for_every_gfm_reader` and its template
  twin fail with `ModuleNotFoundError: linkify_it`. `markdown_it` 3.0.0 is installed; `linkify-it-py`
  is its optional extra and is declared in NO manifest in this repo. So the hub's own guard that
  the LANE table renders as a table for every GFM reader is wallpaper, and has been. Fix: declare
  the dependency — **which edits `pyproject.toml` and needs operator authorisation**, the reason
  it was not done in the review run.
- **`_promised_resume` bypasses `_usable_ts` (owner: fleet).** That is the file's self-declared ONE
  validator, and `_advisory_ledger_latch` applies it to the SAME field; `"1e400"` returns `inf`
  here. Benign today (it latches to the week re-arm, same as no promise) but it contradicts the
  re-arm docstring's claim that the field "goes through the same validator".
- **`_hold_is_wall` fails OPEN on a non-dict (owner: fleet).** Unreachable from `claude_rotate.py`
  — all three producers of the picture's `hold` emit dict-or-None — but `quota_posture_hook.py`
  re-derives the same notion from the posture JSON, where the shape is whatever was serialised.
- **~~The D-306 contract sentences are graded by nothing three-way~~ — CLOSED 2026-09-20 (D-309).**
  The operator approved the cross-repo edit; `/opt/fabrik-lib/CLAUDE.md` adopted the D-306 block
  (fabrik-lib `618f3f3f`) and the paragraph is now a pinned `_SHARED_SPANS` entry, added as its own
  span with fresh anchors and proven red both ways (end anchor → MISSING, mid-span word → DRIFT).
  All three copies measured byte-identical at 641 chars after normalisation.

## `subprocess.run(text=True)` with no `errors=` — 85 of 88 call sites in `scripts/enforcement/` carry the crash just fixed in one of them (wef3 01M2X0ZQX8YMZX022R9TC1E3M6, routed 2026-09-19)

The reported bug was one strict-UTF-8 decode in `check_secrets.py` killing the whole "Secrets
(Zero Hardcoding)" gate leg. It was fixed there and the class was surveyed. The survey is the
reason this row exists: the same shape is everywhere in the same directory.

**Measured by an AST walk** (`ast.parse` + `ast.walk` over `Call` nodes whose func is `run` with a
`text=True`/`universal_newlines=True` keyword — NOT grep, which produced two false positives by
matching `errors=` inside a comment and an unrelated local named `errors`). Population: **78**
`.py` files directly under `scripts/enforcement/`, **88** `subprocess.run(text=True)` call sites.
**3** carry a per-call `errors=`/`encoding=` and all three are the lines this change just touched;
**85 across 35 files** do not. ⚠️ An earlier seat reported "36 files" — that was the count of files
CONTAINING such a call, reported as the directory total; and an earlier estimate of "4 exposed"
was a file-count subtraction rather than a set difference. Both are recorded here because the
wrong denominators nearly sized this as a four-file cleanup.

**Classification of the 85 unguarded sites, by reading each call's git subcommand:**
**17 REACHABLE** — decode file CONTENT or a commit MESSAGE, the same crash class: `check_changelog`
`:173`, `check_compose_services` `:45`, `check_convergence` `:768`, `check_doc_sync` `:153,:222,
:258,:488`, `check_env_example` `:65`, `check_lint_ratchet` `:229`, `check_openapi_sync` `:59,:80`,
`check_plan_tickets` `:1063` (`%B`), `check_print_ban` `:66`, `check_schema_sync` `:85`,
`check_subagent_flywheel` `:107/:230` (`%B`), `check_test_coverage` `:55,:76` — 12 distinct files.
**51 PATH-ONLY** across 31 files — filenames only, which is the SECOND crash this change closed (a
non-ASCII path under `core.quotePath=false`), so not safe, just differently triggered; note
`check_structure:157` and `check_doc_sprawl:395` FORCE `-c core.quotePath=false`, i.e. they
guarantee raw bytes rather than depending on config. **12 METADATA** (rev-parse, version strings)
and **5 NEEDS-A-PROBE** (jscpd, ruff JSON, mutmut, a `review_rubric.py` subprocess).

**Firing today, or latent?** Scanned all 45 `/opt` git repos, 102,145 tracked files. The
file-content trigger EXISTS: **63 files in 2 of 45 repos** are non-UTF-8 while git classifies them
as text — `/opt/iterative_image_editor` (1) and `/opt/web-ecommerce-factory` (62, the reporter's
own PDFs, one committed the day before the report). The commit-message trigger does NOT: **0 of
~27,000 commits** across 45 repos fail to decode. Nor does the path trigger: **0 of 45** repos hold
a path that is invalid UTF-8 (two have non-ASCII paths; both are valid UTF-8). ⚠️ The seat's own
first pass reported 184 content files and was WRONG — it truncated each blob to 8000 bytes before
decoding, slicing multi-byte characters, and cleared to 63 on a full-content re-run; the 8000-byte
window belongs to git's binary heuristic, not to a decode test. Whether any of the 12 REACHABLE
scripts' own extension filters currently let such a file reach their vulnerable line was NOT
established — most filter to `.py`/`.ts` first — so treat this as latent-fleet-wide with a live
trigger population, not as a firing incident.

**The cheapest correct fix, and it is not 85 edits.** `check_script_headers.py:206` already has the
right pattern and a comment explaining it: capture BYTES, decode stderr `"replace"` for messages
and stdout `"surrogateescape"` for paths, never `text=True`. Two other files (`check_doc_sync.py:70`,
`check_subagent_flywheel.py:104`) define their own `_git` helper. Generalise that one helper into a
shared enforcement util and migrate the call sites to it — mechanical, one line each, and it
collapses three duplicated helpers. Ship a lint rule refusing a new `subprocess.run(text=True)`
without `errors=` IN THE SAME CHANGE as the D-253 cobra guard, or the class regrows at the next
new script. ⚠️ One site parses rather than scans: `check_lint_ratchet.py:229` feeds `git show`
output to `json.loads`, so a replacement character could corrupt a value silently — its wrapping
`except (OSError, ValueError)` falls back to the working-tree copy, which is what makes `replace`
safe there; that reasoning belongs in a comment, not in a copy-paste.

**Destination:** infra. `scripts/enforcement/` is a governance-sync path, so the migration is
rule-1 work with its own full review and a forced sync.


## [infra] The escalation digest routes obligations to a reader who structurally cannot discharge them (2026-09-20)

Measured while handling digest `01M2XQG8ANKS4AM4C3C69XWQD5`: of its 83 rows, **zero** were
obligations on the hub. Every one sits in ANOTHER repo's inbox — 41 from a single fabrik-lib
broadcast, 39 the hub's own sends. The hub's own inbox held one obligation, half a day old.

`mail_escalate.py::_deliver_to_agent` has exactly one destination: the hub mailbox addressed to
`infra`. So the agent bound by the handle-now law is handed a list of other repos' work. The
digest anticipates this and offers `ack --disposition wontfix naming the owner` — but using it
would close 83 obligations the owning repos have never seen, which destroys the signal rather than
discharging it. Leaving them unacked is the honest choice and is why the number only grows.

The shape line shipped today makes the number readable; it does not fix the routing. **The fix is
to escalate each overdue obligation into the OWNING repo's mailbox**, where an agent bound by the
same law can actually act — the hub keeping a summary. That is deliberately NOT done here: it
would inject ~83 new messages across ~40 mailboxes on its first run, which is an outward-facing
action at fleet scale and wants the operator's word before it fires, plus a de-duplication rule so
a repo is not re-escalated every six hours.

Owner: infra (fabrik-mail is its beat). Destination: a `/fabrik-task` or spec-chain change to
`mail_escalate.py`, gated on the operator approving the fan-out.

## [intel/infra] `rule_activation` reads ~2% on its two largest samples, and nobody can say whether that is behaviour or instrument (2026-09-20)

From the 2026-09-18 kaizen collection, adjudicated against `~/.claude/state/kaizen/series/rule_activation@v3.jsonl`
rather than the day's number alone. The series: `.50 (1/2) · .12 (3/25) · .25 (2/8) · .29 (2/7) ·
.047 (2/43) · .024 (1/42)`. Every reading above 10% came from a denominator of 25 or fewer; the
two LARGEST samples (n=43, n=42) give 4.7% and 2.4%. The metric did not fall — it finally has
enough rows to be believed, and what it says is that almost no run-closing session emits a
`rule_activation` event.

⚠️ AMBIGUOUS BETWEEN TWO OPPOSITE FIXES, which is why this is routed rather than acted on: either
sessions genuinely do not activate rules at invocation time (a behaviour gap, and the remedy is in
the corpus), or the event is not emitted where the metric looks for it (an instrument gap, and the
remedy is in the emitter). Deciding needs the emitter driven, not the number read again.

Owner: whoever owns the kaizen instrument (intel by the subagents/flywheel charter, infra by the
hooks). Destination: drive the `rule_activation` emitter over a session known to activate a rule,
and see whether the event lands.

SECOND, cheaper item from the same read: the digest prints one day's value with no history, so an
agent cannot distinguish a moved METRIC from a moved POPULATION — `rules_compliance` fell 98% → 82%
across a denominator collapse from 466 to 66, which is not a comparable decline, and
`premature_stop_rate` at 61% reads as a rise while actually being the lowest of five readings.
Printing the previous two readings WITH their denominators beside each metric would fix it. Filed
against `scripts/sysadmin/kaizen_digest.py` / the collection's mail body.

## ~~[infra] Three SHADOW mailboxes strand 5 obligations~~ — RETRACTED, the finding was false (2026-09-20)

⚠️ **There are no shadow mailboxes and no stranded mail. This row was wrong and is retracted the
same day it was filed.** Kept rather than deleted, because a retracted claim that vanishes teaches
nobody, and because the ROUTED items above and below it were filed by the same run.

What actually happened: the owner leg (D-310) addressed `mail.py send --to` with
`Obligation.repo`, which is sanitised at collection — `_sanitize` translates `_` to a space
because `_` is a markdown metachar and every field is rendered into a message body.
`Reference_Creator` therefore printed as `Reference Creator`, `mail.py` correctly refused it as an
unsafe recipient, and I read the three refusals as evidence of three mailboxes that do not exist.
`find /opt/fabrik-mail -maxdepth 1 -name "* *"` returns nothing; only the underscore directories
are there, and they hold no stranded obligations.

The real defect was mine, one hop upstream: a DISPLAY field used as an ADDRESS. Fixed in
`4fc125207` — `Obligation` gains `repo_key` (the real directory name) for routing while `repo`
stays sanitised for prose, with a grader proven red on revert. Re-ran: `owners=3 sent/0 failed`,
all 44 repos now told.

The one durable lesson, which is not about mailboxes: **a sanitiser's output read back as data is
a fabricated fact.** It looked like evidence, it survived my own write-up, and it was one `find`
away from being disproved. It reached an operator approval request before anyone ran that command.



## [infra] doc↔script coupling is blind to every shell script (2026-09-20)

`render_doc_script_links.py` globs `scripts/**/*.py` only (`:136`), so a `.sh` carrying a valid
`# AFTER-EDIT:` header is silently ignored — its doc never gets a `## Related scripts` row and the
`--check` gate cannot catch the pair drifting. Not hypothetical and not new: `weekly_catchup.sh`
has declared `docs/workstation/kaizen.md` for months and appears in no rendered block, and
`agent_memory.sh` (D-316) declares `cleanup-automation.md` with the same result.

Measured today: the renderer reports "45 coupled doc(s) current" — a denominator that counts only
Python, so the coverage ratchet reads clean while every shell surface on the box is unmeasured.

⚠️ **It is TWO files, not one** (found by a review seat 2026-09-20 that checked the sibling gate
rather than stopping at the one named): `scripts/enforcement/check_script_headers.py:329` filters
`f.endswith(".py")` with the identical effect, so a shell script carrying NO `# AFTER-EDIT:` header
at all is invisible to the WARN as well. The original row understated the scope.

Owner: infra (`scripts/enforcement/` and the doc-coupling tooling are its beat). The fix is a
one-line glob widening in EACH of the two files plus a re-run of `--coverage` to re-seed the
baseline with the shell scripts included — which will make the headless count RISE once, and that
is the ratchet working, not failing.

## [infra] agent_memory.sh — two latent fail-opens the D-278 stop routed rather than fixed (2026-09-20)

Routed from the `/fabrik-review` over the workstation RAM policy, which exited on the scope-growth
stop (`confirmed/own-fix: 9/5 → 15/11 → 3/3` — two of the last three rounds above the two-thirds
line). Both were found by an authoritative seat, both are proven, and both are **unreachable on
this box today** — which is why fixing them inside that loop would have regenerated the surface it
was correcting rather than closing it.

1. **`live` is the one numeric in `cmd_reclaim` not `_is_num`-validated** (`scripts/sysadmin/agent_memory.sh`,
   the live-session guard). `live=$(printf '%s' "$pids" | grep -c . || true)` — if `grep` cannot
   execute, `live=""`, `[ "" -gt 0 ]` exits 2, `if` reads that as false, and **the swapoff proceeds
   with agent sessions live**. Executed by the seat with `PATH=/nonexistent`: `GUARD BYPASSED`.
   Same fail-open class the comment three lines above claims to have closed, and `total`/`free`/
   `avail`/`back` all *are* guarded. Condition: `grep` absent or unexecutable. Not reachable here —
   `/usr/bin/grep` exists and `reclaim` is operator-run.

2. **Reverting the NUL-delimiting in `_swap_devices` to a newline split passes the whole suite** —
   no grader uses a `\012`-named device. Condition: a swap file whose name contains a newline.
   Not reachable here: swap is the single partition `/dev/sdc`.

Owner: whoever next touches `scripts/sysadmin/agent_memory.sh`. Destination: a `/fabrik-task` —
one `_is_num` guard on `live`, and one grader using a `\012`-named device fixture. Both are small;
they are routed only because the loop that found them had stopped being able to judge its own work.

## [fleet] `fabrik fix` seeds every project from the python-api template map unless `--type` is passed (2026-09-22)

Found by the /fabrik-doc-converge closing seat over `docs/workflows/SCAFFOLD_STRUCTURE.md` (round 4, the
substance behind a doc wording defect). `scaffold.py::fix_project` takes `project_type: str = "python-api"`
(`:6278`) and builds `combined_template_map` from SHARED_TEMPLATE_MAP plus `_PYTHON_API_TEMPLATE_MAP` when
that equals `python-api` (`:6292-6293`). Its only caller, `cli.py::fix` (`:1964-1972`), feeds it a `--type`
option whose default is also `python-api`; `project.yaml` is read inside `fix_project` only for the
`has_user_guide` backfill (`:6559`) and never reaches the map. So `fabrik fix /opt/<saas-skeleton project>`
with no `--type` seeds missing files from the FULL python-api map, and a saas type's real `server/` FastAPI
files (laid by `_scaffold_fastapi_backend` from `_scaffold_saas_backend`, `:3251`) are never re-seeded.
Executed 2026-09-22.

Owner: fleet (scaffolding). Destination: a `/fabrik-task` — read `type` from `project.yaml` when `--type` is
absent (refuse when neither exists), carry the type's real map and prefix, plus one grader: scaffold a
`saas-skeleton` fixture, delete one `server/` file, run `fix_project` with no `--type`, assert it is back
and no python-api file appeared. Mailed to fleet from the converge close.

## [infra] Deferred: the measured doc-converge queue — 6 tier-1 and 9 tier-2 docs describe machinery that no longer exists (2026-09-22)

Operator 2026-09-22: "defer all of these doc updates … i have more urgent things to do." Measured the same day
over 62 docs (docs/, docs/workflows, docs/reference; ledgers excluded): repo-path references dead in both the hub
and a real project, script names absent on disk, retired-subject mentions. Done before the stop:
`docs/workflows/SCAFFOLD_STRUCTURE.md` (1fe9943ff) and `docs/workflows/DATA_SYNC_WORKFLOW.md` (21442fe88 + 6d20fc83f).

Tier 1 (converge needed): `docs/workflows/KILO_AGENT_MANAGEMENT.md` (23 absent scripts, 55 Kilo mentions) ·
`docs/workflows/KILO_BENCHMARK_WORKFLOW.md` (22 absent) — the two describe one pipeline that now runs in
`/opt/ai-model-catalog/engine` and may collapse into one pointer doc · `docs/FEATURES.md` (31 absent script names,
two `scripts/` paths that live in `templates/i18n-kit/`, 10 wpf mentions) · `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md`
(28 wpf, 8 Cascade, 6 dead paths, 61 KB) · `docs/CONFIGURATION.md` (8 absent scripts, 14 Kilo, 57 KB).
Tier 2: `docs/DEPLOYMENT_ARCHITECTURE.md`, `docs/CAPABILITIES.md`, `docs/reference/architecture.md`,
`docs/workflows/development-and-deployment-workflow.md`, `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`,
`docs/reference/external-services-registry.md`, `docs/reference/fabrik-cli-reference.md` (16 wpf), `docs/SERVICES.md`
and `docs/workflows/SYNC_PROJECTS_WORKFLOW.md` (captcha, retired).

Owner: infra (hub docs). Destination: `/fabrik-doc-converge <doc>` per doc, in the order above, AFTER the review-loop
re-engineering lands — the two runs done took 7 and 6 rounds because the loop degenerates after round 1 into a
one-seat-per-cell hunt (memory: converge-fast-no-serial-delta-chain). Trigger: the operator's word, not a schedule.

## [infra] CLAUDE.md's Subagent fan-out bullet reads its Sonnet + Haiku pair as covering the section loops

The bullet names `/fabrik-spec-review` and `/fabrik-plan-review` among "the partitioned review loops", gives them
"Opus on the rule/grammar sections, Sonnet on the rest, no Haiku seat", then continues in the same sentence with
"two cheap finders per slice — one Sonnet and one Haiku … no Opus finder" (D-344), which is scoped to the FILE
loops only. A reader following the literal sentence could build a section slice with the wrong pair. Found by
the chunk-6 review (D-361, B-S3); older than that change and on a governance-sync path, so it waits for the
next deliberate contract edit: scope the pair clause to the file loops. Owner: infra.
