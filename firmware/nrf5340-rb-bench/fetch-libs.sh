#!/bin/bash
# Fetch the libraries in libs.lock at their pinned commits into build/libs/.
# Entries with paths are fetched as a sparse, blob-filtered checkout of only
# those paths (for large repos such as RIOT and Contiki-NG).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build/libs
grep -v '^#' libs.lock | while read -r name url commit paths; do
    [ -n "$name" ] || continue
    dir=build/libs/$name
    if [ ! -d "$dir/.git" ]; then
        if [ -n "$paths" ]; then
            git clone -q --filter=blob:none --no-checkout "$url" "$dir"
            # shellcheck disable=SC2086
            git -C "$dir" sparse-checkout set --no-cone $paths
        else
            git clone -q "$url" "$dir"
        fi
    fi
    # shellcheck disable=SC2086
    [ -n "$paths" ] && git -C "$dir" sparse-checkout set --no-cone $paths
    # fetch only when the pinned commit is not here yet (a fetch per library
    # on every run cost about 20 s, 2026-11-15)
    git -C "$dir" cat-file -e "$commit^{commit}" 2>/dev/null || git -C "$dir" fetch -q origin "$commit" 2>/dev/null || true
    git -C "$dir" -c advice.detachedHead=false checkout -q "$commit"
    [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ] || { echo "$name: wrong commit" >&2; exit 1; }
    echo "$name $(git -C "$dir" rev-parse --short=12 HEAD)"
done

# micoring: generate the config header for its documented SPSC mode, from the
# library's own source-tree header (the CMake option MRING_CONCURRENCY_MODE
# does the same). Kept in build/, never in the repo.
mkdir -p build/gen/micoring
sed 's/^#define MRING_CONCURRENCY_MODE MRING_CONCURRENCY_SINGLE_CONTEXT$/#define MRING_CONCURRENCY_MODE MRING_CONCURRENCY_SPSC_ATOMIC/' \
    build/libs/micoring/include/mring_config.h > build/gen/micoring/mring_config.h
grep -q 'MRING_CONCURRENCY_MODE MRING_CONCURRENCY_SPSC_ATOMIC$' build/gen/micoring/mring_config.h \
    || { echo "micoring: could not select SPSC mode" >&2; exit 1; }
# mring.h includes "mring_config.h" from its own directory first, so put an
# unchanged copy of mring.h next to the generated config.
cp build/libs/micoring/include/mring.h build/gen/micoring/mring.h
