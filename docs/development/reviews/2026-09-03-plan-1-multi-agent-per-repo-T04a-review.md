# Acceptance review — T04a (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch (worktree-agent-acebd2e7d801c89f7, head 56e9dd72) against its merge base c22bd91c — 1 file, `commands/_sources/fabrik-spec.md` +34/−2 (the epic-file intake bullet in Phase 0, a one-clause addendum in § 1b). Coder: native Sonnet worktree; Gate 1 red-before (0) → 2; `--check` reports only this file as DRIFT (expected from a worktree); `check_command_corpus` sound across 94 files. Brief defect found by the coder: the ticket's Context File `EPIC-ARTIFACT-SCHEMA.md` carries the 11-field machine frontmatter, not the 15-field `### Metadata` prose block — the names were grounded from `03-expand-epic-files-fabrik.md` § Metadata + a live epic + the ettw trigger (carried into T04b's brief).

## Round 1
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 1.

### Adjudication (pool layer)
- ALL THREE — CONTRADICTION, CONFIRMED by the orchestrator's read of the branch file (line 43): the unchanged Scale up-route bullet ("If the idea is an **epic** … → route to `…/00-trigger-fabrik.md`") fires on every epic-file argument by definition, while the new bullet says "The Scale up-route and Duplicate-check bullets below still run" — the intake path is unreachable as written → FIXUP routed to the coder (exempt the epic-file argument in the up-route sentence itself; the retired-trigger path stays — T10 owns that retirement, `grep -l 00-trigger-fabrik` over the set → T10 only).
- deepseek + qwen — Metadata casing ("Universal Categories", "Dark + Light", "HAS USER GUIDE", "Rule packs"; "Abuse Detection" not a field) — UNVERIFIED by them (no source lines quoted); carried to the coder as a character-for-character check against `03-expand-epic-files-fabrik.md` § Metadata with the lines quoted.
- gemini — "the 15-name list includes `target_vps`/`Registrars` which are also among the four named rows, so rows duplicate" — REFUTED: the four are a SUBSET named explicitly so they never drop (the ticket's own wording), one row each; "§ 1b-bis does not exist" — REFUTED by grep: `### 1b-bis — Fabrik hard constraints…` is line 107 of the file, referenced 3 times; "instructional prose defect" (explains provenance) — a wording preference, weighed by the native finder under Part B/C.
- qwen — "the `argument-hint` line changed" (byte drift) — it is the diff's own `-`/`+` pair for the intake hint; whether the chat-brief hint text survived verbatim is in the native finder's brief (every `-` line accounted for).
Native finder (opus): PENDING — appended when it returns.
