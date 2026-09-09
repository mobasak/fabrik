import pathlib, sys
p = pathlib.Path("scripts/enforcement/check_review_coverage.py"); s = p.read_text(encoding="utf-8")
M = {"N1-rewindow": ("cells[i + 1 :]", "cells[i + 1 : i + 3]"),
     "N2-drop-open-guard": (r'_CELL_OPENS_FOUND = re.compile(r"^\s*\**found:\s*\d+(?!\s*\w)")',
                            r'_CELL_OPENS_FOUND = re.compile(r"^\s*\**found:\s*\d")'),
     "N3-drop-found-left": ("""        if not any(_LOOSE_FOUND.search(c) for c in cells[:i]):
            continue""", "        pass")}
old, new = M[sys.argv[1]]; assert s.count(old) == 1, f"{sys.argv[1]}: {s.count(old)}"
p.write_text(s.replace(old, new), encoding="utf-8")
