# T02 — merge_request.py request: finishing work sends one request

## Scope
PRECONDITION: W-076ff4a9 (the owner resolver's row selection) is closed before this ticket is dispatched — the dispatcher reads `status` in `.fabrik/work/W-076ff4a9.json` and holds T02 while it is not `done`. Implements spec § The delta 1, 2, 3 and 8. New `scripts/merge_request.py` with the `request [--item <id>]` verb, run inside a linked worktree: refuses unless the branch is pushed and `head` equals the remote tip (`git ls-remote`; an unreachable remote exits with the reason and sends nothing), resolves the owner with `python3 /opt/fabrik/scripts/decisions.py --merge-owner <repo root>` — the hub's box-wide absolute path, the convention the template already uses (`templates/governance/CLAUDE.md:129`), because `decisions.py` is not synced into projects — and — a repo with no `docs/DECISIONS.md` at all is UNDECLARED, checked before the resolver runs, because the resolver exits 1 there (`scripts/decisions.py:584-588`) — on UNDECLARED (no ledger, or exit 3) refuses with the adopt command, on any other non-zero exit refuses naming the resolver failure (never read as UNDECLARED); writes the body (`branch`, `head`, `base`, `item`, `review` — verified to exist, `doorbell`, `sent`) itself; sends one `merge-request` to the merge owner and, when the distributor in `.fabrik/work/config.json` is a different agent, a second with `ack: no` to it (no config ⇒ one message); runs `mail.py who` for each recipient, records the names in `doorbell`, and prints one `SendMessage` line per name; with `--item` releases the caller's live claim on that item (`python3 scripts/work.py release <id>`, the CLI — `scripts/work.py:2937` `cmd_release`). The script carries an `# AFTER-EDIT:` header naming its test and `docs/reference/multi-agent-operating-model.md`. In the SAME ticket — so no sync ever ships a contract or a hook naming a script the fleet lacks (T05a names `request`, T04 names `merge`) — `merge_request.py` joins `CORE_SCRIPTS` in `scripts/fabrik_synced_manifest.py` (beside `mail.py`, `:51`; `CORE_SCRIPTS` is the Python list synced from `scripts/` — never `RUN_SCRIPTS`, the bash wrappers at `:79-91`) and the `scripts/(…)\.py$` alternation of the `governance-sync` `files:` filter (`.pre-commit-config.yaml:164`), so a later commit touching only the script distributes. The filter edit is made in scratch and written only in the staging step: an unstaged `.pre-commit-config.yaml` refuses every session's commit.

Depends: T01b
Parallel: ⛓️
Complexity: complex
Gate: python -m pytest tests/test_merge_request_send.py tests/test_synced_manifest.py -q
Docs: none (the model doc is T06's)

## Touches
- scripts/merge_request.py — PRIMARY PATH
- tests/test_merge_request_send.py
- scripts/fabrik_synced_manifest.py
- .pre-commit-config.yaml
- tests/test_synced_manifest.py

## Behavior Contract
- **Given** a worktree branch not pushed, or pushed but behind local `head`, or a remote that cannot be reached, **When** `merge_request.py request` runs, **Then** it exits non-zero with the reason and no mail is written (spec § Validation V1)
- **Given** a repo with no `MERGE OWNER:` row, or with no `docs/DECISIONS.md` at all, **When** `request` runs, **Then** it refuses and prints the `docs_updater.py --adopt` command; **Given** the owner resolver missing or failing, **Then** it refuses naming the resolver, never the adopt command (spec § The delta 8; § Validation V1)
- **Given** a repo whose distributor differs from the merge owner, **When** `request` runs, **Then** two messages are written — the owner's `ack: required`, the distributor's `ack: no` — each with the script-written body; with no `config.json`, or a distributor equal to the owner, exactly one (spec § Validation V2)
- **Given** `mail.py who` returning a live session for the owner, **When** `request` runs, **Then** the body's `doorbell` field names it and stdout carries one `SendMessage` line for it; with none, `doorbell: none` (spec § The delta 4)
- **Given** `--item W-xxxxxxxx` held by the caller, **When** `request` runs, **Then** the caller's claim on that item is released (spec § The delta 2)
- **Given** the synced manifest and the `governance-sync` filter, **When** they are read, **Then** `merge_request.py` is in `CORE_SCRIPTS` (not `RUN_SCRIPTS`) and the path `scripts/merge_request.py` matches the filter's regex (spec § Contract deltas; § The delta 5 (g))

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- scripts/mail.py
- scripts/decisions.py
- scripts/fabrik_synced_manifest.py
