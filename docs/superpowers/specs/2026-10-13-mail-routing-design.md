# Mail routing to the right agent — hub and fabrik-lib

Status: CONVERGED
Size: small (≈330 lines, 5 files)

Work item: W-931b6837 · Owner: infra · Seams: D-815 · Inputs: kaizen mails 01M4TC3JVN (measurements) and 01M4TCHD5Y (ownership-map draft, five seams settled) · Research ledger: `docs/reference/research/2026-10-13-mail-routing-ledger.md`

## Personas

**Primary — the operator**, in their own words: *"read and understand our need and tell me how we will perfectly rout mails/kaizen/feedbacks to correct agent in fabrik and in fabrik-lib"*, and *"we need it asap"* (relayed by kaizen in 01M4TC3JVN). Two more, recorded in D-815: *"when a mail arrive to hub, i want it to be assigned to infra, intel, fleet, kaizen properly and automatically"* and *"fabrik-lib has 3 agents and their work must be routed like this too"*.

| Persona | What they need | Duty this spec gives them |
|---|---|---|
| Operator | every mail lands with the agent who will fix it, without chasing | reads the routing report; nothing else |
| Hub receiving agents (infra, fleet, intel, kaizen) | mail for their beat reaches them; mail not for them is visibly someone else's | read the `→ map:` owner shown by `list`/notify/claim; when they re-route, `route()` records why |
| Project sending agents (~46 synced repos) | to know who owns what before they send | read the send-time advisory; correct `--to-agent` or keep it |
| fabrik-lib agents (`fabrik-lib-sentinel`, `fabrik-lib-dev1`, `fabrik-lib-dev2`) | module mail reaches the module owner | the sentinel agrees to the fabrik-lib leg (D7) before it is switched on |
| kaizen | the beats written once; feedback verdicts stay its own | owns the map's WORDING and reviews the build's pilot numbers before `auto_address` is switched on (§ Lifecycle step 2) |
| infra | the map's CODE: loader, validator, trail, send/read/claim markers, the cron tie-break | builds and maintains every mechanism here |
| Automated: the Haiku tie-break (`claude -p`, one call per path-less unclaimed mail, inside `mail_escalate.py`) | a map-only rubric | returns one agent name or `none`; never a message id |
| Automated: `mail_escalate.py` (cron, every 6 h, hub-only) | the map's owner for unclaimed mail | names the owner on stale mail; runs the tie-break; writes the sidecar |
| Automated: `mail_notify.py` hook (fleet-synced, fail-open) | shows unread mail per session | shows the `map-owner:` header's `→ map: <owner>` beside the addressee (reads the header only, no import, no model) |

**The primary loop, counted (STEP BUDGET = 5):** (1) a project agent sends a finding citing `scripts/sysadmin/dispatch_headroom.py`, addressed to intel; (2) `mail.py send` delivers it to intel as addressed and prints *"advisory: the ownership map names infra (scripts/sysadmin/dispatch_headroom.py → …)"*; the sender sends nothing again, because a second send would deliver it twice, and next time may address `--to-agent map`; (3) the mail lands in `/opt/fabrik-mail/fabrik/inbox`; (4) every agent's prompt banner and `mail.py list` show `→ map: infra` beside the addressee — `list --agent infra` lists it for infra too — and `mail.py claim` by a non-owner prints the same advisory; (5) the owning agent claims it. Every feature below traces to one of these steps or to the measure that decides when step 4 may become a move.

## Goal

Every mail reaches the agent that owns its subject, assigned automatically where the map is certain. The owner is decided by ONE machine-readable map per mailbox. Mail with no addressee is addressed from the map at send time; an agent's explicit address is never overwritten by a guess, and mis-addressed mail is shown with its map owner wherever it is read. Moving mis-addressed mail automatically is a later gate, opened only when the measured re-route rate shows the map beats the sender (D5). fabrik-lib's unaddressed mail is addressed the same way from its existing module map, once its sentinel agrees (D7).

## Why this exists

Measured by kaizen on 2026-10-13 over hub mail since 2026-10-01 (01M4TC3JVN):
- Missing addresses are rare: `mail.py send` already refuses unaddressed hub mail (`scripts/mail.py:1079-1091`); 18 of 1,262 hub mails (1.4%) went out unaddressed.
- **Wrong** addresses are the problem: of 143 project mails with a first reply, 15 (10%) were answered by a different agent than the addressee, and those waited a median **125.9 h** for a first reply against **8.4 h** when the addressee answered.
- 224 of 295 project→hub mails were addressed to infra, so beat ambiguity always lands on infra's inbox.
- The beats are written in five places — four charters (`docs/reference/agents/*.md`), `CLAUDE.md`, and the refusal prose at `scripts/mail.py:1083-1089` — and they disagree on five seams (§ The delta D2).
- `route()` (`scripts/mail.py:1756-1806`) rewrites the `agent:` line and keeps no history, so no one can measure the mis-route rate.
- A Haiku classifier given a charter rubric agreed with the actual replier on 64% (90/141) against the sender's own 91% (128/141); its "high confidence" answers were right 64% of the time too.
- fabrik-lib: 83 of 139 mails since 2026-10-01 (60%) were unaddressed, so only the sentinel's arm saw them; 79 (57%) named modules of exactly one owner (01M4TCHD5Y § C).

The approach resolves exactly this: one map ends the five-way disagreement; the send-time step addresses mail automatically where the map is certain and corrects the sender before the mail leaves (where 91% accuracy already lives); every read surface shows the map owner, so a mis-addressed mail is visible to its real owner at once instead of after 125.9 h; and the trail makes the remaining mis-route rate measurable.

## What exists today (grounded)

| Component | Where | Behaviour |
|---|---|---|
| Hub beats | `scripts/mail.py:543` | `HUB_BEATS = ("infra", "fleet", "intel", "kaizen")` |
| Send-time address rule | `scripts/mail.py:1040-1091` | refuses an unknown hub beat; refuses an unaddressed hub send; thread replies inherit the asker (`:1060-1067`) |
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

**D — one ownership map per mailbox, applied once at send and shown at every existing touchpoint: read, claim, the notify hook and the escalation cron; plus a routing trail.** It adds no new process. The map owner is applied:
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

**Principle (D-818, sharpened in review round 1): the map is applied once, at send, by construction.**
- `send` computes the owner and writes it into the new message as a `map-owner:` header.
- Every later touchpoint reads that header and never recomputes: `list`, `claim`, the notify hook and the escalation cron. So the fleet-synced notify hook keeps its rule of never importing `mail.py` and pays no lookup per prompt. Only the `list` CLI and the escalation cron, which writes it, read the tie-break sidecar (D6); the per-prompt hook never does.
- A message sent before this ships (or by a not-yet-synced copy) carries no header and is shown as today.

**D1 — Routing trail.** `route()` (`scripts/mail.py:1756`) appends one header line per re-route and keeps the earlier ones:
`routed: <UTC ISO> · <by> · <from or -> → <to or -> · <reason or (no reason)>`.
- `<by>` is the caller from `_caller_agent()`, `mail.py`'s own identity resolver.
- `<reason>` comes from an optional `--reason`. It is sanitised to one line: every line boundary Python's `str.splitlines()` recognises (CR, LF, VT, FF, the C0 separators 0x1c-0x1e, NEL, U+2028, U+2029) becomes a space and `·` is removed, whitespace is collapsed, and the value is capped at 200 characters — the same boundary set `_parse` and `route()` split on, so a value can never start a header line.
- An automatic address at send (D3a) writes the first `routed:` line with `<by>` = `map`.
- The trail is read from the raw header lines, never through the frontmatter dict parser, which keeps only the last of repeated keys.
- Timestamps use `datetime.now(UTC)`. The trail is what D5 measures.

**D2 — One hub ownership map: `.fabrik/beat-owners.json`.**
- **Shape:** `{"version": <int>, "switches": {"auto_address": false, "fabrik_lib_address": false}, "rules": [{"paths": [...], "topics": [...], "owner": "<beat>", "source": "<D-id or charter line>"}]}`.
- **Matching:** rules are ordered general → specific, and the LAST matching rule wins for a path (CODEOWNERS, co-1). Patterns use gitignore-style segments:
  - `*` matches within one path segment, and `**` matches across segments;
  - a pattern without `/` matches a file name anywhere;
  - a trailing `/` is a directory prefix.
  - This is implemented with a small regex translator, because stdlib `fnmatch` lets `*` cross `/`.
- **Contents:** the seams of D-815 and kaizen's § A path lists (01M4TCHD5Y).
  - Order: each beat's broad paths first, then the specific exceptions. For example, fleet's `templates/**` comes BEFORE infra's `templates/governance/**`, and infra's `scripts/**` comes before intel's `scripts/review_loop_ledger.py`.
  - Non-repo locations (kaizen's "`~/.claude/bin` mesh") become topic phrases, never path patterns.
  - Topics are short phrases, matched case-insensitively as substrings of the message's Subject line only.
- **Switches:** the map's `switches` turn D3a and the fabrik-lib leg on. They live in the one hub file every sender's `mail.py` reads, never in a sender's environment, so the hub turns them on in one place.
- **Validator:** a new gate check, `scripts/enforcement/check_beat_owners.py`.
  - It refuses (exit 1): an owner outside `HUB_BEATS`; a rule missing `owner` or `source`; a malformed pattern; a `paths` pattern matching no tracked file (`git ls-files`); a rule fully shadowed by a later rule with a different owner; and an unknown switch.
  - It reports (advisory) the tracked hub paths no rule owns, with the count and its denominator.
  - It self-skips where the map does not exist (every project repo).
- **Loader:** one stdlib function in `scripts/mail.py`, `owner_of(text, mailbox="fabrik", from_repo="fabrik") -> Routing`, a named tuple `(owner, owners, reason, map_version)`. It never calls a model.
  - **Cited paths:** backticked tokens and `path:line` tokens (with `:line` stripped) that name an existing FILE under the mailbox's repo root. The root is `_opt_root()/fabrik` (`scripts/mail.py:317`), so tests point it at a scratch tree. An absolute token under `_opt_root()/fabrik/` counts for every sender, read as the path below that root. Directories, bare basenames that are not repo paths, and missing files are ignored.
  - **A sender outside the hub:** `send` passes `from_repo` = the sending repo, `_current_repo()` (`scripts/mail.py:951`), never the free-text `--from` lane. When it is not `fabrik`, a relative cited path counts only when it does not exist in the sender's own repo (`_opt_root()/<from_repo>`) or its copy there is byte-identical to the hub's, which is a synced file. So a project's own `CLAUDE.md`, `README.md` or `src/…` is never attributed to a hub beat.
  - **Owned paths:** cited paths that some rule matches; unowned cited paths are ignored.
  - **Result:** `owner` is set when every owned path maps to one owner, with `reason` = `<path> → <rule source>`. With several owners it is `None`, and `owners` lists them.
  - **No owned path:** a Subject topic match to exactly one owner gives `owner` with `reason` = `topic "<phrase>"`, but such an owner is advisory-only and never auto-addresses (01M4TCHD5Y § D.3).
  - **Missing or invalid map:** `Routing(None, [], "", "")`. A `map_version` of `""` means "no map", distinct from "unmapped".
- **The refusal prose** at `scripts/mail.py:1083-1089` stays as written, with one added line pointing at `.fabrik/beat-owners.json` as the authority. kaizen rewords each charter's beat section to point at the map (01M4TCHD5Y § SYSTEMIC).

**D3 — Send (`mail.py send`, deterministic, no model).** `send` first records whether `--to-agent` was given explicitly — `explicit = bool(to_agent)` right after its normalisation at `scripts/mail.py:901` (which turns a missing value into `""`) and before thread inheritance fills it (`:1060-1067`). Then:
- **(a) Automatic address:** with `switches.auto_address` true, a hub-bound send that today's refusal would refuse — no explicit `--to-agent`, no `--broadcast`, and not a thread reply (`is_thread_reply`, `scripts/mail.py:1050`; a reply is exempt from the refusal today and stays untouched) — is addressed to `owner_of`'s owner, but only when that owner came from owned paths, not a topic. It writes `routed: … · map · - → <owner> · ownership map (<reason>)` and prints `addressed to <owner> by the ownership map (<reason>)` to stderr. Otherwise today's refusal (`scripts/mail.py:1079-1091`) stands. This is the operator's "assigned … automatically" applied where the map is certain.
- **(b) Advisory:** an EXPLICIT `--to-agent` that differs from a single map owner prints `advisory: the ownership map names <owner> (<reason>); delivered to <to-agent> as addressed` to stderr and delivers as addressed. An inherited address prints nothing.
- **(c) The `map-owner:` header** on every hub-bound message whose `Routing` has a non-empty `map_version` (a readable map and no fault in the routing step): `map-owner: <owner | mixed:<a>,<b> | unmapped> · v<map_version> · <reason>`, sanitised like D1.
- **(d) `--to-agent map`:** an explicit `--to-agent map` addresses the send to `owner_of`'s paths-derived owner whatever `auto_address` reads, writes `routed: … · map · map → <owner> · ownership map (<reason>)`, and is refused, naming the owners or `unmapped`, when there is no single paths-derived owner. A sender can use the map today, before the switch is on. It is accepted before the `HUB_BEATS` check (`scripts/mail.py:1040`). `map` is a hub-mailbox name only: `--to-agent map` to any other mailbox is refused, because that check is scoped to the hub and would otherwise deliver a literal `agent: map`.
- **(e) Fail-open:** the whole routing step — extraction, the map read and the matcher — runs inside one guard. Any exception yields `Routing(None, [], "", "")` and today's behaviour, so a matcher fault can never block a send that today's code delivers, in any of the ~46 synced repos. `--to-agent map`, which today's code does not know, is then refused as having no owner.
- **Where the map is read:** a project's synced `mail.py` reads the hub map at `_opt_root()/fabrik/.fabrik/beat-owners.json` when it exists, and skips every step silently when it does not (off-box, or a sync-excluded repo).

**D4 — Read and claim, from the header only.**
- `mail.py list` shows `→ map: <owner>` when `map-owner:` names an owner other than the addressee, `→ mixed: <a>,<b>` and `→ unmapped` as written. A message with no header shows nothing.
- `list --agent X` also lists messages whose `map-owner:` is X, marked `(map)`. It stays a filter, never a lock (`route()` docstring).
- `.claude/hooks/mail_notify.py` prints the same marker by reading the header with its existing stdlib parser. It imports nothing new and stays fail-open; its `_parse_fm` already parses each message.
- `mail.py claim <id>` by a caller (`_caller_agent()`) who is not the header's single owner prints the advisory to stderr before the claim and claims anyway. `claim`'s atomic rename stays the only lock.
- Nothing here writes to a message file, so nothing can race `claim`.

**D5 — The measure, and when a mis-addressed mail may be moved automatically.**
- **The measure:** the rerouting rate (tr-8), computed from the D1 trail and the D3c header. For mail whose `map-owner:` differed from the addressee, the share re-routed to the map owner and the share re-routed elsewhere; and for all hub mail, the sender-address re-route rate (≈10% today, 01M4TC3JVN). Because a map owner can simply claim `(map)` mail without calling `route`, the report also counts who ANSWERED: the first reply carrying `from-agent:`, compared with the map owner and with the first addressee; replies are found in EVERY mailbox (`_mail_root()/*/{inbox,archive}`), because a hub agent's reply to a project lands in that project's mailbox (`scripts/mail.py:1111`); the first reply is the earliest one whose `re:` names the message. That is what kaizen measured.
- **The report:** `mail.py route-report --days N` prints these with their numerators and denominators. Before `auto_address` is switched on, the build replays kaizen's pilot over the live archive (plan Phase C step 2): for hub mail of the last 30 days that has a reply carrying `from-agent:` (replies are found in EVERY mailbox (`_mail_root()/*/{inbox,archive}`), because a hub agent's reply to a project lands in that project's mailbox (`scripts/mail.py:1111`); the first reply is the earliest one whose `re:` names the message), it compares `owner_of`'s paths-derived owner and the sender's addressee each against the agent who first replied. D3a acts on UNADDRESSED mail, which has no replier to compare with, so placement accuracy on addressed mail is the proxy; the proxy favours the sender, whose addressee is the agent shown the mail, so a map that matches or beats the sender has passed a test biased against it.
- **The gate** (D-818's wording): auto-moving explicitly mis-addressed project mail is boarded once the map's re-route rate is below 10% AND below the sender's own, over at least 50 such mails. It is a separate operator gate, and this spec does not build it.
- **Cobra (D-253):** the cheapest way to look good is to stamp every mail with a confident label, so no confidence is stored or measured; only receivers' re-routes are (tr-11).

**D6 — Escalation and the tie-break (`scripts/sysadmin/mail_escalate.py`, hub-only, existing 6-hourly cron).**
- Its digest names `map: <owner>` from the header beside the addressee.
- For unclaimed hub mail older than the escalation threshold whose header reads `unmapped`, with no sidecar yet, it makes ONE sequential `claude -p --model haiku` call per mail. This is a low-volume classification step on the subscription path (`.windsurf/rules/core/65-rag-search.md:108`). That rule names fabrik-lib `rag`'s `claude_p_chat` adapter, which the hub does not vendor (`libs/` holds no `rag` module), so the step calls the CLI directly, as the watchdog does (`.windsurf/rules/core/60-watchdog.md:198`), never a fan-out (`.windsurf/rules/core/62-using-subagents.md:103`) and never OpenRouter (`.windsurf/rules/core/62-using-subagents.md:100`). Each call has a 60 s timeout, with at most 10 calls per run.
- **Rubric:** the map file. **Output:** one token validated against `HUB_BEATS ∪ {none}`; anything else reads `none`.
- **Where it lands:** the sidecar `_mail_root()/fabrik/.routing/<id>.json` as `{"suggested", "by": "haiku", "map_version", "at"}`. `list` shows it as `→ haiku: <owner>`; the per-prompt hook does not read sidecars.
- **Never:** a message id from model output (it comes from the file name), a write to the message file, or a move.
- **Deferrable:** decided once, at the start of plan Phase B: if Phase A overran its appetite, the whole tie-break — this section's tie-break bullets, the sidecar store, V7 and V5's `→ haiku:` marker — moves to a follow-up work item and the build ships without it; `→ haiku:` then never appears.

**D7 — fabrik-lib leg: built switched off, requested, and gated on the sentinel's sign-off.**
- **The rule (D-815, 01M4TCHD5Y § C):** with the map's `switches.fabrik_lib_address` true, a send to the `fabrik-lib` mailbox with no `--to-agent` gets an owner when its cited modules all belong to ONE owner in `_opt_root()/fabrik-lib/.fabrik/module-owners.json` (live: `/opt/fabrik-lib/…`; read in place, never copied; tests point `FABRIK_OPT_ROOT` at a scratch tree).
  - A cited module is a cited path under `_opt_root()/fabrik-lib/<module>/…`, or a backticked bare token equal to a module directory name.
  - The message gets that owner as `agent:` plus a `routed: … · map …` line.
  - It is addressed at send, by construction: no second writer on the inbox, no race with `claim`, and the sentinel's bare arm still sees it.
  - Several owners or none leave it for the sentinel.
- **The switch's one precondition:** the sentinel agrees in its own ledger (kaizen's 01M4TCHSPX carries the numbers). Addressing happens in the SENDER's hub-synced `mail.py`, so fabrik-lib's own copy plays no part in it. Two follow-ups ride the same request and never block the switch: re-vendor `mail.py` for the sentinel's own sends, and validate `--to-agent` against its three-name roster.
- **Delivery:** the hub sends this as a request to `fabrik-lib-sentinel` and never edits fabrik-lib (CLAUDE.md HARD STOP, cross-repo).

**D8 — Feedback and kaizen items.**
- Command-feedback verdicts stay single-owner, kaizen (`feedback_owner`, D-627).
- When a verdict needs code, kaizen's relay mail is addressed with the map: D3 addresses or advises before it leaves.
- No separate router is built for feedback; it rides the mail path.

## Contract deltas

- **New files:**
  - `.fabrik/beat-owners.json` (`"version"` integer, `switches` default off);
  - `scripts/enforcement/check_beat_owners.py`, registered in `scripts/final_gate.py`.
- **New mail headers:**
  - `routed:` (repeated, appended, read from raw lines);
  - `map-owner:` (set once, at send).
- **New sidecar store:** `_mail_root()/fabrik/.routing/<id>.json`, written only by `mail_escalate.py`'s tie-break (D6).
- **New CLI:**
  - `mail.py route … --reason <text>` (optional; the trail records `(no reason)` without it, so every existing documented `route` call keeps working);
  - `mail.py route-report --days N`;
  - `mail.py send --to-agent map` (D3d). **Mirror:** `map` becomes a reserved addressee name on the hub mailbox; it is not in `HUB_BEATS`, so no real agent is shadowed.
- **Behaviour change — `send`:**
  - With `auto_address` on, a hub send with no addressee that the map places by owned paths is ADDRESSED instead of refused. **Mirror:** a test relying on that refusal for a single-owner body sees a delivered mail; the switch ships off, so the existing refusal tests stand.
  - An explicit mismatched `--to-agent` gets a stderr advisory. **Mirror:** a caller reading send's stderr as errors sees a non-error line; stdout (the path) is unchanged.
  - Every hub-bound message gains `map-owner:` when the map exists. **Mirror:** a parser that rejects unknown headers. `_parse` and `mail_notify._parse_fm` accept any `key: value` line, verified in planning.
- **Behaviour change — `list --agent X`:** it also lists mail whose `map-owner:` is X. **Mirror:** a script counting its lines counts more; `scripts/merge_request.py:662` filters by kind and is unaffected (verified in planning).
- **Behaviour change — `claim`:** it may print an advisory to stderr; its return and its lock are unchanged.
- **Behaviour change — `mail_notify.py`:** it gains the `→ map:` marker. It is fleet-synced, so its output shape changes in ~46 repos; it stays fail-open and imports nothing new.
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
  2. The build replays kaizen's pilot over the live archive (plan Phase C step 2, D5). The build's commit ships `switches.auto_address` false either way. Its reply hands kaizen the numbers; when the map agrees with the replier at least as often as the sender does over at least 50 mails it can place, and kaizen's review finds no reason against, the hub sets the switch true in a separate one-line map commit.
  3. `switches.fabrik_lib_address` is set true when the sentinel records its agreement (D7).
  4. kaizen rewords the charters in the same week.
- **Growth:**
  - A new hub file or beat is a map rule with a `source`.
  - Trigger: the validator's unowned-path report plus `route-report`'s count of `→ unmapped` mail. When unmapped mail exceeds 20% of a month's hub mail, the map needs a session, which shrinks the population the tie-break serves (judge 1).
  - A fifth hub agent is a `HUB_BEATS` change plus map rules.
- **The measure over time:** `route-report` monthly. If mail the map placed is re-routed by its receiver more often than the sender's ≈10% over 50 mails, `switches.auto_address` goes back to false, and the map is revised before anything else.
- **Degradation:**
  - A missing or invalid map makes `owner_of` return no owner and `map_version` `""`: no `map-owner:` header, no advisory, and unaddressed sends refused as today.
  - The per-prompt hook parses one header and does no lookup, so it cannot slow down; a message with no header is shown as today.
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
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| **`datetime.now(UTC)`, never `datetime.utcnow()`** | `.windsurf/rules/core/10-python.md:220` |
| an operator-facing or batch step (a judge run, a one-off classification), never a per-request path — is `claude -p` through the module's `claude_p_chat` adapter | `.windsurf/rules/core/65-rag-search.md:108` |
| a fan-out of `claude -p` processes from the orchestrator | `.windsurf/rules/core/62-using-subagents.md:103` |
| or a direct OpenRouter HTTP call — a dispatch still spends | `.windsurf/rules/core/62-using-subagents.md:100` |
| any `*.log` file write, any in-app log rotation/retention/cleanup | `.windsurf/rules/core/10-python.md:294` |

Rows applied:
- **No new dependency:** stdlib `json` and `re` only.
- **Timestamps:** the trail's are UTC-aware.
- **Tie-break:** one `claude -p` per path-less mail, never a fan-out or OpenRouter.
- **Logging:** the cron step logs to stdout, which the cron line's existing redirect keeps.

## Validation

- **V1 — trail:** two `route` calls, with and without `--reason`, leave two raw `routed:` lines in order, the second reading `(no reason)`. A reason holding a newline and `agent: x` becomes one sanitised line, and `agent:` is unchanged.
- **V2 — validator:** `check_beat_owners.py` refuses an unknown owner, a missing `source`, a malformed pattern, a dead pattern, a fully shadowed rule and an unknown switch. It reports unowned tracked paths with their denominator, is green on the shipped map, and self-skips where the map is absent.
- **V3 — `owner_of`:**
  - one owner with its reason for a single-owner citation, honouring last match wins and `*` stopping at `/`;
  - `None` plus the owner list for a mixed citation;
  - unowned paths, directories and missing files ignored;
  - a Subject topic giving an advisory-only owner;
  - `map_version` `""` for a missing or invalid map;
  - from a non-hub sender, a cited path that exists in the sender's repo with different bytes is ignored, while a byte-identical (synced) one counts;
  - an absolute `_opt_root()/fabrik/…` token counts for a hub and a non-hub sender alike.
- **V4 — send:**
  - with `auto_address` false, an unaddressed hub send is refused as today;
  - with it true, one the map places by paths is delivered to the owner with a `routed: … · map …` line and the stderr note, while a topic-only or mixed one is still refused;
  - an explicit mismatched address delivers as addressed with the advisory, and an inherited one prints nothing;
  - every hub-bound message carries `map-owner:`;
  - with no map file, there is no header and behaviour is today's;
  - `--to-agent map` addresses a paths-placed send with the switch off, and is refused for a topic-only, mixed or unmapped one;
  - a matcher that raises leaves send's behaviour exactly as today's, with no header, and refuses `--to-agent map`;
  - `--to-agent map` to a non-hub mailbox is refused.
- **V5 — read and claim:**
  - `list` shows `→ map:`, `→ mixed:` and `→ unmapped` from the header, `→ haiku: <owner>` from a tie-break sidecar, and nothing for a message without either;
  - `list --agent X` includes X's map-owned mail marked `(map)`;
  - `claim` by a non-owner prints the advisory and still claims;
  - no message file's bytes change (md5 before and after).
- **V6 — `mail_notify.py`:** shows the marker from the header; a malformed header still prints the banner and exits 0; the hook imports no new module.
- **V7 — the cron tie-break:**
  - called only for unclaimed stale mail whose header reads `unmapped` and that has no sidecar;
  - accepts only `HUB_BEATS ∪ {none}`, so any other output reads `none`;
  - at most 10 calls per run, each with a 60 s timeout;
  - the sidecar carries `map_version`, and the message file is untouched.
- **V8 — `route-report`:** computes each rate with its numerator and denominator from a fixture inbox and archive, including the share answered by the map owner and by the first addressee, from each first reply's `from-agent:`.
- **V9 — fabrik-lib leg:** with `fabrik_lib_address` true and a scratch module map, an unaddressed single-owner module mail is addressed to that owner, a multi-owner one is left unaddressed, and an addressed one is untouched; with it false, nothing changes.

## Cost

Build ≈330 code lines in 5 files plus the map and tests:
- `scripts/mail.py`: ≈200 — the matcher, `owner_of`, trail, send, list, claim, route-report;
- `.claude/hooks/mail_notify.py`: ≈10 — print the header;
- `scripts/sysadmin/mail_escalate.py`: ≈60 — owner naming and the tie-break;
- `scripts/enforcement/check_beat_owners.py`: ≈60;
- `scripts/final_gate.py`: ≈8 — the registration.

Running cost:
- one `owner_of` call per hub-bound send (a few milliseconds);
- one `claude -p` Haiku call per unmapped unclaimed stale hub mail, at most 10 per 6-hourly cron run.

## Open unknowns

- **U1 — the pilot result against the map.** It gates D3a's switch-on; it is measured in the build (plan Phase C step 2) and reviewed by kaizen before the switch commit. It is the adoption criterion, not a design blocker.
- **U2 — the fabrik-lib sentinel's agreement.** It gates D7; kaizen's 01M4TCHSPX carries the numbers.
- **U3 — resolved in review round 1.** The hook reads the `map-owner:` header its own parser already reads, so it gains no import and no lookup. The baseline, 30–80 ms per run over 47 messages including interpreter start-up, is unchanged by construction.

## Decisions taken

- The five hub seams are D-815 (kaizen; ledger rows, charter lines and an Opus + Fable panel).
- The map is JSON at `.fabrik/beat-owners.json` (not YAML, not under `docs/`), so stdlib readers in fleet-synced `mail.py` can load it.
- The map is applied once at send (the `map-owner:` header) and only read afterwards, so the fleet-synced notify hook never imports `mail.py`. This refines D-818, whose row names the touchpoints as "send, list, the notify hook, claim and the 6-hourly escalation cron": after plan-review round 1 the map is applied at send and the others read its result. The approval row records the refinement. The switches live in the map, not in senders' environments.
- Approach D (D-818), the judge panel 3–0 in round 2. Unaddressed mail is assigned automatically where the map is certain (D3a, after the in-build pilot), and any sender may ask for the map's owner with `--to-agent map` from day one. Explicitly addressed mail is never moved; its map owner is shown, and auto-moving it is a later gate with a measured threshold (D5).
- The fabrik-lib leg ADDRESSES unaddressed mail, which is not a move, and only with the sentinel's agreement.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "perfectly rout mails … to correct agent in fabrik" | IN | D1–D6 |
| I1b | "when a mail arrive to hub, i want it to be assigned to infra, intel, fleet, kaizen properly and automatically" (D-815) | IN, CHANGED | D3a assigns unaddressed mail automatically where the map is certain; moving explicitly addressed mail automatically is D5's later gate, because the map is unproven against the sender's 91% |
| I2 | "… and in fabrik-lib" / "fabrik-lib has 3 agents and their work must be routed like this too" | IN | D7 |
| I3 | "… mails/kaizen/feedbacks" — feedback verdicts | IN | D8 |
| I4 | kaizen items — kaizen's code relays | IN | D8 + send-time advisory |
| I5 | "we need it asap" | IN | Size: small; no new process; markers, advisory and `--to-agent map` ship first; D3a is switched on by a one-line map commit once the in-build pilot passes and kaizen has reviewed it |
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
