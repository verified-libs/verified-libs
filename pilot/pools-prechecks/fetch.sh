#!/bin/bash
# Fetch the libraries of the pool pre-checks at their pinned commits into LIBS (default
# ~/vl-next/pools-prechecks), one directory each, sparse. Only git runs here;
# the sources are compiled and run inside the toolchain image (run.sh).
# Prints "name commit" per library, for the record of a run.
set -euo pipefail
cd "$(dirname "$0")"
LIBS=${LIBS:-$HOME/vl-next/pools-prechecks}
mkdir -p "$LIBS"
grep -v '^\s*#' libs.lock | while read -r name url commit paths; do
  [ -z "$name" ] && continue
  d="$LIBS/$name"
  if [ "$(git -C "$d" rev-parse HEAD 2>/dev/null)" != "$commit" ]; then
    rm -rf "$d"
    git init -q "$d"
    git -C "$d" remote add origin "$url"
    git -C "$d" sparse-checkout set --no-cone $paths
    timeout 600 git -C "$d" fetch -q --depth 1 --filter=blob:none origin "$commit"
    git -C "$d" checkout -q FETCH_HEAD
  fi
  echo "$name $(git -C "$d" rev-parse HEAD)"
done
