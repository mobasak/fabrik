**The close is four calls, its inputs written first (D-363) — the default shape, and this command's own close text wins wherever it names something else** (a different order, a `blocked` or `handoff` exit, an operator gate, a pause before execution, a nested run whose caller closes, a ledger row committed separately). It runs BEFORE the response's closing seven-line block (CLAUDE.md § FINAL OUTPUT), whose `FEEDBACK:` line the chain's last call prints — and so before any output section of the command's own that reports the run. Write every input to a file BEFORE the chain,
each in its own call: the commit message with its Agent Provenance Trailers, each shared-ledger hunk, the
`--evidence` and `--feedback` text. Then: (1) the artifact's own check — {{ARTIFACT_CHECK}}; (2) the commit — the
artifact and any code by explicit pathspec FIRST, then the shared-append ledgers (`CHANGELOG.md`,
`docs/DECISIONS.md`, `INDEX.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/LESSONS_LEARNT.md`) through the
private-index recipe in ONE shell — the Doc Sync check reads only the STAGED diff, so a ledger committed first
reads as missing beside the code — then `git push` (never `--force`; a rejected push takes CLAUDE.md § EXIT's ladder); (3) `python scripts/final_gate.py --check --json` (the hub runs it under `.venv/bin/python`); (4) the close this
command's own text names for how the run ended — on the contract met, `python3 scripts/command_run.py done --command {{COMMAND}} --evidence "$(cat <evidence file>)" --feedback "$(cat <feedback file>)"` by name. A red call is fixed and THAT call re-run,
never the chain from the top. A run that wrote nothing tracked commits nothing at (2) and still runs (3) and (4).
