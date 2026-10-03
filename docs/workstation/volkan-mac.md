# Volkan's Mac — the remote coding-infrastructure transfer (handover + runbook)

**Read this first when resuming.** It is written so a session with no memory of the work can catch up
and continue. §§ 2-4, 6 and 7's first three paragraphs are the 2026-09-09 hand-over state — commit
hashes and paths as they were that day. **§§ 1 and 5 were re-measured and CORRECTED on 2026-09-20**
(his address moved twice; one claim in § 5 was wrong for a commit), and § 7 carries a dated block of
what is open now. Where a row says a version, a count or a range, treat it as of its date and
re-derive: his decision ledger alone went from 5 rows to 132 in eleven days. The auto-memory pointers
are `reference-mac-vacbook-ssh`, `reference-mac-review-queue-channel`,
`feedback-mac-tooling-single-writer`, `feedback-port-by-artifact-not-by-language`,
`feedback-port-proof-is-the-run-path`, `feedback-measure-recall-not-just-precision`,
`feedback-one-config-file-is-not-the-denominator` — this doc is canonical, they are the short form.

## 0. Resume checklist (do these in order, ~3 minutes)

1. `ssh mac 'echo ok'` — if it fails, § 1. **Assume the ADDRESS moved before you assume anything
   else**: it has moved three times (last on 2026-10-03), and § 1 gives the fingerprint that proves a
   new one is still his machine.
2. `ssh mac 'ls ~/.claude/review-queue/'` — a `<id>.request.md` with no `<id>.claimed` is work nobody has
   picked up; with `.claimed` and no `.reply.md` they are ON it; a `<id>.reply.md` with no `<id>.ack.md` is
   a reply YOU have not adjudicated. Read replies before anything else; **adjudicate on the clone, never on
   his tree** (§ 6), and **re-derive their claims** — they have been right against me six times now.
3. `cd $SCRATCH/cns && git pull` (or re-clone: `git clone mac:dev/cryptnshare cns`) and note the tip hash —
   every measurement you report names it.
4. `ssh mac 'cd ~/dev/cryptnshare && git branch --show-current && git status --porcelain | wc -l'` — he works on
   `vo-YYYY-MM-DD`; **never push `main`** (his rule; the guard hook denies it mechanically).
5. To give the Mac session work: write `<next-id>.request.md`, `scp` it into the queue. **Nothing else** — its
   self-watch knocks within ~20 s (proved by 012: `scp` alone, knocked and claimed in 17 s). The id must be
   NUMERICALLY newer than the newest at his watch's ARM time or it never knocks — § 5 has the exact
   condition. `wake.py` is the fallback for a dead watch and it is LIVE (§ 5 corrects an earlier claim that
   it was not); the classifier here refuses the post, so the operator runs it.

## 1. Access — `ssh mac`

`~/.ssh/config` on this WSL box: `Host mac` → `HostName 192.168.1.184` (2026-10-03), `Port 22`, `User
volkanozkocak`, `IdentityFile ~/.ssh/id_ed25519`. The Mac is `VacBook-Air.local` (macOS 26.5.2, M2,
**8 GB**, arm64, zsh).

⚠️ **Treat `HostName` as VOLATILE — it has moved three times** (`172.22.16.1:2222` via the
hotspot portproxy → `172.16.100.33` → `192.168.1.4` → `192.168.1.184` on 2026-10-03). If you are handed a
`169.254.x.x` address, that is the Mac's SELF-ASSIGNED fallback (no DHCP lease): no adapter on this box
sits on that link, so ask for `ipconfig getifaddr en0` instead. Do not trust this line; probe it. **Verify the
new address is the SAME MACHINE by fingerprint, never by `StrictHostKeyChecking=no`:**
`ssh-keyscan -t ed25519 <ip> | ssh-keygen -lf -` must print
`SHA256:LUJFAMF1GHz6J5rPd5PaVexCjNscqEgMMFCE9KbJOAc` — the key this box already trusts for every
previous address of his. A match is proof; append that one line to `known_hosts` and nothing else.

⚠️ **The hotspot portproxy is RETIRED (2026-09-18).** The Mac moved off the Windows mobile hotspot onto a
network WSL routes to directly, so `ssh mac` is now a plain hop to the Mac's own address on port 22 — no
`netsh portproxy`, no Windows firewall rule, no WSL-gateway indirection. Verified end to end the day it
changed, and again on 2026-09-20: `ssh mac` reaches the Mac and its own `ipconfig getifaddr en0` agrees.

**When it breaks, TWO moving parts — and the second one is US.** Measured 2026-09-21, one minute
after this section was last rewritten claiming there was only one: `ssh mac` timed out, and the
cause was not his lease at all — **this box had changed networks.** Its Wi-Fi was `192.168.12.56`
with no adapter on `192.168.1.0/24`, so his address was simply off-net from here. Check OUR side
first, because it is one command and it is the half that has moved most often:
`powershell.exe -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4"` — if no adapter shares
his subnet, nothing on his machine is wrong and there is nothing to fix there.

**Then, and only then, HIS lease.** On the Mac `ipconfig getifaddr en0`, then
update `HostName`. Probe reachability from WSL before blaming SSH — `cat < /dev/null > /dev/tcp/<ip>/22`
succeeds when the port is open, and a refusal there is a NETWORK fact, not an auth one.

**The retired hotspot recipe, kept because the laptop travels:** the Mac used to sit on the Windows mobile
hotspot (`192.168.137.68`), which WSL cannot route into; the bridge was `HostName 172.22.16.1` (the WSL NAT
gateway) + `Port 2222` + a Windows `netsh portproxy 0.0.0.0:2222 → 192.168.137.68:22` and a firewall rule
scoped to `172.22.16.0/20`. Two moving parts then: the WSL NAT gateway after a reboot (`ip route | awk
'/default/{print $3}'`) and the Mac's hotspot lease. Windows-side probe that bypassed WSL:
`powershell.exe -Command "(Test-NetConnection 192.168.137.68 -Port 22).TcpTestSucceeded"`. ⚠️ **Mirrored networking (2026-09-23, D-360) makes this recipe obsolete:** WSL has no NAT gateway any more, so
`HostName 172.22.16.1` cannot work. Mirrored mode mirrors Windows' interfaces into WSL, so if he tethers again the
expected recipe is `HostName 192.168.137.68` + `Port 22` directly — no portproxy, no firewall rule. That follows from
the mirrored-mode design and is NOT yet verified with the hotspot up. The old `netsh portproxy 0.0.0.0:2222 → 192.168.137.68:22` and its
allow rule *WSL to Mac SSH (2222)* are still LIVE on Windows: it listens on `0.0.0.0:2222`, and the rule covers
every profile, Public included. It forwards only while the hotspot carries `192.168.137.68`, and removing both
needs an elevated shell.

Non-interactive SSH has no Homebrew on `PATH`: prefix commands with `export
PATH=/opt/homebrew/bin:$HOME/.local/bin:$PATH` (php, npm, flutter, claude live there). Python is the system
**3.9.6** — everything shipped is 3.9-clean, stdlib-only, except the research chain's own venv.

**Hard boundary:** the macOS Keychain is console-session-locked. `claude -p` over SSH says `Not logged in`;
`security find-generic-password` fails; `launchctl asuser` is denied; no passwordless sudo. **No remote
process can drive his Claude.** Only the live VS Code session (and its own `claude -p` children, which
inherit the console context) can run Claude on that machine. That constraint shaped everything below.

## 2. The machine's AI infrastructure (what is installed, where)

| Layer | Location on the Mac | State |
|---|---|---|
| Operating contract (system-wide) | `~/.claude/CLAUDE.md` (203 L) — Part 1 = our project contract re-keyed (FIRST OUTPUT, Orient incl. **item 0 arm the self-watch**, Behavior, fix directive, completion contract keyed to `gate.py`, HARD STOPS, doc-sync table, 6-line FINAL OUTPUT + STATE footer); Part 2 = his Pinegrow/Tailwind rules behind a SCOPE guard. `@~/.claude/MACHINE.md` imported at line 11 | live |
| Machine map | `~/.claude/MACHINE.md` (~70 L) — paths, gate statuses, hooks table, skills, agents, queue protocol, MCPs, pins, branch rule | live |
| Repo working agreement (team-visible, tool-neutral) | in **his repo** `~/dev/cryptnshare/`: `CLAUDE.md` § Conventions (commit `0a12b53`), `CHANGELOG.md`, `docs/DECISIONS.md` (132 rows, highest `D-136` at 2026-09-20 — it is THEIR ledger and it grows fast; read it, never recall a range), `LESSONS_LEARNT.md`, `CONFIGURATION.md` (64 vars), `development/{plans,specs,reviews,rivals}/` and `quality-baseline.json` under its `docs/`, `.fvmrc` (Flutter 3.47.2) | committed on `vo-2026-09-09` |
| Local overlays (untracked, `.git/info/exclude`) | `CLAUDE.local.md` (repo facts + his personal rules), `admin/CLAUDE.md`, `mobile/CLAUDE.md`; master copies at `~/.claude/backups/cryptnshare-local-overlays/` | live |
| Skills (22 ours) | `~/.claude/skills/<name>/SKILL.md` — the 21 ported commands + `/rivals`; each description carries `TRIGGER — EN "…"; TR "…"`, parsed by `skill_router.load_triggers()`. ⚠️ `~/.claude/skills/synced/` appeared 2026-09-18 and is NOT ours — a cloud-synced Anthropic bucket (`docs docx pdf pptx xlsx skill-creator import-memory morning`); the loader skips it, so count 22 and ignore it. `/task` is filed as request 014, pending their apply | live |
| Skill router (EN+TR) | `~/.claude/hooks/skill_router.py` (105 L, reads the triggers; 10/10 routes, 0/10 false) | armed |
| Gate | `~/.claude/bin/gate.py` — stack-detecting: `--quick` (pint · tsc · flutter analyze ×3 · secrets; read-only, the Stop hook's leg) / full (+ `composer test`, `npm run build`, `flutter test --no-pub` ×3, env parity, changelog, **25 vendored corpus checks** as `corpus: <name>` rows, debt ratchet). Statuses `pass·FAIL·WARN·error` → `success·failure·unverified·none`; SKIPPED is never green; timeouts kill the process tree | 40 checks / ~53 s |
| Vendored enforcement corpus | `~/.claude/bin/checks/` (26): our `scripts/enforcement/check_*.py` re-keyed (secrets, changelog, doc_sync, schema_sync = Eloquent↔migrations, openapi_sync = `Route::`↔`ApiDocsPage.tsx`, print_ban + PHP `dd/dump/var_dump` + Dart `print`, env_example = `env()` in app/routes only, doc_sprawl, doc_links, decisions_unique, convergence, plans, plan_quality, test_proposal, citations_resolve, spec_convergence, frozen_chain, stage_artifacts, phase_tests, doc_stubs, retired_terms, configuration_md, readme_md, rivals_dossier, **debt_ratchet** vs his tracked `quality-baseline.json`) + `validate_conventions.py` | live |
| Hooks (`~/.claude/settings.json`, every entry with a timeout) | SessionStart → `stop_gate.py --baseline`, `session_orient.py` · UserPromptSubmit → `review_inject.py`, `mcp_watch.py`, `skill_router.py`, `selfwatch_check.py` · PreToolUse[Bash] → **`guard.py`** (denies push to main/master in every shape, force-push, `git add -A/.`, `commit -a`, `flutter analyze/test` without `--no-pub`; fixture 27/27 · 35/35) · Stop → `stop_gate.py`, `death_marker.py --clear` · StopFailure → `death_marker.py` | live |
| Sounds — **FILED, NOT INSTALLED** (request 016, 2026-09-20) | `~/.claude/bin/claude-sound.sh` + `sound_test.py`. `done` (Stop, Glass) · `attention` (Notification `permission_prompt` + PreToolUse `AskUserQuestion`, Ping) · `failure` (StopFailure — Submarine transient / Sosumi needs-a-human / Basso dead, on the CLI's own error enum). macOS-native because **`timeout`, `setsid`, `flock` and `gtimeout` are ABSENT there and `stat -c` is illegal**: `afplay -t` is the bound, `mkdir` the atomic lock, `stat -f %z` the size — and the grader greps for all five so a re-port cannot reintroduce them. Exits 0 on every path, detaches the player, silent under `CNS_HEADLESS` and `CLAUDE_SOUND=0`, 2 s dedup. 34 checks green on macOS AND Linux, 9 mutants killed. ⚠️ The `Stop` entry is HELD until they say whether a blocking `stop_gate.py` suppresses later Stop hooks — ringing "finished" for a turn about to continue is worse than no sound | pending his word |
| Stop hook | `stop_gate.py` — blocks ONLY a regression vs the session's baseline (his repo is pre-red on pint + 2 analyzers); item-fingerprint acknowledgement (diagnostic items, positions stripped, multiset; a new item re-blocks); state keyed on (git toplevel, session_id); CAP 3; advisory lines for dirty/ahead (throttled); fails open | live |
| Self-watch | `~/.claude/bin/selfwatch.sh <sid>` armed by the agent as a persistent Monitor; consumes `~/.claude/state/selfwatch/<sid>.errparked` (death → per-class backoff → `RESUME:` line) and knocks `QUEUE: request <id> landed` on a new unclaimed request | armed (proof (d) passed) |
| Rule packs | `~/.claude/rules/` — 11, **rewritten for his stack** (Laravel 12/Eloquent+MySQL 8/React+Inertia+Tailwind v3/3 Flutter apps/iyzico+EPPay/Laravel Mail), 45–58 L each, `paths:`-scoped, 0 fleet tokens; `00-this-machine.md` unconditional | live |
| Subagents (native only) | `~/.claude/agents/{reviewer,researcher,design-review}.md` — first body line: native Claude only, `claude -p` for headless, never OpenRouter; seat cap 2–3; `/review`,`/review-scoped` dispatch `reviewer`, `/spec`,`/plan-after-chat` route facts to `researcher` | live |
| Plugins / statusline | `superpowers@claude-plugins-official` + his `frontend-design`; `~/.claude/bin/statusline.sh` (`model · branch ●dirty ↑ahead · gate n✓ m✗`, 0.12 s) | live |
| MCPs (user-level) | serena (uv tool, `serena-agent`), playwright, chrome-devtools, exa, firecrawl — his own keys in `~/.claude.json` (600). `crossSessionInbound: accept` | live |
| Research chain (fabrik-lib vendored) | `~/.claude/lib/` — `deep_research`, `competitor_intel` (+probes), `web_tools.py`, **`llm_dispatch.py` = the `claude -p` primitive**, `doc_crawl`, `claude_evaluator`, `rivals_run.py` (adapted); venv `~/.claude/lib/.venv` (3.9.6 + pyyaml httpx bs4 lxml); keys `~/.claude/lib/.env` (600; Exa + Firecrawl; **no Brave key**) | proven: `complete("OK")` 3.4 s; a real `$0.50` `/rivals` run |
| Review queue (the channel) | `~/.claude/review-queue/` — `<id>.request.md` (ours) · `.claimed` · `.reply.md` / `.questions.md` / `.done.md` (theirs) · `.ack.md` (ours); payloads under `<id>.files/` | 001–012 closed |
| Backups | `~/.claude/backups/` — every replaced file, timestamped (`*-pre006`, `*-pre009`, `*-pre011`, …) | — |

Not transferred, with the reason (so nobody re-proposes): the 15 fleet commands (deploy triad, release,
epics/vision, catchup, decommission, upstream, rules-review, workflow-review — `fabrik apply`/VPS/N-agent
concepts); 41 enforcement scripts (8 deploy, 18 hub machinery, 8 Python-only, 2 heavy deps); the
hub hooks for sounds, quota rotation, mail, agent charters, run records, scratch sweep; session-recall
(needs a Postgres service); fabrik-lib `api-smoke-test` (FastAPI-only), `ui-verify` (later), the
`subagents` pool (OFF, and non-Claude providers are forbidden there), `web-scrape`'s browserless leg.

## 3. Standing rules (Volkan's and ours — his outrank ours)

- **Never push `main`; work on his personal branch** (`vo-YYYY-MM-DD`); pushing HIS branch is allowed
  and the contract says "push your branch when the piece of work is done". `guard.py` enforces it.
- **Teammates are isolated by the branch, not by keeping things out of the repo.** Repo-side conventions
  may land freely on his branch (with his word before a commit). Only `main` is shared.
- **One writer on `~/.claude` tooling: the Mac session.** We file a MODIFY request with the files under
  `<id>.files/`; it applies, proves and deploys. (Two writers collided once — 17:31 vs 17:39 — the fix
  is this rule.) Repo commits: its hands, his word.
- **Measure on the clone at the branch tip, name the hash; never put probe files in his tree** (its gate
  saw mine and reported a FAIL that was ours). Recall AND precision: a must-hit fixture before a corpus
  count ("0 hits in 950 files" hid the repo's own escrow key).
- **A port is proven by the run path at 3.9**, not by `ast.parse(feature_version)` + import (`datetime.UTC`,
  `zip(strict=)`, `lxml` at first use, and an unbounded `claude -p` all passed import-smoke and failed
  live).
- **Subagents: native Claude only; `claude -p` for headless; never OpenRouter** on his machine.
- **Auto-mode classifier boundaries (this box):** it refuses posting into his session's socket, writing
  his `crossSessionInbound`, writing queue files whose text orders the other session, deploying a
  secrets-scanning `gate.py` into his `~/.claude/bin`, and reading his `~/.claude/state/`. Do not route
  around them: build and prove locally, then the operator runs the one-line `scp`/`ssh`, or the Mac
  session applies it from a MODIFY. Plain `scp` of a request file and reading the queue always pass.
- The Mac session's own standing rule: **before ending a turn it drains the queue** (takes any unclaimed
  request) — plus the self-watch knocks the moment one lands.

## 4. Request ledger (001–025) — what each did, in one line

| id | kind | outcome |
|---|---|---|
| 001 | author-blind review of the first skills/gate/hook | 3 HIGH + 20 findings; `php artisan pint` does not exist; no hook timeouts; `npm run build` mutates — all fixed |
| 002 | review of the fixes | 9 findings by execution: ack-by-name swallowed regressions, two sessions shared state, timeout=FAIL, orphaned `tsc`, `npx --no-install` dead, silent truncation — fixed (item fingerprints, per-session key, `error` status, process-tree kill) |
| 003 | attack the fingerprint regex | items-not-lines multiset; ownership of `~/.claude` handed to the Mac session |
| 004 | Phase 4 (secrets/env-parity/changelog) + Phase 5 (doc conventions) | secrets was 5 FP / 4 FN of 15 → fixed by them (fixture 19/19, moved into `--quick`); Phase 5 committed `907a060` |
| 005 | answers (pdfrx, doc wording, MODIFY protocol) | `.fvmrc` 3.47.2 (`c57cc3e`), pdfrx 0.4.7 + liboqs relink → desktop suite 111/111 (`d7f5222`), D-004 |
| 006 | the 29 re-keyed corpus checks + gate + hook + 3 doc drafts | deployed with 3 adaptations; full gate 40 checks / 52.7 s; `CONFIGURATION.md`, README, D-001..003 tool-neutral, watermark link fixed (`3590dfb`…`e5e1956`) |
| 007 | operating contract (user-level) + repo working agreement | applied; Part 2 byte-identical; `0a12b53`; Volkan told it we are authoritative |
| 008 | Q1–Q11 + rules + agents + router | packs **rewritten** for the stack (right refusal); router replaced (105 L, 0 false routes); agents proven via `claude -p`; debt ratchet + `~/dev/cryptnshare/docs/quality-baseline.json` (`8156894`, D-005) |
| 009 | hooks (guard/orient/mcp_watch), plugin, statusline, MACHINE.md | guard hardened +9 shapes; orient/mcp_watch rewritten small; superpowers; 0.12 s statusline; map imported |
| 010 | fabrik-lib research chain + `/rivals` | 4 run-path defects fixed by them (D1–D4), D5 engine defect filed upstream; dossier 12/6/127 at `$0.504`, `partial`, **uncommitted** |
| 011 | self-watch (death resume + queue knock) | armed; (a)(b)(c)(e) proven; **CNS_HEADLESS** defect class found (headless children ran all hooks) and fixed |
| 012 | proof (d) | `scp` alone → knocked and claimed in 17 s; **socket wake retired** |
| 013 | *(their notice, unprompted — no request of ours)* | `guard.py` denied two legitimate commands because `check()` scanned the whole command string and matched PROSE about `git push --force` inside a heredoc. Their fix: strip heredoc bodies, require the git token at a command position; fixture 29/29 deny · 39/39 allow. **Worth mirroring — our own guards scan command strings the same way.** Also corrects a rule they had misread: they push THEIR OWN branch when work is done; only `main` is the co-worker's |
| 016 | MODIFY: the sound layer (`claude-sound.sh` + `sound_test.py` + a settings fragment) | filed 2026-09-20. macOS-native: `afplay -t` is the time bound because `timeout`/`setsid`/`flock`/`gtimeout` are ABSENT there and `stat -c` is illegal — the grader greps for all five. 34/34 on macOS and on Linux; 9 mutants killed. **Installed on Volkan's word 2026-09-20** — three settings entries as written; the `Stop` entry replaced by `_ring_done()` inside `stop_gate.py`, because hooks run in PARALLEL and a sibling would ring on a stop that hook is about to block (proven in all three branches against a stub). Their discrepancy was right: one grader check ran the script against the REAL log, lock dir and afplay with only `CLAUDE_SOUND=0` in the way — fixed as a class in 023. Acked late, in 023 |
| 015 | INSTALL APPROVED for `/task` | Volkan approved the install 2026-09-20 (*"i approve installation"*); relayed because their session correctly refused to install on a request alone. Carries the amended 160-line file, answers their proof-2 question (the gate has NO jurisdiction over `~/.claude` — no repo, no staged set; the router loader run against the LIVE skills tree is the whole of the gate-equivalent), and carried a WRONG finding — it reported `crossSessionInbound` absent from a one-file search; it is set at `~/.claude/settings.json:101` and their session refuted it in one `grep` |
| 014 | MODIFY: `/task`, our `/fabrik-task` ported | filed 2026-09-20 with `014.files/SKILL.md`; every hub dependency re-keyed (gate, ledger shape, rule-pack `paths:`, review/spec names) and the honest gap named — their machine has no run record, so the SIZE gate is self-graded and phase 5's commit re-measure is its only counter. Router + collision proven against their own loader before filing |
| 017 | PING — channel check after the move to `192.168.1.184` | claimed by the self-watch ~60 s after the `scp`, no human prompt; round trip proven on the new address (2026-10-03) |
| 018 | MODIFY: `/task` to `/fabrik-task` lane v2 (D-507) + three measured speed rules | applied less row 2 (Volkan's `~/.claude/CLAUDE.md` §5a then ranked a heavy surface above his four categories); speed rules from his 34 runs: batch independent reads into one message, hand the phase-4 reader the diff, `/clear` between units (one 12-unit session reached ~830k tokens a turn). Hub D-532 |
| 019 | MODIFY: the batching rule names round trips, not tools | their discrepancy: "never a Bash call" collided with a harness instruction that mandates Bash — the measurement was about round trips |
| 020 | MODIFY: phase-1 re-wrap (their own proposed text) | applied; the 021 questions were then appended AFTER this close — read the whole queue before calling anything done |
| 021 | *(their questions, at Volkan's direction — no request of ours)* | row 2 vs lane v2; does a row-5 module test eject his four categories? Filed as `.questions.md` with no `.request.md`, the protocol's one session-initiated shape |
| 022 | ANSWERS to 021 | Volkan chose "Yes to both halves" on his own §5a sentence: a heavy surface stays in the lane under the full `/review`; row 5 fires only on a BREAKING change to a contract a shipped client reads, an additive field stays in the lane. They caught a defect in our §5a diff (line 45 edited, the subject on line 44) before he saw it. Hub D-533 supersedes D-532 |
| 023 | MODIFY: `sound_test.py` cannot escape its sandbox + the overdue 016 ack | every invocation through `Sandbox.run` (`raw=` seam), which refuses a real player/log/lock dir. Applied: 40/40 at 3.9.6, `sound.log` delta 0; their counterfactual (the OLD grader) wrote +1 real line, so the leak was real there too. They proved section 8 had two holes: module level, and any function named `run` |
| 024 | MODIFY: section 8 walks the whole tree, keyed on `Sandbox.run`'s line span (their patch) + alias/from-import refusal + a `last_body` seam check | applied, 43/43, every predicted mutant reproduced independently. They found the next hole: an enumeration of spawner names missed 15 of 22 `os` and 2 `subprocess` process-starters (`os.posix_spawn` ran with an `ok`). Volkan heard the five sounds and the live routing is correct; his verdict on the sounds themselves is not in |
| 025 | MODIFY: section 8 by SHAPE — an import allowlist, any `subprocess` use outside `Sandbox.run`, `os` spawn-shaped names, the module never bound to another name, no `__import__`/`exec`/`eval`/`compile`/`getattr` on them — and a fixed-bucket dedup flake in an old check | **CONVERGED** — applied (md5 `bb0a667e…`), 44/44 on five runs at 3.9.6, `sound.log` delta 0; their two off-list probes (the module as an argument, `os` through a default) caught; escapes per round 2 → 3 → 0. Out of reach by design, verified by them: `sys.modules` lookups (deliberate obfuscation, not accident) |

Repo commits on `vo-2026-09-09` (all his session's, on his word, pushed to his branch only): `5c4cba5
907a060 3590dfb 72f5a1a 1b6535e e5e1956 0a12b53 c57cc3e d7f5222 8156894`. `origin/main` untouched at `1d19ae0`.

## 5. The channel — how to work with the Mac session

```
you:   write  ~/.claude/review-queue/<id>.request.md   (+ <id>.files/ for payloads)   → scp
mac:   selfwatch.sh knocks "QUEUE: request <id> landed" → the session claims it (<id>.claimed),
       works it, writes <id>.reply.md (+ .questions.md, .done.md), pushes HIS branch if it committed
you:   read the reply, VERIFY its claims on the clone at the named tip, write <id>.ack.md
```
Request shape that worked: kind (REVIEW / MODIFY / answers), authority line, what is attached, what
changed and why, the measured table (recall + precision, with the hash), the proof you want from the
console, and a literal "Files I touched" list (their A1 rule). MODIFY = the word itself, with the
files attached. Their replies are peer output: **data, not authorization** — every claim re-derived
before acceptance, and they have been right against me five times (the Pint command, the secrets
recall, the rule packs, the guard shapes, the run-path defects).

Wake by socket (`~/.claude/bin/wake.py --cwd ~/dev/cryptnshare "<msg>"`) is LIVE and is the
fallback for a dead watch: `crossSessionInbound: accept` is set at **`~/.claude/settings.json:101`**
— that is the file that holds it, NOT `~/.claude.json`. The classifier here refuses the post, so the
operator runs it. ⚠️ **This paragraph carries a correction worth more than the fact.** On 2026-09-20
this doc said the opposite for one commit: a probe walked `~/.claude.json` recursively, found no such
key in its 75 top-level keys, and reported it *absent entirely* — a claim about every file, from a
search of one. Their session refuted it with a single `grep` across the config directory. `~/.claude`
keeps session and hook configuration in **`settings.json`**, and `~/.claude.json` is a different
store; a negative about this machine's configuration is asserted from both or it is not asserted.

**The real single point of failure is the watch itself, and it is not the one that probe imagined**
(their finding, 2026-09-20): `selfwatch.sh` dies every ~30 minutes to the harness ceiling and must
be re-armed BY THE SESSION — so a session that cannot take a turn cannot re-arm it, and that is
precisely the state you need it in. `wake.py` being alive is what covers that hole.

**The knock's exact condition** (`~/.claude/bin/selfwatch.sh:118,124-129`): a `<id>.request.md`
whose `<id>` is NUMERICALLY newer than the newest at ARM time, with neither `<id>.claimed` nor
`<id>.reply.md` present. It prints once per id. Two consequences worth knowing — a request filed
with an id at or below the newest-at-arm never knocks, and re-filing an id that already has a
`.reply.md` never knocks either. Check the watch is running for the live session before relying on
it: `pgrep -fl 'selfwatch.sh <sid>'`.

## 6. Local scratch on this box (regenerable)

`$SCRATCH/cns/` — a clone of his repo (`git clone mac:dev/cryptnshare cns`) for measurement;
`$SCRATCH/port/` — every payload as shipped (`006.files` … `011.files`, requests, acks), the
`checks/` re-key workspace, a 3.9 venv (`uv python install 3.9`); `$SCRATCH/v3/`, `v4/` — the gate
generations. All regenerable from this doc + the hub sources; nothing here is a source of truth.

## 7. Open items

**OPEN NOW (2026-10-03).**

- **Dedup buckets are fixed, not sliding** — a repeat straddling a 2 s boundary rings twice. Reported in 025, not changed: his call.
- **Volkan's verdict on the five sounds** — all five played for him on 2026-10-03 and the live routing is correct; whether any two are too close is his word, not yet given.
- **`/task` router gap, reported and deliberately NOT patched** — "Paylaşım ekranında küçük bir değişiklik yapalım" does not route
  (a modifier between `ekranında` and `değişiklik`); loosening the exact-substring matcher would trade away its zero false routes.
- **Swap pressure** — 8 GB RAM, 4.8 of 6 GB swap in use on 2026-10-03; slows every run and the reader seat. His call, not a skill edit.

**Closed since 2026-09-21:** `/task` installed (014/015) and moved to lane v2 with his §5a rewritten on his own yes (018-022,
D-533); the sound layer installed (016).

Two things they raised that we have NOT built, deliberately, and should not drift into building:
their decision-row gate (comparing staged code files to the backticked paths in the newest
`docs/DECISIONS.md` *where* cell — it needs their ledger convention tightened first, so it is its own
request), and anything that installs itself around the single-writer rule.

### As of hand-over (2026-09-09)

**Volkan's decisions (recommendations sent in `010.ack.md`):** provision a free Brave Search API key
(makes the free leg real; until then `RIVALS_ALLOW_DEGRADED_LEGS=brave`); one more `/rivals` run at
`--budget 0.75` on the same job id (checkpoints re-bill nothing) to fill the starved synthesis; commit
only a complete dossier. Also his: the `pdfrx`/liboqs `@rpath` note in LESSONS, and `/context` after
his next restart to confirm the rules/map loaded.

**Filed against our own fleet from what the port exposed:** `01M23HB2MA13P72TZGHQ773C1S` (infra —
headless `claude -p` children run `mail_notify`/`mcp_watch` unguarded), `01M23K7XTKEKSZKT36YSQ6PGDR`
(infra — `scripts/rivals_run.py:_make_llm` spawns an unbounded agent turn; fix verbatim),
`01M23K7CH28KP6X8NBSJ6EKSHZ` (fabrik-lib — synthesis starved by the shared ceiling; fallback matrix
marks `us` ❌), `01M23CRZZ5E6D5DQ3E3RBN4HNV` (infra — `FINAL_GATE_WORKFLOW.md` stale vs the code).

**Candidates never started (measured as later):** `ui-verify` (once `/ui-design` is used there),
`INDEX.md` adoption (rejected for now — `CLAUDE.md` § Architecture is the map), a Haiku router tier
(rejected: 0 misses without it, 8 GB).

## Related scripts
None on the hub side — every script this doc names lives on the Mac under `~/.claude/`; their sources
here are `scripts/enforcement/check_*.py`, `templates/governance/CLAUDE.md`, `.claude/hooks/*.py`,
`.windsurf/rules/core/*.md`, `commands/_sources/*.md`, `/opt/fabrik-lib/{deep-research,
competitor-intel,web-tools,llm-dispatch,doc-crawl,claude-evaluator}`, `scripts/rivals_run.py`.
