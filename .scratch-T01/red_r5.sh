#!/usr/bin/env bash
# RED-FIRST for round 4: the new tests against the module the seats graded (4187a520), and the
# MUTANT proof for item 2's fall-through on the CURRENT module. Backup first, both halves
# asserted, restored in this same call.
GATE=scripts/enforcement/check_review_coverage.py
BAK=.scratch-T01/gate.r5.bak
PY=/opt/fabrik/.venv/bin/python

cp "$GATE" "$BAK"
echo "backup holds the structural detector: $(grep -c '_HEAD_CELL' "$BAK") (expect >0)"

echo "===== RED RUN A: the round-4 tests on 4187a520 ====="
git show 4187a520:"$GATE" > "$GATE"
echo "4187a520 has _HEAD_CELL: $(grep -c '_HEAD_CELL' "$GATE") (expect 0)"
"$PY" -m pytest tests/enforcement/test_review_confirmed_grammar.py -q \
  -k "word_trailed_counter or no_readable_first_run or two_committed_receipts" 2>&1 | tail -8
cp "$BAK" "$GATE"

echo "===== RED RUN B: the same tests on dc9ac108 (the shipped regression) ====="
git show dc9ac108:"$GATE" > "$GATE"
"$PY" -m pytest tests/enforcement/test_review_confirmed_grammar.py -q \
  -k "word_trailed_counter or no_readable_first_run" 2>&1 | tail -6
cp "$BAK" "$GATE"

echo "===== MUTANT: neuter the no-first-run branch (keep nothing, skip the flush) ====="
"$PY" - <<'PYEOF'
import pathlib
p = pathlib.Path("scripts/enforcement/check_review_coverage.py")
s = p.read_text()
old = """                elif current:
                    tables.append(current)
                    current = []
                continue"""
new = """                # MUTANT
                continue"""
assert s.count(old) == 1
p.write_text(s.replace(old, new))
print("mutant applied")
PYEOF
"$PY" -m pytest tests/enforcement/test_review_confirmed_grammar.py -q -k "no_readable_first_run" 2>&1 | tail -6
cp "$BAK" "$GATE"
echo "restored: $(grep -c '_HEAD_CELL' "$GATE") (expect >0); diff: $(diff -q "$GATE" "$BAK" && echo identical)"
"$PY" -m pytest tests/enforcement/test_review_confirmed_grammar.py -q 2>&1 | tail -3
