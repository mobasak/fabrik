# Mail routing to the right agent — hub and fabrik-lib

Status: DRAFT
Size: small (≈340 lines, 4 files)

Work item: W-931b6837 · Owner: infra · Inputs: kaizen mails 01M4TC3JVN (measurements) and 01M4TCHD5Y (ownership-map draft, five seams settled) · Research ledger: `docs/reference/research/2026-10-13-mail-routing-ledger.md`

## Personas

**Primary — the operator**, in their own words: *"read and understand our need and tell me how we will perfectly rout mails/kaizen/feedbacks to correct agent in fabrik and in fabrik-lib"*, and *"we need it asap"* (relayed by kaizen in 01M4TC3JVN). A second line, relayed in 01M4TCHD5Y: *"fabrik-lib has 3 agents and their work must be routed like this too"*.

| Persona | What they need | Duty this spec gives them |
|---|---|---|
| Operator | every mail lands with the agent who will fix it, without chasing | reads the routing report; nothing else |
| Hub receiving agents (infra, fleet, intel, kaizen) | mail for their beat reaches them; mail not for them is visibly someone else's | act on a `suggested-agent` ping; when they re-route, `route()` records why |
| Project sending agents (~46 synced repos) | to know who owns what before they send | read the send-time advisory; correct `--to-agent` or keep it |
| fabrik-lib agents (`fabrik-lib-sentinel`, `fabrik-lib-dev1`, `fabrik-lib-dev2`) | module mail reaches the module owner | the sentinel agrees to the fabrik-lib leg (D7) before it is switched on |
| kaizen | the beats written once; feedback verdicts stay its own | owns the map's WORDING and reruns the pilot against it (D5) |
| infra | the map's CODE: loader, validator, sweep, trail | builds and maintains every mechanism here |
| Automated: the routing sweep (systemd user unit) | runs after each new inbox file and on a timer | computes the owner, writes the sidecar suggestion, pings |
| Automated: the Haiku tie-break (`claude -p`, one call per path-less mail) | a map-only rubric | returns one agent name or `none`; never a message id |
| Automated: `mail_escalate.py` (cron, every 6 h) | the map's owner for unclaimed mail | escalates to the owner, not only the addressee |
| Automated: `mail_notify.py` hook | shows unread mail per session | shows the suggestion beside the addressee (read-only) |

**The primary loop, counted (STEP BUDGET = 5):** (1) a project agent sends a finding citing `scripts/sysadmin/dispatch_headroom.py`, addressed to intel; (2) `mail.py send` prints *"the ownership map names infra for scripts/sysadmin/dispatch_headroom.py"* and the sender re-sends to infra — or keeps intel; (3) the mail lands in `/opt/fabrik-mail/fabrik/inbox`; (4) the sweep sees it, maps the cited path to infra, and — when the addressee is not infra — writes `suggested-agent: infra` to the sidecar and pings infra; (5) the owning agent claims it. Every feature below traces to one of these steps or to the measure that decides when step 4 may become a move.

## Goal

Every mail reaches the agent that owns its subject. The owner is decided by ONE machine-readable map per mailbox, and an agent's explicit address is never overwritten by a guess. Hub routing stays a suggestion until the measured re-route rate shows it beats the sender (D5). fabrik-lib's unaddressed mail is addressed from its existing module map once its sentinel agrees (D7).

## Why this exists

Measured by kaizen on 2026-10-13 over hub mail since 2026-10-01 (01M4TC3JVN):
- Missing addresses are rare: `mail.py send` already refuses unaddressed hub mail (`scripts/mail.py:1079-1090`); 18 of 1,262 hub mails (1.4%) went out unaddressed.
- **Wrong** addresses are the problem: of 143 project mails with a first reply, 15 (10%) were answered by a different agent than the addressee, and those waited a median **125.9 h** for a first reply against **8.4 h** when the addressee answered.
- 224 of 295 project→hub mails were addressed to infra, so beat ambiguity always lands on infra's inbox.
- The beats are written in five places — four charters (`docs/reference/agents/*.md`), `CLAUDE.md`, and the refusal prose at `scripts/mail.py:1083-1088` — and they disagree on five seams (§ The delta D2).
- `route()` (`scripts/mail.py:1756-1806`) rewrites the `agent:` line and keeps no history, so no one can measure the mis-route rate.
- A Haiku classifier given a charter rubric agreed with the actual replier on 64% (90/141) against the sender's own 91% (128/141); its "high confidence" answers were right 64% of the time too.
- fabrik-lib: 83 of 139 mails since 2026-10-01 (60%) were unaddressed, so only the sentinel's arm saw them; 79 (57%) named modules of exactly one owner (01M4TCHD5Y § C).

The approach resolves exactly this: one map ends the five-way disagreement, the send-time advisory corrects the sender before the mail leaves (where 91% accuracy already lives), the sweep catches what the sender kept, and the trail makes the remaining mis-route rate measurable.

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
| systemd user path units | `~/.config/systemd/user/traycer-pid-sync.path` | the precedent this box already runs |

## Chosen approach

**B — one ownership map per mailbox, a routing trail, a send-time advisory, and a delivery-time suggestion sweep; a model only as the tie-break for mail that cites nothing the map can read.** Field practice backs each part:
- One effective ownership file per repository, last matching pattern wins, and a validator that reports invalid owners and unowned paths (GitHub CODEOWNERS and GitLab, ledger co-1, co-10, co-11).
- Deterministic rules first, with the model layered on the remainder and subordinate to the rules: "Automation Rules always take precedence over Auto Triage suggestions" (Freshdesk, tr-2; Zendesk, tr-1; Anthropic's ticket-routing guide, tr-3).
- Suggestion before automation; automatic action only past a level the operator sets from measured outcomes (tr-4, tr-5).
- Quality measured as the rerouting rate, not the router's confidence: Anthropic's guide sets it as "how often tickets need to be reassigned after initial routing … Aim for a rerouting rate below 10%" (tr-8, tr-11).

The judge panel's ranking and any dissent are recorded in § Decisions taken.

## The delta

**D1 — Routing trail.** `route()` (`scripts/mail.py:1756`) keeps every earlier `agent:` and appends one header line per re-route: `routed: <UTC ISO> · <by-agent> · <from or -> → <to or -> · <reason>`. `--reason` is required when an addressee already exists. `send` writes nothing new: the original `agent:` is the first entry by construction. Timestamps use `datetime.now(UTC)`. The trail is what D5 measures.

**D2 — One hub ownership map: `.fabrik/beat-owners.json`.** It uses an ordered rule list, CODEOWNERS semantics (last match wins, ledger co-1), and stdlib `fnmatch` globs:
`{"version": 1, "rules": [{"paths": [...], "topics": [...], "owner": "<beat>", "source": "<D-id or charter line>"}], "default": "sender", "floater": "intel"}`.
- **Contents:** kaizen's draft (01M4TCHD5Y § A–B) verbatim, including the five settled seams:
  - (a) a command, fragment or rule pack's WORDING → kaizen; its rendering or a check that reads it → infra (D-627);
  - (b) `scripts/sysadmin/dispatch_headroom.py` → infra (D-195);
  - (c) a seat brief or `.claude/workflows/fabrik-review-loop.js` → intel; the worktree guard hook → infra (D-643);
  - (d) a plain relay between projects → intel as floater; a deploy, live-site or provisioning relay → fleet;
  - (e) a vendored lib → the beat that consumes it; libs with no hub consumer → intel; re-vendoring plumbing → infra.
- **Validator:** a new gate check, `scripts/enforcement/check_beat_owners.py`. It refuses an owner not in `HUB_BEATS`, a malformed rule, or a pattern matching no tracked file. It reports (advisory) tracked hub paths no rule owns. That is the codeowners-validator practice (co-11), refusing where GitHub silently skips (co-5).
- **Single source:** `mail.py`'s refusal prose (`:1083-1088`) is generated from the map at run time. kaizen rewords each charter's beat section to point at the map rather than restate it (kaizen's own offer, 01M4TCHD5Y § SYSTEMIC).
- **Loader:** one stdlib function in `mail.py`, `owner_of(paths, topics, mailbox) -> (owner | None, reason)`. It returns `None` when the cited paths map to more than one owner, and it never calls a model.
- **Path extraction:** a mail's cited paths are its backticked or `path:line` tokens that exist under the mailbox's repo root.

**D3 — Delivery-time suggestion sweep (hub-side only).** A new `scripts/sysadmin/mail_route_sweep.py` runs from a systemd user path unit with `PathChanged=/opt/fabrik-mail/fabrik/inbox` (fires on a file renamed in, ledger sd-1, sd-2) plus a 15-minute timer.
- **Why the timer:** a path unit holds no watch while its service runs, does not re-trigger for files that arrived meanwhile, and does not fire on files already present at start (sd-4, sd-5, sd-9).
- **What one run does:** an idempotent pass over EVERY inbox message that has no sidecar entry yet, so a missed event is caught by the next event or the timer.
- **Per message:**
  - compute `owner_of`;
  - when an owner exists, differs from the addressee and the sender is not a hub agent (01M4TCHD5Y § D.1), write `{"suggested": owner, "reason": …, "by": "map"}` to the sidecar `/opt/fabrik-mail/fabrik/.routing/<id>.json` — a dot-directory, ignored by path units (sd-11) and by every `*.md` glob;
  - ping the suggested agent with one `SendMessage`-free line in the existing notify channel. `mail_notify.py` prints `→ suggested: <owner>` beside the addressee.
- **Never touched:** the message file itself. Rewriting it would race `claim`'s inbox→archive rename and could resurrect a claimed message. The sweep never moves mail.
- **Mixed or no owner:** a mail mapping to several owners gets `{"suggested": null, "owners": [...]}`, listed and never guessed (co-12). A mail citing no mapped path or topic goes to D4.

**D4 — Haiku tie-break, path-less mail only.** For a hub mail with no mapped path or topic, the sweep runs ONE `claude -p --model haiku` call. That is the low-volume subscription path for a one-off classification (`.windsurf/rules/core/65-rag-search.md:108`), never a fan-out (`.windsurf/rules/core/62-using-subagents.md:103`) and never OpenRouter (`.windsurf/rules/core/62-using-subagents.md:100`).
- **Rubric:** the map file itself, not charter prose.
- **Output:** one token from `HUB_BEATS ∪ {none}`, validated against that set. Any other output reads as `none`.
- **Message ids:** taken only from the file name, never from model output (Haiku mangled one id in kaizen's pilot).
- **Effect:** a suggestion with `by: "haiku"`, never a move. The map always outranks it (tr-2).

**D5 — The measure, and when a suggestion may become a move.**
- **The measure:** the rerouting rate (tr-8), computed from the D1 trail. For mail that carried a map or Haiku suggestion: the share the RECEIVING agent re-routed away from the suggested owner, against the sender-address re-route rate (≈10% today, 01M4TC3JVN).
- **The report:** `mail.py route-report --days N` prints both rates with their denominators. kaizen reruns its 141-mail pilot against the map before the sweep is switched on.
- **The switch:** auto-move (`route()` called by the sweep for project mail only) is a separate operator gate. It is boarded once the map's re-route rate is below the sender's over at least 50 suggested mails; this spec does not ship it.
- **Cobra (D-253):** the cheapest way to look good is to stamp every mail with a confident label. So the router's own confidence is never stored or measured; only the receivers' re-routes are (tr-11).

**D6 — Escalation uses the owner.** `mail_escalate.py` addresses an unclaimed mail's digest line to the sidecar's suggested owner when one exists, beside the addressee. The measured cost of a wrong address is days (125.9 h).

**D7 — fabrik-lib leg, by request, gated on the sentinel's agreement.**
- **The rule (01M4TCHD5Y § C):** an unaddressed fabrik-lib mail whose cited modules map to exactly ONE owner in `/opt/fabrik-lib/.fabrik/module-owners.json` gets its `agent:` SET to that owner. That addresses it rather than moving it; the sentinel's bare arm still sees it. Several owners or none → left for the sentinel, with the named owners in the sidecar.
- **How it runs:** the same sweep, a second watched inbox (`/opt/fabrik-mail/fabrik-lib/inbox`), reading fabrik-lib's map in place, never copied into the hub.
- **Before it is switched on, the sentinel must:** (1) agree to the rule in its own ledger; (2) re-vendor `mail.py` with D1's trail; (3) validate `--to-agent` against its three-name roster.
- **Delivery:** the hub never edits fabrik-lib; this goes as a request mail to `fabrik-lib-sentinel` (CLAUDE.md HARD STOP, cross-repo).

**D8 — Feedback and kaizen items.**
- Command-feedback verdicts stay single-owner, kaizen (`feedback_owner`, D-627).
- When a verdict needs code, kaizen's relay mail is addressed with the map: the send-time advisory (step 2) shows the owner before it leaves, so a `dispatch_headroom.py` verdict goes to infra, not intel.
- No separate router is built for feedback; it rides the mail path.

**Send-time advisory (step 2 of the loop).** `mail.py send` to the hub computes `owner_of` from the body. When it names an owner other than `--to-agent`, it prints one advisory line to stderr and sends anyway: advisory, not refusal, because the sender is right 91% of the time. It is a deterministic map read, so it is safe in fleet-synced `mail.py`. A project's `mail.py` reads the hub map at `/opt/fabrik/.fabrik/beat-owners.json` when that file exists and skips silently when it does not (off-box or sync-excluded).

## Contract deltas

- **New file:** `.fabrik/beat-owners.json` (versioned `"version": 1`).
- **New mail header:** `routed:` (appended).
- **New sidecar store:** `/opt/fabrik-mail/<mailbox>/.routing/<id>.json`.
- **New CLI flags:**
  - `mail.py route --reason`, required when an addressee exists. **Mirror:** a scripted `route` call with no `--reason` on addressed mail now refuses; `grep` finds none in the hub today (verified during planning).
  - `mail.py route-report`.
- **Behaviour change:** `mail.py send` prints an advisory line on stderr. **Mirror:** a caller that parses send's stderr as errors would see a non-error line; `send`'s stdout (the path) is unchanged.
- No data-contract or UI contract exists for this repo.

## Rejected alternatives

- **A — model router that rewrites the addressee.**
  - Measured at 64% against the sender's 91%, with confidence that does not separate right from wrong.
  - It also repeats the shape the hub already rejected: the August destination-side dispatcher, whose keyword stage was "deleted fifth review: routed-once × 0.8-precision = designed permanent misroutes", rejected as a system for "empty the routed population by construction instead of classifying it after the fact" (`docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` § Rejected alternatives, E).
  - This spec keeps that frame: the send-time advisory acts at construction, and the sweep only suggests.
- **C — sender-side only (map + trail + send-time check, no sweep).** Cheaper, but it cannot reach:
  - mail from a project whose synced `mail.py` predates the advisory;
  - fabrik-lib's frozen copy;
  - thread replies that inherit an address;
  - the 60% of fabrik-lib mail that arrives unaddressed.
- **A send-time REFUSAL on a map mismatch.** It would block the 91%-right sender on the 9% where the map is wrong or the topic spans beats.
- **`DirectoryNotEmpty=` on the inbox.** Level-triggered, it re-fires while files remain (sd-6), and hub mail stays in the inbox until claimed, so it would loop into the start limit and fail (sd-8).
- **Rewriting the message file with `suggested-agent:`.** It races the claim rename (see D3).
- **YAML for the map.** Needs a parser the fleet-synced `mail.py` cannot assume; JSON matches fabrik-lib's `module-owners.json`.
- **Copying fabrik-lib's map into the hub.** Two copies drift; the sweep reads it in place (01M4TCHD5Y § C).
- **Per-agent mailboxes instead of one shared hub mailbox.** It changes every sender's addressing and the claim-once model the hub relies on, for a problem an address and a map already solve.
- **A separate router for feedback verdicts.** They have one owner by ruling (D-627); only their code relays need routing, and those are mail.

## Lifecycle

- **Adoption:** the map lands with the validator green and the advisory on, while the sweep is installed disabled. kaizen reruns its pilot against the map. The sweep is enabled when the pilot's map-routed agreement with the replier is at least the sender's 91%. Kaizen rewords the charters in the same week.
- **Growth:** a new hub file or beat is a map rule with a `source`. The validator's unowned-path report is the trigger: unowned tracked paths above 5% of the hub's tracked files means the map needs a session. A fifth hub agent is a `HUB_BEATS` change plus map rules.
- **Escalation of the measure:** `route-report` monthly. If the suggested-owner re-route rate is ever above the sender's for 50 mails, the sweep goes back to logging only and the map is revised before anything else.
- **Degradation:**
  - The path unit can enter failure mode on a trigger burst (200 per 2 s, sd-7) or a start-limit hit (5 per 10 s, sd-8). The timer keeps sweeping, and `mail_escalate` still runs.
  - A missing or invalid map makes `owner_of` return `None`: no advisory, no suggestion. That is today's behaviour, fail-open, which matters for a fleet-synced file.
  - A `claude -p` failure or timeout yields `none`.
- **Retirement:** deleting the map file turns every leg off. Removing the two units stops the sweep. The trail stays as history.

## External dependencies

- **systemd user path and timer units** (systemd 257 man pages, fetched 2026-10-13):
  - `PathChanged=` watches `IN_CREATE`, `IN_CLOSE_WRITE` and `IN_MOVED_TO` on a directory (path.c, sd-1).
  - "It is not activated on every write to the watched file but it is activated if the file which was open for writing gets closed" (sd-2).
  - No watch is held while the service runs, and files arriving meanwhile do not re-trigger (sd-4, sd-5; the `path_unwatch` tail needs one raw re-fetch, see § Open unknowns).
  - Trigger limit default 2 s / 200 (sd-7); service start limit 10 s / 5 (sd-8).
  - https://www.freedesktop.org/software/systemd/man/latest/systemd.path.html · https://raw.githubusercontent.com/systemd/systemd/main/src/core/path.c
- **Claude Code CLI `claude -p`:** the box's subscription path, already used by `.windsurf/rules/core/60-watchdog.md:198`. No new dependency.
- **Ownership-file practice:** GitHub CODEOWNERS (https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), GitLab CODEOWNERS (https://docs.gitlab.com/user/project/codeowners/reference/), codeowners-validator (https://github.com/mszostok/codeowners-validator). All fetched 2026-10-13.
- **Routing practice:**
  - Freshdesk Auto Triage: https://support.freshdesk.com/support/solutions/articles/50000002117-setting-up-auto-triage
  - Zendesk intelligent triage: https://support.zendesk.com/hc/en-us/articles/5222280338202-Intelligent-triage-use-cases-and-workflows
  - Anthropic ticket-routing guide: https://platform.claude.com/docs/en/about-claude/use-case-guides/ticket-routing
  - All fetched 2026-10-13.

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| Ownership map + path→owner lookup | BUILD (stdlib, ~60 lines in `mail.py`) | none fits | no fabrik-lib module maps paths to owners; too hub-specific to be a module (fails the reused-by-≥2-project-types bar) |
| Mail transport, claim, notify | VENDOR as-is | the hub's own `mail.py` | already exists |
| LLM call for the tie-break | none — the box's `claude -p` | — | `subagents`/`llm-dispatch` are pool runtimes, OFF by D-181/D-182 |
| Alerting for escalation | VENDOR as-is | `libs/alerting` (already used by `mail_escalate.py`) | unchanged |

## Shape / infra implications

- Hub-only box tooling; not a deployed service. No scaffold type, no `specs/services` entry, no `shape:` flags, no port, no VPS.
- Two systemd user units on this box (`mail-route-sweep.path`, `mail-route-sweep.timer` + `.service`), installed by the same install step that carries `traycer-pid-sync.path`.

## Documentation landing sites

- `docs/reference/fabrik-mail.md`: a new § Routing (the map, precedence, trail, sidecar, sweep, measure). The hub's fabrik-mail reference doc already exists; this extends it, never a second doc.
- `docs/workstation/hooks-index.md`: the two units' row.
- `docs/reference/agents/{infra,fleet,intel,kaizen}.md`: beat sections point at `.fabrik/beat-owners.json` (kaizen's edit).
- `INDEX.md`: rows for the map, the sweep, the validator and the research ledger.
- `CHANGELOG.md`, `docs/DECISIONS.md` (the seam rulings as one row citing kaizen's panel, plus the approach row).
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
- **Logging:** the sweep logs to stdout only; journald keeps it.

## Validation

- **V1:** `route` on addressed mail without `--reason` refuses. With it, the message keeps its old `agent:` history and gains one `routed:` line; two re-routes leave two lines in order.
- **V2:** `check_beat_owners.py` refuses an unknown owner and a pattern that matches no tracked file, and reports unowned tracked paths. On the shipped map it is green.
- **V3:** `owner_of` returns one owner for a single-owner citation, `None` with the owner list for a mixed citation, and `None` for no citation. Last-match-wins is honoured. A missing map returns `None`.
- **V4:** the sweep suggests for a project mail to the wrong beat, and never for a hub-agent sender. It writes only the sidecar, so the message bytes are unchanged (md5 before and after). It is idempotent: a second run writes nothing. A message claimed mid-run is never recreated in the inbox.
- **V5:** the tie-break accepts only `HUB_BEATS ∪ {none}`; any other output reads `none`, and it is called only for path-less mail.
- **V6:** `send` to the hub prints the advisory on a mismatch and still delivers. With no map file it prints nothing.
- **V7:** `route-report` computes both rates with their denominators from a fixture inbox and archive.
- **V8 (fabrik-lib leg, after the sentinel's agreement):** an unaddressed single-owner module mail gets that owner's `agent:`; a multi-owner one is left; an addressed one is never touched.

## Cost

Build ≈340 code lines in 4 files (`scripts/mail.py`, `scripts/sysadmin/mail_route_sweep.py`, `scripts/enforcement/check_beat_owners.py`, `scripts/sysadmin/mail_escalate.py`) plus the map, the units and tests. Running cost:
- one `claude -p` Haiku call per path-less hub mail (low volume, on the subscription);
- a few milliseconds per sweep run.

## Open unknowns

- **U1** — `path_enter_running`'s `path_unwatch` tail was read via WebFetch, not a raw fetch (sd-4). Resolution: one raw `curl` of `src/core/path.c` during planning. Either way the design does not depend on it, because the timer and the idempotent sweep cover a missed event.
- **U2** — the pilot result against the map (kaizen) gates enabling the sweep (§ Lifecycle). It is the adoption criterion, not a design blocker.
- **U3** — the fabrik-lib sentinel's agreement gates D7 (kaizen is mailing it the numbers).

## Decisions taken

- The five hub seams are settled as kaizen's 01M4TCHD5Y § B states, from ledger rows, charter lines and kaizen's Opus + Fable panel, minted as one D-row with this spec's commit.
- The map is JSON at `.fabrik/beat-owners.json` (not YAML, not under `docs/`), so stdlib readers in fleet-synced `mail.py` can load it.
- Suggest, never move, on the hub. Auto-move is a later, separately boarded operator gate with a measured threshold (D5).
- The fabrik-lib leg ADDRESSES unaddressed mail, which is not a move, and only with the sentinel's agreement.
- Approach ranking: see the panel note appended at the end of § Chosen approach.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "perfectly rout mails … to correct agent in fabrik" | IN | D1–D6 |
| I2 | "… and in fabrik-lib" / "fabrik-lib has 3 agents and their work must be routed like this too" | IN | D7 |
| I3 | "… mails/kaizen/feedbacks" — feedback verdicts | IN | D8 |
| I4 | kaizen items — kaizen's code relays | IN | D8 + send-time advisory |
| I5 | "we need it asap" | IN | Size: small; the sweep ships disabled, the advisory and map ship first |
| I6 | the operator's original proposal, a Haiku agent (01M4TC3JVN) | IN, CHANGED | D4: tie-break only, after measuring 64% vs 91% |
| I7 | kaizen step 1, "A routing trail" | IN | D1 |
| I8 | kaizen step 2, "One canonical ownership map" | IN | D2 |
| I9 | kaizen step 3, at-delivery check, "do NOT move mail a hub agent sent" | IN | D3 |
| I10 | kaizen step 4, "Haiku only as a tie-break" | IN | D4 |
| I11 | kaizen step 5, "the receiver's re-route rate from the trail is" the measure | IN | D5 |
| I12 | kaizen step 6, "Faster escalation of unclaimed hub mail, using the map's owner" | IN | D6 |
| I13 | kaizen finding 6, "a model call in `send` would run in ~46 repos. The router belongs hub-side" | IN | D3, D4 (no model in `send`) |
| I14 | 01M4TCHD5Y § B, the five seams | IN | D2 |
| I15 | 01M4TCHD5Y § D, precedence | IN | D3, D4, D7 |
| I16 | 01M4TCHD5Y § E, `/fabrik-task` row 1791886542 (`step --terminal-amend` until phase 3) | OUT-OF-SCOPE | unrelated to routing; kept in kaizen's `/fabrik-task` feedback queue, owned by infra (`python3 scripts/command_feedback_report.py --queue fabrik-task`) |
| I17 | work-item triage routing by beat (proposed in infra's reply to 01M4TC3JVN) | OUT-OF-SCOPE | triage fills queues by count today (`scripts/work.py:5369`); a beat-aware triage would read the same `owner_of`, recorded as a backlog row in this spec's commit (`docs/STRATEGIC_BACKLOG.md`) |
