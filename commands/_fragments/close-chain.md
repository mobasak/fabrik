**The close is four calls, its inputs written first (D-363).** Write every input to a file BEFORE the chain,
each in its own call: the commit message with its Agent Provenance Trailers, each shared-ledger hunk, the
`--evidence` and `--feedback` text. Then: (1) the artifact's own check — {{ARTIFACT_CHECK}}; (2) the commit — the
artifact and any code by explicit pathspec FIRST, then the shared-append ledgers (`CHANGELOG.md`,
`docs/DECISIONS.md`, `INDEX.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/LESSONS_LEARNT.md`) through the
private-index recipe in ONE shell — the Doc Sync check reads only the STAGED diff, so a ledger committed first
reads as missing beside the code — then `git push` (never `--force`; a rejected push takes CLAUDE.md § EXIT's ladder); (3) `.venv/bin/python scripts/final_gate.py --check --json`; (4)
`python3 scripts/command_run.py done --command {{COMMAND}} --evidence "$(cat <evidence file>)" --feedback "$(cat <feedback file>)"` by name. A red call is fixed and THAT call re-run,
never the chain from the top.
