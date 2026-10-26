# API credit — capped runs on the three prepaid API keys (read-only, and the write lane)

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
  differing only in stdin `hi`, `--max-turns 1`, `--max-budget-usd 0.05` and `--output-format stream-json --verbose`,
  on its own empty config dir (removed after), within `API_CREDIT_PREFLIGHT_TIMEOUT` seconds (60). The run is refused
  (exit 2, nothing provisioned) unless every init event lists exactly Glob, Grep and Read with `apiKeySource` `none`,
  and every result event is an error with `total_cost_usd` 0 and `duration_api_ms` 0. So no other credential — an
  OAuth login, a keychain — can answer for the run; the result's `subtype` reads `success` on this failure and is
  never read. Should some credential answer, the pre-flight's one turn is billed to it, outside this ledger, before the
  refusal. The real run then has only the key: its config dir is fresh and empty, and every inherited
  `ANTHROPIC*`/`CLAUDE*` name is stripped from its env but `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` (forced to `1`)
  before the key and the config dir are set. A bad key fails rather than falling back (probed 2026-10-24 and
  2026-10-25). The one source the pre-flight cannot see is a credential the CLI would read only when a key is present;
  the server-side prepaid credit is the backstop there. The plain `ANTHROPIC_API_KEY` in `.env` stays empty, so nothing
  else bills the API by accident.
- **Managed settings.** A managed-settings directory (`/etc/claude-code`, or `API_CREDIT_MANAGED_DIR`) refuses every
  run before anything spawns: its env and hooks apply under `--safe-mode` and `--restricted` alike, and a managed env
  (a base URL, say) need not change what a keyless probe reports.
- **Reach.** `--safe-mode` disables the user, project and plugin hooks (managed hooks would still run, which is why
  managed settings refuse the run), so the fleet's guards do not run inside a run. That is why the tools are
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

Everything that can fail without spending (the inputs, `--out`, the key file, `claude` on PATH, managed settings, the
state directories, the keyless pre-flight) is checked before the start row, so such a refusal provisions nothing. A result that cannot be written to
`--out` after the run is printed on stdout instead.

`settle` closes a run that has no cost with the console's figure once the run has exited (the settle row its own `run` writes after the child returns or times out exists; a spawn
error's row does not count), or
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

## The write lane (`scripts/api_write.py`)

D-1247 (operator, 2026-10-26: "why arent we utilizing the api and cloud credits as like they are disposable agents?")
turns the same keys into disposable WRITING agents. `api_write.py` takes the brief file a cloud run takes
(`cloud_dispatch.py dispatch --task-file`, or a `drain` batch of `{"slug", "task_file"}`), runs it on a key with write
tools, and pushes the run's own `claude/<slug>` branch:

```
python3 scripts/api_write.py run --pick --model sonnet --out-dir <d> --batch batch.json [--jobs 3] [--budget 10] \
    [--max-turns 300] [--timeout 3600] [--force-new]
python3 scripts/api_write.py run --key sarp --model opus --out-dir <d> --slug lean-t15-fix --task-file brief.md
```

Per run, before anything is spent:
- it refuses when `origin` already has `claude/<slug>`, unless `--force-new`;
- it makes a `git clone --shared` of the main checkout under `~/.claude/state/api-write/<run>/`, so the main checkout's
  worktrees, refs and index are never touched, and points the clone's `origin` at the main checkout's own `origin`;
- it installs a `pre-push` hook (through the clone's `core.hooksPath`) that refuses every ref but
  `refs/heads/claude/<slug>`;
- it runs the keyless pre-flight above on this lane's argv, which must report the write tools.

Then it reserves the budget in the same `api-credit.jsonl` through `api_credit.reserve` (one $200 cap per key across both
lanes; the start row carries `lane: write` and the slug), and runs `claude -p --safe-mode --restricted` in the clone,
in its own process group so a timeout kills everything it started. **Least privilege** (the coordinator's redesign after
the classifier refused a `bypassPermissions` child, "Create Unsafe Agents"): `--permission-mode dontAsk` with the
script's `ALLOWED` list, so anything unlisted is denied — Read, Edit, Write, Glob, Grep, and Bash only for local git on
the slug branch (`git checkout -B claude/*`, status, diff, log, show, add, rm, mv, commit) and the briefs' two gates
(`python3 -m pytest *`, `python3 commands/assemble_commands.py --check`). No fetch, push or pip: the runner fetched
`origin` already and pushes the branch itself, and an editable install from a hub clone would repoint the shared
install box-wide, so the child's PATH starts with the main checkout's venv instead. The SSH agent is dropped from its
env. `--restricted` confines the file tools to the clone. `--safe-mode` keeps the hub's hooks out of the child, the
quota and Stop hooks included. After the child exits the runner settles the cost, pushes `claude/<slug>` (never
forced), writes the scrubbed result to `<out-dir>/<slug>.md` and deletes the run directory. `--jobs` (default 3) runs a
batch in parallel; with `--pick` each job reserves the key with the most room at its own start, so three jobs spread
over the three keys.

**The boundary that remains.** `python3 -m pytest` runs whatever test code the child writes, as this user, so a
determined child can still act outside its clone through a test file. That is named in the script rather than guarded;
the ledger names every run's slug and key, and the pushed branch is reviewed before any merge.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/api_credit.py`
- `scripts/api_write.py`
<!-- END related-scripts -->
