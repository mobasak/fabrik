## Repo identity — resolve WHERE you are before any repo-dependent decision or git mutation

- `TOP=$(git rev-parse --show-toplevel)` — **abort if empty** (`[ -n "$TOP" ] || stop`): `git -C ""`
  is a documented no-op that silently runs in the CURRENT directory — the exact unpinned behavior
  this guard exists to replace.
- **Worktree test needs NORMALIZED paths** (raw `--git-dir` vs `--git-common-dir` false-positives in
  every subdirectory): `GITDIR=$(git rev-parse --path-format=absolute --git-dir)` and
  `COMMON=$(git rev-parse --path-format=absolute --git-common-dir)`; linked worktree ⇔ `GITDIR ≠ COMMON`.
- **In a linked worktree your repo IDENTITY is the MAIN checkout**, derived as
  `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p')` (the first porcelain record is
  always the main worktree; `$COMMON` itself is a `.git` DIRECTORY, never a checkout) — a worktree of
  `/opt/fabrik` IS the hub; a worktree of a project IS that project.
- **Submodule:** `git rev-parse --show-superproject-working-tree` printing a path means you are in a
  SUBMODULE — its identity is the submodule's OWN repo (`$TOP`); the superproject is a DIFFERENT
  repo — never edit upward into it (the cross-repo HARD STOP).
- **Pin every git mutation** — `git -C "$TOP" …` (or `git -C "$MAIN"` when acting on the main
  checkout) — never rely on the shell's cwd surviving between commands.
