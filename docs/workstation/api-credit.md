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
turns the same keys into disposable WRITING agents. `api_write.py` takes the brief file a cloud run takes, runs it on a
key with file-editing tools in a throwaway clone, and the runner commits the edits and pushes `claude/<slug>`:

```
python3 scripts/api_write.py run --pick --model sonnet --out-dir <d> --batch batch.json [--jobs 3] [--budget 10] \
    [--max-turns 300] [--timeout 10800] [--force-new]
python3 scripts/api_write.py run --key sarp --model opus --out-dir <d> --slug lean-t15-fix --task-file brief.md \
    --base claude/lean-t15 --gate "python3 -m pytest -q tests/test_command_rules.py"
```

A batch is a JSON list of `{"slug", "task_file", "base", "gates"}` (`base` defaults to `master`, `gates` to none). An
entry with `cloud_dispatch.py drain`'s inline `task` is refused (write it to a file), and its `files` key is ignored.

**The safety lives in the runner, not in the permission rule** that lets a session start it (the operator's rule admits
`python3 scripts/api_write.py run *`; the classifier refused a session-started headless agent twice, first with blanket
Bash and `bypassPermissions`, then with a Bash allow-list — D-1248, D-1249). The design, D-1251:
- **The child has no git and no free shell.** `claude -p --safe-mode --restricted --permission-mode dontAsk` with Read,
  Edit, Write, Glob and Grep only; `--restricted` confines them to the clone and leaves writes to git and settings
  files to a person, which `dontAsk` denies. A job's gates add `Bash(<gate>)` for each gate string, matched exactly: a
  glob over a command's options admits the options, and the review that built this found three that reach outside the
  clone (pytest's `--basetemp` deletes the directory it names, git's `--output` writes any path, `git commit -F` reads
  any file). A gate is an exact command with no shell syntax; anything else is refused before spending.
- **The runner owns git, and the child has no repository.** Before spending it refuses when `origin` already has
  `claude/<slug>` (unless `--force-new`) or has no `<base>`, clones the main checkout under `<run root>/<run>/`
  (`API_WRITE_RUN_ROOT`, default `~/.cache/fabrik/api-write`; a root under any `.claude*` directory is refused before
  spending, because Claude Code denies every Write and Edit under `~/.claude` as a settings path — the first live runs,
  cloned under `~/.claude/state`, could only read and plan) with the git dir OUTSIDE the work tree
  (`gitdir/`, beyond `--restricted`'s reach; the work tree's `.git` pointer file is deleted), points `origin` at the
  main checkout's `origin` URL, fetches, and checks out `claude/<slug>` at `origin/<base>`. No worktree of the main
  checkout is made and its refs and index are only read; its objects are hardlinked into `gitdir/` (a full copy would
  be 1.7 GB per job), and git adds objects, never rewrites one. Every runner git call that acts on the clone names
  `--git-dir` and `--work-tree`, so nothing written in the work tree picks the repository or its config — the review
  that built this found a child-written `.git/commondir` redirecting config past a digest of `.git/config` — and the
  child's git discovery stops at the run directory (`GIT_CEILING_DIRECTORIES`), so a gate that needs a git repository
  finds none rather than climbing into one that encloses the state directory. The prompt is prefixed with a runner
  note saying so, and telling the child to skip the brief's BASE line, git, fetch, pip and push and to end with `SUBJECT: <commit
  subject>`.
- **After the child exits**, on a clean exit only: the runner refuses when the git dir's config changed or the child
  left any `.git` entry in the work tree, commits every edit as ONE commit (the child's `SUBJECT:` line, `Agent-*`
  trailers naming the run and key) with hooks and fsmonitor forced off, scans that commit's diff — binary files
  included, no diff drivers — for one of the three keys or an `sk-ant-` string, and pushes that same commit to
  `claude/<slug>` at the URL it captured (never forced). A child error, a timeout or a refusal pushes nothing.
- **Money.** The run reserves its budget in the same `api-credit.jsonl` through `api_credit.reserve` (one $200 cap per
  key across both lanes; the start row carries `lane: write` and the slug), runs after the same keyless pre-flight
  (which must report this child's tool set), and every outcome after the start row writes a settle row. The child runs
  in its own process group, so a timeout kills everything in it.
- **Env.** The child's env is `api_credit.child_env` minus every `GIT_*` name and the SSH agent, with the main
  checkout's `.venv/bin` first on PATH when it exists, so a gate's `python3 -m pytest` has the hub's dependencies
  without a pip install (an editable install from a hub clone would repoint the shared install box-wide).

Once the child has exited, with success or an error, the scrubbed result goes to `<out-dir>/<slug>.md` (printed on
stdout when that file cannot be written); a timeout writes none. `--jobs` (default 3) runs a batch in parallel; with
`--pick` each job reserves the key with the most room at its own start, so three jobs spread over the three keys. One
run is one commit, so a multi-ticket brief is split into one entry per ticket.

**What remains** (D-253): the cheapest abuse left is a gate, which runs code the child wrote (a test file, a rendered
source) as this user, outside every fence above (the git dir and the hardlinked objects included) — so gates come
from the brief's author, never from the child, and a job with no gates runs no code at all. Next, anything the child
writes inside the work tree ships to `claude/<slug>` (the secret scan knows only the three keys and the `sk-ant-`
pattern), which is why the branch is reviewed before any merge.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/api_credit.py`
- `scripts/api_write.py`
<!-- END related-scripts -->
