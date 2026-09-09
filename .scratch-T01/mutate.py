import pathlib, sys
p = pathlib.Path("scripts/enforcement/check_review_coverage.py")
s = p.read_text(encoding="utf-8")
which = sys.argv[1]
M = {
 "M1": ("""            if _joined_row(line):
                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                pair = _first_run(line, _second_row_pos(line))
                if pair is not None:
                    row = (pair[0], None, pair[1], None, line)
                    current.append(row)
                    ordered.append(row)
                elif current:
                    tables.append(current)
                    current = []
                continue""",
        """            joined = _first_run(line) if _joined_row(line) else None
            if joined is not None:
                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                row = (joined[0], None, joined[1], None, line)
                current.append(row)
                ordered.append(row)
                continue"""),
 "M2": ("""                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                pair = _first_run(line, _second_row_pos(line))
                if pair is not None:
                    row = (pair[0], None, pair[1], None, line)
                    p_run.append(row)
                    ordered.append(row)""",
        """                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                pair = _first_run(line)
                if pair is not None:
                    row = (pair[0], None, pair[1], None, line)
                    p_run.append(row)
                    ordered.append(row)"""),
 "M3": ("""        if sum(1 for c in cells if _HEAD_CELL.fullmatch(c.strip())) >= 2:
            return True""",
        """        if True:
            return True"""),
}
old, new = M[which]
assert s.count(old) == 1, f"{which}: anchor not unique ({s.count(old)})"
p.write_text(s.replace(old, new), encoding="utf-8")
print(f"{which} applied")
