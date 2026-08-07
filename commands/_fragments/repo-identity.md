### Repo identity — resolve WHERE you are before any repo-dependent decision or git mutation

Run these once, up front (the failure class: a linked worktree or persistent shell cwd sending
reads/writes into the wrong tree):

- `TOP=$(git rev-parse --show-toplevel)` and `COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)`.
- **Linked worktree** (`git-dir` ≠ `git-common-dir`): your repo IDENTITY is the COMMON checkout's
  repo — a worktree of `/opt/fabrik` IS the hub; a worktree of a project IS that project.
- **Submodule guard:** if `git rev-parse --show-superproject-working-tree` prints a path, you are in
  a SUBMODULE, not a worktree — treat it as a normal repo of the superproject before concluding
  anything from the dir layout.
- **Pin every git mutation** — `git -C "$TOP" …` (or the common checkout's toplevel when acting on
  the main tree) — never rely on the shell's current directory surviving between commands.
