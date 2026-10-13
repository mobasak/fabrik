# Mail routing to the right agent — hub and fabrik-lib

Status: DRAFT
Size: small (≈330 lines, 4 files)

Work item: W-931b6837 · Owner: infra · Seams: D-815 · Inputs: kaizen mails 01M4TC3JVN (measurements) and 01M4TCHD5Y (ownership-map draft, five seams settled) · Research ledger: `docs/reference/research/2026-10-13-mail-routing-ledger.md`

## Personas

**Primary — the operator**, in their own words: *"read and understand our need and tell me how we will perfectly rout mails/kaizen/feedbacks to correct agent in fabrik and in fabrik-lib"*, and *"we need it asap"* (relayed by kaizen in 01M4TC3JVN). Two more, recorded in D-815: *"when a mail arrive to hub, i want it to be assigned to infra, intel, fleet, kaizen properly and automatically"* and *"fabrik-lib has 3 agents and their work must be routed like this too"*.

| Persona | What they need | Duty this spec gives them |
|---|---|---|
| Operator | every mail lands with the agent who will fix it, without chasing | reads the routing report; nothing else |
| Hub receiving agents (infra, fleet, intel, kaizen) | mail for their beat reaches them; mail not for them is visibly someone else's | read the `→ map:` owner shown by `list`/notify/claim; when they re-route, `route()` records why |
| Project sending agents (~46 synced repos) | to know who owns what before they send | read the send-time advisory; correct `--to-agent` or keep it |
| fabrik-lib agents (`fabrik-lib-sentinel`, `fabrik-lib-dev1`, `fabrik-lib-dev2`) | module mail reaches the module owner | the sentinel agrees to the fabrik-lib leg (D7) before it is switched on |
| kaizen | the beats written once; feedback verdicts stay its own | owns the map's WORDING and reruns the pilot against it (D5) |
| infra | the map's CODE: loader, validator, trail, send/read/claim markers, the cron tie-break | builds and maintains every mechanism here |
| Automated: the Haiku tie-break (`claude -p`, one call per path-less unclaimed mail, inside `mail_escalate.py`) | a map-only rubric | returns one agent name or `none`; never a message id |
| Automated: `mail_escalate.py` (cron, every 6 h, hub-only) | the map's owner for unclaimed mail | names the owner on stale mail; runs the tie-break; writes the sidecar |
| Automated: `mail_notify.py` hook (fleet-synced, fail-open) | shows unread mail per session | shows `→ map: <owner>` beside the addressee (read-only, no model) |

**The primary loop, counted (STEP BUDGET = 5):** (1) a project agent sends a finding citing `scripts/sysadmin/dispatch_headroom.py`, addressed to intel; (2) `mail.py send` prints *"the ownership map names infra for scripts/sysadmin/dispatch_headroom.py"* and the sender re-sends to infra — or keeps intel; (3) the mail lands in `/opt/fabrik-mail/fabrik/inbox`; (4) every agent's prompt banner and `mail.py list` show `→ map: infra` beside the addressee — `list --agent infra` lists it for infra too — and `mail.py claim` by a non-owner prints the same advisory; (5) the owning agent claims it. Every feature below traces to one of these steps or to the measure that decides when step 4 may become a move.

## Goal

Every mail reaches the agent that owns its subject, assigned automatically where the map is certain. The owner is decided by ONE machine-readable map per mailbox. Mail with no addressee is addressed from the map at send time; an agent's explicit address is never overwritten by a guess, and mis-addressed mail is shown with its map owner wherever it is read. Moving mis-addressed mail automatically is a later gate, opened only when the measured re-route rate shows the map beats the sender (D5). fabrik-lib's unaddressed mail is addressed the same way from its existing module map, once its sentinel agrees (D7).

## Why this exists

Measured by kaizen on 2026-10-13 over hub mail since 2026-10-01 (01M4TC3JVN):
- Missing addresses are rare: `mail.py send` already refuses unaddressed hub mail (`scripts/mail.py:1079-1090`); 18 of 1,262 hub mails (1.4%) went out unaddressed.
- **Wrong** addresses are the problem: of 143 project mails with a first reply, 15 (10%) were answered by a different agent than the addressee, and those waited a median **125.9 h** for a first reply against **8.4 h** when the addressee answered.
- 224 of 295 project→hub mails were addressed to infra, so beat ambiguity always lands on infra's inbox.
- The beats are written in five places — four charters (`docs/reference/agents/*.md`), `CLAUDE.md`, and the refusal prose at `scripts/mail.py:1083-1088` — and they disagree on five seams (§ The delta D2).
- `route()` (`scripts/mail.py:1756-1806`) rewrites the `agent:` line and keeps no history, so no one can measure the mis-route rate.
- A Haiku classifier given a charter rubric agreed with the actual replier on 64% (90/141) against the sender's own 91% (128/141); its "high confidence" answers were right 64% of the time too.
- fabrik-lib: 83 of 139 mails since 2026-10-01 (60%) were unaddressed, so only the sentinel's arm saw them; 79 (57%) named modules of exactly one owner (01M4TCHD5Y § C).

The approach resolves exactly this: one map ends the five-way disagreement; the send-time step addresses mail automatically where the map is certain and corrects the sender before the mail leaves (where 91% accuracy already lives); every read surface shows the map owner, so a mis-addressed mail is visible to its real owner at once instead of after 125.9 h; and the trail makes the remaining mis-route rate measurable.

## What exists today (grounded)

| Component | Where | Behaviour |
|---|---|---|
| Hub beats | `scripts/mail.py:543` | `HUB_BEATS = ("infra", "fleet", "intel", "kaizen")` |
| Send-time address rule | `scripts/mail.py:1040-1090` | refuses an unknown hub beat; refuses an unaddressed hub send; thread replies inherit the asker (`:1060-1067`) |
| Re-route | `scripts/mail.py:1756-1806` | rewrites `agent:` in place via `os.replace`; inbox only; no trail |
| Claim / ack | `scripts/mail.py` `ack()` | `inbox → archive` rename is the only lock |
| Escalation | `scripts/sysadmin/mail_escalate.py`, crontab `0 */6 * * *`, `FABRIK_MAIL_ESCALATE_DAYS=3` | digests unclaimed mail by age |
| Unread banner | `.claude/hooks/mail_notify.py` (fleet-synced, fail-open) | prints unread summaries per prompt |
| fabrik-lib owners | `/opt/fabrik-lib/.fabrik/module-owners.json` | `{"owners": {agent: [module, …]}}`, 3 agents, every module owned |
| fabrik-lib rule | `/opt/fabrik-lib/CLAUDE.md` § Mail routing (`:306-318`) | route before claim; shared surfaces → sentinel |
| fabrik-lib `mail.py` | `/opt/fabrik-lib/scripts/mail.py` | its own frozen copy (sync-excluded); `agent:` unvalidated for that mailbox |
| Feedback verdicts | `.fabrik/work/config.json` `feedback_owner: "kaizen"`; `scripts/work.py:4583` `_feedback_owner` | all command-feedback queues are kaizen's |
| Mail daemons | none — `systemctl --user list-units --type=path` lists only `traycer-pid-sync.path` (2026-10-13) | no process watches the mail store today, and this design adds none |

## Chosen approach

**D — one ownership map per mailbox, a routing trail, and the map read at every existing touchpoint: send, read, claim and the escalation cron.** It adds no new process. The map owner is applied:
- automatically where the mailbox's own rule allows: an unaddressed send, and fabrik-lib's unaddressed mail;
- as an advisory or a visible `→ map:` owner everywhere else.

A Haiku tie-break runs only inside the existing 6-hourly escalation cron, for unclaimed mail the map cannot place. Field practice backs each part:
- One effective ownership file per repository, last matching pattern wins, and a validator that reports invalid owners and unowned paths (GitHub and GitLab CODEOWNERS, ledger co-1, co-10, co-11).
- Deterministic rules first, with a model layered on the remainder and subordinate to the rules: "Automation Rules always take precedence over Auto Triage suggestions" (Freshdesk, tr-2; Zendesk, tr-1; Anthropic's ticket-routing guide, tr-3).
- Suggestion before automation, automatic action only past a level set from measured outcomes (tr-4, tr-5).
- Quality measured as the rerouting rate, never the router's confidence: "how often tickets need to be reassigned after initial routing … Aim for a rerouting rate below 10%" (tr-8, tr-11).

**The judge panel (Phase 3, D-363), three Sonnet seats blind to the recommendation:**
- **Round 1, approaches A / B / C:** B (map plus a systemd watcher) ranked first 2–1. Judge 2's dissent: B's watcher is the box's first mail daemon and repeats work the per-prompt `mail_notify.py` hook and the existing escalation cron already do. Verified: no mail unit exists; both touchpoints exist.
- **Round 2, approaches B / C / D, after folding that dissent:** D ranked first 3–0; B was killed by all three for failing "build where consume exists" and reviving the August dispatcher's shape.
- **Folded from round 2:**
  - each sidecar suggestion carries the map version it was computed against (judge 2);
  - unmapped mail is shown as unmapped, and shrinking that population is the growth trigger (judge 1);
  - the fabrik-lib leg waits for the sentinel's sign-off (judge 3, already D7).
- **Not folded:** judge 1's proposal to drop the Haiku tie-break altogether. Two judges and kaizen's step 4 keep it, and it is confined to path-less unclaimed mail in the hub-only cron, where it can only suggest.

## The delta

**D1 — Routing trail.** `route()` (`scripts/mail.py:1756`) appends one header line per re-route and keeps the earlier ones: `routed: <UTC ISO> · <by-agent> · <from or -> → <to or -> · <reason>`. `--reason` is required when an addressee already exists. An automatic address set at send (D3a) writes the first `routed:` line with `by: map`. Timestamps use `datetime.now(UTC)`. The trail is what D5 measures.

**D2 — One hub ownership map: `.fabrik/beat-owners.json`.** It uses an ordered rule list, CODEOWNERS semantics (last match wins, co-1) and stdlib `fnmatch` globs:
`{"version": 1, "rules": [{"paths": [...], "topics": [...], "owner": "<beat>", "source": "<D-id or charter line>"}], "floater": "intel"}`.
- **Contents:** the seams of D-815 (kaizen's draft, 01M4TCHD5Y § A–B):
  - (1) a command, fragment or rule pack's wording → kaizen; its rendering or checks → infra;
  - (2) `scripts/sysadmin/dispatch_headroom.py` → infra;
  - (3) a seat brief or `.claude/workflows/fabrik-review-loop.js` → intel; the worktree guard hook → infra;
  - (4) a plain relay → intel as floater; a deploy, live-site or provisioning relay → fleet;
  - (5) a vendored lib → its consuming beat; an unconsumed lib → intel; re-vendoring → infra.
- **Validator:** a new gate check, `scripts/enforcement/check_beat_owners.py`. It refuses an owner not in `HUB_BEATS`, a malformed rule, or a pattern that matches no tracked file. It reports (advisory) the tracked hub paths no rule owns. That is the codeowners-validator practice (co-11), refusing where GitHub silently skips (co-5).
- **Single source:** `mail.py`'s refusal prose (`:1083-1088`) is generated from the map at run time. kaizen rewords each charter's beat section to point at the map (01M4TCHD5Y § SYSTEMIC).
- **Loader:** one stdlib function in `mail.py`, `owner_of(paths, topics, mailbox) -> (owner | None, reason, map_version)`. It returns `None` with the owner list when the cited paths map to several owners, and it never calls a model.
- **Cited paths:** a mail's backticked or `path:line` tokens that exist under the mailbox's repo root.
- **Missing or invalid map:** `owner_of` returns `None` everywhere. That is today's behaviour; fail-open matters in a fleet-synced file.

**D3 — The map at send time (`mail.py send`, deterministic, no model).**
- **(a) Automatic address:** a hub-bound send with no `--to-agent`, `--broadcast` or inherited thread address is addressed to the map owner when `owner_of` returns exactly one. It prints `addressed to <owner> by the ownership map (<reason>)` to stderr. The refusal at `:1079-1090` remains only for mail the map cannot place. This is the operator's "assigned … automatically" applied where the map is certain.
- **(b) Advisory:** when an explicit `--to-agent` differs from a single map owner, `send` prints one advisory line to stderr and delivers as addressed. The sender is right 91% of the time, so it is never a refusal.
- **Where the map is read:** a project's synced `mail.py` reads the hub map at `/opt/fabrik/.fabrik/beat-owners.json` when it exists, and skips silently when it does not (off-box, or a sync-excluded repo).

**D4 — The map at read and claim time (no new process).**
- `mail.py list` prints `→ map: <owner>` beside an addressee the map disagrees with, and `→ unmapped` for mail citing nothing the map knows (judge 1's fold).
- `list --agent X` also lists mail whose map owner is X, marked as such. It stays a filter, never a lock (the existing `route()` docstring).
- `.claude/hooks/mail_notify.py` shows the same `→ map:` marker. It remains fail-open: the lookup runs under the hook's existing exception guard, with a per-call time cap.
- `mail.py claim <id>` by an agent who is not the single map owner prints the advisory before the claim (judge 2, round 1) and claims anyway. `claim`'s atomic rename stays the only lock.
- Nothing here writes to a message file, so nothing can race `claim`.

**D5 — The measure, and when a mis-addressed mail may be moved automatically.**
- **The measure:** the rerouting rate (tr-8), from the D1 trail. For mail whose map owner differed from the addressee, the share that receiving agents re-routed to the map owner and the share re-routed elsewhere, against the sender-address re-route rate (≈10%, 01M4TC3JVN).
- **The report:** `mail.py route-report --days N` prints the rates with their denominators. kaizen reruns its 141-mail pilot against the map before D3a ships.
- **The switch:** auto-moving explicitly mis-addressed project mail is a separate operator gate. It is boarded once the map's rate beats the sender's over at least 50 such mails, and this spec does not build it.
- **Cobra (D-253):** the cheapest way to look good is to stamp every mail with a confident label. So no confidence is stored or measured; only the receivers' re-routes are (tr-11).

**D6 — Escalation and the tie-break (`scripts/sysadmin/mail_escalate.py`, hub-only, existing 6-hourly cron).**
- Its digest names the map owner beside the addressee for every stale mail.
- For unclaimed hub mail that cites nothing the map can place, it makes ONE `claude -p --model haiku` call per mail. That is the low-volume subscription step (`.windsurf/rules/core/65-rag-search.md:108`), sequential, never a fan-out (`.windsurf/rules/core/62-using-subagents.md:103`) and never OpenRouter (`.windsurf/rules/core/62-using-subagents.md:100`).
- **Rubric:** the map file. **Output:** one token validated against `HUB_BEATS ∪ {none}`.
- **Where it lands:** in the sidecar `/opt/fabrik-mail/fabrik/.routing/<id>.json` as `{"suggested": …, "by": "haiku", "map_version": …}`. `list` and the hook show it as `→ haiku: <owner>`.
- **Never:** a message id taken from model output, a write to the message file, or a move.

**D7 — fabrik-lib leg: requested, and gated on the sentinel's sign-off.**
- **The rule (D-815, 01M4TCHD5Y § C):** a send to the `fabrik-lib` mailbox with no `--to-agent`, citing modules of exactly ONE owner in `/opt/fabrik-lib/.fabrik/module-owners.json` (read in place, never copied), gets that owner as `agent:`. It is addressed at send time, by construction, with no second writer on the inbox and no race with `claim`. The sentinel's bare arm still sees it.
- **Otherwise:** several owners or none leave the mail for the sentinel.
- **Before switching on, the sentinel must:** (1) agree in its own ledger (kaizen's 01M4TCHSPX carries the numbers); (2) re-vendor `mail.py` for its own sessions' sends; (3) validate `--to-agent` against its three-name roster.
- **Delivery and switch:** the hub sends this as a request to `fabrik-lib-sentinel` and never edits fabrik-lib (CLAUDE.md HARD STOP, cross-repo). The hub's own send path keeps the fabrik-lib leg off until that agreement is recorded.

**D8 — Feedback and kaizen items.**
- Command-feedback verdicts stay single-owner, kaizen (`feedback_owner`, D-627).
- When a verdict needs code, kaizen's relay mail is addressed with the map: D3 addresses or advises before it leaves.
- No separate router is built for feedback; it rides the mail path.

## Contract deltas

- **New file:** `.fabrik/beat-owners.json` (versioned `"version": 1`).
- **New mail header:** `routed:` (appended).
- **New sidecar store:** `/opt/fabrik-mail/fabrik/.routing/<id>.json`, written only by `mail_escalate.py`'s tie-break (D6).
- **New CLI flags:**
  - `mail.py route --reason`, required when an addressee exists. **Mirror:** a scripted `route` call with no `--reason` on addressed mail now refuses; `grep` finds none in the hub today (verified during planning).
  - `mail.py route-report`.
- **Behaviour change — `send`:**
  - A hub send with no addressee that the map can place is now ADDRESSED instead of refused (D3a). **Mirror:** a test or script relying on that refusal for a single-owner body now sees a delivered mail; the refusal still holds for mail the map cannot place.
  - An advisory line goes to stderr on a mismatch (D3b). **Mirror:** a caller that reads send's stderr as errors sees a non-error line; stdout (the path) is unchanged.
- **Behaviour change — `list --agent X`:** it also lists mail whose map owner is X. **Mirror:** a script counting `list --agent X` lines counts more.
- **Behaviour change — `claim`:** it may print an advisory to stderr; its return and its lock are unchanged.
- **Behaviour change — `mail_notify.py`:** it gains a `→ map:` marker. It is fleet-synced, so its output shape changes in ~46 repos; it stays fail-open.
- No data-contract or UI contract exists for this repo.

## Rejected alternatives

- **A — model router that rewrites the addressee.**
  - Measured at 64% against the sender's 91%, with confidence that does not separate right from wrong.
  - It also repeats the shape the hub already rejected: the August destination-side dispatcher, whose keyword stage was "deleted fifth review: routed-once × 0.8-precision = designed permanent misroutes", rejected as a system for "empty the routed population by construction instead of classifying it after the fact" (`docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` § Rejected alternatives, E).
  - This spec keeps that frame: the map acts at construction (send), and everywhere after it only shows or suggests.
- **B — the map plus a delivery-time watcher** (a systemd user `PathChanged=` unit on the inbox, a 15-minute timer, a sweep writing sidecar suggestions and pinging, and a second watcher setting `agent:` in fabrik-lib's inbox).
  - Killed 3–0 in panel round 2 for failing "build where consume exists": the per-prompt hook and the 6-hourly cron already exist.
  - It adds the box's first mail daemon, which the systemd facts show to be a poor fit: no watch is held while its service runs, files arriving meanwhile do not re-trigger, and it does not fire at start (sd-4, sd-5, sd-9). So it needs a timer crutch.
  - Its fabrik-lib leg is a second writer racing the claim rename.
  - It is the August dispatcher's shape again.
- **C — the map plus a claim-time advisory only.** It passes every challenge but stays silent until someone claims: nothing shows a mis-addressed mail's owner while it waits, and fabrik-lib gets nothing. D includes C's advisory.
- **A send-time REFUSAL on a map mismatch.** It would block the 91%-right sender on the 9% where the map is wrong or the topic spans beats.
- **`DirectoryNotEmpty=` on the inbox.** Level-triggered, it re-fires while files remain (sd-6), and hub mail stays in the inbox until claimed, so it would loop into the start limit and fail (sd-8).
- **Rewriting the message file with `suggested-agent:`.** It races the claim rename: `claim` is an atomic `inbox → archive` rename, and a concurrent `os.replace` would recreate a claimed message in the inbox. Suggestions live in a sidecar instead (D6).
- **YAML for the map.** Needs a parser the fleet-synced `mail.py` cannot assume; JSON matches fabrik-lib's `module-owners.json`.
- **Copying fabrik-lib's map into the hub.** Two copies drift; `send` reads it in place (01M4TCHD5Y § C).
- **Per-agent mailboxes instead of one shared hub mailbox.** It changes every sender's addressing and the claim-once model the hub relies on, for a problem an address and a map already solve.
- **A separate router for feedback verdicts.** They have one owner by ruling (D-627); only their code relays need routing, and those are mail.

## Lifecycle

- **Adoption, in order:**
  1. The map, validator, trail, read-time markers and send-time advisory land together. They are safe from day one because they only add information.
  2. kaizen reruns its 141-mail pilot against the map. D3a (automatic addressing of unaddressed hub mail) is switched on when the map agrees with the actual replier at least as often as the sender's 91% on the mails it can place.
  3. The fabrik-lib leg switches on when the sentinel records its agreement (D7).
  4. kaizen rewords the charters in the same week.
- **Growth:**
  - A new hub file or beat is a map rule with a `source`.
  - Trigger: the validator's unowned-path report plus `route-report`'s count of `→ unmapped` mail. When unmapped mail exceeds 20% of a month's hub mail, the map needs a session, which shrinks the population the tie-break serves (judge 1).
  - A fifth hub agent is a `HUB_BEATS` change plus map rules.
- **The measure over time:** `route-report` monthly. If mail the map placed is re-routed by its receiver more often than the sender's ≈10% over 50 mails, D3a goes back to refusing, and the map is revised before anything else.
- **Degradation:**
  - A missing or invalid map makes `owner_of` return `None`: no marker, no advisory, and unaddressed sends refused as today.
  - A slow lookup in `mail_notify.py` is cut off by its time cap and the banner prints without markers.
  - A `claude -p` failure or timeout in the cron yields `none`.
  - Nothing here can block delivery or a claim.
- **Retirement:** deleting `.fabrik/beat-owners.json` turns every leg off at once. The trail and sidecars stay as history.

## External dependencies

- **Claude Code CLI `claude -p`:** the box's subscription path, already used by `.windsurf/rules/core/60-watchdog.md:198`. No new dependency.
- **Ownership-file practice** (fetched 2026-10-13):
  - GitHub CODEOWNERS: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
  - GitLab CODEOWNERS: https://docs.gitlab.com/user/project/codeowners/reference/
  - codeowners-validator: https://github.com/mszostok/codeowners-validator
- **Routing practice** (fetched 2026-10-13):
  - Freshdesk Auto Triage: https://support.freshdesk.com/support/solutions/articles/50000002117-setting-up-auto-triage
  - Zendesk intelligent triage: https://support.zendesk.com/hc/en-us/articles/5222280338202-Intelligent-triage-use-cases-and-workflows
  - Anthropic ticket-routing guide: https://platform.claude.com/docs/en/about-claude/use-case-guides/ticket-routing
- **systemd path units** (systemd 257, fetched 2026-10-13; they ground the rejection of B, not a dependency of D):
  - https://www.freedesktop.org/software/systemd/man/latest/systemd.path.html
  - https://raw.githubusercontent.com/systemd/systemd/main/src/core/path.c

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| Ownership map + path→owner lookup | BUILD (stdlib, ~60 lines in `mail.py`) | none fits | no fabrik-lib module maps paths to owners; too hub-specific to be a module (fails the reused-by-≥2-project-types bar) |
| Mail transport, claim, notify, escalation | EXTEND | the hub's own `mail.py`, `mail_notify.py`, `mail_escalate.py` | the touchpoints already exist; D adds no process |
| LLM call for the tie-break | none — the box's `claude -p` | — | `subagents`/`llm-dispatch` are pool runtimes, OFF by D-181/D-182 |
| Alerting for escalation | VENDOR as-is | `libs/alerting` (already used by `mail_escalate.py`) | unchanged |

## Shape / infra implications

- Hub-only box tooling; not a deployed service. No scaffold type, no `specs/services` entry, no `shape:` flags, no port, no VPS.
- No new unit, cron or process; the 6-hourly `mail_escalate.py` cron gains the tie-break step.

## Documentation landing sites

- `docs/reference/fabrik-mail.md`: a new § Routing (the map, precedence, automatic addressing, trail, markers, tie-break sidecar, measure). The hub's fabrik-mail reference doc already exists; this extends it, never a second doc.
- `docs/workstation/hooks-index.md`: the `mail_notify.py` row gains the `→ map:` marker.
- `docs/reference/agents/{infra,fleet,intel,kaizen}.md`: beat sections point at `.fabrik/beat-owners.json` (kaizen's edit).
- `INDEX.md`: rows for the map and the validator; the spec and the research ledger rows exist already.
- `CHANGELOG.md`, `docs/DECISIONS.md` (the approach row; the seams are D-815 already).
- fabrik-lib documents its own leg in its `CLAUDE.md` § Mail routing (its sentinel's edit).

## Constraints

The design inherits these; every selection above cites one or is unconstrained.

## Constraints Digest

| Quote | Source |
|---|---|
| Dependencies live in pyproject.toml + uv.lock. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| datetime.now(UTC), never datetime.utcnow() | `.windsurf/rules/core/10-python.md:220` |
| an operator-facing or batch step (a judge run, a one-off classification), never a per-request path | `.windsurf/rules/core/65-rag-search.md:108` |
| a fan-out of claude -p processes from the orchestrator | `.windsurf/rules/core/62-using-subagents.md:103` |
| a direct OpenRouter HTTP call — a dispatch still spends | `.windsurf/rules/core/62-using-subagents.md:100` |
| any in-app log rotation/retention/cleanup | `.windsurf/rules/core/10-python.md:294` |

Rows applied:
- **No new dependency:** stdlib `json` and `fnmatch` only.
- **Timestamps:** the trail's are UTC-aware.
- **Tie-break:** one `claude -p` per path-less mail, never a fan-out or OpenRouter.
- **Logging:** the cron step logs to stdout, which the cron line's existing redirect keeps.

## Validation

- **V1 — trail:** `route` on addressed mail without `--reason` refuses. With it, the message keeps its earlier `routed:` lines and gains one, in order.
- **V2 — validator:** `check_beat_owners.py` refuses an unknown owner and a pattern matching no tracked file, and reports unowned tracked paths; it is green on the shipped map.
- **V3 — `owner_of`:**
  - one owner for a single-owner citation, honouring last match wins;
  - `None` plus the owner list for a mixed citation;
  - `None` for no citation and for a missing or invalid map.
- **V4 — send:**
  - an unaddressed hub send that the map places is delivered to the map owner, with a `routed: … by map` line and the stderr note;
  - one the map cannot place is still refused;
  - a mismatched explicit address delivers as addressed and prints the advisory;
  - with no map file, behaviour is today's.
- **V5 — read and claim:**
  - `list` shows `→ map:` and `→ unmapped` correctly;
  - `list --agent X` includes X's map-owned mail;
  - `claim` by a non-owner prints the advisory and still claims;
  - no message file's bytes change (md5 before and after).
- **V6 — `mail_notify.py`:** shows the marker; when the lookup raises or exceeds its cap, it still prints the banner and exits 0.
- **V7 — the cron tie-break:**
  - called only for path-less unclaimed mail;
  - accepts only `HUB_BEATS ∪ {none}`, so any other output reads `none`;
  - the sidecar carries `map_version`;
  - the message file is untouched.
- **V8 — `route-report`:** computes the rates with their denominators from a fixture inbox and archive.
- **V9 — fabrik-lib leg, once switched on:** an unaddressed single-owner module mail is addressed to that owner, a multi-owner one is left unaddressed, and an addressed one is untouched.

## Cost

Build ≈330 code lines in 4 files plus the map and tests:
- `scripts/mail.py`: ≈170 — map loader, trail, send, list, claim, route-report;
- `.claude/hooks/mail_notify.py`: ≈25;
- `scripts/sysadmin/mail_escalate.py`: ≈70 — owner naming and the tie-break;
- `scripts/enforcement/check_beat_owners.py`: ≈65.

Running cost:
- one `claude -p` Haiku call per path-less unclaimed hub mail, inside the 6-hourly cron (low volume, on the subscription);
- a few milliseconds per map lookup.

## Open unknowns

- **U1 — the pilot result against the map (kaizen).** It gates D3a's switch-on. It is the adoption criterion, not a design blocker.
- **U2 — the fabrik-lib sentinel's agreement.** It gates D7; kaizen's 01M4TCHSPX carries the numbers.
- **U3 — `mail_notify.py`'s time cap.** The current per-prompt hook latency is measured during planning, and the cap is set so the hook's added cost stays under 50 ms on today's inbox.

## Decisions taken

- The five hub seams are D-815 (kaizen; ledger rows, charter lines and an Opus + Fable panel).
- The map is JSON at `.fabrik/beat-owners.json` (not YAML, not under `docs/`), so stdlib readers in fleet-synced `mail.py` can load it.
- Approach D (D-818), the judge panel 3–0 in round 2. Unaddressed mail is assigned automatically where the map is certain (D3a, after the pilot). Explicitly addressed mail is never moved; its map owner is shown, and auto-moving it is a later gate with a measured threshold (D5).
- The fabrik-lib leg ADDRESSES unaddressed mail, which is not a move, and only with the sentinel's agreement.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "perfectly rout mails … to correct agent in fabrik" | IN | D1–D6 |
| I1b | "when a mail arrive to hub, i want it to be assigned to infra, intel, fleet, kaizen properly and automatically" (D-815) | IN, CHANGED | D3a assigns unaddressed mail automatically where the map is certain; moving explicitly addressed mail automatically is D5's later gate, because the map is unproven against the sender's 91% |
| I2 | "… and in fabrik-lib" / "fabrik-lib has 3 agents and their work must be routed like this too" | IN | D7 |
| I3 | "… mails/kaizen/feedbacks" — feedback verdicts | IN | D8 |
| I4 | kaizen items — kaizen's code relays | IN | D8 + send-time advisory |
| I5 | "we need it asap" | IN | Size: small; no new process; markers and advisory ship first, D3a after kaizen's pilot |
| I6 | the operator's original proposal, a Haiku agent (01M4TC3JVN) | IN, CHANGED | D6: tie-break only, inside the existing cron, after measuring 64% vs 91% |
| I7 | kaizen step 1, "A routing trail" | IN | D1 |
| I8 | kaizen step 2, "One canonical ownership map" | IN | D2 |
| I9 | kaizen step 3, at-delivery check, "do NOT move mail a hub agent sent" | IN, CHANGED | D4: shown at read and claim time instead of a delivery watcher (panel round 2); nothing is moved |
| I10 | kaizen step 4, "Haiku only as a tie-break" | IN | D6 |
| I11 | kaizen step 5, "the receiver's re-route rate from the trail is" the measure | IN | D5 |
| I12 | kaizen step 6, "Faster escalation of unclaimed hub mail, using the map's owner" | IN | D6 |
| I13 | kaizen finding 6, "a model call in `send` would run in ~46 repos. The router belongs hub-side" | IN | D3 (no model in `send`), D6 (the model only in the hub-only cron) |
| I14 | 01M4TCHD5Y § B, the five seams | IN | D2 |
| I15 | 01M4TCHD5Y § D, precedence | IN | D3, D4, D6, D7 |
| I16 | 01M4TCHD5Y § E, `/fabrik-task` row 1791886542 (`step --terminal-amend` until phase 3) | OUT-OF-SCOPE | unrelated to routing; kept in kaizen's `/fabrik-task` feedback queue, owned by infra (`python3 scripts/command_feedback_report.py --queue fabrik-task`) |
| I17 | work-item triage routing by beat (proposed in infra's reply to 01M4TC3JVN) | OUT-OF-SCOPE | triage fills queues by count today (`scripts/work.py:5369`); a beat-aware triage would read the same `owner_of`, boarded as backlog item `W-94c6447f` |
