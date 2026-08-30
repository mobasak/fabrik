# Plan 3 — The MCP split implementation (per-repo .mcp.json + user-level trim)

**Status:** CONVERGED (review round 1: 4 findings — write-set test, fabrik-lib dark-window reorder, invariant command, B-ref renumber — fixed in-file; round 2 fresh pass: 0 new)
**Date:** 2026-08-30
**Owner:** infra (hub session) — NO-POOL standing directive: solo native, no pool/subagent dispatch
**Authority:** docs/DECISIONS.md D-013..D-024 (the complete MCP adjudication, 17/17 servers ruled) +
docs/workstation/mcp-roster.md (the living roster record) + operator this turn: "do so", "be aware we
have claude account rotation, do not break it", "be sure all agents and subagents can use our mcps
properly".

## Goal

Every Claude Code window loads exactly the MCP servers its repo earned in the D-013..D-022 rulings —
universal 6 everywhere, type sets + per-repo overlays where granted, full set only hub-class — via
per-repo `.mcp.json` files emitted from the live rulings, with the user-level roster trimmed to the
universal 6 through the rotation-safe sync path, and with every native subagent and pool worker still
reaching the servers it declares.

## DONE WHEN

1. `scripts/sysadmin/emit_mcp_project_config.py` derives each typed `/opt` repo's server set LIVE
   from `project.yaml::type` + the per-type table + the per-repo overlay table (each row carrying its
   D-ref), and writes an idempotent `.mcp.json`; `--check` diffs without writing; red-first tests
   cover derivation, idempotence, overlay, URI resolution, and skip rules.
2. The fleet-wide emission run has produced `.mcp.json` in every typed repo (post fleet's D-023 type
   fixes), `.mcp.json` is gitignored fleet-wide via the manifest's generated block, and
   `claude mcp list` (or the config read) in 3 sample repos of different classes shows exactly the
   ruled set.
3. All account-dir rosters are trimmed to the universal 6 via `claude_rotate.py --sync-mcp` (never a
   hand-edit; `active` symlink untouched), `/opt/fabrik/.mcp.json` carries the hub-class remainder,
   and `scripts/dr_claude_backup.sh` has run after every config change. Rotation invariant: all
   account rosters byte-identical after trim.
4. Subagent reachability verified: each Runtime-A agent's declared `mcpServers` resolves in the repos
   it is dispatched to (or absence is proven tolerant), and the pool's `/opt/fabrik/mcp.json` still
   matches its rulings (context7 pool-only survives; github absent).
5. Docs current same-change: mcp-roster.md topology section rewritten (KEEP-CURRENT contract),
   pack 62 § mcp.json source-of-truth names the per-repo layer, CHANGELOG + INDEX rows, and a
   DECISIONS.md row for each planning decision listed in § Decisions minted below.

## Out of Scope

- fabrik-lib's own `.mcp.json` (cross-repo HARD STOP — B4 mails their agent the derived full-set
  content; they land it).
- Scaffolder emission of `.mcp.json` for NEW projects (fleet's beat — B4 mails the request; until
  landed, a new repo gets its file on the next hub emission run).
- The fabrik-claim-validator MCP entry (D-022 planned row — emitted only when their endpoint exists).
- The 12 type corrections themselves (fleet, mail 01M19PKH30) — this plan only ORDERS around them.
- Any change to Runtime-B pool tool policy (pack 62 § Pool tool access stands unchanged).

## Constraints Digest (rule-grounding gate v2 — verbatim quote + file:line per MUST-READ pack)

MATCHED set derived: `python scripts/review_rubric.py --changed scripts/sysadmin/emit_mcp_project_config.py scripts/sysadmin/claude_rotate.py docs/workstation/mcp-roster.md` → FLOOR (35/25/30/12-FACTOR) + core/10 + core/40; plus core/62 (glob `**/*subagent*` + `**/.mcp.json` — the emitted artifact and the pack file itself).

| Rule (verbatim quote) | Pack:line | Bearing on this plan |
|---|---|---|
| "whether the codebase could be made open source at any moment, without compromising any credentials." | .windsurf/rules/core/10-python.md:248 | The emitted `.mcp.json` carries a resolved local `DATABASE_URI` → it MUST be gitignored (manifest block), never committed. |
| "keys via `${ENV}` expansion, never inline" | .windsurf/rules/core/62-using-subagents.md:189 | Governs the POOL file `/opt/fabrik/mcp.json` — unchanged here. Mirror named for the per-repo file: `${VAR}` reads the SHELL env, not the repo `.env` (grounded via docs agent), so per-repo DB URIs cannot use expansion; the resolved-inline + gitignored + hub-regenerated shape is the deliberate exception, recorded as a decision row. |
| "tool access = the agent-type frontmatter (`tools` / `mcpServers` / `disallowedTools`)" | .windsurf/rules/core/62-using-subagents.md:19 | Runtime-A reachability audit (C1) checks each agent's frontmatter names against the per-repo sets. |
| "Never restate tool lists in a command brief — the access lives in the agent-type file (Runtime A) or the `AgentSpec` (Runtime B)." | .windsurf/rules/core/62-using-subagents.md:13 | The emitter encodes SETS (rulings), never touches command briefs or agent files. |
| "Edit existing docs instead of creating new ones." | .windsurf/rules/core/40-documentation.md:167 | Only new .md is this plan (allowlisted path); everything else edits existing docs. |
| 6 | .windsurf/rules/core/40-documentation.md:61 | "Source, config, or Docker file changed" | A3/C3 carry both rows. |
| "cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)" | .windsurf/rules/core/35-security-auth.md:297 | Every roster-config mutation is followed by `dr_claude_backup.sh` (the stronger, versioned form already mandated by memory/contract); `.env` files are only READ, never edited. |
| "swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**." | .windsurf/rules/core/25-data-postgres.md:270 | postgres-pro's per-repo URI lives in emitted CONFIG (env block), resolved from the repo's own `.env` `DATABASE_URL` — no code decides hosts. |
| "Inside a container, `localhost` resolves to the container itself" | .windsurf/rules/core/30-ops.md:37 | Checked-N/A consciously: windows + MCP servers run on the WSL HOST, so a `localhost` PG URI in `.mcp.json` is correct here; the ban binds containers. |
| "Use type hints for all function signatures" | .windsurf/rules/core/10-python.md:150-152 | The emitter is fully typed, modern syntax. |
| "a non-trivial behavior's test proves something only if it has been SEEN RED" | .windsurf/rules/core/45-testing-strategy.md:21 | A1 is red-first by construction: every listed behavior watched red before the emitter exists (test 10 included). |
| "a commit touching the governance-sync trigger surfaces" | CLAUDE.md § Sync-consciousness | The pack-62 edit (C2) is a synced-surface commit — correct for all repos by construction (it documents box topology, not repo behavior). |
| "create/edit/**commit** files in a repo OTHER than the one you were launched in (cross-repo)" | CLAUDE.md § HARD STOPS | The emitter writing `.mcp.json` into `/opt/*` is a NEW sanctioned distribution path of the same class as the governance-sync (operator-ordered by the split ruling) — minted as a decision row, and it writes ONLY the gitignored `.mcp.json`, nothing else, never commits in target repos. |

Selections not covered by a row: `unconstrained`.

## File Scope (hub repo)

- `scripts/sysadmin/emit_mcp_project_config.py` (NEW — AFTER-EDIT header pointing at mcp-roster.md + fabrik_synced_manifest.py)
- `tests/test_emit_mcp_project_config.py` (NEW)
- `scripts/fabrik_synced_manifest.py` (gitignore block gains `.mcp.json`)
- `tests/test_sync_seed_if_missing.py` (extend: gitignore-block assertion for `.mcp.json`)
- `.claude/settings.json` + its synced source in AGENT_HOOK_FILES flow (`enableAllProjectMcpServers: true`)
- `.windsurf/rules/core/62-using-subagents.md` (§ mcp.json source-of-truth gains the per-repo layer)
- `docs/workstation/mcp-roster.md` (topology section rewrite)
- `CHANGELOG.md`, `INDEX.md`, `docs/DECISIONS.md`
- OUTSIDE the repo, sanctioned: per-repo `.mcp.json` writes (gitignored artifacts), `~/.claude-fleet/*` via rotator only, `/opt/fabrik/.mcp.json` (hub's own project file — in-repo actually, gitignored)

## Behavior Contract

- **Given** a fixture repo with `type: python-api`, **When** the emitter runs, **Then** its `.mcp.json` contains exactly the universal 6.
- **Given** a fixture repo with `type: saas-skeleton`, **When** the emitter runs, **Then** the set adds playwright, chrome-devtools, shadcn, magicui.
- **Given** a fixture repo named as an overlay holder (wef shape), **When** the emitter runs, **Then** the D-016/017/019/022 grants are present.
- **Given** a repo `.env` carrying `DATABASE_URL`, **When** the emitter runs, **Then** postgres-pro's env block carries it as `DATABASE_URI`; **Given** no `DATABASE_URL`, **Then** the env block is OMITTED entirely.
- **Given** an emitted `.mcp.json` already current, **When** the emitter re-runs, **Then** no file is written (idempotence) — and `--check` never writes in any state.
- **Given** an untyped or `.git`-less directory, **When** the emitter runs, **Then** it is skipped.
- **Given** the hub repo, **When** the emitter runs, **Then** the full 16-server set is emitted.
- **Given** a full-tree snapshot of a fixture repo, **When** an emission run completes, **Then** the only created/mutated path is `.mcp.json` (write-set containment).
- **Mocked:** nothing — real temp-dir fixture repos with real `project.yaml`/`.env` files; the live `/opt` tree is never a test target.

## Phases

### Phase A — the emitter (hub-side, executable NOW; no fleet-wide writes)

- A1 **Red-first tests**, watched red before implementing:
  (1) headless repo type → exactly universal 6; (2) saas repo → universal 6 + playwright,
  chrome-devtools, shadcn, magicui; (3) overlay repo (wef fixture) → + the D-016/017/019/022 grants;
  (4) postgres-pro env carries the repo's `.env` `DATABASE_URL` as `DATABASE_URI` when present, and
  OMITS the env block when absent (server starts unconnected — degraded, never wrong-DB);
  (5) idempotence: second run writes nothing (mtime/content unchanged); (6) `--check` never writes;
  (7) untyped/`.git`-less dirs skipped; (8) fabrik-claim-validator absent until its endpoint entry
  is added to the source table; (9) hub repo → full 16-server set; (10) **write-set containment**:
  after an emission run over a fixture repo, the ONLY path created/mutated under the repo is
  `.mcp.json` (full-tree snapshot diff) — the digest-row-12 claim as a test, not an assertion.
- A2 Implement `emit_mcp_project_config.py`: server DEFINITIONS mirrored from the live
  `~/.claude.json` shapes (stdio commands/args, citation-verifier `type: http` url); SET DERIVATION
  from `project.yaml::type` + the per-type table + overlay table, every row commented with its D-ref;
  `--repo <path>` single-repo mode; `--check` diff mode; default = all typed `/opt` repos + the hub.
- A3 Manifest: `.mcp.json` joins the generated gitignore block (fleet-wide on next sync);
  CHANGELOG + INDEX rows. Gate + scoped review + commit + push.

### Phase B — rosters (ORDERED: emission BEFORE trim; trim is the LAST mutation)

- B1 **HOLD-POINT: requires fleet's D-023 type-fix ack + operator go-word.** Run the emitter
  fleet-wide; spot-verify 3 repos of different classes (headless / saas / overlay) by reading the
  emitted files + `claude mcp list` in one of them.
- B2 Hub's own `/opt/fabrik/.mcp.json` (full set) + `enableAllProjectMcpServers: true` into the
  synced settings surface (removes the per-repo approval dialog; single-operator threat model —
  every `.mcp.json` on the box is hub-emitted).
- B3 Mails FIRST (moved before the trim — review finding): fabrik-lib (their derived full-set
  `.mcp.json` content, for their agent to land — the trim would otherwise degrade their window to
  universal 6 until it lands) · fleet (scaffold-time emission for new projects + the
  census-dependent re-run note).
- B4 User-level trim to universal 6 — **precondition: fabrik-lib confirmed their `.mcp.json`
  landed** (their reply; if the operator waives the wait, the degraded-to-6 interim is stated, not
  silent). Edit the SOURCE roster once, push with `claude_rotate.py --sync-mcp --from <source>`,
  verify the rotation invariant with the concrete check:

  ```bash
  for f in ~/.claude-fleet/*/.claude.json; do python3 -c "
  import json,sys; print(hash(json.dumps(json.load(open('$f'))['mcpServers'],sort_keys=True)))"; done | sort -u | wc -l   # MUST print 1
  ```

  then `dr_claude_backup.sh`. ⚠️ Never edit an account dir by hand; never touch the `active`
  symlink. Windows pick the trim up on reload — sequencing means no window ever lacks a server its
  repo grants.

### Phase C — subagents + docs (with B, same gate)

- C1 Reachability matrix, EXECUTED not asserted: for each Runtime-A agent with `mcpServers`
  frontmatter (fabrik-gui: playwright/shadcn/chrome-devtools · fabrik-researcher: exa/brave-search)
  × the repo classes it is dispatched in → server present in that repo's derived set, OR a live
  tolerance probe (dispatch the agent in a repo lacking the server; it must degrade, not die).
  Pool: assert `/opt/fabrik/mcp.json` unchanged and matching its rulings.
- C2 Pack 62 § mcp.json source-of-truth gains the per-repo `.mcp.json` layer (emitted, gitignored,
  hub-regenerated — "adding a tool touches" list gains the emitter's table). Synced-surface commit.
- C3 mcp-roster.md topology section rewritten to the POST-split truth (KEEP-CURRENT contract);
  CHANGELOG; DECISIONS rows minted (below); whole-plan review; EXECUTED stamp; archive.

## Decisions minted by this plan (rows appended at the phase that lands them)

1. Emitted `.mcp.json` = gitignored + resolved-inline local URIs + hub-regenerated (the ${VAR}
   expansion limitation, grounded: expansion reads the shell env, not repo `.env`).
2. The emitter is a sanctioned cross-repo distribution path (same class as governance-sync,
   operator-ordered by the split), writing exactly one gitignored file per repo.
3. `enableAllProjectMcpServers: true` fleet-wide (single-operator threat model; every project
   `.mcp.json` is hub-emitted, not third-party).

## Ordering & risk register

- **Rotation safety:** the only account-level mutation is B4, via the rotator's documented merge
  path (`_cmd_sync_shared` — section-level MERGE preserving each dir's OAuth + trust sections,
  parse-failure dirs SKIPPED, verified in code this session). `.mcp.json` files are account-independent.
- **No dark window:** emission (B1) strictly precedes trim (B4); a reload between them shows a
  superset, never a subset, of the ruled set.
- **Fleet dependency:** only B1 gates on fleet; A lands immediately. A late type fix = re-run the
  emitter for that repo (idempotent).
- **`${VAR}` unset behavior** (grounded): Claude Code warns and loads the server with unexpanded
  text — why A1 test 4 mandates OMITTING the env block rather than emitting an unexpandable var.
- **fabrik-gui/shadcn absence** in chrome-extension/docusaurus repos: C1 probes tolerance; if a
  declared-but-absent server breaks agent spawn, the fix is a per-type set addition (roster + D-row),
  not an agent edit.

## Evidence

### Phase A evidence (grounding, this session)

- `scaffold.py::SCAFFOLD_TYPES` = the 12 types (enumerated live; census over 57 dirs, 40 typed).
- `~/.claude-fleet/` layout verified live: `active -> mob` symlink + can/mob/ob/sarp dirs;
  `_fleet_root()` at `scripts/sysadmin/claude_rotate.py:1380`, roster merge at `_cmd_sync_shared`
  (docstring: "section-level MERGE, never a file copy … a dir whose `.claude.json` cannot be parsed
  is SKIPPED rather than overwritten").
- Zero existing `.mcp.json` machinery: `grep -rn "\.mcp\.json" scripts/ src/` → 0 hits (extend-don't-
  duplicate satisfied; the emitter is new by necessity).

```text
$ grep -rn ".mcp.json" /opt/fabrik/scripts /opt/fabrik/src | grep -v .pyc | wc -l
0
```

### Phase B evidence (grounding)

- Claude Code `.mcp.json` semantics grounded via docs agent (code.claude.com/docs/en/mcp.md,
  fetched 2026-08-30): project scope beats user scope on same name; `${VAR}` reads shell env;
  `enableAllProjectMcpServers` bypasses approval; `disabledMcpjsonServers` exists for per-server
  blocking. Interactive approval dialog exists without the setting.
- Pool file read live: `/opt/fabrik/mcp.json` → brave-search, context7, exa, firecrawl.

```text
$ python3 -c "...json.load(open('/opt/fabrik/mcp.json'))..."
['brave-search', 'context7', 'exa', 'firecrawl']
```

### Phase C evidence (grounding)

- Agent declarations read live: `~/.claude/agents/fabrik-gui.md` → `mcpServers: [playwright, shadcn,
  chrome-devtools]`; `fabrik-researcher.md` → `mcpServers: [exa, brave-search]`.

## Self-audit

- Every fleet-wide write is either the gitignored `.mcp.json` (new sanctioned path, decision row 2)
  or rides existing machinery (manifest gitignore block, governance-sync for pack 62/settings,
  rotator for rosters). No target-repo commits, ever.
- The three operator constraints of this turn are each pinned to a mechanism: rotation → B3's
  rotator-only law + byte-identical verify; corrected types → B1 hold-point + live `project.yaml`
  reads; agents/subagents → C1 executed matrix + pool file assert.
- Residual honestly held: per-repo `DATABASE_URI` quality depends on each repo's `.env` having a
  real `DATABASE_URL` (absent → server runs unconnected — same degraded state as today, never worse).
- NO-POOL declared throughout; pack 62's pool-grounder default consciously overridden by the
  operator's standing directive.
