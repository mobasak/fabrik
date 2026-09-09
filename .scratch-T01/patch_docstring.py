import pathlib

P = pathlib.Path("scripts/enforcement/check_review_coverage.py")
s = P.read_text(encoding="utf-8")
old = """    subsets of `_FOUND_TOK`, so a joined line can have no readable first run — which is why the
    caller's no-first-run branch is reachable and load-bearing, not decoration.
    \"\"\""""
new = """    subsets of `_FOUND_TOK`, so a joined line can have no readable first run — which is why the
    caller's no-first-run branch is reachable and load-bearing, not decoration.

    RECORDED (round 3, unchanged): a row that NAMES another round and cites its counter in its
    own cell (`| Pass 4 | … found: 1 | fixed: 1 | re-ran as Pass 3 | found: 3 |`) still trips the
    third arm and is refused — the adjudicated fail-CLOSED choice, since it is indistinguishable
    from a real join and fencing the citation is a one-keystroke repair. 0 committed exemplars.
    \"\"\""""
assert s.count(old) == 1
P.write_text(s.replace(old, new), encoding="utf-8")
print("docstring RECORDED clause restored")
