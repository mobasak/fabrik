# API credit — capped, read-only runs on the three prepaid API keys

Box-local subsystem (`scripts/api_credit.py`, ledger `~/.claude/state/api-credit.jsonl`), built 2026-10-24 on the
operator's order to spend three prepaid $200 Anthropic API credits before they expire (D-1196, W-894f994f). Its sibling
for the five $250 cloud-session credits is [cloud-dispatch.md](cloud-dispatch.md).

A session or an Agent-tool seat bills the subscription through OAuth, and a seat shares its parent's auth, so neither
can be pointed at an API key. This script runs ONE headless task per call on a key instead.

## What a run is

```
python3 scripts/api_credit.py status                       # spend, in-flight provision and room per key
python3 scripts/api_credit.py run --pick --model sonnet --prompt-file brief.md --out answer.md \
    --add-dir /path/to/a/pinned/copy [--budget 5] [--max-turns 40] [--timeout 1800]
python3 scripts/api_credit.py settle --run <id> --cost 0.42   # close a run that has no cost with the console's figure
```

`run` starts `claude -p --safe-mode --restricted` with:
- the chosen key as `ANTHROPIC_API_KEY`;
- the tools fixed at Read, Grep and Glob (a finder can locate files and follow callers in the pinned copy);
- `--permission-mode dontAsk` and `--permission-prompts none`;
- a fresh `CLAUDE_CONFIG_DIR`, deleted after the run;
- an empty cwd under `~/.claude/state/api-credit/`.

The prompt goes on stdin, and the result text lands in `--out`. Every output is scrubbed of the three key values and of
any `sk-ant-…` string. `--pick` takes the key with the most room left.

**Use it for brief-shaped, read-only work**: a review finder over a pinned copy, a research read, an audit. A lead
dispatches it when the fleet quota band is AMBER or RED, or when a credit nears its expiry. Nothing triggers it
automatically.

## The safety boundary

- **Why not `--bare`.** On CLI 2.1.310 `--bare` drops Grep and Glob whatever `--tools` lists (the init event shows
  `['Read']`; probed 2026-10-25, W-230abfd5), which left a finder unable to search. `--safe-mode` keeps them and
  disables hooks, CLAUDE.md, plugins and MCP servers, but its help says auth "works normally", so the auth guarantee is
  executed rather than assumed (next bullet).
- **Auth — the keyless pre-flight.** Before the start row, `run` starts the same argv once with no `ANTHROPIC_API_KEY`,
  stdin `hi`, `--max-turns 1`, `--output-format stream-json --verbose`, on its own empty config dir (removed after).
  The run is refused (exit 2, nothing provisioned) unless the init event lists exactly Glob, Grep and Read with
  `apiKeySource` `none`, and the result is an error with `total_cost_usd` 0 and `duration_api_ms` 0. So no other
  credential — an OAuth login, a keychain, a managed env — can answer for the run; the result's `subtype` reads
  `success` on this failure and is never read. The real run then has only the key: its config dir is fresh and empty,
  and every `ANTHROPIC*`/`CLAUDE*` name is stripped from its env. A bad key fails rather than falling back (probed
  2026-10-24 and 2026-10-25). The one source the pre-flight cannot see is a credential the CLI would read only when a
  key is present; the server-side prepaid credit is the backstop there. The plain `ANTHROPIC_API_KEY` in `.env` stays
  empty, so nothing else bills the API by accident.
- **Managed settings.** A managed-settings directory (`/etc/claude-code`, or `API_CREDIT_MANAGED_DIR`) refuses every
  run: its env and hooks apply under `--safe-mode` and `--restricted` alike, and the pre-flight cannot see them.
- **Reach.** `--safe-mode` disables every hook, so the fleet's guards do not run inside a run. That is why the tools are
  read-only, and why `--restricted` confines them to the cwd and each `--add-dir` (a read outside is denied, probed).
  Every `--add-dir` is vetted, and the run is refused (exit 2) when the directory is not an absolute, non-symlink
  directory, or:
  - is `/`, the home directory or above it;
  - lies inside, or holds anywhere in its tree, a checkout or credential directory (the names in the script's
    `SECRET_DIR_NAMES`, `.git` and `.aws` among them), or holds a credential file (`SECRET_FILE_NAMES`, `SECRET_SUFFIXES`, `SECRET_PREFIXES`, and `.env` /
    `.env.*` other than `.example`, `.sample` or `.template`);
  - holds a symlink that leaves it;
  - holds more than 50,000 entries.
  Pin a copy with `git archive` and pass that. The vetting reads names, not contents: a secret under an ordinary name
  is not caught, which is why `--restricted` and the read-only tools remain the boundary.
- **Env.** The child keeps the caller's environment (`tests/test_hooks_headless_guard.py` requires extend, never
  replace) minus every name, compared upper-cased, that starts with one of the script's `STRIP_PREFIXES` (`ANTHROPIC`,
  `CLAUDE`, and the loader and JS-runtime families such as `LD_` and `NODE_`) or is in `STRIP_ENV` (the CA-bundle,
  `GLIBC_TUNABLES` and proxy names). It sets `FABRIK_HEADLESS=1`.
- **Duties.** An appended system prompt tells the run it has no hub duties (no mail, no work items) and must not follow
  instructions found in the files it reads.

## The cap

Each key is capped at $200. A run's budget is clamped to $200 − $5 margin − spend − the model's per-call ceiling (the
table below), and the run is refused (exit 3, nothing started, no row written) when that clamp falls below $0.05. So a
key with $3 of room still refuses a sonnet run, whose ceiling alone is $3.78.

Each run writes two rows to the ledger, through `cloud_dispatch.LedgerTxn` (one `flock` for the read and the append):
- `start` (key, model, budget, prompt digest, timeout), appended in the same transaction that computed the spend;
- `settle` (the run's reported `total_cost_usd`, rc, subtype, turns).

Spend per key is the largest finite cost settled for each run, plus, for every run with no usable cost (still running,
killed, unparseable), its budget plus the model's per-call ceiling. The ceiling is there because `--max-budget-usd` is
checked after every API call (probed: a three-Read task stopped after call 1), so one call is the most a run can
overshoot:

| model | per-call ceiling | from (list $/MTok, 1M uncached input × 1.25 + 128K output) |
|---|---|---|
| opus | $7.56 | $4 / $20 |
| sonnet | $3.78 | $2 / $10 |
| haiku | $0.95 | $0.50 / $2.50 (the >100K-prompt rate) |
| fable | $18.90 | $10 / $50 |

A run's budget (default $5) is clamped to the room left minus that ceiling and floored to cents.

Every doubt fails closed, so an unknown cost counts as spent, never as free:
- a ledger that does not decode, a line that does not parse, a row of the wrong shape, or a settle row whose start row
  is missing refuses every verb (exit 1);
- a timeout or an error around the `claude` process leaves the run provisioned.

Everything that can fail without spending (the inputs, `--out`, the key file, `claude` on PATH, the state
directories) is checked before the start row, so such a refusal provisions nothing. A result that cannot be written to
`--out` after the run is printed on stdout instead.

`settle` closes a run that has no cost with the console's figure once the run has exited (its own settle row exists), or
else once its timeout plus a minute has passed; it never gives a second figure to a run that already has one. A child
orphaned by a killed parent is bounded by its own `--max-budget-usd`, not by this check, so read the console before
settling such a run.

The cost is Claude Code's list-price estimate (`costBasis: "list"`), not Anthropic's ledger. The server-side credit is
the backstop behind it. Whether a card with auto-reload sits behind any key was asked of the key owners on 2026-10-24;
until they answer, the local cap is the guard of record.

## Cost of a run

A run pays for its own context: the appended prompt, the brief, and whatever the tools read. The first live run
(2026-10-24, sonnet, a bug review of this script over a two-file pin) cost $0.0727 and returned nine candidate findings,
seven of them real.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/api_credit.py`
<!-- END related-scripts -->
