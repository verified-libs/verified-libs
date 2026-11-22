#!/usr/bin/env python3
"""Build the public tree from the private repository (DECISIONS 2026-11-12).

Usage: public-export.py OUT_DIR          (OUT_DIR must not exist)
       public-export.py --check          (only report what blocks an export)

Takes the files committed at HEAD (no history, nothing uncommitted),
leaves out the paths in site/embargo-paths.txt, applies the embargo markup
in markdown files (site/embargo_strip.py), and then
refuses if any word from site/embargo.txt (case-insensitive) is still in a
file or a file name. Nothing is pushed or published: the owner does that.

The records under records/ name the commit they were made at. They are
committed after that commit, so it is never the exported one. The export
therefore writes two files: EXPORTED_FROM (the exported commit) and
SAME_SOURCES (the records' commits whose test sources, TEST_SOURCES below,
are those of the exported commit; documentation aside). verify-build.sh
and repeat.sh rebuild a record from the exported tree if its commit is in
one of the two.

A record of a commit with other test sources may be shown if the tree
still builds, byte for byte, the image it was measured from, and runs and
judges it the same way (DECISIONS 2026-11-22). The export takes that from
two things: the host side of the test sources (side() below) is the same at
the record's commit and at HEAD, and records/rebuilt.json
(lab/tools/image-ledger.py: a rebuild of the record from this tree's
sources) says the image matches. Any other record cannot be checked
against the tree, and the export is refused. A stress record of which only
some libraries' images match is refused too, until the page data says per
library which record it rests on.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "site"))
from embargo_strip import strip_embargo   # noqa: E402


# What a record's firmware is built from and run with: firmware/ and the
# lab files its scripts use.
TEST_SOURCES = ["firmware", "lab/boards.conf", "lab/tools/source-commit.sh", "lab/tools/boardpower.sh"]
RECORD_COMMIT = re.compile(r'"(?:source_commit|bench_commit)":\s*"([0-9a-f]{12,40})"|"commits":\s*\[([^\]]*)\]')


def git_id(rev_path):
    r = subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "-q", rev_path], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


# Compiled or linked into an image: a change shows in the image's checksum.
IMAGE_SUFFIXES = (".c", ".h", ".cpp", ".hpp", ".ld", ".mk", ".rs", ".toml", ".lock", ".S", ".s")
LEDGER = "records/rebuilt.json"


def side(path):
    """Which side of the test a file under TEST_SOURCES is on: "image"
    (compiled or linked into an image), None (documentation), or "host"
    (what the images are built, run and judged with: scripts, judges, the
    board table, and every file of a kind not known here)."""
    if path.endswith(".md"):
        return None
    if path.endswith(IMAGE_SUFFIXES) or os.path.basename(path) == "Makefile":
        return "image"
    return "host"


_ids = {}


def source_ids(commit):
    """(all, host): a checksum over the test sources at commit, and over
    their host side alone. (None, None) if the commit is not in the
    repository."""
    if commit not in _ids:
        r = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "-z", commit, "--", *TEST_SOURCES],
                           capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout:
            _ids[commit] = (None, None)
        else:
            entries = sorted(e for e in r.stdout.split("\0") if e and side(e.split("\t", 1)[1]))
            host = [e for e in entries if side(e.split("\t", 1)[1]) == "host"]
            _ids[commit] = tuple(hashlib.sha256("\n".join(x).encode()).hexdigest() for x in (entries, host))
    return _ids[commit]


def same_sources(commit):
    """True if the test sources are the same at commit and at HEAD."""
    a = source_ids(commit)[0]
    return a is not None and a == source_ids("HEAD")[0]


def same_host_side(commit):
    a = source_ids(commit)[1]
    return a is not None and a == source_ids("HEAD")[1]


def ledger():
    """Record file name -> entry of records/rebuilt.json at HEAD, if the
    ledger was made from the test sources of HEAD; else {}."""
    r = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{LEDGER}"], capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    led = json.loads(r.stdout)
    return led.get("records", {}) if led.get("sources") == source_ids("HEAD")[0] else {}


def lines_of(path):
    with open(os.path.join(ROOT, path)) as fh:
        return [l.strip() for l in fh if l.strip() and not l.lstrip().startswith("#")]


def main():
    check_only = sys.argv[1:] == ["--check"]
    if not check_only and (len(sys.argv) != 2 or sys.argv[1].startswith("-")):
        sys.exit(__doc__)   # also for --help: an option is never taken as OUT_DIR
    out = None if check_only else os.path.abspath(sys.argv[1])
    if out and os.path.exists(out):
        sys.exit(f"{out} exists")
    words = [w.lower() for w in lines_of("site/embargo.txt")]
    skip = [p.rstrip("/") for p in lines_of("site/embargo-paths.txt")]
    files = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", "-z", "HEAD"], capture_output=True, check=True,
                           text=True).stdout.split("\0")
    bad, kept, left_out = [], 0, 0
    rec_commits = {}   # commit named by a record under records/ -> the records' (file name, fw_sha256)
    for f in filter(None, files):
        if any(f == p or f.startswith(p + "/") for p in skip):
            left_out += 1
            continue
        data = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{f}"], capture_output=True,
                              check=True).stdout
        try:
            text = data.decode()
        except UnicodeDecodeError:
            text = None
        if text is not None and f.endswith(".md"):
            text = strip_embargo(text)
            data = text.encode()
        hay = (f + "\n" + (text or "")).lower()
        hits = sorted({w for w in words if w in hay})
        if hits:
            bad.append((f, hits))
            continue
        kept += 1
        if text is not None and f.startswith("records/") and f.endswith(".json"):
            found = set()
            for one, many in RECORD_COMMIT.findall(text):
                found.update([one[:12]] if one else re.findall(r"[0-9a-f]{12,40}", many))
            sha = re.search(r'"fw_sha256":\s*"([0-9a-f]{64})"', text)
            for c in found:
                rec_commits.setdefault(c[:12], []).append((os.path.basename(f), sha.group(1) if sha else None))
        if out:
            dst = os.path.join(out, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(data)
            mode = os.stat(os.path.join(ROOT, f)).st_mode if os.path.exists(os.path.join(ROOT, f)) else 0o644
            os.chmod(dst, mode & 0o777)
    same = sorted(c for c in rec_commits if same_sources(c))
    led = ledger()
    rebuilt, other = 0, {}   # other: commit -> [(record, why not)]
    for c in sorted(set(rec_commits) - set(same)):
        for name, sha in rec_commits[c]:
            e = led.get(name)
            if not same_host_side(c):
                why = "the scripts and judges at that commit are not those of HEAD (or the commit is unknown)"
            elif sha is None:
                why = "it has no image checksum, so it is made again when the sources change"
            elif e is None:
                why = f"no rebuild from the sources of HEAD in {LEDGER} (lab/tools/image-ledger.py)"
            elif e.get("fw_sha256") != sha:
                why = f"{LEDGER} holds another checksum for it"
            elif e.get("result") != "match":
                why = "HEAD builds another image" + (f" (libraries {', '.join(e['libs_differ'])})" if e.get("libs_differ") else "")
            else:
                rebuilt += 1
                continue
            other.setdefault(c, []).append((name, why))
    n_other = sum(len(v) for v in other.values())
    print(f"{kept} files clean, {left_out} left out by path, {len(bad)} with embargoed words, "
          f"{n_other} records that cannot be rebuilt from this tree"
          + (f" ({rebuilt} of other commits whose image this tree builds)" if rebuilt else ""))
    for f, hits in bad:
        print(f"  EMBARGO: {f}: {', '.join(hits)}")
    for c, recs in other.items():
        print(f"  RECORDS: {len(recs)} under records/ name commit {c}, whose test sources "
              f"({', '.join(TEST_SOURCES)}) are not those of HEAD:")
        whys = {}
        for name, why in recs:
            whys.setdefault(why, []).append(name)
        for why, names in whys.items():
            print(f"    {len(names)}: {why}, e.g. {names[0]}")
    if bad or other:
        if out:
            print(f"export refused; {out} is incomplete, delete it")
        sys.exit(1)
    if out:
        # The commit the tree is taken from: lab/tools/verify-build.sh rebuilds
        # the records of this commit from a tree without history.
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, check=True,
                              text=True).stdout.strip()
        with open(os.path.join(out, "EXPORTED_FROM"), "w") as fh:
            fh.write(head + "\n")
        # The records' own commits: same test sources as HEAD (checked above).
        with open(os.path.join(out, "SAME_SOURCES"), "w") as fh:
            fh.write("".join(c + "\n" for c in same))


if __name__ == "__main__":
    main()
