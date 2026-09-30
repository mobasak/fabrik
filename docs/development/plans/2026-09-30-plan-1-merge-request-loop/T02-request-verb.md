# T02 — merge_request.py request: finishing work sends one request

## Scope
Implements spec § The delta 1, 2, 3 and 8. New `scripts/merge_request.py` with the `request [--item <id>]` verb, run inside a linked worktree: refuses unless the branch is pushed and `head` equals the remote tip (`git ls-remote`; an unreachable remote exits with the reason and sends nothing), and in a repo whose `decisions.py --merge-owner` exits 3 (UNDECLARED) refuses with the adopt command; writes the body (`branch`, `head`, `base`, `item`, `review` — verified to exist, `doorbell`, `sent`) itself; sends one `merge-request` to the merge owner and, when the distributor in `.fabrik/work/config.json` is a different agent, a second with `ack: no` to it (no config ⇒ one message); runs `mail.py who` for each recipient, records the names in `doorbell`, and prints one `SendMessage` line per name; with `--item` releases the caller's live claim on that item (`python3 scripts/work.py release <id>`, the CLI — `scripts/work.py:2937` `cmd_release`). The script carries an `# AFTER-EDIT:` header naming its test and `docs/reference/multi-agent-operating-model.md`.

Depends: T01b
Parallel: ⛓️
Complexity: complex
Gate: python -m pytest tests/test_merge_request_send.py -q
Docs: none (the model doc is T06's)

## Touches
- scripts/merge_request.py — PRIMARY PATH
- tests/test_merge_request_send.py

## Behavior Contract
- **Given** a worktree branch not pushed, or pushed but behind local `head`, or a remote that cannot be reached, **When** `merge_request.py request` runs, **Then** it exits non-zero with the reason and no mail is written (spec § Validation V1)
- **Given** a repo with no `MERGE OWNER:` row, **When** `request` runs, **Then** it refuses and prints the `docs_updater.py --adopt` command (spec § The delta 8; § Validation V1)
- **Given** a repo whose distributor differs from the merge owner, **When** `request` runs, **Then** two messages are written — the owner's `ack: required`, the distributor's `ack: no` — each with the script-written body; with no `config.json`, or a distributor equal to the owner, exactly one (spec § Validation V2)
- **Given** `mail.py who` returning a live session for the owner, **When** `request` runs, **Then** the body's `doorbell` field names it and stdout carries one `SendMessage` line for it; with none, `doorbell: none` (spec § The delta 4)
- **Given** `--item W-xxxxxxxx` held by the caller, **When** `request` runs, **Then** the caller's claim on that item is released (spec § The delta 2)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- scripts/mail.py
- scripts/decisions.py
