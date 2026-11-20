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
are byte for byte those of the exported commit). verify-build.sh and
repeat.sh rebuild a record from the exported tree if its commit is in one
of the two. A record of a commit with other test sources cannot be rebuilt
from the tree: the export is refused (DECISIONS 2026-11-16: every record
shown at publication is made at the published sources).
"""
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


def same_sources(commit):
    """True if every TEST_SOURCES path is identical at commit and at HEAD."""
    for path in TEST_SOURCES:
        a = git_id(f"{commit}:{path}")
        if a is None or a != git_id(f"HEAD:{path}"):
            return False
    return True


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
    rec_commits = {}   # commit named by a record under records/ -> number of records
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
            for c in found:
                rec_commits[c[:12]] = rec_commits.get(c[:12], 0) + 1
        if out:
            dst = os.path.join(out, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(data)
            mode = os.stat(os.path.join(ROOT, f)).st_mode if os.path.exists(os.path.join(ROOT, f)) else 0o644
            os.chmod(dst, mode & 0o777)
    same = sorted(c for c in rec_commits if same_sources(c))
    other = sorted(c for c in rec_commits if c not in same)
    n_other = sum(rec_commits[c] for c in other)
    print(f"{kept} files clean, {left_out} left out by path, {len(bad)} with embargoed words, "
          f"{n_other} records that cannot be rebuilt from this tree")
    for f, hits in bad:
        print(f"  EMBARGO: {f}: {', '.join(hits)}")
    for c in other:
        print(f"  RECORDS: {rec_commits[c]} under records/ name commit {c}, whose test sources "
              f"({', '.join(TEST_SOURCES)}) are not those of HEAD")
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
