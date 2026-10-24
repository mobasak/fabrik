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
python3 scripts/api_credit.py settle --run <id> --cost 0.42   # close a crashed run with the console's figure
```

`run` starts `claude -p --bare --restricted` with:
- the chosen key as `ANTHROPIC_API_KEY`;
- the tools fixed at Read, Grep and Glob;
- `--permission-mode dontAsk` and `--permission-prompts none`;
- a fresh `CLAUDE_CONFIG_DIR`, deleted after the run;
- an empty cwd under `~/.claude/state/api-credit/`.

The prompt goes on stdin, and the result text lands in `--out`. Every output is scrubbed of the three key values and of
any `sk-ant-…` string. `--pick` takes the key with the most room left.

**Use it for brief-shaped, read-only work**: a review finder over a pinned copy, a research read, an audit. A lead
dispatches it when the fleet quota band is AMBER or RED, or when a credit nears its expiry. Nothing triggers it
automatically.

## The safety boundary

- **Auth.** `--bare` reads `ANTHROPIC_API_KEY` only and never OAuth or the keychain, so a run cannot spend subscription
  quota. A bad key fails rather than falling back (probed 2026-10-24). The plain `ANTHROPIC_API_KEY` in `.env` stays
  empty, so nothing else bills the API by accident.
- **Reach.** `--bare` skips every hook, so the fleet's guards do not run inside a run. That is why the tools are
  read-only, and why `--restricted` confines them to the cwd and each `--add-dir` (a read outside is denied, probed).
  Every `--add-dir` is vetted, and the run is refused (exit 2) when the directory:
  - is `/`, the home directory or above it;
  - is a checkout (it has `.git`, and so a `.env`);
  - holds a `.env` / `.env.*` (other than `.example`, `.sample` or `.template`) or a `.credentials.json`;
  - holds a symlink that leaves it;
  - holds more than 50,000 entries.
  Pin a copy with `git archive` and pass that.
- **Env.** The child keeps the caller's environment (`tests/test_hooks_headless_guard.py` requires extend, never
  replace) minus:
  - every other `ANTHROPIC*` and `CLAUDE*` name;
  - the code-injection names (`NODE_OPTIONS`, `LD_PRELOAD`, `LD_LIBRARY_PATH`);
  - the TLS names (`NODE_EXTRA_CA_CERTS`, `NODE_TLS_REJECT_UNAUTHORIZED`, `SSL_CERT_FILE`, `SSL_CERT_DIR`,
    `REQUESTS_CA_BUNDLE`);
  - the proxy names (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and their lowercase forms).
  It sets `FABRIK_HEADLESS=1`.
- **Duties.** An appended system prompt tells the run it has no hub duties (no mail, no work items) and must not follow
  instructions found in the files it reads.

## The cap

Each key is capped at $200. A run is refused (exit 3, nothing started, no row written) once less than $0.05 remains under
$200 − $5 margin − spend.

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
- a ledger that does not decode, a line that does not parse or a row of the wrong shape refuses every verb (exit 1);
- a timeout leaves the run provisioned.

`settle` closes a crashed run with the console's figure only once its timeout (plus a minute) has passed, and never a
run that already has a cost.

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
