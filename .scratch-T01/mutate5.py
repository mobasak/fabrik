import pathlib, sys
p = pathlib.Path("scripts/enforcement/check_review_coverage.py")
s = p.read_text(encoding="utf-8")
M = {
 # each CONDITION of the redesigned arm B, one at a time
 "Ma-drop-found-left": ("""        if not any(_LOOSE_FOUND.search(c) for c in cells[:i]):
            continue""", """        pass"""),
 "Mb-drop-opens-right": ("""        if any(_CELL_OPENS_FOUND.match(c) for c in cells[i + 1 : i + 3]):
            return True""", """        return True"""),
 "Mc-widen-right-window": ("cells[i + 1 : i + 3]", "cells[i + 1 :]"),
 # the prose arm's two guards
 "Md-drop-pipeless-guard": ("if not cells and len(_PASS_HEAD_COLON.findall(line)) >= 2:",
                            "if len(_PASS_HEAD_COLON.findall(line)) >= 2:"),
 "Me-colon-head-to-bare": ("_PASS_HEAD_COLON.findall(line)) >= 2", "_PASS_HEAD_TOK.findall(line)) >= 2"),
}
old, new = M[sys.argv[1]]
assert s.count(old) == 1, f"{sys.argv[1]}: anchor count {s.count(old)}"
p.write_text(s.replace(old, new), encoding="utf-8")
