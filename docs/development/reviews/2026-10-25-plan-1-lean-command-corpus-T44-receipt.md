# T44 receipt — /fabrik-reverse-engineer (light form, D-1240 re-run)

Start commit: origin/claude/lean-t44-base (master + the hub's baseline commit; the git SHA is the runner's, no git here).
Baseline: `commands/_rules/fabrik-reverse-engineer.baseline.txt`, sha256 `7b0774d55e866ceb9b5f9fb53d5964261bd1fc48805ec4026bdf28b028002423` (45 units, 1813 words counting the heading prefix of each key).

## Size

Own-text words before -> after: about 1627 -> about 1540 (about 95%). Over 50%: floor table below. The measure is a hand count (no shell beyond the gates), so treat the second figure as +-15 words.

Entries: 39 total, 8 reworded (`re-L*`), 31 unchanged (`u-L*`, whole unit as the carrier). By class (the loader's LEDGER line): ban 16, prose 23 (written `class: ban` on re-L1, re-L7, re-L25, re-L35; `class: prose` on re-L2, re-L6, re-L18, re-L23; the 31 unchanged entries carry no class and the loader infers it). Provenance clauses: 0. Reworded/total: 8/39.

## Reworded entries

| entry | clauses | coverage |
|---|---|---|
| re-L1 | 1 | one phrase; ban span `never from their code` verbatim; anchor `never`, 8/8 stems; the "so we can build our own version from behaviour" tail dropped |
| re-L2 | 1 | one phrase; anchors `github.com/morluto/rea`, `JavaScript/Electron`; 8/8 first stems; the browser/Ghidra feature list dropped |
| re-L6 | 3 | one phrase holds c1-c3 (anchors `binary_session`, `{}`, `result.tool_availability`; 8/8 stems of c3); the "missing engine known before a plan leans on it" tail dropped |
| re-L7 | 1 | ban span `only what the operator named: …our own product` verbatim; 6/8 stems (the heading words "target", "limits" dropped with the bold lead-in) |
| re-L18 | 4 | one phrase; all four clauses' anchors held; c1 loses the "(navigate, click, type), reading page structure, loaded scripts and network requests" tail, past its first 8 stems |
| re-L23 | 1 | one phrase; first 8 stems all held; the tool list shortened |
| re-L25 | 3 | one phrase; c2 ban span `never units` verbatim; c1 8/8, c3 6/8 stems (drops "before or after the fan-out"); `(bundles, captures already taken)` -> `(bundles, captures)` |
| re-L35 | 2 | c1 ban span verbatim; c2 ("that separation is what makes the result our own implementation") labelled `narrative`, the clause's one-line reason, no ban word |

## Pins deleted

None. A grep of `tests/` for `reverse-engineer` found no presence pin on this command's text in the files the ticket lists.

## Vanished labels (author labels — audit owed)

L1, L2, L6, L7, L18, L23, L25, L35: `rule: [re-L<n>]`, each entry's `baseline` equal to that line. No line labelled `narrative` or `duplicate-of`.

## Floor table (why the rest cannot shrink)

| lines | why |
|---|---|
| L3, L4, L5, L12, L21, L28, L30, L31, L32, L34, L45 | ban clauses: the verbatim span runs from the ban word to the end of its `;`/`—` clause, and in L4, L30 and L31 the ban word sits in the first or an early clause so the span is most of the unit (D-1240) |
| L9, L10, L11, L13, L14, L15, L16, L19, L26, L36, L38, L39, L40, L41, L43, L44 | no ban word, but each clause is anchors (backticked tokens, paths, numbers) plus the first 8 stems, and the extra words are the operative conditions (what is checked, who runs it); trimming drops the anchored token or under 6 of 8 stems |
| L8, L20, L24, L27 | short single clauses at or under the 6-stem minimum |

D-191's `Dispatch step (D-191)` marker is read by `assemble_commands.py`'s dispatch grader, so L26 stays whole.

## Self-audit

Read by hand, line by line, baseline against the rewrite and ledger. Pass 1 found and fixed: a duplicated tail in L6 from a bad first edit; L7's bold lead-in had to go for the entry's baseline to match.

COUNTS: 39 entries read / 8 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels

## Failure sets

End state: `tests/test_command_rules.py` 72 passed (LEDGER line for fabrik-reverse-engineer: 39 entries, vanished rule 8, 0 LOSS); `assemble_commands.py --check` exit 1 with one DIFFERS drift line only (no LOSS, no ceiling exit; the render shrank to 7970 words against a 8310 ceiling, for the hub to ratchet). Other groups: 39, 465, 237, 772 (+2 skipped), 349 passed. The agents/dispatch group (`tests/enforcement/test_flip_gate_matrix.py` and five more files) had ONE failure at about 44 tests in (the first file) and then hit the 10-minute background cap, so its failing test id was not read; I could not run it at the start commit (no git), so whether it pre-exists is unproven. No test file was edited.

## LEFT FOR THE HUB

- Own text stays near 95% of the baseline: the command is a dense ban/anchor text (floor table). A further cut needs a D-row on the ban spans, not more rewording.
- Run the author-blind audit pair; the vanished labels are author labels.
- Ratchet `commands/_size_ceiling.json` at merge.
