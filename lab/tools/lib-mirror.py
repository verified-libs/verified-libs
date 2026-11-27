#!/usr/bin/env python3
"""A local mirror of every pinned library, so that the rebuilds of the export
test and of the ledger do not depend on the network at the time they run.

Usage: lab/tools/lib-mirror.py fill  [DIR]   fetch what the mirror lacks (network), then check
       lab/tools/lib-mirror.py check [DIR]   only check: every pin of the lock files is in it, whole
       lab/tools/lib-mirror.py env   [DIR]   check, then print the environment that sends the fetches there

DIR: default $VL_LIB_MIRROR, else ~/vl-scratch/lib-mirror.

The pins are those of this tree's lock files (LOCKS: the version 2 benchmark's,
the CRC kind's and the pools kind's): name, URL, commit. The mirror holds one
bare repository per URL with each pinned commit fetched whole (depth 1, every
object of its tree) and a ref per pin, so that a clone, a fetch of the commit
and a blob-filtered fetch from it all work. The check is the commit ids: every
pinned commit must be in its repository, with every object of its tree (git
rev-list --objects --missing=print), since git checks each object's id as it
stores it.

The fetch scripts are not changed (firmware/nrf5340-rb-bench/fetch-libs.sh,
kinds/*/fetch.sh: the published fetch path for readers stays as it is). The
environment `env` prints sends git there instead, for the processes it is set
in only: url.<mirror>.insteadOf=<URL> per URL (GIT_CONFIG_COUNT/KEY/VALUE), and
GIT_ALLOW_PROTOCOL=file, so that a fetch the mirror cannot serve fails at
once instead of going to the network. The repositories refuse blob filters
(uploadpack.allowFilter false): a blob-filtered clone from a shallow mirror
would fetch its missing blobs lazily, have them rejected (shallow roots) and
nest one lazy fetch in the next without end (2026-11-27: some 520 levels, the
host out of memory). So the clients get every blob of the pin at once, and
GIT_NO_LAZY_FETCH=1 makes any lazy fetch that is still tried fail instead of
nest. lab/tools/test-lib-mirror.sh checks both, bounded.

Exit: 0 the mirror holds every pin (env: printed), 1 it does not (each missing
pin printed: "could not fetch" when fill could not get it), 2 usage.
"""
import hashlib
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOCKS = ["firmware/nrf5340-rb-bench/libs.lock", "kinds/crc/libs.lock", "kinds/pools/libs.lock"]
TRIES = 3
REPO_CONFIG = (("uploadpack.allowFilter", "false"), ("uploadpack.allowAnySHA1InWant", "true"),
               ("uploadpack.allowReachableSHA1InWant", "true"))


def pins():
    """(url, commit, name, lock file) for every line of the lock files"""
    out = []
    for lock in LOCKS:
        with open(os.path.join(ROOT, lock)) as fh:
            for line in fh:
                f = line.split()
                if not f or f[0].startswith("#"):
                    continue
                if len(f) < 3 or not re.fullmatch(r"[0-9a-f]{40}", f[2]):
                    sys.exit(f"{lock}: a line without a full commit id: {line.strip()}")
                out.append((f[1], f[2], f[0], lock))
    return out


def repo_of(mirror, url):
    tail = re.sub(r"[^A-Za-z0-9._-]+", "_", url.rstrip("/").rsplit("/", 1)[-1])
    return os.path.join(mirror, f"{hashlib.sha256(url.encode()).hexdigest()[:12]}-{tail}")


def git(*args, check=False, timeout=None):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check, timeout=timeout,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


def whole(repo, commit):
    """the commit is in repo with every object of its tree"""
    if git("-C", repo, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return False
    r = git("-C", repo, "rev-list", "--objects", "--missing=print", "-1", commit)
    return r.returncode == 0 and not any(l.startswith("?") for l in r.stdout.splitlines())


def check(mirror, p):
    bad = []
    for url, commit, name, lock in p:
        repo = repo_of(mirror, url)
        if not os.path.isdir(repo) or not whole(repo, commit):
            bad.append(f"{lock}: {name} {commit[:12]} ({url}): not in the mirror {repo}")
        elif git("-C", repo, "rev-parse", "-q", "--verify", f"refs/pins/{commit}").stdout.strip() != commit:
            bad.append(f"{lock}: {name} {commit[:12]}: no ref refs/pins/{commit} in {repo}")
        elif any(git("-C", repo, "config", "--get", k).stdout.strip() != v for k, v in REPO_CONFIG):
            bad.append(f"{lock}: {name}: {repo} is not configured as a mirror (lib-mirror.py fill sets it)")
    return bad


def fill(mirror, p):
    os.makedirs(mirror, exist_ok=True)
    failed = []
    for url, commit, name, lock in p:
        repo = repo_of(mirror, url)
        if not os.path.isdir(repo):
            git("init", "-q", "--bare", repo, check=True)
        # allowFilter false: a client's --filter=blob:none is ignored, so it gets every blob of the pin at once and
        # never fetches lazily (from a shallow mirror a lazy fetch's objects are rejected and the fetch nests in
        # itself without end: 2026-11-27, ~520 levels, out of memory)
        for k, v in REPO_CONFIG + (("vl.url", url),):
            git("-C", repo, "config", k, v, check=True)
        if not whole(repo, commit):
            err = ""
            for _ in range(TRIES):
                try:
                    r = git("-C", repo, "fetch", "-q", "--depth", "1", url, commit, timeout=1200)
                    err = r.stderr.strip()
                except subprocess.TimeoutExpired:
                    err = "timed out after 1200 s"
                if whole(repo, commit):
                    break
            else:
                failed.append(f"{lock}: {name} {commit[:12]} ({url}): could not fetch: {err.splitlines()[-1] if err else 'no error text'}")
                continue
        git("-C", repo, "update-ref", f"refs/pins/{commit}", commit, check=True)
        # a clone takes the branches and HEAD: one branch per pin, HEAD on one of them
        git("-C", repo, "update-ref", f"refs/heads/pin-{commit}", commit, check=True)
        git("-C", repo, "symbolic-ref", "HEAD", f"refs/heads/pin-{commit}", check=True)
        print(f"{name} {commit[:12]}: in the mirror", flush=True)
    return failed


def env(mirror, p):
    urls = sorted({u for u, _, _, _ in p})
    # GIT_NO_LAZY_FETCH: should a fetch still miss an object, it fails at once instead of fetching it lazily
    e = {"GIT_CONFIG_COUNT": str(len(urls)), "GIT_ALLOW_PROTOCOL": "file", "GIT_NO_LAZY_FETCH": "1"}
    for i, u in enumerate(urls):
        e[f"GIT_CONFIG_KEY_{i}"] = f"url.file://{repo_of(mirror, u)}.insteadOf"
        e[f"GIT_CONFIG_VALUE_{i}"] = u
    return e


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("fill", "check", "env") or len(a) > 2:
        sys.exit(__doc__)
    mirror = os.path.abspath(os.path.expanduser(a[1] if len(a) == 2 else
                                                os.environ.get("VL_LIB_MIRROR", "~/vl-scratch/lib-mirror")))
    p = pins()
    failed = fill(mirror, p) if a[0] == "fill" else []
    bad = failed or check(mirror, p)
    if bad:
        print("\n".join(bad), file=sys.stderr)
        print(f"{mirror}: {len(bad)} of {len(p)} pins missing", file=sys.stderr)
        return 1
    if a[0] == "env":
        for k, v in env(mirror, p).items():
            print(f"export {k}={shlex.quote(v)}")
    else:
        print(f"{mirror}: all {len(p)} pins of {len(LOCKS)} lock files, whole ({len({u for u, *_ in p})} repositories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
