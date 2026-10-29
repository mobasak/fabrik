# Cloud audit — span-readers (read-only)

**Class:** every reader of markdown inline code spans or fences outside `blank_code_spans` that does not follow
CommonMark's backslash-escape and backtick-run rules. The module is `scripts/enforcement/_fences.py` (the task text
says `scripts/_fences.py`; that path does not exist). The reference model is `blank_code_spans` at
`scripts/enforcement/_fences.py:306`.

**Date:** 2026-10-29. **Checkout:** branch `claude/audit-span-readers`, cut from the session's clone.

## Population searched

- **Tracked files:** 9,187 (`git ls-files | wc -l`).
- **Code files in scope:** 1,369 tracked `*.py`, `*.sh`, `*.js` and `*.ts` files.
  - 1,202 are `.py`: 499 outside `tests/`, 703 under `tests/` or other test directories.
  - The rest are 167 `.sh`, `.js` and `.ts` files.
- **Excluded by design:**
  - Tests, because they hold oracles and fixtures rather than readers. They were scanned and read where they name a reader.
  - `.claude/worktrees/*`, which are stale copies.
  - `docs/**` markdown, which holds no code.
- **Not span readers, so out of the class and not tabulated:**
  - Shell-command backtick parsers: `.claude/hooks/seat_guard.py:230-248,388`, `.claude/hooks/quota_stop.py:158,611`, `libs/subagents/tools.py:64`.
  - Emitters that write backticks: every `.js` and `.sh` hit. `fabrik-review-loop.js:230-277` builds prompt strings, and the `.sh` hits are heredoc and echo text.
  - `strip("`")` and `lstrip` cell-edge cleanups on a single token:
    - `check_plan_tickets.py:395,624,855,1096`
    - `work.py:1437`
    - `check_stage_artifacts.py:295,345`
    - `libs/subagents/select.py:279,355,362,375`
  - Key-line regexes that tolerate decoration ticks (`check_stage_artifacts.py:269-312`), and `_ESCAPED_RE` link-destination unescaping (`check_doc_links.py:112`, `check_doc_index.py:149`).

**Commands used** (scratch scripts are under the session scratchpad):

1. `git ls-files '*.py' '*.sh' '*.js' '*.ts'` gave the population list.
2. An AST scan (`ast.walk`) over every `.py` file listed every `re.*` and `str.*` call, and every `re.compile` assignment, whose literal argument holds a backtick. It returned 466 call sites in 80+ files. 1 file (`src/fabrik/drivers/postgres.py`) failed to parse; its backtick hits are SQL, not markdown. The tests-only sites were skipped.
3. Text greps for hand-rolled scanners that the AST pass cannot see:
   - `grep -nE "(=|\(|,|in|\[)\s*[rbuf]*(\"\`+\"|'\`+')"` over the non-test `.py` files found `s[i] != "`"` loops.
   - `grep -nE '"```|```"'` over the same files.
   - `grep -rn -E 'chr\(96\)|\\x60|\\u0060'` returned 0 hits.
4. I read each surrounding function. I ran concrete inputs through the readers with `python3 -c`-style probe scripts (read-only import of repo modules) against `_fences.blank_code_spans`.

**Search bound:** the AST scan sees only literal arguments. A backtick built at runtime or passed through a variable would be missed. Step 3's `chr(96)` grep covers the common build-time spellings. Treat the table as complete for literal readers only.

Instances are grouped by shared implementation, so one row can name several lines. Row 8 is one regex copied three times. Rows 1 to 3 are three ports of `decisions.py::_code_span_ranges`.

## Findings

| # | path:line | verdict | why (one line) | suggested fix (one line) |
|---|---|---|---|---|
| 1 | `scripts/decisions.py:112` (`_code_span_ranges`, used by `_escape_cell:154` and `_rows:175`) | REAL | No backslash rule. `\`a \| b\` c` is read as a span from the escaped tick, but `blank_code_spans` finds none, so the escape logic and the span ranges disagree and `\|` handling changes. | Skip an escaped first backtick (odd run of `\` before it), or call `_fences.blank_code_spans`. |
| 2 | `.claude/hooks/session_orient.py:250` | REAL | A verbatim port of row 1 for `_cells`; same input fails the same way. | Share the fix with row 1. |
| 3 | `scripts/docs_updater.py:1613` (`_ledger_code_spans`, used by `_ledger_cells:1643`) | REAL | A third port of row 1; same input fails the same way. | Share the fix with row 1. |
| 4 | `commands/command_rules.py:568-573` (`_CODE`, `_mask_code`) | REAL | `\`a\` b \`c\`` masks from the escaped tick (`'\\xxx b xxx'`), where the reference finds `` `a` b `` as one span. Also no cross-line wrap. | Escape-aware opener, or delegate to `blank_code_spans`. |
| 5 | `commands/command_rules.py:51-53` (`_outside_code`) and `:70-76` (`_split_prose`) | REAL | Splits and toggles on every single backtick (`s.split("`")`, `in_code = not in_code`). A double-backtick span containing a tick flips parity: `` ``a`b`` Never `x` `` marks `Never` as code and the real span as prose. | Pair by backtick run, as `_CODE` tries to. |
| 6 | `commands/command_rules.py:122,134,289` (`s.startswith("```")` fence toggles in `_units:103` and the line walk near `:289`) | REAL | Toggle without run length or `~~~`: a ```` ```` ```` fence that contains a ```` ``` ```` line is closed early. | Track `(char, len)` as `check_command_corpus._fence_step` does. |
| 7 | `scripts/command_run.py:5323`, `scripts/mail.py:606`, `scripts/enforcement/check_review_coverage.py:3225` (one regex, three copies, held equal by `tests/test_code_span_readers.py`) | REAL | No backslash rule, no line wrap, and a run cap of 8. `\`a\` b \`c\`` returns spans at index 2 and 8 (`a`, `c`); the reference blanks 3, 5 and 7. A 9-tick run stays literal where CommonMark pairs it. | Skip an escaped first tick, or use `blank_code_spans`. Fix the three copies together. |
| 8 | `scripts/enforcement/check_doc_sync.py:78-100` (`_strip_span_runs`) and `:391` (`line.count("`") % 2` guard) | REAL | The escape is not read. `\`todo\` x \`y\`` deletes `` `todo\` x ` `` (result `'\\ x '`), where the reference leaves `todo` as bare text. A bare `TODO` is hidden, which fails open. | Add the escape rule before pairing; keep the parity guard. |
| 9 | `scripts/enforcement/check_convergence.py:173-215` (`_mask_spans`) | REAL | Same escape gap on the primary view. `a \`b\` c \`d\`` masks `b` and `d` where the reference masks from the second tick. The D-1131 union with `_mask_spans_wrapped` (`:218`) softens it, since a refusal reader refuses when either model does. | Escape-aware opener. |
| 10 | `scripts/enforcement/check_convergence.py:1248-1262` (`_inline_code_spans`) | REAL | Pairs every tick left to right with no run rule. ```` ``a`b`` reviewed `x` ```` gives ranges (0,1), (3,5), (6,17), so `reviewed` lies inside a "span" where the reference puts the first span at 0-8 and leaves `reviewed` bare. The claim is exempted wrongly. | Reuse `blank_code_spans` offsets. |
| 11 | `scripts/enforcement/check_governance_tables.py:84` (`_SPAN`) and `:299-322` (`_piped_spans`) | REAL | The run is not bounded (`(`+)(.+?)\1`), and an escaped backslash before a tick is read as an escaped tick. The row `\\`x\|y`` (escaped backslash, then a live span with `\|`) returns `[]`; the reference sees the span. The gate misses a real finding. | Run-bounded regex; the `\\`` replace must count backslash parity. |
| 12 | `scripts/enforcement/check_command_corpus.py:1179` (`head.count("`") % 2`), `:1207` (`nxt.split("`", 1)`) | REAL | A line-parity read with no escape or run rule decides whether a close sits inside a span. `\`/fabrik-x --feedback\`` or a span with a double-tick pair changes the parity. | Use run-aware span ranges for the line. |
| 13 | `scripts/enforcement/plan_appetite.py:112-119` via `_fences.py:strip_marker_fences:210` | REAL | A closer is any run of 3 or more, regardless of the opener's length: ```` ```` ```` / ```` ``` ```` / `Appetite: 60` / ```` ```` ```` strips only to the inner ``` and leaves `\nAppetite: 60\n`. The quoted `Appetite:` is graded as live. | Closer length must be at least the opener's; the oracle test pins the old behaviour, so change both. |
| 14 | `scripts/enforcement/_fences.py:382` (`fence_toggle`), copied at `scripts/enforcement/check_doc_links.py:283` | REAL | A bare toggle on any line starting with three ticks: a ```` ```` ```` fence holding ```` ``` ```` lines flips state three times. Documented as the stated cost (W-2725ed54). | CommonMark fence model, tracked in W-2725ed54. |
| 15 | `scripts/enforcement/_fences.py:52` (`fence_blocks`), `:147` (`fence_block_bodies`), `:232` (`strip_three_marker_fences`), `:40` (`_INLINE`); consumers `check_convergence.py:541,576,583,1449` and `check_phase_tests.py:110` | REAL | They deliberately keep the legacy regex semantics. The closer must be exactly `k` ticks, so a ```` ``` ```` opener with a ```` ```` ```` closer is not closed; `fence_block_bodies` pairs the first ```` ``` ```` after the opener line; the inline form is triple-tick only. | Move to the CommonMark model in one place (W-2725ed54); the oracle tests then change with it. |
| 16 | `scripts/enforcement/check_plan_lock_release.py:101-135` (`_strip_fences`) | REAL | Own copy (import allowlist), exact-run closer: ```` ``` ```` opener with ```` ```` ```` closer is unclosed and swallows to EOF. | Allow a closer of at least the opener's length. |
| 17 | `.claude/hooks/final_gate_stop.py:3208` (`_CODE_SPAN_RE`), `:3302` / `:3631-3640` (`_FENCE_RE` toggles in `_fence_spans`), `:3666` (`before.count("`") % 2`), `:3624` (single-tick window rule) | REAL | Single-tick pairing and any-run fence toggle: ```` ``a`b`` ```` and ```` ```` ```` fences change what counts as quoted or fenced, so a `NEXT:` offer or decision block is read as quoted or fenced when it is not. | Run-aware spans and a length-tracking fence state. |
| 18 | `scripts/thread_anchor.py:92-111` (`_FENCE_LINE_RE`, `_next_values`) | REAL | Any ```` ``` ```` or `~~~` line toggles; a 4-tick fence holding a ```` ``` ```` line exposes a quoted `NEXT:` as the live footer. | Track fence char and length. |
| 19 | `scripts/enforcement/check_citations_resolve.py:61-72` (`_strip_fences`) | REAL | Any line starting with three ticks toggles (no `~~~`, no length). | Track fence char and length. |
| 20 | `scripts/mail.py:1237` (`stripped.startswith("```")` toggle in the authored-line walk) | REAL | Same toggle; a nested or longer fence in a mail body flips authored and quoted lines. | Track fence char and length. |
| 21 | `scripts/docs_updater.py:1538,2375,2474` (`in_fence = not in_fence`) | REAL | Same any-run toggle (and `~~~`) in the table, heading and TOC walks. `_blank_code_fences:1074` in the same file is CommonMark-correct. | Reuse the `_blank_code_fences` state machine. |
| 22 | `scripts/enforcement/check_changelog.py:190` and `scripts/enforcement/check_doc_sync.py:360` (``re.sub(r"```.+?```", "", …, re.DOTALL)``) | REAL | Pairs the first ```` ``` ```` with the next ```` ``` ```` anywhere, so a 4-tick fence holding ```` ``` ```` lines leaves residue (and a stray `TODO` line) in the scanned text. | Strip with `_fences.strip`. |
| 23 | `libs/subagents/select.py:326` (vendored; `startswith("```")` toggle) | REAL | Same any-run toggle on a routing table; `libs/subagents/` is off-limits to the hub (D-137). | Mail fabrik-lib; do not edit here. |
| 24 | `scripts/sysadmin/liveness_audit.py:2179,2254` (`_FENCE = ^\s*```` ```)` | REAL | Toggle without length or tilde, over docs that quote unit and cron blocks; a nested fence flips `in_fence` and the claim scan. `_UNIT_TOKEN:2181` and `_HOOK_TOKEN:2189` are single-tick token greps. | Track fence char and length. |
| 25 | `scripts/work.py:2280` (`_FENCE_OPEN_RE`, used `:2581,:2961`) | REAL | The opener has no info-string rule: ```` ```code``` ```` plus text opens a fence. The closer test at `:2957` is length-aware. | Reject a backtick opener whose info holds a tick. |
| 26 | `scripts/doc_reconcile.py:172` (``re.findall(r"`([^`]+)`", …)``) | UNSURE | Single-tick extraction (no escape or run rule) harvests identifiers the patch "introduces". A false token could cause a false unreal-identifier finding. Settle by reading `:219-260` for whether a token fails the run. | Use `blank_code_spans` offsets or the run-aware regex. |
| 27 | `src/fabrik/preplan.py:272` (``r"```yaml\s*\n(.*?)\n```"``) | UNSURE | The first ```` ```yaml ```` block read from the preplan doc, closed by any ```` ``` ````. Settle by checking whether preplan templates ever carry a longer wrapper fence. | `_fences.fence_blocks`. |
| 28 | `scripts/archived/kilo_docs_enforcer.py:661,664,667,1793` | SAFE | Archived, in `RETIRED_CORE_SCRIPTS` (`scripts/fabrik_synced_manifest.py:76`), not imported anywhere outside `scripts/archived/`. | none (retired). |
| 29 | `scripts/enforcement/check_command_corpus.py:832-850` (`_fence_step`) and `scripts/enforcement/check_review_hygiene.py:198` | SAFE | CommonMark fence state (char, length, info-string tick rule). Residual: `line.lstrip()` accepts 4+ spaces of indent, which is an indentation rule, not a backtick or escape one. | none. |
| 30 | `scripts/enforcement/check_review_coverage.py:1228,1269-1280` (`_block_regions`) | SAFE | Same CommonMark fence model, 0 to 3 spaces of indent. | none. |
| 31 | `scripts/enforcement/check_data_contract_legend.py:50,143-150` | SAFE | Fence state compares char and length. | none. |
| 32 | `scripts/docs_updater.py:1074-1100` (`_blank_code_fences`) | SAFE | Full CommonMark opener, info-string and closer rules. | none. |
| 33 | `scripts/enforcement/check_doc_sync.py:380-392` (the `% 2` parity guard) | SAFE | A deliberate fail-closed guard, documented in the code (odd count leaves the line intact). The span deletion it guards is row 8. | none. |
| 34 | `libs/competitor_intel/synth.py:125`, `libs/deep_research/engine.py:237`, `templates/i18n-kit/scripts/validate_i18n.py:291` | SAFE | Heuristic fence stripping on LLM replies, documented as best-effort. The input is model output, not authored markdown. | none. |
| 35 | `src/fabrik/preplan.py:250,256,321` | SAFE | Single-tick tokens are checked against `_VALID_SCAFFOLD_TYPES` (`:259-262`), so a mis-read span cannot select an invalid type. | none. |
| 36 | `scripts/review_rubric.py:149` (`_GREPPABLE`) | SAFE | Single-tick extraction for an advisory literal tail (`_literals`, capped at 160). It never decides a verdict. | none. |
| 37 | `scripts/enforcement/check_env_contract.py:25` (`CONFIG_DOC_PATTERN`) | SAFE | A narrow `` `[A-Z][A-Z0-9_]+` `` token read that can only widen the documented set. | none. |
| 38 | `scripts/work.py:2303,2507` (`_STATUS_AFTER_PIPE_RE`, `_table_cell_owner`) | SAFE | Decoration and cell-edge handling, validated by `[a-z0-9-]{1,32}` before use. | none. |
| 39 | `scripts/enforcement/_fences.py:306` (`blank_code_spans`) and its consumers `status_candidates:410`, `blank_code_examples:390` | SAFE | The reference model itself. | none. |

## Fix batches

- **Batch A: duplicated span ranges** (rows 1 to 3).
  - Files: `scripts/decisions.py`, `.claude/hooks/session_orient.py`, `scripts/docs_updater.py`, plus `tests/test_session_orient_hook.py` for the three-reader agreement test.
  - Size: about 25 lines and 3 tests.
  - Note: `docs_updater` and `session_orient` are fleet-synced, so this ships to about 46 repos and needs the full `/fabrik-review`.
- **Batch B: shared `_CODE_SPAN` regex** (row 7).
  - Files: `scripts/command_run.py`, `scripts/mail.py`, `scripts/enforcement/check_review_coverage.py`, `tests/test_code_span_readers.py`.
  - Size: about 15 lines.
  - Note: all three copies move together; the equality test already pins them.
- **Batch C: line-parity readers** (rows 4, 5, 8 to 12).
  - Files: `commands/command_rules.py`, `scripts/enforcement/check_doc_sync.py`, `check_convergence.py`, `check_governance_tables.py`, `check_command_corpus.py`, and each one's test file.
  - Size: about 60 lines.
  - Note: all synced paths; the largest batch.
- **Batch D: fence-toggle family** (rows 6, 13 to 25).
  - This is W-2725ed54's scope.
  - Files: `scripts/enforcement/_fences.py` (add one shared `fence_step`), then the callers:
    - `.claude/hooks/final_gate_stop.py`
    - `scripts/thread_anchor.py`
    - `scripts/mail.py`
    - `scripts/enforcement/check_citations_resolve.py`
    - `scripts/enforcement/plan_appetite.py`
    - `scripts/enforcement/check_plan_lock_release.py`
    - `scripts/enforcement/check_changelog.py`
    - `scripts/enforcement/check_doc_links.py`
    - `scripts/docs_updater.py`
    - `scripts/sysadmin/liveness_audit.py`
    - `scripts/work.py`
    - `commands/command_rules.py`
  - Size: about 120 lines plus oracle-test changes in `tests/enforcement/test_fences.py`.
  - Note: the oracle tests pin the old match set, so they change with the code.
- **Batch E: vendored copy** (row 23). Mail fabrik-lib; no hub edit.

## Counts

39 found, 25 real, 12 safe, 2 unsure (N found, R real, S safe, U unsure).
