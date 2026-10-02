# T01a — mail.py: the merge-request kind and its two guards

## Scope
Implements spec § The delta 1 and § Contract deltas (the `mail.py` guards), plus residuals O34 and the blocked-reason rule (spec § U4, W-8a6a5644). In `scripts/mail.py`: `KINDS` (`scripts/mail.py:54`) gains `merge-request`, and `ACK_BY_KIND` (`scripts/mail.py:55`, the default `send` reads at `:973`) gains `"merge-request": "required"`. `claim` (`scripts/mail.py:1225`) and `ack` (`scripts/mail.py:1307`) of a `merge-request` refuse unless the caller resolves to the message's `agent:`; `ack --disposition done` of one requires `--merge-sha <sha>` that is an ancestor of base, carries the request id in its message, AND has the request's `head` as an ancestor (`git merge-base --is-ancestor <head> <sha>` — O34); `ack --disposition blocked` of one requires `--reason` naming the refused step. FIRST STEP of this ticket, before any code (spec U2): the orchestrator sends one `SendMessage` to a known-idle hub VS Code session and records in the ticket's evidence whether it started a turn; a "no" is a BLOCKED spec contradiction, not a silent continue.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/test_mail_merge_request.py tests/test_mail.py -q
Docs: none (fabrik-mail.md is T06's)

## Touches
- scripts/mail.py — PRIMARY PATH
- tests/test_mail_merge_request.py

## Behavior Contract
- **Given** a `mail.py send --kind merge-request` with no `--ack`, **When** the written header is read, **Then** `ack: required` (spec § The delta 1)
- **Given** a merge-request addressed to `alpha`, **When** a caller resolved as `beta` runs `claim` or `ack`, **Then** both refuse and the message stays where it was (spec § Validation V7b)
- **Given** a merge-request addressed to `alpha`, **When** `alpha` runs `ack --disposition done` without `--merge-sha`, with a SHA not an ancestor of base, with an empty commit naming the request, or with a SHA whose history lacks the request head, **Then** each is refused; with a real merge commit of the head it succeeds (spec § Validation V7b; W-8a6a5644 O34)
- **Given** a merge-request, **When** its addressee runs `ack --disposition blocked` without `--reason`, **Then** it is refused (W-8a6a5644)
- **Given** any other kind, **When** `claim`/`ack` run, **Then** their behaviour is unchanged (spec § Contract deltas)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- scripts/mail.py
- scripts/whoami_agent.py
