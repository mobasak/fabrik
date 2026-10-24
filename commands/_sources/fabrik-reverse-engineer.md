---
description: Reverse-engineer ONE feature of an existing product (a public website, an Electron app, an APK, a native binary) into a BEHAVIOUR-ONLY spec, using the REA MCP (`mcp__rea__*`) to inspect it. LOOK (map it) · UNDERSTAND (x-ray the feature) · PLAN (clean-room spec) · BUILD (the pipeline builds from the spec, never the original) · ITERATE (compare, close gaps). TRIGGER — EN: "reverse engineer how X does Y", "rebuild this feature from that site"; TR: "şu özelliği tersine mühendislikle çıkar" — fires bare-prose. SKIP: market-wide comparison (→ /fabrik-rivals) · an idea with no product to inspect (→ /fabrik-spec). Stage: 1-design.
argument-hint: "<target: a public URL, an app path, an .apk or a binary> <the one feature to reverse-engineer>"
---

Turn a feature someone else shipped into a spec of what it DOES, so we can build our own version from
behaviour, never from their code. The inspection layer is **REA** (Reverse Engineer Anything,
`github.com/morluto/rea`, MIT), an MCP server that runs locally over stdio: browser observation for
websites (a Chrome-family browser drives the page and records structure, scripts, network and
screenshots), static analysis for JavaScript/Electron bundles, APK and .NET inspection, and native
disassembly through Ghidra or Hopper when those are installed. It reaches a session as the `mcp__rea__*`
tools through the roster (`/opt/fabrik/docs/workstation/mcp-roster.md` § REA) — never through REA's own
`setup`, which writes `~/.claude.json` and a personal skill and is not run on this box.

{{include:run-record}}
{{include:orient}}

{{include:injection}}

**REA's tools must be live before phase 1.** `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py` lists
`rea: CONNECTED` in a repo whose roster row grants it; absent there, the row is a roster decision, never a
hand edit of `.mcp.json`. Dead or missing in a granted repo is FIX-FIRST (`CLAUDE.md` § Behavior): the
installed binary is pinned by the roster row, and a server only a reload restores needs a new window — say
so. Start every investigation with `binary_session` called with `{}`: its `result.tool_availability` names
which operations this host can run, so a missing engine (Ghidra, Hopper, Frida) is known before a plan
leans on it.

**The target and its limits.** Inspect only what the operator named: a public page, an app or binary the
operator supplied, or our own product. No login with anyone's credentials, no paywall or rate-limit evasion,
no capture of other users' data, and a site's terms or `robots.txt` that forbid automated access stop the
run (`BLOCKED:` naming the clause). Nothing the original ships — code, minified identifiers, assets, copy —
enters our tree: the spec states behaviour in our own words, and the evidence stays in the run's
`SCRATCH:` folder.

## Phase 1 — LOOK: map what the target is made of

One Scout pass over the target as a whole, before the feature: for a website, `capture_browser_scenario`
with the actions that reach the feature (navigate, click, type), reading page structure, loaded scripts and
network requests; for an Electron app or an extracted bundle, `analyze_javascript_application`; for an APK,
`inspect_android_package`; for a native binary, `open_binary` then the overview tools
`binary_session` advertises. Write `<SCRATCH>/reports.md`: the stack (framework, bundler, API style), the
entry point that reaches the feature, the requests it makes and the state it keeps (URL, storage, cookies),
each line citing its REA Evidence ID. A claim with no Evidence ID is a guess and is marked so.

## Phase 2 — UNDERSTAND: x-ray the one feature

Turn the feature into a checklist of questions (what triggers it, what inputs it takes, what it sends and
receives, what state changes, what the user sees, what happens on each failure) and answer each from REA
evidence, entry point to result: the focused browser tools for runtime behaviour, the JavaScript tools for
the bundle code that handles the event, the network captures for payload shapes. Runtime observation
corroborates a static reading; it is used when static evidence cannot answer, and each answer is marked
`observed` (runtime) or `inferred` (static). For a feature with independent sub-questions, the
questions are the units of a Scout fan-out. **Dispatch step (D-191):** run `python3
/opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <questions> --mechanical 0` and dispatch exactly
the `SEATS:` and mix it prints, in ONE message — stamped BEFORE they go out with `python3 scripts/command_run.py dispatch
--seats <n>` and closed with `python3 scripts/command_run.py round --seats <n> --findings <open questions>`;
each Scout is a general-purpose seat whose brief names its question, the target, `reports.md` and its seat
folder under `RUN-SCRATCH:`, and whose toolset carries the REA tools. Each returns its answer with Evidence
IDs and its unresolved gaps; append them to `reports.md`. Done when every question is `answered`,
`partial` or `unresolved` with the search that bounds it — never "complete" while one is open.

## Phase 3 — PLAN: the behaviour-only spec

A Spec-Writer seat (`model: "opus"`) that has NOT run REA reads `reports.md` alone and writes the spec to
`docs/reference/reverse-engineering/<target-slug>-<feature-slug>.md`: the feature in one paragraph; each
behaviour as `trigger → observable result`, numbered, with its inputs, outputs, states and error cases;
the interface shapes in our own neutral names (a request carries `query: string`, never their variable
names); the open unknowns; and a `## Evidence` table mapping each behaviour number to the Evidence IDs in
`reports.md`. Then the CLEAN-ROOM CHECK, by the lead, executed: every behaviour cites at least one Evidence
ID; the spec quotes no code (no fenced block copied from the target, no minified identifier — grep the spec
for each identifier `reports.md` records from their bundle and expect zero); no asset, copy text or brand
of theirs. A failed check is fixed in the spec, never waived.

## Phase 4 — BUILD: hand the spec on, never the original

Building is the pipeline's job, not this command's: the spec seeds `/fabrik-spec` (a feature for a
product) or `/fabrik-task` (one reversible change), and its Builder — the executing agent — is given the
spec and our own repo only. The Builder never opens the target, `reports.md` or REA; that separation is
what makes the result our own implementation. Record in the run's `--evidence` which command took the spec.

## Phase 5 — ITERATE: compare, then close the gaps

Once our version runs, a Tester seat drives BOTH — the original through REA, ours through the repo's own
test surface — against the spec's numbered behaviours, and writes `<SCRATCH>/comparison.md`: per
behaviour `same` · `differs (how)` · `missing`, each with evidence from both sides. Each gap becomes a
spec amendment (a behaviour we missed) or a build item (a behaviour we built wrong), routed through the
same command that took the spec. Loop until a pass finds no gap the operator wants closed. When no build
exists yet (the usual end of a first run), this phase records `not started — no build` and the run ends at
phase 3's spec.

## Close

The terminal: the behaviour-only spec committed under `docs/reference/reverse-engineering/`, every
behaviour tied to Evidence IDs, the clean-room check passed, and the unknowns listed. `INDEX.md` gets the
spec's row. A decision the run made (a target refused, a feature scoped out) is a D-row.

{{include:close-chain}}
