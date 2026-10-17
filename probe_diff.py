import difflib, re, sys
P="/tmp/claude-1000/-opt-fabrik--claude-worktrees-kaizen/5fa5812d-c98c-4c56-9df3-dbace4bf3d57/scratchpad/run-fabrik-review-2026-10-17T18-46-52-0330-286f5b/pin-1/"
S="/tmp/claude-1000/-opt-fabrik--claude-worktrees-kaizen/5fa5812d-c98c-4c56-9df3-dbace4bf3d57/scratchpad/run-fabrik-review-2026-10-17T18-46-52-0330-286f5b/seat-A-haiku/"
files={"hub":("base/CLAUDE.md","CLAUDE.md"),"tmpl":("base/templates/governance/CLAUDE.md","templates/governance/CLAUDE.md")}
W=("and the same holds in every repo wherever a response shows the operator a work-item,")
def norm(p): return " ".join(open(p,encoding="utf-8").read().split())
def toks(t): return t.split(" ")
for k,(b,c) in files.items():
    nb=norm(P+b); nc=norm(P+c)
    print(k, "clause count base/cur:", nb.count("and the same holds in every repo wherever a response shows the operator a work-item, decision, mail or merge-request id: it carries its meaning in plain words at its first mention in that response;"), nc.count("and the same holds in every repo wherever a response shows the operator a work-item, decision, mail or merge-request id: it carries its meaning in plain words at its first mention in that response;"))
    print(k, "glossed pointer count base/cur:", nb.count("`NEXT: operator decision — W-<id> — <what it decides>`"), nc.count("`NEXT: operator decision — W-<id> — <what it decides>`"))
    print(k, "bare pointer followed by backtick base/cur:", nb.count("`NEXT: operator decision — W-<id>`"), nc.count("`NEXT: operator decision — W-<id>`"))
    sm=difflib.SequenceMatcher(None,toks(nb),toks(nc),autojunk=False)
    for op,i1,i2,j1,j2 in sm.get_opcodes():
        if op!="equal": print(k, op, repr(" ".join(toks(nb)[i1:i2])), "->", repr(" ".join(toks(nc)[j1:j2])))
    print(k, "words base/cur", len(toks(nb)), len(toks(nc)))
