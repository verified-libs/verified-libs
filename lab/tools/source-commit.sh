#!/bin/bash
# Print the source commit of the tree that contains DIR (default: .):
# git HEAD (12 hex digits, "+dirty" if tracked files differ), or, in a
# campaign copy without .git, the COMMIT file that night-all.sh writes at
# the top of the copy; "unknown" otherwise. Recorded as source_commit so a
# record's firmware can be rebuilt (and checked against fw_sha256).
d=${1:-.}
if c=$(git -C "$d" rev-parse --short=12 HEAD 2>/dev/null); then
    [ -n "$(git -C "$d" status --porcelain --untracked-files=no 2>/dev/null)" ] && c="$c+dirty"
    echo "$c"
    exit 0
fi
cd "$d" 2>/dev/null || { echo unknown; exit 0; }
while [ "$PWD" != / ]; do
    [ -f COMMIT ] && { cat COMMIT; exit 0; }
    cd ..
done
echo unknown
