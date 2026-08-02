# `/fabrik-user-test` — upstream feedback (first-consumer run)

**Consumer:** `tryton-crm` (multi-tenant CRM/ERP; GUI = the Tryton 8.0 `sao` web client, rebranded *tojlo crm*)
**Run:** 2026-08-02, Claude Opus orchestrator + 3 parallel `fabrik-gui` subagents
**Command source:** `/opt/fabrik/commands/_sources/fabrik-user-test.md`

The command is well-built — the coverage-denominator framing (inventory → journeys → matrix), the
UI-truth-vs-SYSTEM-truth leg, and the loop-until-two-dry-sweeps rule are exactly right for this product,
and the very first probe it drove me to run found two real defects. Items below are friction/correctness
issues found while actually executing it, ordered by impact.

---

## 1. ⚠️ The Phase-0 surface gate mis-routes hybrid and non-scaffold GUIs (highest impact)

**What it says:** Phase 0.1 — "`project.yaml::type` must be UI-bearing ({`saas-skeleton`, `chrome-extension`,
`mobile-app`, `desktop-app`, `static-site`, `docusaurus`}). A headless type ({`python-api`, …}) → STOP and
route to `/fabrik-service-test`."

**What happened:** tryton-crm is `type: python-api` — so the literal gate says STOP. But the project ships a
**genuine, contract-frozen GUI**: `docs/ui-design.md` (FROZEN, v4), a rebranded client built and served
(`sao-overlay/rebrand.js`, `Dockerfile.trytond:46-51`, live `document.title === "tojlo crm"`), a trilingual
EN/TR/FA GUI, a native analytics dashboard, a pre-auth branded login front-door, and existing GUI regression
tests (`tests/gui/test_rebrand.py`). Obeying the gate literally would have refused a full GUI certification
on a string in a YAML file.

**Why the gate is wrong here:** `project.yaml::type` describes *which scaffold generated the project*, not
*what surfaces it has today*. Two real cases break it:
- **Hybrids** — this product is a GUI **and** a headless bridge API. It legitimately needs *both*
  `/fabrik-user-test` and `/fabrik-service-test`; the current gate forces an either/or.
- **Non-scaffold GUIs** — a GUI that is a *vendored third-party client* (Tryton `sao`, a Grafana/Metabase
  skin, a Django-admin surface) will never carry a UI-bearing scaffold type.

**Suggested fix:** make the gate *evidence-based, with the type as a hint, not the verdict*:
> Proceed if ANY of: `project.yaml::type` ∈ UI-bearing set **OR** `docs/ui-design.md` exists **OR** the
> project serves an HTML client (a `sao-overlay/`-style overlay, a `static/`/`www/` bundle, a templates dir).
> If the type says headless but UI evidence exists, proceed **and emit a finding** that `project.yaml::type`
> is stale (or that the project is a hybrid) — the mismatch is itself worth reporting.
> If BOTH a GUI and a headless API surface exist, say so explicitly and recommend the twin command for the
> other half rather than routing away from the one the operator asked for.

Without this, the command's own anti-pedantry goal is undercut by its first gate.

---

## 2. Parallel `fabrik-gui` subagents cannot share the singleton Playwright MCP browser

**What it says:** Phase 3 — "Browser/device work = native `fabrik-gui` subagents, in PARALLEL — one per
flow-bundle, disjoint scenario ownership", and Subagents — "**≥2 parallel native `fabrik-gui` subagents**".

**The conflict:** the Playwright **MCP server is a single shared browser instance** for the session. Two or
more subagents calling `mcp__playwright__browser_navigate` / `browser_click` concurrently drive the *same*
browser and the *same* tabs — they stomp each other's navigation and their screenshots interleave. "Disjoint
scenario ownership" solves data collisions but not *browser* collisions.

**What I did:** instructed every `fabrik-gui` agent to **not** use the MCP browser tools, and instead author
`.spec.ts` files and run them with `npx playwright test <file>` — each run spawns its own isolated browser
process, so N agents genuinely run in parallel. This also happens to satisfy Phase 3's "persist as you go"
requirement for free, since the artifacts *are* the suite.

**Suggested fix:** state this explicitly in Phase 3, e.g.:
> "For a **parallel** fan-out, agents must NOT drive the shared Playwright MCP browser (one instance per
> session — concurrent drivers collide). Each parallel agent authors and runs its own Playwright spec
> (`npx playwright test`), which isolates the browser per agent and produces the persisted suite directly.
> Reserve the MCP browser for a **single** interactive/exploratory agent, or for a serial round."

This is a correctness bug in the method as written, not a preference — following it literally produces
flaky, mutually-corrupting rounds.

---

## 2b. Parallel agents in one repo also collide on the test-runner's OUTPUT directory (evidence loss)

A second, subtler collision from the same "run agents in parallel" mandate — and this one **silently destroys
the evidence the command requires**.

Playwright **clears `test-results/` at the start of every run** (`preserveOutput` defaults to
`'always'` for *artifacts it manages*, but the output directory itself is wiped per run, and any
`page.screenshot({ path: 'test-results/…' })` written by a previous agent goes with it). With three agents
each invoking `npx playwright test` in the same project, agent B's run deletes agent A's screenshots.
Observed live in this run: the screenshot count went **3 → 0** while all three agents were mid-flight.

Since Phase 3 mandates "**Evidence per verdict, no exceptions** — every PASS = screenshot", this turns the
command's core evidence rule into a race.

**Suggested fix:** pair the parallel-agent instruction (item 2) with an output-isolation requirement:
> "Each parallel agent must write artifacts to its **own** output directory — e.g. run with
> `--output=test-results/<agent-prefix>` and screenshot to `test-results/<agent-prefix>/…` — because the
> test runner clears its output directory per run and concurrent agents would otherwise erase each other's
> evidence."

(Same root cause as item 2 — "parallel agents share one workspace" — but a different shared resource, so it
needs its own line in the command.)

---

## 2c. `fabrik-gui` subagents reliably STALL by backgrounding their own test runs (observed 3x)

**Added after the run continued — the most disruptive practical failure, and it hit three of four gauntlet agents.**

**What happens:** a `fabrik-gui` subagent starts a Playwright run in the background (or arms a Monitor), then
ends its turn with something like *"I'll pause here and resume once the Monitor notification for the
login-probe test arrives."* **Monitor/background notifications do not deliver to a subagent**, so it waits
forever. From the orchestrator's side the agent reports `completed` carrying a non-result, having burned its
budget (one: 122 tool calls / 40 min; another: 52 calls / 11.5 min) and produced spec files but zero verdicts.
Each had to be individually resumed by `SendMessage` with an explicit "run synchronously, never wait on a
Monitor" instruction — after which each worked correctly and returned full results.

Why GUI agents are especially prone: browser suites are slow (a menu-inventory sweep here legitimately took
9.4 minutes), so the agent's instinct is to background the run and await a signal — precisely the mechanism
unavailable to it.

**Suggested fix** — an explicit execution rule in Phase 3, beside the subagent mandate:
> "Subagents must run test suites **synchronously** (a plain shell call with a generous timeout) and read the
> exit output. Never background a run or wait on a Monitor/notification — those do not deliver to a subagent,
> and it will stall until its budget is exhausted. If a suite is too slow for one call, **split its scope**
> and run each slice synchronously."

Worth stating in the **`fabrik-gui` agent definition** too, since it binds every consumer of that agent type,
not just this command.

---

## 3. The mandated pool layer has no documented behaviour when the pool is unavailable

**What it says:** Subagents — "**≥1 pool `fanout` dispatch** for the gradeable non-browser breadth
(auto-records → `set_quality` back-fill) … All-native here = zero flywheel rows (advisory-WARN'd)."

**What happened:** the pool dispatch returned **HTTP 402 Insufficient credits** from OpenRouter for all 3
units (it had succeeded earlier in the same session — credits ran out mid-run). The command gives no
guidance for this, and the flywheel obligation becomes unsatisfiable through no fault of the dispatch.

**Suggested fix:** add one line to the Subagents section:
> "If the pool is unavailable (missing key, 402/quota, network), that is a **BLOCKED-env finding to report**,
> not a silent skip: record it in the report, do the gradeable breadth inline, and note that the flywheel
> gets zero rows for this run and why."

Same pattern the command already applies to the mail-catcher ("no mail-catcher seeded = a BLOCKED-env
finding to fix, never a silent skip") — it is just missing for the pool.

---

## 4. The mandatory journey set assumes a self-serve SaaS; it maps poorly to an admin-provisioned ERP

**What it says:** Phase 1b lists as "minimum": **first-day** (discover → sign up → verify → onboard),
**paying-customer** (paywall → upgrade → invoice → cancel), **leaving-user** (export → delete account).

**The mismatch:** an internal multi-tenant ERP has **no self-serve signup**, **no paywall**, and **no
self-service account deletion** — users are provisioned by an operator (this project's own runbook is
"stock sao user mgmt + a set-password email" in `docs/OPERATIONS.md §3`). Read literally, three of the five
mandatory journeys are N/A, which invites either a bogus "SKIPPED ×3" or an agent inventing flows that do
not exist.

**Suggested fix:** offer an explicit **B2B/internal-tool journey variant** alongside the SaaS one:
> *first-day* → **operator provisions a user; that user logs in for the first time (set-password/invite
> link) and must reach the product's core value once**;
> *paying-customer* → **entitlement/role change: operator grants a role or module access; verify the UI
> unlocks it end-to-end and that revoking it re-locks**;
> *leaving-user* → **operator deactivates the user; verify access is revoked and their records survive
> (an ERP must not lose the departed user's data)**.
> These are the same three arcs with the actor changed from "the user themself" to "an operator", and they
> are testable on every internal tool.

---

## 5. Smaller items

- **`fabrik-lib/doc-crawl` is listed as a Phase-0 vendor for "website and doc-site surfaces"** but there is
  no stated criterion for an **authed SPA with a server-driven menu tree** (sao). I skipped it with a
  documented reason and substituted menu-tree walking. A half-line — "app surfaces with a server-driven nav:
  walk the nav tree instead of crawling links" — would remove the judgement call.
- **The `api-smoke-test` preflight assumes the GUI's backend is *the project's* API.** Here the sao GUI talks
  to **trytond JSON-RPC**, while the project's FastAPI bridge is a *different* consumer-facing service the
  GUI never calls. Worth saying "preflight the backend **the GUI actually calls**", which is not always the
  repo's own API.
- **Phase-0 obligation ordering vs. reality.** The "three mechanical obligations **before Pass 1**"
  (anchor → rubric → persist the review file) sit *after* Phase 0's "app must be RUNNING" in reading order,
  but a run naturally probes drivability first (you cannot scope a checklist for a surface you have not
  confirmed you can reach). Suggest explicitly permitting a *feasibility probe* before the persist step, so
  the orchestrator is not technically in violation while doing the sane thing. (Relatedly: Phase 3 says the
  orchestrator "does not drive" — but Phase 0's drivability probe *is* orchestrator driving. Worth carving
  out: "a bounded Phase-0 feasibility probe by the orchestrator is expected; the *gauntlet* rounds are the
  part that must be delegated.")

---

### Update (same run, later) — item 3 confirmed as a standing blocker
The pool 402 was re-tested after the operator lifted a *Claude* session limit: still
`HTTP 402 Insufficient credits` from OpenRouter. The two limits are independent, which is exactly why the
command needs the documented "pool unavailable" path — the run completed its GUI legs fine while the
mandated flywheel layer was structurally impossible, and there is currently no sanctioned way to record that.

*Filed per the operator's instruction to report issues via the upstream-feedback path. No `/opt/fabrik`
command source was modified — this is a sibling feedback note only.*
