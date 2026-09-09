import importlib.util
import pathlib

s = importlib.util.spec_from_file_location("crc", "scripts/enforcement/check_review_coverage.py")
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

LS = " "
POS = {
    "r4-1 headed word-trailed": "| Pass 3 | re-derivation | found: 5 issues | fixed: 0 | opus |"
    + LS
    + "| Pass 4 | delta | found: 0 | fixed: 0 | opus |",
    "r4-2 headless": "| R1 | found: 3 issues | fixed: 1 |" + LS + "| R2 | found: 0 | fixed: 0 |",
    "r4-3 both trailed": "| Pass 1 | found: 3 issues | fixed: 1 |"
    + LS
    + "| Pass 2 | found: 0 items | fixed: 0 |",
    "mega joined": "| Pass 1 | f | found: 0 | fixed: 0 |" + LS + "| Pass 2 | f | found: 5 | fixed: 0 |",
    "comma joined": "| Pass 9 | o | found: 0, fixed: 0 |" + LS + "| Pass 10 | o | found: 5, fixed: 0 |",
    "prose joined": "Pass 9: found: 0, fixed: 0" + LS + "Pass 10: found: 5, fixed: 0",
    "cell joined": "| 1 | found: 0 | fixed: 0 |" + LS + "| 2 | found: 5 | fixed: 0 |",
}
NEG = {
    "citing cell": "| Pass 3 | o | found: 0 | fixed: 0 | found: 3 was the round-3 number |",
    "citing prose": "Pass 3: found: 0, fixed: 0 — same as Pass 2",
    "citing tail": "| Pass 4 | o | found: 1 | fixed: 1 | the round-3 row said found: 3 |",
    "citing named round": "| Pass 4 | o | found: 1 | fixed: 1 | re-ran as Pass 3 | found: 3 |",
    "stage line": "| stage | found: 3 issues | found: 4 issues |",
    "empty finders cell": "| Pass 3 | | found: 0 | fixed: 0 |",
    "V1 row": "| Pass 19 | opus | found: 4, new: 2, confirmed: 0, fixed: 0, unexecuted: 0 | d |",
}
CORPUS = {
    "08-11:35": "docs/development/reviews/2026-08-11-plan-2-stalled-midstream-resume-review.md",
    "08-18:304": "docs/development/reviews/2026-08-18-mega-enforcement-e2bf0f6e-review.md",
}
print("POSITIVES (must be joined + refused):")
for name, line in POS.items():
    _t, _p, o, r = m._ledger_shapes(line + "\n")
    print(f"  {name:26} joined={m._joined_row(line)!s:5} rows={[x[:4] for x in o]} refusals={len(r)}")
print("NEGATIVES (must NOT be joined):")
for name, line in NEG.items():
    _t, _p, o, r = m._ledger_shapes(line + "\n")
    print(f"  {name:26} joined={m._joined_row(line)!s:5} rows={[x[:4] for x in o]} refusals={len(r)}")
print("THE TWO COMMITTED ROWS (must NOT be joined):")
for name, path in CORPUS.items():
    n = 35 if "08-11" in name else 304
    line = pathlib.Path(path).read_text(encoding="utf-8").splitlines()[n - 1]
    print(f"  {name:26} joined={m._joined_row(line)!s:5}  {line[:60]}…")
