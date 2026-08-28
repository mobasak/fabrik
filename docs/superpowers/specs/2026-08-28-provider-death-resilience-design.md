# Provider-death resilience as a fleet-wide planning-phase standard — design

Status: CONVERGED

**Convergence evidence.** 6 passes (1 wide → 4 scoped/fix → 1 wide closing). Terminal pass: `edits: 0`,
`new: 0`, md5 `1ce4d918ea9590d03dd034bc57817aab` unchanged start→end. All four OpenRouter quotes matched
verbatim against the RAW `llms-full.txt` at the exact cited line numbers (`:72375`, `:72814`, `:72848`,
`:72862`) — the HTML doc pages are client-rendered and cannot verify a quote; all three Prometheus quotes
matched by `grep` in the raw static page. What the review changed: the measurement was re-run code-only
(28→26, 20→19, 8→7, and `web-scraper` dropped out), the `sort`/`order` opt-out caveat was found and is now
load-bearing, an overstated "no deadman exists" absence claim was corrected against the real corpus, and
the 402 claim was made exact for both branches of an undefined `call_provider`.

- **Origin:** youtube mail `01M13YXMCCNS5886ZJMFYP47RM` (kind `request`, ack required, addressed `@infra`),
  filed on operator instruction (Sarp, 2026-08-28): *"this type of hardening must be our de-facto standard
  for all services … resilience.md and .windsurf/rules must enforce this in the planning phase for all
  services."* This is a directive to land, not a proposal to accept or decline.
- **Source proposal:** `/opt/youtube/docs/reference/upstream-proposals/2026-08-28-provider-death-resilience-standard.md`
- **Author:** hub `@infra`. Two of the three requested changes are NOT on this beat — see § Beat split.

## Goal

A permanent **provider death** — a model or endpoint that is gone, not blipping — is a failure class the
Fabrik resilience corpus does not currently name. Timeout, retry, backoff, circuit-breaker and resumable
checkpointing all self-heal a **transient** fault. Provider death needs a **swap**, which is a decision no
retry loop is empowered to make. youtube's backfill sat stalled 8h at 1,223/~15,300 with every one of those
mechanisms working correctly, and nothing alarmed, because zero progress is not an error — it is the
*absence* of events, and nothing in the corpus watches for an absence.

This spec turns that into a planning-phase standard for the fleet.

## What is already true (grounded this session — do not re-derive)

**1. The corpus does not merely lack the standard. It actively teaches the pattern that failed.**

`core/76-gpu-workers.md:113-133` § Provider Failover ships a worked example that reproduces youtube's
outage almost exactly:

- `INFERENCE_CHAIN` (`:117-120`) is a hardcoded two-rung list, one model per provider — **no intra-provider
  diversity**, so a single model's death takes out that whole rung even while its siblings are healthy.
  That is precisely youtube's primary failure (`meta/muse-glimmer-30b` ReadTimeout-down while other free
  NVIDIA models stayed UP).
- `infer_with_failover` (`:122-128`) catches **only** `httpx.TimeoutException, httpx.ConnectError` — two
  *transport* exceptions. Stated precisely, because this is the sharpest claim in the spec: the snippet
  leaves `call_provider` undefined, so there are exactly two possibilities for an `http_402`, and the
  documented failover fails in **both**. If `call_provider` raises (`raise_for_status`), the exception is
  `HTTPStatusError`, which this `except` does not catch, so it propagates out of the loop and the remaining
  rungs are never tried. If `call_provider` does not raise, the 402 body is *returned as if it were a
  completion*. Either way the chain does not advance on the exact error class that killed youtube's Mistral
  tiers 2 and 3 — and `402` is not exotic here, it is what a free tier returns when it is billing-gated.
- `:133` — *"Circuit-breaker per provider (not per model) — if Groq is down, don't keep trying Groq."*
  Per-provider granularity is the wrong resolution for a model-specific death and is what makes it
  invisible.

**2. The corpus has a deadman, but it cannot see this failure.** `rg 'deadman' .windsurf/rules/` does NOT
come back empty — the near-miss is worth naming precisely, because "we already have a deadman" is the most
likely reason someone would judge this standard redundant. `core/60-watchdog.md` and `core/self-healing.md:51` carry
`WatchdogConfig.deadman_timeout_seconds` (default 300). But it is an **ack-timeout** deadman: it arms only
*after* a Tier C alert has been raised and the operator has not acknowledged it, and its action is
`docker restart <main_container>`. It measures operator silence, not work. youtube's loop raised no alert —
there was no error to raise one from — so the deadman never armed, and a container restart would not have
helped a process that was running correctly and finding nothing to do. **What is absent is a detector for
the absence of PROGRESS**, as opposed to the absence of an operator's ack, and `rg 'no progress|forward
progress|zero.progress'` over `.windsurf/rules/` confirms that one: no hit.

**3. `core/self-healing.md` already names the insertion point and mandates the order.**
Its 9-row escalation ladder (`:29-39`) has no row for "an unattended loop makes zero forward progress" and
none for "every rung of the ladder is down at once". Row 4's escalate is the nearest — *"if pause flag
persists past > 4 × ttl_sec"* — which detects a **wedged dependency**, not a **silent stall**, and youtube's
loop never set a pause flag at all. The pack states the rule for this case at `:54`:

> *"If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first,
> then the response logic to the code.** Never silently invent a self-healing response."*

So the corpus's own doctrine says a new failure class lands as a **ladder row**, not as a free-standing rule.

**4. The mandated gateway provides two of the three mechanisms — CONDITIONALLY.**
`CLAUDE.md` § 1b-bis makes **OpenRouter the only sanctioned LLM gateway**, and OpenRouter does outage-aware
routing plus model-level fallback natively. The conditionality is load-bearing and is easy to miss: the
outage-aware step is step 1 of the DEFAULT load-balancing strategy, and setting `sort` or `order` disables
load balancing — so a project that pins a provider has opted OUT of the protection it believes it has. See
§ External dependencies for the verbatim citations with raw-source line numbers. This is the main place
this design departs from the proposal.

**5. fabrik-lib already has the building blocks.** `health-probe/` and `alerting/` exist and are Active.
The proposal's suggested new `resilience/health_promote.py` is a **vendor+enhance**, not a build.

## Measurements (the rule instrument follows the number, not the other way round)

Measured across `/opt` this session, 43 git repos scanned, excluding `archived/`, `node_modules`, `.venv`.
**Measured twice** — the second run restricted the model-call match to CODE files (`*.py`, `*.ts`, `*.js`,
`*.sh`, excluding `docs/` and `*.md`), because the first run counted a repo that merely *mentions*
`openrouter` in a doc as gateway-routed. The corrected run is the one that binds:

| Population | All-files run | **CODE-only (authoritative)** | Meaning |
|---|---:|---:|---|
| Repos with an unattended loop (beat/APScheduler/`while True:`/cron/supervisor) | 41 | 41 | the loop population |
| …that also carry a model/LLM call site | 28 (65%) | **26 (60%)** | what an "unattended external-dependency loop" rule binds |
| …routing **only** through OpenRouter | 20 | **19** | outcome 1 satisfied by the gateway *if* it is not pinned with `sort`/`order`; outcomes 2 and 3 still owed |
| …touching a **direct** provider endpoint | 8 | **7** | candidates for a bespoke probe |
| …of those, that ALSO call OpenRouter in code | not measured | **5** | remedy is likely "route it through the gateway", not "build a probe" |
| …**purely** direct, no gateway path in code | not measured | **2** | the only repos with no cheaper option |

The 7: `ai-model-catalog`\*, `fabrik`\*, `fabrik-dr-store`, `fabrik-lib`\*, `iterative_image_editor`\*,
`llm_batch_processor`, `youtube`\* (\* = also calls OpenRouter in code). `web-scraper` appeared in the
first run and **dropped out** of the second — its only direct-endpoint match was in a doc, not in code.

**Proxy limits, stated rather than hidden.** These are `rg` literal matches, not call-graph analysis. A
repo is counted as having an unattended loop if any file matches `beat_schedule|APScheduler|while True:|
crontab|supervisor` — that match was NOT restricted to code files, so the loop denominator (41) is the
loosest number here and is used only for context, never to bind anything. A direct-endpoint hostname in
code does not prove it is on the unattended path; it proves the repo *can* reach that endpoint. The
numbers above are therefore an **upper bound on the obligation**, which is the safe direction for deciding
that an obligation is small.

**What the numbers decide.** A mechanical gate firing on 60% of the fleet on landing day is wallpaper by
week two — this repo has killed two proposed rules this session at 14% and 15% for less. And a mandate to
hand-roll probe-and-rebuild would be **wrong for 19 of the 26**, because it would have them re-implement
routing their gateway already performs. So: a **planning-phase prose standard** (binds NEW plans/specs, not
existing code) whose bespoke-mechanism clause is scoped to the direct-provider path — at most 7 repos, and
for 5 of those the cheaper remedy is to move the call onto the gateway rather than to build anything.

## Chosen approach — mandate the three OUTCOMES; let the route pick the mechanism

The proposal specifies three *mechanisms*. Specifying mechanisms fleet-wide is what would force 19 repos to
rebuild their gateway. This spec keeps all three of the proposal's guarantees and restates them as
**outcomes**, each with a named default mechanism per route:

| # | Required outcome | OpenRouter-routed (19 repos) | Direct-provider path (≤7 repos) |
|---|---|---|---|
| 1 | **No single point of death in the chain.** One model or endpoint dying must not stop the loop. | Largely satisfied by the platform: outage-aware routing is step 1 of the DEFAULT strategy, and a `models` fallback array covers model-level death on *any* error. But `sort`/`order` DISABLES load balancing and with it the outage step — so the obligation is to declare WHICH mechanism is relied on, in `RESILIENCE.md` §2b. An unstated default is not a design, and a pinned `order` is an opt-OUT. | **Bespoke**: probe the candidate list once at run start, rebuild the chain from live survivors, best candidate stays first so it self-restores. |
| 2 | **The last rung is exercised.** An untested fallback is a silently-dead fallback. | Not provided by any gateway. Binds all 26. | Same. |
| 3 | **Absence of progress is alarmed.** N minutes of zero forward progress fires exactly one operator-facing alert, cleared on recovery. | Not provided by any gateway. Binds all 26. | Same. |

**Outcome 2 is the one the proposal is most right about and the one no platform gives you.** youtube's
last-resort (`claude -p` haiku) was non-functional for reasons entirely unrelated to the outage — untrusted
workspace + expired OAuth. A ladder whose bottom rung has never been executed is a ladder with one fewer
rung than its author believes.

**Outcome 3 is implemented as a Prometheus alert on a progress counter, not as bespoke supervisor code.**
Fabrik already runs Prometheus + Alertmanager + Apprise→Telegram. Prometheus's own guidance is that this is
the right shape for exactly this case, and the `for:` clause supplies the "one alert, not a flood" property
that youtube's reference implementation hand-rolls with day-stamp state. The project's obligation becomes:
**export a monotonically-increasing progress counter**, and declare its stall threshold as a tuning knob in
`RESILIENCE.md` §7a. That is a far smaller and more durable obligation than a bash supervisor per project,
and it survives the loop being rewritten.

### The four changes

**C1 — correct `core/76-gpu-workers.md` § Provider Failover.** (infra) A *correction*, not an addition: the pack currently teaches the failed pattern to every
project whose glob matches. Fix the worked example to catch `HTTPStatusError` (so 402/403/404 fail over
rather than propagate), give the chain intra-provider diversity, and correct `:133` from per-provider to
**per-(provider, model)** breaker granularity, with the youtube evidence as the one-line why.

**C1b — `58-resilience.md`'s Per-Scaffold Applicability matrix omits `python-api-gpu`.** (infra) Verified:
`grep -c python-api-gpu .windsurf/rules/core/58-resilience.md` → **0**, and the matrix (`:23-35`) carries 11
rows against the registry's 12 types (`scaffold.py::SCAFFOLD_TYPES`, read this session). The missing one is
the scaffold type whose entire purpose is model inference — the type most exposed to provider death. An
agent scaffolding a `python-api-gpu` project and looking up its resilience obligations finds no row at all.
Found while grounding C1; it is the same defect class (the corpus is quietest exactly where this failure
lives) and ships with C1.

**C2 — add a `self-healing.md` ladder row.** (infra) Per the pack's own `:54` rule, the new failure class
gets a row: *Symptom* = a progress counter flat for > threshold while the loop is running · *First response*
= rebuild the chain from live survivors (or the gateway's own fallback) · *Fallback* = last-resort rung,
which must have been exercised · *Escalate* = one operator alert via `alerting/`, deduped, cleared on
recovery. Cross-reference from `58-resilience` § Banned Patterns: *a fallback chain that has never had its
bottom rung executed*.

**C3 — the scaffold `docs/RESILIENCE.md` template gains a "Provider-death resilience" section.** (**fleet**)
`templates/scaffold/docs/RESILIENCE_TEMPLATE.md` — the three outcomes as a declaration table, plus the
stall-threshold knob in §7a.

**C4 — `health-probe/` gains a chain-rebuild helper.** (**fabrik-lib**) NOT a new module. `health-probe/`
already returns uniform `{system,status,detail}` over injectable project probes and already feeds
`alerting/`. What is missing is the small pure function on top: *given a quality-ordered candidate list and
a probe result set, return the rebuilt live chain*. `alerting/`'s existing title-based dedup already
supplies outcome 3's "exactly one alert".

### Enforcement — stated honestly, because a rule naming enforcement that does not exist is a defect

| Claim | What actually enforces it |
|---|---|
| `/fabrik-spec-review` §E gains a provider-death / silent-stall row | **PROSE rubric row.** An LLM reads it and judges. There is no mechanical check and this spec does not pretend otherwise. |
| `/fabrik-plan-review` flags a retry-only design for an unattended loop | **PROSE.** Same. |
| The rule packs (C1, C2) | **Glob-activated prose.** They bind an agent that is editing a matching file. |
| The `RESILIENCE.md` §2a row-per-dependency requirement | Already mechanically enforced for the *existence* of the doc; the new section's **content** is prose. |

**No mechanical gate is proposed in this spec, and that is deliberate.** At 60% fleet incidence the gate
would be advisory wallpaper, and the honest mechanical check ("does this loop export a progress counter")
is a different, smaller piece of work that should be measured on its own. It is recorded in § Deferred, not
smuggled in as a claim.

**Does prose-only under-deliver against the instruction?** The instruction was that
*"resilience.md and .windsurf/rules must enforce this in the planning phase"*. Taken at its word, this
design delivers it: at the **planning phase** there is no artifact a mechanical check can read except the
plan/spec prose itself, and `.windsurf/rules` + the review-command rubrics ARE the enforcement surface that
operates there. A mechanical gate necessarily acts on *code*, which is a later phase than the one named.

But the honest reading does leave one gap, and naming it is the point: **the RESILIENCE.md §2b declaration
is mechanically checkable** — "a project with an unattended loop has a Provider-death subsection naming
which of the three outcomes it satisfies and how" is a decidable question about a doc, not a judgement
about code. That is the natural promotion target once C3 has landed and the fleet has run against it once.
It is not proposed here because it cannot be measured until C3's template section exists to be measured
against — proposing a gate for a section no repo has yet is exactly the "rule naming enforcement that does
not exist" defect this spec is organised to avoid. Recorded as the named next step, with its measurement
precondition stated, rather than either shipped blind or quietly dropped.

## Rejected alternatives

- **Mandate the bespoke probe fleet-wide (the proposal as literally written).** Rejected: wrong for 19 of
  26 measured repos, which would re-implement their gateway's own routing. Fails the *"build where consume
  exists"* reality-challenge and criterion 2 (TCO — dev time is the most expensive resource).
- **A new `core/*-resilience.md` pack.** Rejected: `self-healing.md:54` explicitly says a new failure class
  becomes a ROW in the existing ladder. A fourth resilience pack fragments a corpus whose packs already
  cross-reference each other, and it would leave `76-gpu-workers`'s wrong worked example in place —
  the actual source of the harm.
- **A new fabrik-lib `resilience/health_promote.py` module.** Rejected by the 1b ladder: `health-probe/`
  covers most of it; this is vendor+enhance at the seams. A new module also fails new-module-candidate
  test (d) — an existing module covers it.
- **Bespoke per-project stall supervisors (youtube's reference shape).** Rejected as the fleet default:
  every project would carry its own alarm loop, day-stamp state and Telegram call. Prometheus + the `for:`
  clause is the boring, already-deployed, lower-maintenance option (criteria 4 and 5). youtube's
  implementation stays valid for youtube — it predates this standard and works.
- **A blocking mechanical gate on landing.** Rejected on the measured 60%.

## External dependencies

**Every quoted string below was matched verbatim against the RAW source, not against a `WebFetch` answer.**
⚠️ The OpenRouter HTML doc pages are **client-rendered** — `curl` of
`https://openrouter.ai/docs/features/provider-routing` returns an 86 KB shell with no `<title>` and zero
content matches, so an HTML fetch there can neither confirm nor refute a quote. The verifiable raw source
is **`https://openrouter.ai/docs/llms-full.txt`** (3.66 MB), cited below with line numbers so the next
reader can re-run the match instead of re-fetching a page that cannot answer.

| Dependency | Grounded fact | Raw source · line · fetched |
|---|---|---|
| OpenRouter — provider routing | Outage-awareness is step 1 of the DEFAULT strategy: *"Prioritize providers that have not seen significant outages in the last 30 seconds."* Step 3: *"Use the remaining providers as fallbacks."* The `provider` options table gives `allow_fallbacks` type `boolean`, **default `` `true` ``**, *"Whether to allow backup providers when the primary is unavailable."* | `llms-full.txt` :72848 (strategy), :72814 (default) · 2026-08-28 |
| OpenRouter — ⚠️ the caveat that the paraphrase hid | *"If you have `sort` or `order` set in your provider preferences, load balancing will be disabled."* Since outage-prioritisation is **step 1 of load balancing**, a project that pins `order`/`sort` to force a provider **opts out of the outage-aware step** while believing it is protected. | `llms-full.txt` :72862 · 2026-08-28 |
| OpenRouter — model fallbacks | `models` is a **request-body array** in priority order. Trigger set, verbatim: *"By default, any error can trigger the use of a fallback model, including:"* → *"Context length validation errors"* · *"Moderation flags for filtered models"* · *"Rate-limiting"* · *"Downtime"*. | `llms-full.txt` :72375-72380 · 2026-08-28 |
| Prometheus — batch-job alerting | *"at least enough time for 2 full runs of the batch job"*; *"a single failure should not require human intervention"*; *"if it is possible to alert on symptoms rather than causes"* — a flat progress counter IS the symptom; a dead provider is the cause. | `https://prometheus.io/docs/practices/alerting/` — static HTML, all three matched by `grep` in the raw page · 2026-08-28 |

The OpenRouter `models`-array trigger list is load-bearing: the documented trigger is *any error*, so on
the gateway path the `http_402` billing-gate that killed youtube's tiers 2 and 3 is handled by the
platform. That is why outcome 1 is a *declaration* obligation for the 19 and a *build* obligation for at
most 7.

**The `sort`/`order` caveat changes what "declare it" means** and is why outcome 1 is not a no-op for the
gateway path. A project must declare **which** mechanism it relies on — the default load-balanced
outage-aware routing, or a pinned `order`/`sort` (in which case it has disabled step 1 and owes the
`models` fallback array explicitly). "We use OpenRouter" is not a resilience design; it is the name of a
gateway that can be configured out of the protection being claimed.

## fabrik-lib verdict table

| Capability | Verdict | Module · why |
|---|---|---|
| Probe external systems for liveness | **VENDOR** | `health-probe/` — pluggable, injectable project probes, uniform `{system,status,detail}`, already feeds `alerting/`. |
| Rebuild a candidate chain from probe results | **VENDOR + ENHANCE** | `health-probe/` — add the pure ordered-candidates × probe-results → live-chain function. Enhances the module's core ⇒ upstream it, never a silent fork. **Cross-repo write = HARD STOP for me; fabrik-lib's own agent does it.** |
| Fire exactly one operator alert, deduped | **VENDOR** | `alerting/` — SSH→Apprise→Telegram, title-based dedup, stdlib-only, never raises. The dedup IS outcome 3's "one alert". |
| Per-(provider, model) circuit breaking | **VENDOR** | `async-http-client/` — `CircuitBreakerRegistry` already keyed per upstream; C1 corrects the *documented granularity*, not the module. |
| Zero-progress detection | **BUILD → but as configuration, not code** | A Prometheus alert rule on a project-exported counter. No module needed; that is the point. |

## Shape / infra implications

- No new service, container, port, DB or Redis index. Nothing in `specs/services/*.yaml` `shape:` changes.
- Projects adopting outcome 3 need `/metrics` — i.e. `shape.exposes_metrics: true` — which is the existing
  contract for anything exporting a counter, not a new requirement.
- Applies across scaffold types via `58-resilience`'s existing Per-Scaffold Applicability matrix
  (`:23-35`). The static types (`docusaurus`, `static-site`) and `wordpress` (dead legacy string) have no
  unattended loop and are out of scope by that matrix, not by a new exception.

## Beat split and order (the reason this is a spec and not a commit)

| # | Change | Beat | Depends on |
|---|---|---|---|
| C4 | `health-probe/` chain-rebuild helper | **fabrik-lib** | — |
| C3 | scaffold `RESILIENCE_TEMPLATE.md` section | **fleet** | C4 for the "vendor this" pointer |
| C1 | correct `76-gpu-workers.md` § Provider Failover | infra (mine) | — (independent; ship first) |
| C1b | add the `python-api-gpu` row to `58-resilience.md`'s matrix | infra (mine) | — (ships with C1) |
| C2 | `self-healing.md` ladder row + `58-resilience` banned-pattern | infra (mine) | C4 to name a helper that exists |

**C1 is independent and ships first and alone** — it removes a worked example that teaches a 402-blind
failover from a glob-activated pack.

**Is "C1 first" a rationalisation for doing the easy infra half?** It is worth stating the challenge
because the ordering does happen to put my own beat first. The defence is that C1 is the only change that
removes *active* harm rather than adding guidance: today an agent building a `python-api-gpu` inference
chain who follows `76-gpu-workers` correctly ends up with youtube's outage. C3 and C4 make future projects
better; C1 stops the corpus teaching the failure. That said, the ordering claim is only honest if C1 does
not become the *whole* delivery — so this spec's completion condition is C1+C1b+C2 **and** the two mails
that hand C3 to fleet and C4 to fabrik-lib with this spec attached. Shipping C1 and calling the directive
landed would be under-delivery, and the directive was explicit that the scaffold template is in scope.

**C2-before-C4 — does the ordering argument actually hold?** Yes, but narrowly, and only for one sentence
of C2. The ladder row's *First response* column is where a helper would be named; every other column (the
symptom, the escalate-via-`alerting/` step) is implementable today against modules that already exist. So
C2 is not blocked wholesale — the fallback stated below (ship C2 naming the outcome and the gateway
mechanism, add the helper pointer when C4 lands) is a real path, not a face-saving one.

**So the C2 constraint is narrow and precise:** C2 must not ship a First-response that NAMES the C4 helper
before C4 exists — a rule naming enforcement that does not exist is the `oasdiff` defect removed from the
command corpus this morning. C2 itself is not blocked. If C4 slips, C2 ships describing the *outcome* with
the gateway mechanism as the only named default, and gains the helper pointer afterwards.

## Constraints

- `.windsurf/rules/**` and `commands/_sources/**` are governance-sync triggers: every sentence must hold for
  all 12 `SCAFFOLD_TYPES` (`scaffold.py::SCAFFOLD_TYPES`; 11 scaffoldable, `wordpress` raises
  `NotImplementedError`). No hub-only assumption.
- OpenRouter is the only sanctioned LLM gateway (`CLAUDE.md` § 1b-bis). The 7 direct-provider repos are
  pre-existing and this spec does not sanction new ones — it makes the direct path *carry a cost*
  (you owe the bespoke probe), which is the correct incentive.
- No metered LLM API on an operational path; no new secret; the probe calls only endpoints the project
  already authenticates to.
- Advisory/prose on landing. Promotion of any part to a mechanical gate is a separate operator decision
  backed by its own measurement.

## Open / blocking unknowns

| # | Unknown | Resolution step | Blocking? |
|---|---|---|---|
| U1 | Does `health-probe/`'s current public interface admit the chain-rebuild function without a breaking change? Read from its README table only — I have not opened its source (cross-repo read is permitted; I did not need it for the design, but C4's author does). | fabrik-lib's agent reads `health-probe/` and replies with the signature. | Blocks **C4 only**, not C1/C2. |
| U2 | What stall threshold is right per loop class? Prometheus says "2 full runs"; youtube chose 1800s. There is no single fleet number. | The template ships the **knob**, not a value, and the guidance sentence ("≥ 2 full runs of your loop"). | No — resolved by design. |
| U3 | Whether a mechanical "unattended loop exports a progress counter" check is worth building. | Its own measurement pass, after the prose lands and the fleet has run against it once. | No — recorded in § Deferred. |

## Deferred (recorded, not smuggled in)

- A mechanical check that an unattended loop exports a progress counter (U3).
- **The `RESILIENCE.md` §2b Provider-death-declaration check** — the one honest promotion target (see
  § Enforcement). Precondition: C3 must land first, so there is a section to measure conformance against;
  then measure the fire rate before proposing it, advisory-first per doctrine.
- Re-examining the 7 direct-provider repos once C1–C4 land; this spec measured them but did not audit
  them, and a count is not an audit. In particular the 5 that already call OpenRouter in code may need no
  new mechanism at all — only a routing change — and that is a per-repo judgement, not a fleet rule.
