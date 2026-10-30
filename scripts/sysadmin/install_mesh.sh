#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md | docs/workstation/claude-config-backup-restore.md | tests/test_install_mesh.py
# install_mesh.sh [--src DIR] [--dest DIR] — install the REVIEWED, tracked copies of the resume-mesh scripts
# (W-6e656dac T04, spec § Lifecycle): claude-selfwatch.sh, claude-reboot-sweep.sh and claude-mesh-test.sh from
# --src (default: this script's own mesh/ folder) into --dest (default: $HOME/.claude/bin, the live mesh; HOME unset
# and no --dest is a usage error).
#
# Order, all-or-nothing:
#   1. every source file exists and passes `bash -n`;
#   2. the harness is green on the copies being installed (`MESH_TEST_SRC=<src> bash <src>/claude-mesh-test.sh`;
#      MESH_INSTALL_HARNESS names another harness — the tests' stub — and a run that uses one says so on stderr);
#   3. every live file that differs is backed up to <dest>/backups/<f>.backup.<YYYYmmdd-HHMMSS> (a name already
#      taken — a second install in the same second — gets a .<n> suffix, so no backup is ever overwritten) and the
#      backup is compared byte for byte — a backup that fails refuses the install before ANY file is replaced (the
#      DR mirror, scripts/dr_claude_backup.sh, carries ~/.claude/bin whole, backups/ included);
#   4. each file is replaced by a rename of a temp copy in <dest> (mode 0755), so a reader sees the old file or
#      the new one, never half of one. An identical file is left alone and gets no backup. A replace that fails
#      RESTORES every file this run already replaced (from its backup; a file that had none is removed), so no
#      mixed, un-harnessed mesh stays live.
# Exit: 0 installed (or nothing to do); 1 refused (a missing or unparsable source, a red harness, a failed backup
# or replace); 2 usage. Only the operator runs it against the live ~/.claude/bin (T06's gate).
#
# COBRA (D-253): the cheapest pass is a harness that is green because it tested the LIVE files, not the copies —
# so the harness gets MESH_TEST_SRC=<src>, and tests/test_install_mesh.py asserts the src it was handed.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
src="$here/mesh"
dest=""
dest_given=0
usage() { echo "usage: install_mesh.sh [--src DIR] [--dest DIR]" >&2; exit 2; }
while [ $# -gt 0 ]; do
  # an EMPTY value is a usage error (T04 G3): `--dest ""` must never fall back to the live $HOME/.claude/bin
  case "$1" in
    --src) [ $# -ge 2 ] && [ -n "$2" ] || usage; src="$2"; shift 2 ;;
    --dest) [ $# -ge 2 ] && [ -n "$2" ] || usage; dest="$2"; dest_given=1; shift 2 ;;
    *) usage ;;
  esac
done
if [ "$dest_given" = "0" ]; then
  # the default only when --dest was not given: an explicit --dest needs no HOME
  [ -n "${HOME:-}" ] || { echo "install_mesh: HOME is unset — name the destination with --dest" >&2; usage; }
  dest="$HOME/.claude/bin"
fi
files=(claude-selfwatch.sh claude-reboot-sweep.sh claude-mesh-test.sh)
die() { echo "install_mesh: $* — nothing installed" >&2; exit 1; }

for f in "${files[@]}"; do
  [ -f "$src/$f" ] || die "$src/$f is missing"
  bash -n "$src/$f" 2>/dev/null || die "$src/$f fails bash -n"
done
harness="${MESH_INSTALL_HARNESS:-$src/claude-mesh-test.sh}"
if [ "$harness" != "$src/claude-mesh-test.sh" ]; then
  echo "install_mesh: HARNESS OVERRIDDEN by MESH_INSTALL_HARNESS=$harness" >&2
fi
MESH_TEST_SRC="$src" bash "$harness" >&2 || die "the harness ($harness) is red on $src"
mkdir -p "$dest" || die "cannot create $dest"

ts=$(date +%Y%m%d-%H%M%S)
todo=()
declare -A backup=()  # file -> its backup in this run; no entry = the file had no previous version
for f in "${files[@]}"; do
  if [ -f "$dest/$f" ] && cmp -s "$src/$f" "$dest/$f"; then
    echo "install_mesh: $dest/$f is current"
    continue
  fi
  if [ -e "$dest/$f" ]; then
    mkdir -p "$dest/backups" 2>/dev/null
    # claim a name no earlier backup holds: noclobber makes the claim exclusive, so neither a second install in
    # the same second nor a concurrent one overwrites a backup of the ORIGINAL file
    b="$dest/backups/$f.backup.$ts"
    n=0
    until ( set -C; : > "$b" ) 2>/dev/null; do
      n=$(( n + 1 ))
      [ -d "$dest/backups" ] && [ -w "$dest/backups" ] && [ "$n" -le 99 ] || die "the backup of $dest/$f to $b failed"
      b="$dest/backups/$f.backup.$ts.$n"
    done
    if ! { cp -p "$dest/$f" "$b" 2>/dev/null && cmp -s "$dest/$f" "$b"; }; then
      rm -f "$b"
      die "the backup of $dest/$f to $b failed"
    fi
    echo "install_mesh: backed up $dest/$f to $b"
    backup[$f]="$b"
  fi
  todo+=("$f")
done

# restore: put back every file this run replaced — from its backup, or remove it when it was new
restore() {
  local g said=""
  for g in "$@"; do
    if [ -n "${backup[$g]:-}" ]; then
      local t
      t=$(mktemp "$dest/.$g.XXXXXX") && cp "${backup[$g]}" "$t" && chmod 0755 "$t" && mv -f -T "$t" "$dest/$g" \
        && said="$said restored $dest/$g from ${backup[$g]};" \
        || { rm -f "${t:-}"; said="$said COULD NOT restore $dest/$g (its backup is ${backup[$g]});"; }
    else
      rm -f "$dest/$g" && said="$said removed $dest/$g (it was new);" \
        || said="$said COULD NOT remove $dest/$g (it was new);"
    fi
  done
  printf '%s' "${said:- nothing had been replaced yet;}"
}
done_files=()
for f in "${todo[@]}"; do
  tmp=$(mktemp "$dest/.$f.XXXXXX") || {
    echo "install_mesh: cannot write a temp file in $dest —$(restore "${done_files[@]}")" >&2
    exit 1
  }
  if cp "$src/$f" "$tmp" && chmod 0755 "$tmp" && mv -f -T "$tmp" "$dest/$f"; then
    echo "install_mesh: installed $dest/$f"
    done_files+=("$f")
  else
    rm -f "$tmp"
    echo "install_mesh: replacing $dest/$f failed; it is as it was —$(restore "${done_files[@]}") backups in $dest/backups" >&2
    exit 1
  fi
done
exit 0
