#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md | docs/workstation/claude-config-backup-restore.md | tests/test_install_mesh.py
# install_mesh.sh [--src DIR] [--dest DIR] — install the REVIEWED, tracked copies of the resume-mesh scripts
# (W-6e656dac T04, spec § Lifecycle): claude-selfwatch.sh, claude-reboot-sweep.sh and claude-mesh-test.sh from
# --src (default: this script's own mesh/ folder) into --dest (default: $HOME/.claude/bin, the live mesh).
#
# Order, all-or-nothing up to the first replace:
#   1. every source file exists and passes `bash -n`;
#   2. the harness is green on the copies being installed (`MESH_TEST_SRC=<src> bash <src>/claude-mesh-test.sh`;
#      MESH_INSTALL_HARNESS names another harness — the tests' stub);
#   3. every live file that differs is backed up to <dest>/backups/<f>.backup.<YYYYmmdd-HHMMSS> and the backup is
#      compared byte for byte — a backup that fails refuses the install before ANY file is replaced (the DR mirror,
#      scripts/dr_claude_backup.sh, carries ~/.claude/bin whole, backups/ included);
#   4. each file is replaced by a rename of a temp copy in <dest> (mode 0755), so a reader sees the old file or
#      the new one, never half of one. An identical file is left alone and gets no backup.
# Exit: 0 installed (or nothing to do); 1 refused (a missing or unparsable source, a red harness, a failed backup
# or replace); 2 usage. Only the operator runs it against the live ~/.claude/bin (T06's gate).
#
# COBRA (D-253): the cheapest pass is a harness that is green because it tested the LIVE files, not the copies —
# so the harness gets MESH_TEST_SRC=<src>, and tests/test_install_mesh.py asserts the src it was handed.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
src="$here/mesh"
dest="${HOME:?HOME is unset}/.claude/bin"
usage() { echo "usage: install_mesh.sh [--src DIR] [--dest DIR]" >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --src) [ $# -ge 2 ] || usage; src="$2"; shift 2 ;;
    --dest) [ $# -ge 2 ] || usage; dest="$2"; shift 2 ;;
    *) usage ;;
  esac
done
files=(claude-selfwatch.sh claude-reboot-sweep.sh claude-mesh-test.sh)
die() { echo "install_mesh: $* — nothing installed" >&2; exit 1; }

for f in "${files[@]}"; do
  [ -f "$src/$f" ] || die "$src/$f is missing"
  bash -n "$src/$f" 2>/dev/null || die "$src/$f fails bash -n"
done
harness="${MESH_INSTALL_HARNESS:-$src/claude-mesh-test.sh}"
MESH_TEST_SRC="$src" bash "$harness" >&2 || die "the harness ($harness) is red on $src"
mkdir -p "$dest" || die "cannot create $dest"

ts=$(date +%Y%m%d-%H%M%S)
todo=()
for f in "${files[@]}"; do
  if [ -f "$dest/$f" ] && cmp -s "$src/$f" "$dest/$f"; then
    echo "install_mesh: $dest/$f is current"
    continue
  fi
  if [ -e "$dest/$f" ]; then
    mkdir -p "$dest/backups" 2>/dev/null
    b="$dest/backups/$f.backup.$ts"
    { cp -p "$dest/$f" "$b" 2>/dev/null && cmp -s "$dest/$f" "$b"; } || die "the backup of $dest/$f to $b failed"
    echo "install_mesh: backed up $dest/$f to $b"
  fi
  todo+=("$f")
done
for f in "${todo[@]}"; do
  tmp=$(mktemp "$dest/.$f.XXXXXX") || { echo "install_mesh: cannot write a temp file in $dest" >&2; exit 1; }
  if cp "$src/$f" "$tmp" && chmod 0755 "$tmp" && mv -f -T "$tmp" "$dest/$f"; then
    echo "install_mesh: installed $dest/$f"
  else
    rm -f "$tmp"
    echo "install_mesh: replacing $dest/$f failed; it is as it was (backups in $dest/backups)" >&2
    exit 1
  fi
done
exit 0
